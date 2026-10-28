#!/usr/bin/env python3
"""Autonomous, bounded structured-source investigation of priority forecasts.

An observed JSON field is machine-verified only when matched to a current
player/game/source. No fabricated quotes, narrative scouting or attestations.
The verifier's existing research and ranking vetoes remain authoritative.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import fetch_slate as fs
from pick_verification import select, forecast_digest, status_verified, write_atomic
from research_triage import packet_game_key, utc_time
from research_resolver import resolve
from scouting_checklist import required_checks

VERSION = "autonomous-investigation-v1"
MAX_SUBJECTS = 30
MAX_OBSERVATIONS = 20
SPORTS = {"NHL", "NBA", "NFL"}
ALLOWED_SOURCE_HOSTS = frozenset(("api-web.nhle.com", "site.api.espn.com", "site.web.api.espn.com"))
DATEZONE = ZoneInfo("America/Toronto")


def source_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        if "T" in value or value.endswith("Z"):
            d = utc_time(value)
            return d.astimezone(DATEZONE).date() if d else None
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def observation_source(item, date):
    """Return one canonical official feed URL, never one inferred from a report."""
    player_id = str(item.get("player_id") or "")
    if not player_id.isdecimal() or len(player_id) > 14:
        return None
    if item["sport"] == "NHL":
        return fs.nhl_game_log_url(player_id, fs.season_id_from_date(date))
    if item["sport"] == "NBA":
        return fs.espn_gamelog_url(player_id, fs.nba_espn_season_year(date))
    return None  # NFL official play-by-play evidence needs separate signed join.


def verified_source(url):
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.hostname in ALLOWED_SOURCE_HOSTS
            and not parsed.username and not parsed.password)


def _series(item, payload):
    """Use only the repository's tested league-specific stat parsers."""
    sport, stat = item["sport"], item["stat"]
    if sport == "NHL":
        games = fs.parse_nhl_game_log(payload)
        return fs.nhl_series(games, stat) if games is not None else None
    if sport == "NBA":
        games = fs.parse_espn_gamelog(payload)
        return fs.nba_series(games, stat) if games is not None else None
    return None


def _validated_series(item, series, date):
    if series is None:
        return None, "STAT_NOT_AVAILABLE_IN_OFFICIAL_FEED"
    if not isinstance(series, list):
        return None, "INVALID_OFFICIAL_OBSERVATIONS"
    seen, valid = set(), []
    cutoff = datetime.strptime(date, "%Y-%m-%d").date()
    for row in series:
        if not isinstance(row, dict):
            return None, "INVALID_OFFICIAL_OBSERVATIONS"
        ident = str(row.get("tie") or "")
        day = _date(str(row.get("when") or ""))
        value = row.get("value")
        if (not ident or ident in seen or not day or day >= cutoff
                or not _finite(value) or value < 0):
            return None, "INVALID_OR_POST_EVENT_OBSERVATION"
        seen.add(ident)
        valid.append({"game_id": ident, "game_date": day.isoformat(),
                      "stat_value": float(value),
                      "workload_minutes": row.get("workload") if _finite(row.get("workload")) else None})
    valid.sort(key=lambda x: (x["game_date"], x["game_id"]), reverse=True)
    return valid, None


def crosscheck_collector(item, original, observed, now, data_root):
    """Compare independent API response with daily, content-hashed collector data."""
    if not isinstance(original.get("inputs"), dict):
        return {"status": "missing_original_input", "overlap": 0}
    scouting = (original["inputs"].get("scouting") or {})
    if not scouting.get("historical_usage"):
        return {"status": "collector_history_reference_unavailable", "overlap": 0}
    candidate = {"sport": item["sport"], "player_id": item["player_id"],
                 "stat": item["stat"], "team": item["team"],
                 "game_date": original["game_date"], "scouting": scouting}
    try:
        from usage_baseline import load, validate_rows, using_directory
        with using_directory(data_root):
            cache = load(candidate, now)
        validate_rows(cache["observations"], candidate, now)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        return {"status": "collector_history_unavailable_or_invalid",
                "issue": type(exc).__name__, "overlap": 0}
    expected = {str(row["id"]): float(row["value"]) for row in cache["observations"]}
    found = {row["game_id"]: row["stat_value"] for row in observed}
    overlap = set(expected) & set(found)
    mismatches = sorted(key for key in overlap if not math.isclose(
        expected[key], found[key], rel_tol=0, abs_tol=1e-8))
    return {
        "status": ("source_conflict" if mismatches else
                   "independently_correlated" if len(overlap) >= 3 else
                   "insufficient_shared_observations"),
        "overlap": len(overlap), "mismatch_game_ids": mismatches[:10],
        "collector_source": cache.get("source_url"),
        "collector_content_sha256": cache.get("content_sha256"),
    }


