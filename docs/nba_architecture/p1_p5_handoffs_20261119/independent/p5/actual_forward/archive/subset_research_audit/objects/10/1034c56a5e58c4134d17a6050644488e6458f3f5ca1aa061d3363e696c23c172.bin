"""Reviewed exploratory WS2 reuse for a source-listed current-team window.

No fit, full-roster allocation, participation estimator or general source root.
All source candidates and all three model attempts survive local abstentions.
"""
from dataclasses import asdict
from pathlib import Path
import re

from v2 import nba_opportunity as native
from .p1_subset_handoff_v1 import read_requests, canonical, digest
from .subset_contract_v1 import strict_json

VERSION='nba-subset-p3/1.0.0'
MODEL_SHA='ea7eae3afc760eafda0fbf0dbdccd2cb77b31b0aca54fc3606b4b31ba90693de'
NATIVE_SHA='6dfb65b783f881de37e3779f3eb40433e1a1c99db103b0b3fef49e30092a5b30'
COHORT_SHA='0ecd8c98ea97bb8be852807c5935d8427adb2b9d9ca062d823da86279f57357f'
MODELS=('M0','M1','M2')
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'
HISTORY_POPULATION={
    '9':(('401909092','2026-10-22T02:00Z'),('401909850','2026-10-24T02:00Z'),
        ('401909860','2026-10-25T02:00Z'),('401909876','2026-10-27T02:00Z'),
        ('401909888','2026-10-29T00:00Z'),('401909285','2026-10-31T02:00Z'),
        ('401909905','2026-11-02T01:30Z'),('401909919','2026-11-03T03:00Z'),
        ('401909937','2026-11-06T03:00Z'),('401909942','2026-11-08T01:30Z'),
        ('401909959','2026-11-10T03:00Z'),('401909974','2026-11-12T02:30Z'),
        ('401909302','2026-11-14T02:30Z'),('401910000','2026-11-17T01:00Z'),
        ('401910016','2026-11-19T01:00Z')),
    '29':(('401909838','2026-10-22T00:00Z'),('401909850','2026-10-24T02:00Z'),
        ('401909867','2026-10-26T01:00Z'),('401909875','2026-10-27T01:00Z'),
        ('401909895','2026-10-30T02:00Z'),('401909899','2026-11-01T00:00Z'),
        ('401909914','2026-11-03T01:00Z'),('401909927','2026-11-05T01:00Z'),
        ('401909291','2026-11-07T01:00Z'),('401909955','2026-11-10T00:30Z'),
        ('401909970','2026-11-12T01:00Z'),('401909300','2026-11-14T01:00Z'),
        ('401909983','2026-11-15T01:00Z'),('401909996','2026-11-17T00:00Z'),
        ('401910007','2026-11-19T00:00Z'))}


def require(condition,reason):
    if not condition:raise ValueError(reason)


def _http(folder,url,freeze):
    raw=(folder/'body.raw').read_bytes();receipt_raw=(folder/'receipt.json').read_bytes()
    receipt=strict_json(receipt_raw)
    require(isinstance(receipt,dict),'HISTORY_RECEIPT_SCHEMA')
    expected={'schema','url','retrieval_started_at','source_published_at','original_historical_available_at',
        'admission','correction_history_complete','predecessor_sha256','status','headers',
        'retrieval_completed_at','raw_sha256','bytes','byte_domain','ingested_at'}
    require(set(receipt)==expected and receipt.get('schema')=='nba-p1-raw-capture/1.0.0'
        and receipt.get('admission')=='UNADMITTED','HISTORY_RECEIPT_SCHEMA_OR_ADMISSION_CLAIM')
    require(receipt.get('url')==url and receipt.get('status')==200,'HISTORY_ENDPOINT_OR_HTTP_STATUS')
    require(receipt.get('raw_sha256')==digest(raw) and receipt.get('bytes')==len(raw)
        and receipt.get('byte_domain')=='HTTP_RESPONSE_BODY_BYTES','HISTORY_SOURCE_BYTES')
    require(all(receipt.get(k) is None for k in ('source_published_at','original_historical_available_at',
        'correction_history_complete','predecessor_sha256')),'UNSUPPORTED_PUBLICATION_OR_CORRECTION_CLAIM')
    a,b,c=map(native.utc,(receipt['retrieval_started_at'],receipt['retrieval_completed_at'],receipt['ingested_at']))
    require(a<=b<=c<=native.utc(freeze),'HISTORY_LATE_OR_INCONSISTENT_CLOCK')
    body=strict_json(raw);require(isinstance(body,dict),'HISTORY_BODY_SCHEMA')
    return body,dict(body_sha256=digest(raw),receipt_sha256=digest(receipt_raw),
        observed_at=receipt['retrieval_completed_at'],ingested_at=receipt['ingested_at'],
        source_published_at=None,correction_history_complete=None)


