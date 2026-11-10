"""Strict point-in-time checks for *promotion-eligible* prop snapshots.

A backtest with retrospectively filtered rows is not an archived pregame forecast.
The validator intentionally rejects missing source receipts; it never imputes
publication or retrieval timestamps from the game date or from postgame data.
"""
from __future__ import annotations

import math
import re
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SOURCE_COMPONENTS = {"Engine_A", "Engine_B", "Market"}


class ProvenanceError(ValueError):
    pass


def instant(value, field: str) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        raise ProvenanceError("missing_or_imprecise_timestamp:" + field)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError, OverflowError) as exc:
        raise ProvenanceError("invalid_timestamp:" + field) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ProvenanceError("naive_timestamp:" + field)
    return result.astimezone(timezone.utc)


def verified_source_receipt(source: dict, *, forecast: datetime, archive_root: Path | None) -> str:
    """Validate an immutable-archive receipt's metadata and timing.

    This validates the digest against actual immutable source bytes on disk.
    A mere receipt or retrospectively asserted timestamp is insufficient.
    """
    if not isinstance(source, dict) or source.get("status") != "verified":
        raise ProvenanceError("source_not_verified")
    ident = source.get("source_id")
    if not isinstance(ident, str) or not ident.strip():
        raise ProvenanceError("source_id_missing")
    url = source.get("source_url")
    collector_capture = (source.get("source_kind") == "collector_input_bytes"
                         and source.get("clock_semantics") ==
                             "collector_captured_no_publication_claim")
    if url is None and collector_capture:
        if source.get("source_url_status") != "upstream_url_unknown":
            raise ProvenanceError("source_upstream_url_status_invalid")
    else:
        if not isinstance(url, str):
            raise ProvenanceError("source_url_missing")
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username
                or parsed.password or (collector_capture and
                    (parsed.query or parsed.fragment))):
            raise ProvenanceError("source_url_not_https")
    digest = source.get("content_sha256")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ProvenanceError("source_digest_missing_or_invalid")
    observed = instant(source.get("observed_at"), "source.observed_at")
    retrieved = instant(source.get("retrieved_at"), "source.retrieved_at")
    if collector_capture:
        # These bytes were possessed at collector capture; unknown upstream
        # publication time is NOT invented or inferred from a filesystem mtime.
        if not retrieved <= observed <= forecast or source.get("published_at"):
            raise ProvenanceError("source_after_forecast_or_inconsistent_timeline")
    else:
        published = instant(source.get("published_at"), "source.published_at")
        if not observed <= published <= retrieved <= forecast:
            raise ProvenanceError("source_after_forecast_or_inconsistent_timeline")
    relative = source.get("archive_path")
    if archive_root is None:
        raise ProvenanceError("source_archive_root_missing")
    if not isinstance(relative, str) or not relative:
        raise ProvenanceError("source_archive_path_missing")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ProvenanceError("source_archive_path_unsafe")
    root = Path(archive_root).resolve()
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise ProvenanceError("source_archive_file_unavailable")
    if hashlib.sha256(candidate.read_bytes()).hexdigest() != digest:
        raise ProvenanceError("source_archive_digest_mismatch")
    return ident


