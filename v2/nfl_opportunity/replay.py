"""P2-06: chronological shadow scorecard and absence/short-role cohorts.

Each case's target outcome is supplied AFTER the entire as-of simulation is
frozen. No retrospective model can turn this into a historical live forecast.
The independent Poisson baseline is allowed to show illegal totals, but NEVER
an eligible production scenario.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math

from v2.contracts import ContractError, finite, utc, canonical_hash
from v2.evaluation import _cluster_interval, _mean, brier, crps_ensemble
from .simulation import simulate_nfl_opportunities, BASELINE, CHALLENGERS

SCHEMA = "v25-nfl-phase2-rolling-scorecard-v1"


def _model_outcomes(mode: str, simulations: list[dict], player_id: str):
    if mode == BASELINE:
        return [x["targets"].get(player_id,0) for x in simulations]
    return [x["players"][player_id]["targets"] for x in simulations]


def _score(samples: list[float], actual: float) -> dict:
    if not samples:
        raise ContractError("missing_phase2_model_scenarios")
    actual=finite(actual,"actual")
    if actual < 0 or not actual.is_integer():
        raise ContractError("phase2_requires_nonnegative_integer_actual")
    return {
        "crps":crps_ensemble(samples,actual),
        "abs_error":abs(math.fsum(samples)/len(samples)-actual),
        "squared_error":(math.fsum(samples)/len(samples)-actual)**2,
    }


def replay_nfl_opportunity_cases(cases: list[dict], *,
                                 seed: int = 20261110,
                                 n_scenarios: int = 256,
                                 high_usage_share: float = .15,
                                 short_role_max_games: int = 4) -> dict:
    if not isinstance(cases,list) or not cases:
        raise ContractError("empty_nfl_phase2_replay_cases")
    if not 0 < finite(high_usage_share,"high_usage_share") < 1:
        raise ContractError("invalid_high_usage_cohort_cut")
    if type(short_role_max_games) is not int or short_role_max_games < 1:
        raise ContractError("invalid_short_role_cohort_cut")
    seen=set()
    per_case=[]
    by_model=defaultdict(list)
    missing=Counter()
    scenario_violation_count=Counter()
    for index,case in enumerate(cases):
        if not isinstance(case,dict) or set(case)!={"input","outcome"}:
            raise ContractError("phase2_replay_case_has_unknown_fields")
        pre=case["input"]
        outcome=case["outcome"]
        if not isinstance(pre,dict) or not isinstance(outcome,dict):
            raise ContractError("invalid_phase2_replay_case")
        forecast=pre.get("forecast") or {}
        key=(forecast.get("event_id"),forecast.get("team_id"))
        if key in seen:
            raise ContractError("duplicate_phase2_replay_event_team")
        seen.add(key)
        event_start=utc(forecast.get("event_start_at"),"event_start_at")
        if (outcome.get("event_id")!=forecast.get("event_id")
                or outcome.get("team_id")!=forecast.get("team_id")):
            raise ContractError("phase2_outcome_event_team_mismatch")
        actual_time=utc(outcome.get("available_at"),"outcome_available_at")
        if actual_time <= event_start:
            raise ContractError("phase2_outcome_not_postgame")
        if not isinstance(outcome.get("player_targets"),dict):
            raise ContractError("phase2_outcome_targets_missing")
        for value in outcome["player_targets"].values():
            x=finite(value,"outcome_targets")
            if x < 0 or not x.is_integer():
                raise ContractError("phase2_invalid_settled_targets")
        actual_attempts=outcome.get("pass_attempts")
        if type(actual_attempts) is not int or actual_attempts<0:
            raise ContractError("phase2_outcome_pass_attempts_invalid")
        if math.fsum(outcome["player_targets"].values()) > actual_attempts:
            raise ContractError("phase2_actual_player_targets_exceed_attempts")
        sample=simulate_nfl_opportunities(
            pre,seed=seed,n_scenarios=n_scenarios,store_scenarios=True)
        forecast_id=sample["metadata"]["event_id"]
        rows_by_model=sample["scenarios"]
        fitted=sample["metadata"]["fitted_receiver_priors"]
        short_roles={x["player_id"] for x in fitted
                     if x["n_player_history"]<=short_role_max_games}
        absent={x["player_id"] for x in fitted if x["status"]=="verified_out"}
        high_usage_absent=any(
            x["player_id"] in absent
            and (x["route_alpha"]/(x["route_alpha"]+x["route_beta"]))
            * (x["target_alpha"]/(x["target_alpha"]+x["target_beta"]))
            >=high_usage_share
            for x in fitted)
        case_cohorts=["all"]
        if short_roles:
            case_cohorts.append("short_role")
        if high_usage_absent:
            case_cohorts.append("high_usage_verified_absence")
        case_entry={
            "event_id":key[0],"team_id":key[1],
            "input_freeze_at":forecast["freeze_at"],
            "original_input_sha256":sample["metadata"]["original_input_sha256"],
            "outcome_first_available_at":outcome["available_at"],
            "outcome_used_for_fitting":False,
            "cohorts":case_cohorts,
            "missing_modes":sample["metadata"]["unavailable_modes"],
            "models":{},
        }
        for mode,values in rows_by_model.items():
            for scenario in values:
                if mode!=BASELINE:
                    if (sum(p["targets"] for p in scenario["players"].values())
                            +scenario["unassigned_pass_attempts"] !=
                            scenario["team"]["pass_attempts"]
                            or any(p["targets"]>p["routes"]
                                   for p in scenario["players"].values())):
                        scenario_violation_count[mode]+=1
            attempts=[s["team"]["pass_attempts"] for s in values]
            team_score=_score(attempts,actual_attempts)
            player_scores=[]
            for player in fitted:
                pid=player["player_id"]
                if pid not in outcome["player_targets"]:
                    missing["no_settled_player_target:"+pid]+=1
                    continue
                if pid in absent and outcome["player_targets"][pid]>0:
                    raise ContractError("verified_absent_player_has_actual_targets")
                targets=_model_outcomes(mode,values,pid)
                result=_score(targets,outcome["player_targets"][pid])
                player_scores.append(result)
                for cohort in case_cohorts:
                    by_model[(mode,cohort,"player")].append({
                        **result,"event_id":key[0],"date":event_start.date().isoformat(),
                        "player_id":pid})
                if pid in short_roles:
                    by_model[(mode,"short_role_players","player")].append({
                        **result,"event_id":key[0],"date":event_start.date().isoformat(),
                        "player_id":pid})
            for cohort in case_cohorts:
                by_model[(mode,cohort,"team_attempts")].append({
                    **team_score,"event_id":key[0],
                    "date":event_start.date().isoformat()})
            illegal=sum(s.get("illegal_target_sum",False) for s in values)
            case_entry["models"][mode]={
                "team_pass_attempt_crps":team_score["crps"],
                "player_targets_crps":_mean(x["crps"] for x in player_scores),
                "n_settled_roster_players":len(player_scores),
                "baseline_illegal_team_sum_scenarios":illegal,
                "scenario_count":n_scenarios,
                "scenario_sha256":sample["models"][mode]["scenario_sha256"],
            }
        per_case.append(case_entry)
    summaries={}
    for (model,cohort,quantity),rows in sorted(by_model.items()):
        summaries.setdefault(model,{})[cohort+"__"+quantity]={
            "n":len(rows),
            "events":len({r["event_id"] for r in rows}),
            "crps":_mean(r["crps"] for r in rows),
            "abs_error":_mean(r["abs_error"] for r in rows),
            "squared_error":_mean(r["squared_error"] for r in rows),
        }
    # Paired comparisons on identical game/team player contracts only.
    reference=by_model
    comparisons={}
    for mode in CHALLENGERS:
        candidates=reference.get((mode,"all","player"),[])
        baseline=reference.get((BASELINE,"all","player"),[])
        indexed={(r["event_id"],r["player_id"]):r for r in candidates}
        base={(r["event_id"],r["player_id"]):r for r in baseline}
        common=sorted(set(indexed)&set(base))
        differences=[(event,indexed[(event,player)]["crps"]-
                       base[(event,player)]["crps"]) for event,player in common]
        dates=[(indexed[(event,player)]["date"],diff) for (
            (event,player),(_event,diff)) in zip(common,differences)]
        comparisons[mode]={
            "vs":BASELINE,
            "matched_player_contracts":len(common),
            "crps_difference_negative_is_better":_mean(d for _,d in differences),
            "event_cluster_interval":_cluster_interval(
                differences,seed,1000),
            "date_cluster_interval":_cluster_interval(dates,seed,1000),
            "comparison_coverage":len(common),
            "prospective_performance_claim_authorized":False,
        }
    return {
        "schema":SCHEMA,
        "cases":len(cases),"run_seed":seed,"n_scenarios":n_scenarios,
        "total_event_team_groups":len(seen),
        "case_ledgers":per_case,"model_cohort_scores":summaries,
        "paired_vs_independent_poisson":comparisons,
        "incomplete_settlement_reasons":dict(sorted(missing.items())),
        "illegal_constrained_scenarios":dict(sorted(scenario_violation_count.items())),
        "experiment_independence":"retrospective_counterfactual_not_prospective",
        "synthetic_line_profit_claim_allowed":False,
        "auto_promotion_authorized":False,
        "research_exit_requirements_met":False,
        "result_sha256":canonical_hash({
            "scores":summaries,"paired":comparisons,
            "inputs":[entry["original_input_sha256"] for entry in per_case],
        }),
    }
