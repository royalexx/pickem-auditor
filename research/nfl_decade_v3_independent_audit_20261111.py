"""Independent final V3 vs original paired weekly forensic audit, no model fitting."""
from __future__ import annotations
import csv,gzip,hashlib,json,math,pathlib,collections
import numpy as np

ROOT=pathlib.Path.cwd()
PARENT=ROOT/"reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111"
LEGACY=PARENT/"EXP_ALL13_20261111T200951Z"
NEW=PARENT/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z"
OUT=PARENT/"V3_CONTEXT_10YEAR_AUDIT"
OUT.mkdir(parents=True,exist_ok=True)
read=lambda p:json.loads(gzip.open(p,"rb").read() if str(p).endswith(".gz") else p.read_bytes())
canonical=lambda x:json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
sha=lambda b:hashlib.sha256(b).hexdigest()
s=read(NEW/"FINAL_V3_VS_V2_10YEAR_REPORT.json")
legacy=read(LEGACY/"FINAL_2016_2025_RESEARCH_REPORT.json")
assert s["cycles"]==175 and s["status"]=="RESEARCH_ONLY_COMPLETED"
assert s["source_receipt"]["legacy_frozen_replay_sha256"]==legacy["result_sha256"]
assert s["source_receipt"]["historical_source_capture_verified"] is False
assert s["production_allowed"] is False
W=s["weekly_archive"]
issues=collections.Counter()
rows=[]
high=collections.defaultdict(list)
top=collections.Counter()
QB=collections.Counter()
for i,entry in enumerate(W):
 y,w=entry["year"],entry["week"];stem=f"{y}_week_{w:02d}"
 pi=NEW/(stem+"_v3_before_outcomes.json.gz")
 pp=NEW/(stem+"_v3_predictions.json.gz")
 po=NEW/(stem+"_v3_settlements.json.gz")
 for path,k in [(pi,"preweek_sha256"),(pp,"forecast_sha256"),(po,"settlement_sha256")]:
  if not path.exists():issues["missing_weekly_file"]+=1;continue
  if sha(path.read_bytes())!=entry[k]:issues["invalid_weekly_archive_hash"]+=1
 packet=read(pi);pred=read(pp);result=read(po)
 assert len(packet["contracts"])==len(pred["offers"])==result["offered"]
 if sha(canonical(packet["calibration_preimage"]))!=entry["preweek_calibrator_sha256"]:
  issues["calibrator_before_update_mismatch"]+=1
 if pred["calibration_preimage_sha256"]!=sha(canonical(packet["calibration_preimage"])):
  issues["prediction_has_mutated_calibrator"]+=1
 if pred["input_sha256"]!=sha(canonical(packet)):
  issues["forecast_input_mismatch"]+=1
 if result["new_forecast_sha256"]!=sha(pp.read_bytes()):
  issues["outcome_forecast_mismatch"]+=1
 if any(z["season"]>y or(z["season"]==y and z["week"]>=w) for z in packet["history"]):
  issues["historical_outcome_feature_leak"]+=1
 if any(z["season"]>y or(z["season"]==y and z["week"]>=w) for z in packet["pbp_prior"]):
  issues["historical_PBP_feature_leak"]+=1
 if min(z["season"] for z in packet["history"])<max(2014,y-10):
  issues["beyond_10yr_context"]+=1
 if tuple(pred["model_training"]["latest_training_year_week"]) >= (y,w):
  issues["regression_trained_on_future"]+=1
 if len(pred["game_context"])!=len({z["game_id"] for z in packet["games"]}):
  issues["missing_game_simulation"]+=1
 current=result["all"]
 r={"year":y,"week":w,"offered":result["offered"],"scored":result["scored_original"],
    "paired":result["paired"],"history_first_year":entry["first_history_year"],
    "training_rows":entry["training_rows"],**current}
 for key in ("brier_new","brier_v2_joint","brier_v2_history","crps_new","crps_v2_joint","crps_v2_history",
            "logloss_new","logloss_v2_joint","logloss_v2_history","hit_new","hit_v2_joint"):
  if key not in r:issues["missing_score_field"]+=1
 r["delta_brier_new_minus_v2"]=r["brier_new"]-r["brier_v2_joint"]
 r["delta_crps_new_minus_v2"]=r["crps_new"]-r["crps_v2_joint"]
 r["delta_brier_pure_v3_minus_v2"]=r["brier_v3_pure"]-r["brier_v2_joint"]
 rows.append(r)
 for level in (70,80,90,95):
  k=f"conf{level}";nn=current.get(k+"_n",0)
  if nn:
   high[level].append({"year":y,"week":w,"n":nn,
    "success":nn*current[k+"_hit"],"claim":nn*current[k+"_claimed"]})
 QB["old_eligible_game_teams"]+=len(packet["qb1"])
 QB["proxy_overrides"]+=sum(bool(f.get("qb_proxy_override")) for f in pred["offers"])
 QB["total_v3_forecast_contracts"]+=sum(f["status"]=="forecast" for f in pred["offers"])
 # Fixed pregame candidate selection, not post-hoc matched top-10.
 ordered=sorted([f for f in pred["offers"] if f["status"]=="forecast"],
  key=lambda f: max(f["p_over_online"],1-f["p_over_online"]),reverse=True)
 selected=ordered[:10]
 original_scores=read(LEGACY/(stem+"_settlements.json.gz"))
 oracle={(a["game_id"],a["team"],a["player_id"],a["market"]):a for a in original_scores["scored"]
         if a.get("status")=="scored_as_same_contract"}
 for f in selected:
  key=(f["game_id"],f["team"],f["player_id"],f["market"])
  top["selected"]+=1
  a=oracle.get(key)
  if a is None:
   top["unmatched"]+=1
   continue
  p=f["p_over_online"];actual=a["observed_over"]
  top["matched"]+=1
  top["hits"]+=int((p>.5)==bool(actual))
  top["claims_sum"]+=max(p,1-p)

