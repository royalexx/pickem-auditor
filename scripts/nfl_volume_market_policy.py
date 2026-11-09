"""NFL volume-only ranking gate, separate from historical data retention.

Applies equally to research, conditional, and verified NFL ranking boards.
Touchdowns (passing/rushing/receiving/anytime), QB hits, and passes defended
are deliberately blocked. NBA and NHL are unaffected.
This is an eligibility policy, NOT a claim that a market was quoted/available.
"""
from __future__ import annotations

NFL_VOLUME_MARKETS = frozenset((
    "pass attempts","completions","passing yards",
    "targets","receptions","receiving yards",
    "carries","rushing yards",
    "tackles + assists","solo tackles","tackle assists",
))
NFL_EXCLUDED_MARKETS = frozenset((
    "passing touchdowns","receiving touchdowns","rushing touchdowns",
    "anytime touchdown","anytime td","anytime touchdown scorer",
    "anytime td scorer","anytime touchdowns","touchdowns",
    "total touchdowns","qb hits","passes defended",
))

def nfl_volume_market_allowed(sport, stat):
    if str(sport or "").upper() != "NFL":
        return True
    return isinstance(stat,str) and stat.strip().lower() in NFL_VOLUME_MARKETS
