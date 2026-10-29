#!/usr/bin/env python3
"""Recover failed *original* Stan benchmark jobs without rerunning successful fits.

Records all 93 original/recovered forecasts, convergence and source hashes in
a descriptive, strictly non-production report. GitHub Actions artifacts are
treated as untrusted and rechecked against the original immutable preflight.
"""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import urllib.request

import full_backend_eval as evaluator

ORIGINAL_RUN_ID=40894977636
BACKENDS=('pymc','nutpie','cmdstanpy')

def _original_jobs(repo,token,run_id):
    if not token:
        raise ValueError('missing_actions_read_token')
    jobs=[]
    for page in range(1,5):
        uri=(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}'
             f'/jobs?per_page=100&page={page}')
        req=urllib.request.Request(uri,headers={
            'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
            'X-GitHub-Api-Version':'2022-11-28'})
        with urllib.request.urlopen(req,timeout=40) as response:
            parsed=json.load(response)
        jobs.extend(parsed['jobs'])
        if len(jobs)>=int(parsed['total_count']):
            break
    return jobs

def retry_plan(plan,jobs):
    markets=plan['markets']
    if plan.get('market_count')!=len(evaluator.MARKETS):
        raise ValueError('original_plan_not_all_markets')
    if plan.get('blocked_count'):
        raise ValueError('source_preflight_was_not_complete')
    if len(jobs)!=1+3*len(markets):
        raise ValueError('original_run_missing_matrix_jobs')
    if any(j['status']!='completed' for j in jobs):
        raise ValueError('original_run_not_finished')
    names={j['name']:j for j in jobs}
    recover=[]
    for market in sorted(markets):
        for backend in BACKENDS:
            label=f'{market} / {backend}'
            if label not in names:
                raise ValueError('missing_original_market_job:'+label)
            job=names[label]
            if job.get('conclusion')=='success':
                continue
            if backend!='cmdstanpy':
                raise ValueError('unexpected_non_stan_failure:'+label)
            recover.append(market)
    if len(set(recover))!=len(recover):
        raise ValueError('duplicate_recovery_market')
    return {'schema':'all-market-stan-recovery-plan-v1',
            'original_run':ORIGINAL_RUN_ID,
            'history_sha':plan['archive_sha'],
            'market_count':len(markets),
            'retry_count':len(recover),
            'retry_matrix':recover,
            'completed_original_success':len(markets)*3-len(recover),
            'production_untouched':True}

def _report_paths(market,backend,original,recovered):
    name=f'fit_{market}_{backend}.json'
    new=recovered/name
    return new if new.exists() else original/name

