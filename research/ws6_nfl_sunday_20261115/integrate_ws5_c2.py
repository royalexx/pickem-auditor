#!/usr/bin/env python3
"""WS6 independent, create-once integration of original WS5 C2 into a market-only ledger.

DOES NOT collect a source, generate a price/probability, fit a model, backdate
a forecast, publish picks or change WS5's frozen original JSON.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import math

ROOT = Path.cwd()
SOURCE_ROOT = ROOT / "reports/nfl_20261115_prospective"
C2_REL = "calibration_models/sunday_20261115T141848783858Z.json"
C2_SHA = "4bde5ffe88aabfbfe563b57835889dce88e1df56fff703faa6c3b56a132a927e"
MANIFEST_SHA = "5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71"
C2_SOURCE_RUN = "11d1d944-1fcc-4192-925a-aeed8c89802e"
C2_RUN_CREATED = "2026-11-15T14:17:55.370Z"
C2_RUN_COMPLETED = "2026-11-15T14:18:53.662Z"
DEST = ROOT / "reports/nfl_20261115_ws6_real_comparison/c2_market_benchmark_4bde5ffe88aa_v1"
LEGACY = ("engine_a", "engine_b", "bayesian_a", "bayesian_b",
          "strict_nuts", "frozen_60_40", "market_no_vig_legacy")
STATISTICAL_MODELS = (
    "S1", "S2", "S3", "S4", "S5", "S6", "S7",
    "O1", "O2", "O3", "O4", "O5",
    "J1", "J2", "J3",
    "C1", "C3", "C4", "C4_sensitivity_050",
    "C4_sensitivity_090", "C5", "C6", "C7",
)
def fail(s):
    raise RuntimeError("WS6_FAIL_CLOSED:" + str(s))
def file_sha(path):
    h = sha256()
    with Path(path).open("rb") as f:
        for data in iter(lambda: f.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()
def utc(s):
    if not isinstance(s, str):
        fail("MISSING_TIMESTAMP")
    x = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if x.tzinfo is None or x.utcoffset() is None:
        fail("NAIVE_TIMESTAMP")
    return x.astimezone(timezone.utc)
def american(p):
    if isinstance(p, bool) or not isinstance(p, (int,float)) or not math.isfinite(p) or p == 0:
        fail("INVALID_AMERICAN_ODDS")
    return -p / (100-p) if p < 0 else 100 / (100+p)
def record_json(path, data):
    with path.open("x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True,
                  indent=2, allow_nan=False)
        f.write("\n")
def record_jsonl(path, data):
    with path.open("x", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True,
                               separators=(",",":"), allow_nan=False) + "\n")

def main():
    if DEST.exists():
        fail("OUTPUT_EXISTS_ALREADY_DO_NOT_REWRITE")
    pinpath = SOURCE_ROOT / "source_control/HANDOFF_PIN.json"
    pin = json.loads(pinpath.read_bytes())
    mpath = SOURCE_ROOT / pin["source_control_manifest_relative_path"]
    if file_sha(mpath) != MANIFEST_SHA or pin["source_control_manifest_sha256"] != MANIFEST_SHA:
        fail("CANONICAL_MANIFEST_SHA_MISMATCH")
    m = json.loads(mpath.read_bytes())
    if m.get("schema") != "nfl_20261115_source_control_v1" or len(m.get("candidates", [])) != 1845:
        fail("WRONG_CANONICAL_SCHEMA_OR_DENOMINATOR")
    if m["source_certified_quotes"] != 1767 or m["research_shadow_eligible_quotes"] != 1753:
        fail("WS1_DENOMINATOR_DRIFT")
    c2path = ROOT / C2_REL
    if file_sha(c2path) != C2_SHA:
        fail("ORIGINAL_C2_LEDGER_BYTES_CHANGED")
    ws5 = json.loads(c2path.read_bytes())
    rpath = c2path.with_name(c2path.stem + "_receipt.json")
    receipt = json.loads(rpath.read_bytes())
    if (receipt["ledger_sha256"] != C2_SHA or
        receipt["ledger_path"] != C2_REL or
        receipt["ledger_bytes"] != c2path.stat().st_size):
        fail("WS5_RECEIPT_MISMATCH")
    for k in ("input_manifest_sha256",):
        if ws5[k] != MANIFEST_SHA or receipt[k] != MANIFEST_SHA:
            fail("WS5_NOT_BOUND_TO_CORRECT_WS1")
    if (ws5["capture_at"] != receipt["capture_at"] or
        ws5["code_commit"] != receipt["code_commit"] or
        ws5["capture_at"] != "2026-11-15T14:18:48.776849+00:00"):
        fail("WS5_FREEZE_CLOCK_NOT_ORIGINALLY_RECORDED")
    if not (utc(C2_RUN_CREATED) <= utc(ws5["capture_at"])
            <= utc(C2_RUN_COMPLETED) < utc("2026-11-15T14:30:00Z")):
        fail("ORIGINAL_C2_RUN_CHRONOLOGY_INVALID")
    if ws5["registry"]["C2"]["configuration"] != {"devig": "multiplicative_two_way", "family": "market_only"}:
        fail("C2_MODEL_DEFINITION_CHANGED")
    model_id = ws5["registry"]["C2"]["model_id"]
    if not model_id.startswith("C2:") or not len(ws5["code_commit"]) == 40:
        fail("C2_CODE_IDENTITY_MISSING")
    sources = m["sources"]
    declared = ws5.get("verified_original_source_sha256", {})
    if set(declared) != set(sources) or any(v != sources[k]["sha256"] for k,v in declared.items()):
        fail("C2_SOURCE_RECEIPT_HASH_INVENTORY_NOT_CANONICAL")
    # Independently hash the original provider receipt that C2 used.
    provider = SOURCE_ROOT / sources["propline"]["archive_path"]
    if file_sha(provider) != sources["propline"]["sha256"]:
        fail("ORIGINAL_PROVIDER_BYTES_HASH_MISMATCH")
    # The other 49 receipts were independently hashed in WS6's prior source-only run.
    original = m["candidates"]
    if len({c["candidate_id"] for c in original}) != 1845:
        fail("CANONICAL_CONTRACT_ID_COLLISION")
    rows = ws5["forecasts"]
    if len(rows) != 1845 * len(ws5["registry"]):
        fail("WS5_MODEL_ROW_COVERAGE_CHANGED")
    group = defaultdict(list)
    for row in rows:
        group[row["candidate"]].append(row)
    if set(group) != set(ws5["registry"]) or any(len(v) != 1845 for v in group.values()):
        fail("WS5_MODEL_UNIVERSE_NOT_CONSISTENT")
    for name, values in group.items():
        if name == "C2":
            continue
        if any(x["status"] != "abstain" for x in values):
            fail("UNEXPECTED_OTHER_WS5_CALIBRATION_MODEL_OUTPUT:" + name)
    c2 = group["C2"]
    by_index = {}
    for row in c2:
        idx = row.get("input_index")
        if not isinstance(idx, int) or isinstance(idx, bool) or idx in by_index or not 0 <= idx < 1845:
            fail("C2_DUPLICATE_OR_MISSING_INPUT_INDEX")
        by_index[idx] = row
    if set(by_index) != set(range(1845)):
        fail("C2_INDEX_MISSING")
    manifest_rejections, c2_rejections = {}, {}
    out_rows, rejected, excluded, conditional_rows = [], [], [], []
    source_hash_cache = {sources["propline"]["archive_path"]: sources["propline"]["sha256"]}
    counts = Counter()
    by_window = defaultdict(Counter)
    by_market = defaultdict(Counter)
    reasons = Counter()
    times = []
    for i,c in enumerate(original):
        row = by_index[i]
        ident = row["identity"]
        cid = c["candidate_id"]
        is_certified = c.get("source_certified") is True and not c.get("source_validation_failure")
        is_conditional = c.get("research_shadow_eligible") is True
        if row.get("contract_id") != cid or row.get("quote_id") != c.get("quote_id") or row.get("candidate") != "C2" or row.get("model_id") != model_id:
            fail("CONTRACT_ID_OR_C2_ID_MISMATCH:" + str(i))
        for ck, ik in (("event_id","event_id"),("player_id","player_id"),
                       ("stat","stat"),("book","book"),("period","period"),
                       ("line","line"),("quote_id","quote_id")):
            if c.get(ck) != ident.get(ik):
                fail("EXACT_CONTRACT_IDENTITY_MISMATCH:" + ck + ":" + str(i))
        if row.get("event_id") != c.get("event_id") or row.get("input_freeze_at") != c.get("input_freeze_at"):
            fail("EXACT_EVENT_OR_SOURCE_FREEZE_MISMATCH:" + str(i))
        start = c.get("event_start_at") or c["original_quote"]["event_start"]
        # For rejected identities, retain the provider event clock but do not claim official ESPN event verification.
        if is_certified:
            if c["event_start_at"] != c["scheduled_kickoff"] or row.get("event_start_at") != start:
                fail("EVENT_START_MISMATCH:" + str(i))
            if row["status"] != "forecast":
                fail("C2_MISSING_ON_CERTIFIED_SOURCE:" + str(i))
        else:
            if row["status"] != "abstain":
                fail("C2_FORECASTS_UNVERIFIED_IDENTITY:" + str(i))
            if c.get("source_validation_failure") != "CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE":
                fail("UNEXPECTED_WS1_IDENTITY_REJECTION:" + str(i))
            manifest_rejections[cid] = c
            c2_rejections[cid] = row
        market = None
        if row["status"] == "forecast":
            counts["c2_raw_forecast"] += 1
            if row.get("reference_type") != "conditional_on_nonpush_sportsbook_reference":
                fail("C2_REFERENCE_TYPE_INVALID:" + str(i))
            if row.get("unconditional") is not None or row.get("push_policy") != "market_push_unidentified":
                fail("C2_INVENTED_UNCONDITIONAL_PROBABILITIES:" + str(i))
            if row.get("original_quote") != c["original_quote"]:
                fail("ORIGINAL_MARKET_QUOTE_CHANGED:" + str(i))
            if row.get("quote_source_sha256") != c["source_sha256"] or row.get("quote_received_at") != c["source_received_at"]:
                fail("MARKET_SOURCE_LINEAGE_MISMATCH:" + str(i))
            if row.get("source_sha256") != [c["source_sha256"]]:
                fail("C2_SOURCE_HASH_ARRAY_MISMATCH:" + str(i))
            if row.get("original_prices") != {"over_odds":c["over_odds"],"under_odds":c["under_odds"]}:
                fail("BOOK_PRICES_NOT_PRESERVED:" + str(i))
            if row.get("original_quote_reported_at") != c.get("original_quote_reported_at"):
                fail("ORIGINAL_PROVIDER_CLOCK_CHANGED:" + str(i))
            rec = row.get("conditional_no_push")
            if not isinstance(rec,dict):
                fail("C2_NONPUSH_PROBABILITY_MISSING:" + str(i))
            a = rec["over"]; b = rec["under"]
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in (a,b)):
                fail("INVALID_NONPUSH_PROBABILITY:" + str(i))
            po = american(c["over_odds"]); pu = american(c["under_odds"])
            if not math.isclose(a+b,1.0,rel_tol=0,abs_tol=1e-10):
                fail("C2_NONPUSH_MASS_NOT_NORMALIZED:" + str(i))
            if max(abs(a-po/(po+pu)),abs(b-pu/(po+pu))) > 1e-10:
                fail("C2_ODDS_MATH_DIFFERS_FROM_INDEPENDENT_RECALC:" + str(i))
            if row.get("unnormalized_implied") != {"over":po,"under":pu}:
                # Compare numerically rather than floating representation if needed
                raw = row.get("unnormalized_implied",{})
                if max(abs(raw.get("over",float("inf"))-po),abs(raw.get("under",float("inf"))-pu)) > 1e-12:
                    fail("UNNORMALIZED_AMERICAN_PRICES_MISMATCH:" + str(i))
            when=utc(row["forecast_at"]); freeze=utc(row["input_freeze_at"])
            quote_possessed=utc(c["source_received_at"]); kickoff=utc(start)
            if not (quote_possessed <= freeze <= when <= utc(C2_RUN_COMPLETED) < kickoff):
                fail("C2_NOT_AUTHENTIC_PREGAME:" + str(i))
            if when != utc(ws5["capture_at"]):
                fail("WS5_ROW_FREEZE_NOT_C2_ORIGINAL_CAPTURE:" + str(i))
            times.append(when)
            role = "MATCHED_RESEARCH_ELIGIBLE" if is_conditional else "SOURCE_VERIFIED_NOT_PLAYER_FORECAST_ELIGIBLE"
            market = {
                "model_id":model_id,"model_name":"C2","family":"market_only",
                "model_version":ws5["registry"]["C2"]["version"],
                "model_code_commit":ws5["code_commit"],
                "original_ledger_sha256":C2_SHA,
                "reference_type":"conditional_on_nonpush_sportsbook_reference",
                "p_over_given_no_push":a,
                "p_under_given_no_push":b,
                "q_over":None,"q_under":None,"q_push":None,
                "unconditional":None,"mean_projection":None,
                "raw_american_odds":{"over":c["over_odds"],"under":c["under_odds"]},
                "forecast_at":row["forecast_at"],
                "input_freeze_at":row["input_freeze_at"],
                "book":c["book"],
                "source_sha256":c["source_sha256"],
                "source_publication_truth_verified":False,
                "role_comparison_state":role,
                "production_certified":False,
            }
            if is_conditional:
                counts["c2_matched_research_eligible"] += 1
            else:
                if c.get("eligibility_status") != "BACKUP_INELIGIBLE":
                    fail("C2_SOURCE_CERTIFIED_BUT_EXCLUDED_NOT_BACKUP:" + str(i))
                counts["c2_source_verified_player_excluded"] += 1
                excluded.append({"index":i,"contract_id":cid,"quote_id":c["quote_id"],
                                 "event_id":c["event_id"],"reason":c["eligibility_status"],
                                 "C2_original_model_id":model_id})
        else:
            counts["c2_rejected"] += 1
            reasons[row.get("reason") or "UNSPECIFIED"] += 1
            rejected.append({"observation_index":i,"contract_id":cid,"quote_id":c["quote_id"],
                             "ws1_source_failure":c.get("source_validation_failure"),
                             "ws5_c2_rejection":row.get("reason"),
                             "original_quote":c["original_quote"],
                             "original_source_sha256":c.get("source_sha256")})
        label = "CONDITIONAL_ON_PLAYING" if is_conditional else ("ABSTAIN" if is_certified else "REJECTED")
        by_window[start][label] += 1
        by_market[c["stat"]][label] += 1
        if market is not None:
            by_window[start]["C2_MARKET_BENCHMARK"] += 1
            by_market[c["stat"]]["C2_MARKET_BENCHMARK"] += 1
        obj = {
            "observation_index":i,"original_contract_id":cid,"original_quote_id":c["quote_id"],
            "book":c["book"],"player":c["player"],"player_id":c.get("player_id"),
            "event_id":c.get("event_id"),"kickoff_at":start,
            "team":c.get("team"),"opponent":c.get("opponent"),
            "stat":c["stat"],"line":c["line"],"period":c["period"],
            "original_quote":c["original_quote"],
            "original_source_sha256":c["source_sha256"],
            "original_source_received_at":c["source_received_at"],
            "canonical_manifest_sha256":MANIFEST_SHA,
            "ws1_identity_verified":is_certified,
            "ws1_research_shadow_eligible":is_conditional,
            "player_eligibility_status":c.get("eligibility_status"),
            "source_validation_failure":c.get("source_validation_failure"),
            "certification_ladder":label,
            "C2_market_comparator":market,
            "C2_rejection_reason":row.get("reason") if market is None else None,
            "genuine_player_model_forecasts":None,
            "individual_model_columns":{k:None for k in STATISTICAL_MODELS+LEGACY},
            "forecast_input_feature_sha256":None,
            "full_certification":False,
        }
        out_rows.append(obj)
    if (counts["c2_raw_forecast"] != 1767 or counts["c2_rejected"] != 78 or
        counts["c2_matched_research_eligible"] != 1753 or
        counts["c2_source_verified_player_excluded"] != 14):
        fail("C2_RECONCILIATION_COUNTER_DRIFT:" + str(dict(counts)))
    if set(manifest_rejections) != set(c2_rejections) or set(manifest_rejections) & {c["candidate_id"] for c in original if c["source_certified"]}:
        fail("WS1_WS5_REJECTED_CONTRACT_ID_SETS_NOT_EQUAL")
    if dict(reasons) != {"CROSS_TEAM_ROSTER_IDENTITY_UNVERIFIABLE":54,
                         "duplicate_or_conflicting_exact_contract":24}:
        fail("WS5_54_PLUS_24_REJECT_REASONS_CHANGED")
    if len(out_rows) != 1845 or len(rejected) != 78 or len(excluded) != 14:
        fail("FAILED_ORIGINAL_DENOMINATOR_PRESERVATION")
    first, last = min(times).isoformat(), max(times).isoformat()
    if first != last or len(times) != 1767:
        fail("C2_FREEZE_TIMESTAMP_INCONSISTENT")
    if file_sha(c2path) != C2_SHA or file_sha(mpath) != MANIFEST_SHA:
        fail("IMMUTABLE_SOURCE_MUTATED_DURING_AUDIT")
    report = {
        "schema":"ws6_original_c2_independent_market_integration_v1",
        "source_cohort":"AUTHORITATIVE_WS1_20261115",
        "status":"MARKET_BENCHMARK_ACCEPTED_CONDITIONAL_NONPUSH_NOT_PLAYER_MODEL",
        "original_sportsbook_observations":1845,
        "ws1_source_certified":1767,
        "ws1_research_eligible":1753,
        "ws5_c2_probabilities_verified":1767,
        "ws5_c2_rejected":78,
        "ws5_c2_matched_research_eligible":1753,
        "ws5_c2_price_references_on_excluded_backup_QBs":14,
        "ws1_ws5_rejected_contract_id_sets_identical":True,
        "ws5_c2_rejection_reasons":dict(sorted(reasons.items())),
        "original_ws5_c2_ledger":C2_REL,
        "original_ws5_c2_sha256":C2_SHA,
        "original_ws5_receipt_sha256":file_sha(rpath),
        "canonical_ws1_sha256":MANIFEST_SHA,
        "model_id":model_id,
        "model_version":ws5["registry"]["C2"]["version"],
        "model_code_sha":ws5["code_commit"],
        "ws5_original_capture_at":ws5["capture_at"],
        "ws5_original_deepnote_run":C2_SOURCE_RUN,
        "ws5_deepnote_run_created_at":C2_RUN_CREATED,
        "ws5_deepnote_run_completed_at":C2_RUN_COMPLETED,
        "first_market_reference_forecast_at":first,
        "last_market_reference_forecast_at":last,
        "source_hash_inventory_mapped":len(declared),
        "original_prop_line_receipt_sha256":sources["propline"]["sha256"],
        "market_numerical_identity_all_passed":True,
        "all_C2_recorded_freezes_before_individual_kickoff":True,
        "C2_market_only_no_unconditional_mass":True,
        "source_first_publication_certified":False,
        "book_product_terms_fully_certified":False,
        "full_statistical_forecast_count_from_C2":0,
        "research_only":True,"model_promotion":False,"settlement_started":False,
        "per_market":{k:dict(v) for k,v in sorted(by_market.items())},
        "per_kickoff":{k:dict(v) for k,v in sorted(by_window.items())},
        "independent_check_run_kind":"archived_source_bytes+exact_contract_identity+math+chronology",
        "run_execution_source":"Deepnote Basic CPU, detached, independent WS6 auditor",
    }
    DEST.mkdir(parents=True, exist_ok=False)
    record_jsonl(DEST / "comparison_ledger.jsonl", out_rows)
    record_jsonl(DEST / "c2_original_source_rejections.jsonl", rejected)
    record_jsonl(DEST / "c2_market_only_excluded_player_contracts.jsonl", excluded)
    record_json(DEST / "independent_integrity_report.json", report)
    hashes={p.name:file_sha(p) for p in sorted(DEST.iterdir()) if p.is_file()}
    idx={
        "schema":"ws6_c2_immutable_market_benchmark_freeze_index_v1",
        "classification":"PREGAME_C2_MARKET_REFERENCE_ONLY",
        "created_by_WS6_at":datetime.now(timezone.utc).isoformat(),
        "ws5_original_market_reference_freeze_at":ws5["capture_at"],
        "source_manifest_sha256":MANIFEST_SHA,
        "ws5_original_ledger_sha256":C2_SHA,
        "ws5_original_ledger_relative_path":C2_REL,
        "ws5_original_run_id":C2_SOURCE_RUN,
        "row_count":1845,
        "market_reference_rows":1767,
        "market_reference_matched_player_eligible_rows":1753,
        "market_reference_source_verified_but_player_excluded":14,
        "market_reference_rejected_rows":78,
        "statistical_model_forecast_rows":0,
        "independent_row_sha256":hashes,
        "file_hashes_verified":True,
        "no_retroactive_creation_of_market_reference":True,
        "no_implicit_push_mass":True,
        "source_publication_not_fully_certified":True,
        "not_a_statistical_model_certification":True,
        "read_only_original_ws5_file":True,
        "production_release":False,
    }
    record_json(DEST/"freeze_index.json",idx)
    for name,h in hashes.items():
        if file_sha(DEST/name)!=h:
            fail("NEW_OUTPUT_HASH_MISMATCH")
    print("WS6_C2_INTEGRATION_SUCCESS",json.dumps({
        "report":{k:v for k,v in report.items() if k not in ("per_market","per_kickoff")},
        "per_market":report["per_market"],"per_kickoff":report["per_kickoff"],
        "new_directory":str(DEST.relative_to(ROOT)),
        "freeze_index_sha256":file_sha(DEST/"freeze_index.json"),
        "comparison_ledger_sha256":hashes["comparison_ledger.jsonl"],
        "child_file_hashes":hashes},sort_keys=True))
if __name__=="__main__":
    main()
