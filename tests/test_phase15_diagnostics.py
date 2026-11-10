"""Phase 1.5 adversarial tests: no fake edge, hidden exclusions or outcome leakage."""
from __future__ import annotations
import csv
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import phase15_diagnostics as p


class Phase15Tests(unittest.TestCase):
    def make_csv(self, directory, name, rows):
        path = Path(directory) / name
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return path

    def contract(self, i=1, *, actual="5", line="4.5", prob=".7", baseline=".6"):
        return dict(week=str(i), game_id="GAME"+str(i), player_id="P"+str(i),
                    team="ABC", position="WR", market="targets",
                    research_line=line, line_type="synthetic_preweek_position_median",
                    model_p_over=prob, baseline_p_over=baseline,
                    predicted_side="over" if float(prob) >= .5 else "under",
                    selected_model_probability=str(max(float(prob), 1-float(prob))),
                    actual_stat=actual, result="HIT", hit="1")

    def component(self, i=1):
        return dict(week=str(i), game_id="G"+str(i), player_id="P"+str(i),
                    market="targets", forecast_at="2026-11-08T12:00:00Z",
                    event_start_at="2026-11-08T18:00:00Z",
                    pred_team_volume="40", actual_team_volume="50",
                    pred_participation="1", actual_participation="1",
                    pred_share=".1", actual_share=".1",
                    pred_efficiency="1", actual_efficiency="1",
                    predicted_stat_mean="4", actual_stat="5")

    def test_identical_prediction_outcome_score(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [self.contract(i) for i in range(1, 7)]
            result = p.evaluate_contracts(self.make_csv(d, "a.csv", rows), replicates=30)
            self.assertEqual(result["paired_scored_rows"], 6)
            self.assertAlmostEqual(result["model"]["brier"], .09)
            self.assertAlmostEqual(result["baseline"]["brier"], .16)
            self.assertEqual(result["by_side"]["over"]["hits"], 6)
            self.assertEqual(result["matched_paired_uncertainty"]["game"]["clusters"], 6)
            self.assertEqual(result["unique_weeks"], 6)

    def test_rejected_rows_remain_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [self.contract(1), self.contract(2, actual="")]
            rows[1]["result"], rows[1]["hit"] = "UNMATCHED", ""
            result = p.evaluate_contracts(self.make_csv(d, "a.csv", rows), replicates=0)
            self.assertEqual(result["input_rows"], 2)
            self.assertEqual(result["paired_scored_rows"], 1)
            self.assertEqual(result["excluded"]["UNMATCHED"], 1)

    def test_push_excluded_but_counted(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [self.contract(1, actual="4", line="4")]
            rows[0]["result"], rows[0]["hit"] = "PUSH", ""
            result = p.evaluate_contracts(self.make_csv(d, "a.csv", rows), replicates=0)
            self.assertEqual(result["excluded"]["PUSH"], 1)
            self.assertEqual(result["paired_scored_rows"], 0)

    def test_declared_direction_inconsistency_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.contract()
            r["predicted_side"] = "under"
            with self.assertRaisesRegex(p.Phase15Error, "frozen_side_probability_mismatch"):
                p.evaluate_contracts(self.make_csv(d, "a.csv", [r]))

    def test_settlement_hit_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.contract()
            r["hit"] = "0"
            with self.assertRaisesRegex(p.Phase15Error, "settlement_hit_mismatch"):
                p.evaluate_contracts(self.make_csv(d, "a.csv", [r]))

    def test_duplicate_contracts_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.contract()
            with self.assertRaisesRegex(p.Phase15Error, "duplicate_contract"):
                p.evaluate_contracts(self.make_csv(d, "a.csv", [r, r]))

    def test_unknown_actual_with_fabricated_hit_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.contract(actual="")
            with self.assertRaisesRegex(p.Phase15Error, "outcome_status_mismatch"):
                p.evaluate_contracts(self.make_csv(d, "a.csv", [r]))

    def test_nonfinite_probability_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.contract()
            r["model_p_over"] = "nan"
            with self.assertRaisesRegex(p.Phase15Error, "invalid_numeric"):
                p.evaluate_contracts(self.make_csv(d, "a.csv", [r]))

    def test_original_actual_over_and_selected_probability_crosschecked(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.contract()
            r["actual_over"] = "0"
            with self.assertRaisesRegex(p.Phase15Error, "recorded_over_outcome_mismatch"):
                p.evaluate_contracts(self.make_csv(d, "a.csv", [r]))
            r["actual_over"] = "1"
            r["selected_model_probability"] = ".99"
            with self.assertRaisesRegex(p.Phase15Error, "selected_probability_mismatch"):
                p.evaluate_contracts(self.make_csv(d, "b.csv", [r]))

    def test_original_result_status_not_reinterpreted(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.contract()
            r["result"] = "MISS"
            with self.assertRaisesRegex(p.Phase15Error, "settlement_status_mismatch"):
                p.evaluate_contracts(self.make_csv(d, "a.csv", [r]))
            r["result"] = "SOMETHING_UNEXPECTED"
            with self.assertRaisesRegex(p.Phase15Error, "invalid_scored_result_status"):
                p.evaluate_contracts(self.make_csv(d, "b.csv", [r]))

    def test_game_cluster_bootstrap_is_deterministic(self):
        rows = [{"game": str(i), "week": str(i//2), "v": float(i)} for i in range(1, 15)]
        left = p.bootstrap_interval(rows, lambda x: x["v"], cluster="game",
                                    replicates=300, seed=4)
        right = p.bootstrap_interval(rows, lambda x: x["v"], cluster="game",
                                     replicates=300, seed=4)
        self.assertEqual(left, right)
        self.assertLess(left["lower_95"], left["upper_95"])

    def test_simple_oracle_shapley_exact(self):
        pred = (4., 1., 1., 1.)
        actual = (5., 1., 1., 1.)
        gains = p.shapley_diagnostic(pred, actual, 5.)
        self.assertAlmostEqual(gains["team_volume"], 1.)
        for item in ("participation", "share", "efficiency"):
            self.assertAlmostEqual(gains[item], 0.)
        self.assertAlmostEqual(sum(gains.values()), 1.)

    def test_oracle_shapley_conservation_multiple_components(self):
        pred = (40., .8, .1, .7)
        actual = (55., 1., .14, .9)
        gains = p.shapley_diagnostic(pred, actual, 7)
        self.assertAlmostEqual(sum(gains.values()),
                               p.oracle_loss(pred, actual, 7, set())
                               - p.oracle_loss(pred, actual, 7, set(range(4))), places=8)

    def test_component_time_travel_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.component()
            r["forecast_at"] = "2026-11-09T08:00:00Z"
            with self.assertRaisesRegex(p.Phase15Error, "forecast_not_pregame"):
                p.evaluate_components(self.make_csv(d, "c.csv", [r]))

    def test_component_naive_time_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.component()
            r["forecast_at"] = "2026-11-08T12:00:00"
            with self.assertRaisesRegex(p.Phase15Error, "naive_timestamp"):
                p.evaluate_components(self.make_csv(d, "c.csv", [r]))

    def test_component_forecast_reconstruction_guard(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.component()
            r["predicted_stat_mean"] = "10"
            with self.assertRaisesRegex(p.Phase15Error, "reconstructed_forecast_mismatch"):
                p.evaluate_components(self.make_csv(d, "c.csv", [r]))

    def test_component_actuals_are_offline_oracle_not_features(self):
        with tempfile.TemporaryDirectory() as d:
            rows = [self.component(i) for i in range(1, 7)]
            result = p.evaluate_components(self.make_csv(d, "c.csv", rows), replicates=50)
            self.assertAlmostEqual(result["mean_original_squared_error"], 1.)
            self.assertAlmostEqual(result["mean_full_oracle_squared_error"], 0.)
            self.assertAlmostEqual(result["mean_shapley_error_reduction"]["team_volume"], 1.)
            self.assertIn("Postgame oracle", result["interpretation"])

    def test_binomial_tail_known_values(self):
        self.assertEqual(p.binom_survival(2, .5)[0], 1)
        self.assertAlmostEqual(p.binom_survival(2, .5)[1], .75)
        self.assertAlmostEqual(p.binom_survival(2, .5)[2], .25)
        self.assertAlmostEqual(p.binom_survival(2, .5)[3], 0)
        self.assertAlmostEqual(p.binom_survival(10, 0)[1], 0)
        self.assertAlmostEqual(p.binom_survival(10, 1)[10], 1)

    def test_exact_power_meets_alpha_and_target(self):
        x = p.binomial_power(.75, .80, maximum=1500)
        self.assertGreater(x["independent_events"], 100)
        self.assertLessEqual(x["actual_alpha"], .05 + 1e-12)
        self.assertGreaterEqual(x["achieved_power"], .8 - 1e-12)

    def test_power_increases_with_smaller_effect(self):
        a = p.binomial_power(.70, .80)["independent_events"]
        b = p.binomial_power(.75, .80)["independent_events"]
        self.assertGreater(b, a)

    def test_missing_provenance_cannot_certify_tiers(self):
        with tempfile.TemporaryDirectory() as d:
            in_file = self.make_csv(d, "a.csv", [self.contract()])
            out = Path(d) / "receipt.json"
            p.main(["--contracts", str(in_file), "--output", str(out),
                    "--cohort-status", "synthetic_historical", "--bootstrap", "0"])
            import json
            data = json.loads(out.read_text())
            self.assertFalse(data["tier_certified"])
            self.assertFalse(data["promotion_allowed"])
            self.assertIn("certified_real_market_quote_and_payout_comparison", data["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
