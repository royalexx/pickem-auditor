"""Fetch structured slate numbers for the pickem-auditor skill.

Stdlib plus nhl-api-py for NHL, nflreadpy for NFL, ESPN public JSON for the
NBA schedule and player counting stats, and nba_api LeagueDashTeamStats for
NBA team pace. Player props come from odds_providers.py. That module reads
PROPLINE_API_KEY and does not invent a price when the key is missing.
No HTML scraping. No hand-downloaded nflverse CSVs. No Underdog
lines, payouts, or entry slips. This file does not grade and does not
compute a probability. pickem_math.py is the only calculator.

A run with zero rows does not overwrite --out. It writes <out>.failed.json
and exits 2. Output is replaced through a temp file. Two-sided quotes are
written to odds_quotes.jsonl beside --out, one per book per player-stat-line.
--preflight checks imports and HTTPS reachability and does not write the slate file.

Game logs, one per player on the slate:

- NHL: ``https://api-web.nhle.com/v1/player/{id}/game-log/{season}/2``
- NBA: the ESPN athlete gamelog for that season
- NFL: the week-level ``load_player_stats`` frame already loaded, with snaps
  as the workload

``baseline_mean`` stays the mixed season rate. The log adds ``season_n``,
``season_mean``, last-5 and last-10 means, ``sample_variance``, ``sd``,
``var_ratio``, ``zero_rate``, the role-stable window, hit counts versus the
quoted line, and non-overlapping ``baseline_window_mean`` / ``baseline_n`` /
``recent_mean`` / ``recent_n`` (``baseline_n + recent_n <= season_n``).
``suggested_dist`` follows the helper table: poisson when ``var_ratio`` is
1.10 or less, negbin otherwise, and normal for yards, points, combos, and
saves. A missing log leaves those fields null and sets ``log_missing``.
Nothing is imputed. ``workload_tonight`` stays null unless a source gives it.
``prep --stdout`` joins the slate to ``odds_quotes.jsonl`` and prints one
pipeline object per player, stat, and side.

Flag rules use numbers in references/slate_fetch.md and references/workflow_stages.md:

- Pace is well above league when team pace / league pace is above the pace
  clamp, 1.10. Channel: pace.
- Shots against are well above league when that rate / the league rate is
  above the opponent clamp, 1.15. Channel: opponent environment.
- A snap share at or above 0.80 is large because the Stage G thin band for
  tackles snaps stops at 79%. That flag is not a funnel channel.
- `snap_share` is the average of `offense_pct` or `defense_pct`. That is the
  share of snaps, not where the snap was taken. Snap-count columns, when
  present, are stored as snaps per game. There is no alignment average.
- Teammate deployment comes from week-level player stats: the player's rate
  in games a teammate played versus games that teammate missed. Each side
  needs at least 5 games. A routes or route-share average is stored only
  when that numeric column is present. The fetch does not invent a tonight
  workload or a workload ratio.
- Progression reads come from load_ftn_charting joined to load_pbp on
  nflverse_game_id = game_id and nflverse_play_id = play_id. read_thrown
  0 and DES are first read, CHK is checkdown, and 1, 2, and SD are
  secondary. A share can become a multiplier only when the player's target
  games and the team's read games in that bucket are each at least 5.
  Otherwise the share is stored and the multiplier is null. Missing
  charting or a failed join omits the features. baseline_mean is unchanged.
- Defensive rates use that same join, aggregated by defteam on pass attempts.
  A defense under 150 dropbacks is shrunk toward the league mean before the
  ratio. The matchup factor is the checkdown ratio times the suppression
  ratio, then the opponent clamp 0.85-1.15. It is the same for every pass
  catcher and passer. Missing charting omits the factor.
- abs(baseline mean - fetched line) uses the Stage D distances: 0.5 counting,
  2.0 NBA points or a combo, 8 receiving or rushing yards, 15 passing yards.
  A line gap is not a funnel channel.
- Target share is stored. The skill has no target-share cutoff, so none is
  invented.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import random
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from odds_providers import (
    PropLineProvider,
    consensus_input as build_consensus_input,
    ordered_quotes,
    primary_price,
    quotes_for_row,
    redact,
    resolve_quote_teams,
    unmatched_note,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = SKILL_ROOT / "data" / "slate_fetch.jsonl"
NHL_WEB = "https://api-web.nhle.com/v1"
NHL_STATS_SKATER = "https://api.nhle.com/stats/rest/en/skater/summary"
NHL_STATS_GOALIE = "https://api.nhle.com/stats/rest/en/goalie/summary"
ESPN_TIMEOUT = 15
NBA_PACE_TIMEOUT = 20
FETCH_ATTEMPTS = 3
# Three attempts. A retryable failure waits 1s, then 2s, plus jitter.
# 4s is the next step in the series and is not slept after the final attempt.
FETCH_BACKOFF_SECONDS = (1.0, 2.0, 4.0)
FETCH_JITTER_SECONDS = 0.25
PREFLIGHT_TIMEOUT = 8.0
FEED_NAMES = ("nhl", "nfl", "nba", "odds")
PREFLIGHT_IMPORTS = (
    ("nflreadpy", "nfl"),
    ("polars", "nfl"),
    ("nhlpy", "nhl"),
    ("nba_api", "nba"),
)
# host, feed, label. github.com is the nflverse host nflreadpy reads from.
PREFLIGHT_HOSTS = (
    ("api-web.nhle.com", "nhl", "api-web.nhle.com"),
    ("api.nhle.com", "nhl", "api.nhle.com"),
    ("site.api.espn.com", "nba", "site.api.espn.com"),
    ("site.web.api.espn.com", "nba", "site.web.api.espn.com"),
    ("github.com", "nfl", "github.com (nflverse)"),
    ("stats.nba.com", "nba", "stats.nba.com"),
    ("api.prop-line.com", "odds", "api.prop-line.com"),
)
# Root pages often return 403/404 despite healthy data APIs.
PREFLIGHT_URLS = {
    "api-web.nhle.com": "https://api-web.nhle.com/v1/schedule/now",
    "api.nhle.com": "https://api.nhle.com/stats/rest/en/team?limit=1",
    "site.api.espn.com": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "site.web.api.espn.com": "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete?limit=1",
    "github.com": "https://github.com/nflverse/nflverse-data",
    "api.prop-line.com": "https://api.prop-line.com/v1/freshness",
}
NFL_SOURCE = "nflreadpy.load_player_stats"
NBA_SOURCE = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard?dates={compact}"
# ESPN scoreboard and byathlete abbreviations that are not the
# LeagueDashTeamStats TEAM_ABBREVIATION. Pace is joined on the nba_api code.
ESPN_NBA_ABBREV = {
    "GS": "GSW",
    "NO": "NOP",
    "NY": "NYK",
    "SA": "SAS",
    "UTAH": "UTA",
    "WSH": "WAS",
}
# Season averages present on the live statistics/byathlete categories payload.
# general names include gamesPlayed, avgMinutes, avgRebounds.
# offensive names include avgPoints, avgAssists, avgThreePointFieldGoalsMade.
# Those avg* values are already per game. Totals in the same arrays are not used.
NBA_COUNTING_FIELDS = (
    ("points", "offensive", "avgPoints"),
    ("rebounds", "general", "avgRebounds"),
    ("assists", "offensive", "avgAssists"),
    ("threes", "offensive", "avgThreePointFieldGoalsMade"),
)
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

PACE_CLAMP_HIGH = 1.10
OPPONENT_CLAMP_HIGH = 1.15
LARGE_SNAP_SHARE = 0.80
SPLIT_MIN_GAMES = 5
# A numeric column on the player stat file can be averaged. The participation
# `route` string, slot/wide/inline alignment, and play-level charting fields
# are not in this map.
DEPLOYMENT_AVERAGE_COLUMNS = {
    "routes": "routes_per_game",
    "route_share": "route_share",
}
# Confirmed on the 2026 load_ftn_charting frame. Those six codes are the
# whole read_thrown column. Charting is not an alignment source.
READ_BUCKETS = {
    "first_read": frozenset({"0"}),
    "checkdown": frozenset({"CHK"}),
    "secondary_read": frozenset({"1", "2"}),
    "designed": frozenset({"DES"}),
    "scramble_drill": frozenset({"SD"}),
}
FTN_READ_COLUMNS = ("nflverse_game_id", "nflverse_play_id", "read_thrown", "week", "season")
PBP_READ_COLUMNS = (
    "game_id",
    "play_id",
    "posteam",
    "season_type",
    "qb_dropback",
    "pass_attempt",
    "sack",
    "receiver_player_id",
    "receiver_player_name",
    "passer_player_id",
    "passer_player_name",
    "defteam",
    "air_yards",
)
PASSING_STATS = {"pass attempts", "passing yards", "completions"}
# Same bounds as pickem_math OPPONENT_CLAMP. The helper still clamps on the way in.
OPPONENT_FACTOR_CLAMP = (0.85, 1.15)
SHRINK_DROPBACKS = 150
PASS_MATCHUP_POSITIONS = {"WR", "TE", "RB", "QB"}
LINE_COUNTING = 0.5
LINE_NBA_POINTS = 2.0
LINE_REC_RUSH_YARDS = 8.0
LINE_PASS_YARDS = 15.0

NBA_POINT_STATS = {"points", "pra", "pr", "pa", "ra"}
REC_RUSH_YARDS = {"receiving yards", "rushing yards"}
PASS_YARDS = {"passing yards"}

# Same 1.10 cut the math helper uses. This module does not grade.
LOG_VAR_RATIO_POISSON = 1.10
ROLE_BAND = 0.20
RECENT_LONG = 10
RECENT_SHORT = 5
MIN_WINDOW_SIDE = 5
PRIOR_GAME_CAP = 20
SHORT_SEASON_GAMES = 20
LOG_COUNT_STATS = {
    "shots on goal",
    "blocked shots",
    "hits",
    "rebounds",
    "assists",
    "threes",
    "receptions",
    "rush attempts",
    "tackles + assists",
}
LOG_NORMAL_STATS = {
    "points",
    "pra",
    "pr",
    "pa",
    "ra",
    "receiving yards",
    "rushing yards",
    "passing yards",
    "pass attempts",
    "completions",
    "goalie saves",
}
NBA_GAMELOG = (
    "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/"
    "athletes/{athlete_id}/gamelog?season={season}"
)
NBA_LOG_KEYS = {
    "points": "points",
    "rebounds": "rebounds",
    "assists": "assists",
    "threes": "threes",
}
NBA_COMBOS = {
    "pra": ("points", "rebounds", "assists"),
    "pr": ("points", "rebounds"),
    "pa": ("points", "assists"),
    "ra": ("rebounds", "assists"),
}
NFL_DEFENSE_STATS = {"tackles + assists"}
LOG_FIELDS = (
    "season_n",
    "season_mean",
    "last_5_mean",
    "last_10_mean",
    "sample_variance",
    "sd",
    "var_ratio",
    "zero_rate",
    "role_stable_n",
    "role_stable_mean",
    "baseline_n",
    "baseline_window_mean",
    "recent_mean",
    "recent_n",
    "suggested_dist",
    "baseline_workload",
    "workload_tonight",
    "prior_season_mean",
    "prior_n",
    "hits_over",
    "hits_under",
    "pushes",
    "hit_n",
    "stat_log",
)

NFL_COUNTING = (
    ("receptions", "receptions"),
    ("receiving yards", "receiving_yards"),
    ("rushing yards", "rushing_yards"),
    ("rush attempts", "carries"),
    ("passing yards", "passing_yards"),
    ("pass attempts", "attempts"),
    ("completions", "completions"),
)


def eastern_today() -> str:
    return datetime.now(ZoneInfo("America/New_York")).date().isoformat()


def season_id_from_date(game_date: str) -> str:
    year, month, _day = (int(part) for part in game_date.split("-"))
    start = year if month >= 9 else year - 1
    return f"{start}{start + 1}"


def nfl_season_from_date(game_date: str) -> str:
    year, month, _day = (int(part) for part in game_date.split("-"))
    return str(year if month >= 3 else year - 1)


def nba_season_from_date(game_date: str) -> str:
    year, month, _day = (int(part) for part in game_date.split("-"))
    start = year if month >= 8 else year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def nba_espn_season_year(game_date: str) -> int:
    """ESPN season query is the year that season ends. 2026-10-22 is 2027."""
    return int(nba_season_from_date(game_date).split("-")[0]) + 1


def utc_now() -> str:
    return datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _round(value):
    if value is None:
        return None
    return round(float(value), 6)


def person_name(raw: dict) -> str:
    for key in ("skaterFullName", "goalieFullName", "player_display_name", "PLAYER_NAME"):
        if raw.get(key):
            return str(raw[key]).strip()
    first = raw.get("firstName") or {}
    last = raw.get("lastName") or {}
    if isinstance(first, dict):
        first = first.get("default") or ""
    if isinstance(last, dict):
        last = last.get("default") or ""
    return f"{first} {last}".strip()


def parse_toi_seconds(value):
    """NHL ice time as seconds. Accepts seconds or a clock string."""
    number = _num(value)
    if number is not None and not isinstance(value, str):
        return number
    if isinstance(value, str) and ":" in value:
        parts = value.split(":")
        try:
            nums = [float(part) for part in parts]
        except ValueError:
            return number
        if len(nums) == 2:
            return nums[0] * 60 + nums[1]
        if len(nums) == 3:
            return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return number


def mean(values) -> float | None:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return sum(usable) / len(usable)


def ratio(value, baseline) -> float | None:
    if value is None or baseline is None or baseline == 0:
        return None
    return value / baseline


def line_gap_is_serious(stat: str, baseline_mean, line) -> bool:
    if baseline_mean is None or line is None:
        return False
    gap = abs(float(baseline_mean) - float(line))
    name = stat.strip().lower()
    if name in PASS_YARDS:
        return gap >= LINE_PASS_YARDS
    if name in REC_RUSH_YARDS:
        return gap >= LINE_REC_RUSH_YARDS
    if name in NBA_POINT_STATS:
        return gap >= LINE_NBA_POINTS
    return gap >= LINE_COUNTING


def serious_flag(stat: str, baseline_mean, line, pace_ratio, shots_against_ratio, snap_share) -> dict:
    """Return flag, channel, and reasons.

    Channel is pace or opponent environment only for those rate rules.
    A large snap share and a line gap set flag without becoming a channel.
    When pace and shots-against are both extreme, both reasons are kept and
    channel is pace. The shots-against reason is still the opponent channel.
    """
    reasons = []
    if pace_ratio is not None and pace_ratio > PACE_CLAMP_HIGH:
        reasons.append("pace_above_league")
    if shots_against_ratio is not None and shots_against_ratio > OPPONENT_CLAMP_HIGH:
        reasons.append("shots_against_above_league")
    if snap_share is not None and snap_share >= LARGE_SNAP_SHARE:
        reasons.append("large_snap_share")
    if line_gap_is_serious(stat, baseline_mean, line):
        reasons.append("line_gap")
    channel = None
    if "pace_above_league" in reasons:
        channel = "pace"
    elif "shots_against_above_league" in reasons:
        channel = "opponent environment"
    return {"flag": bool(reasons), "channel": channel, "flag_reasons": reasons}


def choose_funnel_rate(candidates: list[tuple[str, float | None]]) -> tuple[str | None, float | None]:
    for name, value in candidates:
        if value is None:
            continue
        if name in {"target_share", "snap_share", "epa"} and value == 0:
            continue
        return name, value
    return None, None


def make_row(
    *,
    sport: str,
    game_date: str,
    player: str,
    team: str,
    opponent: str,
    stat: str,
    baseline_mean: float,
    sample_size: float,
    source_url: str,
    retrieved_at: str,
    pace_per_game=None,
    pace_ratio=None,
    shots_against_per_game=None,
    shots_against_ratio=None,
    epa=None,
    target_share=None,
    snap_share=None,
    ice_time_per_game=None,
    games_started=None,
    minutes=None,
    possessions=None,
    line=None,
    book=None,
    over_odds=None,
    under_odds=None,
) -> dict:
    rate_name, rate_value = choose_funnel_rate(
        [
            ("target_share", target_share),
            ("snap_share", snap_share),
            ("shots_against", shots_against_per_game),
            ("epa", epa),
            ("pace", pace_per_game),
        ]
    )
    decision = serious_flag(stat, baseline_mean, line, pace_ratio, shots_against_ratio, snap_share)
    row = {
        "sport": sport,
        "game_date": game_date,
        "player": player,
        "team": team,
        "opponent": opponent,
        "stat": stat,
        "baseline_mean": _round(baseline_mean),
        "sample_size": _round(sample_size),
        "funnel_rate": _round(rate_value),
        "funnel_rate_name": rate_name,
        "source_url": source_url,
        "retrieved_at": retrieved_at,
        "book": book,
        "line": _round(line) if line is not None else None,
        "over_odds": _round(over_odds) if over_odds is not None else None,
        "under_odds": _round(under_odds) if under_odds is not None else None,
        "flag": decision["flag"],
        "channel": decision["channel"],
        "flag_reasons": decision["flag_reasons"],
        "pace_per_game": _round(pace_per_game),
        "pace_ratio": _round(pace_ratio),
        "shots_against_per_game": _round(shots_against_per_game),
        "shots_against_ratio": _round(shots_against_ratio),
        "epa": _round(epa),
        "target_share": _round(target_share),
        "snap_share": _round(snap_share),
        "ice_time_per_game": _round(ice_time_per_game),
        "games_started": _round(games_started),
        "minutes": _round(minutes),
        "possessions": _round(possessions),
    }
    _blank_log_fields(row)
    return row


def games_from_schedule(payload: dict | None, game_date: str) -> list[dict]:
    if not payload:
        return []
    if payload.get("date") == game_date and "games" in payload:
        return list(payload.get("games") or [])
    games = []
    for day in payload.get("gameWeek") or []:
        if day.get("date") == game_date:
            games.extend(day.get("games") or [])
    return games


def slate_matchups(games: list[dict]) -> dict[str, str]:
    """Team abbrev -> opponent abbrev for the games on the slate."""
    matchups = {}
    for game in games:
        away = (game.get("awayTeam") or {}).get("abbrev")
        home = (game.get("homeTeam") or {}).get("abbrev")
        if away and home:
            matchups.setdefault(away, home)
            matchups.setdefault(home, away)
    return matchups


def team_abbrev_lookup(games: list[dict]) -> dict:
    lookup = {}
    for game in games:
        for side in ("awayTeam", "homeTeam"):
            team = game.get(side) or {}
            abbrev = team.get("abbrev")
            if not abbrev:
                continue
            if team.get("id") is not None:
                lookup[("id", int(team["id"]))] = abbrev
            place = team.get("placeName") or ""
            common = team.get("commonName") or ""
            full = f"{place} {common}".strip()
            if full:
                lookup[("name", full)] = abbrev
    return lookup


def abbrev_on_slate(team_abbrevs: str | None, slate: dict[str, str]) -> str | None:
    if not team_abbrevs:
        return None
    parts = [part.strip() for part in str(team_abbrevs).split(",") if part.strip()]
    for part in parts:
        if part in slate:
            return part
    return None


def index_team_rates(teams: list[dict], lookup: dict) -> dict[str, dict]:
    indexed = {}
    for team in teams:
        abbrev = None
        if team.get("teamId") is not None and ("id", int(team["teamId"])) in lookup:
            abbrev = lookup[("id", int(team["teamId"]))]
        if abbrev is None and team.get("teamFullName"):
            abbrev = lookup.get(("name", team["teamFullName"]))
        if abbrev is None and team.get("abbrev"):
            abbrev = team["abbrev"]
        if not abbrev:
            continue
        indexed[abbrev] = {
            "shots_for_per_game": _num(team.get("shotsForPerGame")),
            "shots_against_per_game": _num(team.get("shotsAgainstPerGame")),
            "games_played": _num(team.get("gamesPlayed")),
        }
    return indexed


def nhl_rows_from_summaries(
    games: list[dict],
    skaters: list[dict],
    goalies: list[dict],
    teams: list[dict],
    game_date: str,
    retrieved_at: str,
    source_url: str,
) -> list[dict]:
    slate = slate_matchups(games)
    lookup = team_abbrev_lookup(games)
    rates = index_team_rates(teams, lookup)
    league_for = mean([row["shots_for_per_game"] for row in rates.values()])
    league_against = mean([row["shots_against_per_game"] for row in rates.values()])
    goalie_source = NHL_STATS_GOALIE if source_url == NHL_STATS_SKATER else source_url
    rows = []
    for skater in skaters:
        team = abbrev_on_slate(skater.get("teamAbbrevs"), slate)
        if not team:
            continue
        games_played = _num(skater.get("gamesPlayed"))
        shots = _num(skater.get("shots"))
        if games_played is None or games_played <= 0 or shots is None:
            continue
        opponent = slate[team]
        own = rates.get(team) or {}
        opp = rates.get(opponent) or {}
        toi = parse_toi_seconds(skater.get("timeOnIcePerGame"))
        built = make_row(
            sport="NHL",
            game_date=game_date,
            player=person_name(skater),
            team=team,
            opponent=opponent,
            stat="shots on goal",
            baseline_mean=shots / games_played,
            sample_size=games_played,
            source_url=source_url,
            retrieved_at=retrieved_at,
            pace_per_game=own.get("shots_for_per_game"),
            pace_ratio=ratio(own.get("shots_for_per_game"), league_for),
            shots_against_per_game=opp.get("shots_against_per_game"),
            shots_against_ratio=ratio(opp.get("shots_against_per_game"), league_against),
            ice_time_per_game=(toi / 60.0) if toi is not None else None,
        )
        if skater.get("playerId") not in (None, ""):
            built["player_id"] = skater.get("playerId")
        rows.append(built)
    for goalie in goalies:
        team = abbrev_on_slate(goalie.get("teamAbbrevs"), slate)
        if not team:
            continue
        started = _num(goalie.get("gamesStarted"))
        played = _num(goalie.get("gamesPlayed"))
        sample = started if started and started > 0 else played
        saves = _num(goalie.get("saves"))
        shots_against = _num(goalie.get("shotsAgainst"))
        if sample is None or sample <= 0 or saves is None:
            continue
        own = rates.get(team) or {}
        per_game_against = shots_against / sample if shots_against is not None else own.get("shots_against_per_game")
        built = make_row(
            sport="NHL",
            game_date=game_date,
            player=person_name(goalie),
            team=team,
            opponent=slate[team],
            stat="goalie saves",
            baseline_mean=saves / sample,
            sample_size=sample,
            source_url=goalie_source,
            retrieved_at=retrieved_at,
            shots_against_per_game=per_game_against,
            shots_against_ratio=ratio(per_game_against, league_against),
            games_started=started,
        )
        if goalie.get("playerId") not in (None, ""):
            built["player_id"] = goalie.get("playerId")
        rows.append(built)
    return rows


def club_stats_to_summaries(payload: dict, abbrev: str) -> tuple[list[dict], list[dict], dict]:
    """Urllib fallback shape from /v1/club-stats/{team}/{season}/2."""
    skaters = []
    for raw in payload.get("skaters") or []:
        skaters.append(
            {
                "skaterFullName": person_name(raw),
                "playerId": raw.get("playerId"),
                "teamAbbrevs": abbrev,
                "gamesPlayed": raw.get("gamesPlayed"),
                "shots": raw.get("shots"),
                "timeOnIcePerGame": parse_toi_seconds(raw.get("avgTimeOnIcePerGame")),
            }
        )
    goalies = []
    shots_against = 0.0
    team_games = 0.0
    for raw in payload.get("goalies") or []:
        played = _num(raw.get("gamesPlayed")) or 0.0
        team_games = max(team_games, played)
        shots_against += _num(raw.get("shotsAgainst")) or 0.0
        goalies.append(
            {
                "goalieFullName": person_name(raw),
                "playerId": raw.get("playerId"),
                "teamAbbrevs": abbrev,
                "gamesPlayed": raw.get("gamesPlayed"),
                "gamesStarted": raw.get("gamesStarted"),
                "saves": raw.get("saves"),
                "shotsAgainst": raw.get("shotsAgainst"),
            }
        )
    team = {
        "abbrev": abbrev,
        "gamesPlayed": team_games or None,
        "shotsAgainstPerGame": (shots_against / team_games) if team_games else None,
        "shotsForPerGame": None,
    }
    return skaters, goalies, team


def read_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _date_text(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


def nfl_games_on(rows: list[dict], game_date: str) -> list[dict]:
    games = []
    for row in rows:
        played_on = _date_text(row.get("gameday") or row.get("game_date"))
        if played_on != game_date:
            continue
        game_type = str(row.get("game_type") or "REG").upper()
        if game_type not in {"REG", "REGULAR"}:
            continue
        away = row.get("away_team")
        home = row.get("home_team")
        if away and home:
            games.append({"away": away, "home": home, "season": str(row.get("season") or "")})
    return games


def nfl_matchups(games: list[dict]) -> dict[str, str]:
    matchups = {}
    for game in games:
        matchups.setdefault(game["away"], game["home"])
        matchups.setdefault(game["home"], game["away"])
    return matchups


def team_play_pace(snap_rows: list[dict]) -> dict[str, float]:
    snaps = {}
    games = {}
    for row in snap_rows:
        if row.get("game_type") not in (None, "", "REG"):
            continue
        team = row.get("team")
        game_id = row.get("game_id")
        offense = _num(row.get("offense_snaps"))
        if not team or not game_id or offense is None:
            continue
        snaps.setdefault(team, {})
        snaps[team][game_id] = max(snaps[team].get(game_id, 0.0), offense)
        games.setdefault(team, set()).add(game_id)
    pace = {}
    for team, by_game in snaps.items():
        if not by_game:
            continue
        pace[team] = sum(by_game.values()) / len(by_game)
    return pace


def player_snap_rates(snap_rows: list[dict]) -> dict[tuple[str, str], dict]:
    """Snap share from offense_pct or defense_pct, plus snap counts when those columns exist.

    The percentage is how many snaps the player took, not where the snap was taken.
    """
    share_sum: dict[tuple[str, str], float] = {}
    share_n: dict[tuple[str, str], int] = {}
    off_sum: dict[tuple[str, str], float] = {}
    off_n: dict[tuple[str, str], int] = {}
    def_sum: dict[tuple[str, str], float] = {}
    def_n: dict[tuple[str, str], int] = {}
    saw_offense = False
    saw_defense = False
    for row in snap_rows:
        if row.get("game_type") not in (None, "", "REG"):
            continue
        name = (row.get("player") or "").strip().lower()
        team = row.get("team") or ""
        if not name:
            continue
        key = (name, team)
        shares = [value for value in (_num(row.get("offense_pct")), _num(row.get("defense_pct"))) if value is not None]
        if shares:
            share = max(shares)
            if share > 1.5:
                share = share / 100.0
            share_sum[key] = share_sum.get(key, 0.0) + share
            share_n[key] = share_n.get(key, 0) + 1
        if "offense_snaps" in row:
            saw_offense = True
            offense = _num(row.get("offense_snaps"))
            if offense is not None:
                off_sum[key] = off_sum.get(key, 0.0) + offense
                off_n[key] = off_n.get(key, 0) + 1
        if "defense_snaps" in row:
            saw_defense = True
            defense = _num(row.get("defense_snaps"))
            if defense is not None:
                def_sum[key] = def_sum.get(key, 0.0) + defense
                def_n[key] = def_n.get(key, 0) + 1
    rates = {}
    for key in set(share_sum) | set(off_sum) | set(def_sum):
        item = {}
        if share_n.get(key):
            item["snap_share"] = share_sum[key] / share_n[key]
        if saw_offense and off_n.get(key):
            item["offense_snaps_per_game"] = off_sum[key] / off_n[key]
        if saw_defense and def_n.get(key):
            item["defense_snaps_per_game"] = def_sum[key] / def_n[key]
        if item:
            rates[key] = item
    return rates


def player_snap_share(snap_rows: list[dict]) -> dict[tuple[str, str], float]:
    return {
        key: item["snap_share"]
        for key, item in player_snap_rates(snap_rows).items()
        if "snap_share" in item
    }


def _share(value):
    number = _num(value)
    if number is None:
        return None
    if number > 1.5:
        return number / 100.0
    return number


def team_pace_from_stats(rows: list[dict]) -> dict[str, float]:
    """Plays per game from nflreadpy team stats. Does not invent a plays column."""
    totals: dict[str, list[float]] = {}
    for row in rows:
        season_type = str(row.get("season_type") or row.get("game_type") or "REG").upper()
        if season_type not in {"REG", "REGULAR"}:
            continue
        team = row.get("team") or row.get("recent_team")
        games_played = _num(row.get("games"))
        plays = None
        for key in ("plays", "off_plays", "offensive_plays", "total_plays"):
            plays = _num(row.get(key))
            if plays is not None:
                break
        if plays is None:
            attempts = _num(row.get("attempts"))
            carries = _num(row.get("carries"))
            if attempts is None and carries is None:
                continue
            plays = (attempts or 0.0) + (carries or 0.0)
        if not team or games_played is None or games_played <= 0:
            continue
        bucket = totals.setdefault(team, [0.0, 0.0])
        bucket[0] += plays
        bucket[1] += games_played
    return {team: plays / games_played for team, (plays, games_played) in totals.items() if games_played}


def deployment_average_columns(columns) -> dict[str, str]:
    """Map a present stat column to a row field.

    Only `routes` and `route_share` qualify. The participation `route` string,
    slot / wide / inline alignment, and play-level charting fields do not.
    """
    names = set(columns)
    return {
        source: dest
        for source, dest in DEPLOYMENT_AVERAGE_COLUMNS.items()
        if source in names
    }


def numeric_column(rows: list[dict] | None, column: str) -> bool:
    """True when `column` is present and every non-empty value is numeric."""
    if not rows or column not in DEPLOYMENT_AVERAGE_COLUMNS:
        return False
    present = False
    for row in rows:
        if column not in row:
            continue
        present = True
        raw = row.get(column)
        if raw is None or raw == "":
            continue
        if _num(raw) is None:
            return False
    return present


def _reg_row(row: dict) -> bool:
    raw = row.get("season_type")
    if raw in (None, ""):
        raw = row.get("game_type")
    if raw in (None, ""):
        return True
    return str(raw).upper() in {"REG", "REGULAR"}


def _game_key(row: dict) -> str | None:
    game_id = row.get("game_id")
    if game_id not in (None, ""):
        return str(game_id)
    week = row.get("week")
    if week in (None, ""):
        return None
    return f"{row.get('season') or ''}:{week}"


def _row_team(row: dict) -> str | None:
    team = row.get("team") or row.get("recent_team")
    if team in (None, ""):
        return None
    return str(team)


def _index_keys(row: dict) -> list[str]:
    keys = []
    player_id = row.get("player_id")
    if player_id not in (None, ""):
        keys.append(f"id:{player_id}")
    name = person_name(row)
    if name:
        keys.append("name:" + name.casefold())
    return keys


def index_game_log(week_rows: list[dict] | None):
    """Index regular-season week rows by team and player. None when this is not a game log."""
    if not week_rows:
        return None
    columns: set[str] = set()
    for row in week_rows:
        columns.update(row)
    if "game_id" not in columns and "week" not in columns:
        return None
    teams: dict[str, dict] = {}
    for row in week_rows:
        if not _reg_row(row):
            continue
        team = _row_team(row)
        game_key = _game_key(row)
        keys = _index_keys(row)
        if not team or not game_key or not keys:
            continue
        roster = teams.setdefault(team, {})
        player = None
        for key in keys:
            player = roster.get(key)
            if player is not None:
                break
        if player is None:
            player = {"name": person_name(row), "games": {}}
        for key in keys:
            roster[key] = player
        player["games"].setdefault(game_key, []).append(row)
    if not teams:
        return None
    return {"columns": columns, "teams": teams}


def _log_player(log, team: str, player_name: str, player_id=None):
    roster = (log or {}).get("teams", {}).get(team) or {}
    if player_id not in (None, ""):
        found = roster.get(f"id:{player_id}")
        if found is not None:
            return found
    if player_name:
        return roster.get("name:" + player_name.casefold())
    return None


def _game_stat(game_rows: list[dict], column: str | None) -> float | None:
    if column is None:
        if not any("def_tackles_solo" in row or "def_tackle_assists" in row for row in game_rows):
            return None
        total = 0.0
        for row in game_rows:
            total += (_num(row.get("def_tackles_solo")) or 0.0) + (_num(row.get("def_tackle_assists")) or 0.0)
        return total
    if not any(column in row for row in game_rows):
        return None
    total = 0.0
    for row in game_rows:
        if column not in row:
            continue
        total += _num(row.get(column)) or 0.0
    return total


def splits_from_log(log, team: str, player_name: str, column: str | None, player_id=None, min_games: int = SPLIT_MIN_GAMES):
    """Player rate with a teammate versus games that teammate missed.

    A teammate played a game when that teammate has a row for the same team and game.
    Returns None when the log or the stat column is missing, and a list otherwise.
    The list keeps a split only when each side has at least `min_games`.
    """
    if log is None:
        return None
    if column is None:
        if "def_tackles_solo" not in log["columns"] and "def_tackle_assists" not in log["columns"]:
            return None
    elif column not in log["columns"]:
        return None
    roster = log["teams"].get(team) or {}
    player = _log_player(log, team, player_name, player_id)
    if player is None:
        return []
    unique = []
    seen = set()
    for teammate in roster.values():
        marker = id(teammate)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(teammate)
    splits = []
    for teammate in unique:
        if teammate is player or not teammate.get("name"):
            continue
        with_vals = []
        without_vals = []
        for game_key, game_rows in player["games"].items():
            value = _game_stat(game_rows, column)
            if value is None:
                continue
            if game_key in teammate["games"]:
                with_vals.append(value)
            else:
                without_vals.append(value)
        if len(with_vals) < min_games or len(without_vals) < min_games:
            continue
        splits.append(
            {
                "teammate": teammate["name"],
                "with_n": len(with_vals),
                "without_n": len(without_vals),
                "with_mean": _round(sum(with_vals) / len(with_vals)),
                "without_mean": _round(sum(without_vals) / len(without_vals)),
            }
        )
    splits.sort(key=lambda item: item["teammate"])
    return splits


def teammate_splits(week_rows: list[dict] | None, team: str, player: str, column: str | None, min_games: int = SPLIT_MIN_GAMES):
    log = index_game_log(week_rows)
    if log is None:
        return None
    return splits_from_log(log, team, player, column, min_games=min_games)


def _counting_average(row: dict, games_played: float, column: str) -> float | None:
    if column not in row:
        return None
    total = _num(row.get(column))
    if total is None or not games_played:
        return None
    return total / games_played


def _share_average(row: dict, column: str) -> float | None:
    if column not in row or row.get(column) in (None, ""):
        return None
    return _share(row.get(column))


def week_metric_mean(log, team: str, player_name: str, column: str, *, share: bool, player_id=None) -> float | None:
    if log is None or column not in log["columns"]:
        return None
    player = _log_player(log, team, player_name, player_id)
    if player is None:
        return None
    values = []
    for game_rows in player["games"].values():
        nums = []
        for row in game_rows:
            if column not in row:
                continue
            number = _share(row.get(column)) if share else _num(row.get(column))
            if number is not None:
                nums.append(number)
        if not nums:
            continue
        values.append(sum(nums) / len(nums) if share else sum(nums))
    if not values:
        return None
    return sum(values) / len(values)


def read_bucket(code) -> str | None:
    """Map one read_thrown code to first_read, checkdown, or secondary_read."""
    if code is None or code == "":
        return None
    if isinstance(code, str):
        text = code.strip()
    else:
        number = _num(code)
        if number is None or float(number) != int(number):
            return None
        text = str(int(number))
    for name, codes in READ_BUCKETS.items():
        if text in codes:
            return name
    return None


def bucket_target_share(player_targets, team_throws) -> float | None:
    """Player targets divided by team throws of the same bucket. Zero throws has no share."""
    targets = _num(player_targets)
    throws = _num(team_throws)
    if targets is None or throws is None or throws <= 0 or targets < 0:
        return None
    return targets / throws


def read_share_multiplier(share, player_games, team_games, min_games: int = SPLIT_MIN_GAMES):
    """The share may scale a stat only when both samples clear the 5-game bar.

    A short sample returns None. The caller stores the share and passes no multiplier.
    """
    if share is None:
        return None
    try:
        player_n = int(player_games)
        team_n = int(team_games)
    except (TypeError, ValueError):
        return None
    if player_n < min_games or team_n < min_games:
        return None
    return share


def _play_token(value):
    number = _num(value)
    if number is None or float(number) != int(number):
        return None
    return str(int(number))


def _game_token(value):
    if value is None or value == "":
        return None
    return str(value).strip()


def _flag_one(value) -> bool:
    number = _num(value)
    return number == 1


def _column_set(rows: list[dict]) -> set[str]:
    names = set()
    for row in rows:
        names.update(row)
    return names


def _joined_read_plays(charting_rows: list[dict], pbp_rows: list[dict]):
    """Join charting to pbp. None when the join columns are absent. [] when nothing matches."""
    chart_cols = _column_set(charting_rows)
    pbp_cols = _column_set(pbp_rows)
    if not {"nflverse_game_id", "nflverse_play_id", "read_thrown"} <= chart_cols:
        return None
    if not {"game_id", "play_id", "pass_attempt", "qb_dropback"} <= pbp_cols:
        return None
    pbp_index = {}
    for row in pbp_rows:
        game_id = _game_token(row.get("game_id"))
        play_id = _play_token(row.get("play_id"))
        if game_id and play_id:
            pbp_index[(game_id, play_id)] = row
    plays = []
    seen = set()
    matched = 0
    for row in charting_rows:
        game_id = _game_token(row.get("nflverse_game_id"))
        play_id = _play_token(row.get("nflverse_play_id"))
        if not game_id or not play_id:
            continue
        key = (game_id, play_id)
        if key in seen:
            continue
        pbp_row = pbp_index.get(key)
        if pbp_row is None:
            continue
        seen.add(key)
        matched += 1
        if not _reg_row(pbp_row):
            continue
        is_throw = _flag_one(pbp_row.get("pass_attempt")) and not _flag_one(pbp_row.get("sack"))
        is_dropback = _flag_one(pbp_row.get("qb_dropback"))
        if not is_throw and not is_dropback:
            continue
        team = pbp_row.get("posteam")
        if team in (None, ""):
            continue
        plays.append(
            {
                "game_id": game_id,
                "team": str(team),
                "bucket": read_bucket(row.get("read_thrown")),
                "is_throw": is_throw,
                "is_dropback": is_dropback,
                "receiver_id": pbp_row.get("receiver_player_id"),
                "receiver_name": pbp_row.get("receiver_player_name") or "",
                "passer_id": pbp_row.get("passer_player_id"),
                "passer_name": pbp_row.get("passer_player_name") or "",
                "defense": None if pbp_row.get("defteam") in (None, "") else str(pbp_row.get("defteam")),
                "air_yards": _num(pbp_row.get("air_yards")) if "air_yards" in pbp_row else None,
            }
        )
    if matched == 0:
        return []
    return plays


def _blank_bucket_map():
    return {name: 0 for name in READ_BUCKETS}


def _blank_game_map():
    return {name: set() for name in READ_BUCKETS}


def _bind_person(roster: dict, player_id, name: str):
    keys = []
    if player_id not in (None, ""):
        keys.append("id:" + str(player_id))
    if name:
        keys.append("name:" + str(name).strip().casefold())
    if not keys:
        return None
    found = None
    for key in keys:
        found = roster.get(key)
        if found is not None:
            break
    if found is None:
        found = {
            "targets": _blank_bucket_map(),
            "games": _blank_game_map(),
            "dropbacks": 0,
            "checkdowns": 0,
            "first_reads": 0,
            "dropback_games": set(),
        }
    for key in keys:
        roster[key] = found
    return found


def shrink_to_league(rate, dropbacks, league_mean, prior: int = SHRINK_DROPBACKS):
    """Pull a defense rate toward the league mean until it has `prior` dropbacks.

    At 0 dropbacks the result is the league mean. At `prior` or more, the observed rate stands.
    """
    if league_mean is None:
        return None
    drops = _num(dropbacks)
    observed = _num(rate) if rate is not None else None
    if drops is None or drops <= 0 or observed is None:
        return league_mean
    if drops >= prior:
        return observed
    weight = drops / prior
    return weight * observed + (1.0 - weight) * league_mean


def clamp_opponent_factor(ratio, bounds: tuple[float, float] = OPPONENT_FACTOR_CLAMP):
    """Existing opponent clamp, 0.85–1.15. None stays None."""
    if ratio is None:
        return None
    number = _num(ratio)
    if number is None:
        return None
    lo, hi = bounds
    return min(hi, max(lo, number))


def shrunk_rate_ratio(rate, dropbacks, league_mean, prior: int = SHRINK_DROPBACKS):
    """Unclamped shrunk rate / league rate, plus the shrunk rate. None when the league rate is 0."""
    shrunk = shrink_to_league(rate, dropbacks, league_mean, prior)
    if shrunk is None or league_mean in (None, 0):
        return None, shrunk
    return shrunk / league_mean, shrunk


def position_index(stat_rows) -> dict[str, str]:
    """Map player id and name to the position already on the stat row. No depth chart."""
    found = {}
    for row in stat_rows or []:
        position = str(row.get("position") or "").strip().upper()
        if not position:
            continue
        player_id = row.get("player_id")
        name = person_name(row)
        if player_id not in (None, ""):
            found["id:" + str(player_id)] = position
        if name:
            found["name:" + name.casefold()] = position
    return found


def _receiver_position(play: dict, positions: dict) -> str | None:
    receiver_id = play.get("receiver_id")
    if receiver_id not in (None, ""):
        found = positions.get("id:" + str(receiver_id))
        if found:
            return found
    name = (play.get("receiver_name") or "").strip()
    if name:
        return positions.get("name:" + name.casefold())
    return None


def _person_key(player_id, name: str) -> str | None:
    if player_id not in (None, ""):
        return "id:" + str(player_id)
    if name and str(name).strip():
        return "name:" + str(name).strip().casefold()
    return None


def defense_read_rates(plays, positions=None, prior: int = SHRINK_DROPBACKS):
    """Defensive pass-read rates from joined throws. None when there is nothing to rate.

    Rates use pass attempts. Shrinkage uses dropbacks. Position RB comes from `positions`.
    """
    if not plays:
        return None
    positions = positions or {}
    defenses = {}

    def defense_bucket(name):
        return defenses.setdefault(
            name,
            {
                "pass_attempts": 0,
                "checkdowns": 0,
                "suppressed": 0,
                "targets": 0,
                "rb_targets": 0,
                "dropbacks": 0,
            },
        )

    for play in plays:
        defense = play.get("defense")
        is_throw = bool(play.get("is_throw"))
        is_target = is_throw and _person_key(play.get("receiver_id"), play.get("receiver_name")) is not None
        position = _receiver_position(play, positions) if is_target else None
        if defense and play.get("is_dropback"):
            defense_bucket(defense)["dropbacks"] += 1
        if defense and is_throw:
            bucket = defense_bucket(defense)
            bucket["pass_attempts"] += 1
            if play.get("bucket") == "checkdown":
                bucket["checkdowns"] += 1
            if play.get("bucket") != "first_read":
                bucket["suppressed"] += 1
            if is_target:
                bucket["targets"] += 1
                if position == "RB":
                    bucket["rb_targets"] += 1

    def observed_rate(numer, denom):
        if not denom:
            return None
        return numer / denom

    observed = {}
    for name, bucket in defenses.items():
        observed[name] = {
            "dropbacks": bucket["dropbacks"],
            "pass_attempts": bucket["pass_attempts"],
            "def_forced_checkdown_rate": observed_rate(bucket["checkdowns"], bucket["pass_attempts"]),
            "def_first_read_suppression_rate": observed_rate(bucket["suppressed"], bucket["pass_attempts"]),
            "def_rb_target_funnel_share": observed_rate(bucket["rb_targets"], bucket["targets"]),
        }
    league_check = mean(row["def_forced_checkdown_rate"] for row in observed.values())
    league_sup = mean(row["def_first_read_suppression_rate"] for row in observed.values())
    league_rb = mean(row["def_rb_target_funnel_share"] for row in observed.values())
    if league_check is None and league_sup is None and league_rb is None:
        return None
    teams = {}
    for name, row in observed.items():
        check_ratio, check_shrunk = shrunk_rate_ratio(
            row["def_forced_checkdown_rate"], row["dropbacks"], league_check, prior
        )
        sup_ratio, sup_shrunk = shrunk_rate_ratio(
            row["def_first_read_suppression_rate"], row["dropbacks"], league_sup, prior
        )
        rb_shrunk = shrink_to_league(row["def_rb_target_funnel_share"], row["dropbacks"], league_rb, prior)
        stacked, clamped = stack_matchup_factor(check_ratio, sup_ratio)
        teams[name] = {
            "dropbacks": row["dropbacks"],
            "pass_attempts": row["pass_attempts"],
            "def_forced_checkdown_rate": _round(row["def_forced_checkdown_rate"]),
            "def_forced_checkdown_rate_shrunk": _round(check_shrunk),
            "def_checkdown_multiplier": _round(check_ratio),
            "def_first_read_suppression_rate": _round(row["def_first_read_suppression_rate"]),
            "def_first_read_suppression_rate_shrunk": _round(sup_shrunk),
            "def_suppression_multiplier": _round(sup_ratio),
            "def_rb_target_funnel_share": _round(row["def_rb_target_funnel_share"]),
            "def_rb_target_funnel_share_shrunk": _round(rb_shrunk),
            "def_matchup_ratio": _round(stacked),
            "def_matchup_factor": _round(clamped),
        }
    return {
        "league": {
            "def_forced_checkdown_rate": _round(league_check),
            "def_first_read_suppression_rate": _round(league_sup),
            "def_rb_target_funnel_share": _round(league_rb),
        },
        "teams": teams,
    }


def stack_matchup_factor(checkdown_ratio, suppression_ratio):
    """Unclamped product of the two shrunk ratios, then the opponent clamp.

    Returns (unclamped, clamped). Either side is None when a ratio is missing.
    The product is the matchup factor. It is not assigned to one player.
    """
    check = _num(checkdown_ratio)
    suppression = _num(suppression_ratio)
    if check is None or suppression is None:
        return None, None
    stacked = check * suppression
    return stacked, clamp_opponent_factor(stacked)


def progression_table(charting_rows, pbp_rows, min_games: int = SPLIT_MIN_GAMES, positions=None):
    """Player and quarterback read features from a charting/pbp join.

    None means charting or pbp was missing, or the join columns were absent.
    status "missing" means a frame was empty. status "unmatched" means no play joined.
    status "ok" holds shares. A multiplier is the share only when both game counts
    clear min_games. The season baseline is not part of this table.
    """
    if charting_rows is None or pbp_rows is None:
        return None
    if not charting_rows or not pbp_rows:
        return {"status": "missing", "players": {}, "qbs": {}}
    plays = _joined_read_plays(charting_rows, pbp_rows)
    if plays is None:
        return None
    if not plays:
        return {"status": "unmatched", "players": {}, "qbs": {}}
    team_throws = {}
    team_games = {}
    rosters = {}
    for play in plays:
        team = play["team"]
        roster = rosters.setdefault(team, {})
        bucket = play["bucket"]
        if play["is_throw"] and bucket is not None:
            throws = team_throws.setdefault(team, _blank_bucket_map())
            games = team_games.setdefault(team, _blank_game_map())
            throws[bucket] += 1
            games[bucket].add(play["game_id"])
            receiver = _bind_person(roster, play["receiver_id"], play["receiver_name"])
            if receiver is not None:
                receiver["targets"][bucket] += 1
                receiver["games"][bucket].add(play["game_id"])
        if play["is_dropback"]:
            passer = _bind_person(roster, play["passer_id"], play["passer_name"])
            if passer is None:
                continue
            passer["dropbacks"] += 1
            passer["dropback_games"].add(play["game_id"])
            if bucket == "checkdown":
                passer["checkdowns"] += 1
            elif bucket == "first_read":
                passer["first_reads"] += 1
    players = {}
    qbs = {}
    for team, roster in rosters.items():
        throws = team_throws.get(team) or _blank_bucket_map()
        games = team_games.get(team) or _blank_game_map()
        seen = set()
        for person in roster.values():
            marker = id(person)
            if marker in seen:
                continue
            seen.add(marker)
            if any(person["targets"].values()):
                first_games = len(person["games"]["first_read"])
                check_games = len(person["games"]["checkdown"])
                team_first = len(games["first_read"])
                team_check = len(games["checkdown"])
                first_share = bucket_target_share(person["targets"]["first_read"], throws["first_read"])
                check_share = bucket_target_share(person["targets"]["checkdown"], throws["checkdown"])
                first_multiplier = read_share_multiplier(first_share, first_games, team_first, min_games)
                check_multiplier = read_share_multiplier(check_share, check_games, team_check, min_games)
                feature = {
                    "first_read_target_share": _round(first_share) if first_share is not None else None,
                    "first_read_player_games": first_games,
                    "first_read_team_games": team_first,
                    "first_read_multiplier": None if first_multiplier is None else _round(first_multiplier),
                    "checkdown_target_share": _round(check_share) if check_share is not None else None,
                    "checkdown_player_games": check_games,
                    "checkdown_team_games": team_check,
                    "checkdown_multiplier": None if check_multiplier is None else _round(check_multiplier),
                }
                for key, owner in roster.items():
                    if owner is person:
                        players.setdefault(team, {})[key] = feature
            if person["dropbacks"] > 0:
                qb_feature = {
                    "qb_checkdown_tendency": _round(person["checkdowns"] / person["dropbacks"]),
                    "qb_first_read_rate": _round(person["first_reads"] / person["dropbacks"]),
                    "qb_dropback_games": len(person["dropback_games"]),
                }
                for key, owner in roster.items():
                    if owner is person:
                        qbs.setdefault(team, {})[key] = qb_feature
    return {
        "status": "ok",
        "players": players,
        "qbs": qbs,
        "defenses": defense_read_rates(plays, positions),
    }


def _read_person(table, team, name, player_id):
    if not table:
        return None
    roster = table.get(team) or {}
    if player_id not in (None, ""):
        found = roster.get("id:" + str(player_id))
        if found is not None:
            return found
    if name:
        return roster.get("name:" + name.casefold())
    return None


def _team_qb_tendency(read_table: dict, team: str, stat: str) -> float | None:
    qbs = (read_table.get("qbs") or {}).get(team) or {}
    if not qbs:
        return None
    best = max(qbs.values(), key=lambda q: int(q.get("qb_dropback_games") or 0))
    if stat == "receptions":
        return best.get("qb_checkdown_tendency")
    if stat == "receiving yards":
        return best.get("qb_first_read_rate")
    return None


def _attach_read_features(
    row: dict,
    stat: str,
    read_table,
    team: str,
    name: str,
    player_id,
    *,
    team_pass_attempts_pg: float | None = None,
    conversion_rate: float | None = None,
) -> None:
    """Opportunity fields only. baseline_mean is not scaled here."""
    if not read_table or read_table.get("status") != "ok":
        return
    player = _read_person(read_table.get("players"), team, name, player_id)
    if stat == "receiving yards" and player is not None:
        row["first_read_target_share"] = player["first_read_target_share"]
        row["first_read_player_games"] = player["first_read_player_games"]
        row["first_read_team_games"] = player["first_read_team_games"]
        row["first_read_multiplier"] = player["first_read_multiplier"]
        tb = _team_qb_tendency(read_table, team, stat)
        if tb is not None:
            row["team_bucket_throw_share"] = tb
        if team_pass_attempts_pg is not None and team_pass_attempts_pg > 0:
            row["team_pass_attempts_expected"] = _round(team_pass_attempts_pg)
            row["volume_source"] = "team_pass_attempts_expected"
        if conversion_rate is not None and conversion_rate > 0:
            row["conversion"] = _round(conversion_rate)
    elif stat == "receptions" and player is not None:
        row["checkdown_target_share"] = player["checkdown_target_share"]
        row["checkdown_player_games"] = player["checkdown_player_games"]
        row["checkdown_team_games"] = player["checkdown_team_games"]
        row["checkdown_multiplier"] = player["checkdown_multiplier"]
        tb = _team_qb_tendency(read_table, team, stat)
        if tb is not None:
            row["team_bucket_throw_share"] = tb
        if team_pass_attempts_pg is not None and team_pass_attempts_pg > 0:
            row["team_pass_attempts_expected"] = _round(team_pass_attempts_pg)
            row["volume_source"] = "team_pass_attempts_expected"
        if conversion_rate is not None and conversion_rate > 0:
            row["conversion"] = _round(conversion_rate)
    if stat in PASSING_STATS:
        qb = _read_person(read_table.get("qbs"), team, name, player_id)
        if qb is not None:
            row["qb_checkdown_tendency"] = qb["qb_checkdown_tendency"]
            row["qb_first_read_rate"] = qb["qb_first_read_rate"]
            row["qb_dropback_games"] = qb["qb_dropback_games"]


def _attach_defense_reads(row, stat, read_table, team, opponent, position, player_id, name) -> None:
    """Copy the defense's matchup factor onto each pass catcher and passer.

    The same numbers go on every one of those rows. Player read shares and
    their multipliers are left as stored. baseline_mean is not changed.
    """
    del stat, team, player_id, name
    if not read_table or read_table.get("status") != "ok":
        return
    record = ((read_table.get("defenses") or {}).get("teams") or {}).get(opponent)
    if not record or record.get("def_matchup_ratio") is None:
        return
    if str(position or "").strip().upper() not in PASS_MATCHUP_POSITIONS:
        return
    row["def_matchup_ratio"] = record.get("def_matchup_ratio")
    row["def_matchup_factor"] = record.get("def_matchup_factor")


def nfl_rows_from_tables(
    game_rows: list[dict],
    stat_rows: list[dict],
    snap_rows: list[dict],
    game_date: str,
    retrieved_at: str,
    source_url: str,
    team_rows: list[dict] | None = None,
    week_rows: list[dict] | None = None,
    read_table: dict | None = None,
    prior_week_rows: list[dict] | None = None,
) -> list[dict]:
    games = nfl_games_on(game_rows, game_date)
    slate = nfl_matchups(games)
    if not slate:
        return []
    # None means the caller did not ask for team stats, so pace comes from snap counts.
    # An empty list means load_team_stats failed or returned nothing, so pace stays null.
    if team_rows is None:
        pace = team_play_pace(snap_rows)
    else:
        pace = team_pace_from_stats(team_rows)
    league_pace = mean(list(pace.values()))
    snap_rates = player_snap_rates(snap_rows)
    log = index_game_log(week_rows)
    prior_log = index_game_log(prior_week_rows) if prior_week_rows else None
    snap_index = index_player_snaps(snap_rows)
    routes_from_season = numeric_column(stat_rows, "routes")
    share_from_season = numeric_column(stat_rows, "route_share")
    routes_from_week = log is not None and numeric_column(week_rows, "routes")
    share_from_week = log is not None and numeric_column(week_rows, "route_share")
    season = games[0].get("season") or ""
    team_pass_att_pg: dict[str, float] = {}
    team_att_totals: dict[str, float] = {}
    team_max_games: dict[str, float] = {}
    for p_row in stat_rows:
        if season and str(p_row.get("season") or "") not in ("", season):
            continue
        t_code = p_row.get("recent_team") or p_row.get("team")
        if not t_code:
            continue
        gp = _num(p_row.get("games")) or 0.0
        att = _num(p_row.get("attempts")) or 0.0
        if gp > 0:
            team_max_games[t_code] = max(team_max_games.get(t_code, 0.0), gp)
        if att > 0:
            team_att_totals[t_code] = team_att_totals.get(t_code, 0.0) + att
    for t_code, tot_att in team_att_totals.items():
        mg = team_max_games.get(t_code, 0.0)
        if mg > 0 and tot_att > 0:
            team_pass_att_pg[t_code] = tot_att / mg
    rows = []
    for player in stat_rows:
        if season and str(player.get("season") or "") not in ("", season):
            continue
        if str(player.get("position") or "").upper() in {"K", "P"}:
            continue
        team = player.get("recent_team") or player.get("team")
        if team not in slate:
            continue
        games_played = _num(player.get("games"))
        if games_played is None or games_played <= 0:
            continue
        name = person_name(player)
        player_id = player.get("player_id")
        snap_info = snap_rates.get((name.lower(), team)) or {}
        snap = snap_info.get("snap_share")
        target = _share(player.get("target_share"))
        epa_total = sum(_num(player.get(key)) or 0.0 for key in ("passing_epa", "rushing_epa", "receiving_epa"))
        epa = epa_total / games_played
        pace_per_game = pace.get(team)
        pace_ratio = ratio(pace_per_game, league_pace)
        if routes_from_season:
            routes_per_game = _counting_average(player, games_played, "routes")
        elif routes_from_week:
            routes_per_game = week_metric_mean(log, team, name, "routes", share=False, player_id=player_id)
        else:
            routes_per_game = None
        if share_from_season:
            route_share = _share_average(player, "route_share")
        elif share_from_week:
            route_share = week_metric_mean(log, team, name, "route_share", share=True, player_id=player_id)
        else:
            route_share = None
        specs = list(NFL_COUNTING)
        solo = _num(player.get("def_tackles_solo")) or 0.0
        assists = _num(player.get("def_tackle_assists")) or 0.0
        if solo + assists > 0:
            specs.append(("tackles + assists", None))
        for stat, column in specs:
            total = solo + assists if column is None else _num(player.get(column))
            if total is None or total <= 0:
                continue
            built = make_row(
                sport="NFL",
                game_date=game_date,
                player=name,
                team=team,
                opponent=slate[team],
                stat=stat,
                baseline_mean=total / games_played,
                sample_size=games_played,
                source_url=source_url,
                retrieved_at=retrieved_at,
                pace_per_game=pace_per_game,
                pace_ratio=pace_ratio,
                epa=epa,
                target_share=target,
                snap_share=snap,
            )
            if "offense_snaps_per_game" in snap_info:
                built["offense_snaps_per_game"] = _round(snap_info["offense_snaps_per_game"])
            if "defense_snaps_per_game" in snap_info:
                built["defense_snaps_per_game"] = _round(snap_info["defense_snaps_per_game"])
            if routes_per_game is not None:
                built["routes_per_game"] = _round(routes_per_game)
            if route_share is not None:
                built["route_share"] = _round(route_share)
            # None: week log missing. A list, possibly empty: log read, gate applied.
            # baseline_mean stays the mixed season rate. The deployment step chooses a split.
            built["teammate_splits"] = None if log is None else splits_from_log(
                log, team, name, column, player_id=player_id
            )
            targets_total = _num(player.get("targets"))
            conv_rate = (total / targets_total) if (targets_total is not None and targets_total > 0 and stat in ("receptions", "receiving yards")) else None
            _attach_read_features(
                built,
                stat,
                read_table,
                team,
                name,
                player_id,
                team_pass_attempts_pg=team_pass_att_pg.get(team),
                conversion_rate=conv_rate,
            )
            _attach_defense_reads(
                built,
                stat,
                read_table,
                team,
                slate[team],
                player.get("position"),
                player_id,
                name,
            )
            if player_id not in (None, ""):
                built["player_id"] = player_id
            current = nfl_series_from_log(log, snap_index, team, name, player_id, stat, column)
            older = (
                nfl_series_from_log(prior_log, {}, team, name, player_id, stat, column)
                if prior_log is not None
                else None
            )
            apply_log_summary(built, current, older)
            rows.append(built)
    return rows


def dataset_rows(data: dict | None) -> list[dict]:
    """nba_api DataSet dicts use headers plus data or rowSet."""
    if not data:
        return []
    headers = data.get("headers") or []
    raw_rows = data.get("rowSet")
    if raw_rows is None:
        raw_rows = data.get("data") or []
    if headers and raw_rows and not isinstance(raw_rows[0], dict):
        return [dict(zip(headers, row)) for row in raw_rows]
    if raw_rows and isinstance(raw_rows[0], dict):
        return list(raw_rows)
    return []


def result_set_rows(payload: dict | None) -> list[dict]:
    if not payload:
        return []
    sets = payload.get("resultSets") or []
    if sets:
        return dataset_rows(sets[0])
    return dataset_rows(payload)


def nba_team_abbrev(value) -> str | None:
    """Map an ESPN abbreviation onto the LeagueDashTeamStats abbreviation."""
    if value is None:
        return None
    code = str(value).strip().upper()
    if not code:
        return None
    return ESPN_NBA_ABBREV.get(code, code)


def espn_category_names(payload: dict) -> dict[str, list]:
    found = {}
    for category in payload.get("categories") or []:
        if not isinstance(category, dict) or not category.get("name"):
            continue
        found[str(category["name"])] = list(category.get("names") or [])
    return found


def espn_category_value(athlete_categories, names: dict[str, list], category: str, stat_name: str):
    """Value aligned by category name, not by a fixed column index."""
    columns = names.get(category) or []
    try:
        index = columns.index(stat_name)
    except ValueError:
        return None
    for item in athlete_categories or []:
        if not isinstance(item, dict) or item.get("name") != category:
            continue
        values = item.get("values") or []
        if index >= len(values):
            return None
        return values[index]
    return None


def espn_athlete_team(athlete: dict) -> str | None:
    if not isinstance(athlete, dict):
        return None
    team_id = athlete.get("teamId")
    teams = [team for team in (athlete.get("teams") or []) if isinstance(team, dict)]
    chosen = None
    if team_id is not None:
        for team in teams:
            if str(team.get("id")) == str(team_id) and team.get("abbreviation"):
                chosen = team.get("abbreviation")
                break
    if chosen is None:
        for team in teams:
            if team.get("abbreviation"):
                chosen = team.get("abbreviation")
                break
    if chosen is None:
        chosen = athlete.get("teamShortName")
    return nba_team_abbrev(chosen)


def espn_has_counting_averages(payload: dict | None) -> bool:
    """True when the byathlete payload still uses the probed average names."""
    if not isinstance(payload, dict):
        return False
    names = espn_category_names(payload)
    general = set(names.get("general") or [])
    offensive = set(names.get("offensive") or [])
    if general & {"gamesPlayed", "avgMinutes", "avgRebounds"}:
        return True
    return bool(offensive & {"avgPoints", "avgAssists", "avgThreePointFieldGoalsMade"})


def matchups_from_scoreboard(payload: dict | None) -> dict[str, str]:
    """Home/away abbreviations from an ESPN site scoreboard. Odds are ignored."""
    if not isinstance(payload, dict):
        return {}
    matchups = {}
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        for competition in event.get("competitions") or []:
            if not isinstance(competition, dict):
                continue
            away = home = None
            for competitor in competition.get("competitors") or []:
                if not isinstance(competitor, dict):
                    continue
                abbrev = nba_team_abbrev((competitor.get("team") or {}).get("abbreviation"))
                side = competitor.get("homeAway")
                if side == "away":
                    away = abbrev
                elif side == "home":
                    home = abbrev
            if away and home:
                matchups.setdefault(away, home)
                matchups.setdefault(home, away)
                break
    return matchups


def team_pace_table(payload: dict | None, team_abbreviations=None) -> dict[str, dict]:
    table = {}
    if isinstance(payload, dict) and payload and "resultSets" not in payload and "headers" not in payload:
        sample = next(iter(payload.values()), None)
        if isinstance(sample, dict) and ("pace" in sample or "possessions" in sample):
            return payload
    for row in result_set_rows(payload):
        team = row.get("TEAM_ABBREVIATION") or row.get("teamTricode")
        if not team and team_abbreviations:
            team = team_abbreviations.get(str(row.get("TEAM_ID")))
        if not team:
            continue
        pace = _num(row.get("PACE"))
        if pace is None:
            pace = _num(row.get("E_PACE"))
        possessions = _num(row.get("POSS"))
        if possessions is None:
            possessions = _num(row.get("POSS_PER_GAME"))
        table[str(team)] = {"pace": pace, "possessions": possessions}
    return table


def parse_minutes(value):
    if isinstance(value, str) and ":" in value:
        seconds = parse_toi_seconds(value)
        return None if seconds is None else seconds / 60.0
    return _num(value)


def nba_rows_from_stats(
    payload: dict,
    matchups: dict[str, str],
    game_date: str,
    retrieved_at: str,
    source_url: str,
    team_pace: dict | None = None,
) -> list[dict]:
    """Season averages from an ESPN statistics/byathlete payload. No rows are invented.

    avgPoints, avgRebounds, avgAssists, avgThreePointFieldGoalsMade, and
    avgMinutes are already per game. A missing name or value skips that stat.
    """
    if not isinstance(payload, dict):
        return []
    names = espn_category_names(payload)
    athletes = payload.get("athletes") or []
    if not athletes:
        return []
    pace_by_team = team_pace or {}
    league_pace = mean([item.get("pace") for item in pace_by_team.values() if isinstance(item, dict)])
    rows = []
    for item in athletes:
        if not isinstance(item, dict):
            continue
        athlete = item.get("athlete") or {}
        team = espn_athlete_team(athlete)
        if team not in matchups:
            continue
        categories = item.get("categories") or []
        games_played = _num(espn_category_value(categories, names, "general", "gamesPlayed"))
        if games_played is None or games_played <= 0:
            continue
        player = str(athlete.get("displayName") or "").strip()
        if not player:
            continue
        team_rates = pace_by_team.get(team) or {}
        pace_per_game = team_rates.get("pace") if isinstance(team_rates, dict) else None
        possessions = team_rates.get("possessions") if isinstance(team_rates, dict) else None
        minutes = parse_minutes(espn_category_value(categories, names, "general", "avgMinutes"))
        for stat, category, stat_name in NBA_COUNTING_FIELDS:
            total = _num(espn_category_value(categories, names, category, stat_name))
            if total is None:
                continue
            built = make_row(
                sport="NBA",
                game_date=game_date,
                player=player,
                team=str(team),
                opponent=matchups[team],
                stat=stat,
                baseline_mean=total,
                sample_size=games_played,
                source_url=source_url,
                retrieved_at=retrieved_at,
                pace_per_game=pace_per_game,
                pace_ratio=ratio(pace_per_game, league_pace),
                minutes=minutes,
                possessions=possessions,
            )
            if athlete.get("id") not in (None, ""):
                built["player_id"] = athlete.get("id")
            rows.append(built)
    return rows


def consensus_input(quotes, *, now=None, side: str = "over"):
    """Book list for pickem_math pipeline, grouped by player, team, stat, and line."""
    return build_consensus_input(quotes, now=now, side=side)


def attach_prices(rows: list[dict], quotes) -> tuple[list[dict], list[dict]]:
    """Attach the primary line. Sharp line first, otherwise the most-quoted line.

    Every slate row gets n_books and lines_disagree. lines_disagree is triage
    signal 2: approved books posted different lines for the same stat. A row
    with no quote keeps null book, line, and prices. Names join on
    (player_norm, team) using the team already on the slate row.
    """
    if isinstance(quotes, dict):
        quotes = []
    resolved, unmatched = resolve_quote_teams(quotes, rows)
    for row in rows:
        found = quotes_for_row(resolved, row)
        price = primary_price(found)
        if not price:
            row["n_books"] = 0
            row["lines_disagree"] = False
            refresh_hits(row)
            continue
        row["book"] = price["book"]
        row["line"] = _round(price["line"])
        row["over_odds"] = _round(price["over_odds"])
        row["under_odds"] = _round(price["under_odds"])
        row["n_books"] = price["n_books"]
        row["lines_disagree"] = bool(price["lines_disagree"])
        decision = serious_flag(
            row.get("stat"),
            row.get("baseline_mean"),
            row["line"],
            row.get("pace_ratio"),
            row.get("shots_against_ratio"),
            row.get("snap_share"),
        )
        reasons = list(decision["flag_reasons"])
        if price["lines_disagree"] and "lines_disagree" not in reasons:
            reasons.append("lines_disagree")
        row["flag"] = bool(reasons)
        row["channel"] = decision["channel"]
        row["flag_reasons"] = reasons
        refresh_hits(row)
    return resolved, unmatched


def _remember(bucket, url) -> None:
    if bucket is None or not url:
        return
    text = str(url)
    if text not in bucket:
        bucket.append(text)


def _is_retryable_fetch_error(exc: BaseException) -> bool:
    """5xx and timeouts only. A 4xx or a refused connection is not retried."""
    if isinstance(exc, urllib.error.HTTPError):
        try:
            code = int(exc.code)
        except (TypeError, ValueError):
            return False
        return 500 <= code <= 599
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, TimeoutError):
            return True
        text = str(reason).lower()
        return "timed out" in text or "timeout" in text
    return False


def _retry_delay(attempt: int, rng) -> float:
    index = min(max(attempt, 0), len(FETCH_BACKOFF_SECONDS) - 1)
    return FETCH_BACKOFF_SECONDS[index] + float(rng()) * FETCH_JITTER_SECONDS


def _close_http_error(exc: BaseException) -> None:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            exc.close()
        except Exception:
            return


def fetch_bytes(
    url: str,
    timeout: float = 30,
    headers: dict | None = None,
    *,
    opener=None,
    sleeper=None,
    rng=None,
    attempts: int = FETCH_ATTEMPTS,
) -> bytes:
    """GET `url`. Retry 5xx and timeouts up to `attempts` times.

    The waits before the second and third attempts are 1s and 2s plus jitter.
    `opener` defaults to urllib.request.urlopen and is called as
    opener(request, timeout=timeout).
    """
    open_url = opener or urllib.request.urlopen
    sleep = sleeper or time.sleep
    roll = rng or random.random
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json,text/csv,*/*"}
    if headers:
        request_headers.update(headers)
    tries = attempts if attempts and attempts > 0 else 1
    for attempt in range(tries):
        request = urllib.request.Request(url, headers=request_headers)
        try:
            with open_url(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            _close_http_error(exc)
            if not _is_retryable_fetch_error(exc) or attempt >= tries - 1:
                raise
            sleep(_retry_delay(attempt, roll))
    raise RuntimeError(f"fetch failed without an exception: {url}")


def fetch_json(url: str, timeout: float = 30, headers: dict | None = None) -> dict:
    return json.loads(fetch_bytes(url, timeout=timeout, headers=headers).decode("utf-8"))


def make_nhl_client():
    try:
        from nhlpy import NHLClient
    except Exception as exc:
        return None, f"nhl-api-py import failed: {exc}"
    try:
        return NHLClient(), None
    except Exception as exc:
        return None, f"NHLClient() failed: {exc}"


def _call_nhl(client, label: str, fn, fallback):
    """Try the client. On failure, urllib only that call."""
    if client is None:
        try:
            return fallback(), f"{label}: nhl-api-py unavailable; used urllib"
        except Exception as exc:
            return None, f"{label}: nhl-api-py unavailable; urllib failed: {exc}"
    try:
        return fn(), None
    except Exception as exc:
        try:
            return fallback(), f"{label}: NHLClient failed ({exc}); used urllib"
        except Exception as fallback_exc:
            return None, f"{label}: NHLClient failed ({exc}); urllib failed: {fallback_exc}"


def _blank_log_fields(row: dict) -> None:
    """Null every log field. A missing log is not filled from the season rate."""
    for key in LOG_FIELDS:
        row[key] = None
    row["log_missing"] = True


def _when_key(game: dict) -> tuple:
    when = game.get("when")
    tie = str(game.get("tie") or "")
    if isinstance(when, (int, float)) and not isinstance(when, bool):
        return (0, float(when), tie)
    text = str(when or "")
    if text.isdigit():
        return (0, float(text), tie)
    return (1, text, tie)


def _sample_variance(values: list[float]) -> float | None:
    """Unbiased sample variance. Fewer than two games has no variance."""
    count = len(values)
    if count < 2:
        return None
    center = sum(values) / count
    return sum((value - center) ** 2 for value in values) / (count - 1)


def _tail_mean(games: list[dict], count: int) -> float | None:
    if len(games) < count:
        return None
    tail = games[-count:]
    return sum(game["value"] for game in tail) / count


def _workload_average(games: list[dict]) -> float | None:
    values = [game["workload"] for game in games if game.get("workload") is not None]
    if not values:
        return None
    return sum(values) / len(values)


def roles_similar(current: list[dict], prior: list[dict]) -> bool:
    """True when prior workload is within 20% of the current-season average."""
    current_avg = _workload_average(current)
    prior_avg = _workload_average(prior)
    if current_avg is None or prior_avg is None or current_avg == 0:
        return False
    ratio = prior_avg / current_avg
    return (1 - ROLE_BAND) - 1e-9 <= ratio <= (1 + ROLE_BAND) + 1e-9


def suggested_distribution(stat: str, var_ratio, sd) -> str | None:
    """Helper table. Counting stats at or under 1.10 are poisson, not negbin."""
    if stat in LOG_NORMAL_STATS:
        if sd is None or sd <= 0:
            return None
        return "normal"
    if stat not in LOG_COUNT_STATS or var_ratio is None:
        return None
    if var_ratio <= LOG_VAR_RATIO_POISSON + 1e-9:
        return "poisson"
    return "negbin"


def _role_pool(games: list[dict]) -> tuple[list[dict], int | None, float | None]:
    """Games whose workload is within +/-20% of the current average.

    No workload on the log means the role filter cannot be applied. The pool
    is then the whole log and the role-stable fields stay null.
    """
    known = [game["workload"] for game in games if game.get("workload") is not None]
    if not known:
        return list(games), None, None
    average = sum(known) / len(known)
    if average == 0:
        stable = [game for game in games if game.get("workload") is not None and abs(game["workload"]) <= 1e-9]
    else:
        low = average * (1 - ROLE_BAND)
        high = average * (1 + ROLE_BAND)
        stable = [
            game
            for game in games
            if game.get("workload") is not None and low - 1e-9 <= game["workload"] <= high + 1e-9
        ]
    if not stable:
        return [], 0, None
    role_mean = sum(game["value"] for game in stable) / len(stable)
    return stable, len(stable), role_mean


def _split_pool(pool: list[dict]) -> tuple[list[dict], list[dict]]:
    """Non-overlapping baseline and recent slices. Recent is the newest end.

    Recent is 10 games when at least 5 baseline games remain, else 5 when the
    same gate holds. A shorter recent window is omitted rather than overlapped.
    """
    count = len(pool)
    recent_n = RECENT_LONG if count >= RECENT_LONG + MIN_WINDOW_SIDE else 0
    if recent_n == 0 and count >= RECENT_SHORT + MIN_WINDOW_SIDE:
        recent_n = RECENT_SHORT
    if recent_n and count - recent_n < MIN_WINDOW_SIDE:
        recent_n = 0
    if not recent_n:
        return list(pool), []
    return list(pool[:-recent_n]), list(pool[-recent_n:])


def hit_counts(values, line) -> tuple:
    if not values or line is None:
        return None, None, None, None
    try:
        target = float(line)
    except (TypeError, ValueError):
        return None, None, None, None
    if not math.isfinite(target):
        return None, None, None, None
    over = under = push = 0
    for value in values:
        if abs(value - target) <= 1e-9:
            push += 1
        elif value > target:
            over += 1
        else:
            under += 1
    return over, under, push, len(values)


def refresh_hits(row: dict) -> None:
    over, under, push, count = hit_counts(row.get("stat_log"), row.get("line"))
    row["hits_over"] = over
    row["hits_under"] = under
    row["pushes"] = push
    row["hit_n"] = count


def summarize_log(games: list[dict], stat: str, prior: list[dict] | None = None) -> dict:
    """Season, recent, and baseline windows from one current-season log.

    ``games`` may arrive in any order. Baseline and recent are a partition of
    the role-stable pool (or of the whole log when workload is missing), so
    ``baseline_n + recent_n`` cannot exceed ``season_n``. ``sd`` is the
    baseline window, the one paired with ``baseline_window_mean``. Sample
    variance and ``var_ratio`` use the distribution sample: the current log
    when it has 20 or more games, otherwise that log plus the end of the
    prior season when the workload was similar. Last-5 and last-10 means
    describe the full current log. Prior-season fields stay null when that
    end-of-season workload is not within 20% of the current average.
    """
    def identity(game):
        value=game.get('tie') or game.get('when')
        return str(value) if value not in (None,'') else None
    def unique(rows):
        found={};anonymous=[]
        for game in rows or []:
            ident=identity(game)
            if ident is None:anonymous.append(game);continue
            if ident in found and any(found[ident].get(k)!=game.get(k) for k in ('value','workload')):
                raise ValueError('conflicting repeated historical game: '+ident)
            found[ident]=game
        return list(found.values())+anonymous
    games=unique(games)
    prior=unique(prior)
    current_ids={identity(g) for g in games if identity(g) is not None}
    if current_ids.intersection(identity(g) for g in prior if identity(g) is not None):
        raise ValueError('same historical game appears in current and prior season')
    ordered = sorted(games or [], key=_when_key)
    summary = {key: None for key in LOG_FIELDS}
    summary["season_n"] = len(ordered)
    summary["stat_log"] = [_round(game["value"]) for game in ordered]
    summary["workload_tonight"] = None
    if not ordered:
        return summary
    summary["season_mean"] = _round(sum(game["value"] for game in ordered) / len(ordered))
    summary["last_5_mean"] = _round(_tail_mean(ordered, 5))
    summary["last_10_mean"] = _round(_tail_mean(ordered, 10))
    zeros = sum(1 for game in ordered if abs(game["value"]) <= 1e-9)
    summary["zero_rate"] = _round(zeros / len(ordered))
    pool, role_n, role_mean = _role_pool(ordered)
    summary["role_stable_n"] = role_n
    summary["role_stable_mean"] = _round(role_mean)
    baseline, recent = _split_pool(pool)
    if baseline:
        base_values = [game["value"] for game in baseline]
        base_mean = sum(base_values) / len(base_values)
        summary["baseline_n"] = len(baseline)
        summary["baseline_window_mean"] = _round(base_mean)
        base_variance = _sample_variance(base_values)
        if base_variance is not None:
            summary["sd"] = _round(math.sqrt(base_variance))
        loads = [game["workload"] for game in baseline if game.get("workload") is not None]
        if loads:
            summary["baseline_workload"] = _round(sum(loads) / len(loads))
    if recent:
        summary["recent_n"] = len(recent)
        summary["recent_mean"] = _round(sum(game["value"] for game in recent) / len(recent))
    older = []
    if prior and summary["season_n"]:
        older = sorted(prior, key=_when_key)[-PRIOR_GAME_CAP:]
        if older and roles_similar(ordered, older):
            summary["prior_n"] = len(older)
            summary["prior_season_mean"] = _round(sum(game["value"] for game in older) / len(older))
        else:
            older = []
    windows={'baseline':baseline,'recent':recent,'prior':older}
    if all(identity(g) is not None for window in windows.values() for g in window):
        summary['observation_ids']={name:[identity(g) for g in window] for name,window in windows.items()}
    dist_games = list(ordered)
    if len(ordered) < SHORT_SEASON_GAMES and older and summary["prior_n"]:
        dist_games.extend(older)
    dist_values = [game["value"] for game in dist_games]
    dist_variance = _sample_variance(dist_values)
    summary["sample_variance"] = _round(dist_variance)
    ratio = None
    if dist_variance is not None and dist_values:
        dist_mean = sum(dist_values) / len(dist_values)
        if dist_mean > 0:
            ratio = _round(dist_variance / dist_mean)
    summary["var_ratio"] = ratio
    summary["suggested_dist"] = suggested_distribution(stat, ratio, summary["sd"])
    if not summary["baseline_n"] or not summary["baseline_window_mean"] or summary["baseline_window_mean"] <= 0:
        summary["suggested_dist"] = None
    return summary


def apply_log_summary(row: dict, games: list[dict] | None, prior: list[dict] | None = None) -> None:
    """Attach a log, or mark it missing. Never copies the season rate into the log."""
    if games is None:
        _blank_log_fields(row)
        return
    row.update(summarize_log(games, row.get("stat") or "", prior))
    row['usage_observations']=[dict(id=str(g.get('tie') or ''),date=g.get('when'),
        value=g.get('value'),workload=g.get('workload')) for g in games]
    row['prior_usage_observations']=[dict(id=str(g.get('tie') or ''),date=g.get('when'),
        value=g.get('value'),workload=g.get('workload')) for g in prior or []]
    row["log_missing"] = False
    refresh_hits(row)


def previous_season_id(season: str) -> str:
    start = int(str(season)[:4])
    return f"{start - 1}{start}"


def nhl_game_log_url(player_id, season) -> str:
    return f"{NHL_WEB}/player/{player_id}/game-log/{season}/2"


def espn_gamelog_url(athlete_id, season_year: int) -> str:
    return NBA_GAMELOG.format(athlete_id=athlete_id, season=int(season_year))


def parse_nhl_game_log(payload):
    """Game list from api-web, or the list the nhl-api-py client already unwrapped."""
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and "gameLog" in payload:
        return [row for row in (payload.get("gameLog") or []) if isinstance(row, dict)]
    return None


def nhl_stat_value(game: dict, stat: str):
    if stat == "shots on goal":
        if "shots" not in game:
            return None
        return _num(game.get("shots"))
    if stat == "blocked shots":
        for key in ("blockedShots", "blockedShot", "blocked"):
            if key in game:
                return _num(game.get(key))
        return None
    if stat == "hits":
        return _num(game["hits"]) if "hits" in game else None
    if stat == "goalie saves":
        if "saves" in game and game.get("saves") is not None:
            return _num(game.get("saves"))
        shots_against = _num(game.get("shotsAgainst"))
        goals_against = _num(game.get("goalsAgainst"))
        if shots_against is None or goals_against is None:
            return None
        return shots_against - goals_against
    return None


def nhl_series(games, stat: str):
    """None when the log did not carry this stat. An empty list is a real empty log."""
    if games is None:
        return None
    series = []
    for game in games:
        if not isinstance(game, dict):
            continue
        value = nhl_stat_value(game, stat)
        if value is None:
            continue
        seconds = parse_toi_seconds(game.get("toi"))
        series.append(
            {
                "value": value,
                "workload": None if seconds is None else seconds / 60.0,
                "when": str(game.get("gameDate") or ""),
                "tie": str(game.get("gameId") or ""),
            }
        )
    if games and not series:
        return None
    return series


def _player_ids(rows) -> list[str]:
    found = []
    seen = set()
    for row in rows or []:
        player_id = row.get("player_id")
        if player_id in (None, ""):
            continue
        key = str(player_id)
        if key in seen:
            continue
        seen.add(key)
        found.append(key)
    return found


def load_history_pairs(player_ids, current_season, prior_season, loader, source_urls, *, workers=4):
    """Bound independent history requests; merge provenance in player order.

    Each task owns its URL list and requests current before prior. A failed current
    observation never substitutes a prior-season history. Injected clients can opt
    for workers=1 when they carry mutable request state.
    """
    if isinstance(workers,bool) or not isinstance(workers,int) or not 1<=workers<=4:
        raise ValueError('history workers must be between one and four')
    def one(player_id):
        urls=[]
        current=loader(player_id,current_season,urls)
        prior=loader(player_id,prior_season,urls) if current is not None else None
        return player_id,current,prior,urls
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results=list(pool.map(one,player_ids))
    current_logs={};prior_logs={};failed=0;prior_failed=0
    for player_id,current,prior,urls in results:
        for url in urls:_remember(source_urls,url)
        current_logs[player_id]=current
        if current is None:failed+=1;continue
        prior_logs[player_id]=prior
        if prior is None:prior_failed+=1
    return current_logs,prior_logs,failed,prior_failed


def load_nhl_game_log(client, player_id, season, fetch, source_urls):
    """Client first. Urllib the same endpoint only when that call fails."""
    url = nhl_game_log_url(player_id, season)
    _remember(source_urls, url)
    if client is not None:
        try:
            payload = client.stats.player_game_log(str(player_id), str(season), 2)
        except Exception:
            payload = None
        else:
            parsed = parse_nhl_game_log(payload)
            if parsed is not None:
                return parsed
    try:
        return parse_nhl_game_log(fetch(url))
    except Exception:
        return None


def _copy_context_row(template: dict, stat: str, baseline_mean: float, sample_size: float, source_url: str) -> dict:
    built = make_row(
        sport=template["sport"],
        game_date=template["game_date"],
        player=template["player"],
        team=template["team"],
        opponent=template["opponent"],
        stat=stat,
        baseline_mean=baseline_mean,
        sample_size=sample_size,
        source_url=source_url,
        retrieved_at=template["retrieved_at"],
        pace_per_game=template.get("pace_per_game"),
        pace_ratio=template.get("pace_ratio"),
        shots_against_per_game=template.get("shots_against_per_game"),
        shots_against_ratio=template.get("shots_against_ratio"),
        epa=template.get("epa"),
        target_share=template.get("target_share"),
        snap_share=template.get("snap_share"),
        ice_time_per_game=template.get("ice_time_per_game"),
        games_started=template.get("games_started"),
        minutes=template.get("minutes"),
        possessions=template.get("possessions"),
    )
    if template.get("player_id") not in (None, ""):
        built["player_id"] = template.get("player_id")
    for key in ("offense_snaps_per_game", "defense_snaps_per_game", "routes_per_game", "route_share"):
        if key in template:
            built[key] = template[key]
    return built


def attach_nhl_game_logs(rows, current_logs, prior_logs=None, season: str | None = None) -> None:
    """Attach fetched logs. A stat the payload does not carry stays log_missing."""
    prior_logs = prior_logs or {}
    for row in rows:
        player_id = str(row.get("player_id") or "")
        if not player_id or player_id not in current_logs:
            continue
        games = current_logs[player_id]
        if games is None:
            _blank_log_fields(row)
            continue
        series = nhl_series(games, row.get("stat"))
        older = prior_logs.get(player_id)
        prior_series = nhl_series(older, row.get("stat")) if older else None
        apply_log_summary(row, series, prior_series)
    if not season:
        return
    existing = {(str(row.get("player_id")), row.get("stat")) for row in rows}
    templates = {str(row.get("player_id")): row for row in rows if row.get("stat") == "shots on goal"}
    extra = []
    for player_id, games in current_logs.items():
        if not games or player_id not in templates:
            continue
        older = prior_logs.get(player_id)
        for stat in ("blocked shots", "hits"):
            if (player_id, stat) in existing:
                continue
            series = nhl_series(games, stat)
            if not series:
                continue
            mixed = sum(item["value"] for item in series) / len(series)
            built = _copy_context_row(
                templates[player_id], stat, mixed, len(series),
                nhl_game_log_url(player_id, season),
            )
            apply_log_summary(built, series, nhl_series(older, stat) if older else None)
            extra.append(built)
            existing.add((player_id, stat))
    rows.extend(extra)


def _made_of_pair(value):
    if value is None or value == "":
        return None
    text = str(value).strip()
    if "-" in text:
        return _num(text.split("-", 1)[0])
    return _num(text)


def parse_espn_gamelog(payload):
    """Regular-season games from the ESPN athlete gamelog. None when that shape is absent."""
    if not isinstance(payload, dict) or "names" not in payload or "seasonTypes" not in payload:
        return None
    names = [str(name) for name in (payload.get("names") or [])]
    events = payload.get("events") if isinstance(payload.get("events"), dict) else {}
    found = {}
    for season_type in payload.get("seasonTypes") or []:
        if not isinstance(season_type, dict):
            continue
        if "regular season" not in str(season_type.get("displayName") or "").lower():
            continue
        for category in season_type.get("categories") or []:
            if not isinstance(category, dict):
                continue
            for event in category.get("events") or []:
                if not isinstance(event, dict):
                    continue
                event_id = str(event.get("eventId") or "")
                if not event_id or event_id in found:
                    continue
                stats = event.get("stats") or []
                meta = events.get(event_id) if isinstance(events.get(event_id), dict) else {}
                game = {
                    "when": str((meta or {}).get("gameDate") or ""),
                    "tie": event_id,
                    "minutes": None,
                    "points": None,
                    "rebounds": None,
                    "assists": None,
                    "threes": None,
                }
                for name, raw in zip(names, stats):
                    if name == "minutes":
                        game["minutes"] = parse_minutes(raw)
                    elif name == "points":
                        game["points"] = _num(raw)
                    elif name == "totalRebounds":
                        game["rebounds"] = _num(raw)
                    elif name == "assists":
                        game["assists"] = _num(raw)
                    elif str(name).startswith("threePointFieldGoalsMade"):
                        game["threes"] = _made_of_pair(raw)
                found[event_id] = game
    return list(found.values())


def nba_series(games, stat: str):
    if games is None:
        return None
    parts = NBA_COMBOS.get(stat)
    series = []
    for game in games:
        if parts:
            values = [game.get(key) for key in parts]
            if any(value is None for value in values):
                continue
            value = sum(values)
        else:
            value = game.get(NBA_LOG_KEYS.get(stat, ""))
            if value is None:
                continue
        series.append(
            {
                "value": value,
                "workload": game.get("minutes"),
                "when": game.get("when") or "",
                "tie": game.get("tie") or "",
            }
        )
    if games and not series:
        return None
    return series


def load_espn_gamelog(fetch, athlete_id, season_year: int, source_urls):
    url = espn_gamelog_url(athlete_id, season_year)
    _remember(source_urls, url)
    try:
        try:
            payload = fetch(url, timeout=ESPN_TIMEOUT)
        except TypeError:
            payload = fetch(url)
    except Exception:
        return None
    return parse_espn_gamelog(payload)


def attach_nba_game_logs(rows, current_logs, prior_logs=None, season_year: int | None = None) -> None:
    prior_logs = prior_logs or {}
    for row in rows:
        player_id = str(row.get("player_id") or "")
        if not player_id or player_id not in current_logs:
            continue
        games = current_logs[player_id]
        if games is None:
            _blank_log_fields(row)
            continue
        older = prior_logs.get(player_id)
        apply_log_summary(
            row,
            nba_series(games, row.get("stat")),
            nba_series(older, row.get("stat")) if older else None,
        )
    if season_year is None:
        return
    existing = {(str(row.get("player_id")), row.get("stat")) for row in rows}
    extra = []
    for row in list(rows):
        if row.get("stat") != "points":
            continue
        player_id = str(row.get("player_id") or "")
        games = current_logs.get(player_id)
        if not games:
            continue
        older = prior_logs.get(player_id)
        for stat in NBA_COMBOS:
            if (player_id, stat) in existing:
                continue
            series = nba_series(games, stat)
            if not series:
                continue
            mixed = sum(item["value"] for item in series) / len(series)
            built = _copy_context_row(row, stat, mixed, len(series), espn_gamelog_url(player_id, season_year))
            apply_log_summary(built, series, nba_series(older, stat) if older else None)
            extra.append(built)
            existing.add((player_id, stat))
    rows.extend(extra)


def index_player_snaps(snap_rows) -> dict:
    index = {}
    for row in snap_rows or []:
        if not isinstance(row, dict) or not _reg_row(row):
            continue
        names = []
        raw_name = row.get("player") or row.get("player_display_name") or ""
        if str(raw_name).strip():
            names.append(str(raw_name).strip().lower())
        player_id = row.get("player_id")
        if player_id not in (None, ""):
            names.append(f"id:{player_id}")
        team = str(row.get("team") or row.get("recent_team") or "")
        if not names or not team:
            continue
        info = {}
        if "offense_snaps" in row:
            info["offense_snaps"] = _num(row.get("offense_snaps"))
        if "defense_snaps" in row:
            info["defense_snaps"] = _num(row.get("defense_snaps"))
        if not info:
            continue
        game_id = row.get("game_id")
        week = row.get("week")
        for name in names:
            if game_id not in (None, ""):
                index[(name, team, "g", str(game_id))] = info
            if week not in (None, ""):
                index[(name, team, "w", str(week))] = info
    return index


def _snap_workload(index, names, team, game_key, week, stat):
    field = "defense_snaps" if stat in NFL_DEFENSE_STATS else "offense_snaps"
    keys = []
    for name in names:
        if game_key:
            keys.append((name, team, "g", str(game_key)))
        if week not in (None, ""):
            keys.append((name, team, "w", str(week)))
    for key in keys:
        info = index.get(key)
        if info and info.get(field) is not None:
            return info[field]
    return None


def _row_snap_total(game_rows, stat):
    field = "defense_snaps" if stat in NFL_DEFENSE_STATS else "offense_snaps"
    if not any(field in row for row in game_rows):
        return None
    total = 0.0
    saw = False
    for row in game_rows:
        if field not in row:
            continue
        number = _num(row.get(field))
        if number is None:
            continue
        total += number
        saw = True
    return total if saw else None


def nfl_series_from_log(log, snap_index, team: str, name: str, player_id, stat: str, column):
    """None when the week log, the player, or the stat column is missing."""
    if log is None:
        return None
    if column is None:
        if "def_tackles_solo" not in log["columns"] and "def_tackle_assists" not in log["columns"]:
            return None
    elif column not in log["columns"]:
        return None
    player = _log_player(log, team, name, player_id)
    if player is None:
        return None
    names = []
    if name:
        names.append(name.strip().lower())
    if player_id not in (None, ""):
        names.append(f"id:{player_id}")
    series = []
    for game_key, game_rows in player["games"].items():
        value = _game_stat(game_rows, column)
        if value is None:
            continue
        week = None
        for row in game_rows:
            week = row.get("week")
            raw_name = row.get("player") or row.get("player_display_name") or ""
            if str(raw_name).strip():
                lowered = str(raw_name).strip().lower()
                if lowered not in names:
                    names.append(lowered)
            if week not in (None, ""):
                break
        workload = _row_snap_total(game_rows, stat)
        if workload is None:
            workload = _snap_workload(snap_index, names, team, game_key, week, stat)
        series.append(
            {
                "value": value,
                "workload": workload,
                "when": next((r.get('game_date') or r.get('gameday') for r in game_rows if r.get('game_date') or r.get('gameday')),
                             week if week not in (None, "") else game_key),
                "tie": str(game_key),
            }
        )
    if player["games"] and not series:
        return None
    return series


def _pipeline_ready(row: dict) -> bool:
    dist = row.get("suggested_dist")
    window = row.get("baseline_window_mean")
    base_n = row.get("baseline_n")
    season_n = row.get("season_n")
    if dist not in {"poisson", "negbin", "normal"}:
        return False
    if window is None or window <= 0 or base_n is None or base_n < 1 or season_n is None:
        return False
    recent_n = row.get("recent_n")
    if recent_n is not None and base_n + recent_n > season_n:
        return False
    if (row.get("recent_mean") is None) != (recent_n is None):
        return False
    if dist == "normal" and not (row.get("sd") and row["sd"] > 0):
        return False
    if dist == "negbin" and not (row.get("var_ratio") is not None and row["var_ratio"] > LOG_VAR_RATIO_POISSON + 1e-9):
        return False
    return True


def prepare_pipeline(rows, quotes, now=None) -> list[dict]:
    """One object per (player, stat, side) on the primary line.

    The object is the batch schema: project fields, ``book_side`` on each
    book, retrieved age in minutes, and the qualitative defaults left for
    the research pass. A row without a log distribution or a two-sided quote
    is omitted. The season rate is not copied in to fill either gap.
    ``baseline_mean`` in the object is the non-overlapping baseline window.
    """
    payloads = []
    for row in rows or []:
        if not _pipeline_ready(row):
            continue
        found = quotes_for_row(quotes, row)
        price = primary_price(found)
        if not price or price.get("line") is None:
            continue
        line = float(price["line"])
        on_line = [
            quote
            for quote in found
            if quote.get("line") is not None and abs(float(quote["line"]) - line) <= 1e-9
        ]
        if not on_line:
            continue
        for side in ("over", "under"):
            groups = build_consensus_input(on_line, now=now, side=side)
            info = next(
                (group for group in groups if abs(float(group["line"]) - line) <= 1e-9),
                None,
            )
            if not info or not info.get("books"):
                continue
            payload = {
                "id": f"{row.get('sport')}|{row.get('player')}|{row.get('stat')}|{side}",
                "side_name": f"{row.get('player')} {side} {info['line']} {row.get('stat')}",
                "team": row.get("team"),
                "opponent": row.get("opponent"),
                "event_id_namespace": row.get("event_id_namespace"),
                "game_date": row.get("game_date"),
                "player_id": row.get("player_id"),
                "event_id": row.get("event_id"),
                "dist": row["suggested_dist"],
                "side": side,
                "line": info["line"],
                "baseline_mean": row["baseline_window_mean"],
                "baseline_n": row["baseline_n"],
                "season_n": row["season_n"],
                "stat": row.get("stat"),
                "soft_flags": 0,
                "mechanisms": 0,
                "hard_veto": "no",
                "data_veto": "no",
                "research_checklist": "no",
                "books": info["books"],
            }
            if row.get('observation_ids') is not None:
                ids=dict(row['observation_ids'])
                # Prior histories are transmitted only when actually used.
                if not row.get('prior_n') or row.get('season_n',0)>=SHORT_SEASON_GAMES:ids['prior']=[]
                payload['observation_ids']=ids
            if row.get("recent_n") is not None:
                payload["recent_mean"] = row["recent_mean"]
                payload["recent_n"] = row["recent_n"]
            if row["suggested_dist"] == "normal":
                payload["sd"] = row["sd"]
            elif row["suggested_dist"] == "negbin":
                payload["var_ratio"] = row["var_ratio"]
            season_n = row.get("season_n")
            prior_mean = row.get("prior_season_mean")
            prior_n = row.get("prior_n")
            if (
                season_n is not None
                and season_n < SHORT_SEASON_GAMES
                and prior_mean is not None
                and prior_mean >= 0
                and prior_n
            ):
                payload["prior_mean"] = prior_mean
                payload["prior_n"] = prior_n
            age = info.get("retrieved_minutes_ago")
            if age is not None:
                payload["retrieved_minutes_ago"] = age
            if info.get('market_retrieved_at'):
                payload['market_retrieved_at'] = info['market_retrieved_at']
            if str(row.get("sport") or "").upper() == "NFL" and any(
                row.get(k) is not None
                for k in (
                    "first_read_target_share",
                    "checkdown_target_share",
                    "team_pass_attempts_expected",
                    "def_matchup_factor",
                )
            ):
                payload["sport"] = "NFL"
                for rkey in (
                    "team_pass_attempts_expected",
                    "team_bucket_throw_share",
                    "player_bucket_target_share",
                    "conversion",
                    "volume_source",
                    "def_matchup_factor",
                    "first_read_target_share",
                    "first_read_player_games",
                    "first_read_team_games",
                    "checkdown_target_share",
                    "checkdown_player_games",
                    "checkdown_team_games",
                    "reads_charting_ok",
                    "reads_charting_missing",
                    "reads_charting_status",
                    "reads_join_ok",
                    "reads_join_failed",
                    "reads_join_status",
                ):
                    if row.get(rkey) is not None:
                        payload[rkey] = row[rkey]
            payloads.append(payload)
    payloads.sort(key=lambda item: (item["id"], item["side"]))
    return payloads


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def run_prep(argv: list[str] | None = None):
    """``prep --stdout`` prints pipeline JSONL. It does not fetch and does not grade."""
    parser = argparse.ArgumentParser(prog="fetch_slate.py prep")
    parser.add_argument("--stdout", action="store_true", help="Print one pipeline object per line.")
    parser.add_argument("--slate", default=str(DEFAULT_OUT))
    parser.add_argument("--quotes", default=None)
    parser.add_argument("--now", default=None, help="ISO timestamp used to age the quotes.")
    args = parser.parse_args(argv)
    slate_path = Path(args.slate)
    if not slate_path.exists():
        sys.stderr.write(f"prep: slate file not found: {slate_path}\n")
        raise SystemExit(1)
    quotes_path = Path(args.quotes) if args.quotes else quotes_path_for(slate_path)
    try:
        rows = read_jsonl(slate_path)
        quotes = read_jsonl(quotes_path) if quotes_path.exists() else []
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"prep: invalid JSON: {exc}\n")
        raise SystemExit(1)
    payloads = prepare_pipeline(rows, quotes, now=args.now)
    coverage = {
        "slate_rows": len(rows), "quote_rows": len(quotes),
        "priced_sides": len(payloads),
        "unpriced_or_ungradeable_rows": max(0, len(rows) - len({item["id"].rsplit("|", 1)[0] for item in payloads})),
    }
    sys.stderr.write("prep coverage: " + json.dumps(coverage, sort_keys=True) + "\n")
    if rows and not payloads:
        code = "NO_ODDS_QUOTES" if not quotes else "NO_TWO_SIDED_GRADEABLE_QUOTES"
        sys.stderr.write(f"prep: BLOCKED ({code}); not an empty successful slate\n")
        raise SystemExit(2)
    sys.stdout.write("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in payloads))
    sys.stdout.flush()
    return {"rows": len(payloads), "stdout": bool(args.stdout)}


def fetch_nhl(game_date: str, retrieved_at: str, client=None, client_error: str | None = None, fetch=fetch_json, source_urls=None, history_workers=4):
    notes = []
    if client_error:
        notes.append(client_error)
    season = None
    schedule_url = f"{NHL_WEB}/schedule/{game_date}"
    _remember(source_urls, schedule_url)

    def schedule_fallback():
        return fetch(schedule_url)

    schedule, note = _call_nhl(
        client,
        "schedule.daily_schedule",
        lambda: client.schedule.daily_schedule(date=game_date),
        schedule_fallback,
    )
    if note:
        notes.append(note)
    games = games_from_schedule(schedule, game_date)
    if games:
        season = str(games[0].get("season") or season_id_from_date(game_date))
    else:
        season = season_id_from_date(game_date)
        if schedule is None:
            notes.append(f"schedule: no games. Endpoint {schedule_url} failed or was empty.")

    def page_stats(method_name: str):
        # Client stats only. The club-stats loop below is the urllib fallback.
        if client is not None:
            try:
                method = getattr(client.stats, method_name)
                rows = []
                start = 0
                # NHL REST caps result pages at 100 even when a larger limit
                # is requested. Treating that cap as EOF drops most skaters.
                page = 100
                while start < 4000:
                    kwargs = {
                        "start_season": season,
                        "end_season": season,
                        "start": start,
                        "limit": page,
                    }
                    if method_name == "team_summary":
                        kwargs["fact_cayenne_exp"] = "gamesPlayed>=1"
                    batch = method(**kwargs)
                    if not batch:
                        break
                    rows.extend(batch)
                    if len(batch) < page:
                        break
                    start += page
                return rows, None
            except Exception as exc:
                notes.append(f"{method_name}: NHLClient failed ({exc})")
        return None, f"{method_name}: client unavailable"

    skaters, skater_note = page_stats("skater_stats_summary")
    goalies, goalie_note = page_stats("goalie_stats_summary")
    teams, team_note = page_stats("team_summary")
    for note in (skater_note, goalie_note, team_note):
        if note and "failed" in note:
            notes.append(note)

    source = NHL_STATS_SKATER
    if skaters is None or goalies is None or teams is None:
        slate = slate_matchups(games)
        recovered_skaters, recovered_goalies, recovered_teams = [], [], []
        for abbrev in sorted(slate):
            url = f"{NHL_WEB}/club-stats/{abbrev}/{season}/2"
            _remember(source_urls, url)
            try:
                payload = fetch(url)
            except Exception as exc:
                notes.append(f"club-stats {abbrev}: urllib {url} failed: {exc}")
                continue
            team_skaters, team_goalies, team_rate = club_stats_to_summaries(payload, abbrev)
            if skaters is None:
                recovered_skaters.extend(team_skaters)
            if goalies is None:
                recovered_goalies.extend(team_goalies)
            if teams is None:
                recovered_teams.append(team_rate)
        if skaters is None:
            skaters = recovered_skaters
            source = f"{NHL_WEB}/club-stats/{{team}}/{season}/2"
        if goalies is None:
            goalies = recovered_goalies
        if teams is None:
            teams = recovered_teams
    _remember(source_urls, source)
    if source == NHL_STATS_SKATER:
        _remember(source_urls, NHL_STATS_GOALIE)
    rows = nhl_rows_from_summaries(
        games,
        skaters or [],
        goalies or [],
        teams or [],
        game_date,
        retrieved_at,
        source,
    )
    prior_season = previous_season_id(season)
    current_logs,prior_logs,failed,prior_failed=load_history_pairs(
        _player_ids(rows),season,prior_season,
        lambda player_id,year,urls:load_nhl_game_log(client,player_id,year,fetch,urls),
        source_urls,workers=history_workers)
    attach_nhl_game_logs(rows, current_logs, prior_logs, season)
    if failed:
        notes.append(
            f"nhl: game-log failed for {failed} player(s). "
            f"Endpoint {NHL_WEB}/player/{{id}}/game-log/{{season}}/2. Log fields left null."
        )
    if prior_failed:
        notes.append(
            f"nhl: prior-season game-log failed for {prior_failed} player(s). "
            "prior_season_mean left null."
        )
    return rows, notes


def frame_to_rows(frame) -> list[dict]:
    if frame is None:
        return []
    if hasattr(frame, "to_dicts"):
        return frame.to_dicts()
    if isinstance(frame, list):
        return frame
    raise TypeError(f"expected a Polars frame or a list of rows, got {type(frame).__name__}")


def load_nfl_module():
    try:
        import nflreadpy as nfl
    except Exception as exc:
        return None, f"nflreadpy import failed ({type(exc).__name__}: {exc})"
    return nfl, None


def date_nfl_weeks(rows,games,season):
    """Attach real game dates/IDs to both seasons before source-cache persistence."""
    index={}
    for game in games or []:
        if str(game.get('season'))!=str(season) or game.get('game_type',game.get('season_type'))!='REG':continue
        for team in (game.get('home_team'),game.get('away_team')):
            key=(str(game.get('week')),str(team))
            if key in index and index[key].get('game_id')!=game.get('game_id'):
                raise ValueError('ambiguous NFL schedule game')
            index[key]=game
    result=[]
    for row in rows or []:
        if row.get('season') is not None and str(row['season'])!=str(season):continue
        game=index.get((str(row.get('week')),str(_row_team(row))))
        dated=dict(row)
        if game:
            if game.get('gameday'):dated['game_date']=str(game['gameday'])[:10]
            if game.get('game_id'):dated['game_id']=str(game['game_id'])
        result.append(dated)
    return result


def fetch_nfl(game_date: str, retrieved_at: str, loader=None, source_urls=None, season_store_path=None):
    persist_season = loader is None or season_store_path is not None
    notes = []
    _remember(source_urls, NFL_SOURCE)
    _remember(source_urls, "https://github.com/nflverse/nflverse-data")
    if loader is None:
        loader, error = load_nfl_module()
        if error:
            return [], [error]
    season = int(nfl_season_from_date(game_date))

    def call(name, fn, columns=None):
        try:
            frame = fn()
            if columns and hasattr(frame, "select") and hasattr(frame, "columns"):
                keep = [column for column in columns if column in frame.columns]
                if keep and len(keep) < len(frame.columns):
                    frame = frame.select(keep)
            return frame_to_rows(frame), None
        except Exception as exc:
            return None, f"nfl: {name} failed ({type(exc).__name__}: {exc}). Those fields left null."

    games, note = call("load_schedules", lambda: loader.load_schedules(seasons=[season]))
    if note:
        return [], [note]
    if not nfl_games_on(games or [], game_date):
        return [], [f"nfl: load_schedules returned no REG game on {game_date}. No NFL rows."]
    stats, note = call(
        "load_player_stats",
        lambda: loader.load_player_stats(seasons=[season], summary_level="reg"),
    )
    if note or stats is None:
        return [], [note or "nfl: load_player_stats returned nothing. No NFL rows."]
    weeks, week_note = call(
        "load_player_stats week",
        lambda: loader.load_player_stats(seasons=[season], summary_level="week"),
    )
    if week_note:
        notes.append(week_note)
        weeks = None
    if weeks:
        weeks=date_nfl_weeks(weeks,games,season)
    prior_season = season - 1
    prior_loaded, prior_note = call(
        "load_player_stats prior week",
        lambda: loader.load_player_stats(seasons=[prior_season], summary_level="week"),
    )
    prior_weeks = None
    if prior_note:
        notes.append(prior_note)
    else:
        prior_weeks = [
            row
            for row in (prior_loaded or [])
            if str(row.get("season") or "") == str(prior_season)
        ]
        if prior_weeks:
            prior_games,prior_schedule_note=call('load_schedules prior',lambda:loader.load_schedules(seasons=[prior_season]))
            if prior_schedule_note:notes.append(prior_schedule_note)
            else:prior_weeks=date_nfl_weeks(prior_weeks,prior_games,prior_season)
    snaps, snap_note = call("load_snap_counts", lambda: loader.load_snap_counts(seasons=[season]))
    if snap_note:
        notes.append(snap_note)
        snaps = []
    team_stats, team_note = call(
        "load_team_stats",
        lambda: loader.load_team_stats(seasons=[season], summary_level="reg"),
    )
    if team_note:
        notes.append(team_note)
        team_stats = []
    from nfl_season_store import FTN_FIELDS, PBP_FIELDS, SeasonStore, candidate_context
    from nfl_context_data import PBP_FIELDS as CONTEXT_PBP_FIELDS
    charting, chart_note = call(
        "load_ftn_charting",
        lambda: loader.load_ftn_charting(seasons=[season]),
        tuple(dict.fromkeys(FTN_READ_COLUMNS + FTN_FIELDS)),
    )
    if chart_note:
        notes.append(chart_note)
        charting = None
    pbp, pbp_note = call(
        "load_pbp",
        lambda: loader.load_pbp(seasons=[season]),
        tuple(dict.fromkeys(PBP_READ_COLUMNS + PBP_FIELDS + CONTEXT_PBP_FIELDS)),
    )
    if pbp_note:
        notes.append(pbp_note)
        pbp = None
    read_table = (
        progression_table(charting, pbp, positions=position_index(stats))
        if charting is not None and pbp is not None
        else None
    )
    if charting is not None and pbp is not None and read_table is None:
        notes.append("nfl: load_ftn_charting join to load_pbp failed. Read features omitted.")
    elif read_table and read_table.get("status") == "unmatched":
        notes.append("nfl: load_ftn_charting join to load_pbp matched no plays. Read features omitted.")
        read_table = None
    elif read_table and read_table.get("status") == "missing":
        read_table = None
    rows = nfl_rows_from_tables(
        games or [],
        stats,
        snaps or [],
        game_date,
        retrieved_at,
        NFL_SOURCE,
        team_rows=team_stats if team_stats is not None else [],
        week_rows=weeks,
        read_table=read_table,
        prior_week_rows=prior_weeks or None,
    )
    if persist_season and pbp is not None:
        try:
            from nfl_context_live import write as save_context, cache_path
            context_store=Path(season_store_path) if season_store_path else SKILL_ROOT/'data'/'season'/f'nfl_{season}.sqlite3'
            save_context(cache_path(context_store,season),
                {"stats":weeks or [],"snaps":snaps or [],"schedule":games or [],"pbp":pbp},
                charting,stats,season=season,retrieved_at=retrieved_at)
        except Exception as exc:
            notes.append(f'nfl: joint context snapshot unavailable ({type(exc).__name__}: {exc})')
        try:
            path=Path(season_store_path) if season_store_path else SKILL_ROOT/'data'/'season'/f'nfl_{season}.sqlite3'
            store=SeasonStore(path)
            store.refresh(season,pbp,charting,games or [],as_of=retrieved_at)
            profiles=store.profiles(season,as_of=retrieved_at)
            for row in rows:
                if row.get('player_id'):
                    row['season_context']=candidate_context(profiles,row.get('team'),row.get('opponent'),row['player_id'])
        except Exception as exc:
            notes.append(f'nfl: season store unavailable ({type(exc).__name__}: {exc})')
    return rows, notes


def espn_nba_counting_url(season_year: int, page: int = 1) -> str:
    """One byathlete page. limit=500 returned every athlete in one page when probed."""
    url = f"{NBA_SOURCE}?season={int(season_year)}&seasontype=2&limit=500"
    if page > 1:
        url += f"&page={int(page)}"
    return url


def load_espn_nba_counting_stats(fetch, season_year: int) -> dict:
    """Fetch statistics/byathlete and append later pages. Categories stay from page 1."""
    payload = fetch(espn_nba_counting_url(season_year), timeout=ESPN_TIMEOUT)
    if not isinstance(payload, dict):
        raise ValueError("statistics/byathlete response was not a JSON object")
    pages = (payload.get("pagination") or {}).get("pages") or 1
    try:
        page_count = int(pages)
    except (TypeError, ValueError):
        page_count = 1
    if page_count < 1:
        page_count = 1
    if page_count > 10:
        raise RuntimeError(f"statistics/byathlete reported {page_count} pages")
    athletes = list(payload.get("athletes") or [])
    for page in range(2, page_count + 1):
        nxt = fetch(espn_nba_counting_url(season_year, page), timeout=ESPN_TIMEOUT)
        if not isinstance(nxt, dict):
            raise ValueError("statistics/byathlete response was not a JSON object")
        athletes.extend(nxt.get("athletes") or [])
    merged = dict(payload)
    merged["athletes"] = athletes
    return merged


class NbaPaceClient:
    """LeagueDashTeamStats only. The HTTP timeout is capped at 20 seconds."""

    def __init__(self, timeout: float = NBA_PACE_TIMEOUT):
        self.timeout = int(min(timeout, NBA_PACE_TIMEOUT))

    def team_pace(self, season: str) -> dict:
        from nba_api.stats.endpoints import leaguedashteamstats

        stats = leaguedashteamstats.LeagueDashTeamStats(
            season=season,
            per_mode_detailed="PerGame",
            season_type_all_star="Regular Season",
            measure_type_detailed_defense="Advanced",
            timeout=self.timeout,
        )
        from nba_api.stats.static import teams
        abbreviations = {str(t["id"]): t["abbreviation"] for t in teams.get_teams()}
        table = team_pace_table(stats.get_dict(), abbreviations)
        if not table or not any(v.get("pace") is not None for v in table.values()):
            raise ValueError("LeagueDashTeamStats returned no usable team pace rows")
        return table


def fetch_nba(game_date: str, retrieved_at: str, fetch=None, pace_client=None, source_urls=None, history_workers=4):
    """ESPN scoreboard and counting stats. Pace stays LeagueDashTeamStats.

    A pace timeout or error leaves pace and possessions null and keeps the
    ESPN player rows. Schedule and counting-stat failures return no NBA rows.
    """
    fetch = fetch or fetch_json
    notes = []
    compact = game_date.replace("-", "")
    scoreboard_url = ESPN_SCOREBOARD.format(sport_path="basketball/nba", compact=compact)
    _remember(source_urls, scoreboard_url)
    try:
        scoreboard = fetch(scoreboard_url, timeout=ESPN_TIMEOUT)
    except Exception as exc:
        return [], f"nba: ESPN scoreboard failed ({type(exc).__name__}: {exc}). No NBA rows."
    matchups = matchups_from_scoreboard(scoreboard)
    if not matchups:
        return [], "nba: ESPN scoreboard returned no games. No NBA rows."
    _remember(source_urls, espn_nba_counting_url(nba_espn_season_year(game_date)))
    try:
        players = load_espn_nba_counting_stats(fetch, nba_espn_season_year(game_date))
    except Exception as exc:
        return [], (
            "nba: ESPN statistics/byathlete failed "
            f"({type(exc).__name__}: {exc}). Counting stats left null. No NBA rows."
        )
    if not espn_has_counting_averages(players):
        return [], (
            "nba: ESPN statistics/byathlete did not include season averages. "
            "Counting stats left null. No NBA rows."
        )
    if pace_client is None:
        pace_client = NbaPaceClient()
    team_pace = {}
    _remember(source_urls, "https://stats.nba.com/stats/leaguedashteamstats")
    try:
        team_pace = pace_client.team_pace(nba_season_from_date(game_date)) or {}
    except Exception as exc:
        notes.append(
            "nba: LeagueDashTeamStats failed "
            f"({type(exc).__name__}: {exc}). Pace and possessions left null."
        )
    rows = nba_rows_from_stats(players, matchups, game_date, retrieved_at, NBA_SOURCE, team_pace)
    season_year = nba_espn_season_year(game_date)
    current_logs,prior_logs,failed,prior_failed=load_history_pairs(
        _player_ids(rows),season_year,season_year-1,
        lambda player_id,year,urls:load_espn_gamelog(fetch,player_id,year,urls),
        source_urls,workers=history_workers)
    attach_nba_game_logs(rows, current_logs, prior_logs, season_year)
    if failed:
        notes.append(
            f"nba: ESPN athlete gamelog failed for {failed} player(s) "
            f"({NBA_GAMELOG}). Log fields left null."
        )
    if prior_failed:
        notes.append(
            f"nba: prior-season gamelog failed for {prior_failed} player(s). "
            "prior_season_mean left null."
        )
    return rows, " ".join(notes) if notes else None


def fetch_odds(game_date: str, fetch=fetch_json, source_urls=None, provider=None, sports=None):
    """Player props from the odds provider. ESPN scoreboard odds are not props.

    With no configured odds credential the provider returns [] and a note. This does not
    invent a line or a price. The return is (quotes, note).
    """
    if os.environ.get("PICKEM_DISABLE_ODDS") == "1":
        return [], "ODDS_DISABLED_FOR_HISTORICAL_COLLECTION: free public game data only; no paid sportsbook requests made."
    if provider is None:
        provider = PropLineProvider(fetch=fetch)
    try:
        quotes = provider.fetch(game_date, sports)
    except Exception as exc:
        secret = getattr(provider, "api_key", "")
        return [], f"odds: {type(exc).__name__}: {redact(exc, secret)}. No prices were invented."
    # Optional, quota-capped NHL blocked-shot fallback: only when the primary
    # bookmaker payload genuinely contains no blocked-shot markets.
    # The Odds API event-odds endpoint is chargeable, so bound requests.
    note = provider.note
    if (sports is None or any(str(s).upper() in ('NHL','ICEHOCKEY_NHL') for s in sports)):
        from nhl_blocks_fallback import fetch_nhl_blocked_shots
        fallback, diag = fetch_nhl_blocked_shots(
            game_date, quotes, fetch=fetch,
            api_key=os.environ.get('ODDS_API_KEY') or '',
            enabled=os.environ.get('PICKEM_ENABLE_ODDS_API_NHL_BLOCKS') == '1')
        if fallback:
            quotes=list(quotes)+fallback
            # Do not conflate event-id namespaces or silently replace prices.
            from odds_providers import dedupe_quotes
            quotes=dedupe_quotes(quotes)
        if diag.get('status') != 'disabled':
            note=(note+' ' if note else '')+'NHL_BLOCKS_FALLBACK_JSON='+json.dumps(
                diag,sort_keys=True,separators=(',',':'))
    for url in getattr(provider, "source_urls", []) or []:
        _remember(source_urls, url)
    for quote in quotes:
        _remember(source_urls, quote.get("source_url"))
    return list(quotes), note


def _as_notes(notes) -> list[str]:
    if notes is None or notes == "":
        return []
    if isinstance(notes, str):
        return [notes]
    return [str(item) for item in notes if item not in (None, "")]


def _split_feed_result(result):
    if not isinstance(result, tuple):
        return result, [], []
    if len(result) >= 3:
        return result[0], result[1], list(result[2] or [])
    if len(result) == 2:
        return result[0], result[1], []
    if len(result) == 1:
        return result[0], [], []
    return None, [], []


def _feed_record(status: str, rows: int, started: str, finished: str, notes, source_urls) -> dict:
    urls = []
    for url in source_urls or []:
        _remember(urls, url)
    return {
        "status": status,
        "rows": int(rows),
        "started_at": started,
        "finished_at": finished,
        "notes": list(notes),
        "source_urls": urls,
    }


def _urls_from_rows(rows) -> list[str]:
    urls = []
    for row in rows or []:
        if isinstance(row, dict):
            _remember(urls, row.get("source_url"))
    return urls


def _run_feed(name: str, fn, clock) -> tuple[dict, object]:
    started = clock()
    payload = None
    urls: list[str] = []
    failed = False
    if fn is None:
        notes = [f"{name}: feed was not run"]
        failed = True
    else:
        try:
            payload, raw_notes, urls = _split_feed_result(fn())
            notes = _as_notes(raw_notes)
            urls = list(urls or [])
        except Exception as exc:
            notes = [f"{name}: {type(exc).__name__}: {exc}"]
            urls = []
            payload = None
            failed = True
    finished = clock()
    if name == "odds":
        quote_list = payload if isinstance(payload, list) else []
        count = len(quote_list)
        status = "failed" if failed or count == 0 else "ok"
        record = _feed_record(status, count, started, finished, notes, urls)
        record["priced_stats"] = count
        return record, payload if isinstance(payload, list) else {}
    if failed or not isinstance(payload, list):
        rows = []
    else:
        rows = payload
    for url in _urls_from_rows(rows):
        _remember(urls, url)
    status = "failed" if failed or not rows else "ok"
    kept = rows if status == "ok" else []
    return _feed_record(status, len(kept), started, finished, notes, urls), kept


def _builtin_fetchers(game_date, retrieved_at, nhl_client, nhl_client_error, fetch_json_fn, data_dir=None):
    buckets = {name: [] for name in FEED_NAMES}

    def nhl():
        rows, notes = fetch_nhl(
            game_date,
            retrieved_at,
            client=nhl_client,
            client_error=nhl_client_error,
            fetch=fetch_json_fn,
            source_urls=buckets["nhl"],
        )
        return rows, notes, list(buckets["nhl"])

    def nfl():
        path=Path(data_dir)/'season'/f'nfl_{int(nfl_season_from_date(game_date))}.sqlite3' if data_dir else None
        rows, notes = fetch_nfl(game_date, retrieved_at, source_urls=buckets["nfl"],season_store_path=path)
        return rows, notes, list(buckets["nfl"])

    def nba():
        rows, note = fetch_nba(
            game_date,
            retrieved_at,
            fetch=fetch_json_fn,
            source_urls=buckets["nba"],
        )
        return rows, note, list(buckets["nba"])

    def odds():
        quotes, note = fetch_odds(game_date, fetch=fetch_json_fn, source_urls=buckets["odds"])
        return quotes, note, list(buckets["odds"])

    return {"nhl": nhl, "nfl": nfl, "nba": nba, "odds": odds}


def quotes_path_for(out: Path) -> Path:
    """``data/slate_fetch.jsonl`` -> ``data/odds_quotes.jsonl``."""
    return Path(out).with_name("odds_quotes.jsonl")


def collected_coverage(rows,quotes):
    """Report collected-row coverage without asserting upstream completeness."""
    counts={}
    for row in rows:
        sport=str(row.get('sport') or 'UNKNOWN')
        group=counts.setdefault(sport,dict(rows=0,history_ready_rows=0,priced_rows=0,priced_history_ready_rows=0))
        history=_pipeline_ready(row)
        priced=primary_price(quotes_for_row(quotes,row)) is not None
        group['rows']+=1;group['history_ready_rows']+=int(history)
        group['priced_rows']+=int(priced);group['priced_history_ready_rows']+=int(history and priced)
    return dict(by_sport=counts,
                has_priced_history_rows=any(c['priced_history_ready_rows'] for c in counts.values()),
                scope='collected rows only; quote freshness, source completeness and research readiness are not established')


def collect(
    game_date: str,
    retrieved_at: str | None = None,
    nhl_client=None,
    nhl_client_error: str | None = None,
    fetch_json_fn=fetch_json,
    fetchers=None,
    clock=None,
    quotes_path=None,
) -> tuple[list[dict], dict]:
    """Fetch every feed. A feed with zero rows is status ``failed`` and is not required for the others."""
    clock = clock or utc_now
    retrieved_at = retrieved_at or clock()
    if fetchers is None:
        fetchers = _builtin_fetchers(
            game_date,
            retrieved_at,
            nhl_client,
            nhl_client_error,
            fetch_json_fn,
            data_dir=Path(quotes_path).parent if quotes_path else None,
        )
    summary = {"date": game_date, "retrieved_at": retrieved_at, "feeds": {}}
    player_rows: list[dict] = []
    quote_payload: list = []
    quotes_ready = False
    for name in FEED_NAMES:
        record, payload = _run_feed(name, fetchers.get(name), clock)
        summary["feeds"][name] = record
        if name == "odds":
            if isinstance(payload, list):
                quotes_ready = True
                quote_payload = payload
        elif record["status"] == "ok" and isinstance(payload, list):
            player_rows.extend(payload)
    resolved, unmatched = attach_prices(player_rows, quote_payload)
    if quotes_ready and quotes_path is not None:
        write_jsonl(ordered_quotes(resolved), Path(quotes_path))
        summary["quotes_out"] = str(quotes_path)
    note = unmatched_note(unmatched)
    if note:
        summary["feeds"]["odds"]["notes"].append(note)
    summary["rows"] = len(player_rows)
    summary['coverage']=collected_coverage(player_rows,resolved)
    summary["flagged"] = sum(1 for row in player_rows if row.get("flag"))
    summary["usable"] = bool(player_rows)
    summary["missing"] = [name for name in FEED_NAMES if summary["feeds"][name]["status"] != "ok"]
    return player_rows, summary


def atomic_write_text(path: Path, text: str, *, replace=None) -> None:
    """Write `text` to a temp file in the same directory, then `os.replace` it into place."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    swap = replace or os.replace
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=os.fspath(path.parent))
    renamed = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        swap(tmp_name, os.fspath(path))
        renamed = True
    finally:
        if not renamed and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def write_jsonl(rows: list[dict], path: Path) -> None:
    lines = [json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows]
    atomic_write_text(path, "".join(lines))


