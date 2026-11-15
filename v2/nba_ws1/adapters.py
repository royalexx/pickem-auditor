"""Adapters reuse the existing ESPN population parser; no collector or schedule.

All ESPN/NBA identifiers stay namespaced. Cross-provider mapping requires an
explicit source-backed time-valid crosswalk; names never create identities.
"""
from datetime import date
from zoneinfo import ZoneInfo
import math
from .store import Record, Receipt, instant, utc
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2] / "scripts"))
import population_normalizers as norm


def espn_id(kind,value):return 'espn:'+kind+':'+str(value)


def schedule_records(raw,receipt):
    result=[]
    for event in raw.get('events',[]):
        comps=event.get('competitions',[])
        if len(comps)!=1:raise ValueError('AMBIGUOUS_COMPETITION')
        comp=comps[0];teams=comp.get('competitors',[])
        home=[x for x in teams if x.get('homeAway')=='home'];away=[x for x in teams if x.get('homeAway')=='away']
        if len(home)!=1 or len(away)!=1:raise ValueError('AMBIGUOUS_TEAMS')
        state=event.get('status',{}).get('type',{})
        status={'STATUS_SCHEDULED':'scheduled','STATUS_POSTPONED':'postponed','STATUS_CANCELED':'cancelled','STATUS_FINAL':'final'}.get(state.get('name'),'live')
        result.append(Record.make('schedule',receipt,dict(game_id=espn_id('game',event['id']),
            home_team_id=espn_id('team',home[0]['team']['id']),away_team_id=espn_id('team',away[0]['team']['id']),
            event_start_at=utc(event['date']),venue=comp.get('venue',{}).get('fullName'),status=status)))
    return result


def legacy_population_records(rows,receipt,*,eligible_game_ids=()):
    """No original availability clocks survive in v1 rows: always proxy lineage.

    The receipt must cover the exact shard bytes read by the caller. ESPN team
    abbreviations are retained as a separate namespace, never equated to team IDs.
    A caller needs an explicit dated crosswalk to join these histories to ESPN IDs.
    """
    import population_history as population
    if receipt.origin!='retrospective_retrieval':raise ValueError('LEGACY_REQUIRES_PROXY_LABEL')
    groups={};rejections=[]
    franchise=set('ATL BOS BKN CHA CHI CLE DAL DEN DET GS HOU IND LAC LAL MEM MIA MIL MIN NO NY OKC ORL PHI PHX POR SAC SA TOR UTAH WSH'.split())
    for row in rows:
        population.validate(row)
        if row['sport']!='NBA':raise ValueError('NON_NBA_POPULATION')
        reason='NON_FRANCHISE_EXHIBITION' if row['team'] not in franchise or row['opponent'] not in franchise else 'GAME_SCOPE_UNVERIFIED' if row['game_id'] not in eligible_game_ids else None
        if reason:
            rejections.append(dict(game_id=row['game_id'],player_id=row['player_id'],stat=row['stat'],code=reason));continue
        key=(row['game_id'],row['player_id'])
        data=dict(game_id=espn_id('game',row['game_id']),player_id=espn_id('player',row['player_id']),
            team_id='espn_abbrev:team:'+row['team'],opponent_id='espn_abbrev:team:'+row['opponent'],
            game_date=row['game_date'],minutes=row['workload'],participation='played',starter=None,stats={})
        old=groups.setdefault(key,data)
        if any(old[k]!=data[k] for k in data if k!='stats'):raise ValueError('CROSS_STAT_IDENTITY_COLLISION')
        if row['stat'] in old['stats'] and old['stats'][row['stat']]!=row['value']:raise ValueError('CROSS_STAT_CONFLICT')
        old['stats'][row['stat']]=row['value']
    return [Record.make('player_game',receipt,d) for _,d in sorted(groups.items())],dict(attempted=len(rows),rejected_rows=len(rejections),rejections=rejections)