def sum_metrics(v):
 n=sum(w["paired"] for w in v)
 def weigh(col):
  return sum(w["paired"]*w.get(col,0.) for w in v)/n if n else None
 return {"n":n,"weeks":len(v),"brier_new":weigh("brier_new"),"brier_v2_joint":weigh("brier_v2_joint"),
  "brier_v2_history":weigh("brier_v2_history"),
  "delta_brier":weigh("delta_brier_new_minus_v2"),
  "delta_pure_brier":weigh("delta_brier_pure_v3_minus_v2"),
  "crps_new":weigh("crps_new"),"crps_v2_joint":weigh("crps_v2_joint"),
  "delta_crps":weigh("delta_crps_new_minus_v2"),
  "logloss_new":weigh("logloss_new"),"logloss_v2_joint":weigh("logloss_v2_joint"),
  "hit_new":weigh("hit_new"),"hit_v2_joint":weigh("hit_v2_joint")}
full=sum_metrics(rows)
byyear={str(y):sum_metrics([r for r in rows if r["year"]==y]) for y in range(2016,2026)}
market=[]
for m in s["markets"]:
 x=s["markets"][m]
 if not x:continue
 market.append({"market":m,"n":x["n"],"brier_v3":x["brier_new"],
  "brier_v2":x["brier_v2_joint"],
  "brier_control":x["brier_v2_history"],
  "brier_pure_v3":x["brier_v3_pure"],
  "delta_brier":x["brier_new"]-x["brier_v2_joint"],
  "crps_v3":x["crps_new"],"crps_v2":x["crps_v2_joint"],
  "delta_crps":x["crps_new"]-x["crps_v2_joint"],
  "hit_v3":x["hit_new"],"hit_v2":x["hit_v2_joint"],
  "mean_bias_v3":x["count_mean_bias"],"claim80":x["conf80_claimed"],
  "hit80":x["conf80_hit"],"n80":x["conf80_n"]})
