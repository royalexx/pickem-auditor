"""Reform Step 9 — reproducible, read-only same-game leg dependence audit.

Contracts and forecasts are loaded from pinned settlements. Each market is
scored on its *model-chosen pregame side*, not after viewing its outcome.
Pairs/triples are HYPOTHETICAL combinations, not booked entries. The signed
residual product is a diagnostic, not a fitted correlation coefficient;
marginal bias and player-role selection can produce the same signal.

Never assume leg independence in production, and never estimate payout/ROI
from the descriptive hypothetical grid.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
import random

from reform_phase4_scorecard import load_nfl_slate, load_historical, read_json

SCHEMA="pickem-reform-step9-game-leg-dependence-v1"
MIN_DATES_FOR_INTERVAL=20
MIN_GAMES_FOR_INTERVAL=20
MIN_COMBOS_FOR_INTERVAL=100
BOOTSTRAPS=400
SEED=20261108
MAX_LEGS_PER_GAME=75
COHORT_MIN_CONFIDENCE=(0.50,0.60)


class LegDependenceError(ValueError):
    pass


def _prob(value):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value<=1


def _identity(row):
    """Extract exact game/player/stat, without merging multiple betting lines."""
    key=row.get("contract")
    if not isinstance(key,tuple) or len(key) not in (7,8):
        raise LegDependenceError("unrecognized_original_contract_identity")
    if len(key)==8:
        sport,event,team,opponent,player_id,player,stat,line=key
        person=str(player_id)
        if str(event)=="" or not str(opponent):
            raise LegDependenceError("missing_frozen_event_or_opponent")
    else:
        day,sport,gid,team,player,stat,line=key
        if str(day)!=str(row.get("date")) or str(gid)!=str(row.get("game_id")):
            raise LegDependenceError("retrospective_contract_game_mismatch")
        person=str(player)
    if not all([sport,team,person,stat,line]):
        raise LegDependenceError("missing_exact_contract_identity")
    return (str(sport),str(row["date"]),str(row["game_id"]),
            str(team),person,str(stat)),tuple(str(v) for v in key)


def eligible_legs(rows, *, model, minimum_probability=0.50,
                  historically_reliable_only=False):
    if not _prob(minimum_probability) or minimum_probability<.5:
        raise LegDependenceError("invalid_pregame_confidence_floor")
    by_game=defaultdict(list)
    rejected=Counter()
    dedupe={}
    for row in rows:
        if historically_reliable_only and row.get("original_reliable") is not True:
            rejected["historically_unqualified"]+=1
            continue
        leg=(row.get("models") or {}).get(model)
        if leg is None:
            rejected["model_unavailable"]+=1
            continue
        if leg.get("side") not in ("under","over") or leg.get("winner") not in ("under","over"):
            rejected["invalid_original_direction"]+=1
            continue
        if (not all(_prob(leg.get(k)) for k in ("p","over","under"))
                or abs(leg["over"]+leg["under"]-1)>1e-8):
            rejected["noncomplementary_model_probability"]+=1
            continue
        if (not math.isclose(leg["p"],leg[leg["side"]],abs_tol=1e-8)
                or leg["p"]<minimum_probability):
            rejected["under_confidence_floor_or_inconsistent_selected_side"]+=1
            continue
        if type(leg.get("hit")) is not int or leg["hit"] not in (0,1):
            rejected["unverified_binary_outcome"]+=1
            continue
        if leg["hit"]!=int(leg["side"]==leg["winner"]):
            raise LegDependenceError("mismatched_official_outcome_and_model_side")
        player_key,contract=_identity(row)
        if contract in dedupe:
            raise LegDependenceError("duplicate_original_settled_contract")
        p=float(leg["p"])
        dedupe[contract]={"date":str(row["date"]),"sport":str(row["sport"]),
                          "game_id":str(row["game_id"]),"team":player_key[3],
                          "player_key":player_key,"contract":contract,
                          "stat":str(row["stat"]),"side":leg["side"],
                          "p":p,"hit":leg["hit"]}
    # Multiple lines for the SAME player+stat/game can produce nearly
    # deterministic relationships. Remove every ambiguous such contract,
    # instead of choosing the successful line after settlement.
    by_player_market=defaultdict(list)
    for leg in dedupe.values():
        by_player_market[leg["player_key"]].append(leg)
    for group in by_player_market.values():
        if len(group)>1:
            rejected["ambiguous_player_stat_multiple_lines"]+=len(group)
            continue
        leg=group[0]
        by_game[(leg["sport"],leg["date"],leg["game_id"])].append(leg)
    for key,legs in by_game.items():
        if len(legs)>MAX_LEGS_PER_GAME:
            raise LegDependenceError("too_many_hypothetical_legs_in_one_game")
        legs.sort(key=lambda x:x["contract"])
    return by_game,dict(rejected)


def categorize(legs):
    if len(legs)==2:
        a,b=legs
        same_player=a["player_key"][4]==b["player_key"][4] and a["team"]==b["team"]
        if same_player:
            return "same_player_different_stats"
        if a["team"]==b["team"]:
            return "teammates"
        return "opponents"
    return "all_distinct_pair_types"


def combine_legs(by_game, *, length):
    if length not in (2,3):
        raise LegDependenceError("unsupported_leg_count")
    out=[]
    for (sport,day,gid),legs in sorted(by_game.items()):
        for group in combinations(legs,length):
            p=math.prod(x["p"] for x in group)
            all_hit=int(all(x["hit"] for x in group))
            if any(x["game_id"]!=gid or x["date"]!=day for x in group):
                raise LegDependenceError("cross_game_or_date_combinations_forbidden")
            out.append({
                "sport":sport,"date":day,"game_id":gid,
                "n_legs":length,"pair_type":categorize(group),
                "same_stat":len({x["stat"] for x in group})==1,
                "direction_type":("both_over" if all(x["side"]=="over" for x in group)
                                  else "both_under" if all(x["side"]=="under" for x in group)
                                  else "mixed_directions"),
                "joint_hit":all_hit,
                "independence_probability":p,
                "independence_minus_realized":p-all_hit,
                "excess_joint_hit_vs_independent":all_hit-p,
                "residual_product":(math.prod(x["hit"]-x["p"] for x in group)
                                    if length==2 else None)})
    return out


def _summary(grid, *, bootstraps=BOOTSTRAPS,seed=SEED):
    if not grid:
        return {"hypothetical_combinations":0,
                "independent_games":0,"independent_dates":0,
                "status":"no_eligible_same_game_combinations",
                "interval_95":None}
    grouped=defaultdict(list)
    for event in grid:
        grouped[(event["date"],event["game_id"])].append(event)
    dates=sorted({d for d,_ in grouped})
    games=len(grouped)
    def by_game_values(source):
        g=defaultdict(list)
        for event in source:
            g[(event["date"],event["game_id"])].append(event)
        values=[]
        for legs in g.values():
            n=len(legs)
            values.append((
                sum(x["joint_hit"] for x in legs)/n,
                sum(x["independence_probability"] for x in legs)/n,
                sum(x["excess_joint_hit_vs_independent"] for x in legs)/n,
                (sum(x["residual_product"] for x in legs)/n
                 if legs[0]["n_legs"]==2 else None)))
        return values
    vg=by_game_values(grid)
    n=len(grid)
    summary={
        "hypothetical_combinations":n,
        "independent_games":games,"independent_dates":len(dates),
        "all_hit_rate_pair_weighted":sum(x["joint_hit"] for x in grid)/n,
        "independence_product_pair_weighted":sum(x["independence_probability"] for x in grid)/n,
        "all_hit_rate_game_weighted":sum(x[0] for x in vg)/games,
        "independence_product_game_weighted":sum(x[1] for x in vg)/games,
        "joint_excess_game_weighted":sum(x[2] for x in vg)/games,
        "mean_signed_probability_residual_product_game_weighted":
            sum(x[3] for x in vg)/games if grid[0]["n_legs"]==2 else None,
        "method":"game_equal_weight_joint_hit_vs_frozen_independent_probability",
        "not_a_estimated_joint_copula_or_approved_correlation":True,
        "status":"descriptive_low_independent_date_coverage",
        "interval_95":None}
    if (len(dates)<MIN_DATES_FOR_INTERVAL or
            games<MIN_GAMES_FOR_INTERVAL or n<MIN_COMBOS_FOR_INTERVAL):
        return summary
    # Re-sample WHOLE original game dates. Once a date is selected, every
    # associated game enters with equal weight; never bootstrap prop pairs.
    by_date=defaultdict(list)
    for vals in vg:
        pass
    for game_key,events in grouped.items():
        by_date[game_key[0]].append(
            sum(x["excess_joint_hit_vs_independent"] for x in events)/len(events))
    rng=random.Random(seed)
    sample=[]
    for _ in range(bootstraps):
        selected=rng.choices(dates,k=len(dates))
        values=[v for date in selected for v in by_date[date]]
        sample.append(sum(values)/len(values))
    sample.sort()
    summary["status"]="descriptive_date_block_interval_not_production_covariance"
    summary["interval_95"]=[sample[int(.025*bootstraps)],
                            sample[int(.975*bootstraps)-1]]
    summary["bootstraps"]=bootstraps
    return summary


def analyze(rows, *, model, reliable_only=False):
    cohorts={}
    for min_p in COHORT_MIN_CONFIDENCE:
        by_game,rejected=eligible_legs(rows,model=model,
                         minimum_probability=min_p,
                         historically_reliable_only=reliable_only)
        all_legs=[x for group in by_game.values() for x in group]
        combos={}
        for n in (2,3):
            grid=combine_legs(by_game,length=n)
            categories={}
            if n==2:
                for label in ("same_player_different_stats","teammates","opponents"):
                    categories[label]=_summary([x for x in grid if x["pair_type"]==label])
                for label in ("both_over","both_under","mixed_directions"):
                    categories[label]=_summary([x for x in grid if x["direction_type"]==label])
            combos[str(n)]={"all":_summary(grid),"subgroups":categories}
        cohorts[f"{min_p:.2f}"]={
            "legs":len(all_legs),
            "unique_games_with_legs":len(by_game),
            "counts_excluded":rejected,"combinations":combos}
    return {"model":model,"historically_reliable_only":reliable_only,
            "cohorts":cohorts,
            "source_contract_count":len(rows),
            "mode":"same_game_hypothetical_2_and_3_leg_research_only"}


def audit(*,frozen,settlement,pinned,historical,archive_root):
    nfl,source=load_nfl_slate(frozen,settlement,pinned)
    past,older=load_historical(historical,archive_root)
    results={
      "schema":SCHEMA,
      "status":"descriptive_only_cannot_fit_portfolio_correlation",
      "training_started":False,"production_changed":False,
      "entry_probability_model_deployed":False,
      "new_bet_recommendations":False,
      "source_sha256":{"frozen":read_json(frozen)[1],
                       "settlement":read_json(settlement)[1],
                       "pinned":read_json(pinned)[1],
                       "historical":read_json(historical)[1]},
      "cohorts":{
          "current_2026_11_08_original_60_40":analyze(nfl,model="Consensus"),
          "older_2026_11_05_07_engine_a":analyze(past,model="Engine_A"),
          "older_historically_reliable_engine_a":analyze(
              past,model="Engine_A",reliable_only=True)},
      "independence_is_not_validated":True,
      "inference_blocked_reasons":[
          "Only one current-production slate date with six NFL kickoff games",
          "Retrospective older policy has three dates, is not current frozen 60/40",
          "Historical feature-source publication timing not independently complete",
          "Many hypothetical combinations share players, games and line signals, so pair count is not sample size",
          "Observed pair excess can reflect marginal calibration bias and opponent game script",
          "These are hypothetical portfolios; original wager entries and pay tables are not archived",
          "Covariance coefficients cannot be promoted without independent future dates and games"],
      "limitations":[
          "Never multiply individual leg probabilities to claim a real entry edge",
          "Model-picked sides are fixed before settlement; outcomes only label hit or miss",
          "Same player+stat multiple lines removed entirely to prevent pseudo-independent duplicate legs",
          "Same-game combinations are exhaustive hypothetical pairs/triples, not recommended entries",
          "Date-block intervals require >=20 independent dates, >=20 games and >=100 combinations",
          "No statistical test from this archive can certify a universal joint distribution",
          "Separate legacy and current-policy cohorts are never pooled for predictive promotion"]}
    return results


def main(argv=None):
    parser=argparse.ArgumentParser()
    for k in ("frozen","settlement","pinned","historical","archive_root"):
        parser.add_argument("--"+k.replace("_","-"),type=Path,required=True)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args(argv)
    report=audit(frozen=args.frozen,settlement=args.settlement,
                 pinned=args.pinned,historical=args.historical,
                 archive_root=args.archive_root)
    data=json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+"\n"
    if args.out:
        if args.out.exists() and args.out.read_text()!=data:
            raise LegDependenceError("would_overwrite_previous_immutable_audit_receipt")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(data)
    print(json.dumps({"status":report["status"],
                      "cohorts":{k:{
                        f"{p}_{n}":{
                          "legs":v["legs"],
                          "combinations":v["combinations"][n]["all"]}
                         for p,v in cohort["cohorts"].items()
                         for n in ("2","3")}
                      for k,cohort in report["cohorts"].items()}},
                     sort_keys=True))


if __name__=="__main__":
    main()
