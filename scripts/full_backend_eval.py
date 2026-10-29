#!/usr/bin/env python3
"""Source-audited, every-stat sampler comparison; NEVER used for production picks.

Eligible markets are enumerated from population_history, not from a selected
list of favorable outcomes. All inputs/digests frozen before sampler runs.
No current odds, no historical bookmaker lines, and no market promotion.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
import population_history as history
import benchmark_bayes_backends as benchmark

ROOT=Path(__file__).resolve().parents[1]
VERSION='all-market-backend-evaluation-v1'
SEEDS=(19031,29031)
MARKETS={
    (sport.lower()+'_'+history.slug(stat)):(sport,stat)
    for sport in history.SPORTS
    for stat in (*history.COUNT[sport],*history.CONTINUOUS.get(sport,()))
}
WINDOWS={
    'NHL':('2023-10-01','2023-12-15','2024-01-09'),
    'NBA':('2023-10-01','2023-12-15','2024-01-09'),
    'NFL':('2023-09-01','2024-11-20','2025-01-31'),
}
PER_POSITION={'NHL':16,'NBA':8,'NFL':16}

def config_for_market(root,market):
    sport,stat=MARKETS[market]
    start,cutoff,until=WINDOWS[sport]
    train=history.read(root,sport=sport,stat=stat,after=start,before=cutoff)
    cohort=benchmark.joint.training_only_subset(
        train,max_per_position=PER_POSITION[sport])
    # This research threshold comes ONLY from training observations, never
    # the heldout values, sportsbook quotes, or observed model performance.
    if len(cohort)<300:
        raise ValueError('insufficient_pre_cutoff_market_rows:'+str(len(cohort)))
    ordered=sorted(float(row['value']) for row in cohort)
    typical=ordered[int(.55*(len(ordered)-1))]
    line=float(math.floor(typical)+.5)
    if history.family(sport,stat)=='count':
        line=max(0.5,line)
    return dict(sport=sport,stat=stat,train_from=start,cutoff=cutoff,
                until=until,line=line,max_per_position=PER_POSITION[sport],
                min_rows=300)

def _digest(config):
    return hashlib.sha256(history.canonical_json(config).encode()).hexdigest()

def build_plan(root,archive_sha=None):
    outcomes={}
    ready=[]
    for market in sorted(MARKETS):
        sport,stat=MARKETS[market]
        receipt={'market':market,'sport':sport,'stat':stat,
                 'status':'blocked','source_verified':False}
        try:
            config=config_for_market(root,market)
            design,heldout,heldout_sha=benchmark.freeze(root,config)
            receipt.update(status='ready',source_verified=True,
                           configuration=config,configuration_sha256=_digest(config),
                           train_source_digest=design['source_digest'],
                           holdout_digest=heldout_sha,
                           train_rows=design['rows'],train_players=len(design['players']),
                           train_seasons=design['seasons'],
                           heldout_rows=len(heldout),
                           heldout_dates=len({r['game_date'] for r in heldout}))
            ready.append(market)
        except (ValueError,KeyError,TypeError,OSError) as error:
            receipt.update(reason=type(error).__name__+':'+str(error)[:270])
        outcomes[market]=receipt
    return dict(schema=VERSION,archive_sha=archive_sha,market_count=len(MARKETS),
                ready_count=len(ready),blocked_count=len(MARKETS)-len(ready),
                ready_matrix=ready,markets=outcomes,production_untouched=True,
                no_live_betting_lines=True,publication_eligible=False)

def _archive_sha():
    try:
        return subprocess.check_output(['git','rev-parse',
            'refs/remotes/origin/data/bayesian-history'],text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        return None

def run_market(root,market,backend,plan,*,draws,tune,chains,replicates):
    started=time.perf_counter()
    report={'schema':VERSION,'market':market,'backend':backend,
            'status':'blocked','replicate_count_requested':replicates,
            'draws_per_chain':draws,'warmup_per_chain':tune,'chains':chains,
            'target_accept':.95,'seed_policy':'fixed_independent_research_seeds',
            'production_untouched':True,'publication_eligible':False,
            'ranking_allowed':False}
    try:
        if market not in MARKETS:
            raise ValueError('unsupported_market')
        record=plan['markets'][market]
        if record['status']!='ready':
            raise ValueError('market_preflight_blocked:'+record.get('reason','unknown'))
        if plan['archive_sha'] and _archive_sha()!=plan['archive_sha']:
            raise ValueError('history_warehouse_snapshot_sha_changed')
        config=config_for_market(root,market)
        if _digest(config)!=record['configuration_sha256']:
            raise ValueError('market_training_configuration_drift')
        design,holdout,heldout_sha=benchmark.freeze(root,config)
        if (design['source_digest']!=record['train_source_digest'] or
                heldout_sha!=record['holdout_digest']):
            raise ValueError('source_verified_training_or_heldout_drift')
        report.update(status='running',config=config,
                      train_rows=design['rows'],
                      train_players=len(design['players']),
                      train_seasons=design['seasons'],
                      heldout_rows=len(holdout),
                      train_source_digest=design['source_digest'],
                      holdout_digest=heldout_sha,replicates=[])
        for ix,seed in enumerate(SEEDS[:replicates]):
            diagnostic,cache,timing,versions=benchmark.sample_backend(
                backend,design,draws=draws,tune=tune,chains=chains,
                root=root,seed=seed)
            scoring=benchmark.score(design,holdout,cache,config['line'])
            fit_sec=timing['total_model_fit_wall_sec']
            report['replicates'].append({
                'seed':seed,'diagnostics':diagnostic,'timing':timing,
                'versions':versions,'score':scoring,
                'min_bulk_ess_per_second':diagnostic['min_bulk_ess']/fit_sec})
        n=len(report['replicates'])
        report['summary']={
            'n':n,
            'mean_fit_seconds':statistics.mean(x['timing']['total_model_fit_wall_sec']
                                               for x in report['replicates']),
            'mean_min_ess_per_second':statistics.mean(
                x['min_bulk_ess_per_second'] for x in report['replicates']),
            'mean_brier':statistics.mean(x['score']['brier'] for x in report['replicates']),
            'mean_log_loss':statistics.mean(
                x['score']['log_loss'] for x in report['replicates']),
            'max_rhat':max(x['diagnostics']['max_rhat'] for x in report['replicates']),
            'minimum_ess':min(x['diagnostics']['min_bulk_ess'] for x in report['replicates']),
            'divergences':sum(x['diagnostics']['divergences'] for x in report['replicates']),
            'all_replicates_pass_convergence':all(
                x['diagnostics']['posterior_sampling_ok'] for x in report['replicates']),
            'mean_predicted_over':statistics.mean(
                x['score']['mean_predicted_over'] for x in report['replicates']),
            'observed_over':report['replicates'][0]['score']['observed_over']
        }
        report['status']='completed_convergence_pass' if report['summary'][
            'all_replicates_pass_convergence'] else 'completed_diagnostics_fail'
    except Exception as error:
        report.update(status='blocked_or_failed',error=type(error).__name__+':'+str(error)[:340])
    report['wall_seconds']=time.perf_counter()-started
    return report

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--plan',action='store_true')
    p.add_argument('--plan-file',type=Path,
                   default=Path('reports/full_backend_preflight.json'))
    p.add_argument('--market',choices=sorted(MARKETS))
    p.add_argument('--backend',choices=('pymc','nutpie','cmdstanpy'))
    p.add_argument('--draws',type=int,default=500)
    p.add_argument('--tune',type=int,default=700)
    p.add_argument('--chains',type=int,default=4)
    p.add_argument('--replicates',type=int,default=2)
    p.add_argument('--out',type=Path,default=Path('reports/full_backend_result.json'))
    a=p.parse_args(argv)
    if a.plan:
        result=build_plan(a.root,archive_sha=_archive_sha())
        a.plan_file.parent.mkdir(parents=True,exist_ok=True)
        a.plan_file.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
        print(json.dumps({'market_count':result['market_count'],
             'ready_count':result['ready_count'],
             'blocked_count':result['blocked_count'],
             'blocked':{k:v['reason'] for k,v in result['markets'].items()
                        if v['status']=='blocked'}},sort_keys=True))
        output=os.getenv('GITHUB_OUTPUT')
        if output:
            with open(output,'a',encoding='utf-8') as handle:
                handle.write('matrix='+json.dumps(result['ready_matrix'],
                                                  separators=(',',':'))+'\n')
                handle.write('ready_count='+str(result['ready_count'])+'\n')
                handle.write('history_sha='+str(result['archive_sha'])+'\n')
        return 0
    if not (a.market and a.backend and 200<=a.draws<=3000 and
            200<=a.tune<=3500 and a.chains==4 and a.replicates in (1,2)):
        p.error('invalid_backend_or_research_sampling_configuration')
    plan=json.loads(a.plan_file.read_text())
    result=run_market(a.root,a.market,a.backend,plan,draws=a.draws,
                      tune=a.tune,chains=a.chains,replicates=a.replicates)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'market':a.market,'backend':a.backend,
                      'status':result['status'],
                      'summary':result.get('summary'),
                      'error':result.get('error')},sort_keys=True))
    return 0 if result['status'].startswith('completed_') else 2

if __name__=='__main__':
    raise SystemExit(main())
