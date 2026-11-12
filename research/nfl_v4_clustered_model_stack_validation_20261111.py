"""Validate learned market-level probability stacking with game/week clustering.

This is retrospective with development-exposed 2024-25, not a pristine test.
Only 2016-2023 outcomes can estimate stacking parameters.
The 2024-25 outcomes appear after fixed forecasts and are used for scoring.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,math,pathlib,sys,time
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit,logit
ROOT=pathlib.Path.cwd()
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
V3=BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z"
V2=BASE/"EXP_ALL13_20261111T200951Z"
OUT=BASE/"V4_STACK_PROSPECTIVE_STYLE_CLUSTERED_VALIDATION"
OUT.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(gzip.open(p,"rb").read())
def clip(x):return np.clip(x,.005,.995)
observations=collections.defaultdict(list)
test=[]
t0=time.time()
for year in range(2016,2026):
 for week in range(1,18 if year<=2020 else 19):
  base=f"{year}_week_{week:02d}"
  f=read(V3/(base+"_v3_predictions.json.gz"))
  s=read(V2/(base+"_settlements.json.gz"))
  preds={(z["game_id"],z["team"],z["player_id"],z["market"]):z
     for z in f["offers"] if z["status"]=="forecast"}
  for z in s["scored"]:
   if z["status"]!="scored_as_same_contract" or not all(k in z["model_scores"] for k in ("shared_opportunity","player_history")):continue
   key=(z["game_id"],z["team"],z["player_id"],z["market"])
   p=preds.get(key)
   if p is None:continue
   a=z["model_scores"]
   r={"year":year,"week":week,"game":z["game_id"],"market":z["market"],
      "p_v3":float(p["p_over_online"]),
      "p_v2":float(a["shared_opportunity"]["p_over_online"]),
      "p_history":float(a["player_history"]["p_over_online"]),
      "outcome":int(z["observed_over"])}
   if year<=2023:observations[z["market"]].append(r)
   else:test.append(r)
 print("FREEZE_MODEL_STACK_SOURCE_SEASON",year,
   "training_rows",sum(len(x) for x in observations.values()),"test_rows",len(test),flush=True)
allmarkets=sorted(observations)
require=lambda flag,msg:(_ for _ in ()).throw(AssertionError(msg)) if not flag else None
require(len(test)==83925,"test_denominator_changed")
params={}
for market in allmarkets:
 x=observations[market]
 y=np.asarray([t["outcome"] for t in x])
 xx=np.asarray([logit(clip([t["p_v3"],t["p_v2"],t["p_history"]])) for t in x])
 avg=xx.mean(axis=0);scale=np.maximum(xx.std(axis=0),.05)
 X=np.column_stack([np.ones(len(xx)),(xx-avg)/scale])
 def obj(b):
  z=X@b
  p=expit(z);lam=35.0/len(y)
  loss=np.mean(np.logaddexp(0,z)-y*z)+.5*lam*np.sum(b[1:]**2)
  grad=X.T@(p-y)/len(y)
  grad[1:]+=lam*b[1:]
  return float(loss),grad
 b=np.zeros(4);b[0]=logit(clip(y.mean()));b[1]=.9
 res=minimize(obj,b,jac=True,method="L-BFGS-B",options={"maxiter":130,"ftol":1e-10})
 require(res.success or res.nit>=100,"stack_fit_failed_"+market)
 params[market]={"mean":avg,"scale":scale,"coeff":res.x,"n_prior":len(x),
   "max_training_season":2023}
def predict(row):
 f=params[row["market"]]
 z=logit(clip([row["p_v3"],row["p_v2"],row["p_history"]]))
 x=np.r_[1,(z-f["mean"])/f["scale"]]
 return float(clip(expit(x@f["coeff"])))
for x in test:x["p_stack"]=predict(x)
def metrics(rows):
 n=len(rows)
 if not n:return {}
 y=np.asarray([r["outcome"] for r in rows])
 out={"n":n}
 for name in ("stack","v3","v2"):
  pp=np.asarray([r["p_"+name] for r in rows])
  hit=(pp>.5)==(y==1)
  brier=(pp-y)**2
  out[name+"_brier"]=float(brier.mean())
  out[name+"_hit"]=float(hit.mean())
  out[name+"_logloss"]=float(np.mean(-(y*np.log(pp)+(1-y)*np.log(1-pp))))
  for cut in (.7,.8,.9):
   sel=np.maximum(pp,1-pp)>=cut
   pre=name+"_conf"+str(int(cut*100))
   out[pre+"_n"]=int(sel.sum())
   out[pre+"_claimed"]=float(np.maximum(pp[sel],1-pp[sel]).mean()) if sel.any() else None
   out[pre+"_hit"]=float(hit[sel].mean()) if sel.any() else None
 out["delta_stack_minus_v3_brier"]=out["stack_brier"]-out["v3_brier"]
 out["delta_stack_minus_v3_hit"]=out["stack_hit"]-out["v3_hit"]
 return out
overall=metrics(test);bymarket={m:metrics([r for r in test if r["market"]==m]) for m in allmarkets}
byseason={str(year):metrics([r for r in test if r["year"]==year]) for year in (2024,2025)}
byweek={str(year)+"-"+str(week):metrics([r for r in test if r["year"]==year and r["week"]==week])
       for year in (2024,2025) for week in range(1,19)}
# Bootstrap pre-aggregated week and game clusters, matching contracts among all methods
group_week=collections.defaultdict(list);group_game=collections.defaultdict(list)
for r in test:
 group_week[(r["year"],r["week"])].append(r)
 group_game[(r["year"],r["game"])].append(r)
def brier_delta(rows):
 a=np.asarray([r["p_stack"] for r in rows]);v=np.asarray([r["p_v3"] for r in rows]);y=np.asarray([r["outcome"] for r in rows])
 return float(np.sum((a-y)**2-(v-y)**2))
def hit_delta(rows):
 a=np.asarray([r["p_stack"]>.5 for r in rows]);v=np.asarray([r["p_v3"]>.5 for r in rows]);y=np.asarray([r["outcome"]>0 for r in rows])
 return float(np.sum((a==y).astype(int)-(v==y).astype(int)))
def boot(groups,rep=3500):
 c=list(groups.values());n=np.asarray([len(t) for t in c],dtype=int)
 d=np.asarray([brier_delta(t) for t in c]);h=np.asarray([hit_delta(t) for t in c])
 rng=np.random.default_rng(42691);values=[];acc=[]
 for _ in range(rep):
  ix=rng.integers(0,len(c),len(c))
  den=n[ix].sum()
  values.append(float(d[ix].sum()/den))
  acc.append(float(h[ix].sum()/den))
 return {"clusters":len(c),
  "mean_brier_difference":float(d.sum()/n.sum()),
  "brier_diff_ci95":np.quantile(values,[.025,.975]).tolist(),
  "hit_difference":float(h.sum()/n.sum()),
  "hit_diff_ci95":np.quantile(acc,[.025,.975]).tolist()}
clustered={"weekly":boot(group_week),"game":boot(group_game)}
reliability={}
for name in ("stack","v3","v2"):
 for low,high in ((.5,.6),(.6,.7),(.7,.8),(.8,.9),(.9,1.0001)):
  group=[z for z in test if low<=max(z["p_"+name],1-z["p_"+name])<high]
  pp=np.asarray([z["p_"+name] for z in group])
  yy=np.asarray([z["outcome"] for z in group])
  confidence=np.maximum(pp,1-pp)
  reliability[name+"_"+str(low)+"_"+str(high)]={
   "n":len(group),"mean_claim":float(confidence.mean()) if len(group) else None,
   "observed_hit":float(np.mean((pp>.5)==(yy==1))) if len(group) else None}
# Save test probabilities for auditable reruns, not only macro scores.
with (OUT/"TEST_2024_25_FROZEN_PREDICTION_COMPARISON.csv").open("w",newline="") as f:
 names=["year","week","game","market","p_v3","p_v2","p_history","p_stack","outcome"]
 w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(test)
model_receipt={m:{"n_prior":v["n_prior"],"max_training_season":v["max_training_season"],
 "mean":v["mean"].tolist(),"scale":v["scale"].tolist(),"coeff":v["coeff"].tolist()} for m,v in params.items()}
receipt={"status":"RESEARCH_ONLY_VALIDATION_COMPLETE",
 "n_test":len(test),"n_train_up_to_2023":sum(len(z) for z in observations.values()),
 "training_cutoff":"end 2023","evaluation":"2024-2025",
 "evaluation_truly_untouched_in_wider_project":False,
 "no_bookmaker_quotes":True,"source_pregame_certified":False,
 "candidate":"regularized three-probability market logistic model (known from 2022-23 research)",
 "overall":overall,"season":byseason,"market":bymarket,"week":byweek,
 "clustered":clustered,"calibration_bins":reliability,"model":model_receipt,
 "frozen_pregame_source":"V3 + V2 archived forecast/settlement probability receipts",
 "scored_only_after_frozen_prediction":True,
 "real_market_tiers_authorized":False,
 "runtime_s":round(time.time()-t0,2)}
(OUT/"CLUSTERED_VALIDATION_RECEIPT.json").write_text(json.dumps(receipt,indent=2,sort_keys=True,default=str))
print("CLUSTERED_STACK_VALIDATION_COMPLETE",json.dumps({"n":len(test),"overall":overall,
  "byseason":byseason,"clustered":clustered,
  "selected_market_gains":{m:{"brier":v["delta_stack_minus_v3_brier"],"hit":v["delta_stack_minus_v3_hit"],"n":v["n"]} for m,v in bymarket.items()},
  "runtime":receipt["runtime_s"]},sort_keys=True),flush=True)
