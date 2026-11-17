"""P1-only official prior-game evidence. Never reads the outcome vault.

Trust boundary: bytes must come from independently reviewed NBA HTTPS captures.
Hash/URL validation establishes internal consistency, not collector authenticity.
No original historical availability timestamp is inferred from a game date.
"""
from datetime import date
from fractions import Fraction
import hashlib
import math
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .v2_contracts import digest, instant

VERSION = 'nba-p1-prior-game-evidence/1.0.0'
STAT_KEYS = {
    'points': 'points', 'rebounds': 'reboundsTotal', 'assists': 'assists',
    'threes': 'threePointersMade', 'fgm': 'fieldGoalsMade',
    'fga': 'fieldGoalsAttempted', 'fg3a': 'threePointersAttempted',
    'ftm': 'freeThrowsMade', 'fta': 'freeThrowsAttempted',
    'oreb': 'reboundsOffensive', 'dreb': 'reboundsDefensive',
    'steals': 'steals', 'blocks': 'blocks', 'turnovers': 'turnovers',
    'personal_fouls': 'foulsPersonal',
}


def _fail(code):
    from .p1_history import fail
    fail(code)


def _capture(bundle):
    """Validate complete receipt chain, exact raw hashes and source identity."""
    from .p1_history import _strict_json
    if not isinstance(bundle, dict) or set(bundle) != {'capture', 'raw', 'prior'}:
        _fail('OFFICIAL_EVIDENCE_FIELDS')
    chain = bundle['prior']
    if not isinstance(chain, list):
        _fail('OFFICIAL_REVISION_CHAIN')
    previous = None
    url = None
    game = None
    for n, item in enumerate(chain + [bundle], 1):
        if not isinstance(item, dict) or set(item) != {'capture', 'raw', 'prior'}:
            _fail('OFFICIAL_EVIDENCE_FIELDS')
        # Prior entries are flat; nested chains would create ambiguous ancestry.
        if item is not bundle and item['prior']:
            _fail('OFFICIAL_REVISION_CHAIN')
        c, raw = item['capture'], item['raw']
        if not isinstance(c, dict) or set(c) != {
            'schema', 'url', 'raw_sha256', 'retrieved_at', 'revision',
            'supersedes_receipt_sha256'}:
            _fail('OFFICIAL_CAPTURE_FIELDS')
        if c['schema'] != VERSION:
            _fail('OFFICIAL_CAPTURE_SCHEMA')
        if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != c['raw_sha256']:
            _fail('OFFICIAL_SOURCE_SHA_MISMATCH')
        u = urlsplit(c['url'])
        if (u.scheme != 'https' or u.netloc != 'cdn.nba.com' or u.query or u.fragment
                or not re.fullmatch(r'/static/json/liveData/boxscore/boxscore_[0-9]{10}\.json', u.path)):
            _fail('OFFICIAL_SOURCE_IDENTITY')
        if type(c['revision']) is not int or c['revision'] != n:
            _fail('OFFICIAL_REVISION_CHAIN')
        if c['supersedes_receipt_sha256'] != (digest(previous) if previous else None):
            _fail('OFFICIAL_REVISION_CHAIN')
        if previous and (c['url'] != url or instant(c['retrieved_at']) <= instant(previous['retrieved_at'])):
            _fail('OFFICIAL_REVISION_IDENTITY_OR_CLOCK')
        parsed = _strict_json(raw)
        current = parsed.get('game')
        if not isinstance(current, dict):
            _fail('OFFICIAL_GAME_MISSING')
        if u.path != '/static/json/liveData/boxscore/boxscore_' + str(current.get('gameId')) + '.json':
            _fail('OFFICIAL_GAME_IDENTITY')
        if game and (current['gameId'] != game['gameId'] or
                     any(current.get(k, {}).get('teamId') != game.get(k, {}).get('teamId')
                         for k in ('homeTeam', 'awayTeam'))):
            _fail('OFFICIAL_REVISION_GAME_CONFLICT')
        if instant(c['retrieved_at']) <= instant(current['gameTimeUTC']):
            _fail('OFFICIAL_CAPTURE_BEFORE_GAME')
        previous, url, game = c, c['url'], current
    return game


