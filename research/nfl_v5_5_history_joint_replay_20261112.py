"""Research-only NFL V5: decade rolling-origin replay of a single coherent
two-team / offense / defense joint game state. Legacy V2/V3 are strictly
comparators; NO per-stat distribution fallback or legacy-probability stacking.

Each week's independently executed forecast receives only frozen historical
stats, pre-week factor weights and synthetic contract lines. The parent reads
official outcomes only AFTER freezing forecast and game-state hashes.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,json,math,os,pathlib,subprocess,sys,time
import numpy as np
ROOT=pathlib.Path.cwd()
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
V3=BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z"
V2=BASE/"EXP_ALL13_20261111T200951Z"
sys.path[:0]=[str(ROOT/"research"),str(V2/"frozen_code")]
from nfl_v5_4_historical_moment_allocator_20261112 import (
 JointGameModel,JointFactorWeights,PROFILES,VERSION,seed,require,
 validate_joint_state,serializable_game_state)
from v25_decade_qb_components import QBRushComponentModel
from nfl_v5_3_joint_scenario_reweight_20261112 import TiltLearner,tilt_forecast
VERSION="v5_5_history_workload_and_joint_soft_anchor_20261112"
V4=BASE/"V4_ADAPTIVE_FACTORS_10YEAR_FULL_20261112T014530Z"
MARKETS=("pass attempts","completions","passing yards","targets","receptions","receiving yards","carries",
 "rushing yards","tackles + assists","solo tackles","tackle assists","qb rushing attempts","qb rushing yards")
SCHEMA="NFL_V5_5_HISTORICAL_MOMENT_SHARED_GAME_SOFT_ANCHOR_RESEARCH"
def read(p):
 b=pathlib.Path(p).read_bytes()
 return json.loads(gzip.decompress(b) if str(p).endswith(".gz") else b)
def canon(obj):return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def save(path,obj):
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 b=canon(obj)
 if p.suffix==".gz":b=gzip.compress(b,compresslevel=4,mtime=0)
 else:b+=b"\n"
 with p.open("xb") as file:file.write(b)
 return sha(b)
def score_crps(draws,actual):
 d=np.sort(np.asarray(draws,dtype=float));n=len(d)
 return float(np.mean(np.abs(d-actual))-np.dot(2*np.arange(n)-n+1,d)/(n*n))
def select_shared_draws(models,mask,n):
 """Choose SAME complete-game profile for both offenses and both defenses."""
 selected={}
 allkeys=set().union(*(set(v) for v in models.values()))
 for identity in allkeys:
  fields=set().union(*(set(d[identity]) for d in models.values() if identity in d))
  selected[identity]={}
  for market in fields:
   vals=[models[label].get(identity,{}).get(market) for label in PROFILES]
   if any(v is None for v in vals):
    # Missing an entire market is an explicit abstention, not V3 fallback.
    continue
   arrays=np.stack([np.asarray(v) for v in vals])
   require(arrays.shape==(3,n),"incomplete_profile_draws")
   selected[identity][market]=arrays[mask,np.arange(n)]
 return selected
def select_shared_state(states,mask,n):
 """Couple each scenario's offensive and defensive state fields in one pass."""
 teams=next(iter(states.values())).keys()
 out={}
 for team in teams:
  result={}
  keys=set().union(*(states[profile][team] for profile in PROFILES))
  for key in keys:
   vals=[states[profile][team].get(key) for profile in PROFILES]
   if any(isinstance(v,np.ndarray) for v in vals):
    require(all(isinstance(v,np.ndarray) and v.shape==(n,) for v in vals),
            "incompatible_selected_shared_state_"+key)
    result[key]=np.stack(vals)[mask,np.arange(n)]
   else:
    require(all(v==vals[0] for v in vals),
            "incompatible_profile_roster_"+key)
    result[key]=vals[0]
  out[team]=result
 return out
