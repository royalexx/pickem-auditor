"""P2 adapter from independently signed provider HTTPS bodies to P0 MarketQuote.

Never constructs odds or player/provider crosswalks. The exact raw source
and HMAC proof are independently read before P0 quote admission.
"""
from __future__ import annotations
from datetime import timedelta

from v2.p0_integrity.contracts import VERSION, canonical_bytes, utc, validate_record
from v2.p0_integrity.storage import append_immutable, verify_immutable_record
from .source_pipeline import (SourceBlocked, require, digest, stamp, clock,
                              current_storage, quote_from_archived_raw, attempt)
from .market_capture import verify_original_provider


def _source_record(original):
    collected = stamp(clock(original["received_at"]))
    return {
        "record_type": "SourceReceipt", "schema_version": VERSION,
        "receipt_id": "p2market:" + digest(canonical_bytes([
            original["source_url"], original["sha256"], collected])),
        "source_id": "nhl_sog_real_provider:" + original["sha256"],
        "source_kind": "original_sportsbook_http_response",
        "source_available_at": collected, "collected_at": collected,
        "source_sha256": original["sha256"],
        "archive_path": original["archive_path"],
        "provenance_class": "collector_possession"
    }


def verified_real_quote(root, *, raw_ref, offered, player_id, team,
                        opponent, event_id, start, freeze,
                        official_profile_entry, history_pool):
    """Validate the exact two-sided rows and write P0 receipts once."""
    current_storage(root)
    verify_original_provider(root, raw_ref, freeze=freeze, event_start=start)
    from .history_bridge import signed_original_profile_name, checked_pool
    verified_pool = checked_pool(root, history_pool)
    require(isinstance(official_profile_entry, dict),
            "SIGNED_OFFICIAL_PROFILE_REQUIRED_FOR_REAL_QUOTE")
    name = signed_original_profile_name(
        verified_pool, official_profile_entry, freeze=freeze,
        event_start=start)
    item = quote_from_archived_raw(
        root, raw_ref, offered, player_id=player_id, team=team,
        opponent=opponent, event_id=event_id, start=start, freeze=freeze,
        official_name=name)
    source = _source_record(raw_ref)
    validate_record("SourceReceipt", source)
    stored_source = append_immutable(root, "SourceReceipt", source)
    quote = {
        "record_type": "MarketQuote", "schema_version": VERSION,
        "quote_id": item["quote_id"],
        "contract_id": "p2contract:" + digest(canonical_bytes([
            item["event_id"], item["player_id"], item["period"], item["book"],
            item["line"], item["over_american"], item["under_american"],
            item["quote_timestamp"]])),
        "event_id": item["event_id"], "sport": "NHL",
        "team_id": item["team_id"], "opponent_id": item["opponent_id"],
        "player_id": item["player_id"], "stat_key": "shots on goal",
        "period": "full", "quote_timestamp": item["quote_timestamp"],
        "event_start_at": start, "book": item["book"],
        "product_type": item["product_type"], "quote_kind": "real",
        "line": item["line"], "side": "paired",
        "source_receipt_id": source["receipt_id"],
        "source_sha256": source["source_sha256"],
        "terms": {
            "over_american": item["over_american"],
            "under_american": item["under_american"],
            "provider_event_id": item["provider_event_id"],
            "provider_player_id": item["provider_player_id"],
            "provider_player_name": item["provider_player_name"],
            "crosswalk_source_sha256": item["crosswalk_source_sha256"],
            "structured_row_sha256": item["structured_row_sha256"],
            "source_hmac_proof_sha256": raw_ref["proof_sha256"],
            "official_name_source_proof_sha256":
                official_profile_entry["raw_profile_receipt"]["collector_proof_sha256"],
            "origin": "original_collector_possession",
            "publisher_publication_time_verified": False
        },
        "accepted": True, "reject_reason": None
    }
    validate_record("MarketQuote", quote)
    stored_quote = append_immutable(root, "MarketQuote", quote)
    return {
        "verified_quote": item, "p0_quote_record": quote,
        "p0_quote_sha256": stored_quote["sha256"],
        "p0_source_record": source,
        "p0_source_sha256": stored_source["sha256"],
        "provider_original_capture": raw_ref,
        "official_profile_entry": official_profile_entry,
        "history_pool": str(verified_pool.relative_to(__import__("pathlib").Path(root).resolve())),
        "source_status": "REAL_TWO_SIDED_VERIFIED_COLLECTOR_POSSESSION"
    }


