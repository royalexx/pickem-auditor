#!/usr/bin/env python3
"""Reconcile frozen-market NUTS evaluations without promoting failed posteriors.

The three backend implementations sample one common generative model.
A speed comparison is valid only for a market where all THREE backends have
two independent seeds passing the common convergence gates. Nonconvergence
is NOT counted as a predictive loss, and scores are never imputed.
"""
from __future__ import annotations
import argparse
import collections
import json
import math
from pathlib import Path

BACKENDS=('pymc','nutpie','cmdstanpy')
APPROVED='converged_heldout_scored'
REJECTED='not_converged_no_predictive_comparison'
VERSION='converged-bayesian-backend-audit-v1'
FROZEN='cb3e26d8c251160dfecb2cb8cee312deeb3b5ed1'

def reconcile(items,*,expected):
    if expected not in (12,93):
        raise ValueError('unsupported_predeclared_benchmark_scope')
    by_market={}
    invalid=[]
    for artifact,item in items:
        market=item.get('market')
        backend=item.get('backend')
        key=(market,backend)
        if not market or backend not in BACKENDS or key in by_market:
            invalid.append({'file':str(artifact),'reason':'invalid_duplicate_or_unknown_identity'})
            continue
        if item.get('schema')!='matched-convergence-benchmark-v1':
            invalid.append({'file':str(artifact),'reason':'wrong_benchmark_schema'})
            continue
        if item.get('source_archive')!=FROZEN:
            invalid.append({'file':str(artifact),'reason':'unverified_historical_source_sha'})
            continue
        if not item.get('train_digest') or not item.get('holdout_digest'):
            invalid.append({'file':str(artifact),'reason':'missing_source_digest'})
            continue
        if item.get('model_changed') or item.get('likelihood_prior_changed'):
            invalid.append({'file':str(artifact),'reason':'model_equivalence_not_retained'})
            continue
        status=item.get('status')
        if status not in (APPROVED,REJECTED):
            invalid.append({'file':str(artifact),'reason':'operational_failure_or_unknown_status:'+str(status)})
            continue
        if item.get('chain_count')!=4 or item.get('seeds')!=[19031,29031]:
            invalid.append({'file':str(artifact),'reason':'mismatched_chain_or_seed_protocol'})
            continue
        if status==REJECTED and any(k in item for k in ('mean_brier','mean_log_loss','mean_ess_per_second')):
            invalid.append({'file':str(artifact),'reason':'unconverged_posterior_had_predictive_score'})
            continue
        if status==APPROVED:
            attempts=item.get('attempts',[])
            ok=[a for a in attempts if 'holdout' in a]
            if len(ok)!=2 or {a['seed'] for a in ok}!={19031,29031}:
                invalid.append({'file':str(artifact),'reason':'no_two_approved_independent_seed_scores'})
                continue
            if any(not a.get('common_diagnostics',{}).get('posterior_sampling_ok') for a in ok):
                invalid.append({'file':str(artifact),'reason':'forecasted_unconverged_seed'})
                continue
            if not all(math.isfinite(float(item[k])) for k in (
                    'mean_brier','mean_log_loss','mean_ess_per_second',
                    'total_fit_wall_seconds')):
                invalid.append({'file':str(artifact),'reason':'invalid_approved_metrics'})
                continue
        by_market[key]=item
    if len(by_market)!=expected or invalid:
        reason='incomplete_or_invalid_benchmark_artifact_set'
    else:
        reason=None
    sport_summary=collections.defaultdict(lambda:collections.Counter())
    markets={}
    for market in sorted({m for m,_ in by_market}):
        backends={b:by_market.get((market,b)) for b in BACKENDS}
        representative=next((v for v in backends.values() if v),None)
        sport=market.split('_',1)[0].upper()
        source_train={v['train_digest'] for v in backends.values() if v}
        source_hold={v['holdout_digest'] for v in backends.values() if v}
        identical_source=(len(source_train)==1 and len(source_hold)==1 and
                          all(backends.values()))
        passing={b:v for b,v in backends.items() if v and v.get('status')==APPROVED}
        all_three=identical_source and len(passing)==3
        if all_three:
            fastest=min(passing,key=lambda b:passing[b]['total_fit_wall_seconds'])
            speed={b:passing[b]['total_fit_wall_seconds'] for b in BACKENDS}
            brier_range=max(v['mean_brier'] for v in passing.values())-min(
                v['mean_brier'] for v in passing.values())
            sport_summary[sport]['fully_comparable_markets']+=1
        else:
            fastest=None;speed=None;brier_range=None
            sport_summary[sport]['not_fully_comparable_markets']+=1
        sport_summary[sport]['markets']+=1
        for b in BACKENDS:
            if b in passing:sport_summary[sport][b+'_converged']+=1
        markets[market]={'sport':sport,
            'identical_source_across_backends':identical_source,
            'all_three_backends_converged':bool(all_three),
            'fastest_reliable_backend':fastest,
            'time_to_convergence_seconds':speed,
            'posterior_predictive_brier_range_after_convergence':brier_range,
            'backend_results':{b:{
                'status':v['status'] if v else 'missing',
                'converged':b in passing,
                'selected_stage':v.get('selected_stage') if v else None,
                'total_fit_wall_seconds':v.get('total_fit_wall_seconds') if v else None,
                'brier_only_if_converged':v.get('mean_brier') if v else None,
                'attempts':len(v.get('attempts',[])) if v else 0,
                'last_common_diagnostics':(
                    v.get('attempts',[])[-1].get('common_diagnostics')
                    if v and v.get('attempts') else None)}
                 for b,v in backends.items()}}
        if not identical_source:
            invalid.append({'market':market,'reason':'backend_training_holdout_source_mismatch'})
    overall={'schema':VERSION,'status':'complete' if not reason and not invalid else 'invalid_or_incomplete',
             'expected_backend_market_evaluations':expected,
             'accepted_backend_market_evaluations':len(by_market),
             'frozen_history_source_sha':FROZEN,
             'model_was_unchanged':True,'production_weight_changes':False,
             'sports':{k:dict(v) for k,v in sorted(sport_summary.items())},
             'converged_backend_market_evaluations':sum(
                 v['status']==APPROVED for v in by_market.values()),
             'fully_comparable_markets':sum(v['all_three_backends_converged']
                                            for v in markets.values()),
             'invalid':invalid,'markets':markets,
             'not_converged_does_not_mean_inaccurate':True,
             'prediction_scores_comparable_only_if_converged':True}
    return overall