def espn_boxscore_records(raw,receipt):
    """Completed ESPN summaries, preserving DNP and observed zero minutes.

    Team profiles come from explicit team totals only; possessions/pace remain
    null because summing an incomplete player table is not a verified team total.
    """
    header=raw.get('header',{});comps=header.get('competitions',[])
    if len(comps)!=1:raise ValueError('AMBIGUOUS_COMPETITION')
    comp=comps[0];state=comp.get('status',{}).get('type',{})
    if state.get('completed') is not True or state.get('name')!='STATUS_FINAL':raise ValueError('BOX_NOT_FINAL')
    if instant(comp.get('date',header.get('date'))) >= instant(receipt.observed_at):raise ValueError('BOX_FUTURE_START')
    day=instant(comp.get('date',header.get('date'))).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
    gid=espn_id('game',comp['id']);teams={espn_id('team',c['team']['id']) for c in comp['competitors']}
    if len(teams)!=2:raise ValueError('TEAM_COLLISION')
    result=[];seen=set()
    for box in raw.get('boxscore',{}).get('players',[]):
        team=espn_id('team',box['team']['id'])
        if team not in teams:raise ValueError('BOX_TEAM_MISMATCH')
        opponent=next(iter(teams-{team}))
        for group in box.get('statistics',[]):
            labels=group.get('labels') or group.get('names') or []
            for p in group.get('athletes',[]):
                pid=espn_id('player',p['athlete']['id'])
                if pid in seen:raise ValueError('PLAYER_CROSSWALK_COLLISION')
                seen.add(pid);stats={};minutes=None
                values=dict(zip(labels,p.get('stats',[])))
                if p.get('didNotPlay') is True:participation='dnp'
                elif len(p.get('stats',[]))!=len(labels):participation='unknown'
                else:
                    raw_min=values.get('MIN',values.get('minutes'))
                    minutes=observed_minutes(raw_min)
                    participation='played' if minutes is not None else 'unknown'
                if participation=='played':
                    for stat,aliases in norm.NBA_LABELS.items():
                        for label in aliases:
                            v=norm.count(values.get(label))
                            if v is None and stat=='threes':v=norm.made_from_attempt_pair(values.get(label))
                            if v is not None:stats[stat]=v;break
                    for label,made,attempts in (('FG','fgm','fga'),('3PT','threes','fg3a'),('FT','ftm','fta')):
                        pair=values.get(label)
                        if isinstance(pair,str) and '-' in pair:
                            a,b=pair.split('-',1);a=norm.count(a);b=norm.count(b)
                            if a is not None and b is not None and a<=b:stats[made]=a;stats[attempts]=b
                    for label,key in (('OREB','oreb'),('DREB','dreb'),('PF','personal_fouls')):
                        v=norm.count(values.get(label))
                        if v is not None:stats[key]=v
                    for combo,parts in norm.NBA_COMBOS.items():
                        if all(k in stats for k in parts):stats[combo]=sum(stats[k] for k in parts)
                result.append(Record.make('player_game',receipt,dict(game_id=gid,player_id=pid,team_id=team,opponent_id=opponent,
                    game_date=day,minutes=minutes,participation=participation,starter=p.get('starter') if type(p.get('starter'))==bool else None,stats=stats)))
    if not result:raise ValueError('BOX_PLAYERS_MISSING')
    return result


def resolve_crosswalk(provider_id,kind,at,entries,receipts):
    """Require source-backed, nonoverlapping effective intervals and as-of capture."""
    lookup={r.receipt_id:r for r in receipts};candidates=[]
    for e in entries:
        if e['provider_id']!=provider_id or e['kind']!=kind:continue
        r=lookup.get(e['receipt_id'])
        if r is None or instant(r.source_available_at)>instant(at):continue
        if instant(e['valid_from'])<=instant(at) and (e['valid_to'] is None or instant(at)<instant(e['valid_to'])):candidates.append(e['canonical_id'])
    if len(candidates)!=1:raise ValueError('CROSSWALK_MISSING_OR_COLLISION')
    return candidates[0]


