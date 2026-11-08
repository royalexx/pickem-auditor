"""Adversarial Phase 1 tests: no time leakage, false zeros, or retroactive picks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import directional_phase1_validation as audit


def fixture(*, line=4.5, actual=7.0, n_games=1):
    run = "c0d0ffee-0000-4000-8000-000000000001"
    forecast = "2026-11-08T12:00:00+00:00"
    kickoff = "2026-11-08T18:00:00Z"
    picks, contracts, games = [], [], []
    for i in range(n_games):
        team, opp = "AAA" + str(i), "BBB" + str(i)
        player = "Player " + str(i)
        player_id = "00-0000" + str(i).zfill(3)
        games.append({"teams": [team, opp], "espn_event_id": str(i + 4000000),
                      "source": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event="
                                + str(i + 4000000)})
        for side in ("over", "under"):
            over = side == "over"
            base = {"Engine_A": .70, "Engine_B": .65, "Bayesian_A": .60,
                    "Bayesian_B": .55, "Consensus": .62, "Market": .51}
            models = {}
            for name, p in base.items():
                value = p if over else 1 - p
                details = {"status": "forecast", "probability": value}
                if name in ("Bayesian_A", "Bayesian_B"):
                    details["generated_at"] = "2026-11-08T12:05:00+00:00"
                    details["trained_through"] = "2026-10-29"
                if name == "Market":
                    details["observed_at"] = "2026-11-08T11:45:00+00:00"
                if name == "Consensus":
                    details["empirically_calibrated"] = False
                models[name] = details
            models["NUTS"] = {"status": "unavailable", "probability": None,
                              "reason": "no_strict_model"}
            rec = {
                "run_id": run, "sport": "NFL", "game_date": "2026-11-08",
                "team": team, "opponent": opp, "player": player,
                "player_id": player_id, "stat": "tackles + assists",
                "line": line, "side": side, "forecast_at": forecast,
                "event_start": kickoff, "models": models,
                "production_consensus_available": True,
                "production_policy_version": "production-historical-ensemble-60-40-20261108-v1",
                "production_ensemble": {
                    "status": "forecast",
                    "historical_families": ["Engine_A", "Bayesian_A", "Bayesian_B"],
                    "weight_historical": .60, "weight_b": .40
                },
            }
            for name in audit.MODELS:
                rec[name] = models[name]["probability"]
            picks.append(rec)
        winner = "push" if actual == line else "over" if actual > line else "under"
        contracts.append({
            "team": team, "opponent": opp, "player": player,
            "player_id_gsis": player_id, "stat": "tackles + assists",
            "line": line, "actual": actual, "winning_side": winner,
            "settlement_status": "verified", "espn_game_id": str(i + 4000000),
            "pregame_forecast_at": forecast
        })
    comparison = {"schema": "slate-model-comparison-v1",
                  "metadata": {"run_id": run, "code_sha": "frozen-fixture"},
                  "picks": picks}
    settlement = {
        "pregame_run": run, "code_sha": "frozen-fixture",
        "start_window_utc": kickoff, "sport": "NFL",
        "games": games, "contracts": contracts
    }
    return comparison, settlement


class DirectionalPhase1Tests(unittest.TestCase):
    def check_block(self, comparison, settlement=None, reason=None, features=None):
        with self.assertRaises(audit.AuditError) as raised:
            audit.run(comparison, settlement=settlement, features=features)
        if reason:
            self.assertIn(reason, str(raised.exception))

    def test_scoring_one_contract_not_both_sides(self):
        c, s = fixture()
        d = audit.run(c, settlement=s)
        self.assertEqual(d["scope"]["side_rows"], 2)
        self.assertEqual(d["scope"]["contracts"], 1)
        self.assertEqual(d["scorecard"]["same_cohort_consensus_contracts"], 1)
        self.assertEqual(d["scorecard"]["models"]["Consensus"]
                         ["on_settled_consensus_cohort"]["hits"], 1)
        self.assertEqual(d["scorecard"]["models"]["NUTS"]["own_coverage"]["n"], 0)
        self.assertFalse(d["ranking_allowed"])
        self.assertFalse(d["production_promotion_allowed"])
        self.assertFalse(d["changes_training_or_policy"])

    def test_different_original_line_is_distinct_contract(self):
        c, s = fixture()
        copy_c, _ = fixture(line=5.5)
        c["picks"].extend(copy_c["picks"])
        r = audit.run(c)
        self.assertEqual(r["scope"]["contracts"], 2)
        self.assertEqual(r["scope"]["side_rows"], 4)

    def test_no_hindsight_prediction_after_kickoff(self):
        c, _ = fixture()
        c["picks"][0]["forecast_at"] = "2026-11-08T19:00:00Z"
        self.check_block(c, reason="forecast_after_event_started")

    def test_naive_timestamp_rejected(self):
        c, _ = fixture()
        c["picks"][0]["forecast_at"] = "2026-11-08T12:00:00"
        self.check_block(c, reason="naive_timestamp")

    def test_duplicate_side_rejected(self):
        c, _ = fixture()
        c["picks"].append(copy.deepcopy(c["picks"][0]))
        self.check_block(c, reason="duplicate_paired_side")

    def test_missing_complementary_side_rejected(self):
        c, _ = fixture()
        c["picks"].pop()
        self.check_block(c, reason="missing_over_or_under_side")

    def test_one_sided_availability_rejected(self):
        c, _ = fixture()
        c["picks"][0]["NUTS"] = .5
        c["picks"][0]["models"]["NUTS"] = {
            "status": "forecast", "probability": .5,
            "generated_at": "2026-11-08T12:05:00Z"
        }
        self.check_block(c, reason="one_sided_model_availability")

    def test_post_event_model_generation_rejected(self):
        c, _ = fixture()
        c["picks"][0]["models"]["Bayesian_A"]["generated_at"] = \
            "2026-11-08T18:01:00Z"
        self.check_block(c, reason="model_generated_outside_pregame")

    def test_missing_model_generation_receipt_rejected(self):
        c, _ = fixture()
        c["picks"][0]["models"]["Bayesian_B"].pop("generated_at")
        self.check_block(c, reason="missing_timestamp:Bayesian_B.generated_at")

    def test_post_forecast_market_evidence_rejected(self):
        c, _ = fixture()
        c["picks"][0]["models"]["Market"]["observed_at"] = \
            "2026-11-08T12:01:00Z"
        self.check_block(c, reason="post_forecast_market_price")

    def test_future_feature_source_rejected(self):
        c, _ = fixture()
        f = self.feature(c)
        f["retrieved_at"] = "2026-11-08T12:03:00Z"
        self.check_block(c, reason="feature_retrieved_after_forecast", features=[f])

    def test_missing_feature_source_rejected(self):
        c, _ = fixture()
        f = self.feature(c)
        f.pop("source_url")
        self.check_block(c, reason="feature_missing_source_url", features=[f])

    def test_unverified_feature_source_rejected(self):
        c, _ = fixture()
        f = self.feature(c)
        f["status"] = "hypothesis"
        self.check_block(c, reason="feature_not_verified", features=[f])

    def test_verified_feature_receipt_accepted(self):
        c, _ = fixture()
        result = audit.run(c, features=[self.feature(c)])
        self.assertEqual(result["feature_verification"]["total_source_verified"], 1)

    def feature(self, c):
        row = c["picks"][0]
        return {k: row[k] for k in (
            "run_id", "sport", "event_start", "team", "opponent",
            "player_id", "player", "stat", "line"
        )} | {
            "source_url": "https://example.org/official-report",
            "source_id": "example-123", "status": "verified",
            "published_at": "2026-11-08T11:40:00Z",
            "retrieved_at": "2026-11-08T11:55:00Z",
            "feature_family": "official_active_list"
        }

    def test_unverified_inactive_remains_unscored(self):
        c, s = fixture()
        s["contracts"][0].update(
            settlement_status="unverified", actual=None,
            winning_side=None, verification="player_missing_from_boxscore")
        r = audit.run(c, settlement=s)
        self.assertEqual(r["scorecard"]["models"]["Consensus"]["own_coverage"]["n"], 0)
        self.assertEqual(r["settlement"]["excluded"]["unverified"], 1)

    def test_official_push_excluded_from_binary_scoring(self):
        c, s = fixture(line=4, actual=4)
        r = audit.run(c, settlement=s)
        self.assertEqual(r["scorecard"]["models"]["Consensus"]["own_coverage"]["n"], 0)
        self.assertEqual(r["settlement"]["excluded"]["push"], 1)

    def test_unverified_result_not_imputed_zero(self):
        c, s = fixture()
        s["contracts"][0].update(settlement_status="unverified",
                                 actual=None, winning_side=None)
        r = audit.run(c, settlement=s)
        self.assertEqual(r["settlement"]["verified_contracts"], 0)

    def test_fake_winning_side_rejected(self):
        c, s = fixture(actual=7)
        s["contracts"][0]["winning_side"] = "under"
        self.check_block(c, s, reason="actual_disagrees_with_winning_side")

    def test_settlement_wrong_original_line_rejected(self):
        c, s = fixture()
        s["contracts"][0]["line"] = 5.5
        self.check_block(c, s, reason="settlement_not_on_original_frozen_line")

    def test_settlement_wrong_official_fixture_rejected(self):
        c, s = fixture()
        s["contracts"][0]["espn_game_id"] = "999999"
        self.check_block(c, s, reason="settlement_wrong_official_game")

    def test_settlement_regenerated_forecast_rejected(self):
        c, s = fixture()
        s["contracts"][0]["pregame_forecast_at"] = "2026-11-09T09:00:00Z"
        self.check_block(c, s, reason="settlement_forecast_timestamp_mismatch")

    def test_duplicated_settlement_rejected(self):
        c, s = fixture()
        s["contracts"].append(copy.deepcopy(s["contracts"][0]))
        self.check_block(c, s, reason="duplicate_settlement_contract")

    def test_missing_settlement_not_inferred_zero(self):
        c, s = fixture()
        s["contracts"].clear()
        d = audit.run(c, settlement=s)
        self.assertEqual(d["settlement"]["excluded"]["missing_settlement_contract"], 1)
        self.assertEqual(d["scorecard"]["models"]["Consensus"]["own_coverage"]["n"], 0)

    def test_misrepresented_model_probability_rejected(self):
        c, _ = fixture()
        c["picks"][0]["Engine_A"] = .9
        self.check_block(c, reason="model_probability_mismatch:Engine_A")

    def test_weight_change_blocks_baseline(self):
        c, _ = fixture()
        c["picks"][0]["production_ensemble"]["weight_historical"] = .7
        self.check_block(c, reason="production_baseline_weight_changed")

    def test_market_does_not_enter_ensemble(self):
        c, _ = fixture()
        c["picks"][0]["production_ensemble"]["historical_families"].append("Market")
        self.check_block(c, reason="invalid_historical_families")

    def test_no_fake_nuts_replacement(self):
        c, _ = fixture()
        c["picks"][0]["NUTS"] = .8
        c["picks"][0]["models"]["NUTS"].update(
            status="forecast", probability=.8, generated_at="2026-11-08T12:05:00Z")
        self.check_block(c, reason="one_sided_model_availability")

    def test_small_number_of_games_reports_underpowered(self):
        c, s = fixture(n_games=6)
        result = audit.run(c, settlement=s)
        self.assertEqual(result["scorecard"]["models"]["Consensus"]
                         ["game_cluster_uncertainty"]["status"],
                         "insufficient_independent_games")

    def test_game_block_bootstrap_deterministic(self):
        c, s = fixture(n_games=9)
        # One of nine game clusters is an under, to avoid a trivial all-hit CI.
        s["contracts"][0]["actual"] = 1
        s["contracts"][0]["winning_side"] = "under"
        result = audit.run(c, settlement=s)
        block = result["scorecard"]["models"]["Consensus"]["game_cluster_uncertainty"]
        self.assertEqual(block["status"], "descriptive_cluster_bootstrap")
        self.assertEqual(block["independent_games"], 9)
        a = audit.run(c, settlement=s)["scorecard"]["models"]["Consensus"]["game_cluster_uncertainty"]
        self.assertEqual(block, a)
        self.assertFalse(block["significance_or_promotion_certificate"])

    def test_inputs_remain_byte_for_byte_unchanged(self):
        c, s = fixture()
        a = json.dumps(c, sort_keys=True)
        b = json.dumps(s, sort_keys=True)
        audit.run(c, settlement=s)
        self.assertEqual(json.dumps(c, sort_keys=True), a)
        self.assertEqual(json.dumps(s, sort_keys=True), b)

    def test_canonical_report_and_unchanged_60_40_policy(self):
        manifest, _ = audit.exact_json(
            ROOT / "config/directional_research_baseline_20261108.json")
        self.assertTrue((ROOT / manifest["canonical_methodology"]).is_file())
        policy = ROOT / manifest["production_policy_path"]
        self.assertEqual(audit.git_blob_sha(policy),
                         manifest["production_policy_git_blob_sha"])
        value, _ = audit.exact_json(policy)
        self.assertEqual(value["weight_a"], .6)
        self.assertEqual(value["weight_b"], .4)
        self.assertFalse(value["empirically_calibrated"])

    def test_cli_requires_exact_comparison_sha_and_policy(self):
        c, s = fixture()
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            path = p / "predictions.json"
            path.write_text(json.dumps(c), encoding="utf-8")
            wrong = p / "manifest.json"
            wrong.write_text(json.dumps({
                "original_frozen_comparison_sha256": "0" * 64
            }), encoding="utf-8")
            code = audit.main([
                "--comparison", str(path),
                "--baseline-manifest", str(wrong),
                "--policy", str(ROOT / "config/production_consensus.json"),
                "--output", str(p / "must_not_exist.json")
            ])
            self.assertEqual(code, 2)
            self.assertFalse((p / "must_not_exist.json").exists())


    def test_sequential_sides_within_capture_window_allowed(self):
        c, s = fixture()
        c["picks"][1]["forecast_at"] = "2026-11-08T12:00:02+00:00"
        r = audit.run(c, settlement=s)
        self.assertEqual(r["scorecard"]["models"]["Consensus"]["own_coverage"]["n"], 1)

    def test_side_snapshots_more_than_five_minutes_apart_rejected(self):
        c, _ = fixture()
        c["picks"][1]["forecast_at"] = "2026-11-08T12:08:00+00:00"
        for name in ("Bayesian_A", "Bayesian_B"):
            c["picks"][1]["models"][name]["generated_at"] = \
                "2026-11-08T12:09:00+00:00"
        self.check_block(c, reason="paired_side_snapshots_more_than_5min_apart")

    def test_explained_frozen_nuts_sidecar_drift_is_warning_only(self):
        c, _ = fixture()
        for row in c["picks"]:
            nuts = .52 if row["side"] == "over" else .47
            row["NUTS"] = nuts
            row["models"]["NUTS"] = {
                "status": "forecast", "probability": nuts,
                "generated_at": "2026-11-08T12:07:00Z",
                "trained_through": "2026-01-04"
            }
            row["production_ensemble"]["historical_families"].append("NUTS")
            p = .4 * row["Engine_B"] + .6 * sum(
                row[name] for name in ("Engine_A", "Bayesian_A", "Bayesian_B", "NUTS")) / 4
            row["Consensus"] = p
            row["models"]["Consensus"]["probability"] = p
        receipt = audit.run(c)
        warnings = receipt["scope"]["nonunit_sidecar_warnings"]
        self.assertEqual({w["model"] for w in warnings}, {"NUTS", "Consensus"})
        self.assertFalse(receipt["ranking_allowed"])

    def test_non_nuts_consensus_drift_rejected(self):
        c, _ = fixture()
        c["picks"][1]["Consensus"] -= .01
        c["picks"][1]["models"]["Consensus"]["probability"] -= .01
        self.check_block(c, reason="side_probabilities_not_complementary:Consensus")

    def test_full_archive_can_be_scoped_to_one_event_without_mutation(self):
        c, s = fixture(n_games=2)
        for row in c["picks"][2:]:
            row["event_start"] = "2026-11-08T22:00:00Z"
        s["contracts"] = s["contracts"][:1]
        untouched = json.dumps(c, sort_keys=True)
        result = audit.run(c, settlement=s, sport="NFL",
                           event_start="2026-11-08T18:00:00Z")
        self.assertEqual(result["scope"]["contracts"], 1)
        self.assertEqual(result["scope_filter"]["original_frozen_side_rows"], 4)
        self.assertEqual(result["scope_filter"]["evaluated_side_rows"], 2)
        self.assertEqual(result["settlement"]["verified_contracts"], 1)
        self.assertEqual(json.dumps(c, sort_keys=True), untouched)

    def test_cli_receipt_is_repeatable_but_cannot_be_rewritten(self):
        c, s = fixture()
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            p = root / "frozen.json"
            q = root / "official.json"
            out = root / "receipt.json"
            p.write_text(json.dumps(c), encoding="utf-8")
            q.write_text(json.dumps(s), encoding="utf-8")
            args = ["--comparison", str(p), "--settlement", str(q),
                    "--sport", "NFL", "--event-start", "2026-11-08T18:00:00Z",
                    "--output", str(out)]
            self.assertEqual(audit.main(args), 0)
            baseline = out.read_bytes()
            self.assertEqual(audit.main(args), 0)
            self.assertEqual(out.read_bytes(), baseline)
            s["contracts"][0]["actual"] = 1.0
            s["contracts"][0]["winning_side"] = "under"
            q.write_text(json.dumps(s), encoding="utf-8")
            self.assertEqual(audit.main(args), 2)
            self.assertEqual(out.read_bytes(), baseline)

    def test_agents_policy_links_approved_research(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md", agents)
        self.assertIn("config/directional_research_baseline_20261108.json", agents)
        self.assertIn("No production promotion or Tier changes", agents)


if __name__ == "__main__":
    unittest.main()
