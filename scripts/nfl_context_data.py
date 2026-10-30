"""Source-separated NFL research data and strictly pregame features.

Team PBP totals are not inferred by adding player snap counts. Player targets,
receptions, carries and pass attempts reconcile independently to PBP identities.
Historical availability is an explicit start+18h approximation, not an archive.
"""
from __future__ import annotations
import gzip
import json
import math
from collections import Counter, defaultdict
from datetime import date, time, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import nhl_context_data as common
import nhl_context_train as io
import population_nfl as source

VERSION="nfl-context-data-v1"
MARKETS={"targets":5.5,"receptions":3.5,"carries":10.5,"pass attempts":30.5,"tackles + assists":5.5}
PBP_FIELDS=("game_id","play_id","season_type","posteam","defteam","no_play","two_point_attempt",
            "pass_attempt","rush_attempt","sack","qb_dropback","receiver_player_id","complete_pass",
            "rusher_player_id","passer_player_id","play_type")
NAMES=["home","rest_difference","recent_player_snaps","own_team_plays","opponent_plays",
       "own_opportunity_environment","opponent_opportunity_environment"]


def one(value):
    return value is True or (not isinstance(value,bool) and value==1)


def no_play(row):
    """nflfastR encodes nullified plays in play_type; older inputs may flag them.

    Neither representation is manufactured when absent. A void marker in
    either source field excludes the event, even if the other field is zero.
    """
    flag=row.get("no_play")
    if one(flag) or row.get("play_type")=="no_play":return True
    if flag is False or (not isinstance(flag,bool) and flag==0):return False
    if isinstance(row.get("play_type"),str):return False
    # Administrative rows may have null play_type and no offensive event.
    if "play_type" in row and not any(one(row.get(k)) for k in
                                     ("pass_attempt","rush_attempt","sack","qb_dropback")):
        return True
    raise ValueError("missing_pbp_no_play_classification")


def pbp_records(frame):
    columns=set(frame.columns)
    absent=(set(PBP_FIELDS)-{"no_play","play_type"})-columns
    if absent:raise ValueError("missing_pbp_columns:"+",".join(sorted(absent)))
    if not columns&{"no_play","play_type"}:
        raise ValueError("missing_pbp_no_play_or_play_type_column")
    return frame.select([k for k in PBP_FIELDS if k in columns]).to_dicts()


def kickoff(game):
    # nflverse schedules gametime is US Eastern; gameday is local calendar date.
    stamp=f"{game['gameday']}T{game['gametime']}"
    return datetime.fromisoformat(stamp).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)


def clean(value):
    if isinstance(value,(date,time,datetime)):return value.isoformat()
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    return value