market=sorted(market,key=lambda x:x["delta_brier"])
rng=np.random.default_rng(1131177)
def bootstrap_cluster(weekly,key="delta_brier_new_minus_v2",reps=4000):
 xx=np.asarray([r[key] for r in weekly]);nn=np.asarray([r["paired"] for r in weekly])
 res=np.empty(reps)
 for i in range(reps):
  ix=rng.integers(0,len(xx),len(xx))
  res[i]=np.dot(xx[ix],nn[ix])/nn[ix].sum()
 return {"ci95":np.quantile(res,[.025,.975]).tolist(),
   "prob_delta_lt_zero":float(np.mean(res<0)), "clusters":len(xx),
   "point":float(np.dot(xx,nn)/nn.sum())}
boot=bootstrap_cluster(rows)
conf={}
for level,vals in high.items():
 totals=sum(z["n"] for z in vals)
 claimed=sum(z["claim"] for z in vals)/totals
 hit=sum(z["success"] for z in vals)/totals
 bs=[]
 for _ in range(3500):
  ix=rng.integers(0,len(vals),len(vals))
  ss=[vals[i] for i in ix]; den=sum(x["n"] for x in ss)
  bs.append(sum(x["success"]-x["claim"] for x in ss)/den)
 conf[str(level)]={"n":totals,"claimed":claimed,"hit":hit,
   "gap":hit-claimed,"week_cluster_gap_ci95":np.quantile(bs,[.025,.975]).tolist(),
   "weeks":len(vals)}
# Audit a simple precommitted confidence-only shrinkage alternative to isolate
# whether the new context contributes beyond making V2 less extreme.
baseline=collections.Counter()
for entry in W:
 y,w=entry["year"],entry["week"];stem=f"{y}_week_{w:02d}"
 pp=read(NEW/(stem+"_v3_predictions.json.gz"))
 original_scores=read(LEGACY/(stem+"_settlements.json.gz"))
 oracle={(a["game_id"],a["team"],a["player_id"],a["market"]):a for a in original_scores["scored"]
         if a.get("status")=="scored_as_same_contract"}
 for f in pp["offers"]:
  if f["status"]!="forecast":continue
  a=oracle.get((f["game_id"],f["team"],f["player_id"],f["market"]))
  if not a or not all(z in a["model_scores"] for z in ("shared_opportunity","player_history")):continue
  old=a["model_scores"]["shared_opportunity"]["p_over_online"]
  actual=a["observed_over"]
  baseline["n"]+=1
  baseline["v2_brier"]+=(old-actual)**2
  for retain in (.9,.75):
   p=.5+(old-.5)*retain
   baseline[f"shrink_{retain}_brier"]+=(p-actual)**2
  baseline["new_brier"]+=(f["p_over_online"]-actual)**2
if int(baseline["n"])!=full["n"]:issues["shrink_cohort_mismatch"]+=1
shrinks={k:float(v/baseline["n"]) for k,v in baseline.items() if k!="n"}
shrinks["n"]=int(baseline["n"])
assert full["n"]==s["paired"]
assert full["weeks"]==175
report={"status":"INDEPENDENT_AUDIT_DONE_RESEARCH_ONLY","integrity_issues":dict(issues),
 "source_is_original_pregame_certified":False,
 "all":full,"week_cluster_bootstrap":boot,"by_season":byyear,
 "markets":market,"calibration":conf,"top10_selected_before_outcomes":dict(top),
 "QB":dict(QB),"confidence_only_shrink_ablation":shrinks,
 "weekly_joint_v3_better":sum(r["delta_brier_new_minus_v2"]<0 for r in rows),
 "weekly_joint_v3_worse":sum(r["delta_brier_new_minus_v2"]>0 for r in rows),
 "constraints":["Legacy V2 baseline itself fitted with only three years of historical game records",
 "V3 modeled ten-year recency-weighted population and regression context but ensemble retains 75% legacy distributions",
 "2026 retrospective data, no genuine historical sportsbook lines or authenticated source publication",
 "High-confidence model certification prohibited without correctly calibrated prospective evidence",
 "Correlated contracts; bootstrap over weeks rather than assuming independent legs"],
 "worst_weeks":sorted(rows,key=lambda x:x["delta_brier_new_minus_v2"],reverse=True)[:12],
 "best_weeks":sorted(rows,key=lambda x:x["delta_brier_new_minus_v2"])[:12]}
def write(name,obj):
 (OUT/name).write_text(json.dumps(obj,indent=2,sort_keys=True,default=str,allow_nan=False))
