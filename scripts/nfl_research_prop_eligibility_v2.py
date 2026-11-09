"""Pregame-only research prop eligibility; never infer sportsbook offers.

Conservative policy v2 excludes RB receiving TDs and QB rushing TDs
because historical pregame *offered* contracts are unverified here.
This controls which player/position *could plausibly* support a synthetic
research prop. It does not verify a sportsbook quoted an offer, that a player
was active or that a wager could be placed. The only bettable qualification
path remains nfl_prop_offer_validation.validated_bookmaker_prop.
"""
from __future__ import annotations

from datetime import date
from statistics import median
import math

OFFENSE_MARKETS = {
    "pass attempts":frozenset({"QB"}),
    "completions":frozenset({"QB"}),
    "passing yards":frozenset({"QB"}),
    "passing touchdowns":frozenset({"QB"}),
    "targets":frozenset({"WR","TE","RB"}),
    "receptions":frozenset({"WR","TE","RB"}),
    "receiving yards":frozenset({"WR","TE","RB"}),
    "receiving touchdowns":frozenset({"WR","TE"}),
    # Deliberately exclude all WR rushing props even if occasional gadget
    # usage is recorded in the historical database: quote existence unknown.
    "carries":frozenset({"QB","RB"}),
    "rushing yards":frozenset({"QB","RB"}),
    "rushing touchdowns":frozenset({"RB"}),
}
DEFENSE_MARKETS = {
    "tackles + assists":frozenset({"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"}),
    "solo tackles":frozenset({"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"}),
    "tackle assists":frozenset({"LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"}),
    "qb hits":frozenset({"LB","MLB","OLB","ILB","DE","DT","NT"}),
    "passes defended":frozenset({"LB","MLB","OLB","ILB","CB","DB","S","FS","SS"}),
}
MARKET_POSITIONS={**OFFENSE_MARKETS,**DEFENSE_MARKETS}

def position_market_eligible(market,position):
    return position in MARKET_POSITIONS.get(market,())

def _last_values(state, market, player_id, prior_games=5):
    return [float(r["value"]) for r in
            state["player"].get((market,player_id),())[-prior_games:]]

def _recent_median(state,market,player_id):
    vals=_last_values(state,market,player_id)
    return float(median(vals)) if vals else 0.

def eligible_pregame_research_candidate(state,*,market,player_id,position,game_day,
                                       min_prior_games=5):
    """Pre-week history-and-role eligibility; never peeks at target game.

    A low target mean or a high Under probability is NOT evidence of a
    bettable prop. Filter structurally implausible markets before ranking,
    even when the corresponding week would later contain an observed zero.
    """
    if not position_market_eligible(market,position):
        return False,"position_market_not_plausible"
    previous=state["player"].get((market,player_id),())
    cutoff=date.fromisoformat(game_day)
    if any(date.fromisoformat(r["gameday"])>=cutoff for r in previous):
        raise ValueError("candidate_eligibility_target_or_future_history")
    if len(previous)<min_prior_games:
        return False,"insufficient_prior_player_appearances"
    snaps=[float(r.get("snaps",0)) for r in previous[-5:]]
    if any(not math.isfinite(v) or v<0 for v in snaps):
        raise ValueError("invalid_prior_snap_history")
    if median(snaps)<12:
        return False,"low_prior_snap_exposure"

    # For carries/ground yardage and rushing TD the player needs demonstrated
    # rushing workload. No WR gadget usage is ever accepted as a prop.
    if market in {"carries","rushing yards","rushing touchdowns"}:
        typical_carries=_recent_median(state,"carries",player_id)
        minimum=4. if position=="RB" else 2.
        if typical_carries<minimum:
            return False,"insufficient_rushing_opportunity"

    # Only recent target earners receive synthetic receiving market lines.
    if market in {"targets","receptions","receiving yards","receiving touchdowns"}:
        typical_targets=_recent_median(state,"targets",player_id)
        min_targets=2. if position=="RB" else 3.
        if typical_targets<min_targets:
            return False,"insufficient_receiving_opportunity"

    if market=="qb hits":
        if sum(v>0 for v in _last_values(state,"qb hits",player_id))<1:
            return False,"no_recent_pass_rush_event"

    if market=="passes defended":
        if sum(v>0 for v in _last_values(state,"passes defended",player_id))<1:
            return False,"no_recent_pass_defense_event"

    return True,"eligible_research_history_only_unverified_bookmaker"
