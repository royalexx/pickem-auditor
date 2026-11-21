"""Manual P4 NHL SOG research model runner; never a production scheduler.

Examples:
 python -m scripts.p4_nhl_sog_generate --mode synthetic --input /tmp/p4/fixture.json --source-root /tmp/p4 --artifact-root /tmp/p4/output --code-commit <40-hex>
 python -m scripts.p4_nhl_sog_generate --mode original --input signed_p2_bundle.json --source-root P2_ROOT --artifact-root P4_ROOT --code-commit <40-hex>
 python -m scripts.p4_nhl_sog_generate --mode native --source-root PROJECT_ROOT --code-commit <40-hex>
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

from v2.nhl_sog_p4_forecasts import (
    BUNDLE_SCHEMA, P4Blocked, fit_source_bundle, freeze_forecast,
    run_verified_original_gamma_bundle, run_registered_native_nb2_if_original_manifest_exists,
    coverage_attempt, canonical, MODELS, read_immutable
)


def run(args):
    now=datetime.now(timezone.utc)
    clock=now.isoformat().replace("+00:00","Z")
    if args.mode=="native":
        return run_registered_native_nb2_if_original_manifest_exists(
            args.source_root,code_commit=args.code_commit)
    if not args.input:
        raise P4Blocked("P2_INPUT_PATH_REQUIRED")
    blob=Path(args.input).read_bytes()
    bundle=json.loads(blob)
    if args.mode=="original":
        # No synthetic fixture can use the original quote route.
        if bundle.get("schema")!="v25_sog_prospective_input_v1":
            raise P4Blocked("P2_ORIGINAL_BUNDLE_SCHEMA_REQUIRED")
        return run_verified_original_gamma_bundle(bundle,
            source_root=args.source_root,artifact_root=args.artifact_root)
    if bundle.get("schema")!=BUNDLE_SCHEMA or (
            bundle.get("source_classification")!="synthetic" and
            bundle.get("source_classification")!="original_signed"):
        raise P4Blocked("INVALID_DISTRIBUTION_ONLY_SOURCE_BUNDLE")
    ident=hashlib.sha256(blob).hexdigest()[:16]
    try:
        model=fit_source_bundle(bundle,source_root=args.source_root)
        cohort="synthetic" if bundle["source_classification"]=="synthetic" else "distribution_only"
        out=[]
        for kind in MODELS.values():
            fid="p4_"+ident+"_"+kind
            receipt=freeze_forecast(model,kind=kind,
                event_id=bundle["event_id"],player_id=bundle["player_id"],
                team_id=bundle["team_id"],opponent_id=bundle["opponent_id"],
                event_start_at=bundle["event_start_at"],forecast_at=clock,
                training_cutoff_at=bundle["historical_availability_cutoff_at"],
                code_commit=args.code_commit,
                source_manifest_sha256=bundle.get("source_manifest_sha256"),
                artifact_root=args.artifact_root,forecast_id=fid,
                cohort=cohort,experiment_id=None if cohort=="synthetic" else model["experiment_id"])
            out.append({"kind":kind,**receipt})
        return {"schema":"v25_nhl_sog_p4_manual_run_v1",
                "status":"SHADOW_DISTRIBUTIONS_FROZEN","source_classification":cohort,
                "source_input_sha256":hashlib.sha256(blob).hexdigest(),
                "forecast_count":len(out),"forecasts":out,
                "native_nb2_not_admitted":True,"production_unchanged":True}
    except Exception as exc:
        reason=type(exc).__name__+":"+str(exc)[:200]
        receipt=coverage_attempt(args.artifact_root,
            attempt_id="p4_"+ident+"_abstain_"+hashlib.sha256(clock.encode()).hexdigest()[:12],
            event_id=bundle.get("event_id"),player_id=bundle.get("player_id"),
            reason=reason,source_classification=bundle.get("source_classification"),
            forecast_at=clock)
        return {"status":"ABSTAIN","reason":reason,
                "attempt_receipt":receipt,"production_unchanged":True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=("synthetic","distribution","original","native"),
                   required=True)
    p.add_argument("--input")
    p.add_argument("--source-root",required=True)
    p.add_argument("--artifact-root")
    p.add_argument("--code-commit",required=True)
    args=p.parse_args()
    if args.mode in ("synthetic","distribution","original") and not args.artifact_root:
        p.error("--artifact-root is required")
    print(json.dumps(run(args),sort_keys=True,indent=2,allow_nan=False))


if __name__=="__main__":
    main()