def normalize(raw, *, season, until):
    end=common.instant(until)
    games={}
    for g in raw["schedule"]:
        if int(g.get("season",0))!=season or g.get("game_type")!="REG":continue
        if g.get("home_score") is None or g.get("away_score") is None:continue
        start=kickoff(g)
        if start+timedelta(hours=18)>=end:continue
        gid=str(g["game_id"])
        if gid in games:raise ValueError("duplicate_schedule_game")
        games[gid]={"game_id":gid,"season":str(season),"start_time":start.isoformat(),
                    "available_at":(start+timedelta(hours=18)).isoformat(),"schedule":g}
    teams={};events={};person=Counter();pbp_games=set()
    for gid,g in games.items():
        s=g["schedule"]
        for side,other in (("home_team","away_team"),("away_team","home_team")):
            team=s[side];opp=s[other]
            teams[(gid,team)]={k:v for k,v in g.items() if k!="schedule"}
            teams[(gid,team)].update(team=team,opponent=opp,home=side=="home_team",plays=0,
                                    passes=0,rushes=0,targets=0,receptions=0)
    for p in raw["pbp"]:
        gid=str(p.get("game_id"));team=p.get("posteam")
        if gid not in games or p.get("season_type")!="REG" or (gid,team) not in teams:continue
        if no_play(p) or one(p.get("two_point_attempt")):continue
        passing=one(p.get("pass_attempt")) and not one(p.get("sack"))
        rushing=one(p.get("rush_attempt"))
        if not (passing or rushing or one(p.get("sack")) or one(p.get("qb_dropback"))):continue
        if p.get("defteam")!=teams[(gid,team)]["opponent"]:
            raise ValueError("pbp_opponent_identity_mismatch")
        key=(gid,p.get("play_id"))
        if key[1] is None:raise ValueError("missing_pbp_play_identity")
        if key in events:
            if events[key]!=p:raise ValueError("conflicting_duplicate_pbp_event")
            continue
        events[key]=p;pbp_games.add(gid)
        t=teams[(gid,team)];t["plays"]+=1;t["passes"]+=int(passing);t["rushes"]+=int(rushing)
        if passing and p.get("receiver_player_id"):
            receiver=str(p["receiver_player_id"]);t["targets"]+=1
            person[(gid,team,receiver,"targets")]+=1
            if one(p.get("complete_pass")):
                t["receptions"]+=1;person[(gid,team,receiver,"receptions")]+=1
        if rushing and p.get("rusher_player_id"):
            person[(gid,team,str(p["rusher_player_id"]),"carries")]+=1
        if passing and p.get("passer_player_id"):
            person[(gid,team,str(p["passer_player_id"]),"pass attempts")]+=1
    # Game completeness is checked against completed schedule IDs, never just
    # the subset having a convenient PBP match. Missing teams block collection.
    missing=sorted(gid for gid,g in games.items() if gid not in pbp_games or
                   any(teams[(gid,g["schedule"][side])]["plays"]<1 for side in ("home_team","away_team")))
    if missing:raise ValueError("completed_schedule_games_missing_pbp:"+",".join(missing[:10]))
    until_day=end.date().isoformat()
    players,coverage=source.normalize_season(raw["stats"],raw["snaps"],raw["schedule"],season,cutoff=until_day)
    valid=[];excluded=[]
    for p in players:
        if p["stat"] not in MARKETS or p["game_id"] not in games:continue
        if p["stat"]!="tackles + assists":
            counted=person[(p["game_id"],p["team"],p["player_id"],p["stat"])]
            if p["value"]!=counted:
                excluded.append({"game_id":p["game_id"],"player_id":p["player_id"],"market":p["stat"],
                                 "reason":"weekly_pbp_count_mismatch","weekly":p["value"],"pbp":counted})
                continue
        valid.append({**p,**{k:games[p["game_id"]][k] for k in ("start_time","available_at")}})
    if not valid or not teams:raise ValueError("empty_nfl_context_source")
    return {"schema":VERSION,"season":season,"until":until,"source_digest":common.digest(raw),
            "teams":sorted(teams.values(),key=lambda r:(r["start_time"],r["team"])),
            "players":valid,"coverage":coverage,"excluded":excluded,
            "completed_schedule_games":len(games),"pbp_events":len(events),
            "availability_policy":"retrospective_start_plus_18h","ranking_allowed":False}


def fetch(season):
    import nflreadpy as nfl
    print(f"FETCH_SEASON {season} player_stats snaps schedule pbp",flush=True)
    # Retain only used PBP columns before materializing Python objects.
    frame=nfl.load_pbp(seasons=[season])
    pbp=pbp_records(frame)
    return clean({"stats":nfl.load_player_stats(seasons=[season],summary_level="week").to_dicts(),
                  "snaps":nfl.load_snap_counts(seasons=[season]).to_dicts(),
                  "schedule":nfl.load_schedules(seasons=[season]).to_dicts(),
                  "pbp":pbp})


def collect(folder, seasons, until, fetcher=fetch):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    bundles=[]
    for season in seasons:
        path=folder/f"season_{season}.json.gz";receipt=folder/f"season_{season}.receipt.json"
        if path.exists():
            meta=io.load_json(receipt)
            if meta["sha256"]!=io.file_hash(path) or meta["until"]!=until:
                raise ValueError("season_cache_hash_or_cutoff_changed")
            with gzip.open(path,"rt",encoding="utf-8") as h:raw=json.load(h)
            print(f"SOURCE_CACHE_VERIFIED {season}",flush=True)
        else:
            raw=fetcher(season)
            # Preserve fetched evidence even if normalization later fails.
            tmp=path.with_suffix(".tmp")
            tmp.write_bytes(gzip.compress((common.encode(raw)+"\n").encode(),mtime=0));tmp.replace(path)
            io.write_json(receipt,{"sha256":io.file_hash(path),"until":until,
                        "retrieved_at":datetime.now(timezone.utc).isoformat(),
                        "source":"https://github.com/nflverse/nflverse-data/releases"})
        bundles.append(normalize(raw,season=season,until=until))
    return bundles


