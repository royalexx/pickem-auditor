"""Create-only latest-owner synthetic compatibility/approximation packet."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from research.nba_p4_latest.fixture import build
from research.nba_p4_latest.numerical_reference import references
from v2.nba_joint.integration_v2 import simulate_latest
from v2.nba_joint.latest_upstream import prepare
from v2.nba_joint.p4 import scenario_pmfs

PARAMETERS = {'p2': .54, 'p3': .36, 'pft': .78, 'ft_share': .2,
    'rebound_credit': .88, 'offensive_rebound_share': .23,
    'terminal_ft_fraction': .45, 'assist_fraction': .62}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    root=prepare();inputs=build(root)
    p,g,o,side,artifacts,manifest,roles=inputs
    result=simulate_latest(*inputs,upstream_root=root,evidence_mode='latest_synthetic_engineering',
        event_parameters=PARAMETERS,seed=42)
    pmfs=scenario_pmfs(result,p,frozen_at='2026-11-16T23:03:00Z',seed=42)
    # Four finite paths are a compatibility diagnostic. They cannot establish
    # approximation adequacy, calibrated marginals or predictive accuracy.
    rows=[]
    for pid,stats in pmfs.items():
        for stat in ('points','rebounds','assists','threes'):
            target={}
            for sc,audit in zip(result['bundle']['scenarios'],result['audit_rows']):
                law=audit['integration']['P2_to_J_projection'][pid]['conditional_laws'][stat]
                for x in law['pmf']:
                    target[x['value']]=target.get(x['value'],0.)+sc['weight']*x['mass']
            actual={r['value']:r['mass'] for r in stats[stat]['pmf']}
            support=set(target)|set(actual)
            def moments(law):
                mean=math.fsum(k*v for k,v in law.items())
                return {'mean':mean,'variance':math.fsum(v*(k-mean)**2 for k,v in law.items()),
                    'zero_mass':law.get(0,0.),'mass_at_or_above_20':math.fsum(v for k,v in law.items() if k>=20)}
            ct=ca=0.;sup=0.
            for value in range(max(support)+1):
                ct+=target.get(value,0.);ca+=actual.get(value,0.);sup=max(sup,abs(ct-ca))
            rows.append({'player_id':pid,'stat':stat,
                'finite_serialized_target_vs_empirical_TV':.5*math.fsum(abs(target.get(k,0.)-actual.get(k,0.)) for k in support),
                'maximum_integer_CDF_difference':sup,'S_O_moments':moments(target),
                'J_four_path_empirical_moments':moments(actual)})
    packet={'scope':'SYNTHETIC_ENGINEERING_ONLY','original_historical_outcomes_accessed':False,
        'independent_approval':False,'finite_paths':len(result['bundle']['scenarios']),
        'observed_games':0,'statistical_adequacy_established':False,
        'physical_chronology_established':False,'status':result['status'],
        'limitations':['Four paths are not an adequate marginal fidelity experiment.',
            'Rate compatibility and non-tied final-score rejection condition the law.',
            'G overtime is duration-only in the aggregate event kernel.',
            'No event-time co-presence or exact possession/free-throw chronology is certified.']}
    files={'benchmark.json':packet,'integration_result.json':result,
        'contract_inputs.json':{'pregame':p,'G':g,'O':o,'O_sidecar':side,
            'source_manifest':manifest,'roles':roles,
            'artifacts':{k:a.data for k,a in artifacts.items()}},
        'complete_pmfs.json':pmfs,'marginal_distortion.json':rows,
        'analytical_references.json':references()}
    sums=[]
    for name,value in files.items():
        raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        with (output/name).open('xb') as handle:handle.write(raw)
        sums.append(hashlib.sha256(raw).hexdigest()+'  '+name)
    (output/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print(json.dumps(packet,sort_keys=True))


if __name__=='__main__':main()
