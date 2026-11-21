"""P5 research-only proper scores. Complete distributions, no market inference."""
from __future__ import annotations
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timezone

class ScoreError(ValueError):
    pass

def _fail(code):
    raise ScoreError(code)

def _utc(s):
    if not isinstance(s, str) or not (s.endswith("Z") or s.endswith("+00:00")):
        _fail("UTC_TIMESTAMP_REQUIRED")
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        _fail("INVALID_TIMESTAMP")
    if d.utcoffset() is None or d.utcoffset().total_seconds() != 0:
        _fail("UTC_TIMESTAMP_REQUIRED")
    return d

def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                  allow_nan=False).encode()).hexdigest()

def _number(x):
    return type(x) in (float, int) and math.isfinite(x)

def _log_mass(kind, p, k):
    if kind == "poisson":
        mu = p["rate"]
        if mu == 0:
            return 0.0 if k == 0 else -math.inf
        return -mu + k * math.log(mu) - math.lgamma(k + 1)
    if kind == "gamma_poisson":
        a, b = p["shape"], p["rate"]
        return (math.lgamma(k+a)-math.lgamma(a)-math.lgamma(k+1)
                + a * math.log(b/(b+1)) - k * math.log1p(b))
    if kind == "nb2":
        mu, r = p["mean"], p["shape"]
        if mu == 0:
            return 0.0 if k == 0 else -math.inf
        return (math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)
                + r * math.log(r/(r+mu)) + k * math.log(mu/(r+mu)))
    _fail("UNSUPPORTED_LIKELIHOOD")

def full_pmf(distribution, *, observed=None, tail_tolerance=1e-10):
    """Return unrenormalized full-count masses; reject unbounded missing tail."""
    if not isinstance(distribution, dict):
        _fail("DISTRIBUTION_INVALID")
    kind = distribution.get("kind")
    if observed is not None and (type(observed) is not int or observed < 0):
        _fail("ACTUAL_NOT_NONNEGATIVE_COUNT")
    if kind in ("discrete", "scenario_pmf"):
        pairs = distribution.get("masses")
        if not isinstance(pairs, list) or not pairs:
            _fail("MASS_LIST_INVALID")
        v = {}
        for pair in pairs:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                _fail("MASS_PAIR_INVALID")
            x, prob = pair
            if type(x) is not int or x < 0 or not _number(prob) or prob < 0 or x in v:
                _fail("DUPLICATE_OR_INVALID_MASS")
            v[x] = float(prob)
        if abs(math.fsum(v.values())-1.0) > 1e-10:
            _fail("DISTRIBUTION_NOT_NORMALIZED")
        return [v.get(k, 0.0) for k in range(max(max(v), observed or 0)+1)], 0.0
    if kind == "p4_count_pmf":
        masses = distribution.get("pmf_from_zero")
        tail = distribution.get("unallocated_upper_tail_mass")
        if not isinstance(masses, list) or not masses or not _number(tail):
            _fail("P4_PMF_INVALID")
        if not 0 <= tail <= tail_tolerance or any(not _number(p) or p < 0 for p in masses):
            _fail("P4_TAIL_UNBOUNDED")
        if abs(math.fsum(masses)+tail-1) > tail_tolerance:
            _fail("P4_PMF_INCOMPLETE")
        if observed is not None and observed >= len(masses):
            _fail("P4_ACTUAL_OUTSIDE_CERTIFIED_PMF")
        return [float(p) for p in masses], float(tail)
    if kind not in ("poisson", "gamma_poisson", "nb2"):
        _fail("UNSUPPORTED_DISTRIBUTION_KIND")
    p = distribution.get("parameters")
    if not isinstance(p, dict):
        _fail("PARAMETERS_MISSING")
    names = {"poisson":{"rate"}, "gamma_poisson":{"shape","rate"},
             "nb2":{"shape","mean"}}[kind]
    if set(p) != names or any(not _number(v) or v < 0 for v in p.values()):
        _fail("PARAMETER_INVALID")
    if ("shape" in p and p["shape"] <= 0 or
            kind == "gamma_poisson" and p["rate"] <= 0):
        _fail("PARAMETER_INVALID")
    mu = (p["rate"] if kind == "poisson" else
          p["shape"] / p["rate"] if kind == "gamma_poisson" else p["mean"])
    var = (mu if kind == "poisson" else
           mu + mu*mu/(p["shape"] if kind == "nb2" else p["shape"]))
    kmax = max(100, int(math.ceil(mu+20*math.sqrt(max(var, 0))+100)), observed or 0)
    if kmax > 100000:
        _fail("DISTRIBUTION_SUPPORT_TOO_EXPENSIVE")
    masses = [math.exp(_log_mass(kind,p,k)) for k in range(kmax+1)]
    tail = max(0.0, 1.0-math.fsum(masses))
    if tail > tail_tolerance or math.fsum(masses) > 1+tail_tolerance:
        _fail("UNRESOLVED_UPPER_TAIL")
    return masses, tail

