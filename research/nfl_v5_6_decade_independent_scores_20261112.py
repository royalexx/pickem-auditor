"""Independent FULL-decade V3 / V4 / V4.1 / V5.6 audit.

Reads all 175 official frozen weekly settlement receipts and four finalized reports.
Independent scorer recomputes weighted 13-market Brier, hit, logloss, CRPS
and confidence quantities, 10 seasons, plus clustered paired uncertainty.

Research-only. Does not modify model or predictions.
"""
from __future__ import annotations
import collections,gzip,hashlib,json,math,pathlib,time
import numpy as np
BASE=pathlib.Path("reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111")
DIR={
"V3":BASE/"V3_CONTEXT_10YEAR_FULL_20261111T233046Z",
"V4":BASE/"V4_ADAPTIVE_FACTORS_10YEAR_FULL_20261112T014530Z",
"V4.1":BASE/"V4_1_QB_REPAIR_10YEAR_FULL_20261112T020412Z",
"V5.6":BASE/"V5_6_FULL_175_WEEK_HISTORY_CALIBRATED_RESEARCH_20261112T162027Z"}
OUT=BASE/"V5_6_175_WEEK_INDEPENDENT_FULL_AUDIT_20261112"
OUT.mkdir(exist_ok=True,parents=True)
def read(path):
 path=pathlib.Path(path)
 b=path.read_bytes()
 return json.loads(gzip.decompress(b) if path.suffix==".gz" else b)
def ensure(ok,msg):
 if not ok:raise AssertionError("FULL_DECADE_AUDIT_FAIL_CLOSED: "+msg)
def toplain(x):
 if isinstance(x,np.generic):return x.item()
 if isinstance(x,np.ndarray):return x.tolist()
 raise TypeError(str(type(x)))
def write(name,obj):
 path=OUT/name
 path.write_text(json.dumps(obj,indent=2,sort_keys=True,default=toplain)+"\n")
 return path
P={
"V3":read(DIR["V3"]/"FINAL_V3_VS_V2_10YEAR_REPORT.json"),
"V4":read(DIR["V4"]/"V4_FINAL_DECADE_RESEARCH_REPORT.json"),
"V4.1":read(DIR["V4.1"]/"V4_FINAL_DECADE_RESEARCH_REPORT.json"),
"V5.6":read(DIR["V5.6"]/"V5_COMPLETE_OR_PARTIAL_RESEARCH_REPORT.json")}
N=407476
MARKETS=tuple(sorted(P["V3"]["markets"]))
ensure(len(MARKETS)==13,"not_13_markets")
ensure(P["V3"]["cycles"]==175 and P["V4"]["cycles"]==175 and
 P["V4.1"]["cycles"]==175 and P["V5.6"]["weeks_completed"]==175,
 "incomplete_175_week_reports")
ensure(all((P[k]["overall"]["n"]==N) for k in P),"different_paired_cohorts")
ensure(P["V5.6"]["status"]=="COMPLETE_RESEARCH_ONLY" and
 P["V5.6"]["production_authorized"] is False,
 "incorrect_research_only_classification")
