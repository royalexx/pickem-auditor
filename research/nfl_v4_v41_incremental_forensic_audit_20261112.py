"""Independent read-only incremental V4/V4.1 settlement audit.
Uses original paired weekly contract-denominators and immutable forecast SHA.
Recomputes crossweek score weights and confidence coverage; compares
V4.1 to V4 only on common completed weeks.
This cannot certify real-world odds, authentic pregame sources or live tiers.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,pathlib,math
import numpy as np
ROOT=pathlib.Path.cwd()
BASE=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
V4=BASE/"V4_ADAPTIVE_FACTORS_10YEAR_FULL_20261112T014530Z"
V41=BASE/"V4_1_QB_REPAIR_10YEAR_FULL_20261112T020412Z"
OUT=BASE/"V4_INTERIM_INDEPENDENT_AUDIT"
OUT.mkdir(parents=True,exist_ok=True)
def read(p):
 b=p.read_bytes()
 return json.loads(gzip.decompress(b) if p.suffix==".gz" else b)
def sha(b):return hashlib.sha256(b).hexdigest()
def canon(o):return json.dumps(o,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
names={"V4":V4,"V4.1":V41}
results={}
for name,folder in names.items():
 perweek=[];allissues=[];markets=collections.defaultdict(lambda:collections.defaultdict(float))
 weight_history=[];prevfactor=prevstack=None;offer_total=paired_total=0
 for y in range(2016,2026):
  for w in range(1,19 if y>=2021 else 18):
   stem=f"{y}_week_{w:02d}"
   inp=folder/(stem+"_v4_before_outcomes.json.gz")
   pred=folder/(stem+"_v4_predictions.json.gz")
   sett=folder/(stem+"_v4_settlements.json.gz")
   if not sett.exists():continue
   if not inp.exists() or not pred.exists():
    allissues.append([y,w,"missing_frozen_file"]);continue
   p=read(inp);f=read(pred);r=read(sett)
   if sha(canon(p))!=f["input_sha256"]:allissues.append([y,w,"forecast_input_hash"])
   if sha(canon(p["factor_preimage"]))!=f["factor_preimage_sha256"]:
    allissues.append([y,w,"factor_hash"])
   if sha(canon(p["stack_preimage"]))!=f["stack_preimage_sha256"]:
    allissues.append([y,w,"stack_hash"])
   if sha(pred.read_bytes())!=r["forecast_sha256"]:
    allissues.append([y,w,"settlement_forecast_sha"])
   if prevfactor is not None and prevfactor!=p["factor_preimage"]:
    allissues.append([y,w,"factor_lookback_rollover"])
   if prevstack is not None and prevstack!=p["stack_preimage"]:
    allissues.append([y,w,"stack_lookback_rollover"])
   prevfactor=r["factor_weights_updated_only_postsettlement"]
   prevstack=r["stack_weights_updated_only_postsettlement"]
   if any(z["season"]>y or(z["season"]==y and z["week"]>=w) for z in p["history"]):
    allissues.append([y,w,"data_leak_history"])
   if any(z["season"]>y or(z["season"]==y and z["week"]>=w) for z in p["pbp_prior"]):
    allissues.append([y,w,"data_leak_play_by_play"])
   if not f["forecasts_did_not_receive_current_week_settlements"]:
    allissues.append([y,w,"forecast_saw_current_outcomes"])
   n=r["paired"]
   if r["all"]["n"]!=n:allissues.append([y,w,"denominator_mismatch"])
   offer_total+=r["original_offers"];paired_total+=n
   for market,x in r["markets"].items():
    m=markets[market];nn=x.get("n",0)
    m["n"]+=nn
    for key in ("tuned_brier","frozen_v3_brier","frozen_v2_brier",
      "player_history_brier","tuned_crps","v3_crps","tuned_hit","v3_hit",
      "mean_residual","tuned_logloss","v3_logloss"):
     if key in x:m[key]+=nn*x[key]
    for k in (70,80,90,95):
     pre="conf"+str(k)
     count=x.get(pre+"_n",0)
     m[pre+"_n"]+=count
     if count:
      m[pre+"_claimed_sum"]+=count*x[pre+"_claimed"]
      m[pre+"_hit_sum"]+=count*x[pre+"_hit"]
   q=r["all"]
   a={"year":y,"week":w,"n":n,"offered":r["original_offers"],
      "factor_v3":p["factor_preimage"]["weights"][0],
      "factor_recent":p["factor_preimage"]["weights"][1],
      "factor_long":p["factor_preimage"]["weights"][2],
      "stack_mature_weeks":max(p["stack_preimage"]["nweeks"].values(),default=0)}
   a.update(q)
   a["delta_brier"]=q["tuned_brier"]-q["frozen_v3_brier"]
   a["delta_crps"]=q["tuned_crps"]-q["v3_crps"]
   perweek.append(a)
   weight_history.append([y,w,*p["factor_preimage"]["weights"]])
 def metric(group,k):
  n=sum(x["n"] for x in group)
  return sum(x["n"]*x[k] for x in group)/n if n else None
 def summarize(group):
  if not group:return {"n":0,"weeks":0}
  d={"n":sum(x["n"] for x in group),"weeks":len(group)}
  for k in ("tuned_brier","frozen_v3_brier","frozen_v2_brier",
       "tuned_crps","v3_crps","delta_brier","delta_crps",
       "tuned_hit","v3_hit","tuned_logloss","v3_logloss","mean_residual"):
   d[k]=metric(group,k)
  for confidence_threshold in (70,80,90,95):
   pre="conf"+str(confidence_threshold)
   n=sum(x.get(pre+"_n",0) for x in group)
   d[pre+"_n"]=n
   d[pre+"_claimed"]=sum(x[pre+"_n"]*(x[pre+"_claimed"] or 0) for x in group)/n if n else None
   d[pre+"_hit"]=sum(x[pre+"_n"]*(x[pre+"_hit"] or 0) for x in group)/n if n else None
  return d
 # Keep confidence-band loop variables identical in all score aggregators.
 def marketsum(z):
  n=z["n"];d={"n":int(n)}
  if not n:return d
  for k in ("tuned_brier","frozen_v3_brier","frozen_v2_brier",
       "tuned_crps","v3_crps","tuned_hit","v3_hit","tuned_logloss","v3_logloss","mean_residual"):
   d[k]=z[k]/n
  d["brier_delta"]=d["tuned_brier"]-d["frozen_v3_brier"]
  d["crps_delta"]=d["tuned_crps"]-d["v3_crps"]
  for confidence_threshold in (70,80,90,95):
   pre="conf"+str(confidence_threshold)
   count=z[pre+"_n"];d[pre+"_n"]=int(count)
   d[pre+"_claimed"]=z[pre+"_claimed_sum"]/count if count else None
   d[pre+"_hit"]=z[pre+"_hit_sum"]/count if count else None
  return d
 result={"state":"COMPLETE" if len(perweek)==175 else "INTERIM",
   "settled_weeks":len(perweek),"offers":offer_total,
   "paired":paired_total,
   "integrity_issues":allissues[:80],"integrity_issues_count":len(allissues),
   "overall":summarize(perweek),
   "by_season":{str(y):summarize([x for x in perweek if x["year"]==y]) for y in sorted({x["year"] for x in perweek})},
   "by_market":{m:marketsum(v) for m,v in markets.items()},
   "first_week":perweek[0] if perweek else None,
   "last_week":perweek[-1] if perweek else None,
   "factor_first":weight_history[:2],"factor_last":weight_history[-2:],
   "weekly":perweek}
 results[name]=result
 print("MODEL_AUDIT",name,"weeks",len(perweek),"paired",paired_total,
    "issues",len(allissues),"overall",json.dumps(result["overall"]),
    "byyear",json.dumps({k:{"n":z["n"],"delta":z.get("delta_brier")} for k,z in result["by_season"].items()}),
    "last_weights",weight_history[-1:] if weight_history else [],flush=True)
def sum_common(d,name):
 common=set((x["year"],x["week"]) for x in results["V4"]["weekly"])&set((x["year"],x["week"]) for x in results["V4.1"]["weekly"])
 cohort=[x for x in results[name]["weekly"] if (x["year"],x["week"]) in common]
 return common,cohort
common,rs4=sum_common(results,"V4")
_,rs41=sum_common(results,"V4.1")
aa=sum(x["n"] for x in rs4);bb=sum(x["n"] for x in rs41)
assert aa==bb
d=sum(x["n"]*(x["tuned_brier"]-y["tuned_brier"]) for x,y in zip(rs41,rs4))/bb
dh=sum(x["n"]*(x["tuned_hit"]-y["tuned_hit"]) for x,y in zip(rs41,rs4))/bb
cross={"weeks":len(common),"paired":bb,"v41_minus_v4_brier":d,"v41_minus_v4_hit":dh}
print("COMMON_PAIRED",json.dumps(cross),flush=True)
report={"status":"INTERIM_INDEPENDENT_RESEARCH_ONLY",
 "models":results,"common":cross,
 "limitations":["Only completed weekly settlements; no claim of complete 175-week results if count<175",
 "Synthetic historical contract lines, retroactively collected player stats",
 "Paired validation conditional on official observations; unplayed players missing",
 "CRPS aggregated across markets with incompatible units: use market-specific differences",
 "No production model promotion or real sportsbook ROI"]}
(OUT/"V4_V41_INTERIM_FORENSIC_REPORT.json").write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False))
for name,r in results.items():
 with (OUT/(name.replace(".","_")+"_WEEKLY.csv")).open("w",newline="") as f:
  keys=["year","week","n","offered","delta_brier","delta_crps",
   "tuned_brier","frozen_v3_brier","frozen_v2_brier","tuned_hit","v3_hit",
   "conf70_n","conf70_claimed","conf70_hit","conf80_n","conf80_claimed","conf80_hit",
   "factor_v3","factor_recent","factor_long","stack_mature_weeks"]
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
  for z in r["weekly"]:w.writerow({k:z.get(k) for k in keys})
