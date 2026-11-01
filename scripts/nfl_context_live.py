"""Fresh source-separated context snapshot from the existing NFL collector calls."""
import gzip
import json
import math
from datetime import timedelta
from pathlib import Path
import nhl_context_data as common
import nhl_context_train as io
import nfl_context_data as data
from nfl_read_features import join


def cache_path(season_store_path,season):
    return Path(season_store_path).parent/f"nfl_context_{season}.json.gz"


def write(path,raw,charting,catalog,*,season,retrieved_at):
    raw=data.clean(raw)
    bundle=data.normalize(raw,season=season,until=retrieved_at)
    bundle=join(bundle,raw["pbp"],data.clean(charting or []))
    bundle["players"]=[r for r in bundle["players"] if r["stat"]=="targets"]
    people={};ambiguous=set()
    for r in catalog:
        pid=str(r.get("player_id") or "");team=r.get("recent_team") or r.get("team")
        if not pid or not team or pid in ambiguous:continue
        person={"player_id":pid,"team":team,"position":r.get("position"),
                "name":r.get("player_display_name") or r.get("player_name")}
        if pid in people and people[pid]!=person:
            people.pop(pid);ambiguous.add(pid);continue
        people[pid]=person
    schedule=[{k:g.get(k) for k in ("game_id","season","game_type","gameday","gametime","home_team","away_team")}
              for g in raw["schedule"] if g.get("game_type")=="REG" and g.get("season")==season]
    payload={"schema":"nfl-live-context-v1","retrieved_at":retrieved_at,"season":season,
             "bundle":bundle,"schedule":schedule,"catalog":people,"ambiguous_players":sorted(ambiguous),
             "charting_available":charting is not None}
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp");temp.write_bytes(gzip.compress((common.encode(payload)+"\n").encode(),mtime=0));temp.replace(path)
    io.write_json(path.with_suffix(".receipt.json"),{"sha256":io.file_hash(path),"retrieved_at":retrieved_at,
        "source":"https://github.com/nflverse/nflverse-data/releases","attribution":"FTN Data via nflverse, CC BY-SA 4.0"})
    return payload


def load(path,now,*,max_age=3600):
    path=Path(path);receipt=io.load_json(path.with_suffix(".receipt.json"))
    if io.file_hash(path)!=receipt["sha256"]:raise ValueError("nfl_live_source_hash_changed")
    with gzip.open(path,"rt",encoding="utf-8") as stream:payload=json.load(stream)
    if (payload.get("schema")!="nfl-live-context-v1" or payload["retrieved_at"]!=receipt["retrieved_at"] or
        payload["bundle"]["until"]!=payload["retrieved_at"]):raise ValueError("invalid_nfl_live_source_receipt")
    age=(now-common.instant(payload["retrieved_at"])).total_seconds()
    if age<0 or (max_age is not None and age>max_age):raise ValueError("nfl_live_source_stale_or_future")
    return payload,receipt["sha256"]


def refresh_actuals(path,season,now,*,loader=None):
    """Two public bulk calls; exact GSIS/game joins, never reception outcomes."""
    if loader is None:import nflreadpy as loader
    def rows(frame):return data.clean(frame.to_dicts() if hasattr(frame,"to_dicts") else list(frame))
    schedule=rows(loader.load_schedules(seasons=[season]))
    stats=rows(loader.load_player_stats(seasons=[season],summary_level="week"))
    games={}
    for g in schedule:
        if (g.get("game_type")!="REG" or g.get("season")!=season or
            g.get("home_score") is None or g.get("away_score") is None or
            data.kickoff(g)+timedelta(hours=18)>=now):continue
        for team in (g["home_team"],g["away_team"]):
            key=(g["season"],g["week"],team)
            if key in games:raise ValueError("ambiguous_nfl_actual_game")
            games[key]=g
    actual={}
    for r in stats:
        if r.get("season_type")!="REG" or r.get("targets") is None:continue
        g=games.get((r.get("season"),r.get("week"),r.get("team") or r.get("recent_team")))
        if not g or not r.get("player_id"):continue
        v=r["targets"]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or not float(v).is_integer():
            raise ValueError("invalid_nfl_actual_target_count")
        item={"game_id":str(g["game_id"]),"player_id":str(r["player_id"]),"value":v,
              "start_time":data.kickoff(g).isoformat(),"available_at":(data.kickoff(g)+timedelta(hours=18)).isoformat()}
        key=(item["game_id"],item["player_id"])
        if key in actual and actual[key]!=item:raise ValueError("conflicting_nfl_actual_targets")
        actual[key]=item
    payload={"schema":"nfl-targets-actuals-v1","retrieved_at":now.isoformat(),
        "source":"https://github.com/nflverse/nflverse-data/releases/tag/player_stats",
        "source_digest":common.digest([schedule,stats]),"rows":[actual[k] for k in sorted(actual)]}
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_bytes(gzip.compress((common.encode(payload)+'\n').encode(),mtime=0));temp.replace(path)
    io.write_json(path.with_suffix('.receipt.json'),{"sha256":io.file_hash(path)})
    return payload
