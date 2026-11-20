"""Independent pre-fit raw population audit. Never imports/calls a fitter."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[4]
PACKET=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120'
RAW=PACKET/'raw'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def pairs(values):
    out={}
    for key,value in values:
        if key in out:raise ValueError('DUPLICATE_JSON_KEY:'+key)
        out[key]=value
    return out
def parse(raw):return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError(x)))
def utc(text):
    value=datetime.fromisoformat(text.replace('Z','+00:00'));assert value.tzinfo is not None
    return value
def payload(raw):
    matches=re.findall(rb'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw,re.S)
    assert len(matches)==1
    return parse(matches[0])['props']['pageProps']
def name(value):
    words=re.findall('[a-z]+',unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().lower())
    if words and words[-1] in ('jr','sr'):words.pop()
    return ''.join(words)

population_raw=(PACKET/'PREFIT_POPULATION.json').read_bytes();pop=parse(population_raw)
assert (PACKET/'PREFIT_POPULATION.sha256').read_text().split()[0]==sha(population_raw)
cutoff=utc(pop['data_cutoff_at']);sources={};receipts={};observations=[];game_reports=[]
assert len(pop['sources'])==60
for label,ref in pop['sources'].items():
    body=(RAW/label/'body.raw').read_bytes();rraw=(RAW/label/'receipt.json').read_bytes();r=parse(rraw)
    assert sha(body)==ref['body_sha256']==r['raw_sha256'] and sha(rraw)==ref['receipt_sha256']
    assert len(body)==r['bytes'] and r['byte_domain']=='HTTP_RESPONSE_BODY_BYTES'
    assert r['url']==ref['url'] and r['status']==ref['status']==200
    assert utc(r['retrieval_started_at'])<=utc(r['retrieval_completed_at'])<=utc(r['ingested_at'])<=cutoff
    assert r['retrieval_completed_at']==ref['observed_at'] and r['ingested_at']==ref['ingested_at']
    assert all(r[k] is None for k in ('source_published_at','original_historical_available_at','correction_history_complete'))
    sources[label]=body;receipts[label]=r
assert max(utc(r['ingested_at']) for r in receipts.values())<=cutoff
target=pop['target'];target_event=next(e for e in parse(sources['scoreboard'])['events'] if e['id']==target['game_id'])
assert utc(target_event['date'])==utc(target['start'])>cutoff
assert target_event['competitions'][0]['status']['type']['completed'] is False
candidate_ids=[]
for tid in target['teams']:
    roster=parse(sources['roster-'+tid]);assert str(roster['team']['id'])==tid
    candidate_ids.extend((f"espn:player:{row['id']}",f'espn:team:{tid}',row['displayName']) for row in roster['athletes'])
assert len(candidate_ids)==len(set((p,t) for p,t,n in candidate_ids))==35
assert set(candidate_ids)=={(r['player_id'],r['team_id'],r['name']) for r in pop['frozen_candidates']}
selected={}
for tid in target['teams']:
    schedule=parse(sources['schedule-'+tid]);assert str(schedule['team']['id'])==tid
    events=[e for e in schedule['events'] if utc(e['date'])<utc(target['start']) and e['competitions'][0]['status']['type']['completed'] is True]
    selected[tid]=sorted(events,key=lambda e:(utc(e['date']),e['id']))[-10:]
    assert selected[tid]==pop['selected_espn_games'][tid]
    assert all(utc(e['date'])<cutoff and e['id']!=target['game_id'] for e in selected[tid])
assert len({e['id'] for group in selected.values() for e in group})==20

COUNT=('fieldGoalsMade','fieldGoalsAttempted','threePointersMade','threePointersAttempted',
       'freeThrowsMade','freeThrowsAttempted','reboundsOffensive','reboundsDefensive','reboundsTotal',
       'assists','steals','blocks','turnovers','foulsPersonal','points')
DIRECT={'points':'PTS','reboundsTotal':'REB','assists':'AST','turnovers':'TO','steals':'STL',
        'blocks':'BLK','reboundsOffensive':'OREB','reboundsDefensive':'DREB','foulsPersonal':'PF','plusMinusPoints':'+/-'}
PAIRS={'FG':('fieldGoalsMade','fieldGoalsAttempted'),'3PT':('threePointersMade','threePointersAttempted'),
       'FT':('freeThrowsMade','freeThrowsAttempted')}
ROLE={'PG':'G','SG':'G','G':'G','SF':'F','PF':'F','F':'F','C':'C'}
state_counts=Counter();validation_counts=Counter();role_counts=Counter();period_counts=Counter();clock_differences=[];tricode_differences=[]
for join in pop['game_joins']:
    official=payload(sources['nba-box-'+join['nba_id']])['game']
    espn=parse(sources['summary-'+join['espn_id']]);ec=espn['header']['competitions'][0]
    assert official['gameId']==join['nba_id'] and str(ec['id'])==join['espn_id']
    assert official['gameStatus']==3 and official['gameClock']=='PT00M00.00S'
    period=official['period'];assert type(period) is int and period>=4;period_counts[period]+=1
    assert utc(official['gameTimeUTC'])<cutoff and utc(ec['date'])<cutoff
    day=utc(ec['date']).astimezone(ZoneInfo('America/New_York')).strftime('%Y-%m-%d')
    assert day==join['date']==official['gameCode'][:8][:4]+'-'+official['gameCode'][4:6]+'-'+official['gameCode'][6:8]
    index=payload(sources[join['index']]);cards=[c['cardData'] for m in index['gameCardFeed']['modules'] for c in m.get('cards',[]) if 'gameId' in c.get('cardData',{})]
    side_names={t['homeAway']:next(x['team']['name'] for x in espn['boxscore']['players'] if str(x['team']['id'])==str(t['id'])) for t in ec['competitors']}
    name_matches=[c for c in cards if all(c[side+'Team']['teamName']==value for side,value in side_names.items())]
    assert len(name_matches)==1 and name_matches[0]['gameId']==join['nba_id']
    matches=[c for c in cards if c['gameId']==join['nba_id']];assert len(matches)==1
    card=matches[0]
    assert any('https://www.nba.com'+a['resourceLocator']['resourceUrl']==join['url'] for a in card['actions'] if a['title']=='Box Score')
    assert utc(official['gameTimeUTC'])==utc(join['official_start'])==utc(card['gameTimeUtc'])
    if utc(official['gameTimeUTC'])!=utc(ec['date']):clock_differences.append(dict(join,official_payload_start=official['gameTimeUTC'],espn_payload_start=ec['date']))
    total_rows=0;inactive_rows=0;game_ids=set();team_checks=[]
    for side in ('home','away'):
        team=official[side+'Team'];assert team['teamId']==official[side+'TeamId']==card[side+'Team']['teamId']
        expected=list(range(1,period+1));assert [p['period'] for p in team['periods']]==expected
        assert sum(p['score'] for p in team['periods'])==team['score']
        eid=next(str(t['id']) for t in ec['competitors'] if t['homeAway']==side)
        et=next(t for t in espn['boxscore']['players'] if str(t['team']['id'])==eid)
        assert et['team']['name']==team['teamName']==card[side+'Team']['teamName']
        if et['team']['abbreviation']!=team['teamTricode']:
            tricode_differences.append(dict(espn_game_id=join['espn_id'],side=side,
                espn_abbreviation=et['team']['abbreviation'],nba_tricode=team['teamTricode'],
                exact_shared_team_name=team['teamName']))
        es=et['statistics'][0];indexed={}
        for person in es['athletes']:indexed.setdefault(name(person['athlete']['displayName']),[]).append(person)
        sums=Counter();sec_sum=0;team_rejections=Counter()
        for row in team['players']:
            total_rows+=1;pid=row['personId'];assert pid not in game_ids;game_ids.add(pid)
            stat=row['statistics'];reason=None;raw_min=stat.get('minutes');seconds=None
            match=re.fullmatch(r'(\d+):(\d{2})',raw_min) if isinstance(raw_min,str) else None
            if match and int(match[2])<60:
                seconds=int(match[1])*60+int(match[2]);sec_sum+=seconds
                state='POSITIVE_GE_30_SECONDS' if seconds>=30 else ('SUB_30_SECONDS' if seconds>0 else 'PRINTED_ZERO')
            elif raw_min=='' and row.get('comment','').startswith('DNP - '):state='EXPLICIT_DNP_COMMENT'
            else:state='UNKNOWN_EXPOSURE'
            state_counts[state]+=1
            if not all(type(stat.get(k)) is int and stat[k]>=0 for k in COUNT):reason='NONINTEGER_OR_MISSING_COUNT'
            elif not (stat['points']==2*stat['fieldGoalsMade']+stat['threePointersMade']+stat['freeThrowsMade']
                and stat['reboundsTotal']==stat['reboundsOffensive']+stat['reboundsDefensive']
                and stat['threePointersMade']<=stat['threePointersAttempted']<=stat['fieldGoalsAttempted']
                and stat['threePointersMade']<=stat['fieldGoalsMade']<=stat['fieldGoalsAttempted']
                and stat['freeThrowsMade']<=stat['freeThrowsAttempted']):reason='COUNT_ARITHMETIC'
            elif seconds is not None and seconds>60*(48+5*(period-4)):reason='EXPOSURE_PHYSICS'
            if all(type(stat.get(k)) is int for k in COUNT):
                for k in COUNT:sums[k]+=stat[k]
            match_people=indexed.get(name(row['firstName']+' '+row['familyName']),[]);other=match_people[0] if len(match_people)==1 else None
            role=None;espn_id=None
            if state=='POSITIVE_GE_30_SECONDS' and reason is None:
                if other is None:reason='UNMATCHED_OR_AMBIGUOUS_NAME'
                elif other.get('didNotPlay') is not False:reason='PARTICIPATION_CONFLICT'
                else:
                    try:
                        values=dict(zip(es['names'],other['stats']))
                        if not all(int(values[v])==stat[k] for k,v in DIRECT.items()):reason='CROSS_SOURCE_COUNT_CONFLICT'
                        if not all(tuple(map(int,values[k].split('-')))==tuple(stat[f] for f in fields) for k,fields in PAIRS.items()):reason='CROSS_SOURCE_SHOOTING_CONFLICT'
                    except (ValueError,KeyError,TypeError):reason='UNPARSEABLE_ESPN_COUNTS'
                    role=ROLE.get(other['athlete'].get('position',{}).get('abbreviation'))
                    if reason is None and role is None:reason='AMBIGUOUS_OR_MISSING_OBSERVED_POSITION_BIN'
                    espn_id=other['athlete']['id']
            if state!='POSITIVE_GE_30_SECONDS':reason=reason or state
            status='ELIGIBLE_BEFORE_READER_REVIEW' if reason is None else reason
            validation_counts[status]+=1;team_rejections[status]+=1
            if reason is None:role_counts[role]+=1
            observations.append(dict(nba_game_id=join['nba_id'],espn_game_id=join['espn_id'],
                nba_person_id=pid,espn_player_id=espn_id,espn_team_id=eid,name=row['firstName']+' '+row['familyName'],
                state=state,exact_reported_seconds=seconds,minutes_raw=raw_min,status=status,observed_peer_position_bin=role))
        for row in team['inactives']:
            assert row['personId'] not in game_ids;game_ids.add(row['personId']);inactive_rows+=1
            observations.append(dict(nba_game_id=join['nba_id'],nba_person_id=row['personId'],state='INACTIVE_IDENTITIES_SEPARATE',status='INACTIVE_IDENTITIES_SEPARATE'))
        team_checks.append(dict(side=side,source_row_seconds=sec_sum,expected_team_seconds=5*60*(48+5*(period-4)),
            exact_count_sum_mismatches={k:[sums[k],team['statistics'].get(k)] for k in COUNT if sums[k]!=team['statistics'].get(k)},row_statuses=dict(team_rejections)))
    assert total_rows==pop['official_game_player_rows'][join['nba_id']]
    game_reports.append(dict(nba_game_id=join['nba_id'],espn_game_id=join['espn_id'],period=period,player_rows=total_rows,inactive_rows=inactive_rows,teams=team_checks))
state_counts['INACTIVE_IDENTITIES_SEPARATE']=sum(g['inactive_rows'] for g in game_reports)
assert dict(state_counts)==pop['raw_rows_by_state']
assert len(observations)==532+166
result=dict(prefit_population_sha256=sha(population_raw),scope_sha256=sha((PACKET/'SCOPE.md').read_bytes()),
    source_receipts_rehashed=len(sources),max_source_ingested_at=max(r['ingested_at'] for r in receipts.values()),
    data_cutoff_at=pop['data_cutoff_at'],target=target,candidate_count=35,selected_team_games={t:[e['id'] for e in g] for t,g in selected.items()},
    raw_states=dict(state_counts),validation_counts=dict(validation_counts),eligible_peer_bin_counts=dict(role_counts),
    final_period_counts=dict(period_counts),provider_clock_differences=clock_differences,
    provider_team_tricode_differences=tricode_differences,game_reports=game_reports,
    observations=observations,fit_performed=False,model_admission_granted=False,
    disposition='FROZEN_SOURCE_POPULATION_AUDITED_PENDING_IMPLEMENTATION_READER_REVIEW')
print(json.dumps(result,indent=2,sort_keys=True))
