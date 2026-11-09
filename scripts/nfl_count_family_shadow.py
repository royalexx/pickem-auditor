"""Chronological Bayesian count-family comparison for NFL volume markets.

Ribeiro et al. (2025) motivate comparing Poisson, overdispersed and
zero-inflated dynamic count models with out-of-sample proper scoring.

This lightweight shadow diagnostic has one exact Gamma-Poisson posterior
predictive family and two moment-empirical-Bayes alternatives (NB, ZINB).
It is NOT a PyMC posterior sample, not the paper's fitted dynamic ZIP and
does NOT automatically replace accepted NUTS models or select 2024 models
using 2024 outcomes.

Family decisions are frozen using past-only walk-forward observations, and
require actual evidence of excess zeros before ZINB can be considered.
"""
from __future__ import annotations
from datetime import date
import math

FAMILIES=("gamma_poisson","neg_binomial","zero_inflated_nb")
EPS=1e-12

def _numeric_count(y):
    if isinstance(y,bool) or not isinstance(y,(int,float)) or not math.isfinite(y):
        raise ValueError("nonfinite_count")
    if y<0 or not float(y).is_integer():raise ValueError("non_integer_count")
    return int(y)

def _history(obs,cutoff,half_life_days=56.):
    target=date.fromisoformat(str(cutoff))
    pairs=[]
    for row in obs:
        d=date.fromisoformat(str(row["gameday"]))
        if d>=target:raise ValueError("future_or_target_day_leakage")
        v=_numeric_count(row["value"])
        weight=2**(-(target-d).days/half_life_days)
        pairs.append((v,weight))
    return pairs

def fit_shadow_count_families(observations,*,cutoff,reference_mean=2.,half_life_days=56.):
    if not math.isfinite(reference_mean) or reference_mean<=0:
        raise ValueError("invalid_reference_mean")
    rows=_history(observations,cutoff,half_life_days=half_life_days)
    neff=sum(w for _,w in rows)
    ysum=sum(v*w for v,w in rows)
    mu=(2.*reference_mean+ysum)/(2.+neff)
    # Exact Gamma-Poisson posterior predictive, starting with a proper Gamma
    # prior; older observations contribute less to posterior sufficient stats.
    alpha=2.*reference_mean+ysum
    beta=2.+neff
    var=max(0.,sum(w*(v-mu)**2 for v,w in rows)/max(neff,1e-9))
    dispersion=max(1.,min(300.,mu*mu/max(1e-6,var-mu))) if var>mu else 300.
    expected0=(dispersion/(dispersion+mu))**dispersion
    observed0=(1.+sum(w for v,w in rows if v==0))/(2.+neff)
    extra0=max(0.,min(.45,(observed0-expected0)/max(.001,1.-expected0)))
    return dict(n=len(rows),effective_n=neff,mean=mu,
       gamma_shape=alpha,gamma_rate=beta,
       nb_dispersion=dispersion,extra_zero_probability=extra0,
       observed_zero_rate=observed0,nb_expected_zero_rate=expected0,
       reference_mean=reference_mean,fit_asof=cutoff)

def probability_mass(y,params,family):
    from scipy.stats import nbinom
    y=_numeric_count(y)
    mu=float(params["mean"])
    if family=="gamma_poisson":
        a=float(params["gamma_shape"]);b=float(params["gamma_rate"])
        return float(nbinom.pmf(y,a,b/(b+1.)))
    k=float(params["nb_dispersion"])
    base=float(nbinom.pmf(y,k,k/(k+mu)))
    if family=="neg_binomial":return base
    if family=="zero_inflated_nb":
        pi=float(params["extra_zero_probability"])
        return float(pi+(1-pi)*base) if y==0 else float((1-pi)*base)
    raise ValueError("unregistered_count_family")

def probability_over(line,params,family):
    from scipy.stats import nbinom
    if not isinstance(line,(int,float)) or not math.isfinite(line):
        raise ValueError("invalid_count_line")
    if line<0:return 1.
    y=math.floor(line)
    mu=float(params["mean"])
    if family=="gamma_poisson":
        a=float(params["gamma_shape"]);b=float(params["gamma_rate"])
        return float(nbinom.sf(y,a,b/(b+1.)))
    k=float(params["nb_dispersion"]);p=k/(k+mu)
    over=float(nbinom.sf(y,k,p))
    if family=="neg_binomial":return over
    if family=="zero_inflated_nb":
        return (1.-float(params["extra_zero_probability"]))*over
    raise ValueError("unregistered_count_family")

def chronological_family_selection(observations,*,evaluation_start,
                                   cutoff,reference_mean=2.,min_validation=80):
    """Use only data BEFORE cutoff and time-forward validation within that.

    All rows after or equal to cutoff are forbidden from family selection.
    The last period starting evaluation_start is scored one day at a time;
    same-day outcomes are never included in that day's predictive fit.
    """
    start=date.fromisoformat(str(evaluation_start))
    end=date.fromisoformat(str(cutoff))
    if start>=end:raise ValueError("invalid_family_validation_window")
    sequence=sorted(observations,key=lambda x:x["gameday"])
    past=[];byday={}
    for row in sequence:
        day=date.fromisoformat(str(row["gameday"]))
        if day>=end:raise ValueError("family_selection_uses_future_outcomes")
        _numeric_count(row["value"])
        if day<start:past.append(row)
        else:byday.setdefault(day,[]).append(row)
    scored={k:[] for k in FAMILIES}
    for day,items in sorted(byday.items()):
        if len(past)<30:
            past+=items
            continue
        p=fit_shadow_count_families(past,cutoff=str(day),reference_mean=reference_mean)
        for item in items:
            for family in FAMILIES:
                prob=probability_mass(item["value"],p,family)
                scored[family].append(-math.log(max(EPS,prob)))
        past+=items
    n=min(map(len,scored.values()))
    if n<min_validation:
        return dict(status="insufficient_chronological_family_evidence",
            selected_family=None,n_validation=n,mean_log_score=None)
    aggregate={f:sum(scored[f])/len(scored[f]) for f in FAMILIES}
    # Extra parameters are justified only with persistent zero excess and
    # heldout log-score gain; otherwise prefer the simpler count models.
    finalist=min(("gamma_poisson","neg_binomial"),key=lambda f:aggregate[f])
    finalfit=fit_shadow_count_families(past,cutoff=str(end),
                                      reference_mean=reference_mean)
    if (finalfit["extra_zero_probability"]>=.08 and
        aggregate["zero_inflated_nb"]+0.005<aggregate[finalist]):
        finalist="zero_inflated_nb"
    return dict(status="shadow_family_selected_past_only",
        selected_family=finalist,n_validation=n,
        mean_log_score=aggregate,selection_cutoff=str(end),
        zero_extra_rate=finalfit["extra_zero_probability"],
        production_allowed=False)
