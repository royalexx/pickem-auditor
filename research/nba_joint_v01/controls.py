"""Simple isolated controls; no production models are recomputed or changed."""
import numpy as np
from v2.nba_joint.common import rng_for,combos,STATS
from v2.nba_opportunity import MinutesModel


def marginals(game,model,n,seed,*,empirical=False):
    mm=MinutesModel(**model['minutes']);p=len(game['players'])
    result={k:np.zeros((n,p),dtype=np.int64) for k in STATS[:4]}
    for i,player in enumerate(game['players']):
        for stat in STATS[:4]:
            rng=rng_for(seed,game['game_id'],i,('F0/' if empirical else 'J0/')+stat)
            if empirical:result[stat][:,i]=rng.choice(player['history_stats'][stat],n)
            else:
                # Valid full-support marginal Gamma-Poisson, not a validated champion.
                law=mm.law('M0',player['minute_features'],player['position'])
                lengths=np.full(n,48.)
                ot=rng.random(n)<mm.ot_probability
                lengths[ot]+=5*rng.geometric(1-mm.ot_continuation,int(ot.sum()))
                minutes=np.array([law.sample_at_length(rng,l) for l in lengths])
                h=player['history_stats'][stat];total=sum(h)
                # Posterior shape from prior + observed counts, fixed mean rate.
                shape=max(1.,total+model['prior_rates'][stat]*48)
                rate=rng.gamma(shape,player['rates'][stat]/shape,n)
                result[stat][:,i]=rng.poisson(rate*minutes)
    return combos(result)


def independent_permutation(stats,game_id,seed):
    # Exactly preserves every J2 single-stat empirical PMF; combos are rederived.
    result={k:v.copy() for k,v in stats.items() if k in STATS[:4]}
    for stat,x in result.items():
        for i in range(x.shape[1]):x[:,i]=x[rng_for(seed,game_id,i,'shuffle/'+stat).permutation(len(x)),i]
    return combos(result)
