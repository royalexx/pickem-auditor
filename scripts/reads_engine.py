"""Legacy read-bucket diagnostics; not the production Engine B. Standard library only."""

import math
from statistics import NormalDist

MIN_BUCKET_GAMES = 5
VAR_RATIO_POISSON = 1.10
GAP_EPSILON = 1e-9

NFL_RECEIVING_STATS = frozenset({"receptions", "receiving yards"})


class ReadsError(ValueError):
    """Invalid reads-engine input."""


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ReadsError(f"{name} must be a finite number")
    return float(value)


def _clip01(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ReadsError(f"{label} is not finite")
    return min(1.0, max(0.0, value))


def _negbin_rejected(var_ratio: float) -> bool:
    return var_ratio <= VAR_RATIO_POISSON + GAP_EPSILON


def _pois_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(k * math.log(lam) - lam - math.lgamma(k + 1))


def _nb_pmf(k: int, mu: float, r: float) -> float:
    if mu <= 0:
        return 1.0 if k == 0 else 0.0
    n = mu / (r - 1)
    p = 1 / r
    return math.exp(
        math.lgamma(k + n) - math.lgamma(n) - math.lgamma(k + 1)
        + n * math.log(p) + k * math.log(1 - p)
    )


def _side_probs(dist: str, mu: float, line: float, side: str, sd=None, r=None):
    mu = _finite("mean", mu)
    line = _finite("line", line)
    if mu <= 0:
        raise ReadsError("mean must be positive")
    if line < 0:
        raise ReadsError("line must be >= 0")
    if side not in ("over", "under"):
        raise ReadsError("side must be over or under")
    whole = abs(line - round(line)) < 1e-9
    over_threshold = int(math.floor(line)) + 1

    if dist == "normal":
        sd = _finite("sd", sd)
        if sd <= 0:
            raise ReadsError("sd must be positive")
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
            raise ReadsError("var_ratio is 1.10 or less; use poisson instead of negbin")
        pmf = lambda k: _nb_pmf(k, mu, r)

        def p_ge(t, pmf=pmf):
            return 1 - sum(pmf(k) for k in range(0, max(t, 0)))

        p_eq = lambda t: pmf(t) if t >= 0 else 0.0
    else:
        raise ReadsError("dist must be poisson, negbin, or normal")

    push = p_eq(int(round(line))) if whole else 0.0
    over_win = p_ge(over_threshold)
    if side == "over":
        win, push_p = over_win, push
    else:
        win, push_p = 1 - over_win - push, push
    return _clip01(win, "q_win"), _clip01(push_p, "q_push")


def _abstain(reason: str, terms=None) -> dict:
    return {
        "mean_b": None,
        "q_win_b": None,
        "q_push_b": None,
        "se_b": None,
        "abstain": True,
        "abstain_reason": reason,
        "terms": terms or {},
        "shared_inputs": ["volume"],
    }


def _optional_finite(candidate: dict, name: str):
    if name not in candidate or candidate[name] is None:
        return None
    return _finite(name, candidate[name])


def _bucket_fields(stat: str) -> tuple[str, str, str, str]:
    if stat == "receptions":
        return (
            "checkdown_target_share",
            "checkdown_player_games",
            "checkdown_team_games",
            "checkdown",
        )
    return (
        "first_read_target_share",
        "first_read_player_games",
        "first_read_team_games",
        "first_read",
    )


def _charting_blocked(candidate: dict) -> bool:
    if candidate.get("reads_charting_missing") is True:
        return True
    if candidate.get("reads_charting_ok") is False:
        return True
    status = candidate.get("reads_charting_status")
    if isinstance(status, str) and status.strip().lower() in ("missing", "unmatched", "failed"):
        return True
    return False


def _join_failed(candidate: dict) -> bool:
    if candidate.get("reads_join_failed") is True:
        return True
    if candidate.get("reads_join_ok") is False:
        return True
    status = candidate.get("reads_join_status")
    if isinstance(status, str) and status.strip().lower() in ("failed", "unmatched"):
        return True
    return False


def _mean_se(dist: str, mean: float, n_eff: float, sd=None, var_ratio=None) -> float:
    if n_eff <= 0:
        return float("nan")
    if dist == "normal":
        sd = _finite("sd", sd)
        return sd / math.sqrt(n_eff)
    if dist == "negbin":
        ratio = _finite("var_ratio", var_ratio)
        return math.sqrt(ratio * mean / n_eff)
    return math.sqrt(mean / n_eff)


def project_reads(candidate: dict) -> dict:
    """Project NFL receptions or receiving yards from charted read buckets.

    Mean (independent of Engine A ``baseline_mean``):

      mean_b = team_pass_attempts_expected
             * team_bucket_throw_share
             * player_bucket_target_share
             * conversion
             * def_matchup_factor

    Terms:
      team_pass_attempts_expected — tonight's expected team pass attempts (volume).
      team_bucket_throw_share — share of team throws in the read bucket
        (first_read for receiving yards, checkdown for receptions).
      player_bucket_target_share — this player's target share within that bucket.
      conversion — receptions per target (receptions) or yards per target
        (receiving yards) in that bucket.
      def_matchup_factor — opponent clamp already applied on the slate row.

    The only input shared with Engine A is volume (``team_pass_attempts_expected``).
    """
    if not isinstance(candidate, dict):
        raise ReadsError("candidate must be a JSON object")

    sport = candidate.get("sport")
    if isinstance(sport, str):
        sport = sport.strip().upper()
    stat = candidate.get("stat")
    if isinstance(stat, str):
        stat = stat.strip().lower()
    if sport != "NFL" or stat not in NFL_RECEIVING_STATS:
        return _abstain("unsupported_sport_or_stat")

    if _charting_blocked(candidate):
        return _abstain("charting_missing")
    if _join_failed(candidate):
        return _abstain("join_failed")

    share_key, player_games_key, team_games_key, bucket_name = _bucket_fields(stat)
    player_share = candidate.get("player_bucket_target_share")
    if player_share is None:
        player_share = candidate.get(share_key)
    try:
        player_games = int(candidate.get(player_games_key))
        team_games = int(candidate.get(team_games_key))
    except (TypeError, ValueError):
        player_games = -1
        team_games = -1

    if player_games < MIN_BUCKET_GAMES or team_games < MIN_BUCKET_GAMES:
        return _abstain("insufficient_bucket_games")

    volume = _optional_finite(candidate, "team_pass_attempts_expected")
    team_throw_share = _optional_finite(candidate, "team_bucket_throw_share")
    conversion = _optional_finite(candidate, "conversion")
    def_factor = _optional_finite(candidate, "def_matchup_factor")
    if player_share is not None:
        player_share = _finite("player_bucket_target_share", player_share)

    terms = {
        "team_pass_attempts_expected": volume,
        "team_bucket_throw_share": team_throw_share,
        "player_bucket_target_share": player_share,
        "conversion": conversion,
        "def_matchup_factor": def_factor,
        "bucket": bucket_name,
        "volume_source": candidate.get("volume_source"),
        "player_bucket_games": player_games,
        "team_bucket_games": team_games,
    }
    if any(value is None for value in (
        volume, team_throw_share, player_share, conversion, def_factor,
    )):
        return _abstain("missing_term", terms)

    if volume <= 0 or team_throw_share <= 0 or player_share < 0 or conversion <= 0 or def_factor <= 0:
        return _abstain("invalid_term", terms)

    # The checkdown and first-read buckets are partial subsets of total receptions
    # or receiving yards. They cannot independently forecast a TOTAL prop without
    # externally charted coverage and a verified total-stat conversion model.
    # Until that full-coverage projection exists, abstain rather than wrongly
    # treating bucket production as full-game production and demoting good picks.
    if candidate.get("reads_total_stat_validated") is not True:
        return _abstain("partial_bucket_not_total_stat", terms)

    mean_b = volume * team_throw_share * player_share * conversion * def_factor
    if mean_b <= 0 or not math.isfinite(mean_b):
        return _abstain("nonpositive_mean", terms)

    dist = candidate.get("dist")
    if not isinstance(dist, str):
        return _abstain("missing_dist", terms)
    dist = dist.strip().lower()
    if dist not in {"poisson", "negbin", "normal"}:
        return _abstain("invalid_dist", terms)

    side = str(candidate.get("side", "")).strip().lower()
    if side not in ("over", "under"):
        return _abstain("missing_side", terms)
    line = _optional_finite(candidate, "line")
    if line is None:
        return _abstain("missing_line", terms)

    sd = candidate.get("sd")
    var_ratio = candidate.get("var_ratio")
    if dist == "normal" and sd is None:
        return _abstain("missing_sd", terms)
    if dist == "negbin" and (var_ratio is None or _negbin_rejected(float(var_ratio))):
        return _abstain("missing_var_ratio", terms)
    if dist == "poisson" and (sd is not None or var_ratio is not None):
        return _abstain("poisson_extra_params", terms)

    sd_used = sd
    if dist == "normal" and sd is not None:
        base_mu = _optional_finite(candidate, "baseline_mean")
        if base_mu is not None and base_mu > 0:
            sd_used = _finite("sd", sd) * (mean_b / base_mu)

    n_eff = float(min(player_games, team_games))
    se_b = _mean_se(dist, mean_b, n_eff, sd=sd_used, var_ratio=var_ratio)
    if not math.isfinite(se_b) or se_b < 0:
        return _abstain("invalid_se", terms)

    try:
        q_win_b, q_push_b = _side_probs(dist, mean_b, line, side, sd=sd_used, r=var_ratio)
    except ReadsError:
        return _abstain("distribution_error", terms)

    return {
        "mean_b": mean_b,
        "q_win_b": q_win_b,
        "q_push_b": q_push_b,
        "se_b": se_b,
        "abstain": False,
        "abstain_reason": None,
        "terms": terms,
        "shared_inputs": ["volume"],
    }