def _competition(node,game_id,date=None):
    require(str(node.get('id'))==str(game_id),'HISTORY_GAME_IDENTITY')
    comps=node.get('competitions',[])
    require(len(comps)==1,'HISTORY_COMPETITION_COUNT')
    comp=comps[0]
    require(str(comp.get('id'))==str(game_id),'HISTORY_COMPETITION_IDENTITY')
    require(comp.get('status',{}).get('type',{}).get('completed') is True,'HISTORY_NOT_COMPLETED')
    if date is not None:require(native.utc(comp['date'])==native.utc(date),'HISTORY_GAME_DATE')
    teams=comp.get('competitors',[])
    require(len(teams)==2 and len({str(t['id']) for t in teams})==2,'HISTORY_TEAM_POPULATION')
    require({t.get('homeAway') for t in teams}=={'home','away'},'HISTORY_HOME_AWAY')
    return comp


def _observation(row,index):
    state='UNKNOWN';minutes=None
    stats=row.get('stats',[]);text=stats[index] if len(stats)>index else None
    dnp=row.get('didNotPlay')
    if dnp is True:
        if stats!=[]:
            return dict(state='UNKNOWN',displayed_minutes=None,raw_display=text,
                units='ESPN_DISPLAYED_ROUNDED_MINUTES',exact_seconds=None,
                source_row_issue='DNP_NONEMPTY_CREDIT_ARRAY_UNVERIFIED',raw_credit_array=stats)
        require(text in (None,'','--','0'),'DNP_POSITIVE_MINUTE_CONFLICT')
        state='DNP'
    elif dnp is False and isinstance(text,str) and re.fullmatch(r'[0-9]+',text):
        minutes=int(text)
        require(0<=minutes<=120,'DISPLAYED_MINUTE_SUPPORT')
        state='PLAYED' if minutes>0 else 'PLAYED_ZERO_DISPLAY'
    return dict(state=state,displayed_minutes=minutes,raw_display=text,
        units='ESPN_DISPLAYED_ROUNDED_MINUTES',exact_seconds=None)


def read_team_history(history_dir,team_id,cohort):
    """Native identities only. Missing athlete rows remain UNKNOWN, never DNP."""
    root=Path(history_dir);freeze=cohort['freeze_at'];sources={}
    schedule,receipt=_http(root/('schedule-'+team_id),BASE+'teams/'+team_id+'/schedule',freeze)
    require(str(schedule.get('team',{}).get('id'))==team_id,'HISTORY_SCHEDULE_TEAM')
    sources['schedule-'+team_id]=receipt
    all_events=schedule.get('events',[])
    require(len({str(e['id']) for e in all_events})==len(all_events),'HISTORY_DUPLICATE_GAME')
    events=[e for e in all_events if native.utc(e['date'])<native.utc(cohort['start'])
        and e.get('competitions',[{}])[0].get('status',{}).get('type',{}).get('completed') is True]
    require({(str(e['id']),e['date']) for e in events}==set(HISTORY_POPULATION[team_id]),
        'HISTORY_REQUIRED_GAME_COVERAGE')
    games=[]
    for event in sorted(events,key=lambda e:(e['date'],e['id'])):
        require(native.utc(event['date'])<native.utc(freeze),'HISTORY_FUTURE_COMPLETED_GAME')
        comp=_competition(event,event['id'],event['date'])
        require(team_id in {str(t['id']) for t in comp['competitors']},'HISTORY_SCHEDULE_MEMBERSHIP')
        label='summary-'+event['id']
        body,receipt=_http(root/label,BASE+'summary?event='+event['id'],freeze);sources[label]=receipt
        header=body['header'];actual=_competition(header,event['id'],event['date'])
        expected={(str(t['id']),t['homeAway']) for t in comp['competitors']}
        require({(str(t['id']),t['homeAway']) for t in actual['competitors']}==expected,'HISTORY_SUMMARY_TEAM_JOIN')
        teams=body.get('boxscore',{}).get('players',[])
        require(len(teams)==2 and {str(t['team']['id']) for t in teams}=={t[0] for t in expected},'HISTORY_BOXSCORE_TEAM_JOIN')
        seen=set();observations={}
        for team in teams:
            stats=team.get('statistics',[])
            require(len(stats)==1 and stats[0].get('names',[]).count('MIN')==1,'HISTORY_MINUTE_COLUMN')
            stat=stats[0];index=stat['names'].index('MIN')
            for row in stat.get('athletes',[]):
                pid=str(row['athlete']['id'])
                require(pid not in seen,'HISTORY_DUPLICATE_PLAYER_IDENTITY');seen.add(pid)
                if str(team['team']['id'])==team_id:observations['espn:player:'+pid]=_observation(row,index)
        games.append(dict(game_id=event['id'],game_date=event['date'][:10],
            game_start_at=event['date'],team='espn:team:'+team_id,observations=observations,
            source_label=label))
    require(bool(games),'HISTORY_NO_PRIOR_GAMES')
    return games,sources


