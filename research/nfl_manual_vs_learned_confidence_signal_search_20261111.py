"""Experimental calibration & signal discovery (frozen NFL 2016-2025) -- NEVER live promotion.

Research hypotheses:
H1 fixed manual shrinkage toward .5 reduces overconfidence without directional gains.
H2 learned Platt slope / intercept improves confidence with past-only fitting.
H3 residual model disagreement and game-context features improve binary direction.
H4 context-specific corrections are better than calibration without context.

Development 2016-21; model-selection 2022-23; test 2024-25. Test seasons
were already exposed in earlier V2.5 research: test is time-ordered but NOT
pristine independent scientific holdout. All quotes are synthetic.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,math,pathlib,sys,time
import numpy as np
from scipy.special import expit,logit
from scipy.optimize import minimize
ROOT=pathlib.Path.cwd()
ROOT0=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
RUN=ROOT0/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z"
OLD=ROOT0/"EXP_ALL13_20261111T200951Z"
OUT=ROOT0/"V3_CALIBRATION_SIGNAL_DISCOVERY_20261111"
OUT.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(gzip.open(p,"rb").read())
clip=lambda p:np.clip(p,1e-5,1-1e-5)
records=[]
st=time.time()
for year in range(2016,2026):
 for week in range(1,18 if year<=2020 else 19):
  stem=f"{year}_week_{week:02d}"
  vp=read(RUN/(stem+"_v3_predictions.json.gz"))
  sett=read(OLD/(stem+"_settlements.json.gz"))
  by={(v["game_id"],v["team"],v["player_id"],v["market"]):v
      for v in sett["scored"] if v["status"]=="scored_as_same_contract"}
  ctx=vp["game_context"]
  for v in vp["offers"]:
   if v["status"]!="forecast":continue
   k=(v["game_id"],v["team"],v["player_id"],v["market"])
   z=by.get(k)
   if z is None or any(x not in z["model_scores"] for x in ("shared_opportunity","player_history")):continue
   a=z["model_scores"]
   game=ctx.get(v["game_id"],{}).get(v["team"],{})
   records.append((year,week,v["market"],v["role"],int(z["observed_over"]),
       float(v["p_over_online"]),float(v["p_over_raw"]),float(v["p_over_pure_v3"]),
       float(a["shared_opportunity"]["p_over_online"]),float(a["player_history"]["p_over_online"]),
       float(game.get("game_shared_plays_average",62.)),
       float(game.get("game_shared_pass_attempt_average",35.)),
       float(game.get("opponent_projected_plays_average",62.)),
       int(bool(v.get("qb_proxy_override"))),
       float(v["line"]),float(v["predicted_mean"]),
       float(z["actual"]),v["game_id"]))
 print("READ_COMPLETE",year,"N",len(records),"elapsed",round(time.time()-st,1),flush=True)

names=["year","week","market","role","y","v3","raw","pure","v2","history","plays","passes","oppplays","qbfix","line","mean","actual","game"]
R={n:np.array([x[i] for x in records],dtype=(object if n in ("market","role","game") else float)) for i,n in enumerate(names)}
N=len(records);assert N==407476
T=R["year"]
TR=T<=2021;VA=(T>=2022)&(T<=2023);TE=T>=2024
require=lambda ok,msg:(_ for _ in ()).throw(ValueError(msg)) if not ok else None
require(np.all(T>=2016), "bad years")
# normalized only using past data; no outcome-derived or postgame features
def X_for(mask,mode):
 p=clip(R["v3"][mask]);p2=clip(R["v2"][mask]);ph=clip(R["history"][mask])
 z=logit(p);z2=logit(p2);zh=logit(ph)
 if mode=="platt":return np.stack([z],axis=1)
 if mode=="market_baselines":
  return np.stack([z,z2,zh],axis=1)
 if mode=="disagreement":
  return np.stack([z,z2,zh,z-z2,np.abs(z-z2),z2-zh,np.abs(z2-zh)],axis=1)
 if mode=="context":
  return np.stack([z,z2,zh,np.abs(z-z2),z2-zh,
    (R["plays"][mask]-62)/10,
    (R["passes"][mask]-35)/10,
    (R["oppplays"][mask]-62)/10,
    (R["week"][mask]-9)/8,
    R["qbfix"][mask]],axis=1)
 raise ValueError(mode)
def fit(mask,mode,strength=35.):
 x=X_for(mask,mode);y=R["y"][mask]
 scales=np.maximum(.05,x.std(axis=0))
 means=np.mean(x,axis=0);means[:1]=0 # score intercept external
 # preserve Platt logit in physically meaningful units? standardized okay
 xx=np.column_stack((np.ones(len(x)),(x-means)/scales))
 def fun(b):
  z=xx@b
  p=expit(z)
  loss=np.mean(np.logaddexp(0,z)-y*z)
  grad=xx.T@(p-y)/len(y)
  lam=strength/len(y)
  loss+=.5*lam*np.sum(b[1:]**2);grad[1:]+=lam*b[1:]
  return loss,grad
 b=np.zeros(xx.shape[1]);b[0]=float(logit(np.mean(y)));b[1]=0.9
 result=minimize(fun,b,jac=True,method="L-BFGS-B",options={"maxiter":110,"ftol":1e-9})
 require(result.success or result.nit>=60,"failed fit")
 return {"mode":mode,"strength":strength,"means":means,"scales":scales,"coefs":result.x}
def predict(f,mask):
 xx=X_for(mask,f["mode"])
 v=np.column_stack((np.ones(len(xx)),(xx-f["means"])/f["scales"]))
 return clip(expit(v@f["coefs"]))
def static_shrink(mask,fac):
 return clip(.5+fac*(R["v3"][mask]-.5))
def score(p,mask):
 y=R["y"][mask];pred=p>=.5
 n=len(y);over=y>.5
 brier=float(np.mean((p-y)**2))
 hit=float(np.mean(pred==over))
 tpr=float(np.mean(pred[over])) if over.any() else None
 tnr=float(np.mean(~pred[~over])) if (~over).any() else None
 bins={}
 for cut in (.7,.8,.9):
  conf=np.maximum(p,1-p);ix=conf>=cut
  bins[str(cut)]={"n":int(np.sum(ix)),"claimed":float(np.mean(conf[ix])) if ix.any() else None,
    "hit":float(np.mean(pred[ix]==over[ix])) if ix.any() else None}
 return {"n":n,"brier":brier,"logloss":float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p))),
 "hit":hit,"balanced_acc":(tpr+tnr)/2 if tpr is not None and tnr is not None else None,
 "mean_p_over":float(np.mean(p)),"observed_over":float(np.mean(y)),"high_conf":bins}
methods=["v2","v3","shrink_0.95","shrink_0.90","shrink_0.80",
  "platt","market_baselines","disagreement","context"]
MARKETS=sorted(set(R["market"]))
fits={};valid={};tests={}
for market in MARKETS:
 flag=R["market"]==market
 tr=TR&flag;va=VA&flag;te=TE&flag
 require(np.sum(tr)>500 and np.sum(va)>200 and np.sum(te)>200,"not enough "+market)
 fit0={mode:fit(tr,mode) for mode in ("platt","market_baselines","disagreement","context")}
 pv={meth:(R["v2"][va] if meth=="v2" else R["v3"][va] if meth=="v3" else
  static_shrink(va,float(meth.split("_")[1])) if meth.startswith("shrink") else
  predict(fit0[meth],va)) for meth in methods}
 # Correct fixed shrink parsing "0.95".
 for meth in methods:
  valid[market,meth]=score(clip(pv[meth]),va)
 best=min(methods,key=lambda m:valid[market,m]["brier"])
 # Independently keep also directional-accuracy best as diagnostic,
 # but do not choose separate side accuracy to chase historical outcomes.
 bestdir=max(methods,key=lambda m:valid[market,m]["balanced_acc"])
 fits[market]={"selected_on_2022_23":best,"best_balanced_accuracy_candidate":bestdir}
 # Refit any learned challenger only on 2016-2023, still no 2024-25 labels.
 fit1={mode:fit((TR|VA)&flag,mode) for mode in ("platt","market_baselines","disagreement","context")}
 for meth in methods:
  pt=(R["v2"][te] if meth=="v2" else R["v3"][te] if meth=="v3" else
      static_shrink(te,float(meth.split("_")[1])) if meth.startswith("shrink") else
      predict(fit1[meth],te))
  tests[market,meth]=score(clip(pt),te)
 fits[market]["diagnostic_context_2022_23_brier_diff"]=(valid[market,"context"]["brier"]-valid[market,"disagreement"]["brier"])
 fits[market]["diagnostic_context_2024_25_brier_diff"]=(tests[market,"context"]["brier"]-tests[market,"disagreement"]["brier"])
 print("MARKET_DONE",market,"selected",best,
    "val_brier",round(valid[market,best]["brier"],6),
    "test_candidate",round(tests[market,best]["brier"],6),
    "test_v3",round(tests[market,"v3"]["brier"],6),flush=True)
# Aggregate with fixed candidate selection performed before 2024-25.
aggregation={}
for meth in methods+["selected_marketwise"]:
 keys=[(m,fits[m]["selected_on_2022_23"] if meth=="selected_marketwise" else meth) for m in MARKETS]
 n=sum(tests[k]["n"] for k in keys)
 agg={"n":n,"brier":sum(tests[k]["brier"]*tests[k]["n"] for k in keys)/n,
      "hit":sum(tests[k]["hit"]*tests[k]["n"] for k in keys)/n,
      "balanced_acc_macro":float(np.mean([tests[k]["balanced_acc"] for k in keys]))}
 aggregation[meth]=agg
# Save all available tabular comparisons; available train/val/test labels were
# never exposed to the fit before their selected time cutoff.
rows=[]
for market in MARKETS:
 for meth in methods:
  a=valid[market,meth];b=tests[market,meth]
  rows.append({"market":market,"method":meth,"selected":int(fits[market]["selected_on_2022_23"]==meth),
    "val_n":a["n"],"val_brier":a["brier"],"val_hit":a["hit"],
    "val_balanced":a["balanced_acc"],"test_n":b["n"],"test_brier":b["brier"],
    "test_hit":b["hit"],"test_balanced":b["balanced_acc"],
    "test_high80_n":b["high_conf"]["0.8"]["n"],
    "test_high80_hit":b["high_conf"]["0.8"]["hit"],
    "test_high80_claim":b["high_conf"]["0.8"]["claimed"]})
with (OUT/"ALL_CALIBRATION_CANDIDATE_MARKETS.csv").open("w",newline="") as fp:
 f=csv.DictWriter(fp,fieldnames=list(rows[0]));f.writeheader();f.writerows(rows)
out={"status":"RESEARCH_ONLY_COMPLETED","data_timing":{
 "training":"2016-2021","model_selection":"2022-2023","subsequent_evaluation":"2024-2025",
 "evaluation_untouched_in_entire_project":False,
 "authentic_historical_pregame_snapshots":False},
 "n_all":N,"n_train":int(TR.sum()),"n_validation":int(VA.sum()),
 "n_test":int(TE.sum()),"aggregate_test":aggregation,
 "market_selected":fits,"market_candidate_test":{m:{meth:tests[m,meth] for meth in methods} for m in MARKETS},
 "market_candidate_val":{m:{meth:valid[m,meth] for meth in methods} for m in MARKETS},
 "conclusions_not_approved_for_production":True,
 "features_calibration":["logit(v3_prob)","logit(v2_prob)","logit(history_prob)",
 "abs model disagreement","team projected plays","team projected pass attempts",
 "opponent projected plays","week","QB proxy override"],
 "caveats":["Research cohort includes synthetic reference lines and retroactively obtained sources",
 "2024-25 had been viewed in earlier model development, so these splits are not untouched scientific holdouts",
 "Market-wise candidate selection overfits validation without separate multiplicity correction",
 "Simplistic logistic L2 models are not causal or safe to use without forward shadow checks"]}
(OUT/"CALIBRATION_SEARCH_RESULT.json").write_text(json.dumps(out,indent=2,sort_keys=True,default=str))
print("CALIBRATION_SEARCH_COMPLETE",json.dumps({"elapsed":round(time.time()-st,1),
 "samples":N,"splits":out["data_timing"],"agg_test":aggregation,
 "selected_by_market":{m:fits[m] for m in MARKETS}},sort_keys=True,default=str),flush=True)
