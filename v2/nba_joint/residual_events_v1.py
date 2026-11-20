"""Chronological shadow event law with explicit anonymous residual actors.

This NEW law uses S parameters as working priors. It does not preserve S1
marginals, claim calibrated possession clocks, or replace the accepted G0 J.
Each fixed G/O/rate scenario has its own OT-conditioned path kernel. Rejected
paths stay in the execution receipt; exhaustion rejects the whole execution.
"""
import math
import numpy as np
from scipy.special import gammainc, gammaincinv
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_joint.common import rng_for,combos
from v2.nba_joint.residual_opportunity_v1 import draw_team,audit_team

VERSION='conditional-residual-forward-J/1'
COUNTS=('points','rebounds','assists','threes','fgm','fga','ftm','fta','oreb','dreb','turnovers','fouls')


class PathExecutionFailure(ValueError):
    def __init__(self,error,partial):
        super().__init__(str(error));self.partial=partial


def _beta(rng,p):
    value=float(rng.beta(p['alpha'],p['beta']))
    require(math.isfinite(value) and 0<value<1,'REAL_J_BETA_NUMERIC')
    return value


def _pick(rng,indices,weights):
    require(bool(indices) and len(indices)==len(weights),'REAL_J_EMPTY_OPPORTUNITY')
    w=np.asarray(weights,dtype=float)
    require(np.all(np.isfinite(w)) and np.all(w>=0) and w.sum()>0,'REAL_J_OPPORTUNITY_WEIGHTS')
    return indices[int(rng.choice(len(indices),p=w/w.sum()))]


def fixed_scenario(model,seed,index,*,zero_weight=None,rate_budget=4096):
    require(type(seed) is int and type(index) is int and index>=0,'REAL_J_SEED_SCENARIO')
    rng=rng_for(seed,model['target'],index,'fixed-G-O-rate')
    players=model['named_players'];teams=sorted({p['team_id'] for p in players})
    require(len(teams)==2,'REAL_J_TWO_TEAMS')
    ots={(p['minutes']['ot_probability'],p['minutes']['ot_continuation']) for p in players}
    require(len(ots)==1,'REAL_J_SHARED_OT_PRIOR')
    p,q=next(iter(ots));k=int(rng.geometric(1-q)) if rng.random()<p else 0
    length=48+5*k;draws={};actors={};rate_rejections=[]
    for team in teams:
        group=[p for p in players if p['team_id']==team]
        draw=draw_team(group,length,rng,fixed_zero_weight=zero_weight);audit_team(draw,length);draws[team]=draw
        actors[team]=[];byid={p['player_id']:p for p in group};residual=None
        for i,a in enumerate(draw['actors']):
            spec=byid[a['player_id']] if a['player_id'] else model['residual_groups'][team]
            if a['player_id'] is None and residual is not None:
                params=residual.copy()
            else:
                params=None
                for attempt in range(rate_budget):
                    rates={s:float(rng.gamma(v['alpha'],1/v['beta'])) for s,v in spec['rates'].items()}
                    require(all(math.isfinite(v) and v>0 for v in rates.values()),'REAL_J_RATE_NUMERIC')
                    if rates['points']>=3*rates['threes']:
                        params=dict(rates=rates,p3=_beta(rng,spec['conversion3']),p2=_beta(rng,spec['conversion2']),
                            pft=_beta(rng,spec['conversion_ft']),ft_share=_beta(rng,spec['ft_non3_point_share']))
                        break
                    rate_rejections.append(dict(team=team,actor_index=i,attempt=attempt,rates=rates,
                        reason='SOURCE_WORKING_POINT_RATE_BELOW_THREE_POINT_RATE'))
                require(params is not None,'REAL_J_RATE_BUDGET_EXHAUSTED')
                if a['player_id'] is None:residual=params.copy()
            actors[team].append(dict(identity=a,index=i,**params))
    pace=float(rng.gamma(model['pace']['shape'],model['pace']['scale']))
    require(math.isfinite(pace) and pace>0,'REAL_J_PACE_NUMERIC')
    global_events={name:_beta(rng,value) for name,value in model['events'].items()}
    return dict(schema='fixed-real-J-scenario/1',index=index,seed=seed,game_id=model['target'],
        overtime_count=k,length=length,teams=teams,O=draws,actors=actors,pace=pace,event_probabilities=global_events,
        rate_rejections=rate_rejections,zero_weight_sensitivity=zero_weight,
        genuine_participation_probability=None,complete_legal_roster_claim=False,
        source_derived_working_priors_not_unchanged_S_marginals=True)


def _oncourt(fixed,team,t):
    for s in fixed['O'][team]['segments']:
        if s['start']<=t<s['end']:return s['player_indices']
    raise ValueError('REAL_J_NO_LINEUP_AT_CLOCK')


