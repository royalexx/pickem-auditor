"""Frozen prospective source population -> exact-second S training inputs.

No fitting or source admission occurs in this reader. Admission requires the
separate independent pre-fit decision over this code and frozen source profile.
NBA/ESPN identity corroboration is per completed game, not a legal roster root.
"""
from collections import Counter,defaultdict
from datetime import timedelta
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from .p1_subset_handoff_v1 import canonical,digest
from .subset_contract_v1 import strict_json
from .gamebook_identity_v1 import name_key
from .subset_p3_v1 import require
from v2.nba_opportunity import utc

VERSION='nba-prospective-exact-S-sources/1.0.0'
SPEC_SHA='9b4ffaf085deeffe83cee50c6d3ecfc5dd2c41848cb849ee32240389cc7b2ed8'
RULE_SHA='ead50b6b76dc319a6c0a390d3dd3add2d25b2330b8314bc7a3e2e4c17add5eed'
STAT_KEYS={'points':'points','rebounds':'reboundsTotal','assists':'assists','threes':'threePointersMade'}
FIELDS=('points','fieldGoalsMade','fieldGoalsAttempted','threePointersMade','threePointersAttempted',
    'freeThrowsMade','freeThrowsAttempted','reboundsOffensive','reboundsDefensive','reboundsTotal',
    'assists','steals','blocks','turnovers','foulsPersonal','plusMinusPoints')
POSITIONS={'PG':'G','SG':'G','G':'G','SF':'F','PF':'F','F':'F','C':'C'}


class _NextData(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=False);self.open=False;self.buffers=[];self.data=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('id')=='__NEXT_DATA__':self.open=True;self.buffers=[]
    def handle_data(self,data):
        if self.open:self.buffers.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self.open:self.data.append(''.join(self.buffers));self.open=False


def next_data(raw):
    parser=_NextData();parser.feed(raw.decode('utf-8'))
    require(len(parser.data)==1 and not parser.open,'OFFICIAL_NEXT_DATA_POPULATION')
    value=strict_json(parser.data[0]);return value['props']['pageProps']


def seconds(text):
    require(isinstance(text,str) and re.fullmatch(r'\d+:\d{2}',text) is not None,'SOURCE_MMSS_REQUIRED')
    minute,second=map(int,text.split(':'));require(second<60,'SOURCE_SECOND_RANGE')
    return minute*60+second


def _integer(value,reason,signed=False):
    require(type(value) is int and (signed or value>=0),reason);return value


def official_vector(stats):
    require(isinstance(stats,dict),'OFFICIAL_STAT_SCHEMA')
    result={key:_integer(stats[key],'OFFICIAL_INTEGER_COUNT:'+key,key=='plusMinusPoints') for key in FIELDS}
    a=result
    require(a['points']==2*a['fieldGoalsMade']+a['threePointersMade']+a['freeThrowsMade'],'OFFICIAL_POINT_ACCOUNTING')
    require(a['reboundsTotal']==a['reboundsOffensive']+a['reboundsDefensive'],'OFFICIAL_REBOUND_ACCOUNTING')
    require(a['threePointersMade']<=a['threePointersAttempted']<=a['fieldGoalsAttempted']
        and a['threePointersMade']<=a['fieldGoalsMade']<=a['fieldGoalsAttempted']
        and a['freeThrowsMade']<=a['freeThrowsAttempted'],'OFFICIAL_SHOT_ACCOUNTING')
    return result


