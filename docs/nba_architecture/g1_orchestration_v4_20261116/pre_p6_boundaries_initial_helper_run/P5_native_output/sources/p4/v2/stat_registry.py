"""Versioned canonical player-prop statistic and settlement semantics.

Never infer a prop's period or overtime/shootout policy from a vague label.
Unlisted aliases and non-full periods require an explicit product contract.
NFL counts are nonnegative; signed yardage can be below zero. These are
structural contracts, NOT recommendations for any likelihood family.
"""
from __future__ import annotations
from dataclasses import dataclass
from .contracts import ContractError, finite

VERSION = "v25-stat-registry-1"


@dataclass(frozen=True)
class Stat:
    sport: str
    key: str
    value_kind: str           # count | signed_count | nonnegative_continuous
    period: str = "full"
    overtime: str = "included"
    shootout: str = "excluded"

    def validate_actual(self, outcome: float) -> float:
        y = finite(outcome, "settlement_actual")
        if self.value_kind in ("count", "signed_count") and not y.is_integer():
            raise ContractError("noninteger_statistic:" + self.key)
        if self.value_kind != "signed_count" and y < 0:
            raise ContractError("negative_statistic:" + self.key)
        return y


# A key is never changed based on a user-supplied pretty display name.
NFL = (
    ("targets", "count"), ("receptions", "count"),
    ("pass attempts", "count"), ("completions", "count"),
    ("passing yards", "signed_count"), ("receiving yards", "signed_count"),
    ("rushing yards", "signed_count"), ("carries", "count"),
    ("rushing touchdowns", "count"), ("receiving touchdowns", "count"),
    ("passing touchdowns", "count"), ("interceptions", "count"),
    ("tackles + assists", "count"), ("solo tackles", "count"),
    ("assisted tackles", "count"), ("sacks", "nonnegative_continuous"),
)
NHL = (
    ("shots on goal", "count"), ("hits", "count"),
    ("blocked shots", "count"), ("goalie saves", "count"),
    ("points", "count"), ("goals", "count"), ("assists", "count"),
    ("power play points", "count"), ("faceoff wins", "count"),
)
NBA = (
    ("points", "count"), ("rebounds", "count"), ("assists", "count"),
    ("threes", "count"), ("three pointers made", "count"),
    ("steals", "count"), ("blocks", "count"),
    ("turnovers", "count"), ("pra", "count"), ("pa", "count"),
    ("pr", "count"), ("ra", "count"), ("stocks", "count"),
    ("minutes", "nonnegative_continuous"),
)
REGISTRY = {
    (sport, key): Stat(sport, key, kind,
                      shootout=("excluded" if sport == "NHL" else "not_applicable"))
    for sport, items in (("NFL", NFL), ("NHL", NHL), ("NBA", NBA))
    for key, kind in items
}
ALIASES = {
    ("NFL", "passing attempts"): "pass attempts",
    ("NFL", "passes attempted"): "pass attempts",
    ("NFL", "passing completions"): "completions",
    ("NFL", "tackles and assists"): "tackles + assists",
    ("NFL", "combined tackles"): "tackles + assists",
    ("NHL", "sog"): "shots on goal",
    ("NHL", "shots"): "shots on goal",
    ("NHL", "blocks"): "blocked shots",
    ("NHL", "saves"): "goalie saves",
    ("NBA", "3ptm"): "threes",
    ("NBA", "3pm"): "threes",
    ("NBA", "points+rebounds+assists"): "pra",
    ("NBA", "points + rebounds + assists"): "pra",
    ("NBA", "points+assists"): "pa",
    ("NBA", "points+rebounds"): "pr",
    ("NBA", "rebounds+assists"): "ra",
}


def canonical_stat(sport: str, stat: str, period: str = "full") -> Stat:
    if sport not in ("NFL", "NHL", "NBA") or not isinstance(stat, str):
        raise ContractError("stat_identity_unknown")
    if period != "full":
        raise ContractError("unsupported_stat_period:" + str(period))
    raw = stat.strip().casefold()
    key = ALIASES.get((sport, raw), raw)
    result = REGISTRY.get((sport, key))
    if result is None:
        raise ContractError("stat_contract_not_registered:" + sport + "/" + raw)
    return result


def validate_full_game_settlement(sport: str, stat: str, period: str, actual: float) -> float:
    return canonical_stat(sport, stat, period).validate_actual(actual)
