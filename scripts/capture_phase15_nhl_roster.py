#!/usr/bin/env python3
"""Capture raw NHL-hosted current team rosters, before future slate events.

Research-only. This does not confirm active lineup or NHL goalie starters.
Preserves missing-source attempts without inventing team membership.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v2.phase15_nhl_roster import roster_url,roster_members,utc,digest


def capture(*,phase1,output_dir,code_commit,source_phase1_sha256,fetch=None,now=None):
    if phase1.get("schema")!="v25-phase1-nhl-nba-certified-replay-v1":
        raise ValueError("wrong_original_phase1_schema")
    if phase1.get("model_promotion_authorized") is not False:
        raise ValueError("phase1_production_promotion_not_allowed")
    if output_dir.exists():
        raise FileExistsError("append_only_new_roster_archive_directory_required")
    output_dir.mkdir(parents=True,exist_ok=False)
    contracts=[x for x in phase1["contracts"] if x["sport"]=="NHL"]
    teams={}
    for c in contracts:
        for team in (c["team_id"],c["opponent_id"]):
            teams.setdefault(team,[]).append(utc(c["event_start"]))
    receipts={}
    errors={}
    if fetch is None:
        def fetch(url):
            request=urllib.request.Request(url,headers={
                "User-Agent":"pickem-auditor-independent-pre-event-research/1",
                "Accept":"application/json"})
            with urllib.request.urlopen(request,timeout=20) as resp:
                if resp.status!=200:raise ValueError("non_200_official_roster")
                return resp.read()
    clock=now or (lambda:datetime.now(timezone.utc))
    for team,events in sorted(teams.items()):
        observed=clock()
        if observed>=min(events):
            errors[team]="team_event_started_before_roster_capture"
            continue
        try:
            url=roster_url(team)
            raw=fetch(url)
            observed=clock()  # Actual observed-after-download clock, not publication.
            if observed>=min(events):
                raise ValueError("roster_collected_at_or_after_event")
            player_ids=roster_members(raw)
            filename=f"nhl_roster_{team}_{digest(raw)[:16]}.json"
            with (output_dir/filename).open("xb") as f:f.write(raw)
            receipts[team]={
               "schema":"nhl_independent_current_roster_receipt_v1",
               "team":team,"source_url":url,
               "retrieved_at":observed.isoformat().replace("+00:00","Z"),
               "raw_archive_path":filename,"bytes":len(raw),
               "sha256":digest(raw),
               "players_seen":len(player_ids),
               "membership_claim_only_not_lineup_confirmation":True,
            }
        except (ValueError,OSError,TimeoutError) as exc:
            errors[team]=type(exc).__name__+":"+str(exc)[:160]
    result={
       "schema":"phase15_nhl_pregame_roster_capture_v1",
       "source_phase1_sha256":source_phase1_sha256,
       "code_commit":code_commit,
       "teams_attempted":len(teams),
       "teams_captured":len(receipts),
       "roster_receipts":receipts,
       "teams_unverifiable":errors,
       "source_kind":"nhl_hosted_roster_CURRENT_first_collector_possession",
       "provider_published_at_claimed":False,
       "membership_is_not_game_participation":True,
       "output_is_production_forecast":False,
    }
    (output_dir/"roster_manifest.json").write_text(
        json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf8")
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase1",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--code-commit",required=True)
    args=p.parse_args(argv)
    try:
        import hashlib
        raw=args.phase1.read_bytes()
        phase=json.loads(raw)
        out=capture(phase1=phase,output_dir=args.output_dir,
                    code_commit=args.code_commit,
                    source_phase1_sha256=hashlib.sha256(raw).hexdigest())
        print(json.dumps({"output":str(args.output_dir),
             "source_phase1_sha256":out["source_phase1_sha256"],
             "teams_attempted":out["teams_attempted"],"teams_captured":out["teams_captured"],
             "status":"research_only_no_lineup_or_release"},sort_keys=True))
        return 0 if out["teams_captured"] else 2
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print("NHL_PREGAME_ROSTER_CAPTURE_BLOCKED "+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":raise SystemExit(main())
