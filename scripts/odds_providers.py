"""Pluggable player-prop odds for the pickem-auditor slate fetch.

The live source is PropLine. api.prop-line.com must be reachable.
Load PROPLINE_API_KEY from the
environment or config/credentials.local.json. If neither configures a key,
return no quotes and never invent a line or a price.

Quotes are two-sided only. One book posting one player, one stat, and one
line is one quote. Books are not collapsed into a single price.

Underdog is banned. This module does not request that bookmaker, the
us_dfs region, or any page on that site.
"""

from __future__ import annotations

import abc
import json
import math
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from local_credentials import propline_api_key

API_ROOT = "https://api.prop-line.com"
# Public API host: api.prop-line.com.
ALLOWLIST_NOTE = "api.prop-line.com must be added to the network allowlist."
ODDS_TIMEOUT = 20
EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# Requested books are a strict approved subset; never request DFS operators.
REQUEST_BOOKMAKERS = (
    "pinnacle",
    "fanduel",
    "draftkings",
    "betmgm",
)
DOCUMENTED_BOOKMAKERS = (
    "pinnacle",
    "fanduel",
    "draftkings",
    "betmgm",
    "williamhill_us",
)
RAW_BOOKS = {
    "pinnacle": "Pinnacle",
    "circa": "Circa",
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "bet365": "Bet365",
    "caesars": "Caesars",
    "williamhill_us": "Caesars",
    "betmgm": "BetMGM",
}
CANON_BOOKS = {
    "pinnacle": "Pinnacle",
    "circa": "Circa",
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "bet365": "Bet365",
    "caesars": "Caesars",
    "williamhillus": "Caesars",
    "betmgm": "BetMGM",
}
SHARP_BOOKS = ("pinnacle", "circa")
BOOK_PRIORITY = (
    "pinnacle",
    "circa",
    "fanduel",
    "draftkings",
    "bet365",
    "caesars",
    "betmgm",
)
QUOTE_FIELDS = (
    "sport",
    "event_id",
    "team",
    "opponent",
    "player",
    "player_norm",
    "stat",
    "book",
    "line",
    "over_odds",
    "under_odds",
    "retrieved_at",
    "source_url",
)

NBA_MARKETS = (
    ("player_points", "points"),
    ("player_rebounds", "rebounds"),
    ("player_assists", "assists"),
    ("player_threes", "threes"),
    ("player_points_rebounds_assists", "pra"),
    ("player_points_rebounds", "pr"),
    ("player_points_assists", "pa"),
    ("player_rebounds_assists", "ra"),
)
NHL_MARKETS = (
    ("player_shots_on_goal", "shots on goal"),
    ("player_blocked_shots", "blocked shots"),
    ("goalie_saves", "goalie saves"),
)
NFL_MARKETS = (
    ("player_receptions", "receptions"),
    ("player_reception_yds", "receiving yards"),
    ("player_rush_yds", "rushing yards"),
    ("player_pass_yds", "passing yards"),
    ("player_pass_attempts", "pass attempts"),
    ("player_pass_completions", "completions"),
    ("player_rush_attempts", "rush attempts"),
    ("player_tackles_assists", "tackles + assists"),
)
SPORTS = (
    ("NBA", "basketball_nba", NBA_MARKETS),
    ("NHL", "icehockey_nhl", NHL_MARKETS),
    ("NFL", "americanfootball_nfl", NFL_MARKETS),
)
STAT_BY_MARKET = {market: stat for _sport, _key, markets in SPORTS for market, stat in markets}
STAT_BY_MARKET['player_total_saves'] = 'goalie saves'  # legacy historical fixtures only
PROPLINE_SUPPORTED_MARKETS = frozenset({
    'player_points', 'player_rebounds', 'player_assists', 'player_threes',
    'player_points_rebounds_assists', 'player_shots_on_goal',
    'player_blocked_shots', 'goalie_saves', 'player_receptions',
    'player_reception_yds', 'player_rush_yds', 'player_pass_yds',
    'player_pass_attempts', 'player_pass_completions',
    'player_rush_attempts', 'player_tackles_assists', 'spreads', 'totals',
})
KNOWN_STATS = set(STAT_BY_MARKET.values())
SPORT_FROM_KEY = {key: sport for sport, key, _markets in SPORTS}

_SUFFIX_RE = re.compile(r"(?:\s+(?:jr|sr|iii|ii))+$")
_NETWORK_MARKERS = (
    "timed out",
    "timeout",
    "name or service not known",
    "temporary failure",
    "nodename",
    "not permitted",
    "network is unreachable",
    "network unavailable",
    "connection refused",
    "connection reset",
    "denied",
    "unreachable",
)

