"""Leakage-guarded player 5/10 recent games + role reference research lines.

These are NOT historical sportsbook quotes; no target-week outcomes may be
used to construct lines for the week's frozen predictions.
"""
from __future__ import annotations
from datetime import date
import math
from statistics import median

# Source-informed research starting values, not claimed bookmaker prices.
FALLBACK = {
 "tackles + assists": 5.5, "solo tackles": 3.5, "tackle assists": 1.5,
 "qb hits": .5, "passes defended": .5, "targets": 4.5,
 "receptions": 3.5, "receiving yards": 35.5,
 "receiving touchdowns": .5, "pass attempts": 31.5,
 "completions": 20.5, "passing yards": 230.5,
 "passing touchdowns": 1.5, "carries": 10.5,
 "rushing yards": 45.5, "rushing touchdowns": .5,
}
ROLE = {
 "tackles + assists": {
  "MLB": 8.5, "ILB": 8.5, "LB": 7.5, "OLB": 5.5,
  "SS": 5.5, "S": 5.5, "FS": 5.5, "DB": 5.5,
  "CB": 4.5, "DE": 3.5, "DT": 2.5, "NT": 2.5},
 "solo tackles": {
  "MLB": 5.5, "ILB": 5.5, "LB": 4.5, "OLB": 3.5,
  "SS": 3.5, "S": 3.5, "FS": 3.5, "CB": 3.5,
  "DE": 2.5, "DT": 1.5, "NT": 1.5},
 "tackle assists": {
  "MLB": 3.5, "ILB": 3.5, "LB": 2.5, "OLB": 1.5,
  "SS": 1.5, "S": 1.5, "FS": 1.5, "CB": 1.5,
  "DE": 1.5, "DT": .5, "NT": .5},
 "targets": {"WR": 6.5, "TE": 4.5, "RB": 3.5},
 "receptions": {"WR": 4.5, "TE": 3.5, "RB": 3.5},
 "receiving yards": {"WR": 55.5, "TE": 35.5, "RB": 20.5},
 "receiving touchdowns": {"WR": .5, "TE": .5, "RB": .5},
 "pass attempts": {"QB": 31.5}, "completions": {"QB": 20.5},
 "passing yards": {"QB": 230.5}, "passing touchdowns": {"QB": 1.5},
 "carries": {"RB": 13.5, "QB": 4.5, "WR": 1.5},
 "rushing yards": {"RB": 55.5, "QB": 20.5, "WR": 5.5},
 "rushing touchdowns": {"RB": .5, "QB": .5, "WR": .5},
 "qb hits": {"DE": .5, "DT": .5, "NT": .5, "OLB": .5, "LB": .5},
 "passes defended": {"CB": .5, "S": .5, "FS": .5, "SS": .5, "LB": .5},
}


def hybrid_research_line(state, *, market, player_id, position, game_day):
    """Compute synthetic half-point line using exclusively prior played games.

    With >=10 prior appearances: 50% median last 5, 30% last 10,
    20% position prior. Sparse histories transfer weight to position prior.
    """
    if market not in FALLBACK:
        raise ValueError("unrecognized_market_for_hybrid:"+str(market))
    prior=ROLE.get(market,{}).get(position,FALLBACK[market])
    previous=state["player"].get((market,player_id),())
    cutoff=date.fromisoformat(game_day)
    if any(date.fromisoformat(r["gameday"])>=cutoff for r in previous):
        raise ValueError("hybrid_line_future_or_current_week_leak")
    values=[float(r["value"]) for r in previous[-10:]]
    if any(not math.isfinite(v) for v in values) or (\n        market not in {"rushing yards", "passing yards", "receiving yards"}\n        and any(v<0 for v in values)):
        raise ValueError("invalid_hybrid_line_history")
    n=len(values)
    m5=float(median(values[-5:])) if n else None
    m10=float(median(values)) if n else None
    w5=.5*min(1.,n/5.)
    w10=.3*min(1.,n/10.)
    wr=1.-w5-w10
    raw=w5*(m5 if m5 is not None else 0.)+w10*(
        m10 if m10 is not None else 0.)+wr*prior
    if not math.isfinite(raw):
        raise ValueError("nonfinite_hybrid_line")
    # Negative yardage is legitimate. A prop research line cannot be negative.
    raw=max(0.,raw)
    line=math.floor(raw)+.5
    return line, {
      "method":"player_last5_last10_role_v1" if n else "role_prior_only_v1",
      "history_games":n,"median_last5":m5,"median_last10":m10,
      "role_reference":prior,"w5":round(w5,6),"w10":round(w10,6),
      "w_role":round(wr,6),"unrounded_line":raw,
      "synthetic_not_bookmaker":True}
