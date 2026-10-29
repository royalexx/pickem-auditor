#!/usr/bin/env python3
"""Authorize a more thorough research-only NUTS fit after safe diagnostic failures.

Only numerical convergence checks may authorize extra draws. Missing manifests,
non-finite diagnostics, divergences, source identity mismatches, or model errors
remain blocking. Never relax R-hat, ESS, divergence or BFMI acceptance thresholds.
"""
import argparse
import json
import math
from pathlib import Path


def retry_eligible(path, *, sport, stat, cutoff):
    path=Path(path)
    if not path.is_file():
        return False
    try:
        manifest=json.loads(path.read_text())
        checks=manifest.get("diagnostics") or {}
        if not isinstance(checks,dict):
            return False
        if manifest.get("schema")!="multisport_joint_fit_manifest_v1":
            return False
        if (manifest.get("sport"),manifest.get("stat"),manifest.get("training_cutoff_exclusive"))!=(sport,stat,cutoff):
            return False
        if manifest.get("model_version")!="multisport-joint-bayes-v1":
            return False
        if checks.get("status")!="sampling_diagnostics_failed" or checks.get("posterior_sampling_ok") is not False:
            return False
        if type(checks.get("divergences")) is not int or checks["divergences"]!=0:
            return False
        rhat,ess,bfmi=(float(checks[key]) for key in ("max_rhat","min_bulk_ess","minimum_bfmi"))
        if not all(math.isfinite(v) for v in (rhat,ess,bfmi)) or bfmi<.30:
            return False
        return rhat>1.01 or ess<400
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError):
        return False


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--manifest",required=True,type=Path)
    parser.add_argument("--sport",required=True)
    parser.add_argument("--stat",required=True)
    parser.add_argument("--as-of",required=True)
    parser.add_argument("--github-output",type=Path)
    args=parser.parse_args(argv)
    eligible=retry_eligible(args.manifest,sport=args.sport,stat=args.stat,cutoff=args.as_of)
    print("CONVERGENCE_RETRY_ELIGIBLE="+str(eligible))
    if args.github_output:
        with args.github_output.open("a",encoding="utf-8") as output:
            output.write("eligible="+str(eligible).lower()+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
