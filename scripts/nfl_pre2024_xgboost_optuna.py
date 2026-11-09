"""Optuna TPE/XGBoost NFL opportunity challenger — STRICT PRE-2024 FIT.

All training features, hyperparameter trials, validation fold labels, fitted
weights, calibration and fallback decisions must be dated before 2024-01-01.
The first data from 2024 is the GAME SCHEDULE, used to assemble a frozen
forecast ledger. 2024 player stats may be read ONLY after every forecast is
locked for evaluation; never make a later 2024 forecast adaptive.

FTN is supported upstream but excluded from this replay: observed pulled
timestamp 2024-09-06 exceeds training cutoff. NGS and PBP season records
2021-23 are admitted only for game dates before Jan 1, 2024.

No production model, ranking or engine-credibility weights are changed.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib,json,math
from pathlib import Path

import numpy as np
from nfl_pre2024_pbp_ngs_sources import CUTOFF
import nfl_pre2024_team_defense_challenger as baseline

VERSION="nfl-pre2024-xgboost-tpe-team-defense-v1"
TRAINING_SEASONS=frozenset((2021,2022,2023))
MARKETS=tuple(baseline.VOLUME_MARKETS)
SEED=20261109
FEATURES=(
    "player_last5_mean","player_last5_weight","role_prior",
    "player_last5_n","player_prior_mean","days_since_last_play",
    "recent_snap_exposure","position_code",
    "team_expected_opportunities","team_offense_ratio",
    "opponent_allowed_opportunities","opponent_allowed_ratio",
    "team_matchup_factor","team_eff_games","opponent_eff_games",
    "short_pass_matchup","rb_short_target_matchup","neutral_pass_matchup",
    "qb_aimed_air_yards","qb_completion_over_expected","qb_time_to_throw",
    "wr_cushion","wr_separation","wr_air_yard_share",
    "rb_rush_over_expectation","rb_box_defenders",
    "ngs_available","year_sin","year_cos"
)
POSITION_CODES={name:i for i,name in enumerate(sorted({p for opts in baseline.ROLE_POS.values() for p in opts}))}
COUNTS=frozenset(baseline.COUNT_MARKETS)

def sha_json(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),
                       allow_nan=False).encode()).hexdigest()

def _cutoff(row):
    day=date.fromisoformat(str(row["game_date"])[:10])
    if day>=CUTOFF:raise ValueError("2024_plus_training_label_forbidden")
    if int(row["season"]) not in TRAINING_SEASONS:
        raise ValueError("forbidden_training_season")
    return day

def _series(state,key,asof,*,source,metric,half=84,limit=8):
    records=state[source].get(key,())
    rows=sorted((r for r in records if date.fromisoformat(str(r.get("gameday") or r.get("game_date"))[:10])<asof),
       key=lambda r:str(r.get("gameday") or r.get("game_date")),reverse=True)[:limit]
    v=[]
    for r in rows:
        x=r.get(metric)
        try:x=float(x)
        except (ValueError,TypeError):continue
        if not math.isfinite(x):continue
        age=(asof-date.fromisoformat(str(r.get("gameday") or r.get("game_date"))[:10])).days
        v.append((x,2**(-age/half)))
    if not v:return np.nan
    return float(sum(x*w for x,w in v)/sum(w for _,w in v))

def make_feature(state,*,stat,player_id,position,team,opponent,asof):
    day=date.fromisoformat(str(asof))
    if day>CUTOFF:raise ValueError("cannot_consume_2024_plus_model_features")
    if stat not in MARKETS or position not in baseline.ROLE_POS[stat]:
        return None
    prior,evidence=baseline.player_rate(state,stat,str(player_id),
                                          position,team,day)
    if prior is None:return None
    history=sorted((r for r in state["player"].get((stat,str(player_id)),())
              if date.fromisoformat(r["gameday"])<day and r["team"]==team),
              key=lambda r:r["gameday"],reverse=True)
    if not history:return None
    last5=history[:5]
    baseline_mean=evidence["player_recent_mean"]
    role=evidence["role_prior"]
    age=(day-date.fromisoformat(last5[0]["gameday"])).days
    metric=baseline.MARKET_TEAM_METRIC[stat]
    at=opponent if "tackle" in stat else team
    dt=team if "tackle" in stat else opponent
    teamfactor,meta=baseline.team_metric_ratio(state,metric,at,dt,day)
    short,_=baseline.team_metric_ratio(state,"short_pass_attempts",at,dt,day)
    rb_short,_=baseline.team_metric_ratio(state,"short_rb_targets",at,dt,day)
    neutral,_=baseline.team_metric_ratio(state,"neutral_passes",at,dt,day)
    own=_series(state,(metric,at),day,source="team_offense",metric="value",half=120,limit=25)
    allowed=_series(state,(metric,dt),day,source="opponent_allowed",metric="value",half=120,limit=25)
    prev=_series(state,(stat,str(player_id)),day,source="player",metric="value",half=365,limit=10)
    ngfields=[
        ("passing","avg_intended_air_yards"),
        ("passing","completion_percentage_above_expectation"),
        ("passing","avg_time_to_throw"),
        ("receiving","avg_cushion"),
        ("receiving","avg_separation"),
        ("receiving","percent_share_of_intended_air_yards"),
        ("rushing","rush_yards_over_expected_per_att"),
        ("rushing","percent_attempts_gte_eight_defenders"),
    ]
    ng=[_series(state,(kind,str(player_id)),day,source="ngs",metric=k,half=90,limit=5)
        for kind,k in ngfields]
    ret=[
        float(baseline_mean),float(evidence["player_recent_weight"]),
        float(role),float(len(last5)),float(prev),float(age),
        float(_series(state,(stat,str(player_id)),day,
               source="player",metric="workload",half=35,limit=5)),
        float(POSITION_CODES[position]),float(own),float(meta.get("own_ratio",1)),
        float(allowed),float(meta.get("opponent_allowed_ratio",1)),
        float(teamfactor),float(meta.get("team_effective_games",0)),
        float(meta.get("opponent_effective_games",0)),float(short),
        float(rb_short),float(neutral),
        *ng,float(any(math.isfinite(x) for x in ng)),
        math.sin(2*math.pi*day.timetuple().tm_yday/365.),
        math.cos(2*math.pi*day.timetuple().tm_yday/365.)
    ]
    if len(ret)!=len(FEATURES):raise ValueError("feature_registry_mismatch")
    if any(math.isinf(x) for x in ret):raise ValueError("nonfinite_training_feature")
    return ret

def make_training_rows(state,player_rows):
    grouped={m:[] for m in MARKETS}
    keys=set()
    for r in sorted(player_rows,key=lambda x:(x["game_date"],x["game_id"],x["player_id"],x["stat"])):
        day=_cutoff(r)
        m=r["stat"]
        if m not in MARKETS or r["position"] not in baseline.ROLE_POS[m]:continue
        key=(r["game_id"],r["player_id"],m)
        if key in keys:raise ValueError("duplicate_train_player_game_market")
        keys.add(key)
        row=make_feature(state,stat=m,player_id=r["player_id"],
            position=r["position"],team=r["team"],opponent=r["opponent"],
            asof=r["game_date"])
        if row is None:continue
        y=float(r["value"])
        if not math.isfinite(y):raise ValueError("nonfinite_training_label")
        if m in COUNTS and (y<0 or not y.is_integer()):
            raise ValueError("invalid_count_label")
        grouped[m].append(dict(date=r["game_date"],year=int(r["season"]),
            week=int(r.get("week",0)),game_id=r["game_id"],player_id=r["player_id"],
            x=row,y=y,position=r["position"]))
    return grouped

def validation_folds(data):
    # Calendar-defined expanding windows, NEVER random shuffle.
    d=np.asarray([date.fromisoformat(x["date"]) for x in data])
    boundaries=(("2022-10-01","2022-12-15"),
                ("2023-09-15","2023-11-01"),
                ("2023-11-01","2024-01-01"))
    folds=[]
    for start,end in boundaries:
        start=date.fromisoformat(start);end=date.fromisoformat(end)
        train=np.flatnonzero(d<start)
        valid=np.flatnonzero((d>=start)&(d<end))
        if len(train)>=100 and len(valid)>=30:
            if max(d[train])>=min(d[valid]):raise ValueError("training_validation_leak")
            folds.append((train,valid))
    return folds

def _likelihood(y,means,market):
    from scipy.stats import nbinom,t
    means=np.maximum(1e-4,np.asarray(means,dtype=float))
    y=np.asarray(y,dtype=float)
    if market in COUNTS:
        k=baseline.COUNT_DISPERSION[market]
        return -np.log(np.maximum(1.e-16,
            nbinom.pmf(y,k,k/(k+means))))
    return -t.logpdf((y-means)/baseline.YARD_SCALE[market],df=5)+math.log(baseline.YARD_SCALE[market])

def _model(params,market):
    import xgboost as xgb
    obj="count:poisson" if market in COUNTS else "reg:squarederror"
    return xgb.XGBRegressor(objective=obj,tree_method="hist",
       random_state=SEED,n_jobs=2,verbosity=0,
       **params)

def _suggest_params(trial):
    return dict(
      n_estimators=trial.suggest_int("n_estimators",90,250,step=40),
      max_depth=trial.suggest_int("max_depth",2,4),
      learning_rate=trial.suggest_float("learning_rate",.025,.14,log=True),
      subsample=trial.suggest_float("subsample",.72,1.),
      colsample_bytree=trial.suggest_float("colsample_bytree",.72,1.),
      min_child_weight=trial.suggest_int("min_child_weight",3,18),
      reg_lambda=trial.suggest_float("reg_lambda",1.,20.,log=True),
      reg_alpha=trial.suggest_float("reg_alpha",1e-3,2.,log=True),
      gamma=trial.suggest_float("gamma",0.,2.),
      max_bin=128)

def fit_one_market(rows,market,*,trials=8):
    import optuna
    if not 1<=trials<=100:raise ValueError("unbounded_bayesian_search")
    n=len(rows);folds=validation_folds(rows)
    if n<250 or len(folds)<2:
        return None,dict(status="insufficient_chronological_data",rows=n,folds=len(folds))
    X=np.asarray([r["x"] for r in rows],dtype=np.float32)
    y=np.asarray([r["y"] for r in rows],dtype=np.float32)
    if not np.isfinite(y).all():raise ValueError("nonfinite_targets")
    if market in COUNTS and np.any(y<0):raise ValueError("negative_count")
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    trial_scores=[]
    def objective(trial):
        p=_suggest_params(trial)
        foldloss=[]
        for tr,va in folds:
            model=_model(p,market)
            model.fit(X[tr],y[tr])
            preds=model.predict(X[va])
            if not np.isfinite(preds).all():return 1.e9
            scores=_likelihood(y[va],preds,market)
            foldloss.append(float(np.mean(scores)))
        result=float(np.mean(foldloss))
        trial_scores.append(result)
        return result
    sampler=optuna.samplers.TPESampler(seed=SEED,n_startup_trials=min(4,trials))
    study=optuna.create_study(direction="minimize",sampler=sampler)
    study.optimize(objective,n_trials=trials,n_jobs=1,show_progress_bar=False)
    params=dict(study.best_params,max_bin=128)
    fitted=_model(params,market)
    fitted.fit(X,y)
    return fitted,dict(status="fitted_pre2024_only",
       rows=n,n_trials=len(study.trials),folds=[
        {"train":len(tr),"validation":len(va),
         "latest_train_day":rows[tr[-1]]["date"],
         "first_validation_day":rows[va[0]]["date"]} for tr,va in folds],
       best_params=params,best_cv_negative_loglik=float(study.best_value),
       feature_importances=dict(zip(FEATURES,fitted.feature_importances_.astype(float).tolist())))

def predict_market(model,state,market,player_id,position,team,opponent,*,variant="xgboost_pbp_ngs"):
    x=make_feature(state,stat=market,player_id=player_id,
                   position=position,team=team,opponent=opponent,
                   asof="2024-01-01")
    if x is None:return None
    if model is None:return None
    # XGB predictions are allowed only with previously fitted, frozen trees.
    pred=float(model.predict(np.asarray([x],dtype=np.float32))[0])
    if not math.isfinite(pred):return None
    return max(0.,pred)
