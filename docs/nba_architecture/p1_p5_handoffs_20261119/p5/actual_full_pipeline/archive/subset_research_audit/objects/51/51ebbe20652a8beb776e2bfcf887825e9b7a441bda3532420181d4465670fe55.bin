"""Game-specific dual-source identity joins; never forward roster/trade evidence."""
import hashlib
import json
import re
import unicodedata
from zoneinfo import ZoneInfo
from datetime import datetime
from .v2_contracts import req,instant


def name_key(value):
    value=unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().lower()
    words=re.findall('[a-z]+',value)
    if words and words[-1] in ('sr','jr'):words.pop()
    return ''.join(words)


def join_game_ids(gamebook,espn_raw,espn_receipt):
    req(hashlib.sha256(espn_raw).hexdigest()==espn_receipt['raw_sha256'],'GAMEBOOK_ID_SOURCE_HASH')
    source=json.loads(espn_raw)
    event=str(source['header']['id'])
    req(espn_receipt['url']=='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event='+event and
        espn_receipt['status']==200,'GAMEBOOK_ID_SOURCE_URL')
    event_time=source['header']['competitions'][0]['date']
    req(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z',event_time) is not None,'GAMEBOOK_ID_EVENT_TIME')
    # Only the local calendar date is joined; minute precision is preserved
    # as source evidence and never used as an availability/release timestamp.
    day=datetime.fromisoformat(event_time.replace('Z','+00:00')).astimezone(ZoneInfo('America/Toronto')).strftime('%Y%m%d')
    req(day==gamebook['game_date'],'GAMEBOOK_ID_DATE')
    indexed={};result=[]
    for team in source['boxscore']['players']:
        abbr=team['team']['abbreviation'];team_id=str(team['team']['id']);stat=team['statistics'][0]
        for person in stat['athletes']:
            athlete=person['athlete'];key=(abbr,str(athlete['jersey']))
            req(key not in indexed,'GAMEBOOK_ID_DUPLICATE_SOURCE')
            indexed[key]=(team_id,athlete,person,stat['labels'])
    expected={(r['team'],r['jersey']) for r in gamebook['rows']}
    req(set(indexed)==expected,'GAMEBOOK_ID_COMPLETE_LISTED_POPULATION')
    for row in gamebook['rows']:
        team_id,athlete,person,labels=indexed[row['team'],row['jersey']]
        req(name_key(row['name'])==name_key(athlete['displayName']),'GAMEBOOK_ID_NAME')
        req((row['state']=='DNP')==(person['didNotPlay'] is True),'GAMEBOOK_ID_DNP')
        if row['state']!='DNP':
            values=dict(zip(labels,person['stats']));s=row['stats']
            for old,new in {'PTS':'points','REB':'rebounds','AST':'assists','TO':'turnovers','STL':'steals','BLK':'blocks','OREB':'oreb','DREB':'dreb','PF':'personal_fouls','+/-':'plus_minus'}.items():
                req(int(values[old])==s[new],'GAMEBOOK_ID_STAT_JOIN')
            for key,made,attempted in (('FG','fgm','fga'),('3PT','threes','fg3a'),('FT','ftm','fta')):
                req(tuple(map(int,values[key].split('-')))==(s[made],s[attempted]),'GAMEBOOK_ID_MAKES_ATTEMPTS')
        result.append(dict(game_id='espn:game:'+event,game_date=day,player_id='espn:player:'+str(athlete['id']),
            team_id='espn:team:'+team_id,source_name=row['name'],jersey=row['jersey'],
            official_pdf_raw_sha256=gamebook['source_raw_sha256'],espn_raw_sha256=espn_receipt['raw_sha256']))
    req(len({r['player_id'] for r in result})==len(result),'GAMEBOOK_ID_PLAYER_COLLISION')
    return dict(schema='nba-gamebook-dual-source-identity/1.0.0',rows=result,
        identity_scope='THIS_COMPLETED_GAME_ONLY',source_event_time=event_time,future_roster_or_trade_evidence=False,
        original_pregame_availability_proven=False,admission='INDEPENDENT_REVIEW_REQUIRED')
