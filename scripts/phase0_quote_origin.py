"""Verify API quote lineage from ORIGINAL frozen quote rows, not wrapper URLs.

PropLine returns API-level quote URLs and collector timestamps, not independent
bookmaker publication timestamps. These existing fields are sufficient for a
bounded, pregame quote-lineage claim once exact athlete, stat, event, book,
line, prices, and retrieval time match the frozen evaluation contract.

This is not an attestation of independent sportsbook publication truth.
Do not add post-hoc provider clocks or consult current/upstream APIs here.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from odds_providers import normalize_player
from point_in_time_provenance import instant

PROPLINE_PATH = {
    "NBA": "/v1/sports/basketball_nba/odds",
    "NHL": "/v1/sports/icehockey_nhl/odds",
    "NFL": "/v1/sports/americanfootball_nfl/odds",
}


def _identity(sport, event_id, player, stat, book, line, over, under, retrieved):
    return (
        str(sport or ""), str(event_id or ""), normalize_player(player),
        str(stat or ""), str(book or ""), float(line), float(over),
        float(under), str(retrieved or ""),
    )


@lru_cache(maxsize=8)
def _frozen_quote_index(filename: str, sha256: str):
    """Cache parsed bytes; the outer strict receipt validator re-hashes on each call."""
    raw = Path(filename).read_bytes()
    if hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError("original_market_quote_archive_sha_mismatch")
    index = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        quote = json.loads(line)
        if not isinstance(quote, dict):
            raise ValueError("invalid_frozen_original_quote")
        key = _identity(
            quote.get("sport"), quote.get("event_id"),
            quote.get("player"), quote.get("stat"), quote.get("book"),
            quote.get("line"), quote.get("over_odds"),
            quote.get("under_odds"), quote.get("retrieved_at"),
        )
        index.setdefault(key, []).append(quote)
    if not index:
        raise ValueError("empty_frozen_original_quotes")
    return index


def verified_original_api_quote_lineage(row: dict, *, archive_root: Path):
    """Return PASS only if every book was actually present in frozen API bytes.

    Scoped to PropLine-namespace contracts. Legacy and third-party source
    contracts retain their existing strict source-receipt gates and are NOT
    declared PropLine-verified on this path.
    """
    if row.get("event_id_namespace") != "propline":
        return True, "not_propline_quote_lineage"
    try:
        sport = str(row.get("sport") or "")
        expected_path = PROPLINE_PATH.get(sport)
        if not expected_path:
            return False, "unrecognized_propline_sport"
        receipts = [
            receipt for receipt in row.get("source_receipts") or []
            if isinstance(receipt, dict)
            and receipt.get("model_component") == "Market"
            and str(receipt.get("archive_path") or "").startswith(
                "original_book_quotes/"
            )
        ]
        if len(receipts) != 1:
            return False, "original_market_quote_receipt_missing_or_ambiguous"
        receipt = receipts[0]
        root = Path(archive_root).resolve()
        path = (root / receipt["archive_path"]).resolve()
        if not path.is_relative_to(root):
            return False, "original_market_quote_path_escape"
        quotes = _frozen_quote_index(
            str(path), receipt["content_sha256"]
        )
        market = row.get("market") or {}
        books = market.get("books")
        if not isinstance(books, list) or not books:
            return False, "original_market_book_receipts_missing"
        frozen_at = instant(row.get("input_freeze_at"), "input_freeze_at")
        for book in books:
            key = _identity(
                sport, row.get("event_id"), row.get("player"),
                row.get("stat"), book.get("book"), book.get("line"),
                book.get("over"), book.get("under"), book.get("retrieved_at"),
            )
            matches = quotes.get(key, ())
            if len(matches) != 1:
                return False, "original_quote_event_player_stat_price_not_unique"
            quote = matches[0]
            url = urlsplit(quote.get("source_url") or "")
            if (url.scheme != "https" or url.hostname != "api.prop-line.com"
                    or url.path != expected_path or url.username is not None
                    or url.password is not None or url.fragment
                    or url.port not in (None, 443)):
                return False, "original_quote_api_origin_invalid"
            if quote.get("event_id_namespace") != "propline":
                return False, "original_quote_namespace_mismatch"
            if quote.get("player_norm") != normalize_player(quote.get("player")):
                return False, "original_quote_player_normalization_inconsistent"
            if quote.get("event_start") != row.get("event_start"):
                return False, "original_quote_event_start_mismatch"
            if instant(quote.get("retrieved_at"), "quote.retrieved_at") > frozen_at:
                return False, "original_quote_after_input_freeze"
        return True, "original_frozen_propline_api_quote_lineage_verified"
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        return False, "original_market_quote_lineage_invalid"
