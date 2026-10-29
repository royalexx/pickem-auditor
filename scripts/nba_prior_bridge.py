"""NBA early-season source-verified, power-likelihood Bayesian shadow bridge.

Use only checksum-verified current/prior game-level observations and 5+ disjoint
peer players. Prior-season likelihood is discounted to 0.4 observations/game,
not expanded into fake current-season games. Requires 3-4 observed current games,
10-20 prior games, documented team identity, and broadly consistent measured
minutes (a weak same-role guard). Shadow only; no Tier authority.
"""
from __future__ import annotations
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import mean, median, variance
import hashlib
import json
import math
import bayesian_engine as be
import bayesian_usage as bu
import usage_baseline as ub

VERSION='nba-source-prior-power-v1'
POWER=0.4
MIN_PEERS=5

def observations(record, *, before, stat, require_bridge=True):
    if record.get('sport')!='NBA' or ub.source_stat(record.get('stat'))!=ub.source_stat(stat):
        raise be.ModelUnavailable('bridge_requires_nba_stat_identity')
    current=record.get('observations') or []
    prior=record.get('prior_observations') or []
    if (not 3<=len(current)<=4 or not 10<=len(prior)<=20):
        raise be.ModelUnavailable('bridge_requires_3_or_4_current_and_10_to_20_prior')
    seen=set();rows=[]
    allow_negative=False
    for group, weight in ((current,1.0),(prior,POWER)):
        for item in group:
            if not isinstance(item,dict):
                raise be.ModelUnavailable('invalid_history_row')
            ident=item.get('id')
            if not isinstance(ident,str) or not ident or ident in seen:
                raise be.ModelUnavailable('duplicate_or_missing_game_id')
            seen.add(ident)
            date=be._date(item.get('date'))
            if date>=before:
                raise be.ModelUnavailable('future_game_in_history')
            y=be._number(item.get('value'))
            w=be._number(item.get('workload'))
            if y<0 or w<=0:
                raise be.ModelUnavailable('invalid_positive_exposure')
            rows.append((ident,date,y,w,weight))
    if max(be._date(x['date']) for x in prior)>=min(be._date(x['date']) for x in current):
        raise be.ModelUnavailable('prior_not_chronologically_disjoint')
    current_w=mean(be._number(x.get('workload')) for x in current)
    prior_w=mean(be._number(x.get('workload')) for x in prior)
    ratio=current_w/prior_w if prior_w>0 else 0
    if not 0.60<=ratio<=1.70:
        raise be.ModelUnavailable('role_workload_shift_requires_verification')
    return rows

def wmean(group):
    total=sum(row[-1] for row in group)
    return sum(row[2]*row[-1] for row in group)/total

def wvariance(group,center):
    total=sum(row[-1] for row in group)
    return sum(row[-1]*(row[2]-center)**2 for row in group)/max(total-1.0,1.0)

def prior_from_peers(peers,kind):
    if len(peers)<MIN_PEERS:raise be.ModelUnavailable('insufficient_verified_prior_peers')
    means=[wmean(p) for p in peers]
    center=mean(means)
    if center<=0:raise be.ModelUnavailable('nonpositive_peer_population')
    within=[wvariance(p,m) for p,m in zip(peers,means)]
    scale=max(median(within),be.EPS)
    sampling=mean(s/sum(row[-1] for row in p) for p,s in zip(peers,within))
    between=max(variance(means)-sampling,scale/12,be.EPS)
    strength=max(2.,min(12.,scale/between))
    if kind=='normal':
        return dict(mean0=center,kappa0=strength,alpha0=3.0,beta0=2*scale,
                    peer_count=len(peers),within_variance=scale,between_variance=between)
    eff=max(2.,min(12.,center/between))
    return dict(alpha0=center*eff,beta0=eff,mean0=center,peer_count=len(peers),
                between_variance=between)

@lru_cache(maxsize=80)
def _cached_peers(root,stat,before):
    folder=Path(root)/'usage'
    found=defaultdict(list)
    if not folder.exists():return ()
    paths=list(folder.glob('*.json'))+list((folder/'snapshots').glob('*.json'))
    for path in paths:
        loaded=be._load_one(path,None)
        if not loaded:continue
        record,stamp=loaded
        if record.get('sport')!='NBA' or not record.get('player_id'):continue
        try:series=observations(record,before=before,stat=stat)
        except (KeyError,ValueError,TypeError,be.ModelUnavailable):continue
        found[str(record['player_id'])].append((stamp,len(series),path.name,tuple(series)))
    return tuple((pid,tuple(sorted(group,key=lambda x:(x[0],x[1],x[2]),reverse=True)))
                 for pid,group in sorted(found.items()))

