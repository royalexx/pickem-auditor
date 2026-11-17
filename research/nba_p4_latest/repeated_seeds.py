"""Predeclared repeated-seed diagnostic of the actual latest-owner J map.

Each Monte Carlo repetition shares the SAME actual O2 draw set. Repetitions
are engineering units, never observed games or new O draws. Full raw API
outputs are retained losslessly; no historical forecast or outcome is read.
"""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import numpy as np
from scipy.stats import nbinom

from research.nba_p4_latest.benchmark import PARAMETERS
from research.nba_p4_latest.fixture import build
from v2.nba_architecture.v2_contracts import ContractError, digest
from v2.nba_joint.integration_v2 import simulate_latest
from v2.nba_joint.latest_upstream import ROOT, REGISTRY, load_upstream, prepare, raw_sha, registry

PLAN = ROOT/'research/nba_p4_latest/repeated_seed_plan_v3.json'
STATS = ('points','rebounds','assists','threes')


def encode(obj):
    return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def full_count_laws(inputs,p2):
    p,g,o,side,artifacts,manifest,roles=inputs
    result={}
    for player in p['players']:
        pid=player['player_id'];result[pid]={}
        for stat in STATS:
            components=[]
            for sc in o['scenarios']:
                row=next(x for x in sc['players'] if x['player_id']==pid)
                pr=p2.predict_conditional(artifacts[stat],player_id=pid,role=roles[pid],
                    projected_exposure=row['minutes'],statistic=stat)
                if pr.abstain_reason:raise RuntimeError(pr.abstain_reason)
                a=pr.parameters;family=artifacts[stat].data['family']
                shape=a['alpha'] if family=='S1' else a['dispersion']
                mean=a['rate_mean']*row['minutes']
                prob=(a['beta']/(a['beta']+row['minutes']) if family=='S1'
                      else shape/(shape+mean))
                components.append({'scenario_id':sc['scenario_id'],'weight':sc['weight'],
                    'shape':shape,'success_probability':prob,'exposure':row['minutes'],
                    'mean':mean,'variance':mean+mean*mean/shape,
                    'source_serialization_tail_bound':a['tail_mass_upper_bound']})
            result[pid][stat]=components
    return result


def plan():
    root=prepare();inputs=build(root);p,g,o,side,artifacts,*_=inputs
    pins=registry()
    return {'schema':'NBA-P4-actual-map-repeated-seed-plan/1.1.0',
        'evidence':'SYNTHETIC_ENGINEERING_ONLY','observed_games':0,
        'preregistration_registry_raw_sha256':raw_sha(REGISTRY.read_bytes()),
        'preregistration_owner_core_commits':{k:v['commit'] for k,v in pins['owners'].items()},
        'executable_source_hashes':{k:v['files'] for k,v in pins['owners'].items()},
        'inherited_g0_files':pins['inherited_g0_files'],
        'reused_owner_files':pins['reused_owner_files'],
        'metadata_successor_policy':'Owner commit metadata and unconsumed inspector inventory may advance only with identical consumed executable closure and fixed inputs; all runtime inventory bytes remain verified and the executed registry is retained separately.',
        'pregame_sha256':p['content_hash'],'G_sha256':g['content_hash'],
        'O_sha256':o['content_hash'],'O_sidecar_sha256':side['content_hash'],
        'artifacts':{k:a.artifact_sha256 for k,a in artifacts.items()},
        'O_variant':'O2','fixed_O_scenarios':4,
        'seeds':list(range(100000,100256)), 'n_independent_J_repetitions':256,
        'repetition_unit':'one J seed with all four fixed weighted G/O scenarios',
        'event_parameters':PARAMETERS,'tail_threshold_inclusive':20,
        'acceptance':'NONE: independent review and physical contract remain pending',
        'metrics':['pooled full weighted empirical PMF','TV/CDF vs actual analytical S_O mixture',
            'mean','variance','zero mass','mass >=20','per-seed clustered Monte Carlo SE'],
        'uncertainty':'Monte Carlo SE over J seeds, not game sampling or predictive validation',
        'batch_size_for_diagnostic_spread':16,
        'raw_output':'lossless gzip full per-seed native API JSON results; every rejection retained'}


def cluster_moments(samples):
    x=np.asarray(samples,dtype=float)
    n=len(x);estimate=x.mean(axis=0)
    # Columns are E[Y], E[Y^2], P(Y=0), P(Y>=threshold) for one weighted seed.
    variance=float(estimate[1]-estimate[0]**2)
    se=np.std(x,axis=0,ddof=1)/math.sqrt(n)
    variance_influence=x[:,1]-2*estimate[0]*x[:,0]
    return {'mean':float(estimate[0]),'mean_MCSE':float(se[0]),
        'variance':variance,'variance_delta_MCSE':float(np.std(variance_influence,ddof=1)/math.sqrt(n)),
        'zero_mass':float(estimate[2]),'zero_mass_MCSE':float(se[2]),
        'mass_at_or_above_20':float(estimate[3]),'tail_mass_MCSE':float(se[3]),
        'indicator_Hoeffding_95_halfwidth':math.sqrt(math.log(40)/(2*n)),
        'MCSE_interpretation':'independent J-seed repetition uncertainty only; no game observations'}


