from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json, math, hashlib

ROOT=Path.cwd()
SRC=ROOT/"reports/nfl_20261115_prospective"
PREV=ROOT/"reports/nfl_20261115_ws6_real_comparison/canonical_s2_c2_first_original_forecast_comparison_v1"
WS4=SRC/"joint_models/real_original_qb_attempts_multievent_v031"
AUDIT=SRC/"independent_validation/ws4_real_original_multievent_audit_v031/8076017e5012af8d4a51e367bd0ce3ea85a83d619ee574bbab695c36a97d1449.json"
DEST=ROOT/"reports/nfl_20261115_ws6_real_comparison/canonical_s2_c2_j1_j2_original_forecast_comparison_v1"

SOURCE_EXPECTED="5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71"
WS4_AUDIT_EXPECTED="8076017e5012af8d4a51e367bd0ce3ea85a83d619ee574bbab695c36a97d1449"
PREV_LEDGER_EXPECTED="2fff057f2f3ed136136844bd61533fa68d20f41eb836b154bb95732dad77e101"
PREV_INDEX_EXPECTED="682e9c7f341959b6c9fd913358de44e1f4f358df9b39e0d10c8959a7e5e8610f"
HISTORY={
 "team_2024": ("pickem_runs/blind_historical_campaign_20261109/2024/source_bundles.json","4a70391b28826053b45979c15c18fa23590e994e701fb0c2eab98cc182436066"),
 "qb_stats_2025": ("reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/source_bundle/stats_2025.json.gz","ba1169df7f3a41b486f33b839cc0870f65f30ffac2e29978ea031d7350b3a1bb"),
 "crosswalk": ("reports/nfl_20261115_prospective/joint_models/historical_sources/nflverse_players_a8a86df9be83cdf88d0dadb47f09fb4a3c5db326e19b46cf20bdade38e3e024d.csv","a8a86df9be83cdf88d0dadb47f09fb4a3c5db326e19b46cf20bdade38e3e024d"),
}
def h(path):
 d=hashlib.sha256()
 with path.open("rb") as f:
  for chunk in iter(lambda:f.read(1024*1024),b""):d.update(chunk)
 return d.hexdigest()
def serial(obj):return json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf8")
def t(s):
 v=datetime.fromisoformat(s.replace("Z","+00:00"))
 assert v.utcoffset() is not None,("NON_TZ_TIMESTAMP",s)
 return v.astimezone(timezone.utc)
def gate(cond,reason):
 if not cond:raise RuntimeError("WS6_WS4_INDEPENDENT_GATE:"+str(reason))
