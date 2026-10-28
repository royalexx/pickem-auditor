#!/usr/bin/env python3
"""Independent resumable historical NHL/NBA/NFL population collection.

No PropLine or odds calls. NHL and NBA use daily completed-game records.
NFL loads three bulk season sources with an independently verified snap join.
Every date/season is checkpointed only AFTER all required source requests
and immutable player-game shards have been written.
"""
from __future__ import annotations
import argparse
import json
import os
import random
import time
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
import population_history as store
import population_normalizers as norm
import population_nfl

DEFAULT_START={"NHL":"2018-10-01","NBA":"2018-10-01","NFL":"2018"}
STATE="multi-sport-population-cursor-v1"
ROOT=Path(__file__).resolve().parents[1]


def state_file(root,sport):
    return Path(root)/"data/bayesian_warehouse/states"/(sport.lower()+".json")


def read_state(root,sport):
    filename=state_file(root,sport)
    if not filename.exists():
        return {"schema":STATE,"sport":sport,"cursor":DEFAULT_START[sport],
                "dates_complete":0,"source_games":0,"market_rows_inserted":0}
    data=json.loads(filename.read_text())
    if data.get("schema")!=STATE or data.get("sport")!=sport:
        raise ValueError("population_state_mismatch")
    if sport=="NFL":
        if not str(data["cursor"]).isdigit():raise ValueError("invalid_nfl_population_cursor")
    else:date.fromisoformat(data["cursor"])
    for k in ("dates_complete","source_games","market_rows_inserted"):
        if not isinstance(data.get(k),int) or data[k]<0:raise ValueError("invalid_population_counter")
    return data


def save_state(root,sport,state):
    p=state_file(root,sport);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(".tmp")
    temp.write_text(json.dumps(state,sort_keys=True,indent=2)+"\n")
    os.replace(temp,p)


def fetch_json(url,*,spacing=.5,attempts=4,sleeper=time.sleep):
    if not (url.startswith(norm.NHL_BASE+"/") or url.startswith(norm.NBA_BASE+"/")):
        raise ValueError("unapproved_history_host")
    for attempt in range(attempts):
        try:
            headers={"User-Agent":"pickem-auditor-independent-population/1.0",
                     "Accept":"application/json"}
            with urlopen(Request(url,headers=headers),timeout=30) as response:
                if response.status!=200:raise ValueError("non_200_historical_response")
                result=json.load(response)
            if not isinstance(result,dict):raise ValueError("invalid_history_json")
            sleeper(spacing)
            return result
        except (HTTPError,URLError,TimeoutError,OSError,ValueError) as exc:
            if attempt+1==attempts:
                raise RuntimeError(f"HISTORICAL_SOURCE_UNAVAILABLE {url}: {type(exc).__name__}: {exc}") from exc
            pause=min(90,2**attempt)
            if isinstance(exc,HTTPError) and exc.code==429:
                try:pause=max(pause,min(120,int(exc.headers.get("Retry-After","10"))))
                except (TypeError,ValueError):pause=max(pause,10)
            sleeper(pause+random.Random(attempt).random())


def nhl_games(board):
    games=board.get("games") if isinstance(board,dict) else None
    if not isinstance(games,list):raise ValueError("missing_nhl_scoreboard")
    selected=[]
    for game in games:
        if game.get("gameType")!=2:continue
        if game.get("gameState") not in ("FINAL","OFF"):
            raise ValueError("regular_season_nhl_game_not_final")
        gid=game.get("id")
        if isinstance(gid,bool) or not isinstance(gid,int):
            raise ValueError("missing_nhl_game_id")
        selected.append(gid)
    if len(selected)!=len(set(selected)):raise ValueError("duplicate_nhl_event")
    return selected


