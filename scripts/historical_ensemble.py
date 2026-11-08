"""Post-shadow historical ensemble: raw outcome masses, explicit eligibility.

This helper never replaces immutable parent forecasts or promotes model health.
It is used only after same-run, pre-event sidecar reconciliation has succeeded.
"""
from __future__ import annotations

import math

HISTORICAL = ("Engine_A", "Bayesian_A", "Bayesian_B", "NUTS")
VERSION = "historical-ensemble-60-40-research-v1"


def _masses(model):
    if not isinstance(model, dict) or model.get("status") != "forecast":
        return None
    win, push = model.get("q_win"), model.get("q_push")
    if (type(win) not in (int, float) or type(push) not in (int, float)
            or not math.isfinite(win) or not math.isfinite(push)
            or not 0 <= win <= 1 or not 0 <= push < 1
            or win + push > 1 + 1e-12):
        return None
    return float(win), float(push)


def calculate(models, *, weight_historical=0.60, weight_b=0.40,
              required=("Engine_A",), min_historical=2):
    """Return guarded historical consensus plus B, or explicit abstention.

    Equal weights among *available* historical families. This is not an
    independence assumption or a calibration certificate. NUTS must already
    have passed the strict upstream adapter, not a provisional NUTS source.
    Model family participation is recorded for prospective comparison.
    """
    if (not isinstance(models, dict)
            or type(weight_historical) not in (float, int)
            or type(weight_b) not in (float, int)
            or not math.isclose(weight_historical + weight_b, 1., abs_tol=1e-12)
            or not 0 < weight_historical < 1
            or min_historical < 2):
        raise ValueError("invalid_historical_ensemble_policy")

    included, unavailable = {}, {}
    for name in HISTORICAL:
        item = models.get(name)
        if name == "NUTS" and isinstance(item, dict) and (
                item.get("provisional") is True
                or item.get("strict_convergence_passed") is False):
            unavailable[name] = "non_strict_nuts_not_production_eligible"
            continue
        result = _masses(item)
        if result is None:
            unavailable[name] = (item or {}).get("reason", "missing_or_invalid_model")
        else:
            included[name] = result
    b = _masses(models.get("Engine_B"))
    outcome = {
        "version": VERSION,
        "historical_families": list(included),
        "historical_unavailable": unavailable,
        "historical_family_weights": {},
        "weight_historical": float(weight_historical),
        "weight_b": float(weight_b),
        "status": "unavailable",
        "publication_eligible": False,
        "empirically_calibrated": False,
        "q_win": None, "q_push": None, "q_loss": None, "probability": None,
    }
    if any(name not in included for name in required):
        outcome["reason"] = "required_historical_model_missing"
        return outcome
    if len(included) < min_historical:
        outcome["reason"] = "insufficient_historical_model_coverage"
        return outcome
    if b is None:
        outcome["reason"] = "engine_b_missing_or_invalid"
        return outcome
    n = len(included)
    history_win = sum(item[0] for item in included.values()) / n
    history_push = sum(item[1] for item in included.values()) / n
    win = weight_historical * history_win + weight_b * b[0]
    push = weight_historical * history_push + weight_b * b[1]
    if push >= 1 or win + push > 1 + 1e-12:
        outcome["reason"] = "invalid_mixed_probability_mass"
        return outcome
    outcome.update(
        status="forecast", reason=None,
        historical_family_weights={k: weight_historical/n for k in included},
        q_win=win, q_push=push, q_loss=max(0., 1-win-push),
        probability=win/(1-push),
    )
    return outcome
