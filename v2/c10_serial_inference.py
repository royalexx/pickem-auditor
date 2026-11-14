"""C10: fixed-horizon dependence stress test, no prospective outcomes.

Independent calibration and validation streams. Critical cutoff is max 97.5th
percentile of -HAC-t across *predeclared* null simulation scenarios. This
offers simulation-conditional control, NOT distribution-free Type-I control.
No automatic promotion, re-selection, or optional looks.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt, log, exp, isfinite, fsum
import random
import statistics

VERSION="v25_c10_serial_calibration_v1"
EXPERIMENT="EXP-V25-NHL-SOG-EXPOSURE-EB-001"
ALPHA=0.025
MIN_USEFUL=0.002
HORIZONS=(12,20,40)
RHO=(0.0,0.3,0.6)
DISTRIBUTIONS=("gaussian","centered_lognormal","heavy_tail")
HETERO=(False,True)
CLUSTERS=("thin","mixed")
SCENARIOS=tuple((rho,dist,het,cluster)
  for rho in RHO for dist in DISTRIBUTIONS for het in HETERO for cluster in CLUSTERS)

def _innovation(rng,dist):
    if dist=="gaussian":
        return rng.gauss(0,1)
    if dist=="centered_lognormal":
        # variance-one, centered log-normal with large positive skew
        z=rng.gauss(0,1)
        return (exp(.75*z)-exp(.75*.75/2))/sqrt(exp(2*.75*.75)-exp(.75*.75))
    if dist=="heavy_tail":
        # Student t with df=3, variance 3
        return rng.gauss(0,1)/sqrt(rng.gammavariate(1.5,2/3))/sqrt(3)
    raise ValueError("unknown distribution")

def simulate_date_differences(*,rng,dates,rho,dist,hetero,cluster,delta=0.0,
                              date_sd=0.04):
    if not 8<=dates<=80 or rho not in RHO or dist not in DISTRIBUTIONS:
        raise ValueError("unsupported scenario")
    if cluster not in CLUSTERS or not isinstance(hetero,bool):
        raise ValueError("bad cluster scenario")
    x=0.0
    out=[]
    for day in range(dates):
        innovation=_innovation(rng,dist)
        x=rho*x+sqrt(1-rho*rho)*innovation
        # Date-level heteroskedasticity, predeclared alternating high/low,
        # independent of outcomes and of the sign of an effect.
        scale=(1.6 if day%2 else .4) if hetero else 1.0
        n_games=rng.randint(1,3) if cluster=="thin" else rng.randint(2,9)
        game_total=0.0
        count=0
        for _ in range(n_games):
            n_contracts=rng.randint(1,3) if cluster=="thin" else rng.randint(1,14)
            g=rng.gauss(0,.25)
            for _contract in range(n_contracts):
                # Same-game and same-date effects deliberately shared
                individual=rng.gauss(0,.18)
                game_total+=x+g+individual
                count+=1
        out.append(delta+date_sd*scale*game_total/count)
    return out

def hac_student_stat(dates,lags=3):
    """Date-equal-weighted, Bartlett HAC, t scaling; no data-driven lag choice."""
    n=len(dates)
    if n<8 or any(not isfinite(x) for x in dates):
        raise ValueError("insufficient/nonfinite dates")
    m=statistics.mean(dates)
    centered=[x-m for x in dates]
    # With 40 days, fixed lag 3: precommitted, not optimized post hoc.
    q=min(lags,n-2)
    var=fsum(x*x for x in centered)/n
    for lag in range(1,q+1):
        gam=fsum(centered[j]*centered[j-lag] for j in range(lag,n))/n
        var+=2*(1-lag/(q+1))*gam
    if var<=1e-20:
        return float("inf") if m<0 else float("-inf") if m>0 else 0.
    return -m/sqrt(var/n)

def quantile_sorted(vals,prob):
    if not vals or not 0<=prob<=1:
        raise ValueError("bad quantile")
    rank=min(len(vals)-1,int(prob*len(vals)))
    return sorted(vals)[rank]

def _one_grid(rng,dates,replicates,delta,scenario,cutoff=None):
    rho,dist,het,cluster=scenario
    statistics_=[]
    for i in range(replicates):
        d=simulate_date_differences(rng=rng,dates=dates,rho=rho,dist=dist,
                                   hetero=het,cluster=cluster,delta=delta)
        statistics_.append(hac_student_stat(d))
    if cutoff is None:return statistics_
    return sum(t>cutoff for t in statistics_)/replicates

def calibrate_and_validate(*,dates=40,calibration_reps=600,validation_reps=1000,
                           seed=20261113,alternatives=(-0.002,),
                           date_sd=0.04):
    """Seed-separated simulation preflight, no forecasts or realized outcomes.

    Calibration picks a single worst-case cutoff from ALL 36 null scenarios.
    A fresh validation stream measures independent null rejection and power.
    Date-SD of 0.04 is a hypothetical planning scale; no real estimate.
    """
    if dates not in HORIZONS or calibration_reps<100 or validation_reps<100:
        raise ValueError("preflight requires supported horizon and >=100 reps")
    if date_sd!=0.04:
        raise ValueError("scale must match locked scenario")
    cal=random.Random(seed)
    validation=random.Random(seed+1_000_003)
    # One-sided family error is calibrated over the enumerated null DGPs,
    # not over post hoc selected variants of a test.
    per=[quantile_sorted(_one_grid(cal,dates,calibration_reps,0.,scenario),
                         1-ALPHA) for scenario in SCENARIOS]
    cutoff=max(per)
    results=[]
    for scenario in SCENARIOS:
        size=_one_grid(validation,dates,validation_reps,0.,scenario,cutoff)
        pwr={str(effect):_one_grid(validation,dates,validation_reps,effect,scenario,cutoff)
             for effect in alternatives}
        results.append({"rho":scenario[0],"dist":scenario[1],
                        "heteroscedastic":scenario[2],"game_cluster":scenario[3],
                        "type1_rate":size,"power":pwr})
    return {"schema":VERSION,"experiment":EXPERIMENT,"date_count":dates,
            "alpha":ALPHA,"delta_min_useful":MIN_USEFUL,
            "date_sd_assumed":date_sd,
            "calibration_reps":calibration_reps,
            "validation_reps":validation_reps,"seed":seed,
            "calibration_cutoff":cutoff,"lag_choice":3,
            "test":"one-sided_fixed_horizon_worst_grid_calibrated_HAC_stat",
            "scenarios":results,
            "worst_null_type1":max(r["type1_rate"] for r in results),
            "min_power_at_minus_0_002":min(r["power"][str(-MIN_USEFUL)] for r in results)
                    if -MIN_USEFUL in alternatives else None,
            "claimed_scope":"simulated_scenario_grid_only",
            "independent_validation_stream":True,
            "full_prospective_signoff":False}

def candidate_status(report,*,max_type1=0.035,min_power=0.8):
    """Do not approve with underpowered 40-date horizon."""
    if report.get("schema")!=VERSION:
        return "INVALID_C10_RECEIPT"
    # 0.035 is a diagnostic Monte Carlo acceptance envelope, NOT alpha.
    if report["worst_null_type1"]>max_type1:
        return "BLOCKED_SIMULATED_SIZE"
    if report["min_power_at_minus_0_002"] is None or (
        report["min_power_at_minus_0_002"]<min_power):
        return "EXPLORATORY_LOW_POWER"
    return "SIMULATION_PASSED_NOT_INDEPENDENTLY_APPROVED"
