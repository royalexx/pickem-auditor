"""Prospective evaluation of a fixed context operator; no new prediction model."""
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import random
import probability_blend as pb
from shared_context import VERSION

METHOD=VERSION+'|'+pb.VERSION

def path(root,scope):return pb.config_path(root,scope).parent.parent/'context_validation'/pb.config_path(root,scope).name

def probabilities(win,push):
    values=[win,push,1-win-push]
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not 0<=x<=1 for x in values):
        raise ValueError('invalid probability mass')
    return values

def rows_from_snapshots(rows,scope):
    groups={}
    # Reuse the same source/version/time eligibility and earliest-forecast rules.
    transformed=[]
    for r in rows:
        context=r.get('shared_context') or {}
        if context.get('version')!=VERSION or not context.get('eligible') or not context.get('applied'):continue
        transformed.append({**r,'shared_context':None,'_original_context':context})
    eligible=pb.from_snapshots(transformed,scope)
    allowed={(r['id'],r['forecast_at']) for r in eligible}
    for r in sorted(transformed,key=lambda r:r['forecast_at']):
        ident='|'.join(str(r.get(k) or '') for k in ('game_date','sport','player','stat','side','reference_line'))
        if (ident,r.get('forecast_at')) not in allowed or ident in groups:continue
        c=r['_original_context'];blend=r.get('blend') or {}
        try:
            baseline=probabilities(blend['q_win'],blend['q_push'])
            contextual=probabilities(c['q_win'],c['q_push'])
        except (KeyError,ValueError,TypeError):continue
        groups[ident]=dict(id=ident,date=r['game_date'],baseline=baseline,context=contextual,outcome=r['outcome'],
                          blend_fingerprint=blend.get('config_version') or 'A_ONLY')
    return list(groups.values())

def fit(rows,scope,*,fingerprint=None):
    data=sorted(rows_from_snapshots(rows,scope),key=lambda r:r['date'])
    if fingerprint is not None:data=[r for r in data if r['blend_fingerprint']==fingerprint]
    if len(data)<400:raise ValueError('need 300 earlier and 100 later context forecasts')
    fingerprints={r['blend_fingerprint'] for r in data}
    if len(fingerprints)!=1:raise ValueError('context validation must use one deployed blend fingerprint')
    cutoff=data[max(300,int(len(data)*.75))]['date']
    train=[r for r in data if r['date']<cutoff];holdout=[r for r in data if r['date']>=cutoff]
    if len(train)<300 or len(holdout)<100:raise ValueError('insufficient distinct chronological dates')
    def loss(group,key):
        return sum(-math.log(max(1e-12,r[key][('win','push','loss').index(r['outcome'])])) for r in group)/len(group)
    days={d:[r for r in holdout if r['date']==d] for d in {r['date'] for r in holdout}}
    rng=random.Random(1729);improvements=[]
    for _ in range(1000):
        sample=[r for d in rng.choices(sorted(days),k=len(days)) for r in days[d]]
        improvements.append(loss(sample,'baseline')-loss(sample,'context'))
    lower=sorted(improvements)[24] if len(days)>=20 else 0.
    calibration={}
    for i,outcome in enumerate(('win','push','loss')):
        calibration[outcome]=dict(mean_prediction=sum(r['context'][i] for r in holdout)/len(holdout),
                                 observed_frequency=sum(r['outcome']==outcome for r in holdout)/len(holdout))
    return dict(scope=scope,method=METHOD,blend_fingerprint=next(iter(fingerprints)),
        input_digest=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),
        validation=dict(score_rule=pb.SCORE_RULE,train_n=len(train),holdout_n=len(holdout),
            train_end=train[-1]['date'],holdout_start=holdout[0]['date'],holdout_end=holdout[-1]['date'],
            holdout_dates=len(days),baseline_log_loss=loss(holdout,'baseline'),context_log_loss=loss(holdout,'context'),
            improvement_ci_low=lower,calibration=calibration))

def eligible(config,scope,fingerprint,as_of):
    try:
        if not isinstance(config,dict):return False
        ev=config['validation']
        if not pb.valid_evidence(ev,'baseline_log_loss','context_log_loss',as_of):return False
        return (config['scope']==scope and config['method']==METHOD and config['blend_fingerprint']==fingerprint and
                ev['score_rule']==pb.SCORE_RULE and ev['train_n']>=300 and ev['holdout_n']>=100 and ev['holdout_dates']>=20 and
                ev['train_end']<ev['holdout_start']<=ev['holdout_end'] and date.fromisoformat(ev['holdout_end'])<as_of and
                math.isfinite(ev['improvement_ci_low']) and ev['improvement_ci_low']>0 and
                math.isfinite(ev['context_log_loss']) and math.isfinite(ev['baseline_log_loss']) and
                ev['context_log_loss']<ev['baseline_log_loss'])
    except (KeyError,ValueError,TypeError):return False

def verify(root,scope,blend,as_of):
    try:
        cfg=json.loads(path(root,scope).read_text())
        return eligible(cfg,scope,blend.get('config_version') or 'A_ONLY',as_of)
    except (OSError,ValueError):return False

def fit_scopes(rows,root,as_of=None):
    result={};as_of=as_of or date.today()
    scopes={f"{r.get('sport')}|{r.get('stat')}" for r in rows if r.get('sport') and r.get('stat')}
    for scope in sorted(scopes):
        target=path(root,scope)
        try:
            deployed=pb.combine({'q_win_robust':.5,'q_push_robust':0,'sample_block':False,'observation_ids_verified':True},
                {'q_win_b':.5,'q_push_b':0,'reliable':True,'abstain':False},pb.config_path(root,scope),scope=scope,as_of=as_of)
            cfg=fit(rows,scope,fingerprint=deployed.get('config_version') or 'A_ONLY')
            if eligible(cfg,scope,cfg['blend_fingerprint'],as_of):
                # Candidate evaluation is not authorization for deployment.
                # Never overwrite the registered context certificate here.
                proposal=(Path(root)/'reports'/'calibration_candidates'/
                          'context_validation'/target.name)
                proposal.parent.mkdir(parents=True,exist_ok=True)
                tmp=proposal.with_suffix('.tmp')
                tmp.write_text(json.dumps(cfg,indent=2,sort_keys=True)+'\n')
                tmp.replace(proposal)
                result[scope]={'status':'candidate_pending_registration',
                    'path':str(proposal),'validation':cfg['validation'],
                    'production_unchanged':True};continue
            reason='holdout_improvement_not_established'
        except (ValueError,KeyError,TypeError) as exc:reason=str(exc)
        result[scope]={'status':'underpowered_or_unvalidated','reason':reason,
                       'production_unchanged':True}
    return result

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--snapshots',required=True)
    parser.add_argument('--root',default=str(Path(__file__).resolve().parents[1]));args=parser.parse_args()
    rows=[json.loads(line) for line in Path(args.snapshots).read_text().splitlines() if line.strip()]
    print(json.dumps(fit_scopes(rows,args.root),indent=2))
