"""Player-prop math for the pickem-auditor skill. Standard library only.

The helper does not know Underdog lines, payouts, or entries. It does these jobs:

  devig       two-way American odds -> hold, q_mult, q_market
  consensus   approved books on one line -> one conservative q_market
  project     historical rates -> historical mean and P(win), P(push)
  grade       model q_win vs the market, on one probability scale
  rank        map a grade plus the Unicorn checklist to a final label
  pipeline    project, optional consensus, grade, and rank on one candidate
  pipeline --batch --stdin
              one JSON object per line in, one JSON result per line out
  scan        prep JSONL -> ranked shortlist. Placeholders: mechanisms=2, soft_flags=0
  log         append researched props
  log --batch --stdin
              one snapshot JSON object per line, one process
              schema v2; rows that omit run_id share one UUID for that process

`project` never reads a market probability. Do not fit the mean to the market.
Tier floors use unconditional P(win). A push is not a win. On a whole-number
line the de-vigged price is conditional on no push; `grade` converts it with
the model's push probability before comparing. `pipeline` passes those floats
through in process. Do not retype a rounded percent.

All constants remain uncalibrated until scripts/report.py shows at least 300
settled graded props. Tier floors, clamps, weights, the old-role prior, the
prior-season cap, and the quadrature below are provisional. Do not retune them
from one slate or from a bin with fewer than 30 settled rows.

`q_win` is the win probability at the shrunk mean, so that mean is treated as
exact. `q_win_robust` integrates the same win probability over uncertainty in
the true mean. `--prior-mean` and `--prior-n` optionally blend a same-role
prior season into the baseline before the recent blend. They default off.
`--tier-basis q_win_robust` grades tiers, the gap, and the Unicorn check on
the robust probability. The default basis is `q_win_robust`. Both probabilities are
always printed.

Run from the skill directory (the folder that contains SKILL.md):

  python3 scripts/pickem_math.py devig --target -125 --other -105
  python3 scripts/pickem_math.py consensus --side-name "Over 3.5 SOG" --retrieved-minutes-ago 5 --book Pinnacle:3.5:-130:+110:over --book FanDuel:3.5:-135:+105:over
  python3 scripts/pickem_math.py project --dist poisson --side over --line 2.5 --baseline-mean 3.2 --baseline-n 30 --recent-mean 3.8 --recent-n 10 --season-n 40 --opponent-factor 1.08
  python3 scripts/pickem_math.py grade --q-model 0.575 --q-market 0.55 --q-push 0 --soft-flags 0 --current-role-n 30
  python3 scripts/pickem_math.py rank --q-model 0.61 --q-market 0.60 --q-push 0 --soft-flags 0 --current-role-n 20 --mechanisms 1 --hard-veto no --data-veto no --market-valid yes --research-checklist yes
  python3 scripts/pickem_math.py pipeline --dist poisson --side over --line 2.5 --baseline-mean 3.2 --baseline-n 30 --soft-flags 0 --mechanisms 1 --hard-veto no --data-veto no --research-checklist no --q-market 0.57 --retrieved-minutes-ago 5 --json
"""

import argparse
import copy
import json
import math
import os
import re
import sys
import uuid
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

HOLD_REJECT = 0.0825
HOLD_FREE = 0.045
HOLD_SLOPE = 0.15
DISAGREE = 0.03
GAP_FLAG = 0.03
GAP_WATCH_CAP = 0.08
GAP_EPSILON = 1e-9  # float noise only; tier floors are not rounded
TIER_1 = 0.58
TIER_2 = 0.57
TIER_3 = 0.56
WATCH_FLOOR = 0.52
# Probability-point threshold (provisional until walk-forward calibration).
# NEVER compare a probability delta against an SE expressed in yards/points/etc.
CROSSCHECK_TOLERANCE_FLOOR = 0.08
CROSSCHECK_TOLERANCE_SCALE = 1.5  # reserved for a validated *probability* SE
# Stage D prefilter. The grade gap's float cushion applies to these cuts.
SCAN_MIN_Q_WIN = TIER_3
SCAN_MAX_ABS_GAP = 0.06
SCAN_MIN_MARKET = 0.54
SCAN_BOTH_SIDES_FLOOR = WATCH_FLOOR
SCAN_CAP = 40
SCAN_OPTIMISTIC_MECHANISMS = 2
SCAN_OPTIMISTIC_SOFT_FLAGS = 0
OLD_ROLE_PRIOR = 8.0
PRIOR_N_CAP = 20.0
QUADRATURE_POINTS = 41
# Physicist Gauss-Hermite, weight exp(-x^2). The weights sum to sqrt(pi).
GAUSS_HERMITE_20 = (
    (-5.387480890011233, 2.2293936455341447e-13),
    (-4.603682449550744, 4.3993409922731747e-10),
    (-3.944764040115625, 1.0860693707692782e-07),
    (-3.3478545673832163, 7.80255647853206e-06),
    (-2.7888060584281305, 0.00022833863601635365),
    (-2.2549740020892757, 0.0032437733422378567),
    (-1.7385377121165861, 0.024810520887463643),
    (-1.234076215395323, 0.1090172060200233),
    (-0.7374737285453944, 0.28667550536283415),
    (-0.24534070830090124, 0.4622436696006101),
    (0.24534070830090124, 0.4622436696006101),
    (0.7374737285453944, 0.28667550536283415),
    (1.234076215395323, 0.1090172060200233),
    (1.7385377121165861, 0.024810520887463643),
    (2.2549740020892757, 0.0032437733422378567),
    (2.7888060584281305, 0.00022833863601635365),
    (3.3478545673832163, 7.80255647853206e-06),
    (3.944764040115625, 1.0860693707692782e-07),
    (4.603682449550744, 4.3993409922731747e-10),
    (5.387480890011233, 2.2293936455341447e-13),
)
CONTEXT_WEIGHT = 8.0
# 0, 1, or 2 cited channels. Role and usage are not a channel.
FUNNEL_CONTEXT_WEIGHT = (CONTEXT_WEIGHT, 16.0, 24.0)
VAR_RATIO_CAP = 3.0
VAR_RATIO_POISSON = 1.10
WORKLOAD_CLAMP = (0.80, 1.25)
WORKLOAD_CLAMP_ROLE = (0.50, 1.60)
RATE_CLAMP = (0.75, 1.35)
RATE_CLAMP_ROLE = (0.50, 1.80)
OPPONENT_CLAMP = (0.85, 1.15)
PACE_CLAMP = (0.90, 1.10)
NORMAL_NEGATIVE_MASS = 0.02
SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_PATH = SKILL_ROOT / "data" / "prop_snapshots.jsonl"
DEFAULT_BLEND_WEIGHTS_PATH = SKILL_ROOT / "config" / "blend_weights.json"
SNAPSHOT_RANKS = {"Tier 1", "Tier 2", "Tier 3", "Watchlist", "Reject", "Unranked"}
SNAPSHOT_REQUIRED = (
    "run_at", "game_date", "sport", "matchup", "player", "stat", "side",
    "reference_line", "final_rank", "status", "researched",
)
SNAPSHOT_SCHEMA_VERSION = 2
RUN_TYPE_SHADOW = "shadow"
SNAPSHOT_STATUS = ("GRADED", "UNRANKED")
SNAPSHOT_BOOK_KEYS = ("book", "line", "over", "under", "retrieved_at")
_BOOK_NAME = r"[A-Za-z][A-Za-z0-9]*(?:[ ][A-Za-z0-9]+)?"
_AMERICAN_ODDS = r"[+-]?\d+(?:\.\d+)?"
_BOOK_PAIR = re.compile(
    rf"({_BOOK_NAME})\s+({_AMERICAN_ODDS})\s*/\s*({_AMERICAN_ODDS})",
    re.IGNORECASE,
)

SHARP_BOOKS = {"pinnacle", "circa"}
RETAIL_BOOKS = {"fanduel", "draftkings", "bet365", "caesars", "betmgm"}
APPROVED_BOOKS = SHARP_BOOKS | RETAIL_BOOKS
MARKET_CHECKS = (
    "line_match",
    "side_match",
    "timestamp_fresh",
    "hold_ok",
    "approved_books",
)
BOOK_SIDES = ("over", "under")

# Stage G numeric cuts. Float noise within GAP_EPSILON stays on the cutoff.
NBA_MINUTES_VETO = 18.0
NBA_MINUTES_THIN_MAX = 27.9
NHL_ICE_VETO = 12.0
NHL_ICE_THIN_MAX = 17.0 + 29.0 / 60.0  # 17:29
NFL_SNAP_VETO = 0.40
NFL_SNAP_THIN_MAX = 0.60
NFL_ROUTE_VETO = 0.50
NFL_ROUTE_THIN_MAX = 0.70
NFL_TACKLE_VETO = 0.50
NFL_TACKLE_THIN_MAX = 0.80
NBA_SPREAD_VETO = 9.5
NBA_SPREAD_SCRIPT = 8.0
NFL_DOG_VETO = 6.5
NFL_DOG_SCRIPT = 4.5
WIND_VETO_MPH = 18.0
WIND_RISK_MPH = 15.0
GUST_RISK_MPH = 25.0
PRECIP_CUT = 60.0
PRECIP_INTENSITIES = ("none", "light", "moderate", "heavy")
HEAVY_INTENSITIES = ("moderate", "heavy")
RAIN_INTENSITIES = ("light", "moderate", "heavy")
CONTEXT_ROLES = ("rb", "wr", "te", "qb", "g", "d", "f", "c")
HARD_NBA_MINUTES = "NBA_MINUTES_UNDER_18"
HARD_NHL_ICE = "NHL_ICE_UNDER_12"
HARD_NFL_SNAPS = "NFL_SNAPS_UNDER_40"
HARD_NFL_ROUTES = "WR_TE_ROUTES_UNDER_50"
HARD_TACKLES = "TACKLES_SNAPS_UNDER_50"
HARD_QB = "NOT_EXPECTED_STARTING_QB"
HARD_SAVES = "SAVES_GOALIE_UNCONFIRMED"
HARD_NBA_SPREAD = "NBA_STARTER_SPREAD"
HARD_NFL_DOG = "NFL_RB_UNDERDOG_RUSH"
HARD_WIND = "SUSTAINED_WIND"
HARD_SNOW = "SNOW"
HARD_NHL_RAIN = "OUTDOOR_NHL_RAIN"
DATA_WEATHER = "WEATHER_NOT_CHECKED"
DERIVED_SOFT_FLAGS = (
    "THIN_WORKLOAD",
    "SCRIPT_RISK",
    "WEATHER_RISK",
    "REST_SPOT",
    "UNCONFIRMED_GOALIE",
)
NBA_STATS = frozenset({"points", "rebounds", "assists", "threes", "pra", "pr", "pa", "ra"})
NHL_SKATER_STATS = frozenset({"shots on goal", "blocked shots"})
NHL_SAVE_STATS = frozenset({"saves"})
NHL_STATS = NHL_SKATER_STATS | NHL_SAVE_STATS
NFL_WEATHER_STATS = frozenset({
    "passing yards", "receiving yards", "receptions", "completions", "pass attempts",
})
NFL_PASS_STATS = frozenset({"passing yards", "completions", "pass attempts"})
NFL_RUSH_STATS = frozenset({"rushing yards", "rush attempts"})
NFL_TACKLE_STATS = frozenset({"tackles", "tackles + assists"})
NFL_STATS = NFL_WEATHER_STATS | NFL_RUSH_STATS | NFL_TACKLE_STATS
COVERED_STATS = NBA_STATS | NHL_STATS | NFL_STATS
STAT_ALIASES = {
    "point": "points",
    "pts": "points",
    "rebound": "rebounds",
    "reb": "rebounds",
    "assist": "assists",
    "ast": "assists",
    "three": "threes",
    "3pm": "threes",
    "3pt": "threes",
    "threes made": "threes",
    "shot": "shots on goal",
    "shots": "shots on goal",
    "sog": "shots on goal",
    "blocked shot": "blocked shots",
    "blocks": "blocked shots",
    "save": "saves",
    "goalie saves": "saves",
    "reception": "receptions",
    "recs": "receptions",
    "receiving yard": "receiving yards",
    "rec yards": "receiving yards",
    "rushing yard": "rushing yards",
    "rush yards": "rushing yards",
    "passing yard": "passing yards",
    "pass yards": "passing yards",
    "pass attempt": "pass attempts",
    "passing attempts": "pass attempts",
    "completion": "completions",
    "rush attempt": "rush attempts",
    "carries": "rush attempts",
    "tackle": "tackles",
    "tackles assists": "tackles + assists",
    "tackles and assists": "tackles + assists",
}
CONTEXT_FIELDS = (
    "stat",
    "minutes_tonight",
    "ice_time_tonight",
    "snap_pct_tonight",
    "route_pct_tonight",
    "spread",
    "team_is_underdog",
    "sustained_wind_mph",
    "gust_mph",
    "precip_prob",
    "precip_intensity",
    "snow",
    "outdoor",
    "is_starter",
    "back_to_back",
    "third_in_four",
    "goalie_confirmed",
    "expected_starting_qb",
    "role",
)

RANK_ORDER = {
    "NUMERIC_TIER_1": 4,
    "NUMERIC_TIER_2": 3,
    "NUMERIC_TIER_3": 2,
    "WATCHLIST": 1,
    "REJECT": 0,
}


class PickemError(ValueError):
    """Invalid input. Callers must not grade a prop when this is raised."""


