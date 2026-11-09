"""Strict point-in-time checks for *promotion-eligible* prop snapshots.

A backtest with retrospectively filtered rows is not an archived pregame forecast.
The validator intentionally rejects missing source receipts; it never imputes
publication or retrieval timestamps from the game date or from postgame data.
"""
from __future__ import annotations

import math
import re
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


def verified_source_receipt(source: dict, *, forecast: datetime) -> str:
    """Validate an immutable-archive receipt's metadata and timing.

    SHA-256 syntax is checked here. Content authentication also requires the
    calling archive loader to compare that digest with the actual source bytes.
    """
    if not isinstance(source, dict) or source.get("status") != "verified":
        raise ProvenanceError("source_not_verified")
    ident = source.get("source_id")
    if not isinstance(ident, str) or not ident.strip():
        raise ProvenanceError("source_id_missing")
    url = source.get("source_url")
    if not isinstance(url, str):
        raise ProvenanceError("source_url_missing")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ProvenanceError("source_url_not_https")
    digest = source.get("content_sha256")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise ProvenanceError("source_digest_missing_or_invalid")
    observed = instant(source.get("observed_at"), "source.observed_at")
    published = instant(source.get("published_at"), "source.published_at")
    retrieved = instant(source.get("retrieved_at"), "source.retrieved_at")
    if not observed <= published <= retrieved <= forecast:
        raise ProvenanceError("source_after_forecast_or_inconsistent_timeline")
    return ident


def blend_snapshot_status(row: dict) -> tuple[bool, str]:
    """Audit a scored row without changing its historical prediction.

    A return of True asserts only that the timeline/identity contract and
    archival receipts are present. It does not independently authenticate
    external source bytes, which must be done by the frozen archive loader.
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
        if not isinstance(market, dict) or market.get("market_valid") is False:
            raise ProvenanceError("market_unavailable")
        observed = instant(market.get("retrieved_at"), "market.retrieved_at")
        if observed > forecast:
            raise ProvenanceError("post_forecast_market_quote")
        if market.get("line") is not None:
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
            ident = verified_source_receipt(receipt, forecast=forecast)
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
        if row.get("source_archive_bytes_verified") is not True:
            raise ProvenanceError("source_archive_bytes_not_verified")
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
