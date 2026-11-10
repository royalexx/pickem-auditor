#!/usr/bin/env python3
"""Phase 2 NFL target-only as-of forecaster, with no 2024 outcome access.

Input is a deliberately *physically separated* week-specific JSON object
containing historical team-game boxes and an outcome-free schedule.
A separate weekly orchestrator builds this file using 2021–23 games and
only earlier revealed 2024 weeks. It MUST NOT contain current/future totals.
This source cannot use route data: results are P2 target-allocation ablations,
NOT validation of the route-capped/ZIDM model.

python scripts/v25_phase2_target_only_forecast.py \
  --input /tmp/asof_2024_w01.json \
  --output /tmp/frozen_2024_w01.json \
  --seed 20261110 --samples 512
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np


def reject(message):
    raise ValueError("P2_TARGET_ASOF_REJECTED:"+message)


def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()


def stable_seed(*items):
    return int.from_bytes(hashlib.sha256(
        "|".join(map(str,items)).encode()).digest()[:8],"big")


def history_valid(history,week):
    if not isinstance(history,list) or not history:
        reject("no_historical_data")
    seen=set()
    for game in history:
        if set(game)!={"event_id","season","week","team","pass_attempts","players"}:
            reject("unexpected_historical_fields")
        if type(game["season"]) is not int or type(game["week"]) is not int:
            reject("invalid_season_week")
        if (game["season"]>2024 or game["season"]==2024 and game["week"]>=week):
            reject("current_or_future_week_observation")
        if game["season"] not in (2021,2022,2023,2024):
            reject("unregistered_training_season")
        if type(game["pass_attempts"]) is not int or game["pass_attempts"]<0:
            reject("invalid_historical_attempts")
        if not isinstance(game["players"],dict):
            reject("invalid_history_players")
        key=(game["event_id"],game["team"])
        if key in seen:reject("duplicate_history_team_game")
        seen.add(key)
        count=0
        for pid,player in game["players"].items():
            if not pid or set(player)!={"targets","role"}:
                reject("invalid_historical_player")
            n=player["targets"]
            if type(n) is not int or n<0 or player["role"] not in ("WR","RB","TE"):
                reject("invalid_historical_target_or_role")
            count+=n
        if count>game["pass_attempts"]:
            reject("historical_targets_exceed_pass_attempts")


def forecast(payload,*,seed=20261110,samples=512):
    if (not isinstance(payload,dict) or payload.get("schema")!=
            "v25-p2-target-only-asof-week-v1"):
        reject("input_schema")
    week=payload.get("week")
    if type(week) is not int or not 1<=week<=18:
        reject("week_out_of_range")
    if type(samples) is not int or not 128<=samples<=4096:
        reject("simulation_sample_bound")
    hist=payload.get("history")
    history_valid(hist,week)
    season2024=max((x["week"] for x in hist if x["season"]==2024),default=0)
    if season2024!=week-1 and week>1:
        # A team may be on bye, but other league teams must have provided
        # training rows in every prior 2024 week.
        reject("latest_revealed_2024_week_not_previous_week")
    pre=[x for x in hist if x["season"]<2024]
    if len(pre)<1200 or any(x["season"] not in (2021,2022,2023) for x in pre):
        reject("incomplete_pre2024_training_universe")
    league=[x["pass_attempts"] for x in pre]
    mu=float(np.mean(league))
    variance=float(np.var(league,ddof=1))
    dispersion=max(5.,min(80.,mu*mu/max(variance-mu,1.)))
    if not 10<mu<65:
        reject("unreasonable_pre2024_league_mean")
    for schedule in payload.get("schedule",[]):
        if set(schedule)!={"event_id","team","opponent","week"}:
            reject("schedule_contains_outcome_or_unrecognized_feature")
        if schedule["week"]!=week or schedule["team"]==schedule["opponent"]:
            reject("invalid_week_or_matchup_in_schedule")
    schedule=payload.get("schedule")
    if not isinstance(schedule,list) or not schedule:
        reject("empty_pregame_schedule")
    schedule_keys=[(s["event_id"],s["team"]) for s in schedule]
    if len(schedule_keys)!=len(set(schedule_keys)):
        reject("duplicate_pregame_schedule_team")
    pooled=defaultdict(list)
    fixed=defaultdict(list)
    for x in sorted(hist,key=lambda r:(r["season"],r["week"],r["event_id"])):
        pooled[x["team"]].append(x)
        if x["season"]<2024:
            fixed[x["team"]].append(x)
    output=[]
    for game in schedule:
        gameout={"event_id":game["event_id"],"team":game["team"],
                 "week":week,"opponent":game["opponent"],
                 "models":{}}
        for mode,source in (("updated",pooled),("no_refit",fixed)):
            recent=source[game["team"]][-10:]
            if len(recent)<3:
                # Unknown expansion team would require a distinct prior.
                gameout["models"][mode]={"status":"unavailable",
                    "reason":"insufficient_prior_team_games"}
                continue
            team_mu=(5.*mu+sum(x["pass_attempts"] for x in recent))/(5.+len(recent))
            rng=np.random.default_rng(stable_seed(seed,week,game["event_id"],
                                                   game["team"],mode))
            passes=rng.negative_binomial(dispersion,dispersion/(dispersion+team_mu),
                                         size=samples)
            # As-of roster proxy: players with actually known targets/appearances
            # in at least one of the two previous team games. NO current-week
            # player stats, realized routes, snaps, injuries or roster.
            roster={}
            for prior in recent[-2:]:
                for pid,row in prior["players"].items():
                    roster[pid]=row["role"]
            roster={pid:role for pid,role in sorted(roster.items())}
            totals={pid:0 for pid in roster}
            for prev in recent:
                for pid,player in prev["players"].items():
                    if pid in totals:
                        totals[pid]+=player["targets"]
            exposure=sum(x["pass_attempts"] for x in recent)
            counted=sum(totals.values())
            if counted>exposure:
                reject("historical_roster_target_counts_exceed_exposure")
            alphas=np.array([.5+totals[pid] for pid in roster]+
                             [2.+exposure-counted],dtype=float)
            weights=rng.dirichlet(alphas,size=samples)
            target_vector=np.zeros((samples,len(roster)),dtype=np.int32)
            for j in range(samples):
                target_vector[j,:]=rng.multinomial(int(passes[j]),weights[j])[:-1]
            target_samples={pid:target_vector[:,k].astype(int).tolist()
                            for k,pid in enumerate(roster)}
            poisson_samples={}
            for pid in roster:
                # Independent Poisson control uses same as-of player counts.
                lam=(totals[pid]+1.)/(len(recent)+.5)
                separate=np.random.default_rng(stable_seed(
                    seed,week,game["event_id"],game["team"],mode,"poisson",pid))
                poisson_samples[pid]=separate.poisson(lam,size=samples).astype(int).tolist()
            if np.any(target_vector.sum(axis=1)>passes):
                reject("player_target_pool_conservation")
            gameout["models"][mode]={
                "status":"shadow_target_allocation_without_routes",
                "pass_mean":float(np.mean(passes)),
                "pass_attempts":passes.astype(int).tolist(),
                "player_targets":target_samples,
                "independent_poisson_targets":poisson_samples,
                "team_training_game_count":len(recent),
                "known_player_count":len(roster),
                "original_current_week_roster_verified":False,
                "all_targets_conserved":True,
            }
        output.append(gameout)
    return {
      "schema":"v25-p2-target-only-frozen-forecast-v1",
      "training_reference":"2021_2023_plus_past_2024_only",
      "week":week,"train_2024_max_week":season2024,
      "initial_training_game_count":len(pre),
      "history_game_count":len(hist),
      "pre2024_league_attempt_mean":mu,
      "pre2024_dispersion_parameter":dispersion,
      "confidence_not_betting":True,
      "fixed_count_roster_proxy_not_true_routes":True,
      "source_data_asof_publication_independently_certified":False,
      "future_outcomes_exposed_to_forecaster":False,
      "original_input_sha256":hashlib.sha256(canonical(payload)).hexdigest(),
      "samples":samples,"seed":seed,"forecasts":output,
    }


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
    obj=json.loads(raw,object_pairs_hook=unique)
    res=forecast(obj,samples=args.samples,seed=args.seed)
    res["original_file_bytes_sha256"]=hashlib.sha256(raw).hexdigest()
    res["frozen_forecast_sha256"]=hashlib.sha256(canonical(res)).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf8") as handle:
        json.dump(res,handle,sort_keys=True,separators=(",",":"),allow_nan=False)
    print(json.dumps({
        "week":res["week"],"games":len(res["forecasts"]),
        "history_team_games":res["history_game_count"],
        "max_2024_train_week":res["train_2024_max_week"],
        "freeze_sha256":res["frozen_forecast_sha256"],
        "outcome_data_seen":False},sort_keys=True))


if __name__=="__main__":
    main()
