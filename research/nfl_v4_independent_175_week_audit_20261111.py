"""Independent V4 175-week forensic audit; no model fitting and no production writes.

Loads completed V4 forecast/settlement receipts and original official retrospective
settlements on exactly paired contracts, checks score arithmetic, evaluates all
13 markets, 175 weeks and game/week-clustered paired uncertainty.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,math,pathlib,sys
import numpy as np
ROOT=pathlib.Path.cwd()
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
STUDIES=sorted(BASE.glob("V4_ADAPTIVE_FACTORS_10YEAR_FULL_*"))
if len(STUDIES)!=1:raise RuntimeError("Unique completed V4 study required: "+str(STUDIES))
STUDY=STUDIES[0]
OLD=BASE/"EXP_ALL13_20261111T200951Z"
OUT=BASE/"V4_ADAPTIVE_FACTORS_INDEPENDENT_AUDIT"
OUT.mkdir(parents=True,exist_ok=True)
def read(p):
 b=p.read_bytes()
 return json.loads(gzip.decompress(b) if p.suffix==".gz" else b)
def canon(v):return json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
result=read(STUDY/"V4_FINAL_DECADE_RESEARCH_REPORT.json")
assert result["cycles"]==175 and result["completion"]=="COMPLETE_RESEARCH_ONLY"
issues=collections.Counter(); examples=collections.defaultdict(list)
allmatches=[];weekrows=[];by_market=collections.defaultdict(list)
original_sha=read(OLD/"FINAL_2016_2025_RESEARCH_REPORT.json")["result_sha256"]
if result["original_source_receipt"]["production_authorized"]:issues["unexpected_production_approval"]+=1
last_factor_after=None;last_stack_after=None
weight_series=[]
top10=collections.Counter()
for entry in result["receipts"]:
 y,w=entry["season"],entry["week"]
 stem=f"{y}_week_{w:02d}"
 pin=STUDY/(stem+"_v4_before_outcomes.json.gz")
 pp=STUDY/(stem+"_v4_predictions.json.gz")
 ps=STUDY/(stem+"_v4_settlements.json.gz")
 for path,label in ((pin,"preweek_sha256"),(pp,"forecast_sha256"),(ps,"settlement_sha256")):
  if not path.exists():issues["missing_week_file"]+=1;continue
  if sha(path.read_bytes())!=entry[label]:issues["weekly_sha_invalid"]+=1
 frozen=read(pin);forecast=read(pp);settled=read(ps)
 if forecast["input_sha256"]!=sha(canon(frozen)):issues["forecast_input_not_bound"]+=1
 if forecast["factor_preimage_sha256"]!=sha(canon(frozen["factor_preimage"])):
  issues["factor_preimage_not_bound"]+=1
 if forecast["stack_preimage_sha256"]!=sha(canon(frozen["stack_preimage"])):
  issues["stack_preimage_not_bound"]+=1
 if settled["preweek_sha256"]!=entry["preweek_sha256"]:
  issues["settlement_frozen_input_mismatch"]+=1
 if settled["forecast_sha256"]!=entry["forecast_sha256"]:
  issues["settlement_frozen_forecast_mismatch"]+=1
 if last_factor_after is not None and canon(frozen["factor_preimage"])!=canon(last_factor_after):
  issues["weekly_factor_state_rollover_mismatch"]+=1
 if last_stack_after is not None and canon(frozen["stack_preimage"])!=canon(last_stack_after):
  issues["weekly_stack_state_rollover_mismatch"]+=1
 last_factor_after=settled["factor_weights_updated_only_postsettlement"]
 last_stack_after=settled["stack_weights_updated_only_postsettlement"]
 hist=frozen["history"]
 if not hist or any(g["season"]>y or(g["season"]==y and g["week"]>=w) for g in hist):
  issues["current_week_outcome_leak_in_history"]+=1
 if min(g["season"] for g in hist)<max(2014,y-10):
  issues["tenyear_limit_violation"]+=1
 if any(g["season"]>y or(g["season"]==y and g["week"]>=w) for g in frozen["pbp_prior"]):
  issues["future_play_by_play"]+=1
 if frozen["pregame_certified"] is not False:issues["source_pregame_mislabel"]+=1
 if not forecast["forecasts_did_not_receive_current_week_settlements"]:
  issues["forecast_has_current_week_outcomes"]+=1
 odds=np.asarray(frozen["factor_preimage"]["weights"],dtype=float)
 if not np.isclose(odds.sum(),1):issues["factor_weights_not_sum_one"]+=1
 weight_series.append({"season":y,"week":w,"weight_v3":float(odds[0]),
  "weight_recent":float(odds[1]),"weight_long":float(odds[2]),
  "weeks_prior":frozen["factor_preimage"]["weeks_prior"]})
 predby={(z["game_id"],z["team"],z["player_id"],z["market"]):z for z in forecast["offers"]}
 if len(predby)!=len(forecast["offers"]):issues["duplicate_offer"]+=1
 old=read(OLD/(stem+"_settlements.json.gz"))
 truthby={(z["game_id"],z["team"],z["player_id"],z["market"]):z
         for z in old["scored"] if z.get("status")=="scored_as_same_contract"}
 if len(predby)!=len(old["scored"]):issues["offered_contract_denom_mismatch"]+=1
 # Point-in-time top 10: choose from offered set BEFORE looking up outcomes.
 pref=[z for z in forecast["offers"] if z["status"]=="forecast"]
 chosen=sorted(pref,key=lambda f:max(f["p_over_tuned"],1-f["p_over_tuned"]),reverse=True)[:10]
 for f in chosen:
  top10["offered_selected"]+=1
  row=truthby.get((f["game_id"],f["team"],f["player_id"],f["market"]))
  if row is None:top10["unmatched_selected"]+=1;continue
  top10["matched_selected"]+=1
  top10["confidence_sum"]+=max(f["p_over_tuned"],1-f["p_over_tuned"])
  top10["correct_selected"]+=int((f["p_over_tuned"]>.5)==bool(row["observed_over"]))
 group=[]
 for k,f in predby.items():
  z=truthby.get(k)
  if z is None or f["status"]!="forecast" or \
   any(k not in z["model_scores"] for k in ("shared_opportunity","player_history")):
   continue
  market=f["market"];p=f["p_over_tuned"];base=f["original_v3_p_online"];v2=z["model_scores"]["shared_opportunity"]["p_over_online"]
  yy=int(z["observed_over"])
  if not (0<p<1):issues["invalid_tuned_probability"]+=1
  brier_t=(p-yy)**2;brier_b=(base-yy)**2
  d=np.sort(np.asarray(f["draws"],dtype=float))
  qcrps=float(np.mean(np.abs(d-z["actual"]))-np.dot(2*np.arange(len(d))-len(d)+1,d)/len(d)**2)
  group.append({"season":y,"week":w,"game":f["game_id"],"market":market,
   "role":f["role"],"brier_tuned":brier_t,"brier_v3":brier_b,
   "delta_brier":brier_t-brier_b,
   "hit_tuned":int((p>.5)==bool(yy)),"hit_v3":int((base>.5)==bool(yy)),
   "delta_hit":int((p>.5)==bool(yy))-int((base>.5)==bool(yy)),
   "crps_tuned":qcrps,"p_tuned":p,"confidence":max(p,1-p),
   "actual":z["actual"],"p_over_v2":v2,"y":yy,
   "mean_bias":f["predicted_mean"]-z["actual"],
   "factor_fallback":f["factor_fallback"]})
  by_market[market].append(group[-1])
 allmatches.extend(group)
 n=len(group)
 if n!=settled["paired"]:issues["weekly_paired_count_mismatch"]+=1
 if n:
  calculated=float(np.mean([r["brier_tuned"] for r in group]))
  if abs(calculated-settled["all"]["tuned_brier"])>1e-10:
   issues["weekly_brier_math_mismatch"]+=1
  check_crps=float(np.mean([r["crps_tuned"] for r in group]))
  if abs(check_crps-settled["all"]["tuned_crps"])>1e-8:
   issues["weekly_crps_math_mismatch"]+=1
  weekrows.append({"season":y,"week":w,"n":n,
    "brier_tuned":calculated,
    "brier_v3":float(np.mean([r["brier_v3"] for r in group])),
    "delta_brier":float(np.mean([r["delta_brier"] for r in group])),
    "hit_tuned":float(np.mean([r["hit_tuned"] for r in group])),
    "hit_v3":float(np.mean([r["hit_v3"] for r in group])),
    "crps_tuned":check_crps,
    "confidence_over80_count":sum(r["confidence"]>=.8 for r in group),
    **{k:float(v) for k,v in weight_series[-1].items() if k.startswith("weight_")}})
 print("V4_AUDIT_WEEK_COMPLETE",y,w,"paired",n,flush=True) if w in (1,9,18) else None

if len(weekrows)!=175 or len(allmatches)!=result["total_paired"]:
 issues["global_paired_cohort_mismatch"]+=1
def summarize(records):
 n=len(records)
 if not n:return {"n":0}
 a={"n":n}
 for name in ("brier_tuned","brier_v3","delta_brier","hit_tuned","hit_v3","delta_hit","crps_tuned","mean_bias"):
  a[name]=float(np.mean([r[name] for r in records]))
 for t in (.7,.8,.9,.95):
  sel=[r for r in records if r["confidence"]>=t]
  k="conf"+str(int(t*100))
  a[k+"_n"]=len(sel)
  a[k+"_claimed"]=float(np.mean([r["confidence"] for r in sel])) if sel else None
  a[k+"_hit"]=float(np.mean([r["hit_tuned"] for r in sel])) if sel else None
 return a
overall=summarize(allmatches)
byyear={str(y):summarize([z for z in allmatches if z["season"]==y]) for y in range(2016,2026)}
bymarket={m:summarize(z) for m,z in by_market.items()}
first_half=summarize([r for r in allmatches if r["season"]<=2020])
last_half=summarize([r for r in allmatches if r["season"]>=2021])
bycluster=collections.defaultdict(list)
for r in allmatches:bycluster[(r["season"],r["week"],r["game"])].append(r)
def bootstrap(groups,reps=3500):
 g=list(groups.values());count=np.asarray([len(z) for z in g])
 db=np.asarray([sum(z["delta_brier"] for z in a) for a in g])
 dh=np.asarray([sum(z["delta_hit"] for z in a) for a in g])
 rng=np.random.default_rng(131299)
 vals=[];hits=[]
 for _ in range(reps):
  ix=rng.integers(0,len(g),len(g));den=count[ix].sum()
  vals.append(float(db[ix].sum()/den));hits.append(float(dh[ix].sum()/den))
 return {"clusters":len(g),"brier_ci95":np.quantile(vals,[.025,.975]).tolist(),
   "hit_ci95":np.quantile(hits,[.025,.975]).tolist()}
weekgroups=collections.defaultdict(list)
for r in allmatches:weekgroups[(r["season"],r["week"])].append(r)
clusters={"week":bootstrap(weekgroups),"game":bootstrap(bycluster)}
tol=1e-9
if abs(overall["brier_tuned"]-result["overall"]["tuned_brier"])>tol:
 issues["global_brier_mismatch"]+=1
if abs(overall["crps_tuned"]-result["overall"]["tuned_crps"])>tol:
 issues["global_crps_mismatch"]+=1
if abs(overall["hit_tuned"]-result["overall"]["tuned_hit"])>tol:
 issues["global_hit_mismatch"]+=1
data={"status":"RESEARCH_ONLY_INDEPENDENT_V4_AUDIT_FINISHED",
 "issues":dict(issues),"weeks":len(weekrows),"total_paired":len(allmatches),
 "overall":overall,"season":byyear,"markets":bymarket,
 "early_2016_2020":first_half,"late_2021_2025":last_half,
 "clustered_difference":clusters,"factor_weights_first":weight_series[:3],
 "factor_weights_last":weight_series[-3:],"early_vs_late_delta_brier":last_half["delta_brier"]-first_half["delta_brier"],
 "weeks_tuned_better":sum(r["delta_brier"]<0 for r in weekrows),
 "top10_pregame_selected_offers":dict(top10),
 "source_pregame_certified":False,
 "synthetic_lines":True,"production_approved":False,
 "notes":["This compares the SAME original matched contracts across V4 and V3",
 "V4 stacked confidence is scored separately from its scenario distribution CRPS",
 "The first time later seasons have been visited is not this run; they are development-exposed",
 "Weekly and game resampling respects cross-prop correlation",
 "No actual sportsbook odds, injuries, starters or ROI certification"]}
(OUT/"V4_INDEPENDENT_175_WEEK_AUDIT.json").write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False))
def csvfile(path,rows):
 keys=sorted(set().union(*(z.keys() for z in rows)))
 with path.open("w",newline="") as f:
  ww=csv.DictWriter(f,fieldnames=keys);ww.writeheader()
  for row in rows:
   ww.writerow({k:(json.dumps(v) if isinstance(v,dict) else v) for k,v in row.items()})
csvfile(OUT/"V4_175_WEEK_RECONCILED_SCORECARDS.csv",weekrows)
csvfile(OUT/"V4_175_WEEK_FACTOR_WEIGHTS.csv",weight_series)
with (OUT/"V4_13_MARKET_SUMMARY.csv").open("w",newline="") as f:
 keys=["market","n","brier_tuned","brier_v3","delta_brier","hit_tuned","hit_v3","delta_hit","crps_tuned","conf80_n","conf80_hit","conf80_claimed"]
 writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
 for k,v in sorted(bymarket.items()):writer.writerow({"market":k,**{kk:v.get(kk) for kk in keys if kk!="market"}})
print("V4_FORENSIC_COMPLETE",json.dumps({"issues":dict(issues),"total":len(allmatches),
 "overall":overall,"early":first_half,"late":last_half,"clusters":clusters,
 "market_delta":{k:{"n":v["n"],"brier_delta":v["delta_brier"],"hit_delta":v["delta_hit"],"conf80_n":v["conf80_n"]} for k,v in bymarket.items()},
 "last_factor_weights":weight_series[-1],"top10":dict(top10)},sort_keys=True),flush=True)
