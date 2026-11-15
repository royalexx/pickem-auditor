"""WS4 joint-contract compatibility extension; author-written, no self approval.

Fast proper scores are cross-checked against existing v2.evaluation reference
implementations in tests. This module does not import simulator internals.
"""
from collections import defaultdict
import numpy as np
from scipy.spatial.distance import cdist, pdist

VERSION='NBAJointEvaluationAdapter/1.0.0'


def crps(x,y):
    x=np.sort(np.asarray(x,dtype=float));n=len(x)
    return float(np.abs(x-y).mean()-np.dot(2*np.arange(1,n+1)-n-1,x)/(n*n))


def energy(x,y):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
    return float(np.linalg.norm(x-y,axis=1).mean()-pdist(x).sum()/len(x)**2)


def variogram(x,y):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float)
    i,j=np.triu_indices(x.shape[1],1)
    return float(np.sum((np.sqrt(np.abs(y[i]-y[j]))-np.sqrt(np.abs(x[:,i]-x[:,j])).mean(axis=0))**2))


def distribution_metrics(x,y):
    x=np.asarray(x);qs=np.quantile(x,[.05,.1,.25,.75,.9,.95],method='inverted_cdf')
    prob=float(np.mean(x==y));v=float(x.var());mean=float(x.mean())
    return dict(crps=crps(x,y),empirical_nlpd=None if prob==0 else float(-np.log(prob)),zero_mass=float(np.mean(x==0)),zero_observed=int(y==0),
        mean=mean,variance=v,bias=mean-y,absolute_error=abs(mean-y),squared_error=(mean-y)**2,
        cover50=int(qs[2]<=y<=qs[3]),cover80=int(qs[1]<=y<=qs[4]),cover90=int(qs[0]<=y<=qs[5]),
        width90=float(qs[5]-qs[0]),upper_tail_observed=int(y>qs[5]),upper_tail_predicted=float(np.mean(x>qs[5])))


def summarize(rows):
    result={}
    for key in ('crps','absolute_error','bias','variance','squared_error','cover50','cover80','cover90','width90','zero_mass','zero_observed','upper_tail_observed','upper_tail_predicted'):
        result[key]=float(np.mean([r[key] for r in rows]))
    valid=[r['empirical_nlpd'] for r in rows if r['empirical_nlpd'] is not None]
    result.update(n=len(rows),empirical_nlpd_infinite_count=len(rows)-len(valid),empirical_nlpd_mean=None if len(valid)!=len(rows) else float(np.mean(valid)),
        empirical_nlpd_finite_subset_mean=float(np.mean(valid)) if valid else None,
        variance_accuracy_ratio=float(np.mean([r['squared_error'] for r in rows])/max(1e-12,np.mean([r['variance'] for r in rows]))),
        zero_residual=result['zero_mass']-result['zero_observed'],upper_tail_residual=result['upper_tail_predicted']-result['upper_tail_observed'])
    return result


def paired_ci(rows,baseline,challenger,metric='crps',cluster='date',seed=20261115):
    indexed=defaultdict(dict)
    for r in rows:
        if r['model'] in (baseline,challenger):indexed[(r['game_id'],r.get('player_id'),r.get('stat'))][r['model']]=r
    groups=defaultdict(list);diffs=[]
    for values in indexed.values():
        if set(values)!={baseline,challenger}:continue
        a,b=values[baseline],values[challenger]
        if a[metric] is None or b[metric] is None:continue
        d=b[metric]-a[metric];groups[a[cluster]].append(d);diffs.append(d)
    if not groups:return dict(n=0,status='BLOCKED-BY-DATA')
    agg=np.array([[sum(v),len(v)] for v in groups.values()]);rng=np.random.default_rng(seed)
    pick=rng.integers(0,len(agg),(1000,len(agg)));sample=agg[pick]
    bootstrap=sample[:,:,0].sum(axis=1)/sample[:,:,1].sum(axis=1)
    return dict(n=len(diffs),clusters=len(groups),cluster=cluster,difference=float(np.mean(diffs)),ci95=np.quantile(bootstrap,[.025,.975]).tolist(),status='INCONCLUSIVE',
        inference='exploratory matched cluster bootstrap; small exposed sample, not release-grade power')
