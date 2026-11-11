"""V3 10-year point-in-time NFL replay: isolated forecaster, weekly forecast SHA,
independent outcomes; old V2 shared opportunity and player-history comparators.

Python: python research/nfl_decade_context_v3_run_20261111.py run --limit 2 --output ...
        python research/nfl_decade_context_v3_run_20261111.py run --output ...
Only writes NEW research outputs; V2 originals remain immutable.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,json,math,os,pathlib,subprocess,sys,time,traceback
import numpy as np
ROOT=pathlib.Path.cwd()
STUDY=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
OLD=STUDY/"EXP_ALL13_20261111T200951Z"
SRC=STUDY/"source_bundle"
OLD_PBP=STUDY/"qb_pbp_components_2014_2020"
NEW_PBP=ROOT/"reports/v25_qb_rushing_components_2024_2025_20261111/sources_v2"
MODEL=ROOT/"research/nfl_decade_context_v3_model_20261111.py"
sys.path[:0]=[str(ROOT/"research"),str(OLD/"frozen_code")]
from v25_decade_joint_opportunity import normalise_player_source,MARKETS
from nfl_decade_context_v3_model_20261111 import GameContextModel,MatchupRegressor,OnlineBayesCalibrator,MARKETS13,DRAWS,VERSION,seed
SCHEMA="nfl_2016_2025_context_v3_10yr_prequential_research"
def read(path):
 b=pathlib.Path(path).read_bytes()
 if str(path).endswith(".gz"):b=gzip.decompress(b)
 return json.loads(b)
def canon(x):return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def save(path,obj):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 b=canon(obj)
 if path.suffix==".gz":b=gzip.compress(b,compresslevel=5,mtime=0)
 else:b+=b"\n"
 with path.open("xb") as f:f.write(b)
 return sha(b)
def require(ok,msg):
 if not ok:raise RuntimeError("V3_PREQUENTIAL_ABORT:"+msg)
def minmax_history(hist,year,week):
 require(all(g["season"]<year or(g["season"]==year and g["week"]<week) for g in hist),"CURRENT_WEEK_DATA_IN_HISTORY")
 return {"first":min(g["season"] for g in hist),"last":max(g["season"] for g in hist),"games":len(hist)}
def child(packet,n=128):
 require(packet["schema"]==SCHEMA,"WRONG_CHILD_PACKET")
 year,week=packet["year"],packet["week"]
 hist=packet["history"]
 minmax_history(hist,year,week)
 require(packet["research_only"] is True and packet["authentic_pregame_sources"] is False,"NOT_RESEARCH")
 require(all(g["season"]<year or(g["season"]==year and g["week"]<week) for g in packet["pbp_prior"]),"FUTURE_PBP_IN_CHILD")
 from v25_decade_qb_components import QBRushComponentModel
 fit=MatchupRegressor(hist)
 model=GameContextModel(hist,year,week,fit)
 pbp=QBRushComponentModel(packet["pbp_prior"],forecast_year=year,forecast_week=week)
 cal=OnlineBayesCalibrator()
 for k,v in packet["calibration_preimage"]["state"].items():
  market,side,b=str(k).split("|")
  cal.s[(market,side,int(b))]=[float(v[0]),float(v[1])]
 offers=collections.defaultdict(list)
 for row in packet["contracts"]:
  offers[row["game_id"]].append(row)
 teams=collections.defaultdict(dict)
 for g in packet["games"]:
  teams[g["game_id"]][g["team"]]=g["opponent"]
 actual=[];context={}
 for gid,players in sorted(offers.items()):
  teamnames=teams[gid]
  require(len(teamnames)==2,"MISSING_SCHEDULED_GAME_TEAM")
  ta,tb=sorted(teamnames)
  require(teamnames[ta]==tb and teamnames[tb]==ta,"TEAM_OPPONENT_MISMATCH")
  qb1={team:packet["qb1"][gid+"|"+team]["player_id"] for team in (ta,tb)}
  draws,meta=model.forecast_game(gid,ta,tb,qb1,n=n,pbp_model=pbp)
  context[gid]=meta
  for p in players:
   key=(p["team"],p["player_id"])
   a=draws.get(key,{}).get(p["market"])
   clean={k:v for k,v in p.items() if k!="v2_draws"}
   if a is None:
    actual.append({**clean,"status":"new_model_abstain","reason":"missing_past_conditional_usage_or_unqualified_QB"})
    continue
   a=np.asarray(a,dtype=float)
   require(a.shape==(n,) and np.all(np.isfinite(a)),"BAD_DRAWS")
   pure_q=(int(np.count_nonzero(a>p["line"]))+.5)/(n+1.)
   prior=p.get("v2_draws")
   if prior is None:
    mixed=a;share=1.;override=False
   else:
    prior=np.asarray(prior,dtype=float)
    require(prior.shape==(n,) and np.all(np.isfinite(prior)),"BAD_ORIGINAL_DRAWS")
    # One immutable game-scoped scenario mask across all original market rows.
    # Preserve V2 conservation on retained draws and V3 conservation on new draws.
    chooser=np.random.default_rng(seed("V3_PRECOMMITTED_BLEND",year,week,gid))
    mask=np.zeros(n,dtype=bool)
    mask[chooser.choice(n,n//4,replace=False)]=True
    override=(p["role"]=="QB" and p["market"] in ("pass attempts","completions","passing yards")
              and np.mean(prior)<2 and np.mean(a)>=10)
    if override:mask[:]=True
    mixed=np.where(mask,a,prior)
    share=float(np.mean(mask))
   q=(int(np.count_nonzero(mixed>p["line"]))+.5)/(n+1.)
   pc=cal.apply(p["market"],q)
   actual.append({**clean,"status":"forecast","p_over_raw":q,"p_over_online":pc,
    "p_over_pure_v3":pure_q,"blend_v3_share":share,
    "qb_proxy_override":override,"predicted_mean":float(np.mean(mixed)),
    "draws":mixed.tolist(),"draw_count":n})
 require(len(actual)==len(packet["contracts"]),"OUTPUT_COUNT_MISMATCH")
 return {"schema":SCHEMA,"year":year,"week":week,"model_version":VERSION,
 "input_sha256":sha(canon(packet)),"calibration_preimage_sha256":sha(canon(packet["calibration_preimage"])),
 "offers":actual,"game_context":context,"model_training":model.quality,"joint_conservation_model":True,
 "forecast_child_received_current_outcomes":False,"source_time_verified":False,
 "production_authorized":False,"tiers_authorized":False}

def evaluate(sett,pred,old_pred,cal,year,week):
 old_by={(f["game_id"],f["team"],f["player_id"],f["market"]):f for f in old_pred["offers"]}
 by={(f["game_id"],f["team"],f["player_id"],f["market"]):f for f in pred["offers"]}
 assert len(by)==len(pred["offers"])
 totals=collections.defaultdict(lambda:collections.defaultdict(float))
 allout=[];updates=[]
 counts=collections.Counter()
 for o in sett["scored"]:
  k=(o["game_id"],o["team"],o["player_id"],o["market"]) if o["status"]=="scored_as_same_contract" else tuple(o["key"])
  f=by.get(k)
  if f is None:raise ValueError("missing_forecast_contract")
  if o["status"]!="scored_as_same_contract":
   counts["unmatched_original_player_observation"]+=1
   continue
  counts["scored_original_observations"]+=1
  if f["status"]!="forecast":
   counts["model_abstained_scored_original"]+=1
   continue
  bm=o["model_scores"]
  if "shared_opportunity" not in bm or "player_history" not in bm:
   counts["one_original_model_missing"]+=1
   continue
  y=o["observed_over"];m=f["market"]
  p=f["p_over_online"];p0=f["p_over_raw"]
  brier=(p-y)**2
  score={"brier_new":brier,"brier_v3_pure":(f["p_over_pure_v3"]-y)**2,
     "brier_new_raw":(p0-y)**2,
     "logloss_new":-math.log(max(1e-12,p if y else 1-p)),
     "brier_v2_joint":bm["shared_opportunity"]["brier_online"],
     "brier_v2_history":bm["player_history"]["brier_online"],
     "logloss_v2_joint":bm["shared_opportunity"]["logloss_online"],
     "logloss_v2_history":bm["player_history"]["logloss_online"],
     "hit_new":float((p>.5)==bool(y)),
     "hit_v2_joint":float((bm["shared_opportunity"]["p_over_online"]>.5)==bool(y)),
     "hit_v2_history":float((bm["player_history"]["p_over_online"]>.5)==bool(y)),
     "claimed_conf":max(p,1-p),"over_0_1":y,"p_over":p,
     "count_mean_bias":f["predicted_mean"]-o["actual"]}
  draws=np.sort(np.asarray(f["draws"],dtype=float))
  n=len(draws)
  score["crps_new"]=float(np.mean(np.abs(draws-o["actual"]))-
     np.dot(2*np.arange(n)-n+1,draws)/(n*n))
  score["crps_v2_joint"]=bm["shared_opportunity"]["crps"]
  score["crps_v2_history"]=bm["player_history"]["crps"]
  lo,hi=np.quantile(draws,[.1,.9])
  score["interval_80_covers"]=float(lo<=o["actual"]<=hi)
  for key in ("all",m):
   rec=totals[key];rec["n"]+=1
   for sk,v in score.items():
    if sk=="claimed_conf":continue
    rec[sk]+=v
   for th in (.7,.8,.9,.95):
    if score["claimed_conf"]>=th:
     name=f"conf{int(th*100)}"
     rec[name+"_n"]+=1
     rec[name+"_claims"]+=score["claimed_conf"]
     rec[name+"_hits"]+=score["hit_new"]
     rec[name+"_under"]+=p<.5
  updates.append((m,p0,y))
  counts["paired_scored"]+=1
  allout.append({"market":m,"game":o["game_id"],"team":o["team"],
      "player_id":o["player_id"],"actual":o["actual"],"observed_over":y,
      "line":o["line"],"p_over_raw":p0,"p_over_online":p,
      "p_over_v2_joint":bm["shared_opportunity"]["p_over_online"],
      "p_over_v2_history":bm["player_history"]["p_over_online"],
      **score})
 cal.update(updates)
 def pack(v):
  n=v.get("n",0)
  if not n:return {"n":0}
  a={"n":int(n)}
  for k,value in v.items():
   if k=="n":continue
   a[k]=float(value/n) if not k.endswith("_n") and not k.endswith("_claims") and not k.endswith("_hits") and not k.endswith("_under") else float(value)
  for th in (70,80,90,95):
   pre=f"conf{th}"
   count=v.get(pre+"_n",0)
   a[pre+"_n"]=int(count)
   a[pre+"_hit"]=float(v.get(pre+"_hits",0)/count) if count else None
   a[pre+"_claimed"]=float(v.get(pre+"_claims",0)/count) if count else None
   a[pre+"_under_share"]=float(v.get(pre+"_under",0)/count) if count else None
  return a
 return {"year":year,"week":week,"offered":len(pred["offers"]),
   "scored_original":counts["scored_original_observations"],
   "paired":counts["paired_scored"],"counts":dict(counts),
   "all":pack(totals["all"]),
   "markets":{m:pack(totals[m]) for m in MARKETS13},
   "season_source_is_retroactive":True,
   "production_authorized":False},allout

def run(output,limit):
 require(not output.exists(),"APPEND_ONLY_DIRECTORY_ALREADY_EXISTS")
 orig=read(OLD/"FINAL_2016_2025_RESEARCH_REPORT.json")
 art=orig["weekly_and_season_source_archive"]
 if limit:art=art[:limit]
 # Verify historical source hashes before using any data.
 manifest=read(SRC/"MANIFEST.json")
 for file,h in manifest["source_files"].items():
  require(sha((SRC/file).read_bytes())==h,"SOURCE_HASH_CHANGED_"+file)
 allgames={}
 for year in range(2014,2026):
  data=read(SRC/f"stats_{year}.json.gz")
  clean=[r for r in data["rows"] if r.get("player_id") and r.get("team") and r.get("game_id")]
  allgames[year]=normalise_player_source(clean,rejection_ledger=[],allowed_seasons=tuple(range(2014,2026)))
 pbp={}
 for year in range(2014,2026):
  base=OLD_PBP if year<=2020 else NEW_PBP
  pbp[year]=read(base/f"qb_components_{year}.json.gz")["rows"]
 output.mkdir(parents=True,exist_ok=False)
 source_receipt={"schema":SCHEMA,"model_sha256":sha(MODEL.read_bytes()),
    "runner_sha256":sha(pathlib.Path(__file__).read_bytes()),
    "source_manifest_sha256":sha((SRC/"MANIFEST.json").read_bytes()),
    "prior_max_years":10,"historical_source_capture_verified":False,
    "legacy_frozen_replay_sha256":orig["result_sha256"],
    "source_type":"nflverse retrospective 2026",
    "original_bookmaker_quotes_present":False,"production_allowed":False,
    "simulation_draws_per_contract":DRAWS}
 save(output/"FROZEN_EXPERIMENT_RECEIPT.json",source_receipt)
 cal=OnlineBayesCalibrator()
 artifact=[];weeks=[];scores=collections.defaultdict(list)
 totalstart=time.time()
 for k,archive in enumerate(art):
  year,week=archive["season"],archive["week"]
  base=f"{year}_week_{week:02}"
  oldpacket=read(OLD/(base+"_before_outcomes.json.gz"))
  oldp=read(OLD/(base+"_predictions.json.gz"))
  require(year==oldpacket["season"]==oldp["season"] and week==oldpacket["week"]==oldp["week"],"OLD_WEEK_MISMATCH")
  hist=[]
  for yr in range(max(2014,year-10),year):hist.extend(allgames[yr])
  hist.extend(g for g in allgames[year] if g["week"]<week)
  pprior=[]
  for yr in range(max(2014,year-10),year):pprior.extend(pbp[yr])
  pprior.extend(r for r in pbp[year] if r["week"]<week)
  require(all(g["season"]<year or(g["season"]==year and g["week"]<week) for g in hist),"FUTURE_HISTORY")
  require(all(g["season"]<year or(g["season"]==year and g["week"]<week) for g in pprior),"FUTURE_PBP")
  contracts=[{**{key:f[key] for key in ("season","week","game_id","team","opponent","player_id","role","market","line")},
    "v2_draws":(f["forecast_models"].get("shared_opportunity") or {}).get("draws")}
    for f in oldp["offers"]]
  snapshot=cal.receipt()  # DEEP copies state, BEFORE postweek update; no alias.
  p={"schema":SCHEMA,"year":year,"week":week,
     "history":hist,"pbp_prior":pprior,"games":oldpacket["games"],
     "qb1":oldpacket["qb1"],"contracts":contracts,"calibration_preimage":snapshot,
     "research_only":True,"authentic_pregame_sources":False}
  inp=output/(base+"_v3_before_outcomes.json.gz")
  predfile=output/(base+"_v3_predictions.json.gz")
  settlement=output/(base+"_v3_settlements.json.gz")
  input_hash=save(inp,p)
  # Isolate forecast in a clean interpreter with NO access to official outcomes.
  cmd=[sys.executable,os.path.abspath(__file__),"forecast","--input",str(inp),"--output",str(predfile)]
  task=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=300)
  require(task.returncode==0,f"FORECAST_CRASH_{year}_{week}:{task.stderr[-3000:]}:{task.stdout[-1000:]}")
  output_preds=read(predfile)
  require(output_preds["input_sha256"]==sha(canon(p)),"CHILD_OUTPUT_NOT_BOUND_TO_FREEZE")
  require(output_preds["calibration_preimage_sha256"]==sha(canon(snapshot)),"MISBOUND_CALIBRATOR")
  prediction_hash=sha(predfile.read_bytes())
  # Current-game outcomes are revealed ONLY after both preweek and forecast files exist.
  oldsett=read(OLD/(base+"_settlements.json.gz"))
  result,rows=evaluate(oldsett,output_preds,oldp,cal,year,week)
  result["original_forecast_sha256"]=sha((OLD/(base+"_predictions.json.gz")).read_bytes())
  result["new_forecast_sha256"]=prediction_hash
  result["preweek_sha256"]=input_hash
  result["calibration_preweek_sha256"]=sha(canon(snapshot))
  settled_hash=save(settlement,result)
  weeks.append(result);artifact.append({"year":year,"week":week,"preweek_sha256":input_hash,
     "forecast_sha256":prediction_hash,"settlement_sha256":settled_hash,
     "preweek_calibrator_sha256":sha(canon(snapshot)),
     "first_history_year":min(g["season"] for g in hist),
     "last_history_year":max(g["season"] for g in hist),
     "training_rows":output_preds["model_training"]["training_rows"]})
  for row in rows:scores[row["market"]].append(row)
  print("V3_WEEK_DONE",json.dumps({"year":year,"week":week,
    "n_offered":result["offered"],"n_paired":result["paired"],
    "n_scored":result["scored_original"],"brier_new":result["all"].get("brier_new"),
    "brier_v2":result["all"].get("brier_v2_joint"),
    "conf80":result["all"].get("conf80_n"),
    "historic_years":year-min(g["season"] for g in hist),
    "elapsed_s":round(time.time()-totalstart,1)}),flush=True)
  if (k+1)%17==0:
   save(output/(base+"_CHECKPOINT.json"),{"complete":k+1,"weekly_hashes":artifact,
         "reported_research_only":True})
  # no training on future outcome: updates already applied after frozen settlement.
 def agg(values):
  if not values:return {}
  n=len(values);a={"n":n}
  for key in ("brier_new","brier_v2_joint","brier_v2_history","brier_v3_pure",
    "logloss_new","logloss_v2_joint","logloss_v2_history",
    "crps_new","crps_v2_joint","crps_v2_history",
    "hit_new","hit_v2_joint","hit_v2_history","interval_80_covers",
    "count_mean_bias","p_over","over_0_1"):
   a[key]=float(np.mean([r[key] for r in values]))
  for t in (70,80,90,95):
   z=[r for r in values if r["claimed_conf"]>=t/100]
   a[f"conf{t}_n"]=len(z)
   a[f"conf{t}_claimed"]=float(np.mean([r["claimed_conf"] for r in z])) if z else None
   a[f"conf{t}_hit"]=float(np.mean([r["hit_new"] for r in z])) if z else None
  return a
 allrows=[x for s in scores.values() for x in s]
 final={"status":"RESEARCH_ONLY_COMPLETED" if len(art)==175 else "RESEARCH_ONLY_PARTIAL_PILOT",
   "schema":SCHEMA,"model_version":VERSION,"source_receipt":source_receipt,
   "total_offered":sum(w["offered"] for w in weeks),
   "total_original_scored":sum(w["scored_original"] for w in weeks),
   "paired":len(allrows),"cycles":len(art),"weekly_archive":artifact,
   "overall":agg(allrows),"markets":{m:agg(scores[m]) for m in MARKETS13},
   "season":{},"original_source_pregame_certified":False,
   "real_bookmaker_quotes":False,"production_allowed":False}
 for y in sorted(set(w["year"] for w in weeks)):
  yrows=[r for r in allrows if r["game"].startswith(str(y)+"_")]
  final["season"][str(y)]=agg(yrows)
 final["result_sha256"]=sha(canon(final))
 save(output/"FINAL_V3_VS_V2_10YEAR_REPORT.json",final)
 # One tabular row per week, 13 markets as separate saved JSON for exact audit.
 fields=["year","week","offered","scored_original","paired","brier_new","brier_v2_joint",
     "brier_v2_history","logloss_new","crps_new","crps_v2_joint","hit_new",
     "conf80_n","conf80_hit","conf80_claimed","history_start","training_rows"]
 with (output/"V3_ALL_WEEKLY_COMPARISON.csv").open("w",newline="") as handle:
  wr=csv.DictWriter(handle,fieldnames=fields);wr.writeheader()
  for w,a in zip(weeks,artifact):
   wr.writerow({"year":w["year"],"week":w["week"],"offered":w["offered"],
    "scored_original":w["scored_original"],"paired":w["paired"],
    **{k:w["all"].get(k) for k in fields if k in w["all"]},
    "history_start":a["first_history_year"],"training_rows":a["training_rows"]})
 print("V3_EXPERIMENT_COMPLETE",json.dumps({"status":final["status"],
  "cycles":final["cycles"],"offered":final["total_offered"],"paired":final["paired"],
  "overall":final["overall"],"receipt":final["result_sha256"],"seconds":round(time.time()-totalstart,1)}),flush=True)

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("action",choices=["run","forecast"])
 p.add_argument("--input",type=pathlib.Path)
 p.add_argument("--output",type=pathlib.Path,required=True)
 p.add_argument("--limit",type=int,default=0)
 args=p.parse_args()
 if args.action=="forecast":
  require(args.input and args.input.exists(),"NO_ISOLATED_FORECAST_PACKET")
  save(args.output,child(read(args.input),n=DRAWS))
 else:run(args.output,args.limit)
