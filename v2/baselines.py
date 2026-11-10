"""Leakage-safe shadow baseline helpers; no recomputation of frozen V1 votes."""
from __future__ import annotations
from dataclasses import dataclass

from .contracts import ContractError, PoissonDistribution, finite, utc


@dataclass(frozen=True)
class HistoricalExposure:
    """Observed outcome from an already finished and publicly available game."""
    player_id: str
    stat_key: str
    role: str
    event_id: str
    event_start_at: str
    available_at: str
    exposure: float
    count: float

    def __post_init__(self) -> None:
        if finite(self.exposure, "exposure") <= 0 or finite(self.count, "count") < 0:
            raise ContractError("invalid_exposure_or_count")
        if utc(self.available_at, "available_at") <= utc(self.event_start_at, "event_start_at"):
            raise ContractError("training_outcome_not_postgame")


def poisson_rate_baseline(history: list[HistoricalExposure], *, player_id: str,
                          stat_key: str, freeze_at: str, window: int = 5,
                          projected_exposure: float = 1.0) -> PoissonDistribution:
    """Last-N per-exposure historical conversion × externally projected exposure.

    projected_exposure must be from a separately validated pregame source;
    never use realized future snaps/routes/minutes here.
    """
    if window < 1 or finite(projected_exposure, "projected_exposure") <= 0:
        raise ContractError("invalid_baseline_parameters")
    asof = utc(freeze_at, "freeze_at")
    rows = sorted((r for r in history if r.player_id == player_id and r.stat_key == stat_key
                   and utc(r.available_at, "available_at") <= asof
                   and utc(r.event_start_at, "event_start_at") < asof),
                  key=lambda x: (utc(x.event_start_at, "event_start_at"), x.event_id))[-window:]
    if not rows:
        raise ContractError("no_pregame_history")
    return PoissonDistribution(projected_exposure * sum(x.count for x in rows) / sum(x.exposure for x in rows))


def role_shrunk_rate(history: list[HistoricalExposure], *, player_id: str,
                     stat_key: str, role: str, freeze_at: str,
                     projected_exposure: float, prior_exposure: float = 20.0) -> PoissonDistribution:
    """Explicit empirical-Bayes role prior, research challenger only.

    Role peer pool excludes the target player. Both peer and player labels
    must have been publicly available by freeze_at.
    """
    if finite(prior_exposure, "prior_exposure") <= 0:
        raise ContractError("invalid_prior_exposure")
    if finite(projected_exposure, "projected_exposure") <= 0:
        raise ContractError("invalid_projected_exposure")
    asof = utc(freeze_at, "freeze_at")
    rows = [r for r in history if r.stat_key == stat_key and
            utc(r.available_at, "available_at") <= asof and
            utc(r.event_start_at, "event_start_at") < asof]
    peers = [r for r in rows if r.role == role and r.player_id != player_id]
    own = [r for r in rows if r.player_id == player_id]
    if not peers:
        raise ContractError("no_role_peer_history")
    prior_rate = sum(x.count for x in peers)/sum(x.exposure for x in peers)
    rate = (sum(x.count for x in own) + prior_rate*prior_exposure)/(sum(x.exposure for x in own) + prior_exposure)
    return PoissonDistribution(rate*projected_exposure)
