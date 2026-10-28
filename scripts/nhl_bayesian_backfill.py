#!/usr/bin/env python3
"""Resumable NHL regular-season boxscore backfill: no PropLine requests or secrets."""
from __future__ import annotations
import argparse
import json
import os
import random
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import historical_nhl_warehouse as wh

FIRST_DAY = "2018-10-01"
STATE_VERSION = "nhl-warehouse-cursor-v1"


def fetch(url, *, retries=5, spacing=0.3, sleeper=time.sleep):
    if not url.startswith(wh.BASE+"/"):
        raise ValueError("non_nhl_official_source")
    for attempt in range(retries):
        try:
            with urlopen(Request(url,headers={
                    "User-Agent":"pickem-auditor-bayesian-history/1.0",
                    "Accept":"application/json"}),timeout=25) as response:
                if response.status != 200:
                    raise RuntimeError("unexpected_http_status")
                packet=json.load(response)
                if not isinstance(packet,dict):
                    raise ValueError("bad_nhl_json")
            sleeper(spacing)
            return packet
        except (HTTPError,URLError,TimeoutError,OSError,ValueError,RuntimeError) as exc:
            if attempt==retries-1:
                raise RuntimeError(f"NHL_SOURCE_UNAVAILABLE: {url}: {type(exc).__name__}: {exc}") from exc
            wait=min(90,2**attempt)
            if isinstance(exc,HTTPError) and exc.code==429:
                try:wait=max(wait,min(120,int(exc.headers.get("Retry-After","5"))))
                except (ValueError,TypeError):wait=max(wait,10)
            sleeper(wait+random.Random(attempt).random())


def state_path(root):
    return Path(root)/"data/bayesian_warehouse/backfill_state.json"


def load_state(root):
    path=state_path(root)
    if not path.exists():
        return {"version":STATE_VERSION,"next_date":FIRST_DAY,"dates_complete":0,
                "games_ingested":0,"skater_games_ingested":0}
    result=json.loads(path.read_text())
    if not isinstance(result,dict) or result.get("version")!=STATE_VERSION:
        raise ValueError("invalid_backfill_checkpoint")
    date.fromisoformat(result["next_date"])
    for key in ("dates_complete","games_ingested","skater_games_ingested"):
        if not isinstance(result.get(key),int) or result[key]<0:
            raise ValueError("invalid_checkpoint_counter")
    return result


def save_state(root,state):
    path=state_path(root)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp")
    temp.write_text(json.dumps(state,sort_keys=True,indent=2)+"\n")
    os.replace(temp,path)


def _regular_games(board,day):
    if not isinstance(board,dict) or not isinstance(board.get("games"),list):
        raise ValueError("missing_daily_scoreboard_games")
    games=[]
    ids=set()
    for row in board["games"]:
        if not isinstance(row,dict):
            raise ValueError("invalid_scoreboard_game")
        if row.get("gameType")!=2:
            continue
        gid=row.get("id")
        if isinstance(gid,bool) or not isinstance(gid,int) or gid in ids:
            raise ValueError("duplicate_or_missing_game_id")
        ids.add(gid)
        if row.get("gameState") not in wh.COMPLETE:
            raise ValueError("historical_game_not_final")
        games.append(gid)
    return games


def collect(root, *, max_days=90, max_games=250, stop_before=None, fetcher=fetch):
    if not 1<=max_days<=366 or not 1<=max_games<=5000:
        raise ValueError("invalid_backfill_budget")
    yesterday=(datetime.now(timezone.utc).date()-timedelta(days=1)).isoformat()
    limit=min(stop_before or yesterday,yesterday)
    date.fromisoformat(limit)
    state=load_state(root)
    receipt={"schema":"nhl_bayesian_history_backfill_v1",
            "started_at":datetime.now(timezone.utc).isoformat(),
            "cursor_before":state["next_date"],"max_days":max_days,
            "max_games":max_games,"days_advanced":0,"new_games":0,
            "new_skater_games":0,"skipped_games":0,"error":None,
            "season_range":"2018-19 onwards; regular season only",
            "feed":"NHL official score/YYYY-MM-DD and gamecenter/{id}/boxscore"}
    day=date.fromisoformat(state["next_date"])
    terminal=date.fromisoformat(limit)
    try:
        while day<=terminal and receipt["days_advanced"]<max_days:
            current=day.isoformat()
            games=_regular_games(fetcher(f"{wh.BASE}/score/{current}"),current)
            # Fail closed on partial dates. New games survive in shard but the
            # checkpoint advances only after every completed game on that date.
            for gid in games:
                path=wh.shard_path(root,current)
                if any(r["game_id"]==str(gid) for r in wh.read_shard(path)):
                    receipt["skipped_games"]+=1
                    continue
                source=fetcher(f"{wh.BASE}/gamecenter/{gid}/boxscore")
                normalized=wh.canonical_game(source,current)
                if str(source["id"])!=str(gid):
                    raise ValueError("boxscore_game_id_mismatch")
                if wh.add_game(root,normalized):
                    receipt["new_games"]+=1
                    receipt["new_skater_games"]+=len(normalized)
            day+=timedelta(days=1)
            state["next_date"]=day.isoformat()
            state["dates_complete"]+=1
            state["games_ingested"]+=len(games)
            all_day=wh.read_shard(wh.shard_path(root,current))
            state["skater_games_ingested"]+=sum(1 for row in all_day if row["game_id"] in {str(gid) for gid in games})
            receipt["days_advanced"]+=1
            save_state(root,state)
            if receipt["new_games"]>=max_games:
                break
    except (ValueError,RuntimeError,TypeError,KeyError,OSError) as exc:
        receipt["error"]=str(exc)
    # Canonical counts and checkpoint are informative, not evidence of completeness.
    receipt["cursor_after"]=state["next_date"]
    receipt["finished_at"]=datetime.now(timezone.utc).isoformat()
    receipt["status"]="blocked" if receipt["error"] else (
         "caught_up" if date.fromisoformat(state["next_date"])>terminal else "partial")
    report=Path(root)/"reports/nhl_bayesian_history_receipt.json"
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    return receipt


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--max-days",type=int,default=90)
    parser.add_argument("--max-games",type=int,default=250)
    parser.add_argument("--stop-before",help="Last historical date to include (YYYY-MM-DD)")
    parser.add_argument("--request-spacing",type=float,default=.3)
    args=parser.parse_args(argv)
    if not .1<=args.request_spacing<=10:parser.error("invalid request pacing")
    r=collect(args.root,max_days=args.max_days,max_games=args.max_games,
              stop_before=args.stop_before,
              fetcher=lambda url:fetch(url,spacing=args.request_spacing))
    print(json.dumps(r,sort_keys=True))
    return 2 if r["status"]=="blocked" else 0


if __name__=="__main__":
    raise SystemExit(main())
