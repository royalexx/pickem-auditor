"""Phase 2: Bayesian workload x conversion Engine B (shadow only).

Empirical-Bayes hyperparameters are learned from *other* source-verified players
within one sport/stat. Subject data update a log-workload Normal-inverse-Gamma
posterior and a conditional conversion posterior. Predictive probabilities
integrate future exposure using deterministic Student-t quantile quadrature,
not Monte Carlo. No market, future game, injury, or qualitative assumptions.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from statistics import mean, median, variance, NormalDist

import bayesian_engine as base
import usage_baseline as ub

VERSION = 'usage-bayes-v1'
GRID_WORKLOAD = 17
GRID_RATE = 121
MIN_POSITIVE = 5
MIN_PEERS = 5
NORMAL_STATS = frozenset({'points','pra','pr','pa','ra','passing yards','receiving yards','rushing yards'})
SIGNED_STATS = frozenset({'passing yards','receiving yards','rushing yards'})
_MODEL_ZERO = 1e-12
ND=NormalDist()


def verified_pairs(record, *, before, sport, stat):
    """Return dated (production, exposure) pairs, rejecting ambiguous records."""
    if not isinstance(record,dict) or not isinstance(record.get('observations'),list):
        raise base.ModelUnavailable('missing_collector_usage_history')
    seen=set()
    pairs=[]
    for item in record['observations']:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not item['id'].strip():
            raise base.ModelUnavailable('missing_usage_observation_id')
        if item['id'] in seen:
            raise base.ModelUnavailable('duplicate_usage_observation')
        seen.add(item['id'])
        if base._date(item.get('date')) >= before:
            raise base.ModelUnavailable('future_usage_observation')
        y=base._number(item.get('value'))
        w=base._number(item.get('workload'))
        if w < 0 or (y < 0 and (sport!='NFL' or stat not in SIGNED_STATS)):
            raise base.ModelUnavailable('invalid_production_or_workload')
        if w == 0 and y != 0:
            raise base.ModelUnavailable('production_without_workload')
        if w > 0:
            pairs.append((item['id'],y,w))
    if len(pairs)<MIN_POSITIVE:
        raise base.ModelUnavailable('insufficient_positive_exposure_games')
    return pairs


@lru_cache(maxsize=128)
def _peer_index(root, sport, stat, before):
    """Cache signed, source-dated versions; enforce exact cutoff on each read."""
    directory=Path(root)/'usage'
    if not directory.exists():
        return ()
    found={}
    for files in (directory.glob('*.json'), (directory/'snapshots').glob('*.json')):
        for path in files:
            loaded=base._load_one(path,None)
            if loaded is None:
                continue
            record,at=loaded
            if record.get('sport')!=sport or not record.get('player_id'):
                continue
            try:
                if ub.source_stat(record.get('stat'))!=ub.source_stat(stat):
                    continue
                pairs=verified_pairs(record,before=before,sport=sport,stat=stat)
            except (base.ModelUnavailable,KeyError,ValueError,TypeError):
                continue
            found.setdefault(str(record['player_id']),[]).append(((at,len(pairs),path.name),tuple(pairs)))
    return tuple((key,tuple(sorted(records,reverse=True))) for key,records in sorted(found.items()))


def peers_from_cache(root, *, sport,stat,player_id,forecast_at,source_date):
    peers=[]
    for key,versions in _peer_index(str(root),sport,stat,source_date):
        if key==str(player_id):
            continue
        for (stamp,count,path),pairs in versions:
            if stamp<=forecast_at:
                peers.append(list(pairs))
                break
    return peers


def _nig_prior(player_series, *, floor=0.0025):
    """Peer-determined prior for a random variable on its natural scale."""
    if len(player_series)<MIN_PEERS:
        raise base.ModelUnavailable('insufficient_usage_peer_players')
    centers=[mean(xs) for xs in player_series]
    within=[variance(xs) for xs in player_series]
    mu=mean(centers)
    within_var=max(median(within),floor)
    between=max(variance(centers)-mean(v/len(xs) for v,xs in zip(within,player_series)),
                within_var/12,1e-8)
    kappa=max(2.0,min(10.0,within_var/between))
    return {'mu0':mu,'kappa0':kappa,'alpha0':3.0,'beta0':2.0*within_var,
            'between_player_variance':between,'within_player_variance':within_var}


def _nig_update(xs, prior):
    n=len(xs)
    if n<MIN_POSITIVE:
        raise base.ModelUnavailable('insufficient_exposure_sample')
    average=mean(xs)
    mu0,k0,a0,b0=(prior[k] for k in ('mu0','kappa0','alpha0','beta0'))
    kn=k0+n
    mu=(k0*mu0+n*average)/kn
    a=a0+n/2.0
    b=b0+sum((x-average)**2 for x in xs)/2.0+k0*n*(average-mu0)**2/(2*kn)
    if not b>0 or not a>1:
        raise base.ModelUnavailable('invalid_workload_posterior')
    return {'mu':mu,'kappa':kn,'alpha':a,'beta':b,'df':2*a,
            'predictive_scale':math.sqrt(b*(kn+1)/(a*kn)),
            'posterior_mean_se':math.sqrt(b/(kn*(a-1)))}


@lru_cache(maxsize=128)
def _t_quantiles(df, count=GRID_WORKLOAD):
    """Deterministic equal-probability Student-t integration, no random draws."""
    result=[]
    for i in range(count):
        quantile=(i+0.5)/count
        lo,hi=-15.0,15.0
        for _ in range(47):
            mid=(lo+hi)/2
            if base.student_t_cdf(mid,df)<quantile:
                lo=mid
            else:
                hi=mid
        result.append((lo+hi)/2)
    return tuple(result)


def workload_posterior(pairs, peers):
    """Model positive-game exposure; do not turn nonappearances into unders."""
    prior=_nig_prior([[math.log(w) for _,_,w in peer] for peer in peers])
    posterior=_nig_update([math.log(w) for _,_,w in pairs],prior)
    # Clamp log only to avoid overflow for extreme but formally finite inputs.
    levels=[]
    for t in _t_quantiles(posterior['df']):
        x=posterior['mu']+posterior['predictive_scale']*t
        if abs(x)>25:
            raise base.ModelUnavailable('implausible_exposure_posterior')
        levels.append(math.exp(x))
    return {'prior':prior,'posterior':posterior,'future_exposures':levels,
            'expected_exposure':mean(levels),
            'exposure_sd':math.sqrt(variance(levels)),
            'integration_method':'equal_mass_student_t_log_workload_v1'}


def _conversion_prior(peers,kind):
    if len(peers)<MIN_PEERS:
        raise base.ModelUnavailable('insufficient_conversion_peer_players')
    rates=[]
    per_game=[]
    exposures=[]
    residual_vars=[]
    for rows in peers:
        total=sum(w for _,_,w in rows)
        r=sum(y for _,y,w in rows)/total
        rates.append(r)
        per_game.append(total)
        exposures.extend(w for _,_,w in rows)
        residual_vars.append(sum((y-r*w)**2 for _,y,w in rows)/max(1,len(rows)-1))
    exposure=median(exposures)
    center=mean(rates)
    between=max(variance(rates)-mean(max(0,r)/total for r,total in zip(rates,per_game)),1e-9)
    if kind=='count':
        if center<=0:
            raise base.ModelUnavailable('nonpositive_conversion_peer_rate')
        equivalent=max(2*exposure,min(10*exposure,center/between))
        return {'alpha0':max(center*equivalent,1e-5),'beta0':equivalent,
                'mean_rate0':center,'equivalent_exposure':equivalent,
                'peer_count':len(peers)}
    residual=max(median(residual_vars),max(abs(center)*exposure*.05,.01)**2)
    between=max(variance(rates),residual/(12*exposure**2))
    game_strength=max(2.0,min(10.0,residual/max(between*exposure**2,1e-9)))
    return {'mu0':center,'kappa0':game_strength*exposure**2,
            'alpha0':3.0,'beta0':2.0*residual,
            'mean_rate0':center,'peer_count':len(peers),
            'residual_variance_prior':residual,'equivalent_games':game_strength}


def _normal_conversion(pairs,peers):
    prior=_conversion_prior(peers,'normal')
    k0,m0,a0,b0=(prior[k] for k in ('kappa0','mu0','alpha0','beta0'))
    k=k0+sum(w*w for _,_,w in pairs)
    mu=(k0*m0+sum(y*w for _,y,w in pairs))/k
    a=a0+len(pairs)/2.0
    b=b0+(sum(y*y for _,y,w in pairs)+k0*m0*m0-k*mu*mu)/2
    if b<=0 or a<=1:
        raise base.ModelUnavailable('invalid_conversion_posterior')
    return {'prior':prior,'mu':mu,'kappa':k,'alpha':a,'beta':b,
            'rate_posterior_se':math.sqrt(b/(k*(a-1)))}


def _count_conversion(pairs,peers,dist,ratio):
    prior=_conversion_prior(peers,'count')
    if any(y<0 or not y.is_integer() for _,y,_ in pairs):
        raise base.ModelUnavailable('count_stat_requires_integer_results')
    if dist=='poisson':
        alpha=prior['alpha0']+sum(y for _,y,_ in pairs)
        beta=prior['beta0']+sum(w for _,_,w in pairs)
        return {'prior':prior,'kind':'gamma_poisson_exact','alpha':alpha,'beta':beta,
                'posterior_rate_mean':alpha/beta,
                'posterior_rate_se':math.sqrt(alpha)/beta}
    if not 1.10<ratio<=3:
        raise base.ModelUnavailable('invalid_negbin_variance_ratio')
    # True NB likelihood on paired (production, exposure), with a Gamma rate
    # prior. Marginal posterior integrates over the *log rate* including its
    # Jacobian. Dispersion is a fixed observational estimate, not integrated.
    center=max(prior['mean_rate0'],
               sum(y for _,y,_ in pairs)/sum(w for _,_,w in pairs),1e-7)
    lo=max(-20.0,math.log(center)-6.5)
    hi=min(16.0,math.log(center)+6.5)
    grid=[]
    for i in range(GRID_RATE):
        z=lo+(hi-lo)*i/(GRID_RATE-1)
        rate=math.exp(z)
        score=prior['alpha0']*z-prior['beta0']*rate
        for _,y,w in pairs:
            mu=w*rate
            shape=mu/(ratio-1)
            score+=(math.lgamma(y+shape)-math.lgamma(shape)-math.lgamma(y+1)
                    +shape*math.log(1/ratio)+y*math.log1p(-1/ratio))
        grid.append((rate,score))
    peak=max(x[1] for x in grid)
    raw=[math.exp(score-peak) for rate,score in grid]
    denom=math.fsum(raw)
    if not denom or not math.isfinite(denom):
        raise base.ModelUnavailable('negbin_integration_failed')
    nodes=[(r,weight/denom) for (r,_),weight in zip(grid,raw)]
    mu=math.fsum(r*weight for r,weight in nodes)
    se=math.sqrt(math.fsum(weight*(r-mu)**2 for r,weight in nodes))
    return {'prior':prior,'kind':'negbin_lograte_quadrature','ratio':ratio,
            'posterior_rate_mean':mu,'posterior_rate_se':se,
            'nodes':nodes}


def _count_cdf(w,conv,dist,cut):
    """Return P(count <= cut | workload=w), integrating conversion rate."""
    if cut<0:
        return 0.0
    if dist=='poisson':
        alpha,beta=conv['alpha'],conv['beta']
        p=(beta/(beta+w))**alpha
        total=p
        for k in range(cut):
            p*=((k+alpha)/(k+1))*(w/(beta+w))
            total+=p
        return max(0.,min(1.,total))
    ratio=conv['ratio']
    total=0.0
    for rate,weight in conv['nodes']:
        if weight<1e-15:
            continue
        mu=w*rate
        shape=mu/(ratio-1)
        p=math.exp(-shape*math.log(ratio))
        cdf=p
        for k in range(cut):
            p*=((k+shape)/(k+1))*(1-1/ratio)
            cdf+=p
        total+=weight*cdf
    return max(0.,min(1.,total))


def forecast(pairs,peers,*,dist,line,side,var_ratio=None,stat,sport):
    """Source-only Bayesian forecast of workload x observed conversion."""
    line=base._number(line)
    if line<0 or side not in ('over','under'):
        raise base.ModelUnavailable('invalid_prop_line_or_side')
    if dist not in ('normal','poisson','negbin'):
        raise base.ModelUnavailable('unsupported_distribution')
    if len(peers)<MIN_PEERS:
        raise base.ModelUnavailable('insufficient_usage_peer_players')
    for observations in [pairs,*peers]:
        if len(observations)<MIN_POSITIVE:
            raise base.ModelUnavailable('thin_player_or_peer_history')
    exposure=workload_posterior(pairs,peers)
    wgrid=exposure['future_exposures']
    if dist=='normal':
        conversion=_normal_conversion(pairs,peers)
        under=push=0.0
        left_tail=0.0
        for w in wgrid:
            mu=w*conversion['mu']
            scale=math.sqrt(conversion['beta']/conversion['alpha']*(1+w*w/conversion['kappa']))
            df=2*conversion['alpha']
            def cdf(v):return base.student_t_cdf((v-mu)/scale,df)
            if abs(line-round(line))<1e-9:
                below=cdf(line-.5)
                upto=cdf(line+.5)
                under+=below
                push+=upto-below
            else:
                under+=cdf(line)
            left_tail+=cdf(-.5)
        under/=len(wgrid);push/=len(wgrid)
        left_tail/=len(wgrid)
        if stat not in SIGNED_STATS and left_tail>.02:
            raise base.ModelUnavailable('normal_predictive_negative_mass')
        rate_mean=conversion['mu']
        rate_se=conversion['rate_posterior_se']
        conversion_summary={'prior':conversion['prior'],'mean':rate_mean,
                            'posterior_se':rate_se,'alpha':conversion['alpha'],
                            'beta':conversion['beta'],'kappa':conversion['kappa'],
                            'likelihood':'normal_inverse_gamma_regression'}
    else:
        conv=_count_conversion(pairs,peers,dist,var_ratio)
        whole=abs(line-round(line))<1e-9
        cut=math.floor(line)
        under=push=0.0
        for w in wgrid:
            below=_count_cdf(w,conv,dist,cut-1 if whole else cut)
            under+=below
            if whole:
                push+=max(0.0,_count_cdf(w,conv,dist,cut)-below)
        under/=len(wgrid);push/=len(wgrid)
        rate_mean=conv['posterior_rate_mean']
        rate_se=conv['posterior_rate_se']
        conversion_summary={k:v for k,v in conv.items() if k!='nodes'}
        left_tail=0.0
    over=max(0.0,1-under-push)
    win=over if side=='over' else under
    loss=under if side=='over' else over
    if not all(math.isfinite(v) and -1e-9<=v<=1+1e-9
               for v in (win,loss,push)) or abs(win+loss+push-1)>1e-8:
        raise base.ModelUnavailable('predictive_mass_inconsistent')
    return dict(version=VERSION,status='shadow_only',q_win=win,q_push=push,q_loss=loss,
                q_over=over,q_under=under,mean=exposure['expected_exposure']*rate_mean,
                workload_mean=exposure['expected_exposure'],workload_sd=exposure['exposure_sd'],
                conversion_mean=rate_mean,conversion_se=rate_se,
                workload={'prior':exposure['prior'],'posterior':exposure['posterior'],
                          'integration_method':exposure['integration_method']},
                conversion=conversion_summary,
                predictive_method='paired_likelihood_and_deterministic_workload_quadrature',
                approximation='empirical_group_hyperparameters_and_equal_mass_workload_quadrature',
                n_exposure_games=len(pairs),peer_count=len(peers),
                negative_tail_mass=left_tail,
                calibrated=False,publication_eligible=False)
