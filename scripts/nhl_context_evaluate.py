"""Paired chronological challenger evaluation. No automatic model promotion."""
from __future__ import annotations

import math
from collections import defaultdict

import nhl_context_data as store


def baseline(training, *, player_id, position, line, target):
    """Frozen gamma-Poisson control; 5 position-average pseudo-games.

    This transparent control is NOT the older converged hierarchical posterior.
    That posterior must supply separate, cutoff-verified predictions for a
    direct comparison through paired_comparison().
    """
    from scipy.stats import nbinom
    peers = [r["target"] for r in training if r["position"] == position]
    if not peers:
        raise ValueError("no_baseline_position_population")
    personal = [r["target"] for r in training if r["player_id"] == player_id]
    shape = 5 * (sum(peers) + .5) / (len(peers) + .5) + sum(personal)
    rate = 5 + len(personal)
    p = rate/(rate+1)
    floor = math.floor(line)
    over = float(nbinom.sf(floor, shape, p))
    under = float(nbinom.cdf(floor-1 if float(line).is_integer() else floor, shape, p))
    push = float(nbinom.pmf(floor, shape, p)) if float(line).is_integer() else 0.
    return {"q_over": over, "q_under": under, "q_push": push,
            "log_predictive_density": float(nbinom.logpmf(target, shape, p))}


def metrics(records):
    if not records:
        raise ValueError("empty_holdout_predictions")
    brier, logloss, coverage, densities, calibration = [], [], [], [], defaultdict(list)
    pushes = 0
    for r in records:
        line, y = r["line"], r["target"]
        qs = [r[k] for k in ("q_over", "q_under", "q_push")]
        if not all(math.isfinite(q) and 0 <= q <= 1 for q in qs) or abs(sum(qs)-1) > 1e-8:
            raise ValueError("invalid_evaluation_probabilities")
        if y == line:
            pushes += 1
        else:
            denom = r["q_over"]+r["q_under"]
            if denom <= 0:
                raise ValueError("no_nonpush_probability_mass")
            p = min(1-1e-12, max(1e-12, r["q_over"]/denom))
            event = int(y > line)
            brier.append((p-event)**2)
            logloss.append(-event*math.log(p)-(1-event)*math.log1p(-p))
            calibration[min(9, int(p*10))].append((p,event))
        if r.get("log_predictive_density") is not None:
            densities.append(-r["log_predictive_density"])
        if "predictive_interval_90" in r:
            lo, hi = r["predictive_interval_90"]
            coverage.append(int(lo <= y <= hi))
    def mean(v):
        return sum(v)/len(v) if v else None
    return {"rows": len(records), "games": len({r["game_id"] for r in records}), "pushes": pushes,
            "nonpush_rows": len(brier), "brier_nonpush": mean(brier), "logloss_nonpush": mean(logloss),
            "mean_negative_log_predictive_density": mean(densities),
            "predictive_interval_90_coverage": mean(coverage),
            "calibration_bins": [{"bin": k, "n": len(v), "mean_probability": mean([p for p,_ in v]),
                                  "observed_frequency": mean([y for _,y in v])} for k,v in sorted(calibration.items())]}


def paired_comparison(challenger, incumbent, *, bootstrap=2000, seed=782):
    """Identical identities, market, line, outcome and dates; bootstrap by GAME.

    All candidate rows must be present in the comparator. Never shrink the
    evaluation population silently to a conveniently successful intersection.
    """
    import numpy as np
    def mapping(rows):
        result = {}
        for row in rows:
            key = (row["game_id"], row["player_id"], row["market"], row["line"])
            if key in result:
                raise ValueError("duplicate_comparison_prediction")
            if store.instant(row["training_cutoff_exclusive"]) > store.instant(row["start_time"]):
                raise ValueError("comparator_trained_on_future")
            result[key] = row
        return result
    a, b = mapping(challenger), mapping(incumbent)
    if not a or set(a) != set(b):
        raise ValueError("paired_population_mismatch")
    deltas = defaultdict(list)
    for key, left in a.items():
        right = b[key]
        if any(left[k] != right[k] for k in ("target", "start_time", "training_cutoff_exclusive")):
            raise ValueError("paired_outcome_date_or_training_cutoff_mismatch")
        if left["target"] == left["line"]:
            continue
        y = int(left["target"] > left["line"])
        def loss(row):
            metrics([row])  # probability contract
            return (row["q_over"]/(row["q_over"]+row["q_under"])-y)**2
        deltas[left["game_id"]].append(loss(left)-loss(right))
    if not deltas or bootstrap < 100:
        raise ValueError("insufficient_paired_bootstrap")
    clusters = list(deltas.values())
    sums = np.asarray([sum(c) for c in clusters])
    sizes = np.asarray([len(c) for c in clusters])
    rng = np.random.default_rng(seed)
    # Bounded memory even on full-population multi-year evaluations.
    samples = []
    for _ in range(bootstrap):
        draw = rng.integers(0, len(clusters), size=len(clusters))
        samples.append(float(sums[draw].sum()/sizes[draw].sum()))
    return {"paired_rows": len(a), "nonpush_games": len(clusters),
            "brier_delta_challenger_minus_incumbent": float(sums.sum()/sizes.sum()),
            "game_cluster_bootstrap_95_interval": np.quantile(samples,[.025,.975]).tolist(),
            "challenger": metrics(challenger), "incumbent": metrics(incumbent),
            "ranking_allowed": False, "automatic_promotion": False}
