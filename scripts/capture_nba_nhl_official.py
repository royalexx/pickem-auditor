#!/usr/bin/env python3
"""Capture ONLY verified FINAL NBA/NHL boxscores for a frozen Phase 1 cohort.

Writes NEW append-only research artifacts. Never overwrites the 2026-11-10
pregame forecast, uses live in-progress player counts as results, or supplies
missing outcome values. Official IDs are matched by unique teams AND start.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen,Request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.official_nba_nhl_capture import (
    SettlementCaptureError, original_event_scope, schedule_games,
    match_schedule, settlement_rows_for_final, instant)

SCHEDULE_URLS={
 "NBA":"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={yyyymmdd}",
 "NHL":"https://api-web.nhle.com/v1/schedule/{date}",
}


def fetch_raw(url):
    if not (url.startswith("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/")
            or url.startswith("https://api-web.nhle.com/v1/")):
        raise SettlementCaptureError("unallowlisted_official_url")
    with urlopen(Request(url,headers={
            "User-Agent":"PickemAuditor/2.5 (official-source-audit)",
            "Accept":"application/json",
        }),timeout=35) as response:
        if response.status!=200:
            raise SettlementCaptureError("official_source_http_not_200")
        payload=response.read(12_000_001)
        if len(payload)>12_000_000:raise SettlementCaptureError("oversized_official_source")
        collected=datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")
    return payload, collected


def json_source(raw):
    try: return json.loads(raw)
    except (ValueError,UnicodeError) as exc:
        raise SettlementCaptureError("provider_nonjson_source") from exc


def _write_new(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb") as file:file.write(raw)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase1",type=Path,required=True)
    parser.add_argument("--date",required=True,help="original sports slate local YYYY-MM-DD")
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error("cannot_overwrite_prior_official_settlement_capture")
    # No manual source URL, identity override, paid API or outcome injection.
    try:
        date=datetime.strptime(args.date,"%Y-%m-%d").date()
        raw_phase1=args.phase1.read_bytes()
        source=json.loads(raw_phase1)
        from v2.phase15_nhl_nba import diagnose
        diagnose(source)
        scoped=original_event_scope(source["contracts"])
        if len({group["start"].date() for group in scoped.values()})>2:
            raise SettlementCaptureError("multiple_dates_in_one_snapshot")
        if not scoped:raise SettlementCaptureError("empty_source_cohort")
        # All games fall on selected Toronto/North American slate date.
        if not all(group["start"].date() in (date,date+timedelta(days=1))
                   for group in scoped.values()):
            raise SettlementCaptureError("source_event_dates_mismatch")
        raw_schedules={}
        observed_schedules={}
        indexed=[]
        for sport in ("NBA","NHL"):
            url=SCHEDULE_URLS[sport].format(date=args.date,yyyymmdd=args.date.replace("-",""))
            payload,clock=fetch_raw(url)
            raw_schedules[sport]=(payload,url)
            observed_schedules[sport]=clock
            indexed+=schedule_games(sport,json_source(payload),game_date=args.date)
        matching=match_schedule(scoped,indexed)
        game_ledger=[]
        pending_reasons=Counter()
        outputs=[]
        unresolved=[]
        raw_sources=[]
        for group_key,group in sorted(scoped.items()):
            sport,event_id=group_key
            official_id=matching.get(group_key)
            status=next((x["status"] for x in indexed if x["id"]==official_id
                         and x["sport"]==sport),"UNMATCHED")
            entry={"sport":sport,"original_event_id":event_id,
                   "original_contract_count":len(group["contracts"]),
                   "official_event_id":official_id,
                   "official_schedule_status":status}
            if official_id is None:
                entry["settlement_status"]="blocked_unmatched_official_schedule"
                pending_reasons[entry["settlement_status"]]+=len(group["contracts"])
            elif status not in ("FINAL", "OFF"):
                entry["settlement_status"]="pending_game_not_final"
                pending_reasons[entry["settlement_status"]]+=len(group["contracts"])
            else:
                url=(f"https://api-web.nhle.com/v1/gamecenter/{official_id}/boxscore"
                     if sport=="NHL" else
                     f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={official_id}")
                payload,observed=fetch_raw(url)
                digest=hashlib.sha256(payload).hexdigest()
                rel=f"{sport.lower()}_{official_id}_boxscore_{digest[:16]}.json"
                try:
                    out,bad=settlement_rows_for_final(
                        group,json_source(payload),game_id=official_id,
                        url=url,raw_digest=digest,source_path=rel,observed_at=observed)
                except (SettlementCaptureError,KeyError,TypeError,ValueError) as exc:
                    entry["settlement_status"]="blocked_invalid_official_final_source"
                    entry["failure_reason"]=str(exc)
                    pending_reasons[entry["settlement_status"]]+=len(group["contracts"])
                else:
                    outputs+=out
                    unresolved+=bad
                    raw_sources.append((rel,payload))
                    entry["settlement_status"]="partially_settled" if bad else "settled_all_observed"
                    entry["actual_settled_rows"]=len(out)
                    entry["unavailable_rows"]=len(bad)
                    entry["official_source_sha256"]=digest
                    pending_reasons["player_unresolved_in_official_final"]+=len(bad)
            game_ledger.append(entry)
        # Validate that the exporter cannot accidentally settle a different
        # player/stat/event than the original frozen cohort.
        whitelist={(c["sport"],str(c["event_id"]),str(c["player_id"]),c["stat"])
                   for c in source["contracts"]}
        actual_keys=[(s["sport"],s["event_id"],s["player_id"],s["stat"])
                     for s in outputs]
        if set(actual_keys)-whitelist or len(actual_keys)!=len(set(actual_keys)):
            raise SettlementCaptureError("unmatched_or_duplicate_output_settlement")
        if len(outputs)>len(source["contracts"]):
            raise SettlementCaptureError("outcomes_exceed_original_cohort")
        # Only create output after successful parsing and exact verification.
        base=args.output_dir
        base.mkdir(parents=True)
        storage=base/"official_source_raw"
        storage.mkdir()
        for sport,(payload,url) in raw_schedules.items():
            _write_new(storage/f"{sport.lower()}_schedule_{hashlib.sha256(payload).hexdigest()[:16]}.json",payload)
        for rel,payload in raw_sources:_write_new(storage/rel,payload)
        settlement_bytes=(json.dumps(outputs,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()
        _write_new(base/"official_settlements.json",settlement_bytes)
        _write_new(base/"unresolved_players.json",(json.dumps(unresolved,indent=2,sort_keys=True)+"\n").encode())
        manifest={
            "schema":"v25_official_nba_nhl_settlement_capture_v1",
            "original_phase1_report_sha256":source["report_sha256"],
            "original_phase1_receipt_bytes_sha256":hashlib.sha256(raw_phase1).hexdigest(),
            "original_game_date":args.date,
            "source_schedules":[{"sport":sport,"url":raw_schedules[sport][1],
                 "retrieved_at":observed_schedules[sport],
                 "sha256":hashlib.sha256(raw_schedules[sport][0]).hexdigest()}
                 for sport in ("NBA","NHL")],
            "games":game_ledger,
            "candidate_contracts":len(source["contracts"]),
            "settled_player_stat_contracts":len(outputs),
            "original_pairs_not_settled":len(source["contracts"])-len(outputs),
            "pending_or_unresolved_reasons":dict(pending_reasons),
            "source_archive_root":"official_source_raw",
            "settlement_rows_sha256":hashlib.sha256(settlement_bytes).hexdigest(),
            "no_original_forecast_mutation":True,
            "not_a_betting_release":True,
        }
        _write_new(base/"capture_manifest.json",(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode())
        print(json.dumps({"output":str(base),"settled":len(outputs),
                "original_contracts":len(source["contracts"]),
                "pending":len(source["contracts"])-len(outputs),
                "schedule_statuses":{e["original_event_id"]:e["settlement_status"]
                                     for e in game_ledger},
                "manifest_sha256":hashlib.sha256((base/"capture_manifest.json").read_bytes()).hexdigest()},
                sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError,KeyError,OverflowError) as exc:
        print("OFFICIAL_CAPTURE_BLOCKED "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
