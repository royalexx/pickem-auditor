"""Dynamic NFL opportunity prior with fast-changing player form and slower team identity.

Research-only empirical Bayes-style shrinkage; not a sampled Bayesian posterior.
Inspired by Ribeiro et al. (2025) dynamic team attack/defense, but explicitly
NOT claimed as their Bayesian ZIP model, and not approved for production.

All input histories must be previous, settled, regular-season games. Current
player form is restricted to the *current* season and last 5 appearances; old
player history is used only as a weak role prior. Team offense/defense tendencies
retain decayed historical team-game totals across seasons.
"""
from __future__ import annotations

from datetime import date
import math
from statistics import mean

PLAYER_LOOKBACK=5
PLAYER_HALF_LIFE_DAYS=28.
TEAM_HALF_LIFE_DAYS=105.
ROLE_HALF_LIFE_DAYS=140.
TEAM_PRIOR_GAMES=4.
OPPONENT_PRIOR_GAMES=5.
TEAM_MULTIPLIER_BOUNDS=(.70,1.35)
MAX_RECENT_GAP_DAYS=28
MIN_CURRENT_SEASON_APPEARANCES=1
MODEL_VERSION="dynamic_team_opportunity_player_last5_v1"

def _valid_date(s):
    return date.fromisoformat(str(s))

def _hist_asof(items,asof,*,half_life_days,max_items=None):
    out=[]
    for e in items:
        d=_valid_date(e["gameday"])
        if d>=asof:raise ValueError("target_or_future_history_in_dynamic_model")
        days=(asof-d).days
        if days<0:raise ValueError("negative_history_age")
        value=float(e["value"])
        if not math.isfinite(value):raise ValueError("nonfinite_historical_stat")
        out.append((d,value,2.**(-days/half_life_days)))
    out.sort(key=lambda t:t[0],reverse=True)
    return out[:max_items] if max_items else out

def _weighted(items):
    if not items:return None,0.
    w=sum(r[2] for r in items)
    return (sum(r[1]*r[2] for r in items)/w,w) if w>1e-12 else (None,0.)

def _shrink(value,weight,reference,pseudo):
    if value is None:return reference
    return (value*weight+reference*pseudo)/(weight+pseudo)

def _league_game_average(state,market,asof):
    z=_hist_asof(state["league_team"].get(market,()),asof,half_life_days=TEAM_HALF_LIFE_DAYS)
    value,effective=_weighted(z)
    return value,effective

def _team_rate(state,bucket,market,team,asof,reference,pseudogames):
    z=_hist_asof(state[bucket].get((market,team),()),asof,
                 half_life_days=TEAM_HALF_LIFE_DAYS,max_items=35)
    value,effective=_weighted(z)
    if value is None:return reference,0.
    # Separate team effects pool toward a common league-wide prior. A team
    # with one old game cannot claim huge precision or a major matchup edge.
    return _shrink(value,effective,reference,pseudogames),effective

def team_opportunity_factor(state,market,team,opponent,asof):
    if team==opponent:raise ValueError("opponent_equals_team")
    league,nleague=_league_game_average(state,market,asof)
    if league is None or league<=1e-6 or nleague<2.:
        return 1.,{"team_effect":1.,"opponent_effect":1.,"league_team_mean":league,
                    "team_effective_games":0.,"opponent_effective_games":0.}
    own,neff=_team_rate(state,"team_history",market,team,asof,league,TEAM_PRIOR_GAMES)
    defense,deff=_team_rate(state,"allowed_history",market,opponent,asof,league,OPPONENT_PRIOR_GAMES)
    ownratio=max(.6,min(1.5,own/league))
    defratio=max(.6,min(1.5,defense/league))
    combo=max(TEAM_MULTIPLIER_BOUNDS[0],
              min(TEAM_MULTIPLIER_BOUNDS[1],ownratio**.60*defratio**.40))
    return combo,{"team_effect":ownratio,"opponent_effect":defratio,
                  "team_effective_games":neff,
                  "opponent_effective_games":deff,
                  "league_team_mean":league}

