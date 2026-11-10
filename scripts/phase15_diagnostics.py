#!/usr/bin/env python3
"""Phase 1.5: read-only forecast-error decomposition and Tier power planning.

Never fits a model, alters predictions, certifies historic quotes, publishes a
Tier, or uses realized outcomes as pregame covariates. Historical synthetic
contracts are distribution/direction diagnostics ONLY.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import random

SCHEMA = "pickem-phase15-diagnostics-v1"
COMPONENTS = ("team_volume", "participation", "share", "efficiency")
POWER_PAIRS = ((.70, .80), (.75, .80), (.80, .85), (.85, .90), (.90, .95))


class Phase15Error(ValueError):
    """Invalid evidence or schema: fail closed rather than silently excluding."""


def number(value, name, *, low=None, high=None):
    if isinstance(value, bool) or value is None or str(value).strip() == "":
        raise Phase15Error("missing_numeric:" + name)
    try:
        out = float(value)
    except (ValueError, TypeError) as exc:
        raise Phase15Error("bad_numeric:" + name) from exc
    if not math.isfinite(out) or (low is not None and out < low) or (high is not None and out > high):
        raise Phase15Error("invalid_numeric:" + name)
    return out


def aware(value, name):
    if not isinstance(value, str) or "T" not in value:
        raise Phase15Error("missing_timestamp:" + name)
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Phase15Error("invalid_timestamp:" + name) from exc
    if stamp.tzinfo is None:
        raise Phase15Error("naive_timestamp:" + name)
    return stamp.astimezone(timezone.utc)


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise Phase15Error("missing_header")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise Phase15Error("duplicate_header")
        return list(reader)


def key(row):
    names = ("week", "game_id", "player_id", "market")
    missing = [n for n in names if not str(row.get(n) or "").strip()]
    if missing:
        raise Phase15Error("missing_identity:" + ",".join(missing))
    return tuple(str(row[n]).strip() for n in names)


def mean(values):
    return sum(values) / len(values) if values else None


def logloss(p, y):
    p = min(max(p, 1e-12), 1 - 1e-12)
    return -(y * math.log(p) + (1 - y) * math.log1p(-p))


def score(rows, prop="model"):
    if not rows:
        return {"n": 0}
    pkey = "p_model" if prop == "model" else "p_baseline"
    brier = [(r[pkey] - r["over"]) ** 2 for r in rows]
    losses = [logloss(r[pkey], r["over"]) for r in rows]
    return {"n": len(rows), "brier": mean(brier), "log_loss": mean(losses),
            "mean_over_probability": mean([r[pkey] for r in rows]),
            "observed_over_rate": mean([r["over"] for r in rows]),
            "over_calibration_bias": mean([r[pkey] - r["over"] for r in rows])}


def bootstrap_interval(rows, value, *, cluster, replicates, seed):
    """Paired cluster bootstrap; resample games/weeks, not individual props."""
    groups = defaultdict(list)
    for r in rows:
        groups[r[cluster]].append(r)
    labels = sorted(groups)
    if len(labels) < 5 or replicates < 1:
        return {"status": "insufficient_clusters", "clusters": len(labels)}
    rng = random.Random(seed)
    values = []
    for _ in range(replicates):
        sampled = [r for _ in labels for r in groups[labels[rng.randrange(len(labels))]]]
        values.append(mean([value(r) for r in sampled]))
    values.sort()
    return {"status": "descriptive_bootstrap_not_a_promotion_test",
            "clusters": len(labels), "replicates": replicates,
            "lower_95": values[max(0, int(.025 * replicates))],
            "upper_95": values[min(replicates - 1, int(.975 * replicates))]}


def evaluate_contracts(source, *, replicates=1000, seed=20261110):
    """One player/stat/line/week per outcome; unavailable rows stay in denominator."""
    all_rows = read_csv(source)
    excluded = Counter()
    joined = []
    unique = set()
    for original in all_rows:
        identity = key(original)
        line = number(original.get("research_line"), "research_line")
        identity += (format(line, ".15g"),)
        if identity in unique:
            raise Phase15Error("duplicate_contract:" + repr(identity))
        unique.add(identity)
        result = str(original.get("result") or "").strip().upper()
        actual_raw = original.get("actual_stat")
        if actual_raw is None or str(actual_raw).strip() == "":
            if result not in ("", "UNMATCHED", "UNSETTLED", "VOID"):
                raise Phase15Error("outcome_status_mismatch")
            excluded[result or "UNSETTLED"] += 1
            continue
        if result in ("UNMATCHED", "VOID", "UNSETTLED"):
            raise Phase15Error("outcome_status_mismatch")
        actual = number(actual_raw, "actual_stat")
        if actual == line:
            excluded["PUSH"] += 1
            continue
        over = int(actual > line)
        p = number(original.get("model_p_over"), "model_p_over", low=0, high=1)
        baseline_raw = original.get("baseline_p_over")
        if baseline_raw is None or str(baseline_raw).strip() == "":
            excluded["missing_baseline"] += 1
            continue
        b = number(baseline_raw, "baseline_p_over", low=0, high=1)
        declared = str(original.get("predicted_side") or "").strip().lower()
        if declared not in ("over", "under"):
            raise Phase15Error("missing_prediction_side")
        if (p > .5 and declared != "over") or (p < .5 and declared != "under"):
            raise Phase15Error("frozen_side_probability_mismatch")
        chosen = p if declared == "over" else 1 - p
        hit = int((declared == "over") == bool(over))
        recorded_over = original.get("actual_over")
        if recorded_over not in (None, ""):
            if str(recorded_over).strip() not in ("0", "1") or int(recorded_over) != over:
                raise Phase15Error("recorded_over_outcome_mismatch")
        if result not in ("HIT", "MISS"):
            raise Phase15Error("invalid_scored_result_status")
        if (result == "HIT") != bool(hit):
            raise Phase15Error("settlement_status_mismatch")
        selected_recorded = original.get("selected_model_probability")
        if selected_recorded not in (None, ""):
            declared_confidence = number(selected_recorded, "selected_model_probability", low=0, high=1)
            if not math.isclose(declared_confidence, chosen, rel_tol=0, abs_tol=1e-9):
                raise Phase15Error("selected_probability_mismatch")
        game = str(original["week"]).strip() + "|" + str(original["game_id"]).strip()
        if original.get("hit") not in ("", None) and str(original["hit"]).strip() not in ("0", "1"):
            raise Phase15Error("invalid_settlement_hit")
        if original.get("hit") not in ("", None) and int(original["hit"]) != hit:
            raise Phase15Error("settlement_hit_mismatch")
        joined.append({"week": str(original["week"]), "game": game,
                       "market": str(original["market"]), "line_type": str(original.get("line_type") or ""),
                       "over": over, "p_model": p, "p_baseline": b,
                       "selected": chosen, "selected_side": declared, "hit": hit})
    model, base = score(joined, "model"), score(joined, "baseline")
    stats = {"input_rows": len(all_rows), "paired_scored_rows": len(joined),
             "excluded": dict(sorted(excluded.items())),
             "unique_games": len({r["game"] for r in joined}),
             "unique_weeks": len({r["week"] for r in joined}),
             "model": model, "baseline": base,
             "model_minus_baseline_brier": (model["brier"] - base["brier"]) if joined else None,
             "model_minus_baseline_log_loss": (model["log_loss"] - base["log_loss"]) if joined else None,
             "selected_under_fraction": mean([int(r["selected_side"] == "under") for r in joined]),
             "selected_hit_rate": mean([r["hit"] for r in joined]),
             "selected_80plus_n": sum(r["selected"] >= .80 for r in joined),
             "selected_80plus_hits": sum(r["hit"] for r in joined if r["selected"] >= .80),
             "by_side": {}, "by_market": {},
             "matched_paired_uncertainty": {},
             "line_types": dict(sorted(Counter(r["line_type"] for r in joined).items())),
             "limitations": [
                 "Historical predictions may have model-development exposure to the season.",
                 "Synthetic lines are not historical sportsbook offers or evidence of profitability.",
                 "Scored population excludes unmatched/push/missing-baseline rows; all are counted.",
                 "Over/Under on the same contract is one Bernoulli observation, not two independent legs.",
                 "Game/week bootstrap intervals are descriptive; multiple testing and selection apply."
             ]}
    for side in ("over", "under"):
        sub = [r for r in joined if r["selected_side"] == side]
        stats["by_side"][side] = {"n": len(sub), "hits": sum(r["hit"] for r in sub),
                                  "hit_rate": mean([r["hit"] for r in sub]),
                                  "mean_selected_probability": mean([r["selected"] for r in sub]),
                                  "confidence_minus_hit_rate": (mean([r["selected"] for r in sub])
                                         - mean([r["hit"] for r in sub])) if sub else None}
    for market in sorted({r["market"] for r in joined}):
        sub = [r for r in joined if r["market"] == market]
        model_m, base_m = score(sub), score(sub, "baseline")
        stats["by_market"][market] = {
            "n": len(sub), "games": len({r["game"] for r in sub}),
            "model_brier": model_m["brier"], "baseline_brier": base_m["brier"],
            "brier_difference": model_m["brier"] - base_m["brier"],
            "selected_under_fraction": mean([r["selected_side"] == "under" for r in sub])}
    for cluster in ("game", "week"):
        stats["matched_paired_uncertainty"][cluster] = bootstrap_interval(
            joined, lambda r: (r["p_model"] - r["over"]) ** 2
            - (r["p_baseline"] - r["over"]) ** 2,
            cluster=cluster, replicates=replicates, seed=seed)
    return stats


def oracle_loss(pred, actual, y, substituted):
    values = [actual[i] if i in substituted else pred[i] for i in range(4)]
    return (math.prod(values) - y) ** 2


def shapley_diagnostic(pred, actual, y):
    """Exact four-input Shapley attribution of squared-error reduction.

    Outcomes are inserted ONLY into offline oracle diagnostics. Attribution is
    a diagnostic association, not causal identification or pregame performance.
    """
    gains = {}
    for i, name in enumerate(COMPONENTS):
        accum = 0.
        remaining = [j for j in range(4) if j != i]
        for size in range(4):
            weight = math.factorial(size) * math.factorial(3-size) / math.factorial(4)
            for subset in combinations(remaining, size):
                s = set(subset)
                accum += weight * (oracle_loss(pred, actual, y, s)
                                   - oracle_loss(pred, actual, y, s | {i}))
        gains[name] = accum
    return gains


def evaluate_components(path, *, replicates=1000, seed=20261110):
    rows = read_csv(path)
    parsed, seen = [], set()
    for r in rows:
        ident = key(r)
        if ident in seen:
            raise Phase15Error("duplicate_component_row")
        seen.add(ident)
        if aware(r.get("forecast_at"), "forecast_at") >= aware(r.get("event_start_at"), "event_start_at"):
            raise Phase15Error("forecast_not_pregame")
        pred, actual = [], []
        for name in COMPONENTS:
            lo, hi = (0, 1) if name in ("participation", "share") else (0, None)
            pred.append(number(r.get("pred_" + name), "pred_" + name, low=lo, high=hi))
            actual.append(number(r.get("actual_" + name), "actual_" + name, low=lo, high=hi))
        y = number(r.get("actual_stat"), "actual_stat")
        if r.get("predicted_stat_mean") not in (None, ""):
            mean_in_archive = number(r["predicted_stat_mean"], "predicted_stat_mean")
            if not math.isclose(math.prod(pred), mean_in_archive, rel_tol=1e-6, abs_tol=1e-6):
                raise Phase15Error("reconstructed_forecast_mismatch")
        gains = shapley_diagnostic(pred, actual, y)
        parsed.append({"week": str(r["week"]), "game": str(r["week"]) + "|" + str(r["game_id"]),
                       "market": str(r["market"]), "gains": gains,
                       "base_loss": oracle_loss(pred, actual, y, set()),
                       "full_oracle_loss": oracle_loss(pred, actual, y, set(range(4))),
                       "actual_product_residual": math.prod(actual) - y})
    totals = {name: mean([r["gains"][name] for r in parsed]) for name in COMPONENTS}
    report = {"rows": len(parsed), "games": len({r["game"] for r in parsed}),
              "weeks": len({r["week"] for r in parsed}),
              "mean_original_squared_error": mean([r["base_loss"] for r in parsed]),
              "mean_full_oracle_squared_error": mean([r["full_oracle_loss"] for r in parsed]),
              "mean_realized_product_minus_outcome": mean([r["actual_product_residual"] for r in parsed]),
              "mean_shapley_error_reduction": totals,
              "clustered_95_intervals": {}, "by_market": {},
              "interpretation": "Postgame oracle sensitivity, not a deployable model, causality estimate or independently validated gain."}
    for name in COMPONENTS:
        report["clustered_95_intervals"][name] = {}
        for cluster in ("game", "week"):
            report["clustered_95_intervals"][name][cluster] = bootstrap_interval(
                parsed, lambda r, n=name: r["gains"][n],
                cluster=cluster, replicates=replicates, seed=seed)
    for market in sorted({r["market"] for r in parsed}):
        sub = [r for r in parsed if r["market"] == market]
        report["by_market"][market] = {"n": len(sub), "mean_shapley_error_reduction":
                                       {n: mean([r["gains"][n] for r in sub]) for n in COMPONENTS}}
    if parsed and abs(sum(totals.values())
                      - (report["mean_original_squared_error"] - report["mean_full_oracle_squared_error"])) > 1e-7:
        raise Phase15Error("shapley_conservation_failed")
    return report


def binom_survival(n, p):
    """Exact-stable binomial survival array indexed k: P(X >= k)."""
    if not 0 <= p <= 1 or n < 0:
        raise Phase15Error("invalid_binomial_parameters")
    if p == 0:
        return [1.] + [0.] * (n + 1)
    if p == 1:
        return [1.] * (n + 1) + [0.]
    mode = min(n, int((n + 1) * p))
    weights = [0.] * (n + 1)
    weights[mode] = 1.
    for k in range(mode, 0, -1):
        weights[k - 1] = weights[k] * k / (n - k + 1) * (1-p) / p
    for k in range(mode, n):
        weights[k + 1] = weights[k] * (n - k) / (k+1) * p / (1-p)
    normalizer = math.fsum(weights)
    tails = [0.] * (n + 2)
    accum = 0.
    for k in range(n, -1, -1):
        accum += weights[k] / normalizer
        tails[k] = min(1., accum)
    return tails


def binomial_power(p0, p1, *, alpha=.05, target=.80, maximum=5000):
    if not (0 < p0 < p1 < 1 and 0 < alpha < 1 and 0 < target < 1):
        raise Phase15Error("invalid_power_design")
    for n in range(1, maximum + 1):
        null_tails = binom_survival(n, p0)
        threshold = next((k for k in range(n+1) if null_tails[k] <= alpha), None)
        if threshold is not None:
            achieved = binom_survival(n, p1)[threshold]
            if achieved >= target:
                return {"null_rate": p0, "true_rate": p1, "independent_events": n,
                        "minimum_hits_for_rejection": threshold, "actual_alpha": null_tails[threshold],
                        "achieved_power": achieved, "target_power": target,
                        "test": "one_sided_exact_binomial_fixed_n"}
    return {"null_rate": p0, "true_rate": p1,
            "status": "not_reached_with_maximum", "maximum": maximum}


def power_table(*, alpha=.05, target=.80, weekly=20, mean_game_cluster=2.0):
    weekly = number(weekly, "weekly_independent_events", low=0)
    mean_game_cluster = number(mean_game_cluster, "mean_game_cluster", low=1)
    scenarios = []
    for p0, p1 in POWER_PAIRS:
        item = binomial_power(p0, p1, alpha=alpha, target=target)
        n = item.get("independent_events")
        if n:
            item["weeks_if_independent_events_per_week"] = (math.ceil(n / weekly) if weekly > 0 else None)
            item["cluster_sensitivity_not_measured"] = {
                str(rho): {"design_effect": 1 + (mean_game_cluster - 1) * rho,
                           "approx_raw_props_needed": math.ceil(n * (1+(mean_game_cluster-1)*rho))}
                for rho in (.05, .15, .30)}
        scenarios.append(item)
    return {"alpha": alpha, "target_power": target,
            "assumed_weekly_effectively_independent_events": weekly,
            "assumed_mean_game_cluster_size": mean_game_cluster, "scenarios": scenarios,
            "limitations": [
                "Exact binomial calculations assume prespecified independent identical Bernoulli trials.",
                "Cluster adjustment is design-effect sensitivity, not an estimated effective sample size.",
                "Repeated looks, adaptive candidate selection and multiple tier tests need adjustment.",
                "Counts establish detection power, not a guarantee that the true hit rate exceeds threshold."
            ]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contracts", type=Path)
    parser.add_argument("--components", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261110)
    parser.add_argument("--weekly-independent", type=float, default=20.)
    parser.add_argument("--mean-game-cluster", type=float, default=2.)
    parser.add_argument("--cohort-status", choices=["synthetic_historical", "real_prospective", "unknown"],
                        default="unknown")
    args = parser.parse_args(argv)
    if not args.contracts and not args.components:
        parser.error("provide at least one of --contracts or --components")
    if not 0 <= args.bootstrap <= 20000:
        parser.error("--bootstrap must be in [0,20000]")
    report = {"schema": SCHEMA, "mode": "read_only_diagnostic_not_certification",
              "cohort_status_user_declared": args.cohort_status,
              "promotion_allowed": False, "tier_certified": False,
              "original_model_unchanged": True,
              "provenance": {}, "missing_evidence": [], "power": power_table(
                  weekly=args.weekly_independent, mean_game_cluster=args.mean_game_cluster)}
    if args.contracts:
        report["provenance"]["contracts_sha256"] = sha256_file(args.contracts)
        report["contracts"] = evaluate_contracts(args.contracts, replicates=args.bootstrap, seed=args.seed)
    else:
        report["missing_evidence"].append("settled_contracts_csv")
    if args.components:
        report["provenance"]["components_sha256"] = sha256_file(args.components)
        report["opportunity_oracle"] = evaluate_components(args.components, replicates=args.bootstrap, seed=args.seed)
    else:
        report["missing_evidence"].append("point_in_time_predicted_and_realized_opportunity_components")
    if args.cohort_status != "real_prospective":
        report["missing_evidence"].append("certified_real_market_quote_and_payout_comparison")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(json.dumps({"output": str(args.output), "schema": SCHEMA, "promotion_allowed": False,
                      "paired_contracts": report.get("contracts", {}).get("paired_scored_rows", 0),
                      "oracle_rows": report.get("opportunity_oracle", {}).get("rows", 0)}))


if __name__ == "__main__":
    main()
