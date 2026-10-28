"""Verified *historical* team-roster continuity, never today's lineup confirmation.

The last 3-5 completed team games provide an auditable tendency signal only.
The source-owned lineup collector must have complete game-active rosters and
full same-day collection coverage. No unlisted injuries become "healthy".
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from shared_context import history_path, validate_history
from usage_baseline import local_day, using_directory


def tendency_path(root, sport, team, stat, game_date):
    from usage_baseline import source_stat
    digest = hashlib.sha256(json.dumps(
        [sport, team, source_stat(stat)], separators=(",", ":")).encode()).hexdigest()
    return Path(root) / "verification" / game_date / "tendencies" / (digest + ".json")


VERSION = "participation-tendency-v1"
NEGATIVE = {"out", "doubtful"}
AMBIGUOUS = {"questionable", "day-to-day"}


def evaluate(candidate, now, *, root="data", packet=None):
    """Return a source-backed historical indicator; never an active declaration."""
    if now.tzinfo is None:
        raise ValueError("lineup tendency needs a timezone-aware evaluation clock")
    now = now.astimezone(timezone.utc)
    result = {"version": VERSION, "status": "unknown", "likely_available": False,
              "confirmed_active": False, "starting_role_confirmed": False,
              "usable_for_verified_tier": False, "sample": 0, "played_last_5": None,
              "label": "No complete same-day team lineup evidence"}
    sport, stat, team = (candidate.get(k) for k in ("sport", "stat", "team"))
    player_id = str(candidate.get("player_id") or "")
    game_date = candidate.get("game_date")
    if sport not in ("NBA", "NHL", "NFL") or not player_id or not game_date or not team:
        result["reason"] = "INCOMPLETE_SUBJECT_IDENTITY"
        return result
    if sport == "NHL" and stat in ("saves", "goalie saves"):
        result.update(status="starter_unknown", reason="NHL_GOALIE_START_REQUIRES_GAME_DAY_PROOF")
        return result
    # NFL lineups use GSIS IDs; never equate an ESPN numeric ID with a GSIS ID.
    if sport == "NFL" and not player_id.startswith("00-"):
        result["reason"] = "NFL_GSIS_PLAYER_ID_BRIDGE_MISSING"
        return result
    try:
        event = local_day(game_date)
        if now.astimezone(ZoneInfo('America/Toronto')).date() != event:
            result["reason"] = "WRONG_SLATE_DATE"
            return result
        with using_directory(root):
            path = tendency_path(root, sport, team, stat, game_date)
            if not path.is_file():
                path = history_path(sport, team, stat)
            history = json.loads(path.read_text(encoding="utf-8"))
        if history.get("sport") != sport or history.get("team") != team:
            raise ValueError("team identity does not match history")
        from usage_baseline import source_stat
        if source_stat(history.get("stat")) != source_stat(stat):
            raise ValueError("stat identity does not match history")
        validate_history(history)
        stamp = datetime.fromisoformat(str(history["retrieved_at"]).replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp > now or (now-stamp).total_seconds() > 86400:
            result["reason"] = "SOURCE_HISTORY_NOT_REFRESHED_TODAY"
            return result
        collection = history.get("collection") or {}
        # History must cover each of the team's recent completed games.
        if (collection.get("errors") or
                not isinstance(collection.get("discovered"), int) or
                not isinstance(collection.get("completed"), int) or
                collection["discovered"] != collection["completed"] or
                collection["completed"] < 5):
            result["reason"] = "INCOMPLETE_TEAM_GAME_COVERAGE"
            return result
        games = [g for g in history["games"] if local_day(g["date"]) < event]
        games.sort(key=lambda g: (local_day(g["date"]), str(g["id"])), reverse=True)
        last = games[:5]
        if len(last) < 5:
            result["reason"] = "FEWER_THAN_FIVE_VERIFIED_TEAM_GAMES"
            return result
        maximum_age = 21 if sport == "NFL" else 11
        if (event - local_day(last[0]["date"])).days > maximum_age:
            result["reason"] = "RECENT_TEAM_SCHEDULE_NOT_COVERED"
            return result
        if len({str(g["id"]) for g in last}) != 5:
            raise ValueError("non-unique recent game ids")
        appearances = [str(player_id) in g["active_players"] for g in last]
        count = sum(appearances)
        digest = hashlib.sha256(json.dumps(
            [dict(id=g["id"],date=g["date"],roster=g["active_players"],
                  url=g["source_url"]) for g in last],
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        result.update(sample=5, played_last_5=count, team_game_ids=[g["id"] for g in last],
                      last_five_results=appearances,
                      source_urls=[g["source_url"] for g in last],
                      source_snapshot_sha256=digest, observed_at=stamp.isoformat(),
                      label="Last five verified team game-active rosters")
        if count < 4 or not all(appearances[:3]):
            result.update(status="low_continuity", reason="RECENT_TEAM_GAME_ABSENCES")
        elif count == 4:
            result.update(status="moderate_continuity", reason="ONE_TEAM_GAME_ABSENCE")
        else:
            # Five previous active rosters is historical continuity, not a
            # statistically calibrated probability or game-day active flag.
            result.update(status="high_continuity", likely_available=True,
                          reason="FIVE_PREVIOUS_TEAM_ROSTER_APPEARANCES")
        # Strictly sourced negative injury status vetoes this tendency.
        availability = ((packet or {}).get("availability") or {}).get(candidate.get("player")) or {}
        status = availability.get("status") or {}
        if isinstance(status, dict):
            value = status.get("value")
            if value in NEGATIVE:
                result.update(status="negative_current_report", likely_available=False,
                              reason="EXPLICIT_GAME_DAY_OUT_OR_DOUBTFUL")
            elif value in AMBIGUOUS:
                result.update(status="uncertain_injury", likely_available=False,
                              reason="CURRENT_QUESTIONABLE_INJURY")
        if any(c.get("resolution") == "unresolved" and
               c.get("player") in (candidate.get("player"), sport + "|" + player_id)
               for c in (packet or {}).get("_source_conflicts") or []
               if isinstance(c, dict)):
            result.update(status="conflicting_sources", likely_available=False,
                          reason="UNRESOLVED_PLAYER_STATUS_CONFLICT")
        return result
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        result["reason"] = "LINEUP_TENDENCY_SOURCE_UNAVAILABLE_OR_INVALID"
        result["detail"] = type(exc).__name__
        return result