def _event_path(fixed,seed,attempt,*,event_budget=4096,capture):
    """One path proposal; discrete rebounds resolve at reported shot-clock time.

    Baseline excludes disqualifications, steals, blocks, technicals, and-and-one
    sequences. Shooting fouls are possible only while an on-court defender has
    fewer than five personals. These are model restrictions, not data claims.
    """
    rng=rng_for(seed,fixed['game_id'],fixed['index'],'event-path:'+str(attempt))
    teams=fixed['teams'];actors=fixed['actors'];length=fixed['length'];k=fixed['overtime_count']
    counts={t:[{s:0 for s in COUNTS} for a in actors[t]] for t in teams}
    score={t:0 for t in teams};ledger=[];t=0.;offense=teams[int(rng.integers(2))]
    capture.update(ledger=ledger,counts=counts,score=score,attempt=attempt)
    ep=fixed['event_probabilities'];remaining_shot=24.;reset_limit=24.
    rotation_boundaries=sorted({s['end'] for team in teams for s in fixed['O'][team]['segments']}|{0.,length})
    ends=[12.,24.,36.,48.]+[48.+5*j for j in range(1,k+1)]
    period_scores=[];current_period=1
    def emit(kind,**data):
        require(len(ledger)<event_budget,'REAL_J_EVENT_BUDGET_EXHAUSTED')
        row=dict(index=len(ledger),elapsed=t,period=current_period,kind=kind,offense=offense,
            score=score.copy(),**data);ledger.append(row);return row['index']
    def increment(team,i,stat,value=1):counts[team][i][stat]+=value
    def other(team):return teams[1] if team==teams[0] else teams[0]
    for period,end in enumerate(ends,1):
        current_period=period;remaining_shot=24.;reset_limit=24.
        emit('PERIOD_START',on_court={team:_oncourt(fixed,team,t) for team in teams})
        while t<end-1e-10:
            defending=other(offense);start=t
            # Inverse-CDF draw from an actually truncated gamma, no floor/clip.
            mean=24./fixed['pace'];scale=mean/4
            mass=float(gammainc(4,remaining_shot/60/scale))
            u=float(rng.random())*mass
            duration=60*scale*float(gammaincinv(4,u))
            require(math.isfinite(duration) and 0<duration<=remaining_shot+1e-9,'REAL_J_CLOCK_NUMERIC')
            terminal=start+duration/60
            if terminal>=end:
                for boundary in rotation_boundaries:
                    if start<boundary<end:
                        t=boundary
                        emit('DEFLECTION_OUT_OF_BOUNDS',shot_clock_remaining=remaining_shot-60*(boundary-start),
                            on_court={team:_oncourt(fixed,team,t) for team in teams})
                t=end;emit('PERIOD_HOLD_END',possession_started=start,shot_clock_elapsed=(end-start)*60,
                    shot_clock_before=remaining_shot);break
            # Planned changes are explicit deflection out-of-bounds dead balls.
            # Carry the shot clock across them; they do not create extra time.
            for boundary in rotation_boundaries:
                if start<boundary<=terminal:
                    t=boundary;remaining_shot-=60*(boundary-start);start=boundary
                    emit('DEFLECTION_OUT_OF_BOUNDS',shot_clock_remaining=remaining_shot,
                        on_court={team:_oncourt(fixed,team,t) for team in teams})
            t=terminal;remaining_shot-=60*(terminal-start)
            own=_oncourt(fixed,offense,t);opp=_oncourt(fixed,defending,t)
            eligible_foul=[i for i in opp if counts[defending][i]['fouls']<5]
            opportunities=[];weights=[]
            for i in own:
                a=actors[offense][i];r=a['rates'];non3=r['points']-3*r['threes']
                for kind,w in (('3',r['threes']/a['p3']),('2',non3*(1-a['ft_share'])/(2*a['p2'])),
                    ('FT',non3*a['ft_share']/(a['pft']*(2+ep['shooting_ft_three_series'])) if eligible_foul else 0),
                    ('TO',r['turnovers'])):
                    opportunities.append((i,kind));weights.append(w)
            shooter,kind=_pick(rng,opportunities,weights)
            new_possession=True;live_miss=None
            if kind=='TO':
                increment(offense,shooter,'turnovers');emit('TURNOVER_OUT_OF_BOUNDS',team=offense,actor=shooter)
            elif kind in ('2','3'):
                a=actors[offense][shooter];made=bool(rng.random()<(a['p3'] if kind=='3' else a['p2']))
                increment(offense,shooter,'fga');assist=None
                if made:
                    increment(offense,shooter,'fgm');increment(offense,shooter,'points',int(kind));score[offense]+=int(kind)
                    if kind=='3':increment(offense,shooter,'threes')
                    peers=[i for i in own if i!=shooter]
                    if rng.random()<ep['assisted_fg']:
                        assist=_pick(rng,peers,[actors[offense][i]['rates']['assists'] for i in peers])
                        increment(offense,assist,'assists')
                shot=emit('FIELD_GOAL',team=offense,actor=shooter,value=int(kind),made=made,assist=assist,
                    shot_clock_remaining=remaining_shot,reset_limit=reset_limit)
                if not made:live_miss=shot
            else:
                fouler=_pick(rng,eligible_foul,[1.]*len(eligible_foul));increment(defending,fouler,'fouls')
                n=3 if rng.random()<ep['shooting_ft_three_series'] else 2
                foul=emit('SHOOTING_FOUL',team=defending,actor=fouler,shooter_team=offense,shooter=shooter,attempts=n,
                    shot_clock_remaining=remaining_shot,reset_limit=reset_limit)
                for number in range(1,n+1):
                    made=bool(rng.random()<actors[offense][shooter]['pft']);increment(offense,shooter,'fta')
                    if made:increment(offense,shooter,'ftm');increment(offense,shooter,'points');score[offense]+=1
                    ft=emit('FREE_THROW',team=offense,actor=shooter,number=number,attempts=n,made=made,foul=foul)
                    if not made and number==n:live_miss=ft
            if live_miss is not None:
                offensive=bool(rng.random()<ep['offensive_rebound']);team=offense if offensive else defending
                credited=bool(rng.random()<ep['credited_rebound']);who=None
                if credited:
                    active=_oncourt(fixed,team,t)
                    who=_pick(rng,active,[actors[team][i]['rates']['rebounds'] for i in active])
                    increment(team,who,'rebounds');increment(team,who,'oreb' if offensive else 'dreb')
                emit('REBOUND',team=team,actor=who,miss=live_miss,offensive=offensive,
                    credited=credited,resolution='INSTANT_AT_REPORTED_CLOCK_MODEL_ASSUMPTION')
                new_possession=not offensive
            if new_possession:offense=defending;remaining_shot=24.;reset_limit=24.
            else:remaining_shot=14.;reset_limit=14.
        t=end;period_scores.append(score.copy());emit('PERIOD_END')
        tied=score[teams[0]]==score[teams[1]]
        # Early reject paths whose already observed period score violates K.
        if period>=4 and tied!=(period<4+k):
            return dict(status='REJECT_OT_PATTERN',ledger=ledger,counts=counts,period_scores=period_scores,
                reason='FIXED_G_OT_COUNT_REQUIRES_DIFFERENT_TIE_PATTERN',attempt=attempt)
    for team in teams:
        for stat in counts[team]:combos(stat)
    return dict(status='ACCEPTED_PATH_PROPOSAL',ledger=ledger,counts=counts,period_scores=period_scores,attempt=attempt)


