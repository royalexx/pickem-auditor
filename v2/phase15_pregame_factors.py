"""Opt-in Phase1.5 PRE-EVENT factor receipt protocol for future NBA/NHL runs.

Never converts postgame box-score values into purported pregame factors.
The first event's market and provenance must already be Phase0R-validated;
this module only certifies the logged factor *structure and capture order*.
A valid receipt remains shadow until its producing engine is separately vetted.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path

from .official_nba_nhl_capture import SettlementCaptureError,instant

NBA_STATS={"points","assists","rebounds","threes","pa","pr","ra","pra"}
FIELDS_REQUIRED={
 "NHL":("team_unblocked_attempts","probability_active","individual_share_if_active",
        "on_target_probability"),
 "NBA":("projected_minutes","projected_team_possessions",
        "player_usage_or_opportunity_rate","conditional_stat_rate_per_minute"),
}


def _num(v,name):
    if isinstance(v,bool):raise SettlementCaptureError("factor_boolean:"+name)
    try:f=float(v)
    except (TypeError,ValueError,OverflowError) as exc:
        raise SettlementCaptureError("factor_non_numeric:"+name) from exc
    if not math.isfinite(f):raise SettlementCaptureError("factor_nonfinite:"+name)
    return f


def _digest(b):return hashlib.sha256(b).hexdigest()


def validate_pregame_factor_receipt(receipt, *, source_root, possession_clock):
    """Validate origin, timing, support. Never assert empirical skill."""
    if not isinstance(receipt,dict) or receipt.get("schema")!="phase15_pregame_factor_receipt_v1":
        raise SettlementCaptureError("factor_schema_missing")
    sport=receipt.get("sport")
    stat=receipt.get("stat")
    if sport not in ("NHL","NBA") or (sport=="NHL" and stat!="shots on goal") or (
            sport=="NBA" and stat not in NBA_STATS):
        raise SettlementCaptureError("factor_stat_unsupported")
    for key in ("event_id","player_id","model_version","period"):
        if not isinstance(receipt.get(key),str) or not receipt[key]:
            raise SettlementCaptureError("factor_identity_missing:"+key)
    if receipt["period"]!="full":
        raise SettlementCaptureError("factor_period_invalid")
    now=instant(possession_clock)
    cap=instant(receipt.get("captured_at"))
    event=instant(receipt.get("event_start"))
    cutoff=instant(receipt.get("model_training_cutoff_at"))
    if cap!=now:
        raise SettlementCaptureError("factor_capture_clock_not_runtime")
    if cap>=event or cutoff>cap:
        raise SettlementCaptureError("factor_not_genuinely_pregame")
    sources=receipt.get("source_receipts")
    if not isinstance(sources,list) or not sources:
        raise SettlementCaptureError("factor_original_sources_missing")
    root=Path(source_root).resolve()
    refs=set()
    for sr in sources:
        if not isinstance(sr,dict):raise SettlementCaptureError("factor_source_invalid")
        relative=sr.get("archive_path")
        hash_=sr.get("sha256")
        if not isinstance(relative,str) or not relative or relative.startswith("/") or (
                "\\" in relative or ".." in relative.split("/")):
            raise SettlementCaptureError("factor_unsafe_source")
        if relative in refs:raise SettlementCaptureError("factor_duplicate_source")
        refs.add(relative)
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise SettlementCaptureError("factor_source_missing")
        if not isinstance(hash_,str) or _digest(path.read_bytes())!=hash_:
            raise SettlementCaptureError("factor_source_hash_mismatch")
        if instant(sr.get("retrieved_at"))>cap:
            raise SettlementCaptureError("factor_future_source")
    values=receipt.get("factors")
    if not isinstance(values,dict) or set(values)!=set(FIELDS_REQUIRED[sport]):
        raise SettlementCaptureError("factor_fields_missing_or_unrecognized")
    val={key:_num(values[key],key) for key in FIELDS_REQUIRED[sport]}
    if sport=="NHL":
        if val["team_unblocked_attempts"]<0 or any(
                not 0<=val[k]<=1 for k in (
                    "probability_active","individual_share_if_active","on_target_probability")):
            raise SettlementCaptureError("factor_nhl_support_violation")
        exp=(val["team_unblocked_attempts"]*val["probability_active"]*
             val["individual_share_if_active"]*val["on_target_probability"])
        if receipt.get("factorization")!="nhl_SOG_unblocked_team_attempt_product_v1":
            raise SettlementCaptureError("factor_nhl_model_definition_missing")
        provided=_num(receipt.get("implied_mean"),"nhl_implied_mean")
        if abs(provided-exp)>max(1e-8,1e-6*max(1,exp)):
            raise SettlementCaptureError("factor_nhl_product_not_coherent")
    else:
        # NBA counting components and combinations are NOT generally
        # a valid four-factor literal product. Require explicit nonmultiplicative
        # status, preserving what the collector actually claims.
        if (val["projected_minutes"]<0 or val["projected_minutes"]>80 or
                val["projected_team_possessions"]<0 or
                val["player_usage_or_opportunity_rate"]<0 or
                val["conditional_stat_rate_per_minute"]<0):
            raise SettlementCaptureError("factor_nba_support_violation")
        if receipt.get("factorization")!="nba_diagnostic_nonmultiplicative_v1":
            raise SettlementCaptureError("factor_nba_invalid_multiplicative_claim")
        if receipt.get("implied_mean") is not None:
            raise SettlementCaptureError("factor_nba_combo_mean_not_identified_from_fields")
    if receipt.get("production_promotion_allowed") is not False:
        raise SettlementCaptureError("factor_promotion_guard_missing")
    if receipt.get("source_status")!="shadow_original_runtime_inputs_only":
        raise SettlementCaptureError("factor_status_not_shadow")
    return {
        "valid_structure":True,
        "source_count":len(sources),
        "factor_field_count":len(val),
        "original_pregame_receipt_verified":True,
        "empirical_forecast_skill_verified":False,
        "released_to_production":False,
    }


def make_shadow_receipt(raw, *, source_root, observed_clock):
    """Stamp runtime first, reject post-event claims, then append only by caller."""
    if not isinstance(raw,dict):
        raise SettlementCaptureError("factor_raw_payload_not_dict")
    candidate=dict(raw)
    candidate["schema"]="phase15_pregame_factor_receipt_v1"
    candidate["captured_at"]=observed_clock
    candidate["source_status"]="shadow_original_runtime_inputs_only"
    candidate["production_promotion_allowed"]=False
    validated=validate_pregame_factor_receipt(candidate,source_root=source_root,
                                               possession_clock=observed_clock)
    candidate["validation_receipt"]=validated
    canonical=json.dumps(candidate,sort_keys=True,separators=(",",":"),
                         ensure_ascii=False,allow_nan=False).encode()
    candidate["receipt_sha256"]=_digest(canonical)
    return candidate