def run(output):
    declared=json.loads(PLAN.read_bytes())
    current=plan()
    metadata={'preregistration_registry_raw_sha256','preregistration_owner_core_commits'}
    if {k:v for k,v in current.items() if k not in metadata}!={k:v for k,v in declared.items() if k not in metadata}:
        raise RuntimeError('PREDECLARED_INPUT_PLAN_MISMATCH')
    output.mkdir(parents=True,exist_ok=False)
    root=prepare();inputs=build(root);p,g,o,side,artifacts,*_=inputs;p2,_=load_upstream(root)
    targets=full_count_laws(inputs,p2)
    pooled={pid:{s:{} for s in STATS} for pid in targets}
    samples={pid:{s:[] for s in STATS} for pid in targets}
    batch_size=declared['batch_size_for_diagnostic_spread']
    batch_pmfs=[{pid:{s:{} for s in STATS} for pid in targets}
                for _ in range(len(declared['seeds'])//batch_size)]
    rejects=[];raw_hash=hashlib.sha256();replay_hash=hashlib.sha256();raw_bytes=0;started=time.perf_counter()
    raw_path=output/'full_seed_outputs.jsonl.gz'
    failed=None;failed_seed=None
    with raw_path.open('xb') as handle,gzip.GzipFile(fileobj=handle,mode='wb',filename='',mtime=0) as stream:
        for seed in declared['seeds']:
            try:
                result=simulate_latest(*inputs,upstream_root=root,evidence_mode='latest_synthetic_engineering',
                    event_parameters=declared['event_parameters'],seed=seed)
            except ContractError as error:
                failed,failed_seed=error,seed
                break
            raw=encode({'seed':seed,'native_result':result});stream.write(raw)
            raw_hash.update(raw);raw_bytes+=len(raw)
            replay_hash.update(encode({'seed':seed,'native_result':{
                k:v for k,v in result.items() if k!='performance'}}))
            by_id=[{x['player_id']:x['stats'] for x in sc['players']} for sc in result['bundle']['scenarios']]
            weights=[sc['weight'] for sc in result['bundle']['scenarios']]
            for pid in targets:
                for stat in STATS:
                    values=[row[pid][stat] for row in by_id]
                    samples[pid][stat].append([math.fsum(w*v for w,v in zip(weights,values)),
                        math.fsum(w*v*v for w,v in zip(weights,values)),
                        math.fsum(w for w,v in zip(weights,values) if v==0),
                        math.fsum(w for w,v in zip(weights,values) if v>=20)])
                    for w,v in zip(weights,values):
                        pooled[pid][stat][v]=pooled[pid][stat].get(v,0.)+w/len(declared['seeds'])
                        batch=batch_pmfs[len(rejects)//batch_size][pid][stat]
                        batch[v]=batch.get(v,0.)+w/batch_size
            rejects.append({'seed':seed,'retained_G_O_scenarios':len(result['bundle']['scenarios']),
                'rate_pair_attempts':sum(row['rate_pair_attempts'] for a in result['audit_rows']
                    for row in a['integration']['P2_to_J_projection'].values()),
                'rejected_rate_pairs':sum(len(row['rejected_rate_pairs']) for a in result['audit_rows']
                    for row in a['integration']['P2_to_J_projection'].values()),
                'event_attempts':sum(a['rejected_tied_event_draws']+1 for a in result['audit_rows']),
                'rejected_tied_event_draws':sum(a['rejected_tied_event_draws'] for a in result['audit_rows'])})
    if failed is not None:
        receipt={'status':'FAILED_PARTIAL_PREFIX_NOT_A_SUCCESS_OR_NORMALIZED_PMF',
            'failed_seed':failed_seed,'completed_prefix_seed_count':len(rejects),
            'planned_seed_count':len(declared['seeds']),'completed_prefix_rejection_denominators':rejects,
            'raw_prefix_uncompressed_sha256':raw_hash.hexdigest(),
            'raw_prefix_uncompressed_bytes':raw_bytes,
            'raw_prefix_gzip_sha256':raw_sha(raw_path.read_bytes()),
            'failure_receipt':getattr(failed,'failure_receipt',{'error_code':failed.code})}
        with (output/'failed_execution_receipt.json').open('xb') as handle:handle.write(encode(receipt))
        raise failed
    metrics=[]
    for pid in targets:
        for stat,components in targets[pid].items():
            empirical=pooled[pid][stat]
            if abs(math.fsum(empirical.values())-1.)>1e-12:raise RuntimeError('NONNORMALIZED_POOLED_PMF')
            maximum=max(max(empirical),*(int(nbinom.ppf(1-1e-13,c['shape'],c['success_probability']))
                                        for c in components))
            support=np.arange(maximum+1)
            expected=sum(c['weight']*nbinom.pmf(support,c['shape'],c['success_probability']) for c in components)
            actual=np.array([empirical.get(int(v),0.) for v in support])
            omitted=float(sum(c['weight']*nbinom.sf(maximum,c['shape'],c['success_probability']) for c in components))
            mean=sum(c['weight']*c['mean'] for c in components)
            second=sum(c['weight']*(c['variance']+c['mean']**2) for c in components)
            source={'mean':mean,'variance':second-mean**2,
                'zero_mass':sum(c['weight']*nbinom.pmf(0,c['shape'],c['success_probability']) for c in components),
                'mass_at_or_above_20':sum(c['weight']*nbinom.sf(19,c['shape'],c['success_probability']) for c in components)}
            observed=cluster_moments(samples[pid][stat])
            batch_tv=[]
            for batch in batch_pmfs:
                law=batch[pid][stat]
                beyond=max(0.,1-math.fsum(law.get(int(v),0.) for v in support))
                batch_tv.append(float(.5*(sum(abs(law.get(int(v),0.)-expected[i])
                    for i,v in enumerate(support))+abs(beyond-omitted))))
            metrics.append({'player_id':pid,'stat':stat,'analytic_S_O':source,'proposed_J':observed,
                'mean_distortion':observed['mean']-mean,
                'variance_distortion':observed['variance']-source['variance'],
                'zero_distortion':observed['zero_mass']-source['zero_mass'],
                'tail_distortion':observed['mass_at_or_above_20']-source['mass_at_or_above_20'],
                'empirical_TV_estimate':float(.5*(np.abs(actual-expected).sum()+omitted)),
                'maximum_integer_CDF_difference':float(np.max(np.abs(np.cumsum(actual)-np.cumsum(expected)))),
                'reference_tail_beyond_comparison_support':omitted,
                'sixteen_seed_batch_TV_estimates':batch_tv,
                'batch_TV_interpretation':'independent smaller-batch diagnostic spread; not a confidence interval for pooled TV',
                'TV_uncertainty':'descriptive finite-ensemble estimate; sampling bias not removed'})
    summary={'schema':'NBA-P4-actual-map-repeated-seed-result/1.0.0','plan':declared,
        'executed_owner_registry':registry(),
        'executed_registry_raw_sha256':raw_sha(REGISTRY.read_bytes()),
        'exact_tested_P4_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'elapsed_seconds':time.perf_counter()-started,'observed_games':0,
        'independent_J_seed_repetitions':len(declared['seeds']),
        'retained_weighted_paths':len(declared['seeds'])*len(o['scenarios']),
        'O_draws_resampled':False,'G_O_scenarios_discarded':0,
        'rate_pair_attempts':sum(x['rate_pair_attempts'] for x in rejects),
        'rejected_rate_pairs':sum(x['rejected_rate_pairs'] for x in rejects),
        'event_attempts':sum(x['event_attempts'] for x in rejects),
        'rejected_tied_event_draws':sum(x['rejected_tied_event_draws'] for x in rejects),
        'raw_full_outputs_uncompressed_sha256':raw_hash.hexdigest(),
        'raw_full_outputs_uncompressed_bytes':raw_bytes,
        'raw_full_outputs_gzip_sha256':raw_sha(raw_path.read_bytes()),
        'semantic_replay_sha256_excluding_performance':replay_hash.hexdigest(),
        'raw_hash_replay_note':'raw receipts include observed runtimes; semantic hash excludes performance only',
        'contract_acceptance':'PENDING_INDEPENDENT_REVIEW','physical_chronology_established':False,
        'predictive_validation_performed':False,'adequacy_acceptance':False,
        'max_absolute_mean_distortion':max(abs(x['mean_distortion']) for x in metrics),
        'max_empirical_TV_estimate':max(x['empirical_TV_estimate'] for x in metrics),
        'MC_uncertainty_unit':'J seed with four fixed O2 scenario weights; never an observed game'}
    files={'summary.json':summary,'metrics.json':metrics,'pooled_complete_pmfs.json':pooled,
        'per_seed_cluster_moments.json':samples,'rejection_denominators.json':rejects,
        'analytic_S_O_components.json':targets,'fixed_inputs.json':{
            'pregame':p,'G':g,'O':o,'O_sidecar':side,
            'artifact_sha256':{k:a.artifact_sha256 for k,a in artifacts.items()}}}
    sums=[raw_sha(raw_path.read_bytes())+'  '+raw_path.name]
    for name,value in files.items():
        raw=encode(value)
        with (output/name).open('xb') as handle:handle.write(raw)
        sums.append(raw_sha(raw)+'  '+name)
    (output/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print(json.dumps(summary,sort_keys=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    parser.add_argument('--write-plan',action='store_true');args=parser.parse_args()
    if args.write_plan:
        with PLAN.open('xb') as handle:handle.write(encode(plan()))
    elif args.output:run(args.output)
    else:parser.error('--output or --write-plan is required')
