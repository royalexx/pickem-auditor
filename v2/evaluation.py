"""Deterministic matched-contract, prequential V2.5 shadow evaluation.

No production promotion, simulated prices, future calibration, or bet decisions.
One settlement key may serve multiple quoted lines, but each quoted contract
is counted once. Abstentions and rejected offers remain in the denominator.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import random
from typing import Iterable

from .contracts import (ContractError, ForecastSnapshot, MarketQuote, finite,
                        utc, no_vig_over)


@dataclass(frozen=True)
class Settlement:
    event_id: str
    player_id: str
    stat_key: str
    period: str
    status: str  # settled | void | unverified; pushed contracts derive from actual
    actual: float | None
    settled_at: str | None

    def __post_init__(self) -> None:
        if self.status not in ("settled", "void", "unverified"):
            raise ContractError("invalid_settlement_status")
        if self.status == "settled":
            if self.actual is None or self.settled_at is None:
                raise ContractError("settlement_actual_or_timestamp_missing")
            finite(self.actual, "actual")
            utc(self.settled_at, "settled_at")
        elif self.actual is not None:
            raise ContractError("nonsettled_actual_must_be_null")

    def key(self) -> tuple[str, str, str, str]:
        return self.event_id, self.player_id, self.stat_key, self.period


def brier(p: float, outcome: int) -> float:
    return (p - outcome) ** 2


LOG_LOSS_EPSILON = 1e-12  # Fixed, reported numerical convention.


def log_loss(p: float, outcome: int) -> float:
    """Finite log score with a disclosed floor for hard 0/1 predictions."""
    p = max(LOG_LOSS_EPSILON, min(1 - LOG_LOSS_EPSILON, p))
    return -math.log(p) if outcome == 1 else -math.log1p(-p)


def categorical_brier(probabilities: tuple[float, float, float],
                      observed: str) -> float:
    """Three-way Over/Under/Push Brier; a push is a real outcome, not a miss."""
    if observed not in ("over", "under", "push"):
        raise ContractError("unknown_categorical_settlement")
    if len(probabilities) != 3 or any(not 0 <= finite(x, "prob") <= 1
                                     for x in probabilities):
        raise ContractError("categorical_probability_invalid")
    if abs(math.fsum(probabilities)-1) > 1e-10:
        raise ContractError("categorical_mass_not_one")
    return math.fsum((p-int(index == ("over","under","push").index(observed)))**2
                     for index,p in enumerate(probabilities))


def categorical_log_loss(probabilities: tuple[float,float,float],
                         observed: str) -> float:
    if observed not in ("over", "under", "push"):
        raise ContractError("unknown_categorical_settlement")
    categorical_brier(probabilities, observed)
    return -math.log(max(LOG_LOSS_EPSILON,
                         probabilities[("over","under","push").index(observed)]))


def _calibration_bins(rows: list[dict]) -> list[dict]:
    bins = [(0., .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.00000001)]
    result = []
    for low, high in bins:
        selected = [r for r in rows if low <= r["p"] < high]
        result.append({"bin": f"[{low:.1f},{min(high,1):.1f}]",
                       "n": len(selected),
                       "predicted_over": _mean(r["p"] for r in selected),
                       "observed_over": _mean(r["observed_over"] for r in selected)})
    return result


def _mean(items: Iterable[float]) -> float | None:
    items = tuple(items)
    return math.fsum(items) / len(items) if items else None


def _cluster_interval(differences: list[tuple[str, float]], seed: int, n: int) -> dict:
    clusters: dict[str, list[float]] = defaultdict(list)
    for group, delta in differences:
        clusters[group].append(delta)
    if len(clusters) < 8:
        return {"status": "insufficient_clusters", "clusters": len(clusters), "interval": None}
    if n < 100:
        raise ContractError("bootstrap_replicates_too_small")
    keys = sorted(clusters)
    rng = random.Random(seed)
    draws = []
    for _ in range(n):
        chosen = (clusters[keys[rng.randrange(len(keys))]] for __ in keys)
        all_diffs = [d for subgroup in chosen for d in subgroup]
        draws.append(_mean(all_diffs))
    draws.sort()
    return {
        "status": "descriptive_only",
        "clusters": len(keys),
        "interval": [draws[int((n - 1) * .025)], draws[int((n - 1) * .975)]],
    }


def evaluate(quotes: list[MarketQuote], forecasts: list[ForecastSnapshot],
             settlements: list[Settlement], *, baseline_model: str = "frozen_v1",
             bootstrap_seed: int = 20261109, bootstrap_replicates: int = 1000) -> dict:
    """Evaluate exact contracts, with a full rejection and missingness ledger.

    Binary metrics are conditional on a non-push settlement. A model's
    probability of Over is q_over/(q_over+q_under), not raw q_over when pushes
    are possible; pushes are reported but never counted as missed predictions.
    """
    by_quote = {}
    contract_ids = set()
    for q in quotes:
        if q.quote_id in by_quote or q.contract_id in contract_ids:
            raise ContractError("duplicate_quote_or_contract_identity")
        by_quote[q.quote_id] = q
        contract_ids.add(q.contract_id)
    by_settlement = {}
    for s in settlements:
        if s.key() in by_settlement:
            raise ContractError("duplicate_settlement_identity")
        by_settlement[s.key()] = s
    by_model = {}
    ids = set()
    for f in forecasts:
        if f.quote_id not in by_quote:
            raise ContractError("forecast_unknown_quote")
        q = by_quote[f.quote_id]
        if not q.accepted:
            raise ContractError("forecast_for_rejected_quote")
        f.validate_against(q)
        if f.forecast_id in ids:
            raise ContractError("duplicate_forecast_id")
        ids.add(f.forecast_id)
        pair = f.quote_id, f.model_id
        if pair in by_model:
            raise ContractError("duplicate_model_quote")
        by_model[pair] = f
    models = sorted({f.model_id for f in forecasts})
    statuses = Counter()
    rejection_reasons = Counter()
    scored: dict[str, dict[str, dict]] = {model: {} for model in models}
    multiclass: dict[str, dict[str, dict]] = {model: {} for model in models}
    quoted_market = {}
    n_settled_contracts = 0
    n_scored_contracts = 0
    real_with_two_sided_prices = 0
    accepted_count = sum(q.accepted for q in quotes)
    for q in quotes:
        if not q.accepted:
            statuses["rejected"] += 1
            rejection_reasons[q.reject_reason] += 1
            continue
        statuses["accepted_real" if q.quote_kind == "real" else "accepted_synthetic"] += 1
        if no_vig_over(q) is not None:
            real_with_two_sided_prices += 1
        s = by_settlement.get(q.settlement_key())
        if s is None:
            statuses["missing_settlement"] += 1
            continue
        if s.status != "settled":
            statuses[s.status] += 1
            continue
        if utc(s.settled_at, "settled_at") < utc(q.event_start_at, "event_start_at"):
            raise ContractError("outcome_available_before_game")
        is_push = s.actual == q.line
        statuses["push" if is_push else "scorable"] += 1
        n_settled_contracts += 1
        n_scored_contracts += int(not is_push)
        observed_over = int(s.actual > q.line)
        observed_state = ("push" if is_push else "over" if observed_over else "under")
        real_market_over = no_vig_over(q)
        if real_market_over is not None and not is_push:
            quoted_market[q.quote_id] = {
                "p": real_market_over, "brier": brier(real_market_over,observed_over),
                "log_loss": log_loss(real_market_over,observed_over),
                "group": q.event_id, "observed_over": observed_over}
        for model in models:
            f = by_model.get((q.quote_id, model))
            if f is None:
                continue
            probs = f.distribution.probabilities(q.line)
            vector = (probs.over, probs.under, probs.push)
            multiclass[model][q.quote_id] = {
                "categorical_brier": categorical_brier(vector, observed_state),
                "categorical_log_loss": categorical_log_loss(vector,observed_state),
                "state": observed_state, "group": q.event_id,
                "date": utc(q.event_start_at,"event_start").date().isoformat(),
            }
            if is_push:
                continue
            p = probs.conditional_over()
            if p is None:
                # A distribution that always pushes cannot be scored as a binary event.
                continue
            chosen = 1 if p > .5 else 0 if p < .5 else None
            scored[model][q.quote_id] = {
                "brier": brier(p, observed_over),
                "log_loss_clipped": p < LOG_LOSS_EPSILON or p > 1 - LOG_LOSS_EPSILON,
                "log_loss": log_loss(p, observed_over),
                "hit": int(chosen == observed_over) if chosen is not None else None,
                "p": p, "observed_over": observed_over,
                "group": q.event_id, "synthetic": q.quote_kind == "synthetic",
                "date": utc(q.event_start_at,"event_start").date().isoformat(),
                "sport": q.sport, "stat": q.stat_key, "product_type": q.product_type,
                "forecast_sha256": f.snapshot_sha256,
            }
    summaries = {}
    for model in models:
        rows = list(scored[model].values())
        category_rows = list(multiclass[model].values())
        directional = [r["hit"] for r in rows if r["hit"] is not None]
        subsets = defaultdict(list)
        for qid, r in scored[model].items():
            quote = by_quote[qid]
            subsets[(quote.sport,quote.stat_key,quote.quote_kind)].append(r)
        stratified = {
            "|".join(k): {
                "n":len(v), "brier":_mean(x["brier"] for x in v),
                "log_loss":_mean(x["log_loss"] for x in v),
                "over_selection_rate":_mean(int(x["p"]>.5) for x in v),
                "observed_over_rate":_mean(x["observed_over"] for x in v),
            } for k,v in sorted(subsets.items())
        }
        summaries[model] = {
            "settled_three_way_scored":len(category_rows),
            "settled_three_way_total": n_settled_contracts,
            "categorical_brier":_mean(x["categorical_brier"] for x in category_rows),
            "categorical_log_loss":_mean(x["categorical_log_loss"] for x in category_rows),
            "categorical_push_n":sum(x["state"]=="push" for x in category_rows),
            "scorable_missing_forecast":n_scored_contracts-len(rows),
            "calibration_bins":_calibration_bins(rows),
            "stratified":stratified,
            "scored": len(rows), "scorable_contracts": n_scored_contracts,
            "forecasted_accepted_offers": sum((q.quote_id, model) in by_model for q in quotes if q.accepted),
            "offer_coverage": sum((q.quote_id, model) in by_model for q in quotes if q.accepted) / accepted_count if accepted_count else 0,
            "log_loss_clipped_rows": sum(r["log_loss_clipped"] for r in rows),
            "coverage": len(rows) / n_scored_contracts if n_scored_contracts else 0,
            "directional_n": len(directional), "hit_rate": _mean(directional),
            "brier": _mean(r["brier"] for r in rows),
            "log_loss": _mean(r["log_loss"] for r in rows),
            "predicted_over_share": _mean(int(r["p"] > .5) for r in rows if r["p"] != .5),
            "observed_over_share": _mean(r["observed_over"] for r in rows),
            "game_clusters": len({r["group"] for r in rows}),
            "synthetic_diagnostic_scored": sum(r["synthetic"] for r in rows),
        }
    paired = {}
    baseline = scored.get(baseline_model, {})
    for model in models:
        if model == baseline_model:
            continue
        common = sorted(set(scored[model]) & set(baseline))
        # Do not interpret mixed synthetic cohorts as real quote profitability.
        diffs = [(scored[model][c]["group"], scored[model][c]["brier"] - baseline[c]["brier"])
                 for c in common]
        by_date = [(scored[model][c]["date"],
                    scored[model][c]["brier"] - baseline[c]["brier"])
                   for c in common]
        ternary_common = sorted(set(multiclass[model]) & set(multiclass.get(baseline_model, {})))
        paired[model] = {
            "vs": baseline_model, "matched_contracts": len(common),
            "matched_settled_three_way": len(ternary_common),
            "brier_difference": _mean(d for _, d in diffs),
            "log_loss_difference": _mean(scored[model][c]["log_loss"] - baseline[c]["log_loss"] for c in common),
            "categorical_brier_difference": _mean(
                multiclass[model][c]["categorical_brier"] -
                multiclass[baseline_model][c]["categorical_brier"]
                for c in ternary_common),
            "categorical_log_loss_difference": _mean(
                multiclass[model][c]["categorical_log_loss"] -
                multiclass[baseline_model][c]["categorical_log_loss"]
                for c in ternary_common),
            "brier_cluster_interval": _cluster_interval(diffs, bootstrap_seed, bootstrap_replicates),
            "date_cluster_brier_interval": _cluster_interval(by_date,bootstrap_seed,bootstrap_replicates),
            "negative_is_better": True,
            "synthetic_diagnostic_count": sum(scored[model][c]["synthetic"] for c in common),
        }
    return {
        "schema": "v25-phase1-shadow-evaluation-1", "promotion_authorized": False,
        "log_loss_clip_epsilon": LOG_LOSS_EPSILON,
        "quotes_total": len(quotes), "statuses": dict(sorted(statuses.items())),
        "rejection_reasons": dict(sorted(rejection_reasons.items())),
        "real_two_sided_market_quotes": real_with_two_sided_prices,
        "scorable_contracts": n_scored_contracts,
        "settled_three_way_contracts": n_settled_contracts,
        "unforecasted_accepted_offers": {
            model:sum(q.accepted and (q.quote_id,model) not in by_model for q in quotes)
            for model in models},
        "real_market_binary_reference": {
            "scored":len(quoted_market),
            "brier":_mean(x["brier"] for x in quoted_market.values()),
            "log_loss":_mean(x["log_loss"] for x in quoted_market.values()),
            "note":"Conditional nonpush sportsbook quote benchmark; does not infer pickem pricing or push mass."},
        "models": summaries, "paired": paired,
        "bootstrap_seed": bootstrap_seed, "bootstrap_replicates": bootstrap_replicates,
    }


def crps_ensemble(samples: list[float], actual: float) -> float:
    """Empirical CDF CRPS; includes diagonal pairs consistently."""
    if not samples:
        raise ContractError("empty_ensemble")
    obs = finite(actual, "actual")
    x = [finite(v, "sample") for v in samples]
    n = len(x)
    return math.fsum(abs(v - obs) for v in x) / n - math.fsum(abs(a-b) for a in x for b in x) / (2*n*n)


def energy_score(scenarios: list[tuple[float, ...]], actual: tuple[float, ...]) -> float:
    """Euclidean energy score, empirical (biased) finite-ensemble form."""
    if not scenarios or not actual or any(len(x) != len(actual) for x in scenarios):
        raise ContractError("invalid_joint_dimensions")
    y = tuple(finite(x, "actual") for x in actual)
    xs = [tuple(finite(t, "scenario") for t in row) for row in scenarios]
    norm = lambda a, b: math.sqrt(math.fsum((u-v)**2 for u,v in zip(a,b)))
    n = len(xs)
    return math.fsum(norm(x,y) for x in xs)/n - math.fsum(norm(x,z) for x in xs for z in xs)/(2*n*n)


def variogram_score(scenarios: list[tuple[float, ...]], actual: tuple[float, ...],
                   *, power: float = 0.5, weights: tuple[tuple[float, ...], ...] | None = None) -> float:
    """Weighted unordered-pair VS_p; default p=.5, unit weights."""
    if not scenarios or len(actual) < 2 or any(len(x) != len(actual) for x in scenarios):
        raise ContractError("invalid_joint_dimensions")
    if power != 0.5:
        raise ContractError("unregistered_variogram_power")
    dim = len(actual)
    if weights is not None and (len(weights) != dim or any(len(r) != dim for r in weights)):
        raise ContractError("invalid_variogram_weights")
    y = tuple(finite(x, "actual") for x in actual)
    xs = [tuple(finite(t, "scenario") for t in row) for row in scenarios]
    score = 0.0
    for i in range(dim):
        for j in range(i+1, dim):
            weight = 1.0 if weights is None else finite(weights[i][j], "weight")
            if weight < 0:
                raise ContractError("negative_variogram_weight")
            obs = abs(y[i]-y[j]) ** power
            expected = math.fsum(abs(x[i]-x[j]) ** power for x in xs)/len(xs)
            score += weight*(obs-expected)**2
    return score
