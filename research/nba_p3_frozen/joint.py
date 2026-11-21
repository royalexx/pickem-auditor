"""Research-only NBA J0/J1 shared game generator.

A narrow original WS5-compatible boundary, not a replacement for or promotion of
v2.nba_joint. This deterministic test adapter is used only when a P1 source
provides a FULL TWO-TEAM ROSTER and an admitted fitted event model. Incomplete
source-listed subsets must abstain from full-game J and may run S/S+O.
"""
from __future__ import annotations
from collections import defaultdict
import math
import numpy as np
from .distributions import ForecastBlocked, canonical, digest

REQUIRED_PLAYER = {"player_id", "team_id", "participation_probability",
                   "projected_minutes"}
REQUIRED_PARAMETERS = {"two_attempts_per_minute", "three_attempts_per_minute",
    "free_throws_per_minute", "two_pct", "three_pct", "ft_pct",
    "rebound_weight", "assist_weight"}


def _validate(game, model):
    if not isinstance(game, dict) or set(game) != {"schema", "teams", "players"} or \
       game["schema"] != "NBA-P3-JointInput/1":
        raise ForecastBlocked("MODEL_NOT_READY", "full_game_contract_missing")
    teams = game["teams"]
    if not isinstance(teams, list) or len(teams) != 2 or len(set(teams)) != 2:
        raise ForecastBlocked("IDENTITY_UNVERIFIED", "two_team_identity")
    roster = game["players"]
    if not isinstance(roster, list) or len(roster) < 10:
        raise ForecastBlocked("MODEL_NOT_READY", "full_roster_missing")
    ids = [r.get("player_id") for r in roster]
    if len(set(ids)) != len(ids) or any(not isinstance(x, str) or not x for x in ids):
        raise ForecastBlocked("IDENTITY_UNVERIFIED", "duplicated_or_missing_player")
    for team in teams:
        if sum(r.get("team_id") == team for r in roster) < 5:
            raise ForecastBlocked("MODEL_NOT_READY", "fewer_than_five_players")
    parameters = model.get("joint_parameters")
    if not isinstance(parameters, dict) or set(parameters) != set(ids):
        raise ForecastBlocked("MODEL_NOT_READY", "unfitted_player_joint_parameters")
    for r in roster:
        if set(r) != REQUIRED_PLAYER or r["team_id"] not in teams:
            raise ForecastBlocked("IDENTITY_UNVERIFIED", "roster_schema_or_team")
        q, minute = r["participation_probability"], r["projected_minutes"]
        if type(q) not in (int,float) or not math.isfinite(q) or not 0 <= q <= 1:
            raise ForecastBlocked("PARTICIPATION_UNRESOLVED", "unknown_probability")
        if type(minute) not in (int,float) or not math.isfinite(minute) or minute < 0 or minute > 48:
            raise ForecastBlocked("MODEL_NOT_READY", "minute_prior_not_available")
        p = parameters[r["player_id"]]
        if set(p) != REQUIRED_PARAMETERS:
            raise ForecastBlocked("MODEL_NOT_READY", "joint_fit_schema")
        for key,value in p.items():
            if type(value) not in (int,float) or not math.isfinite(value) or value < 0:
                raise ForecastBlocked("NUMERICAL_FAILURE", "bad_joint_parameter:"+key)
        if any(p[k] > 1 for k in ("two_pct","three_pct","ft_pct")):
            raise ForecastBlocked("NUMERICAL_FAILURE", "conversion_probability_exceeds_one")
    state = model.get("joint_state")
    if not isinstance(state, dict) or set(state) != {"pace_sigma","ot_probability","ot_continuation","assist_probability","offensive_rebound_probability"}:
        raise ForecastBlocked("MODEL_NOT_READY", "joint_game_state_model_missing")
    for key,x in state.items():
        if type(x) not in (int,float) or not math.isfinite(x) or x < 0:
            raise ForecastBlocked("NUMERICAL_FAILURE", "invalid_state:"+key)
        if key != "pace_sigma" and x >= 1:
            raise ForecastBlocked("NUMERICAL_FAILURE", "state_probability_not_below_one")
    return teams, roster, parameters, state


