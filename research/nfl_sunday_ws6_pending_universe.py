#!/usr/bin/env python3
"""WS6 immutable original-observation comparison skeleton.

Records ALL WS1 quotes including rejected, uncertified, duplicate and unresolved
identities; never calls them comparable original player contracts until receipts
and contract identity pass. Does not run models, score, collect, or infer odds.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from pathlib import Path
import argparse
import json

LEGACY = ("Engine_A", "Engine_B", "Bayesian_A", "Bayesian_B", "NUTS_strict",
          "Consensus_60_40", "Market")
RESEARCH = ("WS2", "WS3", "WS4", "WS5")


def emit(path, rows):
    with Path(path).open("x", encoding="utf8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False) + "\n")


def build(source_file, output_folder):
    from nfl_sunday_ws6_audit import file_sha, fail, load_json, dump
    src = Path(source_file)
    output = Path(output_folder)
    if output.exists():
        fail("RESEARCH_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    raw_sha = file_sha(src)
    data = load_json(src)
    if data.get("schema") != "nfl_20261115_source_control_v1" or data.get("date") != "2026-11-15":
        fail("UNRECOGNIZED_OR_WRONG_SUNDAY_SOURCE")
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        fail("ORIGINAL_CANDIDATES_MISSING")
    if len(candidates) != data.get("quote_observations"):
        fail("QUOTED_DENOMINATOR_MISMATCH")
    if len({r.get("candidate_id") for r in candidates}) != data.get("unique_candidate_ids"):
        fail("ORIGINAL_CANDIDATE_ID_COUNT_MISMATCH")
    if len(candidates) != data.get("attempted_contracts"):
        fail("ATTEMPTED_CONTRACT_COUNT_MISMATCH")
    ids = Counter(c.get("candidate_id") for c in candidates)
    rows = []
    for index, c in enumerate(candidates):
        q = c.get("original_quote")
        if not isinstance(q, dict):
            fail("ORIGINAL_OFFER_MISSING_ROW:" + str(index))
        labels = [c.get("source_validation_failure"),
                  None if c.get("availability_certified") is True else "ORIGINAL_AVAILABILITY_NOT_CERTIFIED",
                  None if c.get("forecast_eligible") is True else "ORIGINAL_FORECAST_NOT_ELIGIBLE",
                  None if c.get("player_id") else "PLAYER_IDENTITY_NOT_CERTIFIED",
                  None if c.get("event_id") else "EVENT_IDENTITY_NOT_CERTIFIED",
                  None if c.get("settlement_semantics") == "strict_gt_lt_equal_push" else "PRODUCT_RULES_UNVERIFIED",
                  "DUPLICATE_CANDIDATE_ID" if ids.get(c.get("candidate_id"), 0) > 1 else None]
        reasons = sorted({str(s) for s in labels if s})
        rows.append({
            "original_observation_ordinal": index,
            "original_ws1_manifest_file_sha256": raw_sha,
            "candidate_id": c.get("candidate_id"),
            "original_source_quote_id": c.get("quote_id"),
            "provider_event_id": c.get("provider_event_id"),
            "espn_event_id": c.get("event_id"),
            "espn_player_id": c.get("player_id"),
            "player_display_name": c.get("player"),
            "team": c.get("team"), "opponent": c.get("opponent"),
            "stat_key": c.get("stat"), "period": c.get("period"),
            "line": c.get("line"), "book": c.get("book"),
            "event_start_at": c.get("event_start_at"),
            "quote_first_collector_received_at": c.get("source_received_at"),
            "freeze_at": c.get("input_freeze_at"),
            "original_provider_source_sha256": c.get("source_sha256"),
            "original_provider_source_path": c.get("source_archive_path"),
            "original_provider_quote": q,
            "ws1_source_certified": c.get("source_certified") is True,
            "ws1_forecast_eligible": c.get("forecast_eligible") is True,
            "eligibility": c.get("eligibility_status"),
            "control_probabilities": {k: None for k in LEGACY},
            "research_probabilities": {k: None for k in RESEARCH},
            "market_no_vig": None,
            "selected_side": None, "tier": None, "actual_stat": None,
            "settlement": "NOT_STARTED_PREGAME",
            "integrity_reasons": reasons,
            "classification": "ORIGINAL_CAPTURE_SHADOW_NOT_CERTIFIED",
        })
    output.mkdir(parents=True, exist_ok=False)
    target = output / "attempted_universe_comparison.jsonl"
    emit(target, rows)
    index = {
        "schema": "ws6_original_attempted_universe_v1",
        "status": "SOURCE_REJECTED_SHADOW_ONLY",
        "slate_date": "2026-11-15",
        "source_original_raw_sha256": raw_sha,
        "original_quote_observations": len(candidates),
        "distinct_candidate_ids": len(ids),
        "duplicate_excess_observations": len(candidates) - len(ids),
        "source_certified_by_ws1": sum(c.get("source_certified") is True for c in candidates),
        "forecast_eligible_by_ws1": sum(c.get("forecast_eligible") is True for c in candidates),
        "original_market_or_model_probabilities": "NOT_POPULATED_OR_BACKFILLED",
        "original_observation_ledger_sha256": file_sha(target),
        "original_source_overwritten": False,
        "tier_promotion": False,
    }
    dump(output / "attempted_universe_index.json", index)
    print(json.dumps(index, sort_keys=True))
    return index


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    try:
        build(args.source, args.output)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as e:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(e)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
