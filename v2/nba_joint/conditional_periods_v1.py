"""Versioned, source-equivalent period transitions for NBA OT conditioning.

Every shot/rebound/foul/clock transition below is copied directly from the
frozen residual_events_v1._event_path and retains its parameters. Only the
period boundary checkpointing and the conditioning algorithm are new.

This module is NOT a production replacement and finite-run PIMH is not
a perfect sampler: its marginal target is exact at stationarity; burn-in and
Monte Carlo convergence must be independently established.
"""
import copy
import math
import numpy as np
from scipy.special import gammainc,gammaincinv
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_joint.common import rng_for,combos
from v2.nba_joint.residual_events_v1 import (
    COUNTS,PathExecutionFailure,_pick,_oncourt,event_path as original_event_path)
from v2.nba_joint.residual_audit_v1 import audit_path

SCHEMA = 'nba-ot-conditional-bootstrap-pimh/1'


def empty_state(fixed):
    teams=fixed['teams'];actors=fixed['actors']
    return dict(ledger=[],counts={t:[{s:0 for s in COUNTS} for a in actors[t]]
                                  for t in teams},
                score={t:0 for t in teams},period_scores=[],t=0.,
                offense=None,opening_jump_winner=None,completed_periods=0)


def period_transition(fixed,state,rng,period,event_budget=4096):
    """Unconditional transition, exactly equivalent to the original kernel.

    The RNG here is the same NumPy Generator for consecutive periods.
    The state contains the complete sufficient path history (including
    personal fouls, lineup, score, clock, and original jump entitlement).
    """
    teams=fixed['teams'];actors=fixed['actors'];length=fixed['length']
    k=fixed['overtime_count']
    require(type(period) is int and period==state['completed_periods']+1 and
            1<=period<=4+k,'PIMH_PERIOD_SEQUENCE')
    counts=copy.deepcopy(state['counts']);score=state['score'].copy()
    ledger=copy.deepcopy(state['ledger']);t=state['t']
    offense=state['offense'];opening_jump_winner=state['opening_jump_winner']
    if period==1:
        require(offense is None and opening_jump_winner is None and t==0.,
                'PIMH_INITIAL_STATE')
        offense=teams[int(rng.integers(2))]
        opening_jump_winner=offense
    ep=fixed['event_probabilities'];remaining_shot=24.;reset_limit=24.
    rotation_boundaries=sorted({s['end'] for team in teams for s in fixed['O'][team]['segments']}|{0.,length})
    ends=[12.,24.,36.,48.]+[48.+5*j for j in range(1,k+1)]
    period_scores=state['period_scores'][:];current_period=period
    def emit(kind,**data):
        require(len(ledger)<event_budget,'REAL_J_EVENT_BUDGET_EXHAUSTED')
        row=dict(index=len(ledger),elapsed=t,period=current_period,kind=kind,offense=offense,
            score=score.copy(),**data);ledger.append(row);return row['index']
    def increment(team,i,stat,value=1):counts[team][i][stat]+=value
    def other(team):return teams[1] if team==teams[0] else teams[0]
    for period,end in [(period,ends[period-1])]:
        current_period=period;remaining_shot=24.;reset_limit=24.
        if period in (2,3):offense=other(opening_jump_winner)
        elif period==4:offense=opening_jump_winner
        elif period>4:offense=teams[int(rng.integers(2))]
        emit('PERIOD_START',on_court={team:_oncourt(fixed,team,t) for team in teams},
            opening_possession_type='FAIR_MODEL_JUMP_BALL' if period==1 or period>4 else 'NBA_QUARTER_ENTITLEMENT')
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
        # Conditioning occurs at the SMC stage boundary, not inside the
        # unconditional continuation transition.

    return dict(ledger=ledger,counts=counts,score=score,period_scores=period_scores,
                t=t,offense=offense,opening_jump_winner=opening_jump_winner,
                completed_periods=period)


def stage_transition(fixed,prefix,rng,stage,*,event_budget=4096):
    """Stage 0=all regulation, stage j>=1=OT j. All prior states copied."""
    k=fixed['overtime_count']
    require(type(stage) is int and 0<=stage<=k,'PIMH_INVALID_STAGE')
    require(prefix['completed_periods']==(0 if stage==0 else 3+stage),
            'PIMH_PREFIX_STAGE_MISMATCH')
    state=prefix
    periods=range(1,5) if stage==0 else (4+stage,)
    for period in periods:
        state=period_transition(fixed,state,rng,period,event_budget=event_budget)
    tied=state['score'][fixed['teams'][0]]==state['score'][fixed['teams'][1]]
    expected=stage<k
    return state,tied==expected


def finalize_path(fixed,state):
    require(state['completed_periods']==4+fixed['overtime_count'],
            'PIMH_INCOMPLETE_PATH')
    out=copy.deepcopy(state)
    for team in fixed['teams']:
        for stats in out['counts'][team]:combos(stats)
    result=dict(status='ACCEPTED_PATH_PROPOSAL',ledger=out['ledger'],
                counts=out['counts'],period_scores=out['period_scores'],
                attempt=-1)
    audit_path(fixed,result)
    return result


def source_transition_fidelity(fixed,seed,attempt):
    """Exact path match on every **unconditional** trajectory.

    It is intentional that a path rejected by the old whole-path model
    can be accepted as an unconditional period-transition checkpoint.
    """
    rng=rng_for(seed,fixed['game_id'],fixed['index'],
                'event-path:'+str(attempt))
    state=empty_state(fixed)
    for stage in range(fixed['overtime_count']+1):
        state,_=stage_transition(fixed,state,rng,stage)
    old=original_event_path(fixed,seed,attempt)
    if old['status']=='ACCEPTED_PATH_PROPOSAL':
        new=finalize_path(fixed,state)
        require(canonical(old['ledger'])==canonical(new['ledger']) and
                canonical(old['counts'])==canonical(new['counts']) and
                canonical(old['period_scores'])==canonical(new['period_scores']),
                'PIMH_ORIGINAL_KERNEL_DRIFT_ACCEPTED')
    else:
        # For rejected original paths compare only the already-produced
        # regulation/OT prefix; the old kernel stops at the first violation.
        n=len(old['ledger'])
        require(canonical(old['ledger'])==canonical(state['ledger'][:n]),
                'PIMH_ORIGINAL_KERNEL_DRIFT_REJECTED_PREFIX')
    return dict(old_status=old['status'],ledger_prefix_identical=True,
                original_ledger_length=len(old['ledger']))
