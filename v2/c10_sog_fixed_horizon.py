"""C10 independent CPU-only sensitivity test: fixed-horizon serial dependence.

NOT a live source of score data or a valid p-value until separately approved.
Calibration and held-out synthetic audit use independent deterministic seeds.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import numpy as np

EXPERIMENT="EXP-V25-NHL-SOG-EXPOSURE-EB-001"
SCHEMA="v25_c10_hac_worstcase_null_grid_v1"
HORIZON=40
ALPHA=.025
LAG=5
EFFECT=-.002
CALIBRATION_TAIL=.01


def generate_slate_date_differences(*,repeats,seed,rho,innovation,hetero,
                                    cluster_pattern,date_sd,effect):
    """40 date-equal weighted paired-score differences with games/contracts."""
    rng=np.random.default_rng(seed)
    games=rng.integers(1,4 if cluster_pattern=="sparse" else 10,
                       size=(repeats,HORIZON))
    contracts=rng.integers(1,5 if cluster_pattern=="sparse" else 22,
                           size=(repeats,HORIZON))
    if innovation=="gaussian":
        innovations=rng.normal(size=(repeats,HORIZON))
    elif innovation=="negative_exponential":
        innovations=1-rng.exponential(size=(repeats,HORIZON))
    elif innovation=="t3":
        innovations=rng.standard_t(df=3,size=(repeats,HORIZON))/np.sqrt(3)
    else:raise ValueError("innovation not preregistered")
    z=np.zeros((repeats,HORIZON))
    z[:,0]=innovations[:,0]
    for t in range(1,HORIZON):
        z[:,t]=rho*z[:,t-1]+np.sqrt(1-rho*rho)*innovations[:,t]
    game=rng.normal(size=(repeats,HORIZON))/np.sqrt(games)
    contract=rng.normal(size=(repeats,HORIZON))/np.sqrt(games*contracts)
    dates=.8*z+.5*game+.3*contract
    if hetero:
        dates*=np.where((np.arange(HORIZON)%3)==0,1.8,.55)[None,:]
    return effect+date_sd*dates


def hac_t(dates,*,lag=LAG):
    """Newey-West Bartlett, fixed bandwidth 5, t-statistic of 40 date means."""
    n=dates.shape[1]
    x=dates-dates.mean(axis=1,keepdims=True)
    v=np.sum(x*x,axis=1)/n
    for k in range(1,lag+1):
        cov=np.sum(x[:,k:]*x[:,:-k],axis=1)/n
        v+=2*(1-k/(lag+1))*cov
    v=np.maximum(v,1e-15)
    return dates.mean(axis=1)/np.sqrt(v/n)


def scenarios():
    for sd,rho,noise,hetero,cluster in itertools.product(
         (.01,.04),(0.,.3,.6,.8),
         ("gaussian","negative_exponential","t3"),
         (False,True),("sparse","dense")):
        yield dict(date_sd=sd,rho=rho,innovation=noise,
                   hetero=hetero,cluster_pattern=cluster)


def seed_for(i,phase):
    return 20261113+phase*100000+i*1009


def run(*,calibrate_reps=1500,audit_reps=2500):
    grid=list(scenarios())
    null_quantiles=[]
    for i,p in enumerate(grid):
        z=hac_t(generate_slate_date_differences(
             repeats=calibrate_reps,seed=seed_for(i,0),effect=0.,**p))
        null_quantiles.append(float(np.quantile(z,CALIBRATION_TAIL)))
    cutoff=min(null_quantiles)
    results=[]
    for i,p in enumerate(grid):
        null=hac_t(generate_slate_date_differences(
             repeats=audit_reps,seed=seed_for(i,1),effect=0.,**p))
        alt=hac_t(generate_slate_date_differences(
             repeats=audit_reps,seed=seed_for(i,2),effect=EFFECT,**p))
        results.append({**p,"type1_rate":float(np.mean(null<=cutoff)),
                        "power_at_minus_0_002":float(np.mean(alt<=cutoff))})
    powers=sorted(q["power_at_minus_0_002"] for q in results)
    out={
       "schema":SCHEMA,"experiment_id":EXPERIMENT,
       "prospective_outcomes_used":False,
       "calibration_replicates_each":calibrate_reps,
       "audit_replicates_each":audit_reps,
       "scenario_count":len(grid),"horizon":HORIZON,
       "primary_date_weighting":"equal",
       "statistic":"Bartlett HAC date-level t, bandwidth=5",
       "threshold_type":"pre-outcome worst-case 1pct simulated null quantile",
       "threshold":cutoff,"alpha_target":ALPHA,
       "observed_max_simulated_type1":max(q["type1_rate"] for q in results),
       "power_min":powers[0],"power_median":powers[len(powers)//2],
       "power_max":powers[-1],"fixed_effect_delta":EFFECT,
       "interpretation":"Stress-grid conditional operating characteristics only; no real-data power assurance",
       "eligible_dates_collected":0,"simulation_scenarios":results}
    out["canonical_sha256"]=hashlib.sha256(
        json.dumps(out,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return out


if __name__=="__main__":
    import argparse
    from pathlib import Path
    p=argparse.ArgumentParser()
    p.add_argument("--output",required=True)
    p.add_argument("--calibrate-reps",type=int,default=1500)
    p.add_argument("--audit-reps",type=int,default=2500)
    a=p.parse_args()
    result=run(calibrate_reps=a.calibrate_reps,audit_reps=a.audit_reps)
    Path(a.output).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k!="simulation_scenarios"},indent=2))