def markdown(result):
    lines=['# Matched Bayesian sampler convergence audit','',
           '**Research-only; no production picks or model-weight changes.**','',
           f'**Frozen source history:** \`{result["frozen_history_source_sha"]}\`','',
           f'**Artifact status:** {result["status"]}; '+
           f'{result["accepted_backend_market_evaluations"]}/'+
           f'{result["expected_backend_market_evaluations"]} matched backend evaluations.',
           f'**Converged:** {result["converged_backend_market_evaluations"]}; '+
           f'**all three converged for same market:** {result["fully_comparable_markets"]}.',
           '',
           'Only when ALL THREE pass shared diagnostics do we compare time to '+
           'convergence. Differences in Brier between implementations of the SAME '+
           'likelihood are not independent evidence of a superior predictive model.',
           '',
           '| Market | PyMC | Nutpie | CmdStanPy | All 3? |',
           '|---|---|---|---|---|']
    for market,record in sorted(result['markets'].items()):
        labels=[]
        for b in BACKENDS:
            detail=record['backend_results'][b]
            if detail['converged']:
                labels.append(f'PASS ({detail["selected_stage"]})')
            elif detail['status']=='missing':labels.append('MISSING')
            else:labels.append('NOT CONVERGED')
        lines.append(f'| {market} | '+' | '.join(labels)+
                     (' | YES |' if record['all_three_backends_converged']
                      else ' | NO — no backend ranking |'))
    lines+=['','## Conclusions','',
            'A convergence failure is **not** a forecast loss; that model is '+
            'unapproved for comparative predictive scoring. More iterations '+
            'cannot guarantee convergence for ill-conditioned hierarchical posteriors.',
            '',
            'If NFL divergences persist, investigate prior predictive scales, '+
            'nonidentifiability, sparse counts, partial pooling and correlated '+
            'player effects before designing a versioned, same-prior reparameterization.',
            '',
            '**Do not change production ranking weights on this evidence.**']
    if result['invalid']:
        lines+=['','## Missing/invalid receipts','',
                '\n'.join('- '+str(x) for x in result['invalid'][:50])]
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--expected',type=int,choices=(12,93),required=True)
    p.add_argument('--out-json',type=Path,required=True)
    p.add_argument('--out-md',type=Path,required=True)
    args=p.parse_args()
    paths=sorted(args.root.rglob('matched_*.json'))
    items=[]
    for path in paths:
        try:items.append((str(path),json.loads(path.read_text())))
        except (OSError,ValueError):
            items.append((str(path),{}))
    result=reconcile(items,expected=args.expected)
    for filename,content in ((args.out_json,json.dumps(result,sort_keys=True,indent=2)+'\n'),
                             (args.out_md,markdown(result))):
        filename.parent.mkdir(exist_ok=True,parents=True)
        filename.write_text(content)
    print(json.dumps({k:result[k] for k in ('status','expected_backend_market_evaluations',
        'accepted_backend_market_evaluations','converged_backend_market_evaluations',
        'fully_comparable_markets')},sort_keys=True))
    return 0 if result['status']=='complete' else 2

if __name__=='__main__':
    raise SystemExit(main())
