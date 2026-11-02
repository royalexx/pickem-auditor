"""Posterior predictive Monte Carlo for Phase 1/2 Bayesian shadow distributions.

Reproducible conditional Monte Carlo: draw posterior latent means/variances,
integrate next-game observation noise analytically (Rao-Blackwellization).
This reduces simulation noise, not epistemic uncertainty. It must never
blend A/B, rank candidates, or replace research/market verification.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import math
import random
from statistics import NormalDist

import bayesian_engine as be

VERSION = 'posterior-mc-v1'
NBA_PRIOR_VERSION = 'nba-source-prior-power-v1'
SUPPORTED_POSTERIOR_VERSIONS_A = frozenset((be.VERSION, NBA_PRIOR_VERSION))
SUPPORTED_POSTERIOR_VERSIONS_B = frozenset((
    'usage-bayes-v1', 'usage-bayes-v2-bounded-exposure', NBA_PRIOR_VERSION))
MIN_DRAWS = 1024
MAX_DRAWS = 8192
TARGET_HALF_WIDTH = 0.008
Z95 = 1.959963984540054
NORM = NormalDist()


def seed_for(identity, engine):
    encoded=json.dumps({'identity':identity,'engine':engine,'model':VERSION},
                       sort_keys=True,allow_nan=False,separators=(',',':')).encode()
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], 'big')


def _rate(value, name):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
        raise be.ModelUnavailable('invalid_posterior_parameter_'+name)
    return float(value)


def t_draw(rng, df):
    return rng.gauss(0,1) * math.sqrt(df/(2*rng.gammavariate(df/2,1)))


def ig_draw(rng,alpha,beta):
    return _rate(beta,'beta')/rng.gammavariate(_rate(alpha,'alpha'),1)


def _cdf_count(dist, mu, threshold, ratio=None):
    if threshold<0:
        return 0.0
    if mu<=0:
        return 1.0
    if dist=='poisson':
        p=math.exp(-mu)
        total=p
        for k in range(threshold):
            p*=mu/(k+1)
            total+=p
        return min(1.0,max(0.0,total))
    if dist=='negbin':
        r=_rate(ratio,'ratio')
        if not 1.1<r<=3:
            raise be.ModelUnavailable('unsupported_nb_ratio')
        shape=mu/(r-1)
        p=math.exp(-shape*math.log(r))
        total=p
        for k in range(threshold):
            p*=((k+shape)/(k+1))*(1-1/r)
            total+=p
        return min(1.0,max(0.0,total))
    raise be.ModelUnavailable('unsupported_count_distribution')


def conditional_probs(dist,mean,line,*,sd=None,ratio=None):
    """(over, under, push) for one latent posterior state, all unconditional."""
    if not math.isfinite(mean) or not math.isfinite(line) or line<0:
        raise be.ModelUnavailable('invalid_conditional_mean_or_line')
    whole=abs(line-round(line))<=1e-9
    if dist=='normal':
        sd=_rate(sd,'sd')
        if whole:
            under=NORM.cdf((line-.5-mean)/sd)
            upto=NORM.cdf((line+.5-mean)/sd)
            push=upto-under
        else:
            under=NORM.cdf((line-mean)/sd)
            push=0.0
    else:
        cut=math.floor(line)
        under=_cdf_count(dist,mean,cut-1 if whole else cut,ratio)
        push=(_cdf_count(dist,mean,cut,ratio)-under) if whole else 0.0
    if min(under,push)<-1e-9 or under+push>1+1e-9:
        raise be.ModelUnavailable('invalid_conditional_probability')
    return max(0,1-under-push),under,max(0,push)


def _nb_grid_a(values,prior,ratio):
    """Same log-rate likelihood and 401 point integration as history-bayes-v1."""
    ratio=_rate(ratio,'ratio')
    if not 1.1<ratio<=3:
        raise be.ModelUnavailable('invalid_negbin_dispersion')
    if any(not x.is_integer() or x<0 for x in values):
        raise be.ModelUnavailable('noninteger_a_observations')
    center=max(prior['mean0'],sum(values)/len(values),be.EPS)
    lo=min(-18.0,math.log(center)-9)
    hi=max(math.log(center)+9,math.log(max(values)+1)+7)
    grid=[]
    for i in range(401):
        z=lo+i*(hi-lo)/400
        lam=math.exp(z)
        score=prior['alpha0']*z-prior['beta0']*lam+sum(
            be._nb_likelihood_log(y,lam,ratio) for y in values)
        grid.append((lam,score))
    return _grid_normalize(grid)


def _grid_normalize(grid):
    if not grid:
        raise be.ModelUnavailable('empty_posterior_rate_grid')
    peak=max(x[1] for x in grid)
    raw=[math.exp(score-peak) for _,score in grid]
    denom=math.fsum(raw)
    if denom<=0 or not math.isfinite(denom):
        raise be.ModelUnavailable('invalid_posterior_rate_grid')
    return [(rate,p/denom) for (rate,_),p in zip(grid,raw)]


def _discrete_sampler(nodes):
    if not nodes:
        raise be.ModelUnavailable('missing_nb_posterior_rate_nodes')
    cum=[];rates=[];total=0.0
    for rate,prob in nodes:
        _rate(rate,'node_rate')
        if not math.isfinite(prob) or prob<0:
            raise be.ModelUnavailable('invalid_nb_node_weight')
        total+=prob
        rates.append(rate)
        cum.append(total)
    if abs(total-1)>1e-6:
        raise be.ModelUnavailable('posterior_rate_weights_not_normalized')
    def choose(rng):
        return rates[min(bisect.bisect_left(cum,rng.random()*total),len(rates)-1)]
    return choose


def sampler_a(posterior, *, values=None):
    """Build conditional predictive sampler from immutable Phase 1 output."""
    if (posterior.get('status')!='forecast' or
            posterior.get('version') not in SUPPORTED_POSTERIOR_VERSIONS_A):
        raise be.ModelUnavailable('invalid_bayesian_a_forecast')
    dist=posterior.get('distribution')
    if posterior.get('version')==NBA_PRIOR_VERSION and dist=='negbin':
        raise be.ModelUnavailable('weighted_prior_negbin_mc_requires_source_reconstruction')
    p=posterior.get('posterior_parameters') or {}
    if dist=='poisson':
        alpha=_rate(p.get('alpha'),'alpha');beta=_rate(p.get('beta'),'beta')
        return lambda rng:(rng.gammavariate(alpha,1/beta),None,None)
    if dist=='negbin':
        if values is None:
            raise be.ModelUnavailable('a_negbin_requires_source_reconstruction')
        prior=posterior.get('population_prior') or {}
        ratio=_rate(p.get('variance_ratio'),'ratio')
        choose=_discrete_sampler(_nb_grid_a(values,prior,ratio))
        return lambda rng:(choose(rng),None,ratio)
    if dist=='normal':
        mu=float(posterior['posterior_mean'])
        alpha=_rate(p.get('alpha'),'alpha')
        beta=_rate(p.get('beta'),'beta')
        kappa=_rate(p.get('kappa'),'kappa')
        return lambda rng:(mu,math.sqrt(ig_draw(rng,alpha,beta)*(1+1/kappa)),None)
    raise be.ModelUnavailable('unsupported_a_distribution')


def sampler_b(posterior, *, pairs=None, peers=None):
    """Sample shared latent future workload, and conditional conversion rate."""
    if (posterior.get('status')!='forecast' or
            posterior.get('version') not in SUPPORTED_POSTERIOR_VERSIONS_B):
        raise be.ModelUnavailable('invalid_bayesian_b_forecast')
    dist=posterior.get('distribution')
    if posterior.get('version')==NBA_PRIOR_VERSION and dist=='negbin':
        raise be.ModelUnavailable('weighted_prior_negbin_mc_requires_source_reconstruction')
    wp=(posterior.get('workload_posterior') or {}).get('posterior') or {}
    wm=float(wp['mu'])
    ws=_rate(wp.get('predictive_scale'),'workload_scale')
    df=_rate(wp.get('df'),'workload_df')
    conversion=posterior.get('conversion_posterior') or {}
    if dist=='poisson':
        alpha=_rate(conversion.get('alpha'),'conversion_alpha')
        beta=_rate(conversion.get('beta'),'conversion_beta')
        def rate(rng):
            return rng.gammavariate(alpha,1/beta),None,None
    elif dist=='negbin':
        if pairs is None or peers is None:
            raise be.ModelUnavailable('b_negbin_requires_source_reconstruction')
        import bayesian_usage as bu
        ratio=_rate(conversion.get('ratio'),'variance_ratio')
        fitted=bu._count_conversion(pairs,peers,'negbin',ratio)
        if abs(fitted['posterior_rate_mean']-conversion['posterior_rate_mean'])>1e-7:
            raise be.ModelUnavailable('b_negbin_source_posterior_mismatch')
        choose=_discrete_sampler(fitted['nodes'])
        def rate(rng):
            return choose(rng),None,ratio
    elif dist=='normal':
        mu=float(conversion['mean'])
        alpha=_rate(conversion.get('alpha'),'conversion_alpha')
        beta=_rate(conversion.get('beta'),'conversion_beta')
        kappa=_rate(conversion.get('kappa'),'conversion_kappa')
        def rate(rng):
            return mu,(alpha,beta,kappa),None
    else:
        raise be.ModelUnavailable('unsupported_b_distribution')
    def sample(rng):
        if posterior.get('version')=='usage-bayes-v2-bounded-exposure':
            details=posterior.get('workload_posterior') or {}
            bounds=details.get('physical_workload_bounds')
            if (not isinstance(bounds,(list,tuple)) or len(bounds)!=2 or
                    not all(isinstance(x,(int,float)) and not isinstance(x,bool)
                            and math.isfinite(x) and x>0 for x in bounds)
                    or bounds[0]>=bounds[1]):
                raise be.ModelUnavailable('missing_bounded_workload_provenance')
            lo,hi=math.log(bounds[0]),math.log(bounds[1])
            # Rejection draws exactly sample the normalized truncated Student-t
            # conditional distribution. No clipping: clipping creates boundary
            # atoms and a different posterior predictive law.
            for _ in range(256):
                logw=wm+ws*t_draw(rng,df)
                if lo<=logw<=hi:
                    break
            else:
                raise be.ModelUnavailable('bounded_workload_mc_rejection_exhausted')
        else:
            logw=wm+ws*t_draw(rng,df)
            if not -25<logw<25:
                raise be.ModelUnavailable('implausible_simulated_workload')
        workload=math.exp(logw)
        r,uncertainty,ratio=rate(rng)
        if uncertainty is None:
            return workload*r,None,ratio
        a,b,k=uncertainty
        # Integrate uncertain conversion beta analytically conditional on
        # posterior residual variance; no extra independent beta draw.
        sd=math.sqrt(ig_draw(rng,a,b)*(1+workload*workload/k))
        return workload*r,sd,None
    return sample


def simulate(posterior, *, engine, identity, line, side,
             draws=MIN_DRAWS, max_draws=MAX_DRAWS, target=TARGET_HALF_WIDTH,
             values=None, pairs=None, peers=None):
    """Adaptive, seeded, *conditional* posterior Monte Carlo.

    MC CI quantifies numerical integration error ONLY, not uncertainty in the
    win probability or model calibration.
    """
    if side not in ('over','under') or not isinstance(draws,int) or not isinstance(max_draws,int):
        raise be.ModelUnavailable('invalid_mc_configuration')
    if not 256<=draws<=max_draws<=65536 or not 0<target<0.1:
        raise be.ModelUnavailable('invalid_mc_sample_budget')
    if engine=='A':
        sampler=sampler_a(posterior,values=values)
    elif engine=='B':
        sampler=sampler_b(posterior,pairs=pairs,peers=peers)
    else:
        raise be.ModelUnavailable('invalid_simulation_engine')
    dist=posterior['distribution']
    seed=seed_for(identity,engine)
    rng=random.Random(seed)
    sums=[0.,0.,0.]
    square=[0.,0.,0.]
    n=0
    while n<max_draws:
        batch=min(draws if n==0 else draws,max_draws-n)
        for _ in range(batch):
            mu,sd,ratio=sampler(rng)
            q=conditional_probs(dist,mu,float(line),sd=sd,ratio=ratio)
            for i,value in enumerate(q):
                sums[i]+=value
                square[i]+=value*value
        n+=batch
        q=[v/n for v in sums]
        se=[math.sqrt(max(0.,(square[i]/n-q[i]**2)/(n-1))) for i in range(3)]
        if n>=draws and max(Z95*s for s in se)<=target:
            break
    over,under,push=q
    win=over if side=='over' else under
    loss=under if side=='over' else over
    win_se=se[0] if side=='over' else se[1]
    expect=posterior.get('q_win')
    expect_push=posterior.get('q_push')
    if not isinstance(expect,(float,int)) or not isinstance(expect_push,(float,int)):
        raise be.ModelUnavailable('missing_analytic_bayesian_comparator')
    # Four independent MC SEs + fixed approximation allowance (B uses 17
    # workload quantiles; MC samples the underlying Student-t distribution).
    allowed=max(.025,4*win_se)
    delta=abs(win-expect)
    return {'version':VERSION,'status':'shadow_only','engine':engine,
        'q_win':win,'q_push':push,'q_loss':loss,'q_over':over,'q_under':under,
        'draws':n,'max_draws':max_draws,'target_95_half_width':target,
        'mc_se_win':win_se,'mc_95_half_width_win':Z95*win_se,
        'mc_95_half_width_push':Z95*se[2],
        'analytic_q_win':expect,'analytic_q_push':expect_push,
        'abs_analytic_delta':delta,
        'analytic_agreement':delta<=allowed and abs(push-expect_push)<=max(.025,4*se[2]),
        'agreement_tolerance':allowed,'seed':seed,
        'randomness':'sha256_seeded_local_python_random',
        'method':'posterior_latent_mc_observation_noise_integrated',
        'uncertainty_note':'MC error is numerical precision, not a confidence interval for the true probability',
        'calibrated':False,'publication_eligible':False}