def child(input,simulations=128):
 packet=read(input)
 require(packet["schema"]==SCHEMA,"packet_schema")
 y,w=packet["season"],packet["week"]
 require(packet["research_only"] is True and packet["pregame_certified"] is False,"uncertified_contract")
 history=packet["history"]
 require(bool(history) and all(g["season"]<y or(g["season"]==y and g["week"]<w) for g in history),
         "history_has_future")
 require(min(g["season"] for g in history)>=max(2014,y-10),"history_lookback_exceeds_ten")
 require(all(g["season"]<y or(g["season"]==y and g["week"]<w) for g in packet["pbp_prior"]),
         "component_history_has_future")
 weights=JointFactorWeights();weights.restore(packet["factor_preimage"])
 pbp=QBRushComponentModel(packet["pbp_prior"],forecast_year=y,forecast_week=w)
 models={name:JointGameModel(history,y,w,profile) for name,profile in PROFILES.items()}
 game_contracts=collections.defaultdict(list)
 for f in packet["contracts"]:game_contracts[f["game_id"]].append(f)
 scheduled=collections.defaultdict(dict)
 for g in packet["games"]:scheduled[g["game_id"]][g["team"]]=g["opponent"]
 results=[];contexts={}
 for gid,items in sorted(game_contracts.items()):
  teams=scheduled[gid]
  require(len(teams)==2,"missing_two_team_schedule")
  home,away=sorted(teams)
  require(teams[home]==away and teams[away]==home,"incorrect_game_opponent")
  qb={team:packet["qb1"][gid+"|"+team]["player_id"] for team in (home,away)}
  variants={};states={};meta={}
  for name,model in models.items():
   variants[name],meta[name],states[name]=model.forecast_game(gid,home,away,qb,
      n=simulations,pbp_model=pbp,return_state=True)
  # One mask per GAME and SCENARIO. Absolutely no player/stat-level blending.
  selection=np.random.default_rng(seed(VERSION,y,w,gid,"whole_game_factor")).choice(
      3,size=simulations,p=weights.get())
  selected_draws=select_shared_draws(variants,selection,simulations)
  selected_state=select_shared_state(states,selection,simulations)
  validate_joint_state(selected_state,selected_draws,(home,away),simulations)
  contexts[gid]={
    "teams":[home,away],"source_profile_indices":selection.tolist(),
    "whole_game_profile_weights_prior":weights.get().tolist(),
    "joint_state":serializable_game_state(selected_state),
    "profile_meta":meta,
    "single_shared_game_state_verified":True,
    "cross_player_fallback_used":False,
  }
  for f in items:
   identity=(f["team"],f["player_id"])
   arrays=selected_draws.get(identity,{})
   market=f["market"]
   original={key:f[key] for key in ("game_id","team","opponent","player_id","role","market","line")}
   draws=arrays.get(market)
   if draws is None:
    results.append({**original,"status":"abstain_missing_joint_distribution",
      "reason":"not_qualified_or_source_market_unavailable",
      "p_over":None,"p_under":None,"p_push":None})
    continue
   draws=np.asarray(draws,dtype=float)
   require(draws.shape==(simulations,) and np.all(np.isfinite(draws)),
          "illegal_joint_market_support")
   # All three sides are empirical counts from EXACTLY the same joint draws.
   line=float(f["line"])
   over=int(np.sum(draws>line))/simulations
   under=int(np.sum(draws<line))/simulations
   push=int(np.sum(draws==line))/simulations
   require(abs(over+under+push-1)<1e-12,"inconsistent_over_under_push")
   profile_losses=[]
   quantiles=[]
   for name in PROFILES:
    d=variants[name].get(identity,{}).get(market)
    require(d is not None,"profile_marginal_missing_when_selected_available")
    d=np.asarray(d,dtype=float)
    profile_losses.append(float(np.sum(d>line))/simulations)
    quantiles.append(np.quantile(d,[.1,.5,.9]).astype(float).tolist())
   results.append({**original,"status":"forecast",
    "draws":draws.tolist(),"draw_count":simulations,
    "p_over":over,"p_under":under,"p_push":push,
    # No independent per-market stacking: this probability is the joint CDF.
    "p_over_tuned":over,"p_over_raw":over,
    "predicted_mean":float(draws.mean()),
    "source_q_over":profile_losses,
    "source_quantiles":quantiles,
    "source_prior_weights":weights.get().tolist(),
    "origin":"V5_SINGLE_GAME_SIMULATION",
    "independent_legacy_model_scenario_substitution":False,
    "original_v3_p_online":f["v3_online"],
    "original_v2_p_raw":f["v2_raw"],
    "original_history_p_raw":f["history_raw"]})
 require(len(results)==len(packet["contracts"]),"missing_offered_contract")
 raw={"schema":SCHEMA,"version":VERSION,"season":y,"week":w,
  "input_sha256":sha(canon(packet)),
  "factor_preimage_sha256":sha(canon(packet["factor_preimage"])),
  "games":contexts,
  "offers":results,
  "source_retroactively_collected":True,"pregame_certified":False,
  "research_only":True,"production_authorized":False,
  "forecasts_did_not_receive_current_week_settlements":True}
 anchors={(f["game_id"],f["team"],f["player_id"],f["market"]):f["v4_anchor_p"]
   for f in packet["contracts"] if f["v4_anchor_p"] is not None}
 tiltprior=TiltLearner()
 tiltprior.restore(packet["tilt_preimage"])
 out=tilt_forecast(raw,anchors,tiltprior,VERSION)
 out["tilt_preimage_sha256"]=sha(canon(packet["tilt_preimage"]))
 out["historical_reference_source_sha256"]=packet["v4_anchor_forecast_sha256"]
 return out

