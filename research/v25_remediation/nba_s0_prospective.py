"""Source-bound NBA S0 *conditional-on-played* research canary.

This module is only the integration adapter:
 P1's existing NBA WS1 original-source owner -> P0 immutable canonical records
 -> P3's unchanged S0 full-count Poisson engine -> P5 later official evaluation.

No new collector, no synthetic source substitution, no market odds, no
participation assumption, no outcome access, no model fitting/learning, no
production tiers, and no retroactive forecasts. All blocked rows are retained.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256 as hashlib_sha256
from pathlib import Path
import json
import os
import re

from v2.p0_integrity.contracts import (
    AdmissionError, canonical_bytes, record, sha256, utc,
    validate_record, verify_source_bytes,
)
from v2.p0_integrity.storage import (
    append_immutable, attest_project_storage, verify_immutable_record,
)
from research.nba_p1_original.feature_store import (
    load_handoff, verify_dev_p0_record, VERSION as P1_VERSION,
)
from research.nba_p1_original.rolling import run_daily
from research.nba_p3_frozen.engine import (
    MODEL_SCHEMA, create_research_model, generate,
)
from research.nba_p3_frozen.distributions import STATS

ROOT = Path("/work")
RESEARCH = Path("research/v25_remediation/nba_s0_research")
MODEL_ID = "PA-V25-NBA-S0-CONDITIONAL-PLAYED"
MODEL_VERSION = "1-method-only"
MODEL_STATS = tuple(STATS)
CODE_SHA = re.compile(r"^[0-9a-f]{40}$")
ORIGINAL_SRC_KINDS = {"original_capture"}
ALLOWED_ABSTENTIONS = {
    "PARTICIPATION_UNRESOLVED", "CONDITIONAL_ON_PLAYING_ONLY",
    "ELIGIBILITY_UNVERIFIED",
}


class IntegrationBlocked(ValueError):
    pass


def require(ok, why):
    if not ok:
        raise IntegrationBlocked(why)


def utc_now():
    return datetime.now(timezone.utc)


def stamp(now=None):
    now = utc_now() if now is None else now
    require(now.tzinfo is not None and now.utcoffset() is not None, "NAIVE_TIME")
    return now.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def digest(raw):
    return hashlib_sha256(raw).hexdigest()


def _once(path, raw):
    """Refuse overwrite, symlink, partial replays and changed original bytes."""
    path = Path(path)
    require(ROOT == Path("/work"), "P0_LOGICAL_ROOT_MISMATCH")
    require(path.is_relative_to(ROOT), "PATH_OUTSIDE_ATTESTED_ROOT")
    require(not path.is_symlink() and not any(
        p.is_symlink() for p in list(path.parents) if p != ROOT and p != Path("/")
    ), "SYMLINK_REJECTED")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        status = "APPENDED"
    except FileExistsError:
        status = "IDEMPOTENT_EXISTING"
    reread = path.read_bytes()
    require(reread == raw, "IMMUTABLE_COLLISION_OR_PARTIAL_WRITE")
    return {"status": status, "sha256": digest(raw),
            "path": str(path.relative_to(ROOT))}


def _method_spec(code_commit, declared_at):
    require(CODE_SHA.fullmatch(code_commit) is not None, "UNPINNED_CODE_COMMIT")
    _ = utc(declared_at)
    return {
        "schema": "PA-V25-NBA-S0-METHOD-PREDICTION-ONLY/1",
        "cohort": "NBA_ORIGINAL_SOURCE_LISTED_CONDITIONAL_ON_PLAYED",
        "method": "S0_POISSON_PLAYER_COUNT_PER_PRIOR_PLAYED_MINUTE",
        "stat_keys": list(MODEL_STATS),
        "historical_rate": "prior_played_counts_sum / prior_played_minutes_sum",
        "future_exposure": "median_minutes_last_five_prior_played_games",
        "minimum_prior_played_games": 2,
        "inference": "count_distribution_conditional_on_player_playing",
        "participation_probability": "UNKNOWN_NOT_ESTIMATED",
        "training": "PREDICTION_ONLY_NO_PRIOR_FIT",
        "market_quote_required": False,
        "model_code_sha": code_commit,
        "declared_at": declared_at,
        "approval": "RESEARCH_ONLY_NO_PRODUCTION_OR_NATIVE_G1_PROMOTION",
    }


def _method_path(code_commit):
    require(CODE_SHA.fullmatch(code_commit) is not None, "UNPINNED_CODE_COMMIT")
    return ROOT / RESEARCH / "method_protocols" / (
        MODEL_ID + "_" + code_commit + ".json"
    )


def _payload(spec):
    return {
        "schema": MODEL_SCHEMA,
        "family": "S0",
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION + "-" + spec["model_code_sha"][:12],
        "training_cutoff_at": spec["declared_at"],
        "training_reference_sha256": sha256(spec),
        "min_history_games": spec["minimum_prior_played_games"],
        "priors_per_minute": {},
        "dispersion_shapes": {},
        "opportunity": {},
        "joint_variant": None,
        "joint_state": None,
        "joint_parameters": None,
        "update_policy": "PREDICTION_ONLY",
    }


def _expected_model(spec):
    payload = _payload(spec)
    body = canonical_bytes(payload)
    model_sha = digest(body)
    model = record("ModelArtifact",
        model_artifact_id="nba-v25-s0-method:" + model_sha,
        model_id=payload["model_id"], model_version=payload["model_version"],
        model_code_sha=spec["model_code_sha"], artifact_sha256=model_sha,
        artifact_path="models/nba_p3/" + model_sha + ".json",
        training_data_sha256=payload["training_reference_sha256"],
        training_cutoff_at=spec["declared_at"],
        created_at=spec["declared_at"],
        training_scope="PREDICTION_ONLY_NO_FITTING_METHOD_REFERENCE",
        feature_schema_id=P1_VERSION)
    return payload, model


def prepare_method(*, code_commit, now=None):
    """Register exactly one PREDECLARED S0 *method*, not a fitted model.

    Must run before its first eligible pregame feature input freeze.
    Never publish a later method as if it existed before an older capture.
    """
    attest_project_storage("/work")
    at = stamp(now)
    protocol_path = _method_path(code_commit)
    if protocol_path.is_file():
        spec = json.loads(protocol_path.read_bytes())
        require(spec == _method_spec(code_commit, spec["declared_at"]),
                "METHOD_PROTOCOL_DRIFT")
    else:
        spec = _method_spec(code_commit, at)
        _once(protocol_path, canonical_bytes(spec))
    model_payload, expected = _expected_model(spec)
    published = create_research_model(model_payload, source_root="/work",
        model_code_sha=code_commit, created_at=spec["declared_at"],
        persist=True, storage_root="/work")
    require(published["record"] == expected, "METHOD_MODEL_RECORD_CHANGED")
    proof = verify_immutable_record("/work", "ModelArtifact", sha256(expected))
    require(proof == expected, "MODEL_READBACK_MISMATCH")
    return {
        "status": "PREDECLARED_S0_METHOD_REGISTERED_NOT_TRAINING",
        "model_record_sha256": sha256(expected),
        "model_artifact_sha256": expected["artifact_sha256"],
        "method_protocol_sha256": sha256(spec),
        "protocol_path": str(protocol_path.relative_to(ROOT)),
        "created_at": spec["declared_at"], "code_commit": code_commit,
        "research_only": True,
        "actual_training_update": False,
    }


def load_predeclared_model(*, code_commit, feature_freeze_at=None):
    """Read-only: verify P0 method identity and original model artifact bytes."""
    attest_project_storage("/work")
    path = _method_path(code_commit)
    require(path.is_file() and not path.is_symlink(), "METHOD_NOT_PREDECLARED")
    raw = path.read_bytes()
    spec = json.loads(raw)
    require(spec == _method_spec(code_commit, spec["declared_at"]),
            "METHOD_PROTOCOL_INVALID")
    expected_bytes = canonical_bytes(spec)
    require(raw == expected_bytes, "METHOD_PROTOCOL_BYTES_CHANGED")
    payload, model = _expected_model(spec)
    require(verify_immutable_record("/work","ModelArtifact",sha256(model))==model,
            "MODEL_NOT_REGISTERED_IN_P0")
    artifact = ROOT/model["artifact_path"]
    require(artifact.is_file() and not artifact.is_symlink() and
            digest(artifact.read_bytes())==model["artifact_sha256"],
            "MODEL_ARTIFACT_BYTES_CHANGED")
    require(artifact.read_bytes()==canonical_bytes(payload), "MODEL_PAYLOAD_MISMATCH")
    if feature_freeze_at is not None:
        require(utc(model["created_at"])<=utc(feature_freeze_at),
                "MODEL_METHOD_DECLARED_AFTER_PREGAME_SOURCE")
    return model


def _verify_raw_handoff(bundle):
    """P1 can hold real source bytes; this never reclassifies a fixture."""
    summary = bundle["summary"]
    require(summary.get("reconstruction_class") == "original" and
            summary.get("research_profile") == "source_listed_subset",
            "P1_ORIGINAL_SOURCE_LISTED_PROFILE_REQUIRED")
    require(utc(summary["input_freeze_at"]) < utc(summary["event_start_at"]),
            "PREGAME_SOURCE_REQUIRED")
    sources = {}
    for x in summary["sources"]:
        src = verify_dev_p0_record("/work","SourceReceipt",x["p0_sha256"])
        require(src["source_kind"] in ORIGINAL_SRC_KINDS and
                src["provenance_class"]=="collector_possession",
                "NONORIGINAL_SOURCE_CLASSIFICATION")
        require(src["source_id"].startswith("https://") and
                ("espn.com/" in src["source_id"] or
                 "nba.com/" in src["source_id"]),
                "UNVERIFIED_UPSTREAM_PROVIDER")
        verify_source_bytes(src,"/work")
        require(utc(src["collected_at"])<=utc(summary["input_freeze_at"]),
                "SOURCE_AFTER_INPUT_FREEZE")
        sources[src["receipt_id"]]=src
    require(len(sources)>0,"NO_ORIGINAL_SOURCE_RECEIPTS")
    for feature in bundle["features"]:
        require(feature["reconstruction_class"]=="original" and
                feature["features"].get("candidate_kind")=="SOURCE_LISTED_SUBSET" and
                feature["features"].get("interface_version")==P1_VERSION and
                feature["features"].get("reconstruction_note")==
                    "AUTHENTIC_SAME_DAY_POSSESSION" and
                feature["features"].get("participation_probability") is None and
                feature["features"].get("legal_eligibility")=="UNVERIFIED",
                "P1_PARTICIPATION_OR_SOURCE_PROFILE_CHANGED")
        require(set(feature["source_receipt_ids"]).issubset(sources),
                "PLAYER_SOURCE_RECEIPTS_MISSING")
    return sources


def _claim_primary(forecast, *, model_sha, handoff_path):
    """Only one primary original S0 forecast per event/player/stat/method.

    A crashed pending claim cannot be retroactively replaced; it is audited.
    """
    natural = {
        "event_id": forecast["event_id"],
        "player_id": forecast["player_id"],
        "stat_key": forecast["stat_key"],
        "model_artifact_sha256": model_sha,
        "cohort": "S0_CONDITIONAL_ON_PLAYED",
    }
    path = ROOT / RESEARCH / "primary_claims" / (sha256(natural)+".json")
    claim = {
        "schema":"PA-V25-NBA-S0-PRIMARY-CLAIM/1",
        "identity":natural,
        "forecast_id":forecast["forecast_id"],
        "forecast_sha256":sha256(forecast),
        "handoff_path":handoff_path,
        "research_only":True,
    }
    data = canonical_bytes(claim)
    try:
        info = _once(path,data)
    except IntegrationBlocked as exc:
        if "IMMUTABLE_COLLISION" in str(exc):
            return {"status":"PRIMARY_FORECAST_ALREADY_CLAIMED",
                    "claim_path":str(path.relative_to(ROOT))}
        raise
    return {"status":info["status"],"claim_path":info["path"],
            "claim_sha256":info["sha256"]}


def freeze_handoff(*, handoff_relpath, code_commit, run_id,
                   max_forecasts=80, seed=22026, clock=utc_now):
    """Only verified and not-yet-started original data reach P3.

    No late forecast is created, and a conditional law cannot become an
    unconditional betting recommendation. Freeze immediately after P1 call,
    not after waiting for a later game's source window.
    """
    attest_project_storage("/work")
    require(CODE_SHA.fullmatch(code_commit) is not None, "UNPINNED_CODE_COMMIT")
    require(isinstance(handoff_relpath,str) and
            handoff_relpath.startswith("research/nba_p1_original/dev_v1/handoffs/"),
            "UNAPPROVED_P1_HANDOFF_PATH")
    require(0<max_forecasts<=500, "EXCESSIVE_FORECAST_CAP")
    bundle=load_handoff("/work",handoff_relpath)
    source_map=_verify_raw_handoff(bundle)
    model=load_predeclared_model(code_commit=code_commit,
                                feature_freeze_at=bundle["summary"]["input_freeze_at"])
    start=bundle["summary"]["event_start_at"]
    require(utc(stamp(clock()))<utc(start), "EVENT_STARTED_NO_RETROACTIVE_FREEZE")
    # Verify every original row against the P1 immutable ID index before P0
    # adopts it; this preserves a single P0 authority and source ownership.
    for src in source_map.values():
        append_immutable("/work","SourceReceipt",src)
    for item in bundle["summary"]["features"]:
        obj=verify_dev_p0_record("/work","PregameFeatureSnapshot",item["sha256"])
        require(obj in bundle["features"],"DEV_FEATURE_OBJECT_CHANGED")
        append_immutable("/work","PregameFeatureSnapshot",obj)
    results=[]
    for feature in bundle["features"][:max_forecasts]:
        if utc(stamp(clock()))>=utc(start):
            results.append({"stat_key":feature["stat_key"],
                "player_id":feature["player_id"],"status":"MISSED_FREEZE"})
            continue
        ids=feature["source_receipt_ids"]
        sources=[source_map[x] for x in ids]
        forecast_at=stamp(clock())
        args=dict(source_root="/work",event_start_at=start,
            forecast_at=forecast_at,code_commit=code_commit,run_id=run_id,
            season=utc(start).year,seed=seed,
            pipeline="S_ONLY",n_scenarios=5000,quote=None)
        dry=generate(feature,model,sources,persist=False,**args)
        if dry.status!="RESEARCH_DRY_RUN" or dry.forecast is None:
            results.append({"stat_key":feature["stat_key"],
                "player_id":feature["player_id"],
                "status":dry.status,"reason":dry.reason})
            continue
        require(dry.forecast["eligible"] is False and
                set(dry.forecast["abstention_reasons"])==ALLOWED_ABSTENTIONS,
                "S0_CONDITIONAL_FORECAST_ELIGIBILITY_DRIFT")
        claim=_claim_primary(dry.forecast,
              model_sha=model["artifact_sha256"],handoff_path=handoff_relpath)
        if claim["status"]=="PRIMARY_FORECAST_ALREADY_CLAIMED":
            results.append({"stat_key":feature["stat_key"],
               "player_id":feature["player_id"],"status":"ALREADY_FROZEN_PRIMARY"})
            continue
        # The claim prevents double-freezing; on a failed store, leave it
        # unresolved and never reconstruct this prediction after the event.
        frozen=generate(feature,model,sources,persist=True,storage_root="/work",**args)
        if frozen.status!="FORECAST_FROZEN":
            results.append({"stat_key":feature["stat_key"],
               "player_id":feature["player_id"],"status":"FREEZE_BLOCKED",
               "reason":frozen.reason,"claim":claim})
            continue
        reread=verify_immutable_record("/work","ForecastSnapshot",
                                      sha256(frozen.forecast))
        require(reread==dry.forecast,
                "ORIGINAL_FORECAST_BYTES_DIVERGED_FROM_VERIFIED_DRY_RUN")
        results.append({"status":"ORIGINAL_CONDITIONAL_S0_FROZEN",
            "player_id":feature["player_id"],"stat_key":feature["stat_key"],
            "event_id":feature["event_id"],"forecast_id":frozen.forecast["forecast_id"],
            "forecast_sha256":sha256(frozen.forecast),
            "frozen_at":forecast_at,"model_version":model["model_version"],
            "conditional_on_played_only":True,
            "unconditional_participation_calibrated":False,
            "betting_eligible":False})
    result={
        "schema":"PA-V25-NBA-S0-PREGAME-CANARY/1",
        "created_at":stamp(clock()),"event_id":bundle["summary"]["event_id"],
        "event_start_at":start,"handoff_path":handoff_relpath,
        "frozen_predictions":sum(x["status"]=="ORIGINAL_CONDITIONAL_S0_FROZEN"
                                 for x in results),
        "attempt_count":len(results),"attempts":results,
        "model_artifact_sha256":model["artifact_sha256"],
        "research_only":True,"unconditional_calibration":False}
    raw=canonical_bytes(result)
    receipt=_once(ROOT/RESEARCH/"forecast_runs"/(digest(raw)+".json"),raw)
    return dict(result,receipt=receipt)


def run_once(*, day, code_commit, max_forecasts=80):
    """Existing P1 capture once; immediately consume each newly frozen handoff."""
    attest_project_storage("/work")
    # Never initialize a new method from a previously frozen input.
    model=load_predeclared_model(code_commit=code_commit)
    p1=run_daily(day=day,wait=False)
    accepted=[]
    for x in p1["attempts"]:
        if x["status"]!="SOURCE_FEATURE_FROZEN":
            continue
        path=x.get("handoff_path")
        try:
            admitted=freeze_handoff(handoff_relpath=path,
                code_commit=code_commit,
                run_id="nba-s0-"+digest((str(x["event_id"])+str(x["phase"])+
                    str(x["receipt_sha256"])+model["artifact_sha256"]).encode())[:32],
                max_forecasts=max_forecasts)
            accepted.append({"event_id":x["event_id"],"phase":x["phase"],
                             "handoff_path":path,"result":admitted})
        except Exception as exc:
            accepted.append({"event_id":x["event_id"],"phase":x["phase"],
                             "handoff_path":path,
                             "status":"FAIL_CLOSED_INTEGRATION_BLOCKED",
                             "reason":type(exc).__name__+":"+str(exc)[:240]})
    return {
       "schema":"PA-V25-NBA-S0-SOURCE-TO-P0-DAILY/1",
       "day":day,"generated_at":stamp(),
       "source_attempts":p1["counts"],
       "games_discovered":p1["games_discovered"],
       "frozen_handoff_count":len(accepted),
       "forecast_reports":accepted,
       "source_manifest_sha256":p1["daily_manifest_sha256"],
       "predeclared_model_artifact_sha256":model["artifact_sha256"],
       "research_only":True,"production_automation_changes":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode",choices=("prepare","run-once","inspect"))
    p.add_argument("--code-commit",required=True)
    p.add_argument("--day")
    p.add_argument("--max-forecasts",type=int,default=80)
    a=p.parse_args(argv)
    if a.mode=="prepare":
        result=prepare_method(code_commit=a.code_commit)
    elif a.mode=="inspect":
        r=load_predeclared_model(code_commit=a.code_commit)
        result={"status":"PREDECLARED_MODEL_READONLY_OK",
                "model_artifact_sha256":r["artifact_sha256"],
                "model_version":r["model_version"],"research_only":True}
    else:
        require(a.day is not None,"DAY_REQUIRED")
        result=run_once(day=a.day,code_commit=a.code_commit,
                        max_forecasts=a.max_forecasts)
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
