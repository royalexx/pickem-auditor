"""Cheap NFL marginal challengers. No collector, production writer or calibrator.

All laws are conditional on a recorded eligible appearance. DNP is never zero.
Empirical laws have finite observed support: valid benchmark distributions,
with no extrapolated unseen tail; that limitation is emitted with each law.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from statistics import mean, variance

from scipy.stats import nbinom, poisson

from .contracts import EventProbabilities, finite, canonical_hash
from .stat_registry import canonical_stat

VERSION = "nfl-ws2-marginal-v1"
PARAMETERS = {
    "min_player": 3, "min_peers": 5, "min_peer_games": 3, "max_history": 40,
    "empirical_strength": 4.0, "gamma_strength_min": 2.0,
    "gamma_strength_max": 12.0, "half_life": 4.0, "ew_window": 20,
    "hurdle_zero_threshold": .25, "hurdle_strength": 4.0,
    "logit_clip": 1e-9, "shrinkage": [.1, .25],
}
MODEL_IDS = ("S1-role-eb-empirical-v1", "S2-ew-empirical-hl4-v1",
             "S3-eb-poisson-v1", "S4-eb-gamma-poisson-v1",
             "S5-hurdle-geometric-v1", "S6-fixed-market-logit-v1",
             "S7-neutral-10-v1", "S7-neutral-25-v1")


class Unavailable(ValueError):
    pass


def checked_probability(value):
    p = finite(value, "probability")
    if not 0 <= p <= 1:
        raise Unavailable("invalid_probability")
    return p


@dataclass(frozen=True)
class Law:
    kind: str
    parameters: dict
    mean: float
    variance: float

    def pmf(self, k):
        if not float(k).is_integer():
            return 0.0
        k = int(k)
        p = self.parameters
        if self.kind == "empirical":
            return dict(p["masses"]).get(k, 0.0)
        if k < 0:
            return 0.0
        if self.kind == "poisson":
            return float(poisson.pmf(k, p["rate"]))
        if self.kind == "gamma_poisson":
            return float(nbinom.pmf(k, p["alpha"], p["beta"] / (p["beta"] + 1)))
        if self.kind == "hurdle_geometric":
            z, q = p["p_zero"], p["positive_success"]
            return z if k == 0 else (1-z)*q*(1-q)**(k-1)
        raise Unavailable("unsupported_law")

    def cdf(self, x):
        k = math.floor(x)
        p = self.parameters
        if self.kind == "empirical":
            return math.fsum(w for y, w in p["masses"] if y <= k)
        if k < 0:
            return 0.0
        if self.kind == "poisson":
            return float(poisson.cdf(k, p["rate"]))
        if self.kind == "gamma_poisson":
            return float(nbinom.cdf(k, p["alpha"], p["beta"] / (p["beta"] + 1)))
        z, q = p["p_zero"], p["positive_success"]
        return z if k == 0 else (z + (1-z)*(-math.expm1(k*math.log1p(-q))) if q < 1 else 1.0)

    def sf(self, x):
        k = math.floor(x)
        p = self.parameters
        if self.kind == "empirical":
            return math.fsum(w for y, w in p["masses"] if y > k)
        if k < 0:
            return 1.0
        if self.kind == "poisson":
            return float(poisson.sf(k, p["rate"]))
        if self.kind == "gamma_poisson":
            return float(nbinom.sf(k, p["alpha"], p["beta"] / (p["beta"] + 1)))
        z, q = p["p_zero"], p["positive_success"]
        return (1-z)*(1-q)**k

    def probabilities(self, line):
        line = finite(line, "line")
        under = self.cdf(math.ceil(line)-1)
        push = self.pmf(line) if line.is_integer() else 0.0
        return EventProbabilities(self.sf(line), under, push)

    def record(self, line):
        p = self.probabilities(line)
        no_push = p.over + p.under
        return {"kind": self.kind, "parameters": self.parameters,
                "parameter_version": VERSION, "mean": self.mean,
                "variance": self.variance, "q_over": p.over,
                "q_under": p.under, "q_push": p.push,
                "p_over_given_no_push": p.over/no_push if no_push else None,
                "conditioning": "eligible_appearance; binary probability additionally conditions on Y != original line",
                "tail_policy": "observed_support_only" if self.kind == "empirical" else "analytic_unbounded_count",
                "distribution_sha256": canonical_hash({"kind": self.kind, "parameters": self.parameters})}


def empirical(values, weights):
    total = math.fsum(weights)
    if not values or len(values) != len(weights) or total <= 0:
        raise Unavailable("empty_empirical_distribution")
    masses = defaultdict(float)
    for y, w in zip(values, weights):
        if w < 0 or not math.isfinite(w):
            raise Unavailable("invalid_empirical_weight")
        masses[y] += w/total
    mu = math.fsum(y*w for y, w in masses.items())
    var = math.fsum(w*(y-mu)**2 for y, w in masses.items())
    return Law("empirical", {"masses": sorted(masses.items())}, mu, var)


def pooled_peer_weights(peers):
    values, weights = [], []
    for xs in peers:
        values.extend(xs)
        weights.extend([1/(len(peers)*len(xs))]*len(xs))
    return values, weights


def gamma_prior(peers):
    """Method of moments on equal-player means, correcting Poisson sampling noise.

    Fixed [2,12] equivalent-game bounds stabilize weak peer estimates. Conditional
    EB, not a posterior integrating peer-hyperparameter uncertainty.
    """
    centers = [mean(xs) for xs in peers]
    center = mean(centers)
    if center <= 0:
        raise Unavailable("nonpositive_peer_count_mean")
    between = max(variance(centers)-mean(m/len(xs) for m, xs in zip(centers, peers)), 1e-9)
    beta = max(PARAMETERS["gamma_strength_min"],
               min(PARAMETERS["gamma_strength_max"], center/between))
    return {"alpha0": center*beta, "beta0": beta, "peer_mean": center,
            "between_variance": between, "peer_players": len(peers)}


def fit_laws(own, peers, *, stat, period="full"):
    """Inputs are chronological eligible appearances, validated by source runner."""
    family = "binary" if stat == "anytime touchdown" else canonical_stat("NFL", stat, period).value_kind
    if period != "full":
        raise Unavailable("unsupported_period")
    if len(own) < PARAMETERS["min_player"]:
        raise Unavailable("insufficient_player_appearances")
    own = own[-PARAMETERS["max_history"]:]
    peers = [xs[-PARAMETERS["max_history"]:] for xs in peers if len(xs) >= PARAMETERS["min_peer_games"]]
    for xs in [own]+peers:
        for y in xs:
            y = finite(y, "historical_value")
            if not y.is_integer() or (family != "signed_count" and y < 0) or (family == "binary" and y not in (0, 1)):
                raise Unavailable("statistic_support_violation")
    if family == "nonnegative_continuous":
        raise Unavailable("unsupported_fractional_statistic")
    result, reasons, diagnostics = {}, {}, {"player_n": len(own), "peer_players": len(peers)}
    recent = own[-PARAMETERS["ew_window"]:]
    weights = [2**(-(len(recent)-1-i)/PARAMETERS["half_life"]) for i in range(len(recent))]
    result[MODEL_IDS[1]] = empirical(recent, weights)
    diagnostics["ew_kish_ess"] = sum(weights)**2/sum(w*w for w in weights)
    if len(peers) < PARAMETERS["min_peers"]:
        for model in (MODEL_IDS[0], MODEL_IDS[2], MODEL_IDS[3], MODEL_IDS[4]):
            reasons[model] = "insufficient_role_position_peers"
        return result, reasons, diagnostics
    pv, pw = pooled_peer_weights(peers)
    strength = PARAMETERS["empirical_strength"]
    result[MODEL_IDS[0]] = empirical(own+pv, [1.0]*len(own)+[strength*w for w in pw])
    diagnostics["empirical_prior_weight"] = strength/(strength+len(own))
    if family in ("signed_count", "binary"):
        for model in MODEL_IDS[2:5]:
            reasons[model] = "not_applicable_to_"+family
        return result, reasons, diagnostics
    try:
        prior = gamma_prior(peers)
        alpha, beta = prior["alpha0"]+sum(own), prior["beta0"]+len(own)
        mu = alpha/beta
        result[MODEL_IDS[2]] = Law("poisson", {"rate": mu}, mu, mu)
        result[MODEL_IDS[3]] = Law("gamma_poisson", {"alpha": alpha, "beta": beta}, mu, mu+alpha/beta**2)
        diagnostics["gamma_prior"] = prior
        diagnostics["posterior_rate"] = {"alpha": alpha, "beta": beta, "own_n": len(own), "prior_mean_weight": prior["beta0"]/beta}
    except Unavailable as exc:
        reasons[MODEL_IDS[2]] = reasons[MODEL_IDS[3]] = str(exc)
    if mean(y == 0 for y in own) < PARAMETERS["hurdle_zero_threshold"]:
        reasons[MODEL_IDS[4]] = "not_zero_heavy_under_prespecified_rule"
    else:
        positive = [y for y in own if y > 0]
        peer_positive = [y for y in pv if y > 0]
        if not positive or not peer_positive:
            reasons[MODEL_IDS[4]] = "positive_opportunity_distribution_unidentified"
        else:
            peer_z = math.fsum(w for y, w in zip(pv, pw) if y == 0)
            peer_positive_mean = math.fsum(y*w for y, w in zip(pv, pw) if y > 0)/(1-peer_z)
            k = PARAMETERS["hurdle_strength"]
            z = (sum(y == 0 for y in own)+k*peer_z)/(len(own)+k)
            posmean = (sum(positive)+k*peer_positive_mean)/(len(positive)+k)
            q = 1/posmean
            mu = (1-z)*posmean
            var = (1-z)*(1-q)/q**2 + z*(1-z)*posmean**2
            result[MODEL_IDS[4]] = Law("hurdle_geometric", {"p_zero": z, "positive_success": q}, mu, var)
    return result, reasons, diagnostics


def fixed_logit(model, market):
    eps = PARAMETERS["logit_clip"]
    a, b = [min(1-eps, max(eps, checked_probability(p))) for p in (model, market)]
    z = .5*(math.log(a)-math.log1p(-a))+.5*(math.log(b)-math.log1p(-b))
    return 1/(1+math.exp(-z)) if z >= 0 else math.exp(z)/(1+math.exp(z))


def probability_only(p, *, kind, push=None):
    p = checked_probability(p)
    if push is not None:
        push = checked_probability(push)
    return {"kind": kind, "parameter_version": VERSION, "p_over_given_no_push": p,
            "q_over": p*(1-push) if push is not None else None,
            "q_under": (1-p)*(1-push) if push is not None else None,
            "q_push": push, "mean": None, "variance": None,
            "moment_status": "not_identified_by_threshold_probability",
            "conditioning": "eligible_appearance and Y != original line; push preserved only from original control when supplied",
            "calibrated": False}


def count_crps(law, y, *, tolerance=1e-10, max_terms=100000):
    """E|X-y| - E|X-X'|/2 via lattice CDF; explicit tail error bound.

    For k>=y, remainder sum S(k)^2 <= S(K)*E[(X-K)+] <=
    S(K)*E[X] on nonnegative support. Never silently truncate material tail.
    """
    y = finite(y, "actual")
    if not y.is_integer() or y < 0 or law.kind == "empirical" and any(x < 0 for x, _ in law.parameters["masses"]):
        raise Unavailable("count_crps_requires_nonnegative_integer")
    score = 0.0
    for k in range(max_terms):
        term = law.cdf(k)**2 if k < y else law.sf(k)**2
        score += term
        bound = law.sf(k)*law.mean
        if k >= y and bound <= tolerance:
            return {"crps": score, "tail_error_upper_bound": bound, "terms": k+1}
    raise Unavailable("count_crps_tail_not_converged")