def _load_model(path):
    raw=Path(path).read_bytes()
    require(digest(raw)==MODEL_SHA,'UNREVIEWED_OR_ALTERED_MINUTES_ARTIFACT')
    require(digest(Path(native.__file__).read_bytes())==NATIVE_SHA,'UNREVIEWED_MINUTES_READER_CODE')
    return native.MinutesModel(**strict_json(raw))


def run_p3(source_raw,capture_dir,cohort,*,history_dir,model_path,forecast_at):
    require(digest(canonical(cohort))==COHORT_SHA,'UNREVIEWED_P3_COHORT_OR_SCOPE')
    handoff=read_requests(source_raw,capture_dir,cohort)
    require(native.utc(cohort['freeze_at'])<=native.utc(forecast_at)<native.utc(cohort['start']),'P3_FORECAST_CLOCK')
    frozen=cohort.get('frozen_candidates')
    if frozen is not None:
        require(frozen==[dict(player_id=r['player_id'],team_id=r['team_id'],name=r['name'])
            for r in handoff['requests']['rows']],'P3_FROZEN_CANDIDATE_POPULATION')
    model=None;model_error=None
    try:
        model=_load_model(model_path)
        require(native.utc(model.training_cutoff_at)<=native.utc(cohort['freeze_at']),'P3_MODEL_AFTER_FREEZE')
    except (OSError,ValueError) as exc:model_error=str(exc)
    histories={};source_manifest={};team_errors={};rosters={}
    for tid in cohort['teams']:
        try:
            histories[tid],source_manifest[tid]=read_team_history(history_dir,tid,cohort)
            roster=strict_json((Path(capture_dir)/('roster-'+tid)/'body.raw').read_bytes())
            require(str(roster['team']['id'])==tid,'P3_CURRENT_ROSTER_TEAM')
            rosters[tid]={}
            for row in roster['athletes']:
                pid='espn:player:'+str(row['id'])
                require(pid not in rosters[tid],'P3_DUPLICATE_CURRENT_ROSTER_IDENTITY')
                rosters[tid][pid]=row
        except (OSError,KeyError,ValueError,TypeError,IndexError,AttributeError) as exc:team_errors[tid]=type(exc).__name__+':'+str(exc)
    rows=[];observations=[]
    for request in handoff['requests']['rows']:
        pid=request['player_id'];tid=request['team_id'].removeprefix('espn:team:')
        reason=None;features=None;position=None;history=[];gap=None
        missing=[dict(game_id=gid,observations={}) for gid,date in HISTORY_POPULATION.get(tid,())]
        for game in histories.get(tid,missing):
            obs=game['observations'].get(pid,dict(state='UNKNOWN',displayed_minutes=None,raw_display=None,units='ESPN_DISPLAYED_ROUNDED_MINUTES',exact_seconds=None))
            observations.append(dict(player_id=pid,team_id=request['team_id'],game_id=game['game_id'],
                source_rejection=team_errors.get(tid),**obs))
            if obs['state']=='PLAYED':history.append(dict(game_date=game['game_date'],game_id=game['game_id'],workload=obs['displayed_minutes'],team=game['team']))
        try:
            require(request['source_request_status']=='SOURCE_READY_CONDITIONAL_REQUEST','P1_SOURCE_ABSTENTION')
            require(model_error is None,'P3_MODEL_UNAVAILABLE:'+str(model_error))
            require(tid not in team_errors,'P3_HISTORY_UNAVAILABLE:'+str(team_errors.get(tid)))
            require(len(history)>=5,'INSUFFICIENT_PRIOR_APPEARANCES')
            last=history[-1]['game_id'];after=False;gap=0
            for game in histories[tid]:
                if after:
                    obs=game['observations'].get(pid,{'state':'UNKNOWN'})
                    require(obs['state']=='DNP','UNKNOWN_RETURN_GAP_POPULATION')
                    gap+=1
                if game['game_id']==last:after=True
            # A rounded zero or missing row between selected played games must
            # not silently disappear from a last-five/ten workload feature.
            start=history[-10:][0]['game_id'];in_window=False
            for game in histories[tid]:
                if game['game_id']==start:in_window=True
                if in_window:
                    require(game['observations'].get(pid,{'state':'UNKNOWN'})['state'] in ('PLAYED','DNP'),
                        'UNKNOWN_CONDITIONAL_HISTORY_WINDOW')
            position_info=rosters[tid][pid].get('position')
            require(isinstance(position_info,dict),'P3_POSITION_UNAVAILABLE')
            position=position_info.get('abbreviation')
            require(position in ('PG','SG','SF','PF','G','F','C','G-F','F-C'),'P3_POSITION_UNAVAILABLE')
            own=next(t for t in cohort['teams'] if t==tid)
            scoreboard=strict_json((Path(capture_dir)/'scoreboard/body.raw').read_bytes())
            event=next(e for e in scoreboard['events'] if str(e['id'])==cohort['game_id'])
            competitor=next(t for t in event['competitions'][0]['competitors'] if str(t['id'])==own)
            require(competitor.get('homeAway') in ('home','away'),'P3_HOME_AWAY_UNKNOWN')
            features=native.causal_features(history,game_date=cohort['start'][:10],team=request['team_id'],home=competitor['homeAway']=='home',prior_team_games_missed=gap)
        except (ValueError,KeyError,StopIteration) as exc:reason=str(exc)
        for name in MODELS:
            forecast=None
            if reason is None:
                sources=source_manifest[tid]
                available=max((s['observed_at'] for s in sources.values()),key=native.utc)
                ingested=max((s['ingested_at'] for s in sources.values()),key=native.utc)
                native_input=native.PregameOpportunityInput(game_id=cohort['game_id'],player_id=pid,
                    team_id=request['team_id'],opponent_id='espn:team:'+next(t for t in cohort['teams'] if t!=tid),
                    event_start_at=cohort['start'],forecast_at=forecast_at,input_freeze_at=cohort['freeze_at'],
                    source_available_at=available,source_ingested_at=ingested,
                    training_cutoff_at=model.training_cutoff_at,source_sha256=digest(canonical(dict(p1=handoff['payload_sha256'],history=sources))),
                    features=features,position=position,reliability_reasons=('CURRENT_TEAM_OBSERVED_WINDOW_ONLY','DISPLAYED_ROUNDED_MINUTES','EXPLORATORY_MODEL_TRAINING_SOURCE_NOT_AUTHENTICATED','UTC_DATE_REST_PROXY'))
                forecast=model.forecast(name,native_input,seed=20261119)
            rows.append(dict(game_id=cohort['game_id'],player_id=pid,team_id=request['team_id'],model=name,
                status='CONDITIONAL_MINUTES_RESEARCH' if forecast else 'ABSTAIN',reason=reason,
                conditioning='conditional_on_participation',participation_probability=None,legal_eligibility=None,
                actual_native_model_executed=forecast is not None,forecast=forecast,
                features=features,position=position,prior_positive_appearances=len(history),explicit_dnp_return_gap=gap))
    payload=dict(schema=VERSION,stage='P3',profile='source_listed_subset',
        p1_handoff_sha256=handoff['payload_sha256'],implementation_sha256=digest(Path(__file__).read_bytes()),
        model_raw_sha256=MODEL_SHA if model else None,native_reader_raw_sha256=NATIVE_SHA,
        model_admission='PINNED_EXPLORATORY_WS2_REUSE_ONLY',source_admission='RESEARCH_BYTES_CONSISTENCY_ONLY',
        source_manifest=source_manifest,team_errors=team_errors,
        history_scope='CURRENT_TEAM_OBSERVED_WINDOW',other_team_history_complete=None,
        source_publication_known=False,correction_history_complete=None,
        forecast_at=forecast_at,input_freeze_at=cohort['freeze_at'],event_start_at=cohort['start'],
        forecast_horizon_seconds=(native.utc(cohort['start'])-native.utc(forecast_at)).total_seconds(),
        candidate_denominator=len(handoff['requests']['rows']),attempt_denominator=len(rows),
        forecasted_rows=sum(r['forecast'] is not None for r in rows),abstained_rows=sum(r['forecast'] is None for r in rows),
        observation_denominator=len(observations),observations=observations,rows=rows,
        team_allocation_performed=False,production_release=False)
    return dict(payload,payload_sha256=digest(canonical(payload)))


def read_p3(raw,*,source_raw,capture_dir,cohort,history_dir,model_path,forecast_at):
    value=strict_json(raw)
    expected=run_p3(source_raw,capture_dir,cohort,history_dir=history_dir,model_path=model_path,forecast_at=forecast_at)
    require(canonical(value)==canonical(expected),'P3_SOURCE_MODEL_OR_OUTPUT_MISMATCH')
    return value