def _historical_findings(item, observations, url, digest, now):
    """Explicit event-level support and opposition, not forecast probabilities."""
    recent = observations[:MAX_OBSERVATIONS]
    line, side = item["line"], item["side"]
    if not _finite(line) or side not in ("over", "under"):
        return None, "INVALID_SIDE_OR_LINE"
    supporting, opposing, pushes = [], [], []
    for row in recent:
        value = row["stat_value"]
        win = value > line if side == "over" else value < line
        if value == line:
            pushes.append(row)
        elif win:
            supporting.append(row)
        else:
            opposing.append(row)
    evidence = {"source_url": url, "retrieved_at": now.isoformat(),
                "payload_sha256": digest, "observation_field": (
                    "gameLog[].shots/blockedShots/saves" if item["sport"] == "NHL"
                    else "seasonTypes[].categories[].events[].stats"),
                "source_kind": "direct_structured_league_game_log",
                "observation_count": len(observations), "sampled_count": len(recent),
                "side": side, "line": line, "support_count": len(supporting),
                "opposing_count": len(opposing), "push_count": len(pushes),
                "last_five_mean": (round(sum(x["stat_value"] for x in recent[:5]) /
                                          len(recent[:5]), 4) if recent else None),
                "observations": recent,
                "supporting_games": supporting[:5],
                "opposing_games": opposing[:5],
                "inference_policy": "historical event comparison only; neither side "
                                    "is a pregame probability or a scouting attestation"}
    return evidence, None


