"""Minimum conservative predicted probabilities for the intended tier language.

These thresholds define candidate quality; a forecast probability is NOT a
demonstrated historical hit rate. Realized win rates require separate,
date-ordered settlement auditing and calibration before the >80% target may
be claimed as achieved. Missing sources never become confirmed lineup facts.
"""
from __future__ import annotations

import math

VERSION = "tier-quality-v3"
PREDICTIVE_FLOORS = {"Tier 1": 0.90, "Tier 2": 0.81, "Tier 3": 0.70}
DESCRIPTION = {
    "Tier 1": "Unicorn / exceptionally rare",
    "Tier 2": "Elite / target >80% realized conditional hit rate",
    "Tier 3": "Remarkable / high-conviction pick",
}


def assess(tier, q_win, *, blend_validated=False, q_market=None, require_edge=False):
    """Evaluate calibrated-confidence *thresholds* and comparable market edge.

    q_market must already be on the unconditional P(win) scale (push included
    when converting a conditional two-way no-vig quote). Price-independent
    model confidence is NOT evidence of positive edge. A nonnegative reference
    edge is necessary but not a sufficient assertion of wager profitability.
    """
    result = {"version": VERSION, "tier": tier, "eligible": False,
              "minimum_model_probability": PREDICTIVE_FLOORS.get(tier),
              "target_is_observed": False, "empirical_hit_rate_certified": False,
              "quality_definition": DESCRIPTION.get(tier, "No approved tier"),
              "reference_edge_evaluated": False,
              "value_evaluated": False, "market_reference_edge": None,
              "expected_value_evaluated": False}
    floor = PREDICTIVE_FLOORS.get(tier)
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
    if require_edge and q_market is None:
        result["reason"] = "COMPARABLE_MARKET_MISSING"
        return result
    if q_market is not None:
        if (isinstance(q_market, bool) or not isinstance(q_market, (int, float))
                or not math.isfinite(q_market) or not 0 <= q_market <= 1):
            result["reason"] = "COMPARABLE_MARKET_INVALID"
            return result
        result["market_reference_edge"] = q_win - q_market
        result["reference_edge_evaluated"] = True
        if q_win + 1e-12 < q_market:
            result["reason"] = "NEGATIVE_MARKET_REFERENCE_EDGE"
            return result
    if tier == "Tier 1" and not blend_validated:
        result["reason"] = "UNICORN_BLEND_NOT_VALIDATED"
        return result
    result["eligible"] = True
    result["reason"] = None
    return result
