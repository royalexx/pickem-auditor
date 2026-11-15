"""Reproducible bounded WS2 replay; all outputs exploratory, no production import.
Run: OPENBLAS_NUM_THREADS=1 python -m research.nba_ws2.run_experiment --input work/ws2_input --output research/nba_ws2/results
"""
from __future__ import annotations
import argparse
from collections import defaultdict, Counter
from dataclasses import asdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time
import numpy as np
import pandas as pd
from scipy.special import betainc, ndtr
from sklearn.linear_model import Ridge
from v2.nba_opportunity import FEATURES, MinutesModel, MinuteLaw, causal_features, position_group, role

SEED=20261115


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_population(folder):
    rows=[]; manifests=[]; identities=set()
    for file in sorted(Path(folder).glob('*.jsonl.gz')):
        if file.stem.split('.')[0] not in ('2024','2025'):continue
        manifests.append({'path':str(file),'sha256':sha(file)})
        for line in gzip.open(file,'rt'):
            r=json.loads(line)
            if r['sport']!='NBA' or r['stat']!='points' or r['workload_unit']!='minutes':raise ValueError('WRONG_POPULATION')
            k=(r['game_id'],r['player_id'])
            if k in identities:raise ValueError('DUPLICATE_PLAYER_GAME')
            identities.add(k)
            if not np.isfinite(r['workload']) or r['workload']<=0:raise ValueError('INVALID_PLAYED_EXPOSURE')
            if len(r['source_sha256'])!=64 or not r['source_url'].startswith('https://'):raise ValueError('INVALID_SOURCE')
            rows.append(r)
    return sorted(rows,key=lambda r:(r['game_date'],r['game_id'],r['player_id'])), manifests


NBA_FRANCHISES = frozenset('ATL BOS BKN CHA CHI CLE DAL DEN DET GS HOU IND LAC LAL MEM MIA MIL MIN NO NY OKC ORL PHI PHX POR SAC SA TOR UTAH WSH'.split())


def franchise_population(rows):
    kept=[];rejected=[]
    for row in rows:
        if row['team'] not in NBA_FRANCHISES or row['opponent'] not in NBA_FRANCHISES:
            rejected.append({**row,'reason':'NON_FRANCHISE_COMPETITION_IDENTITY'})
        else:kept.append(row)
    return kept,rejected


def build_table(rows):
    history=defaultdict(list); team_games=defaultdict(list); out=[]; rejects=[]; season_counts=Counter()
    byday=defaultdict(list)
    for r in rows:byday[r['game_date']].append(r)
    for day,dayrows in sorted(byday.items()):
        for r in dayrows:
            h=history[r['player_id']]
            missed=sum(d>h[-1]['game_date'] for d in team_games[r['team']]) if h and h[-1]['team']==r['team'] else 0
            try:f=causal_features(h,game_date=day,team=r['team'],home=r['home'],prior_team_games_missed=missed)
            except ValueError as e:
                rejects.append({'game_id':r['game_id'],'player_id':r['player_id'],'game_date':day,'season':r['season'],'reason':str(e)})
            else:
                out.append({**r,**f,'observed_position':r['position'],'position':h[-1]['position'],'prior_season_appearances':season_counts[r['season'],r['player_id']],
                    'last_observation_date':h[-1]['game_date'],
                    'cohort':position_group(r['position'])+'/'+role(f['mean10'])})
            season_counts[r['season'],r['player_id']]+=1
        # Every forecast for a day precedes all same-day outcome updates.
        for r in dayrows:history[r['player_id']].append(r)
        for team in {r['team'] for r in dayrows}:team_games[team].append(day)
    return pd.DataFrame(out), rejects


