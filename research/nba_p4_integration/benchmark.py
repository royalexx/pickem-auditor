"""Deterministic pinned P2/P3/J benchmarks and complete four-scenario PMFs.

python -m research.nba_p4_integration.benchmark --output work/benchmark
Outputs are create-only. All inputs synthetic; no training or accuracy scoring.
"""
import argparse
import json
from pathlib import Path
import resource
import sys
import time
from v2.nba_architecture.v2_contracts import digest
from v2.nba_joint.integration import simulate_integrated, raw_sha, PINS
from v2.nba_joint.p4 import scenario_pmfs
from research.nba_p4_integration.fixture import build
from research.nba_p4_integration.prepare import prepare

PARAMETERS={'p2':.54,'p3':.36,'pft':.78,'ft_share':.25,'rebound_credit':.9,
            'offensive_rebound_share':.24,'terminal_ft_fraction':.44,'assist_fraction':.6}


def write(path, value):
    with path.open('x') as f:
        f.write(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n')
    return raw_sha(path.read_bytes())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True)
    args=ap.parse_args();folder=Path(args.output);folder.mkdir(parents=True,exist_ok=True)
    root=prepare();rows=[]
    for n in (8,32,64):
        inputs=build(root,n=n)
        for variant in ('J0','J1','J2'):
            kwargs={'upstream_root':root,'evidence_mode':'pinned_contract_fixture',
                    'event_parameters':PARAMETERS,'seed':42,'variant':variant,
                    'role_sigma':.1 if variant=='J2' else 0.,
                    'efficiency_sigma':.08 if variant=='J2' else 0.}
            start,cpu=time.perf_counter(),time.process_time()
            result=simulate_integrated(*inputs,**kwargs)
            seconds,cpu_seconds=time.perf_counter()-start,time.process_time()-cpu
            replay=simulate_integrated(*inputs,**kwargs)
            assert result['bundle']==replay['bundle']
            assert result['audit_rows']==replay['audit_rows']
            rows.append({'n':n,'variant':variant,'seconds':seconds,'cpu_seconds':cpu_seconds,
                'peak_rss_linux_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'player_draws':12*n,'input_shas':result['input_shas'],
                'bundle_sha256':result['bundle']['content_hash'],
                'audit_sha256':digest(result['audit_rows']),
                'scenario_hashes':result['scenario_hashes'],'replay_exact':True,
                'tie_rejections':sum(x['rejected_tied_event_draws'] for x in result['audit_rows'])})
            print(json.dumps({k:rows[-1][k] for k in ('n','variant','seconds','bundle_sha256','replay_exact')}),flush=True)
    inputs=build(root)
    result=simulate_integrated(*inputs,upstream_root=root,evidence_mode='pinned_contract_fixture',
                              event_parameters=PARAMETERS,seed=42)
    pmfs=scenario_pmfs(result,inputs[0],frozen_at='2026-11-16T23:03:00Z',seed=42)
    # Record descriptive marginal distortion rather than imply P2 laws survive shared allocation.
    drift={}
    for pid,stats in pmfs.items():
        drift[pid]={}
        for stat in ('points','rebounds','assists','threes'):
            target={}
            for audit,sc in zip(result['audit_rows'],result['bundle']['scenarios']):
                law=audit['integration']['P2_to_J_projection'][pid]['conditional_laws'][stat]['pmf']
                for atom in law:
                    target[atom['value']]=target.get(atom['value'],0.)+sc['weight']*atom['mass']
            empirical={a['value']:a['mass'] for a in stats[stat]['pmf']}
            drift[pid][stat]={'P2_retained_mixture_mean':sum(k*v for k,v in target.items()),
                'J_empirical_mean':sum(k*v for k,v in empirical.items()),
                'total_variation':.5*sum(abs(target.get(k,0.)-empirical.get(k,0.)) for k in set(target)|set(empirical)),
                'interpretation':'four finite joint draws; descriptive distortion, not accuracy or calibration'}
    outputs={}
    outputs['contract_inputs.json']=write(folder/'contract_inputs.json',{
        'pregame':inputs[0],'G':inputs[1],'O':inputs[2],'O_sidecar':inputs[3]})
    stable={k:v for k,v in result.items() if k!='performance'}
    outputs['joint_scenarios.json']=write(folder/'joint_scenarios.json',stable)
    outputs['complete_pmfs.json']=write(folder/'complete_pmfs.json',pmfs)
    outputs['marginal_distortion.json']=write(folder/'marginal_distortion.json',drift)
    receipt={'purpose':'P4_PINNED_OWNER_CONTRACT_BENCHMARK_NOT_REAL_SOURCE',
        'real_integration':'BLOCKED','independent_P6_review':'REQUEST_REQUIRED_FOR_EXACT_COMMIT',
        'seed':42,'owner_pins':PINS,'rows':rows,'outputs':outputs,'runtime':sys.version,
        'numpy':__import__('numpy').__version__,'scipy':__import__('scipy').__version__,
        'J2_uncertainty':'declared_unfitted_research_parameters'}
    print('BENCHMARK_RECEIPT_SHA256',write(folder/'benchmark.json',receipt))


if __name__=='__main__':
    main()