# Full names map to the abbreviation the slate row already uses.
# Shared abbreviations (BOS, CHI, LAC, UTA) stay shared. The join also
# checks sport, so a Bruins quote does not land on a Celtics row.
_TEAM_TABLE = """
ATL | Atlanta Hawks | Atlanta Falcons
BOS | Boston Celtics | Boston Bruins
BKN | Brooklyn Nets
CHA | Charlotte Hornets
CHI | Chicago Bulls | Chicago Blackhawks | Chicago Bears
CLE | Cleveland Cavaliers | Cleveland Browns
DAL | Dallas Mavericks | Dallas Stars | Dallas Cowboys
DEN | Denver Nuggets | Denver Broncos
DET | Detroit Pistons | Detroit Red Wings | Detroit Lions
GSW | Golden State Warriors
HOU | Houston Rockets | Houston Texans
IND | Indiana Pacers | Indianapolis Colts
LAC | Los Angeles Clippers | LA Clippers | Los Angeles Chargers | LA Chargers
LAL | Los Angeles Lakers | LA Lakers
LAR | Los Angeles Rams | LA Rams
LAK | Los Angeles Kings | LA Kings
MEM | Memphis Grizzlies
MIA | Miami Heat | Miami Dolphins
MIL | Milwaukee Bucks
MIN | Minnesota Timberwolves | Minnesota Wild | Minnesota Vikings
NOP | New Orleans Pelicans
NO | New Orleans Saints
NYK | New York Knicks | NY Knicks
NYG | New York Giants | NY Giants
NYJ | New York Jets | NY Jets
NYI | New York Islanders | NY Islanders
NYR | New York Rangers | NY Rangers
OKC | Oklahoma City Thunder
ORL | Orlando Magic
PHI | Philadelphia 76ers | Philadelphia Flyers | Philadelphia Eagles
PHX | Phoenix Suns
POR | Portland Trail Blazers
SAC | Sacramento Kings
SAS | San Antonio Spurs
TOR | Toronto Raptors | Toronto Maple Leafs
UTA | Utah Jazz | Utah Hockey Club | Utah Mammoth | Utah HC
WAS | Washington Wizards | Washington Commanders | Washington Football Team
WSH | Washington Capitals
ANA | Anaheim Ducks
BUF | Buffalo Sabres | Buffalo Bills
CGY | Calgary Flames
CAR | Carolina Hurricanes | Carolina Panthers
COL | Colorado Avalanche
CBJ | Columbus Blue Jackets
EDM | Edmonton Oilers
FLA | Florida Panthers
MTL | Montreal Canadiens | Montréal Canadiens
NSH | Nashville Predators
NJD | New Jersey Devils
OTT | Ottawa Senators
PIT | Pittsburgh Penguins | Pittsburgh Steelers
SJS | San Jose Sharks
SEA | Seattle Kraken | Seattle Seahawks
STL | St. Louis Blues | St Louis Blues
TBL | Tampa Bay Lightning
TB | Tampa Bay Buccaneers
VAN | Vancouver Canucks
VGK | Vegas Golden Knights | Las Vegas Golden Knights
WPG | Winnipeg Jets
ARI | Arizona Cardinals
BAL | Baltimore Ravens
CIN | Cincinnati Bengals
GB | Green Bay Packers
JAX | Jacksonville Jaguars
KC | Kansas City Chiefs
LV | Las Vegas Raiders
NE | New England Patriots
SF | San Francisco 49ers
TEN | Tennessee Titans
ALIAS GS GSW
ALIAS UTAH UTA
ALIAS JAC JAX
ALIAS NJ NJD
ALIAS SJ SJS
ALIAS MON MTL
ALIAS BRK BKN
ALIAS CHO CHA
ALIAS PHO PHX
"""


def _team_key(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^A-Za-z0-9]", "", text).upper()


def _build_team_maps(table: str) -> tuple[dict[str, str], dict[str, str]]:
    names: dict[str, str] = {}
    codes: dict[str, str] = {}
    for raw in table.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("ALIAS "):
            _alias, src, dst = line.split()
            codes[_team_key(src)] = dst.upper()
            continue
        abbrev, rest = [part.strip() for part in line.split("|", 1)]
        abbrev = abbrev.upper()
        codes[_team_key(abbrev)] = abbrev
        for label in rest.split("|"):
            label = label.strip()
            if label:
                names[_team_key(label)] = abbrev
    return names, codes


_TEAM_NAMES, _TEAM_CODES = _build_team_maps(_TEAM_TABLE)


def banned(*values) -> bool:
    """True when a book or URL is an Underdog source. The site itself is never requested."""
    for value in values:
        if "underdog" in str(value or "").lower():
            return True
    return False


def canon_book(name) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


