"""P5 NBA C-family: compare complete pipelines on matched prequential games.

S, O and J are layers, NOT three independent model votes.
W2/W3 are fit on earlier verified pairs and cannot certify their own scores.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
import math

from .scoring import (_utc, ScoreError, full_pmf, score_count, digest, local_slate_date)

PIPELINES={"S_ONLY","S_PLUS_O","S_O_J"}
WEIGHT_POLICIES={"W0","W1","W2","W3","W4"}

def _need(ok,code):
    if not ok:
        raise ScoreError(code)

def _key(row):
    return tuple(row[k] for k in ("sport","event_id","player_id","stat_key",
                                   "period","input_freeze_at"))

def verify_complete_pipeline_evidence(rows, *, require_outcomes=True):
    if not rows:
        raise ScoreError("NO_COMPLETE_PIPELINE_EVIDENCE")
    group=defaultdict(dict)
    for row in rows:
        _need(row.get("sport")=="NBA" and row.get("pipeline_id") in PIPELINES,
              "NBA_COMPLETE_PIPELINE_REQUIRED")
        _need(row.get("original_verified") is True and
              row.get("outcome_verified") is True if require_outcomes else
              row.get("original_verified") is True,
              "PIPELINE_PROVENANCE_UNVERIFIED")
        _need(_utc(row["training_cutoff_at"])<=_utc(row["input_freeze_at"])<=
              _utc(row["forecast_at"])<_utc(row["event_start_at"]),
              "PIPELINE_CHRONOLOGY_INVALID")
        if require_outcomes:
            _need(type(row.get("actual")) is int and row["actual"]>=0 and
                  _utc(row["event_start_at"])<_utc(row["official_available_at"]),
                  "PIPELINE_ACTUAL_UNVERIFIED")
        key=_key(row)
        p=row["pipeline_id"]
        _need(p not in group[key],"DUPLICATE_COMPLETE_PIPELINE_FOR_SAME_FORECAST")
        full_pmf(row["distribution"],observed=row.get("actual"))
        group[key][p]=row
    for matches in group.values():
        actuals={m.get("actual") for m in matches.values()}
        _need(len(actuals)==1,"PIPELINE_OFFICIAL_OUTCOME_DISAGREEMENT")
    return group

def matched_pipeline_rows(rows, names):
    group=verify_complete_pipeline_evidence(rows)
    _need(bool(names) and len(names)==len(set(names)) and set(names)<=PIPELINES,
          "PIPELINE_SELECTION_INVALID")
    return [r for r in group.values() if set(names)<=set(r)]

def _mix(pipelines,weights):
    _need(len(pipelines)==len(weights) and all(w>=0 and math.isfinite(w) for w in weights)
          and abs(math.fsum(weights)-1.0)<1e-9,"INVALID_SIMPLEX")
    full=[full_pmf(p)[0] for p in pipelines]
    length=max(map(len,full))
    return {"kind":"discrete","masses":[[k,math.fsum(w*(p[k] if k<len(p) else 0.0)
        for w,p in zip(weights,full))] for k in range(length)]}

def mix_complete_pipelines(matched,weights):
    names=sorted(weights)
    _need(set(names)<=set(matched),"MISSING_COMPLETE_PIPELINE")
    first=matched[names[0]]
    for name in names[1:]:
        _need(_key(matched[name])==_key(first),"PIPELINE_MATCHING_FAILED")
        _need(matched[name].get("original_verified") is True,
              "PIPELINE_ORIGINAL_FORECAST_UNVERIFIED")
    d=_mix([matched[n]["distribution"] for n in names],[weights[n] for n in names])
    return {"distribution":d,"pipeline_weights":weights,
            "same_game_scenario_bank_independence_claim":False}

def _project_simplex(v):
    ordered=sorted(v,reverse=True)
    cumulative=0.
    rho=-1
    threshold=0.
    for i,x in enumerate(ordered):
        cumulative+=x
        t=(cumulative-1)/(i+1)
        if x>t:
            rho=i
            threshold=t
    _need(rho>=0,"SIMPLEX_PROJECTION_FAILED")
    out=[max(0.,x-threshold) for x in v]
    total=math.fsum(out)
    return [x/total for x in out]

def _cdf_arrays(matched, names):
    first=matched[names[0]]
    y=first["actual"]
    vectors=[full_pmf(matched[n]["distribution"],observed=y)[0] for n in names]
    length=max(y+1,*map(len,vectors))
    arrays=[]
    for v in vectors:
        run=0.; cdf=[]
        for k in range(length):
            if k<len(v):
                run+=v[k]
            cdf.append(min(run,1.))
        arrays.append(cdf)
    return arrays,y

def _loss_and_gradient(pairs,names,w,lam):
    L=0.;gradient=[0.]*len(names)
    for matched in pairs:
        arrays,y=_cdf_arrays(matched,names)
        for k in range(len(arrays[0])):
            residual=sum(w[j]*arrays[j][k] for j in range(len(names))) - int(k>=y)
            L+=residual**2
            for j in range(len(names)):
                gradient[j]+=2*residual*arrays[j][k]
    n=len(pairs)
    w0=[1/len(w)]*len(w)
    L=L/n+lam*math.fsum((w[j]-w0[j])**2 for j in range(len(w)))
    gradient=[v/n+2*lam*(w[i]-w0[i]) for i,v in enumerate(gradient)]
    return L,gradient

def fit_chronological_weights(rows, *, policy, cutoff_at, names=None, min_dates=40,
                              min_games=40, lam=0.1, max_iter=250):
    """Return no learned weights unless distinct dates AND games meet the gate.

    Hyperparameter selection and later validation must occur in separate
    windows; the returned training loss is NOT independent validation.
    """
    _need(policy in ("W2","W3"),"LEARNED_WEIGHT_POLICY_UNREGISTERED")
    names=sorted(names or PIPELINES)
    _need(len(names)>=2 and set(names)<=PIPELINES,"INVALID_PIPELINE_SET")
    _need(_utc(cutoff_at),"INVALID_CUTOFF")
    pairs=matched_pipeline_rows(rows,names)
    usable=[]
    for x in pairs:
        first=x[names[0]]
        if _utc(first["official_available_at"])<=_utc(cutoff_at):
            usable.append(x)
    dates={local_slate_date(x[names[0]]["event_start_at"],
         original_date=x[names[0]].get("original_local_slate_date"),
         original_date_verified=x[names[0]].get("original_local_slate_date_verified") is True)
         for x in usable}
    games={x[names[0]]["event_id"] for x in usable}
    if len(dates)<min_dates or len(games)<min_games:
        return {"status":"INSUFFICIENT_CHRONOLOGICAL_EVIDENCE",
                "n_dates":len(dates),"n_games":len(games),
                "minimum_dates":min_dates,"minimum_games":min_games,
                "policy":"W0_FROZEN_CHAMPION"}
    if policy=="W3" and len({x[names[0]]["stat_key"] for x in usable})>1:
        by=defaultdict(list)
        for x in usable:
            by[x[names[0]]["stat_key"]].extend(x.values())
        return {"status":"STAT_SPECIFIC","models":{
            k:fit_chronological_weights(v,policy="W3",cutoff_at=cutoff_at,
                names=names,min_dates=min_dates,min_games=min_games,
                lam=lam,max_iter=max_iter) for k,v in by.items()}}
    _need(_number_is_nonnegative(lam),"REGULARIZATION_INVALID")
    w=[1/len(names)]*len(names)
    initial,_=_loss_and_gradient(usable,names,w,lam)
    for step in range(max_iter):
        loss,grad=_loss_and_gradient(usable,names,w,lam)
        trial=_project_simplex([w[i]-0.02*grad[i] for i in range(len(names))])
        next_loss,_=_loss_and_gradient(usable,names,trial,lam)
        if next_loss>loss:
            break
        if max(abs(trial[i]-w[i]) for i in range(len(names)))<1e-9:
            w=trial
            break
        w=trial
    final,_=_loss_and_gradient(usable,names,w,lam)
    return {"status":"TRAINED_RESEARCH_ONLY_NO_PROMOTION","policy":policy,
            "weights":dict(zip(names,w)),"training_crps":final,
            "initial_equal_weight_training_crps":initial,
            "trained_before":cutoff_at,"n_distinct_dates":len(dates),
            "n_distinct_games":len(games),"n_paired_player_games":len(usable),
            "regularization":lam,"prospective_validation":"NOT_PERFORMED",
            "independent_holdout_approval":False}

def _number_is_nonnegative(x):
    return type(x) in (int,float) and math.isfinite(x) and x>=0

def resolve_policy(*,policy,eligible_names,learned=None,champion="S_ONLY"):
    """No forced mixture. W4 never silently activated."""
    names=sorted(set(eligible_names)&PIPELINES)
    if policy=="W0":
        _need(champion in names,"FROZEN_CHAMPION_MISSING")
        return {champion:1.}
    if policy=="W1":
        _need(bool(names),"NO_COMPLETE_PIPELINES")
        return {k:1/len(names) for k in names}
    if policy in ("W2","W3"):
        if learned is None or learned.get("status")!="TRAINED_RESEARCH_ONLY_NO_PROMOTION":
            return resolve_policy(policy="W0",eligible_names=names,champion=champion)
        w=learned["weights"]
        _need(set(w)==set(names),"LEARNED_PIPELINE_COVERAGE_MISMATCH")
        return w
    raise ScoreError("W4_CONTEXT_GATING_NOT_AUTHORIZED")
