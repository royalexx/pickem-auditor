"""Fail-closed eligibility policy for the uncalibrated NFL 2024 challenger.

This gate is *specific* to the experimental Bayesian-MC+team-XGBoost/active-zero
model family. It must not indiscriminately demote the independent production
consensus or NUTS family. Neither a high raw P(win) nor retrospective synthetic
line accuracy can certify Tier 1/2. Never auto-promote from this policy.
"""
from __future__ import annotations

SCHEMA = "nfl_uncalibrated_2024_challenger_tier_policy_v1"
CHALLENGER_FAMILY = "nfl_team_xgb_bayesian_mc_active_zero_2024_walkforward"
UNSAFE_FAMILIES = frozenset((
    CHALLENGER_FAMILY,
    "nfl_2024_weekly_expanding_training_after_results_v1",
    "xgboost_team_dirichlet_beta_nb_montecarlo_pre2024_v1",
    "nfl_active_zero_pre2024_xgb_hurdle_v1",
))
SUSPENDED_TIERS = frozenset(("Tier 1","Tier 2"))
BLOCK_REASON = "NFL_HYBRID_CHALLENGER_HIGH_CONFIDENCE_CALIBRATION_NOT_CERTIFIED"


def model_family(record):
    """Read explicit immutable provenance; never infer model identity from odds."""
    if not isinstance(record,dict):
        return None
    for field in ("model_family","model_schema","model_id","model_mode"):
        value=record.get(field)
        if isinstance(value,str) and value.strip():
            if value.strip() in UNSAFE_FAMILIES:
                return value.strip()
    for key in ("model","inputs","forecast","source_model"):
        nested=record.get(key)
        if isinstance(nested,dict):
            family=model_family(nested)
            if family:return family
    return None


def authorize(tier, *,family):
    if family in UNSAFE_FAMILIES and tier in SUSPENDED_TIERS:
        return {"eligible":False,"reason":BLOCK_REASON,
                "policy":SCHEMA,"family":family,
                "calibrated_tier_hit_rate_certified":False}
    return {"eligible":True,"reason":None,"policy":SCHEMA,
            "family":family,"calibrated_tier_hit_rate_certified":False}


def forecast_receipt():
    return {
        "model_family":CHALLENGER_FAMILY,
        "production_eligible":False,
        "tier1_eligible":False,"tier2_eligible":False,
        "tier1_tier2_block_reason":BLOCK_REASON,
        "probabilities_uncalibrated":True,
        "research_only":True,
        "policy":SCHEMA,
    }
