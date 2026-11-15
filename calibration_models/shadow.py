"""WS5: outcome-blind forecast generation from a hash-pinned WS1 bundle.

No network, production writer, or Sunday fitting path. See README for the
explicit interchange contract; an unknown manifest schema is a blocker.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reform_step10_calibration_shadow as calibration
from reform_step8_market_shadow import equal_logit_over, proper_pair
from pickem_math import implied
from fit_blend import reliability_bins

VERSION = "nfl-ws5-calibration/1.0.0"
DAY = "2026-11-15"
POLICY = "production-historical-ensemble-60-40-20261108-v1"
CONFIG = {
    "C1": {"family": "identity", "production_policy": POLICY},
    "C2": {"family": "market_only", "devig": "multiplicative_two_way"},
    "C3": {"family": "equal_logit", "model_weight": 0.5, "market_weight": 0.5},
    "C4": {"family": "fixed_shrinkage_NOT_empirically_calibrated", "alpha": 0.75},
    "C4_sensitivity_050": {"family": "fixed_shrinkage_sensitivity", "alpha": 0.5},
    "C4_sensitivity_090": {"family": "fixed_shrinkage_sensitivity", "alpha": 0.9},
    "C5": {"family": "monotone_beta", "l2": calibration.L2,
           "prior": {"a": 1.0, "b": 1.0, "c": 0.0}},
    "C6": {"family": "regularized_global_logit_stack", "l2": calibration.L2,
           "prior": {"intercept": 0.0, "logit_model": 0.5, "logit_market": 0.5}},
    "C7": {"family": "bounded_disagreement_shrinkage", "gap_threshold": 0.15,
           "maximum_shrinkage": 0.25, "gap_at_maximum": 0.50},
}
DEPENDENCIES = ("scripts/fit_blend.py", "scripts/reform_step8_market_shadow.py",
                "scripts/reform_step10_calibration_shadow.py", "scripts/pickem_math.py")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def timestamp(value):
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("missing_precise_timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("naive_timestamp")
    return result.astimezone(timezone.utc)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def source_hashes():
    paths = (*DEPENDENCIES, "calibration_models/shadow.py", "calibration_models/native_ws1.py")
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def load_bundle(path, expected_sha):
    """Require a caller-pinned manifest and verify every referenced byte file."""
    path = Path(path).resolve()
    raw = path.read_bytes()
    if sha(raw) != expected_sha:
        raise ValueError("manifest_sha256_mismatch")
    manifest = json.loads(raw)
    if (manifest.get("schema") != "nfl-ws1-calibration-input-v1"
            or manifest.get("producer") != "workstream_1"
            or manifest.get("target_date") != DAY):
        raise ValueError("unrecognized_WS1_manifest_requires_reviewed_adapter")
    files = {}
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        source = (path.parent / relative).resolve()
        if relative.is_absolute() or not source.is_relative_to(path.parent):
            raise ValueError("manifest_path_escape")
        content = source.read_bytes()
        digest = sha(content)
        if digest != entry["sha256"] or digest in files:
            raise ValueError("source_hash_mismatch_or_duplicate")
        files[digest] = json.loads(content)
    contracts = files[manifest["contracts_sha256"]]
    history = files[manifest["history_sha256"]] if manifest.get("history_sha256") else []
    if not isinstance(contracts, list) or not isinstance(history, list):
        raise ValueError("contracts_and_history_must_be_lists")
    return manifest, files, contracts, history


IDENTITY = ("sport", "event_id", "player_id", "stat_key", "period", "line", "book", "product_type", "settlement_policy")


def identity(row):
    if not isinstance(row, dict):
        raise ValueError("invalid_contract_record")
    for field in IDENTITY:
        if field not in row or row[field] is None or row[field] == "":
            raise ValueError("missing_identity_" + field)
        if field != "line" and not isinstance(row[field], str):
            raise ValueError("invalid_identity_type_" + field)
    if not finite(row["line"]):
        raise ValueError("invalid_line")
    if row["sport"] != "NFL":
        raise ValueError("not_NFL")
    if not isinstance(row.get("contract_id"), str) or not row["contract_id"]:
        raise ValueError("missing_contract_id")
    return tuple(row[x] for x in IDENTITY)


def verify_receipt(row, files, freeze):
    refs = row.get("source_sha256")
    if not isinstance(refs, list) or not refs or any(s not in files for s in refs):
        raise ValueError("missing_original_source_receipt")
    if timestamp(row["source_available_at"]) > freeze:
        raise ValueError("source_after_freeze")
    if row.get("source_conflict") is not False:
        raise ValueError("source_conflict_or_unknown")


def validate(row, *, files, freeze, now, historical=False, require_model=True, require_market=True):
    key = identity(row)
    start, forecast = timestamp(row["event_start_at"]), timestamp(row["forecast_at"])
    local_freeze = timestamp(row["input_freeze_at"])
    if not (local_freeze <= forecast < start and forecast <= freeze):
        raise ValueError("invalid_original_forecast_chronology")
    if not historical and now >= start:
        raise ValueError("started_game")
    if not historical and row.get("game_date") != DAY:
        raise ValueError("wrong_target_date")
    if row.get("game_date") != start.date().isoformat():
        raise ValueError("event_date_identity_conflict")
    verify_receipt(row, files, local_freeze)
    p = None
    if require_model:
        p = validate_model(row, local_freeze)
    if not require_market:
        return key, p, None
    return key, p, validate_market(row, files, local_freeze, start)


def validate_model(row, local_freeze):
    if timestamp(row["model_training_cutoff_at"]) > local_freeze:
        raise ValueError("invalid_original_model_training_cutoff")
    if row.get("production_policy") != POLICY:
        raise ValueError("not_original_frozen_60_40")
    original = row["production"]
    if not isinstance(original, dict):
        raise ValueError("missing_original_probabilities")
    vals = [original.get(k) for k in ("over", "under", "push")]
    if (not all(calibration.finite_probability(v) for v in vals)
            or abs(sum(vals) - 1) > 1e-8 or vals[2] >= 1):
        raise ValueError("noncomplementary_original_probabilities")
    if row.get("stat_support") not in ("integer", "continuous"):
        raise ValueError("unknown_stat_support")
    if (row["stat_support"] == "integer" and row["line"] % 1 != 0
            and original["push"] != 0):
        raise ValueError("impossible_push_at_fractional_integer_line")
    p = original["over"] / (1 - original["push"])
    if not proper_pair({"over": p, "under": original["under"] / (1-original["push"])}):
        raise ValueError("noncomplementary_conditional_model")
    return p


def validate_market(row, files, local_freeze, start):
    quote = row["quote"]
    if not isinstance(quote, dict):
        raise ValueError("missing_original_market_quotes")
    if (any(quote.get(k) != row[k] for k in IDENTITY)
            or timestamp(quote["event_start_at"]) != start):
        raise ValueError("quote_contract_identity_conflict")
    if quote.get("original") is not True or not quote.get("quote_id"):
        raise ValueError("not_authentic_original_quote")
    if quote["product_type"] != "sportsbook_two_sided":
        raise ValueError("market_product_not_comparable")
    quote_source = files.get(quote.get("source_sha256"), {})
    if not isinstance(quote_source, dict) or quote not in quote_source.get("quotes", []):
        # Original raw quote includes its source hash only in the normalized row.
        stripped = {k: v for k, v in quote.items() if k != "source_sha256"}
        if not isinstance(quote_source, dict) or stripped not in quote_source.get("quotes", []):
            raise ValueError("quote_not_in_original_receipt")
    observed = timestamp(quote["observed_at"])
    if not (timestamp(quote["available_at"]) <= observed <= local_freeze
            and observed < start):
        raise ValueError("invalid_quote_chronology")
    odds = [quote.get(k) for k in ("over_odds", "under_odds")]
    if not all(finite(x) and abs(x) >= 100 for x in odds):
        raise ValueError("invalid_original_prices")
    a, b = (implied(x) for x in odds)
    market = a / (a+b)
    # A supplied pair is checked, never silently normalized to fix bad inputs.
    supplied = row.get("market_probability")
    if supplied is not None and (not proper_pair(supplied)
            or abs(supplied["over"] - market) > 1e-8):
        raise ValueError("noncomplementary_or_conflicting_market_probability")
    return market


def learned(history, *, files, freeze):
    """One frozen chronological fit; holdout and target labels never fit."""
    rows, rejects, seen, game_dates = [], Counter(), set(), {}
    for row in history:
        try:
            key, p, market = validate(row, files=files, freeze=freeze, now=freeze, historical=True)
            if timestamp(row["event_start_at"]).date().isoformat() >= DAY:
                raise ValueError("target_or_future_training_event")
            if not (timestamp(row["event_start_at"]) < timestamp(row["settled_at"]) < freeze):
                raise ValueError("label_not_available_before_freeze")
            if row.get("out_of_fold") is not True or row.get("source_certified") is not True:
                raise ValueError("uncertified_or_not_OOF_training")
            outcome = row.get("outcome")
            if outcome not in ("over", "under"):
                raise ValueError("push_void_or_unsettled_excluded_from_binary_fit")
            if key in seen:
                raise ValueError("duplicate_training_contract")
            seen.add(key)
            date = timestamp(row["event_start_at"]).date().isoformat()
            game = row["event_id"]
            if game in game_dates and game_dates[game] != date:
                raise ValueError("game_crosses_date_folds")
            game_dates[game] = date
            rows.append({"date": date, "game_id": game, "contract": key,
                         "settled_at": row["settled_at"], "input_freeze_at": row["input_freeze_at"],
                         "p_model": p, "p_market": market, "y": int(outcome == "over")})
        except (KeyError, TypeError, ValueError) as exc:
            rejects[str(exc)] += 1
    # Duplicates/conflicting dates invalidate the whole cohort, not just later copies.
    fatal = any(k in rejects for k in ("duplicate_training_contract", "game_crosses_date_folds"))
    rows.sort(key=lambda r: (r["date"], repr(r["contract"])))
    train, test, split = calibration.split_dates(rows)
    receipt = {"input_rows": len(history), "eligible_rows": len(rows),
               "exclusions": dict(rejects), "split": split, "fitted": False}
    if train is None or fatal or len({r["y"] for r in train}) != 2:
        receipt["reason"] = "insufficient_certified_chronological_training_or_conflicting_cohort"
        return {}, receipt
    if max(timestamp(r["settled_at"]) for r in train) >= min(timestamp(r["input_freeze_at"]) for r in test):
        receipt["reason"] = "training_labels_not_available_before_historical_holdout_freeze"
        return {}, receipt
    params = {}
    errors = {}
    for name, fitter in (("C5", calibration.fit_beta), ("C6", calibration.fit_stack)):
        try:
            result = fitter(train)
            if not all(finite(x) for x in result.values()):
                raise ValueError("nonfinite_fitted_parameters")
            params[name] = result
        except (ValueError, ArithmeticError) as exc:
            errors[name] = str(exc)
    receipt.update(fitted=bool(params), parameters=params, errors=errors,
                   last_training_date=train[-1]["date"], refit_on_holdout=False,
                   last_training_label_available_at=max(timestamp(r["settled_at"]) for r in train).isoformat())
    # Existing heldout comparison remains descriptive, never a selection rule.
    if set(params) == {"C5", "C6"}:
        scored = calibration.evaluate_predictions(test, params["C5"], params["C6"])
        receipt["historical_holdout"] = {
            "games": len({r["game_id"] for r in test}),
            "metrics": {m: calibration.metric(scored, m) for m in calibration.BASELINES+calibration.CANDIDATES},
            "date_block_comparisons": {
                c: {b: {m: calibration.interval(scored, c, b, metric_name=m)
                        for m in ("brier", "log_loss")} for b in calibration.BASELINES}
                for c in calibration.CANDIDATES}}
    return params, receipt


def probabilities(p, market, params):
    out = {}
    if market is not None:
        out["C2"] = market
    if p is None:
        return out
    out.update({"C1": p, "C4": .5 + .75*(p-.5),
           "C4_sensitivity_050": .5 + .5*(p-.5),
           "C4_sensitivity_090": .5 + .9*(p-.5)})
    if market is not None:
        gap = abs(p-market)
        shrink = 0.25 * min(1.0, max(0.0, (gap-0.15)/0.35))
        out["C3"] = equal_logit_over({"over": p, "under": 1-p},
                                   {"over": market, "under": 1-market})
        out["C7"] = .5 + (1-shrink)*(p-.5)
    if "C5" in params:
        out["C5"] = calibration.beta_map(p, params["C5"])
    if "C6" in params and market is not None:
        out["C6"] = calibration.stack_map(p, market, params["C6"])
    return out


def build(manifest, files, contracts, history, *, now):
    freeze = timestamp(manifest["input_freeze_at"])
    now = timestamp(now)
    if freeze > now:
        raise ValueError("future_input_freeze")
    params, training = learned(history, files=files, freeze=freeze)
    sources = source_hashes()
    registry = {name: {"version": VERSION, "configuration": config,
                      "parameters": params.get(name),
                      "model_id": name + ":" + sha(canonical({"config": config,
                          "parameters": params.get(name), "sources": sources,
                          "training": sha(canonical(history)) if name in ("C5", "C6") else None}))}
                for name, config in CONFIG.items()}
    keys, ids, quote_ids = Counter(), Counter(), Counter()
    for row in contracts:
        try:
            keys[identity(row)] += 1
            ids[row["contract_id"]] += 1
            if isinstance(row.get("quote"), dict) and isinstance(row["quote"].get("quote_id"), str):
                quote_ids[row["quote"]["quote_id"]] += 1
        except (ValueError, TypeError):
            pass
    results = []
    for index, row in enumerate(contracts):
        base = {"input_index": index, "contract_id": row.get("contract_id") if isinstance(row, dict) else None}
        try:
            key = identity(row)
            if keys[key] != 1 or ids[row["contract_id"]] != 1:
                raise ValueError("duplicate_or_conflicting_contract")
            p, market, errors = None, None, {}
            for kind in ("model", "market"):
                try:
                    _, model_value, market_value = validate(row, files=files, freeze=freeze, now=now,
                        require_model=kind == "model", require_market=kind == "market")
                    if kind == "model":
                        p = model_value
                    else:
                        if quote_ids[row["quote"]["quote_id"]] != 1:
                            raise ValueError("duplicate_or_conflicting_quote_id")
                        market = market_value
                except (ValueError, KeyError, TypeError, OverflowError) as exc:
                    errors[kind] = str(exc)
            preds = probabilities(p, market, params)
            for name in CONFIG:
                result = dict(base, model_id=registry[name]["model_id"], candidate=name)
                if name not in preds:
                    reason = (errors.get("market") if name == "C2" else errors.get("model"))
                    if reason is None and name in ("C3", "C6", "C7"):
                        reason = errors.get("market")
                    results.append(dict(result, status="abstain", reason=reason or "prior_training_gate_blocked"))
                    continue
                prob = preds[name]
                push = row["production"]["push"] if p is not None else None
                triple = (dict(row["production"]) if name == "C1" else
                          None if name == "C2" else
                          {"over": (1-push)*prob, "under": (1-push)*(1-prob), "push": push})
                results.append(dict(result, status="forecast", event_id=row["event_id"],
                    identity=dict(zip(IDENTITY, key)), event_start_at=row["event_start_at"],
                    forecast_at=now.isoformat(), input_freeze_at=manifest["input_freeze_at"],
                    original_forecast_at=row["forecast_at"],
                    original_model_training_cutoff_at=row.get("model_training_cutoff_at"),
                    conditional_no_push={"over": prob, "under": 1-prob},
                    unconditional=triple,
                    push_policy="market_push_unidentified" if name == "C2" else "original_push_mass_unchanged",
                    quote_id=row["quote"]["quote_id"] if market is not None else None,
                    quote_source_sha256=row["quote"]["source_sha256"] if market is not None else None,
                    source_sha256=row["source_sha256"],
                    model_market_gap=abs(p-market) if p is not None and market is not None else None))
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            results.extend(dict(base, candidate=name, model_id=registry[name]["model_id"],
                                status="abstain", reason=str(exc)) for name in CONFIG)
    coverage = {name: {"input_contracts": len(contracts),
                      "forecast_contracts": sum(r["candidate"] == name and r["status"] == "forecast" for r in results),
                      "abstentions": dict(Counter(r["reason"] for r in results
                           if r["candidate"] == name and r["status"] == "abstain"))}
                for name in CONFIG}
    return {"schema": VERSION, "target_date": DAY, "status": "UNCERTIFIED_SHADOW",
            "capture_at": now.isoformat(), "source_code_sha256": sources,
            "registry": registry, "training": training, "coverage": coverage,
            "forecasts": results, "production_modified": False,
            "promotion_allowed": False, "source_attestation": "WS1_inherited_not_independently_certified"}


def write_exclusive(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical(payload)
    with path.open("xb") as stream:
        stream.write(raw)
    return sha(raw)


def finalize_emission(report):
    """Recheck the real clock immediately before append-only persistence."""
    emission = datetime.now(timezone.utc)
    report["capture_at"] = emission.isoformat()
    for row in report["forecasts"]:
        if row["status"] != "forecast":
            continue
        if emission >= timestamp(row["event_start_at"]):
            row.update(status="abstain", reason="started_before_immutable_write")
            row.pop("conditional_no_push", None)
            row.pop("unconditional", None)
            count = report["coverage"][row["candidate"]]
            count["forecast_contracts"] -= 1
            reasons = count["abstentions"]
            reasons[row["reason"]] = reasons.get(row["reason"], 0)+1
        else:
            row["forecast_at"] = emission.isoformat()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    # No caller-controlled backdated clock in the forecast CLI.
    now = datetime.now(timezone.utc).isoformat()
    manifest, files, contracts, history = load_bundle(args.manifest, args.manifest_sha256)
    result = build(manifest, files, contracts, history, now=now)
    # Check the real clock again after training and serialization preparation.
    emission = datetime.now(timezone.utc)
    result["capture_at"] = emission.isoformat()
    for row in result["forecasts"]:
        if row["status"] == "forecast":
            if emission >= timestamp(row["event_start_at"]):
                row.update(status="abstain", reason="started_before_immutable_write")
                for field in ("conditional_no_push", "unconditional"):
                    row.pop(field, None)
                count = result["coverage"][row["candidate"]]
                count["forecast_contracts"] -= 1
                count["abstentions"]["started_before_immutable_write"] = count["abstentions"].get("started_before_immutable_write", 0)+1
            else:
                row["forecast_at"] = emission.isoformat()
    result["input_manifest_sha256"] = args.manifest_sha256
    result["input_files_sha256"] = [x["sha256"] for x in manifest["files"]]
    result["code_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not args.out.resolve().is_relative_to((ROOT / "calibration_models").resolve()):
        raise ValueError("output_must_be_in_calibration_models")
    print(json.dumps({"sha256": write_exclusive(args.out, result), "coverage": result["coverage"]}, sort_keys=True))


if __name__ == "__main__":
    main()
