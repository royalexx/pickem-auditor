"""Phase 0R: pin actual pre-evaluation model inputs in an isolated immutable copy.

This module does not infer missing provider publication clocks and does not
certify research runs after their games have begun.  It copies bytes out of a
content-addressed archive, and the numerical evaluator is given ONLY the
frozen candidate and the frozen data/policy root.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from phase0_input_capture import preserve, utc, stamp
from phase0_market_quote_binding import (
    MARKET_QUOTE_ARCHIVE_V1,
    MARKET_QUOTE_ARCHIVE_V1_1,
    detect_market_quote_archive_version,
)
from usage_baseline import key as usage_key

SCHEMA = "pickem_pre_eval_input_binding_v1"
ORIGINAL_QUOTE_ARCHIVE_NOTE = (
    "structured_pre_resolution_quote_records_not_raw_http_bytes"
)


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def _instant(clock):
    now = clock()
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("pre_eval_naive_clock")
    return now.astimezone(timezone.utc)


@contextmanager
def pin(candidate, *, data_root, archive_root, policy_root, clock, identity=None):
    """Pre-stage all declared numerical inputs before calling the model.

    The temporary filesystem is private to one evaluation. Source byte digests
    are verified against immutable archives before materializing its files.
    Any source that cannot be pinned makes the prediction research-only.
    """
    root = Path(data_root)
    archive = Path(archive_root)
    config_root = Path(policy_root)
    identity = identity or {}
    sport = identity.get("sport") or candidate.get("sport")
    player_id = identity.get("player_id") or candidate.get("player_id")
    stat = identity.get("stat") or candidate.get("stat")
    day = identity.get("game_date") or candidate.get("game_date")
    if (sport not in ("NFL", "NBA", "NHL") or not player_id or not stat or not day
            or (candidate.get("id") and
                str(candidate["id"]).split("|", 1)[0] != sport)
            or any(candidate.get(key) not in (None, expected)
                   for key, expected in (("sport", sport), ("player_id", player_id),
                                         ("stat", stat), ("game_date", day)))):
        raise ValueError("pre_eval_identity_mismatch")

    started = _instant(clock)
    receipts = []
    frozen_files = {}
    with tempfile.TemporaryDirectory(prefix="pickem_phase0r_frozen_") as directory:
        frozen = Path(directory)

        def ingest(component, role, raw, relative=None, retrieved=None, url=None):
            # All receipt timestamps are finalized at the end of this capture.
            receipt = preserve(archive, component, role, raw, captured=started,
                               retrieved=retrieved or started, url=url)
            receipts.append(receipt)
            if relative is not None:
                path = frozen / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                frozen_bytes = (archive / receipt["archive_path"]).read_bytes()
                if hashlib.sha256(frozen_bytes).hexdigest() != receipt["content_sha256"]:
                    raise ValueError("pinned_source_digest_mismatch")
                path.write_bytes(frozen_bytes)
                frozen_files[relative] = receipt["source_id"]
            return receipt

        candidate_raw = canonical_bytes(candidate)
        ingest("Engine_A", "evaluated_candidate", candidate_raw,
               relative="model_input_candidate.json")
        # B consumes the same prepared candidate's scouting and read metadata.
        ingest("Engine_B", "evaluated_candidate", candidate_raw)
        # Verify the evaluator will deserialize the exact frozen input bytes.
        frozen_candidate = json.loads((frozen / "model_input_candidate.json").read_bytes())
        if canonical_bytes(frozen_candidate) != candidate_raw:
            raise ValueError("frozen_candidate_roundtrip_mismatch")

        ident = usage_key(sport, player_id, stat, day)
        usage_path = root / "usage" / (ident + ".json")
        usage_raw = usage_path.read_bytes()
        usage_doc = json.loads(usage_raw)
        retrieved = utc(usage_doc.get("retrieved_at"))
        if retrieved is None or retrieved > started:
            raise ValueError("usage_retrieved_timestamp_unavailable_or_future")
        ingest("Engine_A", "historical_usage", usage_raw,
               relative="usage/" + ident + ".json", retrieved=retrieved,
               url=usage_doc.get("source_url"))

        # Archive pre-resolution structured quote records under the strict
        # original_book_quotes role expected by phase0r_contract.
        original_quotes = root / "odds_quotes_original.jsonl"
        resolved_quotes = root / "odds_quotes.jsonl"
        split_archive = original_quotes.is_file() and resolved_quotes.is_file()
        if split_archive:
            odds_raw = original_quotes.read_bytes()
            if not odds_raw.strip():
                raise ValueError("original_book_quotes_missing")
            ingest("Market", "original_book_quotes", odds_raw,
                   relative="odds_quotes_original.jsonl")
            derived_raw = resolved_quotes.read_bytes()
            if not derived_raw.strip():
                raise ValueError("collector_resolved_book_quotes_missing")
            if derived_raw == odds_raw:
                raise ValueError("collector_resolved_quotes_must_differ_from_original")
            ingest("Market", "collector_resolved_book_quotes", derived_raw,
                   relative="odds_quotes.jsonl")
        else:
            odds_raw = resolved_quotes.read_bytes()
            if not odds_raw.strip():
                raise ValueError("original_book_quotes_missing")
            ingest("Market", "original_book_quotes", odds_raw,
                   relative="odds_quotes.jsonl")
        market_input = {k: candidate.get(k) for k in
                        ("books", "line", "side", "market_retrieved_at")}
        ingest("Market", "evaluated_market", canonical_bytes(market_input),
               relative="market_input.json")

        research = root / ("research_" + str(day) + ".json")
        if research.is_file():
            # The merged candidate is what B actually consumes; the original
            # research packet is archived for provenance, not loaded by the
            # numerical evaluator. Avoid cloning a multi-MB research file
            # for every Over/Under candidate.
            from phase0_input_capture import _read_json
            research_bytes, _ = _read_json(research)
            ingest("Engine_B", "original_research", research_bytes)
        # A declared policy must never silently fall back to the one in the
        # mutable repository while a prediction is being computed.
        policy = config_root / "config" / "production_consensus.json"
        if policy.is_file():
            ingest("Engine_A", "production_policy", policy.read_bytes(),
                   relative="config/production_consensus.json")

        # The usage and context operators may read these supplemental paths.
        # If a present input is too large to archive, fail closed rather than
        # scoring against a mutable original file.
        if sport == "NFL":
            season = started.year - (started.month < 3)
            season_file = root / "season" / ("nfl_" + str(season) + ".sqlite3")
            if season_file.is_file():
                ingest("Engine_A", "season_context_db", season_file.read_bytes(),
                       relative="season/" + season_file.name)
        team = candidate.get("team")
        if team:
            from shared_context import history_path
            from usage_baseline import using_directory
            with using_directory(frozen):
                original_relative = "lineups/" + history_path(sport, team, stat).name
            historical = root / original_relative
            if historical.is_file():
                ingest("Engine_B", "lineup_history", historical.read_bytes(),
                       relative=original_relative)

        completed = _instant(clock)
        if completed < started:
            raise ValueError("nonmonotonic_pre_eval_capture_clock")
        # No receipt may claim that collector-owned files were possessed
        # before all of their immutable bytes had actually been archived.
        for receipt in receipts:
            receipt["observed_at"] = stamp(completed)
            if receipt["archive_path"].split("/", 1)[0] != "historical_usage":
                receipt["retrieved_at"] = stamp(completed)

        binding = {
            "schema": SCHEMA,
            "method": "pre_evaluation_archived_copy",
            "candidate_sha256": hashlib.sha256(candidate_raw).hexdigest(),
            "input_files": frozen_files,
            "source_receipt_ids": [r["source_id"] for r in receipts],
            "evaluates_frozen_candidate": True,
            "uses_isolated_data_directory": True,
            "uses_isolated_production_policy": True,
            "external_context_unpinned": bool(candidate.get("event_context")),
            "source_publication_truth_verified": False,
            "market_quote_archive_version": (
                MARKET_QUOTE_ARCHIVE_V1_1 if split_archive else MARKET_QUOTE_ARCHIVE_V1
            ),
            "original_quote_archive_semantics": ORIGINAL_QUOTE_ARCHIVE_NOTE,
        }
        detected = detect_market_quote_archive_version(frozen_files)
        if detected != binding["market_quote_archive_version"]:
            raise ValueError("market_quote_archive_binding_inconsistent")
        evidence = {
            "input_freeze_at": stamp(completed),
            "source_capture_at": stamp(completed),
            "input_freeze_basis": "pre_evaluation_immutable_clone",
            "source_capture_scope": "collector_possession_not_provider_publication",
            "model_training_cutoff_at": stamp(completed),
            "model_training_cutoff_basis": "on_demand_model_data_cutoff",
            "model_input_binding": binding,
            "source_receipts": receipts,
            "used_source_ids": [r["source_id"] for r in receipts],
            "historical_usage_retrieved_at": stamp(retrieved),
        }
        yield evidence, frozen, frozen_candidate
