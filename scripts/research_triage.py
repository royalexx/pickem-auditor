#!/usr/bin/env python3
"""Prioritize verifiable research without changing forecasts or publishing picks."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path

TYPES = {
    "SAMPLE_BLOCK": "sample_or_distribution",
    "INVALID_MARKET": "market_consensus",
    "CONTEXT_UNRESOLVED": "context",
    "NORMAL_LEFT_TAIL": "distribution_caution",
    "STATUS_NOT_VERIFIED": "pregame_identity_and_availability",
    "VENUE_OR_FORECAST_UNVERIFIED": "pregame_identity_and_availability",
}
DIMENSIONS = ("matchup", "opportunity", "injuries", "game_script")
ESPN_PATH = {"NBA": "basketball/nba", "NHL": "hockey/nhl", "NFL": "football/nfl"}

def source_guides(item, date):
    """Find places to CHECK, never imply evidence was actually retrieved."""
    sport = item["sport"]
    path = ESPN_PATH.get(sport)
    if not path:
        return []
    root = "https://site.api.espn.com/apis/site/v2/sports/" + path
    common = {"source_state": "not_checked", "verified": False,
              "identity_rule": "match date, both teams, player and stable ID where available"}
    return [
        {**common, "task": "confirm_fixture_and_start",
         "url": f"{root}/scoreboard?dates={date.replace('-', '')}"},
        {**common, "task": "check_explicit_injury_designations",
         "url": f"{root}/injuries",
         "warning": "absence from injury report does not confirm active status"},
        {**common, "task": "check_game_specific_active_roster",
         "url": None,
         "instruction": "After matching an official scoreboard event ID, read its pregame summary/rosters; require an explicit game-active flag"},
        {**common, "task": "verify_scouting_checklist",
         "url": None,
         "instruction": "Read date-specific evidence for matchup, opportunities, injuries, game script and stat-specific scouting checks; document counterevidence"},
    ]

def packet_game_key(packet, item):
    """Use only a packet game proven to match the subject's team and sport."""
    meta = ((packet.get("index") or {}).get("by_player") or {}).get(item["player"])
    if not isinstance(meta, dict) or meta.get("team") != item["team"] or meta.get("sport") != item["sport"]:
        return None
    game = meta.get("game")
    if not isinstance(game, str) or "@" not in game:
        return None
    teams = {piece.strip() for piece in game.split("@")}
    if len(teams) != 2 or teams != {item["team"], item["opponent"]}:
        return None
    return game


def probability(value):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and 0 <= value <= 1)

def utc_time(value):
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except ValueError:
        return None

def category(reason):
    return next((name for key, name in TYPES.items() if key in reason), "other")

def latest_batch(rows, date):
    batches = defaultdict(list)
    for row in rows:
        if row.get("game_date") == date and row.get("run_type") == "shadow":
            batches[str(row.get("run_id") or "legacy")].append(row)
    if not batches:
        return [], None
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    key = max(batches, key=lambda run: (
        max(utc_time(r.get("forecast_at")) or epoch for r in batches[run]), run))
    return batches[key], key

