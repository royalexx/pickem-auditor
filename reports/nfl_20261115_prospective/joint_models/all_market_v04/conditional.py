"""Versioned conditional allocation stage for the existing WS4 game_once.

Aggregate historical game-average yard marks, not fabricated play tracking.
No defensive exposure defaults, sportsbook synthesis, or final-draw shuffling.
"""
from collections import defaultdict
import copy
import hashlib
import numpy as np

VERSION = 'ws4_all_market_v0.4.0'
MARKETS = ('pass_attempts','completions','passing_yards','rushing_attempts',
 'rushing_yards','targets','receptions','receiving_yards','tackles_assists',
 'rushing_receiving_yards','passing_rushing_yards')
COUNTS = set(MARKETS)-{'passing_yards','rushing_yards','receiving_yards',
 'rushing_receiving_yards','passing_rushing_yards'}


def require(ok, reason):
    if not ok: raise ValueError(reason)


def allocations(rng, n, weights, uncertain, concentration):
    w=np.asarray(weights,dtype=float)
    require(np.all(np.isfinite(w)) and np.all(w>=0) and np.isclose(w.sum(),1,atol=1e-9), 'INVALID_ALLOCATION_BUDGET')
    if uncertain:
        positive=w>0
        v=rng.gamma(w[positive]*concentration,1)
        w[positive]=v/v.sum()
    return rng.multinomial(n,w)


def mark(rng, marks, uncertain):
    require(bool(marks) and np.all(np.isfinite(marks)), 'MISSING_SIGNED_HISTORY_MARKS')
    # Each mark is a historical player-game yards/opportunity ratio. Rounding
    # retains integer official-yard support without imposing nonnegative gains.
    return int(round(float(rng.choice(marks) if uncertain else np.mean(marks))))


def extend_game(event,rng,model,script):
    from joint_simulator import game_once
    require(model in ('J1','J2','J3'), 'MODEL_UNKNOWN')
    require(model!='J3' or event.get('certified_scenario_parameters'), 'J3_SOURCE_SCENARIOS_UNAVAILABLE')
    skeleton=copy.deepcopy(event)
    skeleton.pop('all_market_parameters',None)
    for t in skeleton['teams']:
        t['players']=[p for p in t['players'] if p['role']=='QB']
        for p in t['players']: p.pop('rush_share',None)
    out,state=game_once(skeleton,rng,model,script)
    out=defaultdict(int,{k:v for k,v in out.items() if k[1]=='pass_attempts'})
    uncertain=model in ('J2','J3')
    params=event['all_market_parameters']
    for t in event['teams']:
        tid=t['team_id']; st=state[tid]; par=params[tid]
        ps=par['players']; q=t['starter_qb_id']; residual=tid+':RESIDUAL'
        target_weights=[p['target_share'] for p in ps]
        rush_weights=[p['rush_share'] for p in ps]
        # Residual absorbs all omitted-player and unattributed opportunities.
        target_weights.append(1-sum(target_weights)); rush_weights.append(1-sum(rush_weights))
        ta=allocations(rng,st['pass_attempts'],target_weights,uncertain,par['allocation_concentration'])
        ru=allocations(rng,st['rush_attempts'],rush_weights,uncertain,par['allocation_concentration'])
        starter_left=st['starter_qb_attempts']; attempt_left=st['pass_attempts']
        st.update(team_completions=0,team_passing_yards=0,team_rushing_yards=0,
                  residual_targets=int(ta[-1]),residual_rush_attempts=int(ru[-1]),
                  residual_receptions=0,residual_receiving_yards=0,residual_rushing_yards=0)
        st['receivers']={};st['backs']={}
        for i,p in enumerate(ps+[par['residual']]):
            pid=p['player_id'] if i<len(ps) else residual
            nt=int(ta[i]); nr=int(ru[i])
            a,b=p['catch_alpha'],p['catch_beta']
            rate=float(rng.beta(a,b)) if uncertain else a/(a+b)
            catches=int(rng.binomial(nt,rate))
            # Randomly partition attempts by QB origin, preserving the same
            # receiver completions and passing yard marks on matched plays.
            starter_targets=int(rng.hypergeometric(starter_left,attempt_left-starter_left,nt)) if nt else 0
            starter_catches=int(rng.hypergeometric(starter_targets,nt-starter_targets,catches)) if catches else 0
            starter_left-=starter_targets; attempt_left-=nt
            gains=[mark(rng,p['receiving_marks'],uncertain) for _ in range(catches)]
            rgains=[mark(rng,p['rushing_marks'],uncertain) for _ in range(nr)]
            ry=sum(rgains); y=sum(gains)
            out[(q,'completions')]+=starter_catches
            out[(q,'passing_yards')]+=sum(gains[:starter_catches])
            st['team_completions']+=catches; st['team_passing_yards']+=y; st['team_rushing_yards']+=ry
            if i<len(ps):
                out[(pid,'targets')]=nt;out[(pid,'receptions')]=catches
                out[(pid,'receiving_yards')]=y;out[(pid,'rushing_attempts')]=nr;out[(pid,'rushing_yards')]=ry
                st['receivers'][pid]={'targets':nt,'receptions':catches}
                st['backs'][pid]={'carries':nr}
            else:
                st.update(residual_receptions=catches,residual_receiving_yards=y,residual_rushing_yards=ry)
        for p in ps:
            pid=p['player_id']
            out[(pid,'rushing_receiving_yards')]=out[(pid,'rushing_yards')]+out[(pid,'receiving_yards')]
            if pid==q:out[(pid,'passing_rushing_yards')]=out[(pid,'passing_yards')]+out[(pid,'rushing_yards')]
    verify(out,state,event)
    return dict(out),state


