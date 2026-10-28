"""Bounded box-score collection for complete, source-backed lineup histories.

Missing roster/stat coverage is a failure, never an inferred zero or absence.
Detailed tracking can be imported separately; counting box scores do not invent it.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import json
import math
import re
import urllib.request
from zoneinfo import ZoneInfo
from shared_context import history_path,import_history,validate_history
from usage_baseline import directory,local_day,source_stat
from pathlib import Path
from urllib.parse import urlparse
from odds_providers import normalize_team

ESPN={'NBA':'basketball/nba','NFL':'football/nfl'}
def team_code(value):return normalize_team(value) or str(value).upper()

def fetch_json(url):
    request=urllib.request.Request(url,headers={'User-Agent':'pickem-auditor/1','Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=12) as response:return json.load(response)

def number(value):
    if isinstance(value,bool):raise ValueError('invalid count')
    if isinstance(value,str) and '-' in value:return float(value.split('-')[0])
    result=float(value)
    if result<0 or not math.isfinite(result):raise ValueError('invalid count')
    return result

def label(value):return re.sub('[^a-z0-9]','',str(value).lower())

def active_roster_path():return directory().parent/'nfl_active_rosters.json'

def validate_active_rosters(data):
    """Game-specific GSIS rosters, never season roster membership or snap counts."""
    if data.get('version')!='nfl-active-rosters-v1':raise ValueError('unsupported roster manifest')
    seen=set()
    for row in data['games']:
        key=(row['event_id'],row['team'])
        if key in seen:raise ValueError('duplicate game/team roster')
        seen.add(key)
        if not isinstance(key[0],str) or not key[0].isdigit() or team_code(key[1])!=key[1]:
            raise ValueError('roster requires ESPN event ID and canonical team')
        local_day(row['date'])
        if row.get('game_id') is not None and not re.fullmatch(r'\d{4}_\d{2}_[A-Z0-9]{2,3}_[A-Z0-9]{2,3}',str(row['game_id'])):
            raise ValueError('invalid nflverse roster game ID')
        url=urlparse(row['source_url'])
        if url.scheme!='https' or not url.hostname or '.' not in url.hostname:raise ValueError('public roster source required')
        ids=row['active_players']
        if (row.get('roster_complete') is not True or not isinstance(ids,list) or not ids or
            any(not isinstance(i,str) or not re.fullmatch(r'00-\d{7}',i) for i in ids) or len(ids)!=len(set(ids))):
            raise ValueError('complete unique game-active GSIS roster required')
    return data

def import_active_rosters(data):
    validate_active_rosters(data)
    path=active_roster_path();path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)
    return path

def espn_game(payload,sport,team,stat,event_id,source_url,*,id_map=None,active_roster=None):
    if payload.get('header',{}).get('season',{}).get('type')!=2:raise ValueError('regular-season box score required')
    if not payload.get('header',{}).get('competitions',[{}])[0].get('status',{}).get('type',{}).get('completed'):
        raise ValueError('box score is not final')
    entry=next((p for p in payload.get('boxscore',{}).get('players',[]) if team_code(p.get('team',{}).get('abbreviation'))==team_code(team)),None)
    if not entry:raise ValueError('team box score missing')
    components={'pra':['points','rebounds','assists'],'pr':['points','rebounds'],
                'pa':['points','assists'],'ra':['rebounds','assists']}.get(stat,[stat])
    aliases={'points':['points','pts'],'rebounds':['rebounds','reb','totalrebounds'],
             'assists':['assists','ast'],'threes':['threepointfieldgoalsmadethreepointfieldgoalsattempted','threepointfieldgoalsmade','3pt'],
             'receptions':['receptions','rec'],'receiving yards':['receivingyards'],
             'passing yards':['passingyards'],'rushing yards':['rushingyards'],
             'rush attempts':['rushingattempts','carries'],'pass attempts':['passingattempts'],
             'completions':['completions'],'tackles':['solotackles'],
             'tackles + assists':['totaltackles','tot']}
    values={};active=set();feature={};totals=[]
    # NFL statistical tables alone omit zero-stat participants. A complete source
    # active roster and a stable provider->GSIS bridge are mandatory.
    if sport=='NFL':
        if active_roster is not None:
            validate_active_rosters({'version':'nfl-active-rosters-v1','games':[active_roster]})
            if (active_roster['event_id']!=str(event_id) or active_roster['team']!=team_code(team) or
                local_day(active_roster['date'])!=local_day(payload['header']['competitions'][0]['date'])):
                raise ValueError('game-active roster identity mismatch')
            active.update(active_roster['active_players'])
        roster=next((r for r in payload.get('rosters',[]) if team_code(r.get('team',{}).get('abbreviation'))==team_code(team)),None)
        if not id_map or (active_roster is None and not roster):raise ValueError('NFL requires complete active roster and ESPN/GSIS ID map')
        for person in (roster.get('roster',[]) if active_roster is None else []):
            if person.get('active') is False:continue
            if person.get('active') is not True:raise ValueError('NFL roster lacks explicit active/inactive flags')
            ident=id_map.get(str(person.get('athlete',{}).get('id')))
            if not ident:raise ValueError('unmapped NFL active player')
            active.add(ident)
    for table in entry.get('statistics',[]):
        names=[label(n) for n in table.get('keys',table.get('names',table.get('labels',[])))]
        indices=[]
        for component in components:
            index=next((i for i,n in enumerate(names) if n in aliases.get(component,[])),None)
            if index is None:break
            indices.append(index)
        if len(indices)!=len(components):continue
        if sport=='NFL':
            expected={'receptions':'receiving','receiving yards':'receiving','passing yards':'passing','completions':'passing',
                      'pass attempts':'passing','rushing yards':'rushing','rush attempts':'rushing',
                      'tackles':'defensive','tackles + assists':'defensive'}.get(stat)
            if label(table.get('name'))!=expected:continue
        for person in table.get('athletes',[]):
            dnp=person.get('didNotPlay') is True
            coach_dnp=dnp and label(person.get('reason'))=='coachsdecision'
            if dnp and not coach_dnp:continue
            raw=str(person.get('athlete',{}).get('id') or '')
            ident=id_map.get(raw) if sport=='NFL' else raw
            if not ident:raise ValueError('missing stable player ID')
            stats=person.get('stats',[])
            if coach_dnp:
                # Explicitly available, benched player: a known zero, not an
                # injured/absent roster member. ESPN 'active' is not participation.
                if sport=='NBA':
                    active.add(ident);values[ident]=0.
                    if stat=='threes':feature[ident]=0.
                continue
            if len(stats)!=len(names):raise ValueError('incomplete player statistic row')
            if ident in values:raise ValueError('duplicate statistical participant')
            values[ident]=sum(number(stats[i]) for i in indices)
            if sport=='NBA':active.add(ident)
            if sport=='NBA' and stat=='threes':
                raw_pair=stats[indices[0]]
                if isinstance(raw_pair,str) and '-' in raw_pair:
                    feature[ident]=number(raw_pair.split('-')[1])
        raw_totals=table.get('totals',[])
        if len(raw_totals)!=len(names):raise ValueError('team total unavailable')
        totals.append(sum(number(raw_totals[i]) for i in indices))
    if not values or len(totals)!=1:raise ValueError('unsupported or ambiguous statistic table')
    if sport=='NFL':
        if set(values)-active:raise ValueError('statistical player absent from active roster')
        values={p:values.get(p,0.) for p in active}
    date=payload['header']['competitions'][0]['date']
    result=dict(id=str(event_id),date=date,source_url=source_url,roster_complete=True,
                active_players=sorted(active),production=values,team_total=totals[0])
    if active_roster is not None:result['roster_source_url']=active_roster['source_url']
    if active_roster is not None and active_roster.get('game_id'):
        result['id']=active_roster['game_id'];result['source_event_id']=str(event_id)
    if feature and set(feature)==active:result['features']={'three_point_attempts':feature}
    validate_history(dict(sport=sport,team=team,stat=stat,games=[result]))
    return result

def nhl_game(payload,team,stat,event_id,source_url):
    if payload.get('gameType')!=2:raise ValueError('regular-season NHL game required')
    if payload.get('gameState') not in ('OFF','FINAL'):raise ValueError('NHL game is not final')
    side=next((s for s in ('homeTeam','awayTeam') if payload.get(s,{}).get('abbrev')==team),None)
    if not side:raise ValueError('NHL team identity mismatch')
    group=payload.get('playerByGameStats',{}).get(side,{})
    if not all(k in group for k in ('forwards','defense','goalies')):raise ValueError('incomplete NHL active roster')
    values={};ice={}
    for position,players in group.items():
        if position not in ('forwards','defense','goalies'):continue
        for player in players:
            ident=str(player['playerId'])
            if ident in values:raise ValueError('duplicate NHL participant')
            if stat in ('saves','goalie saves'):
                value=number(player['saves']) if position=='goalies' else 0.
            elif stat in ('shots on goal','blocked shots','hits'):
                field={'shots on goal':'sog','blocked shots':'blockedShots','hits':'hits'}[stat]
                value=number(player[field]) if position!='goalies' else 0.
            else:raise ValueError('unsupported NHL stat')
            values[ident]=value
            if player.get('toi'):
                minutes,seconds=player['toi'].split(':');ice[ident]=int(minutes)+int(seconds)/60
    if stat=='shots on goal':total=number(payload[side]['sog'])
    elif stat in ('saves','goalie saves'):total=sum(values.values())
    else:total=sum(values.values())
    result=dict(id=str(event_id),date=payload['gameDate'],source_url=source_url,roster_complete=True,
                active_players=sorted(values),production=values,team_total=total,features={'ice_time':ice})
    validate_history(dict(sport='NHL',team=team,stat=stat,games=[result]))
    return result

def collect(sport,team,stat,as_of,*,fetch=fetch_json,lookback_days=180,max_games=60,id_map=None,active_rosters=None,persist=True):
    team=team_code(team)
    day=datetime.fromisoformat(as_of).date();first=day-timedelta(days=lookback_days)
    if not 1<=lookback_days<=730 or not 1<=max_games<=100:raise ValueError('collection limits outside supported bounds')
    if sport=='NFL' and id_map is None:
        try:
            import nflreadpy
            rows=nflreadpy.load_players().to_dicts()
            id_map={}
            for r in rows:
                try:
                    if r.get('espn_id') and r.get('gsis_id'):
                        id_map[str(int(float(r['espn_id'])))]=str(r['gsis_id'])
                except (ValueError,TypeError,OverflowError):continue
        except Exception as exc:raise ValueError('NFL provider ID bridge unavailable: '+str(exc)) from exc
    if sport=='NHL':
        start=first.year if first.month>=9 else first.year-1
        end=day.year if day.month>=9 else day.year-1
        events=[]
        for season in range(start,end+1):
            url=f'https://api-web.nhle.com/v1/club-schedule-season/{team}/{season}{season+1}'
            events.extend((str(g['id']),g['gameDate']) for g in fetch(url).get('games',[]) if g.get('gameState') in ('OFF','FINAL') and g.get('gameType')==2)
    else:
        path=ESPN[sport]
        catalog=fetch(f'https://site.api.espn.com/apis/site/v2/sports/{path}/teams?limit=1000')
        teams=[t['team'] for s in catalog.get('sports',[]) for league in s.get('leagues',[]) for t in league.get('teams',[])]
        selected=[t for t in teams if team_code(t.get('abbreviation'))==team]
        if len(selected)!=1:raise ValueError('team catalog identity is ambiguous or missing')
        def season_for(value):return value.year+(value.month>=9) if sport=='NBA' else value.year-(value.month<8)
        events=[];sources=[]
        for year in range(season_for(first),season_for(day)+1):
            url=f'https://site.api.espn.com/apis/site/v2/sports/{path}/teams/{selected[0]["id"]}/schedule?season={year}&seasontype=2'
            sources.append(url)
            for game in fetch(url).get('events',[]):
                competition=game.get('competitions',[{}])[0]
                if not competition.get('status',game.get('status',{})).get('type',{}).get('completed'):continue
                if not any(team_code(c.get('team',{}).get('abbreviation'))==team for c in competition.get('competitors',[])):continue
                events.append((str(game['id']),game['date']))
        url=sources[-1]
    rosters={}
    if sport=='NFL':
        if active_rosters is None and active_roster_path().exists():active_rosters=json.loads(active_roster_path().read_text())
        if active_rosters is not None:
            validate_active_rosters(active_rosters)
            rosters={(r['event_id'],r['team']):r for r in active_rosters['games']}
    eligible=sorted({i:d for i,d in events if first<=local_day(d)<day}.items(),key=lambda x:x[1])[-max_games:]
    existing={}
    try:
        cached=json.loads(history_path(sport,team,stat).read_text())
        validate_history(cached)
        if cached.get('sport')==sport and cached.get('team')==team and source_stat(cached.get('stat'))==source_stat(stat):
            existing={g.get('source_event_id',g['id']):g for g in cached['games'] if local_day(g['date'])<day-timedelta(days=7)
                      and g.get('collector_version')=='lineup-feeds-v2'}
    except (OSError,ValueError,KeyError,TypeError):pass
    def one(item):
        ident,date=item
        cached_game=existing.get(ident)
        manifest=rosters.get((ident,team))
        manifest_matches=not manifest or (cached_game is not None and
            cached_game['id']==manifest.get('game_id',ident) and
            set(cached_game['active_players'])==set(manifest['active_players']) and
            cached_game.get('roster_source_url')==manifest['source_url'])
        if cached_game and manifest_matches and local_day(cached_game['date'])==local_day(date):return cached_game,None
        link=(f'https://api-web.nhle.com/v1/gamecenter/{ident}/boxscore' if sport=='NHL' else
              f'https://site.api.espn.com/apis/site/v2/sports/{ESPN[sport]}/summary?event={ident}')
        try:
            payload=fetch(link)
            row=nhl_game(payload,team,stat,ident,link) if sport=='NHL' else espn_game(payload,sport,team,stat,ident,link,id_map=id_map,active_roster=rosters.get((ident,team)))
            if local_day(row['date'])!=local_day(date):raise ValueError('box-score date mismatch')
            row['collector_version']='lineup-feeds-v2'
            return row,None
        except (ValueError,KeyError,TypeError,OSError) as exc:return None,dict(game_id=ident,error=str(exc),source_url=link)
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,eligible))
    games=[g for g,e in results if g];errors=[e for g,e in results if e]
    data=dict(sport=sport,team=team,stat=stat,games=games,retrieved_at=datetime.now(timezone.utc).isoformat(),
              collection=dict(discovered=len(eligible),completed=len(games),errors=errors,source_url=url))
    if not eligible:raise ValueError('no completed games discovered')
    if errors:raise ValueError('incomplete lineup collection: '+json.dumps(errors))
    if persist:
        import_history(data)
    return data

def prepare(rows,*,fetch=fetch_json):
    """One collection per team/stat, only when a merged candidate needs context."""
    results={}
    for row in rows:
        if not (row.get('event_context') or {}).get('events'):continue
        sport=str(row.get('id','')).split('|')[0]
        team=row.get('team');stat=row.get('stat');day=row.get('game_date')
        scope=(sport,team,stat,day)
        if scope in results:continue
        try:
            if not team or not day:raise ValueError('lineup collection requires team and game date')
            data=collect(sport,team,stat,day,fetch=fetch)
            results[scope]={'ok':True,**data['collection']}
        except (ValueError,KeyError,TypeError,OSError,ImportError) as exc:
            results[scope]={'ok':False,'error':str(exc)}
    return {'|'.join(str(v) for v in k):v for k,v in results.items()}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sport',choices=['NBA','NHL','NFL'],required=True);parser.add_argument('--team',required=True)
    parser.add_argument('--stat',required=True);parser.add_argument('--date',default=datetime.now(ZoneInfo('America/Toronto')).date().isoformat())
    parser.add_argument('--lookback-days',type=int,default=180);parser.add_argument('--max-games',type=int,default=60)
    parser.add_argument('--id-map',help='Source-verified ESPN ID to GSIS ID JSON map for NFL')
    parser.add_argument('--active-rosters',help='Verified game-active GSIS roster manifest; imported for automatic context collection')
    args=parser.parse_args()
    if args.active_rosters:import_active_rosters(json.loads(Path(args.active_rosters).read_text()))
    data=collect(args.sport,args.team,args.stat,args.date,lookback_days=args.lookback_days,max_games=args.max_games,
                 id_map=json.load(open(args.id_map)) if args.id_map else None)
    print(json.dumps(data['collection'],indent=2))
