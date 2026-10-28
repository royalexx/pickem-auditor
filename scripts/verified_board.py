#!/usr/bin/env python3
"""Read-only live board built from immutable forecast-linked verification receipts."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from pick_verification import TIERS, forecast_digest, utc_time, write_atomic
from research_triage import latest_batch, probability


def build(rows, receipts, date, *, now=None, max_age_minutes=60):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    originals, run = latest_batch(rows, date)
    index = {}
    collisions = set()
    for row in originals:
        candidate = row.get("inputs") or {}
        ident = candidate.get("id") if isinstance(candidate, dict) else None
        if ident:
            if ident in index:
                collisions.add(ident)
            else:
                index[ident] = row
    latest, invalid = {}, Counter()
    for receipt in receipts:
        if not isinstance(receipt, dict) or receipt.get("date") != date or receipt.get("schema") != "pick-verification-v1":
            invalid["wrong_receipt_schema_or_date"] += 1
            continue
        if receipt.get("source_forecast_run_id") != run:
            invalid["forecast_run_mismatch"] += 1
            continue
        for decision in receipt.get("decisions") or []:
            if not isinstance(decision, dict):
                invalid["invalid_decision"] += 1
                continue
            ident = decision.get("candidate_id")
            row = index.get(ident)
            if not ident or ident in collisions or not row:
                invalid["missing_or_ambiguous_original"] += 1
                continue
            checked = utc_time(decision.get("checked_at"))
            forecast = utc_time(row.get("forecast_at"))
            start = utc_time(row.get("event_start"))
            if (not checked or not forecast or not start or
                    checked < forecast or checked >= start or checked > now):
                invalid["invalid_event_clock"] += 1
                continue
            if (decision.get("forecast_sha256") != forecast_digest(row)
                    or decision.get("forecast_at") != row.get("forecast_at")
                    or decision.get("event_start") != row.get("event_start")
                    or decision.get("reference_line") != row.get("reference_line")
                    or decision.get("team") != row.get("team")
                    or decision.get("stat") != row.get("stat")
                    or decision.get("side") != row.get("side")):
                invalid["forecast_receipt_identity_mismatch"] += 1
                continue
            if ident not in latest or checked > latest[ident][0]:
                latest[ident] = (checked, decision, row)
    candidates, exclusions = [], Counter()
    for checked, decision, row in latest.values():
        start = utc_time(row.get("event_start"))
        if start <= now:
            exclusions["game_started"] += 1
            continue
        age = (now - checked).total_seconds() / 60
        if age > max_age_minutes:
            exclusions["verification_stale"] += 1
            continue
        if (decision.get("decision") != "verified"
                or decision.get("publication_eligible") is not True
                or decision.get("verified_rank") not in TIERS
                or decision.get("blockers")
                or decision.get("engine_a_reliable") is not True
                or decision.get("engine_b_reliable") is not True
                or not str(decision.get("reviewer") or "").strip()):
            exclusions["latest_decision_not_approved"] += 1
            continue
        quality=decision.get("mechanism_evidence")
        allowed={"Watchlist":0,"Tier 3":1,"Tier 2":2,"Tier 1":3}
        if (not isinstance(quality,dict)
                or quality.get("version") != "mechanism-evidence-v1"
                or quality.get("legacy_count_not_authoritative") is not True
                or quality.get("no_probability_adjustment") is not True
                or quality.get("tier_ceiling") not in allowed):
            exclusions["quality_audit_receipt_missing_or_invalid"] += 1
            continue
        if allowed[decision["verified_rank"]] > allowed[quality["tier_ceiling"]]:
            exclusions["tier_exceeds_source_quality_ceiling"] += 1
            continue
        if (decision.get("review_type") == "structured_machine_verification"
                and (quality.get("machine_overlap_detected") is not True
                     or quality.get("tier_ceiling") != "Tier 3"
                     or not str(decision.get("reviewer") or "").startswith("machine:"))):
            exclusions["machine_review_quality_identity_invalid"] += 1
            continue
        if decision["verified_rank"] == "Tier 1" and decision.get("blend_validated") is not True:
            exclusions["tier1_blend_unvalidated"] += 1
            continue
        p = decision.get("verified_model_probability")
        m = decision.get("verified_market_probability")
        if not probability(p) or not probability(m):
            exclusions["probabilities_missing_or_invalid"] += 1
            continue
        candidates.append({
            "candidate_id": decision["candidate_id"],
            "sport": row.get("sport"), "player": row.get("player"),
            "team": row.get("team"), "opponent": row.get("opponent"),
            "stat": row.get("stat"), "side": row.get("side"),
            "line": row.get("reference_line"), "tier": decision["verified_rank"],
            "q_model": p, "q_market": m, "checked_at": checked.isoformat(),
            "event_start": row.get("event_start"), "reviewer": decision["reviewer"],
            "forecast_sha256": decision["forecast_sha256"],
            "forecast_run_id": run,
            "mechanism_quality": quality.get("quality"),
            "mechanism_quality_ceiling": quality["tier_ceiling"],
        })
    priority = {"Tier 1": 0, "Tier 2": 1, "Tier 3": 2}
    candidates.sort(key=lambda p:(priority[p["tier"]], -(p["q_model"]-p["q_market"]), p["candidate_id"]))
    return {
        "schema": "verified-board-v1", "date": date, "generated_at": now.isoformat(),
        "source_forecast_run_id": run,
        "original_forecasts_in_batch": len(originals),
        "verification_receipts": len(receipts),
        "valid_decision_subjects": len(latest),
        "verified_picks": candidates,
        "rank_counts": dict(Counter(p["tier"] for p in candidates)),
        "excluded": dict(sorted(exclusions.items())),
        "invalid_receipts": dict(sorted(invalid.items())),
        "status": "verified_picks_available" if candidates else "no_verified_picks",
        "source_only_other_candidates_not_promoted": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--snapshots", default="data/prop_snapshots.jsonl")
    parser.add_argument("--archive-root", default="data/verification")
    parser.add_argument("--out", default="reports/verified_board.json")
    args = parser.parse_args(argv)
    rows = [json.loads(x) for x in Path(args.snapshots).read_text(encoding="utf-8").splitlines() if x.strip()]
    files = sorted((Path(args.archive_root) / args.date / "decisions").glob("*.json"))
    report = build(rows, [json.loads(p.read_text(encoding="utf-8")) for p in files], args.date)
    write_atomic(args.out, report)
    print(json.dumps({k:v for k,v in report.items() if k!="verified_picks"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
