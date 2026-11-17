"""P5 cached full-pipeline mixtures and prequential experiment machinery.

No historical fitting is allowed by this initial research package. W2/W3
optimization requires explicitly marked SYNTHETIC fixtures; G2 historical
authorization is intentionally absent. All inputs are complete distributions,
never separately weighted S/O/J mechanism predictions.
"""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import numpy as np
from scipy.optimize import minimize
from .scores import ScoreError, validate_pmf, crps, quantile


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


def _row_date(value, event_start_at=None):
    """Canonical game date is UTC midnight of the event-start UTC day.

    No implicit arena/local-date convention is supported. Check alignment
    BEFORE quarantine; a backdated label is an integrity error in its own right.
    """
    date=_utc(value)
    if date.time()!=datetime.min.time():
        raise ExperimentError("UTC_MIDNIGHT_DATE_REQUIRED")
    if event_start_at is not None and date.date()!=_utc(event_start_at).date():
        raise ExperimentError("INVALID_CHRONOLOGY")
    if date >= datetime(2023,10,1,tzinfo=timezone.utc):
        raise ExperimentError("2023_24_HOLDOUT_QUARANTINED")
    return date


def _identity(value):
    if not isinstance(value,str) or not value.strip() or value!=value.strip():
        raise ExperimentError("INVALID_IDENTITY")
    return value


def _chronology(row):
    for field in ("game_id","player_id","stat","frozen_at","event_start_at",
                  "official_available_at","date"):
        if field not in row:
            raise ExperimentError("MISSING_"+field)
    _identity(row["game_id"])
    _identity(row["player_id"])
    if row["stat"] not in STATS:
        raise ExperimentError("INVALID_STAT")
    freeze=_utc(row["frozen_at"])
    start=_utc(row["event_start_at"])
    released=_utc(row["official_available_at"])
    day=_row_date(row["date"],row["event_start_at"])
    if freeze>=start or released<start:
        raise ExperimentError("INVALID_CHRONOLOGY")
    if "event_end_at" not in row:
        raise ExperimentError("MISSING_event_end_at")
    end=_utc(row["event_end_at"])
    if end<=start or released<end:
        raise ExperimentError("OUTCOME_BEFORE_GAME_END")
    _cutoffs(row,freeze,start)
    return day,freeze,start,released


def _nested_mappings(obj):
    """Walk every dictionary through arbitrary list/tuple nesting.

    Shared substructures are legal. Cycles are not serializable forecast
    evidence and reject explicitly instead of escaping validators by recursion.
    """
    stack=[(obj,frozenset())]
    while stack:
        value,ancestors=stack.pop()
        if not isinstance(value,(dict,list,tuple)):
            continue
        marker=id(value)
        if marker in ancestors:
            raise ExperimentError("CYCLIC_FORECAST_INPUT")
        nested=ancestors|{marker}
        if isinstance(value,dict):
            yield value
            children=value.values()
        else:
            children=value
        stack.extend((child,nested) for child in children
                     if isinstance(child,(dict,list,tuple)))


def _cutoffs(obj, freeze, start):
    # All containers use the same traversal; a list inside a list cannot hide
    # source/model clocks or unsupported timestamps.
    before_freeze={"source_available_at","available_at","published_at",
                   "retrieved_at","ingested_at","input_freeze_at",
                   "decision_cutoff_at","model_training_cutoff_at",
                   "training_cutoff_at","asof_cutoff_utc","cutoff_at"}
    event_clocks={"date","frozen_at","event_start_at","event_end_at",
                  "official_available_at"}
    for mapping in _nested_mappings(obj):
        for key,value in mapping.items():
            if not isinstance(key,str):
                continue  # Integer PMF support is validated separately.
            if key in before_freeze or "cutoff" in key:
                if _utc(value)>freeze:
                    raise ExperimentError("POST_FREEZE_SOURCE_OR_CUTOFF")
            elif key=="forecast_at":
                if not freeze<=_utc(value)<start:
                    raise ExperimentError("INVALID_FORECAST_TIME")
            elif key.endswith("_at") and key not in event_clocks:
                raise ExperimentError("UNSUPPORTED_TIME_FIELD_"+key)


def _linked_fields(obj, row):
    for mapping in _nested_mappings(obj):
        for key,value in mapping.items():
            if key in ("game_id","player_id","stat","date","frozen_at",
                       "event_start_at","event_end_at","official_available_at",
                       "source_profile") and value!=row[key]:
                raise ExperimentError("LINKED_IDENTITY_MISMATCH_"+key)


