"""Strict pre-2024 NFL count hurdle challenger.

Zero/positive classifier learned with chronological XGBoost CV (Optuna TPE).
Predictions refer to a player who was observed to log genuine prior snaps,
NOT verified pregame active status or sportsbook-eligible contracts.

A hurdle is only useful for nonnegative INTEGER markets: rushing/receiving
yardage can be negative, so this code excludes all yard markets.
The joint Monte Carlo applies the zero gate BEFORE allocating team total
opportunities, preventing two independent zeros from being double counted.

Features include observed 3-vs-prior-3-game *snaps* (not invented routes),
recent count zero streak, offense/defense team context, and missingness flags
for participation/personnel/injury records. Never turn missing records into
an assumed active/healthy/limited player. No 2024 observations admitted.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import math,numbers
import numpy as np

CUTOFF=date(2024,1,1)
SEED=20261109
ELIGIBLE_MARKETS=frozenset((
    "targets","carries","tackles + assists",
))
FEATURES=(
    "market_category","position_code",
    "played_prior_games","zero_streak","positive_share_last3",
    "positive_share_last5","value_mean_last3","value_mean_last5",
    "recent_snap_mean3","previous_snap_mean3",
    "snap_drop_fraction","snap_trend_present",
    "team_pass_opportunities","opponent_allowed_pass",
    "team_rush_opportunities","opponent_allowed_rush",
    "team_context_available",
    "opponent_eleven_personnel","eleven_personnel_verified",
    "defense_on_eleven_share","defense_on_eleven_verified",
    "injury_status_code","injury_status_verified",
    "report_practice_limited","report_practice_verified"
)
_POSITIONS=("QB","RB","WR","TE","LB","MLB","OLB","ILB","DE","DT",
 "NT","CB","DB","S","FS","SS")
_MARKETS=tuple(sorted(ELIGIBLE_MARKETS))
MAX_ZERO_PROB=.95
MIN_ZERO_PROB=.005
MIN_TRAIN_ROWS=1000
MIN_FOLD_ROWS=150

def _day(x):
    return date.fromisoformat(str(x)[:10])

def _pre2024_date(x):
    result=_day(x)
    if result>=CUTOFF:
        raise ValueError("2024_plus_hurdle_training_feature_or_label")
    return result

def _recent(history,asof,limit=6):
    if not isinstance(asof,date):asof=_day(asof)
    seen=[]
    for row in history:
        day=_day(row.get("gameday") or row.get("game_date"))
        if day>=asof:continue
        if day>=CUTOFF:raise ValueError("2024_plus_hurdle_history")
        val=float(row.get("value",0))
        exposure=float(row.get("workload",0))
        if not all(map(math.isfinite,(val,exposure))):
            raise ValueError("invalid_zero_history_values")
        if exposure<=0:continue  # No appearance = not a played-game zero.
        seen.append(row)
    return sorted(seen,key=lambda r:str(r.get("gameday") or r.get("game_date")),
                  reverse=True)[:limit]

def _mean(arr):
    return sum(arr)/len(arr) if arr else float("nan")

def _trend_from_history(history):
    if len(history)<6:return (float("nan"),float("nan"),float("nan"),0.)
    recent=[float(x["workload"]) for x in history[:3]]
    prior=[float(x["workload"]) for x in history[3:6]]
    r=_mean(recent);p=_mean(prior)
    return (r,p,(r-p)/max(1.,p),1.)

def _team_context(state,market,team,opp,asof):
    buckets=state.get("team_offense",{});defense=state.get("opponent_allowed",{})
    values=[]
    for stat,records in (("pass_attempts",buckets.get(("pass_attempts",team),())),
      ("pass_attempts",defense.get(("pass_attempts",opp),())),
      ("rush_attempts",buckets.get(("rush_attempts",team),())),
      ("rush_attempts",defense.get(("rush_attempts",opp),()))):
        valid=[r for r in records if _day(r.get("gameday"))<asof]
        valid.sort(key=lambda r:r["gameday"],reverse=True)
        vals=[float(r.get("value",0)) for r in valid[:5]]
        values.append(_mean(vals))
    return values+[float(all(math.isfinite(x) for x in values))]

def asof_features(state,*,market,player_id,position,team,opponent,
                  asof,personnel=None,injury=None):
    day=_day(asof)
    if day>CUTOFF:raise ValueError("2024_hurdle_feature_date_forbidden")
    if market not in ELIGIBLE_MARKETS or position not in _POSITIONS:
        return None
    if injury is not None and injury.get("injury_report_asof"):
        if _day(injury["injury_report_asof"])>=day:
            raise ValueError("postevent_injury_report_leakage")
        _pre2024_date(injury["injury_report_asof"])
    pid=str(player_id)
    h=_recent(state["player"].get((market,pid),()),day)
    if len(h)<3:return None
    vals=[float(x["value"]) for x in h]
    if any(x<0 or not x.is_integer() for x in vals):
        raise ValueError("hurdle_requires_nonnegative_integer_outcomes")
    recent_pos=[int(v>0) for v in vals]
    zero_streak=0
    for p in recent_pos:
        if p:break
        zero_streak+=1
    snap3,snap6,drop,snap_yes=_trend_from_history(h)
    ctx=_team_context(state,market,team,opponent,day)
    pdata=personnel or {}
    eleven=pdata.get("opponent_11_personnel_rate")
    defeleven=pdata.get("defender_11_snap_share")
    if eleven is not None and not 0<=float(eleven)<=1:
        raise ValueError("invalid_opponent_11_personnel")
    if defeleven is not None and not 0<=float(defeleven)<=1:
        raise ValueError("invalid_defender_11_usage")
    status=(injury or {}).get("report_status")
    status_code={"OUT":-3,"DOUBTFUL":-2,"QUESTIONABLE":-1,
                 "PROBABLE":0,"":0,None:0}.get(status,0)
    limited=(injury or {}).get("practice_status")
    practice_limit=float(str(limited or "").upper() in ("LIMITED",
         "DID NOT PARTICIPATE","DNP"))
    features=[
        float(_MARKETS.index(market)),float(_POSITIONS.index(position)),
        float(len(h)),float(zero_streak),
        _mean(recent_pos[:3]),_mean(recent_pos[:5]),
        _mean(vals[:3]),_mean(vals[:5]),
        snap3,snap6,drop,snap_yes,*ctx,
        float(eleven) if eleven is not None else float("nan"),
        float(eleven is not None),
        float(defeleven) if defeleven is not None else float("nan"),
        float(defeleven is not None),
        float(status_code),float(status is not None),
        practice_limit,float(limited is not None)]
    if len(features)!=len(FEATURES):
        raise RuntimeError("hurdle_feature_registry_mismatch")
    return np.asarray(features,dtype=np.float32)

def build_pre2024_appearance_cases(player_market_rows,*,state=None,
                                   pregame_injury=None,pregame_personnel=None):
    """Build train labels with only PRIOR game history, never target game stats.

    A player who has no authenticated appearance is not a 'zero'. The caller
    must supply observed normalized market rows joined to real historical
    playing snaps; do not invent unobserved zero games.
    """
    if state is None:
        state={"player":defaultdict(list),
               "team_offense":defaultdict(list),
               "opponent_allowed":defaultdict(list)}
    else:
        # Caller may supply training-era offense context; no 2024 allowed.
        state={"player":defaultdict(list),
               "team_offense":state.get("team_offense",{}),
               "opponent_allowed":state.get("opponent_allowed",{})}
    cases=[]
    keyed=set()
    daily=defaultdict(list)
    for row in player_market_rows:
        day=_pre2024_date(row["game_date"])
        if int(row["season"])>=2024:raise ValueError("2024_plus_hurdle_label")
        if row["stat"] not in ELIGIBLE_MARKETS:continue
        if float(row.get("workload",0))<=0:continue
        value=float(row["value"])
        if value<0 or not value.is_integer():
            raise ValueError("hurdle_requires_nonnegative_integer_label")
        k=(row["game_id"],str(row["player_id"]),row["stat"])
        if k in keyed:raise ValueError("duplicate_hurdle_player_game")
        keyed.add(k)
        daily[day].append(row)
    for day in sorted(daily):
        # Resolve all same-day candidates against yesterday's state.
        for r in daily[day]:
            m=r["stat"];pid=str(r["player_id"])
            k=(int(r["season"]),int(r.get("week",0)),str(r["team"]),pid)
            injury=(pregame_injury or {}).get(k)
            personnel=(pregame_personnel or {}).get(
                 (r["game_id"],str(r["opponent"]),pid))
            X=asof_features(state,market=m,player_id=pid,
               position=r["position"],team=r["team"],
               opponent=r["opponent"],asof=day,
               personnel=personnel,injury=injury)
            if X is not None:
                cases.append({"date":day.isoformat(),
                   "game_id":r["game_id"],"player_id":pid,
                   "market":m,"position":r["position"],
                   "x":X,"positive":int(float(r["value"])>0)})
        for r in daily[day]:
            state["player"][(r["stat"],str(r["player_id"]))].append(
                {"gameday":day.isoformat(),"value":float(r["value"]),
                 "workload":float(r["workload"]),"season":int(r["season"]),
                 "position":r["position"],"team":r["team"]})
    return cases

def _cv_folds(rows):
    dat=[_day(r["date"]) for r in rows]
    out=[]
    for start,end in (("2022-10-01","2022-12-15"),
       ("2023-09-15","2023-11-01"),("2023-11-01","2024-01-01")):
        a=_day(start);b=_day(end)
        tr=np.flatnonzero(np.asarray([d<a for d in dat]))
        va=np.flatnonzero(np.asarray([a<=d<b for d in dat]))
        if len(tr)>=MIN_TRAIN_ROWS and len(va)>=MIN_FOLD_ROWS:
            if max(dat[j] for j in tr)>=min(dat[j] for j in va):
                raise RuntimeError("hurdle_cv_leakage")
            out.append((tr,va))
    return out

def train_hurdle(cases,*,trials=8):
    import optuna
    from xgboost import XGBClassifier
    if not 1<=trials<=60:raise ValueError("hurdle_search_budget_invalid")
    if not cases:raise ValueError("hurdle_empty_training_data")
    for row in cases:_pre2024_date(row["date"])
    rows=sorted(cases,key=lambda r:(r["date"],r["game_id"],r["player_id"]))
    X=np.asarray([r["x"] for r in rows],dtype=np.float32)
    y=np.asarray([r["positive"] for r in rows],dtype=np.int8)
    folds=_cv_folds(rows)
    if len(folds)<2:raise RuntimeError("insufficient_hurdle_pre2024_validation")
    if np.unique(y).size!=2:raise RuntimeError("hurdle_single_label_dataset")
    from sklearn.metrics import log_loss
    def classifier(params):
        return XGBClassifier(objective="binary:logistic",tree_method="hist",
             random_state=SEED,n_jobs=2,verbosity=0,eval_metric="logloss",**params)
    def suggest(trial):
        return dict(n_estimators=trial.suggest_int("n_estimators",100,300,step=50),
           max_depth=trial.suggest_int("max_depth",2,4),
           learning_rate=trial.suggest_float("learning_rate",.02,.13,log=True),
           subsample=trial.suggest_float("subsample",.72,1.),
           colsample_bytree=trial.suggest_float("colsample_bytree",.72,1.),
           min_child_weight=trial.suggest_int("min_child_weight",5,30),
           reg_lambda=trial.suggest_float("reg_lambda",1.,25.,log=True),
           reg_alpha=trial.suggest_float("reg_alpha",.001,1.,log=True))
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    def objective(trial):
        params=suggest(trial);loss=[]
        for tr,va in folds:
            model=classifier(params);model.fit(X[tr],y[tr])
            prob=np.clip(model.predict_proba(X[va])[:,1],1e-5,1-1e-5)
            loss.append(float(log_loss(y[va],prob,labels=[0,1])))
        return float(np.mean(loss))
    study=optuna.create_study(direction="minimize",
         sampler=optuna.samplers.TPESampler(seed=SEED,n_startup_trials=min(4,trials)))
    study.optimize(objective,n_trials=trials,n_jobs=1)
    best=study.best_params
    # Report paired out-of-fold Brier vs conservative constant-rate baseline.
    val=[];base=[]
    for tr,va in folds:
        model=classifier(best);model.fit(X[tr],y[tr])
        p=np.clip(model.predict_proba(X[va])[:,1],.005,.995)
        rate=(2.+float(y[tr].sum()))/(4.+len(tr))
        val.extend((p-y[va])**2)
        base.extend((rate-y[va])**2)
    final=classifier(best);final.fit(X,y)
    receipt={"status":"trained_pre2024_hurdle_only",
       "n_training":len(rows),"n_trials":len(study.trials),
       "folds":[{"training":len(tr),"validation":len(va)} for tr,va in folds],
       "best_cv_logloss":float(study.best_value),
       "oof_hurdle_brier":float(np.mean(val)),
       "oof_constant_rate_brier":float(np.mean(base)),
       "heldout_improvement_verified":float(np.mean(val))<float(np.mean(base)),
       "cutoff_exclusive":"2024-01-01","training_outcomes_2024":0,
       "route_run_rate_feature_present":False,
       "model_families":"Bernoulli hurdle for target/carry/tackle positive occurrence"}
    return final,receipt

def predict_zero(model,state,market,player_id,position,team,opponent,
                 *,asof="2024-01-01",injury=None,personnel=None):
    X=asof_features(state,market=market,player_id=player_id,
       position=position,team=team,opponent=opponent,asof=asof,
       personnel=personnel,injury=injury)
    if X is None:return None,{"status":"abstain_missing_minimum_prior_appearances"}
    if model is None:return None,{"status":"abstain_no_fitted_hurdle"}
    pos=float(model.predict_proba(X.reshape(1,-1))[0,1])
    if not math.isfinite(pos):raise ValueError("nonfinite_hurdle_probability")
    # Reliability cap until conditional P0 and scored zero-class outcomes have
    # both passed pre2024 calibration gates; do not fabricate 99.9% unders.
    p0=max(MIN_ZERO_PROB,min(MAX_ZERO_PROB,1.-pos))
    return p0,{"status":"pre2024_hurdle_shadow_estimate",
       "p_zero":p0,"p_positive":1.-p0,
       "active_status_verified":False,
       "bookmaker_offer_verified":False,
       "route_participation_verified":False}
