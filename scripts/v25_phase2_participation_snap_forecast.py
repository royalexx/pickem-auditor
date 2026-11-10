#!/usr/bin/env python3
"""P2 actual participation/opportunity research, never postgame feature input.

Forecasting uses historical player ID + already finished NFL offensive snaps,
historical targets, source-labelled lagged roster membership, and timestamped
pregame injury *reports*. It does NOT treat snaps as routes; does NOT infer
a current-week starter from current-week box scores; and does NOT certify
post-hoc source publication. Unidentified current roster players abstain.
All count scenarios conserve attempts across role/players/non-target/unknown.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

from v25_phase2_target_only_forecast import (
    forecast as original_forecast, canonical, stable_seed, reject)

ROLES=("WR","TE","RB")
MODEL="participation_snap"
ABLATION="participation_no_hurdle"
VERSION="v25-p2-lagged-snap-participation-v1"

def _prob(x):
    return float(np.clip(x,.005,.995))

def _asof_exposure_validation(payload):
    week=payload.get("week")
    roster=payload.get("lagged_roster_context")
    snaps=payload.get("lagged_snap_context")
    injuries=payload.get("dated_pregame_injury_context")
    if not isinstance(roster,list) or not isinstance(snaps,list) or not isinstance(injuries,list):
        reject("missing_player_participation_source_inputs")
    prior_week=lambda s,w:(s<2024 or s==2024 and w<week)
    rfields={"season","week","team","player_id","role","status","source_claim"}
    sfields={"season","week","team","player_id","role","offense_snaps",
             "offense_pct","team_plays","source_claim"}
    ifields={"week","event_id","team","player_id","role","report_status",
             "date_modified","freeze_at","source_claim"}
    seen=set()
    for raw in roster:
        if not isinstance(raw,dict) or set(raw)!=rfields:
            reject("lagged_roster_contract_error")
        s,w=raw["season"],raw["week"]
        if type(s)!=int or type(w)!=int or not prior_week(s,w):
            reject("current_or_future_roster_snapshot_forbidden")
        if raw["source_claim"]!="prior_week_archive_unverified_original_capture":
            reject("lagged_roster_source_claim_invalid")
        if raw["role"] not in ROLES or not raw["player_id"] or not raw["team"]:
            reject("lagged_roster_player_identity")
        if raw["status"] not in ("ACT","INA","RES","DEV","CUT","OTHER"):
            reject("unknown_historical_roster_status")
        key=(s,w,raw["team"],raw["player_id"])
        if key in seen:reject("duplicate_lagged_roster_snapshot")
        seen.add(key)
    seen=set()
    for raw in snaps:
        if not isinstance(raw,dict) or set(raw)!=sfields:
            reject("lagged_snap_contract_error")
        s,w=raw["season"],raw["week"]
        if type(s)!=int or type(w)!=int or not prior_week(s,w):
            reject("current_or_future_snap_label_forbidden")
        if raw["source_claim"]!="previously_finished_game_postgame_exposure":
            reject("prior_snap_source_claim_invalid")
        if raw["role"] not in ROLES or not raw["player_id"] or not raw["team"]:
            reject("lagged_snap_identity_invalid")
        for key in ("offense_snaps","offense_pct","team_plays"):
            value=raw[key]
            if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<0:
                reject("lagged_snap_nonnegative_required")
        if raw["offense_pct"]>1.01 or raw["offense_snaps"]>raw["team_plays"]+1:
            reject("lagged_snap_physical_breach")
        key=(s,w,raw["team"],raw["player_id"])
        if key in seen:reject("duplicate_lagged_snap")
        seen.add(key)
    for raw in injuries:
        if not isinstance(raw,dict) or set(raw)!=ifields:
            reject("current_injury_contract_error")
        if type(raw["week"])!=int or raw["week"]!=week:
            reject("injury_from_other_week")
        if raw["source_claim"]!="retrospectively_retrieved_dated_report_not_original_capture":
            reject("current_injury_must_be_downgraded")
        if raw["role"] not in ROLES or not raw["player_id"]:
            reject("current_injury_role_or_identity")
        if raw["report_status"] not in ("Out","Doubtful","Questionable","Note","Unspecified"):
            reject("injury_status_unregistered")
        if not isinstance(raw["date_modified"],str) or not isinstance(raw["freeze_at"],str):
            reject("injury_missing_timestamps")
        from datetime import datetime, timezone
        try:
            a=datetime.fromisoformat(raw["date_modified"].replace("Z","+00:00"))
            b=datetime.fromisoformat(raw["freeze_at"].replace("Z","+00:00"))
        except ValueError:
            reject("injury_invalid_timestamp")
        if a.tzinfo is None or b.tzinfo is None or a>b:
            reject("injury_after_forecast_freeze")
    return roster,snaps,injuries

def _posterior_context(history,snaps):
    history_lookup={(g["season"],g["week"],g["team"]):g for g in history}
    player_games=defaultdict(list)
    roles=defaultdict(list)
    for x in snaps:
        key=(x["season"],x["week"],x["team"])
        game=history_lookup.get(key)
        if game is None:continue
        role=x["role"]
        target=game["players"].get(x["player_id"],{}).get("targets",0)
        if target>x["offense_snaps"]:
            # A few source-ID mismatches are invalid, not high target rates.
            continue
        entry={**x,"targets":target,
               "team_pass_attempts":game["pass_attempts"]}
        player_games[(x["team"],x["player_id"])].append(entry)
        roles[role].append(entry)
    prior={}
    for role in ROLES:
        rows=roles[role]
        if len(rows)<100:
            reject("insufficient_asof_participation_role_source_"+role)
        positive=[x for x in rows if x["offense_snaps"]>0]
        target_sum=sum(x["targets"] for x in positive)
        snap_sum=sum(x["offense_snaps"] for x in positive)
        mean_snap_share=np.mean([x["offense_pct"] for x in positive]) if positive else .4
        prior[role]={
          "p_appearance":(sum(x["offense_snaps"]>0 for x in rows)+1)/(len(rows)+2),
          "mean_snap_share":float(mean_snap_share),
          "target_rate_per_snap":(target_sum+1)/(snap_sum+8),
          "active_zero_target_frequency":(
              sum(x["offense_snaps"]>0 and x["targets"]==0 for x in rows)
              /max(1,len(positive))),
          "matched_past_snap_records":len(rows),
        }
    return player_games,prior

def _lagged_roster_candidates(frozen,roster,injuries):
    week=frozen["week"]
    full=defaultdict(list)
    for x in roster:
        full[x["player_id"]].append(x)
    latest={}
    for pid,history in full.items():
        history.sort(key=lambda r:(r["season"],r["week"]))
        latest[pid]=history[-1]
    byteam=defaultdict(dict)
    for pid,x in latest.items():
        if x["role"] not in ROLES or x["status"] in ("CUT","RES","DEV"):
            continue
        # Limit stale candidates to previous three weeks in the same
        # season, or Week 18 of 2023 in the Week 1 preseason fallback.
        if x["season"]==2024:
            age=week-x["week"]
            if not 1<=age<=3:continue
        elif week<=2 and x["season"]==2023:
            age=4+week
        else:continue
        byteam[x["team"]][pid]={
          "player_id":pid,"role":x["role"],"status":x["status"],
          "stale_weeks":age,"source":"lagged_roster_only",
        }
    # Historical date_modified pregame report may identify a newly
    # acquired/rookie player even when last week's roster never did.
    # It is an unverified retrospective source, never a certified OUT.
    for x in injuries:
        team,pid=x["team"],x["player_id"]
        latest_prior=latest.get(pid)
        if latest_prior is not None and latest_prior["season"]==2024 and latest_prior["team"]!=team:
            continue
        prior=byteam[team].get(pid)
        if prior is None:
            byteam[team][pid]={
              "player_id":pid,"role":x["role"],"status":"OTHER",
              "stale_weeks":9,"source":"dated_injury_only_new_entrant",
            }
    injury_map={(x["event_id"],x["team"],x["player_id"]):x
                for x in injuries}
    return byteam,injury_map

def _role_probabilities(history,team,league_pseudocount=7.):
    recent=sorted((x for x in history if x["team"]==team),
                  key=lambda x:(x["season"],x["week"],x["event_id"]))[-10:]
    if len(recent)<3:return None
    count={role:0. for role in ROLES}
    att=0.
    for x in recent:
        att+=x["pass_attempts"]
        for p in x["players"].values():
            count[p["role"]]+=p["targets"]
    if sum(count.values())>att:reject("role_team_accounting_invalid")
    # Role rates include ALL historical receivers, not just players who
    # appeared on the short-term eligible roster. Historical churn is
    # therefore represented as role opportunity, not permanent non-target.
    non_target=att-sum(count.values())
    return recent,np.array([count[role] for role in ROLES]+[non_target])

def _one_team(team,passes,roster_candidates,injury_map,
              player_games,role_population,history,seed,week,event,method):
    samples=len(passes)
    game=_role_probabilities(history,team)
    if game is None:return {"status":"insufficient_asof_team_history"}
    past,role_counts=game
    rng=np.random.default_rng(stable_seed(seed,week,event,team,method))
    team_passes=np.array(passes,dtype=int)
    team_plays_mean=np.mean([
        x["team_plays"] for (tm,pid),rows in player_games.items() if tm==team
        for x in rows[-2:]]) if any(tm==team for tm,pid in player_games) else 64.
    # A projection of offensive plays, learned from previous games only.
    # Plays >= pass attempts for every scenario; broad game-to-game spread.
    historical_passing_share=np.clip(
        np.mean([x["pass_attempts"] for x in past])/max(1.,team_plays_mean),
        .35,.85)
    prospective_plays=np.maximum(team_passes,rng.negative_binomial(
        35.,35./(35.+np.maximum(team_passes/historical_passing_share,1.)),
        size=samples))
    active_players={}
    forecasted={}
    for pid,player in sorted(roster_candidates.items()):
        role=player["role"]
        old=sorted(player_games.get((team,pid),[]),
                   key=lambda r:(r["season"],r["week"]))[-8:]
        # Cross-team transfers and rookies inherit role priors. Missing
        # snap rows never create a false verified inactive player.
        p0=role_population[role]
        participation=(3.*p0["p_appearance"]+
                       sum(x["offense_snaps"]>0 for x in old))/(3.+len(old))
        if old and old[-1]["offense_snaps"]>0:
            participation=.15+.85*participation
        if player["status"]=="INA":
            participation*=.70
        if player["stale_weeks"]>2:
            participation*=.8
        injury=injury_map.get((event,team,pid))
        if injury is not None:
            status=injury["report_status"]
            if status=="Out":
                # Deliberately not absolute zero: no original capture proof.
                participation=min(participation,.08)
            elif status=="Doubtful":
                participation=min(participation,.25)
            elif status=="Questionable":
                participation*=.75
        participation=_prob(participation)
        snap_share=(5.*p0["mean_snap_share"]+
                    sum(x["offense_pct"] for x in old if x["offense_snaps"]>0)) / (
                    5.+sum(x["offense_snaps"]>0 for x in old))
        snap_share=_prob(snap_share)
        old_snap=sum(x["offense_snaps"] for x in old)
        old_targets=sum(x["targets"] for x in old)
        # Player-specific rate per offensive snap, partially pooled to
        # a role prior. Zero-target playing games enter rate denominator.
        target_rate=(100.*p0["target_rate_per_snap"]+old_targets)/(100.+old_snap)
        if target_rate<0 or target_rate>1:reject("invalid_player_snap_target_rate")
        p_sample=rng.beta(
            max(.1,participation*8.),max(.1,(1-participation)*8.),
            size=samples)
        p_active=rng.random(samples)<p_sample if method=="participation_snap" else np.ones(samples,dtype=bool)
        sn_frac=rng.beta(max(.25,snap_share*7.),max(.25,(1-snap_share)*7.),size=samples)
        sn_num=rng.binomial(prospective_plays,sn_frac)
        sn_num=np.where(p_active,sn_num,0)
        # Beta target-per-offensive-snap posterior uncertainty is NOT
        # collapsed using all team attempts as effective player samples.
        tper=rng.beta(max(.1,target_rate*60.),max(.1,(1-target_rate)*60.),size=samples)
        weight=sn_num*tper
        forecasted[pid]={"weight":weight,"snap_num":sn_num,
                         "p_active":participation,"role":role,
                         "no_history_games":len(old)==0,
                         "status_claim":"unverified_retrospective_proxy",
                         "latest_status":player["status"],
                         "reported_injury":injury["report_status"] if injury else None}
    # A dynamic role pool from all past target recipients, not a fixed
    # bucket containing every historical departed player's targets.
    league_sum=np.array([
        role_population[r]["target_rate_per_snap"] * role_population[r]["mean_snap_share"]
        for r in ROLES]+[.18],dtype=float)
    league_sum=league_sum/league_sum.sum()
    concentration=18. # broad across-game state, fixed before 2024 ablation
    alpha=role_counts+max(1.,len(past))*league_sum
    role_mean=alpha/alpha.sum()
    role_share=rng.dirichlet(np.maximum(.01,role_mean*concentration),size=samples)
    target_draws={pid:np.zeros(samples,dtype=int) for pid in forecasted}
    unknown_receivers=np.zeros(samples,dtype=int)
    non_target_attempts=np.zeros(samples,dtype=int)
    for s in range(samples):
        n=int(team_passes[s])
        rc=rng.multinomial(n,role_share[s])
        non_target_attempts[s]=int(rc[3])
        for k,role in enumerate(ROLES):
            total=int(rc[k])
            if not total:continue
            ids=[pid for pid,row in forecasted.items() if row["role"]==role]
            weights=np.array([forecasted[pid]["weight"][s] for pid in ids],float)
            available=np.array([max(0,forecasted[pid]["snap_num"][s]
                                -target_draws[pid][s]) for pid in ids],int)
            weights=np.where(available>0,weights,0.)
            # Chance of a target to a *truly unrepresented* receiver, not
            # historical departed-player mass treated as a throwaway.
            # Role population prior prevents degenerate loss of unseen mass.
            unseen_weight=(
                np.mean(weights[weights>0])*.08 if np.any(weights>0) else 1.)
            allocation=np.zeros(len(ids),dtype=int)
            for _ in range(total):
                eligible=np.where(available>0,weights,0.)
                positive=np.sum(eligible)
                if positive<=0:
                    unknown_receivers[s]+=1
                    continue
                probs=np.r_[eligible,unseen_weight]
                probs=probs/probs.sum()
                index=int(rng.choice(len(probs),p=probs))
                if index==len(ids):
                    unknown_receivers[s]+=1
                else:
                    allocation[index]+=1
                    available[index]-=1
            for pid,num in zip(ids,allocation):
                target_draws[pid][s]+=num
    if any(np.any(target_draws[pid]>forecasted[pid]["snap_num"])
           for pid in forecasted):
        reject("player_targets_more_than_projected_offensive_snaps")
    total=sum(target_draws.values(),np.zeros(samples,dtype=int))
    if np.any(total+unknown_receivers+non_target_attempts!=team_passes):
        reject("team_target_conservation_failed")
    return {
      "status":"retrospective_participation_snap_challenger_not_certified",
      "pass_attempts":team_passes.tolist(),
      "offensive_plays":prospective_plays.astype(int).tolist(),
      "player_targets":{pid:xs.astype(int).tolist() for pid,xs in target_draws.items()},
      "player_roles":{pid:row["role"] for pid,row in forecasted.items()},
      "player_activity_diagnostics":{pid:{
          "p_active":row["p_active"],"no_prior_snap_history":row["no_history_games"],
          "latest_status":row["latest_status"],"injury":row["reported_injury"],
          "source_certified":False,
       } for pid,row in forecasted.items()},
      "unknown_receiver_targets":unknown_receivers.astype(int).tolist(),
      "non_target_attempts":non_target_attempts.astype(int).tolist(),
      "snap_exposure_not_routes":True,
      "no_current_game_realized_features":True,
      "conservation_ok":True,
    }

def forecast_participation(payload,*,seed=20261110,samples=512):
    original=original_forecast(payload,seed=seed,samples=samples)
    roster,snaps,injuries=_asof_exposure_validation(payload)
    hist=payload["history"]
    player_games,population=_posterior_context(hist,snaps)
    candidates,injury_map=_lagged_roster_candidates(original,roster,injuries)
    result=[]
    for game in original["forecasts"]:
        team=game["team"]
        row={**game,"models":dict(game["models"])}
        old=row["models"]["updated"]
        for method in (MODEL,ABLATION):
            row["models"][method]=(
                {"status":"original_team_volume_unavailable"} if
                old["status"]!="shadow_target_allocation_without_routes" else
                _one_team(team,old["pass_attempts"],candidates.get(team,{}),
                          injury_map,player_games,population,hist,seed,
                          payload["week"],row["event_id"],method))
        result.append(row)
    out={
      "schema":VERSION,"week":payload["week"],
      "train_2024_max_week":original["train_2024_max_week"],
      "original_input_sha256":original["original_input_sha256"],
      "source_kind":"retrospective_lagged_roster_prior_snaps_dated_injuries",
      "prior_week_status_not_original_pregame_certified":True,
      "2024_injury_source_original_capture_verified":False,
      "true_receiver_routes_available":False,
      "current_or_future_game_stats_exposed":False,
      "pre2024_participation_source_rows":len(snaps),
      "asof_lagged_roster_rows":len(roster),
      "asof_dated_injury_rows":len(injuries),
      "population_role_priors":population,
      "models_preserved":["updated","no_refit","independent_poisson"],
      "promotion_authorized":False,
      "forecasts":result,
    }
    out["content_sha256"]=hashlib.sha256(canonical(out)).hexdigest()
    return out

def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--seed",type=int,default=20261110)
    parser.add_argument("--samples",type=int,default=512)
    args=parser.parse_args(argv)
    if args.output.exists():parser.error("immutable_output_exists")
    raw=args.input.read_bytes()
    if len(raw)>160_000_000:parser.error("input_oversize")
    def no_duplicate(pairs):
        obj={}
        for k,v in pairs:
            if k in obj:reject("duplicate_json_keys")
            obj[k]=v
        return obj
    payload=json.loads(raw,object_pairs_hook=no_duplicate)
    result=forecast_participation(payload,seed=args.seed,samples=args.samples)
    result["original_file_bytes_sha256"]=hashlib.sha256(raw).hexdigest()
    result["receipt_sha256"]=hashlib.sha256(canonical(result)).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf8") as f:
        json.dump(result,f,sort_keys=True,separators=(",",":"),allow_nan=False)
    print(json.dumps({"week":result["week"],"n_teams":len(result["forecasts"]),
                      "receipt":result["receipt_sha256"],
                      "latest_training_week":result["train_2024_max_week"],
                      "future_outcomes_exposed":False,
                      "source_certified":False},sort_keys=True))

if __name__=="__main__":
    raise SystemExit(main())