def event_path(fixed,seed,attempt,*,event_budget=4096):
    partial={}
    try:return _event_path(fixed,seed,attempt,event_budget=event_budget,capture=partial)
    except ValueError as exc:raise PathExecutionFailure(exc,partial) from exc


def simulate(model,*,seed=20261120,n=32,path_budget=4096,event_budget=4096,zero_weight=None):
    require(type(n) is int and n>0 and type(path_budget) is int and path_budget>0,'REAL_J_EXECUTION_BUDGET')
    scenarios=[];failed=[]
    for i in range(n):
        try:fixed=fixed_scenario(model,seed,i,zero_weight=zero_weight)
        except ValueError as exc:
            failed.append(dict(index=i,stage='FIXED_SCENARIO',error=str(exc)));continue
        proposals=[];accepted=None
        for attempt in range(path_budget):
            try:proposal=event_path(fixed,seed,attempt,event_budget=event_budget)
            except PathExecutionFailure as exc:
                proposals.append(dict(attempt=attempt,status='REJECT_EXECUTION',error=str(exc),partial_path=exc.partial))
                # Numeric/budget failures are not statistical rejections.
                break
            proposals.append(proposal)
            if proposal['status']=='ACCEPTED_PATH_PROPOSAL':accepted=attempt;break
        record=dict(fixed=fixed,proposals=proposals,accepted_attempt=accepted)
        scenarios.append(record)
        if accepted is None:failed.append(dict(index=i,stage='EVENT_PATH',error='NO_ACCEPTED_PATH_WITHIN_DECLARED_EXECUTION'))
    payload=dict(schema=VERSION,model_raw_sha256=digest(canonical(model)),seed=seed,n_requested=n,
        scenario_denominator=n,scenarios=scenarios,failed=failed,status='FAILED_WHOLE_RUN' if failed else 'ENGINEERING_SAMPLE',
        scenarios_dropped=0,path_budget=path_budget,event_budget=event_budget,
        source_candidates=35,primitive_attempts=140,conditional_named_players=14,
        genuine_participation_probability=None,marginal_fidelity_accepted=False,production_release=False)
    payload['payload_sha256']=digest(canonical(payload));return payload
