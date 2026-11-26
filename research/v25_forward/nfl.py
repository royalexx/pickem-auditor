"""Date-agnostic bounded NFL original-source capture for future slates.

Acquires ESPN scoreboard/rosters/depth/injuries/historical FINAL bytes and one
quota-guarded original PropLine offer snapshot per calendar date. Creates no
probabilities or retrospective claims. Long-running one-job-per-day worker
waits for original pregame capture windows; cannot backfill earlier kickoffs.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
import unicodedata

from v2.nba_ws1.store import instant
from v2.p0_integrity.storage import attest_project_storage

TZ = ZoneInfo("America/Toronto")
ROOT = "reports/nfl_forward_original"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
PROPLINE = "https://api.prop-line.com"
STATS = {"pass attempts", "completions", "passing yards", "rush attempts",
         "rushing yards", "receptions", "receiving yards", "tackles + assists"}
FORWARD_WINDOW_OPEN = timedelta(minutes=60)
HARD_FREEZE_GAP = timedelta(minutes=30)


def now():
    return datetime.now(timezone.utc)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(path, document):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf8") as out:
        json.dump(document,out,sort_keys=True,indent=2,allow_nan=False)
        out.write("\n")


def source(url, folder, *, kind, headers=None, opener=None):
    """Original bytes written before model parsing. Only approved HTTPS providers."""
    p=urlsplit(url)
    if p.scheme!="https" or p.hostname not in ("site.api.espn.com","api.prop-line.com"):
        raise ValueError("SOURCE_HOST_NOT_APPROVED")
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    start=now().isoformat()
    if opener:
        raw=opener(url,headers or {})
    else:
        req=Request(url,headers={"User-Agent":"pickem-nfl-forward-research/1","Accept":"application/json",**(headers or {})})
        with urlopen(req,timeout=18) as response:
            if response.status!=200:raise ValueError("SOURCE_HTTP_STATUS")
            raw=response.read(6*1024*1024+1)
    if len(raw)>6*1024*1024 or not raw:
        raise ValueError("SOURCE_SIZE_BOUND")
    received=now().isoformat()
    digest=sha(raw);rawpath=folder/(digest+".json.gz")
    if not rawpath.exists():
        with rawpath.open("xb") as out:out.write(gzip.compress(raw,mtime=0))
    if sha(gzip.decompress(rawpath.read_bytes()))!=digest:
        raise ValueError("ARCHIVED_ORIGINAL_BYTES_CHANGED")
    record={"kind":kind,"url":url,"request_started_at":start,
            "received_at":received,"original_raw_sha256":digest,
            "bytes":len(raw),"relative_archive":rawpath.name,
            "publication_clock_unverified":True}
    return json.loads(raw),record


def _name(value):
    return re.sub(r"[^a-z0-9]","",unicodedata.normalize("NFKD",str(value or "")).encode("ascii","ignore").decode().lower())


def board_for_day(day,folder,fetch=None):
    board,rec=source(ESPN+"/scoreboard?dates="+day.replace("-","")+"&limit=100",
                     folder,kind="espn_scoreboard",opener=fetch)
    games=[]
    for event in board.get("events",[]):
        try:
            comp=event["competitions"][0]
            players=comp["competitors"]
            teams={x["homeAway"]:{"id":str(x["team"]["id"]), "abbr":x["team"]["abbreviation"]} for x in players}
            start=instant(event["date"])
            if start.astimezone(TZ).date().isoformat()!=day:
                continue
            if len(teams)!=2 or "home" not in teams or "away" not in teams:
                continue
            games.append({"event_id":str(event["id"]),"event_start_at":start.isoformat(),
                          "home":teams["home"],"away":teams["away"],
                          "board_receipt":rec["original_raw_sha256"],
                          "provider_status_at_capture":(comp.get("status") or {}).get("type",{}).get("name")})
        except (ValueError,TypeError,KeyError,IndexError):
            continue
    return sorted(games,key=lambda x:(x["event_start_at"],x["event_id"])),rec


def safe_original_quote_snapshot(day,folder,fetch=None):
    """One original sportsbook pull daily, never a synthetic odds fallback."""
    key=os.environ.get("PROPLINE_API_KEY","")
    if not key:
        return {"status":"BLOCKED_PROPLINE_CREDENTIAL_ABSENT","quotes":[],"receipts":[]}
    scripts=Path(__file__).resolve().parents[2]/"scripts"
    if str(scripts) not in sys.path:sys.path.insert(0,str(scripts))
    from odds_providers import PropLineProvider
    records=[]
    def transport(url,timeout=15,headers=None):
        if urlsplit(url).hostname != "api.prop-line.com":
            raise ValueError("UNAPPROVED_ODDS_HOST")
        d,r=source(url,folder,kind="original_propline_two_sided",headers=headers,opener=fetch)
        # Do NOT publish API keys in receipts; only URL and raw data SHA.
        records.append(r)
        return d
    os.environ["PICKEM_ODDS_QUOTA_GUARD"]="1"
    provider=PropLineProvider(api_key=key,fetch=transport)
    quotes=provider.fetch(day,sports=["NFL"])
    return {"status":"ORIGINAL_SOURCE_QUOTED" if quotes else "NO_VALID_ORIGINAL_QUOTES",
            "quotes":quotes,"receipts":records,"provider_note":provider.note,
            "quote_count":len(quotes)}


def _roster_entries(data):
    athletes=[]
    for group in data.get("athletes",[]):
        if "items" in group:athletes+=group["items"]
        elif "athletes" in group:athletes+=group["athletes"]
    out={}
    for item in athletes:
        p=item.get("athlete",item)
        pid=str(p.get("id") or "")
        if pid and (p.get("displayName") or p.get("fullName")):
            out.setdefault(_name(p.get("fullName") or p.get("displayName")),[]).append(pid)
    return out


def capture_game(game,day,root,quote,*,fetch=None,at=None):
    at=at or now()
    start=instant(game["event_start_at"])
    base=Path(root)/("event_"+game["event_id"])
    if start-FORWARD_WINDOW_OPEN>at or at>=start-HARD_FREEZE_GAP:
        return {"event_id":game["event_id"],"status":"NOT_IN_ORIGINAL_WINDOW",
                "timestamp":at.isoformat()}
    base.mkdir(parents=True,exist_ok=True)
    try:
        once(base/"ACQUISITION_CLAIM.json",{"created_at":at.isoformat(),"game":game})
    except FileExistsError:
        return {"event_id":game["event_id"],"status":"ALREADY_CLAIMED_NO_RETRY"}
    receipts=[];errors=[];context={}
    try:
        board,receipt=board_for_day(day,base/"sources",fetch=fetch)
        receipts.append(receipt)
        current=[g for g in board if g["event_id"]==game["event_id"]]
        if len(current)!=1 or any(current[0][k]!=game[k] for k in ("event_start_at","home","away")):
            raise ValueError("GAME_SCHEDULE_CHANGED_DURING_WINDOW")
        for team in (game["home"],game["away"]):
            tid=team["id"];ab=team["abbr"]
            for kind in ("roster","depthcharts","injuries"):
                url=ESPN+"/teams/"+tid+"/"+kind
                try:
                    doc,receipt=source(url,base/"sources",kind="ESPN_"+ab+"_"+kind,opener=fetch)
                    receipts.append(receipt);context[(ab,kind)]=doc
                except Exception as exc:
                    errors.append({"team":ab,"source":kind,"error":type(exc).__name__+":"+str(exc)})
        roster={}
        for team in (game["home"],game["away"]):
            ab=team["abbr"];data=context.get((ab,"roster"),{})
            roster[ab]=_roster_entries(data)
        quotes=[];reject=[]
        if quote["status"]=="ORIGINAL_SOURCE_QUOTED":
            for obj in quote["quotes"]:
                if obj.get("sport")!="NFL" or obj.get("stat") not in STATS:
                    continue
                names={_name(obj.get("player"))}
                positions=[(t["abbr"],player) for t in (game["home"],game["away"])
                           for name in names for player in roster.get(t["abbr"],{}).get(name,[])]
                # A quote without a source-recoverable player/game mapping is
                # a rejected observation, not silently joined by name alone.
                try:
                    target=instant(obj["event_start"]) if obj.get("event_start") else None
                except ValueError:
                    target=None
                pair=set(obj.get("event_teams") or [])
                expected={game["home"]["abbr"],game["away"]["abbr"]}
                if pair!=expected or target!=start:
                    continue
                if len(positions)!=1:
                    reject.append({"player":obj.get("player"),"book":obj.get("book"),
                                   "stat":obj.get("stat"),"reason":"UNRESOLVED_UNIQUE_ESPN_PLAYER_ID"})
                    continue
                team,player=positions[0]
                pricefields=("line","over_odds","under_odds")
                if any(obj.get(k) is None for k in pricefields):
                    reject.append({"player":obj.get("player"),"stat":obj.get("stat"),
                                   "reason":"ORIGINAL_TWO_SIDED_PRICE_MISSING"})
                    continue
                key=json.dumps({"game":game["event_id"],"player":player,
                                "stat":obj["stat"],"book":obj["book"],
                                "line":obj["line"],"over":obj["over_odds"],
                                "under":obj["under_odds"],"raw_first":quote["receipts"][0]["original_raw_sha256"]
                                if quote["receipts"] else None},sort_keys=True)
                quote_id=sha(json.dumps(obj,sort_keys=True,default=str).encode())
                quotes.append({"contract_id":sha(key.encode()),"original_quote_id":quote_id,
                               "event_id":game["event_id"],
                               "team":team,"player_id":player,
                               "stat":obj["stat"],"book":obj["book"],
                               "line":obj["line"],"over_odds":obj["over_odds"],
                               "under_odds":obj["under_odds"],"original_offer":obj,
                               "original_offer_source_sha256":quote["receipts"][0]["original_raw_sha256"]
                               if quote["receipts"] else None,
                               "original_offer_first_received_at":quote["receipts"][0]["received_at"]
                               if quote["receipts"] else None})
        captured_at=now()
        if captured_at>=start-HARD_FREEZE_GAP:
            raise ValueError("ORIGINAL_CAPTURE_COMPLETED_AFTER_T_MINUS_30")
        snapshot={"schema":"NFLForwardOriginalEvent/1","event":game,
                  "source_received_at":captured_at.isoformat(),
                  "source_receipts":receipts,"original_offer_receipts":quote["receipts"],
                  "contracts":quotes,"rejected_quote_candidates":reject,
                  "roster_source_kind":"ESPN reported team membership, not game-active eligibility",
                  "injury_source_kind":"ESPN report, not official game-day inactives",
                  "source_errors":errors,
                  "model_forecasts":None,"model_status":"NO_NEW_ENGINE_FORECAST_FROZEN"}
        once(base/"snapshot.json",snapshot)
        raw=(base/"snapshot.json").read_bytes()
        once(base/"FIRST_CAPTURE.json",{"snapshot":"snapshot.json","sha256":sha(raw),
                                       "completed_at":captured_at.isoformat(),
                                       "original_contracts":len(quotes)})
        return {"event_id":game["event_id"],"status":"ORIGINAL_RESEARCH_SNAPSHOT",
                "contract_count":len(quotes),"unknown_eligibility":True}
    except Exception as exc:
        result={"event_id":game["event_id"],"status":"BLOCKED_CAPTURE_FIRST_CLAIM_PRESERVED",
                "reason":type(exc).__name__+":"+str(exc)}
        once(base/"blocked.json",result)
        return result


def run(day=None,storage="/work",dry_run=False,wait=True,fetch=None,resume=False):
    at=now();day=day or at.astimezone(TZ).date().isoformat()
    if not dry_run and day != at.astimezone(TZ).date().isoformat():
        raise ValueError("LIVE_DATE_CANNOT_BE_BACKDATED")
    if not (2026<=int(day[:4])<=2027):
        raise ValueError("TARGET_SEASON_NOT_REGISTERED")
    out=Path(storage)/ROOT/day
    if dry_run:
        return {"status":"DRY_RUN_NO_SOURCE_CAPTURE","day":day,
                "first_window":"T-60","freeze_deadline":"T-30",
                "source_protocol":"ESPN / original two-sided PropLine, no retrospective stat forecasts"}
    attest_project_storage(storage)
    if out.exists():
        if (out/"day_final.json").exists():
            return {"status":"ALREADY_FINISHED_DAY","day":day}
        if not resume:
            return {"status":"ALREADY_CLAIMED_DAY","day":day}
        if os.environ.get("NFL_FORWARD_PRIOR_WORKER_INACTIVE_VERIFIED")!="1":
            raise ValueError("RESUME_REQUIRES_INDEPENDENT_INACTIVE_WORKER_VERIFICATION")
        if not (out/"day_start.json").is_file():
            raise ValueError("INCOMPLETE_DAY_WITHOUT_ORIGINAL_START")
        once(out/("resume_"+at.strftime("%Y%m%dT%H%M%S%fZ")+".json"),
             {"resumed_at":at.isoformat(),"previous_worker_inactive_verified_by_caller":True,
              "original_first_claims_never_replaced":True})
    else:
        if resume:raise ValueError("CANNOT_RESUME_NONEXISTENT_DAY")
        out.mkdir(parents=True,exist_ok=False)
        once(out/"day_start.json",{"started_at":at.isoformat(),"day":day,
                                  "status":"one original forward research run, no backfill"})
    board,first_receipt=board_for_day(day,out/"advance_sources",fetch=fetch)
    if not board:
        once(out/"day_final.json",{"status":"NO_SCHEDULED_NFL_EVENTS","day":day})
        return {"status":"NO_SCHEDULED_NFL_EVENTS","day":day}
    states=[];quotes=None
    for game in board:
        earliest=instant(game["event_start_at"])-FORWARD_WINDOW_OPEN
        deadline=instant(game["event_start_at"])-HARD_FREEZE_GAP
        t=now()
        if t>=deadline:
            states.append({"event_id":game["event_id"],"status":"MISSED_ORIGINAL_FREEZE"})
            continue
        if t<earliest:
            if not wait:
                states.append({"event_id":game["event_id"],"status":"NOT_DUE_TEST_ONLY"})
                continue
            while now()<earliest:
                time.sleep(min(20,max(.1,(earliest-now()).total_seconds())))
        if quotes is None:
            prev=out/"original_offer_ledger.json"
            if prev.is_file():
                quotes=json.loads(prev.read_text())
                # Resumed jobs MUST reuse original quote bytes/receipts, not
                # swap odds retrospectively for a quote that has already frozen.
                for receipt in quotes.get("receipts",[]):
                    raw=out/"offer_sources"/(receipt["original_raw_sha256"]+".json.gz")
                    if sha(gzip.decompress(raw.read_bytes()))!=receipt["original_raw_sha256"]:
                        raise ValueError("RESUMED_ORIGINAL_ODDS_BYTES_CHANGED")
            else:
                quotes=safe_original_quote_snapshot(day,out/"offer_sources",fetch=fetch)
                once(prev,{k:v for k,v in quotes.items() if k!="quotes"} | {"quotes":quotes["quotes"]})
        states.append(capture_game(game,day,out,quotes,fetch=fetch))
        once(out/("event_"+game["event_id"]+"_execution.json"),states[-1])
    summary={"day":day,"status":"ORIGINAL_FORWARD_RESEARCH_COLLECTION_WITH_ABSTENTIONS",
             "event_attempts":states,"quote_status":quotes["status"] if quotes else "NOT_ATTEMPTED",
             "frozen_player_model_forecasts":0,
             "no_automatic_model_fit":True,"retrospective_capture_forbidden":True,
             "finished_at":now().isoformat()}
    once(out/"day_final.json",summary)
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--storage",default="/work")
    p.add_argument("--day")
    p.add_argument("--dry-run",action="store_true")
    p.add_argument("--resume",action="store_true",help="only after independent prior worker-stop verification")
    args=p.parse_args()
    print(json.dumps(run(args.day,args.storage,args.dry_run,resume=args.resume),sort_keys=True),flush=True)

if __name__=="__main__":
    main()
