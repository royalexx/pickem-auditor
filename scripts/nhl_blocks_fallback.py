"""Optional independently priced NHL blocked-shot source. Never fills hits.

The Odds API event-odds endpoint publishes player_blocked_shots and charges
for returned markets/regions. Always query only a bounded set of future NHL
games, and never persist an authenticated request URL or credential.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
from urllib.parse import urlencode
from odds_providers import (event_on_date, parse_time, quotes_from_event,
                            dedupe_quotes)
ROOT='https://api.the-odds-api.com/v4/sports/icehockey_nhl'
MAX_EVENT_REQUESTS=8
SAFE_SOURCE=ROOT+'/events/{id}/odds?markets=player_blocked_shots'

def fetch_nhl_blocked_shots(game_date, primary_quotes, *, fetch, api_key,
                            enabled=False, now=None, max_events=MAX_EVENT_REQUESTS):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('aware clock required')
    diag={'schema':'nhl-blocked-shots-fallback-v1','status':'disabled',
          'source':'the-odds-api-v4','market':'player_blocked_shots',
          'event_requests':0,'returned_quotes':0,'event_limit':MAX_EVENT_REQUESTS,
          'notes':[]}
    if not enabled:
        return [],diag
    if any(q.get('sport')=='NHL' and q.get('stat')=='blocked shots'
           for q in primary_quotes or [] if isinstance(q,dict)):
        diag['status']='primary_market_present'
        return [],diag
    if not str(api_key or '').strip():
        diag['status']='missing_api_key'
        return [],diag
    if not 1<=max_events<=MAX_EVENT_REQUESTS:
        raise ValueError('invalid max-events budget')
    diag['event_limit']=max_events
    # The no-odds events listing is quota-free; only chargeable event props
    # consume the bounded daily budget. Never log authenticated URLs.
    try:
        events=fetch(ROOT+'/events?'+urlencode({'apiKey':api_key}),timeout=20)
    except Exception as exc:
        diag['status']='events_source_failed'
        diag['notes']=[type(exc).__name__]
        return [],diag
    if not isinstance(events,list):
        diag['status']='invalid_events_schema'
        return [],diag
    upcoming=[]
    for event in events:
        if not isinstance(event,dict) or not event.get('id'):
            continue
        start=parse_time(event.get('commence_time'))
        if (start is None or start<=now or not event_on_date(event.get('commence_time'),game_date)
                or not event.get('home_team') or not event.get('away_team')):
            continue
        upcoming.append(event)
    upcoming.sort(key=lambda e:(e.get('commence_time') or '',str(e['id'])))
    diag['eligible_events']=len(upcoming)
    diag['skipped_event_budget']=max(0,len(upcoming)-max_events)
    diag['status']='completed'
    quotes=[]
    for event in upcoming[:max_events]:
        url=ROOT+'/events/'+str(event['id'])+'/odds?'+urlencode(
            {'apiKey':api_key,'regions':'us','markets':'player_blocked_shots',
             'oddsFormat':'american'})
        diag['event_requests']+=1
        try:
            payload=fetch(url,timeout=20)
            if not isinstance(payload,dict):
                raise ValueError('expected event odds object')
            if str(payload.get('id'))!=str(event['id']):
                raise ValueError('event id mismatch')
            if (payload.get('home_team')!=event['home_team'] or
                    payload.get('away_team')!=event['away_team'] or
                    not event_on_date(payload.get('commence_time'),game_date)):
                raise ValueError('event fixture mismatch')
            safe_url=SAFE_SOURCE.format(id=str(event['id']))
            found=quotes_from_event(payload,sport='NHL',
                 retrieved_at=now.isoformat(),source_url=safe_url)
            for quote in found:
                quote['event_id_namespace']='the_odds_api'
                quote['source_provider']='the_odds_api'
            quotes.extend(q for q in found if q['stat']=='blocked shots')
        except Exception as exc:
            # Record error category only: exceptions may embed the API key.
            diag['notes'].append(type(exc).__name__)
    result=dedupe_quotes(quotes)
    diag['returned_quotes']=len(result)
    if diag['skipped_event_budget']:
        diag['status']='partial_budget_cap'
    if not result and not diag['notes']:
        diag['status']='no_two_sided_blocked_shot_quotes'
    return result,diag
