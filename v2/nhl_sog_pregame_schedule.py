"""Official pregame identity only. Never consumes score or player outcome fields."""
from datetime import date


def official_games(url, doc, day):
    date.fromisoformat(day)
    base = 'https://api-web.nhle.com/v1/'
    if url == base + 'score/' + day:
        games = doc.get('games')
    elif url == base + 'schedule/' + day:
        weeks = doc.get('gameWeek')
        if not isinstance(weeks, list):
            raise ValueError('OFFICIAL_SCHEDULE_DAYS_MISSING')
        days = [d for d in weeks if d.get('date') == day]
        if len(days) != 1:
            raise ValueError('OFFICIAL_SCHEDULE_DAY_NOT_UNIQUE')
        games = days[0].get('games')
    else:
        raise ValueError('OFFICIAL_PREGAME_ENDPOINT_INVALID')
    if not isinstance(games, list):
        raise ValueError('OFFICIAL_GAMES_MISSING')
    ids = [str(g.get('id')) for g in games]
    if any(not x.isdigit() for x in ids) or len(ids) != len(set(ids)):
        raise ValueError('OFFICIAL_GAME_ID_INVALID_OR_DUPLICATED')
    return games


def capture_identity(day, capture, saved, failure):
    """Only caller's live signed transport or previously verified receipt is used."""
    for kind in ('score', 'schedule'):
        url = 'https://api-web.nhle.com/v1/' + kind + '/' + day
        try:
            rec, doc = capture(url, kind, day)
        except Exception as exc:
            failure('LIVE_' + kind.upper() + '_FETCH', exc)
            continue
        # A response with bad semantics fails closed, rather than masking corruption.
        official_games(rec['source_url'], doc, day)
        return rec, doc
    rec, doc = saved('score')
    official_games(rec['source_url'], doc, day)
    return rec, doc
