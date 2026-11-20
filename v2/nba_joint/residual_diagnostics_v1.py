"""Monte Carlo discrepancy disclosures for a new law, never a gate override."""
import math
import numpy as np
from v2.nba_architecture.full_played_s_v1 import FullPlayedLaw
from v2.nba_architecture.subset_p3_v1 import require
from .residual_audit_v1 import audit_run


def compare_with_full_S(run,full_forecast):
    audit_run(run);n=run['n_requested'];rows=[]
    references={(r['player_id'],r['statistic']):r['model'] for r in full_forecast['law_payload']['rows']}
    # Simultaneous DKW bands over the56 primitive marginals, under independent
    # scenario streams. This measures MC error, not source/model uncertainty.
    epsilon=min(1.,math.sqrt(math.log(2*56/.05)/(2*n)))
    samples={}
    for scenario in run['scenarios']:
        fixed=scenario['fixed'];path=scenario['proposals'][-1]
        for team,actors in fixed['actors'].items():
            for actor in actors:
                pid=actor['identity']['player_id']
                if pid:
                    for stat in ('points','rebounds','assists','threes'):
                        samples.setdefault((pid,stat),[]).append(path['counts'][team][actor['index']][stat])
    for key,reference in references.items():
        if reference is None:
            require(key not in samples,'J_DIAGNOSTIC_UNSUPPORTED_PLAYER_FORECAST')
            rows.append(dict(player_id=key[0],statistic=key[1],status='ABSTAINED_SOURCE_OR_MODEL',n=0));continue
        values=samples[key];require(len(values)==n,'J_DIAGNOSTIC_DROPPED_SAMPLE')
        law=FullPlayedLaw(**reference['rate_parameters'],minutes=reference['minute_parameters'],zero_prior_mean=reference['zero_prior_mean'])
        maximum=max(max(values),128);grid=list(range(maximum+1))
        pmf=law.query(grid);cdf=law.query(grid,kind='cdf');tail=law.query([maximum],kind='sf')
        empirical=np.bincount(values,minlength=maximum+1)/n
        partition_tv=.5*(float(np.abs(empirical-np.asarray(pmf['probabilities'])).sum())+tail['probabilities'][0])
        cdf_gap=float(np.max(np.abs(np.cumsum(empirical)-np.asarray(cdf['probabilities']))))
        mean=float(np.mean(values));sd=float(np.std(values,ddof=1)) if n>1 else None
        rows.append(dict(player_id=key[0],statistic=key[1],status='NEW_J_VS_REFERENCE_S_DIAGNOSTIC_ONLY',n=n,
            new_J_sample_mean=mean,reference_S_mean=law.moments()['mean'],mean_difference=mean-law.moments()['mean'],
            sample_mean_MC_standard_error=sd/math.sqrt(n) if sd is not None else None,
            partition_empirical_TV=partition_tv,partition_limit=maximum,tail_cell_included=True,
            empirical_CDF_max_difference=cdf_gap,simultaneous56_MC_DKW95_half_width=epsilon,
            population_CDF_difference_lower_bound=max(0.,cdf_gap-epsilon),
            reference_S_OT_absolute_omission_bound=max(pmf['omitted_OT_probability_bound'],cdf['omitted_OT_probability_bound']),
            reference_quadrature_difference_is_estimate=True,TV_fidelity_certificate=False))
    return dict(schema='new-J-reference-S-discrepancy/1',scenario_denominator=n,attempt_denominator=len(rows),
        supported_rows=sum(r['n']>0 for r in rows),abstentions=sum(r['n']==0 for r in rows),rows=rows,
        unchanged_S_marginals_claim=False,marginal_fidelity_accepted=False,
        conditioning_comparison='NEW_J_CONDITIONS_ALL14_NAMED_PLAYED_REFERENCE_S_CONDITIONS_OWN_PLAYER_PLAYED;NO_IDENTIFIED_PARTICIPATION_MODEL',
        maximum_CDF_gap=max(r.get('empirical_CDF_max_difference',0) for r in rows),
        simultaneous_MC_DKW95_half_width=epsilon,original_n32_budget_red_preserved=True,
        independent_quality_decision_required=True,release=False)
