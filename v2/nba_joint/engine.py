"""Deterministic, scenario-keyed game simulation with transparent abstention."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import json
import time
import numpy as np
from .common import sha, instant, rng_for, combos, STATS
from .state import sample_state
from .opportunity import allocate, ADAPTER_VERSION
from .events import sample_events


def validate(game,model,n):
    if type(n)!=int or n<1:raise ValueError('INVALID_SCENARIO_COUNT')
    if game['mode'] not in ('synthetic','historical','prospective'):raise ValueError('INVALID_MODE')
    if len(game['teams'])!=2 or len(set(game['teams']))!=2:raise ValueError('TEAM_IDENTITY')
    players=game['players'];ids=[p['player_id'] for p in players]
    if len(set(ids))!=len(ids):raise ValueError('DUPLICATE_PLAYER')
    cutoff=instant(game['analysis_cutoff_at'])
    if instant(model['training_cutoff_at'])>cutoff or instant(model['minutes']['training_cutoff_at'])>cutoff:
        raise ValueError('TRAINING_CUTOFF_VIOLATION')
    for p in players:
        if p['team_id'] not in game['teams'] or p['opponent_id']!=next(t for t in game['teams'] if t!=p['team_id']):raise ValueError('PLAYER_TEAM_IDENTITY')
        if p['last_observation_date']>=game['game_date']:raise ValueError('FUTURE_PLAYER_FEATURE')
        if game['game_id'] in p['history_game_ids']:raise ValueError('SAME_GAME_OUTCOME')
        if set(p['rates'])!=set(STATS[:4]) or any(not np.isfinite(v) or v<0 for v in p['rates'].values()):raise ValueError('INVALID_PLAYER_RATE')
        probability=p.get('participation_probability')
        if probability is not None and (isinstance(probability,bool) or not np.isfinite(probability) or not 0<=probability<=1):raise ValueError('INVALID_PARTICIPATION_PROBABILITY')
        if p.get('eligible') is False and probability not in (0,None):raise ValueError('INACTIVE_PARTICIPATION_CONFLICT')
    if game['mode']=='prospective':
        # Only the strict WS1 adapter may create this mode. No boolean can certify it.
        from .sources import validate_prospective
        validate_prospective(game,model)


def simulate(game,model,*,n=128,seed=20261115,exposure='M0',dependence='J2',state_kind='G1'):
    validate(game,model,n)
    if dependence not in ('J1','J2'):raise ValueError('UNKNOWN_DEPENDENCE')
    start=time.perf_counter();players=game['players'];np_=len(players)
    ix=[np.array([i for i,p in enumerate(players) if p['team_id']==team]) for team in game['teams']]
    if any(len(i)<5 for i in ix):raise ValueError('FEWER_THAN_FIVE_CANDIDATES')
    minutes=[];desired=[];states=[];stats=[];witnesses=[];ledgers=[];scenario_ids=[]
    timing={'state':0.,'opportunity':0.,'events':0.}
    for j in range(n):
        sid=f'{game["game_id"]}/{seed}/{j}';scenario_ids.append(sid)
        t=time.perf_counter();state=sample_state(model['state'],rng_for(seed,game['game_id'],j,'state'),kind=state_kind);timing['state']+=time.perf_counter()-t
        m=np.zeros(np_);raw=np.zeros(np_);segments=[]
        t=time.perf_counter()
        for team,i in zip(game['teams'],ix):
            try:
                m[i],raw[i],seg,active=allocate([players[k] for k in i],model,state,rng_for(seed,game['game_id'],j,'minutes/'+team),name=exposure,constrained=dependence=='J2',conditional=game['conditional_on_roster'])
            except ValueError as exc:
                raise ValueError(f'{exc};scenario={sid};attempted={j+1};completed={j};no_partial_forecast') from exc
            segments.append(seg)
        timing['opportunity']+=time.perf_counter()-t
        t=time.perf_counter();c,ledger=sample_events(players,m,ix,state,model,rng_for(seed,game['game_id'],j,'events'),constrained=dependence=='J2');timing['events']+=time.perf_counter()-t
        stats.append(c);states.append(state);minutes.append(m);desired.append(raw);witnesses.append(segments);ledgers.append(ledger)
    counts={k:np.stack([c[k] for c in stats]) for k in stats[0]};combos(counts)
    out=dict(schema='NBAJointScenarios/1.0.0',mode=game['mode'],conditional_on_roster=game['conditional_on_roster'],game=copy.deepcopy(game),model=copy.deepcopy(model),players=copy.deepcopy(players),
             input_sha256=sha(game),model_sha256=sha(model),seed=seed,n=n,exposure=exposure,dependence=dependence,opportunity_adapter=ADAPTER_VERSION,
             scenario_ids=scenario_ids,minutes=np.asarray(minutes),independent_minutes=np.asarray(desired),stats=counts,
             state={k:np.asarray([s[k] for s in states]) for k in ('duration','overtime','regulation_possession_proxy','team_possession_proxy','offensive_effect')},
             team_indices=[i.tolist() for i in ix],lineup_segments=witnesses,event_ledgers=ledgers,
             timing={**timing,'wall_seconds':time.perf_counter()-start},attempted_scenarios=n,rejected_scenarios=0)
    out['output_sha256']=sha({'input':out['input_sha256'],'model':out['model_sha256'],'seed':seed,'exposure':exposure,'dependence':dependence,'state_kind':state_kind,'state':{k:v.tolist() for k,v in out['state'].items()},'minutes':out['minutes'].tolist(),'stats':{k:v.tolist() for k,v in counts.items()},'event_ledgers':ledgers})
    if dependence=='J2':
        from .invariants import audit
        audit(out)
    return out


def synthetic_fixture():
    """Controlled assumptions only. Constants are not historical estimates."""
    from v2.nba_opportunity import FEATURES
    minute=json.loads((Path(__file__).resolve().parents[2]/'research/nba_ws2/results/model.json').read_text())
    model=dict(schema='NBAJointModel/0.1.0',training_cutoff_at=minute['training_cutoff_at'],minutes=minute,
        state=dict(pace_mean=100.,ot_probability=.08,ot_continuation=.2,log_cov=[[.004,.001,.001],[.001,.008,.002],[.001,.002,.008]]),
        events=dict(p2=.54,p3=.36,pft=.78,ft_share=.25,rebound_credit=.9,offensive_rebound_share=.24,terminal_ft_fraction=.44,assist_fraction=.6),
        provenance=dict(synthetic=True,source_hashes=[],substitution='WS3 unavailable; aggregate event baseline'))
    game=dict(schema='NBAJointInput/1',game_id='fixture:game:1',teams=['fixture:team:1','fixture:team:2'],game_date='2026-11-16',event_start_at='2026-11-16T00:00:00Z',
        analysis_cutoff_at='2026-11-15T00:00:00Z',forecast_at='2026-11-15T00:00:00Z',mode='synthetic',conditional_on_roster=True,source_hashes=[],players=[])
    for t,team in enumerate(game['teams']):
        for i in range(9):
            mean=34.-i*2.5
            features=dict(zip(FEATURES,[mean,mean,mean,6.,0.,3.,0.,0.,0.,float(t==0),10.,float(mean>=28),float(mean<14)]))
            game['players'].append(dict(player_id=f'fixture:player:{t*9+i}',team_id=team,opponent_id=game['teams'][1-t],position='G',eligible=True,
                participation_probability=None,minute_features=features,last_observation_date='2026-11-13',history_game_ids=['fixture:game:0'],
                rates=dict(points=.65-.025*i,rebounds=.22,assists=.16-.01*i,threes=.08-.006*i),history_stats={k:[4,8,12] for k in STATS[:4]}))
    return game,model
