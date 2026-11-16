"""P5 cached full-pipeline mixtures and prequential experiment machinery.

No historical fitting is allowed by this initial research package. W2/W3
optimization requires explicitly marked SYNTHETIC fixtures; G2 historical
authorization is intentionally absent. All inputs are complete distributions,
never separately weighted S/O/J mechanism predictions.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import numpy as np
from scipy.optimize import minimize
from .scores import ScoreError, validate_pmf, crps


class ExperimentError(ValueError):
    pass


MODES=("S_ONLY","S_O","S_O_J")
STATS=("points","rebounds","assists","threes","pr","pa","ra","pra")


def _utc(value):
    try:
        v=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (ValueError,AttributeError) as exc:
        raise ExperimentError("INVALID_TIME") from exc
    if v.tzinfo is None or v.utcoffset()!=timedelta(0):
        raise ExperimentError("UTC_TIME_REQUIRED")
    return v


def _row_date(value):
    date=_utc(value)
    if date >= datetime(2023,10,1,tzinfo=timezone.utc):
        raise ExperimentError("2023_24_HOLDOUT_QUARANTINED")
    return date


def make_walk_forward_folds(rows, *, min_train_dates=3, test_dates=1,
                            embargo_days=0):
    """Metadata-only folds; observations are NEVER fetched by this function.

    Training label release must strictly precede the earliest test freeze.
    Game/date all stay together even if many players/props share that cluster.
    """
    rows=list(rows)
    if not rows or min_train_dates<1 or test_dates<1 or embargo_days<0:
        raise ExperimentError("BAD_FOLD_CONFIG")
    grouped=defaultdict(list)
    seen=set()
    for row in rows:
        for field in ("game_id","player_id","stat","frozen_at","event_start_at",
                      "official_available_at","date"):
            if field not in row:
                raise ExperimentError("MISSING_"+field)
        if row["stat"] not in STATS:
            raise ExperimentError("INVALID_STAT")
        freeze=_utc(row["frozen_at"])
        start=_utc(row["event_start_at"])
        released=_utc(row["official_available_at"])
        d=_row_date(row["date"])
        if freeze>=start or released<start or d.date()!=start.date():
            raise ExperimentError("INVALID_CHRONOLOGY")
        key=(row["game_id"],row["player_id"],row["stat"],row["frozen_at"])
        if key in seen:
            raise ExperimentError("DUPLICATE_FORECAST")
        seen.add(key)
        grouped[d.date()].append(row)
    dates=sorted(grouped)
    result=[]
    for i in range(min_train_dates,len(dates),test_dates):
        cohort=dates[i:i+test_dates]
        if not cohort:
            break
        test=[r for day in cohort for r in grouped[day]]
        earliest=min(_utc(r["frozen_at"]) for r in test)
        eligible=[]
        for day in dates[:i]:
            if day>cohort[0]-timedelta(days=embargo_days+1):
                continue
            for r in grouped[day]:
                if _utc(r["official_available_at"])<earliest:
                    eligible.append(r)
        train_dates={r["date"] for r in eligible}
        if len(train_dates)<min_train_dates:
            continue
        if {r["game_id"] for r in eligible}&{r["game_id"] for r in test}:
            raise ExperimentError("GAME_CROSS_FOLD")
        result.append({"train":eligible,"test":test,"origin":earliest.isoformat(),
                       "n_train_dates":len(train_dates),
                       "n_test_dates":len(cohort)})
    return result


class CachedCohort:
    """Cumulative PMFs cached once; no game reruns while testing weights."""
    def __init__(self, rows, *, authorization=""):
        if authorization!="SYNTHETIC_UNIT_TEST":
            raise ExperimentError("HISTORICAL_WEIGHT_FIT_NOT_AUTHORIZED")
        rows=list(rows)
        if not rows:
            raise ExperimentError("EMPTY_COHORT")
        self.pipeline_ids=tuple(sorted(rows[0]["pipelines"]))
        if not self.pipeline_ids or len(self.pipeline_ids)!=len(set(self.pipeline_ids)):
            raise ExperimentError("INVALID_PIPELINES")
        self.rows=rows
        seen=set()
        support=0
        modes={}
        for row in rows:
            if row.get("source_profile")!="SYNTHETIC":
                raise ExperimentError("ONLY_SYNTHETIC_FITTING")
            if row["stat"] not in STATS or type(row["actual"]) is not int or row["actual"]<0:
                raise ExperimentError("INVALID_OUTCOME_OR_STAT")
            if set(row["pipelines"])!=set(self.pipeline_ids):
                raise ExperimentError("INCOMPLETE_MATCHED_PIPELINES")
            ident=(row["game_id"],row["player_id"],row["stat"],row["date"])
            if ident in seen:
                raise ExperimentError("DUPLICATE_MATCHED_CASE")
            seen.add(ident)
            if _row_date(row["date"])>_utc(row["frozen_at"]):
                raise ExperimentError("FUTURE_DATE")
            if _utc(row["frozen_at"])>=_utc(row["event_start_at"]):
                raise ExperimentError("POSTGAME_FORECAST")
            if _utc(row["official_available_at"])<_utc(row["event_start_at"]):
                raise ExperimentError("OUTCOME_BEFORE_GAME")
            support=max(support,row["actual"])
            for name,item in row["pipelines"].items():
                mode=item.get("mode")
                if mode not in MODES:
                    raise ExperimentError("STAGE_NOT_COMPLETE_PIPELINE")
                if name in modes and modes[name]!=mode:
                    raise ExperimentError("PIPELINE_MODE_CHANGED")
                modes[name]=mode
                pmf=validate_pmf(item["pmf"])
                support=max(support,pmf[-1][0])
        if support>10000:
            raise ExperimentError("UNBOUNDED_CACHE_SUPPORT")
        self.modes=modes
        n,p,k=len(rows),len(self.pipeline_ids),max(support,1)
        pdf=np.zeros((n,p,k+1),dtype=np.float64)
        self.actual=np.array([r["actual"] for r in rows],dtype=int)
        for i,row in enumerate(rows):
            for j,name in enumerate(self.pipeline_ids):
                for x,prob in validate_pmf(row["pipelines"][name]["pmf"]):
                    pdf[i,j,x]=prob
        # All PMFs complete. The last CDF term equals 1 and contributes zero,
        # so remove it for faster quadratic scoring.
        self.cdfs=np.cumsum(pdf,axis=2)[:,:,:-1]
        self.target=(np.arange(k)[None,:]>=self.actual[:,None]).astype(float)
        self.gram=np.einsum("ijk,ilk->jl",self.cdfs,self.cdfs,optimize=True)/n
        self.linear=np.einsum("ijk,ik->j",self.cdfs,self.target,optimize=True)/n
        self.constant=float(np.einsum("ik,ik->",self.target,self.target)/n)
        self.cached_pmf_count=n*p
        self.game_count=len({r["game_id"] for r in rows})
        self.date_count=len({r["date"] for r in rows})

    def crps_for(self,weights):
        w=self._weights(weights)
        return float(w@self.gram@w-2*w@self.linear+self.constant)

    def _weights(self,w):
        a=np.asarray(w,dtype=float)
        if a.shape!=(len(self.pipeline_ids),) or not np.all(np.isfinite(a)) or np.min(a)<-1e-10 or abs(a.sum()-1)>1e-9:
            raise ExperimentError("INVALID_SIMPLEX_WEIGHTS")
        return a

    def nll_for(self,weights):
        w=self._weights(weights)
        probability=np.zeros(len(self.rows))
        for i,r in enumerate(self.rows):
            probability[i]=sum(w[j]*dict(validate_pmf(r["pipelines"][name]["pmf"])).get(r["actual"],0)
                               for j,name in enumerate(self.pipeline_ids))
        return float(-np.log(probability).mean()) if np.all(probability>0) else math.inf


def w0_simple(cache, champion_id):
    if champion_id not in cache.pipeline_ids or cache.modes[champion_id]!="S_ONLY":
        raise ExperimentError("SIMPLE_CHAMPION_REQUIRED")
    return {name:float(name==champion_id) for name in cache.pipeline_ids}


def w1_equal(cache):
    return {name:1/len(cache.pipeline_ids) for name in cache.pipeline_ids}


def _solve(cache,lam,prior):
    if lam<0 or not math.isfinite(lam):
        raise ExperimentError("INVALID_REGULARIZATION")
    p=len(cache.pipeline_ids)
    anchor=np.asarray(prior,dtype=float)
    cache._weights(anchor)
    def objective(x):
        diff=x-anchor
        value=x@cache.gram@x-2*x@cache.linear+cache.constant+lam*(diff@diff)
        gradient=2*(cache.gram@x-cache.linear)+2*lam*diff
        return float(value),gradient
    result=minimize(objective,anchor,method="SLSQP",jac=True,
                    bounds=[(0.,1.)]*p,
                    constraints=[{"type":"eq","fun":lambda x:x.sum()-1,
                                  "jac":lambda x:np.ones_like(x)}],
                    options={"ftol":1e-12,"maxiter":1000})
    if not result.success or np.min(result.x)<-1e-8 or abs(result.x.sum()-1)>1e-8:
        raise ExperimentError("SIMPLEX_OPTIMIZER_FAILURE")
    x=np.maximum(result.x,0)
    x/=x.sum()
    return {name:float(w) for name,w in zip(cache.pipeline_ids,x)}


def w2_global(cache, *, lam=0.1, prior=None):
    """Synthetic-only global CRPS-optimal regularized simplex weights."""
    if prior is None:
        prior=np.full(len(cache.pipeline_ids),1/len(cache.pipeline_ids))
    return _solve(cache,lam,prior)


def w3_by_stat(rows, *, global_weights, lam=1.0, min_games=3):
    """Conditional W3 prototypes; rare stat pools shrink to the W2 anchor."""
    if min_games<1:
        raise ExperimentError("INVALID_MIN_GAMES")
    by_stat=defaultdict(list)
    for row in rows:
        by_stat[row["stat"]].append(row)
    output={}
    for stat,subrows in sorted(by_stat.items()):
        games=len({r["game_id"] for r in subrows})
        if games<min_games:
            output[stat]=dict(global_weights)
        else:
            cache=CachedCohort(subrows,authorization="SYNTHETIC_UNIT_TEST")
            if set(global_weights)!=set(cache.pipeline_ids):
                raise ExperimentError("GLOBAL_ANCHOR_MISMATCH")
            output[stat]=_solve(cache,lam,np.array([global_weights[k]
                                      for k in cache.pipeline_ids]))
    return output


def w4_contextual_gating(*args, **kwargs):
    raise ExperimentError("W4_CONDITIONAL_NOT_AUTHORIZED")


def explore_simplex(cache, *, trials=1000, seed=20261116, alpha=1.0):
    """Seeded synthetic candidate exploration using the cached quadratic."""
    if not 1<=trials<=100000 or alpha<=0:
        raise ExperimentError("INVALID_MC_TRIALS")
    rng=np.random.default_rng(seed)
    draws=rng.dirichlet(np.full(len(cache.pipeline_ids),alpha),size=trials)
    vals=np.einsum("ti,ij,tj->t",draws,cache.gram,draws,optimize=True)
    vals-=2*draws@cache.linear
    vals+=cache.constant
    idx=int(np.argmin(vals))
    return {"weights":{name:float(w) for name,w in
                       zip(cache.pipeline_ids,draws[idx])},
            "crps":float(vals[idx]),"trials":trials,"seed":seed,
            "cached_pmf_count":cache.cached_pmf_count,
            "game_count":cache.game_count,"date_count":cache.date_count}


def mc_precision_probe(pmf, *, seed=20261116, n_small=5000, n_large=20000):
    """Independent seeded sampling precision *diagnostic*, not fit/evidence."""
    if n_small!=5000 or n_large!=20000:
        raise ExperimentError("PRE_REGISTERED_MC_SIZES")
    rows=validate_pmf(pmf)
    values=np.array([v for v,_ in rows])
    masses=np.array([p for _,p in rows])
    rng=np.random.default_rng(seed)
    small=rng.choice(len(rows),size=n_small,p=masses)
    large=rng.choice(len(rows),size=n_large,p=masses)
    p5=np.bincount(small,minlength=len(rows))/n_small
    p20=np.bincount(large,minlength=len(rows))/n_large
    se5=np.sqrt(masses*(1-masses)/n_small)
    se20=np.sqrt(masses*(1-masses)/n_large)
    combined=np.sqrt(se5**2+se20**2)
    z=np.divide(abs(p5-p20),combined,out=np.zeros_like(combined),where=combined>0)
    return {"seed":seed,"counts":[n_small,n_large],
            "probabilities_5000":dict(zip(values.tolist(),p5.tolist())),
            "probabilities_20000":dict(zip(values.tolist(),p20.tolist())),
            "maximum_standardized_difference":float(z.max()),
            "se_ratio_nonzero":2.0,"draws_are_not_independent_games":True}


def paired_block_bootstrap(rows, *, cluster="date", repeats=1000,
                           seed=20261116, lower=.025, upper=.975):
    """Paired score difference (challenger minus control), not scenario rows."""
    if cluster not in ("date","game_id") or repeats<100 or not 0<lower<upper<1:
        raise ExperimentError("INVALID_BOOTSTRAP_CONFIG")
    blocks=defaultdict(list)
    for row in rows:
        for key in (cluster,"challenger_score","control_score"):
            if key not in row:
                raise ExperimentError("BOOTSTRAP_MISSING_FIELD")
        if not all(math.isfinite(row[k]) for k in ("challenger_score","control_score")):
            raise ExperimentError("NONFINITE_SCORE")
        blocks[row[cluster]].append(row["challenger_score"]-row["control_score"])
    if len(blocks)<2:
        raise ExperimentError("INSUFFICIENT_GAME_DATE_BLOCKS")
    keys=sorted(blocks)
    rng=np.random.default_rng(seed)
    samples=np.empty(repeats)
    for i in range(repeats):
        picks=rng.choice(len(keys),size=len(keys),replace=True)
        draws=[v for j in picks for v in blocks[keys[j]]]
        samples[i]=float(np.mean(draws))
    return {"estimate":float(np.mean([v for block in blocks.values() for v in block])),
            "interval":[float(np.quantile(samples,lower)),float(np.quantile(samples,upper))],
            "clusters":len(keys),"rows":sum(map(len,blocks.values())),
            "seed":seed,"cluster":cluster,
            "raw_rows_are_not_independent_observations":True}
