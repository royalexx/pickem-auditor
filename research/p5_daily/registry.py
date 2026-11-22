"""Append-only P5 research model registry, chronological observations, and rollback.

All code is opt-in research. No forecasting mathematics, collectors, live
schedules, V1 weights, NHL locked C10 parameters, or NFL state are changed.
"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import contextlib
import fcntl
import uuid
import hashlib
import json
import os
import re
import tempfile

from .scoring import _utc, digest, ScoreError

VERSION="PA-P5-REGISTRY/1"
OPS={"INCREMENTAL_UPDATE","SUFFICIENT_STATISTICS_REFRESH","BOUNDED_REFIT",
     "PERIODIC_FULL_REFIT","PREDICTION_ONLY","NO_ELIGIBLE_UPDATE",
     "BLOCKED","RESEARCH_ONLY"}
LOCKED_NHL_ID="EXP-V25-NHL-SOG-NB2-NATIVE-PLUGIN-MEAN-20261114"

POLICY={
    "NBA_S0":{"PERIODIC_FULL_REFIT"},
    "NBA_S1":{"PERIODIC_FULL_REFIT"},
    "NBA_S2":{"PERIODIC_FULL_REFIT"},
    "NBA_O":{"PREDICTION_ONLY"},
    "NBA_J":{"PREDICTION_ONLY"},
    "NBA_C":{"PREDICTION_ONLY"},
    "NHL_PLUGIN_POISSON_LOCKED":{"PREDICTION_ONLY"},
    "NHL_GAMMA_LOCKED":{"PREDICTION_ONLY"},
    "NHL_NATIVE_NB2_LOCKED":{"PREDICTION_ONLY"},
    "NHL_GAMMA_ADAPTIVE":{"INCREMENTAL_UPDATE"},
}

def _need(ok,code):
    if not ok:
        raise ScoreError(code)

def _canon(x):
    return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def _secure_root(root):
    p=Path(root)
    _need(not p.is_symlink() and p.is_dir(),"REGISTRY_ROOT_NOT_VERIFIED")
    return p.resolve(strict=True)

def _safe(root, rel):
    _need(isinstance(rel,str) and bool(rel) and
          not Path(rel).is_absolute() and not any(x in ("..",".","") for x in rel.split("/")),
          "REGISTRY_PATH_INVALID")
    p=Path(root)/rel
    for t in [p,*p.parents]:
        if t==Path(root):
            break
        _need(not t.is_symlink(),"REGISTRY_SYMLINK_INVALID")
    _need(p.resolve(strict=False).is_relative_to(Path(root).resolve()),"REGISTRY_PATH_ESCAPE")
    return p

def _write_once(root, relative, obj):
    path=_safe(root,relative)
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=_canon(obj)
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    try:
        fd=os.open(path, flags, 0o600)
    except FileExistsError:
        _need(not path.is_symlink() and path.read_bytes()==raw,
              "IMMUTABLE_RECORD_CONFLICT_OR_CORRUPTION")
        return {"status":"IDEMPOTENT_EXISTING","path":relative,"sha256":hashlib.sha256(raw).hexdigest()}
    with os.fdopen(fd,"wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    _need(path.read_bytes()==raw,"IMMUTABLE_WRITE_FAILED")
    return {"status":"APPENDED","path":relative,"sha256":hashlib.sha256(raw).hexdigest()}

def _write_transition_once(root, relative, obj):
    """Prepare verified bytes; commit by exclusive creation of an EMPTY marker.

    Project FUSE rejected os.link(), so the hardlink activation is retired.
    An immutable JSON record is fsynced and independently reread BEFORE the
    zero-byte O_EXCL commit marker is created. The marker's single filesystem
    namespace operation defines visibility. A crash before that call leaves
    only an ignored prepared record; after it, the complete original bytes
    are addressable by SHA. No rename, overwrite or hardlink is required.

    This protocol still requires the actual mount's O_EXCL, flock, fsync and
    cross-detached recovery tests; owner unit tests alone do not qualify it.
    """
    base=_secure_root(root)
    requested=_safe(base,relative)
    requested.parent.mkdir(parents=True,exist_ok=True)
    raw=_canon(obj)
    checksum=hashlib.sha256(raw).hexdigest()
    seq=obj.get("sequence")
    _need(type(seq) is int and seq>0 and requested.name==f"{seq:08d}.json",
          "TRANSITION_SEQUENCE_INVALID")
    # Every attempt has its own prepared path, so crashed partial writes do
    # not have to be mutated, deleted, or mistaken for a committed transition.
    nonce=uuid.uuid4().hex
    stem=f"{seq:08d}-{checksum}-{nonce}"
    prepared=requested.parent/(stem+".json")
    marker=requested.parent/(stem+".commit")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    try:
        fd=os.open(prepared,flags,0o600)
        with os.fdopen(fd,"wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        _need(prepared.read_bytes()==raw,"TRANSITION_PREPARED_BYTES_INVALID")
        fd=os.open(marker,flags,0o600)
        try:
            # Empty marker: its creation is the entire commit operation.
            # No partially written marker can ever be considered committed.
            os.fsync(fd)
        finally:
            os.close(fd)
        _need(marker.is_file() and not marker.is_symlink()
              and marker.stat().st_size==0,"TRANSITION_COMMIT_MARKER_INVALID")
    except (OSError,ValueError) as exc:
        raise ScoreError("TRANSITION_PREPARE_OR_COMMIT_UNSUPPORTED") from exc
    _need(prepared.read_bytes()==raw,"TRANSITION_POSTCOMMIT_SHA_DRIFT")
    return {"status":"APPENDED","path":str(prepared.relative_to(base)),
            "commit_marker":str(marker.relative_to(base)),
            "sha256":checksum}


def _read(root,relative,expected_sha=None):
    path=_safe(root,relative)
    _need(path.is_file() and not path.is_symlink(),"REGISTRY_ARTIFACT_MISSING")
    raw=path.read_bytes()
    if expected_sha is not None:
        _need(hashlib.sha256(raw).hexdigest()==expected_sha,
              "REGISTRY_SHA_MISMATCH")
    try:
        return json.loads(raw)
    except ValueError as ex:
        raise ScoreError("REGISTRY_JSON_CORRUPTED") from ex

@contextlib.contextmanager
def _lock(root, *, read_only=False):
    """Shared readers never request write permissions on the Deepnote mount."""
    _secure_root(root)
    lock=_safe(root,"registry.lock")
    flags=os.O_RDONLY if read_only else os.O_CREAT|os.O_RDWR
    if hasattr(os,"O_NOFOLLOW"):
        flags|=os.O_NOFOLLOW
    fd=os.open(lock,flags,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_SH if read_only else fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)

def _safe_id(s):
    _need(isinstance(s,str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,150}",s),
          "REGISTRY_MODEL_ID_INVALID")
    return s

def read_transitions(root, model_id):
    """Only verified committed markers count; every orphan stays invisible."""
    base=_secure_root(root)
    name=_safe_id(model_id)
    folder=_safe(base,"transitions/"+name)
    if not folder.exists():
        return []
    out=[]
    found=set()
    for marker in sorted(folder.glob("*.commit")):
        _need(marker.is_file() and not marker.is_symlink()
              and marker.stat().st_size==0,"REGISTRY_COMMIT_MARKER_CORRUPTED")
        parts=marker.stem.split("-")
        _need(len(parts)==3 and len(parts[0])==8 and parts[0].isdigit()
              and re.fullmatch(r"[0-9a-f]{64}",parts[1])
              and re.fullmatch(r"[0-9a-f]{32}",parts[2]),
              "REGISTRY_COMMIT_MARKER_FILENAME_INVALID")
        seq=int(parts[0])
        _need(seq not in found,"REGISTRY_DUPLICATE_COMMITTED_SEQUENCE")
        found.add(seq)
        relative=str(marker.relative_to(base)).removesuffix(".commit")+".json"
        path=_safe(base,relative)
        _need(not path.is_symlink() and path.is_file(),
              "REGISTRY_COMMITTED_TRANSITION_MISSING")
        row=_read(base,relative,parts[1])
        _need(row.get("sequence")==seq and row.get("model_id")==name,
              "REGISTRY_SEQUENCE_OR_MODEL_MISMATCH")
        out.append(row)
    out.sort(key=lambda x:x["sequence"])
    for i,row in enumerate(out,1):
        _need(row["sequence"]==i,"REGISTRY_TRANSITION_GAP")
    return out


def _latest(root, model_id):
    entries=read_transitions(root,model_id)
    if not entries:
        return None
    last=entries[-1]
    artifact=_read(root,last["artifact_path"],last["artifact_sha256"])
    _need(artifact.get("model_id")==model_id and
          digest({k:v for k,v in artifact.items() if k!="payload_sha256"})==artifact.get("payload_sha256"),"REGISTRY_TRANSITION_BROKEN")
    return artifact

def register_model(root, *, model_id, family, pipeline_id, sport,
                   state, parent_version, training_rows, cutoff_at,
                   created_at, code_commit, update_mode, seed, diagnostics,
                   passed_validation, approval="research_eligible"):
    """Serial commit: data artifact first, activation transition LAST.

    A crash after the model blob but before transition leaves an orphan,
    never an active new version. Earlier versions are not overwritten.
    """
    base=_secure_root(root)
    _safe_id(model_id)
    _need(sport in ("NBA","NHL"),"UNSUPPORTED_SPORT")
    _need(isinstance(code_commit,str) and re.fullmatch("[0-9a-f]{40}",code_commit),
          "UNPINNED_CODE_COMMIT")
    _need(update_mode in OPS,"UNKNOWN_UPDATE_OPERATION")
    _need(update_mode in POLICY.get(family,set()),"MODEL_UPDATE_OPERATION_NOT_APPROVED")
    _need(approval=="research_eligible","PRODUCTION_PROMOTION_FORBIDDEN")
    _need(passed_validation is True,"RESEARCH_MODEL_VALIDATION_FAILED")
    _need(isinstance(seed,int) and seed>=0,"MODEL_SEED_INVALID")
    _need(_utc(cutoff_at)<=_utc(created_at),"UPDATE_CUTOFF_AFTER_CREATED")
    _need(isinstance(state,dict) and bool(state),"EMPTY_MODEL_STATE")
    _need(isinstance(training_rows,list) and bool(training_rows),"NO_ELIGIBLE_UPDATE")
    if family.endswith("_LOCKED") or model_id==LOCKED_NHL_ID:
        raise ScoreError("LOCKED_MODEL_NOT_ADAPTIVE")
    obs=set()
    for row in training_rows:
        key=(row.get("sport"),row.get("event_id"),row.get("player_id"),row.get("stat_key"))
        _need(row.get("sport")==sport and key not in obs,"DUPLICATE_OR_WRONG_TRAINING_OBS")
        obs.add(key)
        _need(row.get("training_admitted") is True,"UNVERIFIED_TRAINING_OBSERVATION")
        _need(isinstance(row.get("official_source_sha256"),str) and
              re.fullmatch("[0-9a-f]{64}",row["official_source_sha256"]),
              "TRAINING_SOURCE_RECEIPT_MISSING")
        _need(_utc(row["official_result_available_at"])<=_utc(cutoff_at),
              "FUTURE_OFFICIAL_OUTCOME_IN_TRAINING")
        key_text="|".join(str(row[k]) for k in ("sport","event_id","player_id",
                                                   "stat_key","official_outcome_id"))
        archived=_read(base, f"observations/{digest(key_text)}.json")
        _need(archived==row,"TRAINING_OBSERVATION_NOT_ARCHIVED_UNCHANGED")
    with _lock(base):
        previous=_latest(base,model_id)
        # Deterministic retry of the exact same already committed update is a
        # readback, never an additional training event or transition.
        committed=read_transitions(base,model_id)
        training_sha=digest(sorted(training_rows,key=lambda z:
                              (z["event_id"],z["player_id"],z["stat_key"])))
        if previous is not None and committed and committed[-1]["action"]=="REGISTER":
            last=committed[-1]
            retry_fields={
                "model_id":model_id,"family":family,"pipeline_id":pipeline_id,
                "sport":sport,"parent_version":parent_version,
                "created_at":created_at,"training_cutoff_at":cutoff_at,
                "training_manifest_sha256":training_sha,
                "training_sample_count":len(training_rows),
                "code_commit":code_commit,"seed":seed,"update_mode":update_mode,
                "state":state,"diagnostics":diagnostics,"approval":approval,
            }
            if (previous.get("version")==last["version"] and
                all(previous.get(k)==v for k,v in retry_fields.items())):
                _read(base,last["artifact_path"],last["artifact_sha256"])
                return {"status":"IDEMPOTENT_EXISTING","model":previous,
                        "artifact_receipt":{
                            "status":"IDEMPOTENT_EXISTING",
                            "path":last["artifact_path"],
                            "sha256":last["artifact_sha256"]},
                        "transition_receipt":{
                            "status":"IDEMPOTENT_EXISTING",
                            "sequence":last["sequence"],
                            "sha256":digest(last)}}
        if previous is None:
            _need(parent_version is None,"REGISTRY_PARENT_NOT_FOUND")
            version=1
        else:
            _need(previous["version"]==parent_version,"REGISTRY_PARENT_VERSION_RACE")
            _need(_utc(previous["created_at"])<=_utc(created_at),"REGISTRY_TIME_REVERSAL")
            _need(_utc(previous["training_cutoff_at"])<_utc(cutoff_at),
                  "NONINCREASING_TRAINING_CUTOFF")
            _need(any(_utc(r["official_result_available_at"])>
                      _utc(previous["training_cutoff_at"]) for r in training_rows),
                  "NO_NEW_ELIGIBLE_OBSERVATIONS")
            _need(digest(previous["state"])!=digest(state),"MODEL_STATE_UNCHANGED")
            version=max(r["version"] for r in read_transitions(base,model_id) if r["action"]=="REGISTER")+1
        manifest=digest(sorted(training_rows,key=lambda z:(z["event_id"],z["player_id"],z["stat_key"])))
        body={
            "schema":VERSION, "model_id":model_id,"family":family,"pipeline_id":pipeline_id,
            "sport":sport,"version":version,"parent_version":parent_version,
            "parent_artifact_sha256":read_transitions(base,model_id)[-1]["artifact_sha256"] if previous else None,
            "created_at":created_at,"training_cutoff_at":cutoff_at,
            "max_official_availability_at":max(x["official_result_available_at"] for x in training_rows),
            "training_manifest_sha256":manifest,"training_sample_count":len(training_rows),
            "excluded_count":diagnostics.get("excluded_count",0),
            "code_commit":code_commit,"seed":seed,
            "update_mode":update_mode,"state":state,"diagnostics":diagnostics,
            "validation_passed":True,"approval":approval,
            "research_only":True,
        }
        artifact_sha=digest(body)
        body["payload_sha256"]=artifact_sha
        # Exact SHA covers the body without its own checksum field.
        relative=f"versions/{model_id}/v{version:06d}-{artifact_sha}.json"
        write=_write_once(base,relative,body)
        transition={
            "sequence":len(read_transitions(base,model_id))+1,"model_id":model_id,
            "action":"REGISTER","version":version,"artifact_path":relative,
            "artifact_sha256":hashlib.sha256(_canon(body)).hexdigest(),
            "created_at":created_at,"research_only":True,
        }
        t=_write_transition_once(base,f"transitions/{model_id}/{transition['sequence']:08d}.json",transition)
        return {"model":body,"artifact_receipt":write,
                "transition_receipt":t,"status":"NEW_RESEARCH_MODEL_ELIGIBLE"}

def rollback_model(root, model_id, *, rollback_to, at, reason):
    base=_secure_root(root);_safe_id(model_id);_utc(at)
    _need(bool(reason),"ROLLBACK_REASON_REQUIRED")
    with _lock(base):
        trans=read_transitions(base,model_id)
        _need(bool(trans),"NO_REGISTERED_MODEL")
        matches=[r for r in trans if r["version"]==rollback_to and r["action"]=="REGISTER"]
        _need(bool(matches),"ROLLBACK_TARGET_NOT_FOUND")
        target=matches[-1]
        _read(base,target["artifact_path"],target["artifact_sha256"])
        seq=trans[-1]["sequence"]+1
        row={"sequence":seq,"model_id":model_id,"action":"ROLLBACK",
             "version":rollback_to,"artifact_path":target["artifact_path"],
             "artifact_sha256":target["artifact_sha256"],"created_at":at,
             "reason":reason,"research_only":True}
        return _write_transition_once(base,f"transitions/{model_id}/{seq:08d}.json",row)

def select_for_forecast(root,model_id,*,freeze_at,code_commit=None):
    """One locked version+SHA selection; never return mutable active pointers."""
    base=_secure_root(root)
    with _lock(base,read_only=True):
        entries=read_transitions(base,model_id)
        eligible=[r for r in entries if _utc(r["created_at"])<=_utc(freeze_at)]
        _need(bool(eligible),"NO_PRIOR_MODEL_VERSION_AT_FREEZE")
        selected=eligible[-1]
        body=_read(base,selected["artifact_path"],selected["artifact_sha256"])
        _need(body["research_only"] and body["validation_passed"] and
              body["approval"]=="research_eligible" and
              _utc(body["training_cutoff_at"])<=_utc(freeze_at),
              "MODEL_NOT_ELIGIBLE_AT_FREEZE")
        if code_commit is not None:
            _need(body["code_commit"]==code_commit,"FORECAST_CODE_VERSION_MISMATCH")
        return {"model_id":model_id,"model_version":body["version"],
                "model_artifact_sha256":selected["artifact_sha256"],
                "artifact_path":selected["artifact_path"],
                "training_cutoff_at":body["training_cutoff_at"],
                "selection_transition_sequence":selected["sequence"],
                "state":body["state"],"seed":body["seed"],
                "research_only":True}

def admit_training_observation(root, row, *, effective_cutoff):
    """Append original official observed count once; no forecast requirement."""
    base=_secure_root(root)
    required={"sport","event_id","player_id","team_id","stat_key",
              "official_value","participation","official_source_sha256",
              "official_result_available_at","event_start_at","training_admitted",
              "official_outcome_id","exposure"}
    _need(set(row)==required,"TRAINING_OBSERVATION_SCHEMA_INVALID")
    _need(row["sport"] in ("NBA","NHL") and row["participation"]=="PLAYED",
          "NONPLAYED_TRAINING_EXCLUDED")
    _need(type(row["official_value"]) is int and row["official_value"]>=0,
          "INVALID_TRAINING_COUNT")
    _need(row["training_admitted"] is True,"UNVERIFIED_OFFICIAL_OBSERVATION")
    _need(isinstance(row["official_source_sha256"],str) and
          re.fullmatch("[0-9a-f]{64}",row["official_source_sha256"]),
          "TRAINING_SOURCE_SHA_INVALID")
    _need(_utc(row["event_start_at"])<_utc(row["official_result_available_at"])<=
          _utc(effective_cutoff),"TRAINING_CUTOFF_VIOLATION")
    _need(isinstance(row["exposure"],dict),"EXPOSURE_MUST_BE_VERIFIED_OR_EMPTY")
    _need(isinstance(row["official_outcome_id"],str) and bool(row["official_outcome_id"]),
          "OFFICIAL_REVISION_ID_MISSING")
    key="|".join(str(row[k]) for k in ("sport","event_id","player_id",
                                      "stat_key","official_outcome_id"))
    filename=digest(key)
    return _write_once(base,f"observations/{filename}.json",row)

def latest_training_observations(root, *, cutoff_at, sport=None):
    """Select one as-of-known final version per player-game-stat, not both corrections.

    Outcome corrections are append-only; the newest official source available
    by cutoff wins, and the older version remains recoverable for forensic replay.
    """
    base=_secure_root(root)
    _utc(cutoff_at)
    _need(sport in (None,"NBA","NHL"),"TRAINING_SPORT_INVALID")
    folder=_safe(base,"observations")
    latest={}
    if not folder.exists():
        return []
    for path in sorted(folder.glob("*.json")):
        if path.is_symlink():
            raise ScoreError("TRAINING_OBSERVATION_SYMLINK")
        row=_read(base,str(path.relative_to(base)))
        key_text="|".join(str(row[k]) for k in ("sport","event_id","player_id",
                                                  "stat_key","official_outcome_id"))
        _need(path.stem==digest(key_text),"TRAINING_OBSERVATION_FILENAME_MISMATCH")
        if sport is not None and row["sport"]!=sport:
            continue
        when=_utc(row["official_result_available_at"])
        if when>_utc(cutoff_at):
            continue
        key=tuple(row[k] for k in ("sport","event_id","player_id","stat_key"))
        prev=latest.get(key)
        if prev is None or when>_utc(prev["official_result_available_at"]):
            latest[key]=row
        elif when==_utc(prev["official_result_available_at"]) and row!=prev:
            raise ScoreError("DUPLICATE_OFFICIAL_REVISION_AVAILABILITY")
    return [latest[k] for k in sorted(latest)]
