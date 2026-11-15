"""Read-only Workstream 2/3/4 original-contract handoff validator.

No source retrieval, model fitting, settlement, ranking or manifest mutation.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from pathlib import Path
import argparse
import json

from nfl_sunday_source_contract import VERSION, canonical, instant

WS_DIRS = {
    "simple_models": "simple_models",
    "opportunity_models": "opportunity_models",
    "joint_models": "joint_models",
}
ORIGINAL_KEYS = (
    "candidate_id", "event_id", "player_id", "quote_id", "stat",
    "period", "line", "book", "source_sha256", "event_start_at",
    "input_freeze_at",
)

def load_control(path):
    path = Path(path)
    raw = path.read_bytes()
    if not raw.endswith(b"\n"):
        raise ValueError("SOURCE_MANIFEST_NOT_CANONICAL")
    obj = json.loads(raw)
    if raw != canonical(obj) + b"\n":
        raise ValueError("SOURCE_MANIFEST_BYTES_NONCANONICAL")
    if obj.get("schema") != VERSION:
        raise ValueError("SOURCE_MANIFEST_SCHEMA_UNKNOWN")
    expected_digest = sha256(canonical(obj)).hexdigest()
    if path.stem != expected_digest:
        raise ValueError("SOURCE_MANIFEST_FILE_SHA_MISMATCH")
    observed_ids = [row.get("candidate_id") for row in obj.get("candidates",[])]
    if len(observed_ids) != len(set(observed_ids)):
        # Duplicate provider observations are not silently eliminated.
        # Conflicting duplicate quote identities can be quarantined, but
        # workstreams may not treat them as separate eligible forecasts.
        if any(row.get("source_certified") for row in obj["candidates"]):
            raise ValueError("DUPLICATE_CANDIDATE_ID_STILL_CERTIFIED")
    for row in obj["candidates"]:
        if row.get("source_certified") and (not row.get("event_id") or
                                           not row.get("player_id") or
                                           not row.get("source_sha256")):
            raise ValueError("CERTIFIED_SOURCE_IDENTITY_INCOMPLETE")
        if row.get("forecast_eligible") and not row.get("source_certified"):
            raise ValueError("UNCERTIFIED_CANDIDATE_FORECAST_ELIGIBLE")
    return obj, sha256(raw).hexdigest()

def validate_handoff(control, workstream, output):
    if workstream not in WS_DIRS:
        raise ValueError("UNKNOWN_WORKSTREAM")
    candidates = {r["candidate_id"]:r for r in control["candidates"]
                  if r.get("source_certified") and r.get("research_shadow_eligible")}
    accepted, rejected = [], []
    seen=set()
    for row in output:
        candidate_id = row.get("candidate_id")
        src=candidates.get(candidate_id)
        reason=None
        if src is None:
            reason="ORIGINAL_CANDIDATE_NOT_ELIGIBLE_OR_NOT_FOUND"
        else:
            for key in ORIGINAL_KEYS:
                if row.get(key) != src.get(key):
                    reason="CONTRACT_IDENTITY_MISMATCH:"+key
                    break
            if row.get("source_manifest_file_sha256") != control["_file_sha256"]:
                reason=reason or "ORIGINAL_SOURCE_MANIFEST_HASH_MISMATCH"
            if src.get("source_validation_failure"):
                reason=reason or "SOURCE_NOT_CERTIFIED"
            if row.get("model_training_cutoff_at") is None:
                reason=reason or "MODEL_TRAINING_CUTOFF_MISSING"
            elif reason is None:
                try:
                    if instant(row["model_training_cutoff_at"]) > instant(src["input_freeze_at"]):
                        reason="POST_FREEZE_MODEL_TRAINING"
                except ValueError:
                    reason="TRAINING_TIMESTAMP_INVALID"
            if row.get("forecast_at") is None:
                reason=reason or "FORECAST_TIME_MISSING"
            elif reason is None:
                try:
                    when=instant(row["forecast_at"])
                    if not instant(src["input_freeze_at"]) <= when < instant(src["event_start_at"]):
                        reason="FORECAST_OUTSIDE_PREGAME_WINDOW"
                except ValueError:
                    reason="FORECAST_TIME_INVALID"
            if row.get("model_id") is None or row.get("model_version") is None:
                reason=reason or "MODEL_ID_OR_VERSION_MISSING"
            if row.get("research_only") is not True:
                reason=reason or "SHADOW_ONLY_REQUIRED"
            p=row.get("probabilities")
            if not isinstance(p,dict):
                reason=reason or "PROBABILITIES_UNAVAILABLE"
            elif reason is None:
                try:
                    ps=[p[k] for k in ("over","under","push")]
                    if any(type(v) not in (int,float) or not 0<=v<=1 for v in ps):
                        reason="PROBABILITIES_INVALID"
                    elif abs(sum(ps)-1)>1e-8:
                        reason="PROBABILITY_MASS_MISMATCH"
                except (KeyError,TypeError,ValueError):
                    reason="PROBABILITY_MASS_MISSING"
        idkey=(candidate_id,row.get("model_id"),row.get("model_version"))
        if idkey in seen:
            reason="DUPLICATE_MODEL_FORECAST"
        seen.add(idkey)
        (rejected if reason else accepted).append(
            {"candidate_id":candidate_id,"model_id":row.get("model_id"),
             "status":"rejected" if reason else "accepted",
             "reason":reason})
    return {"schema":"nfl_sunday_ws1_handoff_audit_v1",
            "workstream":workstream,"source_rows":len(control["candidates"]),
            "source_eligible":len(candidates),"outputs":len(output),
            "accepted":len(accepted),"rejected":len(rejected),
            "reasons":dict(sorted(Counter(x["reason"] for x in rejected).items())),
            "rows":accepted+rejected}

def load_output_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-manifest",type=Path,required=True)
    p.add_argument("--workstream",choices=sorted(WS_DIRS),required=True)
    p.add_argument("--output-jsonl",type=Path,required=True)
    p.add_argument("--audit-out",type=Path,required=True)
    a=p.parse_args(argv)
    control,file_sha=load_control(a.source_manifest)
    control["_file_sha256"]=file_sha
    result=validate_handoff(control,a.workstream,load_output_jsonl(a.output_jsonl))
    result["source_manifest_file_sha256"]=file_sha
    from nfl_sunday_source_contract import write_immutable
    print(json.dumps({"receipt_sha256":write_immutable(a.audit_out,result),
                      "accepted":result["accepted"],"rejected":result["rejected"],
                      "reasons":result["reasons"]},sort_keys=True))
    if result["rejected"]:
        raise SystemExit(2)

if __name__=="__main__":
    main()