def build(rows, date, *, packet=None, now=None, limit=30, max_per_game=6,
          minimum_grade=.57, minimum_gap=.03):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware now required")
    batch, run = latest_batch(rows, date)
    reasons = Counter(str(row.get("reason") or "RESEARCH_UNVERIFIED") for row in batch)
    categories = Counter(category(reason) for reason, n in reasons.items() for _ in range(n))
    candidates, excluded = [], Counter()
    recoverable = {"sample_or_distribution", "context", "market_consensus"}
    for row in batch:
        reason = str(row.get("reason") or "")
        reason_class = category(reason)
        is_recovery = reason_class in recoverable
        if reason_class != "pregame_identity_and_availability" and not is_recovery:
            excluded["other_primary_blocker"] += 1
            continue
        inputs = row.get("inputs") or {}
        if not isinstance(inputs, dict) or not row.get("player") or not row.get("team"):
            excluded["missing_identity"] += 1
            continue
        start = utc_time(row.get("event_start"))
        if start and start <= now:
            excluded["game_started"] += 1
            continue
        # A missing production grade MUST NOT be substituted for ranking.
        # The independent A-side estimate is only a diagnostic to prioritize
        # collecting missing source facts; its provenance is recorded explicitly.
        model = row.get("q_grade")
        diagnostic_source = "verified_production_grade"
        if not probability(model) and is_recovery:
            a = row.get("engine_a") or {}
            if a.get("observation_ids_verified") is True:
                model = a.get("q_win_robust")
                diagnostic_source = "engine_a_unverified_recovery_only"
        if not probability(model):
            excluded["missing_source_model_diagnostic"] += 1
            continue
        market = row.get("q_market_comparable")
        if not probability(market):
            market = row.get("q_market")
        market_source = "source_grade"
        if not probability(market) and is_recovery:
            # The initial grade may stop before setting q_market. Reconstruct
            # only from actual same-line, two-sided sportsbook odds.
            from pickem_math import consensus, PickemError
            books_raw = row.get("books") or []
            try:
                books_provenance = [(b["book"],float(b["line"]),float(b["target"]),float(b["other"]))
                                    for b in books_raw if isinstance(b,dict)
                                    and all(k in b for k in ("book","line","target","other"))]
                value = consensus(books_provenance) if len(set(x[0] for x in books_provenance))>=2 else {}
                if probability(value.get("q_market")):
                    market = value["q_market"]
                    market_source = "source_quote_diagnostic_only"
            except (PickemError,ValueError,TypeError,KeyError):
                pass
        books = len({str(b.get("book")).casefold() for b in (row.get("books") or [])
                     if isinstance(b, dict) and b.get("book")})
        if books < 2:
            excluded["insufficient_independent_books"] += 1
            continue
        if not probability(market):
            excluded["missing_comparable_probabilities"] += 1
            continue
        if not is_recovery and not (row.get("engine_a") or {}).get("reliable"):
            excluded["unreliable_engine_a"] += 1
            continue
        if model < (max(minimum_grade, .65) if is_recovery else minimum_grade):
            excluded["below_research_priority_floor"] += 1
            continue
        if not is_recovery and model-market < minimum_gap:
            excluded["below_research_priority_floor"] += 1
            continue
        reliable_b = bool((row.get("engine_b") or {}).get("reliable"))
        scouting = (inputs.get("scouting") or {}).get("evidence") or {}
        missing = [dim for dim in DIMENSIONS if not isinstance(scouting.get(dim), dict)
                   or scouting[dim].get("confidence") != "confirmed"]
        needs = ["explicit_game_specific_player_status",
                 "source_read_scouting_and_adversarial_review",
                 "independent_line_and_model_verification"]
        if is_recovery:
            needs.extend(["RECOVERY_ONLY_NOT_NUMERICALLY_GRADED",
                          "repair_primary_veto:" + reason])
        if "VENUE_OR_FORECAST_UNVERIFIED" in reason:
            needs.append("source_verified_venue_or_forecast")
        if not reliable_b:
            needs.append("engine_b_reliability")
        if missing:
            needs.append("scouting_dimensions:" + ",".join(missing))
        sport, player = str(row["sport"]), str(row["player"])
        cid = str(inputs.get("id") or "|".join((sport, player, str(row.get("stat")), str(row.get("side")))))
        from pickem_math import GAP_WATCH_CAP, GAP_EPSILON
        gap_watch_capped = abs(model-market) >= GAP_WATCH_CAP-GAP_EPSILON
        priority = ("recovery_"+reason_class if is_recovery else
                    "watchlist_gap_capped" if gap_watch_capped else "tier_candidate")
        candidates.append({
            "verification_priority_class": priority,
            "recovery_only": is_recovery,
            "model_diagnostic_source": diagnostic_source,
            "market_diagnostic_source": market_source,
            "watchlist_gap_cap_applies": gap_watch_capped,
            "candidate_id": cid, "sport": sport, "player": player,
            "player_id": row.get("player_id"), "team": str(row["team"]),
            "opponent": str(row.get("opponent") or ""),
            "game": str(row.get("matchup") or ""),
            "stat": row.get("stat"), "side": row.get("side"),
            "line": row.get("reference_line"),
            "model_probability_diagnostic": round(model, 5),
            "market_probability_diagnostic": round(market, 5),
            "provisional_gap": round(model-market, 5),
            "independent_book_count": books, "both_engines_reliable": reliable_b,
            "missing_evidence": needs, "source_tasks": [],
            "source_guides": source_guides({"sport": sport}, date),
            "source_guides_are_evidence": False,
            "reason": reason, "status": "verification_pending",
            "publication_eligible": False,
        })
    # Tier-capable candidates lead, but reserve one-third of a full research
    # budget for fixable source gaps when present. This never promotes them.
    candidates.sort(key=lambda item: (
        item["recovery_only"],
        not item["both_engines_reliable"],
        item["watchlist_gap_cap_applies"],
        -item["model_probability_diagnostic"],
        -item["provisional_gap"],
        item["sport"], item["player"]))
    primary = [item for item in candidates if not item["recovery_only"]]
    recovery = [item for item in candidates if item["recovery_only"]]
    queue, seen, attempted, per_game = [], set(), set(), Counter()
    def select(pool, budget):
        # Round-robin by sport AND statistic so the first priced market cannot
        # monopolize the queue; choose one side per (player, stat, fixture).
        buckets = defaultdict(list)
        for item in pool:
            buckets[(item["sport"],item["stat"])].append(item)
        keys = sorted(buckets)
        while keys and len(queue) < budget:
            nxt=[]
            for key in keys:
                if len(queue)>=budget:break
                while buckets[key]:
                    item=buckets[key].pop(0)
                    identity=(item["sport"],str(item["player_id"] or item["player"]),
                              item["team"],item["opponent"],item["stat"])
                    if item["candidate_id"] in attempted:
                        continue
                    attempted.add(item["candidate_id"])
                    game=(item["sport"],tuple(sorted((item["team"],item["opponent"]))))
                    if identity in seen:
                        excluded["duplicate_player_stat"] += 1
                        continue
                    if per_game[game]>=max_per_game:
                        excluded["game_cap"] += 1
                        continue
                    queue.append(item)
                    seen.add(identity);per_game[game]+=1
                    break
                if buckets[key]:nxt.append(key)
            keys=nxt
    reserve=min(len(recovery),max(0,limit//3))
    select(primary,max(0,limit-reserve))
    # Recoveries are independently quarantined; they cannot enter rank boards
    # until a new immutable forecast has been made with reliable engines.
    select(recovery,limit)
    select(primary,limit)
    if len(queue)<len(candidates):
        excluded["queue_or_identity_cap"] += len(candidates)-len(queue)
    if packet is not None and queue:
        if packet.get("date") != date:
            raise ValueError("research packet date mismatch")
        from context_feeds import gap_paths_for_shortlist
        identifiers = {c["candidate_id"] for c in queue}
        prep = [r.get("inputs") for r in batch if isinstance(r.get("inputs"), dict)
                and r["inputs"].get("id") in identifiers]
        gaps = gap_paths_for_shortlist(packet, list(identifiers), candidate_rows=prep, now=now)
        for item in queue:
            game = packet_game_key(packet, item)
            prefixes = [f"availability.{item['player']}.",
                        f"scouting.{item['candidate_id']}.",
                        f"lineup.{item['team']}."]
            if game:
                prefixes += [f"weather.{game}.", f"environment.{game}."]
            item["source_tasks"] = sorted({str(g["path"]) for g in gaps
                if any(str(g.get("path") or "").startswith(prefix) for prefix in prefixes)})
            item["matched_packet_game"] = game
            if not game:
                item["missing_evidence"].append("packet_fixture_identity_not_verified")
    shared = {}
    for item in queue:
        for guide in item["source_guides"]:
            url = guide.get("url")
            if not url:
                continue
            record = shared.setdefault(url, {"url": url, "task": guide["task"],
                                              "source_state": "not_checked", "verified": False,
                                              "candidates": [], "games": []})
            record["candidates"].append(item["candidate_id"])
            fixture = " / ".join(sorted((item["team"], item["opponent"])))
            if fixture not in record["games"]:
                record["games"].append(fixture)
    source_checklist = list(shared.values())
    for item in source_checklist:
        item["candidates"].sort()
        item["games"].sort()
    for index, item in enumerate(queue, 1):
        item["priority"] = index
    return {
        "date": date, "generated_at": now.isoformat(), "run_id": run,
        "status": "verification_queue_ready" if queue else "no_priority_candidates",
        "forecasts_evaluated": len(batch),
        "unverified_research": sum(not bool(r.get("researched")) for r in batch),
        "numerically_gradeable": sum(probability(r.get("q_grade")) for r in batch),
        "reason_counts": dict(sorted(reasons.items())),
        "blocker_categories": dict(sorted(categories.items())),
        "qualified_before_caps": len(candidates), "review_queue_count": len(queue),
        "tier_candidate_before_caps": sum(not x["watchlist_gap_cap_applies"] and not x["recovery_only"] for x in candidates),
        "tier_candidate_selected": sum(not x["watchlist_gap_cap_applies"] and not x["recovery_only"] for x in queue),
        "watchlist_gap_capped_selected": sum(x["watchlist_gap_cap_applies"] and not x["recovery_only"] for x in queue),
        "recovery_only_selected": sum(x["recovery_only"] for x in queue),
        "recovery_selected_by_sport_stat": dict(sorted(Counter(
            str(x["sport"]) + "|" + str(x["stat"]) for x in queue if x["recovery_only"]).items())),
        "qualified_by_sport": dict(sorted(Counter(c["sport"] for c in candidates).items())),
        "selected_by_sport": dict(sorted(Counter(c["sport"] for c in queue).items())),
        "review_queue_both_engines_reliable": sum(c["both_engines_reliable"] for c in queue),
        "queue_exclusions": dict(sorted(excluded.items())), "queue": queue,
        "source_checklist": source_checklist,
        "unique_public_source_urls_for_review": len(source_checklist),
        "subjects_with_packet_gaps": sum(bool(item["source_tasks"]) for item in queue),
        "source_urls_verified": 0,
        "integrity": {
            "publication_eligible": False, "existing_forecasts_modified": False,
            "model_weights_modified": False, "infer_active_from_injury_absence": False,
            "require_current_explicit_source_facts": True,
            "probability_gap_is_not_proven_value": True,
        },
    }

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True)
    p.add_argument("--path", default="data/prop_snapshots.jsonl")
    p.add_argument("--packet")
    p.add_argument("--out", default="reports/research_triage.json")
    p.add_argument("--limit", type=int, default=30)
    args = p.parse_args(argv)
    if args.limit < 1:
        p.error("limit must be positive")
    rows = [json.loads(line) for line in Path(args.path).read_text(encoding="utf-8").splitlines() if line.strip()]
    packet = json.loads(Path(args.packet).read_text(encoding="utf-8")) if args.packet else None
    result = build(rows, args.date, packet=packet, limit=args.limit)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "queue"}, indent=2))
    return 0 if result["forecasts_evaluated"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
