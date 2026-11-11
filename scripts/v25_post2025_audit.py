#!/usr/bin/env python3
"""Read-only adversarial audit of a completed 2025 count replay.

Never edits the model, fits used for forecasts, archived scores or source data.
New baselines and optimization checks are exploratory diagnostics, not promoted
models. Bootstrap intervals are descriptive under earlier 2025 exposure.
"""
from __future__ import annotations
import argparse,collections,copy,json,math,pathlib,sys
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import nbinom,poisson
from v25_opportunity_repair_replay import read,write_once,file_hash,metrics,probability_score
from v25_nfl_2024_all_volume_rolling_calibration import fit_from_past,ptransform
from v25_opportunity_2025_replay import forecast
from v25_opportunity_distribution import digest

def key(r):return (r['week'],r['game_id'],r['team'],r['player_id'],r['market'],r.get('line',r.get('research_line')))

def binary_baseline(row,p):
    # A binary-event baseline has no count distribution. Never inherit the
    # count model's mean/CRPS/intervals merely because rows are paired.
    result={**row,**probability_score(p,row['y'])}
    for field in ('mean','bias','mae','crps','coverage80','p_zero','p10','p90','p_over','p_under','p_push'):
        result[field]=None
    return result

def cluster_interval(rows,values,cluster='game_id'):
    groups=collections.defaultdict(list)
    for r,v in zip(rows,values):groups[r[cluster]].append(float(v))
    if not groups:return {'n':0}
    sums=np.array([sum(v) for _,v in sorted(groups.items())]);ns=np.array([len(v) for _,v in sorted(groups.items())])
    rng=np.random.default_rng(20261110);idx=rng.integers(0,len(ns),(2000,len(ns)))
    draws=sums[idx].sum(axis=1)/ns[idx].sum(axis=1)
    return {'n':int(ns.sum()),'clusters':len(ns),'cluster':cluster,'mean':float(sums.sum()/ns.sum()),
       'descriptive_95':np.quantile(draws,[.025,.975]).tolist(),'earlier_2025_exposure':True}

def confidence(rows,threshold=.8):
    chosen=[r for r in rows if r.get('hit') is not None and max(r['q'],1-r['q'])>=threshold]
    if not chosen:return {'n':0}
    claim=[max(r['q'],1-r['q']) for r in chosen];hits=[int((r['q']>.5)==bool(r['y'])) for r in chosen]
    return {'n':len(chosen),'hit':float(np.mean(hits)),'claimed':float(np.mean(claim)),
       'under':sum(r['q']<.5 for r in chosen),'over':sum(r['q']>.5 for r in chosen),
       'unique_games':len({r['game_id'] for r in chosen}),'unique_players':len({r['player_id'] for r in chosen}),
       'gap_game':cluster_interval(chosen,[h-p for h,p in zip(hits,claim)]),
       'gap_week':cluster_interval(chosen,[h-p for h,p in zip(hits,claim)],'week'),
       'always_under_hit_same_selected_contracts':float(np.mean([1-r['y'] for r in chosen])),
       'by_side':{side:{'n':len(z),'hit':float(np.mean([r['hit'] for r in z])) if z else None,
                     'claimed':float(np.mean([max(r['q'],1-r['q']) for r in z])) if z else None}
                  for side,z in [('under',[r for r in chosen if r['q']<.5]),('over',[r for r in chosen if r['q']>.5])]},
       'line_counts':dict(collections.Counter(str(r['line']) for r in chosen)),
       'market_counts':dict(collections.Counter(r['market'] for r in chosen))}