def role_recent_reference(state,market,position,asof,default):
    # Role prior: historical population, not the individual player's old totals.
    z=_hist_asof(state["role_history"].get((market,position),()),asof,
                 half_life_days=ROLE_HALF_LIFE_DAYS,max_items=2200)
    role,effective=_weighted(z)
    if role is None:return float(default),0.
    # Weight toward the fixed pre-evaluation position prior for sparse groups.
    return _shrink(role,effective,float(default),16.),effective

def dynamic_player_projection(state,*,market,player_id,team,opponent,position,
                              game_day,season,default_role):
    asof=_valid_date(game_day)
    if not team or not opponent:return None,{"status":"missing_team_or_opponent"}
    player=state["player"].get((market,player_id),())
    if any(_valid_date(r["gameday"])>=asof for r in player):
        raise ValueError("target_or_future_player_stat_in_dynamic_projection")
    # Important: player must actually have logged this season for THIS team.
    # Prior-season roster guesses no longer yield high-confidence Week-1 picks.
    current=[r for r in player if r.get("season")==season and r.get("team")==team
             and (asof-_valid_date(r["gameday"])).days<=56]
    current.sort(key=lambda e:e["gameday"],reverse=True)
    recent=current[:PLAYER_LOOKBACK]
    if len(recent)<MIN_CURRENT_SEASON_APPEARANCES:
        return None,{"status":"no_pregame_current_team_appearance"}
    age=(asof-_valid_date(recent[0]["gameday"])).days
    if age>MAX_RECENT_GAP_DAYS:
        return None,{"status":"stale_current_team_appearance"}
    z=_hist_asof(recent,asof,half_life_days=PLAYER_HALF_LIFE_DAYS)
    recentmean,neff=_weighted(z)
    prior,roleeff=role_recent_reference(state,market,position,asof,default_role)
    # After five consecutive games the last-five mean dominates (82%).
    # The position prior remains a stabilizer, rather than preserving the
    # player's 2021-23 rate as a dominant response predictor.
    recent_share=min(.82,.36+.092*len(recent))
    player_mean=recent_share*recentmean+(1.-recent_share)*prior
    factor,team_evidence=team_opportunity_factor(state,market,team,opponent,asof)
    pred=max(0.,player_mean*factor)
    if not math.isfinite(pred) or pred>1000:
        return None,{"status":"unreliable_dynamic_projection"}
    return pred,{"status":"dynamic_team_player_short_form",
                 "player_recent_games":len(recent),
                 "player_recent_weight":round(recent_share,6),
                 "player_recent_weighted_mean":recentmean,
                 "position_role_prior":prior,
                 "position_prior_effective_observations":roleeff,
                 "team_opportunity_multiplier":factor,
                 **team_evidence,
                 "source_roster_verified":False,
                 "bookmaker_quote_verified":False,
                 "distribution_family_selected_by_holdout":False}

def extend_team_histories(state,rows):
    """Record one completed team-game for each market, never every player-row.
    Call ONLY after the entire week is forecast-locked and settled.
    """
    bucket={}
    for r in rows:
        key=(r["season"],r["game_id"],r["stat"],r["team"],r["opponent"],r["gameday"])
        v=float(r["value"])
        if not math.isfinite(v):raise ValueError("invalid_team_aggregation")
        bucket[key]=bucket.get(key,0.)+v
    # A team may have its own entries for offense or defense, and only a
    # subset of stat markets have observed candidates; no imputation of zeros.
    for (season,gid,market,team,opp,day),value in sorted(bucket.items()):
        record={"gameday":day,"value":value,"season":season,"game_id":gid}
        state["team_history"][(market,team)].append(record)
        state["allowed_history"][(market,opp)].append(record)
        state["league_team"][market].append(record)
