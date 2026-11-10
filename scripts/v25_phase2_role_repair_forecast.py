#!/usr/bin/env python3
"""Phase 2 research-only NFL role-hierarchical target allocation repair.

Retains the exact original immutable as-of week input contract. Uses only
2021–2023 games plus previously revealed 2024 weeks. Team-volume simulations
are reused exactly from the original target-only baseline to isolate allocation.

This is NOT the full route/verified-availability Phase 2 model: weekly box-score
rows identify previous recorded target opportunities, not true active players.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from v25_phase2_target_only_forecast import (
    forecast as original_forecast, history_valid, canonical, stable_seed, reject
)

ROLES = ("WR", "TE", "RB")
ALL_BUCKETS = (*ROLES, "non_target")
VERSION = "v25-p2-role-target-repair-shadow-v1"


def _history_role_pool(history):
    """As-of role population; old-to-new complete team-game ordering only."""
    source = sorted(history, key=lambda g: (
        g["season"],g["week"],g["event_id"],g["team"]))
    total_attempts = 0
    role_totals = defaultdict(int)
    target_positive_counts = defaultdict(int)
    role_presence = defaultdict(int)
    role_games = defaultdict(int)
    all_team_games = defaultdict(lambda:deque(maxlen=6))
    unseen_targets = defaultdict(int)
    for g in source:
        attempts=g["pass_attempts"]
        total_attempts+=attempts
        role_c=defaultdict(int)
        prior_seen = set()
        for old in all_team_games[g["team"]]:
            prior_seen.update(old)
        current_players=set()
        for pid,p in g["players"].items():
            role=p["role"]
            n=p["targets"]
            role_c[role]+=n
            role_presence[role]+=1
            if n>0:
                target_positive_counts[role]+=1
                role_games[role]+=n
            if pid not in prior_seen:
                unseen_targets[role]+=n
            current_players.add(pid)
        for role in ROLES:role_totals[role]+=role_c[role]
        all_team_games[g["team"]].append(current_players)
    if total_attempts<=0 or sum(role_totals.values())>total_attempts:
        reject("invalid_historical_role_targets")
    # Source league role distribution is only past outcomes. Pseudo-counts
    # merely regularize genuinely zero role buckets.
    alpha=np.array([5.+role_totals[r] for r in ROLES]+
        [5.+total_attempts-sum(role_totals.values())],float)
    mean=alpha/alpha.sum()
    role_target_mean={
       r:(role_games[r]+2.)/(target_positive_counts[r]+1.)
       for r in ROLES
    }
    role_hurdle_prior={
       r:(target_positive_counts[r]+1.)/(role_presence[r]+2.)
       if role_presence[r] else .5
       for r in ROLES
    }
    # Expected role-share game-to-game variation from historical team
    # counts; fixed estimation method, NOT fit to 2024 target line success.
    fractions=[]
    for g in source:
        if g["pass_attempts"]<=0:continue
        byrole={r:0 for r in ROLES}
        for p in g["players"].values():byrole[p["role"]]+=p["targets"]
        fractions.append([byrole[r]/g["pass_attempts"] for r in ROLES])
    vals=np.array(fractions,dtype=float)
    concentrations=[]
    if len(vals)>4:
        for i in range(len(ROLES)):
            mu=float(np.mean(vals[:,i]))
            var=float(np.var(vals[:,i],ddof=1))
            if 0<mu<1 and var>0:
                conc=mu*(1-mu)/var-1
                if conc>0:concentrations.append(conc)
    concentration=float(np.median(concentrations)) if concentrations else 20.
    concentration=min(120.,max(5.,concentration))
    # Empirical source-accounting of TARGETS TO NOT PREVIOUSLY OBSERVED
    # players in previous six-game window; it is not an injury forecast.
    others={
       r:(2.+unseen_targets[r])/(10.+role_totals[r])
       for r in ROLES
    }
    return {
      "role_population_share":{r:float(mean[i]) for i,r in enumerate(ALL_BUCKETS)},
      "positive_targets_per_known_targeted_role_player":role_target_mean,
      "observed_player_target_occurrence_rate":role_hurdle_prior,
      "asof_unseen_target_role_share":others,
      "role_share_concentration":concentration,
      "role_training_attempts":total_attempts,
      "role_history_games":len(source),
    }


def _team_and_role_recent(hist, team, cutoff=10):
    games=sorted([x for x in hist if x["team"]==team],
                 key=lambda g:(g["season"],g["week"],g["event_id"]))
    return games[-cutoff:]


def _role_weights(recent, role, prior, *, roster_window=6, prior_player_games=2.):
    """Role-specific uncertain participation and strength, estimated as-of."""
    candidates={}
    for game in recent[-roster_window:]:
        for pid,row in game["players"].items():
            if row["role"]==role:
                candidates[pid]=None
    rows=[]
    for pid in sorted(candidates):
        counts=[(g["players"][pid]["targets"] if pid in g["players"]
                 and g["players"][pid]["role"]==role else 0)
                for g in recent[-roster_window:]]
        historical_positive=sum(v>0 for v in counts)
        last_seen=max((i for i,g in enumerate(recent[-roster_window:])
                       if pid in g["players"]),default=-1)
        last_seen_gap=len(counts)-1-last_seen
        # Empirical-Bayes prior: observed + positive target volume from
        # league/role, rather than treating 1–2 games as true near-zero rate.
        role_average=prior["positive_targets_per_known_targeted_role_player"][role]
        positive_mean=(sum(counts)+prior_player_games*role_average)/(
            historical_positive+prior_player_games)
        occurrence_prior=prior["observed_player_target_occurrence_rate"][role]
        # Weekly box-score appearance is a proxy for a target chance, not
        # verified active-status; shrink weak histories toward role cohort.
        targeted_prob=(historical_positive+4.*occurrence_prior)/(
            roster_window+4.)
        targeted_prob=float(np.clip(targeted_prob,.12,.98))
        rows.append({
          "player_id":pid,"role":role,
          "positive_target_hurdle":targeted_prob,
          "expected_targets_when_targeted":positive_mean,
          "last_seen_games_ago":last_seen_gap,
          "target_history_positive_games":historical_positive,
          "target_history_games_window":roster_window,
        })
    return rows


def _stochastic_allocator(pass_samples, rng, recent, prior, *,
                          use_hurdle=True):
    m=len(pass_samples)
    role_counts=[]
    role_share_base=[]
    for role in ROLES:
        team_role_counts=sum(p["targets"] for g in recent
                             for p in g["players"].values() if p["role"]==role)
        role_share_base.append(team_role_counts)
    team_exposure=sum(g["pass_attempts"] for g in recent)
    historical_non_target=team_exposure-sum(role_share_base)
    if historical_non_target<0:
        reject("invalid_recent_role_opportunity_accounting")
    # All target history (INCLUDING players not in current roster)
    # contributes to team role rates. Historical churn is NOT made into
    # permanent "not targeted" mass.
    league_prior=np.array([
        prior["role_population_share"][role] for role in ALL_BUCKETS],float)
    team_counts=np.array([*role_share_base,historical_non_target],float)
    alpha=70.*league_prior+team_counts
    mean_share=alpha/alpha.sum()
    concentration=prior["role_share_concentration"]
    roster={
       role:_role_weights(recent,role,prior) for role in ROLES
    }
    pred={p["player_id"]:np.zeros(m,dtype=np.int32)
          for role in ROLES for p in roster[role]}
    unassigned=np.zeros(m,dtype=np.int32)
    for s in range(m):
        opportunities=int(pass_samples[s])
        role_share=rng.dirichlet(
            np.maximum(0.00001,mean_share*concentration))
        group_counts=rng.multinomial(opportunities,role_share)
        unassigned[s]+=int(group_counts[3])
        for k,role in enumerate(ROLES):
            n=int(group_counts[k])
            if not n:continue
            eligible=roster[role]
            unseen_base=prior["asof_unseen_target_role_share"][role]
            p_unseen=rng.beta(
                max(1e-5,unseen_base*12.),
                max(1e-5,(1-unseen_base)*12.))
            novel=int(rng.binomial(n,p_unseen))
            unassigned[s]+=novel
            n-=novel
            if not n:continue
            indices=[]
            strength=[]
            for p in eligible:
                active=(not use_hurdle) or (
                    rng.random()<p["positive_target_hurdle"])
                if active:
                    indices.append(p["player_id"])
                    # A role-shrunk target propensity; concentration remains
                    # moderate, so new players are not near-deterministic.
                    strength.append(max(.1,p["expected_targets_when_targeted"]))
            if not indices:
                unassigned[s]+=n
                continue
            # Leave the shape uncertain across games even with 10-game
            # accumulated team exposure; player-specific posterior strength
            # is NOT allowed to be 300+ merely because the QB threw 300.
            rw=np.asarray(strength,dtype=float)
            rw=rw/rw.sum()
            shape=np.maximum(0.1,16.*rw)
            allocation=rng.dirichlet(shape)
            assigned=rng.multinomial(n,allocation)
            for pid,num in zip(indices,assigned):
                pred[pid][s]+=int(num)
    total=np.zeros(m,dtype=np.int32)
    for xs in pred.values():total+=xs
    if np.any(total+unassigned != pass_samples):
        reject("role_allocator_target_conservation")
    return {
       "status":"role_hierarchical_target_only_shadow",
       "player_targets":{pid:xs.tolist() for pid,xs in sorted(pred.items())},
       "pass_attempts":pass_samples.tolist(),
       "unassigned_attempts":unassigned.tolist(),
       "player_count":len(pred),
       "asof_source_roster_proxy":"previous_six_team_game_boxscore_player_ids_not_verified_roster",
       "all_targets_conserved":True,
       "uses_zero_target_participation_hurdle":use_hurdle,
       "uses_actual_2024_current_or_future_stats":False,
    }


def forecast_repaired(payload, *, seed=20261110, samples=512,
                      team_role_prior_attempts=70.):
    if team_role_prior_attempts != 70.:
        reject("research_protocol_locked_role_prior")
    original=original_forecast(payload,seed=seed,samples=samples)
    history=payload["history"]
    week=payload["week"]
    # Role population fitted solely on history already certified by
    # original_forecast.history_valid. Strictly no external live feed.
    prior=_history_role_pool(history)
    if original["train_2024_max_week"]!=week-1:
        reject("role_allocator_future_week_training")
    all_rows=[]
    for x in original["forecasts"]:
        g=dict(x)
        source=g["models"]["updated"]
        if source["status"]!="shadow_target_allocation_without_routes":
            g["models"]["role_repaired"]={"status":"unavailable","reason":source.get("reason")}
            g["models"]["role_no_hurdle"]={"status":"unavailable","reason":source.get("reason")}
            all_rows.append(g)
            continue
        recent=_team_and_role_recent(history,g["team"])
        shared_attempts=np.array(source["pass_attempts"],dtype=np.int32)
        for model,hurdle in (("role_repaired",True),("role_no_hurdle",False)):
            rng=np.random.default_rng(stable_seed(seed,week,g["event_id"],g["team"],model))
            g["models"][model]=_stochastic_allocator(
                shared_attempts,rng,recent,prior,use_hurdle=hurdle)
        all_rows.append(g)
    result={
      "schema":VERSION,
      "week":week,
      "train_2024_max_week":original["train_2024_max_week"],
      "initial_training_game_count":original["initial_training_game_count"],
      "history_game_count":original["history_game_count"],
      "original_input_sha256":original["original_input_sha256"],
      "future_outcomes_exposed_to_forecaster":False,
      "original_current_week_roster_verified":False,
      "posthoc_protocol_selected_after_2024_review":True,
      "player_availability_source":"historical_boxscore_proxy_only",
      "has_actual_route_records":False,
      "promotion_authorized":False,
      "population_prior_diagnostics":prior,
      "seed":seed,"samples":samples,
      "forecasts":all_rows,
    }
    result["forecast_digest"]=hashlib.sha256(canonical(result)).hexdigest()
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--samples",type=int,default=512)
    parser.add_argument("--seed",type=int,default=20261110)
    args=parser.parse_args()
    if args.output.exists():parser.error("immutable_frozen_output_exists")
    raw=args.input.read_bytes()
    if len(raw)>100_000_000:parser.error("oversized_input")
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:reject("duplicate_json_field")
            out[k]=v
        return out
    payload=json.loads(raw,object_pairs_hook=unique)
    res=forecast_repaired(payload,seed=args.seed,samples=args.samples)
    res["original_file_bytes_sha256"]=hashlib.sha256(raw).hexdigest()
    res["run_sha256"]=hashlib.sha256(canonical(res)).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf8") as f:
        json.dump(res,f,sort_keys=True,separators=(",",":"),allow_nan=False)
    print(json.dumps({
      "week":res["week"],"training_latest_week":res["train_2024_max_week"],
      "n_team_forecasts":len(res["forecasts"]),
      "root_sha256":res["run_sha256"],
      "postgame_results_loaded":False,
      "research_only":True,
    },sort_keys=True))


if __name__=="__main__":
    main()
