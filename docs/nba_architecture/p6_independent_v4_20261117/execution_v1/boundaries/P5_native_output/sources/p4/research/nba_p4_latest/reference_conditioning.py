"""Append-only clarification of the repeated-study fixed-scenario reference.

The historical output key ``analytic_S_O`` is retained verbatim. It denotes
conditional S kernels integrated over a FIXED synthetic O scenario population,
not a source-admitted unconditional participation forecast.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import nbinom

from research.nba_p4_latest.fixture import build
from research.nba_p4_latest.repeated_seeds import full_count_laws
from v2.nba_joint.latest_upstream import prepare, load_upstream, raw_sha


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    root=prepare();inputs=build(root);p,g,o,side,artifacts,manifest,roles=inputs
    p2,_=load_upstream(root);targets=full_count_laws(inputs,p2);rows=[]
    for player in p['players']:
        pid=player['player_id'];person=next(x for x in o['players'] if x['player_id']==pid)
        played_weight=sum(sc['weight'] for sc in o['scenarios']
            if next(x for x in sc['players'] if x['player_id']==pid)['participation']!='DNP')
        for stat in ('points','rebounds','assists','threes'):
            kwargs=dict(frozen_pregame=p,target_player_id=pid,role=roles[pid],
                        opportunity=o,game_state=g,seed=42)
            uncond=p2.predict(artifacts[stat],conditioning='unconditional',**kwargs)
            conditional=p2.predict(artifacts[stat],conditioning='conditional_on_participation',**kwargs)
            if uncond.abstain_reason is None or conditional.abstain_reason is not None:
                raise ValueError('UNEXPECTED_PUBLIC_CONDITIONING_RESULT')
            # This study's fixed O2 population has no sampled DNP rows. An
            # unverified prior probability is still not a genuine q=1 claim.
            if abs(played_weight-1.)>1e-12:raise ValueError('STUDY_REFERENCE_CONDITIONING_REQUIRES_REASSESSMENT')
            pmf=conditional.distribution['pmf']
            support=np.array([x['value'] for x in pmf])
            expected=sum(c['weight']*nbinom.pmf(support,c['shape'],c['success_probability'])
                         for c in targets[pid][stat])
            error=float(np.max(np.abs(expected-np.array([x['mass'] for x in pmf]))))
            if error>2e-11:raise ValueError('PLAYED_CONDITIONAL_REFERENCE_MISMATCH')
            rows.append({'player_id':pid,'stat':stat,
                'genuine_participation_probability':person['participation_probability'],
                'participation_evidence':person['participation_evidence'],
                'fixed_all_scenario_weight_denominator':sum(sc['weight'] for sc in o['scenarios']),
                'fixed_played_scenario_weight_denominator':played_weight,
                'public_unconditional_predict':uncond.abstain_reason,
                'public_played_conditional_predict':'ENGINEERING_DISTRIBUTION_EMITTED_NOT_SOURCE_ADMITTED',
                'public_played_conditional_maximum_PMF_error':error})
    result={'schema':'NBA-P4-fixed-scenario-reference-clarification/1.0.0',
        'scope':'SYNTHETIC_ENGINEERING_ONLY','observed_games':0,
        'legacy_metric_field':'analytic_S_O',
        'correct_interpretation':'fixed_G_O_scenario_weighted_S_conditional_kernel_reference',
        'unconditional_participation_forecast_admitted':False,
        'reason':'All genuine q values remain null; sampled PLAYED outcomes do not certify q=1.',
        'comparison_denominators':'Both fixed populations have weight1 in this exact fixture. Public played-conditional output agrees numerically; authentic unconditional predict abstains.',
        'pregame_sha256':p['content_hash'],'O_sha256':o['content_hash'],
        'source_code_sha256':raw_sha(Path(__file__).read_bytes()),'rows':rows,
        'all_48_unconditional_predictions_abstained':len(rows)==48,
        'max_played_conditional_PMF_error':max(r['public_played_conditional_maximum_PMF_error'] for r in rows),
        'original_study_outputs_modified':False,'independent_acceptance':False}
    with args.output.open('xb') as handle:handle.write((json.dumps(result,sort_keys=True,indent=2)+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))


if __name__=='__main__':main()