def evaluate(packet,forecast,truth,weights,tilt):
 by={(f["game_id"],f["team"],f["player_id"],f["market"]):f
     for f in forecast["offers"]}
 require(len(by)==len(forecast["offers"]),"duplicate_contracts")
 ledger=collections.Counter()
 per=collections.defaultdict(lambda:collections.defaultdict(float))
 train=collections.defaultdict(list)
 train_tilt=collections.defaultdict(list)
 origs={(f["game_id"],f["team"],f["player_id"],f["market"]):f for f in packet["contracts"]}
 for z in truth["scored"]:
  if z["status"]!="scored_as_same_contract":
   ledger["unmatched_official"]+=1
   continue
  key=(z["game_id"],z["team"],z["player_id"],z["market"])
  ff=by.get(key)
  require(ff is not None,"missing_offered_identical_identity")
  ledger["official_matched"]+=1
  if ff["status"]!="forecast":
   ledger["joint_abstention"]+=1
   continue
  if any(k not in z["model_scores"] for k in ("shared_opportunity","player_history")):
   ledger["unpaired_legacy_baseline"]+=1
   continue
  if origs[key]["v3_draws"] is None or ff["original_v3_p_online"] is None:
   ledger["unpaired_v3_forecast"]+=1
   continue
  market=z["market"];value=float(z["actual"]);side=int(z["observed_over"])
  q=float(ff["p_over"])
  legacy=float(ff["original_v3_p_online"])
  brier=(q-side)**2
  brier_v3=(legacy-side)**2
  d=ff["draws"];crps=score_crps(d,value)
  crps_v3=score_crps(origs[key]["v3_draws"],value)
  ledger["paired"]+=1
  scores={
   "brier_joint":brier,"brier_v3":brier_v3,
   "brier_v2":float(z["model_scores"]["shared_opportunity"]["brier_online"]),
   "crps_joint":crps,"crps_v3":crps_v3,
   "hit_joint":float((q>.5)==bool(side)),
   "hit_v3":float((legacy>.5)==bool(side)),
   "signed_over_residual":q-side,
   "mean_error_joint":float(ff["predicted_mean"]-value),
   "joint_logloss":-math.log(np.clip(q if side else 1-q,1e-6,1)),
   "v3_logloss":-math.log(np.clip(legacy if side else 1-legacy,1e-6,1))}
  for m in ("all",market):
   dct=per[m];dct["n"]+=1
   for k,v in scores.items():dct[k]+=v
   for k in (70,80,90,95):
    threshold=k/100
    conf=max(q,1-q)
    if conf>=threshold:
     prefix="conf"+str(k)
     dct[prefix+"_n"]+=1
     dct[prefix+"_claimed"]+=conf
     dct[prefix+"_hit"]+=scores["hit_joint"]
  norm={"pass attempts":10.,"completions":8.,"passing yards":90.,
        "targets":4.,"receptions":3.,"receiving yards":30.,
        "carries":6.,"rushing yards":45.,"tackles + assists":3.,
        "solo tackles":2.,"tackle assists":1.5,
        "qb rushing attempts":2.,"qb rushing yards":12.}[market]
  losses=[]
  for pq,qlist in zip(ff["source_q_over"],ff["source_quantiles"]):
   pin=sum((tau-int(value<x))*(value-x) for tau,x in zip((.1,.5,.9),qlist))/3
   losses.append(.65*(pq-side)**2+.35*float(pin)/norm)
  train[market].append(losses)
  # This outcome is visible only in the settlement stage; the 3 whole-game
  # candidate tilt strengths are scored on the frozen joint sample here.
  tiltq=ff["full_game_strength_candidates_q_over"]
  require(len(tiltq)==3,"tilt_candidates_incomplete")
  train_tilt[market].append([(float(qc)-side)**2 for qc in tiltq])
 weights.update(train)
 tilt.update(train_tilt)
 def summary(d):
  n=d.get("n",0)
  if not n:return {"n":0}
  ans={"n":int(n)}
  for k in ("brier_joint","brier_v3","brier_v2","crps_joint","crps_v3",
            "hit_joint","hit_v3","signed_over_residual",
            "mean_error_joint","joint_logloss","v3_logloss"):
   ans[k]=float(d[k]/n)
  for thresh in (70,80,90,95):
   pref=f"conf{thresh}";c=int(d.get(pref+"_n",0))
   ans[pref+"_n"]=c
   ans[pref+"_claimed"]=float(d[pref+"_claimed"]/c) if c else None
   ans[pref+"_hit"]=float(d[pref+"_hit"]/c) if c else None
  return ans
 return {"season":packet["season"],"week":packet["week"],
  "offers":len(forecast["offers"]),"paired":ledger["paired"],
  "ledger":dict(ledger),"all":summary(per["all"]),
  "markets":{k:summary(per[k]) for k in MARKETS},
  "factor_weights_updated_only_after_settlement":weights.receipt(),
  "tilt_weights_updated_only_after_settlement":tilt.receipt(),
  "research_only":True}

