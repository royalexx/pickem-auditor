"""V2.5 Phase 2 NFL opportunity research: strict as-of inputs.

No feed calls, mutable filesystem reads, prop-market inference or production
ranking. Historical outcomes are TRAINING LABELS only if they were available
before the forecast freeze. Original future observations remain unused.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any

from v2.contracts import ContractError, canonical_hash, finite, utc


def positive_integer(value: Any, name: str, *, allow_zero: bool = True) -> int:
    if type(value) is not int or (value < 0 if allow_zero else value < 1):
        raise ContractError("invalid_nonnegative_integer:" + name)
    return value


def valid_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError("missing_nfl_identity:" + name)
    return value


def probability(value: Any, name: str) -> float:
    x = finite(value, name)
    if not 0 <= x <= 1:
        raise ContractError("out_of_range_probability:" + name)
    return x


@dataclass(frozen=True)
class NFLTeamHistory:
    event_id: str
    team_id: str
    event_start_at: str
    label_available_at: str
    possessions: int
    offensive_plays: int
    dropbacks: int
    pass_attempts: int
    tracked_targets: int

    def __post_init__(self) -> None:
        valid_id(self.event_id, "event_id")
        valid_id(self.team_id, "team_id")
        if utc(self.label_available_at, "team_label_available_at") <= utc(
                self.event_start_at, "team_event_start_at"):
            raise ContractError("historical_team_outcome_available_before_game")
        for name in ("possessions", "offensive_plays", "dropbacks",
                     "pass_attempts", "tracked_targets"):
            positive_integer(getattr(self, name), name)
        if not (self.tracked_targets <= self.pass_attempts <=
                self.dropbacks <= self.offensive_plays):
            raise ContractError("historical_team_opportunity_conservation")
        if self.offensive_plays and self.possessions == 0:
            raise ContractError("historical_team_possessions_missing")


@dataclass(frozen=True)
class NFLPlayerHistory:
    event_id: str
    team_id: str
    player_id: str
    role: str
    event_start_at: str
    label_available_at: str
    routes: int
    targets: int
    structurally_inactive: bool | None = None
    verified_absent_teammate_role: str | None = None

    def __post_init__(self) -> None:
        for name in ("event_id", "team_id", "player_id", "role"):
            valid_id(getattr(self, name), name)
        if utc(self.label_available_at, "player_label_available_at") <= utc(
                self.event_start_at, "player_event_start_at"):
            raise ContractError("historical_player_outcome_available_before_game")
        positive_integer(self.routes, "routes")
        positive_integer(self.targets, "targets")
        if self.targets > self.routes:
            raise ContractError("historical_player_targets_exceed_routes")
        if self.structurally_inactive is not None and type(
                self.structurally_inactive) is not bool:
            raise ContractError("structural_inactivity_must_be_verified_boolean_or_null")
        if self.structurally_inactive and (self.routes or self.targets):
            raise ContractError("historical_structural_inactivity_contradiction")
        if self.verified_absent_teammate_role is not None:
            valid_id(self.verified_absent_teammate_role, "verified_absent_teammate_role")


@dataclass(frozen=True)
class NFLRosterPlayer:
    player_id: str
    role: str
    status: str    # available | uncertain | verified_out
    status_published_at: str
    status_retrieved_at: str

    def __post_init__(self) -> None:
        valid_id(self.player_id, "roster_player_id")
        valid_id(self.role, "roster_role")
        if self.status not in ("available", "uncertain", "verified_out"):
            raise ContractError("unsupported_roster_status")
        if utc(self.status_published_at, "status_published_at") > utc(
                self.status_retrieved_at, "status_retrieved_at"):
            raise ContractError("roster_status_retrieved_before_published")


@dataclass(frozen=True)
class NFLPregame:
    run_id: str
    event_id: str
    team_id: str
    opponent_id: str
    qb_player_id: str
    event_start_at: str
    freeze_at: str
    players: tuple[NFLRosterPlayer, ...]
    original_input_sha256: str

    def __post_init__(self) -> None:
        for name in ("run_id", "event_id", "team_id",
                     "opponent_id", "qb_player_id"):
            valid_id(getattr(self, name), name)
        if self.team_id == self.opponent_id:
            raise ContractError("invalid_team_vs_self")
        start = utc(self.event_start_at, "event_start_at")
        freeze = utc(self.freeze_at, "freeze_at")
        if freeze >= start:
            raise ContractError("post_kickoff_nfl_forecast")
        if not self.players or len(self.players) > 32:
            raise ContractError("nfl_roster_size_unusable")
        seen = set()
        for player in self.players:
            if player.player_id in seen:
                raise ContractError("duplicate_nfl_player")
            seen.add(player.player_id)
            if utc(player.status_retrieved_at, "status_retrieved_at") > freeze:
                raise ContractError("roster_data_after_freeze")
        if (len(self.original_input_sha256) != 64 or
                any(c not in "0123456789abcdef" for c in self.original_input_sha256)):
            raise ContractError("missing_original_research_input_sha")


def prepare_inputs(payload: dict) -> tuple[NFLPregame, list[NFLTeamHistory],
                                          list[NFLPlayerHistory], dict]:
    """Return only as-of eligible rows; retain total rejected rows by reason."""
    if not isinstance(payload, dict) or payload.get("schema") != "v25-nfl-p2-input-v1":
        raise ContractError("unregistered_nfl_phase2_input")
    if not isinstance(payload.get("forecast"), dict):
        raise ContractError("missing_nfl_forecast")
    for key in ("team_history", "player_history"):
        if not isinstance(payload.get(key), list):
            raise ContractError("missing_nfl_history:" + key)
    forecast = payload["forecast"]
    if any(key in forecast for key in (
            "final_score", "final_pass_attempts", "realized_routes",
            "realized_snaps", "realized_targets", "realized_dropbacks",
            "final_team_plays", "game_result", "current_game_outcome")):
        raise ContractError("forbidden_postgame_feature_in_forecast")
    players = tuple(NFLRosterPlayer(**r) for r in forecast["players"])
    frozen = NFLPregame(**{k: forecast[k] for k in (
        "run_id", "event_id", "team_id", "opponent_id", "qb_player_id",
        "event_start_at", "freeze_at")}, players=players,
        original_input_sha256=canonical_hash(payload))
    asof = utc(frozen.freeze_at, "freeze_at")
    teams, individuals = [], []
    exclusions: dict[str, int] = {}
    def exclude(reason: str) -> None:
        exclusions[reason] = exclusions.get(reason, 0) + 1
    team_ids = set()
    for raw in payload["team_history"]:
        row = NFLTeamHistory(**raw)
        identifier = (row.event_id, row.team_id)
        if identifier in team_ids:
            raise ContractError("duplicate_historical_team_row")
        team_ids.add(identifier)
        if row.event_id == frozen.event_id:
            exclude("current_game_team_history_embargo")
        elif utc(row.label_available_at, "team_history_available_at") > asof:
            exclude("team_outcome_after_forecast")
        else:
            teams.append(row)
    player_ids = set()
    for raw in payload["player_history"]:
        row = NFLPlayerHistory(**raw)
        identifier = (row.event_id, row.team_id, row.player_id)
        if identifier in player_ids:
            raise ContractError("duplicate_historical_player_row")
        player_ids.add(identifier)
        if row.event_id == frozen.event_id:
            exclude("current_game_player_history_embargo")
        elif utc(row.label_available_at, "player_history_available_at") > asof:
            exclude("player_outcome_after_forecast")
        else:
            individuals.append(row)
    # Cross-row accounting uses only matched games with complete matching
    # record identity. Do not infer unobserved receivers from tracking gaps.
    by_team = {(r.event_id, r.team_id): r for r in teams}
    summed_targets: dict[tuple[str, str], int] = {}
    for row in individuals:
        key = (row.event_id, row.team_id)
        game = by_team.get(key)
        if game is None:
            exclude("player_without_asof_team_game")
            continue
        if row.routes > game.dropbacks:
            raise ContractError("historical_routes_exceed_team_dropbacks")
        summed_targets[key] = summed_targets.get(key, 0) + row.targets
    for key, total in summed_targets.items():
        if total > by_team[key].pass_attempts:
            raise ContractError("historical_player_target_sum_exceeds_attempts")
    return frozen, teams, individuals, {
        "all_team_history_rows": len(payload["team_history"]),
        "eligible_team_history_rows": len(teams),
        "all_player_history_rows": len(payload["player_history"]),
        "eligible_player_history_rows": len(individuals),
        "rejected_history_reasons": dict(sorted(exclusions.items())),
        "original_input_sha256": frozen.original_input_sha256,
        "current_game_excluded": True,
    }