def global_optimum(history,saved):
    x=np.log(np.clip([r['p'] for r in history],.0005,.9995)/(1-np.clip([r['p'] for r in history],.0005,.9995)))
    y=np.asarray([r['y'] for r in history],float);lam=np.array([8.,14.]);prior=np.array([0.,1.])
    def fun(theta):
        z=theta[0]+theta[1]*x
        return float(np.sum(np.logaddexp(0,z)-y*z)+.5*np.sum(lam*(theta-prior)**2))
    def jac(theta):
        err=expit(theta[0]+theta[1]*x)-y
        return np.array([sum(err),sum(err*x)])+lam*(theta-prior)
    start=np.array([saved['a'],saved['b']]);opt=minimize(fun,start,jac=jac,method='L-BFGS-B',bounds=[(-4.5,4.5),(.05,1.8)],options={'ftol':1e-14,'gtol':1e-9,'maxiter':1000})
    pg=jac(start)
    for i,(lo,hi) in enumerate([(-4.5,4.5),(.05,1.8)]):
        if start[i]<=lo+1e-9 and pg[i]>0 or start[i]>=hi-1e-9 and pg[i]<0:pg[i]=0
    return {'old':start.tolist(),'independent_optimum':opt.x.tolist(),'objective_improvement':fun(start)-fun(opt.x),
       'max_projected_gradient_old':float(max(abs(pg))),'optimizer_success':bool(opt.success)}

def moments(history):
    players=collections.defaultdict(list);roles=collections.defaultdict(list)
    for g in sorted(history,key=lambda g:(g['season'],g['week'],g['event_id'])):
        for pid,p in g['players'].items():
            for market,v in p['values'].items():players[pid,market].append((g,p,v));roles[p['role'],market].append(v)
    prior={k:(float(np.mean(v)),float(np.var(v))) for k,v in roles.items()}
    return players,prior

def count_parameters(players,priors,pid,role,market):
    records=players.get((pid,market),[])[-8:]
    if not records or (role,market) not in priors:return None
    values=np.array([v for _,_,v in records],float);pm,pv=priors[role,market];w=len(values)/(len(values)+2.)
    mu=w*float(values.mean())+(1-w)*pm
    variance=w*float(np.var(values,ddof=1) if len(values)>1 else mu)+(1-w)*pv
    return {'mean':mu,'variance':max(mu,variance),'games':len(values),'latest_year':records[-1][0]['season'],
       'latest_week':records[-1][0]['week'],'history_teams':sorted({g['team'] for g,_,_ in records})}

def tail(par,cutoffs):
    mu,var=par['mean'],par['variance'];c=np.floor(cutoffs)
    if mu<=0:return np.zeros_like(c,dtype=float)
    if var<=mu+1e-8:return poisson.sf(c,mu)
    k=mu*mu/(var-mu)
    return nbinom.sf(c,k,k/(k+mu))

def paired_summary(new,old,metric='brier'):
    a={key(r):r for r in new};b={key(r):r for r in old};ks=sorted(a.keys()&b.keys())
    rows=[a[k] for k in ks];d=[a[k][metric]-b[k][metric] for k in ks]
    return {'game':cluster_interval(rows,d),'week':cluster_interval(rows,d,'week')}