def _forecast_only(obj):
    forbidden={"actual","actual_stats","official_available_at","event_end_at",
               "actual_minutes","target_game_outcome","target_game_result",
               "target_game_boxscore","target_result","target_outcome",
               "final_roster","final_score"}
    for mapping in _nested_mappings(obj):
        # Prior-game observations use an explicit prior_game_* namespace;
        # projected_* remains legal. Actual/realized target quantities cannot
        # acquire pregame status by renaming their statistic or nesting them.
        if any(isinstance(key,str) and (key in forbidden or
               key.startswith(("actual_","realized_"))) for key in mapping):
            raise ExperimentError("OUTCOME_IN_FORECAST_PIPELINE")


def _synthetic_witness(row):
    """Explicit interface fixture, NOT a source-authenticated historical adapter.

    Require independent event/forecast/source identities; never derive missing
    clocks from the label date or infer game end from a fixed NBA duration.
    """
    for key in ("event_end_at","event_metadata","source_lineage","actual_stats"):
        if key not in row:
            raise ExperimentError("MISSING_"+key)
    event=row["event_metadata"]
    if not isinstance(event,dict):
        raise ExperimentError("INVALID_EVENT_METADATA")
    for key in ("game_id","date","event_start_at","event_end_at","source_profile"):
        if event.get(key)!=row[key]:
            raise ExperimentError("EVENT_METADATA_MISMATCH_"+key)
    start=_utc(event["event_start_at"])
    season_start=start.year if start.month>=10 else start.year-1
    if event.get("season")!=f"{season_start}-{str(season_start+1)[-2:]}":
        raise ExperimentError("EVENT_SEASON_MISMATCH")
    lineage=row["source_lineage"]
    if not isinstance(lineage,list) or not lineage:
        raise ExperimentError("SOURCE_LINEAGE_REQUIRED")
    _linked_fields(row,row)
    sources=set()
    for source in lineage:
        if not isinstance(source,dict):
            raise ExperimentError("INVALID_SOURCE_LINEAGE")
        for key in ("source_id","sha256","source_available_at","retrieved_at"):
            if key not in source:
                raise ExperimentError("MISSING_SOURCE_"+key)
        sid=_identity(source["source_id"])
        sha=source["sha256"]
        if (sid in sources or not isinstance(sha,str) or len(sha)!=64 or
                any(c not in "0123456789abcdef" for c in sha)):
            raise ExperimentError("INVALID_SOURCE_LINEAGE")
        sources.add(sid)
        if _utc(source["source_available_at"])>_utc(source["retrieved_at"]):
            raise ExperimentError("SOURCE_RETRIEVAL_BEFORE_AVAILABILITY")
    counts=row["actual_stats"]
    if not isinstance(counts,dict) or set(counts)!={"points","rebounds","assists","threes"}:
        raise ExperimentError("INVALID_STATISTICAL_WITNESS")
    if any(type(v) is not int or v<0 for v in counts.values()):
        raise ExperimentError("INVALID_STATISTICAL_WITNESS")
    if 3*counts["threes"]>counts["points"]:
        raise ExperimentError("INVALID_POINT_ACCOUNTING")
    combinations={"pr":("points","rebounds"),"pa":("points","assists"),
                  "ra":("rebounds","assists"),"pra":("points","rebounds","assists")}
    expected=(sum(counts[k] for k in combinations[row["stat"]])
              if row["stat"] in combinations else counts[row["stat"]])
    if row["actual"]!=expected:
        raise ExperimentError("OUTCOME_STAT_IDENTITY_MISMATCH")
    return sources


