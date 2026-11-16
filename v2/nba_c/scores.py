"""P5 C-family proper scores. Outcome access is deliberately caller-supplied.

All distributions are integer, finite, non-negative complete count laws. The
finite PMF is not silently renormalized and sparse support is retained.
"""
from __future__ import annotations
from collections import defaultdict
import math
import random


class ScoreError(ValueError):
    pass


def validate_pmf(pmf):
    """Return sorted (value, mass) pairs from G0 PMF rows or a mapping."""
    rows = list(pmf.items()) if isinstance(pmf, dict) else [
        (x["value"], x["mass"]) if isinstance(x, dict) else tuple(x) for x in pmf
    ]
    if not rows:
        raise ScoreError("EMPTY_PMF")
    seen, clean = set(), []
    for value, mass in rows:
        if type(value) is not int or value < 0 or value in seen:
            raise ScoreError("INVALID_PMF_SUPPORT")
        if type(mass) not in (int, float) or not math.isfinite(mass) or mass < 0:
            raise ScoreError("INVALID_PMF_MASS")
        seen.add(value)
        clean.append((value, float(mass)))
    if abs(math.fsum(m for _, m in clean) - 1.0) > 1e-10:
        raise ScoreError("PMF_NOT_NORMALIZED")
    return tuple(sorted(clean))


def _actual(y):
    if type(y) is not int or y < 0:
        raise ScoreError("INVALID_OFFICIAL_COUNT")
    return y


def mean(pmf):
    return math.fsum(k*p for k,p in validate_pmf(pmf))


def variance(pmf):
    x = validate_pmf(pmf)
    mu = math.fsum(k*p for k,p in x)
    return math.fsum((k-mu)**2*p for k,p in x)


def crps(pmf, outcome):
    """Exact discrete full-count CRPS via E|X-y| - 1/2 E|X-X'|.

    Uses linear-time sorted-support identity for the double expectation,
    including all unrepresented integer gaps and zero/tail mass.
    """
    y = _actual(outcome)
    rows = validate_pmf(pmf)
    ey = math.fsum(p*abs(k-y) for k,p in rows)
    before_mass, before_sum, cross = 0.0, 0.0, 0.0
    for k,p in rows:
        cross += p*(k*before_mass-before_sum)
        before_mass += p
        before_sum += p*k
    return max(0.0, ey-cross)


def reference_crps(pmf, outcome):
    """Independent O(K^2) CRPS reference for small fixtures."""
    y = _actual(outcome)
    rows = validate_pmf(pmf)
    return (math.fsum(p*abs(k-y) for k,p in rows)
            - .5*math.fsum(p*q*abs(k-j)
                           for k,p in rows for j,q in rows))


def nll(pmf, outcome):
    y = _actual(outcome)
    p = dict(validate_pmf(pmf)).get(y, 0.0)
    return -math.log(p) if p > 0 else math.inf


def quantile(pmf, level):
    if not 0 <= level <= 1 or not math.isfinite(level):
        raise ScoreError("INVALID_QUANTILE")
    rows = validate_pmf(pmf)
    total = 0.0
    for k,p in rows:
        total += p
        if total >= level-1e-14:
            return k
    return rows[-1][0]


def randomized_pit(pmf, outcome, *, u=None, seed=None):
    """PIT = F(y-) + U P(y); random U is saved by caller for reproducibility."""
    if (u is None) == (seed is None):
        raise ScoreError("PIT_REQUIRES_SEED_OR_U")
    if u is None:
        u = random.Random(seed).random()
    if not 0 <= u <= 1 or not math.isfinite(u):
        raise ScoreError("INVALID_PIT_RANDOMIZER")
    y = _actual(outcome)
    rows = validate_pmf(pmf)
    return math.fsum(p for k,p in rows if k < y) + u*dict(rows).get(y, 0.0)


def diagnostics(pmf, outcome, *, seed, central=0.9, tail_threshold=30):
    if not 0 < central < 1 or type(seed) is not int:
        raise ScoreError("INVALID_DIAGNOSTIC_CONFIG")
    y = _actual(outcome)
    rows = validate_pmf(pmf)
    mu = mean(rows)
    low = quantile(rows,(1-central)/2)
    high = quantile(rows,1-(1-central)/2)
    return {
        "crps":crps(rows,y), "nlpd":nll(rows,y),
        "absolute_error":abs(mu-y), "squared_error":(mu-y)**2,
        "signed_bias":mu-y, "mean":mu, "variance":variance(rows),
        "pit":randomized_pit(rows,y,seed=seed),
        "interval":[low, high], "covered":low <= y <= high,
        "nominal_coverage":central, "zero_predicted":dict(rows).get(0,0.0),
        "zero_observed":int(y==0),
        "tail_threshold":tail_threshold,
        "tail_predicted":math.fsum(p for k,p in rows if k>=tail_threshold),
        "tail_observed":int(y>=tail_threshold),
    }


