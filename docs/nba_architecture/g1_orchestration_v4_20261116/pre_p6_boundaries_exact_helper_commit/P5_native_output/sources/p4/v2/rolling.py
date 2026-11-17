"""P1-03: deterministic, leakage-sentinel rolling-origin baseline research.

This runner fits only simple count-rate controls. It is a *counterfactual*
historical replay, not evidence that these predictions were originally
published in 2024. The genuine V1 model is NEVER recomputed here: frozen
original V1 votes enter only through the separate Phase 0R-certified adapter.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
import math

from .baselines import HistoricalExposure, poisson_rate_baseline, role_shrunk_rate
from .contracts import (ContractError, MarketQuote, SourceReceipt, canonical_hash,
                        finite, no_vig_over, parse_quote, utc)
from .evaluation import Settlement, brier, log_loss, _mean, _cluster_interval
from .stat_registry import canonical_stat

MODELS = ("naive_pregame_exposure_rate", "role_shrunk_hierarchical_rate",
          "two_sided_no_vig_market")
SCHEMA = "v25-rolling-prequential-shadow-1"


def _id(value, name):
    if not isinstance(value, str) or not value:
        raise ContractError("missing_rolling_identity:" + name)
    return value


def _history(items):
    result = []
    seen = set()
    for raw in items:
        r = HistoricalExposure(**raw)
        key = (r.event_id, r.player_id, r.stat_key)
        if key in seen:
            raise ContractError("duplicate_training_observation")
        seen.add(key)
        result.append(r)
    return result


def run_rolling(payload: dict, *, seed: int = 20261109, bootstrap_replicates: int = 1000):
    if not isinstance(payload, dict) or payload.get("schema") != "v25-rolling-input-1":
        raise ContractError("unrecognized_rolling_input")
    if type(seed) is not int or seed < 0:
        raise ContractError("invalid_rolling_seed")
    for key in ("history", "quotes", "settlements", "origins"):
        if not isinstance(payload.get(key), list):
            raise ContractError("missing_rolling_array:" + key)
    history = _history(payload["history"])
    quotes = [parse_quote(x) for x in payload["quotes"]]
    by_quote = {}
    ids = set()
    for q in quotes:
        if q.quote_id in by_quote or q.contract_id in ids:
            raise ContractError("duplicate_rolling_quote_or_contract")
        by_quote[q.quote_id] = q
        ids.add(q.contract_id)
    by_result = {}
    for raw in payload["settlements"]:
        s = Settlement(**raw)
        if s.key() in by_result:
            raise ContractError("duplicate_rolling_settlement")
        by_result[s.key()] = s
    origin_ids = set()
    prepared = []
    covered = set()
    # PREDECLARE all forecast decision origins. Source outcomes are always
    # filtered at the *start* of each origin, never by the row's final result.
    for raw in payload["origins"]:
        origin_id = _id(raw.get("origin_id"), "origin_id")
        if origin_id in origin_ids:
            raise ContractError("duplicate_rolling_origin")
        origin_ids.add(origin_id)
        frozen = utc(raw.get("freeze_at"), "freeze_at")
        if not isinstance(raw.get("offers"), list) or not raw["offers"]:
            raise ContractError("rolling_origin_offers_missing")
        offers = []
        for offer in raw["offers"]:
            qid = _id(offer.get("quote_id"), "quote_id")
            if qid not in by_quote or qid in covered:
                raise ContractError("unknown_or_reused_origin_quote")
            covered.add(qid)
            q = by_quote[qid]
            if utc(q.quote_at, "quote_at") > frozen and q.accepted:
                raise ContractError("future_market_quote_in_rolling_origin")
            if frozen >= utc(q.event_start_at, "event_start") and q.accepted:
                raise ContractError("rolling_origin_after_kickoff")
            if not isinstance(offer.get("sources"), list) or not offer["sources"]:
                raise ContractError("projected_exposure_source_receipt_missing")
            source_receipts = tuple(SourceReceipt(**s) for s in offer["sources"])
            if len({r.source_id for r in source_receipts}) != len(source_receipts):
                raise ContractError("duplicate_projected_exposure_receipt")
            if any(utc(r.retrieved_at, "source_at") > frozen for r in source_receipts):
                raise ContractError("future_projected_exposure_source")
            exp = finite(offer.get("projected_exposure"), "projected_exposure")
            if exp <= 0:
                raise ContractError("nonpositive_projected_exposure")
            offers.append((q, offer, source_receipts, exp))
        prepared.append((frozen, origin_id, offers))
    if covered != set(by_quote):
        raise ContractError("uncovered_rolling_quote_universe")
    if not prepared:
        raise ContractError("no_rolling_origins")
    if prepared != sorted(prepared, key=lambda x: (x[0], x[1])):
        raise ContractError("rolling_origins_not_chronological")

    all_origins = []
    ledger = []
    model_results = {name: {} for name in MODELS}
    missing = {name: Counter() for name in MODELS}
    statuses = Counter()
    for frozen, origin_id, offers in prepared:
        as_of = frozen.isoformat()
        # All same-origin outcomes are prohibited even if some games ended
        # before a later game that shares an experiment fold.
        current_events = {q.event_id for q, _o, _s, _e in offers}
        eligible = [h for h in history
                    if utc(h.available_at, "history_available_at") <= frozen
                    and utc(h.event_start_at, "history_event_start_at") < frozen
                    and h.event_id not in current_events]
        used_cutoff = max((utc(h.available_at, "available_at")
                           for h in eligible), default=None)
        fold = {"origin_id": origin_id, "input_freeze_at": as_of,
                "forecast_contracts": len(offers),
                "history_rows_available": len(eligible),
                "max_training_available_at": used_cutoff.isoformat() if used_cutoff else None,
                "training_event_ids": sorted({r.event_id for r in eligible}),
                "counterfactual_only": True}
        all_origins.append(fold)
        for q, offer, sources, exposure in offers:
            row = {"origin": origin_id, "quote_id": q.quote_id,
                   "contract_id": q.contract_id, "sport": q.sport,
                   "stat_key": q.stat_key, "event_id": q.event_id,
                   "event_start_at": q.event_start_at, "model_results": {},
                   "quote_kind": q.quote_kind}
            if not q.accepted:
                statuses["rejected_quote"] += 1
                row["status"] = "rejected_quote"
                row["reason"] = q.reject_reason
                ledger.append(row)
                continue
            s = by_result.get(q.settlement_key())
            if s is None:
                statuses["missing_settlement"] += 1
                row["status"] = "missing_settlement"
                ledger.append(row)
                continue
            if s.status != "settled":
                statuses[s.status] += 1
                row["status"] = s.status
                ledger.append(row)
                continue
            if utc(s.settled_at, "settled_at") < utc(q.event_start_at, "start"):
                raise ContractError("rolling_outcome_available_before_game")
            canonical = canonical_stat(q.sport, q.stat_key, q.period)
            actual = canonical.validate_actual(s.actual)
            status = "push" if actual == q.line else "scorable"
            row["status"] = status
            statuses[status] += 1
            if canonical.value_kind != "count":
                for model in MODELS[:2]:
                    missing[model]["non_count_likelihood_requires_distinct_baseline"] += 1
                row["model_results"]["naive_pregame_exposure_rate"] = None
                row["model_results"]["role_shrunk_hierarchical_rate"] = None
            else:
                for model in MODELS[:2]:
                    try:
                        if model == MODELS[0]:
                            distribution = poisson_rate_baseline(
                                eligible, player_id=q.player_id, stat_key=q.stat_key,
                                freeze_at=as_of, projected_exposure=exposure,
                                window=int(offer.get("recent_window", 5)))
                        else:
                            distribution = role_shrunk_rate(
                                eligible, player_id=q.player_id,
                                stat_key=q.stat_key, role=_id(offer.get("role"), "role"),
                                freeze_at=as_of, projected_exposure=exposure,
                                prior_exposure=finite(offer.get("prior_exposure", 20),
                                                      "prior_exposure"))
                        pred = distribution.probabilities(q.line)
                        p = pred.conditional_over()
                        if p is None and status != "push":
                            raise ContractError("baseline_only_predicts_push")
                        prediction = {
                            "model": model, "q_over": pred.over, "q_under": pred.under,
                            "q_push": pred.push, "p_over_conditional": p,
                            "rate": distribution.rate, "origin_id": origin_id,
                            "history_max_available_at": fold["max_training_available_at"],
                            "source_receipt_ids": sorted(r.source_id for r in sources),
                            "counterfactual_generated_not_original": True,
                        }
                        if status != "push":
                            y = int(actual > q.line)
                            prediction.update(
                                brier=brier(p, y), log_loss=log_loss(p, y),
                                direction_hit=int((p > .5) == bool(y)) if p != .5 else None)
                            model_results[model][q.quote_id] = {
                                **prediction, "event_id": q.event_id,
                                "date_utc": q.event_start_at[:10],
                                "observed_over": y}
                        row["model_results"][model] = prediction
                    except (ContractError, ValueError) as exc:
                        reason = str(exc)
                        missing[model][reason] += 1
                        row["model_results"][model] = {"status": "unavailable",
                                                      "reason": reason}
            baseline = no_vig_over(q)
            if baseline is None:
                missing[MODELS[2]]["real_compatible_two_sided_quote_missing"] += 1
                row["model_results"][MODELS[2]] = {"status": "unavailable",
                                                    "reason": "real_compatible_two_sided_quote_missing"}
            else:
                market = {"q_over_nonpush": baseline, "market_is_only_binary_reference": True,
                          "original_quote_sha256": q.quote_receipt_sha256}
                if status != "push":
                    y = int(actual > q.line)
                    market.update(brier=brier(baseline, y), log_loss=log_loss(baseline, y),
                                  direction_hit=int((baseline > .5) == bool(y))
                                  if baseline != .5 else None)
                    model_results[MODELS[2]][q.quote_id] = {
                        **market, "event_id": q.event_id,
                        "date_utc": q.event_start_at[:10], "observed_over": y}
                row["model_results"][MODELS[2]] = market
            ledger.append(row)

    summaries = {}
    for model in MODELS:
        records = model_results[model]
        summaries[model] = {
            "matched_scorable_contracts": len(records),
            "offered_contracts": len(quotes),
            "coverage_of_all_offers": len(records) / len(quotes),
            "brier": _mean(x["brier"] for x in records.values()),
            "log_loss": _mean(x["log_loss"] for x in records.values()),
            "directional_hit_rate": _mean(x["direction_hit"] for x in records.values()
                                          if x.get("direction_hit") is not None),
            "missing_reasons": dict(sorted(missing[model].items())),
            "distinct_event_clusters": len({x["event_id"] for x in records.values()}),
            "distinct_date_clusters": len({x["date_utc"] for x in records.values()}),
        }
    paired = {}
    base = model_results[MODELS[0]]
    for model in MODELS[1:]:
        others = model_results[model]
        common = sorted(set(base) & set(others))
        game_delta = [(base[k]["event_id"], others[k]["brier"]-base[k]["brier"])
                      for k in common]
        date_delta = [(base[k]["date_utc"], others[k]["brier"]-base[k]["brier"])
                      for k in common]
        paired[model] = {
            "vs": MODELS[0], "matched_contracts": len(common),
            "brier_difference": _mean(d for _g,d in game_delta),
            "log_loss_difference": _mean(others[k]["log_loss"]-base[k]["log_loss"]
                                         for k in common),
            "game_cluster_brier_interval": _cluster_interval(
                game_delta, seed, bootstrap_replicates),
            "date_cluster_brier_interval": _cluster_interval(
                date_delta, seed, bootstrap_replicates),
        }
    return {
        "schema": SCHEMA,
        "experiment_id": _id(payload.get("experiment_id"), "experiment_id"),
        "all_quotes": len(quotes),
        "all_origins": len(prepared),
        "statuses": dict(sorted(statuses.items())),
        "origin_manifest": all_origins,
        "models": summaries,
        "paired": paired,
        "contract_ledger": ledger,
        "bootstrap_seed": seed, "bootstrap_replicates": bootstrap_replicates,
        "historical_retrocertification_allowed": False,
        "prospective_forecasts_created": 0,
        "production_promotion_authorized": False,
        "counterfactual_only": True,
    }