def verify_real_quote(root, evidence, *, freeze, event_start):
    """P4/P5 callable read; reject a quote if its raw evidence mutated."""
    current_storage(root)
    require(isinstance(evidence, dict), "P0_QUOTE_EVIDENCE_REQUIRED")
    source = verify_immutable_record(root, "SourceReceipt",
                                     evidence["p0_source_sha256"])
    quote = verify_immutable_record(root, "MarketQuote",
                                    evidence["p0_quote_sha256"])
    require(quote["quote_kind"] == "real" and
            quote["product_type"] == "sportsbook_two_sided" and
            quote["stat_key"] == "shots on goal" and
            quote["period"] == "full" and
            quote["source_receipt_id"] == source["receipt_id"] and
            quote["source_sha256"] == source["source_sha256"],
            "ORIGINAL_QUOTE_P0_SOURCE_IDENTITY_MISMATCH")
    require(clock(quote["quote_timestamp"]) <= clock(freeze) <
            clock(event_start) and
            quote["event_start_at"] == event_start,
            "QUOTE_SOURCE_AFTER_INPUT_FREEZE")
    original = evidence["provider_original_capture"]
    require(original["sha256"] == source["source_sha256"],
            "ORIGINAL_PROVIDER_P0_HASH_MISMATCH")
    verify_original_provider(root, original, freeze=freeze, event_start=event_start)
    from .history_bridge import checked_pool, signed_original_profile_name
    checked_history_pool = checked_pool(root, __import__("pathlib").Path(root) /
                                       evidence["history_pool"])
    source_name = signed_original_profile_name(
        checked_history_pool, evidence["official_profile_entry"],
        freeze=freeze, event_start=event_start)
    require(quote["terms"]["official_name_source_proof_sha256"] ==
            evidence["official_profile_entry"]["raw_profile_receipt"]["collector_proof_sha256"],
            "ORIGINAL_OFFICIAL_NAME_SOURCE_PROOF_CHANGED")
    checked = quote_from_archived_raw(
        root, original,
        {
          "provider_event_id": quote["terms"]["provider_event_id"],
          "provider_player_id": quote["terms"]["provider_player_id"],
          "provider_player_name": source_name,
          "official_event_id": quote["event_id"],
          "native_nhl_player_id": quote["player_id"],
          "team": quote["team_id"], "opponent": quote["opponent_id"],
          "stat": "player_shots_on_goal", "period": "full",
          "product_type": quote["product_type"], "line": quote["line"],
          "book": quote["book"],
          "over_odds": quote["terms"]["over_american"],
          "under_odds": quote["terms"]["under_american"],
          "crosswalk_source_sha256": quote["terms"]["crosswalk_source_sha256"]
        },
        player_id=quote["player_id"], team=quote["team_id"],
        opponent=quote["opponent_id"], event_id=quote["event_id"],
        start=event_start, freeze=freeze, official_name=source_name)
    require(checked["quote_id"] == quote["quote_id"] and
            checked["structured_row_sha256"] ==
            quote["terms"]["structured_row_sha256"],
            "REVERIFIED_QUOTE_DRIFT")
    return quote


def record_quote_candidate(root, *, raw_ref, offered, player_id, team,
                           opponent, event_id, start, freeze,
                           official_profile_entry, history_pool):
    """Include every rejected offer and failure reason, never invent odds."""
    try:
        original = verified_real_quote(
            root, raw_ref=raw_ref, offered=offered, player_id=player_id,
            team=team, opponent=opponent, event_id=event_id, start=start,
            freeze=freeze, official_profile_entry=official_profile_entry,
            history_pool=history_pool)
    except Exception as exc:
        rejection = attempt(
            root, "market_quote", "REJECTED",
            [type(exc).__name__ + ":" + str(exc)[:150]],
            player_id=str(player_id), event_id=str(event_id),
            raw_sha256=raw_ref.get("sha256") if isinstance(raw_ref,dict) else None,
            offered_row_sha256=digest(canonical_bytes(offered))
                if isinstance(offered,dict) else None)
        return {"status": "REJECTED", "attempt": rejection}
    receipt = attempt(
        root, "market_quote", "VERIFIED", [],
        player_id=str(player_id), event_id=str(event_id),
        quote_sha256=original["p0_quote_sha256"])
    return {"status": "VERIFIED", "quote": original, "attempt": receipt}
