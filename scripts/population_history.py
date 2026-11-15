"""Versioned, source-owned player-game observations for joint multi-sport models.

Long-format, one (sport,stat,game,player) per row. A completed record is never
rewritten silently. A repeated backfill is idempotent. Missing workload,
missing stat or missing appearance is NOT silently imputed as zero.
"""
from __future__ import annotations
import gzip
import hashlib
import io
import json
import math
import os
import re
import time
from datetime import date
from pathlib import Path

VERSION="joint-population-history-v1"
COUNT={
 "NHL":("shots on goal","hits","blocked shots","saves"),
 "NBA":("points","rebounds","assists","threes","steals","blocks","turnovers","pra","pr","pa","ra"),
 "NFL":("pass attempts","completions","targets","receptions","carries",
        "passing touchdowns","rushing touchdowns","receiving touchdowns",
        "tackles + assists","solo tackles","tackle assists","qb hits","passes defended"),
}
CONTINUOUS={"NFL":("passing yards","receiving yards","rushing yards")}
SPORTS=tuple(COUNT)

# Legacy NFL shards intentionally remain immutable: early 2018 source
# ingestion included non-eligible player/market combinations (e.g. QB
# receiving targets, WR passing attempts) whose structural zero counts
# corrupt hierarchical position rates. Exclude those records *on read*
# and also stop generating them in future collections.
NFL_MARKET_POSITIONS={
 "pass attempts":frozenset(("QB",)),
 "completions":frozenset(("QB",)),
 "passing yards":frozenset(("QB",)),
 "passing touchdowns":frozenset(("QB",)),
 "targets":frozenset(("WR","RB","TE")),
 "receptions":frozenset(("WR","RB","TE")),
 "receiving yards":frozenset(("WR","RB","TE")),
 "receiving touchdowns":frozenset(("WR","RB","TE")),
 "carries":frozenset(("QB","RB","WR")),
 "rushing yards":frozenset(("QB","RB","WR")),
 "rushing touchdowns":frozenset(("QB","RB","WR")),
}
def market_eligible(row):
    if row["sport"]!="NFL":return True
    positions=NFL_MARKET_POSITIONS.get(row["stat"])
    return positions is None or row["position"] in positions

FIELDS=("schema","sport","stat","family","game_id","game_date","season",
        "player_id","position","team","opponent","home","value",
        "workload","workload_unit","source_url","source_sha256")


def family(sport,stat):
    if stat in COUNT.get(sport,()): return "count"
    if stat in CONTINUOUS.get(sport,()): return "continuous"
    raise ValueError("unsupported_sport_stat_market")


def slug(stat):
    return re.sub(r"[^a-z0-9]+","_",stat.lower()).strip("_")


def canonical_json(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)


def source_hash(payload):
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def validate(row):
    if not isinstance(row,dict) or any(k not in row for k in FIELDS):
        raise ValueError("missing_population_provenance")
    if row["schema"]!=VERSION or row["family"]!=family(row["sport"],row["stat"]):
        raise ValueError("invalid_market_or_version")
    date.fromisoformat(row["game_date"])
    for key in ("game_id","season","player_id","position","team","opponent","source_url"):
        if not isinstance(row[key],str) or not row[key].strip():
            raise ValueError("invalid_population_identity:"+key)
    if row["team"]==row["opponent"]:
        raise ValueError("identical_opposing_teams")
    if not isinstance(row["home"],bool):
        raise ValueError("missing_home_context")
    if not isinstance(row["source_sha256"],str) or not re.fullmatch(r"[0-9a-f]{64}",row["source_sha256"]):
        raise ValueError("invalid_historical_source_digest")
    if not isinstance(row["workload_unit"],str) or row["workload_unit"] not in ("minutes","snaps"):
        raise ValueError("unsupported_workload_source")
    if (row["sport"]=="NFL" and row["workload_unit"]!="snaps") or (
        row["sport"] in ("NHL","NBA") and row["workload_unit"]!="minutes"):
        raise ValueError("sport_workload_measurement_mismatch")
    if row["sport"]=="NHL" and (
        (row["stat"]=="saves" and row["position"]!="G") or
        (row["stat"]!="saves" and row["position"]=="G")):
        raise ValueError("goalie_skater_market_population_mismatch")
    workload=row["workload"]
    if isinstance(workload,bool) or not isinstance(workload,(float,int)) or not math.isfinite(workload) or not 0<workload<=300:
        raise ValueError("invalid_or_missing_observed_workload")
    value=row["value"]
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError("invalid_observed_value")
    if row["family"]=="count" and (not isinstance(value,int) or not 0<=value<=200):
        raise ValueError("invalid_count_or_negative_count")
    if row["family"]=="continuous" and not -150<=value<=1000:
        raise ValueError("invalid_signed_yards")
    return row


def make(*,sport,stat,game_id,game_date,season,player_id,position,team,
         opponent,home,value,workload,workload_unit,source_url,source_sha256):
    row=dict(schema=VERSION,sport=sport,stat=stat,family=family(sport,stat),
             game_id=str(game_id),game_date=str(game_date),season=str(season),
             player_id=str(player_id),position=str(position),team=str(team),
             opponent=str(opponent),home=home,value=value,workload=workload,
             workload_unit=workload_unit,source_url=str(source_url),
             source_sha256=source_sha256)
    return validate(row)