def examples(bundles, market, *, context=True):
    if market not in MARKETS:raise ValueError("unsupported_nfl_context_market")
    teams=[r for b in bundles for r in b["teams"]]
    players=[r for b in bundles for r in b["players"] if r["stat"]==market]
    ids=[(r["game_id"],r["player_id"]) for r in players]
    if len(ids)!=len(set(ids)):raise ValueError("duplicate_nfl_player_game")
    histories=defaultdict(list);personal=defaultdict(list);lookup={}
    for t in teams:
        key=(t["game_id"],t["team"])
        if key in lookup:raise ValueError("duplicate_nfl_team_game")
        lookup[key]=t;histories[t["team"]].append(t)
    for p in players:personal[p["player_id"]].append(p)
    rows=[]
    for p in players:
        at=common.instant(p["start_time"])
        def before(history):
            return sorted((r for r in history if common.instant(r["start_time"])<at and
                           common.instant(r["available_at"])<at and r["game_id"]!=p["game_id"]),
                          key=lambda r:r["start_time"])[-8:]
        own=before(histories[p["team"]]);opp=before(histories[p["opponent"]]);past=before(personal[p["player_id"]])
        def rate(history, field, prior, allowed=False):
            values=[lookup[(r["game_id"],r["opponent"])][field] if allowed else r[field] for r in history]
            return (sum(values)+5*prior)/(len(values)+5)
        # Defense's exposure follows the opposing offense; tackles have no
        # measured tackle-opportunity denominator here. This is a rate model.
        field,prior=("targets",30.) if market in ("targets","receptions") else (
                     ("rushes",27.) if market=="carries" else (("passes",35.) if market=="pass attempts" else ("plays",65.)))
        def rest(history):
            return min(21.,(at-common.instant(history[-1]["start_time"])).total_seconds()/86400) if history else 7.
        prior_snap={"QB":60.,"RB":30.,"WR":45.,"TE":40.}.get(p["position"],45.)
        recent=(sum(r["workload"] for r in past[-5:])+3*prior_snap)/(len(past[-5:])+3)
        x=[float(p["home"]),rest(own)-rest(opp),recent]
        if context:
            environment=([rate(own,field,prior,allowed=True),rate(opp,field,prior)] if market=="tackles + assists"
                         else [rate(own,field,prior),rate(opp,field,prior,allowed=True)])
            x += [rate(own,"plays",65.),rate(opp,"plays",65.),*environment]
        rows.append({**p,"target":p["value"],"x":x,"feature_names":NAMES if context else NAMES[:3],
                     "feature_time":p["start_time"],"prior_player_games":len(past)})
    return sorted(rows,key=lambda r:(r["start_time"],r["game_id"],r["player_id"]))


def prepare(rows, cutoff, *, minimum=200):
    import numpy as np
    if len(rows)<minimum:raise ValueError("insufficient_nfl_context_training_rows")
    if any(common.instant(r[k])>=common.instant(cutoff) for r in rows for k in ("start_time","available_at")):
        raise ValueError("future_nfl_training_row")
    if len({r["stat"] for r in rows})!=1 or len({tuple(r["feature_names"]) for r in rows})!=1:
        raise ValueError("mixed_nfl_design")
    players=sorted({r["player_id"] for r in rows});teams=sorted({r[k] for r in rows for k in ("team","opponent")})
    positions=sorted({r["position"] for r in rows});seasons=sorted({r["season"] for r in rows})
    if len(seasons)<2:raise ValueError("nfl_pilot_requires_two_training_seasons")
    pmap={}
    for r in rows:
        if pmap.setdefault(r["player_id"],r["position"])!=r["position"]:
            raise ValueError("nfl_player_position_changed_requires_mapping")
        if not 0<r["workload"]<160 or r["feature_time"]!=r["start_time"]:
            raise ValueError("invalid_nfl_workload_or_feature_time")
    x=np.asarray([r["x"] for r in rows],dtype=float)
    if not np.isfinite(x).all():raise ValueError("nonfinite_nfl_features")
    center=x.mean(0);scale=np.maximum(x.std(0),.05)
    result={"schema":"nfl-context-design-v1","market":rows[0]["stat"],"players":players,"teams":teams,
            "positions":positions,"seasons":seasons,"player_position":pmap,"cutoff":cutoff,
            "feature_names":rows[0]["feature_names"],"center":center.tolist(),"scale":scale.tolist(),
            "x":((x-center)/scale).tolist(),"snaps":[r["workload"] for r in rows],
            "target":[r["target"] for r in rows],"source_digest":common.digest(rows)}
    for name,items,key in (("player",players,"player_id"),("team",teams,"team"),("opponent",teams,"opponent"),
                           ("season",seasons,"season"),("position",positions,"position")):
        mapping={v:i for i,v in enumerate(items)};result[name+"_idx"]=[mapping[r[key]] for r in rows]
    return result