def audit(a):
    if a.output_dir.exists():raise ValueError('immutable_audit_output_exists')
    a.output_dir.mkdir(parents=True)
    report=read(a.run/'FINAL_REPORT.json');ledger=read(a.run/'SCORED_LEDGER.json.gz')
    if digest({k:v for k,v in report.items() if k!='receipt_sha256'})!=report['receipt_sha256']:
        raise ValueError('source_report_digest_mismatch')
    allraw=[r for k,rows in ledger.items() if k.startswith('expanding|raw|') for r in rows]
    allrole=[r for k,rows in ledger.items() if k.startswith('expanding|role|') for r in rows]
    bymarket={m:confidence(ledger['expanding|role|'+m]) for m in report['markets']}
    result={'schema':'v25-post2025-readonly-audit-v1','source_receipt':report['receipt_sha256'],'model_changed':False,
       'audit_code_sha256':file_hash(pathlib.Path(__file__)),'source_report_file_sha256':file_hash(a.run/'FINAL_REPORT.json'),
       'confidence_80':confidence(allrole),'confidence_90':confidence(allrole,.9),'confidence_95':confidence(allrole,.95),
       'confidence_by_market':bymarket,'all_raw':metrics(allraw),'all_role':metrics(allrole),
       'all_always_under_hit':float(np.mean([1-r['y'] for r in allraw])),
       'raw_vs_role_paired':paired_summary(allrole,allraw)}
    histories=collections.defaultdict(list);fit_checks=[];opt_checks=[];baseline_history=collections.defaultdict(list)
    baselines=collections.defaultdict(list);coherence=[];mc=[];offer_coverage=collections.Counter();special=[];seen_examples=[]
    mean_checks=[];sourcechecks=[];calibration_status=collections.defaultdict(list)
    saved_role_index={key(r):r for r in allrole}
    for receipt in report['manifest']:
        w=receipt['week'];inp=read(a.run/receipt['input_file']);cal=read(a.run/receipt['calibration_file']);st=read(a.run/receipt['settled_file'])
        for kind in ('input','forecast','calibration','settled'):
            if file_hash(a.run/receipt[kind+'_file'])!=receipt[kind+'_sha256']:raise ValueError('changed_source_'+kind)
        # Cross-check fields the original independent rescore did not inspect.
        current_ids={g['event_id'] for g in inp['schedule']};overlap={g['event_id'] for g in inp['history']}&current_ids
        sourcechecks.append({'week':w,'current_event_id_in_training':sorted(overlap)})
        for name,saved in cal['full_parameter_preimages'].items():
            hs=histories[name];refit=fit_from_past(hs)
            same=json.dumps(refit,sort_keys=True)==json.dumps(saved,sort_keys=True)
            fit_checks.append({'week':w,'name':name,'exact_prior_only_refit_match':same,'n':len(hs)})
            if saved['active']:opt_checks.append({'week':w,'name':name,**global_optimum(hs,saved)})
        players,priors=moments(inp['history']);parameters={};linebase=[]
        for state in st['states']:
            pid=state['player_id'];market=state['market'];role=state['source_position']
            par=count_parameters(players,priors,pid,role,market);parameters[state['game_id'],state['team'],pid,market]=par
            if par:
                p=float(tail(par,np.array([state['research_line']]))[0]);q=ptransform(p,state['role'],cal['full_parameter_preimages']['expanding|'+market],'role')
                if max(q,1-q)>=.8:
                    offer_coverage['analytical_role_80:'+state['state']]+=1
                if par['latest_year']<2025:offer_coverage['player_latest_count_observation_pre2025']+=1
        state_index={key(s):s for s in st['states']}
        for offer in cal['offers']:
            if offer['model']=='expanding' and offer['method']=='role' and max(offer['q'],1-offer['q'])>=.8:
                offer_coverage['saved_role_80:'+state_index[key(offer)]['state']]+=1
        # Check analytic marginal CDF ordering, avoiding Monte Carlo artifacts.
        grouped=collections.defaultdict(dict)
        for (game,team,pid,market),par in parameters.items():
            if par:grouped[game,team,pid][market]=par
        pairs=[('receptions','targets'),('completions','pass attempts'),('solo tackles','tackles + assists'),('tackle assists','tackles + assists')]
        for (game,team,pid),pars in grouped.items():
            for small,large in pairs:
                if small not in pars or large not in pars:continue
                ks=np.arange(0,81)
                violation=tail(pars[small],ks)-tail(pars[large],ks);i=int(np.argmax(violation))
                coherence.append({'week':w,'game_id':game,'team':team,'player_id':pid,'small':small,'large':large,
                   'max_analytic_tail_violation':float(violation[i]),'threshold':int(ks[i])})
        current=[r for r in st['scores'] if r['model']=='expanding' and r['method']=='raw']
        for row in current:
            market=row['market'];par=parameters[row['game_id'],row['team'],row['player_id'],market]
            p=float(tail(par,np.array([row['line']]))[0]);q=ptransform(p,row['role'],cal['full_parameter_preimages']['expanding|'+market],'role')
            saved=saved_role_index[key(row)]
            active=cal['full_parameter_preimages']['expanding|'+market]['active']
            calibration_status['fitted' if active else 'raw_identity_warmup'].append(saved)
            mc.append({'week':w,'game_id':row['game_id'],'market':market,'raw_error':row['q']-p,
                'role_80_membership_changed':(max(saved['q'],1-saved['q'])>=.8)!=(max(q,1-q)>=.8)})
            mean_checks.append(abs(row['mean']-par['mean'])/math.sqrt(par['variance']/2048) if par['variance']>0 else 0.)
            for mode in ['market_only','role_line']:
                keys=[(market,row['role'],row['line']),(market,row['role']),(market,)] if mode=='role_line' else [(market,)]
                hs=[]
                for candidate in keys:
                    if len(baseline_history[candidate])>=30:hs=baseline_history[candidate];break
                b=(1+sum(hs))/(2+len(hs)) if hs else .5
                baselines[mode].append(binary_baseline(row,b))
            if row['market'] in ('pass attempts','completions') and max(saved['q'],1-saved['q'])>=.8:
                special.append({k:saved[k] for k in ['week','game_id','team','player_id','market','line','q','actual','hit']}|{'prior_count_parameters':par,'calibration_active':active})
        # Update all diagnostics only after this week's complete scores/maps.
        for row in st['scores']:
            if row['method']=='raw':histories[row['model']+'|'+row['market']].append({'p':row['raw_q'],'y':row['y'],'role':row['role'],'week':w})
        for row in current:
            for k in [(row['market'],row['role'],row['line']),(row['market'],row['role']),(row['market'],)]:baseline_history[k].append(row['y'])
        print('AUDIT_WEEK_DONE',w,flush=True)
    result['calibration_prior_only_refit']={'maps':len(fit_checks),'exact_matches':sum(x['exact_prior_only_refit_match'] for x in fit_checks)}
    result['calibrator_optimization']={'active_maps':len(opt_checks),'objective_improvement_over_1e_6':sum(x['objective_improvement']>1e-6 for x in opt_checks),
       'largest':sorted(opt_checks,key=lambda x:x['objective_improvement'],reverse=True)[:12]}
    result['cdf_coherence']={'pairs':len(coherence),'violation_over_one_percentage_point':sum(x['max_analytic_tail_violation']>.01 for x in coherence),
       'largest':sorted(coherence,key=lambda x:x['max_analytic_tail_violation'],reverse=True)[:15],
       'by_pair':{name:{'n':len(z),'over_1pp':sum(x['max_analytic_tail_violation']>.01 for x in z)}
                  for name,z in [(s+'<='+b,[x for x in coherence if x['small']==s and x['large']==b]) for s,b in pairs]}}
    result['monte_carlo']={'n':len(mc),'raw_probability_rmse_against_analytic':float(np.sqrt(np.mean([x['raw_error']**2 for x in mc]))),
       'role_80_cohort_membership_changes_with_exact_law':sum(x['role_80_membership_changed'] for x in mc),
       'max_sample_mean_standard_errors':float(max(mean_checks))}
    result['baseline_controls']={name:{'metrics':metrics(rows),'raw_model_minus_baseline':paired_summary(allraw,rows),
       'role_model_minus_baseline':paired_summary(allrole,rows),'per_market':{m:metrics([r for r in rows if r['market']==m]) for m in report['markets']},
       'posthoc_exploratory_not_preregistered':True} for name,rows in baselines.items()}
    result['high_confidence_offer_coverage']=dict(offer_coverage)
    result['calibration_status']={k:{'all':metrics(v),'high80':confidence(v)} for k,v in calibration_status.items()}
    result['current_event_overlap_checks']=sourcechecks;result['qb_80_details']=special
    result['receipt_sha256']=digest(result)
    write_once(a.output_dir/'AUDIT_METRICS.json',result)
    write_once(a.output_dir/'CALIBRATION_REFIT_AND_OPTIMALITY.json',{'refits':fit_checks,'optimization':opt_checks})
    write_once(a.output_dir/'CDF_COHERENCE_ALL.json.gz',coherence)
    write_once(a.output_dir/'BASELINE_SCORES.json.gz',dict(baselines))
    print('AUDIT_COMPLETED',flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=pathlib.Path,required=True);p.add_argument('--output-dir',type=pathlib.Path,required=True)
    audit(p.parse_args())
if __name__=='__main__':main()
