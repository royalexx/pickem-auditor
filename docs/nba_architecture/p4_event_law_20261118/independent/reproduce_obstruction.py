"""Recompute the frozen source-law counterexample without P4 or SciPy imports."""
from decimal import Decimal, localcontext
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOURCE = (
    ROOT / "docs/nba_architecture/p4_remediation_v2_20261116/"
    "actual_map_4685425_256_seeds/analytic_S_O_components.json"
)
PLAYER = "espn:player:15"
SCENARIO = "synthetic:latest:0"
LAST_TERM = 160


def nb_tail_bounds(r, p, threshold):
    """Bound the full NB tail with an exact rational geometric remainder."""
    if r < 1 or not 0 < p < 1 or not 0 <= threshold <= LAST_TERM:
        raise ValueError("Unsupported reference")
    q = 1 - p
    term = p**r
    tail = Fraction(0)
    for k in range(LAST_TERM + 1):
        if k >= threshold:
            tail += term
        term *= q * Fraction(k + r, k + 1)
    ratio = q * Fraction(LAST_TERM + 1 + r, LAST_TERM + 2)
    if not 0 < ratio < 1:
        raise ValueError("Unbounded geometric remainder")
    return tail, tail + term / (1 - ratio)


def fmt(value):
    with localcontext() as context:
        context.prec = 70
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def reproduce():
    raw = SOURCE.read_bytes()
    rows = json.loads(raw, parse_float=Decimal)[PLAYER]
    bounds = {}
    evidence = {}
    for stat, threshold in (("points", 60), ("threes", 20)):
        row, = (row for row in rows[stat] if row["scenario_id"] == SCENARIO)
        shape = int(row["shape"])
        if shape != row["shape"]:
            raise ValueError("Integral NB shape required")
        low, high = nb_tail_bounds(shape, Fraction(row["success_probability"]), threshold)
        bounds[stat] = low, high
        evidence[stat] = {
            "threshold": threshold,
            "shape": shape,
            "success_probability": str(row["success_probability"]),
            "reference_serialization_tail_bound": str(row["source_serialization_tail_bound"]),
            "tail_lower_approx": fmt(low),
            "tail_upper_approx": fmt(high),
            "geometric_remainder_upper_approx": fmt(high - low),
        }
    gap = bounds["threes"][0] - bounds["points"][1]
    if gap <= 0:
        raise ValueError("Counterexample missing")
    return {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": sha256(raw).hexdigest(),
        "player_id": PLAYER,
        "scenario_id": SCENARIO,
        "conditioning": "Fixed original G/O scenario in the native synthetic O2 sample",
        "last_term_summed": LAST_TERM,
        "statistics": evidence,
        "necessary_marginal_gap_lower_approx": fmt(gap),
        "minimum_sum_marginal_TV_lower_approx": fmt(gap),
        "same_lower_bound_on_sum_of_marginal_KS_approx": fmt(gap),
    }


if __name__ == "__main__":
    print(json.dumps(reproduce(), indent=2, sort_keys=True))