def write_json(payload: dict, path: Path) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def meta_path_for(out: Path) -> Path:
    """``data/slate_fetch.jsonl`` -> ``data/slate_fetch.meta.json``."""
    return Path(out).with_suffix(".meta.json")


def failed_output_path(out: Path) -> Path:
    """``data/slate_fetch.jsonl`` -> ``data/slate_fetch.jsonl.failed.json``."""
    return Path(str(out) + ".failed.json")


def meta_document(summary: dict) -> dict:
    feeds = {}
    for name, feed in (summary.get("feeds") or {}).items():
        feeds[name] = {
            "status": feed.get("status"),
            "rows": feed.get("rows"),
            "started_at": feed.get("started_at"),
            "finished_at": feed.get("finished_at"),
            "notes": list(feed.get("notes") or []),
            "source_urls": list(feed.get("source_urls") or []),
        }
    return {
        "date": summary.get("date"),
        "retrieved_at": summary.get("retrieved_at"),
        "usable": bool(summary.get("usable")),
        "missing": list(summary.get("missing") or []),
        "rows": summary.get("rows", 0),
        "coverage": summary.get('coverage'),
        "feeds": feeds,
    }


def commit_slate(rows: list[dict], summary: dict, out: Path) -> int:
    """Persist rows. Zero rows leaves `out` untouched, writes `<out>.failed.json`, and returns 2."""
    out = Path(out)
    summary["out"] = str(out)
    summary["meta"] = str(meta_path_for(out))
    summary["usable"] = bool(rows)
    if not rows:
        failed = failed_output_path(out)
        summary["failed_out"] = str(failed)
        if not summary.get("missing"):
            summary["missing"] = list(FEED_NAMES)
        write_json(summary, failed)
        write_json(meta_document(summary), meta_path_for(out))
        return 2
    from usage_baseline import persist
    persist(rows,out.parent)
    write_jsonl(rows, out)
    write_json(meta_document(summary), meta_path_for(out))
    failed = failed_output_path(out)
    if failed.exists():
        try:
            failed.unlink()
        except OSError:
            pass
    return 0