def path(root,sport,stat,season):
    family(sport,stat)
    if not re.fullmatch(r"\d{4}",str(season)):
        raise ValueError("invalid_season_partition")
    return Path(root)/"data/bayesian_warehouse/populations"/sport.lower()/slug(stat)/(str(season)+".jsonl.gz")


def read_shard(filename, *, progress=None):
    """Stream and verify a complete immutable shard; preserve row order.

    Progress is optional. Every row is validated, including records outside
    a later date filter; invalid history must never be silently skipped.
    """
    filename=Path(filename)
    if not filename.exists(): return []
    items=[]
    identities=set()
    expected_season=filename.name.removesuffix(".jsonl.gz")
    expected_stat=filename.parent.name
    expected_sport=filename.parent.parent.name
    with gzip.open(filename,"rt",encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():continue
            item=json.loads(line)
            validate(item)
            if (item["season"]!=expected_season or
                slug(item["stat"])!=expected_stat or
                item["sport"].lower()!=expected_sport):
                raise ValueError("shard_stat_or_season_mismatch")
            key=(item["game_id"],item["player_id"])
            if key in identities:raise ValueError("duplicate_player_market_game")
            identities.add(key)
            items.append(item)
            if progress is not None and len(items)%10000==0:
                progress(len(items))
    return items


def persist(root,rows):
    if not rows:raise ValueError("empty_population_batch")
    for item in rows:validate(item)
    groups={}
    for r in rows:
        filename=path(root,r["sport"],r["stat"],r["season"])
        groups.setdefault(filename,[]).append(r)
    changes={"inserted":0,"already_present":0,"shards":0}
    for filename,batch in sorted(groups.items()):
        old=read_shard(filename)
        existing={(r["game_id"],r["player_id"]):r for r in old}
        added=[]
        seen=set()
        for item in batch:
            key=(item["game_id"],item["player_id"])
            if key in seen:raise ValueError("duplicate_incoming_population_record")
            seen.add(key)
            if key in existing:
                if existing[key]!=item:raise ValueError("IMMUTABLE_POPULATION_SOURCE_CONFLICT")
                changes["already_present"]+=1
            else:
                added.append(item)
        if not added:continue
        rows_sorted=sorted(old+added,key=lambda r:(r["game_date"],r["game_id"],r["player_id"]))
        raw=("".join(canonical_json(x)+"\n" for x in rows_sorted)).encode()
        buffer=io.BytesIO()
        with gzip.GzipFile(filename="",mode="wb",fileobj=buffer,mtime=0,compresslevel=6) as gz:
            gz.write(raw)
        filename.parent.mkdir(parents=True,exist_ok=True)
        tmp=filename.with_suffix(".tmp")
        tmp.write_bytes(buffer.getvalue())
        os.replace(tmp,filename)
        changes["inserted"]+=len(added)
        changes["shards"]+=1
    return changes


def read(root,*,sport,stat,before,after=None,max_seasons=None,min_records=0,
         progress=None):
    family(sport,stat)
    end=date.fromisoformat(before)
    start=date.fromisoformat(after) if after else None
    folder=path(root,sport,stat,"2000").parent
    files=sorted(folder.glob("????.jsonl.gz"))
    if max_seasons is not None and (not isinstance(max_seasons,int) or max_seasons<1):
        raise ValueError("invalid_season_limit")
    rows=[]
    seen=set()
    for filename in files:
        if progress is not None:
            progress({"event":"shard_start","shard":filename.name})
        start_time=time.perf_counter()
        def on_shard_progress(count):
            if progress is not None:
                progress({"event":"shard_progress","shard":filename.name,"validated_rows":count})
        shard_rows=read_shard(filename, progress=on_shard_progress if progress is not None else None)
        selected=0
        for row in shard_rows:
            day=date.fromisoformat(row["game_date"])
            if day>=end or (start is not None and day<start):continue
            if not market_eligible(row):continue
            key=(row["game_id"],row["player_id"])
            if key in seen:raise ValueError("cross_shard_duplicate_population_record")
            seen.add(key); rows.append(row)
            selected+=1
        if progress is not None:
            progress({"event":"shard_done","shard":filename.name,
                      "validated_rows":len(shard_rows),"selected_rows":selected,
                      "seconds":round(time.perf_counter()-start_time,2)})
    # Select seasons only AFTER applying the as-of cutoff. Future season
    # shards may exist in the archive; their presence must not determine
    # which historical seasons a past model is allowed to train on.
    if max_seasons is not None:
        eligible=sorted({r["season"] for r in rows})[-max_seasons:]
        rows=[r for r in rows if r["season"] in eligible]
    rows.sort(key=lambda r:(r["game_date"],r["game_id"],r["player_id"]))
    if len(rows)<min_records:raise ValueError("insufficient_verified_population_history")
    return rows