def seconds(value):
    """Parse raw clock text exactly, independent of Decimal/float precision.

    Physical cap, zero-clock and display-rounding decisions must precede any
    lossy serialization. Arbitrarily small positive source increments matter.
    """
    if not isinstance(value, str):
        _fail('OFFICIAL_MINUTE_FORMAT')
    m = re.fullmatch(r'PT(\d+)M(\d+(?:\.\d+)?)S', value)
    if not m or Fraction(m[2]) >= 60:
        _fail('OFFICIAL_MINUTE_FORMAT')
    return Fraction(m[1]) * 60 + Fraction(m[2])


def duration(bundle, *, game_id, game_date=None):
    """Versioned P2 handoff: actual completed periods, no maximum OT count.

    This function must receive only prior-game evidence. The pregame builder
    separately rejects same-day/future/target games before consuming it.
    """
    g = _capture(bundle)
    if game_id != 'nba:game:' + str(g['gameId']):
        _fail('OFFICIAL_GAME_CROSSWALK_REQUIRED')
    if g.get('gameStatus') != 3 or type(g.get('period')) is not int or g['period'] < 4:
        _fail('OFFICIAL_COMPLETED_DURATION_REQUIRED')
    if seconds(g.get('gameClock')) != 0:
        _fail('OFFICIAL_FINAL_CLOCK_CONFLICT')
    day = instant(g['gameTimeUTC']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
    if game_date is not None and date.fromisoformat(game_date).isoformat() != day:
        _fail('OFFICIAL_GAME_DATE_CONFLICT')
    teams = [g.get(k, {}).get('teamId') for k in ('homeTeam', 'awayTeam')]
    if any(type(t) is not int or t <= 0 for t in teams) or teams[0] == teams[1]:
        _fail('OFFICIAL_TEAM_IDENTITY')
    ot = g['period'] - 4
    return dict(schema=VERSION, game_id=game_id, game_date=day,
                overtime_periods=ot, duration_minutes=48 + 5 * ot,
                source_status='OFFICIAL_BYTES_CONSISTENT_AUTHENTICITY_REVIEW_REQUIRED',
                raw_sha256=bundle['capture']['raw_sha256'],
                receipt_sha256=digest(bundle['capture']),
                retrieved_at=bundle['capture']['retrieved_at'],
                original_pregame_available_at=None,
                certification='HISTORICAL_RECONSTRUCTION_UNCERTIFIED')


def adjudicate_player(data, bundle):
    """Bind identity, clock and every retained stat to official source bytes.

    A zero integer display can represent <30 seconds. Exact zero with positive
    credits remains unresolved: the box alone cannot explain dead-ball credit.
    """
    # Direct native consumers bypass the normalized-history builder. Enforce
    # the same participation/count/minute invariants at this shared boundary.
    from .p1_history import _stats
    if data.get('participation') not in ('played', 'dnp', 'unknown'):
        _fail('INVALID_DNP_STATUS')
    _stats(data['stats'])
    if data['participation'] == 'played':
        displayed = data['minutes']
        if type(displayed) not in (int, float) or not math.isfinite(displayed) or displayed < 0:
            _fail('INVALID_MINUTES')
    elif data['minutes'] is not None or data['stats']:
        _fail('DNP_UNKNOWN_NOT_ZERO')
    d = duration(bundle, game_id=data['game_id'], game_date=data['game_date'])
    g = _capture(bundle)
    teams = {'nba:team:' + str(g[k]['teamId']): g[k] for k in ('homeTeam', 'awayTeam')}
    if data['team_id'] not in teams or data['opponent_id'] not in teams or data['team_id'] == data['opponent_id']:
        _fail('OFFICIAL_TEAM_CONFLICT')
    people = [(tid, p) for tid, team in teams.items() for p in team.get('players', [])
              if 'nba:player:' + str(p.get('personId')) == data['player_id']]
    if len(people) != 1 or people[0][0] != data['team_id']:
        _fail('OFFICIAL_PLAYER_TEAM_CONFLICT')
    p = people[0][1]
    s = p.get('statistics', {})
    if not isinstance(s, dict):
        _fail('OFFICIAL_STAT_CONFLICT')
    normalized = {k: s[v] for k, v in STAT_KEYS.items() if v in s}
    _stats(normalized)
    if data['participation'] != 'played':
        # Nonparticipation evidence must be explicit; absence is not a DNP.
        allowed = ('0',) if data['participation'] == 'dnp' else (None, 'unknown')
        if p.get('played') not in allowed:
            _fail('OFFICIAL_PARTICIPATION_CONFLICT')
        source_minutes = seconds(s['minutes']) if 'minutes' in s else 0
        if source_minutes != 0 or any(normalized.values()):
            _fail('OFFICIAL_NONPARTICIPATION_CREDIT_UNRESOLVED')
        return d, None, 'NONPARTICIPATION_OR_UNKNOWN'
    if p.get('played') != '1':
        _fail('OFFICIAL_PARTICIPATION_CONFLICT')
    exact = seconds(s.get('minutes')) / 60
    if exact > d['duration_minutes']:
        _fail('PLAYER_MINUTES_EXCEED_GAME_DURATION')
    for combo, keys in {'pr': ('points', 'rebounds'), 'pa': ('points', 'assists'),
                        'ra': ('rebounds', 'assists'), 'pra': ('points', 'rebounds', 'assists')}.items():
        if all(k in normalized for k in keys):
            normalized[combo] = sum(normalized[k] for k in keys)
    _stats(normalized)
    if any(k not in normalized or normalized[k] != v for k, v in data['stats'].items()):
        _fail('OFFICIAL_STAT_CONFLICT')
    displayed = data['minutes']
    if displayed > d['duration_minutes']:
        _fail('PLAYER_MINUTES_EXCEED_GAME_DURATION')
    if exact == 0 and any(normalized.values()):
        _fail('ZERO_MINUTE_CREDIT_UNRESOLVED')
    if displayed == 0 and any(normalized.values()):
        if not 0 < exact < Fraction(1, 2):
            _fail('ZERO_MINUTE_CREDIT_UNRESOLVED')
        status = 'ADJUDICATED_ROUNDED_SUBMINUTE'
    else:
        if abs(Fraction(str(displayed)) - exact) > Fraction(1, 2):
            _fail('OFFICIAL_MINUTE_CONFLICT')
        status = 'OFFICIAL_BOX_RECONCILED'
    return d, float(exact), status


def exposure_status(minutes, stats, bundle=None, data=None):
    if bundle is not None:
        return adjudicate_player(data, bundle)
    if minutes == 0 and any(stats.values()):
        _fail('ZERO_MINUTE_CREDIT_UNRESOLVED')
    if minutes > 48:
        _fail('GAME_DURATION_EVIDENCE_REQUIRED')
    # This is explicitly an unresolved research proxy, never verified exposure.
    return None, minutes, 'UNRESOLVED_OFFICIAL_DURATION_AND_SOURCE'


def prior_game_exposure(data, bundle):
    """P2/P3/P4 adapter output; consumers must enforce source admission policy.

    Retains displayed and exact minutes separately. A source-reconciled player
    is not independently authenticated simply because this adapter parsed it.
    Nonparticipation has null exact minutes; never train it as a played zero.
    """
    d, exact, status = adjudicate_player(data, bundle)
    return dict(**d, player_id=data['player_id'], team_id=data['team_id'],
                opponent_id=data['opponent_id'], participation=data['participation'],
                displayed_minutes=data['minutes'], exact_minutes=exact,
                accounting_status=status, stats=dict(data['stats']))
