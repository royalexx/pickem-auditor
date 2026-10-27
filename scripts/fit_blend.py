"""Walk-forward blend fit for Engine A, B, and market probabilities."""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pickem_math as pm

try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore
    _HAS_NUMPY = False

CODE_VERSION = "pickem-auditor-fit_blend/1"
MIN_SETTLED = 300
MIN_STAT_SPLIT = 100
BOOTSTRAP_SAMPLES = 500
RELIABILITY_BINS = 10
PROB_EPS = 1e-6
DEFAULT_L2 = 1.0
MEAN_BLEND_W_PRIOR = 0.5

DEFAULT_BLEND_WEIGHTS_PATH = pm.SKILL_ROOT / "config" / "blend_weights.json"

MODEL_ORDER = ("M0", "M1", "M2", "M3", "mean_blend")

M1_PRIORS = {"intercept": 0.0, "logit_qA": 1.0}
M2_PRIORS = {"intercept": 0.0, "logit_qA": 0.5, "logit_qM": 0.5}
M3_PRIORS = {"intercept": 0.0, "logit_qA": 0.5, "logit_qB": 0.0, "logit_qM": 0.5}


def logit(p: float) -> float:
    p = min(1.0 - PROB_EPS, max(PROB_EPS, float(p)))
    return math.log(p / (1.0 - p))


def sigmoid(z: float) -> float:
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def clip_prob(p: float) -> float:
    return min(1.0 - PROB_EPS, max(PROB_EPS, float(p)))


def brier_score(pairs: list[tuple[float, int]]) -> float | None:
    if not pairs:
        return None
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def log_loss(pairs: list[tuple[float, int]]) -> float | None:
    if not pairs:
        return None
    total = 0.0
    for prob, label in pairs:
        p = clip_prob(prob)
        total += -(label * math.log(p) + (1 - label) * math.log(1.0 - p))
    return total / len(pairs)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x <= 0 or den_y <= 0:
        return None
    return num / (den_x * den_y)


def reliability_bins(pairs: list[tuple[float, int]], n_bins: int = RELIABILITY_BINS) -> list[dict]:
    width = 1.0 / n_bins
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for prob, label in pairs:
        idx = min(n_bins - 1, int(prob / width))
        if prob >= 1.0:
            idx = n_bins - 1
        buckets[idx].append((prob, label))
    out = []
    for i, bucket in enumerate(buckets):
        low = i * width
        high = 1.0 if i == n_bins - 1 else (i + 1) * width
        n = len(bucket)
        if n:
            avg_p = sum(p for p, _y in bucket) / n
            hit = sum(_y for _p, _y in bucket) / n
        else:
            avg_p = None
            hit = None
        out.append({"bin": f"{low:.1f}-{high:.1f}", "n": n, "avg_prediction": avg_p, "hit_rate": hit})
    return out


