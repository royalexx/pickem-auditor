"""Bounded structured-source research; no inferred availability or narrative uplifts."""
from copy import deepcopy
from datetime import datetime, timezone
from odds_providers import normalize_team
from context_feeds import confirmed_fact, _parse_iso, merge_packet_no_clobber

PATHS = {'NBA':'basketball/nba','NFL':'football/nfl','NHL':'hockey/nhl'}

def team_code(value, sport):
    code=normalize_team(value)
    if sport=='NHL':code={'LA':'LAK','TB':'TBL','WAS':'WSH','MON':'MTL'}.get(code,code)
    return code


def resolve(packet, candidate_ids, fetch, *, now=None):
    now=now or datetime.now(timezone.utc)
    stamp=now.isoformat(); result=deepcopy(packet); attempts=[]; events={}; started=[]
    index=packet.get('index',{}).get('by_player',{})
    players={i.split('|')[1] for i in candidate_ids if len(i.split('|'))==4}
    sports={index[p].get('sport') for p in players if p in index and index[p].get('sport') in PATHS}
    update={'date':packet['date'],'availability':{},'weather':{}}
    goalie_update={'date':packet['date'],'availability':{},'player_context':{}}
    goalie_candidates={i.split('|')[1] for i in candidate_ids if len(i.split('|'))==4 and i.split('|')[0]=='NHL' and i.split('|')[2] in ('saves','goalie saves')}
    goalie_observations=[]
    for sport in sorted(sports):
        if sport not in PATHS:continue
        url=f"https://site.api.espn.com/apis/site/v2/sports/{PATHS[sport]}/scoreboard?dates={packet['date'].replace('-','')}"
        attempt={'source_url':url,'retrieved_at':stamp,'purpose':'fixture venue and event identity'}
        try:
            payload=fetch(url,timeout=15)
            count=0
            for event in payload.get('events',[]):
                start=_parse_iso(event.get('date',''))
                if start is None:continue
                from zoneinfo import ZoneInfo
                if start.astimezone(ZoneInfo('America/Toronto')).date().isoformat()!=packet['date']:continue
                for comp in event.get('competitions',[]):
                    competitors=comp.get('competitors',[])
                    teams={team_code(c.get('team',{}).get('abbreviation',''),sport) for c in competitors}
                    teams.discard(None)
                    if len(teams)!=2:continue
                    matching={index[p]['game'] for p in players if p in index and index[p].get('sport')==sport
                              and set(index[p].get('game','').split('@'))==teams}
                    for game in matching:
                        events[game]=(sport,event,comp,start)
                        indoor=comp.get('venue',{}).get('indoor')
                        if isinstance(indoor,bool):
                            update['weather'][game]={'indoor':confirmed_fact('actual scheduled venue indoor',indoor,url,stamp)}
                            count+=1
                        if start<=now or event.get('status',{}).get('type',{}).get('state')!='pre':started.append(game)
                        elif sport=='NHL':
                            for competitor in competitors:
                                team=team_code(competitor.get('team',{}).get('abbreviation',''),sport)
                                confirmed=[p for p in competitor.get('probables',[]) if
                                           p.get('name')=='probableStartingGoalie' and
                                           (p.get('status') or {}).get('type')=='confirmed']
                                # Conflicting starters are not resolved by array order.
                                if len(confirmed)!=1:continue
                                probable=confirmed[0]
                                name=(probable.get('athlete') or {}).get('displayName')
                                goalie_observations.append({'player':name,'team':team,'game':game,
                                    'status':'confirmed','source_url':url,'observed_at':stamp,
                                    'espn_player_id':(probable.get('athlete') or {}).get('id')})
                                if name not in goalie_candidates or index.get(name,{}).get('team')!=team or index[name].get('game')!=game:
                                    continue
                                status=confirmed_fact('ESPN explicit confirmed starting goalie','active',url,stamp)
                                status.update(report_type='game_day_report',observed_at=stamp,
                                              source_field='competitions.competitors.probables.status.type',
                                              espn_player_id=(probable.get('athlete') or {}).get('id'))
                                goalie_update['availability'][name]={'status':status,
                                    'primary_source':confirmed_fact('source classification','beat',url,stamp,source_name='ESPN')}
                                goalie_update['player_context'][name]={'goalie_confirmed':{
                                    **status,'fact':'named starting goalie confirmed','value':True}}
            attempt.update(status='retrieved',resolved_venues=count)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            attempt.update(status='source_failed',error=type(exc).__name__)
        attempts.append(attempt)
    # Game-specific explicit roster flags only. Never use generic roster status,
    # an injury-list omission, statistical participation, or projected lines.
    for game,(sport,event,comp,start) in events.items():
        if game in started:continue
        url=f"https://site.api.espn.com/apis/site/v2/sports/{PATHS[sport]}/summary?event={event['id']}"
        attempt={'source_url':url,'retrieved_at':stamp,'purpose':'explicit game-active roster'}
        try:
            payload=fetch(url,timeout=15)
            header=payload.get('header',{})
            if str(header.get('id'))!=str(event['id']):raise ValueError('summary identity mismatch')
            competitions=header.get('competitions',[])
            if not competitions or competitions[0].get('status',{}).get('type',{}).get('state')!='pre':
                raise ValueError('summary is not pregame')
            resolved=0
            for roster in payload.get('rosters',[]):
                team=team_code(roster.get('team',{}).get('abbreviation',''),sport)
                for person in roster.get('roster',[]):
                    name=person.get('athlete',{}).get('displayName')
                    if name not in players or index.get(name,{}).get('team')!=team or index[name].get('game')!=game:continue
                    if not isinstance(person.get('active'),bool):continue
                    # False means inactive for this game, not medically injured.
                    value='active' if person['active'] else 'out'
                    status=confirmed_fact('explicit game-active roster flag',value,url,stamp)
                    status.update(report_type='final_active_roster',observed_at=stamp)
                    update['availability'][name]={'status':status,'primary_source':confirmed_fact('primary_source','league',url,stamp)}
                    resolved+=1
            attempt.update(status='retrieved',resolved_players=resolved)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            attempt.update(status='source_failed',error=type(exc).__name__)
        attempts.append(attempt)
    for conflict in result.get('_source_conflicts', []):
        if conflict.get('resolution')=='unresolved' and conflict.get('player') in update['availability']:
            conflict['resolution']='explicit_game_active_roster'
            conflict['resolution_fact']=update['availability'][conflict['player']]['status']
    result={**result, **merge_packet_no_clobber(result,update)}
    # A freshly observed explicit game roster resolves older report ambiguity.
    # Keep the competing observations in the ledger instead of discarding them.
    for player, entry in update['availability'].items():
        result['availability'][player]=entry
        for conflict in result.get('_source_conflicts', []):
            if conflict.get('player')==player and conflict.get('field')=='status':
                conflict['resolution']='explicit_game_active_roster'
                conflict['resolution_fact']=entry['status']
    # Goalies are reported starters, not final active-roster flags. Preserve
    # unresolved conflicts instead of overwriting a contradictory Out report.
    for player, facts in goalie_update['player_context'].items():
        goalie_update['player_context'][player]={**result.get('player_context',{}).get(player,{}),**facts}
    result={**result, **merge_packet_no_clobber(result,goalie_update)}
    # ESPN NHL injury reports contain explicit negative designations, but
    # absence from the feed NEVER establishes active status. Prefer actual
    # pregame active-roster flags above an injury-feed entry, and keep source
    # conflicts unresolved instead of arbitrarily resolving them.
    nhl_games={g for g,(sport,_,_,_) in events.items()
               if sport=='NHL' and g not in started}
    if nhl_games:
        injury_url='https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries'
        attempt={'source_url':injury_url,'retrieved_at':stamp,
                 'purpose':'explicit NHL injury designations; no active inference'}
        injury_update={'date':packet['date'],'availability':{}}
        try:
            feed=fetch(injury_url,timeout=15)
            if not isinstance(feed,dict):raise ValueError('invalid injuries payload')
            observed=0
            for block in feed.get('injuries') or []:
                if not isinstance(block,dict):continue
                team=team_code((block.get('team') or {}).get('abbreviation',''),'NHL')
                for record in block.get('injuries') or []:
                    if not isinstance(record,dict):continue
                    name=((record.get('athlete') or {}).get('displayName') or '')
                    meta=index.get(name) or {}
                    if name not in players or meta.get('sport')!='NHL' or meta.get('team')!=team or meta.get('game') not in nhl_games:
                        continue
                    raw_status=record.get('status')
                    raw_status=(raw_status.get('name') or raw_status.get('type') or '') if isinstance(raw_status,dict) else raw_status
                    text_status=str(raw_status or '').strip().lower()
                    status={'out':'out','doubtful':'doubtful',
                            'questionable':'questionable','injured reserve':'out',
                            'long-term injured reserve':'out'}.get(text_status)
                    if status is None:continue
                    fact=confirmed_fact('ESPN explicit injury designation',status,injury_url,stamp,
                                        quote=str(raw_status),source_name='ESPN NHL injuries')
                    fact['report_type']='injury_feed'
                    previous=(result.get('availability',{}).get(name) or {}).get('status')
                    if isinstance(previous,dict):
                        if previous.get('value') != status:
                            # Preserve contradictory source observations, not
                            # just whichever status happens to be retrieved first.
                            conflicts=result.setdefault('_source_conflicts',[])
                            if not any(c.get('player')==name and c.get('field')=='status'
                                       and c.get('resolution')=='unresolved'
                                       and (c.get('challenger') or {}).get('value')==status
                                       for c in conflicts):
                                conflicts.append({'player':name,'field':'status',
                                                  'resolution':'unresolved',
                                                  'previous':previous,'challenger':fact})
                        continue
                    injury_update['availability'][name]={'status':fact,
                        'primary_source':confirmed_fact('source classification','league',injury_url,stamp)}
                    observed+=1
            if observed:
                result=merge_packet_no_clobber(result,injury_update)
            attempt.update(status='retrieved',resolved_negative_statuses=observed)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            attempt.update(status='source_failed',error=type(exc).__name__)
        attempts.append(attempt)
    result['_research_attempts']=list(packet.get('_research_attempts') or [])+attempts
    return result,{'attempts':attempts,'started_games':sorted(set(started)),
                   'verified_pregame_games':sorted(set(events)-set(started)),
                   'unmatched_games':sorted({index[p]['game'] for p in players if p in index and index[p].get('game')}-set(events)),
                   'resolved_statuses':sorted(set(update['availability']) | {p for p in goalie_update['availability'] if (result.get('availability',{}).get(p,{}).get('status') or {}).get('value')=='active'}),
                   'goalie_observations':goalie_observations,
                   'resolved_goalies':sorted(p for p in goalie_update['player_context'] if (result.get('availability',{}).get(p,{}).get('status') or {}).get('value')=='active'),
                   'resolved_venues':sorted(update['weather'])}
