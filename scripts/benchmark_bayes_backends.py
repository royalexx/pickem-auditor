#!/usr/bin/env python3
"""Read-only, actual-data benchmark of identical PyMC/Nutpie/CmdStan posteriors.

Never runs in production. Source-owned, date-frozen, same cohort, same priors;
separate per-backend receipt includes timing, diagnostics, heldout scores.
No synthetic substitutions when a required historical cohort is absent.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time
import traceback
import population_history as warehouse
import joint_population_bayes as joint

ROOT=Path(__file__).resolve().parents[1]
VERSION='joint-backend-benchmark-v1'
FIXTURES={
 'nhl_hits':dict(sport='NHL',stat='hits',train_from='2023-10-01',
                 cutoff='2023-11-25',until='2023-12-12',line=2.5,
                 max_per_position=9,min_rows=180),
 'nba_points':dict(sport='NBA',stat='points',train_from='2023-10-01',
                 cutoff='2023-11-25',until='2023-12-12',line=22.5,
                 max_per_position=7,min_rows=120),
 'nfl_rec_yards':dict(sport='NFL',stat='receiving yards',train_from='2020-09-01',
                 cutoff='2021-11-25',until='2022-01-01',line=49.5,
                 max_per_position=6,min_rows=90),
}

def freeze(root,config):
    train=warehouse.read(root,sport=config['sport'],stat=config['stat'],
                         after=config['train_from'],before=config['cutoff'])
    train=joint.training_only_subset(train,max_per_position=config['max_per_position'])
    design=joint.prepare(train,min_rows=config['min_rows'])
    future=warehouse.read(root,sport=config['sport'],stat=config['stat'],
                          after=config['cutoff'],before=config['until'])
    permitted=set(design['players'])
    heldout=[row for row in future if row['player_id'] in permitted and
             row['opponent'] in design['opponents'] and
             (row['season'] in design['seasons'] or len(design['seasons'])>=2)]
    heldout=sorted(heldout,key=lambda r:(r['game_date'],r['game_id'],r['player_id']))
    if len(heldout)<20 or len({r['game_date'] for r in heldout})<3:
        raise ValueError('insufficient_same_cohort_holdout')
    training_keys={(r['game_id'],r['player_id']) for r in train}
    if any((r['game_id'],r['player_id']) in training_keys for r in heldout):
        raise ValueError('training_holdout_overlap')
    digest=hashlib.sha256((''.join(warehouse.canonical_json(r)+'\n' for r in heldout)).encode()).hexdigest()
    return design,heldout,digest

def stan_data(d):
    is_count=int(d['family']=='count')
    return dict(N=d['rows'],P=len(d['players']),G=len(d['positions']),
                S=len(d['seasons']),O=len(d['opponents']),
                season_on=int(len(d['seasons'])>1),is_count=is_count,
                p=[v+1 for v in d['player_idx']],
                group=[v+1 for v in d['position_idx']],
                season=[v+1 for v in d['season_idx']],
                opponent=[v+1 for v in d['opponent_idx']],
                home=d['home'],workload=d['workload'],
                log_workload=[math.log(v) for v in d['workload']],
                y_value=d['value'],
                y_count=[int(v) if is_count else 0 for v in d['value']],
                base_work={'NHL':2.9,'NBA':3.1,'NFL':3.7}[d['sport']],
                rate_prior_mean=-1.4 if is_count else 0.,
                rate_prior_sd=2.5 if is_count else 5.,
                opponent_prior_sd=.22 if is_count else 1.,
                home_prior_sd=.18 if is_count else 1.,
                season_rate_prior_sd=.2 if is_count else 1.)

def sample_backend(backend,data,*,draws,tune,chains,root):
    import scipy
    import numpy as np
    timing={}
    start=time.perf_counter()
    if backend in ('pymc','nutpie'):
        import pymc as pm
        begin=time.perf_counter()
        model=joint.build(data)
        timing['model_build_sec']=time.perf_counter()-begin
        begin=time.perf_counter()
        with model:
            posterior=pm.sample(draws=draws,tune=tune,chains=chains,
                                cores=min(2,chains),random_seed=19031,
                                progressbar=False,nuts_sampler=backend,
                                nuts={'target_accept':.95},
                                compute_convergence_checks=True,
                                return_inferencedata=True)
        timing['compile_and_sampling_sec']=time.perf_counter()-begin
        diag=joint.diagnostics(posterior)
        frozen=joint.posterior_cache(posterior)
        import pymc
        versions={'pymc':pymc.__version__,'scipy':scipy.__version__}
        if backend=='nutpie':
            import nutpie
            versions['nutpie']=getattr(nutpie,'__version__','unknown')
    else:
        from cmdstanpy import CmdStanModel, cmdstan_version
        stan_file=ROOT/'benchmarks/stan/identical_joint.stan'
        begin=time.perf_counter()
        model=CmdStanModel(stan_file=str(stan_file))
        timing['stan_cpp_compile_sec']=time.perf_counter()-begin
        begin=time.perf_counter()
        fit=model.sample(data=stan_data(data),chains=chains,
                        parallel_chains=min(chains,2),
                        iter_sampling=draws,iter_warmup=tune,
                        seed=19031,adapt_delta=.95,show_progress=False)
        timing['compile_and_sampling_sec']=time.perf_counter()-begin
        summary=fit.summary()
        variables=[i for i in summary.index if not i.startswith('lp__')
                   and not i.startswith('player_effect[')
                   and not i.startswith('opponent_rate[')
                   and not i.startswith('season_workload[')
                   and not i.startswith('season_rate[')]
        max_rhat=float(np.nanmax(summary.loc[variables,'R_hat'].to_numpy()))
        min_ess=float(np.nanmin(summary.loc[variables,'ESS_bulk'].to_numpy()))
        method=fit.method_variables()
        divergences=int(np.asarray(method['divergent__']).sum())
        energy=np.asarray(method['energy__'],dtype=float)
        if energy.shape[0]!=draws and energy.shape[1]==draws:
            energy=energy.T
        bfmi=np.mean(np.diff(energy,axis=0)**2,axis=0)/np.var(energy,axis=0)
        min_bfmi=float(np.min(bfmi))
        diag=dict(max_rhat=max_rhat,min_bulk_ess=min_ess,divergences=divergences,
                  minimum_bfmi=min_bfmi,posterior_sampling_ok=bool(
                    max_rhat<=joint.MAX_RHAT and min_ess>=joint.MIN_ESS and
                    divergences==0 and min_bfmi>=.30),
                  status='research_only')
        keys=['population_workload','population_rate','player_effect',
              'season_workload','season_rate','opponent_rate','home_effect',
              'workload_sigma','count_dispersion','yardage_sigma']
        arrays={}
        for key in keys:
            if (key=='count_dispersion' and data['family']!='count') or (
                    key=='yardage_sigma' and data['family']=='count'):
                continue
            arr=np.asarray(fit.stan_variable(key))
            if key in ('count_dispersion','yardage_sigma'):
                arr=arr.reshape(-1)
            arrays[key]=arr
        frozen={'count':draws*chains,'arrays':arrays}
        # CmdStanPy 1.3 does not expose per-phase timing as public attributes;
        # include Stan compilation and all chains in measured wall time instead.
        timing['stan_reported_warmup_sec']=None
        timing['stan_reported_sampling_sec']=None
        versions={'cmdstanpy':__import__('cmdstanpy').__version__,
                  'cmdstan':str(cmdstan_version()),'scipy':scipy.__version__}
    timing['total_model_fit_wall_sec']=time.perf_counter()-start
    return diag,frozen,timing,versions

def score(data,heldout,frozen,line):
    from scipy.stats import nbinom,t
    import joint_population_holdout as hold
    cache=hold.control_cache([]) if False else None
    rows=[]
    # All backend predictions share the identical 512-draw NumPy posterior
    # predictive procedure, line and per-game deterministic random seeds.
    for item in heldout:
        ident=hashlib.sha256((item['game_id']+':'+item['player_id']+
                             ':'+item['stat']).encode()).digest()
        seed=int.from_bytes(ident[:8],'big')
        outcome=joint.forecast(None,data,player_id=item['player_id'],
            opponent=item['opponent'],season=item['season'],
            home=item['home'],line=line,draws=512,seed=seed,
            diagnostic={'posterior_sampling_ok':True},cache=frozen)
        q=outcome['q_over']
        if not (0<=q<=1 and math.isfinite(q)):
            raise ValueError('invalid_posterior_predictive_probability')
        actual=int(item['value']>line)
        rows.append((q,actual,item['game_date']))
    n=len(rows)
    return {'n':n,'heldout_days':len({x[2] for x in rows}),
            'brier':sum((q-y)**2 for q,y,_ in rows)/n,
            'log_loss':sum(-y*math.log(max(q,1e-12))-(1-y)*math.log(max(1-q,1e-12))
                           for q,y,_ in rows)/n,
            'mean_predicted_over':sum(q for q,y,d in rows)/n,
            'observed_over':sum(y for q,y,d in rows)/n,
            'conditional_on_appearance':True,'research_threshold_not_real_market':True}

def run(backend,fixture,root,*,draws,tune,chains):
    config=FIXTURES[fixture]
    report={'schema':VERSION,'backend':backend,'fixture':fixture,
            'cutoff_exclusive':config['cutoff'],'heldout_end_exclusive':config['until'],
            'line':config['line'],'sample_config':dict(draws=draws,tune=tune,chains=chains,
                                                       target_accept=.95,seed=19031),
            'status':'blocked','publication_eligible':False,
            'ranking_allowed':False,'retraining_production':False}
    started=time.perf_counter()
    try:
        design,holdout,hold_hash=freeze(root,config)
        report.update(train_rows=design['rows'],train_source_digest=design['source_digest'],
                      train_players=len(design['players']),train_seasons=design['seasons'],
                      holdout_rows=len(holdout),holdout_digest=hold_hash)
        diag,frozen,timing,versions=sample_backend(backend,design,draws=draws,
                                 tune=tune,chains=chains,root=root)
        report.update(posterior_diagnostics=diag,timing=timing,versions=versions,
                      test_scores=score(design,holdout,frozen,config['line']),
                      effective_bulk_samples_per_fit_second=(
                         diag.get('min_bulk_ess',0)/max(1e-6,timing['total_model_fit_wall_sec'])))
        report['status']='completed_diagnostics_pass' if diag.get(
            'posterior_sampling_ok') else 'completed_diagnostics_fail'
    except Exception as exc:
        report.update(error_type=type(exc).__name__,error=str(exc)[:350])
    report['total_elapsed_sec']=time.perf_counter()-started
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--backend',choices=('pymc','nutpie','cmdstanpy'),required=True)
    p.add_argument('--fixture',choices=sorted(FIXTURES),default='nhl_hits')
    p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--draws',type=int,default=300)
    p.add_argument('--tune',type=int,default=450)
    p.add_argument('--chains',type=int,default=4)
    p.add_argument('--out',type=Path,default=Path('reports/backend_benchmark.json'))
    args=p.parse_args()
    if not 100<=args.draws<=3000 or not 100<=args.tune<=3000 or args.chains not in (2,4):
        p.error('invalid_research_sampling_budget')
    report=run(args.backend,args.fixture,args.root,
               draws=args.draws,tune=args.tune,chains=args.chains)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,sort_keys=True))
    return 0 if report['status'].startswith('completed_') else 2

if __name__=='__main__':
    raise SystemExit(main())