def probe_import(module_name: str) -> tuple[bool, str]:
    try:
        __import__(module_name)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, ""


def probe_host(host: str, timeout: float = PREFLIGHT_TIMEOUT, resolver=None, opener=None) -> tuple[bool, str]:
    """DNS plus one HTTPS request. An HTTP response, including 4xx and 5xx, means the host answered.

    Never raises. `resolver` and `opener` default to socket.getaddrinfo and urllib.request.urlopen.
    """
    resolve = resolver or socket.getaddrinfo
    open_url = opener or urllib.request.urlopen
    try:
        resolve(host, 443, type=socket.SOCK_STREAM)
    except Exception as exc:
        # HTTPS proxies can resolve upstream hosts even when local DNS is
        # unavailable. Let the configured proxy perform its normal access check.
        if resolver is not None or not urllib.request.getproxies().get("https"):
            return False, f"dns {type(exc).__name__}: {exc}"
    request = urllib.request.Request(
        PREFLIGHT_URLS.get(host, f"https://{host}/"),
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        method="GET",
    )
    try:
        with open_url(request, timeout=timeout) as response:
            code = getattr(response, "status", None)
            if code is None:
                code = response.getcode()
            return True, f"HTTP {code}"
    except urllib.error.HTTPError as exc:
        # A 404 on `/` can be normal for an API host; 401/403/429 mean
        # authentication/permission/quota and must NOT be reported as healthy.
        if exc.code in (401, 403, 429):
            return False, f"HTTP {exc.code} (auth/quota failure)"
        return True, f"HTTP {exc.code} (host reachable, API not validated)"
    except Exception as exc:
        return False, f"https {type(exc).__name__}: {exc}"


