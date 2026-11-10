"""Phase 2 NFL research: conservation, no-market, availability, as-of and replay tests.

All fixtures are explicitly SYNTHETIC and never count as prospective
performance, original sportsbook quotes or a finished Phase 2 exit.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from v2.contracts import ContractError, canonical_hash
from v2.nfl_opportunity import (simulate_nfl_opportunities,
                                replay_nfl_opportunity_cases)
from v2.nfl_opportunity.contracts import prepare_inputs
from v2.nfl_opportunity.state import fit_team_state, fitted_spread_effect
from v2.nfl_opportunity.allocation import (fit_allocator,
                                             independent_poisson_diagnostic)
import random

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/"examples/v25_phase2_nfl_synthetic_case.json"


def input_fixture():
    return json.loads(FIXTURE.read_text())


def game_result(event_id, date):
    return {
        "event_id":event_id,"team_id":"TEAM_A",
        "available_at":date+"T23:30:00Z",
        "pass_attempts":34,
        "player_targets":{
            "WR1_A":0,"WR2_A":7,"TE_A":5,
            "RB_A":3,"ROOKIE_WR2":2,
        },
    }


def chronological_cases(n=8):
    original=input_fixture()
    dates=["2024-12-%02d"%d for d in range(12,12+n)]
    cases=[]
    for i,d in enumerate(dates):
        data=deepcopy(original)
        event="synthetic-future-game-"+str(i)
        if i==0:
            event=original["forecast"]["event_id"]
        data["forecast"]["event_id"]=event
        data["forecast"]["run_id"]="synthetic-phase2-rolling-"+str(i)
        data["forecast"]["event_start_at"]=d+"T18:00:00Z"
        data["forecast"]["freeze_at"]=d+"T15:00:00Z"
        for player in data["forecast"]["players"]:
            player["status_published_at"]=d+"T12:30:00Z"
            player["status_retrieved_at"]=d+"T13:15:00Z"
        cases.append({"input":data,"outcome":game_result(event,d)})
    return cases


class Phase2NflSourceContracts(unittest.TestCase):
    def test_pregame_freeze_original_roster_and_history_cutoffs(self):
        req=input_fixture()
        frozen,team,player,coverage=prepare_inputs(req)
        self.assertEqual(frozen.team_id,"TEAM_A")
        self.assertEqual(len(frozen.players),5)
        self.assertEqual(coverage["eligible_team_history_rows"],24)
        self.assertEqual(coverage["eligible_player_history_rows"],48)
        self.assertIn("current_game_team_history_embargo",
                      coverage["rejected_history_reasons"])
        self.assertIn("current_game_player_history_embargo",
                      coverage["rejected_history_reasons"])
        self.assertEqual(frozen.original_input_sha256,canonical_hash(req))

    def test_lookahead_feature_and_postgame_roster_rejected(self):
        payload=input_fixture()
        payload["forecast"]["final_pass_attempts"]=50
        with self.assertRaisesRegex(ContractError,"forbidden_postgame_feature"):
            prepare_inputs(payload)
        payload=input_fixture()
        payload["forecast"]["players"][0]["status_retrieved_at"]="2024-12-12T15:01:00Z"
        with self.assertRaisesRegex(ContractError,"roster_data_after_freeze"):
            prepare_inputs(payload)
        payload=input_fixture()
        payload["forecast"]["freeze_at"]="2024-12-12T18:00:00Z"
        with self.assertRaisesRegex(ContractError,"post_kickoff"):
            prepare_inputs(payload)

    def test_charted_team_target_total_must_reconcile(self):
        payload=input_fixture()
        first=next(x for x in payload["team_history"]
                   if x["event_id"]=="synthetic-teamA-game-0")
        first["tracked_targets"]=2
        with self.assertRaisesRegex(ContractError,"target_sum_exceeds_charted_targets"):
            prepare_inputs(payload)

    def test_historical_spread_quote_after_kickoff_is_rejected(self):
        payload=input_fixture()
        row=payload["team_history"][0]
        row.update(pregame_spread=-4.,
                   pregame_spread_at="2024-09-05T19:00:00Z",
                   pregame_spread_source_sha256="a"*64,
                   pregame_spread_source_uri="https://example.org/fiction")
        with self.assertRaisesRegex(ContractError,"historical_game_spread_not_pregame"):
            prepare_inputs(payload)

    def test_missing_role_source_and_duplicate_player_rejected(self):
        payload=input_fixture()
        payload["forecast"]["players"][1]["player_id"]="WR1_A"
        with self.assertRaisesRegex(ContractError,"duplicate_nfl_player"):
            prepare_inputs(payload)
        payload=input_fixture()
        payload["player_history"][0]["targets"]=999
        with self.assertRaisesRegex(ContractError,"targets_exceed_routes"):
            prepare_inputs(payload)

    def test_current_game_future_labels_do_not_change_actual_scenarios(self):
        data=input_fixture()
        reference=simulate_nfl_opportunities(data,seed=9,n_scenarios=64,
                                               store_scenarios=False)
        mutation=deepcopy(data)
        for row in mutation["team_history"]:
            if row["event_id"]==data["forecast"]["event_id"]:
                row["pass_attempts"]=48
                row["tracked_targets"]=18
                row["dropbacks"]=50
                row["offensive_plays"]=70
        for row in mutation["player_history"]:
            if row["event_id"]==data["forecast"]["event_id"] and row["player_id"]=="RB_A":
                row["targets"]=5
        challenger=simulate_nfl_opportunities(mutation,seed=9,n_scenarios=64,
                                               store_scenarios=False)
        self.assertNotEqual(reference["metadata"]["original_input_sha256"],
                            challenger["metadata"]["original_input_sha256"])
        for key in reference["models"]:
            self.assertEqual(reference["models"][key]["scenario_sha256"],
                             challenger["models"][key]["scenario_sha256"])

    def test_identical_and_duplicate_game_ids_rejected(self):
        payload=input_fixture()
        payload["forecast"]["opponent_id"]="TEAM_A"
        with self.assertRaisesRegex(ContractError,"invalid_team_vs_self"):
            prepare_inputs(payload)
        payload=input_fixture()
        payload["team_history"].append(payload["team_history"][0])
        with self.assertRaisesRegex(ContractError,"duplicate_historical_team_row"):
            prepare_inputs(payload)

    def test_market_state_is_optional_and_original_spread_must_be_pregame(self):
        payload=input_fixture()
        result=simulate_nfl_opportunities(payload,n_scenarios=64)
        self.assertEqual(result["metadata"]["game_market_effect"]["status"],
                         "no_game_market_requested")
        payload["forecast"]["game_market"]={
            "team_spread":-3.5,"quote_at":"2024-12-12T14:00:00Z",
            "source_sha256":"a"*64,
            "source_uri":"https://example.org/synthetic-only"}
        result=simulate_nfl_opportunities(payload,n_scenarios=64)
        self.assertIn("logistic_normal_market_state",
                      result["metadata"]["unavailable_modes"])
        payload["forecast"]["game_market"]["quote_at"]="2024-12-12T16:00:00Z"
        with self.assertRaisesRegex(ContractError,"game_market_quote_after_freeze"):
            simulate_nfl_opportunities(payload,n_scenarios=64)


class Phase2NflScenarioTests(unittest.TestCase):
    def test_conservation_caps_routes_residual_and_verified_out(self):
        p=input_fixture()
        report=simulate_nfl_opportunities(p,n_scenarios=128,seed=122)
        models=report["scenarios"]
        for name in ("logistic_normal","dirichlet_multinomial","zidm"):
            self.assertIn(name,models)
            for scenario in models[name]:
                team=scenario["team"]
                players=scenario["players"]
                self.assertEqual(team["qb_pass_attempts"],team["pass_attempts"])
                self.assertLessEqual(team["pass_attempts"],team["dropbacks"])
                self.assertLessEqual(team["dropbacks"],team["offensive_plays"])
                self.assertEqual(
                    team["pass_attempts"],
                    sum(x["targets"] for x in players.values())+
                    scenario["unassigned_pass_attempts"])
                self.assertEqual(players["WR1_A"]["targets"],0)
                self.assertEqual(players["WR1_A"]["routes"],0)
                for player in players.values():
                    self.assertLessEqual(player["targets"],player["routes"])
                    self.assertLessEqual(player["routes"],team["dropbacks"])
            self.assertEqual(report["models"][name]["illegal_allocations"],0)

    def test_shared_game_state_and_qb_attempts_in_the_eligible_universe(self):
        report=simulate_nfl_opportunities(input_fixture(),n_scenarios=64,seed=20)
        scenarios=report["scenarios"]
        for idx in range(64):
            a=scenarios["logistic_normal"][idx]["team"]
            for mode in ("dirichlet_multinomial","zidm",
                         "standard_dirichlet_multinomial_diagnostic"):
                self.assertEqual(a,scenarios[mode][idx]["team"])
            self.assertEqual(a,scenarios["independent_poisson_diagnostic"][idx]["team"])
        self.assertIn("qb_pass_attempts",report["models"]["logistic_normal"])
        self.assertTrue(any(
            x["stat_key"]=="pass attempts" and x["player_id"]=="QB_A"
            for x in report["models"]["logistic_normal"]["synthetic_line_probabilities"]))

    def test_single_joint_distribution_for_all_sides_and_seed_determinism(self):
        p=input_fixture()
        one=simulate_nfl_opportunities(p,n_scenarios=64,seed=438,
                                        store_scenarios=False)
        two=simulate_nfl_opportunities(p,n_scenarios=64,seed=438,
                                        store_scenarios=False)
        other=simulate_nfl_opportunities(p,n_scenarios=64,seed=439,
                                        store_scenarios=False)
        self.assertEqual(one["receipt_sha256"],two["receipt_sha256"])
        self.assertNotEqual(one["receipt_sha256"],other["receipt_sha256"])
        for model in one["models"].values():
            for line in model["synthetic_line_probabilities"]:
                self.assertAlmostEqual(
                    line["q_over"]+line["q_under"]+line["q_push"],1,places=12)
                self.assertTrue(line["same_scenarios_for_both_sides"])
                self.assertGreaterEqual(line["finite_m_se_over"],0)
                self.assertFalse(line["original_market_quote"])

    def test_standard_dirichlet_multinomial_is_not_the_capped_version(self):
        report=simulate_nfl_opportunities(input_fixture(),n_scenarios=64,seed=488)
        standard=report["models"]["standard_dirichlet_multinomial_diagnostic"]
        capped=report["models"]["dirichlet_multinomial"]
        self.assertFalse(standard["physically_constrained"])
        self.assertTrue(standard["diagnostic_violations_may_be_present"])
        self.assertTrue(capped["physically_constrained"])
        for i,scenario in enumerate(report["scenarios"][
                "standard_dirichlet_multinomial_diagnostic"]):
            self.assertEqual(scenario["team"],
                             report["scenarios"]["logistic_normal"][i]["team"])
            self.assertEqual(
                sum(p["targets"] for p in scenario["players"].values())+
                scenario["unassigned_pass_attempts"],
                scenario["team"]["pass_attempts"])
        self.assertNotEqual(standard["scenario_sha256"],capped["scenario_sha256"])

    def test_market_optional_challenger_only_when_original_pregame_training_exists(self):
        payload=input_fixture()
        for j,row in enumerate(payload["team_history"]):
            if row["event_id"]==payload["forecast"]["event_id"]:
                continue
            day=row["event_start_at"][:10]
            row["pregame_spread"]=-4.+(j%5)
            row["pregame_spread_at"]=day+"T14:00:00Z"
            row["pregame_spread_source_sha256"]="b"*64
            row["pregame_spread_source_uri"]="https://example.org/synthetic-spread"
        payload["forecast"]["game_market"]={
            "team_spread":-6.,"quote_at":"2024-12-12T14:00:00Z",
            "source_sha256":"a"*64,
            "source_uri":"https://example.org/synthetic-market"}
        forecast=simulate_nfl_opportunities(payload,n_scenarios=64)
        self.assertIn("logistic_normal_market_state",forecast["models"])
        self.assertEqual(
            forecast["metadata"]["game_market_effect"]["status"],
            "fitted_spread_state_challenger")
        self.assertFalse(forecast["metadata"]["phase2_predictive_acceptance"])

    def test_unidentifiable_structural_zero_abstains(self):
        data=input_fixture()
        for row in data["player_history"]:
            row["structurally_inactive"]=None
        out=simulate_nfl_opportunities(data,n_scenarios=64)
        self.assertNotIn("zidm",out["models"])
        self.assertEqual(out["metadata"]["unavailable_modes"]["zidm"]["reason"],
                         "insufficient_verified_structural_inactivity_labels")
        self.assertEqual(out["models"]["logistic_normal"]["illegal_allocations"],0)

    def test_absence_capacity_and_rookie_role_uncertainty(self):
        out=input_fixture()
        original=simulate_nfl_opportunities(out,n_scenarios=64,seed=23)
        self.assertIn("ROOKIE_WR2",original["models"]["logistic_normal"]["player_targets"])
        fitted={r["player_id"]:r for r in original["metadata"]["fitted_receiver_priors"]}
        self.assertEqual(fitted["ROOKIE_WR2"]["n_player_history"],0)
        self.assertGreater(fitted["ROOKIE_WR2"]["participation_beta"],0)
        self.assertEqual(original["models"]["logistic_normal"]["player_targets"]["WR1_A"]["mean"],0)
        present=deepcopy(out)
        present["forecast"]["players"][0]["status"]="available"
        allowed=simulate_nfl_opportunities(present,n_scenarios=64,seed=23)
        self.assertGreater(allowed["models"]["logistic_normal"]["player_targets"]["WR1_A"]["mean"],0)

    def test_unregistered_line_and_invalid_simulation_count_rejected(self):
        p=input_fixture()
        p["forecast"]["diagnostic_lines"].append({
            "player_id":"QB_A","stat_key":"passing touchdowns","line":1.5})
        with self.assertRaisesRegex(ContractError,"phase2_only_targets"):
            simulate_nfl_opportunities(p,n_scenarios=64)
        with self.assertRaisesRegex(ContractError,"n_scenarios_outside"):
            simulate_nfl_opportunities(input_fixture(),n_scenarios=4)

    def test_poisson_zero_lambda_produces_zero_not_negative(self):
        req=input_fixture()
        frozen,team,players,_=prepare_inputs(req)
        fit=fit_allocator(team,players,frozen)
        samples=independent_poisson_diagnostic({"pass_attempts":0},fit,
                                               random.Random(114))
        self.assertEqual(samples["total_player_targets"],0)
        self.assertFalse(samples["illegal_target_sum"])

    def test_league_state_pooled_for_short_history(self):
        req=input_fixture()
        frozen,team,players,_=prepare_inputs(req)
        fit=fit_team_state(team,frozen)
        self.assertEqual(fit.n_league_games,24)
        self.assertEqual(fit.n_team_games,12)
        self.assertTrue(0 < fit.mean_possessions < fit.mean_plays)
        self.assertLessEqual(fit.training_cutoff_at,frozen.freeze_at)

    def test_retrospective_state_is_never_production_model(self):
        out=simulate_nfl_opportunities(input_fixture(),n_scenarios=64)
        meta=out["metadata"]
        self.assertFalse(meta["phase2_predictive_acceptance"])
        self.assertFalse(meta["production_promotion_authorized"])
        self.assertFalse(meta["tier_1_2_authorized"])
        self.assertFalse(meta["heavy_nuts_training_started"])
        self.assertTrue(all(x["counterfactual_not_original_pregame_model"]
                            for x in out["models"].values()))


class Phase2NflReplayTests(unittest.TestCase):
    def test_eight_event_walkforward_and_absence_cohort_scorecards(self):
        report=replay_nfl_opportunity_cases(chronological_cases(8),
                                            n_scenarios=64,seed=919)
        self.assertEqual(report["cases"],8)
        self.assertEqual(report["total_event_team_groups"],8)
        self.assertFalse(report["auto_promotion_authorized"])
        self.assertFalse(report["research_exit_requirements_met"])
        self.assertIn("logistic_normal",report["model_cohort_scores"])
        self.assertEqual(report["paired_vs_independent_poisson"]
                         ["logistic_normal"]["matched_player_contracts"],40)
        self.assertEqual(report["paired_vs_independent_poisson"]
                         ["logistic_normal"]["event_cluster_interval"]["status"],
                         "descriptive_only")
        self.assertEqual(report["illegal_constrained_scenarios"],{})
        self.assertIn("short_role__player",
                      report["model_cohort_scores"]["logistic_normal"])
        self.assertIn("high_usage_verified_absence__player",
                      report["model_cohort_scores"]["logistic_normal"])

    def test_exact_replay_is_seed_deterministic_and_temporally_strict(self):
        cases=chronological_cases(2)
        first=replay_nfl_opportunity_cases(cases,n_scenarios=64,seed=1234)
        second=replay_nfl_opportunity_cases(cases,n_scenarios=64,seed=1234)
        self.assertEqual(first["result_sha256"],second["result_sha256"])
        leak=deepcopy(cases)
        leak[0]["outcome"]["available_at"]="2024-12-12T17:00:00Z"
        with self.assertRaisesRegex(ContractError,"outcome_not_postgame"):
            replay_nfl_opportunity_cases(leak,n_scenarios=64)
        duplicate=cases+[cases[0]]
        with self.assertRaisesRegex(ContractError,"duplicate_phase2_replay"):
            replay_nfl_opportunity_cases(duplicate,n_scenarios=64)

    def test_inconsistent_settlement_abstains_before_scoring(self):
        cases=chronological_cases(1)
        cases[0]["outcome"]["player_targets"]["WR1_A"]=1
        with self.assertRaisesRegex(ContractError,"verified_absent_player_has_actual_targets"):
            replay_nfl_opportunity_cases(cases,n_scenarios=64)
        cases=chronological_cases(1)
        cases[0]["outcome"]["pass_attempts"]=1
        with self.assertRaisesRegex(ContractError,"actual_player_targets_exceed_attempts"):
            replay_nfl_opportunity_cases(cases,n_scenarios=64)


if __name__=="__main__":
    unittest.main()
