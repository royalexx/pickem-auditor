"""Read-only exact-contract, status-complete, post-settlement scoring (WS4 v0.1).

Never modifies original forecasts, offers or outcomes. Synthetic fixtures cannot be
promoted to market research. Missing model/market probabilities stay missing.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import math
import pathlib
import statistics
from typing import Any
import numpy as np

VALID_STATUS={"ATTEMPTED","UNAVAILABLE","ELIGIBLE","REJECTED","DNP","VOID","PUSH","UNSETTLED","OFFICIALLY_SETTLED"}
MODEL_ORDER=("production_60_40","market_only","engine_a","engine_b","bayesian_a","bayesian_b",
             "strict_nuts","ws2_simple","ws3_opportunity","J1","J2","J3")


def identity(row:dict)->tuple:
    return tuple(row.get(k) for k in ("contract_id","original_quote_id","event_id","player_id","team_id","stat_key","period","line"))


def checked_probability(p:Any)->float:
    if not isinstance(p,(float,int)) or not math.isfinite(p) or not 0<=p<=1:
        raise ValueError('INVALID_PROBABILITY')
    return float(p)


def crps_count(pmf:dict[str,float],y:int)->float:
    if isinstance(y,bool) or not isinstance(y,int) or y<0:raise ValueError('INVALID_COUNT_OUTCOME')
    masses={int(k):checked_probability(v) for k,v in pmf.items()}
    if not masses or min(masses)<0 or abs(sum(masses.values())-1)>1e-8:raise ValueError('INVALID_PMF')
    end=max(y,max(masses))
    cdf=0.;loss=0.
    for k in range(0,end+1):
        cdf+=masses.get(k,0.)
        loss+=(cdf-(1.0 if y<=k else 0.0))**2
    return loss


def score_pair(f:dict,s:dict)->dict:
    if identity(f)!=identity(s):raise ValueError('CONTRACT_IDENTITY_MISMATCH')
    if s['status'] not in ('OFFICIALLY_SETTLED','PUSH'):
        raise ValueError('NON_SETTLED_SCORED')
    if f.get('status')!='FORECAST':raise ValueError('ABSTENTION_SCORED')
    y=s['official_stat'];line=s['line']
    if not isinstance(y,(int,float)) or not math.isfinite(y):raise ValueError('INVALID_SETTLED_STAT')
    realized='OVER' if y>line else ('UNDER' if y<line else 'PUSH')
    if s['status']=='PUSH' and realized!='PUSH':raise ValueError('PUSH_STATUS_DISAGREEMENT')
    if s['status']=='OFFICIALLY_SETTLED' and realized=='PUSH':raise ValueError('PUSH_STATUS_DISAGREEMENT')
    q=[checked_probability(f['p_over']),checked_probability(f['p_under']),checked_probability(f['p_push'])]
    if abs(sum(q)-1)>1e-8:raise ValueError('COMPLEMENTARITY')
    obs=[float(realized==k) for k in ('OVER','UNDER','PUSH')]
    # Unscaled three-way Brier: sum of squared residuals (max=2).
    score3=sum((a-b)**2 for a,b in zip(q,obs))
    p_real=q[('OVER','UNDER','PUSH').index(realized)]
    r={"model_id":f['model_id'],"identity":identity(f),"event_id":s['event_id'],
       "game_date":s.get('game_date'),"stat_key":s['stat_key'],
       "realized":realized,"p_over":q[0],"observed_over":obs[0],"three_way_brier":score3,
       "three_way_logloss":-math.log(max(p_real,1e-12)),
       "binary_brier":None,"binary_logloss":None,"directional_hit":None,
       "count_crps":None,"selection_rank":s.get('frozen_selection_rank')}
    if realized!='PUSH':
        r['binary_brier']=(q[0]-obs[0])**2
        r['binary_logloss']=-(obs[0]*math.log(max(q[0],1e-12))+(1-obs[0])*math.log(max(1-q[0],1e-12)))
        side='OVER' if q[0]>q[1] else ('UNDER' if q[1]>q[0] else 'TIE')
        r['directional_hit']=int(side==realized) if side!='TIE' else None
    if f.get('pmf') is not None and isinstance(y,int) and y>=0:
        r['count_crps']=crps_count(f['pmf'],y)
    return r


def prepare(forecasts:list[dict],settlements:list[dict])->tuple[list[dict],dict]:
    fidx={};sidx={};counts=collections.Counter()
    for s in settlements:
        st=s.get('status')
        if st not in VALID_STATUS:raise ValueError('UNKNOWN_SETTLEMENT_STATUS')
        key=identity(s)
        if key in sidx:raise ValueError('DUPLICATE_SETTLEMENT')
        sidx[key]=s;counts['settlement_'+st]+=1
    for f in forecasts:
        key=(f.get('model_id'),identity(f))
        if key in fidx:raise ValueError('DUPLICATE_MODEL_FORECAST')
        fidx[key]=f;counts['forecast_'+f.get('status','UNKNOWN')]+=1
    rows=[]
    for (model,key),f in fidx.items():
        s=sidx.get(key)
        if s is None:counts['forecast_unmatched']+=1;continue
        if s['status'] not in ('OFFICIALLY_SETTLED','PUSH'):
            counts['forecast_'+s['status']]+=1;continue
        if f.get('status')!='FORECAST':counts['settled_abstention']+=1;continue
        rows.append(score_pair(f,s))
        counts['scored_model_rows']+=1
    for key,s in sidx.items():
        if not any(k[1]==key for k in fidx):counts['settled_without_any_forecast']+=1
    return rows,dict(counts)


def paired(rows:list[dict],model_a:str,model_b:str,metric:str='binary_brier',n_boot:int=2000,seed:int=20261115)->dict:
    aa={r['identity']:r for r in rows if r['model_id']==model_a and r.get(metric) is not None}
    bb={r['identity']:r for r in rows if r['model_id']==model_b and r.get(metric) is not None}
    keys=sorted(set(aa)&set(bb),key=repr)
    if not keys:return {"status":"NO_COMMON_SETTLED_COHORT","matched":0}
    diffs=np.asarray([aa[k][metric]-bb[k][metric] for k in keys],dtype=float)
    groups=collections.defaultdict(list)
    for i,k in enumerate(keys): groups[aa[k]['event_id']].append(i)
    out={"status":"DESCRIPTIVE_ONLY" if len(groups)<10 else "HISTORICAL_RESEARCH_ONLY",
         "model_a":model_a,"model_b":model_b,"metric":metric,"matched":len(keys),
         "n_game_clusters":len(groups),"mean_a_minus_b":float(diffs.mean()),
         "cluster_ci95":None,"bootstrap_draws":0}
    if len(groups)>=2 and n_boot:
        rng=np.random.default_rng(seed)
        indexed=[np.asarray(v,dtype=int) for v in groups.values()]
        means=[]
        for _ in range(n_boot):
            selected=rng.integers(0,len(indexed),size=len(indexed))
            ids=np.concatenate([indexed[j] for j in selected])
            means.append(float(diffs[ids].mean()))
        out['cluster_ci95']=np.quantile(means,[.025,.975]).tolist()
        out['bootstrap_draws']=n_boot
    return out


def summary(rows:list[dict],counts:dict)->dict:
    bymodel=collections.defaultdict(list)
    for r in rows:bymodel[r['model_id']].append(r)
    models={}
    for model,rr in bymodel.items():
        def avg(key):
            valid=[r[key] for r in rr if r.get(key) is not None]
            return None if not valid else sum(valid)/len(valid)
        def top(k):
            subset=[r for r in rr if isinstance(r.get('selection_rank'),int) and 1<=r['selection_rank']<=k]
            return {"n":len(subset),"brier":None if not subset else float(np.mean([r['binary_brier'] for r in subset if r['binary_brier'] is not None]))}
        models[model]={"n_three_way":len(rr),"n_binary":sum(r['binary_brier'] is not None for r in rr),
                       "brier":avg('binary_brier'),"logloss":avg('binary_logloss'),
                       "three_way_brier":avg('three_way_brier'),"count_crps":avg('count_crps'),
                       "forecast_mean_over":avg('p_over'),"realized_over_frequency":avg('observed_over'),
                       "directional_hit":avg('directional_hit'),"top5":top(5),"top10":top(10)}
    return {"schema":"PA_WS4_MATCHED_POSTSETTLEMENT_v1", "denominators":counts,
            "model_summary":models,"policy":"Binary push contracts excluded; three-way Brier unscaled; cluster by event/game; no price or profitability inference."}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--forecasts',required=True,type=pathlib.Path)
    ap.add_argument('--settlements',required=True,type=pathlib.Path)
    ap.add_argument('--output',required=True,type=pathlib.Path)
    a=ap.parse_args()
    ff=json.loads(a.forecasts.read_text());ss=json.loads(a.settlements.read_text())
    forecasts=ff['contracts'] if isinstance(ff,dict) else ff
    settled=ss['contracts'] if isinstance(ss,dict) else ss
    rows,counts=prepare(forecasts,settled)
    report=summary(rows,counts)
    if ff.get('classification')=='SYNTHETIC_FIXTURE':report['classification']='SYNTHETIC_FIXTURE_NOT_SPORTS_EVIDENCE'
    report['paired']=[paired(rows,'J2','J1'),paired(rows,'J3','J1')]
    report['source_sha256']={"forecasts":hashlib.sha256(a.forecasts.read_bytes()).hexdigest(),
                             "settlements":hashlib.sha256(a.settlements.read_bytes()).hexdigest()}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as out:json.dump(report,out,sort_keys=True,indent=2,allow_nan=False)
    print(json.dumps({"counts":counts,"models":list(report['model_summary'])},sort_keys=True))

if __name__=='__main__':main()