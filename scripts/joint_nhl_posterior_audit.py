#!/usr/bin/env python3
"""Independent posterior joint-correlation and energy check on a saved NUTS fit.

Never retrain or tune on later game outcomes. An explicitly disallowed
posterior cannot be upgraded into production by this independent audit.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path


def evaluate_posterior(idata, manifest):
    import numpy as np
    import xarray as xr
    from arviz_stats import rhat, ess
    import joint_nhl_bayes as joint

    if (manifest.get("version")!=joint.VERSION or
        manifest.get("publication_eligible") is not False or
        manifest.get("diagnostics",{}).get("posterior_sampling_ok") is not True):
        raise ValueError("original_joint_fit_not_eligible_for_diagnostic_recheck")

    posterior=idata.posterior
    corr=np.asarray(posterior["player_chol_corr"],dtype=float)
    if corr.ndim!=4 or corr.shape[-2:]!=(2,2):
        raise ValueError("unexpected_joint_player_correlation_shape")
    rho=corr[:,:,0,1]
    if not np.all(np.isfinite(rho)) or np.any(np.abs(rho)>1):
        raise ValueError("invalid_player_correlation")
    ds=xr.Dataset({"workload_shot_rate_corr":(("chain","draw"),rho)})
    rhat_vals=joint._diagnostic_values(rhat(ds))
    ess_vals=joint._diagnostic_values(ess(ds,method="bulk"))
    if len(rhat_vals)!=1 or len(ess_vals)!=1:
        raise ValueError("ambiguous_joint_correlation_diagnostics")
    cr,ce=rhat_vals[0],ess_vals[0]
    energy=np.asarray(idata.sample_stats["energy"],dtype=float)
    if energy.shape!=rho.shape or not np.all(np.isfinite(energy)):
        raise ValueError("invalid_nuts_energy")
    variance=np.var(energy,axis=1,ddof=1)
    if np.any(variance<=0):
        raise ValueError("zero_energy_variance")
    bfmi=np.mean(np.diff(energy,axis=1)**2,axis=1)/variance
    if not np.all(np.isfinite(bfmi)):
        raise ValueError("invalid_energy_bfmi")
    extra_ok=(cr<=joint.MAX_RHAT and ce>=joint.MIN_ESS_BULK and
              np.min(bfmi)>=.30)
    return {"schema":"nhl_joint_posterior_geometry_v1",
        "model_version":joint.VERSION,
        "source_digest":manifest["source_digest"],
        "train_cutoff_exclusive":manifest["training_cutoff_exclusive"],
        "chains":int(rho.shape[0]),"draws_per_chain":int(rho.shape[1]),
        "correlation":"latent player log-workload versus log-shot-rate",
        "posterior_correlation_mean":float(np.mean(rho)),
        "posterior_correlation_quantiles_025_50_975":[
            float(v) for v in np.quantile(rho,[.025,.5,.975])],
        "correlation_rhat":float(cr),"correlation_bulk_ess":float(ce),
        "nuts_bfmi_by_chain":[float(x) for x in bfmi],
        "minimum_bfmi":float(np.min(bfmi)),
        "correlation_and_energy_check_pass":bool(extra_ok),
        "overall_sampling_check_pass":bool(extra_ok),
        "status":"supplemental_diagnostics_pass" if extra_ok else "supplemental_diagnostics_fail",
        "publication_eligible":False,"calibrated_for_production":False,
        "models_or_weights_modified":False}


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--model-dir",type=Path,required=True)
    p.add_argument("--out",type=Path)
    args=p.parse_args(argv)
    import arviz as az
    idata=az.from_netcdf(args.model_dir/"posterior.nc")
    manifest=json.loads((args.model_dir/"manifest.json").read_text())
    result=evaluate_posterior(idata,manifest)
    out=args.out or args.model_dir/"posterior_geometry_audit.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print(json.dumps(result,sort_keys=True))
    return 0 if result["overall_sampling_check_pass"] else 2


if __name__=="__main__":
    raise SystemExit(main())