def _allocate(roster, horizon, rng, sigma):
    """Water-filled simplex with each individual capped by game duration."""
    active = None
    for attempt in range(256):
        ids = [r for r in roster if rng.random() < r["participation_probability"]]
        if len(ids) >= 5:
            active = ids
            break
    if active is None:
        raise ForecastBlocked("MODEL_NOT_READY", "infeasible_participation")
    weights = np.array([max(1e-9,r["projected_minutes"]) * math.exp(
        rng.normal(-sigma*sigma/2,sigma)) for r in active], dtype=float)
    if not np.isfinite(weights).all() or not weights.sum():
        raise ForecastBlocked("NUMERICAL_FAILURE", "minute_weights")
    target = 5. * horizon
    lo, hi = 0., max(horizon/w for w in weights)*2.
    for _ in range(90):
        mid=(hi+lo)/2.
        if np.minimum(mid*weights,horizon).sum() < target:
            lo=mid
        else:
            hi=mid
    minutes=np.minimum(hi*weights,horizon)
    # Correct roundoff without altering caps or the 5-on-court feasibility set.
    err=target-float(minutes.sum())
    if abs(err)>1e-7:
        raise ForecastBlocked("NUMERICAL_FAILURE", "minutes_not_conserved")
    return {r["player_id"]:float(minutes[i]) for i,r in enumerate(active)}


def lineup_segments(minute_map, horizon):
    """Construct an explicit feasible five-at-once schedule from capped totals.

    For a given remaining horizon T, select 5 highest remaining totals including
    any forced (remaining=T). Advance to the next player exhaustion or next
    previously benched player becoming forced. This is a fractional exact
    5-uniform decomposition, not a claimed actual NBA in-game rotation.
    """
    remaining={k:float(v) for k,v in minute_map.items()}
    if abs(sum(remaining.values())-5*horizon)>1e-7 or any(x<-1e-9 or x>horizon+1e-7 for x in remaining.values()):
        raise ForecastBlocked("NUMERICAL_FAILURE","invalid_minute_simplex")
    segments=[]
    clock=float(horizon)
    for _ in range(1024):
        if clock < 1e-7:
            break
        chosen=sorted(remaining,key=lambda k:(-remaining[k],k))[:5]
        if len(chosen)!=5 or any(remaining[k]<=0 for k in chosen):
            raise ForecastBlocked("NUMERICAL_FAILURE","five_on_court_violation")
        unchosen=[k for k in remaining if k not in chosen]
        step=min([clock]+[remaining[k] for k in chosen]+[
            max(0.,clock-remaining[k]) for k in unchosen])
        if step<=1e-9:
            raise ForecastBlocked("NUMERICAL_FAILURE","lineup_decomposition_stalled")
        segments.append({"duration":float(step),"players":sorted(chosen)})
        for k in chosen:
            remaining[k]=max(0.,remaining[k]-step)
        clock-=step
    else:
        raise ForecastBlocked("NUMERICAL_FAILURE","lineup_decomposition_limit")
    if clock>1e-7 or any(x>1e-6 for x in remaining.values()):
        raise ForecastBlocked("NUMERICAL_FAILURE","lineup_ledger_not_conserved")
    return segments


def _pick(weights, rng):
    ids=list(weights)
    vals=np.array([weights[k] for k in ids],dtype=float)
    if vals.sum() <= 0 or not np.isfinite(vals).all():
        raise ForecastBlocked("NUMERICAL_FAILURE","empty_event_pool")
    return ids[int(rng.choice(len(ids),p=vals/vals.sum()))]


