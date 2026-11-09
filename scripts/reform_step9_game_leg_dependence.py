"""Reform Step 9: same-game leg dependence and false-independence controls.

Research-only, read-only, original settlement. A game offers many pairs,
but NOT many independent observations. This module never trains a joint
distribution, manufactures a correlation coefficient, or authorizes an
independence-product entry payout probability.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import itertools
import json
import math
from pathlib import Path
import random

from reform_phase4_scorecard import load_nfl_slate, load_historical, read_json
from reform_step8_market_shadow import proper_pair

SCHEMA="pickem-reform-step9-game-leg-dependence-v1"
BOOTSTRAP_SEED=20261109
MIN_GAMES_FOR_DESCRIPTIVE_CI=20
MIN_DATES_FOR_DESCRIPTIVE_CI=10
MIN_PAIRS_FOR_DESCRIPTIVE_CI=100


class LegDependenceError(ValueError):
    pass


def leg_from_contract(row, *, model, source):
    """One original settled, nonpush, coherent TWO-sided contract -> one leg."""
    if source not in ("nov8_current","nov5_7_retrospective"):
        raise LegDependenceError("invalid_leg_archive_origin")
    if row.get("outcome") not in ("over","under"):
        raise LegDependenceError("unsettled_or_push_leg")
    m=(row.get("models") or {}).get(model)
    if m is None:
        return None,"model_unavailable"
    if not proper_pair(m):
        return None,"noncomplementary_or_invalid_original_pair"
    side=m.get("side")
    if side not in ("over","under") or not 0<=m.get("p",-1)<=1:
        raise LegDependenceError("unmatched_frozen_model_direction")
    if m.get("hit") != int(side==row["outcome"]) or abs(m["p"]-m[side])>1e-10:
        raise LegDependenceError("model_probabilities_not_same_frozen_side")
    key=row.get("contract")
    if not isinstance(key,tuple) or len(key)!=8:
        raise LegDependenceError("invalid_exact_contract")
    if source=="nov8_current":
        sport,_,team,opponent,player_id,player_name,stat,_line=key
    else:
        _date,sport,_event,team,player_name,stat,_line=key
        # Historical legacy contract key has SEVEN members, so source
        # evolution must be checked explicitly before interpreting fields.
        raise LegDependenceError("unexpected_historical_contract_layout")
    if str(sport)!=str(row.get("sport")) or str(stat)!=str(row.get("stat")):
        raise LegDependenceError("settled_contract_market_identity_changed")
    if not row.get("date") or not row.get("game_id") or not str(player_id):
        raise LegDependenceError("missing_game_date_or_player_identity")
    return {
        "sport":str(sport),"date":str(row["date"]),
        "game_id":str(row["game_id"]),"team":str(team),
        "player_id":str(player_id),"player":str(player_name),
        "stat":str(stat),"line":str(key[-1]),
        "side":side,"p":float(m["p"]),"hit":int(m["hit"]),
        "contract":key,
        "same_contract_original_outcome":row["outcome"],
    },None


def leg(row, *, model, source):
    """Legacy research keys: (date,sport,game_id,team,player,stat,line)."""
    if source=="nov5_7_retrospective":
        key=row.get("contract")
        if not isinstance(key,tuple) or len(key)!=7:
            raise LegDependenceError("invalid_legacy_contract_layout")
        if (key[0]!=row.get("date") or key[1]!=row.get("sport") or
                str(key[2])!=str(row.get("game_id")) or key[5]!=row.get("stat")):
            raise LegDependenceError("legacy_contract_game_mismatch")
        m=(row.get("models") or {}).get(model)
        if m is None:return None,"model_unavailable"
        if not proper_pair(m):return None,"noncomplementary_or_invalid_original_pair"
        side=m.get("side")
        if side not in ("over","under") or m.get("hit")!=int(side==row.get("outcome")):
            raise LegDependenceError("legacy_side_inconsistent_with_original_outcome")
        if abs(m["p"]-m[side])>1e-10:
            raise LegDependenceError("legacy_probability_direction_mismatch")
        return {"sport":str(row["sport"]),"date":str(row["date"]),
                "game_id":str(row["game_id"]),"team":str(key[3]),
                "player_id":str(key[4]),"player":str(key[4]),
                "stat":str(key[5]),"line":str(key[6]),
                "side":side,"p":float(m["p"]),"hit":int(m["hit"]),
                "contract":key,
                "same_contract_original_outcome":row["outcome"]},None
    return leg_from_contract(row,model=model,source=source)


def validated_legs(rows, *, model, source):
    results=[];excluded=Counter();seen=set()
    for row in rows:
        item,reason=leg(row,model=model,source=source)
        if item is None:
            excluded[reason]+=1
            continue
        ident=tuple(item["contract"])
        if ident in seen:
            raise LegDependenceError("duplicate_original_settled_contract")
        seen.add(ident)
        results.append(item)
    return results,dict(excluded)


def same_player(x,y):
    return x["player_id"]==y["player_id"] and x["team"]==y["team"]


def pair_category(x,y):
    if x["sport"]!=y["sport"] or x["date"]!=y["date"] or x["game_id"]!=y["game_id"]:
        raise LegDependenceError("pair_must_share_game")
    # Selecting two different tackle lines on the same player/stat or
    # both sides of the same outcome is not two independent exposures.
    if same_player(x,y) and x["stat"]==y["stat"]:
        return None
    if same_player(x,y):
        return "same_player_different_stats"
    if x["team"]==y["team"]:
        return "same_team_distinct_players"
    return "opposing_teams_distinct_players"


def pair_receipt(x,y):
    category=pair_category(x,y)
    if category is None:return None
    p=x["p"]*y["p"]
    joint=x["hit"]*y["hit"]
    prod=(x["hit"]-x["p"])*(y["hit"]-y["p"])
    return {
        "game_key":(x["sport"],x["date"],x["game_id"]),
        "relationship":category,
        "stat_pair":"/".join(sorted((x["stat"],y["stat"]))),
        "same_stat":x["stat"]==y["stat"],
        "joint_hit":joint,"independence_product":p,
        "joint_excess":joint-p,
        "residual_product":prod,
        "selected_sides":"/".join(sorted((x["side"],y["side"]))),
    }


def per_game_summary(pairs):
    grouped=defaultdict(list)
    for p in pairs:
        grouped[p["game_key"]].append(p)
    result={}
    for key,rows in grouped.items():
        n=len(rows)
        result[key]={
            "n_pairs":n,
            "mean_joint_hit":sum(x["joint_hit"] for x in rows)/n,
            "mean_independence_product":sum(x["independence_product"] for x in rows)/n,
            "mean_joint_excess":sum(x["joint_excess"] for x in rows)/n,
            "mean_residual_product":sum(x["residual_product"] for x in rows)/n,
        }
    return result


def summary(pairs, *, draws=500, seed=BOOTSTRAP_SEED):
    games=per_game_summary(pairs)
    units=sorted(games)
    dates={k[1] for k in units}
    if not games:
        return {"n_pairs":0,"n_games":0,"n_dates":0,
                "status":"no_eligible_same_game_pairs","interval_95":None}
    # Each GAME contributes equally to the estimate, regardless of how
    # many superficially distinct correlated pairs it supplies.
    properties=("mean_joint_hit","mean_independence_product",
                "mean_joint_excess","mean_residual_product")
    mean={p:sum(games[k][p] for k in units)/len(units) for p in properties}
    n_pairs=sum(x["n_pairs"] for x in games.values())
    ok=(len(units)>=MIN_GAMES_FOR_DESCRIPTIVE_CI
        and len(dates)>=MIN_DATES_FOR_DESCRIPTIVE_CI
        and n_pairs>=MIN_PAIRS_FOR_DESCRIPTIVE_CI)
    interval=None
    if ok:
        if draws<100:raise LegDependenceError("insufficient_bootstrap_draws")
        rng=random.Random(seed)
        values=[]
        for _ in range(draws):
            sample=rng.choices(units,k=len(units))
            values.append(sum(games[k]["mean_residual_product"] for k in sample)/len(sample))
        values.sort()
        interval=[values[int(draws*.025)],values[int(draws*.975)-1]]
    return {
        "n_pairs":n_pairs,"n_games":len(units),"n_dates":len(dates),
        "pair_weighting":"equal_game_weight_not_independent_pair_rows",
        **mean,
        "status":("descriptive_game_cluster_interval_not_entry_authorization"
                  if ok else "insufficient_independent_games_or_dates"),
        "interval_95":interval,
    }


def cross_game_same_day_control(legs):
    """Same-slate, different-game pairs are an exploratory negative control.

    This is not a causal test or statistically exchangeable permutation:
    matchups and stat populations differ. Never use it to estimate an entry.
    """
    by_sport_date=defaultdict(list)
    for r in legs:
        by_sport_date[(r["sport"],r["date"])].append(r)
    by_source_game=defaultdict(list)
    for (sport,date),rows in by_sport_date.items():
        teams=defaultdict(list)
        for x in rows:teams[x["game_id"]].append(x)
        if len(teams)<2:continue
        for game,inside in teams.items():
            others=[r for other,group in teams.items() if other!=game for r in group]
            # Same-stat control: avoids mixing an NHL skater shots market with
            # the volume of NBA rebounds or an NFL reception count.
            other_by_stat=defaultdict(list)
            for y in others:other_by_stat[y["stat"]].append(y)
            for x in inside:
                candidates=other_by_stat.get(x["stat"],[])
                if not candidates:continue
                # One fixed lexicographically identified counterpart per leg,
                # avoiding O(n^2) and preventing random post-hoc selection.
                y=sorted(candidates,key=lambda z:(
                    z["game_id"],z["team"],z["player_id"],z["line"],z["side"]))[0]
                by_source_game[(sport,date,game)].append({
                    "game_key":(sport,date,game),
                    "relationship":"cross_game_same_date_stat_control",
                    "joint_hit":x["hit"]*y["hit"],
                    "independence_product":x["p"]*y["p"],
                    "joint_excess":x["hit"]*y["hit"]-x["p"]*y["p"],
                    "residual_product":(x["hit"]-x["p"])*(y["hit"]-y["p"]),
                })
    return [x for group in by_source_game.values() for x in group]


def frechet_entry_bounds(probabilities, *, same_game=True):
    """Valid *marginal-only* bounds; NEVER a fitted joint distribution."""
    if (not isinstance(probabilities,(tuple,list)) or len(probabilities)<2
            or len(probabilities)>20):
        raise LegDependenceError("entry_requires_2_to_20_marginal_probabilities")
    if any(type(p) not in (float,int) or not math.isfinite(p) or not 0<=p<=1
           for p in probabilities):
        raise LegDependenceError("invalid_leg_marginal_probability")
    values=[float(x) for x in probabilities]
    lower=max(0.,sum(values)-(len(values)-1))
    upper=min(values)
    product=math.prod(values)
    return {
        "leg_count":len(values),"same_game":bool(same_game),
        "frechet_lower_bound":lower,"frechet_upper_bound":upper,
        "independence_product_for_comparison_only":product,
        "independence_assumption_verified":False,
        "joint_probability_approved":False,
        "payout_ev_approved":False,
        "method":"sharp_marginal_frechet_bounds_no_correlational_claim",
    }


def dependence_audit(rows, *, model, source, draws=500):
    legs,excluded=validated_legs(rows,model=model,source=source)
    games=defaultdict(list)
    for x in legs:games[(x["sport"],x["date"],x["game_id"])].append(x)
    all_pairs=[];skipped=Counter()
    for group in games.values():
        for x,y in itertools.combinations(group,2):
            pair=pair_receipt(x,y)
            if pair is None:
                skipped["same_player_and_stat_multiple_lines"]+=1
                continue
            all_pairs.append(pair)
    cats={c:[x for x in all_pairs if x["relationship"]==c]
          for c in ("same_player_different_stats",
                    "same_team_distinct_players","opposing_teams_distinct_players")}
    same_stat=[x for x in all_pairs if x["same_stat"]]
    cross=cross_game_same_day_control(legs)
    return {
        "model":model,"source_cohort":source,
        "archive_rows":len(rows),"eligible_one_side_per_contract":len(legs),
        "unavailable_or_invalid_forecasts":excluded,
        "n_distinct_source_games":len(games),
        "n_source_dates":len({g[1] for g in games}),
        "dropped_same_player_stat_pairs":skipped["same_player_and_stat_multiple_lines"],
        "all_same_game_pairs":summary(all_pairs,draws=draws),
        "by_relationship":{key:summary(value,draws=draws)
                           for key,value in cats.items()},
        "same_stat_different_player_pairs":summary(same_stat,draws=draws),
        "cross_game_same_date_stat_negative_control":summary(cross,draws=draws),
        "pairwise_outcome_and_calibration_confounding":True,
        "joint_distribution_fitted":False,
        "multi_leg_probability_authorized":False,
        "entry_independence_product_authorized":False,
        "payout_ev_authorized":False,
        "limitations":[
            "Many pairs from the same game constitute ONE independent game cluster",
            "Mean hit-minus-prediction residual products mix miscalibration and true common outcomes",
            "A same-slate cross-game negative control is not an exchangeable causal estimate",
            "Opposing Over/Under sides can induce negative dependence; do not universalize a single rho",
            "Same player and stat across lines must not be treated as distinct legs",
            "Incomplete source receipts and short game/date histories forbid fitted covariance",
        ],
    }


def audit(*,frozen,settlement,pinned,historical,archive_root,draws=500):
    live,source_live=load_nfl_slate(frozen,settlement,pinned)
    old,source_old=load_historical(historical,archive_root)
    if not isinstance(draws,int) or draws<100 or draws>10000:
        raise LegDependenceError("invalid_bootstrap_sample_count")
    reports={
        "nov8_market":dependence_audit(live,model="Market",source="nov8_current",draws=draws),
        "nov8_consensus":dependence_audit(live,model="Consensus",source="nov8_current",draws=draws),
        "nov8_engine_a":dependence_audit(live,model="Engine_A",source="nov8_current",draws=draws),
        "nov5_7_engine_a_research":dependence_audit(old,model="Engine_A",
                                                    source="nov5_7_retrospective",draws=draws),
        "nov5_7_market_research":dependence_audit(old,model="Market",
                                                   source="nov5_7_retrospective",draws=draws),
    }
    return {
        "schema":SCHEMA,
        "status":"read_only_game_dependence_diagnostics_no_joint_probability",
        "source_hashes_sha256":{
            "nov8_frozen":read_json(frozen)[1],
            "nov8_official_settlement":read_json(settlement)[1],
            "nov8_pinned_receipt":read_json(pinned)[1],
            "nov5_7_retrospective":read_json(historical)[1],
        },
        "source_receipts":{"nov8":source_live,"nov5_7":source_old},
        "current_and_older_policies_pooled":False,
        "results":reports,
        "report_retraining_performed":False,
        "production_changed":False,
        "leg_probability_estimated":False,
        "payout_expected_value_estimated":False,
        "next_requirements":[
            "Capture more independently settled same-game and cross-game bets on many dates",
            "Obtain point-in-time quotes and original provider evidence for every source model",
            "Build predeclared pair classes by game script/stat/role/side",
            "Estimate heldout joint probabilities versus independence and market baseline with game-cluster uncertainty",
            "Only after independent validation, allow a correlation-aware entry optimizer",
        ],
    }


def main(argv=None):
    p=argparse.ArgumentParser()
    for key in ("frozen","settlement","pinned","historical","archive_root"):
        p.add_argument("--"+key.replace("_","-"),type=Path,required=True)
    p.add_argument("--draws",type=int,default=500)
    p.add_argument("--out",type=Path)
    a=p.parse_args(argv)
    result=audit(frozen=a.frozen,settlement=a.settlement,pinned=a.pinned,
                 historical=a.historical,archive_root=a.archive_root,draws=a.draws)
    serialized=json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if a.out:
        if a.out.exists() and a.out.read_text()!=serialized:
            raise LegDependenceError("would_rewrite_different_step9_receipt")
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(serialized)
    print(json.dumps({"status":result["status"],
                      "summary":{k:{"legs":v["eligible_one_side_per_contract"],
                          "games":v["n_distinct_source_games"],
                          "pairs":v["all_same_game_pairs"],
                          "relationships":v["by_relationship"],
                          "negative_control":v["cross_game_same_date_stat_negative_control"]}
                          for k,v in result["results"].items()}},sort_keys=True))


if __name__=="__main__":
    main()