def overtime_training(rows):
    totals=defaultdict(float)
    for r in rows:totals[r['game_id'],r['team']]+=r['workload']
    bygame=defaultdict(list)
    for (g,t),value in totals.items():bygame[g].append(value)
    counts=[]; rejected=0
    for g,vals in bygame.items():
        k=[max(0,round((v-240)/25)) for v in vals]
        if len(vals)!=2 or k[0]!=k[1] or any(abs(v-(240+25*j))>6 for v,j in zip(vals,k)):
            rejected+=1;continue
        counts.append(k[0])
    positive=[k for k in counts if k>0]
    # Beta(1,1) smoothed OT rate and continuation; no postgame OT feature.
    p=(len(positive)+1)/(len(counts)+2)
    q=(sum(k-1 for k in positive)+1)/(sum(positive)+2)
    return p,q,{'eligible_games':len(counts),'rejected_games':rejected,'counts':dict(Counter(counts)),
        'limitation':'OT inferred from rounded team exposure outcomes for train-only frequency; not official period labels'}


def fit(train,source_manifest,code_commit,ot):
    cohorts={'ALL':{'mean':float(train.workload.mean()),'variance':float(train.workload.var())}}
    for key,g in train.groupby('cohort'):
        cohorts[key]={'mean':float(g.workload.mean()),'variance':float(g.workload.var()),'n':len(g)}
    x=train[list(FEATURES)].to_numpy(); y=train.workload.to_numpy()
    center=x.mean(axis=0); scale=x.std(axis=0);scale[scale<1e-8]=1
    ridge=Ridge(alpha=100.).fit((x-center)/scale,y)
    model=MinutesModel(cohorts,{'M0':{},'M1':{},'M2':{}},center.tolist(),scale.tolist(),
        ridge.coef_.tolist(),float(ridge.intercept_),ot[0],ot[1],
        '2024-04-15T00:00:00Z',source_manifest,code_commit)
    for name in ('M0','M1','M2'):
        pred=np.array([model.parameters(name,{k:row[k] for k in FEATURES},row['position'])[0] for row in train.to_dict('records')])
        for state in ('low','mid','high'):
            ix=train.mean10.map(role).to_numpy()==state
            model.residual_variance[name][state]=float(np.mean((y[ix]-pred[ix])**2))
    return model


def score(model,name,table,family=None,permuted=False):
    records=table.to_dict('records')
    fs=[{k:r[k] for k in FEATURES} for r in records]
    if permuted:
        order=np.random.default_rng(SEED).permutation(len(fs))
        fs=[{k:(fs[j][k] if k not in ('median5','mean10') else fs[i][k]) for k in FEATURES} for i,j in enumerate(order)]
    params=np.array([model.parameters(name,f,r['position']) for f,r in zip(fs,records)])
    means=params[:,0]; variances=params[:,1]
    grid=np.arange(0,120.001,.25); outcomes=table.workload.to_numpy()
    all_scores=[]
    for start in range(0,len(table),512):
        mu=means[start:start+512];va=variances[start:start+512];y=outcomes[start:start+512]
        a,b=np.array([MinuteLaw(m,v,model.ot_probability,model.ot_continuation).shape() for m,v in zip(mu,va)]).T
        xx=np.concatenate([np.broadcast_to(grid,(len(y),len(grid))),
            np.maximum(0,y[:,None]-.5),y[:,None]+.5],axis=1)
        cdf=np.zeros_like(xx)
        for length,weight in MinuteLaw(24,64,model.ot_probability,model.ot_continuation).ot_components():
            u=np.clip(xx/length,0,1)
            if (family or model.family)=='beta':c=betainc(a[:,None],b[:,None],u)
            else:
                share=a/(a+b);var=a*b/((a+b)**2*(a+b+1))
                s=np.sqrt(np.log1p(var/share**2));loc=np.log(share)-s*s/2
                c=ndtr((np.log(np.maximum(u,1e-300))-loc[:,None])/s[:,None])/ndtr(-loc/s)[:,None]
                c=np.where(xx<=0,0,np.where(xx>=length,1,c))
            cdf += weight*c
        c=cdf[:,:len(grid)]
        crps=np.trapezoid((c-(grid[None,:]>=y[:,None]))**2,grid,axis=1)
        # Midpoint correction: y falls on the integration grid for rounded data;
        # trapezoid at its step has O(h) direction bias. Average the two endpoint conventions.
        crps += .25*(c[np.arange(len(y)),np.minimum((y*4).astype(int),len(grid)-1)]-.5)
        nlp=-np.log(np.maximum(cdf[:,-1]-cdf[:,-2],1e-300))
        for j in range(len(y)):
            qs=np.interp([.05,.1,.25,.5,.75,.9,.95],c[j],grid)
            all_scores.append({'mae':abs(y[j]-qs[3]),'point_mae':abs(y[j]-mu[j]),'crps':crps[j],
                'nlpd_rounded_bin':nlp[j], 'cover50':float(qs[2]<=y[j]<=qs[4]),
                'cover80':float(qs[1]<=y[j]<=qs[5]),'cover90':float(qs[0]<=y[j]<=qs[6]),
                'width90':qs[6]-qs[0], 'mean':mu[j], 'variance_parameter':va[j],
                'q05':qs[0],'q50':qs[3],'q95':qs[6]})
    return pd.DataFrame(all_scores,index=table.index)


