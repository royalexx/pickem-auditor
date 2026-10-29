#!/usr/bin/env python3
"""Diagnostics-first, matched sampler experiment over the frozen 31-market cohort.

All three backends fit the UNCHANGED likelihood and priors. Original 31-market
preflight source hashes must match. A fixed, predeclared sampling ladder is
applied identically. Forecast scoring is forbidden until BOTH independent
seeds of a stage pass the SAME Rhat, bulk ESS, tail ESS, BFMI and divergence
criteria for all source-relevant model parameters including player/opponent
effects. Never promotes or changes betting/pick rankings.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import time
import numpy as np
import xarray as xr
from arviz_stats import ess, rhat
import full_backend_eval as historic
import benchmark_bayes_backends as sampler

VERSION='matched-convergence-benchmark-v1'
# Draws are PER CHAIN. Stages are fixed before observing any outcomes.
STAGES=(
    dict(name='initial',draws=1200,tune=1600,target_accept=.99),
    dict(name='extended',draws=2400,tune=3000,target_accept=.995),
    dict(name='geometry_warning',draws=3800,tune=4500,target_accept=.997),
)
SEEDS=(19031,29031)
CORE_KEYS=(
 'population_workload','population_rate','player_chol_stds',
 'player_correlation','workload_sigma','opponent_rate_sd','home_effect',
 'player_effect','opponent_rate',
)
MULTI_SEASON_KEYS=(
 'season_workload_sd','season_rate_sd','season_workload','season_rate',
)

def _numbers(result):
    """Get rank-normalized ArviZ-stat result without broadcasting variables."""
    if isinstance(result,xr.Dataset):
        items=[np.asarray(result[name],dtype=float).ravel()
               for name in result.data_vars]
        return np.concatenate(items)
    return np.asarray(result,dtype=float).ravel()

def common_diagnostics(cache,backend_diag,design,*,draws,chains):
    """Strictly identical diagnostics and variables across PyMC/Nutpie/Stan.

    CmdStanPy stan_variable concatenates whole chains in order (CmdStanPy
    1.3.0 API). PyMC posterior_cache does the same. Never flatten chains in
    interleaved draw order or Rhat/ESS would be invalid.
    """
    keys=list(CORE_KEYS)
    keys.append('count_dispersion' if design['family']=='count' else 'yardage_sigma')
    if len(design['seasons'])>1:
        keys.extend(MULTI_SEASON_KEYS)
    arrays=cache.get('arrays',{})
    missing=sorted(set(keys)-set(arrays))
    if missing:
        raise ValueError('missing_matched_diagnostic_parameters:'+','.join(missing))
    if cache['count']!=draws*chains:
        raise ValueError('posterior_chain_draw_count_mismatch')
    extreme_rhat=0.
    least_bulk=float('inf')
    least_tail=float('inf')
    worst_name=None
    parameter_count=0
    for key in keys:
        raw=np.asarray(arrays[key],dtype=float)
        if raw.shape[0]!=draws*chains:
            raise ValueError('nonconformant_'+key+'_posterior_draw_order')
        chain_draws=raw.reshape((chains,draws)+raw.shape[1:])
        if not np.all(np.isfinite(chain_draws)):
            raise ValueError('nonfinite_posterior_'+key)
        dims=('chain','draw')+tuple(f'dim{i}' for i in range(raw.ndim-1))
        ds=xr.Dataset({'value':(dims,chain_draws)})
        rh=_numbers(rhat(ds,var_names=['value']))
        bulk=_numbers(ess(ds,var_names=['value'],method='bulk'))
        tail=_numbers(ess(ds,var_names=['value'],method='tail'))
        if not (np.all(np.isfinite(rh)) and np.all(np.isfinite(bulk))
                and np.all(np.isfinite(tail))):
            raise ValueError('invalid_shared_convergence_diagnostics:'+key)
        peak=float(np.max(rh))
        if peak>extreme_rhat:
            extreme_rhat=peak
            worst_name=key
        least_bulk=min(least_bulk,float(np.min(bulk)))
        least_tail=min(least_tail,float(np.min(tail)))
        parameter_count+=int(rh.size)
    divergences=int(backend_diag['divergences'])
    bfmi=float(backend_diag['minimum_bfmi'])
    passed=bool(extreme_rhat<=1.01 and least_bulk>=400 and least_tail>=400
                and divergences==0 and bfmi>=.30)
    return {'status':'passed' if passed else 'failed',
            'posterior_sampling_ok':passed,
            'max_rank_rhat':extreme_rhat,'min_bulk_ess':least_bulk,
            'min_tail_ess':least_tail,'divergences':divergences,
            'minimum_bfmi':bfmi,'worst_rhat_parameter_group':worst_name,
            'parameter_components_tested':parameter_count,
            'parameter_groups_tested':keys,
            'common_library':'arviz-stats',
            'common_limits':{'max_rank_rhat':1.01,'min_bulk_ess':400,
                             'min_tail_ess':400,'max_divergences':0,
                             'min_bfmi':.30}}

def evaluate(root,plan,market,backend,*,max_stages=3):
    receipt={'schema':VERSION,'market':market,'backend':backend,
             'model_changed':False,'likelihood_prior_changed':False,
             'status':'blocked','ranking_allowed':False,
             'publication_eligible':False,'is_sportsbook_line_evaluation':False,
             'chain_count':4,'seeds':list(SEEDS),'attempts':[]}
    if max_stages not in (1,2,3):raise ValueError('invalid_predeclared_stage_count')
    try:
        if market not in historic.MARKETS:raise ValueError('unknown_market')
        expected_sha=plan.get('archive_sha')
        if not expected_sha or os.environ.get('FROZEN_WAREHOUSE_SHA')!=expected_sha:
            raise ValueError('source_archive_not_pinned_to_preflight')
        subprocess.run(['git','cat-file','-e',expected_sha+'^{commit}'],
                       cwd=root,check=True,capture_output=True)
        record=plan['markets'][market]
        if record['status']!='ready':raise ValueError('source_preflight_not_ready')
        config=historic.config_for_market(root,market)
        design,holdout,heldout_digest=sampler.freeze(root,config)
        if (historic._digest(config)!=record['configuration_sha256'] or
                design['source_digest']!=record['train_source_digest'] or
                heldout_digest!=record['holdout_digest']):
            raise ValueError('source_digest_or_configuration_mismatch')
        receipt.update(status='running',source_archive=expected_sha,
                       train_digest=design['source_digest'],
                       holdout_digest=heldout_digest,
                       train_rows=design['rows'],holdout_rows=len(holdout),
                       fixed_training_only_line=config['line'],
                       diagnostic_policy='shared_all_hierarchy_and_effects')
        start=time.perf_counter()
        for stage in STAGES[:max_stages]:
            outcomes=[]
            for seed in SEEDS:
                diag,cache,timing,versions=sampler.sample_backend(
                    backend,design,draws=stage['draws'],tune=stage['tune'],
                    chains=4,root=root,seed=seed,
                    target_accept=stage['target_accept'])
                matched=common_diagnostics(
                    cache,diag,design,draws=stage['draws'],chains=4)
                attempt={'stage':stage,'seed':seed,'common_diagnostics':matched,
                         'original_backend_diagnostics':diag,'timing':timing,
                         'versions':versions,'fit_time_seconds':timing['total_model_fit_wall_sec']}
                outcomes.append((attempt,cache))
                receipt['attempts'].append(attempt)
                if not matched['posterior_sampling_ok']:
                    # A seed failure makes this stage ineligible. All backends
                    # use the same deterministic early escalation rule.
                    break
            if (len(outcomes)==len(SEEDS) and all(
                    x['common_diagnostics']['posterior_sampling_ok']
                    for x,_ in outcomes)):
                for x,cache in outcomes:
                    x['holdout']=sampler.score(
                        design,holdout,cache,config['line'])
                    x['ess_per_second']=x['common_diagnostics']['min_bulk_ess']/max(
                        x['timing']['total_model_fit_wall_sec'],1e-9)
                receipt.update(status='converged_heldout_scored',
                               selected_stage=stage['name'],
                               total_fit_wall_seconds=sum(
                                   x['fit_time_seconds'] for x in receipt['attempts']),
                               mean_brier=sum(x['holdout']['brier'] for x,_ in outcomes)/2,
                               mean_log_loss=sum(x['holdout']['log_loss'] for x,_ in outcomes)/2,
                               mean_ess_per_second=sum(x['ess_per_second'] for x,_ in outcomes)/2)
                break
        if receipt['status']=='running':
            receipt.update(status='not_converged_no_predictive_comparison',
                           total_fit_wall_seconds=sum(
                               x['fit_time_seconds'] for x in receipt['attempts']))
        receipt['elapsed_wall_seconds']=time.perf_counter()-start
    except Exception as exc:
        receipt.update(status='evaluation_error',error=type(exc).__name__+':'+str(exc)[:350])
    return receipt

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=historic.ROOT)
    p.add_argument('--plan-file',type=Path,required=True)
    p.add_argument('--market',choices=sorted(historic.MARKETS),required=True)
    p.add_argument('--backend',choices=('pymc','nutpie','cmdstanpy'),required=True)
    p.add_argument('--max-stages',type=int,choices=(1,2,3),default=3)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    plan=json.loads(a.plan_file.read_text())
    result=evaluate(a.root,plan,a.market,a.backend,max_stages=a.max_stages)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({key:result.get(key) for key in (
        'market','backend','status','selected_stage','mean_brier','error')},
        sort_keys=True))
    # A non-converged research posterior is a completed, EXPLICITLY REJECTED
    # result, not a success. Raise on operational errors, not valid nonconvergence.
    return 2 if result['status']=='evaluation_error' else 0

if __name__=='__main__':
    raise SystemExit(main())
