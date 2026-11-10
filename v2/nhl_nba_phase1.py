"""P1 NHL/NBA: deterministic, source-certified pregame baseline replay.

Consumes ORIGINAL frozen Nov-2026 run bundles and complete candidate attempt
ledgers. Does not rewrite the legacy forecast, silently infer market odds or
publish a newly computed baseline as an original pregame prediction.

The naive and pooled rate forecasts are *counterfactual shadow controls*:
they are computed at replay time from inputs known in the original archive.
Results become scored only when independently supplied official settlements
have a post-event timestamp and exact contract identity. No model promotion.
"""
from __future__ import annotations

import base64
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import tempfile

from .contracts import ContractError, FixedLineDistribution, PoissonDistribution, utc
from .evaluation import brier, log_loss, _cluster_interval, _mean
from .stat_registry import canonical_stat

SCHEMA = "v25-phase1-nhl-nba-certified-replay-v1"
BOOK_ORDER = ("Pinnacle", "Circa", "FanDuel", "DraftKings",
              "Caesars", "Bet365", "BetMGM")


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _finite(value, field):
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ContractError("invalid_numeric:" + field) from exc
    if not math.isfinite(number):
        raise ContractError("nonfinite_numeric:" + field)
    return number


def _pair_key(row):
    return (str(row["sport"]), str(row["event_id"]), str(row["player_id"]),
            str(row["stat"]), _finite(row["reference_line"], "line"))


def _attempt_key(row, *, original=False):
    return (str(row["sport"]), str(row["player_id"]), str(row["stat"]),
            str(row["side"]), _finite(row["reference_line"] if original
                                      else row["line"], "line"))


