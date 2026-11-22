"""NBA P3 mathematical controls: complete count laws, never model votes.

Research-only code. Analytic Poisson/NB2 are controls; mixtures and scenario
histograms are full distributions, not empirically calibrated claims.
"""
from __future__ import annotations
import hashlib
import json
import math
from collections import Counter

STATS = ("points", "rebounds", "assists", "threes")
COMBOS = {"pr": ("points", "rebounds"), "pa": ("points", "assists"),
          "ra": ("rebounds", "assists"),
          "pra": ("points", "rebounds", "assists")}
TAIL_TOL = 1e-11
MAX_SUPPORT = 8192


class ForecastBlocked(ValueError):
    def __init__(self, status, detail):
        self.status, self.detail = status, detail
        super().__init__(status + ": " + detail)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def number(value, name, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ForecastBlocked("NUMERICAL_FAILURE", name + "_invalid")
    return float(value)


def pmf(mean, shape=None, *, tolerance=TAIL_TOL):
    """Poisson or NB2 with shape>0; exact recursion up to bounded missing tail.

    A computed tail is bounded by the remainder of a convergent recurrence:
    once pmf terms decline geometrically, the remaining tail is <= first
    omitted term / (1 - ratio upper bound). We conservatively require both
    this bound and the normalization residual below tolerance.
    """
    mu = number(mean, "mean")
    if mu > 1000:
        raise ForecastBlocked("NUMERICAL_FAILURE", "count_mean_too_high")
    if shape is None:
        p = math.exp(-mu)
        def ratio(k):
            return mu / k
    else:
        s = number(shape, "shape", 1e-12)
        p = math.exp(s * math.log(s / (s + mu))) if mu else 1.0
        q = mu / (s + mu)
        def ratio(k):
            return q * (s + k - 1) / k
    if p == 0:
        raise ForecastBlocked("NUMERICAL_FAILURE", "underflow_zero_mass")
    masses = [p]
    for k in range(1, MAX_SUPPORT + 1):
        p *= ratio(k)
        masses.append(p)
        total = math.fsum(masses)
        if not math.isfinite(total) or total > 1 + 1e-10:
            raise ForecastBlocked("NUMERICAL_FAILURE", "pmf_over_normalized")
        next_ratio = ratio(k + 1)
        if next_ratio < 1 and total >= 1 - tolerance / 2:
            # NB2 ratio is decreasing only when s>=1; for s<1 it increases
            # toward q, which supplies a conservative geometric upper bound.
            upper = max(next_ratio, (mu / (mu + shape)) if shape is not None and mu else 0.)
            bound = p * upper / (1 - upper) if upper < 1 else math.inf
            if bound < tolerance / 2:
                lost = max(0.0, 1.0 - total)
                scale = 1.0 / total
                return {k: float(v * scale) for k, v in enumerate(masses) if v > 0}, lost
    raise ForecastBlocked("NUMERICAL_FAILURE", "count_support_limit")


def discrete(weights, *, truncation_bound=0.0):
    if not isinstance(weights, dict) or not weights:
        raise ForecastBlocked("NUMERICAL_FAILURE", "empty_mass")
    rows = {}
    for k, v in weights.items():
        if type(k) is not int or k < 0:
            raise ForecastBlocked("NUMERICAL_FAILURE", "count_support")
        rows[k] = number(v, "mass")
    total = math.fsum(rows.values())
    if not total or abs(1 - total) > 1e-9:
        raise ForecastBlocked("NUMERICAL_FAILURE", "unnormalized_distribution")
    rows = {k: float(v / total) for k, v in sorted(rows.items()) if v > 0}
    tail = number(truncation_bound, "truncation_bound")
    return {"kind": "discrete", "masses": [[k, p] for k, p in rows.items()]}, tail


def mixture(components):
    """components: (mixture weight, mean, shape or None)."""
    sums = {}
    bound = 0.
    weights = 0.
    for weight, mean, shape in components:
        w = number(weight, "mix_weight")
        if not w:
            continue
        sub, rem = pmf(mean, shape)
        for k, p in sub.items():
            sums[k] = sums.get(k, 0.0) + w * p
        weights += w
        bound += w * rem
    if abs(weights - 1.0) > 1e-9:
        raise ForecastBlocked("NUMERICAL_FAILURE", "mixture_weights_not_one")
    result, _ = discrete(sums, truncation_bound=bound)
    return result, bound


def empirical(counts):
    if not counts:
        raise ForecastBlocked("NUMERICAL_FAILURE", "no_scenarios")
    if any(type(x) is not int or x < 0 for x in counts):
        raise ForecastBlocked("NUMERICAL_FAILURE", "invalid_scenario_stat")
    size = len(counts)
    return discrete({k: v / size for k, v in Counter(counts).items()})[0]


def mass_dictionary(distribution):
    kind = distribution["kind"]
    if kind in ("discrete", "scenario_pmf"):
        return dict(distribution["masses"])
    if kind == "poisson":
        return pmf(distribution["parameters"]["rate"])[0]
    if kind == "nb2":
        p = distribution["parameters"]
        return pmf(p["mean"], p["shape"])[0]
    if kind == "gamma_poisson":
        p = distribution["parameters"]
        return pmf(p["shape"] / p["rate"], p["shape"])[0]
    raise ForecastBlocked("MODEL_NOT_READY", "unsupported_full_distribution")


def statistics(distribution):
    masses = mass_dictionary(distribution)
    mean = math.fsum(k * p for k, p in masses.items())
    var = math.fsum((k - mean) ** 2 * p for k, p in masses.items())
    ordered = sorted(masses.items())
    quantiles = {}
    for name, level in (("p05", .05), ("p25", .25), ("p50", .5),
                        ("p75", .75), ("p95", .95), ("p99", .99)):
        accum = 0.
        for k, p in ordered:
            accum += p
            if accum >= level - 1e-14:
                quantiles[name] = k
                break
        else:
            quantiles[name] = ordered[-1][0]
    return {"mean": mean, "variance": var, "quantiles": quantiles,
            "p_zero": masses.get(0, 0.0), "support_max": ordered[-1][0],
            "mass_sum": math.fsum(masses.values())}


def threshold(distribution, line):
    line = number(line, "line")
    masses = mass_dictionary(distribution)
    p_over = math.fsum(p for k, p in masses.items() if k > line)
    p_push = masses.get(int(line), 0.) if line.is_integer() else 0.
    p_under = math.fsum(p for k, p in masses.items() if k < line)
    if abs(p_over + p_under + p_push - 1.) > 1e-9:
        raise ForecastBlocked("NUMERICAL_FAILURE", "threshold_complementarity")
    return {"over": p_over, "under": p_under, "push": p_push,
            "conditional_over_nonpush": p_over / (1. - p_push) if p_push < 1 else None}


def s_control(rate_per_minute, projected_minutes, *, family="S0", shape=None):
    mu = number(rate_per_minute, "rate_per_minute") * number(projected_minutes, "minutes")
    if family == "S0":
        return {"kind": "poisson", "parameters": {"rate": mu}}
    if family in ("S1", "S2"):
        return {"kind": "nb2", "parameters": {"mean": mu,
                                              "shape": number(shape, "shape", 1e-12)}}
    raise ForecastBlocked("MODEL_NOT_READY", "unadmitted_s_variant")


def opportunity_mixture(rate, minute_atoms, p_play, *, family="S0", shape=None):
    """Unconditional mixture with explicit PLAYED vs DNP probabilities.

    DNP mass is a predictive statistic mixture, NOT an official scored zero.
    Consumers must separately honor bookmaker's DNP/VOID settlement terms.
    """
    q = number(p_play, "participation_probability")
    if q > 1:
        raise ForecastBlocked("PARTICIPATION_UNRESOLVED", "participation_probability")
    atoms = []
    mass_sum = 0.
    for atom in minute_atoms:
        if set(atom) != {"minutes", "probability"}:
            raise ForecastBlocked("MODEL_NOT_READY", "minute_atom_schema")
        m = number(atom["minutes"], "minutes")
        p = number(atom["probability"], "minute_probability")
        if m > 53:  # 1OT-only bound; longer games require explicit game context.
            raise ForecastBlocked("MODEL_NOT_READY", "minute_ot_support_unspecified")
        atoms.append((p * q, m, None if family == "S0" else shape))
        mass_sum += p
    if not atoms or abs(mass_sum - 1) > 1e-9:
        raise ForecastBlocked("MODEL_NOT_READY", "conditional_minute_mass")
    components = [(1 - q, 0., None)]
    components.extend((w, rate * minutes, sh) for w, minutes, sh in atoms)
    return mixture(components)


def combo_counts(draws, statistic):
    if statistic in STATS:
        return [x[statistic] for x in draws]
    if statistic not in COMBOS:
        raise ForecastBlocked("MODEL_NOT_READY", "unsupported_statistic")
    return [sum(x[k] for k in COMBOS[statistic]) for x in draws]