def canon_book(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PickemError(f"{name} must be a finite number")
    return float(value)


def _clip01(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise PickemError(f"{label} is not finite")
    return min(1.0, max(0.0, value))


def _exceeds(spread: float, limit: float) -> bool:
    """True when spread is strictly above limit. Float noise at the limit does not count."""
    return spread > limit + GAP_EPSILON


def _at_least(value: float, limit: float) -> bool:
    """True when value reaches limit. Float noise just under the limit still counts."""
    return not _exceeds(limit, value)


def _below(value: float, limit: float) -> bool:
    """True when value is under limit. Float noise at the limit does not count."""
    return _exceeds(limit, value)


def _at_most(value: float, limit: float) -> bool:
    """True when value is at or under limit. Float noise just over the limit still counts."""
    return not _exceeds(value, limit)


def _negbin_rejected(var_ratio: float) -> bool:
    """Variance / mean at or under 1.10 is a poisson prop, not negative binomial."""
    return var_ratio <= VAR_RATIO_POISSON + GAP_EPSILON


def _funnel_channels(value) -> int:
    """Pace and opponent environment only. 0, 1, or 2. Not a count of checklist items."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PickemError("--funnel-channels must be 0, 1, or 2")
    channels = int(value)
    if channels != value or channels not in (0, 1, 2):
        raise PickemError("--funnel-channels must be 0, 1, or 2")
    return channels


def implied(american: float) -> float:
    odds = _finite("odds", american)
    if abs(odds) < 100:
        raise PickemError("American odds must be <= -100 or >= 100")
    if odds < 0:
        return (-odds) / ((-odds) + 100)
    return 100 / (odds + 100)


def devig(target: float, other: float) -> dict:
    p_t, p_o = implied(target), implied(other)
    total = p_t + p_o
    if total <= 0 or not math.isfinite(total):
        raise PickemError("implied-probability sum is invalid")
    hold = total - 1
    q_mult = _clip01(p_t / total, "q_mult")
    q_market = _clip01(q_mult - HOLD_SLOPE * max(0.0, hold - HOLD_FREE), "q_market")
    target_odds = _finite("odds", target)
    return {
        "p_target": p_t,
        "p_other": p_o,
        "hold": hold,
        "q_mult": q_mult,
        "q_market": q_market,
        "reject_hold": hold > HOLD_REJECT,
        "target_odds": target_odds,
        "target_plus_money": target_odds > 0 or q_mult < 0.5,
    }


def _anchor_plus_money(rows: list[dict], pre_hold: float | None = None) -> bool:
    """One PLUS-MONEY rule for the sharp path and the agreeing-retail path.

    Print when an anchor book posts the chosen side at American plus-money, or
    the pre-hold anchor probability is below 50%. Exactly 50% does not print.
    Rank does not read this note. On a sharp market, and when retail books
    disagree, the anchor books are the ones that set q_market and each book's
    own q_mult is the pre-hold probability. When retail books agree, pre_hold
    is the mean of their q_mult and every book in that mean is an anchor book.
    """
    if any(row["target_odds"] > 0 for row in rows):
        return True
    if pre_hold is None:
        return any(row["q_mult"] < 0.5 for row in rows)
    return pre_hold < 0.5


def consensus(books: list[tuple[str, float, float, float]], retrieved_minutes_ago: float | None = None) -> dict:
    """books are (name, line, target_odds, other_odds). Every line must match."""
    if len(books) < 1:
        raise PickemError("consensus needs at least one book")
    seen = set()
    lines = []
    rows, used = [], []
    for name, line, target, other in books:
        key = canon_book(name)
        if key not in APPROVED_BOOKS:
            raise PickemError(
                f"unapproved book '{name}'. Use only Pinnacle, Circa, FanDuel, "
                "DraftKings, Bet365, Caesars, BetMGM"
            )
        if key in seen:
            raise PickemError(f"duplicate book '{name}'")
        seen.add(key)
        line = _finite("line", line)
        lines.append(line)
        row = devig(target, other)
        row["book"] = name
        row["key"] = key
        row["line"] = line
        rows.append(row)
        if not row["reject_hold"]:
            used.append(row)
    if max(lines) - min(lines) > 1e-9:
        raise PickemError("books are not on the same line; grade each line separately")
    sharp = [row for row in used if row["key"] in SHARP_BOOKS]
    retail = [row for row in used if row["key"] in RETAIL_BOOKS]
    out = {
        "rows": rows,
        "valid": bool(sharp) or len(retail) >= 2,
        "flags": [],
        "line": lines[0],
    }
    if not out["valid"]:
        out["flags"].append(
            "INVALID MARKET: need Pinnacle/Circa, or 2+ approved retail books, with hold <= 8.25%"
        )
        _stamp_market(out, retrieved_minutes_ago)
        return out
    # Sharp is the anchor. A longer or higher-hold retail price must not pull it
    # down, and it must not add DISAGREE just for sitting below that anchor.
    # DISAGREE on a sharp market means the sharp books disagree with each other,
    # or a retail book is shorter than the anchor by more than 3 points.
    if sharp:
        base = min(row["q_market"] for row in sharp)
        rule = "sharp anchor (lowest sharp value; retail does not undercut it)"
        sharp_spread = max(row["q_market"] for row in sharp) - base
        retail_above = any(_exceeds(row["q_market"] - base, DISAGREE) for row in retail)
        if _exceeds(sharp_spread, DISAGREE) or retail_above:
            rule = "sharp anchor (disagreement above the anchor; lowest sharp value kept)"
            out["flags"].append(
                "DISAGREE: sharp books differ by more than 3 points, or a retail book is "
                "more than 3 points above the sharp anchor"
            )
        plus = _anchor_plus_money(
            [row for row in sharp if abs(row["q_market"] - base) <= 1e-9]
        )
    else:
        quotes = [row["q_market"] for row in retail]
        base = sum(quotes) / len(quotes)
        rule = "mean of retail books"
        if _exceeds(max(quotes) - min(quotes), DISAGREE):
            base = min(quotes)
            rule = "lowest value (books disagree by more than 3 points)"
            out["flags"].append("DISAGREE: books differ by more than 3 points; conservative value used")
            plus = _anchor_plus_money(
                [row for row in retail if abs(row["q_market"] - base) <= 1e-9]
            )
        else:
            mean_mult = sum(row["q_mult"] for row in retail) / len(retail)
            plus = _anchor_plus_money(retail, mean_mult)
        if len(retail) == 2:
            out["flags"].append("RETAIL_ONLY_TWO_BOOKS: exactly two retail books and no sharp book")
    if plus:
        out["flags"].append(
            "PLUS-MONEY: chosen side is American plus-money or the pre-hold anchor "
            "probability is below 50%; audit note, not a soft flag. Rank does not use it"
        )
    out["q_market"] = _clip01(base, "consensus q_market")
    out["rule"] = rule
    _stamp_market(out, retrieved_minutes_ago)
    return out


def _retrieval_age(retrieved_minutes_ago) -> float:
    age = _finite("retrieved_minutes_ago", retrieved_minutes_ago)
    if age < 0:
        raise PickemError("retrieved_minutes_ago must be >= 0")
    return age


def _timestamp_fresh(age: float | None) -> bool:
    """An age of exactly 30 minutes is still fresh. Older than that is stale."""
    return age is not None and age <= 30


def _stamp_market(out: dict, retrieved_minutes_ago: float | None) -> None:
    """A price consensus is not a usable market until its age is known and fresh."""
    if not out.get("valid"):
        out["timestamp_checked"] = retrieved_minutes_ago is not None
        out["market_valid"] = False
        if retrieved_minutes_ago is not None:
            out["retrieved_minutes_ago"] = _retrieval_age(retrieved_minutes_ago)
        return
    if retrieved_minutes_ago is None:
        out["timestamp_checked"] = False
        out["market_valid"] = False
        out["flags"].append("TIMESTAMP_MISSING")
        return
    age = _retrieval_age(retrieved_minutes_ago)
    out["timestamp_checked"] = True
    out["retrieved_minutes_ago"] = age
    if not _timestamp_fresh(age):
        out["market_valid"] = False
        out["flags"].append("STALE")
        return
    out["market_valid"] = True


def _pois_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(k * math.log(lam) - lam - math.lgamma(k + 1))


def _nb_pmf(k: int, mu: float, r: float) -> float:
    """Negative binomial with mean mu and variance r * mu (r > 1)."""
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    n = mu / (r - 1)
    p = 1 / r
    return math.exp(
        math.lgamma(k + n) - math.lgamma(n) - math.lgamma(k + 1)
        + n * math.log(p) + k * math.log(1 - p)
    )


def side_probs(dist: str, mu: float, line: float, side: str, sd=None, r=None):
    """Return (q_win, q_push). q_win is the strict win, not a push."""
    mu = _finite("mean", mu)
    line = _finite("line", line)
    if mu <= 0:
        raise PickemError("mean must be positive")
    if line < 0:
        raise PickemError("line must be >= 0")
    if side not in ("over", "under"):
        raise PickemError("side must be over or under")
    whole = abs(line - round(line)) < 1e-9
    over_threshold = int(math.floor(line)) + 1

    if dist == "normal":
        sd = _finite("sd", sd)
        if sd <= 0:
            raise PickemError("sd must be positive")
        nd = NormalDist(mu, sd)
        p_ge = lambda t: 1 - nd.cdf(t - 0.5)
        p_eq = lambda t: nd.cdf(t + 0.5) - nd.cdf(t - 0.5)
    elif dist == "poisson":
        pmf = lambda k: _pois_pmf(k, mu)

        def p_ge(t, pmf=pmf):
            return 1 - sum(pmf(k) for k in range(0, max(t, 0)))

        p_eq = lambda t: pmf(t) if t >= 0 else 0.0
    elif dist == "negbin":
        r = _finite("var_ratio", r)
        if _negbin_rejected(r):
            raise PickemError("var_ratio is 1.10 or less; use poisson instead of negbin")
        pmf = lambda k: _nb_pmf(k, mu, r)

        def p_ge(t, pmf=pmf):
            return 1 - sum(pmf(k) for k in range(0, max(t, 0)))

        p_eq = lambda t: pmf(t) if t >= 0 else 0.0
    else:
        raise PickemError("dist must be poisson, negbin, or normal")

    push = p_eq(int(round(line))) if whole else 0.0
    over_win = p_ge(over_threshold)
    if side == "over":
        win, push_p = over_win, push
    else:
        win, push_p = 1 - over_win - push, push
    return _clip01(win, "q_win"), _clip01(push_p, "q_push")


def _normal_tails(mu: float, sd: float, line: float) -> tuple[float, float, float]:
    """Over, under, and push for a normal, including a non-positive posterior mean."""
    sd = _finite("sd", sd)
    if sd <= 0:
        raise PickemError("sd must be positive")
    whole = abs(line - round(line)) < 1e-9
    over_threshold = int(math.floor(line)) + 1
    nd = NormalDist(mu, sd)
    over = 1 - nd.cdf(over_threshold - 0.5)
    push = 0.0
    if whole:
        center = int(round(line))
        push = nd.cdf(center + 0.5) - nd.cdf(center - 0.5)
    under = 1 - over - push
    return over, under, push


def _count_mass_at_zero(line: float) -> tuple[float, float, float]:
    """Poisson or negbin mass at zero: a push only on the whole line 0."""
    whole = abs(line - round(line)) < 1e-9
    if whole and int(round(line)) == 0:
        return 0.0, 0.0, 1.0
    return 0.0, 1.0, 0.0


def _node_probs(dist: str, mu: float, line: float, sd, var_ratio) -> tuple[float, float, float]:
    """Over, under, and push at one candidate mean. Same formulas as side_probs."""
    if not math.isfinite(mu):
        raise PickemError("posterior mean is not finite")
    if dist == "normal" and mu <= 0:
        return _normal_tails(mu, sd, line)
    if mu <= 0:
        return _count_mass_at_zero(line)
    over, push = side_probs(dist, mu, line, "over", sd, var_ratio)
    under, _under_push = side_probs(dist, mu, line, "under", sd, var_ratio)
    return over, under, push


def _gammainc_reg(shape: float, x: float) -> float:
    """Lower regularized incomplete gamma P(shape, x)."""
    if x <= 0:
        return 0.0
    if x < shape + 1.0:
        term = 1.0 / shape
        total = term
        for k in range(1, 5000):
            term *= x / (shape + k)
            total += term
            if abs(term) <= 1e-16 * abs(total):
                break
        logp = -x + shape * math.log(x) - math.lgamma(shape) + math.log(total)
        if logp < -745:
            return 0.0
        return min(1.0, math.exp(logp))
    tiny = 1e-30
    b = x + 1.0 - shape
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 5000):
        an = -i * (i - shape)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            break
    if h <= 0 or not math.isfinite(h):
        return 0.0
    logq = -x + shape * math.log(x) - math.lgamma(shape) + math.log(h)
    q = 0.0 if logq < -745 else math.exp(logq)
    return max(0.0, min(1.0, 1.0 - q))


def _gamma_ppf(p: float, shape: float, rate: float) -> float:
    """Quantile of a Gamma(shape, rate) posterior. Mean is shape / rate."""
    if not 0.0 < p < 1.0 or shape <= 0 or rate <= 0:
        raise PickemError("gamma posterior quantile is undefined")
    if shape < 1:
        # Very small shapes have representable quantiles hundreds of orders
        # below 1e-12. A linear-space floor/bisection silently loses them.
        lo=math.log(math.nextafter(0.0,1.0))
        hi=math.log(max(1.0,shape))
        if _gammainc_reg(shape,math.exp(lo))>=p:return 0.0
        while _gammainc_reg(shape,math.exp(hi))<p:hi+=math.log(2)
        for _ in range(160):
            mid=(lo+hi)/2
            if _gammainc_reg(shape,math.exp(mid))<p:lo=mid
            else:hi=mid
        return math.exp((lo+hi)/2)/rate
    if shape >= 1:
        z = NormalDist().inv_cdf(min(max(p, 1e-12), 1 - 1e-12))
        h = 2.0 / (9.0 * shape)
        w = 1.0 - h + z * math.sqrt(h)
        y = shape * (w ** 3) if w > 0 else shape * 1e-3
    else:
        y = math.exp(math.log(max(p, 1e-12) * shape) / shape)
    y = max(float(y), 1e-12)
    lo = 0.0
    hi = None
    for _ in range(80):
        cdf = _gammainc_reg(shape, y)
        logdens = -y + (shape - 1.0) * math.log(y) - math.lgamma(shape)
        dens = math.exp(logdens) if logdens > -700 else 0.0
        err = cdf - p
        if abs(err) < 1e-12:
            break
        if dens > 0 and abs(err) / dens < y * 2:
            y_new = y - err / dens
        else:
            y_new = y * (1.2 if err < 0 else 0.8)
        if y_new <= 0:
            y_new = y * 0.5
        if err > 0:
            hi = y
        else:
            lo = y
        if hi is not None and not (lo < y_new < hi):
            y_new = 0.5 * ((lo if lo else y * 0.5) + hi)
        y = y_new
    if abs(_gammainc_reg(shape, y) - p) > 1e-8:
        lo = min(y, shape) * 0.25
        hi = max(y, shape, 1e-6) * 2.0
        for _ in range(80):
            if lo <= 0 or _gammainc_reg(shape, lo) <= p:
                break
            lo *= 0.5
        for _ in range(80):
            if _gammainc_reg(shape, hi) >= p:
                break
            hi *= 2.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            if _gammainc_reg(shape, mid) < p:
                lo = mid
            else:
                hi = mid
        y = 0.5 * (lo + hi)
    if y <= 0 or not math.isfinite(y):
        raise PickemError("gamma posterior quantile is not finite")
    return y / rate


def _gamma_posterior_nodes(shape: float, rate: float) -> list[tuple[float, float]]:
    """Fixed 41-point midpoint rule on the gamma quantile grid."""
    nodes = []
    for i in range(QUADRATURE_POINTS):
        probability = (i + 0.5) / QUADRATURE_POINTS
        nodes.append((_gamma_ppf(probability, shape, rate), 1.0))
    return nodes


def _normal_posterior_nodes(mean: float, se: float) -> list[tuple[float, float]]:
    """20-point Gauss-Hermite nodes for a normal posterior of the mean."""
    span = math.sqrt(2.0)
    return [(mean + se * span * x, weight) for x, weight in GAUSS_HERMITE_20]


def _quadrature_probs(dist, line, sd, var_ratio, nodes) -> tuple[float, float, float]:
    overs, unders, pushes, weights = [], [], [], []
    for mu, weight in nodes:
        over, under, push = _node_probs(dist, mu, line, sd, var_ratio)
        overs.append(weight * over)
        unders.append(weight * under)
        pushes.append(weight * push)
        weights.append(weight)
    scale = math.fsum(weights)
    if scale <= 0 or not math.isfinite(scale):
        raise PickemError("quadrature weights are empty")
    over = max(0.0, math.fsum(overs) / scale)
    under = max(0.0, math.fsum(unders) / scale)
    push = max(0.0, math.fsum(pushes) / scale)
    total = over + under + push
    if total <= 0 or not math.isfinite(total):
        raise PickemError("robust probabilities are not finite")
    return over / total, under / total, push / total


def _robust_win(dist, mean, line, sd, var_ratio, n_eff, side, over_win, under_win, push) -> dict:
    """Integrate q_win over the posterior of the true mean.

    Poisson and negbin use a Gamma posterior matched to mean and mean_se.
    Normal uses a Normal posterior. n_eff <= 0 has no finite standard error,
    so the robust probabilities stay on the point estimate.
    """
    point = over_win if side == "over" else under_win
    if n_eff <= 0 or not math.isfinite(n_eff):
        return {
            "q_win_over_robust": over_win,
            "q_win_under_robust": under_win,
            "q_push_robust": push,
            "q_win_robust": point,
            "q_loss_robust": _clip01(1 - point - push, "q_loss_robust"),
            "mean_se": None,
            "sample_effective_n": 0.0,
        }
    if dist == "normal":
        mean_se = sd / math.sqrt(n_eff)
        nodes = None  # exact convolution below
    elif dist == "poisson":
        mean_se = math.sqrt(mean / n_eff)
        nodes = None  # exact Gamma-Poisson mixture below
    elif dist == "negbin":
        ratio = _finite("var_ratio", var_ratio)
        mean_se = math.sqrt(ratio * mean / n_eff)
        rate = n_eff / ratio
        nodes = _gamma_posterior_nodes(mean * rate, rate)
    else:
        raise PickemError("dist must be poisson, negbin, or normal")
    if not math.isfinite(mean_se) or mean_se < 0:
        raise PickemError("mean_se is not finite")
    if dist == "poisson":
        # Gamma-Poisson mixture has an exact negative-binomial predictive law.
        # Internal PMF accepts variance ratios near one; no arbitrary 1.10 gate.
        ratio = 1.0 + 1.0 / n_eff
        whole = abs(line - round(line)) < 1e-9
        threshold = int(math.floor(line)) + 1
        over = _clip01(1 - math.fsum(_nb_pmf(k, mean, ratio) for k in range(threshold)), "over")
        push_r = _nb_pmf(int(round(line)), mean, ratio) if whole else 0.0
        under = _clip01(1 - over - push_r, "under")
    elif dist == "normal":
        # Convolution of Normal observation and Normal mean uncertainty is exact.
        over, under, push_r = _normal_tails(mean, math.hypot(sd, mean_se), line)
    else:
        over, under, push_r = _quadrature_probs(dist, line, sd, var_ratio, nodes)
    q_win = over if side == "over" else under
    return {
        "q_win_over_robust": over,
        "q_win_under_robust": under,
        "q_push_robust": push_r,
        "q_win_robust": q_win,
        "q_loss_robust": _clip01(1 - q_win - push_r, "q_loss_robust"),
        "mean_se": mean_se,
        "sample_effective_n": float(n_eff),
    }


def _blend_prior(baseline_mean, baseline_n, prior_mean, prior_n, notes) -> tuple[float, float]:
    """Blend a same-role prior season into the baseline mean. Default is off.

    prior_n is capped at 20. The returned prior count is 0 when no prior is passed.
    current_role_n does not absorb that count; sample_effective_n does.
    """
    if prior_mean is None and prior_n is None:
        return baseline_mean, 0.0
    if prior_mean is None or prior_n is None:
        raise PickemError("pass prior mean and prior n together, or omit both")
    prior_mean = _finite("prior_mean", prior_mean)
    prior_n = _finite("prior_n", prior_n)
    if prior_mean < 0 or prior_n <= 0:
        raise PickemError("prior mean must be >= 0 and prior n must be positive")
    prior_n_used = min(prior_n, PRIOR_N_CAP)
    blended = (
        baseline_n * baseline_mean + prior_n_used * prior_mean
    ) / (baseline_n + prior_n_used)
    notes.append("PRIOR_USED")
    return blended, prior_n_used


def _tier_basis(value) -> str:
    if value is None or value == "":
        return "q_win_robust"
    if not isinstance(value, str) or value.strip() not in ("q_win", "q_win_robust"):
        raise PickemError("tier_basis must be q_win or q_win_robust")
    return "q_win_robust"  # legacy point requests cannot change published grading


def _clamp(value: float, bounds: tuple[float, float]) -> tuple[float, bool]:
    lo, hi = bounds
    clamped = min(hi, max(lo, value))
    return clamped, abs(clamped - value) > 1e-12


def _form_mean(baseline_mean, baseline_n, recent_mean, recent_n, season_n, role_change, notes):
    """Non-overlapping sample-size blend, or an empirical-Bayes update after a role change.

    Baseline and recent must not contain the same games. When both come from one
    log, baseline_n + recent_n must be <= season_n.
    """
    if recent_mean is None:
        return baseline_mean, 0.0, False
    recent_mean = _finite("recent_mean", recent_mean)
    recent_n = _finite("recent_n", recent_n)
    if recent_mean < 0 or recent_n <= 0:
        raise PickemError("recent mean must be >= 0 and recent n must be positive")
    if recent_n < 5 and not role_change:
        notes.append("RECENT_IGNORED")
        return baseline_mean, 0.0, False
    if season_n is None:
        raise PickemError("a recent window requires --season-n")
    season_n = _finite("season_n", season_n)
    if season_n < 1:
        raise PickemError("season_n must be >= 1")
    if baseline_n + recent_n > season_n + 1e-9:
        raise PickemError(
            "OVERLAP: baseline_n + recent_n exceeds season_n. "
            "Remove the recent games from the baseline before blending."
        )
    if role_change:
        # Old-role prior of 8 games. This pulls the new-role mean toward the old role.
        form = (recent_n * recent_mean + OLD_ROLE_PRIOR * baseline_mean) / (recent_n + OLD_ROLE_PRIOR)
        notes.append("ROLE_EB")
        if recent_n < 5:
            notes.append("NEW_ROLE_SHORT_WINDOW")
        return form, recent_n / (recent_n + OLD_ROLE_PRIOR), True
    form = (baseline_n * baseline_mean + recent_n * recent_mean) / (baseline_n + recent_n)
    return form, recent_n / (baseline_n + recent_n), True


def project(
    dist: str,
    side: str,
    line: float,
    baseline_mean: float,
    baseline_n: float,
    recent_mean: float | None = None,
    recent_n: float | None = None,
    season_n: float | None = None,
    workload_baseline: float | None = None,
    workload_expected: float | None = None,
    rate_baseline: float | None = None,
    rate_expected: float | None = None,
    opponent_factor: float = 1.0,
    pace_factor: float = 1.0,
    role_change: bool = False,
    sd: float | None = None,
    var_ratio: float | None = None,
    funnel_channels: int = 0,
    prior_mean: float | None = None,
    prior_n: float | None = None,
    observation_ids: dict | None = None,
) -> dict:
    """History-only projection and strict win/push probabilities.

    All constants remain uncalibrated until scripts/report.py shows at least 300
    settled graded props.

    See references/math_helper.md for historical pooling, role-change Kish N,
    exact Poisson and Normal predictive uncertainty, and legacy argument behavior.
    Context arguments are excluded; observed Normal dispersion stays unchanged.
    """
    if side not in ('over', 'under'):
        raise PickemError('side must be over or under')
    if not isinstance(role_change, bool):
        raise PickemError("role_change must be a boolean")
    if var_ratio is not None:
        var_ratio = _finite("var_ratio", var_ratio)
    if dist == "poisson" and (sd is not None or var_ratio is not None):
        raise PickemError("poisson does not take --sd or --var-ratio")
    if dist == "normal" and sd is None:
        raise PickemError("normal requires --sd from the player's game log")
    if dist == "negbin" and (var_ratio is None or _negbin_rejected(var_ratio)):
        raise PickemError(
            "negbin requires --var-ratio above 1.10 from the player's game log; "
            "use poisson when variance / mean is 1.10 or less"
        )
    if (recent_mean is None) != (recent_n is None):
        raise PickemError("pass recent mean and recent n together, or omit both")
    if (workload_baseline is None) != (workload_expected is None):
        raise PickemError("pass both workload figures, or omit both")
    if (rate_baseline is None) != (rate_expected is None):
        raise PickemError("pass both rate figures, or omit both")

    baseline_mean = _finite("baseline_mean", baseline_mean)
    baseline_n = _finite("baseline_n", baseline_n)
    if baseline_mean <= 0 or baseline_n < 1:
        raise PickemError("baseline mean must be positive and baseline n must be >= 1")

    if observation_ids is not None:
        if not isinstance(observation_ids, dict):raise PickemError("observation_ids must be an object")
        if set(observation_ids)-{'baseline','recent','prior'}:
            raise PickemError('unknown historical observation window')
        seen_ids=set()
        for window, expected in (("baseline",baseline_n),("recent",recent_n or 0),("prior",prior_n or 0)):
            ids=observation_ids.get(window,[])
            if not isinstance(ids,list) or len(ids)!=expected or any(not isinstance(x,str) or not x.strip() or x!=x.strip() for x in ids):
                raise PickemError("observation ID count mismatch for "+window)
            if len(ids)!=len(set(ids)) or seen_ids.intersection(ids):
                raise PickemError("duplicate historical observation across or within windows")
            seen_ids.update(ids)
    _funnel_channels(funnel_channels)  # validate legacy input even though excluded
    notes = []
    baseline_mean, prior_n_used = _blend_prior(
        baseline_mean, baseline_n, prior_mean, prior_n, notes
    )
    # History-only Engine A. Legacy context arguments remain accepted so old
    # prep files can be inspected; none may change this engine's forecast.
    if any((workload_baseline is not None, rate_baseline is not None,
            opponent_factor != 1.0, pace_factor != 1.0, funnel_channels != 0)):
        notes.append("CONTEXT_EXCLUDED_FROM_ENGINE_A")
    # Check overlap using actual current-season counts, before adding prior data.
    form, recent_weight, recent_used = _form_mean(
        baseline_mean, baseline_n, recent_mean, recent_n, season_n, role_change, notes
    )
    current_role_n = (float(recent_n) if recent_used else 0.0) if role_change else (
        baseline_n + (float(recent_n) if recent_used else 0.0))
    if not role_change:
        total_n = baseline_n + prior_n_used + (float(recent_n) if recent_used else 0.0)
        form = ((baseline_n + prior_n_used) * baseline_mean +
                (float(recent_n) * float(recent_mean) if recent_used else 0.0)) / total_n
        # Independent equal-weight observations, including capped historical prior.
        effective_n = total_n
        recent_weight = float(recent_n) / total_n if recent_used else 0.0
    elif recent_used:
        # Kish effective N for an old-role prior of fixed total weight 8.
        old_n = baseline_n + prior_n_used
        effective_n = (float(recent_n) + OLD_ROLE_PRIOR) ** 2 / (
            float(recent_n) + OLD_ROLE_PRIOR ** 2 / old_n)
    else:
        effective_n = 0.0
    shrunk = trusted = form
    ratio = rate_ratio = opp = pace = 1.0
    channels = 0
    context_weight = 0.0
    workload_given = False
    if shrunk <= 0 or not math.isfinite(shrunk):
        raise PickemError("historical mean must be positive")

    sd_used = None
    left_mass = None
    if dist == "normal":
        # Preserve observed historical dispersion; context does not rescale it.
        sd = _finite("sd", sd)
        if sd <= 0:
            raise PickemError("sd must be positive")
        sd_used = sd
        left_mass = NormalDist(shrunk, sd_used).cdf(-0.5)
        if left_mass > NORMAL_NEGATIVE_MASS:
            notes.append("NORMAL_LEFT_TAIL")
    if dist == "negbin" and var_ratio is not None and var_ratio > VAR_RATIO_CAP:
        notes.append("VAR_RATIO_CLAMPED")
        var_ratio = VAR_RATIO_CAP

    over_win, over_push = side_probs(dist, shrunk, line, "over", sd_used, var_ratio)
    under_win, under_push = side_probs(dist, shrunk, line, "under", sd_used, var_ratio)
    if abs(over_push - under_push) > 1e-6:
        raise PickemError("over and under push probabilities disagree")
    q_push = over_push
    if abs(over_win + under_win + q_push - 1) > 1e-5:
        raise PickemError("over, under, and push do not sum to 1")
    q_win = over_win if side == "over" else under_win
    q_loss = _clip01(1 - q_win - q_push, "q_loss")
    supports = shrunk > line if side == "over" else shrunk < line
    if role_change and current_role_n < 1 and not workload_given:
        sample_block = True
        notes.append("NO_CURRENT_ROLE")
    elif not role_change and current_role_n < 5:
        sample_block = True
        notes.append("SAMPLE_BLOCK")
    else:
        sample_block = False
    if "NORMAL_LEFT_TAIL" in notes:
        sample_block = True
    if role_change and current_role_n < 5:
        notes.append("NEW_ROLE_THIN")
    robust = _robust_win(
        dist, shrunk, line, sd_used, var_ratio, effective_n, side,
        over_win, under_win, q_push,
    )
    if dist == "normal" and robust["mean_se"] is not None:
        predictive_left_mass = NormalDist(shrunk, math.hypot(sd_used, robust["mean_se"])).cdf(-.5)
        if predictive_left_mass > NORMAL_NEGATIVE_MASS:
            if "NORMAL_LEFT_TAIL" not in notes:
                notes.append("NORMAL_LEFT_TAIL")
            sample_block = True
    return {
        "observation_ids_verified": observation_ids is not None,
        "blended_rate": form,
        "recent_weight": recent_weight,
        "workload_ratio": ratio,
        "rate_ratio": rate_ratio,
        "opponent_factor_used": opp,
        "pace_factor_used": pace,
        "trusted_mean": trusted,
        "shrunk_mean": shrunk,
        "current_role_n": current_role_n,
        "funnel_channels": channels,
        "context_weight": context_weight,
        "q_win": q_win,
        "q_win_over": over_win,
        "q_win_under": under_win,
        "q_push": q_push,
        "q_loss": q_loss,
        "q_win_robust": robust["q_win_robust"],
        "q_win_over_robust": robust["q_win_over_robust"],
        "q_win_under_robust": robust["q_win_under_robust"],
        "q_push_robust": robust["q_push_robust"],
        "q_loss_robust": robust["q_loss_robust"],
        "mean_se": robust["mean_se"],
        "sample_effective_n": robust["sample_effective_n"],
        "whole_line": abs(float(line) - round(float(line))) < 1e-9,
        "mean_supports_side": supports,
        "low_sample": current_role_n < 10,
        "sample_block": sample_block,
        "sd_used": sd_used,
        "var_ratio_used": var_ratio if dist == 'negbin' else None,
        "normal_left_mass": left_mass,
        "distribution_block": "NORMAL_LEFT_TAIL" in notes,
        "notes": notes,
    }


def _gap_caps(magnitude: float) -> bool:
    """True when the absolute gap reaches 8 points, allowing for binary float noise."""
    return magnitude >= GAP_WATCH_CAP - GAP_EPSILON


def _lower_rank(left: str, right: str) -> str:
    return left if RANK_ORDER[left] <= RANK_ORDER[right] else right


def _band(q: float) -> str:
    if q >= TIER_1:
        return "NUMERIC_TIER_1"
    if q >= TIER_2:
        return "NUMERIC_TIER_2"
    if q >= TIER_3:
        return "NUMERIC_TIER_3"
    if q >= WATCH_FLOOR:
        return "WATCHLIST"
    return "REJECT"


def _flag_cap(flags: int) -> str:
    if flags <= 0:
        return "NUMERIC_TIER_1"
    if flags == 1:
        return "NUMERIC_TIER_2"
    if flags == 2:
        return "NUMERIC_TIER_3"
    return "WATCHLIST"


FINAL_ORDER = {
    "Tier 1": 5,
    "Tier 2": 4,
    "Tier 3": 3,
    "Watchlist": 2,
    "Reject": 1,
    "Unranked": 0,
}


def _lower_final(left: str, right: str) -> str:
    return left if FINAL_ORDER[left] <= FINAL_ORDER[right] else right


def grade(
    q_model: float,
    q_market: float,
    soft_flags: int,
    current_role_n: float,
    role_change: bool = False,
    q_push: float = 0.0,
    workload_adjusted: bool = False,
    normal_left_tail: bool = False,
) -> dict:
    """Score unconditional P(win). The market benchmark is separate.

    q_market is conditional on no push when q_push > 0. The comparable benchmark is
    q_market * (1 - q_push) and is model-adjusted on a whole-number line.
    gap_magnitude = abs(q_model - q_market_comparable).
    A magnitude above 0.03 adds one MODEL_MARKET_GAP flag. A magnitude of 0.08 or
    more caps the numerical rank at Watchlist. The signed gap is not subtracted from q_grade.
    """
    q_model = _finite("q_model", q_model)
    q_market = _finite("q_market", q_market)
    q_push = _finite("q_push", q_push)
    current_role_n = _finite("current_role_n", current_role_n)
    if current_role_n < 0:
        raise PickemError("current_role_n must be >= 0")
    if not 0 <= q_model <= 1 or not 0 <= q_market <= 1 or not 0 <= q_push <= 1:
        raise PickemError("probabilities must be between 0 and 1")
    if q_model + q_push > 1 + 1e-9:
        raise PickemError("q_model + q_push exceeds 1")
    if isinstance(soft_flags, bool) or not isinstance(soft_flags, int) or soft_flags < 0:
        raise PickemError("soft_flags must be an integer >= 0")
    q_loss = _clip01(1 - q_model - q_push, "q_loss")
    comparable = _clip01(q_market * (1.0 - q_push), "q_market_comparable")
    signed_gap = q_model - comparable
    magnitude = abs(signed_gap)
    market_scale = "unconditional" if q_push == 0 else "conditional_converted_with_model_push"
    base = {
        "q_model": q_model,
        "q_push": q_push,
        "q_loss": q_loss,
        "q_market": q_market,
        "q_market_comparable": comparable,
        "q_market_scale": market_scale,
        "market_conversion": "q_market * (1 - q_push)" if q_push else "identity",
        "q_gap": signed_gap,
        "gap_magnitude": magnitude,
        "current_role_n": current_role_n,
        "numerical_band": None,
        "unicorn_numeric": False,
    }
    blocked = (not role_change and current_role_n < 5) or (
        role_change and current_role_n < 1 and not workload_adjusted
    )
    if normal_left_tail or blocked:
        if normal_left_tail:
            reason = "NORMAL_LEFT_TAIL"
        elif role_change:
            reason = "NO_CURRENT_ROLE"
        else:
            reason = "SAMPLE_BLOCK"
        return {
            **base,
            "status": "UNRANKED",
            "reason": reason,
            "q_grade": None,
            "soft_flags": soft_flags,
            "qualitative_flags": soft_flags,
            "probability_rank": None,
            "flag_ceiling": None,
            "notes": [reason],
        }
    notes = []
    flags = soft_flags
    if current_role_n < 10:
        flags += 1
        notes.append("LOW_SAMPLE")
    if role_change and current_role_n < 5:
        flags += 1
        notes.append("NEW_ROLE_THIN")
    if _exceeds(magnitude, GAP_FLAG):
        flags += 1
        notes.append("MODEL_MARKET_GAP")
    if _gap_caps(magnitude):
        notes.append("GAP_LARGE")
    # Review the large-edge rule explicitly, rather than silently weakening
    # the cap or treating model/market disagreement as independent evidence.
    gap_review = {'large_gap': _gap_caps(magnitude),
                  'signed_gap': signed_gap,
                  'requires': ['fresh_same_line_market_consensus',
                               'independent_sourced_mechanisms',
                               'adversarial_review'] if _gap_caps(magnitude) else [],
                  'cap': 'Watchlist' if _gap_caps(magnitude) else None,
                  'override_authorized': False}
    q_grade = q_model
    numerical = _band(q_grade)
    # Tier 1's numeric band requires the market benchmark as well as the model.
    if comparable < TIER_1 - GAP_EPSILON:
        numerical = _lower_rank(numerical, "NUMERIC_TIER_2")
    rank = _lower_rank(numerical, _flag_cap(flags))
    if _gap_caps(magnitude):
        rank = _lower_rank(rank, "WATCHLIST")
    unicorn = (
        q_grade >= TIER_1
        and comparable >= TIER_1
        and flags == 0
        and current_role_n >= 10
        and not _gap_caps(magnitude)
    )
    return {
        **base,
        "status": "GRADED",
        "reason": None,
        "q_grade": q_grade,
        "numerical_band": numerical,
        "soft_flags": flags,
        "qualitative_flags": soft_flags,
        "probability_rank": rank,
        "flag_ceiling": _flag_cap(flags),
        "unicorn_numeric": unicorn,
        "notes": notes,
        "gap_review": gap_review,
    }


def finalize(
    scored: dict,
    mechanisms: int,
    hard_veto: bool,
    data_veto: bool,
    market_valid: bool,
    research_checklist: bool,
) -> str:
    """Authoritative label. Research attestation cannot override a failed machine check."""
    if isinstance(mechanisms, bool) or not isinstance(mechanisms, int) or mechanisms < 0:
        raise PickemError("mechanisms must be an integer >= 0")
    if data_veto or not market_valid or scored.get("status") != "GRADED":
        return "Unranked"
    if hard_veto:
        return "Reject"
    band = scored.get("probability_rank")
    if band is None:
        return "Unranked"
    labels = {
        "REJECT": "Reject",
        "WATCHLIST": "Watchlist",
        "NUMERIC_TIER_3": "Tier 3",
        "NUMERIC_TIER_2": "Tier 2",
        "NUMERIC_TIER_1": "Tier 1",
    }
    if band not in labels:
        raise PickemError(f"unknown probability_rank '{band}'")
    final = labels[band]
    if mechanisms < 1 and final in ("Tier 1", "Tier 2", "Tier 3"):
        final = "Watchlist"
    if mechanisms < 2 and final == "Tier 1":
        final = "Tier 2"
    machine_unicorn = (
        scored.get("q_grade") is not None
        and scored["q_grade"] >= TIER_1
        and scored["q_market_comparable"] >= TIER_1
        and scored["soft_flags"] == 0
        and scored["current_role_n"] >= 10
        and not _gap_caps(scored["gap_magnitude"])
        and mechanisms >= 2
        and research_checklist
    )
    if final == "Tier 1" and not machine_unicorn:
        final = "Tier 2" if mechanisms >= 1 else "Watchlist"
    ceiling = {0: "Tier 1", 1: "Tier 2", 2: "Tier 3"}.get(scored["soft_flags"], "Watchlist")
    final = _lower_final(final, ceiling)
    if _gap_caps(scored["gap_magnitude"]):
        final = _lower_final(final, "Watchlist")
    if scored["current_role_n"] < 10:
        final = _lower_final(final, "Tier 2")
    return final


def decide(
    q_model: float,
    q_market: float,
    soft_flags: int,
    current_role_n: float,
    mechanisms: int,
    hard_veto: bool = False,
    data_veto: bool = False,
    market_valid: bool = True,
    research_checklist: bool = False,
    role_change: bool = False,
    q_push: float = 0.0,
    workload_adjusted: bool = False,
    normal_left_tail: bool = False,
) -> dict:
    scored = grade(
        q_model, q_market, soft_flags, current_role_n, role_change, q_push,
        workload_adjusted, normal_left_tail,
    )
    final = finalize(scored, mechanisms, hard_veto, data_veto, market_valid, research_checklist)
    scored["final_rank"] = final
    scored["mechanisms"] = mechanisms
    scored["hard_veto"] = hard_veto
    scored["data_veto"] = data_veto
    scored["market_valid"] = market_valid
    scored["research_checklist"] = research_checklist
    return scored


def is_shadow_row(row: dict) -> bool:
    """Calibration-only rows written by scripts/jobs.py snapshot."""
    if not isinstance(row, dict):
        return False
    return str(row.get("run_type") or "").strip().lower() == RUN_TYPE_SHADOW


def user_facing_rows(rows: list[dict]) -> list[dict]:
    """Rows that may appear on a published board or in tier calibration stats."""
    return [row for row in rows if not is_shadow_row(row)]


def _reject_underdog(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if "underdog" in str(key).lower():
                raise PickemError("snapshot cannot contain an Underdog field")
            _reject_underdog(item)
    elif isinstance(value, list):
        for item in value:
            _reject_underdog(item)


def _lock_handle(handle) -> None:
    """Exclusive lock. fcntl on Unix, msvcrt on Windows."""
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return
    import fcntl
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock_handle(handle) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl
    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def locked_snapshot(path: Path, create: bool = False):
    """Open the snapshot log and hold an exclusive lock until the block exits."""
    path = Path(path)
    if not create and not path.exists():
        raise PickemError(f"snapshot file not found: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_RDWR | (os.O_CREAT if create else 0)
    fd = os.open(path, flags, 0o644)
    handle = os.fdopen(fd, "r+", encoding="utf-8", newline="\n")
    try:
        _lock_handle(handle)
        try:
            handle.seek(0)
            text = handle.read()
            yield handle, text
        finally:
            _unlock_handle(handle)
    finally:
        handle.close()


def _canonical_run_id(value) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise PickemError("run_id must be a UUID")
    try:
        return str(uuid.UUID(value.strip()))
    except ValueError as exc:
        raise PickemError("run_id must be a UUID") from exc


def _json_number(name: str, value):
    if value is None or value == "":
        return None
    if isinstance(value, str):
        text = value.strip().replace("+", "")
        if text == "":
            return None
        try:
            number = float(text)
        except ValueError as exc:
            raise PickemError(f"{name} must be a finite number") from exc
    else:
        number = value
    number = _finite(name, number)
    if number == int(number):
        return int(number)
    return number


def _optional_unit(name: str, value):
    if value is None:
        return None
    number = _finite(name, value)
    if number < -1e-9 or number > 1 + 1e-9:
        raise PickemError(f"{name} must be between 0 and 1")
    return min(1.0, max(0.0, number))


def _retrieved_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _book_quote(book, line, over, under, retrieved_at) -> dict:
    name = str(book).strip()
    if not name:
        raise PickemError("book entry needs a book name")
    return {
        "book": name,
        "line": _json_number("line", line),
        "over": _json_number("over", over),
        "under": _json_number("under", under),
        "retrieved_at": _retrieved_text(retrieved_at),
    }


def books_from_text(text, line, retrieved_at) -> list[dict]:
    """Turn a legacy books sentence into quote objects. Odds stay null when absent."""
    raw = str(text).strip()
    if not raw:
        return []
    over_hit = re.search(
        rf"\bbest over\s+({_BOOK_NAME})\s+({_AMERICAN_ODDS})", raw, re.IGNORECASE,
    )
    under_hit = re.search(
        rf"\bbest under\s+({_BOOK_NAME})\s+({_AMERICAN_ODDS})", raw, re.IGNORECASE,
    )
    if over_hit or under_hit:
        quotes = []
        if over_hit:
            quotes.append(_book_quote(
                over_hit.group(1), line, over_hit.group(2), None, retrieved_at,
            ))
        if under_hit:
            quotes.append(_book_quote(
                under_hit.group(1), line, None, under_hit.group(2), retrieved_at,
            ))
        return quotes
    pairs = list(_BOOK_PAIR.finditer(raw))
    if pairs:
        return [
            _book_quote(match.group(1), line, match.group(2), match.group(3), retrieved_at)
            for match in pairs
        ]
    return [_book_quote(raw, line, None, None, retrieved_at)]


def _prices_for_side(target, other, book_side, snapshot_side):
    side = book_side or snapshot_side
    if side == "over":
        return target, other
    if side == "under":
        return other, target
    raise PickemError("book side must be over or under")


def _quote_from_mapping(item: dict, snapshot_side: str, line, retrieved_at, lenient: bool) -> dict:
    if "book" not in item:
        raise PickemError("book entry needs a book name")
    quote_line = item["line"] if item.get("line") is not None else line
    quote_retrieved = item.get("retrieved_at", retrieved_at)
    if "over" in item or "under" in item:
        return _book_quote(
            item["book"], quote_line, item.get("over"), item.get("under"), quote_retrieved,
        )
    if "target" in item or "other" in item:
        book_side = item.get("book_side")
        if book_side is not None:
            try:
                book_side = _parse_book_side(book_side)
            except PickemError:
                if not lenient:
                    raise
                book_side = None
        if book_side is not None and book_side != snapshot_side:
            raise PickemError(
                f"{item['book']} book_side {book_side} does not match candidate side {snapshot_side}"
            )
        if book_side is None and "book_side" not in item:
            _warn_legacy_book(str(item.get("book")))
        over, under = _prices_for_side(
            item.get("target"), item.get("other"), book_side, snapshot_side,
        )
        return _book_quote(item["book"], quote_line, over, under, quote_retrieved)
    return _book_quote(item["book"], quote_line, None, None, quote_retrieved)


def _quote_from_spec(spec: str, snapshot_side: str, line, retrieved_at, lenient: bool) -> dict:
    try:
        parsed = _parse_book_spec(spec)
    except PickemError:
        if not lenient:
            raise
        return _book_quote(spec, line, None, None, retrieved_at)
    book_side = parsed["book_side"]
    if book_side is not None and book_side != snapshot_side:
        raise PickemError(
            f"{parsed['book']} book_side {book_side} does not match candidate side {snapshot_side}"
        )
    over, under = _prices_for_side(
        parsed["target"], parsed["other"], book_side, snapshot_side,
    )
    return _book_quote(parsed["book"], parsed["line"], over, under, retrieved_at)


def _is_book_spec(text: str) -> bool:
    return text.count(":") >= 3 and not text.strip().lower().startswith("http")


def convert_books(books, *, side: str, line, retrieved_at, lenient: bool = False) -> list[dict]:
    """Books are always `{book, line, over, under, retrieved_at}` objects."""
    side_text = str(side or "over").strip().lower()
    if side_text not in ("over", "under"):
        if not lenient:
            raise PickemError("side must be over or under")
        side_text = "over"
    fallback_line = line
    try:
        if fallback_line is not None:
            _json_number("line", fallback_line)
    except PickemError:
        fallback_line = None
    if books is None:
        return []
    if isinstance(books, str):
        return books_from_text(books, fallback_line, retrieved_at)
    if isinstance(books, dict):
        items = [books]
    elif isinstance(books, (list, tuple)):
        items = list(books)
    else:
        raise PickemError("books must be a list")
    quotes = []
    for item in items:
        if isinstance(item, str):
            if _is_book_spec(item):
                quotes.append(_quote_from_spec(
                    item, side_text, fallback_line, retrieved_at, lenient,
                ))
            else:
                quotes.extend(books_from_text(item, fallback_line, retrieved_at))
        elif isinstance(item, dict):
            quotes.append(_quote_from_mapping(
                item, side_text, fallback_line, retrieved_at, lenient,
            ))
        elif isinstance(item, (list, tuple)) and len(item) in (4, 5):
            mapping = {
                "book": item[0], "line": item[1], "target": item[2], "other": item[3],
            }
            if len(item) == 5:
                mapping["book_side"] = item[4]
            quotes.append(_quote_from_mapping(
                mapping, side_text, fallback_line, retrieved_at, lenient,
            ))
        else:
            raise PickemError(
                "book entry must be a quote, a spec string, or {book, line, over, under}"
            )
    for quote in quotes:
        extra = set(quote) - set(SNAPSHOT_BOOK_KEYS)
        if extra:
            raise PickemError("book quote has unexpected fields")
    return quotes


def _copy_inputs(raw: dict):
    if "inputs" not in raw or raw["inputs"] is None:
        return None
    if not isinstance(raw["inputs"], dict):
        raise PickemError("inputs must be the pipeline JSON object")
    return copy.deepcopy(raw["inputs"])


def _snapshot_dist(raw: dict, inputs):
    value = raw.get("dist") if raw.get("dist") is not None else None
    if value is None and isinstance(inputs, dict):
        value = inputs.get("dist")
    if value is None:
        return None
    if not isinstance(value, str):
        raise PickemError("dist must be poisson, negbin, or normal")
    dist = value.strip().lower()
    if dist not in {"poisson", "negbin", "normal"}:
        raise PickemError("dist must be poisson, negbin, or normal")
    return dist


def _take(raw: dict, name: str, *fallbacks):
    if name in raw:
        return raw[name]
    for source in fallbacks:
        if isinstance(source, dict) and name in source:
            return source[name]
    return None


def _snapshot_flags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (tuple, list)):
        flags = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise PickemError("derived_flags must be strings")
            flags.append(item.strip())
        return flags
    raise PickemError("derived_flags must be a list")


def _snapshot_status(value) -> str:
    if not isinstance(value, str):
        raise PickemError("status must be GRADED or UNRANKED")
    status = value.strip().upper()
    if status not in SNAPSHOT_STATUS:
        raise PickemError("status must be GRADED or UNRANKED")
    return status


def _snapshot_reason(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise PickemError("reason must be a string")
    text = value.strip()
    return text or None


def load_blend_weights_version() -> str | None:
    """Live blend config version stamped on each new snapshot row."""
    path = DEFAULT_BLEND_WEIGHTS_PATH
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = payload.get("version")
    if version in (None, ""):
        return None
    return str(version)


def normalize_snapshot(raw: dict, run_id: str | None = None) -> dict:
    """One researched prop. Schema version 2. Picks and rejects use the same record.

    `run_id` fills a row that omits it. One log process passes the same id.
    `inputs` is stored exactly. `status` is only GRADED or UNRANKED.
    `final_rank` stays the skill rank.
    """
    if not isinstance(raw, dict):
        raise PickemError("snapshot must be a JSON object")
    _reject_underdog(raw)
    missing = [key for key in SNAPSHOT_REQUIRED if key not in raw]
    if missing:
        raise PickemError("snapshot missing " + ", ".join(missing))
    record = dict(raw)
    for key in ("run_at", "game_date", "matchup", "player", "stat"):
        value = record[key]
        if not isinstance(value, str) or not value.strip():
            raise PickemError(f"{key} must be a non-empty string")
        record[key] = value.strip()
    record["side"] = str(record["side"]).strip().lower()
    record["sport"] = str(record["sport"]).strip()
    record["final_rank"] = str(record["final_rank"]).strip()
    run_type = str(record.get("run_type") or "").strip().lower()
    if run_type == RUN_TYPE_SHADOW:
        record["run_type"] = RUN_TYPE_SHADOW
        if record["researched"] not in (False, True):
            raise PickemError("researched must be true or false for shadow rows")
    else:
        if run_type:
            record["run_type"] = run_type
        elif "run_type" in record:
            record.pop("run_type", None)
        if record["researched"] is not True:
            raise PickemError("log only props that were actually researched")
    if record["final_rank"] not in SNAPSHOT_RANKS:
        raise PickemError("final_rank must be a skill rank")
    if record["sport"] not in ("NBA", "NHL", "NFL"):
        raise PickemError("sport must be NBA, NHL, or NFL")
    if record["side"] not in ("over", "under"):
        raise PickemError("side must be over or under")
    record["status"] = _snapshot_status(record["status"])
    if "run_id" in raw and raw["run_id"] not in (None, ""):
        record["run_id"] = _canonical_run_id(raw["run_id"])
    else:
        record["run_id"] = _canonical_run_id(run_id) or str(uuid.uuid4())
    inputs = _copy_inputs(raw)
    record["inputs"] = inputs
    record["dist"] = _snapshot_dist(raw, inputs)
    project = raw.get("project") if isinstance(raw.get("project"), dict) else None
    grade = raw.get("grade") if isinstance(raw.get("grade"), dict) else None
    q_win = _optional_unit("q_win", _take(raw, "q_win", project))
    q_push = _optional_unit("q_push", _take(raw, "q_push", project, grade))
    q_loss = _take(raw, "q_loss", project, grade)
    if q_loss is None and q_win is not None and q_push is not None:
        q_loss = 1.0 - q_win - q_push
    q_loss = _optional_unit("q_loss", q_loss) if q_loss is not None else None
    q_gap = _take(raw, "q_gap", grade)
    if q_gap is not None:
        q_gap = _finite("q_gap", q_gap)
        if abs(q_gap) > 1 + 1e-6:
            raise PickemError("q_gap must be between -1 and 1")
    if "books" in raw:
        books_source = raw["books"]
    elif isinstance(inputs, dict) and "books" in inputs:
        books_source = inputs["books"]
    else:
        books_source = None
    record["schema_version"] = SNAPSHOT_SCHEMA_VERSION
    blend_meta = _snapshot_nested_block(raw, "blend")
    record["blend_weights_version"] = ((blend_meta or {}).get("config_version")
                                       if "blend" in raw else load_blend_weights_version())
    record["derived_flags"] = _snapshot_flags(_take(raw, "derived_flags"))
    record["q_win"] = q_win
    record["q_push"] = q_push
    record["q_loss"] = q_loss
    record["q_grade"] = _optional_unit("q_grade", _take(raw, "q_grade", grade))
    record["q_market"] = _optional_unit("q_market", _take(raw, "q_market", grade))
    record["q_market_comparable"] = _optional_unit(
        "q_market_comparable", _take(raw, "q_market_comparable", grade),
    )
    record["q_gap"] = q_gap
    record["books"] = convert_books(
        books_source,
        side=record["side"],
        line=record.get("reference_line"),
        retrieved_at=record.get("retrieved_at"),
    )
    record["reason"] = _snapshot_reason(_take(raw, "reason", grade))
    record.setdefault("actual_stat", None)
    record.setdefault("closing_line", None)
    record.setdefault("closing_q_market", None)
    record.setdefault("outcome", None)
    record.setdefault("settled_at", None)
    record["engine_a"] = _snapshot_nested_block(raw, "engine_a")
    record["engine_b"] = _snapshot_nested_block(raw, "engine_b")
    record["crosscheck"] = _snapshot_nested_block(raw, "crosscheck")
    record["blend"] = _snapshot_nested_block(raw, "blend")
    market = _snapshot_nested_block(raw, "market")
    if market is None:
        market = {}
        q_market = record.get("q_market")
        if q_market is not None:
            market["q_market"] = q_market
        comparable = record.get("q_market_comparable")
        if comparable is not None:
            market["q_market_comparable"] = comparable
        if record.get("retrieved_at") is not None:
            market["retrieved_at"] = record.get("retrieved_at")
        closing = record.get("closing_q_market")
        if closing is not None:
            market["closing_q_market"] = closing
        market = market or None
    record["market"] = market
    return record


def settlement_outcome(side: str, line, actual) -> str:
    """Win, loss, or push for the logged side. A push is not a win."""
    label = str(side).strip().lower()
    if label not in ("over", "under"):
        raise PickemError("side must be over or under")
    line_n = _finite("reference_line", line)
    actual_n = _finite("actual_stat", actual)
    if actual_n > line_n + 1e-9:
        return "win" if label == "over" else "loss"
    if line_n > actual_n + 1e-9:
        return "loss" if label == "over" else "win"
    return "push"


def snapshot_key(record: dict) -> tuple:
    run_id = record.get("run_id")
    try:
        run_text = str(uuid.UUID(str(run_id).strip())) if run_id not in (None, "") else ""
    except (ValueError, AttributeError):
        run_text = str(run_id or "").strip()
    return (
        run_text,
        str(record.get("game_date") or "").strip(),
        str(record.get("player") or "").strip(),
        str(record.get("stat") or "").strip(),
        str(record.get("side") or "").strip().lower(),
    )


def _duplicate_message(key: tuple) -> str:
    return (
        "duplicate snapshot for run_id={0}, game_date={1}, player={2}, stat={3}, side={4}"
    ).format(*key)


def iter_snapshot_lines(text: str):
    """Yield line number, original line, and object. Blank lines are skipped."""
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PickemError(f"snapshot JSON is invalid on line {line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise PickemError(f"snapshot line {line_no} must be a JSON object")
        yield line_no, line, row


def dump_snapshot(record: dict) -> str:
    try:
        body = json.dumps(record, sort_keys=True, ensure_ascii=False)
    except TypeError as exc:
        raise PickemError(f"snapshot is not JSON: {exc}") from exc
    return body + "\n"


def _reject_batch_duplicates(records: list[dict]) -> None:
    seen = set()
    for record in records:
        key = snapshot_key(record)
        if key in seen:
            raise PickemError(_duplicate_message(key))
        seen.add(key)


def _append_locked(destination: Path, records: list[dict]) -> None:
    payload = "".join(dump_snapshot(record) for record in records)
    with locked_snapshot(destination, create=True) as (handle, text):
        seen = {snapshot_key(row) for _line_no, _line, row in iter_snapshot_lines(text)}
        for record in records:
            key = snapshot_key(record)
            if key in seen:
                raise PickemError(_duplicate_message(key))
            seen.add(key)
        if text and not text.endswith("\n"):
            payload = "\n" + payload
        handle.seek(0, os.SEEK_END)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def append_snapshot(raw: dict, path: Path | None = None) -> Path:
    destination = Path(path) if path is not None else DEFAULT_SNAPSHOT_PATH
    record = normalize_snapshot(raw)
    _append_locked(destination, [record])
    return destination


def append_snapshots(rows, path: Path | None = None) -> tuple[Path, int]:
    """Append many researched props in one process. A bad row writes nothing."""
    if isinstance(rows, dict) or not isinstance(rows, (list, tuple)):
        raise PickemError("log --batch expects one JSON object per line")
    destination = Path(path) if path is not None else DEFAULT_SNAPSHOT_PATH
    if not rows:
        return destination, 0
    batch_id = str(uuid.uuid4())
    records = [normalize_snapshot(row, run_id=batch_id) for row in rows]
    _reject_batch_duplicates(records)
    _append_locked(destination, records)
    return destination, len(records)


def pct(x: float) -> str:
    return f"{100 * x:.2f}%"


def _raw(x: float) -> str:
    """Six decimal places for a human copy. Pipeline JSON is the unrounded value."""
    return f"{x:.6f}"


def _yn(flag: bool) -> str:
    return "yes" if flag else "no"


def _print_project(result: dict) -> None:
    print(
        f"blended_rate={result['blended_rate']:.3f} recent_weight={result['recent_weight']:.3f} "
        f"workload_ratio={result['workload_ratio']:.3f} rate_ratio={result['rate_ratio']:.3f}"
    )
    print(
        f"opponent_factor_used={result['opponent_factor_used']:.3f} "
        f"pace_factor_used={result['pace_factor_used']:.3f}"
    )
    print(
        f"trusted_mean={result['trusted_mean']:.3f} shrunk_mean={result['shrunk_mean']:.3f} "
        f"current_role_n={result['current_role_n']:.0f} "
        f"funnel_channels={result['funnel_channels']} context_weight={result['context_weight']:.0f}"
    )
    print(
        f"q_win={pct(result['q_win'])} q_win_over={pct(result['q_win_over'])} "
        f"q_win_under={pct(result['q_win_under'])} q_push={pct(result['q_push'])} q_loss={pct(result['q_loss'])}"
    )
    print(
        f"q_win_raw={_raw(result['q_win'])} q_win_over_raw={_raw(result['q_win_over'])} "
        f"q_win_under_raw={_raw(result['q_win_under'])} q_push_raw={_raw(result['q_push'])} "
        f"q_loss_raw={_raw(result['q_loss'])}"
    )
    print(
        f"q_win_robust={pct(result['q_win_robust'])} "
        f"q_win_over_robust={pct(result['q_win_over_robust'])} "
        f"q_win_under_robust={pct(result['q_win_under_robust'])} "
        f"q_push_robust={pct(result['q_push_robust'])} "
        f"q_loss_robust={pct(result['q_loss_robust'])}"
    )
    print(
        f"q_win_robust_raw={_raw(result['q_win_robust'])} "
        f"q_win_over_robust_raw={_raw(result['q_win_over_robust'])} "
        f"q_win_under_robust_raw={_raw(result['q_win_under_robust'])} "
        f"q_push_robust_raw={_raw(result['q_push_robust'])} "
        f"q_loss_robust_raw={_raw(result['q_loss_robust'])}"
    )
    se_text = "na" if result["mean_se"] is None else f"{result['mean_se']:.6f}"
    effective = result["sample_effective_n"]
    if abs(effective - round(effective)) <= 1e-9:
        effective_text = str(int(round(effective)))
    else:
        effective_text = f"{effective:.3f}".rstrip("0").rstrip(".")
    print(f"mean_se={se_text} sample_effective_n={effective_text}")
    if result.get("sd_used") is not None:
        print(
            f"sd_used={result['sd_used']:.4f} normal_left_mass={result['normal_left_mass']:.4f}"
        )
    print(
        f"whole_line={_yn(result['whole_line'])} "
        f"mean_supports_side={_yn(result['mean_supports_side'])} "
        f"low_sample={_yn(result['low_sample'])} "
        f"sample_block={_yn(result['sample_block'])} "
        f"distribution_block={_yn(result.get('distribution_block', False))}"
    )
    if result["notes"]:
        print("notes=" + ",".join(result["notes"]))


def _print_grade(result: dict) -> None:
    print(f"status={result['status']}")
    if result["reason"]:
        print(f"reason={result['reason']}")
    print(
        f"q_model={pct(result['q_model'])} q_push={pct(result['q_push'])} q_loss={pct(result['q_loss'])}"
    )
    print(
        f"q_market={pct(result['q_market'])} q_market_scale={result['q_market_scale']} "
        f"market_conversion={result['market_conversion']}"
    )
    print(
        f"q_market_comparable={pct(result['q_market_comparable'])} "
        f"q_gap={pct(result['q_gap'])} gap_magnitude={pct(result['gap_magnitude'])}"
    )
    print(
        f"q_model_raw={_raw(result['q_model'])} q_market_raw={_raw(result['q_market'])} "
        f"q_market_comparable_raw={_raw(result['q_market_comparable'])} q_push_raw={_raw(result['q_push'])}"
    )
    print(f"current_role_n={result['current_role_n']:.0f}")
    if result["q_grade"] is not None:
        print(f"q_grade={pct(result['q_grade'])}")
    print(f"soft_flags={result['soft_flags']} unicorn_numeric={_yn(result['unicorn_numeric'])}")
    if result["probability_rank"]:
        print(f"probability_rank={result['probability_rank']}")
    if result["notes"]:
        print("notes=" + ",".join(result["notes"]))
    print("convention=unconditional_win")
    print("whole_number_benchmark=model_adjusted" if result["q_push"] else "whole_number_benchmark=not_needed")
    print("q_grade is the model estimate. It is not a calibrated true probability.")
    print("probability_rank is not the published tier. Publish final_rank from pipeline.")


PROJECT_FIELDS = {
    "dist", "side", "line", "baseline_mean", "baseline_n",
    "recent_mean", "recent_n", "season_n",
    "workload_baseline", "workload_expected",
    "rate_baseline", "rate_expected",
    "opponent_factor", "pace_factor",
    "role_change", "sd", "var_ratio", "funnel_channels",
    "prior_mean", "prior_n", "observation_ids",
}

READS_PIPELINE_FIELDS = frozenset({
    "sport",
    "team_pass_attempts_expected",
    "team_bucket_throw_share",
    "player_bucket_target_share",
    "conversion",
    "volume_source",
    "def_matchup_factor",
    "first_read_target_share",
    "first_read_player_games",
    "first_read_team_games",
    "checkdown_target_share",
    "checkdown_player_games",
    "checkdown_team_games",
    "reads_charting_ok",
    "reads_charting_missing",
    "reads_charting_status",
    "reads_join_ok",
    "reads_join_failed",
    "reads_join_status",
    "reads_total_stat_validated",
})


def _mean_supports_side(mean, line, side) -> bool:
    if mean is None or line is None or side not in ("over", "under"):
        return False
    mean = float(mean)
    line = float(line)
    if side == "over":
        return mean > line + GAP_EPSILON
    return mean < line - GAP_EPSILON


def crosscheck(a: dict, b: dict, market: dict) -> dict:
    """Compare Engine A to Engine B. Abstain is silent; disagree adds CROSSCHECK_DISAGREE.

    ``tolerance`` is an explicitly provisional probability-point threshold.
    ``se_b`` is in stat units and MUST NOT be compared to probability differences.
    ``b_vote`` is agree only when both means support the candidate side and
    |q_win_a - q_win_b| is within the probability-point tolerance.
    Engine B never raises a published rank; pipeline only adds a soft flag on disagree.
    """
    if not isinstance(a, dict) or not isinstance(b, dict) or not isinstance(market, dict):
        raise PickemError("crosscheck inputs must be objects")
    side = market.get("side")
    line = market.get("line")
    if b.get("abstain"):
        tolerance = CROSSCHECK_TOLERANCE_FLOOR
        return {
            "both_clear_floor": False,
            "side_agree": False,
            "abs_diff": None,
            "tolerance": tolerance,
            "b_vote": "abstain",
        }
    q_a = _finite("q_win", a["q_win"])
    q_b = _finite("q_win_b", b["q_win_b"])
    _finite("se_b", b["se_b"])  # validity only: standard error is NOT a probability
    tolerance = CROSSCHECK_TOLERANCE_FLOOR
    abs_diff = abs(q_a - q_b)
    mean_a = a.get("mean")
    mean_b = b.get("mean_b")
    side_agree = _mean_supports_side(mean_a, line, side) and _mean_supports_side(mean_b, line, side)
    both_clear_floor = (
        _at_least(q_a, WATCH_FLOOR)
        and _at_least(q_b, WATCH_FLOOR)
    )
    if side_agree and not _exceeds(abs_diff, tolerance):
        vote = "agree"
    else:
        vote = "disagree"
    return {
        "both_clear_floor": both_clear_floor,
        "side_agree": side_agree,
        "abs_diff": abs_diff,
        "tolerance": tolerance,
        "b_vote": vote,
    }


def _reads_candidate(project_raw: dict, context: dict, reads_bits: dict) -> dict:
    payload = dict(reads_bits)
    payload.update({
        "stat": context.get("stat"),
        "dist": project_raw.get("dist"),
        "side": project_raw.get("side"),
        "line": project_raw.get("line"),
        "sd": project_raw.get("sd"),
        "var_ratio": project_raw.get("var_ratio"),
        "baseline_mean": project_raw.get("baseline_mean"),
    })
    return payload


def _engine_a_block(projected: dict) -> dict:
    return {
        "mean": projected["shrunk_mean"],
        "q_win": projected["q_win"],
        "q_push": projected["q_push"],
        "q_win_robust": projected["q_win_robust"],
        "q_push_robust": projected["q_push_robust"],
        "reliable": not projected["sample_block"] and projected.get('observation_ids_verified',False),
        "reliability_reasons": (["sample_or_distribution_block"] if projected['sample_block'] else []) +
                               ([] if projected.get('observation_ids_verified') else ['unverified_observation_identity']),
        "version": "history-v5",
        "observation_ids_verified": projected.get("observation_ids_verified",False),
    }


def _engine_b_block(reads: dict) -> dict:
    return {
        "mean": reads.get("mean_b"),
        "q_win": reads.get("q_win_b"),
        "q_push": reads.get("q_push_b"),
        "se": reads.get("se_b"),
        "abstain": reads.get("abstain"),
        "abstain_reason": reads.get("abstain_reason"),
        "abstain_detail": reads.get("abstain_detail"),
        "terms": copy.deepcopy(reads.get("terms") or {}),
        "reliable": reads.get("reliable", False),
        "version": reads.get("version"),
        "calibrated": False,
        "coverage": copy.deepcopy(reads.get("coverage") or {}),
        "quality": copy.deepcopy(reads.get("quality") or {}),
        "baseline_origin": reads.get('baseline_origin'),
        "history_through": reads.get('history_through'),
    }


def _snapshot_nested_block(raw: dict, name: str):
    if name not in raw or raw[name] is None:
        return None
    value = raw[name]
    if not isinstance(value, dict):
        raise PickemError(f"{name} must be a JSON object")
    return copy.deepcopy(value)


def _format_line(value: float) -> str:
    value = float(value)
    if abs(value - round(value)) <= 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _looks_like_number(token: str) -> bool:
    try:
        float(token)
    except (TypeError, ValueError):
        return False
    return True


def _parse_book_side(value) -> str:
    if not isinstance(value, str):
        raise PickemError("book_side must be over or under")
    side = value.strip().lower()
    if side not in BOOK_SIDES:
        raise PickemError("book_side must be over or under")
    return side


def _warn_legacy_book(label: str) -> None:
    warnings.warn(
        f"{label} has no book_side; 4-part book specs are deprecated and set SIDE_UNVERIFIED",
        DeprecationWarning,
        stacklevel=4,
    )


def _book_record(name, line, target, other, book_side, *, legacy: bool, label: str) -> dict:
    if not str(name).strip():
        raise PickemError("book spec needs a book name")
    try:
        line_f = float(line)
        target_f = float(target)
        other_f = float(other)
    except (TypeError, ValueError) as exc:
        raise PickemError("book spec line and odds must be numbers") from exc
    if legacy:
        _warn_legacy_book(label)
        side = None
    else:
        side = _parse_book_side(book_side)
    return {
        "book": str(name).strip(),
        "line": line_f,
        "target": target_f,
        "other": other_f,
        "book_side": side,
    }


def _parse_book_spec(spec: str) -> dict:
    """Book:line:target:other:side, or the deprecated Book:line:target:other."""
    if not isinstance(spec, str) or spec.count(":") < 3:
        raise PickemError("book spec must be Book:line:target_odds:other_odds:side")
    five = spec.rsplit(":", 4)
    if len(five) == 5 and five[-1].strip().lower() in BOOK_SIDES:
        name, line_s, target_s, other_s, side_s = five
        return _book_record(
            name, line_s, target_s, other_s, side_s, legacy=False, label=spec,
        )
    if len(five) == 5 and not _looks_like_number(five[-1]):
        raise PickemError("book_side must be over or under")
    four = spec.rsplit(":", 3)
    if len(four) == 4:
        name, line_s, target_s, other_s = four
        return _book_record(
            name, line_s, target_s, other_s, None, legacy=True, label=spec,
        )
    raise PickemError("book spec must be Book:line:target_odds:other_odds:side")


def _books_from_payload(raw) -> list[dict]:
    if isinstance(raw, (str, dict)) or not isinstance(raw, (list, tuple)):
        raise PickemError("books must be a list")
    books = []
    for item in raw:
        if isinstance(item, str):
            books.append(_parse_book_spec(item))
        elif isinstance(item, dict):
            try:
                name, line, target, other = item["book"], item["line"], item["target"], item["other"]
            except KeyError as exc:
                raise PickemError("book entry needs book, line, target, and other") from exc
            if "book_side" in item:
                books.append(_book_record(
                    name, line, target, other, item["book_side"],
                    legacy=False, label=str(name),
                ))
            else:
                books.append(_book_record(
                    name, line, target, other, None, legacy=True, label=str(name),
                ))
        elif isinstance(item, (list, tuple)) and len(item) == 5:
            books.append(_book_record(
                item[0], item[1], item[2], item[3], item[4],
                legacy=False, label=str(item[0]),
            ))
        elif isinstance(item, (list, tuple)) and len(item) == 4:
            books.append(_book_record(
                item[0], item[1], item[2], item[3], None, legacy=True, label=str(item[0]),
            ))
        else:
            raise PickemError(
                "book entry must be a spec string or {book, line, target, other, book_side}"
            )
    return books


def _consensus_tuples(books: list[dict]) -> list[tuple]:
    return [(book["book"], book["line"], book["target"], book["other"]) for book in books]


def _orient_books(books: list[dict], candidate_side: str) -> bool:
    """Return whether any book omitted book_side. A stated side must match."""
    unverified = False
    for book in books:
        side = book["book_side"]
        if side is None:
            unverified = True
            continue
        if side != candidate_side:
            raise PickemError(
                f"{book['book']} book_side {side} does not match candidate side {candidate_side}"
            )
    return unverified


def _direct_q_market(value) -> float:
    q_market = _finite("q_market", value)
    if not 0.0 < q_market < 1.0:
        raise PickemError("q_market must be inside (0, 1)")
    return q_market


def _market_valid_downgrade(requested, fresh: bool) -> bool:
    """An explicit no forces the market invalid. An explicit yes never upgrades it."""
    if requested is None:
        return fresh
    if isinstance(requested, bool):
        allow = requested
    else:
        allow = _as_bool(requested, "market_valid")
    if not allow:
        return False
    return fresh


def _market_checks(
    books: list[dict],
    consensus_result: dict | None,
    projected_line: float | None,
    direct_age: float | None,
    direct: bool,
) -> list[str]:
    """Which market gates passed. Absent names are the gates that did not."""
    passed = set()
    if books and consensus_result is not None and projected_line is not None:
        market_line = consensus_result.get("line")
        if market_line is not None and abs(market_line - projected_line) <= 1e-9:
            passed.add("line_match")
        if books and all(book["book_side"] is not None for book in books):
            passed.add("side_match")
        age = consensus_result.get("retrieved_minutes_ago")
        if consensus_result.get("timestamp_checked") and _timestamp_fresh(age):
            passed.add("timestamp_fresh")
        rows = consensus_result.get("rows") or []
        if rows and all(not row.get("reject_hold") for row in rows):
            passed.add("hold_ok")
        if rows and all(row.get("key") in APPROVED_BOOKS for row in rows):
            passed.add("approved_books")
    elif direct and _timestamp_fresh(direct_age):
        passed.add("timestamp_fresh")
    return [name for name in MARKET_CHECKS if name in passed]


def _as_bool(value, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("yes", "true"):
        return True
    if isinstance(value, str) and value.strip().lower() in ("no", "false"):
        return False
    raise PickemError(f"{name} must be yes or no")


def _as_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PickemError(f"{name} must be an integer")
    if int(value) != value:
        raise PickemError(f"{name} must be an integer")
    return int(value)


def _consensus_public(result: dict) -> dict:
    public = {key: value for key, value in result.items() if key != "rows"}
    public["rows"] = [
        {
            "book": row["book"],
            "line": row["line"],
            "hold": row["hold"],
            "q_mult": row["q_mult"],
            "q_market": row["q_market"],
        }
        for row in result["rows"]
    ]
    return public


def _derived_flag_names(projected: dict, consensus_result: dict | None, books_passed: bool) -> list[str]:
    """Flags pipeline counts itself. The caller must not pass these again."""
    names = []
    if books_passed and consensus_result is not None:
        for flag in consensus_result.get("flags", []):
            if flag.startswith("DISAGREE") and "DISAGREE" not in names:
                names.append("DISAGREE")
            elif flag.startswith("RETAIL_ONLY_TWO_BOOKS") and "RETAIL_ONLY_TWO_BOOKS" not in names:
                names.append("RETAIL_ONLY_TWO_BOOKS")
    if not projected["mean_supports_side"]:
        names.append("MEAN_LINE_MISMATCH")
    if "VAR_RATIO_CLAMPED" in projected["notes"]:
        names.append("VAR_RATIO_CLAMPED")
    return names


def _canon_text(value: str) -> str:
    cleaned = value.strip().lower().replace("_", " ").replace("-", " ").replace("+", " ").replace("/", " ")
    return " ".join(cleaned.split())


def _optional_side(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PickemError("side must be over or under")
    side = value.strip().lower()
    if side not in BOOK_SIDES:
        raise PickemError("side must be over or under")
    return side


def _optional_stat(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PickemError("stat must be a covered market")
    text = _canon_text(value)
    if not text:
        raise PickemError("stat must be a covered market")
    text = STAT_ALIASES.get(text, text)
    if text not in COVERED_STATS:
        raise PickemError("stat must be a covered market")
    return text


def _optional_role(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PickemError("role must be rb, wr, te, qb, g, d, f, or c")
    role = value.strip().lower()
    if role not in CONTEXT_ROLES:
        raise PickemError("role must be rb, wr, te, qb, g, d, f, or c")
    return role


def _optional_bool(value, name: str) -> bool | None:
    if value is None:
        return None
    return _as_bool(value, name)


def _optional_number(value, name: str) -> float | None:
    if value is None:
        return None
    return _finite(name, value)


def _optional_nonneg(value, name: str) -> float | None:
    number = _optional_number(value, name)
    if number is not None and number < 0:
        raise PickemError(f"{name} must be >= 0")
    return number


def _optional_share(value, name: str) -> float | None:
    """A 0–1 share, or a percent when the number is above 1.5."""
    number = _optional_nonneg(value, name)
    if number is None:
        return None
    if number > 1.5:
        number = number / 100.0
    if number > 1 + GAP_EPSILON:
        raise PickemError(f"{name} must be a share from 0 to 1 or a percent from 0 to 100")
    return number


def _optional_precip(value) -> float | None:
    """Percent 0–100. A fraction from 0 to 1 is converted to a percent."""
    number = _optional_number(value, "precip_prob")
    if number is None:
        return None
    if number < 0 or number > 100:
        raise PickemError("precip_prob must be from 0 to 100, or a fraction from 0 to 1")
    if number <= 1:
        number *= 100.0
    return number


def _optional_intensity(value) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PickemError("precip_intensity must be none, light, moderate, or heavy")
    text = value.strip().lower()
    if text not in PRECIP_INTENSITIES:
        raise PickemError("precip_intensity must be none, light, moderate, or heavy")
    return text


def _underdog_margin(spread: float, team_is_underdog: bool | None) -> float | None:
    """Positive team spread is the underdog margin. An explicit no blocks it."""
    if team_is_underdog is False:
        return None
    if team_is_underdog is True:
        return abs(spread)
    if spread > 0:
        return spread
    return None


def derive_vetoes_and_flags(candidate: dict) -> dict:
    """Stage G numeric vetoes and soft flags from optional context fields.

    An omitted field does not fire its rule. Overs-only rules ignore Unders.
    Sport rules need `stat`. The caller must not count `soft_flags_derived`
    again. Qualitative flags stay manual.
    """
    if not isinstance(candidate, dict):
        raise PickemError("candidate must be a JSON object")
    side = _optional_side(candidate.get("side"))
    stat = _optional_stat(candidate.get("stat"))
    role = _optional_role(candidate.get("role"))
    minutes = _optional_nonneg(candidate.get("minutes_tonight"), "minutes_tonight")
    ice = _optional_nonneg(candidate.get("ice_time_tonight"), "ice_time_tonight")
    snaps = _optional_share(candidate.get("snap_pct_tonight"), "snap_pct_tonight")
    routes = _optional_share(candidate.get("route_pct_tonight"), "route_pct_tonight")
    spread = _optional_number(candidate.get("spread"), "spread")
    underdog = _optional_bool(candidate.get("team_is_underdog"), "team_is_underdog")
    wind = _optional_nonneg(candidate.get("sustained_wind_mph"), "sustained_wind_mph")
    gust = _optional_nonneg(candidate.get("gust_mph"), "gust_mph")
    precip = _optional_precip(candidate.get("precip_prob"))
    intensity = _optional_intensity(candidate.get("precip_intensity"))
    snow = _optional_bool(candidate.get("snow"), "snow")
    outdoor = _optional_bool(candidate.get("outdoor"), "outdoor")
    starter = _optional_bool(candidate.get("is_starter"), "is_starter")
    back_to_back = _optional_bool(candidate.get("back_to_back"), "back_to_back")
    third_in_four = _optional_bool(candidate.get("third_in_four"), "third_in_four")
    goalie = _optional_bool(candidate.get("goalie_confirmed"), "goalie_confirmed")
    starting_qb = _optional_bool(candidate.get("expected_starting_qb"), "expected_starting_qb")
    over = side == "over"
    hard: list[str] = []
    data: list[str] = []
    thin = False
    script = False
    weather_risk = False

    def add_hard(code: str) -> None:
        if code not in hard:
            hard.append(code)

    # Unresolved venue and incomplete forecasts are not equivalent to safe weather.
    if stat in NFL_STATS | NHL_STATS:
        if outdoor is None:
            data.append("VENUE_UNCONFIRMED")
        elif outdoor and any(value is None for value in (wind, gust, precip, intensity)):
            data.append(DATA_WEATHER)

    if over and stat in NBA_STATS and minutes is not None:
        if _below(minutes, NBA_MINUTES_VETO):
            add_hard(HARD_NBA_MINUTES)
        elif _at_least(minutes, NBA_MINUTES_VETO) and _at_most(minutes, NBA_MINUTES_THIN_MAX):
            thin = True

    if over and stat in NHL_SKATER_STATS and ice is not None:
        if _below(ice, NHL_ICE_VETO):
            add_hard(HARD_NHL_ICE)
        elif _at_least(ice, NHL_ICE_VETO) and _at_most(ice, NHL_ICE_THIN_MAX):
            thin = True

    if over and stat in NFL_STATS and snaps is not None:
        if stat in NFL_TACKLE_STATS:
            if _below(snaps, NFL_SNAP_VETO):
                add_hard(HARD_NFL_SNAPS)
            if _below(snaps, NFL_TACKLE_VETO):
                add_hard(HARD_TACKLES)
            elif _at_least(snaps, NFL_TACKLE_VETO) and _below(snaps, NFL_TACKLE_THIN_MAX):
                thin = True
        elif _below(snaps, NFL_SNAP_VETO):
            add_hard(HARD_NFL_SNAPS)
        elif _at_least(snaps, NFL_SNAP_VETO) and _below(snaps, NFL_SNAP_THIN_MAX):
            thin = True

    if over and stat in NFL_STATS and role in ("wr", "te") and routes is not None:
        if _below(routes, NFL_ROUTE_VETO):
            add_hard(HARD_NFL_ROUTES)
        elif _at_least(routes, NFL_ROUTE_VETO) and _below(routes, NFL_ROUTE_THIN_MAX):
            thin = True

    if stat in NFL_PASS_STATS:
        if starting_qb is False:
            add_hard(HARD_QB)
        elif starting_qb is None:
            data.append("STARTING_QB_UNCONFIRMED")

    if stat in NHL_SAVE_STATS:
        if goalie is False:
            add_hard(HARD_SAVES)
        elif goalie is None:
            data.append("STARTING_GOALIE_UNCONFIRMED")

    if over and stat in NBA_STATS and starter is True and spread is not None:
        margin = abs(spread)
        if _at_least(margin, NBA_SPREAD_VETO):
            add_hard(HARD_NBA_SPREAD)
        elif _at_least(margin, NBA_SPREAD_SCRIPT) and _below(margin, NBA_SPREAD_VETO):
            script = True

    if over and stat in NFL_RUSH_STATS and role == "rb" and spread is not None:
        margin = _underdog_margin(spread, underdog)
        if margin is not None:
            if _at_least(margin, NFL_DOG_VETO):
                add_hard(HARD_NFL_DOG)
            elif _at_least(margin, NFL_DOG_SCRIPT) and _below(margin, NFL_DOG_VETO):
                script = True

    nfl_weather = stat in NFL_WEATHER_STATS and outdoor is not False
    outdoor_shots = stat == "shots on goal" and outdoor is True
    weather_market = nfl_weather or outdoor_shots
    if weather_market and wind is not None:
        if _at_least(wind, WIND_VETO_MPH):
            add_hard(HARD_WIND)
        elif _at_least(wind, WIND_RISK_MPH) and _below(wind, WIND_VETO_MPH):
            weather_risk = True
    if nfl_weather and gust is not None and _at_least(gust, GUST_RISK_MPH):
        weather_risk = True
    snow_cut = (
        weather_market
        and snow is True
        and precip is not None
        and intensity in HEAVY_INTENSITIES
        and _at_least(precip, PRECIP_CUT)
    )
    if snow_cut:
        add_hard(HARD_SNOW)
    if (
        nfl_weather
        and not snow_cut
        and snow is not True
        and precip is not None
        and intensity in HEAVY_INTENSITIES
        and _at_least(precip, PRECIP_CUT)
    ):
        weather_risk = True
    if (
        outdoor_shots
        and snow is not True
        and intensity in RAIN_INTENSITIES
    ):
        add_hard(HARD_NHL_RAIN)

    rest = over and (back_to_back is True or third_in_four is True)
    unconfirmed = stat == "shots on goal" and goalie is False
    soft = []
    if thin:
        soft.append("THIN_WORKLOAD")
    if script:
        soft.append("SCRIPT_RISK")
    if weather_risk:
        soft.append("WEATHER_RISK")
    if rest:
        soft.append("REST_SPOT")
    if unconfirmed:
        soft.append("UNCONFIRMED_GOALIE")
    return {
        "hard_veto_reasons": hard,
        "data_veto_reasons": data,
        "soft_flags_derived": soft,
    }


def evaluate_candidate(raw: dict, *, now=None) -> dict:
    """Project, optional consensus, grade, and rank using the raw floats.

    `--soft-flags` excludes DISAGREE, RETAIL_ONLY_TWO_BOOKS (when books are
    passed), MEAN_LINE_MISMATCH, VAR_RATIO_CLAMPED, and SIDE_UNVERIFIED.
    It also excludes THIN_WORKLOAD, SCRIPT_RISK, WEATHER_RISK, REST_SPOT, and
    UNCONFIRMED_GOALIE when context fields derive them. Do not count those
    manually. PLUS-MONEY is not a soft flag. Final hard_veto is the input OR
    any derived hard reason. Final data_veto is the input OR any derived data
    reason. NORMAL_LEFT_TAIL forces Unranked. A direct q_market requires
    retrieved_minutes_ago and must sit inside (0, 1). It cannot be combined
    with books. Book lines must match the projected line. book_side must
    match the candidate side. `tier_basis` selects q_win or q_win_robust for
    the grade, the gap, and the Unicorn check. The default is q_win.
    """
    if not isinstance(raw, dict):
        raise PickemError("pipeline candidate must be a JSON object")
    raw = dict(raw)
    tier_basis = _tier_basis(raw.pop("tier_basis", None))
    scouting = raw.pop("scouting", None)
    event_context = raw.pop('event_context',None)
    scouting_identity = {k:raw.get(k) for k in ("player_id", "team", "game_date")}
    ident = raw.pop("id", None)
    side_name = raw.pop("side_name", "target side")
    books_raw = raw.pop("books", None)
    retrieved = raw.pop("retrieved_minutes_ago", None)
    market_stamp = raw.pop('market_retrieved_at', None)
    if market_stamp is not None:
        try:
            stamp = datetime.fromisoformat(str(market_stamp).replace('Z','+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('timezone required')
            elapsed = ((now or datetime.now(timezone.utc))-stamp).total_seconds()/60
            if elapsed < 0:
                raise ValueError('future market timestamp')
            retrieved = max(elapsed, _retrieval_age(retrieved)) if retrieved is not None else elapsed
        except (ValueError, TypeError) as exc:
            raise PickemError('invalid market_retrieved_at: '+str(exc)) from exc

    q_market_in = raw.pop("q_market", None)
    market_valid_in = raw.pop("market_valid", None)
    # Research identity and diagnostic metadata are not probability-model terms.
    research_issues = [raw.pop(k) for k in (
        "availability_issue", "weather_issue", "role_window_issue", "identity_issue"
    ) if k in raw]
    raw.pop('research_merge_base',None)  # merge provenance, not model input
    raw.pop('research_soft_flags',None)  # packet merge bookkeeping, not a model term
    for k in ("team", "player_id", "event_id", "game_date", "opponent", "event_id_namespace", "event_start"):
        raw.pop(k, None)
    if "soft_flags" not in raw or "mechanisms" not in raw:
        raise PickemError("pipeline requires soft_flags and mechanisms")
    soft_flags = _as_int(raw.pop("soft_flags"), "soft_flags")
    mechanisms = _as_int(raw.pop("mechanisms"), "mechanisms")
    if soft_flags < 0 or mechanisms < 0:
        raise PickemError("soft_flags and mechanisms must be >= 0")
    for key in ("hard_veto", "data_veto", "research_checklist"):
        if key not in raw:
            raise PickemError(f"pipeline requires {key}")
    hard_veto = _as_bool(raw.pop("hard_veto"), "hard_veto")
    data_veto = _as_bool(raw.pop("data_veto"), "data_veto")
    research = _as_bool(raw.pop("research_checklist"), "research_checklist")
    context = {key: raw.pop(key) for key in CONTEXT_FIELDS if key in raw}
    if context.get('stat') is not None:
        context['stat']=_optional_stat(context['stat'])
    reads_bits = {key: raw.pop(key) for key in list(raw) if key in READS_PIPELINE_FIELDS}
    unknown = sorted(set(raw) - PROJECT_FIELDS)
    if unknown:
        raise PickemError("unknown pipeline fields: " + ", ".join(unknown))
    for key in ("dist", "side", "line", "baseline_mean", "baseline_n"):
        if key not in raw:
            raise PickemError(f"pipeline requires {key}")
    context["side"] = raw["side"]
    stage_g = derive_vetoes_and_flags(context)
    if stage_g["hard_veto_reasons"]:
        hard_veto = True
    if stage_g["data_veto_reasons"]:
        data_veto = True
    if books_raw and q_market_in is not None:
        raise PickemError("pass q_market or books, not both")

    direct_age = None
    if not books_raw:
        if q_market_in is None:
            raise PickemError("pipeline requires q_market or at least one book")
        q_market_in = _direct_q_market(q_market_in)
        if retrieved is None:
            raise PickemError("q_market requires retrieved_minutes_ago")
        direct_age = _retrieval_age(retrieved)

    projected = project(**raw)
    from scouting_engine import project_scout
    from probability_blend import combine, config_path, preview_70_30
    sport = str(ident).split("|", 1)[0] if ident else str(reads_bits.get("sport") or "UNKNOWN")
    reads_result = project_scout({**raw, **scouting_identity, "sport": sport, "stat": context.get("stat"), "scouting": scouting}, now=now)
    source_candidate={**raw,**scouting_identity,'sport':sport,'stat':context.get('stat'),'scouting':scouting}
    source_verified=False
    # Source verification belongs to A even when B abstains for thin workload
    # history. B's sample/reliability gate must not disable A's independent check.
    if isinstance(scouting,dict) and scouting.get('historical_usage'):
        from usage_baseline import verify_a
        try:source_verified=verify_a(source_candidate,now or datetime.now(timezone.utc))
        except (OSError,ValueError,KeyError,TypeError):pass
    # Researcher totals cannot become either side of a validated live mixture.
    if not source_verified:
        projected['observation_ids_verified']=False
    scope = sport + "|" + str(context.get("stat") or "UNKNOWN")
    blend = combine(projected, reads_result, config_path(SKILL_ROOT, scope), scope=scope,
                    as_of=now.date() if now else None)
    blend['preview_70_30'] = preview_70_30(projected, reads_result)
    engine_a = _engine_a_block(projected)
    engine_b = _engine_b_block(reads_result)
    from shared_context import apply as apply_context
    shared_context=apply_context(source_candidate,projected,reads_result,blend,event_context,
                                 now or datetime.now(timezone.utc))
    if shared_context.get('applied'):
        from context_validation import verify as verify_context
        shared_context['validated']=verify_context(SKILL_ROOT,scope,blend,
            (now or datetime.now(timezone.utc)).date())
    projected_line = _finite("line", raw["line"])
    books = _books_from_payload(books_raw) if books_raw else []
    side_unverified = _orient_books(books, raw["side"]) if books else False
    consensus_result = consensus(_consensus_tuples(books), retrieved) if books else None
    if books:
        market_line = consensus_result["line"]
        if abs(market_line - projected_line) > 1e-9:
            raise PickemError(
                f"market line {_format_line(market_line)} does not match "
                f"projected line {_format_line(projected_line)}"
            )
    derived = _derived_flag_names(projected, consensus_result, bool(books))
    if side_unverified:
        derived.append("SIDE_UNVERIFIED")
    cross_market = {
        "side": raw["side"],
        "line": projected_line,
        "q_market": None,
        "q_market_comparable": None,
        "retrieved_at": None,
        "closing_q_market": None,
    }
    cross = crosscheck(engine_a, reads_result if reads_result.get("reliable") else {**reads_result, "abstain": True}, cross_market)
    if cross["b_vote"] == "disagree":
        derived.append("CROSSCHECK_DISAGREE")
    g_soft = stage_g["soft_flags_derived"]
    checks = _market_checks(
        books, consensus_result, projected_line if books else None, direct_age, not books,
    )
    workload_adjusted = False  # context cannot substitute for historical samples
    out = {
        "ok": True,
        "id": ident,
        "side_name": side_name,
        "project": projected,
        "consensus": _consensus_public(consensus_result) if consensus_result else None,
        "derived_flags": derived,
        "derived_vetoes": {
            "hard_veto_reasons": stage_g["hard_veto_reasons"],
            "data_veto_reasons": stage_g["data_veto_reasons"],
        },
        "derived_soft_flags": g_soft,
        "soft_flags_passed": soft_flags,
        "soft_flags_to_grade": soft_flags + len(derived) + len(g_soft),
        "market_checks": checks,
        "research_issues": research_issues,
        "tier_basis": tier_basis,
        "engine_a": engine_a,
        "engine_b": engine_b,
        "crosscheck": cross,
        "blend": blend,
        "shared_context":shared_context,
    }
    if books and "q_market" not in consensus_result:
        out["final_rank"] = "Unranked"
        out["reason"] = "INVALID_MARKET"
        out["grade"] = None
        out["market"] = cross_market
        return out
    if books:
        q_market = consensus_result["q_market"]
        market_valid = _market_valid_downgrade(
            market_valid_in, bool(consensus_result["market_valid"]),
        )
    else:
        q_market = q_market_in
        market_valid = _market_valid_downgrade(market_valid_in, _timestamp_fresh(direct_age))
    # Published grades always integrate uncertainty. Point estimates stay visible
    # as diagnostics. No evidence-backed B weights means explicit A-only fallback.
    q_model, q_push_grade = shared_context['q_win'], shared_context['q_push']
    baseline_only = shared_context.get('baseline_only') if source_verified else None
    if baseline_only:
        q_model, q_push_grade = baseline_only['q_win'], baseline_only['q_push']
    if not shared_context['eligible'] and not baseline_only:
        out.update(final_rank='Unranked',reason=shared_context['reason'],grade=None)
        return out
    tier_basis = "q_win_robust"
    out["tier_basis"] = tier_basis
    decided = decide(
        q_model, q_market, soft_flags + len(derived) + len(g_soft),
        projected["current_role_n"],
        mechanisms, hard_veto, data_veto, market_valid, research, bool(raw.get("role_change")),
        q_push_grade, workload_adjusted, bool(projected["distribution_block"]),
    )
    decided["tier_basis"] = tier_basis
    if decided["final_rank"] == "Tier 1" and (not blend["validated"] or
            not reads_result.get("reliable") or not engine_a['reliable'] or
            (shared_context['applied'] and not shared_context['validated'])):
        decided["final_rank"] = "Tier 2"
        decided["reason"] = "TIER1_REQUIRES_RELIABLE_ENGINES_AND_VALIDATED_BLEND"
    if baseline_only:
        decided['final_rank'] = _lower_final(decided['final_rank'], 'Watchlist')
        if decided['final_rank'] == 'Watchlist':
            decided['reason'] = 'CONTEXT_UNSUPPORTED_BASELINE_ONLY'
        out['tier_basis'] = 'unadjusted_baseline_diagnostic'
        decided['tier_basis'] = 'unadjusted_baseline_diagnostic'
    out["final_rank"] = decided["final_rank"]
    if not source_verified and out['final_rank'] in ('Tier 1','Tier 2','Tier 3'):
        out['final_rank']='Watchlist'
        decided['final_rank']='Watchlist'
        decided['reason']='SOURCE_HISTORY_NOT_VERIFIED'
    out["reason"] = "NORMAL_LEFT_TAIL" if projected["distribution_block"] else decided.get("reason")
    out["grade"] = decided
    cross_market["q_market"] = q_market
    cross_market["q_market_comparable"] = decided.get("q_market_comparable")
    out["market"] = cross_market
    if out["final_rank"] == "Unranked" and not out.get("reason"):
        out["reason"] = _block_reason(out)
    return out


def _print_pipeline(result: dict) -> None:
    print(f"id={result['id'] if result.get('id') else ''}")
    print("project:")
    _print_project(result["project"])
    consensus_result = result.get("consensus")
    if consensus_result:
        print("consensus:")
        if "q_market" in consensus_result:
            print(
                f"consensus q_market={pct(consensus_result['q_market'])} "
                f"q_market_raw={_raw(consensus_result['q_market'])} via {consensus_result['rule']}"
            )
        for flag in consensus_result.get("flags", []):
            print(flag)
        print(f"market_valid={'yes' if consensus_result.get('market_valid') else 'no'}")
    derived = result["derived_flags"]
    print("derived_flags=" + (",".join(derived) if derived else "none"))
    vetoes = result.get("derived_vetoes") or {}
    hard_names = vetoes.get("hard_veto_reasons") or []
    data_names = vetoes.get("data_veto_reasons") or []
    print("derived_vetoes=" + (",".join(hard_names) if hard_names else "none"))
    print("derived_data_vetoes=" + (",".join(data_names) if data_names else "none"))
    g_soft = result.get("derived_soft_flags") or []
    print("derived_soft_flags=" + (",".join(g_soft) if g_soft else "none"))
    checks = result.get("market_checks") or []
    print("market_checks=" + (",".join(checks) if checks else "none"))
    print(
        f"soft_flags_passed={result['soft_flags_passed']} "
        f"soft_flags_to_grade={result['soft_flags_to_grade']}"
    )
    print(f"tier_basis={result.get('tier_basis', 'q_win')}")
    if result.get("grade"):
        print("grade:")
        _print_grade(result["grade"])
        print(f"mechanisms={result['grade'].get('mechanisms')}")
    if result.get("reason"):
        print(f"reason={result['reason']}")
    print(f"final_rank={result['final_rank']}")


def _run_batch(stream: str) -> int:
    failed = 0
    for line_no, line in enumerate(stream.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            failed += 1
            print(json.dumps({
                "ok": False,
                "line": line_no,
                "final_rank": "Unranked",
                "error": f"invalid JSON: {exc}",
            }))
            continue
        try:
            print(json.dumps(evaluate_candidate(payload)))
        except PickemError as exc:
            failed += 1
            ident = payload.get("id") if isinstance(payload, dict) else None
            print(json.dumps({
                "ok": False,
                "id": ident,
                "line": line_no,
                "final_rank": "Unranked",
                "error": str(exc),
            }))
    return 1 if failed else 0


class _ScanParseError:
    """One prep line that was not JSON. Not a candidate."""

    def __init__(self, reason: str):
        self.reason = reason


_SCAN_FIELDS = (
    "id", "side", "q_win", "q_market_comparable", "q_gap",
    "shrunk_mean", "current_role_n", "sample_block", "reason",
)


def _normalize_triggers(triggers) -> set[str]:
    if triggers is None:
        return set()
    if isinstance(triggers, str):
        triggers = [triggers]
    if not isinstance(triggers, (list, tuple, set)):
        raise PickemError("triggers must be a list of strings")
    found = set()
    for item in triggers:
        if not isinstance(item, str) or not item.strip():
            raise PickemError("triggers must be non-empty strings")
        found.add(item.strip())
    return found


def _row_trigger_flag(value) -> bool:
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("", "no", "false", "0"):
            return False
        return True
    raise PickemError("trigger must be yes or no")


def _pair_key(ident, side, line_no: int) -> str:
    if isinstance(ident, str) and ident:
        if side in ("over", "under") and ident.endswith("|" + side):
            return ident[: -(len(side) + 1)]
        return ident
    return f"\0{line_no}"


def _is_trigger_control(payload: dict) -> bool:
    if "triggers" not in payload:
        return False
    return "dist" not in payload and "side" not in payload and "line" not in payload


def _scan_bounds(min_q_win, max_abs_gap, min_market, both_sides_floor, cap, tier_basis):
    min_q_win = _finite("min_q_win", min_q_win)
    max_abs_gap = _finite("max_abs_gap", max_abs_gap)
    min_market = _finite("min_market", min_market)
    both_sides_floor = _finite("both_sides_floor", both_sides_floor)
    cap_n = _as_int(cap, "cap")
    if cap_n < 0:
        raise PickemError("cap must be >= 0")
    if max_abs_gap < 0:
        raise PickemError("max_abs_gap must be >= 0")
    for name, value in (
        ("min_q_win", min_q_win),
        ("min_market", min_market),
        ("both_sides_floor", both_sides_floor),
    ):
        if value < 0 or value > 1:
            raise PickemError(f"{name} must be between 0 and 1")
    return min_q_win, max_abs_gap, min_market, both_sides_floor, cap_n, _tier_basis(tier_basis)


def _keep_reason(q_basis, q_gap, q_market, min_q_win, max_abs_gap, min_market):
    """Why a graded side clears the numeric screen, or None."""
    if q_basis is None or q_gap is None or q_market is None:
        return None
    if _at_least(q_basis, min_q_win):
        return "q_win"
    if _at_most(abs(q_gap), max_abs_gap) and _at_least(q_market, min_market):
        return "q_gap"
    return None


def _block_reason(result: dict) -> str:
    project = result.get("project") or {}
    if project.get("sample_block"):
        notes = project.get("notes") or []
        for code in ("NORMAL_LEFT_TAIL", "NO_CURRENT_ROLE", "SAMPLE_BLOCK"):
            if code in notes:
                return code
        if result.get("reason"):
            return str(result["reason"])
        return "SAMPLE_BLOCK"
    if result.get("reason"):
        return str(result["reason"])
    if result.get("research_issues"):
        return ",".join(dict.fromkeys(result["research_issues"]))
    data = (result.get("derived_vetoes") or {}).get("data_veto_reasons") or []
    if data:
        return ",".join(str(item) for item in data)
    flags = (result.get("consensus") or {}).get("flags") or []
    if "STALE" in flags:
        return "STALE"
    if "TIMESTAMP_MISSING" in flags:
        return "TIMESTAMP_MISSING"
    grade = result.get("grade") or {}
    if grade.get("market_valid") is False:
        return "INVALID_MARKET"
    consensus = result.get("consensus")
    if consensus is not None and consensus.get("market_valid") is False:
        return "INVALID_MARKET"
    if grade.get("data_veto"):
        return "INPUT_DATA_VETO"
    return "Unranked"


def _public_scan_row(row: dict) -> dict:
    return {key: row[key] for key in _SCAN_FIELDS}


def _blank_scan_row(ident, side, reason: str) -> dict:
    return {
        "id": ident if isinstance(ident, str) else None,
        "side": side if isinstance(side, str) else None,
        "q_win": None,
        "q_market_comparable": None,
        "q_gap": None,
        "shrunk_mean": None,
        "current_role_n": None,
        "sample_block": None,
        "reason": reason,
        "researchable": False,
        "triggered": False,
        "numeric": False,
        "q_basis": None,
        "pair_key": "",
    }


def _scan_sort_key(row: dict):
    q_win = row.get("q_win")
    q_win = q_win if isinstance(q_win, (int, float)) and not isinstance(q_win, bool) else -1.0
    gap = row.get("q_gap")
    gap_abs = abs(gap) if isinstance(gap, (int, float)) and not isinstance(gap, bool) else 0.0
    return (-q_win, gap_abs, str(row.get("id") or ""), str(row.get("side") or ""))


def _pairs_under_floor(rows: list[dict], floor: float) -> set[str]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["pair_key"], []).append(row)
    dropped = set()
    for key, group in groups.items():
        by_side: dict[str, list[dict]] = {}
        for row in group:
            by_side.setdefault(row["side"], []).append(row)
        if "over" not in by_side or "under" not in by_side:
            continue
        graded = by_side["over"] + by_side["under"]
        if all(
            row["q_basis"] is not None and _below(row["q_basis"], floor)
            for row in graded
        ):
            dropped.add(key)
    return dropped


def _evaluate_scan_payload(payload, line_no: int, basis: str, triggers: set[str]) -> dict:
    if isinstance(payload, _ScanParseError):
        return _blank_scan_row(None, None, payload.reason)
    if not isinstance(payload, dict):
        return _blank_scan_row(None, None, "pipeline candidate must be a JSON object")
    ident = payload.get("id")
    side = payload.get("side")
    pair = _pair_key(ident, side, line_no)
    triggered = _triggered_row(ident, pair, False, triggers)
    try:
        raw = dict(payload)
        row_flag = _row_trigger_flag(raw.pop("trigger", None))
        triggered = _triggered_row(ident, pair, row_flag, triggers)
        raw["mechanisms"] = SCAN_OPTIMISTIC_MECHANISMS
        raw["soft_flags"] = SCAN_OPTIMISTIC_SOFT_FLAGS
        raw["tier_basis"] = basis
        result = evaluate_candidate(raw)
    except PickemError as exc:
        row = _blank_scan_row(ident, side, str(exc))
        row["pair_key"] = pair
        row["triggered"] = triggered
        return row
    project = result.get("project") or {}
    grade = result.get("grade") or {}
    sample_block = bool(project.get("sample_block"))
    blocked = sample_block or result.get("final_rank") == "Unranked"
    row = {
        "id": ident if isinstance(ident, str) else result.get("id"),
        "side": side if isinstance(side, str) else None,
        "q_win": project.get("q_win"),
        "q_market_comparable": grade.get("q_market_comparable") if grade else None,
        "q_gap": grade.get("q_gap") if grade else None,
        "shrunk_mean": project.get("shrunk_mean"),
        "current_role_n": project.get("current_role_n"),
        "sample_block": sample_block if project else None,
        "reason": _block_reason(result) if blocked else None,
        "researchable": not blocked,
        "triggered": triggered,
        "numeric": False,
        "q_basis": grade.get("q_model") if grade else project.get("q_win_robust" if basis == "q_win_robust" else "q_win"),
        "pair_key": pair,
    }
    if not project:
        row["sample_block"] = None
    return row


def _triggered_row(ident, pair_key: str, row_flag: bool, triggers: set[str]) -> bool:
    if row_flag:
        return True
    if isinstance(ident, str) and ident in triggers:
        return True
    if pair_key and not pair_key.startswith("\0") and pair_key in triggers:
        return True
    return False


def scan_candidates(
    payloads,
    triggers=None,
    min_q_win: float = SCAN_MIN_Q_WIN,
    max_abs_gap: float = SCAN_MAX_ABS_GAP,
    min_market: float = SCAN_MIN_MARKET,
    both_sides_floor: float = SCAN_BOTH_SIDES_FLOOR,
    cap: int = SCAN_CAP,
    tier_basis: str | None = None,
) -> dict:
    """Rank prep rows. Placeholders do not publish a grade.

    `mechanisms=2` and `soft_flags=0` are filled in before `evaluate_candidate`.
    Market-line checks and derived vetoes still run there. The default tier
    basis is `q_win_robust`. Printed `q_win` is the plug-in probability. The 0.56 cut,
    the gap, and the 0.52 both-sides floor use the tier-basis probability.
    """
    if not isinstance(payloads, (list, tuple)):
        raise PickemError("scan expects one JSON object per line")
    min_q_win, max_abs_gap, min_market, floor, cap_n, basis = _scan_bounds(
        min_q_win, max_abs_gap, min_market, both_sides_floor, cap, tier_basis,
    )
    trigger_set = _normalize_triggers(triggers)
    items = []
    for payload in payloads:
        if isinstance(payload, dict) and _is_trigger_control(payload):
            trigger_set |= _normalize_triggers(payload.get("triggers"))
            continue
        items.append(payload)

    scored = []
    unresearchable = []
    for line_no, payload in enumerate(items, start=1):
        row = _evaluate_scan_payload(payload, line_no, basis, trigger_set)
        if row["researchable"]:
            scored.append(row)
        else:
            unresearchable.append(row)

    dropped_pairs = _pairs_under_floor(scored, floor)
    kept = []
    for row in scored:
        if row["pair_key"] in dropped_pairs and not row["triggered"]:
            continue
        reason = _keep_reason(
            row["q_basis"], row["q_gap"], row["q_market_comparable"],
            min_q_win, max_abs_gap, min_market,
        )
        if reason:
            row["reason"] = reason
            row["numeric"] = True
            kept.append(row)
        elif row["triggered"]:
            row["reason"] = "trigger"
            row["numeric"] = False
            kept.append(row)

    numeric_rows = sorted((row for row in kept if row["numeric"]), key=_scan_sort_key)
    chosen = list(numeric_rows[:cap_n])
    chosen_ids = {id(row) for row in chosen}
    for row in kept:
        if row["triggered"] and id(row) not in chosen_ids:
            chosen.append(row)
    chosen.sort(key=_scan_sort_key)
    shortlist = [_public_scan_row(row) for row in chosen]
    blocked = [_public_scan_row(row) for row in unresearchable]
    # Research discovery must not depend on publication confirmations.
    resolvable = {"VENUE_UNCONFIRMED", "WEATHER_NOT_CHECKED", "STARTING_QB_UNCONFIRMED",
                  "STARTING_GOALIE_UNCONFIRMED", "CONTEXT_UNRESOLVED", "STALE", "TIMESTAMP_MISSING",
                  "STATUS_NOT_VERIFIED", "VENUE_OR_FORECAST_UNVERIFIED"}
    pending = []
    for row in unresearchable:
        codes = set(str(row.get("reason") or "").split(","))
        if (not row.get("sample_block") and codes & resolvable and
                (row["triggered"] or row.get("q_basis") is not None and row["q_basis"] >= min_q_win)):
            pending.append({**_public_scan_row(row), "publication_eligible": False,
                            "verification_gaps": sorted(codes), "discovery_basis": basis})
    research_candidates = [{**r, "publication_eligible": False, "verification_gaps": []}
                           for r in shortlist] + sorted(pending, key=_scan_sort_key)
    return {
        "tier_basis": basis,
        "counts": {
            "scanned": len(items),
            "unresearchable": len(blocked),
            "shortlisted": len(shortlist),
        },
        "shortlist": shortlist,
        "research_candidates": research_candidates,
        "unresearchable": blocked,
    }


def scan_stream(text: str, **kwargs) -> dict:
    """Parse prep JSONL and return the shortlist document."""
    payloads = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            payloads.append(json.loads(line))
        except json.JSONDecodeError as exc:
            payloads.append(_ScanParseError(f"invalid JSON: {exc}"))
    return scan_candidates(payloads, **kwargs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    devig_p = sub.add_parser("devig")
    devig_p.add_argument("--target", type=float, required=True)
    devig_p.add_argument("--other", type=float, required=True)

    cons = sub.add_parser("consensus")
    cons.add_argument("--side-name", default="target side")
    cons.add_argument("--retrieved-minutes-ago", type=float)
    cons.add_argument(
        "--book", action="append", required=True,
        help="Book:line:target_odds:other_odds:side, or deprecated Book:line:target_odds:other_odds. "
             "Every book must use the same line. side is over or under.",
    )
    cons.add_argument("--json", action="store_true")

    proj = sub.add_parser("project")
    proj.add_argument("--dist", choices=["poisson", "negbin", "normal"], required=True)
    proj.add_argument("--side", choices=["over", "under"], required=True)
    proj.add_argument("--line", type=float, required=True)
    proj.add_argument("--baseline-mean", type=float, required=True)
    proj.add_argument("--baseline-n", type=float, required=True)
    proj.add_argument("--recent-mean", type=float)
    proj.add_argument("--recent-n", type=float)
    proj.add_argument("--season-n", type=float)
    proj.add_argument("--workload-baseline", type=float)
    proj.add_argument("--workload-expected", type=float)
    proj.add_argument("--rate-baseline", type=float)
    proj.add_argument("--rate-expected", type=float)
    proj.add_argument("--opponent-factor", type=float, default=1.0)
    proj.add_argument("--pace-factor", type=float, default=1.0)
    proj.add_argument("--role-change", action="store_true")
    proj.add_argument("--funnel-channels", type=int, default=0)
    proj.add_argument("--sd", type=float)
    proj.add_argument("--var-ratio", type=float)
    proj.add_argument(
        "--prior-mean", type=float,
        help="Prior-season rate in the same role. Requires --prior-n. Default off.",
    )
    proj.add_argument(
        "--prior-n", type=float,
        help="Prior-season games in that role. Capped at 20. Requires --prior-mean.",
    )
    proj.add_argument("--json", action="store_true")

    grd = sub.add_parser("grade")
    grd.add_argument("--q-model", type=float, required=True)
    grd.add_argument("--q-market", type=float, required=True)
    grd.add_argument("--q-push", type=float, default=0.0)
    grd.add_argument("--soft-flags", type=int, required=True)
    grd.add_argument("--current-role-n", type=float, required=True)
    grd.add_argument("--role-change", action="store_true")
    grd.add_argument("--workload-adjusted", action="store_true")
    grd.add_argument("--normal-left-tail", choices=["yes", "no"], default="no")
    grd.add_argument("--json", action="store_true")

    rank_p = sub.add_parser("rank")
    rank_p.add_argument("--q-model", type=float, required=True)
    rank_p.add_argument("--q-market", type=float, required=True)
    rank_p.add_argument("--q-push", type=float, default=0.0)
    rank_p.add_argument("--soft-flags", type=int, required=True)
    rank_p.add_argument("--current-role-n", type=float, required=True)
    rank_p.add_argument("--mechanisms", type=int, required=True)
    rank_p.add_argument("--hard-veto", choices=["yes", "no"], required=True)
    rank_p.add_argument("--data-veto", choices=["yes", "no"], required=True)
    rank_p.add_argument("--market-valid", choices=["yes", "no"], required=True)
    rank_p.add_argument("--research-checklist", choices=["yes", "no"], required=True)
    rank_p.add_argument("--role-change", action="store_true")
    rank_p.add_argument("--workload-adjusted", action="store_true")
    rank_p.add_argument("--normal-left-tail", choices=["yes", "no"], default="no")
    rank_p.add_argument("--json", action="store_true")

    pipe = sub.add_parser(
        "pipeline",
        help="Project, optional consensus, grade, and rank in one call.",
        description=(
            "Optional context fields derive Stage G hard vetoes and soft flags. "
            "Final hard_veto is --hard-veto OR those reasons. "
            "Derived soft flags are added to --soft-flags. Do not count them manually."
        ),
    )
    pipe.add_argument("--batch", action="store_true", help="Read one JSON candidate per line from stdin.")
    pipe.add_argument("--stdin", action="store_true")
    pipe.add_argument("--json", action="store_true")
    pipe.add_argument("--dist", choices=["poisson", "negbin", "normal"])
    pipe.add_argument("--side", choices=["over", "under"])
    pipe.add_argument("--line", type=float)
    pipe.add_argument("--baseline-mean", type=float)
    pipe.add_argument("--baseline-n", type=float)
    pipe.add_argument("--recent-mean", type=float)
    pipe.add_argument("--recent-n", type=float)
    pipe.add_argument("--season-n", type=float)
    pipe.add_argument("--workload-baseline", type=float)
    pipe.add_argument("--workload-expected", type=float)
    pipe.add_argument("--rate-baseline", type=float)
    pipe.add_argument("--rate-expected", type=float)
    pipe.add_argument("--opponent-factor", type=float, default=1.0)
    pipe.add_argument("--pace-factor", type=float, default=1.0)
    pipe.add_argument("--role-change", action="store_true")
    pipe.add_argument("--funnel-channels", type=int, default=0)
    pipe.add_argument("--sd", type=float)
    pipe.add_argument("--var-ratio", type=float)
    pipe.add_argument(
        "--prior-mean", type=float,
        help="Prior-season rate in the same role. Requires --prior-n. Default off.",
    )
    pipe.add_argument(
        "--prior-n", type=float,
        help="Prior-season games in that role. Capped at 20. Requires --prior-mean.",
    )
    pipe.add_argument(
        "--tier-basis", choices=["q_win", "q_win_robust"], default="q_win_robust",
        help="Probability used for tiers, the gap, and the Unicorn check. "
             "Default q_win. Both probabilities are always printed.",
    )
    pipe.add_argument(
        "--q-market", type=float,
        help="Direct de-vigged price inside (0, 1). Requires --retrieved-minutes-ago. "
             "Do not combine with --book.",
    )
    pipe.add_argument(
        "--book", action="append",
        help="Book:line:target_odds:other_odds:side, or deprecated Book:line:target_odds:other_odds. "
             "The line must match --line and side must match --side.",
    )
    pipe.add_argument(
        "--retrieved-minutes-ago", type=float,
        help="Required with --q-market. Age over 30 minutes makes that market invalid.",
    )
    pipe.add_argument("--side-name", default="target side")
    pipe.add_argument("--soft-flags", type=int)
    pipe.add_argument("--mechanisms", type=int)
    pipe.add_argument("--hard-veto", choices=["yes", "no"])
    pipe.add_argument("--data-veto", choices=["yes", "no"])
    pipe.add_argument(
        "--market-valid", choices=["yes", "no"],
        help="Downgrade only. no forces an invalid market. yes never upgrades a stale price.",
    )
    pipe.add_argument("--research-checklist", choices=["yes", "no"])
    pipe.add_argument("--stat", help="Covered market. Sport rules do not fire without it.")
    pipe.add_argument("--minutes-tonight", type=float, help="NBA minutes.")
    pipe.add_argument("--ice-time-tonight", type=float, help="NHL ice time in minutes.")
    pipe.add_argument("--snap-pct-tonight", type=float, help="NFL snap share, 0–1 or a percent.")
    pipe.add_argument("--route-pct-tonight", type=float, help="WR/TE route share, 0–1 or a percent.")
    pipe.add_argument("--spread", type=float, help="Signed team spread. Negative means favored.")
    pipe.add_argument("--team-is-underdog", choices=["yes", "no"])
    pipe.add_argument("--sustained-wind-mph", type=float)
    pipe.add_argument("--gust-mph", type=float)
    pipe.add_argument("--precip-prob", type=float, help="Percent 0–100, or a fraction 0–1.")
    pipe.add_argument("--precip-intensity", choices=["none", "light", "moderate", "heavy"])
    pipe.add_argument("--snow", choices=["yes", "no"])
    pipe.add_argument("--outdoor", choices=["yes", "no"])
    pipe.add_argument("--is-starter", choices=["yes", "no"])
    pipe.add_argument("--back-to-back", choices=["yes", "no"])
    pipe.add_argument("--third-in-four", choices=["yes", "no"])
    pipe.add_argument("--goalie-confirmed", choices=["yes", "no"])
    pipe.add_argument("--expected-starting-qb", choices=["yes", "no"])
    pipe.add_argument("--role", choices=list(CONTEXT_ROLES))

    scan_p = sub.add_parser(
        "scan",
        help="Prefilter prep JSONL into a ranked shortlist.",
        description=(
            "Read prep output from stdin, one pipeline object per line. "
            "Each row is evaluate_candidate with mechanisms=2 and soft_flags=0. "
            "Those placeholders are not the published grade. "
            "The default tier basis is q_win. "
            "Market-line checks and derived vetoes still run."
        ),
    )
    scan_p.add_argument("--stdin", action="store_true", help="Read prep JSONL from stdin.")
    scan_p.add_argument("--min-q-win", type=float, default=SCAN_MIN_Q_WIN,
                        help="Keep a side at or above this tier-basis probability. Default 0.56.")
    scan_p.add_argument("--max-abs-gap", type=float, default=SCAN_MAX_ABS_GAP,
                        help="Gap clause: absolute q_gap at or under this. Default 0.06.")
    scan_p.add_argument("--min-market", type=float, default=SCAN_MIN_MARKET,
                        help="Gap clause: q_market_comparable at or above this. Default 0.54.")
    scan_p.add_argument("--both-sides-floor", type=float, default=SCAN_BOTH_SIDES_FLOOR,
                        help="Drop a player-stat when Over and Under are both under this. Default 0.52.")
    scan_p.add_argument("--cap", type=int, default=SCAN_CAP,
                        help="Maximum numeric rows per slate. Triggers can exceed it. Default 40.")
    scan_p.add_argument("--trigger", action="append", default=None,
                        help="Role or availability id. Repeatable. Full id or id without the side.")
    scan_p.add_argument("--tier-basis", choices=["q_win", "q_win_robust"], default=None,
                        help="Probability for the cut, the gap, and the both-sides floor. Default q_win.")

    log_p = sub.add_parser("log")
    log_p.add_argument("--stdin", action="store_true", help="Read snapshot JSON from stdin.")
    log_p.add_argument(
        "--batch", action="store_true",
        help="Read one snapshot JSON object per line. Requires --stdin. One process for the slate.",
    )
    log_p.add_argument("--path", help="Snapshot file. Default: data/prop_snapshots.jsonl in the skill folder.")

    args = ap.parse_args()
    try:
        if args.cmd == "devig":
            row = devig(args.target, args.other)
            print(f"p_target={pct(row['p_target'])} p_other={pct(row['p_other'])} hold={pct(row['hold'])}")
            print(f"q_mult={pct(row['q_mult'])} q_market={pct(row['q_market'])}")
            if row["reject_hold"]:
                print("REJECT: hold above 8.25%")
            if row["target_plus_money"]:
                print("FLAG: chosen side is American plus-money or below 50% before the hold adjustment")
        elif args.cmd == "consensus":
            parsed = [_parse_book_spec(spec) for spec in args.book]
            result = consensus(_consensus_tuples(parsed), args.retrieved_minutes_ago)
            if args.json:
                public = {k: v for k, v in result.items() if k != "rows"}
                public["rows"] = [
                    {"book": row["book"], "line": row["line"], "hold": row["hold"], "q_market": row["q_market"]}
                    for row in result["rows"]
                ]
                print(json.dumps(public))
                return
            print(f"{args.side_name}:")
            for row in result["rows"]:
                note = "  EXCLUDED (hold > 8.25%)" if row["reject_hold"] else ""
                print(
                    f"  {row['book']}: hold={pct(row['hold'])} q_mult={pct(row['q_mult'])} "
                    f"q_market={pct(row['q_market'])}{note}"
                )
            if "q_market" in result:
                print(
                    f"consensus q_market={pct(result['q_market'])} "
                    f"q_market_raw={_raw(result['q_market'])} via {result['rule']}"
                )
            for flag in result["flags"]:
                print(flag)
            print(f"market_valid={'yes' if result.get('market_valid') else 'no'}")
        elif args.cmd == "project":
            projected = project(
                args.dist, args.side, args.line, args.baseline_mean, args.baseline_n,
                args.recent_mean, args.recent_n, args.season_n, args.workload_baseline,
                args.workload_expected, args.rate_baseline, args.rate_expected,
                args.opponent_factor, args.pace_factor, args.role_change, args.sd, args.var_ratio,
                funnel_channels=args.funnel_channels,
                prior_mean=args.prior_mean, prior_n=args.prior_n,
            )
            if args.json:
                print(json.dumps(projected))
            else:
                _print_project(projected)
        elif args.cmd == "grade":
            scored = grade(
                args.q_model, args.q_market, args.soft_flags, args.current_role_n,
                args.role_change, args.q_push, args.workload_adjusted,
                args.normal_left_tail == "yes",
            )
            if args.json:
                print(json.dumps(scored))
            else:
                _print_grade(scored)
        elif args.cmd == "rank":
            decided = decide(
                args.q_model, args.q_market, args.soft_flags, args.current_role_n,
                args.mechanisms, args.hard_veto == "yes", args.data_veto == "yes",
                args.market_valid == "yes", args.research_checklist == "yes",
                args.role_change, args.q_push, args.workload_adjusted,
                args.normal_left_tail == "yes",
            )
            if args.json:
                print(json.dumps(decided))
            else:
                _print_grade(decided)
                print(f"mechanisms={decided['mechanisms']}")
                print(f"final_rank={decided['final_rank']}")
        elif args.cmd == "pipeline":
            if args.batch:
                if not args.stdin:
                    raise PickemError("pipeline --batch requires --stdin")
                code = _run_batch(sys.stdin.read())
                if code:
                    raise SystemExit(code)
            else:
                missing = [
                    name for name in (
                        "dist", "side", "line", "baseline_mean", "baseline_n",
                        "soft_flags", "mechanisms", "hard_veto", "data_veto", "research_checklist",
                    )
                    if getattr(args, name) is None
                ]
                if missing:
                    raise PickemError("pipeline requires " + ", ".join(missing))
                raw = {
                    "dist": args.dist,
                    "side": args.side,
                    "line": args.line,
                    "baseline_mean": args.baseline_mean,
                    "baseline_n": args.baseline_n,
                    "opponent_factor": args.opponent_factor,
                    "pace_factor": args.pace_factor,
                    "role_change": args.role_change,
                    "funnel_channels": args.funnel_channels,
                    "soft_flags": args.soft_flags,
                    "mechanisms": args.mechanisms,
                    "hard_veto": args.hard_veto,
                    "data_veto": args.data_veto,
                    "research_checklist": args.research_checklist,
                    "side_name": args.side_name,
                    "tier_basis": args.tier_basis,
                }
                for name in (
                    "recent_mean", "recent_n", "season_n", "workload_baseline", "workload_expected",
                    "rate_baseline", "rate_expected", "sd", "var_ratio", "prior_mean", "prior_n",
                ):
                    value = getattr(args, name)
                    if value is not None:
                        raw[name] = value
                if args.book and args.q_market is not None:
                    raise PickemError("pass q_market or books, not both")
                if args.book:
                    raw["books"] = list(args.book)
                elif args.q_market is not None:
                    raw["q_market"] = args.q_market
                else:
                    raise PickemError("pipeline requires q_market or at least one book")
                if args.retrieved_minutes_ago is not None:
                    raw["retrieved_minutes_ago"] = args.retrieved_minutes_ago
                if args.market_valid is not None:
                    raw["market_valid"] = args.market_valid
                for name in CONTEXT_FIELDS:
                    value = getattr(args, name)
                    if value is not None:
                        raw[name] = value
                result = evaluate_candidate(raw)
                if args.json:
                    print(json.dumps(result))
                else:
                    _print_pipeline(result)
        elif args.cmd == "scan":
            if not args.stdin:
                raise PickemError("scan requires --stdin")
            result = scan_stream(
                sys.stdin.read(),
                triggers=args.trigger,
                min_q_win=args.min_q_win,
                max_abs_gap=args.max_abs_gap,
                min_market=args.min_market,
                both_sides_floor=args.both_sides_floor,
                cap=args.cap,
                tier_basis=args.tier_basis,
            )
            print(json.dumps(result))
        elif args.cmd == "log":
            if args.batch and not args.stdin:
                raise PickemError("log --batch requires --stdin")
            if not args.stdin:
                raise PickemError("log requires --stdin and one JSON object")
            destination_path = Path(args.path) if args.path else None
            if args.batch:
                rows = []
                for line_no, line in enumerate(sys.stdin.read().splitlines(), start=1):
                    if not line.strip():
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise PickemError(
                            f"snapshot JSON is invalid on line {line_no}: {exc}"
                        ) from exc
                destination, count = append_snapshots(rows, destination_path)
                print(f"logged={count} path={destination}")
            else:
                try:
                    payload = json.loads(sys.stdin.read())
                except json.JSONDecodeError as exc:
                    raise PickemError(f"snapshot JSON is invalid: {exc}") from exc
                destination = append_snapshot(payload, destination_path)
                print(f"logged=1 path={destination}")
    except PickemError as exc:
        raise SystemExit(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
