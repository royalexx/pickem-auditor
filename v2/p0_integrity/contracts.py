"""Shared NBA/NHL immutable-record admission layer (P0/1); research only.

This module is an adapter/validator, not a statistical engine or collector.
Validation of serialized fields is NOT evidence that a source was actually
available: admit_forecast independently rereads archived original bytes.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping
import hashlib
import json
import math
import re

VERSION = "PA-P0/1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
ID_FIELDS = {"receipt_id","source_id","feature_snapshot_id","model_artifact_id",
             "model_id","model_version","forecast_id","run_id","event_id",
             "player_id","team_id","opponent_id","stat_key","period","quote_id",
             "contract_id","outcome_id","settlement_id","training_state_id",
             "experiment_id","source_receipt_id","source_kind","sport","league",
             "book","product_type","settlement_policy"}
SCHEMAS = {
 "SourceReceipt": """receipt_id source_id source_kind source_available_at collected_at
 source_sha256 archive_path provenance_class""".split(),
 "PregameFeatureSnapshot": """feature_snapshot_id sport event_id team_id opponent_id
 player_id stat_key period input_freeze_at source_receipt_ids feature_sha256
 reconstruction_class features""".split(),
 "ModelArtifact": """model_artifact_id model_id model_version model_code_sha
 artifact_sha256 artifact_path training_data_sha256 training_cutoff_at created_at
 training_scope feature_schema_id""".split(),
 "ForecastSnapshot": """forecast_id run_id sport league season event_id team_id
 opponent_id player_id stat_key period event_start_at forecast_at input_freeze_at
 model_training_cutoff_at feature_snapshot_id model_artifact_id model_id
 model_version source_receipt_ids input_sha256 output_sha256 model_code_sha
 artifact_sha256 seed distribution uncertainty abstention_reasons admission_class
 eligible quote_id line side market_probability""".split(),
 "MarketQuote": """quote_id contract_id event_id sport team_id opponent_id player_id
 stat_key period quote_timestamp event_start_at book product_type quote_kind
 line side source_receipt_id source_sha256 terms accepted reject_reason""".split(),
 "OutcomeRecord": """outcome_id sport event_id team_id player_id stat_key period
 official_result_available_at official_source_receipt_id official_source_sha256
 actual_value participation result_version status""".split(),
 "SettlementRecord": """settlement_id forecast_id outcome_id quote_id contract_id
 settled_at disposition settlement_policy settlement_version supersedes_id
 source_receipt_ids computation_sha256""".split(),
 "TrainingUpdateReceipt": """training_state_id sport model_id prior_artifact_sha256
 new_artifact_sha256 observation_cutoff_at updated_at settlement_ids
 source_receipt_ids model_code_sha state_sha256 update_mode""".split(),
 "ExperimentManifest": """experiment_id sport created_at frozen_code_sha
 protocol_sha256 eligible_universe primary_metric baseline challenger
 cutoff_policy freeze_policy approval_state evidence_refs""".split(),
}
TIME_FIELDS = {"source_available_at","collected_at","input_freeze_at",
 "training_cutoff_at","created_at","event_start_at","forecast_at",
 "model_training_cutoff_at","quote_timestamp","official_result_available_at",
 "settled_at","observation_cutoff_at","updated_at"}
HASH_FIELDS = {"source_sha256","feature_sha256","artifact_sha256",
 "training_data_sha256","input_sha256","output_sha256",
 "official_source_sha256","computation_sha256","prior_artifact_sha256",
 "new_artifact_sha256","state_sha256","protocol_sha256"}
CODE_FIELDS = {"model_code_sha","frozen_code_sha"}
FORBIDDEN_TARGET_FEATURES = {"actual_minutes","realized_minutes",
 "realized_usage","final_score","outcome","target_game_boxscore",
 "target_game_result","target_game_play_by_play","future_outcomes"}

class AdmissionError(ValueError):
    pass

def fail(code):
    raise AdmissionError(code)

def canonical_bytes(obj):
    try:
        return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (TypeError,ValueError) as exc:
        raise AdmissionError("NONCANONICAL_JSON") from exc

def sha256(obj):
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()

def utc(value):
    if not isinstance(value,str) or not re.search(r"(Z|\+00:00)$",value):
        fail("TIMESTAMP_MUST_BE_UTC_AWARE")
    try:
        dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise AdmissionError("TIMESTAMP_INVALID") from exc
    if dt.utcoffset()!=timedelta(0):
        fail("TIMESTAMP_MUST_BE_UTC_AWARE")
    return dt

def valid_id(x):
    return isinstance(x,str) and x.strip()==x and bool(x) and "\x00" not in x

def _require_hash(value,code):
    if not isinstance(value,str) or HEX64.fullmatch(value) is None:
        fail(code)

def relative_path(value):
    if not valid_id(value) or "\\" in value or Path(value).is_absolute() or \
       any(p in (".","..","") for p in value.split("/")):
        fail("UNSAFE_ARCHIVE_PATH")
    return value

def _feature_keys(v):
    if isinstance(v,dict):
        for k,child in v.items():
            if k in FORBIDDEN_TARGET_FEATURES:
                fail("TARGET_GAME_OUTCOME_AS_PREGAME_FEATURE")
            _feature_keys(child)
    elif isinstance(v,list):
        for child in v:
            _feature_keys(child)


def validate_distribution(d):
    if not isinstance(d,dict) or not isinstance(d.get("kind"),str):
        fail("DISTRIBUTION_MISSING")
    kind=d["kind"]
    if kind in ("discrete","scenario_pmf"):
        masses=d.get("masses")
        if not isinstance(masses,list) or not masses:
            fail("DISTRIBUTION_MASS_MISSING")
        seen=set()
        for x,p in masses:
            if type(x) is not int or x<0 or type(p) not in (int,float) or \
               not math.isfinite(p) or p<0 or x in seen:
                fail("DISTRIBUTION_MASS_OR_SUPPORT_INVALID")
            seen.add(x)
        if abs(math.fsum(p for x,p in masses)-1.0)>1e-10:
            fail("DISTRIBUTION_NOT_NORMALIZED")
    elif kind in ("poisson","gamma_poisson","nb2"):
        params=d.get("parameters",{})
        if not isinstance(params,dict) or not params:
            fail("DISTRIBUTION_PARAMETERS_MISSING")
        for v in params.values():
            if type(v) not in (int,float) or not math.isfinite(v) or v<0:
                fail("DISTRIBUTION_PARAMETERS_INVALID")
    elif kind=="scenario_ref":
        if not isinstance(d.get("count"),int) or d["count"]<=0:
            fail("SCENARIO_COUNT_INVALID")
        _require_hash(d.get("scenario_sha256"),"SCENARIO_SHA_INVALID")
        if d.get("support")!="nonnegative_integer":
            fail("SCENARIO_SUPPORT_INVALID")
    elif kind=="fixed_line":
        probs=(d.get("over"),d.get("under"),d.get("push"))
        if any(type(x) not in (int,float) or not math.isfinite(x) or
               not 0<=x<=1 for x in probs) or abs(math.fsum(probs)-1)>1e-10:
            fail("FIXED_LINE_PROBABILITY_INVALID")
    else:
        fail("DISTRIBUTION_KIND_UNREGISTERED")
    return True

def validate_record(kind, data):
    """Exact, versioned schema: unexpected or missing fields are rejected."""
    if kind not in SCHEMAS:
        fail("UNKNOWN_RECORD_KIND")
    if not isinstance(data,dict) or data.get("record_type")!=kind or \
       data.get("schema_version")!=VERSION:
        fail("SCHEMA_MISMATCH")
    expected=set(SCHEMAS[kind])|{"record_type","schema_version"}
    if set(data)!=expected:
        fail("REQUIRED_OR_UNKNOWN_FIELDS:"+",".join(sorted(set(data)^expected)))
    for key,value in data.items():
        if key in ID_FIELDS:
            nullable=(kind,key) in {
                ("ForecastSnapshot","quote_id"),
                ("SettlementRecord","quote_id"),
                ("SettlementRecord","contract_id"),
            }
            if not (nullable and value is None) and not valid_id(value):
                fail("INVALID_ID:"+key)
        if key in TIME_FIELDS:
            utc(value)
        if key in HASH_FIELDS:
            _require_hash(value,"INVALID_SHA256:"+key)
        if key in CODE_FIELDS and (not isinstance(value,str) or
                                  HEX40.fullmatch(value) is None):
            fail("INVALID_CODE_SHA:"+key)
    if kind=="SourceReceipt":
        relative_path(data["archive_path"])
        if data["provenance_class"] not in ("original_publication","collector_possession"):
            fail("INVALID_SOURCE_PROVENANCE")
        if utc(data["source_available_at"])>utc(data["collected_at"]):
            fail("SOURCE_CAPTURED_BEFORE_AVAILABLE")
        if data["provenance_class"]=="collector_possession" and \
           data["source_available_at"]!=data["collected_at"]:
            fail("POSSESSION_CLOCK_NOT_EXACT")
    if kind=="PregameFeatureSnapshot":
        if data["reconstruction_class"] not in ("original","reconstructed"):
            fail("RECONSTRUCTION_CLASS_INVALID")
        if not isinstance(data["features"],dict):
            fail("FEATURES_NOT_OBJECT")
        _feature_keys(data["features"])
        if sha256(data["features"])!=data["feature_sha256"]:
            fail("FEATURE_HASH_MISMATCH")
    if kind=="ModelArtifact":
        relative_path(data["artifact_path"])
        if utc(data["training_cutoff_at"])>utc(data["created_at"]):
            fail("MODEL_TRAINED_BEFORE_CUTOFF")
    if kind=="ForecastSnapshot":
        if data["sport"] not in ("NBA","NHL") or data["team_id"]==data["opponent_id"]:
            fail("SPORT_OR_TEAM_IDENTITY_INVALID")
        if type(data["season"]) is not int or data["season"]<1900:
            fail("INVALID_SEASON")
        if type(data["seed"]) is not int or data["seed"]<0:
            fail("SEED_INVALID")
        if data["admission_class"] not in ("A","B","C"):
            fail("INVALID_ADMISSION_CLASS")
        if type(data["eligible"]) is not bool or not isinstance(data["abstention_reasons"],list) \
           or any(not valid_id(x) for x in data["abstention_reasons"]):
            fail("INVALID_ELIGIBILITY")
        if data["eligible"] and data["abstention_reasons"]:
            fail("ELIGIBLE_WITH_ABSTENTIONS")
        if not isinstance(data["distribution"],dict) or \
           not valid_id(data["distribution"].get("kind")):
            fail("DISTRIBUTION_MISSING")
        validate_distribution(data["distribution"])
        if sha256(data["distribution"])!=data["output_sha256"]:
            fail("OUTPUT_HASH_MISMATCH")
        if not isinstance(data["uncertainty"],dict):
            fail("UNCERTAINTY_MISSING")
        if not isinstance(data["source_receipt_ids"],list) or \
           not data["source_receipt_ids"] or \
           len(set(data["source_receipt_ids"]))!=len(data["source_receipt_ids"]):
            fail("SOURCE_IDS_MISSING_OR_DUPLICATED")
        if not (utc(data["model_training_cutoff_at"])<=utc(data["input_freeze_at"])<=
                utc(data["forecast_at"])<utc(data["event_start_at"])):
            fail("FORECAST_TEMPORAL_ORDER")
        if data["admission_class"]=="A" and any(data[x] is not None for x in
                ("quote_id","line","side","market_probability")):
            fail("A_MUST_BE_MARKET_FREE")
        if data["admission_class"]=="B" and (not valid_id(data["quote_id"]) or
                data["line"] is None or data["side"] not in ("over","under")):
            fail("B_REQUIRES_EXACT_OFFER")
        if data["market_probability"] is not None:
            # May be computed downstream only from compatible actual two-sided
            # odds and explicit de-vig method; never admitted as a naked field.
            fail("UNATTESTED_MARKET_PROBABILITY")
    if kind=="MarketQuote":
        if data["quote_kind"] not in ("real","synthetic") or \
           data["side"] not in ("over","under","paired"):
            fail("INVALID_QUOTE_KIND_OR_SIDE")
        if data["team_id"]==data["opponent_id"]:
            fail("QUOTE_IDENTITY_CONFLICT")
        if isinstance(data["line"],bool) or not isinstance(data["line"],(int,float)) or \
           not math.isfinite(data["line"]):
            fail("INVALID_LINE")
        if not isinstance(data["terms"],dict) or type(data["accepted"]) is not bool:
            fail("INVALID_OFFER_TERMS")
        if data["accepted"] and data["reject_reason"] is not None or \
           not data["accepted"] and not valid_id(data["reject_reason"]):
            fail("INVALID_QUOTE_REJECTION")
        if utc(data["quote_timestamp"])>=utc(data["event_start_at"]):
            fail("POST_EVENT_QUOTE")
    if kind=="OutcomeRecord":
        if data["participation"] not in ("PLAYED","DNP","UNKNOWN"):
            fail("INVALID_PARTICIPATION")
        if data["status"] not in ("FINAL","PENDING","CORRECTED"):
            fail("OUTCOME_STATUS_INVALID")
        if data["participation"]=="DNP" and data["actual_value"] is not None:
            fail("DNP_IS_NOT_ZERO")
        if data["actual_value"] is not None and \
           (type(data["actual_value"]) not in (int,float) or
            not math.isfinite(data["actual_value"])):
            fail("INVALID_ACTUAL_VALUE")
    if kind=="SettlementRecord":
        if data["disposition"] not in ("HIT","MISS","PUSH","VOID","SCORED","PENDING"):
            fail("DISPOSITION_INVALID")
        if not isinstance(data["source_receipt_ids"],list):
            fail("SETTLEMENT_SOURCES_MISSING")
        if type(data["settlement_version"]) is not int or data["settlement_version"]<1:
            fail("SETTLEMENT_VERSION_INVALID")
    if kind=="TrainingUpdateReceipt":
        if utc(data["observation_cutoff_at"])>utc(data["updated_at"]):
            fail("TRAINING_USES_FUTURE_OUTCOMES")
        if not isinstance(data["settlement_ids"],list) or \
           not isinstance(data["source_receipt_ids"],list):
            fail("TRAINING_INPUTS_MISSING")
        if data["update_mode"] not in ("shadow_incremental","shadow_refit","no_update"):
            fail("UNAPPROVED_TRAINING_MODE")
    if kind=="ExperimentManifest":
        if data["approval_state"] not in ("shadow_only","independent_review_pending",
                                           "rejected","accepted_for_research"):
            fail("INVALID_EXPERIMENT_APPROVAL")
        if not isinstance(data["evidence_refs"],list):
            fail("EXPERIMENT_LINEAGE_MISSING")
    return data

def record(kind,**fields):
    payload={"record_type":kind,"schema_version":VERSION,**fields}
    return validate_record(kind,payload)

def verify_source_bytes(source,source_root):
    validate_record("SourceReceipt",source)
    root=Path(source_root).resolve(strict=True)
    relative_path(source["archive_path"])
    path=Path(source_root)/source["archive_path"]
    if path.is_symlink() or any(x.is_symlink() for x in path.parents if x!=Path(source_root)):
        fail("UNSAFE_SOURCE_SYMLINK")
    if not path.resolve(strict=True).is_relative_to(root):
        fail("SOURCE_ESCAPE")
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=source["source_sha256"]:
        fail("SOURCE_CONTENT_CHANGED")
    return True

IDENTITY=("sport","event_id","team_id","opponent_id","player_id","stat_key","period")

def admit_forecast(forecast,feature,model,sources,quote=None,*,source_root=None):
    """Fail-closed evidence check. No source_root => no original certification."""
    for kind,obj in (("ForecastSnapshot",forecast),("PregameFeatureSnapshot",feature),
                     ("ModelArtifact",model)):
        validate_record(kind,obj)
    if source_root is None:
        fail("ORIGINAL_SOURCE_BYTES_NOT_REVERIFIED")
    if forecast["feature_snapshot_id"]!=feature["feature_snapshot_id"] or \
       forecast["model_artifact_id"]!=model["model_artifact_id"]:
        fail("MODEL_FEATURE_REF_MISMATCH")
    if any(forecast[k]!=feature[k] for k in IDENTITY if k in feature):
        fail("FEATURE_IDENTITY_MISMATCH")
    if forecast["input_freeze_at"]!=feature["input_freeze_at"] or \
       forecast["input_sha256"]!=sha256(feature):
        fail("IMMUTABLE_INPUT_HASH_MISMATCH")
    if forecast["model_training_cutoff_at"]!=model["training_cutoff_at"] or \
       forecast["model_code_sha"]!=model["model_code_sha"] or \
       forecast["artifact_sha256"]!=model["artifact_sha256"] or \
       forecast["model_id"]!=model["model_id"] or \
       forecast["model_version"]!=model["model_version"]:
        fail("MODEL_ARTIFACT_IDENTITY_MISMATCH")
    # Model manifest fields alone cannot prove artifact integrity.
    path=Path(source_root)/model["artifact_path"]
    root=Path(source_root).resolve(strict=True)
    if path.is_symlink() or any(x.is_symlink() for x in path.parents if x!=Path(source_root)):
        fail("UNSAFE_MODEL_ARTIFACT_PATH")
    if not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
        fail("MODEL_ARTIFACT_BYTES_MISSING")
    if hashlib.sha256(path.read_bytes()).hexdigest()!=model["artifact_sha256"]:
        fail("MODEL_ARTIFACT_BYTES_CHANGED")
    if utc(model["created_at"])>utc(forecast["forecast_at"]):
        fail("MODEL_CREATED_AFTER_FORECAST")
    refs={s["receipt_id"]:s for s in sources}
    if len(refs)!=len(sources) or set(forecast["source_receipt_ids"])!=set(refs) or \
       not set(feature["source_receipt_ids"]).issubset(refs):
        fail("SOURCE_RECEIPT_SET_MISMATCH")
    for src in sources:
        verify_source_bytes(src,source_root)
        if utc(src["collected_at"])>utc(forecast["input_freeze_at"]) or \
           utc(src["source_available_at"])>utc(forecast["input_freeze_at"]):
            fail("FUTURE_SOURCE_LEAKAGE")
    if feature["reconstruction_class"]=="reconstructed":
        if forecast["admission_class"]!="C":
            fail("RECONSTRUCTED_MASQUERADES_AS_ORIGINAL")
    elif forecast["admission_class"]=="C":
        # C can contain original sources, but is explicitly still retrospective.
        pass
    if forecast["admission_class"]=="B":
        if quote is None:
            fail("B_MISSING_QUOTE")
        validate_record("MarketQuote",quote)
        if not quote["accepted"] or quote["quote_kind"]!="real" or \
           quote["quote_id"]!=forecast["quote_id"]:
            fail("B_AUTHENTIC_QUOTE_REQUIRED")
        for k in IDENTITY:
            if quote[k]!=forecast[k]:
                fail("QUOTE_FORECAST_IDENTITY_MISMATCH:"+k)
        if quote["side"] not in (forecast["side"],"paired") or \
           quote["line"]!=forecast["line"] or \
           utc(quote["quote_timestamp"])>utc(forecast["forecast_at"]) or \
           utc(quote["quote_timestamp"])>utc(forecast["input_freeze_at"]):
            fail("QUOTE_LINE_SIDE_OR_TIME_MISMATCH")
        if quote["source_receipt_id"] not in refs or \
           refs[quote["source_receipt_id"]]["source_sha256"]!=quote["source_sha256"]:
            fail("QUOTE_SOURCE_RECEIPT_MISMATCH")
        if "raw_quote_path" in quote["terms"] and \
           quote["terms"]["raw_quote_path"]!=refs[quote["source_receipt_id"]]["archive_path"]:
            fail("QUOTE_SOURCE_PATH_MISMATCH")
    elif quote is not None:
        fail("QUOTE_WITH_MARKET_FREE_FORECAST")
    return {"status":"ADMITTED_RESEARCH_ONLY","admission_class":forecast["admission_class"],
            "forecast_id":forecast["forecast_id"],"snapshot_sha256":sha256(forecast),
            "source_count":len(sources),"production_allowed":False}

def reject_duplicate_records(rows):
    seen_ids=set()
    seen_forecasts=set()
    for row in rows:
        k=row.get("record_type")
        validate_record(k,row)
        unique_key=(k,row[SCHEMAS[k][0]])
        if unique_key in seen_ids:
            fail("DUPLICATE_RECORD_ID")
        seen_ids.add(unique_key)
        if k=="ForecastSnapshot":
            natural=(row["sport"],row["event_id"],row["player_id"],row["stat_key"],
                     row["period"],row["model_artifact_id"],row["forecast_at"])
            if natural in seen_forecasts:
                fail("DUPLICATE_FORECAST_NATURAL_KEY")
            seen_forecasts.add(natural)
    return True


def admit_settlement(settlement, forecast, outcome, quote=None):
    """An official outcome is not an admissible pregame input."""
    validate_record("SettlementRecord",settlement)
    validate_record("ForecastSnapshot",forecast)
    validate_record("OutcomeRecord",outcome)
    if settlement["forecast_id"]!=forecast["forecast_id"] or \
       settlement["outcome_id"]!=outcome["outcome_id"]:
        fail("SETTLEMENT_REFERENCE_MISMATCH")
    for k in ("sport","event_id","team_id","player_id","stat_key","period"):
        if forecast[k]!=outcome[k]:
            fail("OUTCOME_IDENTITY_MISMATCH:"+k)
    if utc(outcome["official_result_available_at"])>utc(settlement["settled_at"]) or \
       utc(forecast["event_start_at"])>utc(outcome["official_result_available_at"]):
        fail("OUTCOME_NOT_AVAILABLE_FOR_SETTLEMENT")
    if outcome["status"]=="PENDING" and settlement["disposition"]!="PENDING":
        fail("EARLY_SETTLEMENT")
    if outcome["participation"]=="DNP" and settlement["disposition"] not in ("VOID","PENDING"):
        fail("DNP_IMPROPERLY_SCORED")
    if forecast["admission_class"]=="B":
        if quote is None or quote["quote_id"]!=settlement["quote_id"] or \
           quote["contract_id"]!=settlement["contract_id"]:
            fail("SETTLEMENT_QUOTE_MISMATCH")
        validate_record("MarketQuote",quote)
    elif settlement["quote_id"] is not None or settlement["contract_id"] is not None:
        fail("DISTRIBUTION_ONLY_SETTLEMENT_MUST_BE_UNPRICED")
    return {"status":"SETTLEMENT_ADMITTED_RESEARCH_ONLY",
            "settlement_sha256":sha256(settlement)}

def admit_training_update(update, settlements):
    validate_record("TrainingUpdateReceipt",update)
    if set(update["settlement_ids"])!={x["settlement_id"] for x in settlements}:
        fail("TRAINING_SETTLEMENT_SET_MISMATCH")
    for settlement in settlements:
        validate_record("SettlementRecord",settlement)
        if settlement["disposition"]=="PENDING" or \
           utc(settlement["settled_at"])>utc(update["observation_cutoff_at"]):
            fail("TRAINING_USES_UNRELEASED_SETTLEMENT")
    return {"status":"RESEARCH_TRAINING_RECEIPT_ADMITTED","sha256":sha256(update)}