def run(out,limit):
 require(not out.exists(),"run_directory_exists")
 v3=read(V3/"FINAL_V3_VS_V2_10YEAR_REPORT.json")
 require(v3["cycles"]==175,"base_archive_not_complete")
 archive=v3["weekly_archive"][:limit or None]
 out.mkdir(parents=True)
 v4final=read(V4/"V4_FINAL_DECADE_RESEARCH_REPORT.json")
 require(v4final["cycles"]==175,"V4_reference_archive_incomplete")
 v4hashes={(z["season"],z["week"]):z["forecast_sha256"]
   for z in v4final["receipts"]}
 receipt={"model_version":VERSION,"schema":SCHEMA,"profiles":PROFILES,
  "model_sha256":sha((ROOT/"research/nfl_v5_4_historical_moment_allocator_20261112.py").read_bytes()),
  "game_tilt_code_sha256":sha((ROOT/"research/nfl_v5_3_joint_scenario_reweight_20261112.py").read_bytes()),
  "V4_reference_final_receipt":v4final["result_sha256"],
  "V4_reference_used_as_soft_game_moment_constraint":True,
  "runner_sha256":sha(pathlib.Path(__file__).read_bytes()),
  "baseline_research_sha256":v3["result_sha256"],
  "research_only":True,"production_authorized":False,
  "historical_lines_synthetic":True,
  "historical_source_original_pregame_verified":False,
  "legacy_scenarios_never_enter_joint_simulation":True,
  "probabilities_derived_only_from_single_joint_game_state":True}
 save(out/"V5_METHOD_AND_SOURCE_RECEIPT.json",receipt)
 weights=JointFactorWeights();tilt=TiltLearner();reports=[];receipts=[]
 for index,item in enumerate(archive):
  y,w=item["year"],item["week"];stem=f"{y}_week_{w:02d}"
  source=read(V3/(stem+"_v3_before_outcomes.json.gz"))
  old=read(V3/(stem+"_v3_predictions.json.gz"))
  oldv2=read(V2/(stem+"_predictions.json.gz"))
  pathv4=V4/(stem+"_v4_predictions.json.gz")
  require(sha(pathv4.read_bytes())==v4hashes[(y,w)],
    "historical_v4_reference_sha_mismatch")
  v4forecast=read(pathv4)
  require(v4forecast["season"]==y and v4forecast["week"]==w and
      v4forecast["forecasts_did_not_receive_current_week_settlements"] is True,
      "V4_reference_is_not_chronological")
  anchors={(f["game_id"],f["team"],f["player_id"],f["market"]):
       f["p_over_tuned"] for f in v4forecast["offers"]
       if f["status"]=="forecast"}
  require(sha((V3/(stem+"_v3_predictions.json.gz")).read_bytes())==
          item["forecast_sha256"],"baseline_hash_drift")
  by={(f["game_id"],f["team"],f["player_id"],f["market"]):f
       for f in oldv2["offers"]}
  contracts=[]
  for f in old["offers"]:
   key=(f["game_id"],f["team"],f["player_id"],f["market"])
   leg=by.get(key)
   require(leg is not None,"legacy_missing_contract")
   md=leg["forecast_models"]
   p2=md["shared_opportunity"]
   ph=md["player_history"]
   contracts.append({**{z:f[z] for z in ("game_id","team","opponent","player_id","role","market","line")},
     "v3_draws":f.get("draws") if f["status"]=="forecast" else None,
     "v3_online":f.get("p_over_online"),
     "v2_raw":float(p2["q_over_raw"]) if p2 else .5,
     "history_raw":float(ph["q_over_raw"]) if ph else .5,
     "v4_anchor_p":anchors.get(key)})
  frozen={"schema":SCHEMA,"season":y,"week":w,
    "history":source["history"],"pbp_prior":source["pbp_prior"],
    "games":source["games"],"qb1":source["qb1"],
    "contracts":contracts,"factor_preimage":weights.receipt(),
    "tilt_preimage":tilt.receipt(),
    "v4_anchor_forecast_sha256":v4hashes[(y,w)],
    "original_v3_prediction_sha256":item["forecast_sha256"],
    "pregame_certified":False,"research_only":True}
  pre=out/(stem+"_v5_preweek.json.gz")
  fore=out/(stem+"_v5_forecast.json.gz")
  after=out/(stem+"_v5_settlement.json.gz")
  frozenhash=save(pre,frozen)
  cmd=[sys.executable,os.path.abspath(__file__),"forecast","--input",str(pre),
       "--output",str(fore)]
  p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=420)
  require(p.returncode==0,"isolated_forecast_error_"+str((y,w))+": "+p.stderr[-4500:])
  predicted=read(fore)
  require(predicted["input_sha256"]==sha(canon(frozen)),
          "forecast_not_from_preweek_hash")
  require(predicted["factor_preimage_sha256"]==sha(canon(frozen["factor_preimage"])),
          "future_factor_state_leak")
  require(predicted["tilt_preimage_sha256"]==sha(canon(frozen["tilt_preimage"])),
          "future_tilt_parameter_leak")
  require(predicted["historical_reference_source_sha256"]==v4hashes[(y,w)],
          "V4_reference_source_mismatch")
  forecastsha=sha(fore.read_bytes())
  truth=read(V2/(stem+"_settlements.json.gz"))
  settled=evaluate(frozen,predicted,truth,weights,tilt)
  settled.update({"preweek_sha256":frozenhash,"forecast_sha256":forecastsha,
    "score_only_after_frozen_forecast":True,
    "tilt_preimage_sha256":sha(canon(frozen["tilt_preimage"]))})
  settlementsha=save(after,settled)
  reports.append(settled)
  receipts.append({"season":y,"week":w,"input_sha256":frozenhash,
       "forecast_sha256":forecastsha,"settlement_sha256":settlementsha,
       "paired":settled["paired"]})
  score=settled["all"]
  print("V5_JOINT_WEEK_SETTLED",json.dumps({
    "season":y,"week":w,"paired":settled["paired"],
    "brier_v5":score.get("brier_joint"),
    "brier_v3":score.get("brier_v3"),
    "crps_v5":score.get("crps_joint"),
    "crps_v3":score.get("crps_v3"),
    "factor_prior_for_next_week":weights.get().round(3).tolist(),
    "tilt_strength_weights_next_week":tilt.get().round(3).tolist()}),flush=True)
 def aggregate(rows):
  N=sum(z["all"]["n"] for z in rows)
  if N==0:return {"n":0}
  out={"n":N,"weeks":len(rows)}
  for k in ("brier_joint","brier_v3","brier_v2","crps_joint","crps_v3","hit_joint","hit_v3",
            "signed_over_residual","mean_error_joint","joint_logloss","v3_logloss"):
   out[k]=sum(z["all"]["n"]*z["all"].get(k,0) for z in rows)/N
  out["delta_brier"]=out["brier_joint"]-out["brier_v3"]
  out["delta_crps"]=out["crps_joint"]-out["crps_v3"]
  for th in (70,80,90,95):
   prefix="conf"+str(th);cnt=sum(z["all"][prefix+"_n"] for z in rows)
   out[prefix+"_n"]=cnt
   out[prefix+"_claimed"]=(sum(z["all"][prefix+"_n"]*(z["all"][prefix+"_claimed"] or 0)
                        for z in rows)/cnt) if cnt else None
   out[prefix+"_hit"]=(sum(z["all"][prefix+"_n"]*(z["all"][prefix+"_hit"] or 0)
                        for z in rows)/cnt) if cnt else None
  return out
 result={"status":"COMPLETE_RESEARCH_ONLY" if len(reports)==175 else "PARTIAL_RESEARCH_ONLY",
  "weeks_completed":len(reports),"receipts":receipts,
  "overall":aggregate(reports),
  "season":{str(y):aggregate([z for z in reports if z["season"]==y])
    for y in sorted({z["season"] for z in reports})},
  "source_retroactive":True,"research_only":True,"production_authorized":False,
  "unmatched_and_abstained":{str(y)+"-"+str(w):a["ledger"] for (y,w),a in zip(
    [(q["season"],q["week"]) for q in reports],reports)},
  "underlying_joint_state_and_distribution_bound_to_same_game_scenario":True,
  "V4_reference_hash_verified_before_forecast":True,
  "tilt_weights_update_only_postsettlement":True,
  "method_sha256":sha(canon(receipt))}
 result["result_sha256"]=sha(canon(result))
 save(out/"V5_COMPLETE_OR_PARTIAL_RESEARCH_REPORT.json",result)
 fields=["season","week","n","brier_joint","brier_v3","delta_brier","crps_joint","crps_v3",
         "hit_joint","hit_v3","conf80_n","conf80_claimed","conf80_hit"]
 with (out/"V5_WEEKLY_SCORES.csv").open("w",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
  for z in reports:
   score=z["all"]
   writer.writerow({"season":z["season"],"week":z["week"],"n":score["n"],
    **{k:score.get(k) for k in fields if k in score},
    "delta_brier":score.get("brier_joint",0)-score.get("brier_v3",0)})
 print("V5_JOINT_REPLAY_DONE",json.dumps({"weeks":len(reports),
     "overall":result["overall"],"status":result["status"],
     "result_sha":result["result_sha256"]}),flush=True)

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("mode",choices=["forecast","run"])
 p.add_argument("--input",type=pathlib.Path)
 p.add_argument("--output",type=pathlib.Path,required=True)
 p.add_argument("--limit",type=int,default=0)
 args=p.parse_args()
 if args.mode=="forecast":
  require(args.input is not None,"frozen_input_required")
  save(args.output,child(args.input))
 else:run(args.output,args.limit)