def approved_book_name(value) -> str | None:
    if banned(value):
        return None
    raw = str(value or "").strip().lower()
    if raw in RAW_BOOKS:
        return RAW_BOOKS[raw]
    key = canon_book(value)
    return CANON_BOOKS.get(key)


def canon_stat(value) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    if text in KNOWN_STATS:
        return text
    return ""


def normalize_player(name) -> str:
    """Lower-case name without accents, punctuation, or a trailing Jr/Sr/II/III."""
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("'", "").replace("’", "").replace("`", "").replace(".", "")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    text = _SUFFIX_RE.sub("", text).strip()
    return re.sub(r"\s+", " ", text).strip()


def normalize_team(value) -> str:
    """Abbreviation used on the slate row. Unknown full names become blank."""
    key = _team_key(value)
    if not key:
        return ""
    if key in _TEAM_CODES:
        return _TEAM_CODES[key]
    if key in _TEAM_NAMES:
        return _TEAM_NAMES[key]
    if 2 <= len(key) <= 4 and key.isalpha():
        return key
    return ""


def _json_number(number: float):
    if abs(number - round(number)) < 1e-9:
        return int(round(number))
    return float(number)


def _line(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if isinstance(value, bool) or not math.isfinite(number):
        return None
    number = round(number, 6)
    return _json_number(number)


def _american(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if isinstance(value, bool) or not math.isfinite(number) or abs(number) < 100:
        return None
    return _json_number(number)


def parse_time(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _timestamp(value, fallback: str) -> str:
    parsed = parse_time(value)
    if parsed is None:
        return fallback
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def age_minutes(retrieved_at, now) -> float | None:
    then = parse_time(retrieved_at)
    current = parse_time(now)
    if then is None or current is None:
        return None
    minutes = (current - then).total_seconds() / 60.0
    if minutes < 0:
        return None
    return minutes


def event_on_date(commence, game_date: str) -> bool:
    """True when commence_time falls on game_date in US Eastern."""
    if commence is None:
        return False
    text = str(commence).strip()
    if len(text) == 10:
        return text == game_date
    parsed = parse_time(text)
    if parsed is None:
        return False
    return parsed.astimezone(EASTERN).date().isoformat() == game_date


def make_quote(
    *,
    sport,
    event_id,
    team,
    opponent,
    player,
    stat,
    book,
    line,
    over_odds,
    under_odds,
    retrieved_at,
    source_url,
) -> dict | None:
    """One two-sided quote, or None when a side, book, or stat is unusable."""
    if banned(book, source_url):
        return None
    book_name = approved_book_name(book)
    stat_name = canon_stat(stat)
    line_value = _line(line)
    over = _american(over_odds)
    under = _american(under_odds)
    player_name = " ".join(str(player or "").split())
    if not book_name or not stat_name or not player_name or line_value is None or over is None or under is None:
        return None
    quote = {
        "sport": str(sport or "").strip().upper(),
        "event_id": str(event_id or ""),
        "team": normalize_team(team),
        "opponent": normalize_team(opponent),
        "player": player_name,
        "player_norm": normalize_player(player_name),
        "stat": stat_name,
        "book": book_name,
        "line": line_value,
        "over_odds": over,
        "under_odds": under,
        "retrieved_at": str(retrieved_at or ""),
        "source_url": str(source_url or ""),
    }
    _assert_quote_shape(quote)
    return quote


def _opponent_abbrev(team: str, home, away) -> str:
    home_code = normalize_team(home)
    away_code = normalize_team(away)
    if team and team == home_code and away_code and away_code != team:
        return away_code
    if team and team == away_code and home_code and home_code != team:
        return home_code
    return ""


def _pair_outcomes(outcomes) -> list[dict]:
    buckets: dict[tuple, dict] = {}
    order: list[tuple] = []
    for outcome in outcomes or []:
        if not isinstance(outcome, dict):
            continue
        side = str(outcome.get("name") or "").strip().lower()
        if side not in ("over", "under"):
            continue
        player = " ".join(str(outcome.get("description") or outcome.get("player") or "").split())
        if not player:
            continue
        line = _line(outcome.get("point") if "point" in outcome else outcome.get("line"))
        odds = _american(outcome.get("price") if "price" in outcome else outcome.get(f"{side}_odds"))
        if line is None or odds is None:
            continue
        key = (player, line)
        if key not in buckets:
            buckets[key] = {"player": player, "line": line, "teams": []}
            order.append(key)
        bucket = buckets[key]
        bucket[side] = odds
        team_name = outcome.get("team") or outcome.get("team_name")
        if team_name:
            bucket["teams"].append(team_name)
    pairs = []
    for key in order:
        bucket = buckets[key]
        if "over" not in bucket or "under" not in bucket:
            continue
        teams = {normalize_team(name) for name in bucket["teams"]}
        teams.discard("")
        if len(teams) > 1:
            continue
        pairs.append(
            {
                "player": bucket["player"],
                "line": bucket["line"],
                "over": bucket["over"],
                "under": bucket["under"],
                "team": next(iter(teams)) if teams else "",
            }
        )
    return pairs


def quotes_from_event(event: dict, *, sport: str, retrieved_at: str, source_url: str) -> list[dict]:
    """Approved two-sided player props from one Odds API event payload."""
    if not isinstance(event, dict) or banned(source_url):
        return []
    event_sport = SPORT_FROM_KEY.get(str(event.get("sport_key") or "").lower(), sport)
    event_id = str(event.get("id") or event.get("event_id") or "")
    home = event.get("home_team")
    away = event.get("away_team")
    quotes = []
    for bookmaker in event.get("bookmakers") or []:
        if not isinstance(bookmaker, dict):
            continue
        if banned(bookmaker.get("key"), bookmaker.get("title")):
            continue
        book_name = approved_book_name(bookmaker.get("key") or bookmaker.get("title"))
        if not book_name:
            continue
        for market in bookmaker.get("markets") or []:
            if not isinstance(market, dict):
                continue
            market_key = str(market.get("key") or "")
            if market_key.endswith("_alternate"):
                continue
            stat = STAT_BY_MARKET.get(market_key) or canon_stat(market.get("stat") or "")
            if not stat:
                continue
            stamp = _timestamp(market.get("last_update") or bookmaker.get("last_update"), retrieved_at)
            for pair in _pair_outcomes(market.get("outcomes") or market.get("player_markets") or []):
                team = pair["team"]
                opponent = _opponent_abbrev(team, home, away) if team else ""
                quote = make_quote(
                    sport=event_sport,
                    event_id=event_id,
                    team=team,
                    opponent=opponent,
                    player=pair["player"],
                    stat=stat,
                    book=book_name,
                    line=pair["line"],
                    over_odds=pair["over"],
                    under_odds=pair["under"],
                    retrieved_at=stamp,
                    source_url=source_url,
                )
                if quote:
                    quote['event_id_namespace']='propline'
                    quote['event_start']=event.get('commence_time')
                    quote['event_teams']=[normalize_team(home),normalize_team(away)]
                    start=parse_time(event.get('commence_time'))
                    if start:quote['game_date']=start.astimezone(EASTERN).date().isoformat()
                    quotes.append(quote)
    return quotes


def quotes_from_api_payload(payload, *, sport: str, retrieved_at: str, source_url: str) -> list[dict]:
    """Parse an event, a list of events, or return [] for a game-odds document."""
    events: list = []
    if isinstance(payload, list):
        events = payload
    elif isinstance(payload, dict) and isinstance(payload.get("bookmakers"), list):
        events = [payload]
    elif isinstance(payload, dict):
        nested = payload.get("events")
        if isinstance(nested, list):
            events = [item for item in nested if isinstance(item, dict) and item.get("bookmakers")]
    quotes = []
    for event in events:
        if isinstance(event, dict):
            quotes.extend(
                quotes_from_event(event, sport=sport, retrieved_at=retrieved_at, source_url=source_url)
            )
    return dedupe_quotes(quotes)


def quotes_from_records(records, *, source_url: str = "", retrieved_at: str = "") -> list[dict]:
    """Normalize fixture rows. A missing side, banned book, or unknown stat is dropped."""
    quotes = []
    for record in records or []:
        if not isinstance(record, dict):
            continue
        if banned(record.get("book"), record.get("source_url"), record.get("source")):
            continue
        quote = make_quote(
            sport=record.get("sport") or "",
            event_id=record.get("event_id") or "",
            team=record.get("team") or "",
            opponent=record.get("opponent") or "",
            player=record.get("player") or "",
            stat=record.get("stat") or "",
            book=record.get("book") or "",
            line=record.get("line"),
            over_odds=record.get("over_odds"),
            under_odds=record.get("under_odds"),
            retrieved_at=record.get("retrieved_at") or retrieved_at,
            source_url=record.get("source_url") or source_url,
        )
        if quote:
            for key in ('game_date','event_start','event_id_namespace','event_teams'):
                if key in record:quote[key]=record[key]
            quotes.append(quote)
    return dedupe_quotes(quotes)


def dedupe_quotes(quotes: list[dict]) -> list[dict]:
    seen = set()
    kept = []
    for quote in quotes:
        key = (
            quote.get("sport"),
            quote.get("event_id"),
            quote.get("player_norm"),
            quote.get("team"),
            quote.get("stat"),
            canon_book(quote.get("book")),
            quote.get("line"),
        )
        if key in seen:
            continue
        seen.add(key)
        kept.append(quote)
    return kept


def ordered_quotes(quotes) -> list[dict]:
    def sort_key(quote):
        line = quote.get("line")
        return (
            quote.get("sport") or "",
            quote.get("player_norm") or "",
            quote.get("team") or "",
            quote.get("stat") or "",
            line if isinstance(line, (int, float)) else 0,
            quote.get("book") or "",
            quote.get("event_id") or "",
        )

    return sorted((dict(quote) for quote in quotes or []), key=sort_key)


def _same_player(quote: dict, row: dict) -> bool:
    if quote.get("player_norm") != normalize_player(row.get("player")):
        return False
    quote_sport = str(quote.get("sport") or "").strip().upper()
    row_sport = str(row.get("sport") or "").strip().upper()
    if quote_sport and row_sport and quote_sport != row_sport:
        return False
    return True


def same_fixture(quote, row):
    """Reject contradictory fixture evidence without equating provider ID spaces."""
    for field,normalize in (('opponent',normalize_team),('game_date',str)):
        if quote.get(field) and row.get(field) and normalize(quote[field])!=normalize(row[field]):
            return False
    teams={normalize_team(t) for t in quote.get('event_teams',[]) if t}
    if teams and any(row.get(k) and normalize_team(row[k]) not in teams for k in ('team','opponent')):
        return False
    namespace=quote.get('event_id_namespace')
    if namespace and namespace==row.get('event_id_namespace') and quote.get('event_id') and row.get('event_id'):
        if str(quote['event_id'])!=str(row['event_id']):return False
    return True


def _unmatched_reason(quote: dict, rows) -> str:
    compatible = [row for row in rows or [] if _same_player(quote, row)]
    teams = {normalize_team(row.get("team")) for row in compatible}
    teams.discard("")
    team = quote.get("team") or ""
    if not team:
        if len(teams) > 1:
            return "same name on more than one team"
        if not teams:
            return "name is not on the slate"
        return "team missing"
    same_team = [row for row in compatible if normalize_team(row.get("team")) == team]
    if not same_team:
        return "team does not match a slate row"
    if not any(canon_stat(row.get("stat")) == quote.get("stat") for row in same_team):
        return "stat is not on the slate row"
    return "unmatched"


def resolve_quote_teams(quotes, rows) -> tuple[list[dict], list[dict]]:
    """Fill a blank team from the slate when the normalized name is on one team.

    The join key is (player_norm, team), and team is the slate row's team.
    A quote that still does not match is returned in the unmatched log.
    Every quote is kept.
    """
    resolved = []
    unmatched = []
    slate = list(rows or [])
    for original in quotes or []:
        quote = dict(original)
        quote["player_norm"] = normalize_player(quote.get("player"))
        quote["team"] = normalize_team(quote.get("team"))
        quote["opponent"] = normalize_team(quote.get("opponent"))
        quote["stat"] = canon_stat(quote.get("stat")) or quote.get("stat")
        if not quote["team"]:
            compatible = [row for row in slate if _same_player(quote, row) and same_fixture(quote,row)]
            teams = {normalize_team(row.get("team")) for row in compatible}
            teams.discard("")
            if len(teams) == 1:
                only = next(iter(teams))
                quote["team"] = only
                if not quote["opponent"]:
                    sample = next(row for row in compatible if normalize_team(row.get("team")) == only)
                    quote["opponent"] = normalize_team(sample.get("opponent"))
        matched = any(
            _same_player(quote, row)
            and same_fixture(quote,row)
            and normalize_team(row.get("team")) == quote.get("team")
            and canon_stat(row.get("stat")) == quote.get("stat")
            for row in slate
        )
        if not matched:
            unmatched.append(
                {
                    "player": quote.get("player"),
                    "player_norm": quote.get("player_norm"),
                    "team": quote.get("team") or "",
                    "stat": quote.get("stat"),
                    "sport": quote.get("sport") or "",
                    "reason": _unmatched_reason(quote, slate),
                }
            )
        resolved.append(quote)
    return resolved, unmatched


def unmatched_note(items) -> str:
    if not items:
        return ""
    shown = []
    for item in items[:20]:
        team = item.get("team") or "blank"
        shown.append(
            f"{item.get('player')} {item.get('stat')} team={team} ({item.get('reason')})"
        )
    extra = len(items) - len(shown)
    suffix = f" (+{extra} more)" if extra else ""
    noun = "quote" if len(items) == 1 else "quotes"
    return f"odds: {len(items)} unmatched {noun}: " + "; ".join(shown) + suffix


def quotes_for_row(quotes, row) -> list[dict]:
    """Quotes whose (player_norm, team) equals the slate row, and whose stat matches."""
    player = normalize_player(row.get("player"))
    team = normalize_team(row.get("team"))
    stat = canon_stat(row.get("stat"))
    sport = str(row.get("sport") or "").strip().upper()
    found = []
    for quote in quotes or []:
        if quote.get("player_norm") != player:
            continue
        if normalize_team(quote.get("team")) != team:
            continue
        if quote.get("stat") != stat:
            continue
        quote_sport = str(quote.get("sport") or "").strip().upper()
        if sport and quote_sport and sport != quote_sport:
            continue
        if not same_fixture(quote,row):continue
        found.append(quote)
    return found


def _distinct_books(quotes) -> list[dict]:
    chosen: dict[str, dict] = {}
    for quote in quotes:
        key = canon_book(quote.get("book"))
        chosen.setdefault(key, quote)
    return list(chosen.values())


def _book_rank(quote) -> tuple:
    key = canon_book(quote.get("book"))
    try:
        priority = BOOK_PRIORITY.index(key)
    except ValueError:
        priority = len(BOOK_PRIORITY)
    return (priority, quote.get("book") or "")


def primary_price(quotes) -> dict | None:
    """Sharp line when any sharp book posted one, otherwise the most-quoted line.

    Pinnacle wins when Pinnacle and Circa are on different lines. n_books
    counts distinct books on that primary line. lines_disagree stays true
    whenever the approved books posted more than one line.
    """
    by_line: dict = {}
    for quote in quotes or []:
        line = quote.get("line")
        if line is None:
            continue
        by_line.setdefault(line, []).append(quote)
    if not by_line:
        return None

    def rank(line):
        books = _distinct_books(by_line[line])
        keys = {canon_book(quote.get("book")) for quote in books}
        sharp = [key for key in keys if key in SHARP_BOOKS]
        return (1 if sharp else 0, len(sharp), 1 if "pinnacle" in keys else 0, len(books))

    best_line = None
    best_rank = None
    for line in by_line:
        score = rank(line)
        if best_rank is None or score > best_rank or (score == best_rank and line < best_line):
            best_rank = score
            best_line = line
    group = _distinct_books(by_line[best_line])
    anchor = min(group, key=_book_rank)
    return {
        "line": best_line,
        "book": anchor["book"],
        "over_odds": anchor["over_odds"],
        "under_odds": anchor["under_odds"],
        "n_books": len(group),
        "lines_disagree": len(by_line) > 1,
    }


def _format_number(value, *, odds: bool) -> str:
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        whole = int(round(number))
        if odds and whole > 0:
            return f"+{whole}"
        return str(whole)
    text = f"{number:.6f}".rstrip("0").rstrip(".")
    if odds and number > 0:
        return f"+{text}"
    return text


def book_spec(book, line, target, other, side: str) -> str:
    """Book:line:target:other:side, the five-part spec pipeline accepts."""
    return ":".join(
        (
            str(book),
            _format_number(line, odds=False),
            _format_number(target, odds=True),
            _format_number(other, odds=True),
            side,
        )
    )


def consensus_input(quotes, *, now=None, side: str = "over") -> list[dict]:
    """Group quotes by (player_norm, team, stat, line) for pickem_math pipeline.

    `books` entries have book, line, target, other, and book_side. `book_specs`
    is the same list as Book:line:target:other:side strings. target is the
    price on `side`. retrieved_minutes_ago is the oldest quote in the group.
    """
    chosen = str(side or "").strip().lower()
    if chosen not in ("over", "under"):
        raise ValueError("side must be over or under")
    current = parse_time(now) if now is not None else datetime.now(UTC)
    groups: dict[tuple, list] = {}
    for quote in quotes or []:
        key = (
            quote.get("player_norm") or normalize_player(quote.get("player")),
            quote.get("team") or "",
            quote.get("stat") or "",
            quote.get("line"),
            quote.get('sport') or '', quote.get('game_date') or '',
            quote.get('opponent') or '', quote.get('event_id_namespace') or '', quote.get('event_id') or '',
        )
        groups.setdefault(key, []).append(quote)
    outputs = []
    for key in sorted(groups, key=lambda item: (item[0] or "", item[1], item[2] or "", item[3] or 0)):
        bucket = _distinct_books(groups[key])
        bucket.sort(key=_book_rank)
        first = bucket[0]
        books = []
        specs = []
        ages = []
        for quote in bucket:
            if chosen == "over":
                target, other = quote["over_odds"], quote["under_odds"]
            else:
                target, other = quote["under_odds"], quote["over_odds"]
            books.append(
                {
                    "book": quote["book"],
                    "line": quote["line"],
                    "target": target,
                    "other": other,
                    "book_side": chosen,
                }
            )
            specs.append(book_spec(quote["book"], quote["line"], target, other, chosen))
            age = age_minutes(quote.get("retrieved_at"), current)
            if age is not None:
                ages.append(age)
        outputs.append(
            {
                "player": first.get("player"),
                "player_norm": first.get("player_norm"),
                "team": first.get("team") or "",
                "opponent": first.get("opponent") or "",
                "sport": first.get("sport") or "",
                "stat": first.get("stat"),
                "line": first.get("line"),
                "books": books,
                "book_specs": specs,
                "retrieved_minutes_ago": max(ages) if ages and len(ages)==len(bucket) else None,
                "market_retrieved_at": min(parse_time(q["retrieved_at"]) for q in bucket).isoformat() if ages and len(ages)==len(bucket) else None,
            }
        )
    return outputs


def resolve_sports(sports) -> list[tuple]:
    if not sports:
        return list(SPORTS)
    wanted = []
    seen = set()
    aliases = {}
    for sport, key, markets in SPORTS:
        aliases[sport] = (sport, key, markets)
        aliases[key.upper()] = (sport, key, markets)
    for item in sports:
        label = str(item or "").strip().upper().replace("-", "_")
        match = aliases.get(label)
        if match and match[0] not in seen:
            seen.add(match[0])
            wanted.append(match)
    return wanted


def redact(value, secret: str | None = None) -> str:
    text = str(value)
    if secret:
        text = text.replace(str(secret), "REDACTED")
    return re.sub(r"(apiKey=)[^&\s]+", r"\1REDACTED", text, flags=re.IGNORECASE)


def _public_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = [(key, val) for key, val in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if key.lower() != "apikey"]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query, safe=","), "")
    )