def aggregate(scores):
    rows = list(scores)
    if not rows:
        raise ScoreError("EMPTY_SCORE_COHORT")
    output = {}
    keys = ("crps","absolute_error","squared_error","signed_bias","covered",
            "zero_predicted","zero_observed","tail_predicted","tail_observed")
    for key in keys:
        output[key] = math.fsum(float(r[key]) for r in rows)/len(rows)
    output["rmse"] = math.sqrt(output.pop("squared_error"))
    output["mae"] = output.pop("absolute_error")
    output["mean_nlpd"] = (math.fsum(r["nlpd"] for r in rows)/len(rows)
                             if all(math.isfinite(r["nlpd"]) for r in rows) else math.inf)
    output["n_forecast_rows_not_scenarios"] = len(rows)
    return output


def _joint(scenarios, y):
    """Each scenario is one coherent same-game vector with a weight."""
    if not scenarios or not y:
        raise ScoreError("EMPTY_JOINT")
    d = len(y)
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in y):
        raise ScoreError("INVALID_JOINT_OUTCOME")
    rows = []
    for item in scenarios:
        x,p = item if isinstance(item,tuple) else (item["values"],item["weight"])
        if len(x)!=d or any(type(v) not in (int,float) or not math.isfinite(v) for v in x):
            raise ScoreError("JOINT_DIMENSION_OR_VALUE")
        if type(p) not in (int,float) or not math.isfinite(p) or p < 0:
            raise ScoreError("JOINT_WEIGHT")
        rows.append((tuple(x),float(p)))
    if abs(math.fsum(w for _,w in rows)-1)>1e-10:
        raise ScoreError("JOINT_WEIGHT_SUM")
    return rows


def _norm(x,y):
    return math.sqrt(math.fsum((a-b)**2 for a,b in zip(x,y)))


def energy_score(scenarios, outcome, *, max_pair_terms=None, seed=0):
    """ES = E||X-y|| - (1/2) E||X-X'||.

    Exact with all ordered pairs or seeded independent pair quadrature.
    Pair terms are computational integration, NEVER observed game samples.
    """
    rows = _joint(scenarios,outcome)
    first = math.fsum(w*_norm(x,outcome) for x,w in rows)
    if max_pair_terms is None or len(rows)**2 <= max_pair_terms:
        second = math.fsum(w*v*_norm(x,z) for x,w in rows for z,v in rows)
    else:
        if type(max_pair_terms) is not int or max_pair_terms < 100:
            raise ScoreError("TOO_FEW_PAIR_TERMS")
        rng=random.Random(seed)
        cumulative=[]
        running=0.0
        for _,w in rows:
            running+=w
            cumulative.append(running)
        import bisect
        second=math.fsum(_norm(rows[bisect.bisect_left(cumulative,rng.random())][0],
                               rows[bisect.bisect_left(cumulative,rng.random())][0])
                          for _ in range(max_pair_terms))/max_pair_terms
    return first-.5*second


def variogram_score(scenarios, outcome, *, power=.5, pair_weights=None):
    """VS_p = sum_{i<j} w_ij(|y_i-y_j|^p-E|X_i-X_j|^p)^2."""
    rows=_joint(scenarios,outcome)
    if not 0<power<2:
        raise ScoreError("INVALID_VARIOGRAM_POWER")
    d=len(outcome)
    result=0.0
    for i in range(d):
        for j in range(i+1,d):
            w=1.0 if pair_weights is None else pair_weights.get((i,j),0.0)
            if not math.isfinite(w) or w<0:
                raise ScoreError("INVALID_PAIR_WEIGHT")
            expect=math.fsum(prob*abs(x[i]-x[j])**power for x,prob in rows)
            result+=w*(abs(outcome[i]-outcome[j])**power-expect)**2
    return result


def scenarios_to_pmf(scenarios, statistic_index=0):
    rows=_joint(scenarios,(0,)*len(scenarios[0][0] if isinstance(scenarios[0],tuple) else scenarios[0]["values"]))
    sums=defaultdict(float)
    for vec,w in rows:
        v=vec[statistic_index]
        if type(v) is not int or v<0:
            raise ScoreError("NONINTEGER_JOINT_COUNT")
        sums[v]+=w
    return tuple(sorted(sums.items()))