def score_count(distribution, actual, *, forecast_id="", level=.90):
    if type(actual) is not int or actual < 0:
        _fail("ACTUAL_NOT_NONNEGATIVE_COUNT")
    if not 0 < level < 1:
        _fail("COVERAGE_LEVEL_INVALID")
    masses, tail = full_pmf(distribution, observed=actual)
    mean = math.fsum(k*v for k,v in enumerate(masses))
    var = math.fsum((k-mean)**2*v for k,v in enumerate(masses))
    f = 0.
    crps = 0.
    quantiles = {}
    targets = ((1-level)/2, .5, (1+level)/2)
    for k,p in enumerate(masses):
        f += p
        crps += (f-(1.0 if k>=actual else 0.0))**2
        for q in targets:
            if q not in quantiles and f >= q:
                quantiles[q] = k
    if len(quantiles)!=3:
        _fail("QUANTILE_NOT_AVAILABLE")
    below = math.fsum(masses[:actual])
    observed_mass = masses[actual] if actual < len(masses) else 0
    seed = int(hashlib.sha256(str(forecast_id).encode()).hexdigest()[:16], 16)
    randomized_pit = below + random.Random(seed).random()*observed_mass
    low, med, high = [quantiles[q] for q in targets]
    tail_threshold = quantiles[.95] if .95 in quantiles else next(
         (i for i in range(len(masses)) if math.fsum(masses[:i+1]) >= .95),
         len(masses)-1)
    return {
        "crps": crps, "nlpd": -math.log(observed_mass) if observed_mass else math.inf,
        "mae": abs(mean-actual), "squared_error": (mean-actual)**2,
        "rmse": abs(mean-actual), "signed_bias": mean-actual,
        "randomized_pit": randomized_pit, "mean": mean, "variance": var,
        "p_zero": masses[0], "observed_zero": int(actual==0),
        "q_low": low, "q_median": med, "q_high": high,
        "interval_covered": int(low<=actual<=high),
        "p_upper_tail": math.fsum(masses[tail_threshold:])+tail,
        "observed_upper_tail": int(actual>=tail_threshold),
        "upper_tail_threshold": tail_threshold,
        "p_lower_tail": math.fsum(masses[:low+1]),
        "observed_lower_tail": int(actual<=low),
        "remaining_tail_bound": tail,
        "actual": actual,
    }

def three_way(distribution, line):
    if not _number(line) or line < 0:
        _fail("INVALID_MARKET_LINE")
    masses, tail=full_pmf(distribution)
    floor=int(math.floor(line))
    under=math.fsum(masses[:min(floor+1,len(masses))]) if line != floor else math.fsum(masses[:min(floor,len(masses))])
    push=masses[floor] if line==floor and floor<len(masses) else 0.
    over=max(0.0,1.0-under-push)
    if tail>1e-10:
        _fail("UNRESOLVED_MARKET_TAIL")
    return {"over":over,"under":under,"push":push}

def score_contract(distribution, actual, quote):
    if quote.get("quote_kind")!="real" or quote.get("accepted") is not True:
        _fail("ORIGINAL_REAL_QUOTE_REQUIRED")
    if not isinstance(quote.get("terms"),dict):
        _fail("ORIGINAL_CONTRACT_TERMS_REQUIRED")
    line=quote["line"]
    p=three_way(distribution,line)
    outcome="over" if actual>line else "under" if actual<line else "push"
    brier=math.fsum((p[k]-int(k==outcome))**2 for k in ("over","under","push"))
    return {"probabilities":p,"observed":outcome,"three_way_brier":brier,
            "three_way_log_loss": -math.log(p[outcome]) if p[outcome] else math.inf,
            "quote_id": quote["quote_id"], "contract_id":quote["contract_id"],
            "line":line,"book":quote["book"]}