def simulate(game, model, *, seed, n=5000, variant="J1"):
    if variant not in ("J0","J1","J2"):
        raise ForecastBlocked("MODEL_NOT_READY","J3_J4_not_fitted")
    if type(seed) is not int or seed<0 or type(n) is not int or not 1<=n<=20000:
        raise ForecastBlocked("NUMERICAL_FAILURE","invalid_seed_or_path_count")
    teams, roster, params, state=_validate(game,model)
    by_team={team:[r for r in roster if r["team_id"]==team] for team in teams}
    rng=np.random.default_rng(seed)
    draws=[]
    for _ in range(n):
        ot=0
        if rng.random() < state["ot_probability"]:
            ot=1
            while ot<4 and rng.random()<state["ot_continuation"]:
                ot+=1
        horizon=48+5*ot
        pace=math.exp(rng.normal(-state["pace_sigma"]**2/2,state["pace_sigma"])) if variant!="J0" else 1.
        minutes={team:_allocate(by_team[team],horizon,rng,
                    0.17 if variant=="J2" else 0.) for team in teams}
        segments={team:lineup_segments(minutes[team],horizon) for team in teams}
        player_counts={r["player_id"]:{"points":0,"rebounds":0,"assists":0,"threes":0,
                       "two_attempts":0,"two_made":0,"three_attempts":0,
                       "ft_attempts":0,"ft_made":0} for r in roster}
        field_goals=[]
        misses={team:0 for team in teams}
        for r in roster:
            pid=r["player_id"]
            m=minutes[r["team_id"]].get(pid,0.)
            if m<=0:
                continue
            p=params[pid]
            two=int(rng.poisson(p["two_attempts_per_minute"]*m*pace))
            three=int(rng.poisson(p["three_attempts_per_minute"]*m*pace))
            ft=int(rng.poisson(p["free_throws_per_minute"]*m*pace))
            twom=int(rng.binomial(two,p["two_pct"]))
            threem=int(rng.binomial(three,p["three_pct"]))
            ftm=int(rng.binomial(ft,p["ft_pct"]))
            c=player_counts[pid]
            c.update(two_attempts=two,two_made=twom,three_attempts=three,
                     threes=threem,ft_attempts=ft,ft_made=ftm,
                     points=2*twom+3*threem+ftm)
            field_goals.extend([(r["team_id"],pid)]*(twom+threem))
            misses[r["team_id"]]+=two-twom+three-threem
        for team, shooter in field_goals:
            if rng.random()<state["assist_probability"]:
                weights={pid:params[pid]["assist_weight"]*m for pid,m in minutes[team].items()
                         if pid!=shooter and m>0}
                if weights and sum(weights.values())>0:
                    player_counts[_pick(weights,rng)]["assists"]+=1
        for team in teams:
            other=teams[1] if team==teams[0] else teams[0]
            for _miss in range(misses[team]):
                side=team if rng.random()<state["offensive_rebound_probability"] else other
                weights={pid:params[pid]["rebound_weight"]*m
                         for pid,m in minutes[side].items() if m>0}
                if weights and sum(weights.values())>0:
                    player_counts[_pick(weights,rng)]["rebounds"]+=1
        for pid,c in player_counts.items():
            if c["threes"]>c["three_attempts"] or c["two_made"]>c["two_attempts"] or \
               c["ft_made"]>c["ft_attempts"] or \
               c["points"]!=2*c["two_made"]+3*c["threes"]+c["ft_made"]:
                raise ForecastBlocked("NUMERICAL_FAILURE","shooting_conservation")
        if sum(c["assists"] for c in player_counts.values())>len(field_goals) or \
           sum(c["rebounds"] for c in player_counts.values())!=sum(misses.values()):
            raise ForecastBlocked("NUMERICAL_FAILURE","event_pool_conservation")
        draws.append({"overtime_periods":ot,"pace_factor":pace,
                      "minutes":minutes,"lineup_segments":segments,
                      "missed_field_goals":misses,"players":player_counts})
    return {"schema":"NBA-P3-JScenarioBank/1","seed":seed,"variant":variant,
            "n":n,"game_hash":digest(game),"model_hash":digest(model),
            "scenario_sha256":digest(draws),"draws":draws}


def player_draws(bank,player_id):
    if not any(player_id in draw["players"] for draw in bank["draws"]):
        raise ForecastBlocked("IDENTITY_UNVERIFIED","player_not_in_game")
    return [d["players"][player_id] for d in bank["draws"]]
