"""Exact frozen official PBP source -> event facts. No simulation admission.

Box records and event clocks are source observations, not a reconstructed legal
roster, wallclock-end timestamp or general source-authentication root.
"""
from collections import Counter,defaultdict
from decimal import Decimal
from pathlib import Path
import re
from .p1_subset_handoff_v1 import canonical,digest
from .subset_contract_v1 import strict_json
from .subset_p3_v1 import require
from .prospective_s_sources_v1 import next_data,official_vector
from .gamebook_identity_v1 import name_key
from v2.nba_opportunity import utc


def game_clock(text):
    require(isinstance(text,str) and re.fullmatch(r'PT\d+M\d+(?:\.\d+)?S',text) is not None,'PBP_CLOCK_FORMAT')
    minute,second=text[2:-1].split('M');second=Decimal(second)
    require(0<=second<60,'PBP_CLOCK_SECOND_RANGE')
    return Decimal(minute)*60+second


def parse_pbp(raw,box_raw,game_id):
    """Structural parser only. Native IDs stay dated to this game and team."""
    page=next_data(raw);game=page['game'];pbp=page['playByPlay'];old=next_data(box_raw)['game']
    require(game['gameId']==pbp['gameId']==old['gameId']==game_id,'PBP_GAME_IDENTITY')
    require(game['gameStatus']==old['gameStatus']==3 and game['gameClock']==old['gameClock']=='PT00M00.00S',
        'PBP_NOT_FINAL')
    require(game['period']==old['period'] and game['gameTimeUTC']==old['gameTimeUTC'],'PBP_GAME_SCOPE')
    players={};teams={};expected={};counts={};aliases=defaultdict(set)
    for side in ('homeTeam','awayTeam'):
        team=game[side];prior=old[side];tid=str(team['teamId']);teams[side]=tid
        require(team['teamId']==prior['teamId'] and team['score']==prior['score'],'PBP_TEAM_OR_SCORE')
        native={str(p['personId']):p for p in prior['players']}
        require(len(native)==len(prior['players']),'PBP_DUPLICATE_BOX_ID')
        require({str(p['personId']) for p in team['players']}==set(native),'PBP_BOX_PLAYER_POPULATION')
        for p in team['players']:
            pid=str(p['personId']);require(pid not in players,'PBP_DUPLICATE_PLAYER')
            vector=official_vector(p['statistics'])
            require(vector==official_vector(native[pid]['statistics']) and p['statistics']['minutes']==native[pid]['statistics']['minutes'],
                'PBP_LATER_BOX_FACT_CONFLICT')
            players[pid]=dict(team_id=tid,name=p['firstName']+' '+p['familyName'],reported_minutes=p['statistics']['minutes'],comment=p.get('comment'))
            expected[pid]=vector;counts[pid]=Counter()
            for name in (p['familyName'],p.get('nameI','')):
                if name:aliases[(tid,name_key(name))].add(pid)
    actions=pbp['actions'];require(isinstance(actions,list) and bool(actions),'PBP_ACTIONS_REQUIRED')
    ids=set();previous=None;ends={};unresolved=[];events=[]
    for number,row in enumerate(actions):
        aid=row['actionId'];period=row['period'];clock=game_clock(row['clock'])
        require(type(aid) is int and aid not in ids,'PBP_DUPLICATE_ACTION_ID');ids.add(aid)
        require(type(period) is int and 1<=period<=game['period'],'PBP_PERIOD')
        length=720 if period<=4 else 300;require(0<=clock<=length,'PBP_CLOCK_SUPPORT')
        elapsed=Decimal(720*min(period-1,4)+300*max(period-5,0))+Decimal(length)-clock
        require(previous is None or elapsed>=previous,'PBP_NONCHRONOLOGICAL_SOURCE');previous=elapsed
        typ=row['actionType'];pid=str(row['personId']);tid=str(row['teamId']);description=row['description']
        if pid in players:
            require(tid==players[pid]['team_id'],'PBP_ACTOR_TEAM')
            if row.get('playerName'):aliases[(tid,name_key(row['playerName']))].add(pid)
            # Native source initial-name field can differ from box family-name
            # order. This remains a dated native-ID alias, never an ESPN or
            # forward roster crosswalk. Ambiguous strings stay unresolved.
            initial=re.fullmatch(r'[A-Za-z]{1,3}\.\s+(.+)',row.get('playerNameI',''))
            if initial:aliases[(tid,name_key(initial.group(1)))].add(pid)
        if typ=='period' and row['subType']=='end':
            require(clock==0 and period not in ends,'PBP_PERIOD_END')
            ends[period]=(int(row['scoreHome']),int(row['scoreAway']))
        if row['isFieldGoal']==1:
            require(pid in players and row['shotValue'] in (2,3) and row['shotResult'] in ('Made','Missed'),'PBP_SHOT')
            counts[pid]['fieldGoalsAttempted']+=1
            if row['shotValue']==3:counts[pid]['threePointersAttempted']+=1
            if row['shotResult']=='Made':
                counts[pid]['fieldGoalsMade']+=1;counts[pid]['points']+=row['shotValue']
                if row['shotValue']==3:counts[pid]['threePointersMade']+=1
        elif typ=='Free Throw':
            require(pid in players,'PBP_FT_ACTOR');counts[pid]['freeThrowsAttempted']+=1
            if not description.startswith('MISS '):counts[pid]['freeThrowsMade']+=1;counts[pid]['points']+=1
        if typ=='Rebound' and pid in players:
            match=re.search(r'Off:(\d+) Def:(\d+)',description)
            require(match is not None,'PBP_REBOUND_CREDIT')
            off,deff=map(int,match.groups());delta=off-counts[pid]['reboundsOffensive']+deff-counts[pid]['reboundsDefensive']
            require(delta==1 and off>=counts[pid]['reboundsOffensive'] and deff>=counts[pid]['reboundsDefensive'],'PBP_REBOUND_SEQUENCE')
            counts[pid]['reboundsOffensive']=off;counts[pid]['reboundsDefensive']=deff;counts[pid]['reboundsTotal']=off+deff
        if typ=='Turnover' and pid in players:counts[pid]['turnovers']+=1
        if typ=='' and pid in players:
            if ' STEAL ' in description:counts[pid]['steals']+=1
            if ' BLOCK ' in description:counts[pid]['blocks']+=1
        events.append(dict(index=number,action_id=aid,period=period,clock=row['clock'],elapsed_seconds=str(elapsed),
            type=typ,subtype=row['subType'],native_person_id=pid,native_team_id=tid,description=description,
            shot_value=row['shotValue'],is_field_goal=row['isFieldGoal'],shot_result=row['shotResult'],
            source_score_home=row['scoreHome'],source_score_away=row['scoreAway']))
    require(set(ends)==set(range(1,game['period']+1)),'PBP_PERIOD_COVERAGE')
    require(ends[game['period']]==(game['homeTeam']['score'],game['awayTeam']['score']),'PBP_FINAL_SCORE')
    require(ends[game['period']][0]!=ends[game['period']][1],'PBP_TIED_FINAL_GAME')
    require(all(ends[p][0]==ends[p][1] for p in range(4,game['period'])),'PBP_OVERTIME_WITHOUT_TIE')
    # Assist labels are source text; ambiguous aliases never invent identities.
    for row in actions:
        match=re.search(r'\(([^()]*) (\d+) AST\)',row['description'])
        if match:
            candidates=aliases[(str(row['teamId']),name_key(match.group(1)))]
            if len(candidates)==1:
                assister=next(iter(candidates));require(assister!=str(row['personId']),'PBP_SELF_ASSIST')
                counts[assister]['assists']+=1
            else:unresolved.append(dict(action_id=row['actionId'],reason='UNRESOLVED_ASSIST_ALIAS',text=match.group(1)))
    fields=('points','fieldGoalsMade','fieldGoalsAttempted','threePointersMade','threePointersAttempted',
        'freeThrowsMade','freeThrowsAttempted','reboundsOffensive','reboundsDefensive','reboundsTotal','assists','steals','blocks','turnovers')
    discrepancies=[dict(native_person_id=pid,field=key,event_count=counts[pid][key],box_count=vector[key])
        for pid,vector in expected.items() for key in fields if counts[pid][key]!=vector[key]]
    return dict(schema='nba-official-PBP-facts/1',game_id=game_id,game_start_at=game['gameTimeUTC'],
        raw_sha256=digest(raw),box_raw_sha256=digest(box_raw),players=players,
        action_denominator=len(actions),events=events,unresolved_alias_denominator=len(unresolved),unresolved_aliases=unresolved,
        reconciled_event_credit_fields=list(fields),event_derived_PF_and_plus_minus_admitted=False,
        event_credit_discrepancies=discrepancies,all_credited_event_counts_reconciled=not discrepancies,
        period_end_scores=ends,reported_end_wallclock_text=actions[-1]['description'],exact_wallclock_end_at=None,
        source_admission='STRUCTURAL_ONLY_PENDING_INDEPENDENT_CAPABILITY_REVIEW',
        on_court_lineup_completeness=None,correction_history_complete=None)