def score_joint(paths, actual_vector, *, pair_budget=100000, seed=7, variogram_p=.5):
    """Shared game paths only; paths are Monte Carlo quadrature, never n games."""
    if not isinstance(paths,list) or not paths or len(paths[0])<2:
        _fail("JOINT_BANK_REQUIRED")
    d=len(paths[0]); n=len(paths)
    if len(actual_vector)!=d or any(len(p)!=d for p in paths):
        _fail("JOINT_DIMENSION_MISMATCH")
    if any(any(not _number(x) for x in row) for row in paths+[actual_vector]):
        _fail("JOINT_NONFINITE")
    def dist(a,b):
        return math.sqrt(math.fsum((a[i]-b[i])**2 for i in range(d)))
    mean_to_y=math.fsum(dist(p,actual_vector) for p in paths)/n
    if n*n <= pair_budget:
        pair_sum=math.fsum(dist(a,b) for a in paths for b in paths)/(n*n)
        pair_method="exact_all_pairs"
    else:
        rng=random.Random(seed)
        pair_sum=math.fsum(dist(paths[rng.randrange(n)],paths[rng.randrange(n)])
                           for _ in range(pair_budget))/pair_budget
        pair_method="fixed_seed_uniform_pair_mc"
    es=mean_to_y-.5*pair_sum
    vs=0.
    for i in range(d):
        for j in range(i+1,d):
            modeled=math.fsum(abs(p[i]-p[j])**variogram_p for p in paths)/n
            vs+=(abs(actual_vector[i]-actual_vector[j])**variogram_p-modeled)**2
    return {"energy_score":es,"variogram_score_p05":vs,
            "pair_evaluation":pair_method,"n_simulated_paths":n,
            "n_independent_observed_games":1}

def validate_combo(path):
    if any(type(path.get(k)) is not int or path[k]<0 for k in ("points","rebounds","assists","made_threes")):
        _fail("NBA_SCENARIO_COUNTS_INVALID")
    p,r,a=[path[k] for k in ("points","rebounds","assists")]
    if path.get("PR")!=p+r or path.get("PA")!=p+a or path.get("RA")!=r+a or path.get("PRA")!=p+r+a:
        _fail("NBA_COMBO_NOT_SAME_SCENARIO")
    if 3*path["made_threes"]>p:
        _fail("NBA_THREES_EXCEED_POINTS")
    return True

def paired_differences(rows, *, group="event_id", seed=9, n_boot=1000):
    """One paired unit per game/date; no line- or scenario-count inflation."""
    by=defaultdict(list)
    for r in rows:
        if not isinstance(r.get("a"),(int,float)) or not isinstance(r.get("b"),(int,float)):
            _fail("PAIRED_SCORES_MISSING")
        by[r[group]].append(float(r["a"])-float(r["b"]))
    if not by:
        _fail("EMPTY_PAIRED_COHORT")
    keys=sorted(by)
    clustered=[math.fsum(by[k])/len(by[k]) for k in keys]
    mean=math.fsum(clustered)/len(clustered)
    rng=random.Random(seed)
    boots=sorted(math.fsum(clustered[rng.randrange(len(clustered))]
              for _ in clustered)/len(clustered) for _ in range(n_boot))
    return {"mean_cluster_paired_difference":mean,
            "n_distinct_clusters":len(keys),
            "ci95":[boots[int(.025*(n_boot-1))],boots[int(.975*(n_boot-1))]],
            "n_simulated_paths_as_games":0}

LOCKED_NHL="EXP-V25-NHL-SOG-NB2-NATIVE-PLUGIN-MEAN-20261114"
def matched_native_nhl_pair(nb, control, *, count_dates):
    fields=("event_id","player_id","book","quote_id","contract_id",
            "line","source_manifest_sha256","input_freeze_at",
            "original_mean","outcome_id")
    if any(nb.get(k)!=control.get(k) or nb.get(k) is None for k in fields):
        _fail("REGISTERED_NB2_PAIR_IDENTITY_MISMATCH")
    if nb.get("experiment_id")!=LOCKED_NHL or nb.get("shape")!=4 or nb.get("model_family")!="native_nb2":
        _fail("REGISTERED_NB2_OR_SHAPE_INVALID")
    if control.get("model_family")!="plugin_poisson" or control.get("source_classification")!="original_signed":
        _fail("ORIGINAL_PLUGIN_POISSON_CONTROL_MISSING")
    if not nb.get("original_verified") or not control.get("original_verified"):
        _fail("REGISTERED_ORIGINAL_BYTES_UNVERIFIED")
    return {"status":"CONFIRMATORY_LOCKED" if count_dates>=40 else "DESCRIPTIVE_ONLY",
            "distinct_prospective_dates":count_dates,"minimum_distinct_dates":40,
            "control_original_mean":control["original_mean"],"shape":4}
