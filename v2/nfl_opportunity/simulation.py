"""P2 NFL: replayable shared-state target allocation and QB volume simulations.

There is ONE common no-market team game-state draw per scenario and all
allocator challengers consume its exact pass-attempt count. Targets for both
sides of a prop are extracted from the same sample distribution. No ranking,
market edge, Tier authorization, live source claim or NUTS fitting occurs.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import asdict
from v2.contracts import ContractError, canonical_hash, finite, utc
from .contracts import prepare_inputs
from .state import fit_team_state, fitted_spread_effect
from .allocation import (fit_allocator, allocate_attempts,
                         independent_poisson_diagnostic,
                         standard_dm_diagnostic)

SCHEMA = "v25-nfl-phase2-opportunity-shadow-v1"
CHALLENGERS = ("logistic_normal", "dirichlet_multinomial", "zidm")
BASELINE = "independent_poisson_diagnostic"
STANDARD_DM = "standard_dirichlet_multinomial_diagnostic"


def _seed_for(seed: int, run_id: str, event_id: str,
              scenario: int, component: str) -> int:
    material = "|".join((str(seed), run_id, event_id, str(scenario), component))
    return int.from_bytes(hashlib.sha256(material.encode()).digest()[:8], "big")


def _summary_samples(samples):
    if not samples:
        return None
    xs=sorted(samples)
    n=len(xs)
    return {
        "mean":math.fsum(xs)/n,
        "median":xs[n//2],
        "p05":xs[int((n-1)*.05)],
        "p95":xs[int((n-1)*.95)],
        "n":n,
    }


def _probabilities(samples, line: float) -> dict:
    if not samples:
        return {"status":"unavailable"}
    line=finite(line, "line")
    n=len(samples)
    over=sum(x>line for x in samples)/n
    under=sum(x<line for x in samples)/n
    push=sum(x==line for x in samples)/n
    if abs((over+under+push)-1) > 1e-12:
        raise ContractError("noncomplementary_scenario_probabilities")
    return {
        "status":"shadow_diagnostic_only",
        "line":line,"q_over":over,"q_under":under,"q_push":push,
        "conditional_over":(over/(over+under) if over+under else None),
        "finite_m_se_over":math.sqrt(over*(1-over)/n),
        "n_scenarios":n,
        "same_scenarios_for_both_sides":True,
    }


def simulate_nfl_opportunities(payload: dict, *, seed: int = 20261110,
                               n_scenarios: int = 512,
                               prior_game_strength: float = 5.,
                               prior_route_exposure: float = 30.,
                               dm_concentration: float = 25.,
                               store_scenarios: bool = True) -> dict:
    if type(seed) is not int or seed < 0:
        raise ContractError("invalid_phase2_seed")
    if type(n_scenarios) is not int or not 64 <= n_scenarios <= 10000:
        raise ContractError("phase2_n_scenarios_outside_research_bounds")
    forecast, team_rows, player_rows, coverage = prepare_inputs(payload)
    posterior = fit_team_state(team_rows, forecast,
                               prior_game_strength=prior_game_strength)
    allocator = fit_allocator(team_rows, player_rows, forecast,
                              prior_route_exposure=prior_route_exposure)
    if (utc(posterior.training_cutoff_at, "team_fit_cutoff") >
        utc(forecast.freeze_at,"freeze")
        or utc(allocator.training_cutoff_at, "player_fit_cutoff") >
        utc(forecast.freeze_at,"freeze")):
        raise ContractError("trained_on_future_nfl_outcome")
    game_market = fitted_spread_effect(payload["forecast"].get("game_market"),
                                       payload["team_history"],forecast.freeze_at,
                                       forecast.team_id)
    modes = list(CHALLENGERS)
    zidm_missing = [p.player_id for p in allocator.players
                    if p.structural_zero_probability is None
                    and p.status != "verified_out"]
    mode_abstentions = {}
    if zidm_missing:
        modes.remove("zidm")
        mode_abstentions["zidm"] = {
            "reason":"insufficient_verified_structural_inactivity_labels",
            "players_without_identified_zero_process":zidm_missing,
        }
    if game_market["shift"] is not None:
        modes.append("logistic_normal_market_state")
    else:
        mode_abstentions["logistic_normal_market_state"]={
            "reason":game_market["status"],
            "market_quote_not_assumed":True,
        }
    if allocator.unidentifiable_role_transitions:
        mode_abstentions["absence_role_uplift"]={
            "reason":"insufficient_asof_verified_role_transition_pairs",
            "unidentifiable_roles":list(allocator.unidentifiable_role_transitions),
            "fallback":"no_unverified_uplift_applied",
        }
    scenarios={name:[] for name in modes}
    scenarios[BASELINE]=[]
    scenarios[STANDARD_DM]=[]
    legal_failures={}
    sample_seed_sha=[]
    for n in range(n_scenarios):
        state_seed=_seed_for(seed,forecast.run_id,forecast.event_id,n,"state_no_market")
        state=posterior.draw(random.Random(state_seed))
        sample_seed_sha.append(hashlib.sha256(str(state_seed).encode()).hexdigest())
        for mode in modes:
            if mode == "logistic_normal_market_state":
                conditional_seed=_seed_for(seed,forecast.run_id,forecast.event_id,
                                           n,"market_state")
                effective_state=posterior.draw(
                    random.Random(conditional_seed),
                    market_pass_logit_shift=game_market["shift"])
                algorithm="logistic_normal"
            else:
                effective_state=state
                algorithm=mode
            rng=random.Random(_seed_for(
                seed,forecast.run_id,forecast.event_id,n,"allocation_"+mode))
            result=allocate_attempts(effective_state,allocator,rng,
                                     method=algorithm,
                                     dm_concentration=dm_concentration)
            if not result["conservation_ok"]:
                legal_failures[mode]=legal_failures.get(mode,0)+1
                raise ContractError("phase2_illegal_allocation")
            scenarios[mode].append({
                "team":effective_state,
                "players":result["players"],
                "unassigned_pass_attempts":result["residual_unassigned_attempts"],
                "tracked_player_targets":result["tracked_player_targets"],
                "model":mode,
            })
        independent=independent_poisson_diagnostic(
            state,allocator,random.Random(_seed_for(
                seed,forecast.run_id,forecast.event_id,n,"independent_poisson")))
        scenarios[BASELINE].append({
            "team":state,
            "targets":independent["targets"],
            "illegal_target_sum":independent["illegal_target_sum"],
            "not_jointly_physically_valid":True,
        })
        standard=standard_dm_diagnostic(
            state,allocator,random.Random(_seed_for(
                seed,forecast.run_id,forecast.event_id,n,"standard_dm")),
            concentration=dm_concentration)
        scenarios[STANDARD_DM].append({
            "team":state,
            "players":standard["players"],
            "unassigned_pass_attempts":standard["unassigned_pass_attempts"],
            "tracked_player_targets":standard["tracked_player_targets"],
            "illegal_route_capacity_players":standard["illegal_route_capacity_players"],
            "not_jointly_physically_valid":standard["not_jointly_physically_valid"],
        })
    lines = payload["forecast"].get("diagnostic_lines", [])
    if not isinstance(lines,list):
        raise ContractError("invalid_synthetic_diagnostic_lines")
    for contract in lines:
        if (not isinstance(contract,dict)
                or set(contract) != {"player_id","stat_key","line"}):
            raise ContractError("invalid_diagnostic_line_contract")
        if contract["stat_key"] not in ("targets","pass attempts"):
            raise ContractError("phase2_only_targets_and_qb_attempts")
        if contract["stat_key"]=="pass attempts":
            if contract["player_id"]!=forecast.qb_player_id:
                raise ContractError("qb_pass_attempts_identity_mismatch")
        elif contract["player_id"] not in {p.player_id for p in forecast.players}:
            raise ContractError("diagnostic_target_player_not_in_frozen_roster")
        finite(contract["line"], "diagnostic_line")

    summaries = {}
    for mode, rows in scenarios.items():
        counts={
            player.player_id:[
                (r["targets"].get(player.player_id,0) if mode==BASELINE
                 else r["players"][player.player_id]["targets"])
                for r in rows]
            for player in forecast.players
        }
        attempts=[r["team"]["pass_attempts"] for r in rows]
        dropbacks=[r["team"]["dropbacks"] for r in rows]
        possessions=[r["team"]["possessions"] for r in rows]
        unassigned=([
            r["unassigned_pass_attempts"] for r in rows] if mode!=BASELINE else None)
        raw_lines=[]
        for contract in lines:
            samples=(attempts if contract["stat_key"]=="pass attempts"
                     else counts[contract["player_id"]])
            raw_lines.append({**contract,"original_market_quote":False,
                              **_probabilities(samples,contract["line"])})
        illegal=(sum(r["illegal_target_sum"] for r in rows) if mode==BASELINE
                 else sum(bool(r["illegal_route_capacity_players"]) for r in rows)
                 if mode==STANDARD_DM else 0)
        summaries[mode]={
            "scenario_count":n_scenarios,
            "team_pass_attempts":_summary_samples(attempts),
            "team_dropbacks":_summary_samples(dropbacks),
            "team_possessions":_summary_samples(possessions),
            "qb_pass_attempts":_summary_samples(attempts),
            "player_targets":{name:_summary_samples(samples)
                              for name,samples in sorted(counts.items())},
            "residual_unassigned_attempts":_summary_samples(unassigned)
                  if unassigned is not None else None,
            "synthetic_line_probabilities":raw_lines,
            "illegal_allocations":illegal,
            "illegal_allocation_frequency":illegal/n_scenarios,
            "physically_constrained":mode not in (BASELINE,STANDARD_DM),
            "diagnostic_violations_may_be_present":mode in (BASELINE,STANDARD_DM),
            "counterfactual_not_original_pregame_model":True,
            "scenario_sha256":canonical_hash({"samples":rows}),
        }
    metadata={
        "schema":SCHEMA,"run_id":forecast.run_id,"event_id":forecast.event_id,
        "team_id":forecast.team_id,"opponent_id":forecast.opponent_id,
        "qb_player_id":forecast.qb_player_id,
        "freeze_at":forecast.freeze_at,"event_start_at":forecast.event_start_at,
        "original_input_sha256":forecast.original_input_sha256,
        "seed":seed,"n_scenarios":n_scenarios,
        "state_training_cutoff_at":posterior.training_cutoff_at,
        "allocation_training_cutoff_at":allocator.training_cutoff_at,
        "training_source_coverage":coverage,
        "n_asof_team_games":posterior.n_team_games,
        "n_asof_league_games":posterior.n_league_games,
        "n_asof_player_games":allocator.n_player_rows,
        "fitted_team_posterior":asdict(posterior),
        "fitted_receiver_priors":[asdict(p) for p in allocator.players],
        "registered_hyperparameters":{
            "prior_game_strength":prior_game_strength,
            "prior_route_exposure":prior_route_exposure,
            "dm_concentration":dm_concentration,
            "sampling_parameter_status":"research_hyperparameters_not_calibrated",
        },
        "shared_no_market_state_seed_material_sha256":canonical_hash(
            {"seed_shas":sample_seed_sha}),
        "game_market_effect":game_market,
        "unavailable_modes":mode_abstentions,
        "absence_redistribution":"remove verified_out player, recompute simplex; role uplift only if asof transitions identifiable",
        "phase2_predictive_acceptance":False,
        "production_promotion_authorized":False,
        "tier_1_2_authorized":False,
        "heavy_nuts_training_started":False,
    }
    out={"metadata":metadata,"models":summaries}
    if store_scenarios:
        out["scenarios"]=scenarios
    out["receipt_sha256"]=canonical_hash(out)
    return out
