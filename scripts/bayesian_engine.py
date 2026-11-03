"""Source-only hierarchical empirical-Bayes Engine A, shadow model (history-bayes-v1).

A group prior is estimated from *other players'* verified, dated game logs within
one sport/stat; the subject's own dated production updates that prior. No
workload, context, market, outcome, or post-forecast data enters the model.

This is conditional Bayesian inference with empirical hyperparameters, NOT a
fully Bayesian posterior over population hyperparameters. Do not publish tiers.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from statistics import mean, median, variance
from functools import lru_cache

VERSION = 'history-bayes-v2-cdf-fixed'
MIN_PLAYER_GAMES = 5
MIN_PEERS = 5
EPS = 1e-9


class ModelUnavailable(ValueError):
    """No legitimate, supported posterior can be generated."""


def _number(value, *, allow_zero=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ModelUnavailable('invalid_numeric_observation')
    if not allow_zero and value <= 0:
        raise ModelUnavailable('nonpositive_parameter')
    return float(value)


def _date(value):
    if not isinstance(value, str):
        raise ModelUnavailable('missing_source_date')
    try:
        v = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if len(value) == 10:
            return v.date()
        if v.tzinfo is None:
            raise ModelUnavailable('naive_source_timestamp')
        return v.astimezone(ZoneInfo('America/Toronto')).date()
    except (TypeError, ValueError) as exc:
        raise ModelUnavailable('invalid_source_date') from exc


def _stamp(value):
    try:
        v = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if v.tzinfo is None:
            raise ValueError('timezone missing')
        return v.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError) as exc:
        raise ModelUnavailable('invalid_retrieval_time') from exc


def validated_values(record, *, before, allow_negative=False):
    """Never accept future, undated, duplicate or unowned observation IDs."""
    if not isinstance(record, dict) or not isinstance(record.get('observations'), list):
        raise ModelUnavailable('missing_collector_game_log')
    rows = record['observations']
    if len(rows) < MIN_PLAYER_GAMES:
        raise ModelUnavailable('short_player_history')
    ids, values = set(), []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
            raise ModelUnavailable('missing_observation_identity')
        ident = row['id']
        if ident in ids:
            raise ModelUnavailable('duplicate_observation_identity')
        ids.add(ident)
        if _date(row.get('date')) >= before:
            raise ModelUnavailable('future_game_observation')
        value = _number(row.get('value'))
        if value < 0 and not allow_negative:
            raise ModelUnavailable('negative_count_or_production')
        values.append(value)
    return values, sorted(ids)


def _load_one(path: Path, cutoff: datetime):
    """Verify cached source digest even for peer histories before using it."""
    try:
        raw = path.read_text(encoding='utf-8')
        record = json.loads(raw)
        if not isinstance(record, dict) or record.get('version') != 'usage-history-v2':
            return None
        if path.parent.name == 'snapshots':
            if hashlib.sha256(json.dumps(record, sort_keys=True, allow_nan=False).encode()).hexdigest() != path.stem:
                return None
        else:
            digest = record.get('content_sha256')
            if not isinstance(digest, str):
                return None
            clone = {k: v for k, v in record.items() if k != 'content_sha256'}
            if digest != hashlib.sha256(json.dumps(clone, sort_keys=True, allow_nan=False).encode()).hexdigest():
                return None
        stamp = _stamp(record.get('retrieved_at'))
        if cutoff is not None and stamp > cutoff:
            return None
        return record, stamp
    except (OSError, ValueError, TypeError, ModelUnavailable):
        return None


@lru_cache(maxsize=128)
def _peer_index(root, sport, stat, source_date):
    """Cache checksum-verified peers once per sport/stat/day.

    Retrieval timestamps remain in the index. Each forecast's exact cutoff
    is enforced after caching, never rounded to a minute.
    """
    import usage_baseline as ub
    folder = Path(root) / 'usage'
    if not folder.is_dir():
        return []
    selected = {}
    for pattern in (folder.glob('*.json'), (folder / 'snapshots').glob('*.json')):
        for path in pattern:
            loaded = _load_one(path, None)
            if loaded is None:
                continue
            rec, stamp = loaded
            try:
                if (rec.get('sport') != sport or ub.source_stat(rec.get('stat')) != ub.source_stat(stat)
                        or not rec.get('player_id')):
                    continue
                values, ids = validated_values(rec, before=source_date, allow_negative=stat in ('receiving yards','rushing yards','passing yards'))
                if len(values) < MIN_PLAYER_GAMES:
                    continue
                key = str(rec['player_id'])
                identity = (stamp, len(values), path.name)
                selected.setdefault(key, []).append((identity, values, ids))
            except (ValueError, TypeError, ModelUnavailable):
                continue
    return tuple((key,tuple(sorted(items,reverse=True))) for key,items in sorted(selected.items()))


def peers_from_cache(root, *, sport, stat, player_id, cutoff, source_date):
    """Exclude target player and any snapshot retrieved after this forecast."""
    result=[]
    for key,versions in _peer_index(str(root),sport,stat,source_date):
        if key == str(player_id):continue
        for (stamp, count, path),values,ids in versions:
            if stamp <= cutoff:
                result.append((values,ids))
                break
    return result


def group_prior(peer_values, kind):
    """Estimate stable between-player dispersion from disjoint player logs.

    Hyperparameters deliberately have modest effective sample strength; they
    are fitted on peer production only, without using the subject's game log.
    """
    if len(peer_values) < MIN_PEERS:
        raise ModelUnavailable('insufficient_peer_players')
    means = [mean(v) for v in peer_values]
    center = mean(means)
    if not math.isfinite(center) or center <= 0:
        raise ModelUnavailable('nonpositive_peer_population')
    between_raw = variance(means)
    within = [variance(v) if len(v) > 1 else center for v in peer_values]
    within_scale = max(median(within), EPS)
    sampling_var = mean(s / len(v) for s, v in zip(within, peer_values))
    between = max(between_raw - sampling_var, within_scale / 12, EPS)
    strength = max(2.0, min(12.0, within_scale / between))
    if kind == 'normal':
        # Normal-inverse-Gamma prior; variance is uncertain and integrated out.
        return dict(mean0=center, kappa0=strength, alpha0=3.0,
                    beta0=2.0 * within_scale, peer_count=len(means),
                    within_variance=within_scale, between_variance=between)
    if kind == 'count':
        # Gamma prior on the Poisson/NB latent rate: E[lambda] = alpha/beta.
        rate = max(2.0, min(12.0, center / between))
        return dict(alpha0=center * rate, beta0=rate, peer_count=len(means),
                    mean0=center, between_variance=between)
    raise ModelUnavailable('unsupported_distribution')


def _betacf(a, b, x):
    """Continued fraction for regularized incomplete beta (Numerical Recipes)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1, a - 1
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny: d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 301):
        m2 = 2*m
        aa = m*(b-m)*x/((qam+m2)*(a+m2))
        d = 1+aa*d
        if abs(d) < tiny: d = tiny
        c = 1+aa/c
        if abs(c) < tiny: c = tiny
        d = 1/d
        h *= d*c
        aa = -(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d = 1+aa*d
        if abs(d) < tiny: d = tiny
        c = 1+aa/c
        if abs(c) < tiny: c = tiny
        d = 1/d
        # Numerical Recipes: multiply the second continued-fraction factor
        # exactly once. Double-multiplication corrupted Student-t CDF tails.
        delta = d*c
        h *= delta
        if abs(delta-1) < 2e-13:
            return h
    raise ModelUnavailable('beta_cdf_nonconvergence')


def _ibeta(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    factor = math.exp(math.lgamma(a+b) - math.lgamma(a) - math.lgamma(b)
                      + a*math.log(x) + b*math.log1p(-x))
    if x < (a+1)/(a+b+2):
        return max(0.0, min(1.0, factor*_betacf(a,b,x)/a))
    return max(0.0, min(1.0, 1-factor*_betacf(b,a,1-x)/b))


def student_t_cdf(x, df):
    if not math.isfinite(x) or df <= 0:
        raise ModelUnavailable('invalid_student_t_input')
    if x == 0: return 0.5
    p = 0.5*_ibeta(df/2, 0.5, df/(df+x*x))
    return 1-p if x > 0 else p


def _normal_predictive(values, prior, *, line):
    n = len(values)
    xbar = mean(values)
    ss = sum((v-xbar)**2 for v in values)
    k0, a0, b0, mu0 = (prior[k] for k in ('kappa0','alpha0','beta0','mean0'))
    kn, an = k0+n, a0+n/2
    mun = (k0*mu0+n*xbar)/kn
    bn = b0+ss/2+(k0*n*(xbar-mu0)**2)/(2*kn)
    df = 2*an
    scale = math.sqrt(bn*(kn+1)/(an*kn))
    # Integer-valued sports stats have genuine whole-line push probabilities.
    if abs(line-round(line)) <= 1e-9:
        under=student_t_cdf((line-0.5-mun)/scale,df)
        upper=student_t_cdf((line+0.5-mun)/scale,df)
        push=max(0.0,upper-under)
        over=1-upper
    else:
        under=student_t_cdf((line-mun)/scale,df)
        push=0.0
        over=1-under
    negative_mass=student_t_cdf((-0.5-mun)/scale,df)
    return dict(mean=mun, q_over=over, q_under=under, q_push=push,
                negative_tail_mass=negative_mass,
                predictive_scale=scale, degrees_freedom=df,
                posterior_mean_se=math.sqrt(bn/(kn*(an-1))),
                posterior_parameters={'kappa':kn,'alpha':an,'beta':bn})


def _low_count_probs(probs, *, line):
    if line < 0 or not math.isfinite(line):
        raise ModelUnavailable('invalid_count_line')
    whole = abs(line-round(line)) <= 1e-9
    cut = math.floor(line)
    under = sum(probs[:cut]) if whole else sum(probs[:cut+1])
    push = probs[cut] if whole and cut < len(probs) else 0.0
    return max(0.0,1-under-push), under, push


def _gamma_poisson_predictive(values, prior, line):
    if any(not x.is_integer() for x in values):
        raise ModelUnavailable('noninteger_count_observation')
    alpha, beta = prior['alpha0']+sum(values), prior['beta0']+len(values)
    mean_next = alpha/beta
    p0 = (beta/(beta+1))**alpha
    vals = [p0]
    # NB predictive with shape alpha and success probability beta/(beta+1).
    for k in range(max(0, math.floor(line))):
        vals.append(vals[-1]*(k+alpha)/(k+1)/(beta+1))
    over, under, push = _low_count_probs(vals,line=line)
    return dict(mean=mean_next,q_over=over,q_under=under,q_push=push,
                posterior_mean_se=math.sqrt(alpha)/beta,
                posterior_parameters={'alpha':alpha,'beta':beta},
                predictive_variance=mean_next*(1+1/beta))


def _nb_likelihood_log(y, lam, ratio):
    shape = lam/(ratio-1)
    return (math.lgamma(y+shape) - math.lgamma(shape) - math.lgamma(y+1)
            + shape*math.log(1/ratio) + y*math.log1p(-1/ratio))


def _negative_binomial_predictive(values, prior, line, ratio):
    if any(not x.is_integer() for x in values):
        raise ModelUnavailable('noninteger_count_observation')
    if not 1.1 < ratio <= 3.0:
        raise ModelUnavailable('invalid_negbin_dispersion')
    alpha0, beta0 = prior['alpha0'],prior['beta0']
    center=max(prior['mean0'],mean(values),EPS)
    # Deterministic log-rate quadrature: includes Jacobian exp(log-rate).
    lo = min(-18.0, math.log(center)-9)
    hi = max(math.log(center)+9, math.log(max(values)+1)+7)
    nodes = 401
    step = (hi-lo)/(nodes-1)
    data = []
    for i in range(nodes):
        z=lo+i*step
        lam=math.exp(z)
        lp=alpha0*z-beta0*lam + sum(_nb_likelihood_log(v,lam,ratio) for v in values)
        data.append((lam,lp))
    high=max(row[1] for row in data)
    mass=[math.exp(score-high) for lam,score in data]
    total=math.fsum(mass)
    if not math.isfinite(total) or total == 0:
        raise ModelUnavailable('posterior_integration_failure')
    weights=[v/total for v in mass]
    mean_next=math.fsum(lam*w for (lam,_),w in zip(data,weights))
    cutoff=max(0,math.floor(line))
    prob=[0.0]*(cutoff+1)
    for (lam,_),weight in zip(data,weights):
        if weight < 1e-16: continue
        shape=lam/(ratio-1)
        p=math.exp(shape*math.log(1/ratio))
        for k in range(cutoff+1):
            prob[k]+=weight*p
            p*=((k+shape)/(k+1))*(1-1/ratio)
    over, under, push=_low_count_probs(prob,line=line)
    return dict(mean=mean_next,q_over=over,q_under=under,q_push=push,
                posterior_mean_se=math.sqrt(math.fsum(w*(lam-mean_next)**2 for (lam,_),w in zip(data,weights))),
                posterior_parameters={'quadrature_nodes':nodes,'variance_ratio':ratio},
                uncertainty_method='log_rate_quadrature')


def forecast(values, peers, *, dist, line, side, var_ratio=None, allow_negative=False):
    """Output strictly unconditional win/push/loss, never Tier labels."""
    if side not in ('over','under'):
        raise ModelUnavailable('invalid_side')
    line=_number(line)
    if not values or any(not math.isfinite(v) or (v < 0 and dist != 'normal') for v in values):
        raise ModelUnavailable('invalid_subject_history')
    if dist not in ('poisson','negbin','normal'):
        raise ModelUnavailable('unsupported_distribution')
    prior=group_prior(peers, 'normal' if dist=='normal' else 'count')
    if dist=='normal':
        prediction=_normal_predictive(values, prior, line=line)
    elif dist=='poisson':
        prediction=_gamma_poisson_predictive(values, prior, line)
    else:
        prediction=_negative_binomial_predictive(values, prior, line, _number(var_ratio,allow_zero=False))
    if dist=='normal' and not allow_negative and prediction['negative_tail_mass']>0.02:
        raise ModelUnavailable('normal_predictive_negative_mass')
    q_win=prediction['q_over'] if side=='over' else prediction['q_under']
    q_push=prediction['q_push']
    if not (0 <= q_win <= 1 and 0 <= q_push <= 1 and q_win+q_push <= 1+1e-9):
        raise ModelUnavailable('invalid_posterior_probability')
    return {**prediction,'version':VERSION,'status':'shadow_only','distribution':dist,
            'q_win':q_win,'q_push':q_push,'q_loss':max(0.0,1-q_win-q_push),
            'n_observations':len(values),'peer_count':len(peers),
            'population_prior':prior,'empirical_hyperparameters':True,
            'validated_for_publication':False}