def _safe_probe(fn, arg) -> tuple[bool, str]:
    try:
        result = fn(arg)
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if isinstance(result, tuple) and result:
        detail = ""
        if len(result) > 1 and result[1] is not None:
            detail = " ".join(str(result[1]).split())
        return bool(result[0]), detail
    return bool(result), ""


def preflight(import_check=None, reach_check=None, timeout: float = PREFLIGHT_TIMEOUT) -> dict:
    """Check feed imports and host reachability. Never raises."""
    check_import = import_check or probe_import
    check_reach = reach_check or (lambda host: probe_host(host, timeout=timeout))
    checks = []
    try:
        for module, feed in PREFLIGHT_IMPORTS:
            ok, detail = _safe_probe(check_import, module)
            checks.append({"kind": "import", "name": module, "feed": feed, "ok": ok, "detail": detail})
        for host, feed, label in PREFLIGHT_HOSTS:
            ok, detail = _safe_probe(check_reach, host)
            checks.append({"kind": "https", "name": label, "feed": feed, "ok": ok, "detail": detail})
    except Exception as exc:
        checks.append(
            {
                "kind": "preflight",
                "name": "preflight",
                "feed": "",
                "ok": False,
                "detail": f"{type(exc).__name__}: {exc}",
            }
        )
    if import_check is None and reach_check is None:
        from local_credentials import propline_api_key
        try:
            key_present = bool(propline_api_key())
            key_detail = 'present' if key_present else 'missing; player props cannot be priced'
        except ValueError:
            key_present = False
            key_detail = 'invalid local credentials configuration'
        checks.append({"kind": "credential", "name": "PROPLINE_API_KEY", "feed": "odds",
                       "ok": key_present, "detail": key_detail})
    # Capability assessment is separate from the strict diagnostic "ok" flag.
    # NHL has a urllib/REST fallback without nhl-api-py; NBA's ESPN path does
    # not require nba_api or stats.nba.com. Missing an optional dependency must
    # not suppress data from independent, working feeds.
    def passes(kind, name):
        values = [bool(c.get("ok")) for c in checks if c.get("kind") == kind and c.get("name") == name]
        return bool(values) and all(values)
    feeds_ready = {
        "nhl": passes("https", "api-web.nhle.com"),
        "nba": passes("https", "site.api.espn.com") and passes("https", "site.web.api.espn.com"),
        "nfl": (passes("import", "nflreadpy") and passes("import", "polars")
                and passes("https", "github.com (nflverse)")),
        "odds": (passes("https", "api.prop-line.com") and
                 (passes("credential", "PROPLINE_API_KEY") if any(c.get("kind") == "credential" for c in checks)
                  else True)),
    }
    operational = feeds_ready["odds"] and any(feeds_ready[f] for f in ("nhl", "nba", "nfl"))
    return {"ok": bool(checks) and all(item["ok"] for item in checks), "checks": checks,
            "feeds_ready": feeds_ready, "operational": operational}