def peers(root, *, stat, player_id, cutoff, before):
    result=[]
    for pid, versions in _cached_peers(str(root),stat,before):
        if pid==str(player_id):continue
        for stamp,n,path,series in versions:
            if stamp<=cutoff:
                result.append(series)
                break
    if len(result)<MIN_PEERS:
        raise be.ModelUnavailable('insufficient_verified_prior_peers')
    return result

def model_a(record,*,root,stat,player_id,cutoff,before,dist,line,side,var_ratio=None):
    subject=observations(record,before=before,stat=stat)
    cohort=peers(root,stat=stat,player_id=player_id,cutoff=cutoff,before=before)
    kind='normal' if dist=='normal' else 'count'
    prior=prior_from_peers(cohort,kind)
    y=[row[2] for row in subject]
    weights=[row[-1] for row in subject]
    n=sum(weights)
    if dist=='normal':
        avg=sum(w*x for w,x in zip(weights,y))/n
        ss=sum(w*(x-avg)**2 for w,x in zip(weights,y))
        k0,a0,b0,mu0=(prior[k] for k in ('kappa0','alpha0','beta0','mean0'))
        kn=k0+n
        an=a0+n/2
        mun=(k0*mu0+n*avg)/kn
        bn=b0+ss/2+k0*n*(avg-mu0)**2/(2*kn)
        scale=math.sqrt(bn*(kn+1)/(an*kn))
        df=2*an
        def cdf(v):return be.student_t_cdf((v-mun)/scale,df)
        if abs(line-round(line))<1e-9:
            under=cdf(line-0.5);push=cdf(line+0.5)-under
        else:
            under=cdf(line);push=0.
        negative=cdf(-0.5)
        if negative>0.02:raise be.ModelUnavailable('normal_predictive_negative_mass')
        posterior={'kappa':kn,'alpha':an,'beta':bn}
        mean_next=mun
        se=math.sqrt(bn/(kn*(an-1)))
    elif dist in ('poisson','negbin'):
        if any(not v.is_integer() for v in y):
            raise be.ModelUnavailable('noninteger_count_observation')
        alpha0,beta0=prior['alpha0'],prior['beta0']
        if dist=='poisson':
            alpha=alpha0+sum(w*x for w,x in zip(weights,y))
            beta=beta0+n
            mean_next=alpha/beta
            p=(beta/(beta+1))**alpha
            probs=[p]
            for k in range(max(0,math.floor(line))):
                probs.append(probs[-1]*(k+alpha)/(k+1)/(beta+1))
            posterior={'alpha':alpha,'beta':beta}
            se=math.sqrt(alpha)/beta
        else:
            ratio=be._number(var_ratio,allow_zero=False)
            if not 1.1<ratio<=3:raise be.ModelUnavailable('invalid_negbin_dispersion')
            center=max(prior['mean0'],sum(w*x for w,x in zip(weights,y))/n,be.EPS)
            lo=min(-18.,math.log(center)-9)
            hi=max(math.log(center)+9,math.log(max(y)+1)+7)
            grid=[]
            for k in range(401):
                z=lo+(hi-lo)*k/400
                lam=math.exp(z)
                score=alpha0*z-beta0*lam+sum(w*be._nb_likelihood_log(x,lam,ratio)
                                                 for w,x in zip(weights,y))
                grid.append((lam,score))
            peak=max(v for _,v in grid)
            raw=[math.exp(v-peak) for _,v in grid]
            total=math.fsum(raw)
            if not total:raise be.ModelUnavailable('posterior_integration_failure')
            posterior_weights=[v/total for v in raw]
            mean_next=math.fsum(lam*w for (lam,_),w in zip(grid,posterior_weights))
            se=math.sqrt(math.fsum(w*(lam-mean_next)**2
                                for (lam,_),w in zip(grid,posterior_weights)))
            probs=[0.]*(max(0,math.floor(line))+1)
            for (lam,_),w in zip(grid,posterior_weights):
                if w<1e-16:continue
                shape=lam/(ratio-1)
                p=math.exp(shape*math.log(1/ratio))
                for k in range(len(probs)):
                    probs[k]+=w*p
                    p*=((k+shape)/(k+1))*(1-1/ratio)
            posterior={'quadrature_nodes':401,'variance_ratio':ratio}
        over,under,push=be._low_count_probs(probs,line=line)
    else:
        raise be.ModelUnavailable('unsupported_distribution')
    if dist=='normal':
        over=max(0.,1-under-push)
    win=over if side=='over' else under
    loss=under if side=='over' else over
    if side not in ('under','over') or not all(0<=p<=1 for p in (win,loss,push)):
        raise be.ModelUnavailable('invalid_posterior_probability')
    return dict(version=VERSION,status='shadow_only',q_win=win,q_push=push,q_loss=loss,
                mean=mean_next,posterior_mean_se=se,posterior_parameters=posterior,
                distribution=dist,population_prior=prior,n_observations=len(subject),
                effective_observation_count=n,peer_count=len(cohort),
                source_only_prior_power=POWER,publication_eligible=False,
                input_fingerprint=hashlib.sha256(json.dumps(
                    [(v[0],v[2],v[-1]) for v in subject],sort_keys=True).encode()).hexdigest())

