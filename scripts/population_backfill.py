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
from collections import Counter
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
import population_history as store
import population_normalizers as norm
import population_nfl

DEFAULT_START={"NHL":"2018-10-01","NBA":"2018-10-01","NFL":"2018"}
RECENT_START={"NHL":"2023-10-01","NBA":"2023-10-01"}
STATE="multi-sport-population-cursor-v1"
ROOT=Path(__file__).resolve().parents[1]


def state_file(root,sport,*,stream="archive"):
    if stream not in ("archive","recent") or (stream=="recent" and sport=="NFL"):
        raise ValueError("invalid_population_stream")
    name=sport.lower()+("_recent" if stream=="recent" else "")+".json"
    return Path(root)/"data/bayesian_warehouse/states"/name


def read_state(root,sport,*,stream="archive"):
    filename=state_file(root,sport,stream=stream)
    if not filename.exists():
        state={"schema":STATE,"sport":sport,
               "cursor":RECENT_START[sport] if stream=="recent" else DEFAULT_START[sport],
               "dates_complete":0,"source_games":0,"market_rows_inserted":0}
        if stream=="recent":state["stream"]="recent"
        return state
    data=json.loads(filename.read_text())
    if data.get("schema")!=STATE or data.get("sport")!=sport or (
            data.get("stream","archive")!=stream):
        raise ValueError("population_state_mismatch")
    if sport=="NFL":
        if not str(data["cursor"]).isdigit():raise ValueError("invalid_nfl_population_cursor")
    else:date.fromisoformat(data["cursor"])
    for k in ("dates_complete","source_games","market_rows_inserted"):
        if not isinstance(data.get(k),int) or data[k]<0:raise ValueError("invalid_population_counter")
    return data