def espn_team_records(raw,receipt):
    """Team totals are observed counts; no possession/usage estimates are invented."""
    comp=raw['header']['competitions'][0]
    if comp.get('status',{}).get('type',{}).get('completed') is not True:raise ValueError('BOX_NOT_FINAL')
    day=instant(comp['date']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
    teams=raw.get('boxscore',{}).get('teams',[]);totals={}
    names={'fieldGoalsMade':'fgm','fieldGoalsAttempted':'fga','threePointFieldGoalsMade':'threes','threePointFieldGoalsAttempted':'fg3a',
           'freeThrowsMade':'ftm','freeThrowsAttempted':'fta','offensiveRebounds':'oreb','defensiveRebounds':'dreb','totalRebounds':'rebounds',
           'assists':'assists','steals':'steals','blocks':'blocks','turnovers':'turnovers','fouls':'personal_fouls','points':'points'}
    for team in teams:
        tid=espn_id('team',team['team']['id']);stats={}
        for item in team.get('statistics',[]):
            key=names.get(item.get('name'));value=norm.count(item.get('displayValue'))
            if key and value is not None:stats[key]=value
            for label,made,attempts in [('fieldGoalsMade-fieldGoalsAttempted','fgm','fga'),('threePointFieldGoalsMade-threePointFieldGoalsAttempted','threes','fg3a'),('freeThrowsMade-freeThrowsAttempted','ftm','fta')]:
                if item.get('name')==label:
                    pair=str(item.get('displayValue','')).split('-')
                    if len(pair)==2:
                        a,b=map(norm.count,pair)
                        if a is not None and b is not None and a<=b:stats[made]=a;stats[attempts]=b
        score=next((c.get('score') for c in comp['competitors'] if espn_id('team',c['team']['id'])==tid),None)
        value=norm.count(score)
        if value is not None:stats['points']=value
        totals[tid]=stats
    if len(totals)!=2:raise ValueError('TEAM_TOTALS_MISSING')
    return [Record.make('team_game',receipt,dict(game_id=espn_id('game',comp['id']),team_id=team,opponent_id=next(iter(set(totals)-{team})),
        game_date=day,possessions=None,pace_per_48=None,stats=stats,opponent_stats=totals[next(iter(set(totals)-{team}))])) for team,stats in sorted(totals.items())]


def espn_roster_records(raw,receipt,*,game_id,team_id):
    if espn_id('team',raw['team']['id'])!=team_id:raise ValueError('ROSTER_TEAM_MISMATCH')
    # Season-level membership is evidence, never a confirmed game-active list.
    return [Record.make('roster',receipt,dict(game_id=game_id,player_id=espn_id('player',p['id']),team_id=team_id,
        status='membership_only',uncertainty='reported')) for p in raw.get('athletes',[])]


def espn_injury_records(raw,receipt,*,game_id):
    result=[]
    for team in raw.get('injuries',[]):
        tid=espn_id('team',team['team']['id'])
        for item in team.get('injuries',[]):
            if item.get('date') and instant(item['date'])>instant(receipt.observed_at):raise ValueError('FUTURE_INJURY_REPORT')
            result.append(Record.make('availability',receipt,dict(game_id=game_id,player_id=espn_id('player',item['athlete']['id']),
                team_id=tid,status=item.get('status','unknown'),uncertainty='reported',role=None,
                detail=json_detail(item))))
    return result


def json_detail(item):
    # Preserve exact report details without projecting a minutes adjustment.
    from .store import canonical
    return canonical({'reported_at':item.get('date'),'details':item.get('details'),'type':item.get('type')})


def observed_minutes(value):
    # ESPN observed historical workload; long OT games must not be censored at 65.
    if isinstance(value,bool) or value is None:return None
    if isinstance(value,str) and ':' in value:
        parts=value.split(':')
        if len(parts)!=2 or not all(p.isdigit() for p in parts) or int(parts[1])>=60:return None
        value=int(parts[0])+int(parts[1])/60
    try:value=float(value)
    except (TypeError,ValueError):return None
    return value if math.isfinite(value) and 0<=value<=1000 else None
