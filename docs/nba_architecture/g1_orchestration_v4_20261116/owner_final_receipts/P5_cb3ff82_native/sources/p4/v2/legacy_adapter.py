"""Adapter for ORIGINAL frozen V1 60/40 forecast pairs, never a V1 re-fit.

The adapter cannot turn A/B previews, absent consensus or historical source
hashes into an authenticated V1 benchmark. Both sides and their exact quotes
must be independently certified by Phase 0R before a paired distribution is
scorable. Ineligible originals remain in the complete reason ledger.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .contracts import (ContractError, FixedLineDistribution,
                        ForecastSnapshot, MarketQuote, SourceReceipt,
                        canonical_hash, finite, utc)


@dataclass(frozen=True)
class FrozenLegacyPair:
    key: tuple
    over_row: dict
    under_row: dict
    distribution: FixedLineDistribution
    original_over_sha256: str
    original_under_sha256: str
    certified: bool

    def bind(self, quote: MarketQuote, *, code_commit: str,
             model_artifact_sha256: str, run_id: str | None = None) -> ForecastSnapshot:
        """Convert only independently certified original votes to a V2.5 snapshot.

        Artifact digest must come from the actual original run provenance.
        A paired model output hash is NOT substituted for a trained artifact.
        """
        if not self.certified:
            raise ContractError("uncertified_legacy_cannot_be_scored")
        over, under = self.over_row, self.under_row
        if (canonical_hash(over) != self.original_over_sha256
                or canonical_hash(under) != self.original_under_sha256):
            raise ContractError("original_frozen_legacy_modified_after_scan")
        original_market_digests = {
            r.get("content_sha256") for row in (over,under)
            for r in (row.get("source_receipts") or [])
            if r.get("model_component") == "Market"
        }
        if quote.quote_receipt_sha256 not in original_market_digests:
            raise ContractError("legacy_quote_original_market_receipt_unmatched")
        if ((over.get("team") is not None and str(over["team"]) != str(quote.team_id))
                or (over.get("opponent") is not None
                    and str(over["opponent"]) != str(quote.opponent_id))):
            raise ContractError("legacy_team_or_opponent_mismatch")
        if (str(quote.event_id) != str(over["event_id"])
                or str(quote.player_id) != str(over["player_id"])
                or str(quote.stat_key) != str(over["stat"])
                or float(quote.line) != self.distribution.line):
            raise ContractError("legacy_quote_contract_mismatch")
        if quote.sport != over["sport"] or quote.period != "full":
            raise ContractError("legacy_sport_or_period_mismatch")
        # P0R receipts record archive possession, not an upstream provider's
        # unknown publication date. Never infer a source publication clock.
        seen = set()
        sources = []
        for row in (over, under):
            for receipt in row.get("source_receipts") or []:
                source_id = receipt.get("source_id")
                if source_id in seen:
                    continue
                seen.add(source_id)
                if receipt.get("source_kind") != "collector_input_bytes":
                    raise ContractError("unsupported_legacy_source_kind")
                captured = receipt.get("observed_at")
                if captured is None:
                    raise ContractError("legacy_source_possession_time_missing")
                sources.append(SourceReceipt(
                    source_id=source_id,
                    first_available_at=captured, retrieved_at=captured,
                    content_sha256=receipt["content_sha256"],
                    source_uri=None, archive_path=receipt["archive_path"],
                    source_kind="archive_possession",
                ))
        if not sources:
            raise ContractError("legacy_source_receipts_missing")
        start = max(utc(over["forecast_at"], "forecast_at"),
                    utc(under["forecast_at"], "forecast_at"))
        freeze = max(utc(over["input_freeze_at"], "freeze"),
                     utc(under["input_freeze_at"], "freeze"))
        trained = max(utc(over["model_training_cutoff_at"], "model_cutoff"),
                      utc(under["model_training_cutoff_at"], "model_cutoff"))
        latest_source = max(utc(r.retrieved_at, "source_time") for r in sources)
        if latest_source > freeze:
            raise ContractError("legacy_paired_source_exceeds_freeze")
        snapshot = ForecastSnapshot(
            forecast_id="v1pair:" + canonical_hash({
                "over": self.original_over_sha256,
                "under": self.original_under_sha256,
                "quote": quote.quote_id,
            }),
            run_id=run_id or str(over["run_id"]),
            model_id="frozen_v1",
            model_version="archived_original_60_40_no_refit",
            quote_id=quote.quote_id, contract_id=quote.contract_id,
            event_id=quote.event_id, sport=quote.sport, league=quote.league,
            season=quote.season, team_id=quote.team_id,
            opponent_id=quote.opponent_id, player_id=quote.player_id,
            stat_key=quote.stat_key, period=quote.period, line=quote.line,
            quote_receipt_sha256=quote.quote_receipt_sha256,
            forecast_at=start.isoformat(),
            input_freeze_at=freeze.isoformat(),
            decision_cutoff_at=freeze.isoformat(),
            model_training_cutoff_at=trained.isoformat(),
            model_artifact_sha256=model_artifact_sha256,
            code_commit=code_commit,
            sources=tuple(sources),
            distribution=self.distribution,
        )
        snapshot.validate_against(quote)
        return snapshot


def _key(row: dict) -> tuple:
    required = ("run_id", "game_date", "sport", "event_id", "player_id",
                "stat", "reference_line")
    for item in required:
        if row.get(item) is None or row[item] == "":
            raise ContractError("legacy_missing_identity:" + item)
    return tuple(str(row[k]) for k in required[:-1]) + (finite(row["reference_line"], "line"),)


def _is_final_v1(row: dict) -> str | None:
    blend = row.get("blend") or {}
    if not isinstance(blend, dict):
        return "invalid_legacy_blend"
    weights = blend.get("weights") or {}
    if (blend.get("preliminary") or blend.get("post_shadow_finalization_pending")
            or blend.get("available") is not True):
        return "legacy_consensus_not_final"
    if (not isinstance(weights, dict) or
            weights.get("a") != 0.6 or weights.get("b") != 0.4):
        return "legacy_frozen_60_40_weights_unverified"
    if row.get("q_model") is None:
        return "legacy_final_probability_missing"
    if row.get("source_capture_error"):
        return "legacy_source_capture_failed"
    return None


def scan_original_pairs(rows: list[dict], *, strict_checker: Callable | None = None,
                        archive_root=None) -> dict:
    """Return complete all-side audit and eligible paired contracts.

    A source archive must be checked by the REAL Phase 0R validator. No
    checker, failed checker or retrospective data means diagnostic-only.
    """
    groups: dict[tuple, dict] = {}
    reasons: Counter = Counter()
    pairs: list[FrozenLegacyPair] = []
    decisions = []
    invalid_rows = 0
    for index, row in enumerate(rows):
        try:
            if not isinstance(row, dict):
                raise ContractError("legacy_row_not_object")
            key = _key(row)
            side = row.get("side")
            if side not in ("over", "under"):
                raise ContractError("legacy_invalid_side")
        except (ContractError, ValueError, TypeError) as exc:
            reason = str(exc)
            reasons[reason] += 1
            invalid_rows += 1
            decisions.append({"row_index": index, "status": "rejected", "reason": reason})
            continue
        bucket = groups.setdefault(key, {})
        if side in bucket:
            # Two contradictory frozen originals for the same exact side
            # cannot be treated as separate candidate betting contracts.
            raise ContractError("legacy_duplicate_original_side")
        bucket[side] = (index, row)
    for key in sorted(groups):
        bucket = groups[key]
        if set(bucket) != {"over", "under"}:
            reason = "legacy_opposite_side_missing"
        else:
            over = bucket["over"][1]
            under = bucket["under"][1]
            reason = _is_final_v1(over) or _is_final_v1(under)
            if reason is None:
                try:
                    # q_model is the original PRESELECTED side's absolute win
                    # probability. Do not substitute q_win, component scores,
                    # a 70/30 preview or a post-hoc consensus.
                    a = finite(over["q_model"], "original_over_win")
                    b = finite(under["q_model"], "original_under_win")
                    ap = finite(over["q_push"], "original_over_push")
                    bp = finite(under["q_push"], "original_under_push")
                    if abs(ap - bp) > 1e-9:
                        raise ContractError("legacy_push_mismatch")
                    distribution = FixedLineDistribution(key[-1], a, b, ap)
                    if (str(over.get("event_start")) != str(under.get("event_start"))
                            or str(over.get("event_id")) != str(under.get("event_id"))):
                        raise ContractError("legacy_event_pair_mismatch")
                except (ContractError, KeyError, ValueError) as exc:
                    reason = str(exc)
            if reason is None:
                if strict_checker is None or archive_root is None:
                    reason = "phase0r_certificate_required"
                else:
                    for row in (over, under):
                        try:
                            approved, why = strict_checker(row, archive_root=archive_root)
                        except (ValueError, TypeError, KeyError, OSError) as exc:
                            approved, why = False, type(exc).__name__ + ":" + str(exc)[:80]
                        if not approved:
                            reason = "phase0r:" + str(why)
                            break
            if reason is None:
                pairs.append(FrozenLegacyPair(
                    key=key, over_row=deepcopy(over), under_row=deepcopy(under),
                    distribution=distribution,
                    original_over_sha256=canonical_hash(over),
                    original_under_sha256=canonical_hash(under),
                    certified=True,
                ))
        if reason:
            reasons[reason] += 1
        decisions.append({"key": list(key), "status": "eligible" if reason is None
                          else "rejected", "reason": reason})
    return {
        "schema": "v25-frozen-v1-adapter-1",
        "rows": len(rows), "unique_contracts": len(groups),
        "invalid_original_rows": invalid_rows,
        "eligible_pairs": len(pairs),
        "rejected_pairs": sum(reasons.values()),
        "reasons": dict(sorted(reasons.items())),
        "decisions": decisions,
        "pairs": pairs,  # caller may bind ONLY these after strict cert.
        "historical_retrocertification_allowed": False,
    }
