"""Verify the exact on-disk bytes referenced by V2.5 shadow records.

Without an explicitly supplied original archive root, a correctly shaped
SHA-256 string is just a claim, not a verified source receipt. This module
is deliberately NOT a publication or historical recertification authority.
"""
from __future__ import annotations

from pathlib import Path
import hashlib

from .contracts import ContractError


def _verify_path(root: Path, relative: str, expected_sha: str) -> None:
    if not isinstance(relative, str) or not relative.strip():
        raise ContractError("original_archive_path_missing")
    path = Path(relative)
    if path.is_absolute() or "\\" in relative or ".." in path.parts:
        raise ContractError("original_archive_path_unsafe")
    absolute_root = Path(root).resolve()
    target = (absolute_root / path).resolve()
    if not target.is_relative_to(absolute_root) or not target.is_file():
        raise ContractError("original_source_bytes_unavailable")
    h = hashlib.sha256()
    with target.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != expected_sha:
        raise ContractError("original_source_bytes_digest_mismatch")


def verify_original_source_bytes(quotes, forecasts, root: Path) -> dict:
    """Every quote and forecast source is verified or the entire proof fails.

    A synthetic research quote still needs a frozen source for proof of
    deterministic reconstruction, but cannot become a real offered market
    even with valid bytes.
    """
    n_quotes = 0
    n_receipts = 0
    for quote in quotes:
        _verify_path(root, quote.quote_archive_path, quote.quote_receipt_sha256)
        n_quotes += 1
    for forecast in forecasts:
        for receipt in forecast.sources:
            _verify_path(root, receipt.archive_path, receipt.content_sha256)
            n_receipts += 1
    return {"status": "original_bytes_verified_no_market_certification",
            "quote_files_checked": n_quotes, "forecast_source_files_checked": n_receipts}
