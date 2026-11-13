"""Versioned Market quote archive bindings for Phase 0R strict certification.

``original_book_quotes`` always means the pre-collector-resolution structured
quote records (parsed API fields), not byte-identical upstream HTTP responses
unless those bytes were explicitly captured elsewhere.
"""
from __future__ import annotations

MARKET_QUOTE_ARCHIVE_V1 = "pickem_market_quote_archive_v1"
MARKET_QUOTE_ARCHIVE_V1_1 = "pickem_market_quote_archive_v1_1"


def detect_market_quote_archive_version(input_files: dict) -> str:
    files = input_files or {}
    if "odds_quotes_original.jsonl" in files:
        return MARKET_QUOTE_ARCHIVE_V1_1
    if "odds_quotes.jsonl" in files:
        return MARKET_QUOTE_ARCHIVE_V1
    return ""


def original_quote_frozen_path(input_files: dict) -> str | None:
    files = input_files or {}
    if "odds_quotes_original.jsonl" in files:
        return "odds_quotes_original.jsonl"
    if "odds_quotes.jsonl" in files:
        return "odds_quotes.jsonl"
    return None


def verify_market_quote_file_bindings(binding: dict, by_role: dict) -> str | None:
    """Return a fail-closed reason, or None when bindings are consistent."""
    files = binding.get("input_files")
    if not isinstance(files, dict):
        return "frozen_input_file_map_missing"
    original = by_role.get(("Market", "original_book_quotes"))
    if original is None:
        return "pre_eval_required_source_role_missing"
    version = binding.get("market_quote_archive_version") or detect_market_quote_archive_version(files)
    if not version:
        return "frozen_original_quote_path_missing"
    if version != binding.get("market_quote_archive_version"):
        return "market_quote_archive_version_mismatch"
    path = original_quote_frozen_path(files)
    if path is None:
        return "frozen_original_quote_path_missing"
    if files.get(path) != original.get("source_id"):
        return "frozen_original_quotes_file_unbound"
    if version == MARKET_QUOTE_ARCHIVE_V1_1:
        resolved = by_role.get(("Market", "collector_resolved_book_quotes"))
        if resolved is None:
            return "collector_resolved_quote_receipt_missing"
        if files.get("odds_quotes.jsonl") != resolved.get("source_id"):
            return "frozen_resolved_quotes_file_unbound"
        if files.get("odds_quotes_original.jsonl") == files.get("odds_quotes.jsonl"):
            return "resolved_quotes_alias_original_quotes"
    elif "odds_quotes_original.jsonl" in files:
        return "split_quote_paths_without_v1_1_binding"
    return None