def blend_snapshot_status(row: dict, *, archive_root: Path | None = None) -> tuple[bool, str]:
    """Audit a scored row without changing its historical prediction.

    A return of True requires exact relative archive bytes to match every
    source digest, along with the pregame timeline and contract identifiers.
    It does not prove independently that a provider's publication timestamp
    is truthful; immutable captured source timestamps must be reviewed.
    """
    try:
        forecast = instant(row.get("forecast_at"), "forecast_at")
        start = instant(row.get("event_start"), "event_start")
        settled = instant(row.get("settled_at"), "settled_at")
        if not forecast < start <= settled:
            raise ProvenanceError("poststart_forecast_or_early_settlement")
        day = row.get("game_date")
        if start.astimezone(ZoneInfo("America/Toronto")).date().isoformat() != day:
            raise ProvenanceError("event_game_date_mismatch")
        market = row.get("market")
        if not isinstance(market, dict) or market.get("market_valid") is not True:
            raise ProvenanceError("market_unavailable_or_unverified")
        observed = instant(market.get("retrieved_at"), "market.retrieved_at")
        if observed > forecast:
            raise ProvenanceError("post_forecast_market_quote")
        if market.get("line") is None:
            raise ProvenanceError("market_line_not_archived")
        if float(market["line"]) != float(row["reference_line"]):
            raise ProvenanceError("different_market_line")
        for quote in market.get("books", []) or []:
            if not isinstance(quote, dict) or "retrieved_at" not in quote:
                raise ProvenanceError("missing_book_quote_timestamp")
            if instant(quote["retrieved_at"], "market.book.retrieved_at") > forecast:
                raise ProvenanceError("future_book_quote")
            if quote.get("line") is not None and float(quote["line"]) != float(row["reference_line"]):
                raise ProvenanceError("different_book_line")
        receipts = row.get("source_receipts")
        used = row.get("used_source_ids")
        if not isinstance(receipts, list) or not receipts or not isinstance(used, list) or not used:
            raise ProvenanceError("source_manifest_missing")
        ids = set()
        components = set()
        for receipt in receipts:
            ident = verified_source_receipt(receipt, forecast=forecast, archive_root=archive_root)
            if ident in ids:
                raise ProvenanceError("duplicate_source_id")
            ids.add(ident)
            component = receipt.get("model_component")
            if component not in SOURCE_COMPONENTS:
                raise ProvenanceError("unknown_source_component")
            components.add(component)
        if not all(isinstance(x, str) and x for x in used) or len(set(used)) != len(used):
            raise ProvenanceError("invalid_used_source_ids")
        if set(used) != ids:
            raise ProvenanceError("incomplete_or_unused_source_manifest")
        required = {"Engine_A", "Market"}
        if not (row.get("engine_b") or {}).get("abstain"):
            required.add("Engine_B")
        if not required <= components:
            raise ProvenanceError("missing_engine_or_market_source_receipt")
        # Reconcile the archived outcome, never repair it silently.
        actual = row.get("actual_stat")
        if actual is not None:
            value, line = float(actual), float(row["reference_line"])
            if not math.isfinite(value) or not math.isfinite(line):
                raise ProvenanceError("nonfinite_actual_or_line")
            side = row.get("side")
            if side not in ("over", "under"):
                raise ProvenanceError("invalid_side")
            expected = ("push" if value == line else
                        "win" if (value > line) == (side == "over") else "loss")
            if expected != row.get("outcome"):
                raise ProvenanceError("actual_outcome_mismatch")
        return True, "verified_metadata_and_archived_source_receipts"
    except (ProvenanceError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return False, str(exc)


def pregame_snapshot_status(row: dict, *, archive_root: Path | None = None) -> tuple[bool, str]:
    """Fail-closed pre-event source/market/training-cutoff attestation.

    Unlike blend_snapshot_status this can run BEFORE the game settles. It never
    needs or trusts actual_stat, outcome, settlement or retrospective feature
    values. Archived original bytes are mandatory for every declared input.
    This certifies receipt/timing consistency, not the truth of a provider's
    independently claimed publication date or hidden upstream transformations.
    """
    try:
        if not isinstance(row, dict):
            raise ProvenanceError("invalid_forecast")
        forecast = instant(row.get("forecast_at"), "forecast_at")
        start = instant(row.get("event_start"), "event_start")
        if not forecast < start:
            raise ProvenanceError("forecast_not_strictly_before_event")
        freeze = instant(row.get("input_freeze_at"), "input_freeze_at")
        if freeze > forecast:
            raise ProvenanceError("input_freeze_after_forecast")
        cutoff = instant(row.get("model_training_cutoff_at"), "model_training_cutoff_at")
        if cutoff > freeze:
            raise ProvenanceError("model_trained_after_input_freeze")
        capture_at = row.get("source_capture_at")
        if capture_at is not None and instant(capture_at, "source_capture_at") > freeze:
            raise ProvenanceError("source_captured_after_input_freeze")
        if start.astimezone(ZoneInfo("America/Toronto")).date().isoformat() != row.get("game_date"):
            raise ProvenanceError("event_game_date_mismatch")
        for key in ("run_id", "sport", "player_id", "stat", "side", "event_id"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ProvenanceError("missing_contract_identity:" + key)
        if row["side"] not in ("over", "under"):
            raise ProvenanceError("invalid_side")
        line = row.get("reference_line")
        if (isinstance(line, bool) or not isinstance(line, (int, float))
                or not math.isfinite(line) or line < 0):
            raise ProvenanceError("invalid_reference_line")
        market = row.get("market")
        if not isinstance(market, dict) or market.get("market_valid") is not True:
            raise ProvenanceError("market_unavailable_or_unverified")
        market_time = instant(market.get("retrieved_at"), "market.retrieved_at")
        if market_time > freeze:
            raise ProvenanceError("post_input_freeze_market_quote")
        price_line = market.get("line")
        if (isinstance(price_line, bool) or not isinstance(price_line, (int, float))
                or not math.isfinite(price_line) or float(price_line) != float(line)):
            raise ProvenanceError("different_market_line")
        books = market.get("books")
        if not isinstance(books, list) or not books:
            raise ProvenanceError("market_book_quote_receipt_missing")
        for book in books:
            if not isinstance(book, dict) or not str(book.get("book") or "").strip():
                raise ProvenanceError("invalid_book_identity")
            observed = instant(book.get("retrieved_at"), "market.book.retrieved_at")
            if observed > freeze:
                raise ProvenanceError("post_input_freeze_book_quote")
            if (book.get("line") is None or isinstance(book["line"], bool)
                    or not isinstance(book["line"], (int, float))
                    or float(book["line"]) != float(line)):
                raise ProvenanceError("different_book_line")
        receipts, used = row.get("source_receipts"), row.get("used_source_ids")
        if not isinstance(receipts, list) or not receipts or not isinstance(used, list) or not used:
            raise ProvenanceError("source_manifest_missing")
        ids = set()
        components = set()
        for receipt in receipts:
            ident = verified_source_receipt(receipt, forecast=freeze, archive_root=archive_root)
            if receipt.get("source_kind") == "collector_input_bytes" and capture_at is None:
                raise ProvenanceError("source_capture_at_missing")
            if ident in ids:
                raise ProvenanceError("duplicate_source_id")
            ids.add(ident)
            component = receipt.get("model_component")
            if component not in SOURCE_COMPONENTS:
                raise ProvenanceError("unknown_source_component")
            components.add(component)
        if (any(not isinstance(x, str) or not x for x in used)
                or len(used) != len(set(used)) or set(used) != ids):
            raise ProvenanceError("incomplete_or_unused_source_manifest")
        required = {"Engine_A", "Market"}
        if not (row.get("engine_b") or {}).get("abstain"):
            required.add("Engine_B")
        if not required <= components:
            raise ProvenanceError("missing_engine_or_market_source_receipt")
        return True, "pregame_archived_inputs_and_training_timeline_verified"
    except (ProvenanceError, KeyError, TypeError, ValueError, OverflowError) as exc:
        return False, str(exc)