def output_json(p,x):
 with p.open("x",encoding="utf8") as f:json.dump(x,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write("\n")

gate(not DEST.exists(),"IMMUTABLE_DESTINATION_ALREADY_EXISTS")
old_index=PREV/"freeze_index.json";old_ledger=PREV/"comparison_ledger_1845.jsonl"
gate(h(old_index)==PREV_INDEX_EXPECTED and h(old_ledger)==PREV_LEDGER_EXPECTED,"PRIOR_WS6_LEDGER_MUTATED")
prev_meta=json.loads(old_index.read_bytes())
gate(prev_meta["artifacts"]["comparison_ledger_1845.jsonl"]==PREV_LEDGER_EXPECTED,"PRIOR_INDEX_MISMATCH")
gate(h(AUDIT)==WS4_AUDIT_EXPECTED,"WS4_AUDIT_HASH_MISMATCH")
report=json.loads(AUDIT.read_bytes())
gate(report["status"]=="PASS_PROVENANCE_AND_NUMERICAL_RESEARCH_SHADOW_ONLY","WS4_AUDIT_STATUS")
gate(len(report["events"])==11 and report["J1_forecast_rows"]==report["J2_forecast_rows"]==58,"WS4_AUDIT_COUNTS")
for name,(rel,expected) in HISTORY.items():
 gate(h(ROOT/rel)==expected,("ORIGINAL_HISTORY_BYTES",name))

pin=json.loads((SRC/"source_control/HANDOFF_PIN.json").read_bytes())
manifest=SRC/pin["source_control_manifest_relative_path"]
gate(h(manifest)==SOURCE_EXPECTED and pin["source_control_manifest_sha256"]==SOURCE_EXPECTED,"CANONICAL_WS1_MANIFEST_HASH")
ws1=json.loads(manifest.read_bytes());source=ws1["candidates"]
gate(len(source)==1845,"CANONICAL_ORIGINAL_DENOMINATOR")
byid={x["candidate_id"]:x for x in source}
gate(len(byid)==1845,"NON_UNIQUE_ORIGINAL_ID")
previous=[]
with old_ledger.open(encoding="utf8") as f:
 for line in f:
  if line.strip(): previous.append(json.loads(line))
gate(len(previous)==1845,"PRIOR_COMPARISON_MISSING_ROWS")
for i,(a,b) in enumerate(zip(previous,source)):
 gate(a["observation_index"]==i and a["original_candidate_id"]==b["candidate_id"] and a["original_quote_id"]==b["quote_id"] and a["original_quote"]==b["original_quote"],("PRIOR_ORIGINAL_ID_MISMATCH",i))
gate(sum(x["S2_original_source_model"] is not None for x in previous)==1672,"S2_COHORT_CHANGED")
gate(sum(x["C2_original_market_reference"] is not None for x in previous)==1767,"C2_COHORT_CHANGED")

models={"J1":{},"J2":{}}
file_manifest=[]
event_counters=defaultdict(Counter)
for ev in report["events"]:
 e_sha=ev["file_sha256"]
 f=WS4/(e_sha+".json")
 gate(f.is_file() and h(f)==e_sha,("MISSING_OR_CHANGED_EVENT_BYTES",e_sha))
 raw=f.read_bytes()
 payload=json.loads(raw)
 gate(raw==serial(payload)+b"\n",("NONCANONICAL_SOURCE_BYTES",e_sha))
 gate(payload["schema"]=="PA_WS4_REAL_ORIGINAL_CONTRACT_EVENT_V031_v1","WRONG_WS4_SCHEMA")
 gate(payload["canonical_ws1_sha256"]==SOURCE_EXPECTED,"DIFFERENT_WS1")
 gate(payload["research_only"] is True and payload["production_promotion"] is False,"INVALID_RELEASE_STATUS")
 gate(payload["git_commit_at_execution"] and len(payload["git_commit_at_execution"])==40,"MISSING_CODE_SHA")
 gate(payload["abstained_models"]=={"J3":"NO_CERTIFIED_PREGAME_SPREAD","J4":"DIAGNOSTIC_ONLY"},"INVENTED_J3")
 ir=payload["input_packet"];out=payload["model_output"]
 gate(payload["source_input_sha256"]==ir["input_manifest_sha256"]==out["source_input_sha256"]==ev["input_sha256"],"BAD_INPUT_LINK")
 gate(hashlib.sha256(serial({k:v for k,v in ir.items() if k!="input_manifest_sha256"})).hexdigest()==ir["input_manifest_sha256"],"CHANGED_INPUT_PACKET")
 gate(hashlib.sha256(serial({k:v for k,v in out.items() if k!="output_sha256"})).hexdigest()==out["output_sha256"],"CHANGED_MODEL_OUTPUT")
 gate(len(ir["events"])==1 and ir["events"][0]["event_id"]==ev["event_id"],"EVENT_ID_SCOPE_MISMATCH")
 game=ir["events"][0]
 start=t(game["event_start_at"]);freeze=t(ir["input_freeze_at"]);created=t(out["forecast_created_at"]);cutoff=t(ir["model_training_cutoff_at"])
 gate(start==t(ev["start_at"]) and created==t(ev["forecast_created_at"]),"GAME_CLOCK_MISMATCH")
 gate(cutoff<=freeze<=created<start,"MODEL_NOT_FROZEN_BEFORE_KICKOFF")
 gate(ir["source_certification_status"]=="SOURCE_CERTIFIED_RESEARCH_SHADOW" and out["classification"]=="UNCERTIFIED_SHADOW","STATUS_LAUNDERED")
 gate(out.get("model_version") and isinstance(out.get("contracts"),list),"OUTPUT_MISSING_VERSION")
 gate(payload["source_receipts"]["historical_stats_2025_file_sha256"]==HISTORY["qb_stats_2025"][1] and payload["source_receipts"]["historical_teams_2024_file_sha256"]==HISTORY["team_2024"][1] and payload["source_receipts"]["nflverse_id_master_sha256"]==HISTORY["crosswalk"][1],"HISTORY_DIFFERENT_SOURCE")
 gate(payload["source_receipts"]["ws1_manifest_file_sha256"]==SOURCE_EXPECTED,"WS1_SOURCE_SHA_NOT_BOUND")
 gate(t(payload["source_receipts"]["crosswalk_first_received_at"])<=freeze,"PLAYER_CROSSWALK_POSTFREEZE")
 gate(t(payload["source_receipts"]["model_training_cutoff_conservative_snapshot_at"])<=freeze,"HISTORICAL_CUTOFF_POSTFREEZE")
 for group in ("source_receipts","scenario_source_receipts"):
  gate(bool(game.get(group)),("HISTORICAL_RECEIPTS_ABSENT",group))
  for receipt in game[group]:
   gate(len(receipt["sha256"])==64 and t(receipt["available_at"])<=freeze,("RECEIPT_FUTURE",group))
 # Independently check 1,845 original-record identities preserved within EACH frozen game output.
 denom=payload["original_denominator_ledger"]
 gate(len(denom)==1845,"ORIGINAL_DENOMINATOR_DROPPED")
 gate(all(denom[i]["candidate_id"]==source[i]["candidate_id"] and
          denom[i]["quote_id"]==source[i]["quote_id"] and
          denom[i]["book"]==source[i]["book"] and
          denom[i]["stat"]==source[i]["stat"] and
          denom[i]["line"]==source[i]["line"] and
          denom[i]["player_id"]==source[i]["player_id"]
          for i in range(1845)),"PER_GAME_SOURCE_ID_DRIFT")
 ready={x["candidate_id"] for x in denom if x["status"] in ("READY_J1_ONLY","READY_J1_J2")}
 input_contracts=ir["contracts"];ids={c["contract_id"] for c in input_contracts}
 gate(len(ids)==len(input_contracts)==ev["distinct_original_contracts"] and ids==ready,("READY_INPUT_UNIVERSE_MISMATCH",ev["event_id"]))
 for contract in input_contracts:
  cid=contract["contract_id"]
  orig=byid.get(cid)
  gate(orig is not None and orig.get("source_certified") and orig.get("research_shadow_eligible"),("ORIGINAL_CONTRACT_UNVERIFIED",cid))
  gate(orig.get("event_id")==ev["event_id"] and orig.get("event_start_at")==game["event_start_at"],("MODEL_EVENT_NOT_ORIGINAL",cid))
  keys=[("quote_id","original_quote_id"),("player_id","player_id"),("team","team_id"),
        ("line","line"),("period","period"),("event_id","event_id"),("source_sha256","original_quote_receipt_sha256")]
  gate(all(orig[k]==contract[v] for k,v in keys),("ORIGINAL_OFFER_MUTATED",cid))
  gate(orig["stat"]=="pass attempts" and contract["stat_key"]=="pass_attempts" and orig["position"]=="QB" and orig["eligibility_status"]=="EXPECTED_STARTER_SOURCE_BACKED",("QB_ROLE_NOT_SOURCE_BACKED",cid))
  gate(t(orig["source_received_at"])==t(contract["original_quote_at"])<=freeze,"SOURCE_NOT_PRE_FORECAST")
  gate(orig["book"]==next(z["book"] for z in denom if z["candidate_id"]==cid),"BOOK_SOURCE_ID_CHANGED")
  # check source receipt at recorded immutable archive
  src_file=SRC/orig["source_archive_path"]
  gate(src_file.is_file() and orig["source_sha256"]==ws1["sources"]["propline"]["sha256"],"QUOTE_ARCHIVE_ID_UNVERIFIED")
 rows=out["contracts"]
 gate(len(rows)==2*len(input_contracts)==ev["J1_forecasts"]+ev["J2_forecasts"],"FORECAST_COUNTS_DONT_MATCH")
 gate(len({(x["model_id"],x["contract_id"]) for x in rows})==len(rows),"DUPLICATE_FORECAST_MODEL_CONTRACT")
 input_byid={c["contract_id"]:c for c in input_contracts}
 for row in rows:
  name=row.get("model_id");cid=row["contract_id"];c=input_byid.get(cid)
  gate(name in models and c is not None,("MODEL_OR_ID_UNKNOWN",cid))
  gate(row["status"]=="FORECAST" and row["classification"]=="UNCERTIFIED_SHADOW" and row["draws"]==4096,"NOT_MODEL_FORECAST")
  gate(row["model_version"]==out["model_version"] and row["input_id"]==ir["input_manifest_sha256"],"MODEL_VERSION_OR_INPUT_ID")
  for k in ("event_id","player_id","team_id","line","period","stat_key","contract_id","original_quote_id","original_quote_at","original_quote_receipt_sha256"):
   gate(row[k]==c[k],("CHANGED_MODEL_ORIGINAL_CONTRACT_FIELD",k,cid))
  prob=(row["p_over"],row["p_under"],row["p_push"])
  gate(all(isinstance(p,(int,float)) and not isinstance(p,bool) and math.isfinite(p) and 0<=p<=1 for p in prob) and abs(sum(prob)-1)<1e-12,"PROBABILITY_NONNORMALIZED")
  gate(row["seed_key"]==ir["input_manifest_sha256"]+"|"+c["event_id"]+"|"+name+"|"+row["model_version"],"SIMULATOR_RANDOMNESS_NOT_PINNED")
  pmf={int(k):float(v) for k,v in row["pmf"].items()}
  gate(all(k>=0 and v>=0 and float(k).is_integer() for k,v in pmf.items()) and abs(sum(pmf.values())-1)<1e-12,"PMF_SUPPORT_OR_SUM")
  line=float(row["line"])
  pmf_proba=(sum(v for k,v in pmf.items() if k>line),
             sum(v for k,v in pmf.items() if k<line),
             sum(v for k,v in pmf.items() if k==line))
  gate(all(abs(x-y)<1e-12 for x,y in zip(prob,pmf_proba)),"PMF_TAIL_DISAGREEMENT")
  mu=sum(k*v for k,v in pmf.items())
  variance=sum(v*(k-mu)**2 for k,v in pmf.items())
  gate(abs(mu-row["mean"])<1e-10 and abs(variance-row["variance"])<1e-8,"MEAN_VARIANCE_WRONG")
  gate(abs(row["mc_se_over"]-math.sqrt(prob[0]*(1-prob[0])/4096))<1e-12,"MC_STANDARD_ERROR_WRONG")
  gate(row["q05"]<=row["q50"]<=row["q95"],"QUANTILE_ORDER")
  gate(cid not in models[name],("DUPLICATE_CROSS_EVENT_FORECAST",cid,name))
  gate(not float(line).is_integer() or row["p_push"]==pmf.get(int(line),0),"INTEGER_PUSH_NOT_EXACT")
  mark={
   "model_id":name,"model_version":row["model_version"],"model_code_commit":payload["git_commit_at_execution"],
   "model_forecast_created_at":out["forecast_created_at"],"input_freeze_at":ir["input_freeze_at"],
   "model_training_cutoff_at":ir["model_training_cutoff_at"],"source_input_sha256":ir["input_manifest_sha256"],
   "source_manifest_sha256":SOURCE_EXPECTED,"original_event_file_sha256":e_sha,
   "original_quote_receipt_sha256":row["original_quote_receipt_sha256"],
   "original_contract_id":cid,"original_quote_id":row["original_quote_id"],
   "p_over":row["p_over"],"p_under":row["p_under"],"p_push":row["p_push"],
   "p_over_given_no_push":row["p_over"]/(1-row["p_push"]) if row["p_push"]<1 else None,
   "mean":row["mean"],"variance":row["variance"],
   "pmf":row["pmf"],"q05":row["q05"],"q50":row["q50"],"q95":row["q95"],
   "draws":row["draws"],"mc_se_over":row["mc_se_over"],"mc_se_under":row["mc_se_under"],
   "expected_qb_depth_status":"EXPECTED_STARTER_SOURCE_BACKED_NOT_GAME_DAY_ACTIVE_CONFIRMED",
   "conditioning":"expected starter plays; injury/substitution and settlement semantics unverified",
   "certification":"PROSPECTIVE_RESEARCH_FORECAST_CONDITIONAL_ON_PLAYING_NOT_FULLY_CERTIFIED",
   "release_allowed":False
  }
  models[name][cid]=mark;event_counters[ev["event_id"]][name]+=1
 file_manifest.append({
  "event_id":ev["event_id"],"event_start_at":game["event_start_at"],
  "original_event_sha256":e_sha,"source_input_sha256":ir["input_manifest_sha256"],
  "model_output_sha256":out["output_sha256"],
  "code_commit":payload["git_commit_at_execution"],
  "created_at":out["forecast_created_at"],
  "J1":event_counters[ev["event_id"]]["J1"],"J2":event_counters[ev["event_id"]]["J2"],
  "model_training_cutoff_at":ir["model_training_cutoff_at"]
 })
gate(len(models["J1"])==len(models["J2"])==58,"MODEL_COUNT_NOT_58")
gate(set(models["J1"])==set(models["J2"]),"J1_J2_CONTRACT_SETS_DIFFER")
gate(len(file_manifest)==11,"NOT_ALL_EVENT_FILES")
gate(sum(v["J1"] for v in file_manifest)==58,"J1_PER_GAME_SUM_INVALID")
gate("401873053" not in event_counters,"FIRST_STARTED_GAME_BACKFILLED")
gate(sum(c["stat"]=="pass attempts" for c in source)==69,"ORIGINAL_PASS_ATTEMPTS_DENOMINATOR")
gate(len({x["event_id"] for x in file_manifest})==11,"EVENT_ID_DUPLICATE")

joined=[];window=defaultdict(Counter);markets=defaultdict(Counter);counts=Counter()
for i,(original,prior) in enumerate(zip(source,previous)):
 cid=original["candidate_id"];j1=models["J1"].get(cid);j2=models["J2"].get(cid)
 gate((j1 is None)==(j2 is None),"MISMATCH_J1_J2_AVAILABILITY")
 s2=prior["S2_original_source_model"];c2=prior["C2_original_market_reference"]
 if j1 is not None:
  gate(original["research_shadow_eligible"] is True,"WS4_FORECAST_ON_INELIGIBLE")
  gate(original["stat"]=="pass attempts" and prior["event_id"] not in (None,"401873053"),"MODEL_MARKET_OR_EVENT_WRONG")
  counts["J1_J2_DISTINCT_CONTRACTS"]+=1
  if s2:
   counts["S2_C2_J1_J2_EXACT_INTERSECTION"]+=1
  else:
   counts["J1_J2_C2_NO_S2"]+=1
  gate(c2 is not None,"WS4_NO_SOURCE_C2_REFERENCE")
 if s2:counts["S2"]+=1
 if c2:counts["C2"]+=1
 if s2 and c2:counts["S2_C2"]+=1
 if s2 and not j1:counts["S2_NO_JOINT"]+=1
 start=original.get("event_start_at") or original["original_quote"]["event_start"]
 for counter in [markets[original["stat"]],window[start]]:
  counter["original"]+=1;counter["S2"]+=int(s2 is not None);counter["C2"]+=int(c2 is not None)
  counter["J1"]+=int(j1 is not None);counter["J2"]+=int(j2 is not None)
  counter["S2_C2_J1_J2"]+=int(s2 is not None and j1 is not None)
 updated=dict(prior)
 updated["J1_original_joint_game_model"]=j1
 updated["J2_original_joint_game_model"]=j2
 updated["J3_original_joint_game_model"]=None
 updated["J3_missing_reason"]="NO_VERIFIED_ORIGINAL_PREGAME_SPREAD"
 updated["J4"]=None
 updated["J4_status"]="DIAGNOSTIC_ONLY_NOT_PROBABILITY_MODEL"
 updated["joint_forecast_comparison_state"]=("S2_C2_J1_J2" if s2 and j1 else
         "C2_J1_J2_NO_S2" if j1 else
         "S2_C2_NO_JOINT" if s2 else
         "C2_ONLY_NO_JOINT" if c2 else "ORIGINAL_SOURCE_REJECTED")
 updated["joint_status"]="CONDITIONAL_ON_EXPECTED_QB" if j1 is not None else "ABSTAIN"
 updated["joint_abstention_reason"]=None if j1 else ("KICKOFF_CLOSED" if start=="2026-11-15T14:30:00Z" else
        "NO_QB_ATTEMPTS_FORECAST_FOR_THIS_ORIGINAL_CONTRACT")
 updated["fully_certified"]=False
 if "other_model_columns" in updated:
  gate(updated["other_model_columns"].get("J1") is None and updated["other_model_columns"].get("J2") is None,"PREEXISTING_MODEL_FORECAST_OVERWRITE")
  updated["other_model_columns"]=dict(updated["other_model_columns"],J1=None if j1 is None else "SEE_J1_original_joint_game_model",J2=None if j2 is None else "SEE_J2_original_joint_game_model")
 joined.append(updated)
gate(len(joined)==1845 and counts["S2"]==1672 and counts["C2"]==1767 and counts["S2_C2"]==1672,"PRIOR_MODEL_POPULATION_CHANGED")
gate(counts["J1_J2_DISTINCT_CONTRACTS"]==58,"WS4_GENUINE_ORIGINAL_CONTRACT_COUNT")
gate(sum(v["J1"] for v in markets.values())==58,"MARKET_COVERAGE_INCONSISTENCY")
gate(counts["S2_C2_J1_J2_EXACT_INTERSECTION"]+counts["J1_J2_C2_NO_S2"]==58,"FOUR_WAY_COUNT_NOT_RECONCILED")
gate(h(old_ledger)==PREV_LEDGER_EXPECTED and h(old_index)==PREV_INDEX_EXPECTED,"PRIOR_IMMUTABLE_LEDGER_CHANGED_DURING_AUDIT")
gate(h(AUDIT)==WS4_AUDIT_EXPECTED,"WS4_INDEPENDENT_AUDIT_MUTATED_DURING_RECONCILIATION")

DEST.mkdir(parents=True,exist_ok=False)
outledger=DEST/"comparison_ledger_1845.jsonl"
with outledger.open("x",encoding="utf8") as f:
 for record in joined:f.write(serial(record).decode("utf8")+"\n")
manifest_out=DEST/"ws4_individual_event_file_receipts.json"
output_json(manifest_out,sorted(file_manifest,key=lambda x:x["event_id"]))
report_out=DEST/"independent_join_audit_report.json"
summary={
 "schema":"WS6_NFL_20261115_S2_C2_J1_J2_INDEPENDENT_JOIN_V1",
 "status":"IMMUTABLE_RESEARCH_FORECAST_ONLY_NOT_FULLY_CERTIFIED",
 "canonical_original_observations":1845,"source_verified":1767,"research_eligible":1753,
 "source_manifest_sha256":SOURCE_EXPECTED,
 "parent_S2_C2_ledger_sha256":PREV_LEDGER_EXPECTED,
 "parent_S2_C2_freeze_index_sha256":PREV_INDEX_EXPECTED,
 "WS4_existing_independent_audit_sha256":WS4_AUDIT_EXPECTED,
 "WS4_individual_forecast_file_counts":len(file_manifest),
 "WS4_distinct_original_contracts":58,
 "WS4_J1_forecasts":58,"WS4_J2_forecasts":58,"WS4_J3_forecasts":0,
 "S2_forecasts":counts["S2"],"C2_market_nonpush_references":counts["C2"],
 "S2_C2_exact_matched":counts["S2_C2"],
 "S2_C2_J1_J2_exact_matched":counts["S2_C2_J1_J2_EXACT_INTERSECTION"],
 "J1_J2_C2_without_S2":counts["J1_J2_C2_NO_S2"],
 "S2_C2_without_J1_J2":counts["S2_NO_JOINT"],
 "all_model_record_counts":dict(counts),
 "by_market":{k:dict(v) for k,v in sorted(markets.items())},
 "by_kickoff":{k:dict(v) for k,v in sorted(window.items())},
 "J1_J2_first_genuine_timestamp":min(t(x["created_at"]) for x in file_manifest).isoformat(),
 "J1_J2_last_genuine_timestamp":max(t(x["created_at"]) for x in file_manifest).isoformat(),
 "historical_source_receipts":{k:{"path":rel,"sha256":sha} for k,(rel,sha) in HISTORY.items()},
 "WS4_source_readiness_and_model_event_timestamps_all_verified":True,
 "WS4_recomputed_116_exact_probabilities_PMF_mean_variance":True,
 "WS4_original_files_11_immutable_sha_bytes_verified":True,
 "original_denominator_preserved_per_WS4_event_file":True,
 "WS4_numerical_identity_rejections":0,
 "J3_abstention_reason":"NO_CERTIFIED_PREGAME_SPREAD",
 "J4_status":"DEPENDENCE_DIAGNOSTIC_ONLY",
 "unconfirmed_2026_starter_active":True,
 "historical_2024_2025_rate_calibration_proven":False,
 "provider_terms_certified":False,"production_promotion_allowed":False,
 "performance_comparison_performed":False,
 "source_code_not_modified":True,
 "WS4_model_execution_run":"33231250-59f2-4859-9e8f-94adaa06db4e",
 "WS4_independent_numeric_run":"0d255b78-fcf9-4c0f-ac2d-60cd933b6c56",
 "WS4_67_test_run":"b55d19c9-fc2a-4850-b653-bab309daf318"
}
output_json(report_out,summary)
children={p.name:h(p) for p in (outledger,report_out,manifest_out)}
idx={
 "schema":"WS6_20261115_IMMUTABLE_S2_C2_J1_J2_FREEZE_INDEX_V1",
 "status":"RESEARCH_ONLY_VERIFIED_S2_C2_J1_J2_ORIGINAL_CONTRACTS",
 "created_at":datetime.now(timezone.utc).isoformat(),
 "original_observations":1845,"S2":1672,"C2_market_only":1767,"J1":58,"J2":58,"J3":0,
 "exact_S2_C2_J1_J2_intersection":counts["S2_C2_J1_J2_EXACT_INTERSECTION"],
 "canonical_source_manifest_sha256":SOURCE_EXPECTED,
 "prior_S2_C2_ledger_sha256":PREV_LEDGER_EXPECTED,
 "WS4_independent_audit_sha256":WS4_AUDIT_EXPECTED,
 "child_files":children,
 "not_full_certified":True,"original_source_and_model_artifacts_unchanged":True,
 "no_postgame_scores":True,"no_production_promotion":True
}
freeze=DEST/"freeze_index.json";output_json(freeze,idx)
for fn,digest in children.items():gate(h(DEST/fn)==digest,"NEW_IMMUTABLE_ARTIFACT_CHANGED")
print("WS6_WS4_NEW_JOIN_SUCCESS",json.dumps({
 "counts":dict(counts),"markets":summary["by_market"],
 "by_kickoff":summary["by_kickoff"],
 "ws4_first_time":summary["J1_J2_first_genuine_timestamp"],
 "ws4_last_time":summary["J1_J2_last_genuine_timestamp"],
 "final_ledger_sha256":h(outledger),"freeze_index_sha256":h(freeze),
 "filenames":children,"directory":str(DEST.relative_to(ROOT))},sort_keys=True))
