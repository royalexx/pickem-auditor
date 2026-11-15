"""Proper scores and dependence-aware uncertainty, WS4 schema v1."""
import hashlib
import math
import random
from collections import defaultdict


def probability(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError('INVALID_PROBABILITY')
    return float(x)


def masses(pmf):
    if not isinstance(pmf, (list, tuple)) or not pmf:
        raise ValueError('EMPTY_SUPPORT')
    p = [probability(x) for x in pmf]
    if abs(math.fsum(p)-1) > 1e-10:
        raise ValueError('NON_NORMALIZED_MASS')
    return p


def threshold(pmf, line):
    p = masses(pmf)
    if isinstance(line, bool) or not math.isfinite(line) or line < 0:
        raise ValueError('INVALID_LINE')
    return {name: math.fsum(v for k, v in enumerate(p) if relation(k, line))
            for name, relation in [('over', lambda k,l:k>l), ('under', lambda k,l:k<l), ('push', lambda k,l:k==l)]}


def log_score(p):
    p = probability(p)
    return -math.log(p) if p else float('inf')


def binary(p, y):
    p = probability(p)
    if y not in (0, 1): raise ValueError('INVALID_BINARY_TARGET')
    return {'brier': (p-y)**2, 'log_loss': log_score(p if y else 1-p), 'signed_over_residual': p-y}


def distribution(pmf, y, *, identity, seed=20261115, interval=.9, tail=10):
    """Count CRPS = sum_{k>=0}(F(k)-1{y<=k})²; finite complete support only.

    Unrepresented mass is rejected; an observed count beyond finite support has
    infinite NLPD, and CRPS includes all intervening integer thresholds.
    """
    p = masses(pmf)
    if isinstance(y, bool) or not isinstance(y, int) or y < 0: raise ValueError('INVALID_COUNT')
    if not 0 < interval < 1 or not isinstance(tail, int) or tail < 0: raise ValueError('INVALID_DIAGNOSTIC')
    cdf=[]; total=0
    for v in p: total+=v; cdf.append(total)
    def quantile(q): return next((k for k,v in enumerate(cdf) if v>=q),len(p)-1)
    lo,hi=quantile((1-interval)/2),quantile((1+interval)/2)
    u=random.Random(hashlib.sha256(f'{seed}|{identity}'.encode()).hexdigest()).random()
    below=math.fsum(p[:y]); at=p[y] if y<len(p) else 0
    return {'count_crps': math.fsum(((cdf[k] if k<len(p) else 1)-int(y<=k))**2 for k in range(max(len(p),y+1))),
            'nlpd': log_score(at), 'randomized_pit': below+u*at,
            'interval': [lo,hi], 'interval_nominal': interval, 'interval_covered': lo<=y<=hi,
            'predicted_zero':p[0], 'observed_zero':int(y==0),
            'tail_threshold':tail, 'predicted_tail':math.fsum(p[tail:]), 'observed_tail':int(y>=tail)}


def mean(xs): return math.fsum(xs)/len(xs) if xs else None


def summary(rows):
    """Rows already validated; all-eligible and selected summaries kept separate."""
    nonpush=[r for r in rows if r['outcome'] in ('over','under')]
    scored=[dict(r, **binary(r['p'], int(r['outcome']=='over'))) for r in nonpush]
    selected=[r for r in scored if r['p'] != .5]
    def side_report(rs):
        return {'n':len(rs), 'confidence':mean([max(r['p'],1-r['p']) for r in rs]),
                'hit_rate':mean([int((r['p']>.5)==(r['outcome']=='over')) for r in rs])}
    # Selection is fixed by forecast confidence, grouped by decision/slate ID;
    # it is formed BEFORE filtering pushes/voids from the scoring denominator.
    selections={}
    for k in (1,5,10):
        groups=defaultdict(list)
        for r in rows:
            if r['p']!=.5: groups[r['slate_id']].append(r)
        chosen=[r for g in groups.values() for r in sorted(g,key=lambda r:(-max(r['p'],1-r['p']),r['contract_id']))[:k]]
        resolved=[r for r in chosen if r['outcome'] in ('over','under')]
        selections[str(k)]={**side_report(resolved), 'selected_sides':len(chosen),
            'push':sum(r['outcome']=='push' for r in chosen), 'void':sum(r['outcome']=='void' for r in chosen),
            'unsettled':sum(r['outcome']=='pending' for r in chosen),
            'brier':mean([binary(r['p'],int(r['outcome']=='over'))['brier'] for r in resolved]),
            'contract_ids':[r['contract_id'] for r in chosen]}
    return {'available':len(rows), 'binary_scored':len(scored),
        'games':len({r['event_id'] for r in scored}), 'dates':len({r['date'] for r in scored}),
        'players':len({r['player_id'] for r in scored}), 'contracts':len({r['contract_id'] for r in scored}),
        'selected_sides':len(selected), 'ties':len(scored)-len(selected),
        'brier':mean([r['brier'] for r in scored]), 'log_loss':mean([r['log_loss'] for r in scored]),
        'calibration_in_the_large_observed_minus_predicted':mean([int(r['outcome']=='over')-r['p'] for r in scored]),
        'signed_over_probability_residual':mean([r['signed_over_residual'] for r in scored]),
        'side_conditional':{s:side_report([r for r in selected if (r['p']>.5)==(s=='over')]) for s in ('over','under')},
        'top_k':selections}


def paired_bootstrap(rows, *, cluster='date', draws=2000, seed=20261115):
    """Paired row-weighted difference; resample whole date/game clusters.

    Caller supplies one precomputed challenger-minus-control loss per matched
    contract. Game sensitivity does not establish independence across games.
    """
    if cluster not in ('date','game'): raise ValueError('INDEPENDENT_ROW_BOOTSTRAP_FORBIDDEN')
    groups=defaultdict(list); seen=set()
    for r in rows:
        if r['contract_id'] in seen: raise ValueError('DUPLICATE_MATCH')
        seen.add(r['contract_id'])
        if not math.isfinite(r['delta']): raise ValueError('NONFINITE_PAIRED_SCORE')
        groups[r['date'] if cluster=='date' else (r['date'],r['event_id'])].append(r['delta'])
    vals=list(groups.values())
    result={'n':len(rows),'clusters':len(vals),'cluster':cluster,'mean_delta':mean([r['delta'] for r in rows]),
            'interval':None,'seed':seed,'draws':draws,'status':'INCONCLUSIVE'}
    if len(vals)<2: return result
    if not isinstance(draws,int) or draws<100: raise ValueError('INSUFFICIENT_BOOTSTRAP_DRAWS')
    rng=random.Random(seed)
    sims=sorted(mean([x for g in rng.choices(vals,k=len(vals)) for x in g]) for _ in range(draws))
    result.update(interval=[sims[int(.025*draws)],sims[min(draws-1,int(.975*draws))]],status='DESCRIPTIVE_ONLY')
    return result


def poisson_diagnostics(rate, y, *, identity, seed=20261115, interval=.9):
    """Exact count CRPS for Poisson; no truncated/renormalized tail mass.

    CRPS = (y-lambda)(2F(y)-1)+2lambda f(y)
           -lambda exp(-2lambda)[I0(2lambda)+I1(2lambda)].
    Scaled Bessel functions avoid overflow. Degenerate lambda=0 is exact.
    """
    from scipy.stats import poisson
    from scipy.special import ive
    if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not math.isfinite(rate) or rate<0:
        raise ValueError('INVALID_POISSON_RATE')
    if isinstance(y,bool) or not isinstance(y,int) or y<0:raise ValueError('INVALID_COUNT')
    if not 0<interval<1:raise ValueError('INVALID_INTERVAL')
    f=float(poisson.pmf(y,rate));cdf=float(poisson.cdf(y,rate));below=float(poisson.cdf(y-1,rate))
    crps=float((y-rate)*(2*cdf-1)+2*rate*f-rate*(ive(0,2*rate)+ive(1,2*rate))) if rate else float(y)
    lo,hi=int(poisson.ppf((1-interval)/2,rate)),int(poisson.ppf((1+interval)/2,rate))
    tail=int(poisson.ppf(.9,rate))
    u=random.Random(hashlib.sha256(f'{seed}|{identity}'.encode()).hexdigest()).random()
    return {'count_crps':crps,'nlpd':float(-poisson.logpmf(y,rate)),
        'randomized_pit':below+u*f,'predicted_zero':float(poisson.pmf(0,rate)),'observed_zero':int(y==0),
        'interval':[lo,hi],'interval_nominal':interval,'interval_covered':lo<=y<=hi,
        'upper_tail_threshold_strict_gt':tail,'predicted_tail':float(poisson.sf(tail,rate)),
        'observed_tail':int(y>tail),'proper_support':'all_nonnegative_integers'}
