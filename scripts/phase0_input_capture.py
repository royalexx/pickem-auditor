"""Capture live forecast input bytes before forecast freeze; never backfill past slates.

These receipts prove collector-side possession and SHA-256 byte integrity.
They do not prove a provider's publication clock, independent data accuracy, or
the upstream availability of a source before its actual collection.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from usage_baseline import key as usage_key

MAX_INPUT_BYTES = 64_000_000
_STATIC_RECEIPTS = {}
SAFE_ID = re.compile(r"^[a-zA-Z0-9._-]+$")


def utc(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return result.astimezone(timezone.utc) if result.tzinfo else None


def stamp(when):
    return when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def source_url(value):
    """Drop credentials and query strings; never publish a provider API key."""
    if not isinstance(value, str):
        return None
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return None
    return urlunsplit(("https", parts.netloc, parts.path, "", ""))


def _safe_bytes(raw):
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("source_input_exceeds_capture_limit")
    secrets = [os.environ.get(name, "") for name in ("GITHUB_TOKEN", "PROPLINE_API_KEY")]
    if any(secret and secret.encode("utf-8") in raw for secret in secrets):
        raise ValueError("source_input_contains_secret")
    return raw


def preserve(root, component, role, raw, *, captured, retrieved, url=None):
    """Atomic content-addressed write, no modification of an existing snapshot."""
    # Shared research and market files are identical for many contracts.
    # The cached immutable byte object remains pinned by the file cache.
    cache_key = ((component, role, id(raw), retrieved.isoformat(), url)
                 if role in ("original_research", "original_book_quotes") else None)
    if cache_key is not None and cache_key in _STATIC_RECEIPTS:
        stored_receipt, stored_bytes = _STATIC_RECEIPTS[cache_key]
        if stored_bytes is raw:
            return dict(stored_receipt)
    raw = _safe_bytes(raw)
    if not raw:
        raise ValueError("empty_source_input")
    if not isinstance(captured, datetime) or captured.tzinfo is None:
        raise ValueError("capture_clock_unavailable")
    if not isinstance(retrieved, datetime) or retrieved.tzinfo is None:
        raise ValueError("retrieval_clock_unavailable")
    if retrieved > captured:
        raise ValueError("source_timestamp_after_capture")
    if not SAFE_ID.fullmatch(role):
        raise ValueError("invalid_archive_role")
    digest = hashlib.sha256(raw).hexdigest()
    rel = f"{role}/{digest}.bin"
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        pass
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError("existing_source_archive_mutated")
    receipt = {
        "source_id": f"{component}_{role}_{digest[:24]}",
        "model_component": component,
        "source_kind": "collector_input_bytes",
        "source_url": source_url(url),
        "source_url_status": "sanitized_url" if source_url(url) else "upstream_url_unknown",
        "clock_semantics": "collector_captured_no_publication_claim",
        "archive_path": rel,
        "content_sha256": digest,
        "observed_at": stamp(captured),
        "retrieved_at": stamp(retrieved),
        "status": "verified",
    }
    if cache_key is not None:
        _STATIC_RECEIPTS[cache_key] = (receipt, raw)
    return receipt


@lru_cache(maxsize=32)
def _read_json_version(path, mtime_ns, size):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("source_file_too_large")
    return raw, json.loads(raw)


def _read_json(path):
    path = Path(path)
    stat = path.stat()
    return _read_json_version(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def capture(candidate, result, *, data_root, archive_root, clock, identity=None):
    """Capture exact inputs actually available at evaluation, not postgame sources.

    Failure returns no certification rather than manufacturing a timestamp or
    changing the model's output. The original numerical forecast is untouched.
    """
    root = Path(data_root)
    archive = Path(archive_root)
    when = clock()
    if when.tzinfo is None:
        raise ValueError("naive_capture_time")
    when = when.astimezone(timezone.utc)
    receipts = []
    # Most NHL/NBA forecasting payloads intentionally omit the redundant
    # sport field. Use the pre-matched, original slate identity rather than
    # claiming it was included in the numerical engine inputs.
    identity = identity or {}
    sport = identity.get("sport") or candidate.get("sport")
    player_id = identity.get("player_id") or candidate.get("player_id")
    stat = identity.get("stat") or candidate.get("stat")
    game_date = identity.get("game_date") or candidate.get("game_date")
    candidate_id_sport = (str(candidate["id"]).split("|", 1)[0]
                          if candidate.get("id") else None)
    if (sport not in ("NBA", "NHL", "NFL") or not player_id or not stat
            or not game_date or
            (candidate_id_sport is not None and candidate_id_sport != sport) or
            any(candidate.get(k) not in (None, v) for k, v in
                (("sport", sport), ("player_id", player_id),
                 ("stat", stat), ("game_date", game_date)))):
        raise ValueError("original_slate_candidate_identity_mismatch")
    usage_ident = usage_key(sport, player_id, stat, game_date)
    usage_path = root / "usage" / (usage_ident + ".json")
    usage_bytes, usage_doc = _read_json(usage_path)
    retrieved = utc(usage_doc.get("retrieved_at"))
    if retrieved is None or retrieved > when:
        raise ValueError("usage_retrieved_timestamp_unavailable_or_future")
    # The existing opportunity loader already rejects current-day game stats.
    receipts.append(preserve(archive, "Engine_A", "historical_usage", usage_bytes,
                             captured=when, retrieved=retrieved,
                             url=usage_doc.get("source_url")))
    input_bytes = json.dumps(candidate, sort_keys=True, ensure_ascii=False,
                             allow_nan=False, separators=(",", ":")).encode("utf-8")
    receipts.append(preserve(archive, "Engine_A", "evaluated_candidate", input_bytes,
                             captured=when, retrieved=when))
    # A separate original research packet supports role/source auditing.
    engine_b = result.get("engine_b") or {}
    if not engine_b.get("abstain"):
        research_path = root / ("research_" + str(candidate["game_date"]) + ".json")
        research_bytes, _ = _read_json(research_path)
        receipts.append(preserve(archive, "Engine_B", "original_research", research_bytes,
                                 captured=when, retrieved=when))
        receipts.append(preserve(archive, "Engine_B", "evaluated_candidate", input_bytes,
                                 captured=when, retrieved=when))
    quote_bytes, _ = _read_jsonl(root / "odds_quotes.jsonl")
    receipts.append(preserve(archive, "Market", "original_book_quotes", quote_bytes,
                             captured=when, retrieved=when))
    market_bytes = json.dumps({"books": candidate.get("books"), "line": candidate.get("line"),
                              "side": candidate.get("side"), "market": result.get("market")},
                              sort_keys=True, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8")
    receipts.append(preserve(archive, "Market", "evaluated_market", market_bytes,
                             captured=when, retrieved=when))
    # This is the time the latest historical input was retrieved, not a claim
    # about the time that a hierarchical NUTS model was trained.
    return {
        # Engine A is fitted on demand, rather than loaded from an opaque
        # pretrained artifact. This is the effective calculation/data freeze
        # time; historical source retrieval has a separately recorded clock.
        "model_training_cutoff_at": stamp(when),
        "model_training_cutoff_basis": "on_demand_engine_a_input_freeze",
        "historical_usage_retrieved_at": stamp(retrieved),
        "source_receipts": receipts,
        "used_source_ids": [entry["source_id"] for entry in receipts],
        "source_capture_at": stamp(when),
        "source_capture_scope": "actual_collected_inputs_not_provider_publication_truth",
    }


@lru_cache(maxsize=8)
def _read_jsonl_version(path, mtime_ns, size):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("source_file_too_large")
    if not raw.strip():
        raise ValueError("source_book_quotes_missing")
    return raw, None


def _read_jsonl(path):
    path = Path(path)
    stat = path.stat()
    return _read_jsonl_version(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
