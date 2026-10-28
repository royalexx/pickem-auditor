#!/usr/bin/env python3
"""One-time resumable, NBA 3PT-only historic correction. Never rewrites other stats.

ESPN's boxscore can express made threes as e.g. 3PT=3-8; previously this
market could be skipped. Replay only original completed dates before the
normal NBA cursor and only insert missing 3PM observations. Existing source
provenance and forward collection cursors remain immutable.
"""
from __future__ import annotations
import argparse
import json
import os
from datetime import date,timedelta
from pathlib import Path
import population_history as store
import population_normalizers as norm
import population_backfill as backfill

BEGIN="2018-10-01"
END_EXCLUSIVE="2018-10-26"
STATE_SCHEMA=backfill.STATE
ROOT=Path(__file__).resolve().parents[1]


def checkpoint(root):
    return Path(root)/"data/bayesian_warehouse/states/nba_threes_replay.json"


def run(root,*,max_days=35,fetcher=backfill.fetch_json):
    if not 1<=max_days<=100:raise ValueError("invalid_repair_budget")
    original=backfill.read_state(root,"NBA")
    limit=min(date.fromisoformat(END_EXCLUSIVE),date.fromisoformat(original["cursor"]))
    p=checkpoint(root)
    state=json.loads(p.read_text()) if p.exists() else {
        "schema":STATE_SCHEMA,"sport":"NBA","cursor":BEGIN,
        "dates_complete":0,"source_games":0,"market_rows_inserted":0}
    if state["schema"]!=STATE_SCHEMA or state["sport"]!="NBA":
        raise ValueError("invalid_replay_checkpoint")
    day=date.fromisoformat(state["cursor"])
    report={"schema":"nba_threes_historical_repair_v1","cursor_before":state["cursor"],
            "original_nba_cursor":original["cursor"],"dates_completed":0,
            "games_verified":0,"new_threes_records":0,"error":None,
            "publication_eligible":False}
    try:
        while day<limit and report["dates_completed"]<max_days:
            current=day.isoformat()
            board=fetcher(f"{norm.NBA_BASE}/scoreboard?dates={day.strftime('%Y%m%d')}&limit=100")
            games=norm.scoreboard_games("NBA",board,current)
            added=0
            for gid in games:
                summary=fetcher(f"{norm.NBA_BASE}/summary?event={gid}")
                normalized=norm.nba_game(summary,current,gid)
                threes=[r for r in normalized if r["stat"]=="threes"]
                if not threes:
                    raise ValueError("no_3pt_values_in_completed_nba_game:"+str(gid))
                # Historical records for other stats and any existing 3PM
                # records are NEVER recalculated, overwritten or rehashed.
                filename=store.path(root,"NBA","threes",threes[0]["season"])
                already={(r["game_id"],r["player_id"]) for r in store.read_shard(filename)}
                missing=[r for r in threes if (r["game_id"],r["player_id"]) not in already]
                if missing:
                    inserted=store.persist(root,missing)
                    added+=inserted["inserted"]
            state["dates_complete"]+=1
            state["source_games"]+=len(games)
            state["market_rows_inserted"]+=added
            report["new_threes_records"]+=added
            report["games_verified"]+=len(games)
            report["dates_completed"]+=1
            day+=timedelta(days=1)
            state["cursor"]=day.isoformat()
            p.parent.mkdir(parents=True,exist_ok=True)
            tmp=p.with_suffix(".tmp")
            tmp.write_text(json.dumps(state,sort_keys=True,indent=2)+"\n")
            os.replace(tmp,p)
    except (ValueError,RuntimeError,OSError,KeyError,TypeError) as exc:
        report["error"]=str(exc)
    report["cursor_after"]=state["cursor"]
    report["status"]="blocked" if report["error"] else (
        "caught_up" if day>=limit else "partial")
    out=Path(root)/"reports/nba_threes_replay.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--max-days",type=int,default=35)
    a=p.parse_args(argv)
    receipt=run(a.root,max_days=a.max_days)
    print(json.dumps(receipt,sort_keys=True))
    return 2 if receipt["status"]=="blocked" else 0


if __name__=="__main__":
    raise SystemExit(main())