def _nig_update(values,prior):
    total=sum(w for y,w in values)
    avg=sum(y*w for y,w in values)/total
    mu0,k0,a0,b0=(prior[k] for k in ('mean0','kappa0','alpha0','beta0'))
    kn=k0+total
    mu=(k0*mu0+total*avg)/kn
    a=a0+total/2
    b=b0+sum(w*(y-avg)**2 for y,w in values)/2+k0*total*(avg-mu0)**2/(2*kn)
    if a<=1 or b<=0:raise be.ModelUnavailable('invalid_posterior')
    return dict(mu=mu,kappa=kn,alpha=a,beta=b,df=2*a,
                predictive_scale=math.sqrt(b*(kn+1)/(a*kn)),
                posterior_mean_se=math.sqrt(b/(kn*(a-1))))

def model_b(record,*,root,stat,player_id,cutoff,before,dist,line,side,var_ratio=None):
    subject=observations(record,before=before,stat=stat)
    cohort=peers(root,stat=stat,player_id=player_id,cutoff=cutoff,before=before)
    # True power likelihoods on log game workloads and production/exposure.
    def log_series(s):return [(math.log(row[3]),row[4]) for row in s]
    peer_log=[log_series(p) for p in cohort]
    m=[sum(y*w for y,w in p)/sum(w for _,w in p) for p in peer_log]
    scale=max(median(sum(w*(y-c)**2 for y,w in p)/max(sum(w for _,w in p)-1,1)
                     for p,c in zip(peer_log,m)),.0025)
    between=max(variance(m)-mean(scale/sum(w for _,w in p) for p in peer_log),
                scale/12,.0025)
    k0=max(2.,min(10.,scale/between))
    workload_prior=dict(mean0=mean(m),kappa0=k0,alpha0=3.,beta0=2*scale)
    workload=_nig_update(log_series(subject),workload_prior)
    grid=[]
    for t in bu._t_quantiles(workload['df']):
        x=workload['mu']+workload['predictive_scale']*t
        if abs(x)>25:raise be.ModelUnavailable('implausible_exposure_posterior')
        grid.append(math.exp(x))
    # Pool independent peers for the production-per-minute prior.
    rates=[]
    totals=[]
    residual=[]
    exposures=[]
    for group in cohort:
        total=sum(row[3]*row[4] for row in group)
        rate=sum(row[2]*row[4] for row in group)/total
        rates.append(rate);totals.append(total)
        exposures.extend(row[3] for row in group)
        residual.append(sum(row[4]*(row[2]-row[3]*rate)**2 for row in group)/
                        max(sum(row[4] for row in group)-1.,1.))
    center=mean(rates)
    if center<=0:raise be.ModelUnavailable('nonpositive_peer_conversion')
    exposure=median(exposures)
    if dist=='normal':
        resid=max(median(residual),max(abs(center)*exposure*.05,.01)**2)
        between=max(variance(rates),resid/(12*exposure**2))
        game_strength=max(2.,min(10.,resid/max(between*exposure**2,1e-9)))
        k0=game_strength*exposure**2
        a0,b0=3.,2*resid
        k=k0+sum(row[4]*row[3]**2 for row in subject)
        mu=(k0*center+sum(row[4]*row[2]*row[3] for row in subject))/k
        a=a0+sum(row[4] for row in subject)/2
        b=b0+(sum(row[4]*row[2]**2 for row in subject)+k0*center**2-k*mu**2)/2
        if b<=0 or a<=1:raise be.ModelUnavailable('invalid_conversion_posterior')
        under=push=left=0.
        for w in grid:
            mn=w*mu
            scale=math.sqrt(b/a*(1+w*w/k))
            def cdf(v):return be.student_t_cdf((v-mn)/scale,2*a)
            if abs(line-round(line))<1e-9:
                below=cdf(line-.5)
                under+=below
                push+=cdf(line+.5)-below
            else:under+=cdf(line)
            left+=cdf(-.5)
        under/=len(grid);push/=len(grid);left/=len(grid)
        if left>.02:raise be.ModelUnavailable('normal_predictive_negative_mass')
        convert=dict(kind='normal_power_likelihood',mean=mu,kappa=k,alpha=a,beta=b)
        rate_se=math.sqrt(b/(k*(a-1)))
    elif dist in ('poisson','negbin'):
        if any(not row[2].is_integer() for row in subject):
            raise be.ModelUnavailable('noninteger_count_observation')
        between=max(variance(rates)-mean(max(0,r)/total for r,total in zip(rates,totals)),1e-9)
        equiv=max(2*exposure,min(10*exposure,center/between))
        alpha0,beta0=max(center*equiv,1e-5),equiv
        if dist=='poisson':
            alpha=alpha0+sum(row[4]*row[2] for row in subject)
            beta=beta0+sum(row[4]*row[3] for row in subject)
            convert=dict(kind='gamma_poisson_exact',alpha=alpha,beta=beta,
                         posterior_rate_mean=alpha/beta,posterior_rate_se=math.sqrt(alpha)/beta)
            rate_se=convert['posterior_rate_se']
        else:
            ratio=be._number(var_ratio,allow_zero=False)
            if not 1.1<ratio<=3:raise be.ModelUnavailable('invalid_negbin_variance_ratio')
            center=max(center,sum(row[4]*row[2] for row in subject)/
                       sum(row[4]*row[3] for row in subject),1e-7)
            lo=max(-20.,math.log(center)-6.5)
            hi=min(16.,math.log(center)+6.5)
            nodes=[]
            for i in range(bu.GRID_RATE):
                z=lo+(hi-lo)*i/(bu.GRID_RATE-1)
                rate=math.exp(z)
                score=alpha0*z-beta0*rate
                for row in subject:
                    mu=row[3]*rate
                    score+=row[4]*be._nb_likelihood_log(row[2],mu,ratio)
                nodes.append((rate,score))
            peak=max(v for _,v in nodes)
            raw=[math.exp(v-peak) for _,v in nodes]
            total=math.fsum(raw)
            if total<=0:raise be.ModelUnavailable('negbin_integration_failed')
            post=[(rate,w/total) for (rate,_),w in zip(nodes,raw)]
            rate_mean=math.fsum(rate*w for rate,w in post)
            rate_se=math.sqrt(math.fsum(w*(rate-rate_mean)**2 for rate,w in post))
            convert=dict(kind='negbin_lograte_quadrature',nodes=post,ratio=ratio,
                         posterior_rate_mean=rate_mean,posterior_rate_se=rate_se)
        whole=abs(line-round(line))<1e-9
        cut=math.floor(line)
        under=push=0.
        for w in grid:
            lower=bu._count_cdf(w,convert,dist,cut-1 if whole else cut)
            under+=lower
            if whole:push+=max(0.,bu._count_cdf(w,convert,dist,cut)-lower)
        under/=len(grid);push/=len(grid)
        left=0.
        mu=convert['posterior_rate_mean']
    else:raise be.ModelUnavailable('unsupported_distribution')
    over=max(0.,1-under-push)
    win=over if side=='over' else under
    loss=under if side=='over' else over
    if side not in ('under','over') or not all(0<=p<=1 for p in (win,loss,push)):
        raise be.ModelUnavailable('invalid_posterior_probability')
    conversion_summary={k:v for k,v in convert.items() if k!='nodes'}
    return dict(version=VERSION,status='shadow_only',q_win=win,q_push=push,q_loss=loss,
                q_over=over,q_under=under,mean=mean(grid)*mu,
                workload_mean=mean(grid),workload_sd=math.sqrt(variance(grid)),
                conversion_mean=mu,conversion_se=rate_se,
                workload={'prior':workload_prior,'posterior':workload,
                          'integration_method':'weighted_prior_student_t_workload_quadrature'},
                conversion=conversion_summary,negative_tail_mass=left,
                n_exposure_games=len(subject),
                effective_exposure_games=sum(row[4] for row in subject),peer_count=len(cohort),
                predictive_method='source_verified_early_season_power_likelihood',
                approximation='peer_hyperparameter_empirical_bayes',
                publication_eligible=False,source_only_prior_power=POWER,
                input_fingerprint=hashlib.sha256(json.dumps(
                    [(row[0],row[2],row[3],row[4]) for row in subject]).encode()).hexdigest())
