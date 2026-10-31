#!/usr/bin/env python3
"""Read-only audit of a finished NFL fit. Never samples or changes its status."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import zipfile

import nhl_context_train as io
from nhl_context_model import diagnostics,_diagnostic_values


def finite_json(value):
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:finite_json(v) for k,v in value.items()}
    if isinstance(value,list):return [finite_json(v) for v in value]
    return value


def design_report(design):
    import numpy as np
    x=np.asarray(design["x"],dtype=float)
    names=design["feature_names"]
    if x.ndim!=2 or x.shape[1]!=len(names) or not np.isfinite(x).all():
        raise ValueError("invalid_frozen_design_matrix")
    constant=[i for i in range(x.shape[1]) if np.ptp(x[:,i])<=1e-12]
    duplicate=[]
    for i in range(x.shape[1]):
        if i in constant:continue
        for j in range(i):
            if j not in constant and np.array_equal(x[:,i],x[:,j]):
                duplicate.append({"feature":names[i],"same_as":names[j]});break
    singular=np.linalg.svd(x,compute_uv=False)
    tolerance=singular[0]*max(x.shape)*np.finfo(float).eps if singular.size else 0.
    rank=int((singular>tolerance).sum())
    return {"rows":len(x),"columns":len(names),"rank":rank,
            "constant_features":[names[i] for i in constant],"duplicate_features":duplicate,
            "singular_values":singular.tolist()}


def coordinate(name,index,shape,design):
    import numpy as np
    indices=list(map(int,np.unravel_index(index,shape))) if shape else []
    result={"flat_index":int(index),"indices":indices}
    if name in ("beta_rate","beta_workload") and indices:
        result["feature"]=design["feature_names"][indices[0]]
    elif name in ("population_workload","population_log_rate") and indices:
        result["position"]=design["positions"][indices[0]]
    elif name in ("player_effect","player_z") and len(indices)==2:
        result.update(player_id=design["players"][indices[0]],effect=("workload","production")[indices[1]])
    elif name in ("player_workload_raw","player_rate_z") and indices:
        result.update(player_id=design["players"][indices[0]],
                      effect="workload_sampling_coordinate" if name=="player_workload_raw" else "conditional_production")
    elif name in ("team_effect","team_z") and len(indices)==2:
        result.update(team=design["teams"][indices[0]],effect=("own_team","opponent_allowance")[indices[1]])
    elif name in ("season_effect","season_z") and len(indices)==2:
        result.update(season=design["seasons"][indices[0]],effect=("workload","production")[indices[1]])
    return result


def parameter_report(trace,design,quality):
    import numpy as np
    from arviz_stats import rhat,ess
    p=trace.posterior.to_dataset() if hasattr(trace.posterior,"to_dataset") else trace.posterior
    p=p.copy(deep=False)
    corr=p["player_chol_corr"]
    p["estimated_player_correlation"]=corr.isel({corr.dims[-2]:0,corr.dims[-1]:1},drop=True)
    names=quality.get("checked_variables") or json.loads(p.attrs["stochastic_variables"])
    result=[];errors=[]
    for name in dict.fromkeys(names):
        try:
            subset=p[[name]]
            rv=np.asarray(_diagnostic_values(rhat(subset)))
            bulk=np.asarray(_diagnostic_values(ess(subset,method="bulk")))
            tail=np.asarray(_diagnostic_values(ess(subset,method="tail")))
            variable=p[name].transpose("chain","draw",*[k for k in p[name].dims if k not in ("chain","draw")])
            shape=variable.shape[2:]
            worst=int(rv.argmax());smallest=int(bulk.argmin());tail_index=int(tail.argmin())
            selected=np.asarray(variable).reshape((variable.shape[0],variable.shape[1],-1))[:,:,worst]
            result.append({"variable":name,"max_rhat":float(rv.max()),"min_bulk_ess":float(bulk.min()),
                "min_tail_ess":float(tail.min()),"rhat_failures":int((rv>1.01).sum()),
                "bulk_ess_failures":int((bulk<400).sum()),"tail_ess_failures":int((tail<400).sum()),
                "worst_rhat_coordinate":coordinate(name,worst,shape,design),
                "lowest_bulk_coordinate":coordinate(name,smallest,shape,design),
                "lowest_tail_coordinate":coordinate(name,tail_index,shape,design),
                "worst_coordinate_chain_means":selected.mean(axis=1).tolist(),
                "worst_coordinate_chain_sd":selected.std(axis=1).tolist()})
        except (KeyError,ValueError,TypeError,AttributeError) as exc:
            errors.append({"variable":name,"error":str(exc)})
    return {"by_rhat":sorted(result,key=lambda x:x["max_rhat"],reverse=True),
            "by_bulk_ess":sorted(result,key=lambda x:x["min_bulk_ess"]),"errors":errors}


def audit(run_dir):
    import arviz as az
    import numpy as np
    root=Path(run_dir);folder=root/"context"
    manifest=io.load_json(folder/"manifest.json");design=io.load_json(folder/"design.json")
    if io.file_hash(folder/"posterior.nc")!=manifest["posterior_sha256"]:
        raise ValueError("posterior_checksum_changed")
    if io.file_hash(folder/"design.json")!=manifest["design_sha256"]:
        raise ValueError("design_checksum_changed")
    trace=az.from_netcdf(folder/"posterior.nc");quality=diagnostics(trace)
    stats=trace.sample_stats;chain={}
    for name in ("diverging","tree_depth","n_steps","step_size","lp"):
        if name not in stats:continue
        raw=np.asarray(stats[name])
        chain[name]={"mean_per_chain":raw.mean(axis=1).tolist(),"max_per_chain":raw.max(axis=1).tolist()}
    energy=np.asarray(stats["energy"])
    variance=energy.var(axis=1)
    bfmi=np.divide((np.diff(energy,axis=1)**2).mean(axis=1),variance,
                   out=np.full(len(variance),np.nan),where=variance>0)
    chain["energy"]={"bfmi_per_chain":bfmi.tolist()}
    report={"schema":"nfl-convergence-audit-v1","sampling_rerun":False,"ranking_allowed":False,
            "recorded_diagnostics":manifest["diagnostics"],"recomputed_diagnostics":quality,
            "parameters":parameter_report(trace,design,quality),"design":design_report(design),
            "chain_statistics":chain,"posterior_sha256":manifest["posterior_sha256"]}
    # Only new audit files are written. No posterior, frozen input or status edit.
    report=finite_json(report)
    destination=root/"convergence_audit.json";io.write_json(destination,report)
    packet=root/"convergence_diagnostics.zip"
    with zipfile.ZipFile(packet,"w",zipfile.ZIP_DEFLATED) as z:
        for name in ("convergence_audit.json","config.json","code_receipt.json","runtime_receipt.json",
                     "context/manifest.json","context/design.json","frozen/preflight.json","frozen/frozen_hashes.json"):
            path=root/name
            if path.is_file():z.write(path,name)
        license_file=Path(__file__).resolve().parents[1]/"THIRD_PARTY_DATA.md"
        if license_file.is_file():z.write(license_file,"THIRD_PARTY_DATA.md")
    print(json.dumps({"diagnostics":report["recomputed_diagnostics"],"worst_parameters":report["parameters"]["by_rhat"][:5],
                      "design_rank":report["design"]["rank"],"design_columns":report["design"]["columns"],
                      "packet":str(packet)},allow_nan=False,indent=2))
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir",type=Path,default=Path(__file__).resolve().parents[1]/"reports/nfl_reads_full_v1")
    audit(p.parse_args().run_dir)