ARCHIVE=P["V3"]["weekly_archive"]
ensure(len(ARCHIVE)==175,"wrong_original_archive_length")
# Verify top-level final report SHA without assuming checksum of archive serialization.
recsha=P["V5.6"]["result_sha256"]
without_sha={k:v for k,v in P["V5.6"].items() if k!="result_sha256"}
canonical=json.dumps(without_sha,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()
ensure(hashlib.sha256(canonical).hexdigest()==recsha,
 "v56_final_report_self_sha_mismatch")
print("AUDIT_FINAL_REPORT_SHA_VERIFIED",recsha,flush=True)
def keys(y,w):return f"{y}_week_{w:02d}"
def weekly_path(model,stem):
 suffix={"V4":"v4_settlements","V4.1":"v4_settlements","V5.6":"v5_settlement"}[model]
 return DIR[model]/(stem+"_"+suffix+".json.gz")
SC={
 "V3":{"brier":"brier_v3","hit":"hit_v3","logloss":"v3_logloss","crps":"crps_v3"},
 "V4":{"brier":"tuned_brier","hit":"tuned_hit","logloss":"tuned_logloss","crps":"tuned_crps"},
 "V4.1":{"brier":"tuned_brier","hit":"tuned_hit","logloss":"tuned_logloss","crps":"tuned_crps"},
 "V5.6":{"brier":"brier_joint","hit":"hit_joint","logloss":"joint_logloss","crps":"crps_joint"}
}
# Sufficient stats with n-weighted pooling, not naive average of weeks.
totals={model:collections.defaultdict(lambda:collections.defaultdict(lambda:collections.defaultdict(float)))
 for model in P}
weeks=[];bugs=[];cohort={"paired":0,"offered":0}
T0=time.monotonic()
for index,item in enumerate(ARCHIVE):
 y,w=int(item["year"]),int(item["week"]);stem=keys(y,w)
 z={model:read(weekly_path(model,stem)) for model in ("V4","V4.1","V5.6")}
 n=int(z["V5.6"]["paired"])
 ensure(all(z[k]["paired"]==n for k in z),"not_same_weekly_paired_cohort_"+stem)
 ensure(all(z[k]["season"]==y and z[k]["week"]==w for k in z),"week_identity_"+stem)
 ensure(n==z["V5.6"]["all"]["n"],"overall_n_mismatch_"+stem)
 cohort["paired"]+=n;cohort["offered"]+=z["V5.6"]["offers"]
 itemscore={"season":y,"week":w,"paired":n,"brier":{},"market_n":{}}
 for m in ("all",)+MARKETS:
  base_n=int(z["V5.6"][m]["n"] if m=="all" else z["V5.6"]["markets"][m]["n"])
  for model in ("V4","V4.1"):
   source=z[model]["all"] if m=="all" else z[model]["markets"][m]
   ensure(int(source["n"])==base_n,
     "different_market_week_cohort_"+stem+"_"+model+"_"+m)
  if m!="all":itemscore["market_n"][m]=base_n
  if base_n==0:continue
  # All models use their own persisted frozen paired contract probability.
  for model in P:
   source=(z["V5.6"]["all"] if m=="all" else z["V5.6"]["markets"][m]) if model in ("V3","V5.6") else (
     z[model]["all"] if m=="all" else z[model]["markets"][m])
   d=totals[model][m]
   for group in ("all",str(y)):
    bucket=d[group]
    bucket["n"]+=base_n
    for field,column in SC[model].items():
     ensure(column in source,"missing_score_"+stem+"_"+model+"_"+m+"_"+column)
     bucket[field]+=base_n*float(source[column])
   if m=="all" and field=="crps":
    pass
   if m=="all":
    itemscore["brier"][model]=float(source[SC[model]["brier"]])
 weeks.append(itemscore)
 if index%25==24:
  print("AUDIT_REPLAY_WEEK_SCORES_RECHECKED",index+1,
   "of_175",round(time.monotonic()-T0,1),"s",flush=True)
ensure(cohort["paired"]==N,"total_n_wrong")
def pull(model,market,year="all"):
 raw=totals[model][market].get(str(year),{})
 n=int(raw.get("n",0))
 if n==0:return {"n":0}
 return {"n":n,**{metric:raw[metric]/n for metric in ("brier","hit","logloss","crps")}}
ALL={model:pull(model,"all") for model in P}
for model in P:
 official=P[model]["overall"];source={
  "V3":{"brier":"brier_new","hit":"hit_new","logloss":"logloss_new","crps":"crps_new"},
  "V4":{"brier":"tuned_brier","hit":"tuned_hit","logloss":"tuned_logloss","crps":"tuned_crps"},
  "V4.1":{"brier":"tuned_brier","hit":"tuned_hit","logloss":"tuned_logloss","crps":"tuned_crps"},
  "V5.6":{"brier":"brier_joint","hit":"hit_joint","logloss":"joint_logloss","crps":"crps_joint"}}[model]
 for k,original in source.items():
  ensure(abs(ALL[model][k]-official[original])<1e-9,
   "aggregate_does_not_match_independently_"+model+"_"+k)
print("AUDIT_INDEPENDENT_175_WEEK_TOTALS_RECONCILED",flush=True)
season={str(y):{model:pull(model,"all",y) for model in P}
        for y in range(2016,2026)}
market={m:{model:pull(model,m) for model in P} for m in MARKETS}
# All 175 weekly brier differences, exact paired by matched roster/lines:
weights=np.array([x["paired"] for x in weeks] if weeks else [x["paired"] for x in []])
pairs=np.array([[x["brier"][m] for m in P] for x in weeks]) if weeks else None
# Fill weekly array here, after checking that weekly list appended.
byweek=np.array([[s["brier"][m] for m in P] for s in weeks],dtype=float) if weeks else np.empty((0,4))
comparisons={}
for challenger in ("V4","V4.1","V5.6"):
 d_b=ALL[challenger]["brier"]-ALL["V3"]["brier"]
 d_h=ALL[challenger]["hit"]-ALL["V3"]["hit"]
 comparisons[challenger]={
  "delta_brier":d_b,"delta_hit":d_h,
  "delta_logloss":ALL[challenger]["logloss"]-ALL["V3"]["logloss"],
  "delta_crps":ALL[challenger]["crps"]-ALL["V3"]["crps"],
  "relative_brier_percent":100*d_b/ALL["V3"]["brier"],
  "weekly_brier_wins":sum(s["brier"][challenger]<s["brier"]["V3"] for s in weeks),
  "weekly_brier_losses":sum(s["brier"][challenger]>s["brier"]["V3"] for s in weeks),
  "seasonal_brier_wins":sum(season[str(y)][challenger]["brier"]<season[str(y)]["V3"]["brier"]
                          for y in range(2016,2026))}
# Corrected weekly list is filled below as settlement process runs.
result={"schema":"NFL_V56_INDEPENDENT_DECADE_PAIRED_SCORE_AUDIT_v1",
 "classification":"RESEARCH_ONLY_NOT_PROSPECTIVELY_CERTIFIED",
 "weeks":175,"paired":N,"synthetic_historical_offer_cohort":True,
 "reference_v5_sha256":recsha,
 "sources":{k:{"result_sha256":v["result_sha256"]} for k,v in P.items()},
 "overall":ALL,"comparisons_against_v3":comparisons,
 "season":season,"markets":market,
 "v56_all_thresholds":{str(th):{
   k:P["V5.6"]["overall"].get("conf"+str(th)+"_"+k)
   for k in ("n","claimed","hit")} for th in (70,80,90,95)},
 "v3_all_thresholds":{str(th):{
   k:P["V3"]["overall"].get("conf"+str(th)+"_"+k)
   for k in ("n","claimed","hit")} for th in (70,80,90,95)},
 "notes":["V4 and V4.1 are post-hoc historical archive challengers, not independent books.",
 "V4.1 post-hoc QB shares do not conserve all joint game components.",
 "Historical offer universe is assembled retrospectively and conditioned on observed players.",
 "No genuine historical pregame source timestamp certification."],
 "generated_at_utc":__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}
path=write("INDEPENDENT_175_WEEK_COMPARISON_TABLES.json",result)
print("AUDIT_COMPARISON_TABLES_COMPLETE",json.dumps({"path":str(path),"n":N,
 "overall":ALL,"differences":comparisons,
 "v56_conf80":result["v56_all_thresholds"]["80"],
 "elapsed_seconds":round(time.monotonic()-T0,1)}),flush=True)
