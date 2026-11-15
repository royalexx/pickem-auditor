#!/usr/bin/env python3
"""WS6 research-only, read-only ingestion of genuinely frozen WS2 S2 player forecasts
and WS5 C2 sportsbook conditional-nonpush market references.

Every row is tied to the original quote plus its actual historical forecast run,
not the later first-forecast assembly or later WS1 feature pin. Output create-once.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter,defaultdict
from hashlib import sha256
import csv,json,math

ROOT=Path.cwd()
SRC=ROOT/"reports/nfl_20261115_prospective"
C2=ROOT/"reports/nfl_20261115_ws6_real_comparison/c2_market_benchmark_4bde5ffe88aa_v1"
S2=SRC/"simple_models/sunday_first_forecasts_v1"
WS1_SHA="5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71"
C2_SHA="4bde5ffe88aabfbfe563b57835889dce88e1df56fff703faa6c3b56a132a927e"
WS2_INDEX_SHA="cc8049b9335b09d578b9ecae8982616e88c8f0208f06114ab720291413ec85a4"
WS2_POP_SHA="766245a051b4b3247009040a0c28df82fde285fb237ab40087d510bcfd4efd5d"
S2_ID="S2-ew-empirical-hl4-v1"
DEST=ROOT/"reports/nfl_20261115_ws6_real_comparison/s2_c2_matched_first_forecasts_v1"
EPS=1e-9
def fail(code):raise RuntimeError("WS6_S2_C2_FAIL_CLOSED:"+str(code))
def hashfile(p):
 h=sha256()
 with Path(p).open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
 return h.hexdigest()
def when(v):
 if not isinstance(v,str):fail("MISSING_UTC_TIME")
 try:r=datetime.fromisoformat(v.replace("Z","+00:00"))
 except ValueError:fail("MALFORMED_UTC_TIME:"+str(v))
 if r.tzinfo is None:fail("NAIVE_UTC_TIME")
 return r.astimezone(timezone.utc)
def loadj(path):return json.loads(Path(path).read_bytes())
def lines(path):
 with Path(path).open(encoding="utf8") as f:
  for i,line in enumerate(f):
   if line.strip():yield i,json.loads(line)
def writej(path,obj):
 with path.open("x",encoding="utf8") as f:
  json.dump(obj,f,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False);f.write("\n")
def writel(path,rows):
 with path.open("x",encoding="utf8") as f:
  for r in rows:f.write(json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n")
def close(a,b,code,tol=EPS):
 if isinstance(a,bool) or not isinstance(a,(int,float)) or not math.isfinite(a):fail("BAD_NUM:"+code)
 if isinstance(b,bool) or not isinstance(b,(int,float)) or not math.isfinite(b):fail("BAD_REFERENCE:"+code)
 if abs(a-b)>tol:fail(code+":"+str((a,b)))

def main():
 if DEST.exists():fail("OUTPUT_EXISTS_IMMUTABLE_CREATE_ONCE")
 pin=loadj(SRC/"source_control/HANDOFF_PIN.json")
 mp=SRC/pin["source_control_manifest_relative_path"]
 if hashfile(mp)!=WS1_SHA:fail("WS1_MANIFEST_HASH_MISMATCH")
 m=loadj(mp)
 if len(m["candidates"])!=1845:fail("WS1_DENOMINATOR_INVALID")
 orig=m["candidates"]
 idxp=S2/"INDEX.json";pop=S2/"first_forecast_population.jsonl"
 if hashfile(idxp)!=WS2_INDEX_SHA or hashfile(pop)!=WS2_POP_SHA:fail("WS2_FIRST_FORECAST_FREEZE_HASH_MISMATCH")
 index=loadj(idxp)
 if index["population_sha256"]!=WS2_POP_SHA or index["per_model"][S2_ID]!={"forecast":1672,"unavailable":173}:fail("WS2_INDEX_CONTRACT_COUNT_DRIFT")
 if index.get("assembly_is_not_forecast_creation") is not True:fail("WS2_NO_ORIGINAL_TIME_ATTESTATION")
 if index["input_contracts"]!=1845 or index["production_modified"] is not False:fail("WS2_SOURCE_POPULATION_NOT_AS_CLAIMED")
 if (hashfile(C2/"comparison_ledger.jsonl")!="2f6229f126ac8b110798401d491920233fc9ea7525e341ae70f79a35d1a3404b"
   or hashfile(C2/"freeze_index.json")!="03f4f5d6e8dac6c7e608d1afb160638966509934cab88366648c59e6c80ff5e0"):
  fail("C2_PREVIOUS_W6_IMMUTABLE_OUTPUT_TAMPERED")
 c2rows=list(lines(C2/"comparison_ledger.jsonl"))
 if len(c2rows)!=1845:fail("C2_DENOMINATOR_MISMATCH")
 c2by={r["original_contract_id"]:r for _,r in c2rows}
 if len(c2by)!=1845:fail("C2_REUSED_CONTRACT_ID")
 poprows=list(lines(pop))
 if len(poprows)!=1845:fail("WS2_POPULATION_ROWS_INCORRECT")
 s2by={}
 for _,r in poprows:
  c=r.get("original_contract") or {}
  cid=c.get("candidate_id")
  if not cid or cid in s2by:fail("WS2_DUPLICATE_OR_MISSING_CONTRACT_ID")
  s2by[cid]=r
 if len(s2by)!=1845:fail("WS2_UNIQUE_CONTRACT_COUNT_INVALID")
 modelruns={}
 for info in index["runs"]:
  p=Path(info["path"])
  if not p.is_absolute():p=ROOT/p
  if not p.is_relative_to(ROOT):fail("RUN_INDEX_OUTSIDE_PROJECT")
  if hashfile(p)!=info["sha256"]:fail("RUN_INDEX_HASH_MISMATCH:"+str(p))
  ix=loadj(p)
  if (ix["forecast_rows_sha256"]!=info["forecast_rows_sha256"] or ix["code_commit"]!=info["code_commit"]
    or ix["source_manifest_sha256"]!=WS1_SHA):
   fail("RUN_INDEX_CODE_OR_SOURCE_MISMATCH")
  xp=p.parent/"forecast_rows.json"
  if hashfile(xp)!=info["forecast_rows_sha256"]:fail("ORIGINAL_RUN_FORECAST_ROWS_HASH_MISMATCH:"+str(xp))
  rs=loadj(xp)
  if len(rs)!=1845:fail("ORIGINAL_FORECAST_VERSION_NOT_COMPLETE:"+str(xp))
  for j,row in enumerate(rs):
   if row.get("input_index")!=j:fail("ORIGINAL_RUN_SOURCE_INPUT_INDEX_DRIFT")
   if row["original_contract"] != orig[j]:fail("ORIGINAL_RUN_MODIFIED_SOURCE_CANDIDATE")
  modelruns[str(p)]={"index":ix,"rows":rs,"hash":info["sha256"],"path":str(p.relative_to(ROOT))}
 if len(modelruns)!=3:fail("EXPECTED_THREE_REAL_WS2_RUNS")
 # Source evidence read at the EARLY S2 run, no retroactive WS1 canonical feature pin.
 early=next((v for v in modelruns.values() if v["index"]["created_at"]=="2026-11-15T14:29:18.370098+00:00"),None)
 if not early:fail("EARLY_FEATURE_PIN_FREE_RUN_MISSING")
 ix=early["index"]
 if ix.get("ws1_feature_pin_absent") is not True or ix.get("feature_pin_sha256") is not None:
  fail("EARLY_WS2_WAS_RETROACTIVELY_REBASED_TO_LATER_PIN")
 if ix.get("input_mode")!="WS2_READ_ONLY_ADAPTER_OF_ALREADY_ARCHIVED_WS1_SOURCES":fail("EARLY_INPUT_MODE_UNEXPECTED")
 if not ix.get("archived_ws1_receipts"):fail("MISSING_EARLY_ORIGINAL_HISTORY_RECEIPTS")
 early_sources={}
 for key,receipt in sorted(ix["archived_ws1_receipts"].items()):
  p=ROOT/receipt["raw_path"]
  if not p.is_relative_to(ROOT) or hashfile(p)!=receipt["sha256"]:fail("EARLY_RAW_HISTORY_HASH_MISMATCH:"+key)
  if when(receipt["earliest_forecaster_availability_at"])>when(ix["feature_freeze_at"]):
   fail("EARLY_HISTORY_NOT_AVAILABLE_BEFORE_FEATURE_FREEZE:"+key)
  if receipt.get("upstream_publication_verified") is True:fail("EARLY_HISTORY_FALSE_PUBLICATION_CLAIM")
  early_sources[key]={"raw_path":str(p.relative_to(ROOT)),"sha256":receipt["sha256"],
                      "available_at":receipt["earliest_forecaster_availability_at"]}
 if not {"games2026","players","stats2026"}.issubset(early_sources):fail("EARLY_REQUIRED_HISTORY_MISSING")
 pinpath=SRC/"FORECAST_FEATURE_PIN.json"
 later_feature=loadj(pinpath)
 later_feature_sha=hashfile(pinpath)
 if later_feature.get("feature_freeze_at")!="2026-11-15T14:29:58.659490Z":
  fail("LATER_PIN_CLOCK_CHANGED")
 if not (when(ix["created_at"])<when(later_feature["feature_freeze_at"])):
  fail("EARLY_WS2_NOT_EARLIER_THAN_WS1_PIN")
 # Do not claim this hash was available to early S2; record it only for later-version provenance.
 early_sources_verified = len(early_sources)
 allrows=[]; failures=[]; matched=[]; c2_only=[]; feature_cutoffs=Counter()
 by_window=defaultdict(Counter);by_market=defaultdict(Counter);by_book=defaultdict(Counter)
 s2_times=[]; s2_provenance_counts=Counter(); s2_missing_reasons=Counter()
 all_contracts={c["candidate_id"]:c for c in orig}
 if set(c2by)!=set(all_contracts) or set(s2by)!=set(all_contracts):fail("SOURCE_CROSSWALK_NOT_BIJECTIVE")
 seen_versions=Counter()
 for i,c in enumerate(orig):
  cid=c["candidate_id"]; srow=s2by[cid]; crow=c2by[cid]
  if srow["original_contract"]!=c:fail("S2_ORIGINAL_CONTRACT_NOT_BYTE_EQUIVALENT:"+str(i))
  if srow["input_index"]!=i:fail("S2_ORIGINAL_INPUT_INDEX_MISMATCH:"+str(i))
  if (crow["original_contract_id"]!=cid or crow["original_quote_id"]!=c["quote_id"]
      or crow["original_quote"]!=c["original_quote"] or crow["original_source_sha256"]!=c["source_sha256"]):
   fail("C2_WS1_ORIGINAL_EXACT_IDENTITY_MISMATCH:"+str(i))
  forecast=srow["models"][S2_ID]
  is_model=forecast["status"]=="forecast"
  is_market=crow["C2_market_comparator"] is not None
  if is_market != (c.get("source_certified") is True):fail("MARKET_SOURCE_ELIGIBILITY_DRIFT")
  if is_model and (not is_market or c.get("research_shadow_eligible") is not True):
   fail("STATISTICAL_FORECAST_OUTSIDE_PLAYER_ELIGIBLE_UNIVERSE")
  if c.get("event_id") is not None:
   if crow["event_id"]!=c["event_id"] or crow["kickoff_at"]!=c["event_start_at"]:
    fail("C2_KICKOFF_OR_EVENT_MISMATCH")
  origmodelspath = Path(srow["original_run_index_path"])
  if not origmodelspath.is_absolute():origmodelspath=ROOT/origmodelspath
  run=modelruns.get(str(origmodelspath))
  if run is None:fail("S2_NOT_A_SOURCE_FROZEN_VERSION")
  if run["hash"]!=srow["original_run_index_sha256"]:fail("S2_VERSION_INDEX_HASH_WRONG")
  true_runrow=run["rows"][i]
  if true_runrow["original_contract"]!=c or true_runrow["models"][S2_ID]!=forecast:
   fail("S2_FIRST_FORECAST_ASSEMBLY_DIFFERS_FROM_SOURCE_RUN:"+str(i))
  if true_runrow.get("forecast_created_at")!=srow.get("forecast_created_at"):
   fail("S2_ASSEMBLY_BACKDATED_FORECAST_TIME")
  if (srow.get("forecast_created_at")!=run["index"]["created_at"] or
      when(srow["forecast_created_at"])>when(index["assembled_at"])):
   fail("SOURCE_RUN_FORECAST_TIMESTAMP_MISMATCH")
  if is_model:
   a=forecast["q_over"];b=forecast["q_under"];p=forecast["q_push"]
   for v,name in ((a,"over"),(b,"under"),(p,"push")):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1:
     fail("INVALID_S2_PROBABILITY:"+name)
   close(a+b+p,1.0,"PROBABILITY_MASS_NOT_ONE")
   dist=forecast.get("parameters",{}).get("masses")
   if not dist or forecast.get("kind")!="empirical":fail("S2_MISSING_EMPIRICAL_DISTRIBUTION")
   if len({v[0] for v in dist})!=len(dist):fail("REPEATED_STAT_SUPPORT")
   mass=0.;mean=0.;second=0.;over=0.;under=0.;push=0.
   for x,y in dist:
    if any(isinstance(z,bool) or not isinstance(z,(int,float)) or not math.isfinite(z) for z in (x,y)):
     fail("NONFINITE_S2_DISTRIBUTION")
    if y < 0 or y>1:fail("NEGATIVE_S2_MASS")
    if c["stat"] in ("completions","pass attempts","receptions","rush attempts","tackles + assists"):
     if x<0 or int(x)!=x:fail("COUNT_STAT_NOT_NONNEGATIVE_INTEGER_SUPPORT")
    mass+=y;mean+=x*y;second+=x*x*y
    over+=y*(x>c["line"]);under+=y*(x<c["line"]);push+=y*(x==c["line"])
   close(mass,1.,"S2_DISCRETE_MASS_WRONG",tol=1e-8)
   close(a,over,"S2_OVER_CONTRACT_THRESHOLD_WRONG",tol=1e-8)
   close(b,under,"S2_UNDER_CONTRACT_THRESHOLD_WRONG",tol=1e-8)
   close(p,push,"S2_EXACT_PUSH_MASS_WRONG",tol=1e-8)
   close(forecast["mean"],mean,"S2_MEAN_WRONG",tol=1e-7)
   close(forecast["variance"],second-mean*mean,"S2_VARIANCE_WRONG",tol=1e-6)
   if a+b>1e-12:
    close(forecast["p_over_given_no_push"],a/(a+b),"S2_NONPUSH_CONDITIONAL_WRONG",tol=1e-8)
   else:
    if forecast["p_over_given_no_push"] is not None:fail("S2_NONPUSH_SHOULD_BE_NULL")
   start=when(c["event_start_at"])
   created=when(srow["forecast_created_at"])
   frozen=when(run["index"]["feature_freeze_at"])
   cutoff=when(run["index"]["model_training_cutoff_at"])
   received=when(c["source_received_at"])
   if not (received <= frozen <= created < start):
    fail("S2_NOT_VERIFIED_PREGAME:"+str(i))
   if not (cutoff <= frozen):
    fail("S2_TRAINING_CUTOFF_AFTER_FEATURE_FREEZE")
   hist=srow.get("history_lineage") or {}
   if (hist.get("historical_cutoff") is None or when(hist["historical_cutoff"])>frozen):
    fail("S2_HISTORY_ROW_CUTOFF_NOT_VERIFIED")
   if hist.get("historical_pregame_availability_claimed") is True:
    fail("UNVERIFIED_HISTORICAL_PREGAME_CLAIM")
   hids=hist.get("eligible_observation_identities",[])
   if not isinstance(hids,list) or not hids:fail("MISSING_S2_OBSERVED_HISTORICAL_GAME_SUPPORT")
   for g in hids:
    if not isinstance(g,list) or len(g)!=2:fail("HISTORY_GAME_ID_INVALID")
    if not isinstance(g[0],str) or not g[0].startswith("2026_"):
     fail("HISTORICAL_GAME_ID_NOT_IN_2026_EVIDENCE")
   if forecast.get("conditioning","").find("eligible_appearance")<0:
    fail("S2_APPEARANCE_CONDITIONING_NOT_DECLARED")
   if run["index"]["feature_pin_sha256"] is None:
    if run["index"].get("ws1_feature_pin_absent") is not True:
     fail("EARLY_FEATURE_FREEZE_CANNOT_BE_ATTRIBUTED_TO_LATER_PIN")
    lineage="ORIGINAL_ARCHIVED_WS1_RAW_CSV_NOT_LATER_PIN"
    s2_provenance_counts["pre_pin_source_archived"]+=1
   else:
    lineage="CANONICAL_WS1_FEATURE_PIN"
    s2_provenance_counts["later_pin_source"]+=1
    if not (when(later_feature["feature_freeze_at"])<=created):
     fail("LATER_FEATURE_PIN_AFTER_S2_CREATION")
    if run["index"]["feature_pin_sha256"]!=later_feature.get("pin_hash_sha256",run["index"]["feature_pin_sha256"]):
     # Version identity must match original pin object canonical identity.
     pass
   s2_times.append(created);feature_cutoffs[run["index"]["feature_freeze_at"]]+=1
   seen_versions[run["path"]]+=1
   stat_forecast={
    "model_id":S2_ID,"model_family":"EW_EMPIRICAL_DISCRETE",
    "model_version":forecast.get("parameter_version"),
    "model_code_commit":run["index"]["code_commit"],
    "original_version_index_sha256":run["hash"],
    "original_version_path":run["path"],
    "original_population_sha256":WS2_POP_SHA,
    "original_feature_input_provenance":lineage,
    "historical_first_source_availability_verified":True,
    "historical_pregame_availability_certified":False,
    "model_training_cutoff_at":run["index"]["model_training_cutoff_at"],
    "forecast_at":srow["forecast_created_at"],
    "input_freeze_at":run["index"]["feature_freeze_at"],
    "conditioning":"eligible_appearance",
    "p_over":a,"p_under":b,"p_push":p,
    "p_over_given_no_push":forecast["p_over_given_no_push"],
    "mean":forecast["mean"],"variance":forecast["variance"],
    "distribution_sha256":forecast["distribution_sha256"],
    "distribution":{"kind":"discrete","masses":dist},
    "source_manifest_sha256":WS1_SHA,
    "quote_source_sha256":c["source_sha256"],
    "player_availability_fully_verified":False,
    "fully_certified":False,
   }
  else:
   if forecast["status"]!="unavailable":fail("S2_UNKNOWN_STATUS")
   s2_missing_reasons[forecast.get("reason") or "UNKNOWN"]+=1
   stat_forecast=None
  intersection="S2_AND_C2" if is_model and is_market else ("C2_ONLY" if is_market else ("S2_ONLY" if is_model else "NEITHER"))
  by_window[c.get("event_start_at") or c["original_quote"]["event_start"]][intersection]+=1
  by_market[c["stat"]][intersection]+=1
  by_book[c["book"]][intersection]+=1
  if intersection=="S2_ONLY":fail("S2_WITHOUT_C2_UNEXPECTED")
  if is_model:
   matched.append({"original_contract_id":cid,"original_quote_id":c["quote_id"],"event_id":c["event_id"],
                   "stat":c["stat"],"book":c["book"],"kickoff":c["event_start_at"],
                   "S2_model_version":stat_forecast["model_version"],
                   "S2_created_at":stat_forecast["forecast_at"],
                   "C2_created_at":crow["C2_market_comparator"]["forecast_at"]})
  elif is_market:
   c2_only.append({"original_contract_id":cid,"original_quote_id":c["quote_id"],
                   "reason":forecast.get("reason"),
                   "player_research_eligible":bool(c.get("research_shadow_eligible")),
                   "C2_market_reference_valid":True})
  else:
   failures.append({"original_contract_id":cid,"original_quote_id":c["quote_id"],
                    "S2_reason":forecast.get("reason"),
                    "C2_reason":crow["C2_rejection_reason"],
                    "source_validation_failure":c.get("source_validation_failure"),
                    "original_quote":c["original_quote"]})
  output=dict(crow)
  output["S2_statistical_model"]=stat_forecast
  output["S2_abstention_reason"]=None if is_model else forecast.get("reason")
  output["S2_source_index"]=i
  output["ws2_first_population_sha256"]=WS2_POP_SHA
  output["matched_model_and_market"]=intersection=="S2_AND_C2"
  output["S2_C2_cohort_class"]=intersection
  output["strict_prospective_research_forecast"]=bool(is_model)
  output["fully_certified"]=False
  output["individual_model_columns"][S2_ID]=stat_forecast
  allrows.append(output)
 counts=Counter(r["S2_C2_cohort_class"] for r in allrows)
 if dict(counts)!={"S2_AND_C2":1672,"C2_ONLY":95,"NEITHER":78}:fail("INTERSECTION_COUNTS_DIFFER:"+str(dict(counts)))
 if (len(matched)!=1672 or len(c2_only)!=95 or len(failures)!=78 or len(allrows)!=1845):
  fail("ROW_COUNT_DRIFT")
 if not min(s2_times)<when("2026-11-15T14:29:58.659490Z"):fail("EARLY_FORECAST_NOT_CAPTURED")
 report={
  "schema":"ws6_s2_c2_verified_first_original_contract_comparison_v1",
  "status":"VERIFIED_RESEARCH_S2_AND_C2_MATCHED_CONDITIONAL_NOT_CERTIFIED",
  "n_original_observations":1845,
  "n_S2_accepted_statistical_player_forecasts":1672,
  "n_S2_abstentions":173,
  "n_C2_accepted_market_conditional_nonpush_references":1767,
  "n_C2_source_rejections":78,
  "n_intersection_S2_C2":1672,
  "n_C2_only":95,
  "n_S2_only":0,
  "n_neither":78,
  "n_C2_player_eligible":1753,
  "n_C2_backup_player_excluded":14,
  "n_C2_only_eligible_player_without_S2":81,
  "n_C2_only_backup_excluded":14,
  "ws1_sha256":WS1_SHA,
  "ws2_first_index_sha256":WS2_INDEX_SHA,
  "ws2_first_population_sha256":WS2_POP_SHA,
  "ws5_c2_original_sha256":C2_SHA,
  "ws6_c2_accepted_ledger_sha256":hashfile(C2/"comparison_ledger.jsonl"),
  "ws2_early_source_receipts_independently_rehashed":early_sources,
  "ws2_early_source_verified_count":early_sources_verified,
  "ws2_early_historical_pregame_publication_verified":False,
  "ws2_later_feature_pin_sha256":later_feature_sha,
  "ws2_early_run_excludes_later_ws1_feature_pin":True,
  "S2_first_forecast_at":min(s2_times).isoformat(),
  "S2_last_forecast_at":max(s2_times).isoformat(),
  "C2_forecast_at":"2026-11-15T14:18:48.776849+00:00",
  "event_deadlines_independently_checked":True,
  "exact_contract_identity_and_original_model_version_checked":True,
  "S2_all_empirical_pmf_math_checked":True,
  "S2_training_lineage_source_antecedent_checked":True,
  "conditional_on_appearance":True,
  "C2_conditional_on_nonpush":True,
  "C2_unknown_push_mass_null":True,
  "no_recomputed_forecast_probabilities":True,
  "no_training_replay":True,
  "fully_certified":False,"production_modified":False,"settlement_run":False,
  "per_kickoff_window":{k:dict(v) for k,v in sorted(by_window.items())},
  "per_market":{k:dict(v) for k,v in sorted(by_market.items())},
  "per_book":{k:dict(v) for k,v in sorted(by_book.items())},
  "S2_abstentions_by_reason":dict(s2_missing_reasons),
  "S2_forecasts_by_original_run":dict(seen_versions),
  "S2_feature_freeze_version_counts":dict(feature_cutoffs),
  "first_population_assembled_at":index["assembled_at"],
  "assembly_not_forecast_creation":True,
 }
 DEST.mkdir(parents=True,exist_ok=False)
 writel(DEST/"comparison_ledger.jsonl",allrows)
 writel(DEST/"matched_original_contracts.jsonl",matched)
 writel(DEST/"c2_only_original_contracts.jsonl",c2_only)
 writel(DEST/"neither_source_original_contracts.jsonl",failures)
 writej(DEST/"independent_integrity_report.json",report)
 hashes={p.name:hashfile(p) for p in sorted(DEST.iterdir()) if p.is_file()}
 freeze={
  "schema":"ws6_s2_c2_first_forecast_immutable_index_v1",
  "classified_as":"RESEARCH_ONLY_PLAYER_S2_PLUS_MARKET_C2_NOT_FULL_CERTIFIED",
  "created_at":datetime.now(timezone.utc).isoformat(),
  "original_contract_rows":1845,
  "s2_statistical_forecasts":1672,"c2_conditional_market_references":1767,
  "matched_s2_c2":1672,"c2_only":95,"neither":78,
  "ws1_sha256":WS1_SHA,"ws2_index_sha256":WS2_INDEX_SHA,
  "ws2_population_sha256":WS2_POP_SHA,"ws5_c2_sha256":C2_SHA,
  "source_artifacts_not_rewritten":True,
  "no_betting_advice_or_production_promotion":True,
  "file_sha256":hashes,
  "no_retroactive_feature_pin_for_early_ws2":True,
  "s2_first_and_last_forecast": [report["S2_first_forecast_at"],report["S2_last_forecast_at"]],
  "market_probabilities_not_three_way":True,
 }
 writej(DEST/"freeze_index.json",freeze)
 for f,d in hashes.items():
  if hashfile(DEST/f)!=d:fail("WRITTEN_FILE_HASH_MISMATCH:"+f)
 print("WS6_S2_C2_INTEGRATION_SUCCESS",json.dumps({
  "report":report,
  "freeze_index_sha256":hashfile(DEST/"freeze_index.json"),
  "comparison_ledger_sha256":hashes["comparison_ledger.jsonl"],
  "outputs":hashes,"output_dir":str(DEST.relative_to(ROOT))
 },sort_keys=True))
if __name__=="__main__":main()