def _solve_linear(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    mat = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = col
        for row in range(col + 1, n):
            if abs(mat[row][col]) > abs(mat[pivot][col]):
                pivot = row
        if abs(mat[pivot][col]) < 1e-14:
            continue
        mat[col], mat[pivot] = mat[pivot], mat[col]
        div = mat[col][col]
        for row in range(n):
            if row == col:
                continue
            factor = mat[row][col] / div
            for j in range(col, n + 1):
                mat[row][j] -= factor * mat[col][j]
        for j in range(col, n + 1):
            mat[col][j] /= div
    return [mat[i][n] for i in range(n)]


def _fit_logistic_newton(
    design: list[list[float]],
    y: list[int],
    priors: list[float],
    l2: float,
    max_iter: int = 60,
) -> list[float]:
    n_rows = len(y)
    n_feat = len(design[0]) if design else 0
    if n_rows == 0 or n_feat == 0:
        return priors[:]
    w = priors[:]

    for _ in range(max_iter):
        grad = [0.0] * n_feat
        hess = [[0.0] * n_feat for _ in range(n_feat)]
        max_delta = 0.0
        for i, row in enumerate(design):
            z = sum(w[j] * row[j] for j in range(n_feat))
            p = sigmoid(z)
            err = p - y[i]
            weight = p * (1.0 - p)
            for j in range(n_feat):
                grad[j] += row[j] * err
                for k in range(n_feat):
                    hess[j][k] += row[j] * row[k] * weight
        for j in range(n_feat):
            grad[j] += 2.0 * l2 * (w[j] - priors[j])
            hess[j][j] += 2.0 * l2
        try:
            delta = _solve_linear(hess, [-g for g in grad])
        except (IndexError, ZeroDivisionError):
            break
        for j in range(n_feat):
            w[j] += delta[j]
            max_delta = max(max_delta, abs(delta[j]))
        if max_delta < 1e-8:
            break
    return w


def _fit_logistic_numpy(
    design: list[list[float]],
    y: list[int],
    priors: list[float],
    l2: float,
    max_iter: int = 60,
) -> list[float]:
    x = np.asarray(design, dtype=float)
    yv = np.asarray(y, dtype=float)
    prior = np.asarray(priors, dtype=float)
    w = prior.copy()
    for _ in range(max_iter):
        z = x @ w
        p = 1.0 / (1.0 + np.exp(-z))
        err = p - yv
        grad = x.T @ err + 2.0 * l2 * (w - prior)
        weight = p * (1.0 - p)
        hess = x.T @ (x * weight[:, None]) + 2.0 * l2 * np.eye(len(w))
        try:
            delta = np.linalg.solve(hess, -grad)
        except np.linalg.LinAlgError:
            break
        w = w + delta
        if float(np.max(np.abs(delta))) < 1e-8:
            break
    return w.tolist()


def fit_logistic(
    rows: list[dict],
    feature_names: list[str],
    priors: dict[str, float],
    l2: float,
) -> dict[str, float]:
    if not rows:
        return {name: priors.get(name, 0.0) for name in ["intercept"] + feature_names}
    names = ["intercept"] + feature_names
    prior_vec = [priors.get(name, 0.0) for name in names]
    design = []
    y = []
    for row in rows:
        feats = row["features"]
        design.append([1.0] + [feats[name] for name in feature_names])
        y.append(row["label"])
    if _HAS_NUMPY:
        weights = _fit_logistic_numpy(design, y, prior_vec, l2)
    else:
        weights = _fit_logistic_newton(design, y, prior_vec, l2)
    return {name: weights[i] for i, name in enumerate(names)}


def predict_logistic(row: dict, weights: dict[str, float], feature_names: list[str]) -> float:
    z = weights.get("intercept", 0.0)
    feats = row["features"]
    for name in feature_names:
        z += weights.get(name, 0.0) * feats[name]
    return sigmoid(z)


def _unit_prob(value) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= number <= 1:
        return number
    return None


def _conditional_probability(win, push):
    win, push = _unit_prob(win), _unit_prob(push)
    if win is None or push is None or push >= 1 or win + push > 1 + 1e-9:
        return None
    return min(1.0, win / (1-push))


def _q_market(row: dict) -> float | None:
    market = row.get("market") if isinstance(row.get("market"), dict) else {}
    # Book q_market already conditions on no push. Prefer it to a comparable
    # probability built with some other model's push estimate.
    value = market.get("q_market", row.get("q_market"))
    if value is not None:
        return _unit_prob(value)
    return _conditional_probability(market.get("q_market_comparable", row.get("q_market_comparable")),
                                    row.get("q_push", 0))


def _q_engine_a(row: dict) -> float | None:
    block = row.get("engine_a") if isinstance(row.get("engine_a"), dict) else {}
    if block.get("q_win_robust") is not None:
        return _conditional_probability(block["q_win_robust"], block.get("q_push_robust", 0))
    return _conditional_probability(block.get("q_win", row.get("q_win")),
                                    block.get("q_push", row.get("q_push", 0)))


def _q_engine_b(row: dict) -> float | None:
    block = row.get("engine_b") if isinstance(row.get("engine_b"), dict) else {}
    if block.get("abstain"):
        return None
    return _conditional_probability(block.get("q_win"), block.get("q_push", 0))


def _mean_a(row: dict) -> float | None:
    block = row.get("engine_a") if isinstance(row.get("engine_a"), dict) else {}
    value = block.get("mean")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _mean_b(row: dict) -> float | None:
    block = row.get("engine_b") if isinstance(row.get("engine_b"), dict) else {}
    if block.get("abstain"):
        return None
    value = block.get("mean")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _b_abstained(row: dict) -> bool:
    block = row.get("engine_b") if isinstance(row.get("engine_b"), dict) else {}
    return bool(block.get("abstain"))


def _dist_fields(row: dict) -> dict | None:
    dist = row.get("dist")
    inputs = row.get("inputs") if isinstance(row.get("inputs"), dict) else {}
    if dist is None and isinstance(inputs, dict):
        dist = inputs.get("dist")
    side = row.get("side")
    line = row.get("reference_line")
    if line is None and isinstance(inputs, dict):
        line = inputs.get("line")
    if dist not in ("poisson", "negbin", "normal") or side not in ("over", "under"):
        return None
    try:
        line_n = float(line)
    except (TypeError, ValueError):
        return None
    sd = None
    var_ratio = None
    if dist == "normal":
        for source in (row, inputs):
            if isinstance(source, dict) and source.get("sd") is not None:
                sd = float(source["sd"])
                break
    if dist == "negbin":
        for source in (row, inputs):
            if isinstance(source, dict) and source.get("var_ratio") is not None:
                var_ratio = float(source["var_ratio"])
                break
    return {
        "dist": dist,
        "side": side,
        "line": line_n,
        "sd": sd,
        "var_ratio": var_ratio,
    }


def outcome_label(row: dict) -> int | None:
    outcome = row.get("outcome")
    if outcome == "win":
        return 1
    if outcome == "loss":
        return 0
    return None


def dedupe_settled(rows: list[dict]) -> list[dict]:
    by_side: dict[tuple, dict] = {}
    for row in rows:
        if outcome_label(row) is None:
            continue
        key = (
            str(row.get("game_date") or ""),
            str(row.get("player") or "").casefold(),
            str(row.get("stat") or "").casefold(),
            str(row.get("side") or "").casefold(),
        )
        prev = by_side.get(key)
        if prev is None or str(row.get("settled_at") or "") > str(prev.get("settled_at") or ""):
            by_side[key] = row
    return list(by_side.values())


def load_settled_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    rows = [row for _line_no, _line, row in pm.iter_snapshot_lines(text)]
    settled = [
        row for row in rows
        if str(row.get("status") or "").upper() == "GRADED" and outcome_label(row) is not None
    ]
    return dedupe_settled(settled)


def enrich_row(row: dict) -> dict | None:
    q_a = _q_engine_a(row)
    q_m = _q_market(row)
    if q_a is None or q_m is None:
        return None
    q_b = _q_engine_b(row)
    label = outcome_label(row)
    if label is None:
        return None
    features = {
        "logit_qA": logit(q_a),
        "logit_qM": logit(q_m),
    }
    if q_b is not None:
        features["logit_qB"] = logit(q_b)
    out = {
        "game_date": str(row.get("game_date") or ""),
        "stat": str(row.get("stat") or ""),
        "label": label,
        "qA": q_a,
        "qB": q_b,
        "qM": q_m,
        "features": features,
        "abstain_b": _b_abstained(row),
        "mean_a": _mean_a(row),
        "mean_b": _mean_b(row),
        "dist_fields": _dist_fields(row),
        "raw": row,
    }
    return out


def mean_blend_probability(row: dict, w: float) -> float | None:
    mean_a = row.get("mean_a")
    mean_b = row.get("mean_b")
    dist_info = row.get("dist_fields")
    if mean_a is None or mean_b is None or not dist_info:
        return None
    w = min(1.0, max(0.0, float(w)))
    blended_mean = w * mean_a + (1.0 - w) * mean_b
    dist = dist_info["dist"]
    kwargs = {}
    if dist == "normal":
        kwargs["sd"] = dist_info["sd"]
    if dist == "negbin":
        kwargs["r"] = dist_info["var_ratio"]
    try:
        q_win, _push = pm.side_probs(
            dist,
            blended_mean,
            dist_info["line"],
            dist_info["side"],
            **kwargs,
        )
    except pm.PickemError:
        return None
    return q_win / (1 - _push) if _push < 1 else None


def _mean_blend_loss(w: float, train: list[dict]) -> float:
    pairs = []
    for row in train:
        prob = mean_blend_probability(row, w)
        if prob is None:
            continue
        pairs.append((prob, row["label"]))
    ll = log_loss(pairs)
    if ll is None:
        return float("inf")
    penalty = DEFAULT_L2 * (w - MEAN_BLEND_W_PRIOR) ** 2
    return ll + penalty


def fit_mean_blend_w(train: list[dict]) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(80):
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        f1 = _mean_blend_loss(m1, train)
        f2 = _mean_blend_loss(m2, train)
        if f1 < f2:
            hi = m2
        else:
            lo = m1
    return 0.5 * (lo + hi)


def model_feature_names(model_id: str) -> list[str]:
    if model_id == "M1":
        return ["logit_qA"]
    if model_id == "M2":
        return ["logit_qA", "logit_qM"]
    if model_id == "M3":
        return ["logit_qA", "logit_qB", "logit_qM"]
    return []


def model_priors(model_id: str) -> dict[str, float]:
    if model_id == "M1":
        return dict(M1_PRIORS)
    if model_id == "M2":
        return dict(M2_PRIORS)
    if model_id == "M3":
        return dict(M3_PRIORS)
    return {}


def predict_model(model_id: str, row: dict, weights: dict | None) -> float | None:
    if model_id == "M0":
        return row["qM"]
    if model_id == "mean_blend":
        if weights is None:
            return None
        return mean_blend_probability(row, weights.get("w", MEAN_BLEND_W_PRIOR))
    names = model_feature_names(model_id)
    if weights is None:
        return None
    return predict_logistic(row, weights, names)


def walk_forward(
    rows: list[dict],
    models: tuple[str, ...],
    l2: float,
) -> tuple[dict[str, list[tuple[float, int]]], dict[str, dict[str, float] | None]]:
    dates = sorted({row["game_date"] for row in rows if row.get("game_date")})
    oof: dict[str, list[tuple[float, int]]] = {model: [] for model in models}
    last_weights: dict[str, dict[str, float] | None] = {model: None for model in models}
    for index, test_date in enumerate(dates):
        if index == 0:
            continue
        train = [row for row in rows if row["game_date"] < test_date]
        test = [row for row in rows if row["game_date"] == test_date]
        if not train or not test:
            continue
        for model_id in models:
            if model_id == "M0":
                fitted = None
            elif model_id == "mean_blend":
                train_mb = [row for row in train if row.get("mean_a") is not None and row.get("mean_b") is not None]
                if not train_mb:
                    fitted = None
                else:
                    fitted = {"w": fit_mean_blend_w(train_mb)}
            else:
                names = model_feature_names(model_id)
                if model_id == "M3":
                    train_fit = [row for row in train if "logit_qB" in row["features"]]
                else:
                    train_fit = train
                if not train_fit:
                    fitted = None
                else:
                    fitted = fit_logistic(train_fit, names, model_priors(model_id), l2)
            last_weights[model_id] = fitted
            for row in test:
                if model_id == "M3" and "logit_qB" not in row["features"]:
                    continue
                if model_id == "mean_blend" and (
                    row.get("mean_a") is None or row.get("mean_b") is None
                ):
                    continue
                prob = predict_model(model_id, row, fitted)
                if prob is None:
                    continue
                oof[model_id].append((prob, row["label"]))
    return oof, last_weights


def bootstrap_ci(
    pairs_a: list[tuple[float, int]],
    pairs_b: list[tuple[float, int]],
    metric: str,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = 42,
) -> dict | None:
    if len(pairs_a) != len(pairs_b) or not pairs_a:
        return None
    rng = random.Random(seed)
    n = len(pairs_a)
    diffs = []
    for _ in range(samples):
        idxs = [rng.randrange(n) for _ in range(n)]
        sample_a = [pairs_a[i] for i in idxs]
        sample_b = [pairs_b[i] for i in idxs]
        if metric == "brier":
            va = brier_score(sample_a)
            vb = brier_score(sample_b)
            if va is None or vb is None:
                continue
            diffs.append(va - vb)
        else:
            va = log_loss(sample_a)
            vb = log_loss(sample_b)
            if va is None or vb is None:
                continue
            diffs.append(va - vb)
    if not diffs:
        return None
    diffs.sort()
    lo = diffs[int(0.025 * len(diffs))]
    hi = diffs[int(0.975 * len(diffs))]
    return {"low": lo, "high": hi, "mean": sum(diffs) / len(diffs)}


def summarize_model(pairs: list[tuple[float, int]]) -> dict:
    return {
        "n": len(pairs),
        "brier": brier_score(pairs),
        "log_loss": log_loss(pairs),
        "reliability": reliability_bins(pairs),
    }


def compare_models(
    oof: dict[str, list[tuple[float, int]]],
    model_id: str,
    baselines: tuple[str, ...],
) -> dict:
    out = {}
    target = oof.get(model_id) or []
    for base in baselines:
        base_pairs = oof.get(base) or []
        if len(target) != len(base_pairs):
            out[base] = {"brier_diff_ci": None, "log_loss_diff_ci": None}
            continue
        out[base] = {
            "brier_diff_ci": bootstrap_ci(base_pairs, target, "brier"),
            "log_loss_diff_ci": bootstrap_ci(base_pairs, target, "log_loss"),
        }
    return out


def ab_diagnostics(rows: list[dict]) -> dict:
    scored = [row for row in rows if row.get("qB") is not None]
    if not scored:
        return {"correlation": None, "agreement_rate": None, "n": 0}
    q_as = [row["qA"] for row in scored]
    q_bs = [row["qB"] for row in scored]
    agree = 0
    for row in scored:
        same_side = (row["qA"] - 0.5) * (row["qB"] - 0.5) > 0
        close = abs(row["qA"] - row["qB"]) <= pm.CROSSCHECK_TOLERANCE_FLOOR
        if same_side or close:
            agree += 1
    return {
        "correlation": pearson(q_as, q_bs),
        "agreement_rate": agree / len(scored),
        "n": len(scored),
    }


def fit_final_weights(rows: list[dict], models: tuple[str, ...], l2: float) -> dict:
    weights = {}
    for model_id in models:
        if model_id == "M0":
            weights[model_id] = None
            continue
        if model_id == "mean_blend":
            train_mb = [row for row in rows if row.get("mean_a") is not None and row.get("mean_b") is not None]
            weights[model_id] = {"w": fit_mean_blend_w(train_mb)} if train_mb else None
            continue
        names = model_feature_names(model_id)
        train_fit = rows
        if model_id == "M3":
            train_fit = [row for row in rows if "logit_qB" in row["features"]]
        if not train_fit:
            weights[model_id] = None
        else:
            weights[model_id] = fit_logistic(train_fit, names, model_priors(model_id), l2)
    return weights


def stat_splits(rows: list[dict], models: tuple[str, ...], l2: float) -> dict:
    by_stat: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_stat[row["stat"]].append(row)
    out = {}
    for stat, group in sorted(by_stat.items()):
        if len(group) < MIN_STAT_SPLIT:
            continue
        dates = sorted({row["game_date"] for row in group})
        subset_oof, _weights = walk_forward(group, models, l2=l2)
        out[stat] = {
            "n": len(group),
            "dates": len(dates),
            "models": {model_id: summarize_model(subset_oof.get(model_id) or []) for model_id in models},
        }
    return out


def should_emit_config(report: dict, oof: dict[str, list[tuple[float, int]]]) -> tuple[bool, str]:
    m3 = oof.get("M3") or []
    m0 = oof.get("M0") or []
    m2 = oof.get("M2") or []
    if report.get("n_settled", 0) < MIN_SETTLED:
        return False, f"n_settled={report.get('n_settled')} < {MIN_SETTLED}"
    if len(m3) != len(m0) or len(m3) != len(m2):
        return False, "M3/M0/M2 out-of-fold rows are not aligned"
    for base, label in ((m0, "M0"), (m2, "M2")):
        ci = bootstrap_ci(base, m3, "log_loss")
        if ci is None:
            return False, f"log_loss CI vs {label} unavailable"
        if ci["low"] <= 0 <= ci["high"]:
            return False, f"log_loss improvement vs {label} CI includes 0 ({ci['low']:.4f}, {ci['high']:.4f})"
        if ci["mean"] <= 0:
            return False, f"M3 does not beat {label} on mean log_loss diff"
    return True, "M3 beats M0 and M2 on log_loss with 95% CI excluding 0"


def build_fit_report(rows_raw: list[dict], l2: float, force: bool) -> dict:
    enriched = [row for row in (enrich_row(row) for row in rows_raw) if row is not None]
    with_b = [row for row in enriched if not row["abstain_b"] and "logit_qB" in row["features"]]
    abstain = [row for row in enriched if row["abstain_b"]]

    cohort_with_b_models = ("M0", "M1", "M2", "M3", "mean_blend")
    cohort_abstain_models = ("M0", "M1", "M2")

    oof_with_b, _ = walk_forward(with_b, cohort_with_b_models, l2)
    oof_abstain, _ = walk_forward(abstain, cohort_abstain_models, l2)

    n_settled = len(enriched)
    underpowered = n_settled < MIN_SETTLED
    include_weights = (not underpowered) or force

    def cohort_block(rows: list[dict], models: tuple[str, ...], oof: dict) -> dict:
        model_reports = {}
        for model_id in models:
            pairs = oof.get(model_id) or []
            entry = summarize_model(pairs)
            entry["vs_M0"] = compare_models(oof, model_id, ("M0",))["M0"] if model_id != "M0" else None
            entry["vs_M2"] = compare_models(oof, model_id, ("M2",))["M2"] if model_id not in ("M0", "M2") else None
            model_reports[model_id] = entry
        weights = fit_final_weights(rows, models, l2) if include_weights else None
        if underpowered and force and weights is not None:
            stamp = "UNDERPOWERED"
        else:
            stamp = None
        return {
            "n": len(rows),
            "models": model_reports,
            "weights": weights,
            "weights_stamp": stamp,
        }

    report = {
        "code_version": CODE_VERSION,
        "fit_date": date.today().isoformat(),
        "l2_strength": l2,
        "n_settled": n_settled,
        "underpowered": underpowered,
        "weights_included": include_weights,
        "ab_diagnostics": ab_diagnostics(with_b),
        "cohorts": {
            "with_b": cohort_block(with_b, cohort_with_b_models, oof_with_b),
            "b_abstain": cohort_block(abstain, cohort_abstain_models, oof_abstain),
        },
        "stat_splits": stat_splits(with_b, cohort_with_b_models, l2),
    }
    return report, oof_with_b


def write_fit_output(report: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def emit_config_from_oof(
    report: dict,
    oof_with_b: dict[str, list[tuple[float, int]]],
    config_path: Path,
) -> tuple[bool, str]:
    ok, reason = should_emit_config(report, oof_with_b)
    if not ok:
        return False, reason
    weights = report["cohorts"]["with_b"].get("weights") or {}
    m3 = weights.get("M3")
    if not m3:
        return False, "M3 weights missing"
    payload = {
        "version": f"{report['fit_date']}-{CODE_VERSION}",
        "underpowered": report.get("underpowered", False),
        "code_version": CODE_VERSION,
        "model": "M3",
        "weights": m3,
        "l2_strength": report.get("l2_strength"),
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return True, f"wrote {config_path}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fit blend weights on settled prop snapshots.")
    parser.add_argument("--path", default=str(pm.DEFAULT_SNAPSHOT_PATH))
    parser.add_argument("--out", help="Output JSON path (default data/blend_fit_<date>.json)")
    parser.add_argument("--l2", type=float, default=DEFAULT_L2, help="L2 regularization strength")
    parser.add_argument("--force", action="store_true", help="Emit weights when n < 300 (UNDERPOWERED)")
    parser.add_argument("--emit-config", action="store_true", help="Write config/blend_weights.json when M3 wins")
    parser.add_argument("--config-path", default=str(DEFAULT_BLEND_WEIGHTS_PATH))
    args = parser.parse_args(argv)

    try:
        rows = load_settled_rows(Path(args.path))
    except pm.PickemError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not rows:
        # No data is an underpowered calibration state, not a computation failure.
        report = {"code_version": CODE_VERSION, "fit_date": date.today().isoformat(),
                  "n_settled": 0, "underpowered": True, "weights_included": False,
                  "status": "no_settled_outcomes", "cohorts": {}, "stat_splits": {}}
        out = Path(args.out) if args.out else pm.SKILL_ROOT / "data" / f"blend_fit_{report['fit_date']}.json"
        write_fit_output(report, out)
        print(f"UNDERPOWERED: no settled outcomes; diagnostic written {out}")
        return 2

    report, oof_with_b = build_fit_report(rows, l2=args.l2, force=args.force)

    if not report["weights_included"]:
        print(
            f"ERROR: n_settled={report['n_settled']} < {MIN_SETTLED}; "
            "refusing weights (use --force to stamp UNDERPOWERED)",
            file=sys.stderr,
        )

    out_path = Path(args.out) if args.out else pm.SKILL_ROOT / "data" / f"blend_fit_{report['fit_date']}.json"
    write_fit_output(report, out_path)
    print(f"wrote {out_path}")

    if args.emit_config:
        ok, reason = emit_config_from_oof(report, oof_with_b, Path(args.config_path))
        if ok:
            print(reason)
        else:
            print(f"emit-config skipped: {reason}")

    return 0 if report["weights_included"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
