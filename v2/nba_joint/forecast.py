"""Versioned empirical distributions; push is separate from DNP/product void."""
from pathlib import Path
import gzip
import hashlib
import json
import numpy as np
from scipy.stats import beta
from .common import VERSION, STATS, canonical, sha


def binomial_interval(hits,n,alpha=.05):
    # Clopper-Pearson remains informative at zero sampled tail events.
    return [float(beta.ppf(alpha/2,hits,n-hits+1)) if hits else 0.,float(beta.ppf(1-alpha/2,hits+1,n-hits)) if hits<n else 1.]


def extract_forecast(out,player_index,stat,*,line=None):
    if out.get('research_opportunity') is not None:raise ValueError('DIAGNOSTIC_NOT_FORECAST')
    if stat not in STATS:raise ValueError('UNSUPPORTED_MARKET')
    p=out['players'][player_index];x=out['stats'][stat][:,player_index];n=len(x)
    values,counts=np.unique(x,return_counts=True)
    probs=None;mc=None
    if line is not None:
        if isinstance(line,bool) or not np.isfinite(line) or line<0:raise ValueError('INVALID_LINE')
        hits={'over':int(np.sum(x>line)),'under':int(np.sum(x<line)),'push':int(np.sum(x==line))}
        probs={k:v/n for k,v in hits.items()}
        mc={k:{'se':float(np.sqrt(v/n*(1-v/n)/n)),'ci95':binomial_interval(v,n)} for k,v in hits.items()}
        if float(line)%1:mc['push']={'se':0.,'ci95':[0.,0.]}
    g=out['game'];model=out['model']
    f=dict(schema=VERSION,game_id=g['game_id'],player_id=p['player_id'],team_id=p['team_id'],opponent_id=p['opponent_id'],stat=stat,
        mode=out['mode'],status='UNCERTIFIED/SHADOW',certified=False,eligibility=p['eligible'],participation_probability=p.get('participation_probability'),
        conditioning='conditional_on_supplied_roster' if out['conditional_on_roster'] else 'unconditional_research',
        model_version='nba-joint-v0.1/'+out['dependence']+'/'+out['exposure'],model_sha256=out['model_sha256'],data_version='NBAJointInput/1',scenario_version=out['schema'],
        forecast_at=g['forecast_at'],analysis_cutoff_at=g['analysis_cutoff_at'],source_cutoffs=g.get('source_cutoffs'),source_hashes=g['source_hashes'],training_cutoff_at=model['training_cutoff_at'],
        retrospective=g['mode']=='historical',input_sha256=out['input_sha256'],scenario_output_sha256=out['output_sha256'],scenario_count=n,seed=out['seed'],
        mean=float(x.mean()),variance=float(x.var()),quantiles={str(q):int(np.quantile(x,q,method='inverted_cdf')) for q in (.05,.1,.25,.5,.75,.9,.95)},
        pmf={str(v):int(c)/n for v,c in zip(values,counts)},line=line,threshold_kind='synthetic research thresholds' if line is not None else None,probabilities=probs,monte_carlo=mc,
        abstention_status='trusted_forecast_abstained',abstention_reasons=['MODEL_UNVALIDATED']+(['UNAUTHENTICATED_HISTORICAL_RECONSTRUCTION'] if g['mode']=='historical' else ['SYNTHETIC'] if g['mode']=='synthetic' else [])+(['PARTICIPATION_UNKNOWN'] if p.get('participation_probability') is None else []),
        calibration_version='none',product_void_semantics='unavailable unless exact original contract terms supplied')
    f['output_sha256']=sha(f)
    return f


def freeze(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(payload)+'\n'
    with path.open('x',encoding='utf-8') as handle:handle.write(raw)
    return sha(payload)


def freeze_scenarios(path,out):
    def serial(v):
        if isinstance(v,np.ndarray):return v.tolist()
        if isinstance(v,np.generic):return v.item()
        raise TypeError(type(v).__name__)
    raw=json.dumps(out,default=serial,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    with Path(path).open('xb') as f:f.write(gzip.compress(raw,mtime=0))
    return hashlib.sha256(raw).hexdigest()