def consolidate(plan,original,recovered):
    report={'schema':'all-market-31-by-3-backend-final-audit-v1',
            'historical_archive_sha':plan['archive_sha'],
            'all_source_markets':len(evaluator.MARKETS),
            'expected_model_evaluations':len(evaluator.MARKETS)*3,
            'publication_eligible':False,
            'ranking_allowed':False,
            'is_sportsbook_line_evaluation':False,
            'markets':{},'missing_or_rejected':[]}
    n_ok=0;n_diag_pass=0
    lines=['# Full 31-market / 3-backend Bayesian shadow benchmark',
           '',
           f'Original frozen source warehouse commit: \`{plan["archive_sha"]}\`.',
           '',
           'These are training-derived fixed research thresholds, NOT observed sports-'
           'book odds or calibrated betting recommendations. **No production switch**.',
           '',
           '| Sport / stat | PyMC | Nutpie | CmdStanPy | Holdout rows |',
           '|:--|:--|:--|:--|--:|']
    for market,source in sorted(plan['markets'].items()):
        market_out={'sport':source['sport'],'stat':source['stat'],
                    'line':source['configuration']['line'],
                    'training_source_digest':source['train_source_digest'],
                    'heldout_digest':source['holdout_digest'],
                    'holdout_rows':source['heldout_rows'],
                    'backends':{}}
        cells=[]
        for backend in BACKENDS:
            item={'status':'missing'}
            path=_report_paths(market,backend,original,recovered)
            try:
                data=json.loads(path.read_text())
                if data.get('market')!=market or data.get('backend')!=backend:
                    raise ValueError('artifact_identity_mismatch')
                if data.get('train_source_digest')!=source['train_source_digest']:
                    raise ValueError('training_data_digest_mismatch')
                if data.get('holdout_digest')!=source['holdout_digest']:
                    raise ValueError('heldout_data_digest_mismatch')
                if not data.get('status','').startswith('completed_'):
                    raise ValueError('fit_not_completed:'+str(data.get('status')))
                summary=data['summary']
                if summary['n']!=2:
                    raise ValueError('missing_required_independent_seed')
                for k in ('mean_brier','mean_log_loss','mean_fit_seconds',
                          'mean_min_ess_per_second','max_rhat','minimum_ess'):
                    if not math.isfinite(float(summary[k])):
                        raise ValueError('invalid_performance_metric:'+k)
                item={'status':data['status'],'summary':summary,
                      'recovered':path.parent==recovered,
                      'posterior_diagnostics_pass':bool(
                          summary['all_replicates_pass_convergence'])}
                n_ok+=1;n_diag_pass+=int(item['posterior_diagnostics_pass'])
            except (ValueError,KeyError,TypeError,OSError) as exc:
                item['reason']=str(exc)[:180]
                report['missing_or_rejected'].append(
                    {'market':market,'backend':backend,'reason':item['reason']})
            market_out['backends'][backend]=item
            if 'summary' in item:
                s=item['summary']
                cell=(f'Brier {s["mean_brier"]:.4f}; '
                      f'ESS/s {s["mean_min_ess_per_second"]:.1f}')
                cell+= ' ✓' if item['posterior_diagnostics_pass'] else ' (not converged)'
            else:
                cell='MISSING / INVALID'
            cells.append(cell)
        report['markets'][market]=market_out
        lines.append(f'| {source["sport"]} {source["stat"]} | '+
                     ' | '.join(cells)+f' | {source["heldout_rows"]} |')
    report['complete_evaluations']=n_ok
    report['passed_all_nuts_diagnostics']=n_diag_pass
    report['missing_evaluations']=len(report['missing_or_rejected'])
    report['status']='complete_research_only' if n_ok==len(evaluator.MARKETS)*3 else 'incomplete'
    lines+=['',f'Completed with matched verified source hashes: **{n_ok}/93**.',
            f'Fits with both seeds passing all convergence gates: **{n_diag_pass}/93**.',
            f'Invalid or missing: **{report["missing_evaluations"]}/93**.',
            '',
            'Model-selection decision: no automatic promotion. Sampling speed and '
            'out-of-sample historical Brier scores alone do not establish an '
            'advantage at actual sportsbook thresholds, nor validate daily picks.'
            ]
    return report,'\n'.join(lines)+'\n'

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--preflight',type=Path,required=True)
    p.add_argument('--plan',action='store_true')
    p.add_argument('--source-run',type=int,default=ORIGINAL_RUN_ID)
    p.add_argument('--original',type=Path)
    p.add_argument('--recovered',type=Path)
    p.add_argument('--out-json',type=Path)
    p.add_argument('--out-md',type=Path)
    p.add_argument('--out-plan',type=Path)
    a=p.parse_args(argv)
    original=json.loads(a.preflight.read_text())
    if a.plan:
        if a.source_run!=ORIGINAL_RUN_ID:
            raise ValueError('different_original_benchmark_run')
        jobs=_original_jobs(os.environ.get('GITHUB_REPOSITORY',''),
                           os.environ.get('GITHUB_TOKEN',''),a.source_run)
        receipt=retry_plan(original,jobs)
        if a.out_plan:
            a.out_plan.parent.mkdir(parents=True,exist_ok=True)
            a.out_plan.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
        github_out=os.environ.get('GITHUB_OUTPUT')
        if github_out:
            with open(github_out,'a',encoding='utf-8') as stream:
                stream.write('matrix='+json.dumps(receipt['retry_matrix'],separators=(',',':'))+'\n')
                stream.write('count='+str(receipt['retry_count'])+'\n')
                stream.write('history_sha='+receipt['history_sha']+'\n')
        print(json.dumps(receipt,sort_keys=True))
        return 0
    if not (a.original and a.recovered and a.out_json and a.out_md):
        p.error('missing_aggregate_directories_or_output_paths')
    report,md=consolidate(original,a.original,a.recovered)
    for dest,txt in [(a.out_json,json.dumps(report,indent=2,sort_keys=True)+'\n'),
                     (a.out_md,md)]:
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(txt)
    print(json.dumps({k:report[k] for k in (
       'status','complete_evaluations','passed_all_nuts_diagnostics',
       'missing_evaluations')},sort_keys=True))
    return 0 if report['status']=='complete_research_only' else 2

if __name__=='__main__':
    raise SystemExit(main())
