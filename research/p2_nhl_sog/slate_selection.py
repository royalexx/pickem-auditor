"""Frozen research eligibility based on the five latest completed club games."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import Future
from datetime import timedelta
from pathlib import Path
from statistics import median
from threading import Lock
import unicodedata

from scripts.c03_live_transport import capture_signed_live, verify_signed_capture
from v2.official_nba_nhl_capture import nhl_stat_rows, normalized_team

from .official_transport import USER_AGENT
from .source_pipeline import (
    OFFICIAL, ROOT_NAMESPACE, SourceBlocked, canonical_bytes, capture_official,
    clock, digest, require, put_once,
)

POLICY = "nhl-sog-slate-once-v2"
INJURIES = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"
FINAL_STATES = {"FINAL", "OFF"}
DECISION_PATH = ROOT_NAMESPACE + "/slate_selection/"
ESPN_TO_NHL = {"LA": "LAK", "NJ": "NJD", "SJ": "SJS", "TB": "TBL",
              "VEG": "VGK", "VGS": "VGK", "UTAH": "UTA"}


def _name(value):
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in value if char.isalnum())


def injury_index(document, teams):
    """Treat every listed injury as a conflict and fail closed on identity gaps."""
    groups = document["injuries"]
    require(isinstance(groups, list) and bool(groups), "INJURY_FEED_EMPTY_OR_INVALID")
    result = {team: set() for team in teams}
    matched = set()
    for group in groups:
        identifier = str(group.get("id") or "")
        injuries = group["injuries"]
        require(identifier.isdigit() and isinstance(injuries, list) and injuries,
                "INJURY_FEED_TEAM_IDENTITY_UNCERTAIN")
        clubs = [injury["athlete"]["team"] for injury in injuries]
        abbreviations = {club["abbreviation"].upper() for club in clubs}
        abbreviations = {ESPN_TO_NHL.get(short, short) for short in abbreviations}
        if not abbreviations.intersection(result):
            continue
        require(len(abbreviations) == 1 and all(str(club["id"]) == identifier for club in clubs),
                "INJURY_FEED_TEAM_IDENTITY_UNCERTAIN")
        team = abbreviations.pop()
        require(team not in matched, "INJURY_FEED_DUPLICATE_TEAM")
        matched.add(team)
        for injury in injuries:
            name = _name(injury["athlete"]["displayName"])
            require(bool(name), "INJURY_FEED_PLAYER_NAME_MISSING")
            result[team].add(name)
    return result


def recent_games(document, team, freeze):
    games = document["games"]
    require(isinstance(games, list), "RECENT_TEAM_SCHEDULE_INVALID")
    finals = [g for g in games if g.get("gameState") in FINAL_STATES
              and clock(g["startTimeUTC"]) < clock(freeze)]
    finals.sort(key=lambda g: clock(g["startTimeUTC"]), reverse=True)
    recent = finals[:5]
    require(len(recent) == 5 and len({g["id"] for g in recent}) == 5,
            "FIVE_RECENT_TEAM_FINALS_REQUIRED")
    require(clock(freeze) - clock(recent[0]["startTimeUTC"]) <= timedelta(days=7),
            "RECENT_TEAM_FINAL_TOO_OLD")
    for game in recent:
        require(team in {game["awayTeam"]["abbrev"], game["homeTeam"]["abbrev"]},
                "RECENT_SCHEDULE_TEAM_MISMATCH")
    return recent


def decisions(members, roster_document, injuries, recent):
    names = {}
    for group in ("forwards", "defensemen", "goalies"):
        for player in roster_document[group]:
            name = _name(player["firstName"]["default"] + " " + player["lastName"]["default"])
            require(bool(name), "CURRENT_ROSTER_NAME_MISSING")
            names[str(player["id"])] = name
    name_counts = Counter(names.values())
    # An unmatched reported injury might be an alias for a rostered player.
    require(injuries <= set(names.values()), "INJURY_NAME_CROSSWALK_UNRESOLVED")
    result = {}
    for pid, member in members.items():
        if member["position_group"] not in {"F", "D"}:
            continue
        played = [game[pid]["observed_workload_minutes"] for game in recent if pid in game]
        reason = None
        if name_counts[names[pid]] > 1:
            reason = "ROSTER_NAME_IDENTITY_AMBIGUOUS"
        elif names[pid] in injuries:
            reason = "PREGAME_INJURY_STATUS_CONFLICT"
        elif len(played) < 4 or pid not in recent[0]:
            reason = "RECENT_DRESSING_UNCERTAIN"
        elif (median(played) < (8 if member["position_group"] == "F" else 12)
              or max(played) - min(played) > 8):
            reason = "RECENT_WORKLOAD_UNCERTAIN"
        result[pid] = {"team_id": member["team_id"], "games_played_of_five": len(played),
                       "recent_median_toi_minutes": median(played) if played else None,
                       "reason": reason}
    return result


class SlateSelection:
    """One owner archives selection inputs and shares identical captures."""

    def __init__(self, root, day, freeze, first_start):
        self.root = root
        self.lock = Lock()
        self.sources = {}
        self.injuries = None
        self.injury_error = None
        archive = Path(root) / ROOT_NAMESPACE / "c03"
        try:
            receipt = capture_signed_live(INJURIES, archive_root=archive, source_namespace="espn",
                                          source_id="espn:nhl:injuries:" + day,
                                          input_cutoff_at=freeze, event_start_at=first_start,
                                          user_agent=USER_AGENT)
            document = verify_signed_capture(receipt, archive_root=archive,
                                             freeze=freeze, event_start=first_start)
            self.injuries = receipt, document
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.injury_error = str(exc)[:160]

    def _nhl(self, route, kind, *, freeze, start):
        with self.lock:
            pending = self.sources.get(route)
            owner = pending is None
            if owner:
                pending = self.sources[route] = Future()
        if owner:
            try:
                pending.set_result(capture_official(
                    self.root, OFFICIAL + route, event_start_at=start,
                    input_freeze_at=freeze, source_kind=kind, source_id="nhl:" + route))
            except BaseException as exc:
                with self.lock:
                    self.sources.pop(route)
                pending.set_exception(exc)
        source = pending.result()
        require(clock(source["c03_receipt"]["received_at"]) <= clock(freeze),
                "RECENT_SOURCE_AFTER_GAME_FREEZE")
        return source

    def __call__(self, game, rosters, members, *, freeze):
        rows, evidence = {}, {}
        teams = (game["home_team"], game["away_team"])
        try:
            require(self.injuries is not None, "PREGAME_INJURY_SOURCE_UNAVAILABLE")
            injury_receipt, injury_document = self.injuries
            require(clock(injury_receipt["received_at"]) <= clock(freeze), "INJURY_SOURCE_AFTER_GAME_FREEZE")
            injuries = injury_index(injury_document, teams)
            injury_error = None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            injury_receipt = self.injuries[0] if self.injuries else None
            injury_error = str(exc)[:160]
        for team in teams:
            refs = []
            try:
                require(injury_error is None, injury_error)
                schedule = self._nhl(f"/club-schedule-season/{team}/{game['official_season']}",
                                     "nhl_recent_team_schedule", freeze=freeze, start=game["start_at"])
                refs.append(schedule["c03_receipt"])
                appearances = []
                for prior in recent_games(schedule["document"], team, freeze):
                    require(str(prior["id"]) != game["event_id"], "TARGET_IN_RECENT_HISTORY")
                    src = self._nhl(f"/gamecenter/{prior['id']}/boxscore", "nhl_recent_final",
                                    freeze=freeze, start=game["start_at"])
                    refs.append(src["c03_receipt"])
                    doc = src["document"]
                    require(doc["id"] == prior["id"] and all(
                        doc[side]["abbrev"] == prior[side]["abbrev"] for side in ("awayTeam", "homeTeam")
                    ), "RECENT_FINAL_IDENTITY_MISMATCH")
                    stats = nhl_stat_rows(doc, expected_teams={
                        normalized_team(prior[side]["abbrev"], "NHL") for side in ("awayTeam", "homeTeam")})
                    appearances.append({pid: row for pid, row in stats.items()
                                        if row["team"] == normalized_team(team, "NHL")})
                decisions_for_team = decisions(members[team], rosters[team]["document"],
                                               injuries[team], appearances)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                decisions_for_team = {pid: {"team_id": team, "reason": str(exc)[:160]}
                                      for pid, row in members[team].items()
                                      if row["position_group"] in {"F", "D"}}
            evidence[team] = refs
            rows.update(decisions_for_team)
        report = {"policy": POLICY, "event_id": game["event_id"], "input_freeze_at": freeze,
                  "skaters": rows, "team_evidence": evidence, "injury_receipt": injury_receipt,
                  "injury_error": self.injury_error or injury_error, "research_only": True}
        raw = canonical_bytes(report)
        return rows, put_once(self.root, DECISION_PATH + digest(raw) + ".json", raw)["sha256"]