def _is_network_failure(message: str) -> bool:
    text = message.lower()
    return any(marker in text for marker in _NETWORK_MARKERS)


def _error_text(exc: BaseException, secret: str) -> str:
    body = ""
    read = getattr(exc, "read", None)
    if callable(read):
        try:
            raw = read()
        except Exception:
            raw = b""
        if isinstance(raw, bytes):
            body = raw.decode("utf-8", "replace")
        elif raw:
            body = str(raw)
    close = getattr(exc, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
    code = getattr(exc, "code", None)
    prefix = f"HTTP {code} " if code else f"{type(exc).__name__}: "
    return redact(f"{prefix}{exc} {body}".strip(), secret)


def _default_fetch(url: str, timeout: float = ODDS_TIMEOUT, headers: dict | None = None):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "pickem-auditor-odds",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class Provider(abc.ABC):
    """Source of player-prop quotes. fetch returns a list and never invents a price.

    `note` explains an empty or partial result. `source_urls` are public URLs
    with the API key removed.
    """

    def __init__(self):
        self.note: str | None = None
        self.source_urls: list[str] = []

    @abc.abstractmethod
    def fetch(self, game_date: str, sports: list[str] | None = None) -> list[dict]:
        """Quotes for game_date (US Eastern YYYY-MM-DD) and the requested sports."""


class FixtureProvider(Provider):
    """Offline provider. Pass quote records or a PropLine event payload."""

    def __init__(self, records=None, events=None, sport: str = "NHL", retrieved_at: str | None = None, source_url: str | None = None):
        super().__init__()
        self.records = list(records or [])
        self.events = events
        self.sport = sport
        self.retrieved_at = retrieved_at or "2026-10-22T16:00:00Z"
        self.source_url = source_url or "https://example.test/odds"

    def fetch(self, game_date: str, sports: list[str] | None = None) -> list[dict]:
        del game_date, sports
        if self.events is not None:
            quotes = quotes_from_api_payload(
                self.events,
                sport=self.sport,
                retrieved_at=self.retrieved_at,
                source_url=self.source_url,
            )
        else:
            quotes = quotes_from_records(
                self.records,
                source_url=self.source_url,
                retrieved_at=self.retrieved_at,
            )
        self.source_urls = [self.source_url] if quotes else []
        self.note = None if quotes else "odds: fixture returned no two-sided player props."
        return quotes


class PropLineProvider(Provider):
    """PropLine bulk player-prop feed. One request per sport, never per event.

    Only approved sportsbooks, paired over/under prices and identity-matched
    events are retained. Auth is carried in X-API-Key, never in URLs or logs.
    """

    def __init__(self, api_key: str | None = None, fetch=None, clock=None):
        super().__init__()
        self.api_key = str(propline_api_key() if api_key is None else api_key or "")
        self.fetch_json = fetch or _default_fetch
        self.clock = clock or (lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

    @staticmethod
    def _daily_quota_check(secret: str, opener=None) -> tuple[int | None, str | None]:
        """One authenticated lightweight request; fail closed on absent quota."""
        request = urllib.request.Request(
            API_ROOT + "/v1/sports",
            headers={"X-API-Key":secret, "Accept":"application/json"},
        )
        try:
            with (opener or urllib.request.urlopen)(request, timeout=12) as response:
                if getattr(response, "status", 200) != 200:
                    return None, "PROPLINE_QUOTA_CHECK_HTTP_ERROR"
                remaining = response.headers.get("X-Daily-Remaining")
                if remaining is None or not str(remaining).isdigit():
                    return None, "PROPLINE_QUOTA_HEADER_MISSING"
                return int(remaining), None
        except (OSError, ValueError, TypeError):
            return None, "PROPLINE_QUOTA_CHECK_UNAVAILABLE"

    def _url(self, path: str, params: dict | None = None) -> str:
        query = urllib.parse.urlencode(params or {}, safe=",")
        return API_ROOT + path + (("?" + query) if query else "")

    def _remember(self, url: str) -> None:
        public = _public_url(url)
        if public not in self.source_urls:
            self.source_urls.append(public)

    def _get(self, url: str, secret: str):
        self._remember(url)
        try:
            return self.fetch_json(
                url, timeout=ODDS_TIMEOUT, headers={"X-API-Key":secret}
            ), None
        except Exception as exc:
            return None, exc

    def _fail(self, sport_key: str, action: str, exc: BaseException, secret: str) -> str:
        message = _error_text(exc, secret)
        note = f"odds: PropLine {sport_key} {action} failed ({message}). No prices were invented."
        if _is_network_failure(message):
            note += " " + ALLOWLIST_NOTE
        return note

    def _events(self, sport_key: str, secret: str):
        url = self._url(f"/v1/sports/{sport_key}/events")
        payload, error = self._get(url, secret)
        if error:
            return [], self._fail(sport_key, "events", error, secret)
        if isinstance(payload, dict):
            payload = payload.get("events") or payload.get("data")
        if not isinstance(payload, list):
            return [], f"odds: PropLine {sport_key} events schema mismatch."
        return payload, None

    def _bulk_odds(self, sport_key: str, markets, secret: str):
        allowed = [market for market, _stat in markets if market in PROPLINE_SUPPORTED_MARKETS]
        if not allowed:
            return [], None
        url = self._url(f"/v1/sports/{sport_key}/odds", {
            "markets":",".join(allowed),
            "bookmakers":",".join(REQUEST_BOOKMAKERS),
        })
        payload, error = self._get(url, secret)
        if error:
            return [], self._fail(sport_key, "bulk odds", error, secret)
        if isinstance(payload, dict):
            payload = payload.get("events") or payload.get("data")
        if not isinstance(payload, list):
            return [], f"odds: PropLine {sport_key} bulk odds schema mismatch."
        return payload, None

    def fetch(self, game_date: str, sports: list[str] | None = None) -> list[dict]:
        self.note = None
        self.source_urls = []
        secret = self.api_key.strip()
        if not secret:
            self.note = "odds: PROPLINE_API_KEY is not configured. No line or price was invented."
            return []
        selected = resolve_sports(sports)
        if not selected:
            self.note = "odds: no supported sports requested."
            return []
        if os.environ.get("PICKEM_ODDS_QUOTA_GUARD") == "1":
            remaining, error = self._daily_quota_check(secret)
            if error:
                self.note = "odds: " + error + ". No bulk requests attempted."
                return []
            if remaining < len(selected):
                self.note = (f"odds: PROPLINE_QUOTA_INSUFFICIENT: {remaining} requests remaining, "
                             f"{len(selected)} sports requested. No bulk requests attempted.")
                return []
        notes, quotes = [], []
        now = self.clock()
        for sport, key, markets in selected:
            payload, error = self._bulk_odds(key, markets, secret)
            if error:
                notes.append(error)
                continue
            dated = [ev for ev in payload if isinstance(ev, dict)
                     and event_on_date(ev.get("commence_time"), game_date)
                     and not ev.get("is_outright")]
            if not dated:
                notes.append(f"odds: PropLine {key} had no matching pregame events on {game_date}.")
            public = self._url(f"/v1/sports/{key}/odds", {
                "markets":",".join(m for m,_ in markets if m in PROPLINE_SUPPORTED_MARKETS),
                "bookmakers":",".join(REQUEST_BOOKMAKERS),
            })
            for event in dated:
                quotes.extend(quotes_from_event(
                    event, sport=sport, retrieved_at=now, source_url=public
                ))
        quotes = dedupe_quotes(quotes)
        if notes:
            self.note = " ".join(notes)
        elif not quotes:
            self.note = "odds: PropLine returned no approved two-sided player props."
        return quotes


def _assert_quote_shape(quote: dict) -> None:
    missing = [field for field in QUOTE_FIELDS if field not in quote]
    if missing:
        raise ValueError("quote missing " + ", ".join(missing))
