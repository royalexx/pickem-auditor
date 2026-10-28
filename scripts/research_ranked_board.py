#!/usr/bin/env python3
"""Numerically ranked research candidates. NEVER an approved pick list."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import pickem_math as pm
from pick_verification import forecast_digest, utc_time, write_atomic
from research_triage import latest_batch, probability

# A 56-58% grade cannot legitimately be called Tier 2 (>80% realized target)
# or a remarkable Tier 3. Keep it visible as a screened research candidate.
# The stricter prospects are still UNVERIFIED until holdout calibration exists.
PROSPECT_FLOORS = (("Unicorn Research Prospect", 0.90),
                   ("Tier 2 Research Prospect", 0.81),
                   ("Tier 3 Research Prospect", 0.70))
NEGATIVE_STATUS = {"PLAYER_NOT_CONFIRMED_ACTIVE",
                   "UNRESOLVED_CONTRADICTORY_STATUS_EVIDENCE",
                   "MACHINE_PLAYER_NOT_CONFIRMED_ACTIVE",
                   "MACHINE_UNRESOLVED_CONTRADICTORY_STATUS_EVIDENCE"}


def matched_books(row):
    from pickem_math import canon_book, APPROVED_BOOKS
    matched = set()
    for book in ((row.get("inputs") or {}).get("books") or row.get("books") or []):
        if not isinstance(book, dict):
            continue
        name = book.get("book")
        if (not isinstance(name, str) or canon_book(name) not in APPROVED_BOOKS
                or book.get("line") != row.get("reference_line")
                or book.get("book_side") not in (None, row.get("side"))):
            continue
        if all(isinstance(book.get(k), (int, float)) and
               not isinstance(book[k], bool) and math.isfinite(book[k])
               for k in ("target", "other")):
            matched.add(canon_book(name))
    return len(matched)


def build(rows, queue, date, *, now=None, decisions=(), history_root="data", packet=None):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    batch, run = latest_batch(rows, date)
    if queue.get("date") != date or queue.get("run_id") != run or not run:
        return {"schema": "research-ranked-v1", "status": "snapshot_queue_mismatch",
                "date": date, "research_ranked": [], "publication_eligible": False}
    by_id = {}
    duplicate = set()
    for row in batch:
        inputs = row.get("inputs") or {}
        ident = inputs.get("id") if isinstance(inputs, dict) else None
        if ident in by_id:
            duplicate.add(ident)
        elif isinstance(ident, str) and ident:
            by_id[ident] = row
    blocked = {}
    for receipt in decisions:
        if (receipt.get("schema") != "pick-verification-v1" or
                receipt.get("date") != date or
                receipt.get("source_forecast_run_id") != run):
            continue
        for d in receipt.get("decisions") or []:
            row = by_id.get(d.get("candidate_id"))
            if row and d.get("forecast_sha256") == forecast_digest(row):
                checked = utc_time(d.get("checked_at"))
                first = utc_time(row.get("forecast_at"))
                start = utc_time(row.get("event_start"))
                if checked and first and start and first <= checked < start:
                    key = d["candidate_id"]
                    if key not in blocked or checked > blocked[key][0]:
                        blocked[key] = (checked, d)
    chosen, excluded, seen = [], Counter(), set()
    for item in queue.get("queue") or []:
        ident = item.get("candidate_id") if isinstance(item, dict) else None
        row = by_id.get(ident)
        if not row or ident in duplicate or ident in seen:
            excluded["missing_or_duplicate"] += 1
            continue
        seen.add(ident)
        keys = ("sport", "player", "player_id", "team", "opponent", "stat", "side")
        if (any(str(item.get(k)) != str(row.get(k)) for k in keys) or
                item.get("line") != row.get("reference_line")):
            excluded["identity_mismatch"] += 1
            continue
        forecast, event = utc_time(row.get("forecast_at")), utc_time(row.get("event_start"))
        if not forecast or not event or forecast > now or forecast >= event or event <= now:
            excluded["started_or_invalid_clock"] += 1
            continue
        if row.get("reason") not in ("STATUS_NOT_VERIFIED", "VENUE_OR_FORECAST_UNVERIFIED",
                                      "CONTEXT_UNRESOLVED", "RESEARCH_UNVERIFIED"):
            excluded["nonresearch_primary_veto"] += 1
            continue
        if (not (row.get("engine_a") or {}).get("reliable") or
                not (row.get("engine_b") or {}).get("reliable")):
            excluded["engine_unreliable"] += 1
            continue
        if matched_books(row) < 2 or (row.get("market") or {}).get("market_valid") is False:
            excluded["market_not_correlated"] += 1
            continue
        p, m, push, comparable = (row.get("q_grade"), row.get("q_market"),
                                   row.get("q_push"), row.get("q_market_comparable"))
        flags, n = row.get("soft_flags"), row.get("current_role_n")
        if (not all(probability(v) for v in (p, m, push, comparable)) or
                p + push > 1 + 1e-9 or not isinstance(flags, int) or
                isinstance(flags, bool) or flags < 0 or
                not isinstance(n, (int, float)) or isinstance(n, bool) or
                not math.isfinite(n) or n < 0):
            excluded["invalid_numeric_provenance"] += 1
            continue
        try:
            score = pm.grade(p, m, flags, n, q_push=push)
        except (pm.PickemError, ValueError, TypeError):
            excluded["numeric_regrade_failed"] += 1
            continue
        if (score.get("status") != "GRADED" or
                abs(score["q_market_comparable"] - comparable) > 1e-6 or
                p < .57 or p - comparable < .03):
            excluded["below_research_quality_floor"] += 1
            continue
        if abs(p - comparable) >= pm.GAP_WATCH_CAP - pm.GAP_EPSILON:
            excluded["large_gap_watchlist_cap"] += 1
            continue
        band = score.get("probability_rank")
        if band not in ("NUMERIC_TIER_1","NUMERIC_TIER_2","NUMERIC_TIER_3"):
            rank = None
        else:
            rank = next((name for name, floor in PROSPECT_FLOORS if p >= floor),
                        "Screened Research Candidate")
        if rank is None:
            excluded["numeric_flag_or_sample_cap"] += 1
            continue
        price = utc_time((row.get("inputs") or {}).get("market_retrieved_at") or (row.get("market") or {}).get("retrieved_at") or row.get("retrieved_at"))
        if price and (price > forecast or (forecast-price).total_seconds() > 1800):
            excluded["stale_at_original_forecast"] += 1
            continue
        recent = blocked.get(ident)
        if recent:
            d = recent[1]
            if d.get("decision") == "verified" and d.get("publication_eligible") is True:
                excluded["already_on_verified_board"] += 1
                continue
            if any(b in NEGATIVE_STATUS for b in d.get("blockers") or []):
                excluded["explicit_negative_status"] += 1
                continue
        from recent_lineup_tendency import evaluate as estimate_lineup
        tendency = estimate_lineup({
            "sport": row["sport"], "stat": row["stat"], "team": row["team"],
            "player_id": row.get("player_id"), "player": row["player"],
            "game_date": date,
        }, now, root=history_root, packet=packet)
        chosen.append({
            "candidate_id": ident, "sport": row["sport"], "player": row["player"],
            "team": row["team"], "opponent": row["opponent"], "stat": row["stat"],
            "side": row["side"], "line": row["reference_line"], "research_rank": rank,
            "lineup_tendency": tendency, "lineup_status": (
                "historically_likely" if tendency["likely_available"] else "unconfirmed"), 
            "forecast_calibration": "not_certified_for_tier_hit_rate",
            "q_model": p, "q_market_comparable": comparable,
            "model_market_gap": round(p-comparable, 6),
            "forecast_at": row["forecast_at"], "event_start": row["event_start"],
            "price_timestamp_verified": price is not None,
            "price_refresh_required": price is None or (now-price).total_seconds() > 1800,
            "forecast_sha256": forecast_digest(row), "source_forecast_run_id": run,
            "verification_status": "game_specific_evidence_pending",
            "publication_eligible": False, "verified_pick": False,
            "actionable_without_verification": False,
        })
    order = {"Unicorn Research Prospect":0,"Tier 2 Research Prospect":1,
             "Tier 3 Research Prospect":2,"Screened Research Candidate":3}
    chosen.sort(key=lambda r: (order[r["research_rank"]],
                                -r["q_model"], -r["model_market_gap"], r["candidate_id"]))
    return {"schema": "research-ranked-v1", "date": date,
            "generated_at": now.isoformat(), "source_forecast_run_id": run,
            "original_forecasts_in_batch": len(batch), "queue_size": len(queue.get("queue") or []),
            "research_ranked": chosen, "rank_counts": dict(Counter(x["research_rank"] for x in chosen)),
            "excluded": dict(excluded), "status": "research_ranked" if chosen else "no_research_ranks",
            "publication_eligible": False, "verified_board_unchanged": True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True)
    p.add_argument("--snapshots", default="data/prop_snapshots.jsonl")
    p.add_argument("--queue", default="reports/research_triage.json")
    p.add_argument("--archive-root", default="data/verification")
    p.add_argument("--out", default="reports/research_ranked_board.json")
    args = p.parse_args()
    rows = [json.loads(s) for s in Path(args.snapshots).read_text().splitlines() if s.strip()]
    queue = json.loads(Path(args.queue).read_text())
    receipts = [json.loads(f.read_text()) for f in sorted(
        (Path(args.archive_root)/args.date/"decisions").glob("*.json"))]
    packet_path = Path(args.archive_root) / args.date / "packet.json"
    packet = json.loads(packet_path.read_text()) if packet_path.exists() else None
    report = build(rows, queue, args.date, decisions=receipts,
                   history_root=Path(args.snapshots).parent, packet=packet)
    write_atomic(args.out, report)
    print(json.dumps({k: v for k, v in report.items() if k != "research_ranked"}, indent=2))
    return 0 if report["status"] != "snapshot_queue_mismatch" else 2


if __name__ == "__main__":
    raise SystemExit(main())