def save_state(root,sport,state,*,stream="archive"):
    if state.get("stream","archive")!=stream:
        raise ValueError("population_stream_checkpoint_mismatch")
    p=state_file(root,sport,stream=stream);p.parent.mkdir(parents=True,exist_ok=True)
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
        stream="archive",max_nfl_seasons=1,
        fetcher=fetch_json,nfl_loader=population_nfl.fetch_season):
    if sport not in store.SPORTS:raise ValueError("unsupported_population_sport")
    if not 1<=max_days<=366 or not 1<=max_games<=5000 or not 1<=max_nfl_seasons<=6:
        raise ValueError("invalid_population_fetch_budget")
    if stream=="recent" and sport=="NFL":
        raise ValueError("nfl_recent_stream_not_supported_use_season_backfill")
    boundary=min(date.fromisoformat(stop_before) if stop_before else date.today()-timedelta(days=1),
                 date.today()-timedelta(days=1))
    state=read_state(root,sport,stream=stream)
    result={"schema":"multi_population_backfill_receipt_v1","sport":sport,"stream":stream,
            "status":"running","cursor_before":state["cursor"],"advanced":0,
            "source_games":0,"market_rows_added":0,"market_rows_verified_by_stat":{},"source_exclusions":[],
            "error":None,"publication_eligible":False}
    try:
        if sport=="NFL":
            while result["advanced"]<max_nfl_seasons:
                year=int(state["cursor"])
                # A current NFL season is not completed; require March of
                # the following year so no partial 2026 data is sealed.
                if date(year+1,3,1)>boundary:break
                stats,snaps,schedule=nfl_loader(year)
                rows,coverage=population_nfl.normalize_season(
                    stats,snaps,schedule,year,cutoff=(boundary+timedelta(days=1)).isoformat())
                result["source_exclusions"].append(coverage)
                if not rows:raise ValueError("nfl_season_has_no_matched_snaps")
                counts=store.persist(root,rows)
                result["market_rows_added"]+=counts["inserted"]
                result["source_games"]+=len({r["game_id"] for r in rows})
                totals=Counter(result["market_rows_verified_by_stat"])
                totals.update(r["stat"] for r in rows)
                result["market_rows_verified_by_stat"]=dict(sorted(totals.items()))
                state["cursor"]=str(year+1)
                state["dates_complete"]+=1
                state["source_games"]+=len({r["game_id"] for r in rows})
                state["market_rows_inserted"]+=counts["inserted"]
                result["advanced"]+=1
                save_state(root,sport,state,stream=stream)
        else:
            day=date.fromisoformat(state["cursor"])
            while day<=boundary and result["advanced"]<max_days:
                current=day.isoformat()
                if sport=="NHL":
                    board=fetcher(f"{norm.NHL_BASE}/score/{current}")
                    game_ids=nhl_games(board)
                    get_game=lambda gid: fetcher(f"{norm.NHL_BASE}/gamecenter/{gid}/boxscore")
                    normalize=lambda raw,gid: norm.nhl_game(raw,current,expected_id=gid)
                else:
                    board=fetcher(f"{norm.NBA_BASE}/scoreboard?dates={day.strftime('%Y%m%d')}&limit=100")
                    game_ids=norm.scoreboard_games(sport,board,current,
                        exclusions=result["source_exclusions"])
                    get_game=lambda gid: fetcher(f"{norm.NBA_BASE}/summary?event={gid}")
                    normalize=lambda raw,gid: norm.nba_game(raw,current,gid)
                # Count verified completed game IDs, not how many market rows
                # were nonmissing; a zero-row populated game fails below.
                if result["source_games"]+len(game_ids)>max_games and result["advanced"]:
                    break
                # Normalize *all* official completed games before mutating
                # any shard. A malformed/failed game cannot leave half a
                # date in the warehouse. Persist once per completed day to
                # avoid O(games x season-history) repeated gzip rewrites.
                daily=[]
                totals=Counter(result["market_rows_verified_by_stat"])
                for gid in game_ids:
                    rows=normalize(get_game(gid),gid)
                    if not rows:raise ValueError("completed_game_missing_population_rows")
                    totals.update(r["stat"] for r in rows)
                    daily.extend(rows)
                inserted_today=0
                if daily:
                    saved=store.persist(root,daily)
                    inserted_today=saved["inserted"]
                    result["market_rows_added"]+=inserted_today
                result["market_rows_verified_by_stat"]=dict(sorted(totals.items()))
                result["source_games"]+=len(game_ids)
                state["source_games"]+=len(game_ids)
                state["market_rows_inserted"]+=inserted_today
                state["dates_complete"]+=1
                day+=timedelta(days=1)
                state["cursor"]=day.isoformat()
                result["advanced"]+=1
                save_state(root,sport,state,stream=stream)
    except (RuntimeError,ValueError,TypeError,KeyError,OSError) as exc:
        result["error"]=str(exc)
    result["cursor_after"]=state["cursor"]
    result["status"]="blocked" if result["error"] else (
        "caught_up" if (date(int(state["cursor"])+1,3,1)>boundary if sport=="NFL"
                        else date.fromisoformat(state["cursor"])>boundary)
        else "partial")
    suffix="_recent" if stream=="recent" else ""
    receipt=Path(root)/"reports"/f"population_{sport.lower()}{suffix}_receipt.json"
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sport",choices=store.SPORTS,required=True)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--stream",choices=("archive","recent"),default="archive",
                        help="Separate recent NHL/NBA stream beginning 2023-10-01; immutable shared shard storage")
    parser.add_argument("--max-nfl-seasons",type=int,default=1,
                        help="Max fully completed nflverse seasons per invocation")
    parser.add_argument("--max-days",type=int,default=10)
    parser.add_argument("--max-games",type=int,default=100)
    parser.add_argument("--stop-before")
    parser.add_argument("--request-spacing",type=float,default=.7)
    args=parser.parse_args(argv)
    if not .1<=args.request_spacing<=5:
        parser.error("request spacing must be between .1 and 5 seconds")
    result=run(args.root,args.sport,max_days=args.max_days,
        max_games=args.max_games,stop_before=args.stop_before,
        stream=args.stream,max_nfl_seasons=args.max_nfl_seasons,
        fetcher=lambda url:fetch_json(url,spacing=args.request_spacing))
    print(json.dumps(result,sort_keys=True))
    return 2 if result["status"]=="blocked" else 0


if __name__=="__main__":
    raise SystemExit(main())