def summarize(scores):
    keys=['mae','point_mae','crps','nlpd_rounded_bin','cover50','cover80','cover90','width90']
    return {'n':len(scores),**{k:float(scores[k].mean()) for k in keys}}


def bootstrap_diff(base,challenger,clusters):
    d=challenger.crps.to_numpy()-base.crps.to_numpy()
    frame=pd.DataFrame({'d':d,'cluster':np.asarray(clusters)})
    agg=frame.groupby('cluster').d.agg(['sum','count']).to_numpy()
    rng=np.random.default_rng(SEED); draws=[]
    for _ in range(1000):
        pick=rng.integers(0,len(agg),len(agg)); sample=agg[pick]
        draws.append(sample[:,0].sum()/sample[:,1].sum())
    return {'difference':float(d.mean()),'ci97_5':np.quantile(draws,[.0125,.9875]).tolist(),'clusters':len(agg)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();dest=Path(args.output);dest.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();cpu=time.process_time()
    executed_hashes={p:sha(p) for p in ['v2/nba_opportunity.py','research/nba_ws2/run_experiment.py']}
    raw_rows,manifest=load_population(args.input);rows,source_exclusions=franchise_population(raw_rows);table,rejects=build_table(rows)
    train=table[table.season=='2024'];test=table[table.season=='2025'].reset_index(drop=True)
    source_sha=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    code=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    ot=overtime_training([r for r in rows if r['season']=='2024'])
    model=fit(train,source_sha,code,ot)
    # Family comparison is entirely within fitting data, never test selection.
    sample=train.iloc[np.linspace(0,len(train)-1,min(2000,len(train))).astype(int)].reset_index(drop=True)
    family={f:summarize(score(model,'M1',sample,family=f)) for f in ('beta','truncated_lognormal')}
    chosen=min(family,key=lambda f:family[f]['crps']);model.family=chosen
    if chosen!='beta':raise RuntimeError('TRAIN_FAMILY_CHOICE_REQUIRES_LOGNORMAL_MOMENT_REVIEW')
    model.save(dest/'model.json')
    timing={};scores={}
    for name in ('M0','M1','M2','M2_disabled'):
        print('Scoring '+name,flush=True)
        ts=time.perf_counter();scores[name]=score(model,name,test);timing[name]=time.perf_counter()-ts
    ts=time.perf_counter();scores['M2_permuted']=score(model,'M2',test,permuted=True);timing['M2_permuted']=time.perf_counter()-ts
    cohorts={
      'early_season':test.prior_season_appearances<10,
      'changed_role_proxy':(test.trend.abs()>=5)|(test.team_change==1),
      'stable_role_proxy':(test.trend.abs()<5)&(test.team_change==0),
      'low_historical_minutes':test.mean10<14,'mid_historical_minutes':(test.mean10>=14)&(test.mean10<28),
      'high_historical_minutes':test.mean10>=28,
      'return_after_missed_team_games_proxy':test.return_gap>=2,
      'back_to_back_appearance_proxy':test.back_to_back==1,
      'team_change':test.team_change==1,'low_minute_outcome_le5':test.workload<=5,
      'early_exit_proxy':(test.workload<10)&(test.mean10>=28)}
    totals=defaultdict(float)
    for r in rows:
        if r['season']=='2025':totals[r['game_id'],r['team']]+=r['workload']
    test['team_observed_total']=[totals[g,t] for g,t in zip(test.game_id,test.team)]
    cohorts['inferred_overtime_outcome']=test.team_observed_total>=257.5
    metrics={n:summarize(s) for n,s in scores.items()}
    compare={n:{'date':bootstrap_diff(scores['M0'],scores[n],test.game_date),
                'game':bootstrap_diff(scores['M0'],scores[n],test.game_id)} for n in ('M1','M2')}
    acceptance={}
    for name in ('M1','M2'):
        a,b=metrics[name],metrics['M0'];diff=compare[name]['date']
        coverage=all(abs(a['cover'+str(level)]-level/100)<=.05 and abs(a['cover'+str(level)]-level/100)<=abs(b['cover'+str(level)]-level/100)+.03 for level in (50,80,90))
        acceptance[name]={'primary_pass':diff['ci97_5'][1]<0 and a['crps']<=.99*b['crps'],
                          'mae_pass':a['mae']<=b['mae']+.2,'coverage_pass':coverage,
                          'promotion':False}
    role_truth=test.workload.map(role).to_numpy()
    rotation={n:{'state_error_rate':float(np.mean(np.array([role(m) for m in s['mean']])!=role_truth)),
        'definition':'workload low<14, mid<28, high>=28; not starter/bench labels'} for n,s in scores.items()}
    report={'status':'HISTORICAL_EXPLORATORY_SHADOW_ONLY','experiment_sha256':sha('research/nba_ws2/experiment.json'),
        'code_commit':code,'executed_code_hashes':executed_hashes,'source_branch_commit':subprocess.check_output(['git','rev-parse','origin/data/bayesian-history'],text=True).strip(),
        'source_manifest':manifest,'rows_loaded_raw':len(raw_rows),'source_identity_exclusions':len(source_exclusions),'rows_loaded':len(rows),'rows_train':len(train),'rows_test':len(test),
        'rejected_by_season':dict(Counter(x['season'] for x in rejects)),
        'test_games':int(test.game_id.nunique()),'test_dates':int(test.game_date.nunique()),
        'train_start':train.game_date.min(),'train_end':train.game_date.max(),
        'test_start':test.game_date.min(),'test_end':test.game_date.max(),
        'training_family_comparison':family,'chosen_family':chosen,'overtime_training':ot[2],
        'ot_probability':ot[0],'ot_continuation':ot[1],
        'metrics':metrics,'paired_crps':compare,'acceptance':acceptance,
        'cohorts':{c:{n:summarize(s.loc[ix]) for n,s in scores.items() if n in ('M0','M1','M2')} for c,ix in cohorts.items()},
        'rotation_state':rotation,'participation_fpr':None,'participation_fnr':None,
        'missing_evidence':['complete historical eligible rosters and DNP labels','pregame injury/availability receipts',
            'historical current lineup confirmations','pregame spread/team-strength archives','authenticated historical source availability timestamps'],
        'runtime_seconds_by_model':timing,
        'total_wall_seconds':time.perf_counter()-start,'total_cpu_seconds':time.process_time()-cpu,
        'max_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'environment':{'numpy':np.__version__,'pandas':pd.__version__},
        'numeric_scoring':'CRPS quarter-minute trapezoid with step midpoint correction, integration through120; mass beyond120 reported separately; NLPD integer-rounded +/-0.5 minute bins; not continuous density',
        'decision':'Retain M0 benchmark. No promotion. Challenger statistical status determined by preregistered gates and prospective missing evidence.'}
    tablecols=['game_id','game_date','player_id','team','position','workload','mean10','trend','return_gap','team_change','last_observation_date','prior_season_appearances']
    pred=test[tablecols].copy()
    for name,s in scores.items():
        for col in s:pred[name+'_'+col]=s[col].to_numpy()
    pred.to_csv(dest/'matched_predictions.csv.gz',index=False)
    pd.DataFrame(rejects).to_csv(dest/'rejected_ledger.csv.gz',index=False)
    pd.DataFrame(source_exclusions).to_csv(dest/'source_identity_exclusions.csv',index=False)
    (dest/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ('rows_loaded','rows_train','rows_test','training_family_comparison','metrics','paired_crps','acceptance','total_wall_seconds','max_rss_mib')},indent=2))

if __name__=='__main__':main()
