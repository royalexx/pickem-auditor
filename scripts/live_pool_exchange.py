#!/usr/bin/env python3
"""Source-linked GitHub daily data pool for pregame/settlement and future training.

The shared data/live-observations branch is append-only and isolated from main,
frozen precision campaigns, and data/shadow-calibration. No model is silently
trained/promoted here. Morning official player-game rows may be imported into a
future population warehouse ONLY with a strict, exclusive as-of cutoff.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCHEMA = "pickem_shared_live_pool_v1"
REPO = "royalexx/pickem-auditor"
BRANCH = "data/live-observations"
ROOT = Path(__file__).resolve().parents[1]
TORONTO = ZoneInfo("America/Toronto")
MAX_COMPRESSED = 8_000_000
# GitHub contents API accepts immutable 5 MB binary part blobs; the manifest
# is published LAST, so interrupted uploads do not expose partial cohorts.
ARCHIVE_PART_BYTES = 5_000_000
MAX_ARCHIVE_PARTS = 64
CHUNK_SCHEMA = "pickem_shared_live_pool_chunk_manifest_v1"
ALLOWED_PHASES = ("afternoon", "morning")
REQUIRED_POPULATION = (
    "schema","sport","stat","family","game_id","game_date","season","player_id",
    "position","team","opponent","home","value","workload","workload_unit",
    "source_url","source_sha256"
)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)

def sha256(value: bytes):
    return hashlib.sha256(value).hexdigest()

def today():
    return datetime.now(TORONTO).date().isoformat()

def day_before(day):
    return (date.fromisoformat(day)-timedelta(days=1)).isoformat()

def jsonl(path: Path):
    if not path.is_file():
        return []
    items=[]
    with path.open("rt",encoding="utf-8") as handle:
        for i,line in enumerate(handle,1):
            if not line.strip(): continue
            value=json.loads(line)
            if not isinstance(value,dict):
                raise ValueError("nonobject_jsonl_at_"+str(i)+":"+str(path))
            items.append(value)
    return items

def dump_jsonl(path, rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("".join(canonical(r)+"\n" for r in rows),encoding="utf-8")

def api(path, *, token, method="GET", payload=None):
    if not token:
        raise RuntimeError("GITHUB_TOKEN_MISSING: configure encrypted Deepnote environment variable with repo Contents read/write")
    if not path.startswith("/") or "://" in path or ".." in path:
        raise ValueError("unsafe_github_api_route")
    url="https://api.github.com/repos/"+REPO+path
    request=urllib.request.Request(url,
        data=(canonical(payload).encode("utf-8") if payload is not None else None),
        headers={"Accept":"application/vnd.github+json",
                 "Authorization":"Bearer "+token,
                 "X-GitHub-Api-Version":"2022-11-28",
                 "User-Agent":"pickem-auditor-live-pool",
                 "Content-Type":"application/json"},method=method)
    try:
        with urllib.request.urlopen(request,timeout=90) as response:
            raw=response.read()
        return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        # Never leak the token or the raw response URL into reports.
        raise RuntimeError("GITHUB_API_"+str(exc.code)+"_"+method+"_"+path.split("/")[1]) from None

def archive_path(day,phase,digest):
    date.fromisoformat(day)
    if phase not in ALLOWED_PHASES or not re.fullmatch(r"[0-9a-f]{64}",digest):
        raise ValueError("invalid_shared_pool_identity")
    return "data/live_pool/"+day+"/"+phase+"/"+digest+".json.gz"


def part_path(day, phase, compressed_sha, index):
    date.fromisoformat(day)
    if (phase not in ALLOWED_PHASES
            or not re.fullmatch(r"[0-9a-f]{64}", compressed_sha)
            or type(index) is not int or not 0 <= index < MAX_ARCHIVE_PARTS):
        raise ValueError("invalid_shared_pool_part_identity")
    return ("data/live_pool/" + day + "/" + phase + "/parts/" +
            compressed_sha + "." + f"{index:03}" + ".part")


def manifest_path(day, phase, digest):
    date.fromisoformat(day)
    if phase not in ALLOWED_PHASES or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("invalid_shared_pool_manifest_identity")
    return "data/live_pool/" + day + "/" + phase + "/" + digest + ".manifest.json"


def _put_immutable(path, payload, *, token):
    """Write a content-addressed file, verifying bytes on repeated/concurrent PUTs."""
    encoded=base64.b64encode(payload).decode("ascii")
    for attempt in range(4):
        try:
            result=api("/contents/"+path, token=token, method="PUT",
                       payload={"message":"Archive immutable Pickem chunk "+path.rsplit("/",1)[-1],
                                "content":encoded,"branch":BRANCH})
            return {"status":"published","commit_sha":result.get("commit",{}).get("sha")}
        except RuntimeError as exc:
            if "GITHUB_API_409_" not in str(exc) and "GITHUB_API_422_" not in str(exc):
                raise
            try:
                blob=api("/contents/"+path+"?ref="+urllib.parse.quote(BRANCH,safe=""),
                         token=token)
                if blob.get("sha") and read_blob(blob["sha"],token=token)==payload:
                    return {"status":"already_present"}
                if blob.get("sha"):
                    raise ValueError("IMMUTABLE_REMOTE_BUNDLE_CONFLICT:"+path)
            except RuntimeError as get_error:
                if "GITHUB_API_404_" not in str(get_error):
                    raise
            if attempt==3:
                raise
            time.sleep(.15 * (attempt+1))
    raise AssertionError("unreachable_immutable_put")


def publish_sharded(doc, *, token):
    """Split the ORIGINAL deterministic compressed bytes, never model forecasts.

    Supports oversized source-slate/quotes, sidecars and morning populations.
    Hash-verified parts are written before an atomic content-addressed manifest.
    Original pregame timestamps and raw win/push masses remain untouched.
    """
    payload=gzip.compress(canonical(doc).encode("utf-8"),compresslevel=6,mtime=0)
    if len(payload)<=MAX_COMPRESSED:
        raise ValueError("unnecessary_chunked_archive")
    size=ARCHIVE_PART_BYTES
    n=(len(payload)+size-1)//size
    if n>MAX_ARCHIVE_PARTS:
        raise ValueError("LIVE_POOL_TOO_MANY_ARCHIVE_PARTS")
    digest=sha256(payload)
    day,phase=doc["game_date"],doc["phase"]
    parts=[]
    count_published=0
    for idx in range(n):
        chunk=payload[idx*size:(idx+1)*size]
        path=part_path(day,phase,digest,idx)
        state=_put_immutable(path,chunk,token=token)
        count_published+=int(state["status"]=="published")
        parts.append({"path":path,"sha256":sha256(chunk),"bytes":len(chunk)})
    manifest={"schema":CHUNK_SCHEMA,"game_date":day,"phase":phase,
              "payload_sha256":digest,"payload_bytes":len(payload),
              "part_bytes":size,"parts":parts}
    raw=canonical(manifest).encode("utf-8")
    target=manifest_path(day,phase,sha256(raw))
    state=_put_immutable(target,raw,token=token)
    return {"status":state["status"],"path":target,"sha256":digest,
            "manifest_sha256":sha256(raw),"archive_format":"manifest_parts_v1",
            "part_count":n,"parts_published":count_published,
            "commit_sha":state.get("commit_sha")}


def _restore_manifest(raw, path, *, index, token):
    """Fail closed on missing, malformed or substituted immutable shard bytes."""
    try:
        manifest=json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("LIVE_POOL_MANIFEST_INVALID_JSON") from exc
    if not isinstance(manifest,dict) or manifest.get("schema")!=CHUNK_SCHEMA:
        raise ValueError("LIVE_POOL_MANIFEST_SCHEMA_INVALID")
    day,phase=manifest.get("game_date"),manifest.get("phase")
    digest=manifest.get("payload_sha256")
    if path!=manifest_path(day,phase,sha256(raw)):
        raise ValueError("LIVE_POOL_MANIFEST_PATH_MISMATCH")
    if not re.fullmatch(r"[0-9a-f]{64}",str(digest)):
        raise ValueError("LIVE_POOL_MANIFEST_PAYLOAD_DIGEST_INVALID")
    parts=manifest.get("parts")
    total=manifest.get("payload_bytes")
    if (not isinstance(parts,list) or not 2<=len(parts)<=MAX_ARCHIVE_PARTS
            or type(total) is not int or total<=MAX_COMPRESSED
            or total>MAX_ARCHIVE_PARTS*ARCHIVE_PART_BYTES
            or manifest.get("part_bytes")!=ARCHIVE_PART_BYTES):
        raise ValueError("LIVE_POOL_MANIFEST_PARTS_INVALID")
    payload=[]
    for i, part in enumerate(parts):
        expected=part_path(day,phase,digest,i)
        if not isinstance(part,dict) or part.get("path")!=expected:
            raise ValueError("LIVE_POOL_SHARD_PATH_MISMATCH")
        stored=index.get(expected)
        if not stored:
            raise ValueError("LIVE_POOL_SHARD_MISSING:"+expected)
        chunk=read_blob(stored,token=token)
        if (sha256(chunk)!=part.get("sha256") or len(chunk)!=part.get("bytes")
                or not 0<len(chunk)<=ARCHIVE_PART_BYTES):
            raise ValueError("LIVE_POOL_SHARD_DIGEST_MISMATCH:"+expected)
        payload.append(chunk)
    content=b"".join(payload)
    if len(content)!=total or sha256(content)!=digest:
        raise ValueError("LIVE_POOL_SHARDED_PAYLOAD_DIGEST_MISMATCH")
    doc=unpack(content)
    if doc.get("game_date")!=day or doc.get("phase")!=phase:
        raise ValueError("LIVE_POOL_MANIFEST_METADATA_MISMATCH")
    return doc


def pack(doc):
    raw=canonical(doc).encode("utf-8")
    payload=gzip.compress(raw,compresslevel=6,mtime=0)
    if len(payload)>MAX_COMPRESSED:
        raise ValueError("LIVE_POOL_BUNDLE_TOO_LARGE: split sport/source by date before publication")
    return payload

def unpack(data):
    obj=json.loads(gzip.decompress(data))
    if obj.get("schema")!=SCHEMA or obj.get("phase") not in ALLOWED_PHASES:
        raise ValueError("unrecognized_live_pool_schema")
    date.fromisoformat(obj["game_date"])
    return obj

def pick_latest(rows,day,*,run_id=None):
    candidates=[r for r in rows if r.get("game_date")==day and r.get("run_type")=="shadow"]
    if run_id is None and candidates:
        last=max(candidates,key=lambda r:(str(r.get("forecast_at") or ""),str(r.get("run_id") or "")))
        run_id=last.get("run_id")
    if run_id is None:return [],None
    batch=[r for r in candidates if r.get("run_id")==run_id]
    if any(not r.get("forecast_at") for r in batch):
        raise ValueError("pregame_forecast_timestamp_required")
    return batch,run_id

def bundle(root: Path, *, phase, game_date, snapshot_path=None, population_path=None, run_id=None):
    date.fromisoformat(game_date)
    if phase not in ALLOWED_PHASES:raise ValueError("unknown_phase")
    source=root/"data"
    snapshot=Path(snapshot_path) if snapshot_path else source/"prop_snapshots.jsonl"
    records=jsonl(snapshot)
    population=jsonl(Path(population_path)) if population_path else []
    if phase=="afternoon":
        forecasts,selected_run=pick_latest(records,game_date,run_id=run_id)
        if not forecasts:raise ValueError("no_new_pregame_forecasts_to_archive")
        if any(r.get("actual_stat") is not None for r in forecasts):
            raise ValueError("pregame_forecast_already_contains_outcome")
        settlements=[]
    else:
        forecasts=[]
        settlements=[r for r in records if r.get("game_date")==game_date and
            r.get("actual_stat") is not None and r.get("outcome") in ("win","loss","push")]
        selected_run=run_id or "morning"
        if any(r.get("settled_at") is None for r in settlements):
            raise ValueError("settled_row_missing_settlement_timestamp")
        if not settlements and not population:
            raise ValueError("no_settled_predictions_or_training_observations")
        if any(r.get("game_date")!=game_date for r in population):
            raise ValueError("population_date_mismatch")

    source_quotes=jsonl(source/"odds_quotes.jsonl") if phase=="afternoon" else []
    source_slate=jsonl(source/"slate_fetch.jsonl") if phase=="afternoon" else []
    source_quotes=[q for q in source_quotes if q.get("game_date") in (None,game_date)]
    source_slate=[r for r in source_slate if r.get("game_date")==game_date]
    shadow={}
    for key,folder in (("bayesian_a","bayesian_shadow"),("bayesian_b","bayesian_b_shadow"),
                       ("monte_carlo","posterior_mc"),("online_bayes","online_bayes_shadow"),
                       ("nhl_saves_nuts","nhl_joint_saves_shadow"),
                       ("nfl_targets_nuts","nfl_context"),
                       ("population_nuts","population_nuts_shadow"),
                       ("provisional_nuts","provisional_nuts_shadow"),
                       ("model_comparisons","model_comparisons")):
        rows=jsonl(source/folder/(game_date+".jsonl")) if phase=="afternoon" else []
        if key=="nfl_targets_nuts":
            # Independent targets projections have their own immutable run id;
            # genuine sportsbook target lines remain linked to the selected run.
            shadow[key]=[r for r in rows if (
                r.get("run_id")==selected_run or (
                  r.get("line_origin")=="research_threshold"
                  and r.get("run_id","").startswith("targets-projection:")))]
        else:
            shadow[key]=[r for r in rows if r.get("run_id")==selected_run]
    meta=source/"slate_fetch.meta.json"
    source_meta=json.loads(meta.read_text()) if phase=="afternoon" and meta.is_file() else None
    # Retain already-collected, time-stamped same-book quotes in the identical
    # immutable prospective packet as original predictions, not in a later
    # reconstruction. Verify the normalized archive's SHA before publication.
    market_quote_archive=[]
    phase0_pregame_receipt=None
    if phase=="afternoon":
        from market_odds_archive import SCHEMA as ODDS_SCHEMA, digest as odds_digest
        odds_folder=source/"market_odds_history"/game_date/"afternoon"
        for odds_path in sorted(odds_folder.glob("*.json")):
            archive_doc=json.loads(odds_path.read_text(encoding="utf-8"))
            checksum=archive_doc.get("snapshot_sha256")
            if (archive_doc.get("schema")!=ODDS_SCHEMA
                    or archive_doc.get("date")!=game_date
                    or archive_doc.get("phase")!="afternoon"
                    or odds_digest({k:v for k,v in archive_doc.items()
                                    if k!="snapshot_sha256"})!=checksum):
                raise ValueError("invalid_original_market_quote_archive")
            market_quote_archive.append(archive_doc)
        evidence_path=root/"reports/phase0_pregame_provenance.json"
        if evidence_path.is_file():
            candidate=json.loads(evidence_path.read_text(encoding="utf-8"))
            if (candidate.get("schema")=="pickem_phase0_pregame_provenance_v1"
                    and candidate.get("game_date")==game_date
                    and candidate.get("selected_run_id")==selected_run
                    and candidate.get("publication_eligible") is False):
                phase0_pregame_receipt=candidate
    raw_source_path=root/"data/live_pool_staging/raw"/(game_date+".json")
    raw_collected_sources=(json.loads(raw_source_path.read_text())
                           if phase=="morning" and raw_source_path.is_file() else {})
    observations=[]
    for row in population:
        if any(key not in row for key in REQUIRED_POPULATION):
            raise ValueError("population_provenance_missing")
        observations.append(row)

    raw_nhl=[]
    if phase=="morning":
        for file in sorted((source/"nhl/games"/game_date).glob("*.json")):
            content=json.loads(file.read_text())
            if content.get("game_date")!=game_date or content.get("state") not in ("FINAL","OFF"):
                raise ValueError("invalid_official_NHL_game_summary")
            raw_nhl.append(content)
    receipt_path=root/"reports"/("live_population_collect_"+game_date+".json")
    collection_receipt=(json.loads(receipt_path.read_text())
                        if phase=="morning" and receipt_path.is_file() else None)
    doc={"schema":SCHEMA,"game_date":game_date,"phase":phase,
         "captured_at_utc":datetime.now(timezone.utc).isoformat(),
         "source":"Deepnote cloud inference / completed-game independent verification",
         "predictions_are_frozen":True,"run_id":selected_run,
         "forecasts":forecasts,"settlements":settlements,
         "population":observations,"population_collection_receipt":collection_receipt,"raw_completed_game_sources":raw_collected_sources,"nhl_completed_boxscores":raw_nhl,
         "source_slate":source_slate,"source_quotes":source_quotes,
         "source_meta":source_meta,
         "market_quote_archive":market_quote_archive,
         "phase0_pregame_receipt":phase0_pregame_receipt,
         "shadow":shadow,
         "verification_state":"research_only; no retrospective model upgrades"}
    if phase=="afternoon" and any(
            (r.get("game_date")!=game_date for r in source_slate)):
        raise ValueError("source_date_mismatch")
    return doc


def write_recovery_copy(doc, directory):
    """Keep the complete original immutable bundle if GitHub publication fails.

    This is private Deepnote project storage, not a regenerated postgame model.
    It stores no credentials. The name pins the bytes and the capture cohort.
    """
    if not directory:
        return None
    payload=gzip.compress(canonical(doc).encode("utf-8"),compresslevel=6,mtime=0)
    digest=sha256(payload)
    day,phase=doc["game_date"],doc["phase"]
    date.fromisoformat(day)
    if phase not in ALLOWED_PHASES:
        raise ValueError("recovery_invalid_phase")
    dest=Path(directory)
    dest.mkdir(parents=True,exist_ok=True)
    path=dest/("live_pool_"+day+"_"+phase+"_"+digest+".json.gz")
    if path.exists():
        if path.read_bytes()!=payload:
            raise ValueError("IMMUTABLE_RECOVERY_COPY_CONFLICT")
        return path
    temp=path.with_name(path.name+".tmp")
    temp.write_bytes(payload)
    os.replace(temp,path)
    return path


def load_recovery_copy(file):
    path=Path(file)
    match=re.fullmatch(r"live_pool_(\d{4}-\d{2}-\d{2})_(afternoon|morning)_([0-9a-f]{64})\.json\.gz",path.name)
    if match is None:
        raise ValueError("RECOVERY_COPY_IDENTITY_INVALID")
    payload=path.read_bytes()
    if sha256(payload)!=match.group(3):
        raise ValueError("RECOVERY_COPY_DIGEST_MISMATCH")
    doc=unpack(payload)
    if doc.get("game_date")!=match.group(1) or doc.get("phase")!=match.group(2):
        raise ValueError("RECOVERY_COPY_METADATA_MISMATCH")
    for row in doc.get("forecasts") or []:
        if (row.get("game_date")!=doc["game_date"]
                or row.get("actual_stat") is not None
                or not row.get("forecast_at")):
            raise ValueError("RECOVERY_COPY_NOT_FROZEN_PREGAME")
        try:
            forecast=datetime.fromisoformat(row["forecast_at"].replace("Z","+00:00"))
            start=datetime.fromisoformat(row["event_start"].replace("Z","+00:00"))
            if forecast.tzinfo is None or start.tzinfo is None or forecast>=start:
                raise ValueError("RECOVERY_COPY_FORECAST_NOT_PREGAME")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("RECOVERY_COPY_FORECAST_NOT_PREGAME") from exc
    return doc


def publish(doc, *,token):
    # Retain the compact legacy format for old/small datasets. Fall back to
    # independent immutable chunks for a larger archive; do not truncate.
    try:
        payload=pack(doc)
    except ValueError as exc:
        if str(exc).startswith("LIVE_POOL_BUNDLE_TOO_LARGE"):
            return publish_sharded(doc,token=token)
        raise
    digest=sha256(payload)
    path=archive_path(doc["game_date"],doc["phase"],digest)
    encoded=base64.b64encode(payload).decode("ascii")
    try:
        result=api("/contents/"+path,token=token,method="PUT",
                   payload={"message":"Archive "+doc["game_date"]+" "+doc["phase"]+
                            " source-verified Pickem observations",
                            "content":encoded,"branch":BRANCH})
    except RuntimeError as exc:
        if "GITHUB_API_422_" in str(exc) or "GITHUB_API_409_" in str(exc):
            # Concurrent identical writes are not silently overwritten.
            blob=api("/contents/"+path+"?ref="+urllib.parse.quote(BRANCH,safe=""),
                     token=token)
            if not blob.get("sha"):raise
            remote=read_blob(blob["sha"],token=token)
            if remote!=payload:raise ValueError("IMMUTABLE_REMOTE_BUNDLE_CONFLICT")
            return {"status":"already_present","path":path,"sha256":digest}
        raise
    return {"status":"published","path":path,"sha256":digest,
            "commit_sha":result.get("commit",{}).get("sha")}

def read_blob(blob_sha,*,token):
    if not re.fullmatch("[0-9a-f]{40}",blob_sha):raise ValueError("invalid_blob_identity")
    blob=api("/git/blobs/"+blob_sha,token=token)
    if blob.get("encoding")!="base64" or not isinstance(blob.get("content"),str):
        raise ValueError("unsupported_github_blob_encoding")
    return base64.b64decode(blob["content"])

def iter_remote_docs(*,token,before,after=None,phase=None):
    cutoff=date.fromisoformat(before)
    begin=date.fromisoformat(after) if after else None
    tree=api("/git/trees/"+BRANCH+
             "?recursive=1",token=token)
    if tree.get("truncated"):raise RuntimeError("GITHUB_TREE_TRUNCATED")
    entries=[]
    index={item.get("path"):item.get("sha") for item in tree.get("tree",[])
           if item.get("type","blob")=="blob"}
    for item in tree.get("tree",[]):
        path=item.get("path","")
        parts=path.split("/")
        if (len(parts)!=5 or parts[:2]!=["data","live_pool"]
                or parts[3] not in ALLOWED_PHASES
                or not (parts[4].endswith(".json.gz")
                        or parts[4].endswith(".manifest.json"))):
            continue
        try:day=date.fromisoformat(parts[2])
        except ValueError:continue
        if day>=cutoff or (begin and day<begin) or (phase and parts[3]!=phase):
            continue
        entries.append((path,item["sha"]))
    for path,sha in sorted(entries):
        payload=read_blob(sha,token=token)
        if path.endswith(".manifest.json"):
            doc=_restore_manifest(payload,path,index=index,token=token)
        else:
            if sha256(payload)!=Path(path).name[:-len(".json.gz")]:
                raise ValueError("LIVE_POOL_HASH_MISMATCH:"+path)
            doc=unpack(payload)
            if path!=archive_path(doc["game_date"],doc["phase"],sha256(payload)):
                raise ValueError("LIVE_POOL_PATH_METADATA_MISMATCH:"+path)
        yield doc,path

def canonical_afternoon_docs(documents):
    """Deterministically use the first archived frozen batch for each game date.

    Later same-day reruns are independent immutable evidence, but never replace
    or merge into the original prospective evaluation cohort. Each selected
    batch keeps its original associated Bayesian/Monte Carlo sidecars.
    """
    selected={}
    for doc in documents:
        if doc.get("phase")!="afternoon":
            raise ValueError("CANONICAL_SELECTION_REQUIRES_AFTERNOON_BUNDLE")
        day=doc.get("game_date")
        date.fromisoformat(day)
        raw_stamp=doc.get("captured_at_utc")
        try:
            stamp=datetime.fromisoformat(str(raw_stamp).replace("Z","+00:00"))
        except (ValueError,TypeError) as exc:
            raise ValueError("AFTERNOON_CAPTURE_TIMESTAMP_MISSING_OR_INVALID") from exc
        if stamp.tzinfo is None:
            raise ValueError("AFTERNOON_CAPTURE_TIMESTAMP_UNZONED")
        stamp=stamp.astimezone(timezone.utc)
        forecasts=doc.get("forecasts")
        if not isinstance(forecasts,list) or not forecasts:
            raise ValueError("AFTERNOON_FROZEN_FORECASTS_EMPTY")
        if any(r.get("game_date")!=day or r.get("actual_stat") is not None
               or not r.get("forecast_at") for r in forecasts):
            raise ValueError("INVALID_FROZEN_PREGAME_BATCH")
        prev=selected.get(day)
        if prev is not None and prev[0]==stamp and prev[1]!=doc:
            raise ValueError("AMBIGUOUS_SAME_INSTANT_FORECAST_ARCHIVES")
        if prev is None or stamp<prev[0]:
            selected[day]=(stamp,doc)
    return {day:pair[1] for day,pair in selected.items()}

def restore_forecasts(*, token, before, after, dest):
    """Restore one immutable first-published afternoon batch per game date."""
    docs=list(iter_remote_docs(token=token,before=before,after=after,phase="afternoon"))
    canonical_days=canonical_afternoon_docs(doc for doc,_ in docs)
    rows={}
    for day,doc in sorted(canonical_days.items()):
        for r in doc["forecasts"]:
            ident=(r.get("game_date"),r.get("run_id"),r.get("sport"),
                   r.get("player_id") or r.get("player"),r.get("stat"),
                   r.get("side"),r.get("reference_line"))
            if ident in rows and rows[ident]!=r:
                raise ValueError("CONFLICT_WITHIN_CANONICAL_AFTERNOON_ARCHIVE")
            rows[ident]=r
    dump_jsonl(dest,list(rows.values()))
    return {"restored_forecasts":len(rows),"bundles":len(docs),
            "canonical_dates":len(canonical_days),
            "later_immutable_reruns_excluded":len(docs)-len(canonical_days),
            "selection_policy":"first_archived_pregame_batch_per_date",
            "path":str(dest)}

def collect_population(root: Path, *, day, sports=("NHL","NBA","NFL")):
    # Only previous finalized games, never a pregame snapshot.
    if date.fromisoformat(day)>=datetime.now(TORONTO).date():
        raise ValueError("population_requires_past_completed_date")
    import population_backfill as fetch
    import population_nfl
    import population_normalizers as norm
    import population_history as hist
    all_rows=[]
    raw_sources={}
    result={"schema":"live_population_collect_v1","game_date":day,"sports":{},
            "completed_games":{},"per_stat":{},"errors":{}}
    for sport in sports:
        rows=[]
        source_games=[]
        try:
            if sport=="NHL":
                board=fetch.fetch_json(norm.NHL_BASE+"/score/"+day,spacing=.1)
                game_ids=fetch.nhl_games(board)
                for gid in game_ids:
                    raw=fetch.fetch_json(norm.NHL_BASE+"/gamecenter/"+str(gid)+"/boxscore",spacing=.1)
                    rows.extend(norm.nhl_game(raw,day,expected_id=gid))
                    source_games.append(raw)
            elif sport=="NBA":
                board=fetch.fetch_json(norm.NBA_BASE+"/scoreboard?dates="+day.replace("-","")+"&limit=100",spacing=.1)
                game_ids=norm.scoreboard_games("NBA",board,day)
                for gid in game_ids:
                    raw=fetch.fetch_json(norm.NBA_BASE+"/summary?event="+str(gid),spacing=.1)
                    rows.extend(norm.nba_game(raw,day,gid))
                    source_games.append(raw)
            elif sport=="NFL":
                season=int(day[:4])
                if int(day[5:7])<=3:season-=1
                stats,snaps,schedule=population_nfl.fetch_season(season)
                cohort,coverage=population_nfl.normalize_season(
                    stats,snaps,schedule,season,cutoff=(date.fromisoformat(day)+timedelta(days=1)).isoformat())
                rows=[r for r in cohort if r["game_date"]==day]
                game_ids=sorted({r["game_id"] for r in rows})
                result["sports"]["NFL_source_coverage"]=coverage
                chosen_games=[g for g in schedule if str(g.get("gameday") or "")[:10]==day
                              and str(g.get("season") or "")==str(season)
                              and g.get("game_type")=="REG"]
                teams_by_week={(g.get("week"),team) for g in chosen_games
                               for team in (g.get("home_team"),g.get("away_team"))}
                selected_ids={str(g.get("game_id")) for g in chosen_games}
                source_games=[{"schedule":chosen_games,
                    "player_stats":[r for r in stats if (r.get("week"),r.get("team") or r.get("recent_team")) in teams_by_week
                                    and r.get("season_type")=="REG"],
                    "snap_counts":[r for r in snaps if str(r.get("game_id")) in selected_ids]}]
            else:
                raise ValueError("unrecognized_sport")
            for row in rows:
                hist.validate(row)
                if row["game_date"]!=day:raise ValueError("wrong_game_date")
            result["sports"][sport]={"rows":len(rows),"games":len(set(r["game_id"] for r in rows))}
            result["completed_games"][sport]=len(game_ids)
            result["per_stat"][sport]=dict(sorted(Counter(r["stat"] for r in rows).items()))
            all_rows.extend(rows)
            raw_sources[sport]=source_games
        except Exception as exc:
            # A sport's unavailable source cannot be mislabeled as complete.
            result["errors"][sport]=type(exc).__name__+":"+str(exc)[:300]
    result["status"]="complete" if not result["errors"] else "partial_source_failure"
    raw_path=root/"data/live_pool_staging/raw"/(day+".json")
    raw_path.parent.mkdir(parents=True,exist_ok=True)
    raw_path.write_text(canonical(raw_sources)+"\n")
    receipt=root/"reports"/("live_population_collect_"+day+".json")
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    out=root/"data/live_pool_staging/populations"/(day+".jsonl")
    dump_jsonl(out,all_rows)
    return result,out

def import_population(root, *,token,before,after=None):
    import population_history as hist
    existing_by_shard={}
    seen={}
    accepted=[]
    skipped=Counter()
    examples={}
    packages=0
    for doc,path in iter_remote_docs(token=token,before=before,after=after,phase="morning"):
        packages+=1
        for r in doc.get("population",[]):
            hist.validate(r)
            if r["game_date"]!=doc["game_date"]:
                raise ValueError("MISMATCHED_GAME_DATE_IN_LIVE_POOL")
            ident=(r["sport"],r["stat"],r["game_id"],r["player_id"])
            shard=hist.path(root,r["sport"],r["stat"],r["season"])
            if shard not in existing_by_shard:
                existing_by_shard[shard]={
                    (p["game_id"],p["player_id"]):p for p in hist.read_shard(shard)}
            previous=seen.get(ident) or existing_by_shard[shard].get(ident[2:])
            if previous:
                # Same observed game/player/stat from a different source is ONE
                # training event, not independent evidence. Different measured
                # values/exposures mean a source conflict requiring review.
                core=("sport","stat","game_id","game_date","season","player_id",
                      "position","team","opponent","home","value","workload","workload_unit")
                if any(previous.get(k)!=r.get(k) for k in core):
                    examples[str(ident)]={"prior_source":previous.get("source_url"),
                                          "new_source":r.get("source_url")}
                    raise ValueError("LIVE_SOURCE_OBSERVATION_CONFLICT:"+str(ident))
                skipped["same_player_game_stat"]+=1
                continue
            seen[ident]=r
            accepted.append(r)
    counts=hist.persist(root,accepted) if accepted else {"inserted":0,"already_present":0,"shards":0}
    return {"schema":"live_population_import_v1","before_exclusive":before,
            "after_inclusive":after,"remote_bundles_checked":packages,
            "records_imported":counts["inserted"],"redundant":dict(skipped),
            "shards_modified":counts["shards"],"original_source_records_preserved":True,
            "no_outcome_training_leakage":True,"production_models_changed":False}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="cmd",required=True)
    for command in ("collect","publish","publish-frozen","import","restore-forecasts"):
        subp=sub.add_parser(command)
        subp.add_argument("--root",type=Path,default=ROOT)
        subp.add_argument("--day")
        if command=="collect":
            subp.add_argument("--sports",default="NHL,NBA,NFL")
        if command=="publish-frozen":
            subp.add_argument("--frozen",type=Path,required=True)
        if command=="publish":
            subp.add_argument("--phase",choices=ALLOWED_PHASES,required=True)
            subp.add_argument("--snapshots",type=Path)
            subp.add_argument("--population",type=Path)
            subp.add_argument("--run-id")
        if command in ("import","restore-forecasts"):
            subp.add_argument("--before",required=True)
            subp.add_argument("--after")
        if command=="restore-forecasts":
            subp.add_argument("--dest",type=Path,required=True)
    args=p.parse_args(argv)
    if args.cmd=="collect":
        day=args.day or day_before(today())
        sports=tuple(k.strip().upper() for k in args.sports.split(","))
        result,_=collect_population(args.root,day=day,sports=sports)
    elif args.cmd=="publish":
        day=args.day or (today() if args.phase=="afternoon" else day_before(today()))
        doc=bundle(args.root,phase=args.phase,game_date=day,
                   snapshot_path=args.snapshots,population_path=args.population,
                   run_id=args.run_id)
        # Persistent, checksum-addressed local copy is written BEFORE network.
        # This makes future repair possible without another model invocation.
        recovery=write_recovery_copy(
            doc,os.environ.get("PICKEM_LIVE_ARCHIVE_RECOVERY_DIR"))
        result=publish(doc,token=os.environ.get("GITHUB_TOKEN"))
        if recovery:result["recovery_copy"]=str(recovery)
        result["forecasts"]=len(doc["forecasts"])
        result["settlements"]=len(doc["settlements"])
        result["population"]=len(doc["population"])
    elif args.cmd=="publish-frozen":
        # Reads and verifies bytes captured before the game. No new model
        # computation or source fetch occurs at any point in recovery.
        doc=load_recovery_copy(args.frozen)
        result=publish(doc,token=os.environ.get("GITHUB_TOKEN"))
        result["restored_from_frozen_bytes"]=True
        result["original_forecasts"]=len(doc.get("forecasts") or [])
    elif args.cmd=="import":
        result=import_population(args.root,token=os.environ.get("GITHUB_TOKEN"),
                                 before=args.before,after=args.after)
    else:
        # Later archived reruns remain untouched but are never mixed into
        # the first published prospective cohort for the same game date.
        result=restore_forecasts(token=os.environ.get("GITHUB_TOKEN"),
                                 before=args.before,after=args.after,dest=args.dest)
    print(json.dumps(result,sort_keys=True))
    return 0 if result.get("status") not in ("partial_source_failure",) else 2

if __name__=="__main__":
    sys.exit(main())
