"""Phase 2 P2-01: pregame-only, market-optional NFL team-volume scenarios.

The standard champion has no sportsbook input. The game-market challenger
uses ONLY a verified pregame game spread and an as-of fitted spread slope,
not player-prop quotes, a final score or realized team pass attempts.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from statistics import mean, stdev

from v2.contracts import ContractError, finite, utc
from .contracts import NFLPregame, NFLTeamHistory, probability


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _binomial(rng: random.Random, n: int, prob: float) -> int:
    return sum(rng.random() < prob for _ in range(n))


def _variance(rows, attr: str) -> float:
    values = [float(getattr(row, attr)) for row in rows]
    if len(values) < 2:
        return 0.0
    mu = math.fsum(values) / len(values)
    return math.fsum((x - mu) ** 2 for x in values) / (len(values) - 1)


def _correlation(rows, a: str, b: str) -> float:
    if len(rows) < 3:
        return 0.0
    av = [getattr(x, a) for x in rows]
    bv = [getattr(x, b) for x in rows]
    am, bm = mean(av), mean(bv)
    cross = math.fsum((x - am) * (y - bm) for x, y in zip(av, bv))
    scale = math.sqrt(math.fsum((x-am)**2 for x in av) *
                      math.fsum((x-bm)**2 for x in bv))
    return _clamp(cross/scale, -0.95, 0.95) if scale else 0.0


@dataclass(frozen=True)
class TeamPosterior:
    team_id: str
    training_cutoff_at: str
    n_league_games: int
    n_team_games: int
    mean_possessions: float
    mean_plays: float
    sd_possessions: float
    sd_plays: float
    correlation_possessions_plays: float
    dropback_alpha: float
    dropback_beta: float
    attempt_alpha: float
    attempt_beta: float
    prior_game_strength: float

    def __post_init__(self) -> None:
        for k in ("mean_possessions", "mean_plays", "dropback_alpha",
                  "dropback_beta", "attempt_alpha", "attempt_beta",
                  "prior_game_strength"):
            if finite(getattr(self, k), k) <= 0:
                raise ContractError("invalid_fitted_team_parameter:" + k)
        if not -0.95 <= self.correlation_possessions_plays <= 0.95:
            raise ContractError("invalid_fitted_state_correlation")

    def draw(self, rng: random.Random, market_pass_logit_shift: float = 0.) -> dict:
        tempo = rng.gauss(0., 1.)
        residual = rng.gauss(0., 1.)
        corr = self.correlation_possessions_plays
        possessions = max(1, round(self.mean_possessions +
                                   self.sd_possessions * tempo))
        plays = max(possessions, round(
            self.mean_plays + self.sd_plays * (
                corr * tempo + math.sqrt(1.0-corr*corr) * residual)))
        p_dropback = rng.betavariate(self.dropback_alpha, self.dropback_beta)
        if market_pass_logit_shift:
            # A *fitted*, explicitly disclosed alternative, not a hard anchor.
            logit = math.log(p_dropback/(1-p_dropback))
            p_dropback = 1 / (1+math.exp(-_clamp(logit+market_pass_logit_shift,-30,30)))
        dropbacks = _binomial(rng, plays, p_dropback)
        p_attempt = rng.betavariate(self.attempt_alpha, self.attempt_beta)
        attempts = _binomial(rng, dropbacks, p_attempt)
        return {
            "possessions":possessions, "offensive_plays":plays,
            "dropbacks":dropbacks, "pass_attempts":attempts,
            "non_attempt_dropbacks":dropbacks-attempts,
            "qb_pass_attempts":attempts,
            "qb_dropbacks":dropbacks,
            "pregame_state_only":True,
        }


def fit_team_state(history: list[NFLTeamHistory], forecast: NFLPregame, *,
                   prior_game_strength: float = 5.) -> TeamPosterior:
    """Empirical-Bayes shrinkage to as-of league cohort, without markets."""
    prior = finite(prior_game_strength, "prior_game_strength")
    if prior <= 0:
        raise ContractError("invalid_team_pooling_strength")
    freeze = utc(forecast.freeze_at, "forecast_freeze")
    data = [x for x in history
            if utc(x.label_available_at, "team_label") <= freeze
            and x.event_id != forecast.event_id]
    if len(data) < 4:
        raise ContractError("insufficient_asof_nfl_team_game_history")
    own = [r for r in data if r.team_id == forecast.team_id]
    wg = len(own) / (len(own) + prior)
    def shrunk(attr):
        league = mean(getattr(r, attr) for r in data)
        team = mean(getattr(r, attr) for r in own) if own else league
        return wg*team+(1.-wg)*league
    mean_poss = max(1., shrunk("possessions"))
    mean_plays = max(mean_poss, shrunk("offensive_plays"))
    league_var_pos = _variance(data,"possessions")
    team_var_pos = _variance(own,"possessions")
    league_var_plays = _variance(data,"offensive_plays")
    team_var_plays = _variance(own,"offensive_plays")
    sd_poss = math.sqrt(max(.25, wg*team_var_pos+(1.-wg)*league_var_pos))
    sd_plays = math.sqrt(max(1., wg*team_var_plays+(1.-wg)*league_var_plays))
    c = wg*_correlation(own,"possessions","offensive_plays") + (
        1.-wg)*_correlation(data,"possessions","offensive_plays")
    total_play = sum(r.offensive_plays for r in data)
    total_drop = sum(r.dropbacks for r in data)
    total_attempt = sum(r.pass_attempts for r in data)
    if not total_play or not total_drop:
        raise ContractError("invalid_team_training_opportunity_denominators")
    # Empirical league prior means, with declared pseudo-exposure strength.
    league_drop = total_drop/total_play
    league_att = total_attempt/total_drop
    effective = prior * mean_plays
    team_play = sum(r.offensive_plays for r in own)
    team_drop = sum(r.dropbacks for r in own)
    team_attempt = sum(r.pass_attempts for r in own)
    return TeamPosterior(
        team_id=forecast.team_id,
        training_cutoff_at=max(utc(r.label_available_at,"team_label") for r in data).isoformat(),
        n_league_games=len(data),n_team_games=len(own),
        mean_possessions=mean_poss,mean_plays=mean_plays,
        sd_possessions=sd_poss,sd_plays=sd_plays,
        correlation_possessions_plays=c,
        dropback_alpha=1.+team_drop+effective*league_drop,
        dropback_beta=1.+team_play-team_drop+effective*(1.-league_drop),
        attempt_alpha=1.+team_attempt+effective*league_att,
        attempt_beta=1.+team_drop-team_attempt+effective*(1.-league_att),
        prior_game_strength=prior,
    )


def fitted_spread_effect(market: dict | None, team_history: list[dict],
                         freeze_at: str, team_id: str) -> dict:
    """Fit optional spread/attempt share slope on available prior games.

    If market receipt or prior as-of quote-history is unavailable, ABSTAIN.
    This challenger never consumes target props or final game spreads.
    """
    if market is None:
        return {"status":"no_game_market_requested","shift":None}
    if not isinstance(market,dict) or set(market) != {
            "team_spread", "quote_at", "source_sha256", "source_uri"}:
        raise ContractError("game_market_fields_incomplete_or_forbidden")
    spread = finite(market["team_spread"],"team_spread")
    if (not isinstance(market["source_sha256"],str)
            or len(market["source_sha256"])!=64
            or any(c not in "0123456789abcdef" for c in market["source_sha256"])):
        raise ContractError("game_market_receipt_digest_missing")
    if not isinstance(market["source_uri"],str) or not market["source_uri"].startswith("https://"):
        raise ContractError("game_market_original_source_required")
    freeze=utc(freeze_at,"freeze_at")
    if utc(market["quote_at"],"quote_at") > freeze:
        raise ContractError("game_market_quote_after_freeze")
    sample=[]
    for r in team_history:
        try:
            available=utc(r["label_available_at"],"hist_available")
            observed=utc(r["event_start_at"],"hist_start")
            quoted=utc(r["pregame_spread_at"],"historical_spread_at")
            if not r.get("pregame_spread_source_sha256"):
                continue
            count=r["offensive_plays"]
            drop=r["dropbacks"]
            if (available <= freeze and observed < freeze and quoted < observed
                    and count > 0):
                sample.append((finite(r["pregame_spread"],"historical_spread"),
                               drop / count))
        except (KeyError,ValueError,TypeError,ContractError):
            continue
    # With scant matched point-in-time original quotes, no market challenger.
    if len(sample)<8 or len({x for x,_ in sample})<3:
        return {"status":"insufficient_asof_pregame_spread_training",
                "shift":None,"matched_training_games":len(sample)}
    mx=mean(x for x,_ in sample)
    my=mean(y for _,y in sample)
    denom=math.fsum((x-mx)**2 for x,_ in sample)
    slope=math.fsum((x-mx)*(y-my) for x,y in sample)/denom
    # The alternative shifts log-odds, using fitted probability sensitivity.
    base=_clamp(my, .01,.99)
    pred=_clamp(my+slope*(spread-mx),.01,.99)
    logit=lambda p: math.log(p/(1-p))
    return {"status":"fitted_spread_state_challenger",
            "shift":logit(pred)-logit(base),
            "matched_training_games":len(sample),
            "training_mean_spread":mx,"fitted_linear_rate_slope":slope,
            "not_player_prop_anchoring":True,
            "quote_source_sha256":market["source_sha256"]}