def load_odds_game_events(game_date: str, fetch=fetch_json, provider=None) -> list[dict]:
    """Public sportsbook game spreads/totals from PropLine bulk feeds."""
    from odds_providers import SPORTS, event_on_date
    if os.environ.get("PICKEM_DISABLE_ODDS") == "1":
        return []
    if provider is None:
        provider = PropLineProvider(fetch=fetch)
    secret = str(getattr(provider, "api_key", "") or "").strip()
    if not secret:
        return []
    markets = (("spreads", "spread"), ("totals", "total"))
    events = []
    for _sport, key, _player_markets in SPORTS:
        payload, error = provider._bulk_odds(key, markets, secret)
        if error:
            continue
        for event in payload:
            if not isinstance(event, dict) or not event_on_date(event.get("commence_time"), game_date):
                continue
            event = dict(event)
            event["source_url"] = provider._url(f"/v1/sports/{key}/odds", {"markets":"spreads,totals","bookmakers":",".join(__import__('odds_providers').REQUEST_BOOKMAKERS)})
            events.append(event)
    return events


def emit_slate_context(
    game_date: str,
    rows: list[dict],
    retrieved_at: str,
    *,
    fetch_json_fn=fetch_json,
    collector=None,
    data_dir=None,
) -> dict:
    """Write availability JSONL and research packet when the slate has rows."""
    from context_feeds import collect_context, write_availability_jsonl, write_research_packet

    collector = collector or collect_context
    data_dir = Path(data_dir) if data_dir is not None else SKILL_ROOT / "data"
    nfl_schedule: list[dict] = []
    nhl_games: list[dict] = []
    nba_matchups: dict[str, str] = {}
    notes: list[str] = []

    loader, nfl_err = load_nfl_module()
    if loader is not None:
        try:
            season = int(nfl_season_from_date(game_date))
            nfl_schedule = frame_to_rows(loader.load_schedules(seasons=[season]))
        except Exception as exc:
            notes.append(f"context: nfl schedule for rest ({type(exc).__name__}: {exc})")
    elif nfl_err:
        notes.append(f"context: {nfl_err}")

    try:
        schedule_url = f"{NHL_WEB}/schedule/{game_date}"
        nhl_payload = fetch_json_fn(schedule_url, timeout=ESPN_TIMEOUT)
        nhl_games = games_from_schedule(nhl_payload, game_date)
    except Exception as exc:
        notes.append(f"context: nhl schedule ({type(exc).__name__}: {exc})")

    try:
        compact = game_date.replace("-", "")
        scoreboard_url = ESPN_SCOREBOARD.format(sport_path="basketball/nba", compact=compact)
        scoreboard = fetch_json_fn(scoreboard_url, timeout=ESPN_TIMEOUT)
        nba_matchups = matchups_from_scoreboard(scoreboard)
    except Exception as exc:
        notes.append(f"context: nba scoreboard ({type(exc).__name__}: {exc})")

    odds_events = load_odds_game_events(game_date, fetch=fetch_json_fn)
    packet, availability, ctx_notes = collector(
        game_date,
        rows,
        retrieved_at,
        fetch=fetch_json_fn,
        odds_events=odds_events,
        nfl_schedule=nfl_schedule,
        nhl_schedule_games=nhl_games,
        nba_matchups=nba_matchups,
        nfl_loader=loader,
    )
    notes.extend(ctx_notes)
    avail_path = data_dir / f"availability_{game_date}.jsonl"
    research_path = data_dir / f"research_{game_date}.json"
    if availability:
        write_availability_jsonl(avail_path, availability)
    else:
        write_availability_jsonl(avail_path, [])
    write_research_packet(research_path, packet)
    return {
        "availability_out": str(avail_path),
        "research_out": str(research_path),
        "availability_rows": len(availability),
        "notes": notes,
    }


