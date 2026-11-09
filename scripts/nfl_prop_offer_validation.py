"""Fail-closed NFL prop offer/availability validator for historical/live ranking.

A player projection is NOT a tradeable sportsbook proposition. Only verified
pregame two-sided odds for the exact player, market, game, and time qualify.
Research/hybrid lines remain permitted for diagnostics but NEVER for bets.
"""
from __future__ import annotations
from datetime import datetime,timezone
import math
import re

from nfl_volume_market_policy import nfl_volume_market_allowed
class OfferNotVerified(ValueError):pass

def _utc(raw):
    if not isinstance(raw,str):raise OfferNotVerified("missing_precise_utc_timestamp")
    try:
        v=datetime.fromisoformat(raw.replace("Z","+00:00"))
    except ValueError as e:raise OfferNotVerified("invalid_timestamp") from e
    if v.tzinfo is None:raise OfferNotVerified("timestamp_must_have_timezone")
    return v.astimezone(timezone.utc)

def _positive_decimal_odds(v):
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=1.:
        raise OfferNotVerified("invalid_decimal_bookmaker_odds")
    return float(v)

def validated_bookmaker_prop(offer, *, allow_age_hours=24):
    """Require actual timestamped quoted odds and pre-kickoff active status.

    Returns a new immutable-contract-shaped summary. The caller must persist
    raw source and quote ID; this only validates supplied evidence.
    """
    if not isinstance(offer,dict):raise OfferNotVerified("no_bookmaker_offer")
    if not nfl_volume_market_allowed("NFL",offer.get("market")):
        raise OfferNotVerified("nfl_market_excluded_volume_only_policy")
    if offer.get("source_kind")!="bookmaker_quote":
        raise OfferNotVerified("synthetic_or_nonbookmaker_line")
    if offer.get("market_available") is not True:
        raise OfferNotVerified("bookmaker_market_not_available")
    if offer.get("player_active_asof") is not True:
        raise OfferNotVerified("player_not_verified_active_pregame")
    if offer.get("identity_verified") is not True:
        raise OfferNotVerified("unverified_player_game_identity")
    for k in ("player_id","game_id","market","bookmaker","quote_id"):
        if not isinstance(offer.get(k),str) or not offer[k].strip():
            raise OfferNotVerified("missing_offered_contract_field:"+k)
    digest=offer.get("source_sha256")
    if not isinstance(digest,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",digest):
        raise OfferNotVerified("missing_verified_source_digest")
    start=_utc(offer.get("kickoff"))
    quote=_utc(offer.get("quoted_at"))
    available=_utc(offer.get("roster_status_available_at"))
    if not quote<start or not available<start:
        raise OfferNotVerified("market_or_roster_evidence_post_kickoff")
    hours=(start-quote).total_seconds()/3600
    if not 0<hours<=allow_age_hours:
        raise OfferNotVerified("quote_too_stale")
    line=offer.get("line")
    if isinstance(line,bool) or not isinstance(line,(int,float)) or not math.isfinite(line) or line<0:
        raise OfferNotVerified("invalid_bookmaker_line")
    o=_positive_decimal_odds(offer.get("over_decimal_odds"))
    u=_positive_decimal_odds(offer.get("under_decimal_odds"))
    implied_o,implied_u=1./o,1./u
    if not 1.0<=implied_o+implied_u<=1.5:
        raise OfferNotVerified("invalid_bookmaker_market_hold")
    return {"player_id":offer["player_id"],"game_id":offer["game_id"],
      "market":offer["market"],"bookmaker":offer["bookmaker"],
      "quote_id":offer["quote_id"],"line":float(line),
      "quoted_at":quote.isoformat(),"kickoff":start.isoformat(),
      "p_market_over_novig":implied_o/(implied_o+implied_u),
      "p_market_under_novig":implied_u/(implied_o+implied_u),
      "over_decimal_odds":o,"under_decimal_odds":u,
      "source_sha256":digest,"line_source":"verified_bookmaker_quote",
      "availability_verified":True,"production_research_only":False}

def rank_verified_props(projections,*,max_picks=10):
    """Return only fully verified, positive-expectation candidate props.

    No forced top-ten quota. Predictions with unverified market evidence
    abstain. Expected value is per unit risked including a push refund.
    """
    ranked=[]
    for row in projections:
        try:offer=validated_bookmaker_prop(row.get("offer"))
        except OfferNotVerified:continue
        if (offer["player_id"]!=str(row.get("player_id")) or
            offer["game_id"]!=str(row.get("game_id")) or
            offer["market"]!=str(row.get("market"))):
            continue
        over=row.get("p_over")
        under=row.get("p_under")
        push=row.get("p_push",0.)
        if any(isinstance(p,bool) or not isinstance(p,(int,float)) or
               not math.isfinite(p) or not 0<=p<=1 for p in (over,under,push)):
            continue
        if abs(over+under+push-1.)>1e-8:continue
        for side,p,odds in (("over",over,offer["over_decimal_odds"]),
                            ("under",under,offer["under_decimal_odds"])):
            # On a push the stake is returned: EV excludes push payoff.
            ev=float(p)*(odds-1)-(1.-float(p)-float(push))
            if ev<=0:continue
            ranked.append({**offer,"side":side,"p_win":p,"p_push":push,
                           "expected_value_per_unit":ev})
    ranked.sort(key=lambda x:(-x["expected_value_per_unit"],x["game_id"],
                               x["player_id"],x["market"],x["side"]))
    selected=[];players=set();games={}
    for r in ranked:
        if r["player_id"] in players or games.get(r["game_id"],0)>=4:continue
        selected.append(r)
        players.add(r["player_id"])
        games[r["game_id"]]=games.get(r["game_id"],0)+1
        if len(selected)>=max_picks:break
    return selected
