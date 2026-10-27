"""Calibration report on settled prop snapshots."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import pickem_math as pm

Q_GRADE_BINS = (
    (0.50, 0.52, "0.50-0.52"),
    (0.52, 0.54, "0.52-0.54"),
    (0.54, 0.56, "0.54-0.56"),
    (0.56, 0.58, "0.56-0.58"),
    (0.58, 0.60, "0.58-0.60"),
    (0.60, 1.01, "0.60+"),
)
MIN_BIN_N = 30
GAP_FLAG_POINTS = 0.08


def _read_rows(path: Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8")
    return [row for _line_no, _line, row in pm.iter_snapshot_lines(text)]


def is_settled(row: dict) -> bool:
    if row.get("actual_stat") is None:
        return False
    outcome = row.get("outcome")
    return outcome in ("win", "loss", "push")


def graded_rows(rows: list[dict]) -> list[dict]:
    return [
        row for row in rows
        if is_settled(row) and str(row.get("status") or "").upper() == "GRADED"
    ]


def _conditional(prob, row):
    try:
        push = float(row.get("q_push") or 0)
        if not 0 <= push < 1 or not math.isfinite(prob) or prob + push > 1 + 1e-9:
            return None
        return min(1.0, prob / (1 - push))
    except (TypeError, ValueError):
        return None


def prediction_probability(row: dict) -> float | None:
    for key in ("q_grade", "q_win", "q_model"):
        value = row.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if 0 <= number <= 1:
            return _conditional(number, row)
    return None


def market_probability(row: dict) -> float | None:
    value = row.get("q_market_comparable")
    if value is None:
        value = row.get("q_market")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if 0 <= number <= 1:
        return (_conditional(number, row) if row.get("q_market_comparable") is not None else number)
    return None


def outcome_win(row: dict) -> int | None:
    outcome = row.get("outcome")
    if outcome == "win":
        return 1
    if outcome == "loss":
        return 0
    return None


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def dedupe_props(rows: list[dict]) -> list[dict]:
    """One observation per event/player/market/line/side, earliest pregame forecast.

    Legacy rows without forecast timestamps retain latest-settlement selection.
    Known postgame forecasts are never eligible calibration observations.
    """
    by_side: dict[tuple, dict] = {}
    def identity(row, name):
        inputs = row.get("inputs") if isinstance(row.get("inputs"), dict) else {}
        return row.get(name) or inputs.get(name)

    for row in rows:
        forecast = _timestamp(row.get("forecast_at"))
        start = _timestamp(row.get("event_start"))
        if forecast is not None and start is not None and forecast >= start:
            continue
        key = (
            str(row.get("sport") or "").upper(),
            str(row.get("game_date") or ""),
            str(identity(row, "event_id_namespace") or ""),
            str(identity(row, "event_id") or row.get("matchup") or ""),
            str(identity(row, "player_id") or str(row.get("player") or "").casefold()),
            str(row.get("stat") or "").casefold(),
            str(row.get("side") or "").casefold(),
            row.get("reference_line"),
        )
        prev = by_side.get(key)
        if prev is None:
            by_side[key] = row
            continue
        previous_forecast = _timestamp(prev.get("forecast_at"))
        previous_start = _timestamp(prev.get("event_start"))
        verified = forecast is not None and start is not None
        previous_verified = previous_forecast is not None and previous_start is not None
        if verified and (not previous_verified or forecast < previous_forecast):
            by_side[key] = row
        elif not verified and not previous_verified:
            if str(row.get("settled_at") or "") > str(prev.get("settled_at") or ""):
                by_side[key] = row
    return list(by_side.values())


def brier_score(pairs: list[tuple[float, int]]) -> float | None:
    if not pairs:
        return None
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def log_loss(pairs: list[tuple[float, int]]) -> float | None:
    if not pairs:
        return None
    total = 0.0
    for prob, label in pairs:
        p = min(1 - 1e-15, max(1e-15, prob))
        total += -(label * math.log(p) + (1 - label) * math.log(1 - p))
    return total / len(pairs)


def hit_rate(rows: list[dict]) -> float | None:
    wins = [outcome_win(row) for row in rows]
    scored = [value for value in wins if value is not None]
    if not scored:
        return None
    return sum(scored) / len(scored)


def q_grade_bin(probability: float) -> str | None:
    for low, high, label in Q_GRADE_BINS:
        if low <= probability < high:
            return label
    return None


def build_report(rows: list[dict], *, include_shadow: bool = False) -> dict:
    if not include_shadow:
        rows = pm.user_facing_rows(rows)
    settled = dedupe_props(graded_rows(rows))
    model_pairs = []
    market_pairs = []
    gap_large = 0
    for row in settled:
        label = outcome_win(row)
        if label is None:
            continue
        pred = prediction_probability(row)
        if pred is not None:
            model_pairs.append((pred, label))
        market = market_probability(row)
        if market is not None:
            market_pairs.append((market, label))
        gap = row.get("q_gap")
        if gap is not None:
            try:
                if abs(float(gap)) >= GAP_FLAG_POINTS:
                    gap_large += 1
            except (TypeError, ValueError):
                pass
    scored_n = len([row for row in settled if outcome_win(row) is not None])
    reliability = []
    for low, high, label in Q_GRADE_BINS:
        bucket = []
        for row in settled:
            pred = prediction_probability(row)
            label_value = outcome_win(row)
            if pred is None or label_value is None:
                continue
            if low <= pred < high:
                bucket.append((pred, label_value))
        n = len(bucket)
        reliability.append(
            {
                "bin": label,
                "n": n,
                "hit_rate": hit_rate([{"outcome": "win" if y else "loss"} for _p, y in bucket]) if n else None,
                "avg_prediction": (sum(p for p, _y in bucket) / n) if n else None,
                "status": "insufficient" if n < MIN_BIN_N else "ok",
            }
        )
    by_rank = defaultdict(list)
    by_slice = defaultdict(list)
    for row in settled:
        label = outcome_win(row)
        if label is None:
            continue
        by_rank[str(row.get("final_rank") or "unknown")].append(row)
        slice_key = (
            str(row.get("sport") or ""),
            str(row.get("stat") or ""),
            str(row.get("side") or ""),
        )
        by_slice[slice_key].append(row)
    return {
        "probability_scale": "conditional_on_no_push",
        "n_settled_graded": len(settled),
        "n_scored": scored_n,
        "brier_model": brier_score(model_pairs),
        "log_loss_model": log_loss(model_pairs),
        "brier_market_comparable": brier_score(market_pairs),
        "gap_abs_ge_8pts_share": (gap_large / scored_n) if scored_n else None,
        "reliability_by_q_grade": reliability,
        "hit_rate_by_final_rank": {
            rank: hit_rate(group) for rank, group in sorted(by_rank.items())
        },
        "hit_rate_by_sport_stat_side": {
            f"{sport}|{stat}|{side}": hit_rate(group)
            for (sport, stat, side), group in sorted(by_slice.items())
        },
    }


def format_report(report: dict) -> str:
    lines = [
        f"n_settled_graded={report['n_settled_graded']}",
        f"n_scored={report['n_scored']}",
    ]
    for key in ("brier_model", "log_loss_model", "brier_market_comparable", "gap_abs_ge_8pts_share"):
        value = report.get(key)
        lines.append(f"{key}=" + ("na" if value is None else f"{value:.6f}"))
    lines.append("reliability_by_q_grade:")
    for bucket in report["reliability_by_q_grade"]:
        tag = f" [{bucket['status']}]" if bucket["status"] == "insufficient" else ""
        hit = bucket["hit_rate"]
        hit_text = "na" if hit is None else f"{hit:.4f}"
        lines.append(f"  {bucket['bin']}: n={bucket['n']} hit_rate={hit_text}{tag}")
    lines.append("hit_rate_by_final_rank:")
    for rank, rate in report["hit_rate_by_final_rank"].items():
        lines.append(f"  {rank}: " + ("na" if rate is None else f"{rate:.4f}"))
    lines.append("hit_rate_by_sport_stat_side:")
    for label, rate in report["hit_rate_by_sport_stat_side"].items():
        lines.append(f"  {label}: " + ("na" if rate is None else f"{rate:.4f}"))
    if report["n_settled_graded"] < 300:
        lines.append("calibration_gate=need at least 300 settled graded props before retuning constants")
    else:
        lines.append("calibration_gate=ok for constant review (n>=300)")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report on settled graded prop snapshots.")
    parser.add_argument("--path", default=str(pm.DEFAULT_SNAPSHOT_PATH))
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--include-shadow",
        action="store_true",
        help="include shadow calibration rows when computing calibration metrics",
    )
    args = parser.parse_args(argv)
    try:
        rows = _read_rows(Path(args.path))
    except pm.PickemError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    report = build_report(rows, include_shadow=args.include_shadow)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        sys.stdout.write(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