def tabular(name,data):
 if not data:return
 fields=sorted(set().union(*(x.keys() for x in data)))
 with (OUT/name).open("w",newline="") as file:
  w=csv.DictWriter(file,fieldnames=fields);w.writeheader()
  for x in data:w.writerow(x)
write("V3_DECADE_INDEPENDENT_AUDIT.json",report)
tabular("V3_ALL_175_WEEKLY_AUDIT.csv",sorted(rows,key=lambda x:(x["year"],x["week"])))
tabular("V3_13_MARKET_AUDIT.csv",market)
intro=["# V3 opponent-aware ten-year research replay: 175-week independent audit","",
 "NOT a certified pregame sportsbook backtest; no model promoted.",
 f"- Integrity issues: {dict(issues)}",
 f"- Paired scored: {full['n']:,} across {full['weeks']} weeks",
 f"- Brier: V3 ensemble {full['brier_new']:.6f}; original V2 {full['brier_v2_joint']:.6f}; difference {full['delta_brier']:+.6f}",
 f"- Log loss: V3 {full['logloss_new']:.6f}; V2 {full['logloss_v2_joint']:.6f}",
 f"- CRPS (UNNORMALIZED, different units across markets): V3 {full['crps_new']:.5f}; V2 {full['crps_v2_joint']:.5f}",
 f"- Week-clustered 95% difference interval: {boot['ci95']}",
 f"- Confidence-only shrinkage baseline: {shrinks}","",
 "## By season","",
 "| Season | N | V3 Brier | V2 Brier | Delta | V3 vs V2 CRPS Δ |",
 "|---|---:|---:|---:|---:|---:|"]
for y,v in byyear.items():
 intro.append(f"| {y} | {v['n']:,} | {v['brier_new']:.4f} | {v['brier_v2_joint']:.4f} | {v['delta_brier']:+.4f} | {v['delta_crps']:+.4f} |")
intro+=["","## By market","",
 "| Market | N | V3 Brier | V2 Brier | Delta | CRPS delta | V3 80% hit vs claimed |",
 "|---|---:|---:|---:|---:|---:|---|"]
for m in market:
 h=(f"{m['hit80']:.1%} vs {m['claim80']:.1%}" if m["hit80"] is not None else "N/A")
 intro.append(f"| {m['market']} | {m['n']:,} | {m['brier_v3']:.4f} | {m['brier_v2']:.4f} | {m['delta_brier']:+.4f} | {m['delta_crps']:+.4f} | {h} |")
intro+=["","## High-confidence reliability","",
 "| Threshold | N | Claimed | Hit | Gap | Week-cluster gap interval |",
 "|---|---:|---:|---:|---:|---:|"]
for k,d in sorted(conf.items()):
 intro.append(f"| {k}% | {d['n']:,} | {d['claimed']:.1%} | {d['hit']:.1%} | {d['gap']:+.1%} | [{d['week_cluster_gap_ci95'][0]:+.1%}, {d['week_cluster_gap_ci95'][1]:+.1%}] |")
intro+=["","## Limitations and next actions","",
 "- A scenario mixture is not a fully re-trained standalone ten-year model. The legacy component still uses three-year histories.",
 "- Original research lines are synthetic, historical source timestamps are not authenticated as-of pregame.",
 "- The old 26.1% unmatched universe must stay in the denominator; the new pregame top-ten count includes unmatched offers.",
 "- Study residual biases separately by market and by role; prevent overconfident Tier release.",
 "- Do not infer sports-book profitability or automatic model promotion from any Brier gain.",
 ""]
(OUT/"V3_FULL_AUDIT.md").write_text("\n".join(intro))
print("INDEPENDENT_V3_DECADE_AUDIT_COMPLETE",json.dumps({
 "integrity":dict(issues),"overall":full,"boot":boot,"market":[{k:v for k,v in m.items() if k in ("market","n","delta_brier","delta_crps","hit80","claim80")} for m in market],
 "high":conf,"top10":dict(top),"QB":dict(QB),
 "shrink_only":shrinks,"week_wins":report["weekly_joint_v3_better"]},default=str),flush=True)
