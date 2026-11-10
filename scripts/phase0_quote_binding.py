"""Exact original two-sided quote binding for Phase 0R.

Compare the originally evaluated per-book prices against the original
collector JSONL. Hashing both independently is insufficient: a detached
or substituted market candidate could otherwise reference unrelated
authentic bytes. No bookmaker price, game identity or clock is inferred.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math

from odds_providers import normalize_player


def _utc(text):
    if not isinstance(text, str) or "T" not in text:
        raise ValueError("market_quote_timestamp_missing")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("market_quote_timestamp_invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("market_quote_timestamp_naive")
    return parsed.astimezone(timezone.utc)


def _finite(value, name):
    if isinstance(value, bool):
        raise ValueError("market_quote_" + name + "_invalid")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("market_quote_" + name + "_invalid") from exc
    if not math.isfinite(result):
        raise ValueError("market_quote_" + name + "_invalid")
    return result


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def bind_original_quotes(candidate, original_jsonl, *, freeze_at):
    """Return SHA-256 of exactly matched collector quote records.

    Require every evaluated book to originate from the same exact
    event/player/stat/line/side and offered price pair. Source possession is
    established independently by the signed archival receipt timeline.
    """
    if not isinstance(candidate, dict):
        raise ValueError("market_binding_candidate_invalid")
    parts = str(candidate.get("id") or "").split("|")
    if len(parts) != 4 or parts[3].strip().lower() not in ("over", "under"):
        raise ValueError("market_binding_player_identity_missing")
    sport, player, stat, side = (x.strip() for x in parts)
    if not player or not sport or not stat:
        raise ValueError("market_binding_player_identity_missing")
    if (sport != candidate.get("sport") or stat != candidate.get("stat")
            or side.lower() != str(candidate.get("side") or "").lower()):
        raise ValueError("market_binding_identity_mismatch")
    event = str(candidate.get("event_id") or "").strip()
    if not event:
        raise ValueError("market_binding_event_missing")
    line = _finite(candidate.get("line"), "line")
    books = candidate.get("books")
    if not isinstance(books, list) or not books:
        raise ValueError("market_binding_books_missing")
    freeze = _utc(freeze_at)
    origin = []
    for index, raw in enumerate(original_jsonl.splitlines(), 1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("market_original_jsonl_invalid:" + str(index)) from exc
        if not isinstance(item, dict):
            raise ValueError("market_original_quote_not_object")
        if (str(item.get("event_id") or "").strip() != event
                or str(item.get("sport") or "").strip() != sport
                or str(item.get("stat") or "").strip() != stat
                or normalize_player(item.get("player")) != normalize_player(player)
                or _finite(item.get("line"), "line") != line):
            continue
        if item.get("team") and candidate.get("team") and item["team"] != candidate["team"]:
            continue
        if _utc(item.get("retrieved_at")) > freeze:
            raise ValueError("market_original_quote_after_freeze")
        origin.append(item)
    if not origin:
        raise ValueError("market_original_offer_missing")
    verified = []
    used = set()
    for selected in books:
        if not isinstance(selected, dict) or selected.get("book_side") != side.lower():
            raise ValueError("market_book_side_mismatch")
        if _finite(selected.get("line"), "line") != line:
            raise ValueError("market_book_line_mismatch")
        book = str(selected.get("book") or "").strip()
        if not book or book in used:
            raise ValueError("market_book_duplicate_or_missing")
        used.add(book)
        matches = []
        for item in origin:
            if item.get("book") != book:
                continue
            a = item.get("over_odds") if side.lower() == "over" else item.get("under_odds")
            b = item.get("under_odds") if side.lower() == "over" else item.get("over_odds")
            if _finite(a, "price") == _finite(selected.get("target"), "price") and _finite(b, "price") == _finite(selected.get("other"), "price"):
                matches.append(item)
        if len(matches) != 1:
            raise ValueError("market_book_original_offer_mismatch_or_ambiguous")
        verified.append(matches[0])
    earliest = min(_utc(r["retrieved_at"]) for r in verified)
    if _utc(candidate.get("market_retrieved_at")) != earliest:
        raise ValueError("market_original_retrieval_clock_mismatch")
    # Canonical record digest is independent of JSON whitespace, order of
    # source rows and the Over/Under representation of the same original offer.
    normalized = sorted(verified, key=lambda q: (q["book"], q["retrieved_at"]))
    return hashlib.sha256(_canonical(normalized)).hexdigest()