def verify(out,state,event):
    for t in event['teams']:
        s=state[t['team_id']];q=t['starter_qb_id']
        require(s['plays']==s['pass_attempts']+s['rush_attempts']+s['sacks'],'PLAY_ACCOUNTING')
        require(sum(p['targets'] for p in s['receivers'].values())+s['residual_targets']==s['pass_attempts'],'TARGET_ACCOUNTING')
        require(sum(p['carries'] for p in s['backs'].values())+s['residual_rush_attempts']==s['rush_attempts'],'RUSH_ACCOUNTING')
        require(sum(p['receptions'] for p in s['receivers'].values())+s['residual_receptions']==s['team_completions']<=s['pass_attempts'],'COMPLETION_ACCOUNTING')
        require(out.get((q,'completions'),0)<=out[(q,'pass_attempts')]<=s['pass_attempts'],'QB_ACCOUNTING')
        require(all(p['receptions']<=p['targets'] for p in s['receivers'].values()),'CATCH_ACCOUNTING')
        pids=[p['player_id'] for p in event['all_market_parameters'][t['team_id']]['players']]
        require(sum(out.get((p,'receiving_yards'),0) for p in pids)+s['residual_receiving_yards']==s['team_passing_yards'],'PASS_YARD_ACCOUNTING')
        require(sum(out.get((p,'rushing_yards'),0) for p in pids)+s['residual_rushing_yards']==s['team_rushing_yards'],'RUSH_YARD_ACCOUNTING')
    for (p,k),v in out.items():
        require(k not in COUNTS or (int(v)==v and v>=0),'INVALID_COUNT')
        if k=='rushing_receiving_yards':require(v==out.get((p,'rushing_yards'),0)+out.get((p,'receiving_yards'),0),'COMPOSITE_ARITHMETIC')
        if k=='passing_rushing_yards':require(v==out.get((p,'passing_yards'),0)+out.get((p,'rushing_yards'),0),'COMPOSITE_ARITHMETIC')


def covariance(x,y):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
    require(x.shape==y.shape and x.ndim==1 and len(x)>1 and np.all(np.isfinite(x)) and np.all(np.isfinite(y)),'INVALID_MATCHED_DRAWS')
    cov=float(np.mean((x-x.mean())*(y-y.mean())))
    variance=float(np.var(x+y)); rhs=float(np.var(x)+np.var(y)+2*cov)
    require(np.isclose(variance,rhs,atol=1e-9),'INVALID_COVARIANCE')
    return dict(covariance=cov,correlation=float(cov/(x.std()*y.std())) if x.std()*y.std()>0 else None,variance_sum=variance,variance_identity_rhs=rhs)