def investigate(rows, queue, packet, date, *, now=None, limit=10, phase="initial",
                fetch=None, data_root=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("aware evaluation clock required")
    now = now.astimezone(timezone.utc)
    if (now.astimezone(DATEZONE).date().isoformat() != date or
            packet.get("date") != date or queue.get("date") != date):
        raise ValueError("same-day queue, packet and evaluation required")
    if not 1 <= limit <= MAX_SUBJECTS:
        raise ValueError("subject limit must be 1..30")
    if fetch is None:
        fetch = fs.fetch_json
    selected, exclusions, run_id, batch_count = select(
        rows, queue, date, now, phase, limit)
    updated = deepcopy(packet)
    resolution = {"attempts": [], "resolved_statuses": [],
                  "verified_pregame_games": [], "started_games": []}
    # Shared scoreboard/summary/injury fetches occur ONCE, not per market.
    if selected:
        updated, resolution = resolve(
            updated, [item["candidate_id"] for item, _ in selected], fetch, now=now)
    entries, counts, cache = [], Counter(), {}
    for item, original in selected:
        entry = {"candidate_id": item["candidate_id"],
                 "forecast_sha256": forecast_digest(original),
                 "sport": item["sport"], "player": item["player"],
                 "player_id": item["player_id"], "team": item["team"],
                 "opponent": item["opponent"], "stat": item["stat"],
                 "side": item["side"], "line": item["line"],
                 "event_start": original.get("event_start"),
                 "checked_at": now.isoformat(), "source_attempts": [],
                 "observed_history": None, "supporting_evidence": [],
                 "opposing_evidence": [], "blockers": [],
                 "missing_scouting_checks": list(required_checks(item["sport"], item["stat"])),
                 "source_read_by_human": False, "research_attested": False,
                 "publication_eligible": False}
        reasons = entry["blockers"]
        if packet_game_key(updated, item) is None:
            reasons.append("CANONICAL_FIXTURE_IDENTITY_NOT_CONFIRMED")
        ok, issue = status_verified(updated, item, now)
        if not ok:
            reasons.append(issue)
        url = observation_source(item, date)
        if url is None or not verified_source(url):
            reasons.append("NO_SUPPORTED_PRIMARY_GAMELOG_URL")
        else:
            # One source per unique player, even when multiple stat/side candidates.
            if url not in cache:
                attempt = {"url": url, "retrieved_at": now.isoformat(),
                           "purpose": "independently check actual historical games",
                           "identity": {"sport": item["sport"],
                                        "player_id": str(item["player_id"])}}
                try:
                    response = fetch(url, timeout=15)
                    if not isinstance(response, (dict, list)):
                        raise ValueError("non-JSON official game log")
                    cache[url] = (response, None, source_hash(response))
                    attempt.update(status="retrieved",
                                   payload_sha256=cache[url][2])
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    cache[url] = (None, type(exc).__name__, None)
                    attempt.update(status="source_failed",
                                   failure_type=type(exc).__name__)
                entry["source_attempts"].append(attempt)
            payload, error, sha = cache[url]
            if error:
                reasons.append("OFFICIAL_GAMELOG_UNAVAILABLE_" + error.upper())
            else:
                series = _series(item, payload)
                observations, issue = _validated_series(item, series, date)
                if issue:
                    reasons.append(issue)
                else:
                    history, issue = _historical_findings(item, observations, url, sha, now)
                    if issue:
                        reasons.append(issue)
                    else:
                        entry["observed_history"] = history
                        entry["supporting_evidence"] = history["supporting_games"]
                        entry["opposing_evidence"] = history["opposing_games"]
                        checked = crosscheck_collector(
                            item, original, observations, now, data_root or Path("data"))
                        entry["collector_independent_check"] = checked
                        if checked["status"] == "source_conflict":
                            reasons.append("COLLECTOR_VS_OFFICIAL_OBSERVATION_CONFLICT")
                        if not observations:
                            reasons.append("NO_PRE_EVENT_GAME_OBSERVATIONS")
                        counts["primary_history_retrieved"] += 1
                        if checked["status"] == "independently_correlated":
                            counts["collector_history_correlated"] += 1
        # Structured observations never silently fulfill line matching, goalie
        # quality, pace, opponent schemes or the reviewer-read checklist.
        reasons.append("UNVERIFIED_CONTEXTUAL_MATCHUP_AND_ADVERSARIAL_REVIEW")
        entry["status"] = "partial_source_research" if entry["observed_history"] else "source_research_blocked"
        counts[entry["status"]] += 1
        entries.append(entry)
    attempts = list(resolution.get("attempts") or [])
    attempts += [a for e in entries for a in e["source_attempts"]]
    report = {
        "schema": VERSION, "date": date, "phase": phase,
        "generated_at": now.isoformat(), "source_forecast_run_id": run_id,
        "original_forecast_count": batch_count, "selected_candidates": len(entries),
        "not_selected": dict(exclusions), "source_calls_attempted": len(attempts),
        "official_event_checks": len(resolution.get("verified_pregame_games") or []),
        "confirmed_active_subjects": sum(1 for item,_ in selected
                                         if status_verified(updated, item, now)[0]),
        "counts": dict(counts), "attempts": attempts, "candidates": entries,
        "research_complete": False, "publication_eligible": False,
        "verification_gate": "requires independent contextual/qualitative "
                             "scouting plus adversarial review; machine observations "
                             "are NOT reviewer attestations",
        "prop_line_requests": 0,
    }
    # This section is outside the scoring packet schema: never mark
    # scouting facts confirmed merely because a source URL was reachable.
    updated["_autonomous_investigation"] = {
        "schema": VERSION, "generated_at": now.isoformat(),
        "candidate_summaries": {e["candidate_id"]: {
            "forecast_sha256": e["forecast_sha256"],
            "source": (e["observed_history"] or {}).get("source_url"),
            "supporting_game_count": len(e["supporting_evidence"]),
            "opposing_game_count": len(e["opposing_evidence"]),
            "blockers": e["blockers"]}
            for e in entries},
        "research_complete": False, "promotion_authorized": False}
    return report, updated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--snapshots", default="data/prop_snapshots.jsonl")
    parser.add_argument("--queue", default="reports/research_triage.json")
    parser.add_argument("--packet", help="Input research packet, never a guessed file")
    parser.add_argument("--out", default="reports/autonomous_investigation.json")
    parser.add_argument("--phase", choices=("initial", "recheck"), default="initial")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--now", help="Test-only timestamp")
    args = parser.parse_args(argv)
    now = utc_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        parser.error("invalid aware timestamp")
    packet_path = Path(args.packet or f"data/research_{args.date}.json")
    rows = [json.loads(line) for line in Path(args.snapshots).read_text().splitlines() if line.strip()]
    queue = json.loads(Path(args.queue).read_text())
    packet = json.loads(packet_path.read_text())
    report, updated = investigate(rows, queue, packet, args.date, now=now,
                                  limit=args.limit, phase=args.phase,
                                  data_root=Path(args.data_root))
    write_atomic(args.out, report)
    # Snapshot is untouched. Current research packet gains only machine
    # observations and independently rechecked official status facts.
    write_atomic(packet_path, updated)
    print(json.dumps({"date": args.date, "status": "investigated",
                      "selected": report["selected_candidates"],
                      "counts": report["counts"], "source_attempts": report["source_calls_attempted"],
                      "research_complete": False, "publication_eligible": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