def espn_vector(row,names):
    require(type(row.get('didNotPlay')) is bool,'ESPN_PARTICIPATION_FIELD')
    if row['didNotPlay']:return None
    values=row['stats'];require(len(values)==len(names) and len(set(names))==len(names),'ESPN_STAT_COLUMNS')
    v=dict(zip(names,values))
    def integer(key,signed=False):
        text=v[key];require(isinstance(text,str) and re.fullmatch(r'[+-]?\d+' if signed else r'\d+',text),'ESPN_INTEGER_COUNT:'+key)
        return _integer(int(text),'ESPN_INTEGER_COUNT:'+key,signed)
    def pair(key):
        require(re.fullmatch(r'\d+-\d+',v[key]) is not None,'ESPN_SHOT_PAIR:'+key)
        return tuple(map(int,v[key].split('-')))
    fg,fga=pair('FG');threes,tpa=pair('3PT');ft,fta=pair('FT')
    result=dict(zip(FIELDS,[integer('PTS'),fg,fga,threes,tpa,ft,fta,integer('OREB'),integer('DREB'),integer('REB'),integer('AST'),integer('STL'),integer('BLK'),integer('TO'),integer('PF'),integer('+/-',True)]))
    official_vector(result)
    return result


def parse_completed_game(official_raw,espn_raw,index_raw,join):
    """Structural capability check only; frozen-byte verification is separate."""
    game=next_data(official_raw)['game'];summary=strict_json(espn_raw)
    require(str(game['gameId'])==join['nba_id'] and str(summary['header']['id'])==join['espn_id'],'GAME_NATIVE_ID_JOIN')
    require(type(game['gameStatus']) is int and game['gameStatus']==3,'OFFICIAL_NOT_FINAL')
    period=game['period'];require(type(period) is int and period>=4 and game['gameClock']=='PT00M00.00S','OFFICIAL_FINAL_PERIOD_CLOCK')
    duration_seconds=(48+5*(period-4))*60
    official_start=utc(game['gameTimeUTC'])
    require(official_start.astimezone(ZoneInfo('America/New_York')).strftime('%Y%m%d')==game['gameCode'].split('/')[0],'OFFICIAL_GAME_DATE')
    require(official_start==utc(join['official_start']),'OFFICIAL_CAPTURED_START')
    competition=summary['header']['competitions'][0]
    require(competition['status']['type']['completed'] is True,'ESPN_NOT_COMPLETED')
    require(utc(competition['date'])==utc(join['espn_start']),'ESPN_CAPTURED_START')
    require(utc(competition['date']).astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')==join['date'],'CROSS_SOURCE_GAME_DATE')
    cards=[c['cardData'] for m in next_data(index_raw)['gameCardFeed']['modules'] for c in m.get('cards',[]) if c.get('cardData',{}).get('gameId')==join['nba_id']]
    require(len(cards)==1,'OFFICIAL_INDEX_GAME_POPULATION');card=cards[0]
    require(card['gameStatus']==3 and card['period']==period and utc(card['gameTimeUtc'])==official_start,'OFFICIAL_INDEX_GAME_WITNESS')
    require(game['gameCode'].split('/')[1]==game['awayTeam']['teamTricode']+game['homeTeam']['teamTricode'],'OFFICIAL_GAME_CODE_TEAMS')
    teams=summary['boxscore']['players'];require(len(teams)==2 and len({str(t['team']['id']) for t in teams})==2,'ESPN_BOX_TEAM_POPULATION')
    homeaway={str(t['id']):t['homeAway'] for t in competition['competitors']}
    require(len(homeaway)==2 and set(homeaway.values())=={'home','away'},'ESPN_HOME_AWAY')
    rows=[];native_ids=set();espn_ids=set();members={};notes=[]
    for team in teams:
        tid=str(team['team']['id']);side=homeaway[tid];nba=game[side+'Team'];index_team=card[side+'Team']
        require(nba['teamName']==team['team']['name']==index_team['teamName'],'TEAM_NAME_SCOPE_JOIN')
        require(int(nba['teamId'])==int(index_team['teamId'])==int(game[side+'TeamId']),'OFFICIAL_TEAM_ID_JOIN')
        period_scores=lambda rows:[(p['period'],p['score']) for p in rows]
        require(period_scores(nba['periods'])==period_scores(index_team['periods']) and nba['score']==index_team['score'],
            'OFFICIAL_INDEX_PERIOD_SCORE_JOIN')
        require([p['period'] for p in nba['periods']]==list(range(1,period+1)),'OFFICIAL_PERIOD_COVERAGE')
        require(sum(_integer(p['score'],'OFFICIAL_PERIOD_SCORE') for p in nba['periods'])==nba['score']==nba['statistics']['points'],'OFFICIAL_PERIOD_SCORE_ACCOUNTING')
        stats=team['statistics'];require(len(stats)==1,'ESPN_STAT_GROUP_POPULATION');names=stats[0]['names']
        byname=defaultdict(list)
        for a in stats[0]['athletes']:
            pid=str(a['athlete']['id']);require(pid not in espn_ids,'ESPN_DUPLICATE_GAME_PLAYER');espn_ids.add(pid)
            byname[name_key(a['athlete']['displayName'])].append(a)
        printed_sums=Counter();positive_seconds=0
        for number,row in enumerate(nba['players']):
            person=str(row['personId']);require(person not in native_ids,'OFFICIAL_DUPLICATE_GAME_PLAYER');native_ids.add(person)
            name=row['firstName']+' '+row['familyName'];comment=row.get('comment','');display=row.get('statistics',{}).get('minutes')
            record=dict(game_id='espn:game:'+join['espn_id'],nba_game_id=join['nba_id'],team_id='espn:team:'+tid,
                nba_team_id=str(nba['teamId']),nba_person_id=person,name=name,source_list='players',source_row_index=number,
                official_reported_minutes=display,official_comment=comment,exact_seconds=None,exact_minutes_rational=None,
                player_id=None,role=None,state='UNKNOWN',reason=None,official_counts=None,espn_counts=None,
                game_start_at=game['gameTimeUTC'],espn_game_start_at=competition['date'],source_clock_discrepancy=official_start!=utc(competition['date']))
            try:
                vector=official_vector(row['statistics']);record['official_counts']=vector
                for key,value in vector.items():printed_sums[key]+=value
                if re.match(r'^DNP\b',comment):
                    require(display in ('',None),'DNP_EXPOSURE_CONFLICT')
                    require(all(value==0 for value in vector.values()),'DNP_CREDIT_CONFLICT')
                    record.update(state='DNP',reason='EXPLICIT_DNP_NO_TRAINING_EXPOSURE')
                else:
                    sec=seconds(display);record.update(exact_seconds=sec,exact_minutes_rational=str(Fraction(sec,60)))
                    require(sec<=duration_seconds,'PLAYER_EXPOSURE_EXCEEDS_GAME')
                    positive_seconds+=sec
                    record.update(state='PLAYED_ORDINARY' if sec>=30 else 'PLAYED_SUB30' if sec>0 else 'ZERO_DISPLAY',
                        reason=None if sec>=30 else 'SUB_30_SECOND_EXPOSURE' if sec>0 else 'ZERO_DISPLAY_NO_EXCEPTION_ADMISSION')
                candidates=byname[name_key(name)];require(len(candidates)==1,'UNMATCHED_OR_AMBIGUOUS_NAME')
                other=candidates[0];record['player_id']='espn:player:'+str(other['athlete']['id'])
                record['espn_displayed_minutes']=other.get('stats',[None])[0] if other.get('stats') else None
                ev=espn_vector(other,names);record['espn_counts']=ev
                if record['state']=='DNP':require(other['didNotPlay'] is True,'CROSS_SOURCE_DNP_STATE_CONFLICT')
                else:require(ev is not None and ev==vector,'CROSS_SOURCE_FULL_COUNT_VECTOR_CONFLICT')
                source_position=other['athlete'].get('position',{}).get('abbreviation')
                group=POSITIONS.get(source_position);record['espn_position_observed_at_capture']=source_position
                require(group is not None,'AMBIGUOUS_OR_MISSING_CAPTURE_POSITION')
                record['role']='ESPN_POSITION_BIN_AT_CAPTURE:'+group
                members[record['player_id']]=record['team_id']
            except (KeyError,ValueError,TypeError,AttributeError) as exc:record['reason']=str(exc)
            record['fit_included']=record['state']=='PLAYED_ORDINARY' and record['reason'] is None
            rows.append(record)
        # Integer credits include all printed rows, even excluded/unmatched ones.
        for key in FIELDS:
            if key!='plusMinusPoints':require(printed_sums[key]==nba['statistics'][key],'OFFICIAL_PRINTED_TEAM_COUNT_SUM:'+key)
        notes.append(dict(team_id='espn:team:'+tid,reported_individual_second_sum=positive_seconds,
            period_rule_team_seconds=5*duration_seconds,resolution_delta_seconds=positive_seconds-5*duration_seconds,
            normalization_applied=False,bench_starter_aggregates='QUARANTINED_NOT_EXPOSURE_WITNESS'))
        for number,row in enumerate(nba.get('inactives',[])):
            rows.append(dict(game_id='espn:game:'+join['espn_id'],nba_game_id=join['nba_id'],team_id='espn:team:'+tid,
                nba_team_id=str(nba['teamId']),nba_person_id=str(row.get('personId')),name=row.get('firstName','')+' '+row.get('familyName',''),
                source_list='inactives',source_row_index=number,state='INACTIVE_LISTED',reason='INACTIVE_LIST_HAS_NO_ORDINARY_PLAY_EXPOSURE',
                exact_seconds=None,player_id=None,role=None,fit_included=False,game_start_at=game['gameTimeUTC']))
    return dict(game_id='espn:game:'+join['espn_id'],nba_game_id=join['nba_id'],game_start_at=game['gameTimeUTC'],
        overtime_periods=period-4,duration_seconds=duration_seconds,members=members,rows=rows,notes=notes,
        verification_scope='STRUCTURAL_ONLY_NOT_SOURCE_ADMISSION')


def build_dataset(raw_dir,spec_path,policy_path):
    spec_raw=Path(spec_path).read_bytes();require(digest(spec_raw)==SPEC_SHA,'UNREVIEWED_PREFIT_POPULATION')
    spec=strict_json(spec_raw);root=Path(raw_dir);cutoff=utc(spec['data_cutoff_at'])
    policy=Path(policy_path).read_bytes();require(digest(policy)==RULE_SHA,'NBA_TIMING_RULE_POLICY_BYTES')
    require(b'All periods of regulation play in the NBA will be twelve minutes.' in policy
        and b'All overtime periods of play will be five minutes.' in policy,'NBA_TIMING_RULE_TEXT')
    bodies={};receipts={}
    for name,expected in spec['sources'].items():
        body=(root/name/'body.raw').read_bytes();rr=(root/name/'receipt.json').read_bytes();r=strict_json(rr)
        require(digest(body)==expected['body_sha256']==r['raw_sha256'] and digest(rr)==expected['receipt_sha256'],'FROZEN_CAPTURE_BYTES:'+name)
        require(r['url']==expected['url'] and r['status']==200,'CAPTURE_ENDPOINT_STATUS:'+name)
        require(utc(r['retrieval_started_at'])<=utc(r['retrieval_completed_at'])<=utc(r['ingested_at'])<=cutoff,'CAPTURE_AFTER_DATA_CUTOFF:'+name)
        require(all(r.get(k) is None for k in ('source_published_at','original_historical_available_at','correction_history_complete','predecessor_sha256')),'UNSUPPORTED_CAPTURE_CLAIM:'+name)
        bodies[name]=body;receipts[name]=r
    records=[];manifest={};raw_sources={};games=[]
    for join in spec['game_joins']:
        official='nba-box-'+join['nba_id'];summary='summary-'+join['espn_id']
        parsed=parse_completed_game(bodies[official],bodies[summary],bodies[join['index']],join)
        require(utc(parsed['game_start_at'])<cutoff and join['espn_id']!=spec['target']['game_id'],'TARGET_OR_FUTURE_TRAINING_GAME')
        key=digest((root/official/'receipt.json').read_bytes());receipt=receipts[official]
        components=[receipts[name] for name in (official,summary,join['index'])]
        observed=max((r['retrieval_completed_at'] for r in components),key=utc)
        ingested=max((r['ingested_at'] for r in components),key=utc)
        require(utc(parsed['game_start_at'])+timedelta(seconds=parsed['duration_seconds'])<=utc(receipt['retrieval_completed_at']),
            'FINAL_RESULT_OBSERVED_BEFORE_MINIMUM_GAME_END')
        manifest[key]=dict(raw_sha256=digest(bodies[official]),available_at=ingested,status='P1_VERIFIED',
            games={parsed['game_id']:dict(overtime_periods=parsed['overtime_periods'],game_start_at=parsed['game_start_at'],players=parsed['members'],duration_receipt_sha256=key)})
        raw_sources[key]=bodies[official].decode('utf-8')
        for row in parsed['rows']:
            row.update(source_receipt_sha256=key,source_raw_sha256=digest(bodies[official]),
                outcome_available_at=observed,source_ingested_at=ingested,
                role_source_observed_at=receipts[summary]['retrieval_completed_at'],
                role_identity_source_raw_sha256=digest(bodies[summary]),
                role_identity_source_receipt_sha256=digest((root/summary/'receipt.json').read_bytes()))
            records.append(row)
        games.append({k:v for k,v in parsed.items() if k!='rows'})
    # A per-game name match never silently resolves conflicting native identities.
    id_map=defaultdict(set);reverse=defaultdict(set)
    for row in records:
        if row.get('player_id'):
            id_map[row['player_id']].add(row['nba_person_id']);reverse[row['nba_person_id']].add(row['player_id'])
    for row in records:
        if row.get('player_id') and len(id_map[row['player_id']])!=1:row.update(fit_included=False,reason='AMBIGUOUS_NATIVE_ID_ACROSS_GAMES')
        if row.get('player_id') and len(reverse[row['nba_person_id']])!=1:row.update(fit_included=False,reason='AMBIGUOUS_ESPN_ID_ACROSS_GAMES')
    history={stat:[] for stat in STAT_KEYS};attempts=[]
    for index,row in enumerate(records):
        for stat,key in STAT_KEYS.items():
            attempt=dict(source_observation_index=index,statistic=stat,included=row['fit_included'],reason=row['reason'])
            if row['fit_included']:
                value=dict(game_id=row['game_id'],player_id=row['player_id'],team_id=row['team_id'],stat=stat,role=row['role'],
                    game_start_at=row['game_start_at'],outcome_available_at=row['outcome_available_at'],
                    source_receipt_sha256=row['source_receipt_sha256'],source_raw_sha256=row['source_raw_sha256'],
                    count=row['official_counts'][key],minutes=float(Fraction(row['exact_seconds'],60)),three_attempts=row['official_counts']['threePointersAttempted'])
                history[stat].append(value);attempt['native_row_sha256']=digest(canonical(value))
            attempts.append(attempt)
    payload=dict(schema=VERSION,spec_raw_sha256=SPEC_SHA,reader_raw_sha256=digest(Path(__file__).read_bytes()),timing_rule_raw_sha256=RULE_SHA,
        data_cutoff_at=spec['data_cutoff_at'],target=spec['target'],frozen_candidates=spec['frozen_candidates'],
        source_capture_count=len(bodies),game_count=len(games),source_observation_denominator=len(records),
        player_row_denominator=sum(r['source_list']=='players' for r in records),inactive_identity_denominator=sum(r['source_list']=='inactives' for r in records),
        training_attempt_denominator=len(attempts),included_training_attempts=sum(a['included'] for a in attempts),
        excluded_training_attempts=sum(not a['included'] for a in attempts),records=records,attempts=attempts,games=games,
        histories=history,source_manifest=manifest,raw_sources=raw_sources,
        role_semantics='ESPN_POSITION_BIN_OBSERVED_AT_CAPTURE',exposure_semantics='EXACT_SOURCE_REPORTED_SECONDS_GE_30',
        source_admission='REQUIRES_SEPARATE_INDEPENDENT_PREFIT_READER_APPROVAL',correction_history_complete=None,
        source_publication_at=None,original_historical_pregame_availability=None,fit_performed=False)
    return dict(payload,payload_sha256=digest(canonical(payload)))