def read_population(raw_dir,population_path,original_raw_dir):
    """Read a supplied frozen collection; its SHA is recorded, not approval."""
    raw=Path(raw_dir);population_raw=Path(population_path).read_bytes();population=strict_json(population_raw)
    rows=[]
    for name,item in population['sources'].items():
        body=(raw/name/'body.raw').read_bytes();rr=(raw/name/'receipt.json').read_bytes();r=strict_json(rr)
        require(digest(body)==item['body_sha256']==r['raw_sha256'] and digest(rr)==item['receipt_sha256'],'PBP_FROZEN_BYTES')
        require(r['url']==item['url'] and r['status']==200 and r['url'].startswith('https://www.nba.com/game/')
            and r['url'].endswith('/play-by-play'),'PBP_ENDPOINT')
        require(utc(r['retrieval_started_at'])<=utc(r['retrieval_completed_at'])<=utc(r['ingested_at'])<=utc(population['frozen_at']),'PBP_CAPTURE_CLOCK')
        require(all(r.get(k) is None for k in ('source_published_at','original_historical_available_at','correction_history_complete','predecessor_sha256')),'PBP_UNSUPPORTED_CLAIM')
        gid=name.removeprefix('pbp-')
        try:
            value=parse_pbp(body,(Path(original_raw_dir)/('nba-box-'+gid)/'body.raw').read_bytes(),gid)
            rows.append(dict(game_id=gid,status='PARSED_STRUCTURAL_ONLY',facts=value))
        except (ValueError,KeyError,TypeError) as error:rows.append(dict(game_id=gid,status='REJECTED',reason=str(error),facts=None))
    payload=dict(schema='nba-PBP-population-reader/1',population_raw_sha256=digest(population_raw),
        reader_raw_sha256=digest(Path(__file__).read_bytes()),game_denominator=len(rows),rows=rows,
        rejected_games=sum(r['facts'] is None for r in rows),source_admission=False)
    return dict(payload,payload_sha256=digest(canonical(payload)))
