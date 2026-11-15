"""Conservative aggregate event baseline substituted for unavailable NBA WS3.

Shots are genuine modeled attempts, inferred from aggregate historical rates
and pooled conversions when player attempt histories are absent. This is not
tracking data or possession-by-possession basketball. Rebounds include an
unattributed category. Assists are tied to scorer-specific teammate field goals.
"""
import numpy as np


def weights(v):
    x=np.asarray(v,dtype=float)
    if np.any(~np.isfinite(x)) or np.any(x<0) or x.sum()<=0:raise ValueError('INVALID_OPPORTUNITY_WEIGHTS')
    return x/x.sum()


def sample_events(players, minutes, team_indices, state, model, rng, *, constrained=True):
    e=model['events'];n=len(players)
    p2,p3,pft=e['p2'],e['p3'],e['pft']
    for k in ('p2','p3','pft','ft_share','rebound_credit','offensive_rebound_share','assist_fraction','terminal_ft_fraction'):
        if not np.isfinite(e[k]) or not 0<=e[k]<=1:raise ValueError('INVALID_EVENT_PROBABILITY:'+k)
    if min(p2,p3,pft)<=0:raise ValueError('ZERO_CONVERSION_REQUIRES_DIFFERENT_AGGREGATE_RATE_ADAPTER')
    counts={k:np.zeros(n,dtype=np.int64) for k in ('two_pa','two_pm','three_pa','threes','fta','ftm','points','oreb','dreb','rebounds','assists')}
    budgets=[];unassisted=[];assist_matrix=np.zeros((n,n),dtype=np.int64)
    for t,ix in enumerate(team_indices):
        rate=np.array([[p['rates'][k] for k in ('points','threes')] for p in [players[i] for i in ix]])
        non3=np.maximum(0,rate[:,0]-3*rate[:,1])
        expectations=np.column_stack([non3*(1-e['ft_share'])/(2*p2),rate[:,1]/p3,non3*e['ft_share']/pft])*minutes[ix,None]
        factor=state['regulation_possession_proxy']/model['state']['pace_mean']*state['offensive_effect'][t]
        expectations*=factor
        for j,key in enumerate(('two_pa','three_pa','fta')):
            means=expectations[:,j]
            if means.sum()==0:alloc=np.zeros(len(ix),dtype=np.int64)
            elif constrained:
                total=int(rng.poisson(means.sum()));alloc=rng.multinomial(total,weights(means))
            else:alloc=rng.poisson(means)
            counts[key][ix]=alloc
        counts['two_pm'][ix]=rng.binomial(counts['two_pa'][ix],p2)
        counts['threes'][ix]=rng.binomial(counts['three_pa'][ix],p3)
        counts['ftm'][ix]=rng.binomial(counts['fta'][ix],pft)
        budgets.append({k:int(counts[k][ix].sum()) for k in ('two_pa','two_pm','three_pa','threes','fta','ftm')})
        fg=counts['two_pm'][ix]+counts['threes'][ix]
        ast_weights=np.array([players[i]['rates']['assists'] for i in ix])*minutes[ix]
        team_unassisted=0
        for scorer, made in zip(ix,fg):
            w=ast_weights.copy();w[np.asarray(ix)==scorer]=0
            # No player can assist their own basket. Positive exposure required.
            assisted=int(rng.binomial(int(made),e['assist_fraction'])) if w.sum()>0 else 0
            a=rng.multinomial(assisted,weights(w)) if assisted else np.zeros(len(ix),dtype=np.int64)
            counts['assists'][ix]+=a;assist_matrix[ix,scorer]+=a
            team_unassisted+=int(made)-assisted
        unassisted.append(team_unassisted)
    rebound_ledger=[]
    for shooter_team,ix in enumerate(team_indices):
        other=team_indices[1-shooter_team];b=budgets[shooter_team]
        fg_misses=b['two_pa']+b['three_pa']-b['two_pm']-b['threes']
        # Aggregate terminal-FT approximation; not every missed FT is reboundable.
        terminal_ft=int(rng.binomial(b['fta']-b['ftm'],e['terminal_ft_fraction']))
        available=fg_misses+terminal_ft
        credited=int(rng.binomial(available,e['rebound_credit']))
        offensive=int(rng.binomial(credited,e['offensive_rebound_share']))
        defensive=credited-offensive
        for side,key,total in ((ix,'oreb',offensive),(other,'dreb',defensive)):
            w=minutes[side]*np.array([players[i]['rates']['rebounds'] for i in side])
            if total and w.sum()<=0:raise ValueError('REBOUND_ALLOCATION_INFEASIBLE')
            if total:counts[key][side]+=rng.multinomial(total,weights(w))
        rebound_ledger.append(dict(fg_misses=fg_misses,terminal_ft=terminal_ft,available=available,credited=credited,offensive=offensive,defensive=defensive,unattributed=available-credited))
    counts['points']=2*counts['two_pm']+3*counts['threes']+counts['ftm']
    counts['rebounds']=counts['oreb']+counts['dreb']
    return counts,dict(team_budgets=budgets,unassisted=unassisted,assist_matrix=assist_matrix.tolist(),rebounds=rebound_ledger)
