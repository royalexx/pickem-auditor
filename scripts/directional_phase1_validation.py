#!/usr/bin/env python3
"""Phase 1 research validator: immutable pregame predictions and exact settlements.

This module NEVER calculates new bets, retrains any model, changes production
weights, fetches live odds, or grants ranking/Tier eligibility. It checks
frozen artifacts and evaluates already-supplied, officially verified actuals.

Usage:
  python scripts/directional_phase1_validation.py \
      --comparison SLATE/slate_model_comparisons.json \
      --settlement SLATE/slate_1pm_nfl_settlement_20261108.json \
      --baseline-manifest config/directional_research_baseline_20261108.json \
      --policy config/production_consensus.json \
      --output /tmp/directional-phase1-receipt.json
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import sys

VERSION = "directional-phase1-frozen-prospective-audit-v1"
MODELS = ("Engine_A", "Engine_B", "Bayesian_A", "Bayesian_B",
          "NUTS", "Consensus", "Market")
HISTORICAL = ("Engine_A", "Bayesian_A", "Bayesian_B", "NUTS")


class AuditError(ValueError):
    """Hard integrity failure; no evaluation receipt can be authorized."""


def exact_json(path: Path) -> tuple[dict, str]:
    """Load strict JSON with SHA of the bytes actually read."""
    data = Path(path).read_bytes()
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise AuditError("duplicate_json_key:" + key)
            obj[key] = value
        return obj
    try:
        parsed = json.loads(data, object_pairs_hook=unique,
                            parse_constant=lambda value:
                                (_ for _ in ()).throw(AuditError("nonfinite_json:" + value)))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditError("invalid_json") from exc
    if not isinstance(parsed, dict):
        raise AuditError("document_not_an_object")
    return parsed, hashlib.sha256(data).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def instant(value, *, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise AuditError("missing_timestamp:" + field)
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditError("invalid_timestamp:" + field) from exc
    if date.tzinfo is None:
        raise AuditError("naive_timestamp:" + field)
    return date.astimezone(timezone.utc)


def num(value, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise AuditError("non_numeric:" + field)
    v = float(value)
    if not math.isfinite(v):
        raise AuditError("nonfinite:" + field)
    return v


def probability(value, *, field: str) -> float | None:
    if value is None:
        return None
    v = num(value, field=field)
    if not 0 <= v <= 1:
        raise AuditError("out_of_range_probability:" + field)
    return v


def key_from_row(row: dict) -> tuple:
    required = ("run_id", "sport", "player", "team",
                "opponent", "stat", "event_start")
    for field in required:
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise AuditError("missing_contract_field:" + field)
    # Original frozen NBA/NHL source IDs can be ESPN integers; NFL GSIS IDs
    # are strings. Normalize numeric identity without changing source rows.
    player_id = row.get("player_id")
    if (isinstance(player_id, bool) or
            not isinstance(player_id, (str, int)) or
            not str(player_id).strip()):
        raise AuditError("missing_contract_field:player_id")
    if row["sport"] not in ("NFL", "NBA", "NHL"):
        raise AuditError("unknown_sport")
    line = num(row.get("line"), field="line")
    if line < 0:
        raise AuditError("negative_line")
    return (row["run_id"], row["sport"], row["event_start"], row["team"],
            row["opponent"], str(player_id), row["player"], row["stat"], line)


def key_from_settlement(row: dict, *, run_id: str, event_start: str,
                        sport: str) -> tuple:
    for field in ("team", "opponent", "player_id_gsis", "player", "stat"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise AuditError("missing_settlement_field:" + field)
    return (run_id, sport, event_start, row["team"], row["opponent"],
            row["player_id_gsis"], row["player"], row["stat"],
            num(row.get("line"), field="settlement_line"))


def validate_model_provenance(row: dict, at: datetime, start: datetime) -> None:
    model_details = row.get("models")
    if not isinstance(model_details, dict):
        raise AuditError("missing_model_provenance")
    for model in MODELS:
        details = model_details.get(model)
        if not isinstance(details, dict):
            raise AuditError("missing_model_status:" + model)
        status = details.get("status")
        if status not in ("forecast", "unavailable"):
            raise AuditError("invalid_model_status:" + model)
        p = probability(row.get(model), field=model)
        q = probability(details.get("probability"), field=model + ".probability")
        if (p is None) != (q is None) or (p is not None and abs(p - q) > 1e-10):
            raise AuditError("model_probability_mismatch:" + model)
        if status == "forecast" and p is None:
            raise AuditError("forecast_without_probability:" + model)
        if status == "unavailable" and p is not None:
            raise AuditError("unavailable_with_probability:" + model)
        if model in ("Bayesian_A", "Bayesian_B", "NUTS") and status == "forecast":
            generated = instant(details.get("generated_at"), field=model + ".generated_at")
            if not at <= generated < start:
                raise AuditError("model_generated_outside_pregame:" + model)
            trained = details.get("trained_through")
            if trained is not None and isinstance(trained, str) and trained:
                try:
                    train_dt = datetime.fromisoformat(trained)
                except ValueError:
                    raise AuditError("invalid_training_cutoff:" + model)
                # A date-only trained_through is interpreted as a latest
                # training DATE. Calendar day equal to game day is ambiguous
                # unless a full timezone-aware time receipt is provided.
                if train_dt.tzinfo is None and len(trained) > 10:
                    raise AuditError("naive_training_cutoff:" + model)
                if train_dt.tzinfo is None:
                    if train_dt.date() >= start.date():
                        raise AuditError("training_date_not_strictly_pregame:" + model)
                elif train_dt.astimezone(timezone.utc) > generated:
                    raise AuditError("training_cutoff_after_generation:" + model)
        for ts in ("available_at", "source_published_at", "retrieved_at"):
            if details.get(ts) is not None:
                when = instant(details[ts], field=model + "." + ts)
                if when > at:
                    raise AuditError("future_feature_used:" + model + "." + ts)
        if model == "Market" and status == "forecast":
            observed = instant(details.get("observed_at"), field="Market.observed_at")
            if observed > at:
                raise AuditError("post_forecast_market_price")
    if bool(row.get("production_consensus_available")) != (
            row.get("Consensus") is not None):
        raise AuditError("production_consensus_flag_mismatch")
    if row.get("production_consensus_available"):
        if (row["models"]["Consensus"].get("empirically_calibrated") is True):
            raise AuditError("unapproved_empirically_calibrated_consensus")
        ensemble = row.get("production_ensemble")
        if not isinstance(ensemble, dict) or ensemble.get("status") != "forecast":
            raise AuditError("missing_production_ensemble_receipt")
        families = ensemble.get("historical_families")
        if (not isinstance(families, list) or "Engine_A" not in families
                or len(families) < 2 or len(set(families)) != len(families)
                or any(f not in HISTORICAL for f in families)):
            raise AuditError("invalid_historical_families")
        if any(row.get(model) is None for model in families + ["Engine_B"]):
            raise AuditError("missing_ensemble_component")
        if abs(float(ensemble.get("weight_historical", -1)) - .6) > 1e-12:
            raise AuditError("production_baseline_weight_changed")
        if abs(float(ensemble.get("weight_b", -1)) - .4) > 1e-12:
            raise AuditError("production_baseline_weight_changed")


def audit_frozen(comparison: dict) -> tuple[dict, dict]:
    if comparison.get("schema") != "slate-model-comparison-v1":
        raise AuditError("unexpected_comparison_schema")
    info = comparison.get("metadata")
    if not isinstance(info, dict) or not isinstance(info.get("run_id"), str):
        raise AuditError("missing_run_id")
    rows = comparison.get("picks")
    if not isinstance(rows, list) or not rows:
        raise AuditError("missing_frozen_rows")
    groups = defaultdict(dict)
    by_window = Counter()
    min_stamp = None
    max_stamp = None
    for row in rows:
        if not isinstance(row, dict) or row.get("run_id") != info["run_id"]:
            raise AuditError("mixed_frozen_run")
        key = key_from_row(row)
        side = row.get("side")
        if side not in ("over", "under"):
            raise AuditError("invalid_side")
        if side in groups[key]:
            raise AuditError("duplicate_paired_side")
        start = instant(row["event_start"], field="event_start")
        at = instant(row.get("forecast_at"), field="forecast_at")
        if at >= start:
            raise AuditError("forecast_after_event_started")
        if at > datetime.now(timezone.utc):
            raise AuditError("forecast_in_future_relative_to_audit")
        validate_model_provenance(row, at, start)
        min_stamp = min(min_stamp, at) if min_stamp is not None else at
        max_stamp = max(max_stamp, at) if max_stamp is not None else at
        groups[key][side] = row
        by_window[(row["sport"], row["event_start"])] += 1

    unit_sum_warnings = []
    for key, pair in groups.items():
        if set(pair) != {"over", "under"}:
            raise AuditError("missing_over_or_under_side")
        over, under = pair["over"], pair["under"]
        if over["forecast_at"] != under["forecast_at"]:
            raise AuditError("sides_have_different_forecast_time")
        for model in MODELS:
            p = over.get(model)
            q = under.get(model)
            if (p is None) != (q is None):
                raise AuditError("one_sided_model_availability:" + model)
            if p is None:
                continue
            total = p + q
            if abs(total - 1) > 1e-8:
                # Existing NUTS sidecars have small normalization discrepancies.
                # Audit and warn, never silently normalize or change picks.
                if model != "NUTS" or abs(total - 1) > .05:
                    raise AuditError("side_probabilities_not_complementary:" + model)
                unit_sum_warnings.append({"model": model, "contract": list(key),
                                          "side_sum": total})
        if (over.get("production_consensus_available") !=
                under.get("production_consensus_available")):
            raise AuditError("asymmetric_production_consensus")
    return groups, {
        "run_id": info["run_id"], "code_sha": info.get("code_sha"),
        "side_rows": len(rows), "contracts": len(groups),
        "eligible_consensus_contracts": sum(
            pair["over"]["Consensus"] is not None for pair in groups.values()),
        "sport_event_start_side_rows": [
            {"sport": s, "event_start": t, "side_rows": n}
            for (s, t), n in sorted(by_window.items())],
        "earliest_forecast": min_stamp.isoformat(),
        "latest_forecast": max_stamp.isoformat(),
        "nonunit_sidecar_warnings": unit_sum_warnings,
        "all_source_features_independently_verified": False
    }


def verify_feature_receipts(features: list[dict], groups: dict) -> dict:
    """Optional Phase 2 feature intake: reject all ungrounded or late evidence.

    Feature evidence must be available at or before *the frozen forecast*, not
    merely before kickoff. Missing features are not silently filled.
    """
    accepted = Counter()
    for f in features:
        if not isinstance(f, dict):
            raise AuditError("feature_not_an_object")
        for k in ("run_id", "sport", "event_start", "team", "opponent",
                  "player_id", "player", "stat", "line"):
            if k not in f:
                raise AuditError("feature_missing_identity:" + k)
        key = key_from_row(f)
        pair = groups.get(key)
        if pair is None:
            raise AuditError("feature_not_linked_to_frozen_contract")
        if not isinstance(f.get("source_url"), str) or not f["source_url"].startswith("https://"):
            raise AuditError("feature_missing_source_url")
        if not isinstance(f.get("source_id"), str) or not f["source_id"]:
            raise AuditError("feature_missing_source_id")
        published = instant(f.get("published_at"), field="feature.published_at")
        retrieved = instant(f.get("retrieved_at"), field="feature.retrieved_at")
        at = instant(pair["over"]["forecast_at"], field="forecast_at")
        if published > retrieved or retrieved > at:
            raise AuditError("feature_retrieved_after_forecast")
        if f.get("status") != "verified":
            raise AuditError("feature_not_verified")
        accepted[str(f.get("feature_family") or "unspecified")] += 1
    return {"total_source_verified": sum(accepted.values()), "by_family": dict(accepted)}


def validate_settlement(comparison: dict, settlement: dict, groups: dict) -> dict:
    """Settlement is postgame evidence only; never used to change a forecast."""
    info = comparison["metadata"]
    if (settlement.get("pregame_run") != info["run_id"] or
            settlement.get("code_sha") != info.get("code_sha")):
        raise AuditError("settlement_wrong_frozen_forecast")
    contracts = settlement.get("contracts")
    if not isinstance(contracts, list):
        raise AuditError("missing_settled_contracts")
    events = settlement.get("games")
    if not isinstance(events, list) or not events:
        raise AuditError("missing_official_game_evidence")
    source_games = {}
    for g in events:
        if not isinstance(g, dict) or not g.get("espn_event_id") or not g.get("source"):
            raise AuditError("invalid_official_game_source")
        if "espn" not in str(g["source"]).lower():
            raise AuditError("unrecognized_game_source")
        teams = frozenset(g.get("teams") or [])
        if len(teams) != 2 or teams in source_games:
            raise AuditError("invalid_game_source_teams")
        source_games[teams] = str(g["espn_event_id"])
    seen = set()
    verified = {}
    excluded = Counter()
    for x in contracts:
        if not isinstance(x, dict):
            raise AuditError("invalid_settlement_record")
        sport = settlement.get("sport") or "NFL"
        event_start = settlement.get("start_window_utc")
        if not event_start:
            raise AuditError("settlement_event_start_unavailable")
        key = key_from_settlement(x, run_id=info["run_id"],
                                  event_start=event_start, sport=sport)
        if key in seen:
            raise AuditError("duplicate_settlement_contract")
        seen.add(key)
        if key not in groups:
            raise AuditError("settlement_not_on_original_frozen_line")
        if frozenset((x["team"], x["opponent"])) not in source_games:
            raise AuditError("settlement_missing_gamebook")
        if str(x.get("espn_game_id")) != source_games[frozenset((x["team"], x["opponent"]))]:
            raise AuditError("settlement_wrong_official_game")
        pair = groups[key]
        if x.get("pregame_forecast_at") != pair["over"]["forecast_at"]:
            raise AuditError("settlement_forecast_timestamp_mismatch")
        if x.get("settlement_status") != "verified":
            excluded[str(x.get("settlement_status") or "unverified")] += 1
            continue
        actual = num(x.get("actual"), field="actual")
        if actual < 0:
            raise AuditError("invalid_negative_actual_stat")
        line = key[-1]
        observed_side = "push" if actual == line else ("over" if actual > line else "under")
        if x.get("winning_side") != observed_side:
            raise AuditError("actual_disagrees_with_winning_side")
        if observed_side == "push":
            excluded["push"] += 1
            continue
        verified[key] = {"actual": actual, "winner": observed_side,
                         "game_id": str(x["espn_game_id"]),
                         "group": tuple(sorted((x["team"], x["opponent"])))}
    missing = len(set(groups) - seen)
    if missing:
        excluded["missing_settlement_contract"] += missing
    return {"verified": verified, "excluded": dict(excluded),
            "seen_settlement_contracts": len(seen),
            "verified_contracts": len(verified)}


def _metrics(predictions: list[dict]) -> dict:
    if not predictions:
        return {"n": 0, "hits": 0, "directional_accuracy": None,
                "brier": None, "log_loss": None}
    correct = sum(row["hit"] for row in predictions)
    return {
        "n": len(predictions),
        "hits": correct,
        "directional_accuracy": correct / len(predictions),
        "brier": sum((row["p"] - int(row["hit"])) ** 2 for row in predictions) / len(predictions),
        "log_loss": -sum(math.log(max(1e-15,
             row["p"] if row["hit"] else 1 - row["p"])) for row in predictions) / len(predictions),
        "mean_preferred_probability": sum(row["p"] for row in predictions) / len(predictions),
        "predicted_over_share": sum(row["side"] == "over" for row in predictions) / len(predictions),
        "actual_over_share": sum(row["winner"] == "over" for row in predictions) / len(predictions),
    }


def game_cluster_bootstrap(predictions: list[dict], *, min_clusters: int = 8,
                           draws: int = 1000, seed: int = 20261108) -> dict:
    """Block-bootstrap identical game outcomes together; no independent-row CI."""
    grouped = defaultdict(list)
    for p in predictions:
        grouped[p["game_id"]].append(p)
    games = sorted(grouped)
    if len(games) < min_clusters:
        return {"status": "insufficient_independent_games",
                "independent_games": len(games), "minimum": min_clusters,
                "interval_95": None}
    rng = random.Random(seed)
    scores = []
    for _ in range(draws):
        draw = [p for g in rng.choices(games, k=len(games)) for p in grouped[g]]
        scores.append(_metrics(draw)["directional_accuracy"])
    scores.sort()
    return {"status": "descriptive_cluster_bootstrap", "independent_games": len(games),
            "draws": draws, "seed": seed,
            "interval_95": [scores[int(.025 * draws)], scores[int(.975 * draws) - 1]],
            "significance_or_promotion_certificate": False}


def score_frozen(groups: dict, outcome: dict) -> dict:
    settled = outcome["verified"]
    all_models = {m: [] for m in MODELS}
    consensus_keys = {key for key in settled if
                      groups[key]["over"]["Consensus"] is not None}
    for key, actual in settled.items():
        pair = groups[key]
        for model in MODELS:
            ov, un = pair["over"].get(model), pair["under"].get(model)
            if ov is None or un is None or abs(ov - un) < 1e-12:
                continue
            side = "over" if ov > un else "under"
            p = max(ov, un)
            all_models[model].append({
                "contract": key, "p": p, "side": side,
                "hit": side == actual["winner"],
                "winner": actual["winner"], "game_id": actual["game_id"]
            })
    report = {}
    for model, scored in all_models.items():
        comparable = [x for x in scored if x["contract"] in consensus_keys]
        report[model] = {
            "own_coverage": _metrics(scored),
            "on_settled_consensus_cohort": _metrics(comparable),
            "missing_on_consensus_cohort": len(consensus_keys) - len(comparable),
            "game_cluster_uncertainty": game_cluster_bootstrap(comparable),
        }
    return {"scored_contracts": len(settled),
            "same_cohort_consensus_contracts": len(consensus_keys),
            "models": report,
            "all_source_supported_contracts": len(groups),
            "never_counts_complementary_sides_as_independent": True}


def run(comparison: dict, *, settlement: dict | None = None,
        expected_run_id: str | None = None, features: list[dict] | None = None) -> dict:
    groups, scope = audit_frozen(comparison)
    if expected_run_id is not None and scope["run_id"] != expected_run_id:
        raise AuditError("unexpected_frozen_run")
    receipt = {
        "schema": VERSION, "status": "read_only_audited",
        "ranking_allowed": False, "production_promotion_allowed": False,
        "recalculates_predictions": False, "changes_training_or_policy": False,
        "research_baseline": "docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md",
        "scope": scope,
        "feature_verification": verify_feature_receipts(features or [], groups),
        "limitations": [
            "Existing source-model forecasts are not retrained or regenerated",
            "Frozen comparison SHA is not proof of complete original provider-source archives",
            "Game cluster intervals are descriptive only and require enough independent games",
            "Any missing official settlement remains excluded, never an inferred zero",
        ],
    }
    if settlement is not None:
        verified = validate_settlement(comparison, settlement, groups)
        receipt["settlement"] = {
            "verified_contracts": verified["verified_contracts"],
            "seen_settlement_contracts": verified["seen_settlement_contracts"],
            "excluded": verified["excluded"]
        }
        receipt["scorecard"] = score_frozen(groups, verified)
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--settlement", type=Path)
    parser.add_argument("--baseline-manifest", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--features", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        original, original_hash = exact_json(args.comparison)
        manifest = None
        if args.baseline_manifest:
            manifest, _ = exact_json(args.baseline_manifest)
            expected = manifest.get("original_frozen_comparison_sha256")
            if original_hash != expected:
                raise AuditError("baseline_comparison_sha256_mismatch")
            if not args.policy:
                raise AuditError("baseline_policy_path_required")
            if git_blob_sha(args.policy) != manifest.get("production_policy_git_blob_sha"):
                raise AuditError("baseline_production_policy_modified")
        actual = exact_json(args.settlement)[0] if args.settlement else None
        feature_rows = None
        if args.features:
            payload, _ = exact_json(args.features)
            feature_rows = payload.get("features")
            if not isinstance(feature_rows, list):
                raise AuditError("feature_rows_missing")
        result = run(original, settlement=actual, features=feature_rows,
                     expected_run_id=manifest.get("baseline_forecast", {}).get("run_id")
                         if manifest else None)
        result["comparison_sha256"] = original_hash
        if args.settlement:
            result["settlement_sha256"] = hashlib.sha256(args.settlement.read_bytes()).hexdigest()
        result["baseline_policy_verified"] = manifest is not None
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2,
                                          allow_nan=False) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "contracts": result["scope"]["contracts"],
                          "receipt": str(args.output)}, sort_keys=True))
        return 0
    except (AuditError, OSError, TypeError, ValueError) as exc:
        print("DIRECTIONAL_PHASE1_BLOCKED:" + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