def make_walk_forward_folds(rows, *, min_train_dates=3, test_dates=1,
                            embargo_days=0):
    """Metadata-only folds; observations are NEVER fetched by this function.

    Training label release must strictly precede the earliest test freeze.
    Game/date all stay together even if many players/props share that cluster.
    """
    rows=deepcopy(list(rows))
    if not rows or min_train_dates<1 or test_dates<1 or embargo_days<0:
        raise ExperimentError("BAD_FOLD_CONFIG")
    grouped=defaultdict(list)
    seen=set()
    games={}
    for row in rows:
        d,freeze,start,released=_chronology(row)
        if "event_metadata" in row:
            event=row["event_metadata"]
            for field in ("game_id","date","event_start_at","event_end_at"):
                if event.get(field)!=row.get(field):
                    raise ExperimentError("EVENT_METADATA_MISMATCH_"+field)
        event=(d,start,_utc(row["event_end_at"]))
        if row["game_id"] in games and games[row["game_id"]]!=event:
            raise ExperimentError("INCONSISTENT_GAME_METADATA")
        games[row["game_id"]]=event
        key=(row["game_id"],row["player_id"],row["stat"])
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
        rows=deepcopy(list(rows))
        if not rows:
            raise ExperimentError("EMPTY_COHORT")
        if not isinstance(rows[0].get("pipelines"),dict):
            raise ExperimentError("INVALID_PIPELINES")
        self.pipeline_ids=tuple(sorted(rows[0]["pipelines"]))
        for name in self.pipeline_ids:
            _identity(name)
        if not self.pipeline_ids or len(self.pipeline_ids)!=len(set(self.pipeline_ids)):
            raise ExperimentError("INVALID_PIPELINES")
        self.rows=rows
        seen=set()
        support=0
        modes={}
        games={}
        for row in rows:
            if row.get("source_profile")!="SYNTHETIC":
                raise ExperimentError("ONLY_SYNTHETIC_FITTING")
            # Quarantine each forecast tree before checking linked outcome
            # witnesses; forbidden forecast keys retain one precise reason.
            if isinstance(row.get("pipelines"),dict):
                for pipeline in row["pipelines"].values():
                    _forecast_only(pipeline)
            day,freeze,start,released=_chronology(row)
            if type(row.get("actual")) is not int or row["actual"]<0:
                raise ExperimentError("INVALID_OUTCOME_OR_STAT")
            sources=_synthetic_witness(row)
            if not isinstance(row.get("pipelines"),dict) or set(row["pipelines"])!=set(self.pipeline_ids):
                raise ExperimentError("INCOMPLETE_MATCHED_PIPELINES")
            ident=(row["game_id"],row["player_id"],row["stat"])
            if ident in seen:
                raise ExperimentError("DUPLICATE_MATCHED_CASE")
            seen.add(ident)
            event=(day,start,_utc(row["event_end_at"]),row["event_metadata"])
            if row["game_id"] in games and games[row["game_id"]]!=event:
                raise ExperimentError("INCONSISTENT_GAME_METADATA")
            games[row["game_id"]]=event
            support=max(support,row["actual"])
            for name,item in row["pipelines"].items():
                if not isinstance(item,dict):
                    raise ExperimentError("INVALID_PIPELINE")
                for field in ("game_id","player_id","stat","date","frozen_at",
                              "event_start_at","source_profile"):
                    if item.get(field)!=row[field]:
                        raise ExperimentError("PIPELINE_IDENTITY_MISMATCH_"+field)
                if item.get("pipeline_id")!=name:
                    raise ExperimentError("PIPELINE_IDENTITY_MISMATCH")
                if (not isinstance(item.get("source_ids"),list) or
                        set(item["source_ids"])!=sources or
                        len(item["source_ids"])!=len(sources)):
                    raise ExperimentError("PIPELINE_SOURCE_LINEAGE_MISMATCH")
                for clock in ("forecast_at","model_training_cutoff_at"):
                    if clock not in item:
                        raise ExperimentError("MISSING_PIPELINE_"+clock)
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
    if lam<0 or not math.isfinite(lam):
        raise ExperimentError("INVALID_REGULARIZATION")
    # Validate even rare-stat fallback; it must never bypass entry guards.
    validated=CachedCohort(rows,authorization="SYNTHETIC_UNIT_TEST")
    if set(global_weights)!=set(validated.pipeline_ids):
        raise ExperimentError("GLOBAL_ANCHOR_MISMATCH")
    validated._weights([global_weights[k] for k in validated.pipeline_ids])
    by_stat=defaultdict(list)
    for row in validated.rows:
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


def mc_precision_probe(pmf, *, seed=20261116, n_small=5000, n_large=20000, outcome=0, tail_threshold=None):
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
    small_pmf=dict(zip(values.tolist(),p5.tolist()))
    large_pmf=dict(zip(values.tolist(),p20.tolist()))
    true_pmf=dict(rows)
    tail_threshold=max(values) if tail_threshold is None else tail_threshold
    def diag(distribution):
        return {"crps":crps(distribution,outcome),
                "mean":sum(k*p for k,p in distribution.items()),
                "zero_mass":distribution.get(0,0.0),
                "upper_tail_mass":sum(p for k,p in distribution.items()
                                      if k>=tail_threshold),
                "median":quantile(distribution,.5)}
    exact=diag(true_pmf)
    five=diag(small_pmf)
    twenty=diag(large_pmf)
    return {"seed":seed,"counts":[n_small,n_large],
            "probabilities_5000":small_pmf,
            "probabilities_20000":large_pmf,
            "exact_reference":exact,
            "estimates_5000":five,"estimates_20000":twenty,
            "absolute_crps_error_5000":abs(five["crps"]-exact["crps"]),
            "absolute_crps_error_20000":abs(twenty["crps"]-exact["crps"]),
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
