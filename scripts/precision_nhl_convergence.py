#!/usr/bin/env python3
"""Read-only NHL full-history fit receipt; never touches running Python processes.

Default mode inspects the completed manifest and receipt without loading large
posteriors. Optional --independent re-computes all-effect R-hat, bulk ESS,
divergences and BFMI from posterior.nc using the pinned model environment.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARKETS={"saves":"saves","hits":"hits",
         "shots-on-goal":"shots on goal","blocked-shots":"blocked shots"}
THRESHOLDS={"max_rhat":1.01,"min_bulk_ess":400,"divergences":0,"minimum_bfmi":0.30}


def inspect(path:Path,market:str,*,independent=False)->dict:
    report={"schema":"nhl_fit_convergence_audit_v1",
            "market":market,"training_dir":str(path),"status":"unavailable",
            "strict_convergence":False,"production_eligible":False}
    manifest_path=path/"manifest.json"
    receipt_path=path/"model_receipt.json"
    posterior_path=path/"posterior.nc"
    report["manifest_present"]=manifest_path.is_file()
    report["posterior_present"]=posterior_path.is_file()
    report["receipt_present"]=receipt_path.is_file()
    if not manifest_path.is_file():
        report["reason"]="FIT_NOT_COMPLETED_OR_MANIFEST_NOT_SAVED"
        return report
    try:
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        receipt=json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else None
    except (OSError,ValueError) as exc:
        report.update(status="invalid",reason=f"UNREADABLE_FIT_RECEIPT:{type(exc).__name__}")
        return report
    diag=manifest.get("diagnostics") or {}
    report.update(
        source_digest=manifest.get("source_digest"),
        cutoff=manifest.get("training_cutoff_exclusive"),
        rows=manifest.get("rows"),players=len(manifest.get("players",[])),
        chains=manifest.get("sampler_chains"),
        posterior_draws_per_chain=manifest.get("sampler_retained_draws_per_chain"),
        all_player_and_opponent_effects=manifest.get("diagnosed_all_player_and_opponent_effects"),
        diagnostics=diag,
        worker_status=receipt.get("status") if receipt else "receipt_pending",
    )
    structural=(manifest.get("schema")=="multisport_joint_fit_manifest_v1"
       and manifest.get("sport")=="NHL" and manifest.get("stat")==market
       and manifest.get("diagnosed_all_player_and_opponent_effects") is True
       and manifest.get("max_per_position")==0
       and manifest.get("sampler_chains")==4
       and manifest.get("sampler_retained_draws_per_chain")==2000
       and posterior_path.is_file()
       and receipt is not None and receipt.get("stat")==market
       and receipt.get("status")=="converged")
    numerical=(diag.get("posterior_sampling_ok") is True
       and isinstance(diag.get("max_rhat"),(int,float)) and math.isfinite(diag["max_rhat"]) and diag["max_rhat"]<=1.01
       and isinstance(diag.get("min_bulk_ess"),(int,float)) and math.isfinite(diag["min_bulk_ess"]) and diag["min_bulk_ess"]>=400
       and diag.get("divergences")==0
       and isinstance(diag.get("minimum_bfmi"),(int,float)) and math.isfinite(diag["minimum_bfmi"]) and diag["minimum_bfmi"]>=.30)
    if independent and posterior_path.is_file():
        # Heavy check should only be used when enough RAM is free; it does NOT
        # trigger new draws and it does not change the original artifact.
        import arviz as az
        sys.path.insert(0,str(ROOT/"scripts"))
        from joint_population_bayes import diagnostics
        independent_checks=diagnostics(az.from_netcdf(str(posterior_path)),all_effects=True)
        report["independent_diagnostics"]=independent_checks
        independent_numerical=(independent_checks.get("posterior_sampling_ok") is True)
        report["diagnostic_reproduction_pass"]=(independent_numerical and all(
            (abs(independent_checks[k]-diag[k]) < .001 if k in ("max_rhat","min_bulk_ess","minimum_bfmi")
             else independent_checks[k]==diag[k])
            for k in ("max_rhat","min_bulk_ess","divergences","minimum_bfmi")
            if k in independent_checks and k in diag))
        numerical=numerical and report["diagnostic_reproduction_pass"]
    report["strict_convergence"]=bool(structural and numerical)
    report["status"]="converged" if report["strict_convergence"] else "not_approved"
    if not structural:
        report["reason"]="MISSING_OR_INCOMPLETE_POSTERIOR_OR_PROVENANCE"
    elif not numerical:
        report["reason"]="STRICT_NUMERICAL_CONVERGENCE_FAILED_OR_UNVERIFIED"
    # Even converged full-history research-only models need predictive
    # validation before any deployment.
    report["production_eligible"]=False
    return report


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--run-id",default="40993538888")
    p.add_argument("--market",choices=tuple(MARKETS),default="saves")
    p.add_argument("--independent",action="store_true",
                   help="recompute full posterior diagnostics, requires ArviZ model environment")
    a=p.parse_args(argv)
    if not re.fullmatch(r"[0-9]{5,20}",a.run_id):
        p.error("unsafe_run_id")
    folder=a.root.resolve()/"reports"/"precision_training"/a.run_id/a.market
    result=inspect(folder,MARKETS[a.market],independent=a.independent)
    print("NHL_CONVERGENCE_REPORT "+json.dumps(result,sort_keys=True,allow_nan=False),flush=True)
    return 0 if result["strict_convergence"] else 2


if __name__=="__main__":
    raise SystemExit(main())
