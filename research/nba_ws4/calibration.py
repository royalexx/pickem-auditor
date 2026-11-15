"""Chronological stat/model-specific calibrators; frozen controls never mutated.

Fits only prior OOF predictions whose labels were available before target freeze.
Method, minimum sample, regularization and model/stat group are preregistered.
The untouched evaluation fold decides acceptance; no best-method selection here.
"""
import math
import numpy as np
from .evaluator import time, require, digest
from .metrics import probability, binary, paired_bootstrap


def _design(ps, method):
    p=np.clip(np.asarray(ps,dtype=float),1e-8,1-1e-8)
    if method=='platt':return np.column_stack([np.ones(len(p)),np.log(p)-np.log1p(-p)])
    if method=='beta':return np.column_stack([np.ones(len(p)),np.log(p),-np.log1p(-p)])
    raise ValueError('UNKNOWN_CALIBRATOR')


def fit_predict(prior, targets, *, method, model, stat, policy):
    require(method in ('none','platt','beta','isotonic'),'UNKNOWN_CALIBRATOR')
    require(policy['methods'] and method in policy['methods'],'UNREGISTERED_METHOD')
    require(policy['model']==model and policy['stat']==stat,'CALIBRATION_GROUP_MISMATCH')
    require(targets,'NO_EVALUATION_TARGETS')
    freeze=min(time(t['input_freeze_at']) for t in targets)
    require(time(policy['registered_at'])<freeze,'POSTHOC_CALIBRATION_POLICY')
    require(all(t['model']==model and t['stat']==stat for t in targets),'MIXED_TARGET_GROUP')
    target_games={t['event_id'] for t in targets}; target_ids={t['contract_id'] for t in targets}
    eligible=[]; excluded=[]; seen=set()
    for r in prior:
        require(r['contract_id'] not in seen,'DUPLICATE_CALIBRATION_CONTRACT'); seen.add(r['contract_id'])
        require(r['event_id'] not in target_games and r['contract_id'] not in target_ids,'CALIBRATION_EVALUATION_GAME_LEAKAGE')
        require(r['is_oof'] is True,'IN_SAMPLE_CALIBRATION_FORBIDDEN')
        require(time(r['training_cutoff'])<time(r['forecast_at'])<time(r['event_start']),'INVALID_OOF_CHRONOLOGY')
        require(r['y'] in (0,1) and not isinstance(r['y'],bool),'INVALID_LABEL')
        require(time(r['label_available_at'])>time(r['event_start']),'EARLY_CALIBRATION_LABEL')
        if r['model']!=model or r['stat']!=stat or time(r['label_available_at'])>=freeze:
            excluded.append({'contract_id':r['contract_id'],'reason':'WRONG_GROUP_OR_LABEL_NOT_YET_AVAILABLE'}); continue
        probability(r['p']); eligible.append(r)
    base=[probability(t['p']) for t in targets]
    result={'method':method,'policy_sha256':digest(policy),'fit_contract_ids':[r['contract_id'] for r in eligible],
            'excluded':excluded,'n':len(eligible),'dates':len({r['date'] for r in eligible}),
            'fit_label_cutoff':max((r['label_available_at'] for r in eligible),default=None),
            'predictions':None,'status':'BLOCKED-BY-DATA','integration_allowed':False}
    if method=='none':result.update(predictions=base,status='CONTROL'); return result
    minimum=policy['min_isotonic'] if method=='isotonic' else policy['min_parametric']
    if len(eligible)<minimum or result['dates']<policy['min_dates'] or len({r['y'] for r in eligible})<2:return result
    ps=[r['p'] for r in eligible]; ys=np.asarray([r['y'] for r in eligible],dtype=float)
    if method=='isotonic':
        from sklearn.isotonic import IsotonicRegression
        fitted=IsotonicRegression(out_of_bounds='clip',y_min=1e-8,y_max=1-1e-8).fit(ps,ys)
        preds=fitted.predict(base); params={'x':fitted.X_thresholds_.tolist(),'y':fitted.y_thresholds_.tolist()}
    else:
        from scipy.optimize import minimize
        from scipy.special import expit
        x=_design(ps,method); initial=np.array([0.,1.] if method=='platt' else [0.,1.,1.])
        penalty=policy['l2']; require(penalty>0,'UNREGULARIZED_CALIBRATION')
        def objective(w):
            z=x@w
            return float(np.sum(np.logaddexp(0,z)-ys*z)+penalty*np.sum((w-initial)**2)/2)
        def gradient(w):return x.T@(expit(x@w)-ys)+penalty*(w-initial)
        # Nonnegative slopes preserve direction/rank monotonicity within group.
        fit=minimize(objective,initial,jac=gradient,bounds=[(None,None)]+[(0,None)]*(len(initial)-1),method='L-BFGS-B')
        require(fit.success and np.all(np.isfinite(fit.x)),'CALIBRATION_OPTIMIZATION_FAILED')
        preds=expit(_design(base,method)@fit.x); params=fit.x.tolist()
    result.update(predictions=[float(p) for p in preds],parameters=params,status='FITTED_RESEARCH_ONLY')
    result['artifact_sha256']=digest({k:v for k,v in result.items() if k not in ('predictions','artifact_sha256')})
    return result


