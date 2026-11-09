"""Active-but-zero Bernoulli hurdle trained exclusively on pre-2024 games.

Only players confirmed to have real snap exposure enter training. DNP, ungraded
and sportsbook-void observations must never become artificial zero labels.
The source gateway distinguishes:
  * 2021-22 NGS dropback field presence: NOT verified routes run
  * observed prior offense 11-personnel fraction: NOT a future game forecast
  * as-of historical questionable/doubtful injury designations: NOT proof
    of an early game exit or a zero outcome.
2023 FTN participation is quarantined by the Dec 31 2023 cutoff.

For 2024 frozen forecasts, absent 2024 as-of role/injury data must remain
missing; do NOT reuse 2022 route presence as a recent last-three-game trend.
No empirical effect is hardcoded for an injury, 11 personnel, or routes dip:
XGBoost and past-only chrono CV learn it. All models remain research-only.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date
import math
import numpy as np

CUTOFF=date(2024,1,1)
VERSION="nfl_active_zero_pre2024_xgb_hurdle_v1"
MARKETS=("targets","carries","tackles + assists","solo tackles","tackle assists")
DEFENSIVE=frozenset(("tackles + assists","solo tackles","tackle assists"))
SEED=20261109
FEATURE_NAMES=(
 "market_id","position_id",
 "player_zero_rate_last5","player_zero_rate_last3",
 "player_stat_last5","last3_stat_change","days_last_game",
 "recent_snap_count","snap_count_change_last3",
 "role_zero_prior","role_history_count",
 "dropback_presence_last3","dropback_presence_change_3wk",
 "personnel11_opponent_last3",
 "injury_questionable_asof","injury_doubtful_asof",
 "injury_report_available","dropback_proxy_available",
 "personnel11_available","prior_games"
)
POSITIONS=("QB","RB","WR","TE","LB","MLB","ILB","OLB","DE","DT","NT","CB","DB","S","FS","SS")
POSITION_ID={x:i for i,x in enumerate(POSITIONS)}
MARKET_ID={x:i for i,x in enumerate(MARKETS)}
MIN_ACTIVE_SNAPS=1.
MIN_PAST_PLAYER_GAMES=3
LATEST_CONTEXT_MAX_AGE_DAYS=28
MIN_CLASS_OBSERVATIONS=30
MIN_POSITIVES=6

def _day(value):
 return date.fromisoformat(str(value)[:10])

def _prior_rows(state,market,pid,asof,*,limit=5):
 rows=[r for r in state["player"].get((market,str(pid)),())
     if _day(r["gameday"])<asof and float(r.get("workload",0.))>=MIN_ACTIVE_SNAPS]
 rows.sort(key=lambda r:r["gameday"],reverse=True)
 return rows[:limit]

def _recent(history,key,asof,*,n=3,max_age=LATEST_CONTEXT_MAX_AGE_DAYS):
 rows=sorted((r for r in history if _day(r["gameday"])<asof),
     key=lambda r:r["gameday"],reverse=True)
 rows=[r for r in rows if (asof-_day(r["gameday"])).days<=max_age][:n]
 if not rows:return float("nan"),float("nan"),0
 vals=[float(r[key]) for r in rows if r.get(key) is not None]
 if not vals:return float("nan"),float("nan"),0
 if not all(math.isfinite(v) for v in vals):
     raise ValueError("nonfinite_hurdle_context")
 # Last-week minus preceding two-week mean; strong drops are negative.
 return float(sum(vals)/len(vals)),float(vals[0]-sum(vals[1:])/len(vals[1:])) if len(vals)>=3 else float("nan"),len(vals)

def _beta_role_zero(state,market,pos,asof):
 rows=[r for r in state["role"].get((market,pos),())
       if _day(r["gameday"])<asof and float(r.get("workload",0.))>=MIN_ACTIVE_SNAPS]
 # Recent team-specific player examples should outweigh two-year-old players.
 weighted=[]
 for r in rows:
  age=(asof-_day(r["gameday"])).days
  weighted.append((float(r["value"])==0.,2**(-age/120.)))
 w=sum(b for a,b in weighted)
 z=sum(b for a,b in weighted if a)
 return float((1.+z)/(2.+w)),float(w)

def features(state,context,*,market,pid,position,team,opponent,
             asof,season=None,week=None):
 day=_day(asof)
 if day>CUTOFF:raise ValueError("2024_plus_hurdle_features_forbidden")
 if market not in MARKETS:raise ValueError("market_not_zero_hurdle_eligible")
 if position not in POSITION_ID:raise ValueError("unknown_hurdle_position")
 hist=_prior_rows(state,market,pid,day)
 if len(hist)<MIN_PAST_PLAYER_GAMES:return None
 if not all(_day(r["gameday"])<day for r in hist):
  raise ValueError("hurdle_same_week_training_leak")
 last=hist[:3];vals=np.asarray([r["value"] for r in hist],dtype=float)
 last3=np.asarray([r["value"] for r in last],dtype=float)
 snaps=np.asarray([r.get("workload",0.) for r in last],dtype=float)
 if not all(np.isfinite(x) for x in (*vals,*snaps)):
  raise ValueError("nonfinite_player_history")
 prior,nrole=_beta_role_zero(state,market,position,day)
 pres=context.get("participation") or {}
 p_hist=(pres.get("player_dropback_presence") or {}).get(str(pid),())
 db,db_delta,db_count=_recent(p_hist,"dropback_presence_rate",day)
 o_hist=(pres.get("offense_11_personnel") or {}).get(str(opponent),())
 personnel,_,personnel_count=_recent(o_hist,"offense_11_personnel_share",day)
 injury_lookup=context.get("injuries") or {}
 inj=injury_lookup.get((str(pid),int(season),int(week))) if season is not None and week is not None else None
 if inj and _day(inj["date_modified"])>=day:
  raise ValueError("injury_report_postdated_pregame_cutoff")
 status=inj.get("status","") if inj else ""
 if status=="out":
  # An official Out designation contradicts confirmed active-game modeling;
  # this is an eligibility/roster decision, not a zero-market price advantage.
  return None
 row=[
  float(MARKET_ID[market]),float(POSITION_ID[position]),
  float((1.+sum(vals==0.))/(2.+len(vals))),
  float((1.+sum(last3==0.))/(2.+len(last3))),
  float(vals.mean()),float(last3[0]-last3[1:].mean()) if len(last3)>=3 else np.nan,
  float((day-_day(hist[0]["gameday"])).days),
  float(snaps.mean()),float(snaps[0]-snaps[1:].mean()) if len(snaps)>=3 else np.nan,
  float(prior),float(nrole),
  float(db),float(db_delta),float(personnel),
  float(status=="questionable"),float(status=="doubtful"),
  float(inj is not None),
  float(db_count==3),float(personnel_count==3),
  float(len(hist))
 ]
 if len(row)!=len(FEATURE_NAMES):raise RuntimeError("hurdle_feature_registry_mismatch")
 if any(math.isinf(v) for v in row):raise ValueError("infinite_hurdle_feature")
 return np.asarray(row,dtype=np.float32)

def make_training_rows(state,context,player_rows):
 out=[]
 seen=set()
 for r in sorted(player_rows,key=lambda r:(r["game_date"],r["game_id"],r["player_id"],r["stat"])):
  day=_day(r["game_date"])
  if day>=CUTOFF or int(r["season"])>=2024:
    raise ValueError("2024_plus_hurdle_label_forbidden")
  if r["stat"] not in MARKETS:continue
  if r["position"] not in POSITION_ID:continue
  # An active game must have observed positive snap exposure; never fill
  # missing records with zero. Only true observed zero labels enter.
  exposure=r.get("workload")
  if exposure is None or not math.isfinite(float(exposure)) or float(exposure)<MIN_ACTIVE_SNAPS:
    continue
  if float(r["value"])<0 or not float(r["value"]).is_integer():
    raise ValueError("invalid_count_for_zero_hurdle")
  key=(r["game_id"],r["player_id"],r["stat"])
  if key in seen:raise ValueError("duplicate_hurdle_training_label")
  seen.add(key)
  x=features(state,context,market=r["stat"],pid=r["player_id"],
      position=r["position"],team=r["team"],opponent=r["opponent"],
      asof=r["game_date"],season=r["season"],
      week=int(str(r["game_id"]).split("_")[1]))
  if x is None:continue
  out.append({"gameday":r["game_date"],"game_id":r["game_id"],
        "player_id":r["player_id"],"stat":r["stat"],
        "position":r["position"],"x":x.tolist(),
        "zero":int(float(r["value"])==0.)})
 return out

def _folds(rows):
 dates=np.asarray([_day(r["gameday"]) for r in rows])
 windows=(("2022-10-01","2022-12-15"),
          ("2023-09-15","2023-11-01"),
          ("2023-11-01","2024-01-01"))
 output=[]
 for start,end in windows:
  a,b=_day(start),_day(end)
  tr=np.flatnonzero(dates<a)
  val=np.flatnonzero((dates>=a)&(dates<b))
  if len(tr)<200 or len(val)<60:continue
  if max(dates[tr])>=min(dates[val]):raise ValueError("hurdle_fold_time_leak")
  output.append((tr,val))
 return output

def train(state,context,player_rows,*,trials=8):
 """One cross-market active-zero XGB classifier, with market as feature.
 Empty or one-class data -> no hurdle; never invent emergency-only risk.
 """
 import xgboost as xgb,optuna
 from sklearn.metrics import log_loss,brier_score_loss
 if not 1<=trials<=40:raise ValueError("hurdle_trial_budget_invalid")
 samples=make_training_rows(state,context,player_rows)
 if len(samples)<400: return None,{"status":"insufficient_pre2024_active_examples","n":len(samples)}
 X=np.asarray([r["x"] for r in samples],dtype=np.float32)
 y=np.asarray([r["zero"] for r in samples],dtype=np.int8)
 if y.sum()<MIN_CLASS_OBSERVATIONS or (len(y)-y.sum())<MIN_CLASS_OBSERVATIONS:
  return None,{"status":"insufficient_zero_class_examples","n":len(samples)}
 folds=_folds(samples)
 if len(folds)<2:return None,{"status":"insufficient_chronological_cv_folds","n":len(samples)}
 def params(trial):
  return {"n_estimators":trial.suggest_int("n_estimators",100,250,step=50),
  "max_depth":trial.suggest_int("max_depth",2,4),
  "learning_rate":trial.suggest_float("learning_rate",.02,.12,log=True),
  "min_child_weight":trial.suggest_int("min_child_weight",5,20),
  "subsample":trial.suggest_float("subsample",.75,1.),
  "colsample_bytree":trial.suggest_float("colsample_bytree",.70,1.),
  "reg_lambda":trial.suggest_float("reg_lambda",1.,25.,log=True)}
 def classifier(p):
  return xgb.XGBClassifier(objective="binary:logistic",tree_method="hist",
     random_state=SEED,n_jobs=2,verbosity=0,eval_metric="logloss",**p)
 def objective(trial):
  p=params(trial);loss=[]
  for tr,va in folds:
   if len(set(y[tr]))!=2:continue
   m=classifier(p)
   m.fit(X[tr],y[tr])
   prob=np.clip(m.predict_proba(X[va])[:,1],1.e-5,1.-1.e-5)
   loss.append(float(log_loss(y[va],prob,labels=[0,1])))
  return float(np.mean(loss)) if loss else 1.e6
 optuna.logging.set_verbosity(optuna.logging.WARNING)
 study=optuna.create_study(direction="minimize",
     sampler=optuna.samplers.TPESampler(seed=SEED,n_startup_trials=min(4,trials)))
 study.optimize(objective,n_trials=trials,n_jobs=1,show_progress_bar=False)
 # Calibrate only from pre2024 out-of-fold forecasts, never in-sample predictions.
 from sklearn.linear_model import LogisticRegression
 oofp=[];oofy=[];dates=[]
 for tr,va in folds:
  m=classifier(study.best_params);m.fit(X[tr],y[tr])
  p=np.clip(m.predict_proba(X[va])[:,1],1.e-5,1.-1.e-5)
  oofp.extend(p.tolist());oofy.extend(y[va].tolist())
  dates.extend(samples[i]["gameday"] for i in va)
 calibrator=None
 if len(set(oofy))==2 and min(sum(oofy),len(oofy)-sum(oofy))>=20:
  logits=np.log(np.asarray(oofp)/(1.-np.asarray(oofp)))
  calibrator=LogisticRegression(C=.4,random_state=SEED)
  calibrator.fit(logits.reshape(-1,1),np.asarray(oofy))
 model=classifier(study.best_params)
 model.fit(X,y)
 receipt={"status":"fitted_pre2024_only","sample_n":len(y),"zero_n":int(y.sum()),
  "n_folds":len(folds),"n_trials":len(study.trials),
  "best_pre2024_cv_logloss":float(study.best_value),
  "calibration_from_pre2024_oof_only":calibrator is not None,
  "oof_dates_latest":max(dates) if dates else None,
  "2024_training_labels_used":0,
  "validity":"active_conditional_zero_not_DNP_not_emergency_exit",
  "first_last_folds":[[samples[int(tr[-1])]["gameday"],samples[int(va[0])]["gameday"]]
                       for tr,va in folds],
  "best_params":study.best_params}
 return (model,calibrator),receipt

def zero_probability(fitted,state,context,*,market,pid,position,team,opponent,
                     asof,season=None,week=None):
 """Return P(Y=0 | game played) or None. Never claim real bettable quotes."""
 x=features(state,context,market=market,pid=pid,position=position,
             team=team,opponent=opponent,asof=asof,season=season,week=week)
 if x is None:return None,{"status":"no_validated_pre2024_zero_features"}
 if fitted is None:return None,{"status":"untrained_hurdle_abstain"}
 mdl,cal=fitted
 p=float(mdl.predict_proba(x.reshape(1,-1))[0,1])
 if cal is not None:
  v=np.log(max(1.e-5,min(1.-1e-5,p))/(1.-max(1.e-5,min(1.-1e-5,p))))
  p=float(cal.predict_proba(np.asarray([[v]]))[:,1][0])
 if not math.isfinite(p):raise ValueError("nonfinite_hurdle_probability")
 return max(.002,min(.995,p)),{"status":"pre2024_conditional_active_zero_probability",
     "active_player_not_2024_verified":True,"bookmaker_quote_verified":False,
     "zero_risk_from_future_data":False}