def format_preflight(report: dict | None) -> str:
    """Plain table plus a `down:` line. Never raises."""
    try:
        checks = list((report or {}).get("checks") or [])
        lines = [f"{'check':<8} {'feed':<5} {'target':<26} {'result':<6} detail"]
        for item in checks:
            if not isinstance(item, dict):
                continue
            result = "ok" if item.get("ok") else "FAIL"
            detail = " ".join(str(item.get("detail") or "").split())
            lines.append(
                f"{str(item.get('kind', '')):<8} {str(item.get('feed', '')):<5} "
                f"{str(item.get('name', '')):<26} {result:<6} {detail}".rstrip()
            )
        down = [
            feed
            for feed in ("nhl", "nfl", "nba", "odds")
            if any((not item.get("ok")) and item.get("feed") == feed for item in checks if isinstance(item, dict))
        ]
        lines.append("down: " + (", ".join(down) if down else "none"))
        lines.append("preflight: " + ("ok" if (report or {}).get("ok") else "failed"))
        return "\n".join(lines) + "\n"
    except Exception as exc:
        return f"preflight: failed\n{type(exc).__name__}: {exc}\n"


def main(
    argv: list[str] | None = None,
    fetchers=None,
    import_check=None,
    reach_check=None,
    clock=None,
    context_emitter=None,
) -> dict:
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw[:1] == ["prep"]:
        return run_prep(raw[1:])
    parser = argparse.ArgumentParser(description="Fetch structured slate numbers. Does not grade.")
    parser.add_argument("--date", default=eastern_today(), help="Game date YYYY-MM-DD in US Eastern.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Check feed imports and host reachability, print a table, and exit.",
    )
    args = parser.parse_args(argv)
    if args.preflight:
        try:
            report = preflight(import_check=import_check, reach_check=reach_check)
            sys.stdout.write(format_preflight(report))
            sys.stdout.flush()
            code = 0 if report.get("ok") else 1
        except Exception as exc:
            sys.stdout.write(f"preflight: failed\n{type(exc).__name__}: {exc}\n")
            sys.stdout.flush()
            code = 1
        raise SystemExit(code)
    quotes_path = quotes_path_for(Path(args.out))
    if fetchers is None:
        client, client_error = make_nhl_client()
        rows, summary = collect(
            args.date,
            nhl_client=client,
            nhl_client_error=client_error,
            clock=clock,
            quotes_path=quotes_path,
        )
    else:
        rows, summary = collect(args.date, fetchers=fetchers, clock=clock, quotes_path=quotes_path)
    code = commit_slate(rows, summary, Path(args.out))
    if code == 0 and rows:
        try:
            summary["context"] = (context_emitter or emit_slate_context)(
                args.date,
                rows,
                summary.get("retrieved_at") or utc_now(),
                data_dir=Path(args.out).parent,
            )
        except Exception as exc:
            summary["context"] = {"status": "failed", "notes": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    if code:
        raise SystemExit(code)
    return summary


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        raise SystemExit(f"ERROR: {exc}")

