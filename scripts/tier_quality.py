"""Minimum conservative predicted probabilities for the intended tier language.

These thresholds define candidate quality; a forecast probability is NOT a
demonstrated historical hit rate. Realized win rates require separate,
date-ordered settlement auditing and calibration before the >80% target may
be claimed as achieved. Missing sources never become confirmed lineup facts.
"""
from __future__ import annotations

import math

VERSION = "tier-quality-v3"
# The NFL 2024 active-zero/online XGBoost + Bayesian Monte Carlo challenger
# failed a historical high-confidence calibration audit. Do not confuse
# this research variant with the production consensus or accepted NUTS models.
SUSPENDED_CHALLENGER_IDS = frozenset({
    "nfl_2024_weekly_expanding_training_after_results_v1",
    "nfl_2024_weekly_xgb_bayesian_mc_active_zero_hurdle",
    "nfl_2024_activezero_hybrid_research_challenger",
    "2024_hybrid_activezero_pre2024_numpy2_clean_v3",
})
CHALLENGER_SUSPENDED_TIERS = frozenset(("Tier 1", "Tier 2"))


def identify_model_provenance(row):
    """Fail closed on explicitly tagged challenger artifacts, never infer lineage.

    Use the exact source identity recorded on the forecast rather than
    probabilities or the NFL market name, which would also block production
    consensus and other separately validated models.
    """
    if not isinstance(row, dict):
        return None
    inputs = row.get("inputs") if isinstance(row.get("inputs"), dict) else {}
    for source in (row, inputs):
        for key in ("model_provenance", "model_id", "challenger_id",
                    "model_schema", "forecast_model_id"):
            value = source.get(key)
            if isinstance(value, str) and value in SUSPENDED_CHALLENGER_IDS:
                return value
    return None
PREDICTIVE_FLOORS = {"Tier 1": 0.90, "Tier 2": 0.81, "Tier 3": 0.70}
DESCRIPTION = {
    "Tier 1": "Unicorn / exceptionally rare",
    "Tier 2": "Elite / target >80% realized conditional hit rate",
    "Tier 3": "Remarkable / high-conviction pick",
}


def assess(tier, q_win, *, blend_validated=False, model_provenance=None):
    """Authorize only a sufficiently high model probability, never a win-rate claim."""
    result = {"version": VERSION, "tier": tier, "eligible": False,
              "minimum_model_probability": PREDICTIVE_FLOORS.get(tier),
              "target_is_observed": False, "empirical_hit_rate_certified": False,
              "quality_definition": DESCRIPTION.get(tier, "No approved tier")}
    floor = PREDICTIVE_FLOORS.get(tier)
    if isinstance(model_provenance, str) and model_provenance in SUSPENDED_CHALLENGER_IDS:
        result["model_provenance"] = model_provenance
        result["production_authorized"] = False
        result["suspension_scope"] = "NFL_2024_ACTIVE_ZERO_XGB_BAYES_CHALLENGER_ONLY"
        if tier in CHALLENGER_SUSPENDED_TIERS:
            result["reason"] = "CHALLENGER_TIER_1_2_SUSPENDED_UNCALIBRATED"
        else:
            result["reason"] = "CHALLENGER_RESEARCH_ONLY_NO_PRODUCTION_AUTHORIZATION"
        return result
    if floor is None:
        result["reason"] = "NO_APPROVED_TIER"
        return result
    if (isinstance(q_win, bool) or not isinstance(q_win, (int, float))
            or not math.isfinite(q_win) or not 0 <= q_win <= 1):
        result["reason"] = "MODEL_PROBABILITY_UNVERIFIED"
        return result
    if q_win < floor:
        result["reason"] = "BELOW_TIER_MODEL_PROBABILITY_FLOOR"
        return result
    if tier == "Tier 1" and not blend_validated:
        result["reason"] = "UNICORN_BLEND_NOT_VALIDATED"
        return result
    result["eligible"] = True
    result["reason"] = None
    return result
