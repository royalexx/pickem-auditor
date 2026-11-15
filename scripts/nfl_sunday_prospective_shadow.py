#!/usr/bin/env python3
"""Outcome-blind, one-contract-per-line NFL Sunday market-reference shadow.

Consumes ONLY the already frozen full-universe comparison, not outcomes or
current sportsbook queries. Isolated prospective capture; never changes
production 60/40, ranking, Bayesian posteriors, market lines, or tiers.
An inherited comparison-file timestamp is NOT independent source certification.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reform_step8_market_shadow import equal_logit_over

VERSION = "nfl-nov15-fixed-market-logit-shadow-v1"
POLICY = "production-historical-ensemble-60-40-20261108-v1"
MODEL_NAMES = ("Consensus", "Market")
EXCLUDE = {"passing touchdowns", "receiving touchdowns", "rushing touchdowns",
           "anytime touchdown", "qb hits", "passes defended"}


def aware(value):
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("timestamp_missing")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp_naive")
    return dt.astimezone(timezone.utc)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def contract_key(row):
    keys = ("sport", "event_start", "team", "opponent", "player_id",
            "player", "stat", "line", "period")
    v = tuple(row.get(k) for k in keys)
    if any(x is None for x in v[:8]):
        raise ValueError("contract_identity_incomplete")
    if isinstance(v[7], bool) or not isinstance(v[7], (int, float)) or not math.isfinite(v[7]):
        raise ValueError("invalid_line")
    return v


def valid_side(row, name):
    m = (row.get("models") or {}).get(name)
    p = m.get("probability") if isinstance(m, dict) else None
    if (not isinstance(m, dict) or m.get("status") != "forecast"
            or type(p) not in (int, float) or not math.isfinite(p)
            or not 0 <= p <= 1):
        raise ValueError(name + "_unavailable_or_invalid")
    if row.get(name) != p:
        raise ValueError(name + "_display_model_disagreement")
    return m, float(p)


def build(payload, *, day, now):
    now = aware(now.isoformat()) if isinstance(now, datetime) else aware(now)
    info = payload.get("metadata")
    if not isinstance(info, dict) or info.get("comparison_schema") != "slate-model-comparison-v1":
        raise ValueError("wrong_frozen_comparison_schema")
    if info.get("day") != day or info.get("production_policy_version") != POLICY:
        raise ValueError("wrong_frozen_day_or_policy")
    if not info.get("run_id") or not info.get("snapshots_sha256") or not info.get("code_sha"):
        raise ValueError("missing_frozen_input_lineage")
    picks = payload.get("picks")
    if not isinstance(picks, list):
        raise ValueError("no_frozen_universe")
    nfl = [r for r in picks if isinstance(r, dict) and r.get("sport") == "NFL"
           and r.get("game_date") == day]
    groups = defaultdict(dict)
    problems = Counter()
    for row in nfl:
        try:
            if str(row.get("stat", "")).lower() in EXCLUDE:
                problems["excluded_nonvolume_market"] += 1
                continue
            side = row.get("side")
            if side not in ("over", "under"):
                raise ValueError("invalid_side")
            k = contract_key(row)
            if side in groups[k]:
                raise ValueError("duplicate_contract_side")
            groups[k][side] = row
        except (TypeError, ValueError) as exc:
            problems[str(exc)] += 1
    results = []
    for key, pair in sorted(groups.items(), key=lambda x: str(x[0])):
        try:
            if set(pair) != {"over", "under"}:
                raise ValueError("missing_complementary_side")
            over, under = pair["over"], pair["under"]
            freeze_times = [aware(r["forecast_at"]) for r in (over, under)]
            event = aware(over["event_start"])
            if not all(t < event for t in freeze_times):
                raise ValueError("forecast_not_pregame")
            if now >= event:
                raise ValueError("shadow_capture_not_pregame")
            values = {}
            sources = {}
            for name in MODEL_NAMES:
                ms = [valid_side(r, name) for r in (over, under)]
                p_over, p_under = ms[0][1], ms[1][1]
                if abs(p_over + p_under - 1) > 1e-8:
                    raise ValueError(name + "_pair_noncomplementary")
                for source, row in zip((ms[0][0], ms[1][0]), (over, under)):
                    generation = source.get("generated_at")
                    if generation is not None and aware(generation) >= event:
                        raise ValueError(name + "_generated_after_kickoff")
                values[name] = {"over": p_over, "under": p_under}
                sources[name] = ms
            m0, m1 = [x[0] for x in sources["Market"]]
            if m0.get("version") != m1.get("version") or (
                    m0.get("books") != m1.get("books") or
                    not isinstance(m0.get("books"), list) or len(m0["books"]) < 2):
                raise ValueError("insufficient_compatible_market_books")
            if any(aware(x.get("observed_at")) > t for x, t in
                   zip((m0, m1), freeze_times)):
                raise ValueError("market_quote_after_frozen_forecast")
            if any(aware(x.get("observed_at")) >= event for x in (m0, m1)):
                raise ValueError("market_quote_not_pregame")
            for a, b in zip((over, under), (over, under)):
                if a.get("run_id") != b.get("run_id"):
                    raise ValueError("run_id_side_mismatch")
            if any(r.get("run_id") != info["run_id"] for r in (over, under)):
                raise ValueError("frozen_run_identity_mismatch")
            if any(r.get("forecast_at") != over.get("forecast_at") for r in (under,)):
                raise ValueError("side_freeze_timestamp_mismatch")
            p = equal_logit_over(values["Consensus"], values["Market"])
            output = {
                "sport": key[0], "event_start": key[1], "team": key[2],
                "opponent": key[3], "player_id": key[4], "player": key[5],
                "stat": key[6], "line": key[7], "period": key[8],
                "game_date": day, "forecast_at": over["forecast_at"],
                "model_probabilities_conditional_no_push": {
                    "frozen_60_40": values["Consensus"],
                    "frozen_market_reference": values["Market"],
                    "fixed_50_50_logit": {"over": p, "under": 1-p}},
                "market_books": m0["books"],
                "market_observed_at": m0["observed_at"],
                "baseline_version": sources["Consensus"][0][0].get("version"),
                "shadow_version": VERSION,
                "prediction_is_conditional_on_player_appearance": True,
                "qb_starter_eligibility_not_independently_verified": True,
                "source_certification": "inherited_frozen_comparison_not_independently_attested",
                "release_authority": "RESEARCH_ONLY_NEVER_TIERS",
            }
            results.append(output)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            problems[str(exc)] += 1
    return {
        "schema": VERSION, "date": day, "frozen_run_id": info["run_id"],
        "frozen_snapshots_sha256": info["snapshots_sha256"],
        "frozen_code_sha": info["code_sha"], "frozen_policy": POLICY,
        "capture_at": now.isoformat(), "original_nfl_side_rows": len(nfl),
        "unique_contracts_in_scope": len(groups),
        "eligible_contracts": len(results),
        "abstained_contracts": len(groups) - len(results),
        "rejection_counts": dict(sorted(problems.items())),
        "validity": "OUTCOME_BLIND_SHADOW_NOT_PROSPECTIVE_SOURCE_CERTIFIED",
        "no_results_inspected": True, "no_production_modification": True,
        "forecast_rows": results,
    }


def freeze(report, destination, source_sha):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError("append_only_forecast_receipt_already_exists")
    data = {k: v for k, v in report.items() if k != "forecast_rows"}
    data["input_comparison_sha256"] = source_sha
    data["forecast_rows_sha256"] = digest(canonical(report["forecast_rows"]))
    data["forecast_rows"] = report["forecast_rows"]
    payload = canonical(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Creation is exclusive, never replace an original frozen receipt.
    with destination.open("xb") as stream:
        stream.write(payload)
    return {"path": str(destination), "bytes": len(payload),
            "sha256": digest(payload),
            "eligible": len(report["forecast_rows"]),
            "blocked": report["abstained_contracts"],
            "status": report["validity"]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--comparison", required=True, type=Path)
    p.add_argument("--date", required=True)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    raw = args.comparison.read_bytes()
    report = build(json.loads(raw), day=args.date,
                   now=datetime.now(timezone.utc))
    print(json.dumps(freeze(report, args.out, digest(raw)),
                     sort_keys=True))


if __name__ == "__main__":
    main()
