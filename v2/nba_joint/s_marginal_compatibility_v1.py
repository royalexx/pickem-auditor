"""Necessary factorial-moment constraint for an exact points/3PM coupling.

For integer X>=3Y, (X)_r >= 3**r*(Y)_r pointwise. For the saved
Gamma-Poisson/full-minute mixtures with identical marginal M and zero weight,
the common positive E[M**r] and zero factor cancel. Thus some independent
statistic marginals cannot belong to any physically valid unchanged joint law.
This is not a lower bound on practical TV distortion or a quality decision.
"""
import math
from v2.nba_architecture.subset_p3_v1 import require


def check_saved_marginals(full_forecast,max_order=100000):
    require(type(max_order) is int and max_order>0,'S_J_MOMENT_BUDGET')
    by_player={}
    for row in full_forecast['law_payload']['rows']:
        if row['model']:by_player.setdefault(row['player_id'],{})[row['statistic']]=row['model']
    rows=[]
    for pid,models in sorted(by_player.items()):
        points,threes=models['points'],models['threes']
        require(points['minute_parameters']==threes['minute_parameters'] and
            points['zero_prior_mean']==threes['zero_prior_mean']<1,'S_J_COMMON_MARGINAL_EXPOSURE')
        p,t=points['rate_parameters'],threes['rate_parameters'];witness=None
        for r in range(1,max_order+1):
            logratio=(math.lgamma(p['alpha']+r)-math.lgamma(p['alpha'])-
                math.lgamma(t['alpha']+r)+math.lgamma(t['alpha'])+
                r*(math.log(t['beta'])-math.log(p['beta'])-math.log(3)))
            # Margin1 logunit avoids calling a roundoff boundary a witness.
            if logratio < -1:
                witness=dict(order=r,log_factorial_moment_ratio=logratio,
                    necessary_ratio_lower_bound=1.,observed_ratio=math.exp(logratio),
                    points_rate_parameters=p,threes_rate_parameters=t);break
        rows.append(dict(player_id=pid,status='EXACT_UNCHANGED_PHYSICAL_COUPLING_IMPOSSIBLE_NUMERICAL_WITNESS' if witness
            else 'NO_WITNESS_IN_SEARCH_BUDGET_NOT_COMPATIBILITY_PROOF',witness=witness))
    return dict(schema='saved-S-marginal-physical-compatibility/1',player_denominator=len(rows),rows=rows,
        max_order=max_order,incompatible_rows=sum(r['witness'] is not None for r in rows),
        hypothesis='X_POINTS_GE_3_TIMES_Y_THREES_ALMOST_SURELY',
        proof='For X>=3Y and integer r>=1: (X)_r >= (3Y)_r >= 3^r*(Y)_r; take finite expectations. Gamma-Poisson factorial moment=(alpha)_r E[M^r]/beta^r. Common M and zero factor cancel.',
        numerical_witness_requires_independent_high_precision_review=True,
        TV_distortion_lower_bound_established=False,history_scored=False,new_fit=False,release=False)