def run(root,sport,*,max_days=10,max_games=100,stop_before=None,
        fetcher=fetch_json,nfl_loader=population_nfl.fetch_season):
    if sport not in store.SPORTS:raise ValueError("unsupported_population_sport")
    if not 1<=max_days<=366 or not 1<=max_games<=5000:
        raise ValueError("invalid_population_fetch_budget")
    boundary=min(date.fromisoformat(stop_before) if stop_before else date.today()-timedelta(days=1),
                 date.today()-timedelta(days=1))
    state=read_state(root,sport)
    result={"schema":"multi_population_backfill_receipt_v1","sport":sport,
            "status":"running","cursor_before":state["cursor"],"advanced":0,
            "source_games":0,"market_rows_added":0,"source_exclusions":[],
            "error":None,"publication_eligible":False}
    try:
        if sport=="NFL":
            year=int(state["cursor"])
            if year<=boundary.year:
                stats,snaps,schedule=nfl_loader(year)
                rows,coverage=population_nfl.normalize_season(
                    stats,snaps,schedule,year,cutoff=(boundary+timedelta(days=1)).isoformat())
                result["source_exclusions"].append(coverage)
                if not rows:raise ValueError("nfl_season_has_no_matched_snaps")
                counts=store.persist(root,rows)
                result["market_rows_added"]+=counts["inserted"]
                result["source_games"]+=len({r["game_id"] for r in rows})
                state["cursor"]=str(year+1)
                state["dates_complete"]+=1
                state["source_games"]+=result["source_games"]
                state["market_rows_inserted"]+=counts["inserted"]
                result["advanced"]+=1
                save_state(root,sport,state)
        else:
            day=date.fromisoformat(state["cursor"])
            while day<=boundary and result["advanced"]<max_days:
                current=day.isoformat()
                if sport=="NHL":
                    board=fetcher(f"{norm.NHL_BASE}/score/{current}")
                    game_ids=nhl_games(board)
                    get_game=lambda gid: fetcher(f"{norm.NHL_BASE}/gamecenter/{gid}/boxscore")
                    normalize=lambda raw,gid: norm.nhl_game(raw,current)
                else:
                    board=fetcher(f"{norm.NBA_BASE}/scoreboard?dates={day.strftime('%Y%m%d')}&limit=100")
                    game_ids=norm.scoreboard_games(sport,board,current)
                    get_game=lambda gid: fetcher(f"{norm.NBA_BASE}/summary?event={gid}")
                    normalize=lambda raw,gid: norm.nba_game(raw,current,gid)
                # Count verified completed game IDs, not how many market rows
                # were nonmissing; a zero-row populated game fails below.
                if result["source_games"]+len(game_ids)>max_games and result["advanced"]:
                    break
                for gid in game_ids:
                    rows=normalize(get_game(gid),gid)
                    if not rows:raise ValueError("completed_game_missing_population_rows")
                    inserted=store.persist(root,rows)
                    result["market_rows_added"]+=inserted["inserted"]
                result["source_games"]+=len(game_ids)
                state["source_games"]+=len(game_ids)
                state["market_rows_inserted"]+=result["market_rows_added"]- (
                    state["market_rows_inserted"] - result.get("_initial_inserted",state["market_rows_inserted"]))
                # replace cumulative counter below with an explicit initial snapshot
                state["dates_complete"]+=1
                day+=timedelta(days=1)
                state["cursor"]=day.isoformat()
                result["advanced"]+=1
                save_state(root,sport,state)
    except (RuntimeError,ValueError,TypeError,KeyError,OSError) as exc:
        result["error"]=str(exc)
    result.pop("_initial_inserted",None)
    result["cursor_after"]=state["cursor"]
    result["status"]="blocked" if result["error"] else (
        "caught_up" if (int(state["cursor"])>boundary.year if sport=="NFL"
                        else date.fromisoformat(state["cursor"])>boundary)
        else "partial")
    receipt=Path(root)/"reports"/f"population_{sport.lower()}_receipt.json"
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sport",choices=store.SPORTS,required=True)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--max-days",type=int,default=10)
    parser.add_argument("--max-games",type=int,default=100)
    parser.add_argument("--stop-before")
    parser.add_argument("--request-spacing",type=float,default=.7)
    args=parser.parse_args(argv)
    if not .1<=args.request_spacing<=5:
        parser.error("request spacing must be between .1 and 5 seconds")
    result=run(args.root,args.sport,max_days=args.max_days,
        max_games=args.max_games,stop_before=args.stop_before,
        fetcher=lambda url:fetch_json(url,spacing=args.request_spacing))
    print(json.dumps(result,sort_keys=True))
    return 2 if result["status"]=="blocked" else 0


if __name__=="__main__":
    raise SystemExit(main())