def prequential(rows, *, policy):
    """One whole calendar slate per origin; no within-slate label reuse."""
    ordered=sorted(rows,key=lambda r:(time(r['input_freeze_at']),r['contract_id']))
    out=[]
    for date in sorted({r['date'] for r in ordered}):
        targets=[r for r in ordered if r['date']==date]
        prior=[r for r in ordered if r['date']<date]
        for method in policy['methods']:
            result=fit_predict(prior,targets,method=method,model=policy['model'],stat=policy['stat'],policy=policy)
            result['date']=date
            result['target_contract_ids']=[r['contract_id'] for r in targets]
            if result['predictions'] is not None:
                pairs=[]
                for r,p in zip(targets,result['predictions']):
                    require(time(r['label_available_at'])>time(r['forecast_at']),'EARLY_EVALUATION_LABEL')
                    pairs.append(dict(r,delta=binary(p,r['y'])['brier']-binary(r['p'],r['y'])['brier']))
                result['paired_brier']=paired_bootstrap(pairs,cluster='date')
            out.append(result)
    return out


def assess_untouched(paired, *, policy):
    """Formal locked-method gate, not a production release approval.

    Both improvements and noninferiority margins must be registered before the
    first evaluated forecast. Per-game outputs remain paired within whole dates.
    """
    require(policy['primary'] in ('improvement','noninferiority'),'UNREGISTERED_ACCEPTANCE_RULE')
    require(policy['brier_margin']>=0 and policy['logloss_margin']>=0,'INVALID_MARGIN')
    require(len({r['contract_id'] for r in paired})==len(paired),'DUPLICATE_UNTOUCHED_CONTRACT')
    for r in paired:
        require(r['untouched'] is True and r['development_exposed'] is False,'DEVELOPMENT_EXPOSED_FOLD')
        require(time(policy['registered_at'])<time(r['forecast_at']),'POSTHOC_ACCEPTANCE_RULE')
    dates=len({r['date'] for r in paired});games=len({r['event_id'] for r in paired})
    result={'status':'BLOCKED-BY-DATA','dates':dates,'games':games,'n':len(paired),'release_allowed':False,
            'policy_sha256':digest(policy)}
    if dates<policy['min_dates'] or games<policy['min_games']:return result
    b=paired_bootstrap([dict(r,delta=r['brier_delta']) for r in paired],cluster='date')
    l=paired_bootstrap([dict(r,delta=r['logloss_delta']) for r in paired],cluster='date')
    result.update(brier=b,logloss=l,status='INCONCLUSIVE')
    if b['interval'] is None or l['interval'] is None:return result
    boundary=-policy['brier_margin'] if policy['primary']=='improvement' else policy['brier_margin']
    if b['interval'][1]<=boundary and l['interval'][1]<=policy['logloss_margin']:
        result['status']='PASSED'
    elif b['interval'][0]>boundary or l['interval'][0]>policy['logloss_margin']:result['status']='FAILED'
    # Independent review, multiplicity and release approval remain external gates.
    result['research_acceptance_only']=True
    return result
