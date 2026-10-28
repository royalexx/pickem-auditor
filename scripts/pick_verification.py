#!/usr/bin/env python3
"""Evidence-gated, append-only verification of pregame shadow forecasts.

Never revises the source forecast. A reviewed decision is a new, timestamped
record bound to the exact forecast content and an independently checked market.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pickem_math as pm
import research_packet as rp
from research_triage import latest_batch, utc_time, probability, packet_game_key

TIERS = {"Tier 1", "Tier 2", "Tier 3"}
ACTIVE_REPORTS = {"game_day_report", "final_active_roster"}
RECHECK_MIN = 25
RECHECK_MAX = 55


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


SETTLEMENT_FIELDS = frozenset(("actual_stat", "outcome", "settled_at"))


def forecast_digest(row):
    """Keep the original forecast bound after morning settlement adds outcomes."""
    return digest({k: v for k, v in row.items() if k not in SETTLEMENT_FIELDS})


def eligible_window(row, now, phase="initial", min_minutes=RECHECK_MIN, max_minutes=RECHECK_MAX):
    event = utc_time(row.get("event_start"))
    initial = utc_time(row.get("forecast_at"))
    if not event or not initial:
        return "EVENT_OR_FORECAST_TIME_UNVERIFIED"
    if initial >= event or initial > now:
        return "FORECAST_NOT_BEFORE_EVENT"
    remaining = (event - now).total_seconds() / 60
    if remaining <= 0:
        return "GAME_ALREADY_STARTED"
    if phase == "recheck" and not min_minutes <= remaining <= max_minutes:
        return "OUTSIDE_PREGAME_RECHECK_WINDOW"
    return None


def select(rows, queue, date, now, phase="initial", limit=10):
    batch, run_id = latest_batch(rows, date)
    by_id = {}
    duplicates = set()
    for row in batch:
        source = row.get("inputs") or {}
        key = source.get("id") if isinstance(source, dict) else None
        if not key:
            continue
        if key in by_id:
            duplicates.add(key)
        else:
            by_id[key] = row
    selected, excluded = [], Counter()
    for item in (queue.get("queue") or []):
        ident = item.get("candidate_id")
        if ident in duplicates or ident not in by_id:
            excluded["UNMATCHED_OR_DUPLICATE_FORECAST"] += 1
            continue
        row = by_id[ident]
        if (item.get("sport") != row.get("sport")
                or item.get("player") != row.get("player")
                or str(item.get("player_id")) != str(row.get("player_id"))
                or item.get("team") != row.get("team")
                or item.get("stat") != row.get("stat")
                or item.get("side") != row.get("side")
                or item.get("line") != row.get("reference_line")):
            excluded["QUEUE_FORECAST_IDENTITY_MISMATCH"] += 1
            continue
        reason = eligible_window(row, now, phase)
        if reason:
            excluded[reason] += 1
            continue
        if len(selected) >= limit:
            excluded["VERIFICATION_CAP"] += 1
            continue
        selected.append((item, row))
    return selected, excluded, run_id, len(batch)


def _report_timestamp(value, now):
    stamp = utc_time(value)
    if not stamp or stamp > now:
        return False
    return 0 <= (now - stamp).total_seconds() <= 3600


def review_verified(remark, row, forecast_hash, now):
    """A named, evidence-reading reviewer must examine supporting AND opposing cases."""
    if not isinstance(remark, dict):
        return False, "ADVERSARIAL_REVIEW_NOT_ATTESTED"
    if (remark.get("candidate_id") != (row.get("inputs") or {}).get("id")
            or remark.get("forecast_sha256") != forecast_hash
            or remark.get("team") != row.get("team")
            or str(remark.get("player_id")) != str(row.get("player_id"))
            or remark.get("decision") != "approve"
            or remark.get("source_read") is not True
            or not str(remark.get("reviewer") or "").strip()
            or not _report_timestamp(remark.get("reviewed_at"), now)):
        return False, "REVIEW_IDENTITY_ATTESTATION_OR_FRESHNESS_INVALID"
    from research_packet import _validate_fact
    for field in ("supporting", "opposing"):
        facts = remark.get(field)
        if not isinstance(facts, list) or not facts:
            return False, "REVIEW_MISSING_" + field.upper()
        for record in facts:
            if not isinstance(record, dict) or not str(record.get("quote") or "").strip():
                return False, "REVIEW_UNSOURCED_" + field.upper()
            errors = []
            checked = _validate_fact(field, record, errors, require_fresh=True, now=now)
            if errors or not checked or record.get("confidence") != "confirmed":
                return False, "REVIEW_INVALID_" + field.upper()
    return True, None


def status_verified(packet, item, now):
    player = item["player"]
    stable = str(item["sport"]) + "|" + str(item.get("player_id") or "")
    if any(isinstance(c, dict) and c.get("field") == "status"
           and c.get("resolution") == "unresolved"
           and c.get("player") in (player, stable)
           for c in packet.get("_source_conflicts") or []):
        return False, "UNRESOLVED_CONTRADICTORY_STATUS_EVIDENCE"
    row = (packet.get("availability") or {}).get(player) or {}
    fact = row.get("status")
    if not isinstance(fact, dict):
        return False, "GAME_SPECIFIC_ACTIVE_STATUS_MISSING"
    issues = []
    validated = rp._validate_fact("availability.status", fact, issues,
                                  require_fresh=True, now=now)
    if issues or not validated or validated.confidence != "confirmed":
        return False, "ACTIVE_STATUS_STALE_OR_INVALID"
    if validated.value != "active":
        return False, "PLAYER_NOT_CONFIRMED_ACTIVE"
    if fact.get("report_type") not in ACTIVE_REPORTS:
        return False, "STATUS_NOT_FROM_EXPLICIT_GAME_REPORT"
    return True, None


def quote_refresh(candidate, quote_rows, now, *, identity=None):
    """Only same-identity, same-line fresh two-sided book quotes can be substituted."""
    if quote_rows is None:
        # Original afternoon quotes are usable only while truly current;
        # an old snapshot is never a substitute for refreshed market data.
        from pickem_math import APPROVED_BOOKS, canon_book
        books = candidate.get("books") or []
        if not isinstance(books, list):
            return None, ["ORIGINAL_MARKET_BOOKS_INVALID"]
        approved = set()
        for quote in books:
            if not isinstance(quote, dict):
                return None, ["ORIGINAL_MARKET_BOOKS_INVALID"]
            if (quote.get("line") != candidate.get("line")
                    or quote.get("book_side") != candidate.get("side")
                    or not quote.get("book") or
                    not isinstance(quote.get("target"), (int, float)) or
                    not isinstance(quote.get("other"), (int, float))):
                return None, ["ORIGINAL_MARKET_BOOKS_INVALID"]
            name = canon_book(quote["book"])
            if name not in APPROVED_BOOKS:
                return None, ["UNAPPROVED_MARKET_SOURCE"]
            approved.add(name)
        if len(approved) < 2:
            return None, ["ORIGINAL_TWO_BOOK_CONSENSUS_MISSING"]
        if not _report_timestamp(candidate.get("market_retrieved_at"), now):
            return None, ["ORIGINAL_MARKET_TIMESTAMP_STALE_OR_MISSING"]
        return dict(candidate), []
    from odds_providers import quotes_for_row, consensus_input
    # Collector-owned pipeline inputs use an id, not a separate player field.
    # Restore identity ONLY from the immutable original snapshot; never guess a
    # match from an alias, stale line or another provider's event namespace.
    subject = dict(candidate)
    if identity is not None:
        for key in ("team", "opponent", "event_id", "event_id_namespace", "game_date"):
            if (subject.get(key) not in (None, "", identity.get(key))
                    and identity.get(key) not in (None, "")):
                return None, ["ORIGINAL_PIPELINE_IDENTITY_CONFLICT"]
        subject.update({k: identity.get(k) for k in
                        ("player", "sport", "team", "opponent", "event_id",
                         "event_id_namespace", "game_date")})
    if not subject.get("player") or not subject.get("team"):
        return None, ["MARKET_PLAYER_OR_TEAM_IDENTITY_MISSING"]
    found = quotes_for_row(quote_rows, subject)
    exact = [q for q in found if q.get("line") == candidate.get("line")]
    sides = consensus_input(exact, now=now.isoformat(), side=candidate.get("side"))
    choice = next((r for r in sides if r.get("line") == candidate.get("line")), None)
    if not choice or len({b.get("book") for b in choice.get("books", [])}) < 2:
        return None, ["CURRENT_TWO_SIDED_SAME_LINE_MARKET_MISSING"]
    if not _report_timestamp(choice.get("market_retrieved_at"), now):
        return None, ["CURRENT_MARKET_TIMESTAMP_INVALID"]
    refreshed = dict(candidate, books=choice["books"],
                     market_retrieved_at=choice["market_retrieved_at"])
    refreshed.pop("retrieved_minutes_ago", None)
    return refreshed, []


def verify(rows, queue, packet, date, *, now=None, phase="initial", limit=10,
           fetch=None, quotes=None, reviews=None, min_minutes=RECHECK_MIN,
           max_minutes=RECHECK_MAX, data_root=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("verification clock must be timezone aware")
    now = now.astimezone(timezone.utc)
    if packet.get("date") != date or queue.get("date") != date:
        raise ValueError("same-date research packet and queue required")
    if phase not in ("initial", "recheck"):
        raise ValueError("unsupported verification phase")
    if limit < 1 or min_minutes < 0 or max_minutes <= min_minutes:
        raise ValueError("invalid verification limits")
    selection, excluded, run, batch_count = select(rows, queue, date, now, phase, limit)
    checked_packet = deepcopy(packet)
    resolver_report = {"attempts": [], "verified_pregame_games": [],
                       "resolved_statuses": [], "started_games": []}
    if selection and fetch:
        from research_resolver import resolve
        checked_packet, resolver_report = resolve(
            checked_packet, [item["candidate_id"] for item, _ in selection],
            fetch, now=now)
    reports = reviews or {}
    if reports.get("date") not in (None, date):
        raise ValueError("cross-date reviewer submissions")
    # Reviewer submissions are optional. Missing reviews NEVER attest research.
    if reports.get("game_day_reports"):
        from verified_reports import apply_reports
        checked_packet = apply_reports(checked_packet, reports["game_day_reports"], now=now)
    if reports.get("scouting_reports"):
        from verified_scouting import apply
        checked_packet = apply(checked_packet, reports["scouting_reports"], now=now)
    attestations = reports.get("attestations") or []
    if not isinstance(attestations, list):
        raise ValueError("attestations must be an array")
    counts = Counter()
    output = []
    for item, original in selection:
        identity = item["candidate_id"]
        forecast_hash = forecast_digest(original)
        reasons = []
        if packet_game_key(checked_packet, item) is None:
            reasons.append("PACKET_FIXTURE_IDENTITY_MISMATCH")
        ok, issue = status_verified(checked_packet, item, now)
        if not ok:
            reasons.append(issue)
        if (item.get("stat") in ("saves", "goalie saves") and item["sport"] == "NHL"):
            starter = ((checked_packet.get("player_context") or {}).get(item["player"]) or {}).get("goalie_confirmed")
            issues = []
            if (not isinstance(starter, dict) or starter.get("value") is not True or
                    not rp._validate_fact("starter", starter, issues, require_fresh=True, now=now) or issues):
                reasons.append("STARTING_GOALIE_NOT_EXPLICITLY_CONFIRMED")
        matching = [a for a in attestations if isinstance(a, dict)
                    and a.get("candidate_id") == identity]
        if len(matching) != 1:
            reasons.append("ADVERSARIAL_REVIEW_NOT_ATTESTED_OR_DUPLICATE")
            attested = False
        else:
            attested, issue = review_verified(matching[0], original, forecast_hash, now)
            if issue:
                reasons.append(issue)
        candidate = original.get("inputs")
        result = None
        if not isinstance(candidate, dict) or candidate.get("id") != identity:
            reasons.append("ORIGINAL_PIPELINE_INPUT_MISSING")
        else:
            refreshed, market_issues = quote_refresh(candidate, quotes, now, identity=original)
            reasons.extend(market_issues)
            if refreshed is not None:
                scoped = rp.candidate_packet(checked_packet, refreshed)
                validated, issues = rp.validate_packet(scoped, now=now)
                if issues:
                    reasons.append("RESEARCH_PACKET_INVALID")
                else:
                    prepared = rp.merge_into_pipeline(validated, [refreshed])
                    if len(prepared) != 1:
                        reasons.append("RESEARCH_MERGE_FAILED")
                    else:
                        prepared[0]["research_checklist"] = "yes" if attested else "no"
                        try:
                            from usage_baseline import using_directory
                            with using_directory(data_root or Path("data")):
                                result = pm.evaluate_candidate(prepared[0], now=now)
                        except (pm.PickemError, ValueError, KeyError, TypeError) as exc:
                            reasons.append("ENGINE_REEVALUATION_FAILED_" + type(exc).__name__)
        rank = (result or {}).get("final_rank", "Unranked")
        a = (result or {}).get("engine_a") or {}
        b = (result or {}).get("engine_b") or {}
        blend = (result or {}).get("blend") or {}
        if result is None:
            reasons.append("NO_CURRENT_VERIFIED_ENGINE_GRADE")
        elif not a.get("reliable") or not b.get("reliable"):
            reasons.append("TWO_RELIABLE_ENGINES_REQUIRED")
        elif rank not in TIERS:
            reasons.append("ENGINE_RANK_NOT_ELIGIBLE_" + rank.upper().replace(" ", "_"))
        if rank == "Tier 1" and not blend.get("validated"):
            reasons.append("TIER1_BLEND_NOT_VALIDATED")
        grade = (result or {}).get("grade") or {}
        if rank in TIERS and (not probability(grade.get("q_model"))
                              or not probability(grade.get("q_market_comparable"))):
            reasons.append("CURRENT_NUMERIC_GRADE_UNVERIFIED")
        accepted = not reasons and rank in TIERS
        final_rank = rank if accepted else "Unranked"
        counts["verified" if accepted else "blocked"] += 1
        machine = ((checked_packet.get("_autonomous_investigation") or {})
                   .get("candidate_summaries") or {}).get(identity)
        if (not isinstance(machine, dict)
                or machine.get("forecast_sha256") != forecast_hash):
            machine = None
        output.append({
            "candidate_id": identity, "snapshot_run_id": run,
            "forecast_sha256": forecast_hash,
            "forecast_at": original.get("forecast_at"),
            "event_start": original.get("event_start"),
            "checked_at": now.isoformat(),
            "game": item.get("game"), "team": item["team"],
            "sport": item["sport"], "player": item["player"],
            "stat": item["stat"], "side": item["side"],
            "reference_line": original.get("reference_line"),
            "decision": "verified" if accepted else "blocked",
            "publication_eligible": accepted,
            "verified_rank": final_rank,
            "diagnostic_regrade_rank": rank,
            "verified_model_probability": ((result or {}).get("grade") or {}).get("q_model"),
            "verified_market_probability": ((result or {}).get("grade") or {}).get("q_market_comparable"),
            "engine_a_reliable": a.get("reliable") is True,
            "engine_b_reliable": b.get("reliable") is True,
            "blend_validated": blend.get("validated") is True,
            "blockers": sorted(set(reasons)),
            "reviewer": matching[0].get("reviewer") if len(matching) == 1 else None,
            "autonomous_investigation": ({
                "source": machine.get("source"),
                "supporting_game_count": machine.get("supporting_game_count", 0),
                "opposing_game_count": machine.get("opposing_game_count", 0),
                "news_mention_count": machine.get("news_mention_count", 0),
                "research_complete": False,
                "approval_authorized": False
            } if machine else None),
            "research_packet_sha256": digest(scoped) if isinstance(candidate, dict) and
                                        refreshed is not None and 'scoped' in locals() else None,
        })
        # Do not leak prior candidate-scoped packets into a later iteration.
        if "scoped" in locals():
            del scoped
    status = ("no_candidates_due" if not selection else
              "all_verified" if not counts["blocked"] else "verification_blocked")
    return {
        "schema": "pick-verification-v1", "phase": phase, "date": date,
        "source_forecast_run_id": run, "generated_at": now.isoformat(),
        "forecast_batch_count": batch_count, "queue_size": len(queue.get("queue") or []),
        "checked": len(output), "verified": counts["verified"],
        "blocked": counts["blocked"], "not_due": dict(sorted(excluded.items())),
        "research_source_attempts": resolver_report.get("attempts") or [],
        "verified_pregame_games": resolver_report.get("verified_pregame_games") or [],
        "status": status, "decisions": output,
        "integrity": {"original_forecasts_modified": False,
                      "original_forecast_hashes_recorded": True,
                      "review_required": True,
                      "no_backdated_approval": True,
                      "source_check_does_not_imply_attestation": True},
    }, checked_packet


def load_json(path, default=None):
    if not path:
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--snapshots", default="data/prop_snapshots.jsonl")
    parser.add_argument("--queue", default="reports/research_triage.json")
    parser.add_argument("--packet")
    parser.add_argument("--reviews", help="Reviewer-read source claims and adversarial attestations (optional)")
    parser.add_argument("--phase", choices=("initial", "recheck"), default="initial")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--refresh-sources", action="store_true")
    parser.add_argument("--refresh-quotes", action="store_true",
                        help="Explicitly consume PropLine quota for current same-line prices")
    parser.add_argument("--quotes-file", help="Current two-sided market quote JSONL")
    parser.add_argument("--out", default="reports/pick_verification.json")
    parser.add_argument("--archive-root", default="data/verification")
    parser.add_argument("--now", help="Test-only frozen evaluation time")
    args = parser.parse_args(argv)
    now = utc_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        parser.error("invalid aware --now")
    if now.astimezone(ZoneInfo("America/Toronto")).date().isoformat() != args.date:
        parser.error("date must be the current Toronto slate date")
    rows = [json.loads(line) for line in Path(args.snapshots).read_text(encoding="utf-8").splitlines() if line.strip()]
    queue = load_json(args.queue)
    packet_path = args.packet or str(Path(args.archive_root) / args.date / "packet.json")
    packet = load_json(packet_path)
    selected, _, _, _ = select(rows, queue, args.date, now, args.phase, args.limit)
    reviews_payload = load_json(args.reviews, {})
    attestations = (reviews_payload or {}).get("attestations") or []
    verified_reviewed = set()
    for item, original in selected:
        for assertion in attestations:
            if (isinstance(assertion, dict) and
                    assertion.get("candidate_id") == item["candidate_id"] and
                    review_verified(assertion, original, forecast_digest(original), now)[0]):
                verified_reviewed.add(item["candidate_id"])
    quotes = None
    quote_note = "original_market_data_subject_to_freshness_gate"
    if selected and args.refresh_quotes and verified_reviewed:
        from odds_providers import PropLineProvider
        requested = sorted({item["sport"] for item, _ in selected
                            if item["candidate_id"] in verified_reviewed})
        provider = PropLineProvider()
        quotes = provider.fetch(args.date, requested)
        quote_note = provider.note or "current_market_quotes_requested"
    elif selected and args.refresh_quotes:
        quote_note = "propline_not_called_no_validated_adversarial_review"
        quotes = []
    elif args.quotes_file:
        quotes = [json.loads(s) for s in Path(args.quotes_file).read_text(encoding="utf-8").splitlines() if s.strip()]
        quote_note = "quote_file"
    if args.refresh_sources and selected:
        from fetch_slate import fetch_json
        fetch = fetch_json
    else:
        fetch = None
    report, checked_packet = verify(
        rows, queue, packet, args.date, now=now, phase=args.phase,
        limit=args.limit, fetch=fetch, quotes=quotes,
        reviews=reviews_payload,
        data_root=Path(args.snapshots).parent)
    report["market_source_note"] = quote_note
    run_id = os.environ.get("GITHUB_RUN_ID") or now.strftime("%Y%m%dT%H%M%S%fZ")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    decision_path = (Path(args.archive_root) / args.date / "decisions" /
                     (run_id + "-" + attempt + "-" + args.phase + ".json"))
    if decision_path.exists():
        raise ValueError("immutable verification decision already exists")
    write_atomic(args.out, report)
    write_atomic(decision_path, report)
    # This is the CURRENT research state; historical decisions are separate.
    write_atomic(Path(args.archive_root) / args.date / "packet.json", checked_packet)
    if args.phase == "initial":
        write_atomic(Path(args.archive_root) / args.date / "queue.json", queue)
    print(json.dumps({k: v for k, v in report.items() if k not in ("decisions", "research_source_attempts")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
