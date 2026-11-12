"""Research-only NFL V4 ten-season chronological factor tuning + prior-only stacking.

Exactly the original 2016-2025 175 weekly synthetic contract slate.
Read-only original V2 and V3 predictions. Two truly re-generated context
models with different HISTORY / OPPONENT / PLAYER OPPORTUNITY factors.
Factor scenario weights and per-market logit stack learn after each week
and are frozen before the next forecast. No production promotion.

python research/nfl_v4_factor_tuning_decade_20261111.py run --limit 2 --output ... 
python research/nfl_v4_factor_tuning_decade_20261111.py run --output ...
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,json,math,os,pathlib,subprocess,sys,time
import numpy as np
ROOT=pathlib.Path.cwd()
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
V3=BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z"
V2=BASE/"EXP_ALL13_20261111T200951Z"
sys.path[:0]=[str(ROOT/"research"),str(V2/"frozen_code")]
from nfl_v4_factor_tuning_model_20261111 import (
    ContextFactorModel,FactorWeights,OnlineMarketStack,PROFILES,
    VERSION,seed,require)
from v25_decade_qb_components import QBRushComponentModel
MARKETS=("pass attempts","completions","passing yards","targets","receptions","receiving yards","carries",
         "rushing yards","tackles + assists","solo tackles","tackle assists","qb rushing attempts","qb rushing yards")
SCHEMA="nfl_v4_10year_adaptive_factors_stack_weekly_frozen_research"
def read(p):
 b=pathlib.Path(p).read_bytes()
 if str(p).endswith(".gz"):b=gzip.decompress(b)
 return json.loads(b)
def canon(obj):return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def save(path,obj):
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 b=canon(obj)
 if p.suffix==".gz":b=gzip.compress(b,mtime=0,compresslevel=5)
 else:b+=b"\n"
 with p.open("xb") as f:f.write(b)
 return sha(b)
def state():
 return FactorWeights(),OnlineMarketStack()
def child(input,simulations=128):
 packet=read(input)
 require(packet["schema"]==SCHEMA,"invalid_packet")
 y,w=packet["season"],packet["week"]
 require(packet["research_only"] is True and packet["pregame_certified"] is False,"source_false")
 history=packet["history"]
 require(bool(history) and all(g["season"]<y or(g["season"]==y and g["week"]<w) for g in history),"future_history")
 require(all(g["season"]<y or(g["season"]==y and g["week"]<w) for g in packet["pbp_prior"]),"future_pbp")
 require(min(g["season"] for g in history)>=max(2014,y-10),"lookback_exceeds_10years")
 weights=FactorWeights();weights.restore(packet["factor_preimage"])
 stack=OnlineMarketStack();stack.restore(packet["stack_preimage"])
 pbp=QBRushComponentModel(packet["pbp_prior"],forecast_year=y,forecast_week=w)
 mods={name:ContextFactorModel(history,y,w,profile) for name,profile in PROFILES.items()}
 per_game=collections.defaultdict(list)
 for f in packet["contracts"]:per_game[f["game_id"]].append(f)
 scheduled=collections.defaultdict(dict)
 for item in packet["games"]:scheduled[item["game_id"]][item["team"]]=item["opponent"]
 output=[];game_context={}
 for gid,items in sorted(per_game.items()):
  teams=scheduled[gid];require(len(teams)==2,"missing_game_teams")
  ta,tb=sorted(teams);require(teams[ta]==tb and teams[tb]==ta,"bad_game_opponent")
  qb={team:packet["qb1"][gid+"|"+team]["player_id"] for team in (ta,tb)}
  variant={};metas={}
  for name,mod in mods.items():
   variant[name],metas[name]=mod.forecast_game(gid,ta,tb,qb,n=simulations,pbp_model=pbp)
  game_context[gid]={
   "teams":list(teams),
   "variant_meta":metas,
   "factor_weights_prior":weights.get().tolist()}
  # IMPORTANT: one global source mask per game, NOT per contract.
  # Thus candidate-path covariance is preserved within the model family.
  rng=np.random.default_rng(seed(VERSION,y,w,gid,"candidate_choice"))
  source=rng.choice(3,size=simulations,p=weights.get())
  for f in items:
   clean={k:v for k,v in f.items() if k not in ("v3_draws","v2_raw","history_raw","v3_online")}
   base=f["v3_draws"]
   if base is None:
    output.append({**clean,"status":"abstain_original_v3",
      "reason":"legacy_source_not_forecast","raw_market_source_available":False})
    continue
   base=np.asarray(base,dtype=float)
   require(base.shape==(simulations,) and np.all(np.isfinite(base)),"bad_original_draws")
   variants=[base]
   fallback={}
   for name in ("recent","long"):
    v=variant[name].get((f["team"],f["player_id"]),{}).get(f["market"])
    if v is None:
     variants.append(base)
     fallback[name]=True
    else:
     v=np.asarray(v,dtype=float)
     require(v.shape==(simulations,) and np.all(np.isfinite(v)),"bad_context_draws")
     variants.append(v)
     fallback[name]=False
   all_arr=np.stack(variants)
   draws=all_arr[source,np.arange(simulations)]
   require(np.isfinite(draws).all(),"invalid_mixed_draw")
   rawq=(int(np.sum(draws>f["line"]))+.5)/(simulations+1)
   # Probabilities of factor profiles are logged to update AFTER settlement.
   qvari=[(int(np.sum(arr>f["line"]))+.5)/(simulations+1) for arr in variants]
   qprofile=[[float(z) for z in np.quantile(arr,[.1,.5,.9])] for arr in variants]
   p,stackdetails=stack.get(f["market"],rawq,f["v2_raw"],f["history_raw"],f["v3_online"])
   output.append({**clean,"status":"forecast",
      "raw_market_source_available":True,
      "p_over_raw":rawq,"p_over_tuned":p,
      "source_q_over":qvari,"source_quantiles":qprofile,
      "stack_weights_prior":stackdetails,
      "sample_weights_prior":weights.get().tolist(),
      "factor_fallback":fallback,
      "predicted_mean":float(np.mean(draws)),"draws":draws.tolist(),
      "draw_count":simulations,
      "original_v3_p_online":float(f["v3_online"]),
      "original_v2_p_raw":float(f["v2_raw"]),
      "original_history_p_raw":float(f["history_raw"])})
 require(len(output)==len(packet["contracts"]),"missing_contract")
 return {
  "schema":SCHEMA,"model_version":VERSION,"season":y,"week":w,
  "input_sha256":sha(canon(packet)),
  "factor_preimage_sha256":sha(canon(packet["factor_preimage"])),
  "stack_preimage_sha256":sha(canon(packet["stack_preimage"])),
  "forecasts_did_not_receive_current_week_settlements":True,
  "offers":output,"context_training":{
   name:{"quality":m.quality,"profile":PROFILES[name]} for name,m in mods.items()},
  "game_context":game_context,
  "production_authorized":False,"pregame_certified":False}

def evaluate(packet,output,sett,weights,stack):
 by={(f["game_id"],f["team"],f["player_id"],f["market"]):f for f in output["offers"]}
 assert len(by)==len(output["offers"])
 ledger=collections.Counter()
 groups=collections.defaultdict(lambda:collections.defaultdict(float))
 trainfactor=collections.defaultdict(list);trainstack=collections.defaultdict(list)
 base_by={(z["game_id"],z["team"],z["player_id"],z["market"]):z for z in packet["contracts"]}
 for row in sett["scored"]:
  if row["status"]!="scored_as_same_contract":
   ledger["missing_official_observation"]+=1
   continue
  key=(row["game_id"],row["team"],row["player_id"],row["market"])
  f=by.get(key)
  require(f is not None,"unmatched_offered_identity")
  ledger["official_scored"]+=1
  if f["status"]!="forecast":ledger["abstained_official"]+=1;continue
  y=int(row["observed_over"]);market=row["market"]
  a=row["model_scores"]
  if any(k not in a for k in ("shared_opportunity","player_history")):
   ledger["unpaired_official"]+=1;continue
  ledger["paired"]+=1
  scores={
   "tuned_brier":(f["p_over_tuned"]-y)**2,
   "raw_brier":(f["p_over_raw"]-y)**2,
   "frozen_v3_brier":(f["original_v3_p_online"]-y)**2,
   "frozen_v2_brier":a["shared_opportunity"]["brier_online"],
   "player_history_brier":a["player_history"]["brier_online"],
   "tuned_logloss":-math.log(max(1e-10,f["p_over_tuned"] if y else 1-f["p_over_tuned"])),
   "v3_logloss":-math.log(max(1e-10,f["original_v3_p_online"] if y else 1-f["original_v3_p_online"])),
   "tuned_hit":float((f["p_over_tuned"]>.5)==bool(y)),
   "v3_hit":float((f["original_v3_p_online"]>.5)==bool(y)),
   "v2_hit":float((a["shared_opportunity"]["p_over_online"]>.5)==bool(y)),
   "over_observed":y,"p_over_tuned":f["p_over_tuned"],
   "mean_residual":f["predicted_mean"]-row["actual"]}
  d=np.sort(np.asarray(f["draws"],dtype=float));n=len(d)
  scores["tuned_crps"]=float(np.mean(np.abs(d-row["actual"]))-
    np.dot(2*np.arange(n)-n+1,d)/(n*n))
  # Recompute original frozen V3 CRPS on exactly the same observed contract.
  b=np.sort(np.asarray(base_by[key]["v3_draws"],dtype=float))
  scores["v3_crps"]=float(np.mean(np.abs(b-row["actual"]))-
    np.dot(2*np.arange(len(b))-len(b)+1,b)/(len(b)*len(b)))
  for key in ("all",market):
   dct=groups[key];dct["n"]+=1
   for k,v in scores.items():dct[k]+=v
   for th in (70,80,90,95):
    confidence=max(f["p_over_tuned"],1-f["p_over_tuned"])
    if confidence>=th/100:
     pre=f"conf{th}"
     dct[pre+"_n"]+=1
     dct[pre+"_claimed"]+=confidence
     dct[pre+"_hit"]+=scores["tuned_hit"]
  # Macro-market Brier + normalized WIS-style pinball loss adapts the
  # historical/opportunity factors on past binary AND full-distribution skill.
  # Deterministic scales are precommitted, never estimated from test outcomes.
  norm={"pass attempts":10.,"completions":8.,"passing yards":90.,
    "targets":4.,"receptions":3.,"receiving yards":30.,
    "carries":6.,"rushing yards":45.,"tackles + assists":3.,
    "solo tackles":2.,"tackle assists":1.5,
    "qb rushing attempts":2.,"qb rushing yards":12.}[market]
  allloss=[]
  for q,predq in zip(f["source_q_over"],f["source_quantiles"]):
   qbrier=(float(q)-y)**2
   pin=sum((tau-int(row["actual"]<value))*(row["actual"]-value)
      for tau,value in zip((.1,.5,.9),predq))/3
   allloss.append(.65*qbrier+.35*float(pin)/norm)
  trainfactor[market].append(allloss)
  trainstack[market].append((f["p_over_raw"],f["original_v2_p_raw"],
          f["original_history_p_raw"],y,f["original_v3_p_online"]))
 # ALL updates happen after we have written both preimage and forecasts.
 weights.update(trainfactor)
 for market,records in trainstack.items():stack.update(market,records)
 def pack(g):
  n=g.get("n",0)
  if n==0:return {"n":0}
  d={"n":int(n)}
  for k,v in g.items():
   if k=="n":continue
   if k.endswith("_n") or k.endswith("_claimed") or k.endswith("_hit") and k.startswith("conf"):
    continue
   d[k]=float(v/n)
  for th in (70,80,90,95):
   pre=f"conf{th}";cnt=int(g.get(pre+"_n",0))
   d[pre+"_n"]=cnt
   d[pre+"_claimed"]=float(g[pre+"_claimed"]/cnt) if cnt else None
   d[pre+"_hit"]=float(g[pre+"_hit"]/cnt) if cnt else None
  return d
 return {"season":packet["season"],"week":packet["week"],
  "original_offers":len(output["offers"]),"ledger":dict(ledger),
  "paired":ledger["paired"],
  "all":pack(groups["all"]),
  "markets":{m:pack(groups[m]) for m in MARKETS},
  "frozen_prediction_receipt":"available",
  "factor_weights_updated_only_postsettlement":weights.receipt(),
  "stack_weights_updated_only_postsettlement":stack.receipt(),
  "research_only":True}

def run(out,limit=0):
 require(not out.exists(),"output_directory_already_exists")
 v3final=read(V3/"FINAL_V3_VS_V2_10YEAR_REPORT.json")
 require(v3final["cycles"]==175,"original_v3_incomplete")
 archive=v3final["weekly_archive"][:limit or None]
 out.mkdir(parents=True)
 receipt={"schema":SCHEMA,"version":VERSION,"profiles":PROFILES,
  "model_sha256":sha((ROOT/"research/nfl_v4_factor_tuning_model_20261111.py").read_bytes()),
  "runner_sha256":sha(pathlib.Path(__file__).read_bytes()),
  "legacy_v3_sha256":v3final["result_sha256"],
  "original_pregame_sources_authenticated":False,
  "all_contract_lines_synthetic":True,
  "production_authorized":False,"draws":128,
  "factor_learner":"preweek global 3-family scenario weights based only on prior macro-market scores",
  "stack_learner":"preweek market-specific simplex logit stack SGD based only on prior official results"}
 save(out/"FROZEN_SOURCE_AND_METHOD_RECEIPT.json",receipt)
 fw,st=state()
 receipts=[];weeks=[];t0=time.monotonic()
 for k,item in enumerate(archive):
  y,w=item["year"],item["week"]
  base=f"{y}_week_{w:02d}"
  vp=read(V3/(base+"_v3_before_outcomes.json.gz"))
  v3pred=read(V3/(base+"_v3_predictions.json.gz"))
  v2pred=read(V2/(base+"_predictions.json.gz"))
  if sha((V3/(base+"_v3_predictions.json.gz")).read_bytes())!=item["forecast_sha256"]:
   raise ValueError("V3 prediction hash mismatch")
  require(vp["year"]==y==v3pred["year"] and vp["week"]==w==v3pred["week"],"source_mismatch")
  old_by={(f["game_id"],f["team"],f["player_id"],f["market"]):f for f in v2pred["offers"]}
  offers=[]
  for f in v3pred["offers"]:
   key=(f["game_id"],f["team"],f["player_id"],f["market"])
   old=old_by.get(key)
   require(old is not None,"missing_old_v2_offer")
   qold=old["forecast_models"]["shared_opportunity"]
   qhist=old["forecast_models"]["player_history"]
   # Retain all old offered contracts, including one-model-only source cases.
   # If an original comparison is unavailable, use a neutral .5 as an inert
   # stack placeholder. Exclude those contracts from paired evaluation later.
   offers.append({**{kk:f[kk] for kk in ("game_id","team","opponent","player_id","role","market","line")},
      "v3_draws":f.get("draws") if f["status"]=="forecast" else None,
      "v3_online":f.get("p_over_online"),
      "v2_raw":qold["q_over_raw"] if qold is not None else .5,
      "history_raw":qhist["q_over_raw"] if qhist is not None else .5,
      "source_models_both_available":qold is not None and qhist is not None})
  inp={"schema":SCHEMA,"season":y,"week":w,"research_only":True,
   "pregame_certified":False,"history":vp["history"],"pbp_prior":vp["pbp_prior"],
   "qb1":vp["qb1"],"games":vp["games"],"contracts":offers,
   "factor_preimage":fw.receipt(),"stack_preimage":st.receipt(),
   "baseline_v3_input_sha256":v3pred["input_sha256"],
   "baseline_v3_prediction_sha256":item["forecast_sha256"]}
  before=out/(base+"_v4_before_outcomes.json.gz")
  after=out/(base+"_v4_predictions.json.gz")
  settled=out/(base+"_v4_settlements.json.gz")
  hashbefore=save(before,inp)
  r=subprocess.run([sys.executable,os.path.abspath(__file__),"forecast",
      "--input",str(before),"--output",str(after)],cwd=ROOT,
      capture_output=True,text=True,timeout=420)
  require(r.returncode==0,
    "isolated_forecast_failed_"+str((y,w))+": "+r.stderr[-3500:]+r.stdout[-800:])
  pred=read(after)
  require(pred["input_sha256"]==sha(canon(inp)),"forecast_not_bound_to_input")
  require(pred["factor_preimage_sha256"]==sha(canon(inp["factor_preimage"])),
          "factor_update_before_prediction")
  require(pred["stack_preimage_sha256"]==sha(canon(inp["stack_preimage"])),
          "stack_update_before_prediction")
  hashpred=sha(after.read_bytes())
  # Only here the official past week outcomes enter the parent.
  truth=read(V2/(base+"_settlements.json.gz"))
  res=evaluate(inp,pred,truth,fw,st)
  res.update({"preweek_sha256":hashbefore,
   "forecast_sha256":hashpred,
   "frozen_factor_preimage_sha256":sha(canon(inp["factor_preimage"])),
   "frozen_stack_preimage_sha256":sha(canon(inp["stack_preimage"])),
   "both_sides_scored_only_after_forecast":True})
  hashsettled=save(settled,res)
  receipts.append({"season":y,"week":w,"preweek_sha256":hashbefore,
      "forecast_sha256":hashpred,"settlement_sha256":hashsettled,
      "factor_preimage_sha256":res["frozen_factor_preimage_sha256"],
      "stack_preimage_sha256":res["frozen_stack_preimage_sha256"],
      "paired":res["paired"]})
  weeks.append(res)
  a=res["all"]
  print("V4_WEEK_COMPLETE",json.dumps({
    "year":y,"week":w,"n":res["paired"],"brier_tuned":a.get("tuned_brier"),
    "brier_v3":a.get("frozen_v3_brier"),"hit_tuned":a.get("tuned_hit"),
    "conf80":a.get("conf80_n"),
    "factor_weights_next_week":fw.get().round(3).tolist(),
    "seconds":round(time.monotonic()-t0,1)}),flush=True)
  if k%18==17:
   save(out/(base+"_CHECKPOINT.json"),{
     "cycles_so_far":k+1,"hashes":receipts,
     "research_only":True})
 def aggregate(samples):
  ns=[r["all"]["n"] for r in samples];N=sum(ns)
  if not N:return {"n":0}
  names=("tuned_brier","raw_brier","frozen_v3_brier","frozen_v2_brier",
    "player_history_brier","tuned_logloss","v3_logloss",
    "tuned_hit","v3_hit","v2_hit","tuned_crps","v3_crps","mean_residual")
  d={"n":N}
  for z in names:d[z]=sum(r["all"].get(z,0)*r["all"]["n"] for r in samples)/N
  for cutoff in (70,80,90,95):
   k=f"conf{cutoff}";co=sum(r["all"][k+"_n"] for r in samples)
   d[k+"_n"]=co
   d[k+"_claimed"]=sum(r["all"][k+"_n"]*(r["all"][k+"_claimed"] or 0) for r in samples)/co if co else None
   d[k+"_hit"]=sum(r["all"][k+"_n"]*(r["all"][k+"_hit"] or 0) for r in samples)/co if co else None
  d["brier_delta_tuned_minus_v3"]=d["tuned_brier"]-d["frozen_v3_brier"]
  d["crps_delta_tuned_minus_v3"]=d["tuned_crps"]-d["v3_crps"]
  d["hit_delta_tuned_minus_v3"]=d["tuned_hit"]-d["v3_hit"]
  return d
 grand=aggregate(weeks)
 byseason={str(y):aggregate([r for r in weeks if r["season"]==y]) for y in sorted({r["season"] for r in weeks})}
 result={"schema":SCHEMA,
  "completion":"COMPLETE_RESEARCH_ONLY" if len(receipts)==175 else "PARTIAL_RESEARCH_ONLY",
  "cycles":len(receipts),"receipts":receipts,
  "overall":grand,"seasons":byseason,
  "original_source_receipt":receipt,
  "total_offered":sum(r["original_offers"] for r in weeks),
  "total_paired":grand["n"],"production_authorized":False,
  "original_historical_pregame_source_certified":False,
  "notes":["Cohort is conditional on original player observation availability",
   "Every week predictions produced without current outcomes",
   "Factor adaptations and logit stacking updated only after week settlement",
   "Ensemble is mostly the original V3 scenario model, not a pure fully ten-year refit",
   "Player usage and matchup factors are hypotheses; genuine prospective verification required"]}
 result["result_sha256"]=sha(canon(result))
 save(out/"V4_FINAL_DECADE_RESEARCH_REPORT.json",result)
 fields=["season","week","n","tuned_brier","raw_brier","frozen_v3_brier",
   "frozen_v2_brier","tuned_crps","v3_crps","tuned_hit","v3_hit","v2_hit",
   "conf80_n","conf80_hit","conf80_claimed","factor_recent","factor_long","factor_v3"]
 with (out/"V4_ALL_175_WEEKLY_SCORECARDS.csv").open("w",newline="") as fp:
  writer=csv.DictWriter(fp,fieldnames=fields);writer.writeheader()
  for rr in weeks:
   aa=rr["all"];fwrec=rr["factor_weights_updated_only_postsettlement"]["weights"]
   writer.writerow({"season":rr["season"],"week":rr["week"],
     **{f:aa.get(f) for f in fields if f in aa},
     "factor_v3":fwrec[0],"factor_recent":fwrec[1],"factor_long":fwrec[2]})
 print("V4_DECADE_RESEARCH_COMPLETE",json.dumps({"status":result["completion"],
  "cycles":result["cycles"],"overall":grand,"receipt":result["result_sha256"],
  "seconds":round(time.monotonic()-t0,1)}),flush=True)

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("action",choices=("forecast","run"))
 p.add_argument("--input",type=pathlib.Path)
 p.add_argument("--output",type=pathlib.Path,required=True)
 p.add_argument("--limit",type=int,default=0)
 args=p.parse_args()
 if args.action=="forecast":
  require(args.input is not None,"missing_frozen_packet")
  save(args.output,child(args.input))
 else:run(args.output,args.limit)