def _original_archives(packet, archive_root):
    blobs = packet.get("phase0_source_input_archive")
    if not isinstance(blobs, list) or not blobs:
        raise ContractError("phase0_original_source_archive_missing")
    root = Path(archive_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    seen = set()
    for entry in blobs:
        relative = entry.get("path")
        if (not isinstance(relative, str) or not relative
                or relative.startswith("/") or "\\" in relative
                or ".." in relative.split("/") or relative in seen):
            raise ContractError("duplicate_or_unsafe_original_source_blob")
        seen.add(relative)
        raw = base64.b64decode(entry["content_b64"], validate=True)
        if len(raw) != entry.get("bytes") or _sha(raw) != entry.get("sha256"):
            raise ContractError("original_source_hash_or_length_mismatch")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ContractError("original_source_path_escape")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return seen


def _usage_doc(row, root):
    receipts = [s for s in row["source_receipts"]
                if s.get("model_component") == "Engine_A"
                and str(s.get("archive_path") or "").startswith("historical_usage/")]
    if len(receipts) != 1:
        raise ContractError("usage_source_receipt_missing_or_ambiguous")
    receipt = receipts[0]
    raw = (root / receipt["archive_path"]).read_bytes()
    if _sha(raw) != receipt["content_sha256"]:
        raise ContractError("usage_source_bytes_changed")
    doc = json.loads(raw)
    if (str(doc.get("sport")) != str(row["sport"])
            or str(doc.get("player_id")) != str(row["player_id"])
            or str(doc.get("stat")) != str(row["stat"])):
        raise ContractError("usage_source_contract_identity_mismatch")
    retrieved = utc(doc.get("retrieved_at"), "history_retrieved_at")
    if retrieved > utc(row["input_freeze_at"], "input_freeze_at"):
        raise ContractError("usage_source_retrieved_after_original_freeze")
    return doc, receipt


def _observations(doc, freeze):
    all_rows = list(doc.get("observations") or [])
    prior = list(doc.get("prior_observations") or [])
    records = {}
    for prior_flag, group in ((True, prior), (False, all_rows)):
        for item in group:
            if not isinstance(item, dict):
                raise ContractError("invalid_historical_observation")
            event = str(item.get("id") or "")
            if not event:
                raise ContractError("missing_historical_event_id")
            raw_date = item.get("date")
            if isinstance(raw_date, str) and "T" not in raw_date:
                # Some NHL official game logs expose only the calendar date.
                # An earlier UTC DATE is safe as past history, but do not
                # invent an exact publication or puck-drop timestamp.
                try:
                    date_only = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError as exc:
                    raise ContractError("invalid_history_calendar_day") from exc
                if date_only >= freeze.date():
                    raise ContractError("unproven_same_day_history_order")
                start = datetime.fromisoformat(raw_date + "T00:00:00+00:00")
                precision = "original_calendar_day_only_ordering"
            else:
                start = utc(raw_date, "history_game_date")
                if start >= freeze:
                    raise ContractError("postfreeze_history_observation")
                precision = "original_precise_game_start"

            value = _finite(item.get("value"), "history_value")
            workload = _finite(item.get("workload"), "history_workload")
            if value < 0 or not value.is_integer() or workload < 0:
                raise ContractError("unsupported_historical_count_or_exposure")
            if event in records:
                if (records[event]["value"] != value or
                        records[event]["workload"] != workload):
                    raise ContractError("contradictory_historical_observation")
                continue
            records[event] = {
                "event_id": event, "start": start, "value": value,
                "workload": workload, "prior_season": prior_flag,
                "time_precision": precision,
            }
    return sorted(records.values(), key=lambda r: (r["start"], r["event_id"]))


def _ready_history(obs):
    return [r for r in obs if r["workload"] > 0]


def _probs(rate, line):
    distribution = PoissonDistribution(rate)
    probs = distribution.probabilities(line)
    return {
        "distribution": distribution.to_record(),
        "q_over": probs.over, "q_under": probs.under,
        "q_push": probs.push, "p_over_nonpush": probs.conditional_over(),
        "model_kind": "counterfactual_poisson_count_control",
        "originally_published_forecast": False,
    }


def _american_decimal(odds):
    n = _finite(odds, "american_odds")
    if n == 0 or -100 < n < 100:
        raise ContractError("unsupported_american_odds")
    return 1.0 + (100.0 / abs(n) if n < 0 else n / 100.0)


def _market_reference(row):
    books = (row.get("market") or {}).get("books") or []
    if not books:
        raise ContractError("frozen_market_book_receipts_missing")
    choices = sorted(books, key=lambda b: (
        BOOK_ORDER.index(b["book"]) if b.get("book") in BOOK_ORDER
        else len(BOOK_ORDER), str(b.get("book")), str(b.get("retrieved_at"))))
    book = choices[0]
    over = 1.0 / _american_decimal(book.get("over"))
    under = 1.0 / _american_decimal(book.get("under"))
    return {
        "status": "available",
        "source": "original_pregame_two_sided_bookmaker_via_PropLine",
        "book": book["book"], "book_count": len(books),
        "retrieved_at": book["retrieved_at"],
        "p_over_nonpush": over / (over + under),
        "over_american": book["over"], "under_american": book["under"],
        "push_mass_not_identifiable": True,
        "not_a_pickem_payout_probability": True,
    }


def _legacy_baseline(over, under):
    # Neither a preliminary A/B vote nor a 70/30 preview is final 60/40 V1.
    for r in (over, under):
        b = r.get("blend") or {}
        w = b.get("weights") or {}
        if (b.get("production_policy") is not True or
                b.get("available") is not True or
                b.get("preliminary") or
                b.get("post_shadow_finalization_pending") or
                w != {"a": 0.6, "b": 0.4} or r.get("q_model") is None):
            return {"status": "unavailable",
                    "reason": "original_60_40_not_final_or_missing",
                    "original_rows_preserved": True}
    probs = FixedLineDistribution(
        _finite(over["reference_line"], "line"),
        _finite(over["q_model"], "over"),
        _finite(under["q_model"], "under"),
        _finite(over.get("q_push"), "push"),
    ).probabilities(_finite(over["reference_line"], "line"))
    return {"status": "available", "q_over": probs.over,
            "q_under": probs.under, "q_push": probs.push,
            "p_over_nonpush": probs.conditional_over(),
            "original_rows_preserved": True}


def _status_for_raw_component(row, key):
    obj = row.get(key) or {}
    if not isinstance(obj, dict):
        return {"status": "unavailable", "reason": "missing_component"}
    if obj.get("abstain") or obj.get("reliable") is not True:
        return {"status": "unavailable", "reason": "source_model_abstained_or_unreliable"}
    v = obj.get("q_win")
    if v is None:
        return {"status": "unavailable", "reason": "component_probability_missing"}
    return {"status": "frozen_original_component",
            "conditional_side_win": _finite(v, key + ".q_win")}


def _settlement_index(items):
    index = {}
    for s in items:
        if not isinstance(s, dict):
            raise ContractError("invalid_official_settlement")
        if s.get("sport") not in ("NBA", "NHL"):
            raise ContractError("non_nba_nhl_settlement")
        if s.get("period") != "full":
            raise ContractError("settlement_period_mismatch")
        key = (str(s.get("sport")), str(s.get("event_id")),
               str(s.get("player_id")), str(s.get("stat")))
        if key in index:
            raise ContractError("duplicate_official_settlement_key")
        if s.get("status") not in ("settled", "void", "unavailable"):
            raise ContractError("unknown_settlement_status")
        if s.get("status") == "settled":
            if not s.get("source_url") or not str(s["source_url"]).startswith("https://"):
                raise ContractError("official_settlement_source_missing")
            if not s.get("settled_at"):
                raise ContractError("official_settlement_timestamp_missing")
            canonical_stat(s["sport"], s["stat"], "full").validate_actual(s.get("actual"))
        index[key] = s
    return index


def run_phase1(packet, attempts, *, archive_root, bundle_sha256,
               code_commit, settlement_rows=None, seed=20261110):
    """One deterministic NBA/NHL Phase 1 infrastructure evaluation.

    The generated simple-model controls are labeled counterfactual, and
    on unplayed slates all scores remain null (not zero). The input snapshot
    contract passes the real Phase0R certification, including frozen API
    quote lineage, before any inferred control distribution is created.
    """
    from phase0r_contract import strict_snapshot_status
    if not isinstance(packet, dict) or packet.get("predictions_are_frozen") is not True:
        raise ContractError("not_an_original_frozen_batch")
    if packet.get("phase") != "afternoon" or packet.get("settlements"):
        # Never treat a mutable postgame settlement write as the initial freeze.
        raise ContractError("non_original_afternoon_capture_bundle")
    if not isinstance(code_commit, str) or len(code_commit) != 40 or any(
            c not in "0123456789abcdef" for c in code_commit):
        raise ContractError("missing_exact_code_commit")
    if type(seed) is not int:
        raise ContractError("invalid_random_seed")
    if not isinstance(attempts, dict) or not isinstance(attempts.get("attempts"), list):
        raise ContractError("attempted_universe_ledger_missing")
    if (attempts.get("all_prepared_contracts_attempted") is not True or
            attempts.get("all_prepared_contracts_in_coverage_denominator") is not True):
        raise ContractError("incomplete_attempted_universe_ledger")
    original_rows = packet.get("forecasts")
    if not isinstance(original_rows, list) or not original_rows:
        raise ContractError("original_forecast_rows_missing")
    archives = _original_archives(packet, archive_root)
    root = Path(archive_root)
    ledger_status = Counter()
    ledger_reasons = Counter()
    attempted = {}
    for row in attempts["attempts"]:
        key = _attempt_key(row)
        if key in attempted:
            raise ContractError("duplicate_prepared_attempt")
        attempted[key] = row
        state = row.get("status")
        if state not in ("forecast", "unavailable"):
            raise ContractError("invalid_attempt_status")
        ledger_status[state] += 1
        if state == "unavailable":
            ledger_reasons[str(row.get("reason"))] += 1
    groups = defaultdict(dict)
    for row in original_rows:
        if row.get("sport") not in ("NHL", "NBA"):
            raise ContractError("unexpected_sport_in_scoped_NHL_NBA_run")
        ok, reason = strict_snapshot_status(row, archive_root=root)
        if not ok:
            raise ContractError("uncertified_original_forecast:" + reason)
        if _attempt_key(row, original=True) not in attempted:
            raise ContractError("forecast_missing_attempt")
        if attempted[_attempt_key(row, original=True)].get("status") != "forecast":
            raise ContractError("rejected_candidate_in_frozen_forecasts")
        key = _pair_key(row)
        side = row.get("side")
        if side not in ("over", "under") or side in groups[key]:
            raise ContractError("duplicate_or_invalid_original_side")
        groups[key][side] = row
    if (len(original_rows) != ledger_status["forecast"] or
            len(attempted) != len(attempts["attempts"])):
        raise ContractError("attempted_and_forecast_denominator_mismatch")
    if len(original_rows) != 2 * len(groups) or any(
            set(pairs) != {"over", "under"} for pairs in groups.values()):
        raise ContractError("unpaired_original_forecast_contract")

    # Every provider game history is first observed at the collector's actual
    # pre-evaluation retrieval time. Do not invent historical publication times.
    history = {}
    for key in sorted(groups):
        row = groups[key]["over"]
        doc, receipt = _usage_doc(row, root)
        obs = _observations(doc, utc(row["input_freeze_at"], "input_freeze_at"))
        history[key] = (doc, receipt, obs)
    peers = defaultdict(list)
    for key, (_doc, _receipt, obs) in history.items():
        sport, event_id, player_id, stat, _line = key
        token = (sport, stat)
        # Multiple alternate quote lines from the same player-game do not
        # duplicate their prior history in the peer pool.
        for o in _ready_history(obs):
            pkey = (sport, stat, player_id, o["event_id"])
            peers[token].append((pkey, o))
    pool = {}
    for token, members in peers.items():
        seen = {}
        for ident, o in members:
            if ident in seen and seen[ident] != o:
                raise ContractError("contradictory_peer_history")
            seen[ident] = o
        pool[token] = list(seen.items())

    indexed = _settlement_index(settlement_rows or [])
    contracts = []
    scores = defaultdict(dict)
    missing = defaultdict(Counter)
    all_states = Counter()
    by_sport = Counter()
    by_stat = Counter()
    for key in sorted(groups):
        sport, event_id, player_id, stat, line = key
        over, under = groups[key]["over"], groups[key]["under"]
        if (over["event_start"] != under["event_start"] or
                over.get("team") != under.get("team") or
                over.get("opponent") != under.get("opponent")):
            raise ContractError("paired_contract_event_mismatch")
        canonical_stat(sport, stat, "full")
        by_sport[sport] += 1
        by_stat[sport + "|" + stat] += 1
        freeze = utc(over["input_freeze_at"], "freeze_at")
        doc, receipt, obs = history[key]
        eligible = _ready_history(obs)
        own = eligible[-5:]
        recent_current = [o for o in own if not o["prior_season"]]
        peer = [(ident, r) for ident, r in pool.get((sport, stat), [])
                if ident[2] != player_id]
        opportunity = {
            "source_receipt_sha256": receipt["content_sha256"],
            "original_source_observed_at": receipt["retrieved_at"],
            "pregame_input_freeze_at": over["input_freeze_at"],
            "history_games_usable": len(eligible),
            "last5_count": len(own),
            "last5_current_season_count": len(recent_current),
            "prior_season_history_used": any(o["prior_season"] for o in own),
            "peer_position_known": False,
            "peer_group": "all_players_same_sport_and_stat_position_unknown",
            "projected_workload_origin": "median_of_last5_originally_archived_pregame_games",
            "historical_publication_time_asserted": False,
        }
        baseline = {}
        if not own:
            for name in ("naive_recent_exposure_rate", "pooled_peer_shrunk_rate"):
                baseline[name] = {"status": "unavailable", "reason": "no_usable_history"}
        else:
            exposure = statistics.median(o["workload"] for o in own)
            opportunity["projected_workload"] = exposure
            own_rate = sum(o["value"] for o in own)/sum(o["workload"] for o in own)
            baseline["naive_recent_exposure_rate"] = {
                "status": "counterfactual_shadow",
                **_probs(exposure*own_rate, line),
                "history_rows": len(own),
                "prior_season_history_used": opportunity["prior_season_history_used"],
            }
            if not peer:
                baseline["pooled_peer_shrunk_rate"] = {
                    "status": "unavailable", "reason": "no_distinct_peer_history"
                }
            else:
                peer_rate = sum(r["value"] for _ident, r in peer)/sum(
                    r["workload"] for _ident, r in peer)
                prior_exposure = 20.0
                shrunk = (sum(r["value"] for r in eligible) +
                          peer_rate*prior_exposure)/(
                          sum(r["workload"] for r in eligible) + prior_exposure)
                baseline["pooled_peer_shrunk_rate"] = {
                    "status": "counterfactual_shadow",
                    **_probs(exposure*shrunk, line),
                    "prior_exposure": prior_exposure,
                    "peer_observations": len(peer),
                    "position_unavailable_no_role_specific_promotion": True,
                }
        baseline["frozen_v1_60_40"] = _legacy_baseline(over, under)
        baseline["real_no_vig_market"] = _market_reference(over)
        baseline["Engine_A_original"] = _status_for_raw_component(over, "engine_a")
        baseline["Engine_B_original"] = _status_for_raw_component(over, "engine_b")
        # Sidecars have their own provenance: never synthesize one model
        # probability from another, or put a preliminary V1 preview in V1.
        for name in ("Bayesian_A", "Bayesian_B", "NUTS"):
            baseline[name] = {
                "status": "not_in_original_production_snapshot",
                "reason": "requires_independent_frozen_sidecar_receipt",
            }
        s = indexed.get((sport, event_id, player_id, stat))
        if s is None:
            outcome = {"status": "pending_official_settlement"}
        elif s["status"] != "settled":
            outcome = {"status": s["status"]}
        else:
            if utc(s["settled_at"], "settled_at") < utc(over["event_start"], "event_start"):
                raise ContractError("settlement_before_event")
            actual = canonical_stat(sport, stat, "full").validate_actual(s["actual"])
            state = "push" if actual == line else "over" if actual > line else "under"
            outcome = {"status": state, "actual": actual,
                       "settled_at": s["settled_at"], "source_url": s["source_url"]}
            if state != "push":
                observed_over = int(state == "over")
                for model, value in baseline.items():
                    if value.get("status") not in (
                            "counterfactual_shadow", "available"):
                        missing[model][value.get("reason", value["status"])] += 1
                        continue
                    prob = value.get("p_over_nonpush")
                    if prob is None:
                        missing[model]["nonpush_probability_unavailable"] += 1
                        continue
                    scores[model][key] = {
                        "brier": brier(prob, observed_over),
                        "log_loss": log_loss(prob, observed_over),
                        "observed_over": observed_over,
                        "selected_over": prob > .5,
                        "event": event_id,
                        "date": over["game_date"],
                        "sport": sport,
                        "stat": stat,
                    }
        all_states[outcome["status"]] += 1
        contracts.append({
            "contract_id": _sha(_canonical({"run_id": over["run_id"],
                "sport": sport, "event_id": event_id, "player_id": player_id,
                "stat": stat, "line": line, "period": "full"})),
            "source_run_id": over["run_id"], "sport": sport, "event_id": event_id,
            "player_id": player_id, "team_id": over["team"],
            "opponent_id": over["opponent"],
            "stat": stat, "period": "full", "line": line,
            "event_start": over["event_start"],
            "input_freeze_at": over["input_freeze_at"],
            "original_over_snapshot_sha256": _sha(_canonical(over)),
            "original_under_snapshot_sha256": _sha(_canonical(under)),
            "source_archive_receipt": receipt["source_id"],
            "market": baseline["real_no_vig_market"],
            "opportunity": opportunity, "models": baseline,
            "outcome": outcome,
        })

    summaries = {}
    for model in ("naive_recent_exposure_rate", "pooled_peer_shrunk_rate",
                  "frozen_v1_60_40", "real_no_vig_market", "Engine_A_original",
                  "Engine_B_original", "Bayesian_A", "Bayesian_B", "NUTS"):
        records = list(scores[model].values())
        counts = Counter(c["models"][model]["status"] for c in contracts)
        summaries[model] = {
            "contract_status_counts": dict(sorted(counts.items())),
            "paired_eligible_contracts": len(contracts),
            "scored_contracts": len(records),
            "brier": _mean(r["brier"] for r in records),
            "log_loss": _mean(r["log_loss"] for r in records),
            "predicted_over_share": _mean(int(r["selected_over"]) for r in records),
            "observed_over_share": _mean(r["observed_over"] for r in records),
            "missing_score_reasons": dict(sorted(missing[model].items())),
            "no_scores_must_not_be_interpreted_as_zero": not bool(records),
        }
    paired = {}
    champion = scores["naive_recent_exposure_rate"]
    for model in ("pooled_peer_shrunk_rate", "frozen_v1_60_40",
                  "real_no_vig_market"):
        other = scores[model]
        common = sorted(set(champion) & set(other))
        event_deltas = [(other[k]["event"], other[k]["brier"]-champion[k]["brier"])
                        for k in common]
        date_deltas = [(other[k]["date"], other[k]["brier"]-champion[k]["brier"])
                       for k in common]
        paired[model] = {
            "vs": "naive_recent_exposure_rate",
            "matched_contracts": len(common),
            "brier_difference": _mean(d for _cluster, d in event_deltas),
            "game_cluster_interval": _cluster_interval(event_deltas, seed, 1000),
            "date_cluster_interval": _cluster_interval(date_deltas, seed, 1000),
            "synthetic_market_probabilities_used": False,
        }

    report = {
        "schema": SCHEMA,
        "scope": ["NBA", "NHL"],
        "input_immutable_bundle_sha256": bundle_sha256,
        "code_commit": code_commit,
        "source_run_id": packet["run_id"],
        "original_forecast_rows": len(original_rows),
        "original_frozen_source_objects": len(archives),
        "prepared_attempt_count": len(attempted),
        "prepared_attempt_statuses": dict(sorted(ledger_status.items())),
        "prepared_rejection_reasons": dict(sorted(ledger_reasons.items())),
        "retained_paired_contracts": len(contracts),
        "by_sport": dict(sorted(by_sport.items())),
        "by_stat": dict(sorted(by_stat.items())),
        "settlement_states": dict(sorted(all_states.items())),
        "canonical_stat_registry": "v25-stat-registry-1",
        "baseline_protocol": {
            "naive": "last5_archived_observation_count_per_workload_times_last5_median_workload",
            "peer_shrink": "all_distinct_other_players_same_sport_stat_20_exposure_prior",
            "peer_position_unavailable": True,
            "actual_production_V1_never_recomputed": True,
            "current_computation_counterfactual_not_original_pregame_forecast": True,
            "no_2024_or_2025_untouched_holdout_claim": True,
            "no_second_stage_model_trained": True,
            "only_original_quote_times_and_source_receipts_used": True,
            "joint_scores": "UNAVAILABLE_NO_ORIGINAL_JOINT_SCENARIO_ENSEMBLE",
        },
        "model_comparison_columns": [
            "naive_recent_exposure_rate", "pooled_peer_shrunk_rate",
            "frozen_v1_60_40", "Engine_A_original", "Engine_B_original",
            "Bayesian_A", "Bayesian_B", "NUTS", "real_no_vig_market",
        ],
        "models": summaries, "paired": paired,
        "contracts": contracts,
        "seed": seed,
        "tier1_tier2_publication_allowed": False,
        "model_promotion_authorized": False,
        "forecast_history_modified": False,
        "historical_retrocertification_allowed": False,
    }
    report["report_sha256"] = _sha(_canonical(report))
    return report
