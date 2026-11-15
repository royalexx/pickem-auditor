#!/usr/bin/env python3
"""Read-only WS1 -> WS6 evidence adapter; never upgrades WS1 uncertified facts.

Input: exact WS1 source_control/captures/<sha>.json immutable source universe.
Output: new derived audit manifest, original-quote ledger and unmodified-candidate
reference ledger. No network collection, forecast generation or new timestamps.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from nfl_sunday_ws6_audit import checked_source, dump, dump_lines, file_sha, instant, fail

WS1 = "nfl_20261115_source_control_v1"
TARGET = "nfl_sunday_ws1_original_v1"
SCHEDULE = (
    ("NE", "DET", "09:30"), ("KC", "ATL", "13:00"),
    ("HOU", "CLE", "13:00"), ("MIN", "GB", "13:00"),
    ("MIA", "IND", "13:00"), ("CAR", "NO", "13:00"),
    ("BUF", "NYJ", "13:00"), ("JAX", "TEN", "13:00"),
    ("LAR", "ARI", "16:05"), ("SEA", "LV", "16:05"),
    ("SF", "DAL", "16:25"), ("PIT", "CIN", "20:20"),
)
VALID_ROLES = {"EXPECTED_STARTER_SOURCE_BACKED", "ROSTER_MEMBER_GAME_ACTIVE_UNCONFIRMED"}


def convert(root, ws1_file, output):
    root, ws1_file, output = Path(root), Path(ws1_file), Path(output)
    if output.exists():
        fail("DERIVED_OUTPUT_ALREADY_EXISTS")
    original_sha = file_sha(ws1_file)
    original = json.loads(ws1_file.read_text(encoding="utf8"))
    if original.get("schema") != WS1 or original.get("date") != "2026-11-15":
        fail("UNRECOGNIZED_WS1_SOURCE_SCHEMA")
    if original.get("handoff", {}).get("no_original_source_recapture") is not True:
        fail("WS1_SOURCE_OWNERSHIP_NOT_LOCKED")
    events = original.get("events") or []
    if len(events) != 12:
        fail("NOT_FULL_12_GAME_SCHEDULE")
    actual_pairs = {(e.get("away"), e.get("home")) for e in events}
    if actual_pairs != {(a, h) for a, h, _ in SCHEDULE}:
        fail("WS1_SCHEDULE_DIFFERS_FROM_OFFICIAL_12_GAMES")
    schedule = []
    for e in events:
        for away, home, hhmm in SCHEDULE:
            if (e["away"], e["home"]) == (away, home):
                hh = hhmm
                break
        if not e.get("schedule_verified") or not e.get("espn_event_id"):
            # Do not fabricate an ID or promote an uncertified fixture.
            schedule.append({"event_id": e.get("espn_event_id") or
                             "WS1_UNVERIFIED_FIXTURE:" + e["fixture_key"],
                             "start_at": e.get("scheduled_kickoff"),
                             "home_id": e["home"], "away_id": e["away"],
                             "official_identity_verified": False})
            continue
        if not e.get("source_sha256"):
            fail("WS1_SCHEDULE_SOURCE_HASH_MISSING")
        schedule.append({"event_id": str(e["espn_event_id"]),
                         "start_at": e["scheduled_kickoff"],
                         "home_id": e["home"], "away_id": e["away"],
                         "official_identity_verified": True})
    receipts = original.get("sources") or {}
    evidence = []
    for source_id, receipt in sorted(receipts.items()):
        reason = None
        try:
            checked_source(root, receipt.get("archive_path"), receipt.get("sha256"))
            if receipt.get("source_bytes_verified") is not True:
                fail("WS1_REPORTED_UNVERIFIED_BYTES")
            instant(receipt.get("source_received_at"), "source_received_at")
        except Exception as exc:
            reason = str(exc)
        evidence.append({"source_id": source_id, "path": receipt.get("archive_path"),
                         "sha256": receipt.get("sha256"),
                         "observed_at": receipt.get("source_received_at"),
                         "publication_truth_verified": receipt.get("source_publication_truth_verified") is True,
                         "integrity_status": "HASH_CHECK_PASS" if reason is None else "REJECTED",
                         "reason": reason})
    if not receipts:
        fail("WS1_SOURCE_RECEIPTS_MISSING")
    source_by_id = {r["source_id"]: r for r in evidence}
    quotes = []
    candidates = original.get("candidates", [])
    for c in candidates:
        ident = str(c.get("candidate_id") or "")
        product = c.get("original_quote") or {}
        source = receipts.get("propline") or {}
        code = c.get("source_validation_failure")
        status = str(c.get("eligibility_status") or "")
        valid_receipt = (source_by_id.get("propline", {}).get("integrity_status") == "HASH_CHECK_PASS")
        # Original source quote presence is not equivalent to compatible
        # settlement terms, live availability, confirmed player participation
        # or independent provider publication-time attestation.
        settlement_verified = c.get("settlement_semantics") == "strict_gt_lt_equal_push"
        source_valid = c.get("source_certified") is True and not code
        availability_valid = c.get("availability_certified") is True
        role_valid = status in VALID_ROLES
        accepted = bool(valid_receipt and source_valid and availability_valid
                        and settlement_verified and role_valid)
        reasons = ([str(code)] if code else [])
        if not valid_receipt:
            reasons.append("WS1_SOURCE_RECEIPT_UNVERIFIED")
        if not availability_valid:
            reasons.append("AVAILABILITY_NOT_CERTIFIED_BY_WS1")
        if not settlement_verified:
            reasons.append("PRODUCT_SETTLEMENT_TERMS_UNVERIFIED")
        if not role_valid:
            reasons.append("PLAYER_ELIGIBILITY_NOT_ESTABLISHED:" + status)
        observed = c.get("source_received_at")
        quote = {
            "schema": TARGET, "quote_id": c.get("quote_id"),
            "contract_id": ident, "candidate_id": ident,
            "event_id": c.get("event_id"), "event_start_at": c.get("event_start_at"),
            "player_id": c.get("player_id"), "player_name": c.get("player"),
            "stat_key": c.get("stat"), "period": c.get("period"),
            "line": c.get("line"), "book": c.get("book"),
            "product_type": "original_provider_offer_terms_unverified",
            "quote_kind": "real", "accepted": accepted,
            "reject_reason": "|".join(reasons) if reasons else None,
            "settlement_policy": ("strict_gt_lt_equal_push" if settlement_verified else
                                  "unverified_product_policy"),
            "source_available_at": observed, "captured_at": observed,
            "quote_at": observed, "source_kind": "archive_possession",
            "source_archive_path": c.get("source_archive_path"),
            "source_sha256": c.get("source_sha256"),
            "player_eligible_pregame": role_valid,
            "role_source_label": status,
            "ws1_source_certified": source_valid,
            "ws1_availability_certified": availability_valid,
            "raw_original_odds": {"over": product.get("over_odds"),
                                  "under": product.get("under_odds"),
                                  "format": "UNVERIFIED"},
            "ws1_candidate_code_sha": c.get("code_commit_sha"),
            "source_publication_truth_verified": False,
        }
        quotes.append(quote)
    # WS1 attempted universe may include rejected quotes: retain all verbatim
    # candidate rows and their immutable original record SHA separately.
    output.mkdir(parents=True, exist_ok=False)
    dump_lines(output / "ws1_original_candidates.jsonl", candidates)
    dump_lines(output / "source_receipts_independent_review.jsonl", evidence)
    dump_lines(output / "derived_original_quotes.jsonl", quotes)
    expected = sum(c["accepted"] for c in quotes)
    derived = {
        "schema": TARGET, "slate_date": "2026-11-15",
        "schedule_complete": len(schedule) == 12 and all(
            e["official_identity_verified"] for e in schedule),
        "events": [{k: x[k] for k in ("event_id", "start_at", "home_id", "away_id")}
                   for x in schedule],
        "expected_contract_count": expected, "expected_models": [],
        "quotes_sha256": file_sha(output / "derived_original_quotes.jsonl"),
        "original_ws1_sha256": original_sha,
        "original_ws1_manifest_path": str(ws1_file),
        "adapter_prohibits_certification": True,
        "captured_attempted_contracts": len(candidates),
        "source_certified_by_ws1": original.get("source_certified_quotes"),
        "forecast_eligible_by_ws1": original.get("forecast_eligible_contracts"),
    }
    dump(output / "derived_source_manifest.json", derived)
    report = {
        "adapter": "WS1_SOURCE_NATIVE_READ_ONLY_V1",
        "source_owner": "WS1", "source_contract_sha256": original_sha,
        "derived_manifest_sha256": file_sha(output / "derived_source_manifest.json"),
        "derived_quote_file_sha256": derived["quotes_sha256"],
        "candidate_count": len(candidates),
        "source_quote_observations": original.get("quote_observations"),
        "ws1_reported_source_certified_quotes": original.get("source_certified_quotes"),
        "ws1_reported_forecast_eligible": original.get("forecast_eligible_contracts"),
        "derived_accepted_contracts": expected,
        "rejection_reasons": dict(Counter(
            r for q in quotes if not q["accepted"] for r in
            (q["reject_reason"] or "UNSPECIFIED").split("|"))),
        "source_receipts_total": len(evidence),
        "source_receipt_hash_pass": sum(x["integrity_status"] == "HASH_CHECK_PASS" for x in evidence),
        "schedule_identity_verified": derived["schedule_complete"],
        "original_market_probability": "UNAVAILABLE_WHILE_PRICE_FORMAT_UNVERIFIED",
        "external_certification": "NOT_PERFORMED", "model_promotion": "PROHIBITED",
    }
    dump(output / "ws1_adapter_integrity_report.json", report)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["schedule_identity_verified"] and expected > 0 else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", required=True, help="Original WS1 archive storage root")
    ap.add_argument("--ws1-file", required=True, help="Original WS1 frozen manifest file")
    ap.add_argument("--output", required=True, help="New derived folder; never overwrite")
    args = ap.parse_args(argv)
    try:
        return convert(args.root, args.ws1_file, args.output)
    except Exception as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
