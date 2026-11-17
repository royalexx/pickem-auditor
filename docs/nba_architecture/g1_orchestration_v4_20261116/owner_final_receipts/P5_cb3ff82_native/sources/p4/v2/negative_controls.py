"""P1-04/P1-06: executable negative controls on explicit retrospective folds.

Controls deliberately perturb historical outcome labels and opponent labels;
they are never original source documents. A control's result cannot be
interpreted as a certified pregame run or as a statistical significance claim.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import random

from .contracts import ContractError
from .rolling import run_rolling, MODELS


def _rates(result, model):
    out = {}
    for row in result["contract_ledger"]:
        vote = row["model_results"].get(model)
        if isinstance(vote,dict) and "rate" in vote:
            out[row["quote_id"]] = vote["rate"]
    return out


def run_negative_controls(original: dict, *, seed: int = 20261109) -> dict:
    if not isinstance(original,dict):
        raise ContractError("negative_controls_invalid_input")
    reference = run_rolling(original,seed=seed)
    controls = {}
    # Label shuffling tests whether the constructed *forecasts* depend on
    # target outcomes. For already-frozen historical training data, preserve
    # labels and alter only future settlement outcomes, not past training.
    labels = deepcopy(original)
    by_stat = defaultdict(list)
    for i,row in enumerate(labels["settlements"]):
        if row["status"] == "settled":
            by_stat[(row["stat_key"],row["period"])].append(i)
    rng = random.Random(seed)
    for indices in by_stat.values():
        values = [labels["settlements"][i]["actual"] for i in indices]
        rng.shuffle(values)
        for i,val in zip(indices,values):
            labels["settlements"][i]["actual"] = val
    placebo = run_rolling(labels,seed=seed)
    for model in MODELS[:2]:
        if _rates(reference,model)!=_rates(placebo,model):
            raise ContractError("negative_control_future_outcome_leaks_into_forecast")
    controls["permuted_outcomes"] = {
        "status":"passed_no_target_feedback_into_frozen_prediction",
        "score_is_diagnostic_only":True,
        "baseline_brier_original":reference["models"][MODELS[0]]["brier"],
        "baseline_brier_permuted_labels":placebo["models"][MODELS[0]]["brier"],
    }
    # Opponent perturbation cannot affect the intentionally opponent-free
    # historical-rate controls. In later matchup challengers, this same
    # diagnostic must be interpreted differently.
    opponents = deepcopy(original)
    keys = sorted({q["opponent_id"] for q in opponents["quotes"]})
    if len(keys) < 2:
        controls["permuted_opponents"] = {
            "status":"not_identifiable_fewer_than_two_distinct_opponents",
            "baseline_is_opponent_agnostic":True}
    else:
        mapping={key:keys[(i+1)%len(keys)] for i,key in enumerate(keys)}
        for q in opponents["quotes"]:
            transformed = mapping[q["opponent_id"]]
            if transformed==q["team_id"]:
                # An illegal same-team match is never used as a control.
                controls["permuted_opponents"] = {
                    "status":"skipped_illegal_identity_collision"}
                break
            q["opponent_id"]=transformed
            # This is now a synthetic perturbed quote, NOT the original.
            q["quote_kind"]="synthetic"
            q["product_type"]="diagnostic_only"
            q["over_decimal_odds"]=None
            q["under_decimal_odds"]=None
            q["quote_receipt_sha256"]=hashlib.sha256(
                json.dumps(q,sort_keys=True).encode("utf-8")).hexdigest()
        else:
            shuffled = run_rolling(opponents,seed=seed)
            for model in MODELS[:2]:
                if _rates(reference,model)!=_rates(shuffled,model):
                    raise ContractError("negative_control_opponent_changed_agnostic_baseline")
            controls["permuted_opponents"]={
                "status":"passed_opponent_agnostic_baseline_invariant",
                "number_of_opponents":len(keys),
                "artificial_quotes_are_not_real_market_evidence":True}
    return {
        "schema":"v25-negative-controls-1","seed":seed,
        "controls":controls,"production_promotion_authorized":False,
        "source_authentication_claimed":False,
    }
