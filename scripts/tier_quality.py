"""Minimum conservative predicted probabilities for the intended tier language.

These thresholds define candidate quality; a forecast probability is NOT a
demonstrated historical hit rate. Realized win rates require separate,
date-ordered settlement auditing and calibration before the >80% target may
be claimed as achieved. Missing sources never become confirmed lineup facts.
"""
from __future__ import annotations

import math

VERSION = "tier-quality-v2"
PREDICTIVE_FLOORS = {"Tier 1": 0.90, "Tier 2": 0.81, "Tier 3": 0.70}
DESCRIPTION = {
    "Tier 1": "Unicorn / exceptionally rare",
    "Tier 2": "Elite / target >80% realized conditional hit rate",
    "Tier 3": "Remarkable / high-conviction pick",
}


def assess(tier, q_win, *, blend_validated=False):
    """Authorize only a sufficiently high model probability, never a win-rate claim."""
    result = {"version": VERSION, "tier": tier, "eligible": False,
              "minimum_model_probability": PREDICTIVE_FLOORS.get(tier),
              "target_is_observed": False, "empirical_hit_rate_certified": False,
              "quality_definition": DESCRIPTION.get(tier, "No approved tier")}
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
    if tier == "Tier 1" and not blend_validated:
        result["reason"] = "UNICORN_BLEND_NOT_VALIDATED"
        return result
    result["eligible"] = True
    result["reason"] = None
    return result
