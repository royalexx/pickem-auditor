"""Independent existing-source capability probe; no fitting or admission."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[4]
NBA=ROOT/'docs/nba_architecture/p1_workflow_repair_20261119/independent/source_search/official-game-box-page'
ESPN=ROOT/'docs/nba_architecture/p1_p5_handoffs_20261119/prospective_inputs/summary-401910007'
raw=(NBA/'body.raw').read_bytes();receipt=json.loads((NBA/'receipt.json').read_bytes())
assert receipt['status']==200 and receipt['raw_sha256']==hashlib.sha256(raw).hexdigest()
assert receipt['bytes']==len(raw)
scripts=re.findall(rb'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw,re.S)
assert len(scripts)==1
game=json.loads(scripts[0])['props']['pageProps']['game']
espn=json.loads((ESPN/'body.raw').read_bytes())
assert game['gameId']=='0022600258' and game['gameCode']=='20261118/MEMCLE'
assert game['gameStatus']==3 and game['period']==4 and game['gameClock']=='PT00M00.00S'
assert datetime.fromisoformat(game['gameTimeUTC'].replace('Z','+00:00'))==datetime.fromisoformat(espn['header']['competitions'][0]['date'].replace('Z','+00:00'))
FIELDS=('fieldGoalsMade','fieldGoalsAttempted','threePointersMade','threePointersAttempted',
    'freeThrowsMade','freeThrowsAttempted','reboundsOffensive','reboundsDefensive',
    'reboundsTotal','assists','steals','blocks','turnovers','foulsPersonal','points')
DIRECT={'points':'PTS','reboundsTotal':'REB','assists':'AST','turnovers':'TO',
    'steals':'STL','blocks':'BLK','reboundsOffensive':'OREB','reboundsDefensive':'DREB','foulsPersonal':'PF'}
PAIR={'FG':('fieldGoalsMade','fieldGoalsAttempted'),'3PT':('threePointersMade','threePointersAttempted'),
    'FT':('freeThrowsMade','freeThrowsAttempted')}
result=dict(game={k:game[k] for k in ('gameId','gameCode','gameStatus','gameStatusText','period','gameClock','gameTimeUTC','gameEt')},
    source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (NBA/'body.raw',NBA/'receipt.json',ESPN/'body.raw',ESPN/'receipt.json')},teams=[],
    fit_performed=False,model_admission_granted=False,fresh_source_admission_granted=False)
all_ids=set();positive_matches=0
for side in ('homeTeam','awayTeam'):
    team=game[side];expected_periods=list(range(1,game['period']+1))
    assert [p['period'] for p in team['periods']]==expected_periods
    assert sum(p['score'] for p in team['periods'])==team['score']
    e=next(t for t in espn['boxscore']['players'] if t['team']['abbreviation']==team['teamTricode'])
    source=e['statistics'][0];erows={}
    for row in source['athletes']:
        erows.setdefault(row['athlete']['displayName'],[]).append(row)
    counts=Counter();seconds=0;observations=[];sums=Counter()
    for row in team['players']:
        pid=row['personId'];assert type(pid) is int and pid not in all_ids;all_ids.add(pid)
        stat=row['statistics'];assert all(type(stat[k]) is int and stat[k]>=0 for k in FIELDS)
        assert stat['points']==2*stat['fieldGoalsMade']+stat['threePointersMade']+stat['freeThrowsMade']
        assert stat['reboundsTotal']==stat['reboundsOffensive']+stat['reboundsDefensive']
        assert stat['threePointersMade']<=stat['threePointersAttempted']<=stat['fieldGoalsAttempted']
        assert stat['threePointersMade']<=stat['fieldGoalsMade']<=stat['fieldGoalsAttempted']
        assert stat['freeThrowsMade']<=stat['freeThrowsAttempted']
        for key in FIELDS:sums[key]+=stat[key]
        match=re.fullmatch(r'(\d+):(\d{2})',stat['minutes'])
        exact_seconds=None
        if match:
            assert int(match[2])<60
            exact_seconds=60*int(match[1])+int(match[2]);assert exact_seconds<=2880
            seconds+=exact_seconds
            state='PLAYED_EXACT_SECONDS_GE30' if exact_seconds>=30 else 'SUB30_OR_ZERO_EXCLUDED'
        elif stat['minutes']=='' and row['comment'].startswith('DNP - '):
            assert all(stat[k]==0 for k in FIELDS)
            state='EXPLICIT_DNP_EXCLUDED'
        else:state='UNKNOWN_EXPOSURE_EXCLUDED'
        counts[state]+=1;name=row['firstName']+' '+row['familyName'];candidates=erows.get(name,[])
        crosswalk=None
        if state=='PLAYED_EXACT_SECONDS_GE30':
            assert len(candidates)==1
            other=candidates[0];values=dict(zip(source['names'],other['stats']))
            assert other['didNotPlay'] is False
            for field,column in DIRECT.items():assert stat[field]==int(values[column])
            for column,fields in PAIR.items():
                made,attempts=map(int,values[column].split('-'))
                assert (stat[fields[0]],stat[fields[1]])==(made,attempts)
            crosswalk=dict(espn_player_id=other['athlete']['id'],scope='EXACT_FULL_NAME_GAME_TEAM_AND_COUNT_VECTOR_SAMPLE_ONLY')
            positive_matches+=1
        observations.append(dict(nba_person_id=pid,name=name,minutes_raw=stat['minutes'],
            exact_reported_seconds=exact_seconds,state=state,comment=row['comment'],
            official_position=row['position'],exact_name_espn_matches=len(candidates),sample_crosswalk=crosswalk))
    assert seconds==14400
    assert all(sums[field]==team['statistics'][field] for field in FIELDS)
    inactive=[]
    for row in team['inactives']:
        assert row['personId'] not in all_ids;all_ids.add(row['personId'])
        inactive.append(dict(nba_person_id=row['personId'],state='OFFICIAL_INACTIVE_CATEGORY_EXCLUDED',
            name=row['firstName']+' '+row['familyName']))
    result['teams'].append(dict(nba_team_id=team['teamId'],tricode=team['teamTricode'],
        player_rows=len(observations),inactive_rows=len(inactive),states=dict(counts),
        sum_player_seconds=seconds,official_team_minutes=team['statistics']['minutes'],
        starters_aggregate_minutes=team['starters']['minutes'],bench_aggregate_minutes=team['bench']['minutes'],
        observations=observations,inactive_observations=inactive))
assert positive_matches==22
result.update(player_row_denominator=25,inactive_row_denominator=10,total_observed_native_people=35,
    positive_exact_seconds_and_full_count_vector_matches=positive_matches,
    explicit_DNP_exclusions=3,
    warnings=[
        'Bench aggregate minutes duplicate starter aggregate minutes and are not a valid exposure witness.',
        'Official position is blank on bench rows; it is not a substitute for reviewed ESPN observed-at-capture peer bins.',
        'DNP Karim López has no exact full-name ESPN match; this script does not normalize or silently alias it.',
        'Exact reported seconds have source reporting resolution; no subsecond precision is claimed.',
        'This one saved page establishes capability only. Fresh population, source reader, fit and real artifact admission remain unapproved.',
    ])
print(json.dumps(result,indent=2,sort_keys=True))
