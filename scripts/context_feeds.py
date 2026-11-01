"""Optional slate context feeds: injuries, weather, game environment, research packet.

Every source is failure-safe: null plus a note, never invented numbers.
Merging into an existing research packet does not clobber non-null facts with null.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from odds_providers import (
    BOOK_PRIORITY,
    SPORT_FROM_KEY,
    approved_book_name,
    event_on_date,
    normalize_team,
)
from research_packet import (
    AVAILABILITY_FIELDS,
    ENVIRONMENT_FIELDS,
    LINEUP_FIELDS,
    WEATHER_FIELDS,
    empty_template,
)

SKILL_ROOT = Path(__file__).resolve().parents[1]
VENUES_PATH = SKILL_ROOT / "data" / "venues.json"
NHL_WEB = "https://api-web.nhle.com/v1"
ESPN_NBA_INJURIES = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
NWS_POINTS = "https://api.weather.gov/points/{lat},{lon}"
EASTERN = ZoneInfo("America/New_York")

NFL_WEATHER_HOURS = 3.5
NHL_WEATHER_HOURS = 3.0

FetchFn = Callable[..., Any]

_STATUS_MAP = {
    "out": "out",
    "o": "out",
    "doubtful": "doubtful",
    "d": "doubtful",
    "questionable": "questionable",
    "q": "questionable",
    "probable": "active",
    "p": "active",
    "active": "active",
    "healthy": "active",
    "day to day": "questionable",
    "day-to-day": "questionable",
}

_INTENSITY_RANK = {
    "none": 0,
    "light": 1,
    "moderate": 2,
    "heavy": 3,
}


def _is_fact(value: Any) -> bool:
    return isinstance(value, dict) and "fact" in value and "value" in value


def _nhl_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("default") or "")
    return str(value or "")


def _nhl_person_name(record: dict) -> str:
    if not isinstance(record, dict):
        return ""
    first = _nhl_text(record.get("firstName"))
    last = _nhl_text(record.get("lastName"))
    full = f"{first} {last}".strip()
    if full:
        return " ".join(full.split())
    return " ".join(_nhl_text(record.get("name")).split())


def confirmed_fact(
    label: str,
    value: Any,
    source_url: str,
    retrieved_at: str,
    *,
    quote: str = "",
    source_name: str = "",
) -> dict:
    text = " ".join(str(quote or "").split())
    if len(text.split()) > 25:
        text = " ".join(text.split()[:25])
    return {
        "fact": label,
        "value": value,
        "source_url": source_url,
        "source_name": source_name or label,
        "retrieved_at": retrieved_at,
        "quote": text,
        "confidence": "confirmed",
    }


def game_key(away: str, home: str) -> str:
    return f"{away}@{home}"


def games_from_schedules(
    game_date: str,
    *,
    nfl_schedule: list[dict] | None = None,
    nhl_games: list[dict] | None = None,
    nba_matchups: dict[str, str] | None = None,
) -> list[dict]:
    games: list[dict] = []
    seen: set[tuple] = set()

    def add(sport: str, away: str, home: str, **extra):
        if not away or not home:
            return
        token = (sport, away, home)
        if token in seen:
            return
        seen.add(token)
        entry = {"sport": sport, "away": away, "home": home, "game": game_key(away, home)}
        entry.update(extra)
        games.append(entry)

    for row in nfl_schedule or []:
        played = str(row.get("gameday") or row.get("game_date") or "")[:10]
        if played != game_date:
            continue
        if str(row.get("game_type") or "REG").upper() not in {"REG", "REGULAR"}:
            continue
        commence = row.get("commence_time")
        if not commence and row.get("gametime"):
            gt = str(row.get("gametime")).strip()
            if re.match(r"^\d{2}:\d{2}$", gt):
                # nflverse `gametime` is Eastern local wall time, NOT UTC.
                kickoff = datetime.fromisoformat(f"{game_date}T{gt}:00").replace(tzinfo=EASTERN)
                commence = kickoff.astimezone(timezone.utc).isoformat()
        add(
            "NFL",
            str(row.get("away_team") or ""),
            str(row.get("home_team") or ""),
            commence_time=commence,
        )

    for row in nhl_games or []:
        away = (row.get("awayTeam") or {}).get("abbrev")
        home = (row.get("homeTeam") or {}).get("abbrev")
        add(
            "NHL",
            str(away or ""),
            str(home or ""),
            nhl_game_id=row.get("id"),
            nhl_season=row.get("season"),
            commence_time=row.get("startTimeUTC") or row.get("commence_time"),
        )

    matchups = nba_matchups or {}
    paired: set[str] = set()
    for team, opp in matchups.items():
        if team in paired:
            continue
        paired.add(team)
        paired.add(opp)
        away, home = team, opp
        add("NBA", away, home)

    return games


def games_from_slate_rows(rows: list[dict], scheduled: list[dict] | None = None) -> list[dict]:
    """Prefer schedule-derived away@home keys; fall back to row pairs."""
    if scheduled:
        return list(scheduled)
    seen: set[tuple] = set()
    games: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        sport = str(row.get("sport") or "").upper()
        team = str(row.get("team") or "").strip()
        opp = str(row.get("opponent") or "").strip()
        if not sport or not team or not opp:
            continue
        pair = tuple(sorted((team, opp)))
        key = (sport, pair[0], pair[1])
        if key in seen:
            continue
        seen.add(key)
        games.append({"sport": sport, "away": team, "home": opp, "game": game_key(team, opp)})
    return games


def load_venues(path: Path | None = None) -> dict:
    target = path or VENUES_PATH
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def venue_for_team(sport: str, team: str, venues: dict | None = None) -> dict | None:
    table = (venues or load_venues()).get(sport.upper()) or {}
    entry = table.get(team)
    return entry if isinstance(entry, dict) else None


def normalize_status(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = " ".join(str(raw).strip().lower().split())
    if not text:
        return None
    if text in _STATUS_MAP:
        return _STATUS_MAP[text]
    for key, val in _STATUS_MAP.items():
        if key in text:
            return val
    return None


def fetch_nfl_injuries(
    loader,
    season: int,
    slate_players: set[str],
    retrieved_at: str,
    *,
    source_url: str = "https://github.com/nflverse/nflverse-data/releases/tag/injuries",
    game_date: str | None = None,
    schedule: list[dict] | None = None,
) -> tuple[list[dict], list[str]]:
    notes: list[str] = []
    rows_out: list[dict] = []
    try:
        frame = loader.load_injuries(seasons=[season])
    except Exception as exc:
        notes.append(f"nfl injuries: load_injuries failed ({type(exc).__name__}: {exc})")
        return rows_out, notes
    records = frame.to_dicts() if hasattr(frame, "to_dicts") else list(frame or [])
    if game_date is not None:
        # This endpoint returns the entire season, not tonight's status list.
        # Retrieval time cannot make an earlier week's Out report current.
        weeks = {}
        for game in schedule or []:
            if str(game.get('gameday') or '')[:10] != game_date:
                continue
            for team in (game.get('home_team'), game.get('away_team')):
                weeks[str(team)] = str(game.get('week'))
        selected = {}
        for row in records:
            team = str(row.get('team') or '')
            if (team not in weeks or str(row.get('week')) != weeks[team]
                    or str(row.get('season')) != str(season)):
                continue
            # Practice participation alone never establishes game availability.
            if not (row.get('report_status') or row.get('status')):
                continue
            stamp = str(row.get('date_modified') or row.get('report_date') or '')
            if stamp and stamp[:10] > str(retrieved_at)[:10]:
                continue
            key = (str(row.get('gsis_id') or row.get('full_name') or row.get('player_name')),team)
            old = selected.get(key)
            if old is None or stamp > old[0]:
                selected[key] = (stamp,row)
            elif stamp == old[0] and row.get('report_status') != old[1].get('report_status'):
                # Conflicting undated reports do not establish a subject status.
                selected[key] = (stamp,{**row,'report_status':None,'status':None,'practice_status':None})
        records = [value[1] for value in selected.values()]
        if not records:
            notes.append('nfl injuries: no game-week status report matched the current slate')
    for row in records:
        name = " ".join(
            str(row.get("full_name") or row.get("player_name") or row.get("gsis_id") or "").split()
        )
        if not name or name not in slate_players:
            continue
        raw_status = row.get("report_status") or row.get("status")
        if game_date is None:
            raw_status = raw_status or row.get("practice_status")
        status = normalize_status(raw_status)
        if status is None:
            continue
        rows_out.append(
            {
                "sport": "NFL",
                "player": name,
                "team": str(row.get("team") or ""),
                "status": status,
                "source_url": source_url,
                "retrieved_at": retrieved_at,
                "note": None,
            }
        )
    if not rows_out and records:
        notes.append("nfl injuries: no matching slate players on injury report")
    return rows_out, notes


def fetch_nba_injuries(
    fetch: FetchFn,
    slate_players: set[str],
    retrieved_at: str,
) -> tuple[list[dict], list[str]]:
    notes: list[str] = []
    rows_out: list[dict] = []
    try:
        payload = fetch(ESPN_NBA_INJURIES, timeout=15)
    except Exception as exc:
        notes.append(f"nba injuries: ESPN endpoint failed ({type(exc).__name__}: {exc})")
        return rows_out, notes
    teams = (payload or {}).get("injuries") or []
    for block in teams:
        if not isinstance(block, dict):
            continue
        team_info = block.get("team") or {}
        team_abbrev = str(team_info.get("abbreviation") or team_info.get("abbrev") or "")
        for item in block.get("injuries") or []:
            if not isinstance(item, dict):
                continue
            athlete = item.get("athlete") or {}
            name = " ".join(str(athlete.get("displayName") or athlete.get("fullName") or "").split())
            if not name or name not in slate_players:
                continue
            raw_status = item.get("status")
            if isinstance(raw_status, dict):
                status = normalize_status(raw_status.get("type") or raw_status.get("name"))
            else:
                status = normalize_status(raw_status)
            if status is None:
                details = item.get("details") if isinstance(item.get("details"), dict) else {}
                fantasy = details.get("fantasyStatus") if isinstance(details.get("fantasyStatus"), dict) else {}
                status = normalize_status(fantasy.get("description"))
            if status is None:
                continue
            rows_out.append(
                {
                    "sport": "NBA",
                    "player": name,
                    "team": team_abbrev,
                    "status": status,
                    "source_url": ESPN_NBA_INJURIES,
                    "retrieved_at": retrieved_at,
                    "note": None,
                }
            )
    return rows_out, notes


def fetch_nhl_availability(
    fetch: FetchFn,
    games: list[dict],
    slate_players: set[str],
    retrieved_at: str,
) -> tuple[list[dict], dict[str, dict], list[str]]:
    """Roster injuries plus goalie starter hints from gamecenter landing."""
    notes: list[str] = []
    rows_out: list[dict] = []
    lineup_by_team: dict[str, dict] = {}
    for game in games:
        if game.get("sport") != "NHL":
            continue
        game_id = game.get("nhl_game_id")
        home = game.get("home")
        away = game.get("away")
        if not game_id:
            continue
        landing_url = f"{NHL_WEB}/gamecenter/{game_id}/landing"
        try:
            landing = fetch(landing_url, timeout=15)
        except Exception as exc:
            notes.append(f"nhl lineup: {landing_url} failed ({type(exc).__name__}: {exc})")
            continue
        for side_key, abbrev in (("homeTeam", home), ("awayTeam", away)):
            team_block = (landing or {}).get(side_key) or {}
            if not abbrev:
                continue
            goalie = team_block.get("goalie") or team_block.get("probableGoalie") or {}
            starter_name = _nhl_person_name(goalie)
            confirmed = goalie.get("confirmed")
            if confirmed is None:
                confirmed = goalie.get("starterConfirmed")
            if confirmed is not None or starter_name:
                lineup_by_team.setdefault(abbrev, {})
                if confirmed is not None:
                    lineup_by_team[abbrev]["goalie_confirmed"] = confirmed_fact(
                        "goalie_confirmed",
                        bool(confirmed),
                        landing_url,
                        retrieved_at,
                        quote=starter_name or "NHL gamecenter",
                        source_name="NHL gamecenter",
                    )
        season_token = game.get("nhl_season") or "current"
        for team_abbrev in (home, away):
            if not team_abbrev:
                continue
            roster_url = f"{NHL_WEB}/roster/{team_abbrev}/{season_token}"
            try:
                roster = fetch(roster_url, timeout=15)
            except Exception:
                roster = None
            if not isinstance(roster, dict):
                continue
            roster_players = (
                (roster.get("forwards") or [])
                + (roster.get("defensemen") or [])
                + (roster.get("goalies") or [])
            )
            for player in roster_players:
                if not isinstance(player, dict):
                    continue
                name = _nhl_person_name(player)
                if not name or name not in slate_players:
                    continue
                inj = player.get("injury") or player.get("injuries")
                status = None
                if isinstance(inj, dict):
                    status = normalize_status(inj.get("status") or inj.get("description"))
                elif isinstance(inj, list) and inj:
                    status = normalize_status(inj[0].get("status") if isinstance(inj[0], dict) else inj[0])
                if status:
                    rows_out.append(
                        {
                            "sport": "NHL",
                            "player": name,
                            "team": team_abbrev,
                            "status": status,
                            "source_url": roster_url,
                            "retrieved_at": retrieved_at,
                            "note": None,
                        }
                    )
    return rows_out, lineup_by_team, notes


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    text = str(ts).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None  # unknown offset: do not silently call local times UTC
    return dt.astimezone(timezone.utc)


def _precip_intensity(prob: float, short_forecast: str) -> str:
    text = (short_forecast or "").lower()
    if prob <= 0 and "rain" not in text and "snow" not in text:
        return "none"
    if any(w in text for w in ("heavy", "thunder", "blizzard")):
        return "heavy"
    if any(w in text for w in ("moderate", "snow", "sleet", "freezing")):
        return "moderate"
    if prob >= 30 or "rain" in text or "shower" in text:
        return "light"
    return "none"


def weather_from_hourly(
    hourly_payload: dict,
    start: datetime,
    hours: float,
    source_url: str,
    retrieved_at: str,
) -> dict[str, Any]:
    end = start + timedelta(hours=hours)
    periods = ((hourly_payload or {}).get("properties") or {}).get("periods") or []
    wind_sustained: float | None = None
    gust: float | None = None
    precip_prob: float | None = None
    intensity = "none"
    has_snow = False
    forecast_bits: list[str] = []
    for period in periods:
        if not isinstance(period, dict):
            continue
        begin = _parse_iso(period.get("startTime") or "")
        if begin is None or begin < start or begin > end:
            continue
        ws = period.get("windSpeed")
        if isinstance(ws, str):
            nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", ws)]
            ws_val = max(nums) if nums else None
        else:
            ws_val = float(ws) if ws is not None else None
        if ws_val is not None:
            wind_sustained = max(wind_sustained or 0.0, ws_val)
        gust_text = period.get("windGust", {}).get("value") if isinstance(period.get("windGust"), dict) else period.get("windGust")
        if gust_text is not None:
            try:
                gust = max(gust or 0.0, float(gust_text))
            except (TypeError, ValueError):
                pass
        prob = period.get("probabilityOfPrecipitation", {}).get("value")
        hour_prob = 0.0
        if prob is not None:
            try:
                hour_prob = float(prob)
                precip_prob = max(precip_prob or 0.0, hour_prob)
            except (TypeError, ValueError):
                pass
        short = str(period.get("shortForecast") or "")
        forecast_bits.append(short)
        hour_intensity = _precip_intensity(hour_prob, short)
        if _INTENSITY_RANK.get(hour_intensity, 0) > _INTENSITY_RANK.get(intensity, 0):
            intensity = hour_intensity
        if any(w in short.lower() for w in ("snow", "blizzard", "flurries", "sleet")):
            has_snow = True
    if wind_sustained is None and gust is None and precip_prob is None:
        return {}
    window_label = f"{start.astimezone(EASTERN).strftime('%H:%M')} ET +{hours}h"
    out: dict[str, Any] = {
        "window": confirmed_fact("forecast_window", window_label, source_url, retrieved_at, quote=window_label),
    }
    if wind_sustained is not None:
        out["sustained_wind_mph"] = confirmed_fact(
            "sustained_wind_mph", wind_sustained, source_url, retrieved_at
        )
    if gust is not None:
        out["gust_mph"] = confirmed_fact("gust_mph", gust, source_url, retrieved_at)
    if precip_prob is not None:
        out["precip_prob"] = confirmed_fact("precip_prob", precip_prob, source_url, retrieved_at)
    out["precip_intensity"] = confirmed_fact(
        "precip_intensity", intensity, source_url, retrieved_at, quote="; ".join(forecast_bits[:3])
    )
    if has_snow:
        out["snow"] = confirmed_fact(
            "snow", True, source_url, retrieved_at, quote="; ".join(forecast_bits[:3])
        )
    return out


def fetch_weather_us(
    fetch: FetchFn,
    lat: float,
    lon: float,
    start: datetime,
    hours: float,
    retrieved_at: str,
) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    points_url = NWS_POINTS.format(lat=lat, lon=lon)
    try:
        points = fetch(points_url, timeout=15, headers={"User-Agent": "pickem-auditor/1.0", "Accept": "application/json"})
    except Exception as exc:
        notes.append(f"weather: points lookup failed ({type(exc).__name__}: {exc})")
        return {}, notes
    hourly_url = ((points or {}).get("properties") or {}).get("forecastHourly")
    if not hourly_url:
        notes.append("weather: forecastHourly URL missing from weather.gov points response")
        return {}, notes
    try:
        hourly = fetch(hourly_url, timeout=15, headers={"User-Agent": "pickem-auditor/1.0", "Accept": "application/json"})
    except Exception as exc:
        notes.append(f"weather: hourly forecast failed ({type(exc).__name__}: {exc})")
        return {}, notes
    facts = weather_from_hourly(hourly, start, hours, hourly_url, retrieved_at)
    return facts, notes


def game_markets_from_events(events: list, game_date: str, retrieved_at: str) -> dict[str, dict]:
    """Spread (home team signed), total, and commence_time per away@home game key."""
    out: dict[str, dict] = {}
    for event in events or []:
        if not isinstance(event, dict):
            continue
        if not event_on_date(event.get("commence_time"), game_date):
            continue
        home_name = event.get("home_team")
        away_name = event.get("away_team")
        home = normalize_team(home_name)
        away = normalize_team(away_name)
        if not home or not away:
            continue
        gkey = game_key(away, home)
        spread_home: float | None = None
        total: float | None = None
        source_url = str(event.get("source_url") or "")
        for bookmaker in sorted(event.get("bookmakers") or [], key=lambda b: _book_rank(b.get("key"))):
            if not isinstance(bookmaker, dict):
                continue
            book = approved_book_name(bookmaker.get("key"))
            if not book:
                continue
            for market in bookmaker.get("markets") or []:
                if not isinstance(market, dict):
                    continue
                mkey = market.get("key")
                if mkey == "spreads" and spread_home is None:
                    for outcome in market.get("outcomes") or []:
                        if normalize_team(outcome.get("name")) == home:
                            try:
                                spread_home = float(outcome.get("point"))
                            except (TypeError, ValueError):
                                pass
                if mkey == "totals" and total is None:
                    for outcome in market.get("outcomes") or []:
                        if str(outcome.get("name", "")).lower() == "over":
                            try:
                                total = float(outcome.get("point"))
                            except (TypeError, ValueError):
                                pass
            if spread_home is not None and total is not None:
                break
        if spread_home is None and total is None:
            continue
        entry = out.setdefault(gkey, {"source_url": source_url})
        if event.get("commence_time"):
            entry["commence_time"] = str(event.get("commence_time"))
        if spread_home is not None:
            entry["spread_home"] = spread_home
        if total is not None:
            entry["total"] = total
    return out


def _book_rank(key: str | None) -> int:
    raw = str(key or "").lower()
    try:
        return BOOK_PRIORITY.index(raw)
    except ValueError:
        return len(BOOK_PRIORITY)


def rest_facts_for_team(
    team: str,
    sport: str,
    game_date: str,
    schedule_rows: list[dict],
    source_url: str,
    retrieved_at: str,
) -> dict[str, Any]:
    try:
        today = datetime.fromisoformat(game_date).date()
    except ValueError:
        return {}
    team_dates = []
    for row in schedule_rows:
        if sport == "NFL":
            if row.get("home_team") != team and row.get("away_team") != team:
                continue
            day_s = str(row.get("gameday") or "")[:10]
        elif sport == "NHL":
            away = (row.get("awayTeam") or {}).get("abbrev")
            home = (row.get("homeTeam") or {}).get("abbrev")
            if team not in (away, home):
                continue
            day_s = str(row.get("gameDate") or row.get("date") or "")[:10]
        elif sport == "NBA":
            away = row.get("away")
            home = row.get("home")
            if team not in (away, home):
                continue
            day_s = str(row.get("date") or "")[:10]
        else:
            continue
        if not day_s:
            continue
        try:
            team_dates.append(datetime.fromisoformat(day_s).date())
        except ValueError:
            continue
    team_dates = sorted(set(team_dates))
    if today not in team_dates:
        team_dates.append(today)
        team_dates.sort()
    idx = team_dates.index(today)
    if idx==0:
        return {}  # Today's slate cannot establish when the team last played.
    rest_days = 0
    if idx > 0:
        rest_days = (today - team_dates[idx - 1]).days - 1
        if rest_days < 0:
            rest_days = 0
    back_to_back = rest_days == 0 and idx > 0
    window_start = today - timedelta(days=3)
    games_in_window = sum(1 for d in team_dates if window_start <= d <= today)
    third_in_four = games_in_window >= 3
    facts: dict[str, Any] = {}
    facts["rest_days"] = confirmed_fact("rest_days", rest_days, source_url, retrieved_at)
    facts["back_to_back"] = confirmed_fact("back_to_back", back_to_back, source_url, retrieved_at)
    if third_in_four:
        facts["third_in_four"] = confirmed_fact("third_in_four", True, source_url, retrieved_at)
    return facts


def build_research_packet(
    game_date: str,
    rows: list[dict],
    availability_rows: list[dict],
    weather_by_game: dict[str, dict],
    environment_by_game: dict[str, dict],
    lineup_by_team: dict[str, dict],
    *,
    scheduled_games: list[dict] | None = None,
    notes: list[str] | None = None,
) -> dict:
    packet = empty_template(game_date)
    players_on_slate: dict[str, dict] = {}
    ambiguous_names = set()
    by_player_id = {}
    teams_on_slate: set[str] = set()
    games_on_slate: set[str] = set()
    scheduled = scheduled_games or games_from_slate_rows(rows)
    game_lookup: dict[tuple, str] = {}
    home_by_game: dict[str, str] = {}
    for g in scheduled:
        game_lookup[(g["sport"], g["away"])] = g["game"]
        game_lookup[(g["sport"], g["home"])] = g["game"]
        home_by_game[g["game"]] = g["home"]
        games_on_slate.add(g["game"])
        teams_on_slate.add(g["away"])
        teams_on_slate.add(g["home"])

    for row in rows or []:
        player = str(row.get("player") or "")
        team = str(row.get("team") or "")
        opp = str(row.get("opponent") or "")
        sport = str(row.get("sport") or "")
        if not player or not team or not opp:
            continue
        g = game_lookup.get((sport, team)) or game_lookup.get((sport, opp)) or game_key(team, opp)
        home_team = home_by_game.get(g) or (g.split("@", 1)[1] if "@" in g else "")
        p_entry: dict[str, Any] = {"team": team, "game": g, "sport": sport}
        for field in ("player_id", "event_id"):
            if row.get(field) not in (None, ""):
                p_entry[field] = row[field]
        if home_team:
            p_entry["is_home"] = (team == home_team)
        previous = players_on_slate.get(player)
        if previous and any(previous.get(k) != p_entry.get(k) for k in ("sport", "team", "player_id", "event_id")):
            ambiguous_names.add(player)
        players_on_slate[player] = p_entry
        if p_entry.get("player_id") is not None:
            by_player_id[f"{sport}|{p_entry['player_id']}"] = p_entry
        teams_on_slate.add(team)
        teams_on_slate.add(opp)

    from scouting_checklist import seed
    for row in rows:
        if row.get('sport') and row.get('player') and row.get('stat'):
            for side in ('over','under'):
                key=f"{row['sport']}|{row['player']}|{row['stat']}|{side}"
                entry=packet['scouting'].setdefault(key, seed(row['sport'],row['stat'],row))
                if row.get('historical_usage'):entry['historical_usage']=row['historical_usage']
                if isinstance(row.get('season_context'),dict):
                    entry['season_context']=row['season_context']
    packet["index"]["by_player"] = players_on_slate
    packet["index"]["by_player_id"] = by_player_id

    avail_by_player: dict[str, dict] = {}
    for item in availability_rows or []:
        player = item.get("player")
        if not player:
            continue
        avail_by_player.setdefault(player, {})
        status = item.get("status")
        if status:
            avail_by_player[player]["status"] = confirmed_fact(
                "availability",
                status,
                item.get("source_url") or "",
                item.get("retrieved_at") or "",
                quote=str(status),
                source_name="league",
            )
            avail_by_player[player]["primary_source"] = confirmed_fact(
                "primary_source",
                "league",
                item.get("source_url") or "",
                item.get("retrieved_at") or "",
            )

    for player, meta in players_on_slate.items():
        packet["availability"][player] = {
            "status": None if player in ambiguous_names else (avail_by_player.get(player) or {}).get("status"),
            "primary_source": (avail_by_player.get(player) or {}).get("primary_source"),
        }

    for team in sorted(teams_on_slate):
        merged = lineup_by_team.get(team) or {}
        packet["lineup"][team] = {
            "projected_lines": merged.get("projected_lines"),
            "pairs": merged.get("pairs"),
            "pp1": merged.get("pp1"),
            "goalie_confirmed": merged.get("goalie_confirmed"),
        }

    for g in sorted(games_on_slate):
        w = weather_by_game.get(g) or {}
        w_out = {
            "sustained_wind_mph": w.get("sustained_wind_mph"),
            "gust_mph": w.get("gust_mph"),
            "precip_prob": w.get("precip_prob"),
            "precip_intensity": w.get("precip_intensity"),
            "window": w.get("window"),
            "indoor": w.get("indoor"),
        }
        if w.get("snow") is not None:
            w_out["snow"] = w.get("snow")
        packet["weather"][g] = w_out

        env = environment_by_game.get(g) or {}
        env_out = {
            "spread": env.get("spread"),
            "total": env.get("total"),
            "back_to_back": env.get("back_to_back"),
            "rest_days": env.get("rest_days"),
        }
        for opt_key in (
            "spread_home",
            "spread_away",
            "third_in_four",
            "away_back_to_back",
            "away_rest_days",
            "away_third_in_four",
        ):
            if env.get(opt_key) is not None:
                env_out[opt_key] = env.get(opt_key)
        packet["environment"][g] = env_out

    if notes:
        packet["_feed_notes"] = list(notes)
    return packet


def merge_packet_no_clobber(existing: dict | None, new: dict) -> dict:
    if not isinstance(existing, dict) or existing.get("date") != new.get("date"):
        return new

    def merge_section(old_sec: dict | None, new_sec: dict | None) -> dict:
        old_sec = old_sec if isinstance(old_sec, dict) else {}
        new_sec = new_sec if isinstance(new_sec, dict) else {}
        keys = set(old_sec) | set(new_sec)
        out: dict = {}
        for key in keys:
            old_entry = old_sec.get(key)
            new_entry = new_sec.get(key)
            if isinstance(old_entry, dict) and isinstance(new_entry, dict):
                subkeys = set(old_entry) | set(new_entry)
                merged_entry = {}
                for sk in subkeys:
                    ov = old_entry.get(sk)
                    nv = new_entry.get(sk)
                    if _is_fact(nv) and _is_fact(ov):
                        # Re-downloading an older source cannot replace a newer
                        # verified observation simply because collection retried.
                        # Contradictory availability has its own stricter
                        # publication-scope conflict check below.
                        new_clock = _parse_iso(nv.get("retrieved_at") or "")
                        old_clock = _parse_iso(ov.get("retrieved_at") or "")
                        merged_entry[sk] = (ov if old_clock and
                            (not new_clock or new_clock < old_clock) else nv)
                    elif _is_fact(nv):
                        merged_entry[sk] = nv
                    elif _is_fact(ov):
                        merged_entry[sk] = ov
                    else:
                        merged_entry[sk] = nv if nv is not None else ov
                out[key] = merged_entry
            else:
                out[key] = new_entry if new_entry is not None else old_entry
        return out

    merged = dict(new)
    merged["availability"] = merge_section(existing.get("availability"), new.get("availability"))
    conflicts = list(existing.get('_source_conflicts') or [])
    for player in set(existing.get('availability', {})) & set(new.get('availability', {})):
        old = existing['availability'][player].get('status')
        fresh = new['availability'][player].get('status')
        if not (_is_fact(old) and _is_fact(fresh)) or old.get('value') == fresh.get('value'):
            continue
        # Effective report time and report scope govern supersession; downloading
        # an older report again must never make its information newer.
        kinds = {'practice_report': 1, 'game_day_report': 2, 'final_active_roster': 3}
        def authority(fact):
            stamp = _parse_iso(fact.get('published_at') or (fact.get('observed_at') if fact.get('report_type')=='final_active_roster' else '') or '')
            kind = kinds.get(fact.get('report_type'))
            return (kind, stamp) if kind and stamp else None
        a, b = authority(old), authority(fresh)
        winner = None
        if a and b and a != b:
            winner = old if a > b else fresh
        merged['availability'][player]['status'] = winner
        if winner is old:
            merged['availability'][player]['primary_source'] = existing['availability'][player].get('primary_source')
        elif winner is None:
            merged['availability'][player]['primary_source'] = None
        record = {'player': player, 'field': 'status', 'observations': [old, fresh],
                  'resolution': 'report_scope_and_publication_time' if winner else 'unresolved'}
        if record not in conflicts:
            conflicts.append(record)
    # A subsequent feed refresh cannot silently erase an unresolved conflict.
    for conflict in existing.get('_source_conflicts') or []:
        if conflict.get('resolution') == 'unresolved' and conflict.get('field') == 'status':
            player = conflict.get('player')
            if player in merged.get('availability', {}):
                merged['availability'][player]['status'] = None
                merged['availability'][player]['primary_source'] = None
    if conflicts:
        merged['_source_conflicts'] = conflicts
    merged["lineup"] = merge_section(existing.get("lineup"), new.get("lineup"))
    merged["weather"] = merge_section(existing.get("weather"), new.get("weather"))
    merged["environment"] = merge_section(existing.get("environment"), new.get("environment"))
    old_index = existing.get("index") if isinstance(existing.get("index"), dict) else {}
    new_index = new.get("index") if isinstance(new.get("index"), dict) else {}
    by_player = dict(old_index.get("by_player") or {})
    by_player.update(new_index.get("by_player") or {})
    by_player_id = dict(old_index.get("by_player_id") or {})
    by_player_id.update(new_index.get("by_player_id") or {})
    merged["index"] = {"by_player": by_player, "by_player_id": by_player_id}
    for sec in ("mechanisms", "role_changes", "player_context", "scouting"):
        if sec in existing and sec not in merged:
            merged[sec] = existing[sec]
        elif sec in existing and isinstance(existing[sec], dict) and isinstance(merged.get(sec), dict):
            combined = dict(existing[sec])
            if sec == 'scouting':
                for key, value in merged[sec].items():
                    if key not in combined or isinstance(value, dict) and value.get('scenarios'):
                        combined[key] = value
                    elif isinstance(value,dict) and isinstance(combined.get(key),dict) and value.get('season_context'):
                        combined[key] = {**combined[key],'season_context':value['season_context']}
                    if isinstance(value,dict) and isinstance(combined.get(key),dict):
                        # Refresh collector-owned references without replacing
                        # researcher facts or leaving a formerly missing B stale.
                        combined[key]=dict(combined[key])
                        if value.get('historical_usage'):
                            combined[key]['historical_usage']=value['historical_usage']
                        else:combined[key].pop('historical_usage',None)
            else:
                combined.update(merged[sec])
            merged[sec] = combined
    return merged


def write_availability_jsonl(path: Path, rows: list[dict], *, replace_fn=None) -> None:
    from fetch_slate import atomic_write_text

    lines = [json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows]
    atomic_write_text(path, "".join(lines), replace=replace_fn)


def write_research_packet(path: Path, packet: dict, *, replace_fn=None) -> None:
    from fetch_slate import atomic_write_text

    existing = None
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = None
    merged = merge_packet_no_clobber(existing, packet)
    text = json.dumps(merged, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    atomic_write_text(path, text, replace=replace_fn)


def collect_context(
    game_date: str,
    rows: list[dict],
    retrieved_at: str,
    *,
    fetch: FetchFn,
    odds_events: list | None = None,
    nfl_schedule: list[dict] | None = None,
    nhl_schedule_games: list[dict] | None = None,
    nba_matchups: dict[str, str] | None = None,
    nba_schedule_rows: list[dict] | None = None,
    nfl_loader=None,
    venues: dict | None = None,
) -> tuple[dict, list[dict], list[str]]:
    """Build research packet and availability jsonl rows. Never raises."""
    notes: list[str] = []
    slate_players = {str(r.get("player")) for r in rows if r.get("player")}
    games = games_from_schedules(
        game_date,
        nfl_schedule=nfl_schedule,
        nhl_games=nhl_schedule_games,
        nba_matchups=nba_matchups,
    )
    if not games:
        games = games_from_slate_rows(rows)
    venues_table = venues or load_venues()

    availability: list[dict] = []
    lineup_by_team: dict[str, dict] = {}

    if nfl_loader is not None:
        season = int(game_date[:4]) if game_date[5:7] >= "09" else int(game_date[:4]) - 1
        nfl_rows, nfl_notes = fetch_nfl_injuries(nfl_loader, season, slate_players, retrieved_at,
                                               game_date=game_date,schedule=nfl_schedule)
        availability.extend(nfl_rows)
        notes.extend(nfl_notes)

    nba_rows, nba_notes = fetch_nba_injuries(fetch, slate_players, retrieved_at)
    availability.extend(nba_rows)
    notes.extend(nba_notes)

    nhl_games_enriched = [g for g in games if g.get("sport") == "NHL"]
    nhl_rows, nhl_lineup, nhl_notes = fetch_nhl_availability(fetch, nhl_games_enriched, slate_players, retrieved_at)
    availability.extend(nhl_rows)
    lineup_by_team.update(nhl_lineup)
    notes.extend(nhl_notes)

    markets = game_markets_from_events(odds_events or [], game_date, retrieved_at)
    environment_by_game: dict[str, dict] = {}
    for g in games:
        gkey = g["game"]
        m = markets.get(gkey) or {}
        source = m.get("source_url")
        env: dict[str, Any] = {}
        if source and m.get("spread_home") is not None:
            sh = float(m["spread_home"])
            env["spread"] = confirmed_fact("spread", sh, source, retrieved_at)
            env["spread_home"] = confirmed_fact("spread_home", sh, source, retrieved_at)
            env["spread_away"] = confirmed_fact("spread_away", -sh, source, retrieved_at)
        if source and m.get("total") is not None:
            env["total"] = confirmed_fact("total", float(m["total"]), source, retrieved_at)
        sched_source = {
            'NFL':'https://github.com/nflverse/nfldata/blob/master/data/games.csv',
            'NHL':f'{NHL_WEB}/schedule/{game_date}',
            'NBA':f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={game_date.replace("-","")}',
        }[g['sport']]
        sched_rows = None
        if g["sport"] == "NFL" and nfl_schedule:
            sched_rows = nfl_schedule
        elif g["sport"] == "NHL" and nhl_schedule_games:
            sched_rows = nhl_schedule_games
        elif g["sport"] == "NBA" and nba_schedule_rows:
            sched_rows = nba_schedule_rows
        if sched_rows:
            rest_home = rest_facts_for_team(g["home"], g["sport"], game_date, sched_rows, sched_source, retrieved_at)
            env.update({k: v for k, v in rest_home.items() if k in ("back_to_back", "rest_days", "third_in_four")})
            rest_away = rest_facts_for_team(g["away"], g["sport"], game_date, sched_rows, sched_source, retrieved_at)
            if "back_to_back" in rest_away:
                env["away_back_to_back"] = confirmed_fact(
                    "away_back_to_back", rest_away["back_to_back"]["value"], sched_source, retrieved_at
                )
            if "rest_days" in rest_away:
                env["away_rest_days"] = confirmed_fact(
                    "away_rest_days", rest_away["rest_days"]["value"], sched_source, retrieved_at
                )
            if "third_in_four" in rest_away:
                env["away_third_in_four"] = confirmed_fact(
                    "away_third_in_four", rest_away["third_in_four"]["value"], sched_source, retrieved_at
                )
        if env:
            environment_by_game[gkey] = env

    weather_by_game: dict[str, dict] = {}
    for g in games:
        sport = g["sport"]
        if sport not in ("NFL", "NHL"):
            continue
        gkey = g["game"]
        venue = venue_for_team(sport, g["home"], venues_table)
        if venue is None:
            notes.append(f"weather: no venue row for {sport} {g['home']}; agent should search national weather service")
            continue
        if venue.get("indoor"):
            weather_by_game[gkey] = {
                "indoor": None,
            }
            notes.append(f"weather: {gkey} local venue hint is indoors; verify the actual game venue/roof from a public source")
            continue
        if venue.get("country") == "CA":
            notes.append(f"weather: {gkey} is Canada; agent should search Environment Canada")
            continue
        lat = venue.get("lat")
        lon = venue.get("lon")
        if lat is None or lon is None:
            notes.append(f"weather: {gkey} missing lat/lon in venues table")
            continue
        commence_raw = g.get("commence_time") or (markets.get(gkey) or {}).get("commence_time")
        parsed_start = _parse_iso(str(commence_raw)) if commence_raw else None
        if parsed_start is not None:
            start_utc = parsed_start
        else:
            start_utc = datetime.fromisoformat(f"{game_date}T18:00:00").replace(tzinfo=EASTERN).astimezone(timezone.utc)
        hours = NFL_WEATHER_HOURS if sport == "NFL" else NHL_WEATHER_HOURS
        facts, w_notes = fetch_weather_us(fetch, float(lat), float(lon), start_utc, hours, retrieved_at)
        notes.extend(w_notes)
        if facts:
            facts["indoor"] = None
            notes.append(f"weather: {gkey} forecast uses local venue coordinates; verify actual game venue/roof")
            weather_by_game[gkey] = facts

    packet = build_research_packet(
        game_date,
        rows,
        availability,
        weather_by_game,
        environment_by_game,
        lineup_by_team,
        scheduled_games=games,
        notes=notes,
    )
    return packet, availability, notes


def gap_paths_for_shortlist(packet: dict, shortlist_ids: list[str], *, candidate_rows=None, now=None) -> list[dict]:
    """List null required fields for players/games on the shortlist."""
    now=now or datetime.now(timezone.utc)
    from research_packet import _validate_fact
    def usable(fact):
        issues=[]
        verified=_validate_fact('required_fact',fact,issues,require_fresh=True,now=now)
        return verified is not None and not issues and verified.confidence=='confirmed'
    index = (packet.get("index") or {}).get("by_player") or {}
    candidates_by_player = {}
    for row_id in shortlist_ids:
        parts = row_id.split("|")
        if len(parts)==4: candidates_by_player.setdefault(parts[1], []).append(parts)
    players: set[str] = set()
    for row_id in shortlist_ids:
        parts = row_id.split("|")
        if len(parts) >= 2:
            players.add(parts[1])

    gaps: list[dict] = []
    for player in sorted(players):
        meta = index.get(player) or {}
        team = meta.get("team")
        game = meta.get("game")
        for field in AVAILABILITY_FIELDS:
            path = f"availability.{player}.{field}"
            entry = ((packet.get("availability") or {}).get(player) or {}).get(field)
            if not usable(entry):
                gaps.append({"path": path, "player": player, "reason": "null"})
        if team:
            # NHL lineup vocabulary is not an NFL/NBA research requirement.
            selections=candidates_by_player.get(player, [])
            fields=set()
            for sport,_,stat,_ in selections:
                from pickem_math import _optional_stat
                stat = _optional_stat(stat)
                if sport=='NHL':
                    fields.update(('goalie_confirmed',) if stat=='saves' else ('projected_lines','pp1'))
                    if stat=='blocked shots':fields.add('pairs')
            for field in sorted(fields):
                path = f"lineup.{team}.{field}"
                entry = ((packet.get("lineup") or {}).get(team) or {}).get(field)
                if field == 'goalie_confirmed' and usable((packet.get('player_context',{}).get(player) or {}).get('goalie_confirmed')):
                    continue
                if not usable(entry):
                    gaps.append({"path": path, "team": team, "reason": "null"})
        if game and meta.get("sport") in ("NFL", "NHL"):
            w_entry = (packet.get("weather") or {}).get(game) or {}
            indoor = w_entry.get("indoor")
            is_indoor = usable(indoor) and indoor.get("value") is True
            if not usable(indoor):
                gaps.append({'path':f'weather.{game}.indoor','game':game,'reason':'invalid_or_stale'})
            if usable(indoor) and indoor.get("value") is False:
                for field in WEATHER_FIELDS:
                    if field == "indoor":
                        continue
                    path = f"weather.{game}.{field}"
                    if not usable(w_entry.get(field)):
                        gaps.append({"path": path, "game": game, "reason": "null"})
            for field in ENVIRONMENT_FIELDS:
                path = f"environment.{game}.{field}"
                if not usable(((packet.get("environment") or {}).get(game) or {}).get(field)):
                    gaps.append({"path": path, "game": game, "reason": "null"})
    for player in sorted(players):
        meta=index.get(player) or {}
        if meta.get('sport')=='NBA' and meta.get('game'):
            game=meta['game']
            for field in ENVIRONMENT_FIELDS:
                if not usable(((packet.get('environment') or {}).get(game) or {}).get(field)):
                    gaps.append({'path':f'environment.{game}.{field}','game':game,'reason':'null'})
    for row_id in shortlist_ids:
        scout = (packet.get("scouting") or {}).get(row_id)
        if not isinstance(scout, dict):
            gaps.append({"path": f"scouting.{row_id}", "reason": "missing_scouting"})
            continue
        for dim in ("matchup", "opportunity", "injuries", "game_script"):
            if not usable((scout.get("evidence") or {}).get(dim)):
                gaps.append({"path": f"scouting.{row_id}.evidence.{dim}", "reason": "null"})
        from scouting_checklist import required_checks
        parts = row_id.split('|')
        if len(parts) == 4:
            for check in required_checks(parts[0],parts[2]):
                if not usable((scout.get('supporting_stats') or {}).get(check)):
                    gaps.append({'path':f'scouting.{row_id}.supporting_stats.{check}', 'reason':'null'})
        if not scout.get("historical_usage") and not scout.get("scenarios"):
            gaps.append({"path": f"scouting.{row_id}.scenarios", "reason": "missing_scenarios"})
    # Use the actual engine validator too: shape-only checks miss stale evidence,
    # incompatible modes, incomplete numeric provenance and insufficient samples.
    from scouting_engine import project_scout
    candidates={r.get('id'):r for r in candidate_rows or [] if isinstance(r,dict)}
    for row_id in sorted(set(shortlist_ids)):
        parts=row_id.split('|')
        if len(parts)!=4:continue
        sport,player,stat,side=parts
        scout=(packet.get('scouting') or {}).get(row_id)
        if not isinstance(scout,dict):continue
        meta=index.get(player) or {}
        context=scout.get('season_context') or {}
        candidate={'sport':sport,'stat':stat,'side':side,'line':0,
                   'game_date':packet.get('date'),
                   'team':meta.get('team'),'player_id':meta.get('player_id'),
                   **candidates.get(row_id,{}),'scouting':scout}
        result=project_scout(candidate,now=now)
        if result['abstain']:
            gaps.append({'path':f'scouting.{row_id}', 'reason':result['abstain_reason'],
                         'detail':result.get('abstain_detail')})
        elif not result['reliable']:
            gaps.append({'path':f'scouting.{row_id}', 'reason':'engine_b_not_reliable',
                         'detail':result.get('quality'), 'coverage':result.get('coverage')})

    # Historical B does not consume narrative scenario fields. Retain these
    # questions for adversarial review, but never call them numeric prerequisites.
    for gap in gaps:
        path = gap['path']
        supporting = any(path.startswith(f'scouting.{rid}.') and
                         (packet.get('scouting', {}).get(rid) or {}).get('historical_usage')
                         for rid in shortlist_ids)
        gap['requirement'] = 'supporting_research' if supporting else 'verification'
        gap['requires_review'] = True
    return gaps
