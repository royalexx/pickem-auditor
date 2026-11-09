"""Team-level XGBoost opportunity forecasts, fit/tuned ONLY before 2024.

Input: pre-2024 nflverse PBP aggregates plus NGS team player-week metrics.
Output: pass and rush opportunities with held-out estimated overdispersion.
Player targets/yardage are NOT direct XGB training labels. The model is frozen
for the entire 2024 test, including its Optuna TPE hyperparameters.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
import math
import numpy as np

VERSION="team_pbp_ngs_xgboost_pre2024_v1"
CUTOFF=date(2024,1,1)
TARGETS=("pass_attempts","rush_attempts")
FEATURES=(
    "team_pass_last5","team_pass_last17","defense_pass_last5","defense_pass_last17",
    "team_rush_last5","team_rush_last17","defense_rush_last5","defense_rush_last17",
    "team_short_pass_last5","defense_short_pass_last5",
    "team_rb_targets_last5","defense_rb_targets_last5",
    "team_neutral_pass_last5","defense_neutral_pass_last5",
    "team_sack_rate_last5","defense_sack_rate_last5",
    "team_ngs_qb_cpoe","team_ngs_qb_air",
    "team_ngs_wr_separation","team_ngs_rb_ryoe",
    "home","week","team_observed_games","defense_observed_games",
)
FALLBACK={
  "pass_attempts":33.,"rush_attempts":26.,
  "short_pass_attempts":10.,"rb_targets":5.,
  "neutral_passes":15.,"sacks":2.,"dropbacks":35.,
  "qb_cpoe":0.,"qb_air":8.,"wr_sep":2.9,"rb_ryoe":0.
}
SEED=20261109

def _day(day):
    return date.fromisoformat(str(day)[:10])

def _avg(rows,key,asof,limit,half_life=112.,default=0.):
    older=sorted((r for r in rows if _day(r["gameday"])<asof),
                  key=lambda r:r["gameday"],reverse=True)[:limit]
    if not older:return float(default),0
    pairs=[]
    for r in older:
        try:value=float(r.get(key,0.))
        except (ValueError,TypeError):continue
        if not math.isfinite(value):continue
        age=(asof-_day(r["gameday"])).days
        pairs.append((value,2.**(-age/half_life)))
    if not pairs:return float(default),0
    total=sum(w for _,w in pairs)
    return sum(x*w for x,w in pairs)/total,len(pairs)

def build_index(team_game_rows,ngs_rows):
    """Indexed 2021–23 histories. Every timestamp checked before indexing."""
    offense=defaultdict(list);defense=defaultdict(list)
    for r in team_game_rows:
        d=_day(r["gameday"])
        if d>=CUTOFF or int(r["season"])>=2024:
            raise ValueError("2024_team_game_entered_training")
        t=str(r["team"]);o=str(r["opponent"])
        if t==o:raise ValueError("same_team_opponent")
        offense[t].append(r)
        defense[o].append(r)
    ngs=defaultdict(list)
    fields={"passing":[("completion_percentage_above_expectation","qb_cpoe"),
                       ("avg_intended_air_yards","qb_air")],
            "receiving":[("avg_separation","wr_sep")],
            "rushing":[("rush_yards_over_expected_per_att","rb_ryoe")]}
    for kind,rows in ngs_rows.items():
        if kind not in fields:raise ValueError("unregistered_ngs_kind")
        by_team_game=defaultdict(lambda:defaultdict(list))
        for r in rows:
            d=_day(r["gameday"])
            if d>=CUTOFF or int(r["season"])>=2024:
                raise ValueError("2024_ngs_entered_team_training")
            group=by_team_game[(r["team"],r["gameday"])]
            for source,label in fields[kind]:
                value=r.get(source)
                if value is None:continue
                try:num=float(value)
                except (TypeError,ValueError):continue
                if math.isfinite(num):group[label].append(num)
        for (team,day),metrics in by_team_game.items():
            record={"gameday":day}
            for k,values in metrics.items():record[k]=sum(values)/len(values)
            ngs[str(team)].append(record)
    for group in (offense,defense,ngs):
        for key in group:
            group[key].sort(key=lambda r:r["gameday"])
    return dict(offense=offense,defense=defense,ngs=ngs)

def features(index,team,opponent,*,asof,home,week):
    day=_day(asof)
    if day>CUTOFF:raise ValueError("2024_observation_as_features_forbidden")
    if team==opponent:raise ValueError("same_team_opponent")
    own=index["offense"].get(team,())
    allowed=index["defense"].get(opponent,())
    qs=[]
    for metric in ("pass_attempts","rush_attempts"):
        for z,limit in ((own,5),(own,17),(allowed,5),(allowed,17)):
            val,n=_avg(z,metric,day,limit,default=FALLBACK[metric])
            # Shrink sparse team records to a historical league prior.
            qs.append((val*n+FALLBACK[metric]*3.)/(n+3.))
    for metric in ("short_pass_attempts","rb_targets","neutral_passes"):
        for z in (own,allowed):
            val,n=_avg(z,metric,day,5,default=FALLBACK[metric])
            qs.append((val*n+FALLBACK[metric]*3.)/(n+3.))
    for z in (own,allowed):
        sack,n=_avg(z,"sacks",day,5,default=FALLBACK["sacks"])
        drop,_=_avg(z,"dropbacks",day,5,default=FALLBACK["dropbacks"])
        qs.append(sack/max(1.,drop))
    for metric in ("qb_cpoe","qb_air","wr_sep","rb_ryoe"):
        val,n=_avg(index["ngs"].get(team,()),metric,day,5,default=FALLBACK[metric])
        qs.append((val*n+FALLBACK[metric]*3.)/(n+3.))
    games=sum(_day(r["gameday"])<day for r in own)
    dgames=sum(_day(r["gameday"])<day for r in allowed)
    qs.extend((float(home),float(week),float(min(games,30)),float(min(dgames,30))))
    if len(qs)!=len(FEATURES) or not all(math.isfinite(x) for x in qs):
        raise ValueError("team_feature_registry_invalid")
    return np.asarray(qs,dtype=np.float32)

def training_rows(team_games,index):
    grouped={m:[] for m in TARGETS}
    for r in sorted(team_games,key=lambda x:(x["gameday"],x["game_id"],x["team"])):
        day=_day(r["gameday"])
        if day>=CUTOFF:raise ValueError("future_team_training_label")
        # The PBP team-game aggregate does not carry home; the canonical
        # nflverse game ID ends in the true home team abbreviation.
        home_team=str(r["game_id"]).split("_")[-1]
        if home_team not in (r["team"],r["opponent"]):
            raise ValueError("malformed_game_home_team")
        x=features(index,r["team"],r["opponent"],asof=day,
                   home=(r["team"]==home_team),week=int(r["week"]))
        for market in TARGETS:
            val=float(r.get(market,0.))
            if not math.isfinite(val) or val<0:raise ValueError("invalid_team_volume_label")
            grouped[market].append(dict(day=day.isoformat(),game_id=r["game_id"],
              team=r["team"],opponent=r["opponent"],x=x.tolist(),y=val))
    return grouped

def _folds(rows):
    day=np.asarray([_day(r["day"]) for r in rows])
    folds=[]
    for start,end in (("2022-10-01","2022-12-15"),
                      ("2023-09-15","2023-11-01"),
                      ("2023-11-01","2024-01-01")):
        a=_day(start);b=_day(end)
        tr=np.where(day<a)[0];va=np.where((day>=a)&(day<b))[0]
        if len(tr)>=200 and len(va)>=50:
            if max(day[tr])>=min(day[va]):raise ValueError("fold_leakage")
            folds.append((tr,va))
    return folds

def _params(trial):
    return dict(n_estimators=trial.suggest_int("n_estimators",100,250,step=50),
       max_depth=trial.suggest_int("max_depth",2,4),
       learning_rate=trial.suggest_float("learning_rate",.025,.13,log=True),
       subsample=trial.suggest_float("subsample",.75,1.),
       colsample_bytree=trial.suggest_float("colsample_bytree",.75,1.),
       min_child_weight=trial.suggest_int("min_child_weight",4,16),
       reg_lambda=trial.suggest_float("reg_lambda",1.,20.,log=True),
       reg_alpha=trial.suggest_float("reg_alpha",.001,2.,log=True))

def _model(params):
    from xgboost import XGBRegressor
    return XGBRegressor(objective="count:poisson",tree_method="hist",
       random_state=SEED,n_jobs=2,verbosity=0,**params)

def train(team_games,index,*,trials=8):
    """Chronological Optuna TPE. Dispersion calibrated with pre-2024 OOF."""
    import optuna
    if not 1<=trials<=100:raise ValueError("invalid_search_budget")
    rows=training_rows(team_games,index)
    fitted={};receipts={}
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    for market in TARGETS:
        data=rows[market]
        folds=_folds(data)
        if len(folds)<2:raise ValueError("insufficient_pre2024_team_cv")
        X=np.asarray([r["x"] for r in data],dtype=np.float32)
        y=np.asarray([r["y"] for r in data],dtype=np.float32)
        def objective(trial):
            p=_params(trial);losses=[]
            for tr,va in folds:
                mdl=_model(p);mdl.fit(X[tr],y[tr])
                pred=np.maximum(1.e-6,mdl.predict(X[va]))
                # Poisson deviance rewards honest means and avoids directional gaming.
                losses.append(float(np.mean(2*(pred-y[va]+np.where(y[va]>0,
                    y[va]*np.log(np.maximum(y[va],1e-6)/pred),0.)))))
            return float(np.mean(losses))
        study=optuna.create_study(direction="minimize",
            sampler=optuna.samplers.TPESampler(seed=SEED,n_startup_trials=min(4,trials)))
        study.optimize(objective,n_trials=trials,n_jobs=1,show_progress_bar=False)
        params=study.best_params
        # Out-of-fold uncertainty estimate, no in-sample residual substitution.
        actual=[];predicted=[]
        for tr,va in folds:
            mdl=_model(params);mdl.fit(X[tr],y[tr])
            actual.extend(y[va].astype(float).tolist())
            predicted.extend(np.maximum(.01,mdl.predict(X[va])).astype(float).tolist())
        a=np.asarray(actual);p=np.asarray(predicted)
        extra=float(np.mean((a-p)**2-np.maximum(0.,p)))
        k=float(max(3.,min(150.,np.mean(p)**2/max(1.,extra))))
        mdl=_model(params);mdl.fit(X,y)
        fitted[market]=mdl
        receipts[market]={"train_rows":len(data),"optuna_trials":len(study.trials),
         "cv_score":float(study.best_value),"dispersion":k,
         "cv_n":len(a),"best_params":params,
         "cv_first_day":min(data[int(va[0])]["day"] for _,va in folds),
         "cv_latest_day":max(data[int(va[-1])]["day"] for _,va in folds),
         "fitted_2024_training_records":0}
    return fitted,receipts

def project(fitted,index,team,opponent,*,home,week):
    x=features(index,team,opponent,asof=CUTOFF.isoformat(),home=home,week=week)
    forecasts={m:max(0.5,float(fitted[m].predict(x.reshape(1,-1))[0]))
               for m in TARGETS}
    if any(not math.isfinite(v) for v in forecasts.values()):
        raise ValueError("nonfinite_team_xgb_forecast")
    return forecasts
