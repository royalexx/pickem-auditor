"""No-network bounded tests for new daily NFL + NBA shadow validation."""
import json
import math
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research.v25_morning_validation import score as m


class StrictMorningTests(unittest.TestCase):
    def test_discrete_crps_exact_not_model_refit(self):
        self.assertAlmostEqual(m.discrete_crps([(2, 1.0)], 4), 2)
        self.assertAlmostEqual(m.discrete_crps([(0, .5), (2, .5)], 1), .5)

    def test_invalid_distribution_mass_rejected(self):
        with self.assertRaisesRegex(ValueError, "PMF_MASS_NONUNIT"):
            m.discrete_crps([(1, .8)], 2)

    def test_probability_scoring_and_boundaries(self):
        self.assertAlmostEqual(m.score_probability(.7, 1)["brier"], .09)
        self.assertTrue(math.isfinite(m.score_probability(1.0, 0)["logloss"]))
        with self.assertRaisesRegex(ValueError, "NONPROBABILITY"):
            m.score_probability(1.1, 1)

    def test_player_stat_source_is_strict_not_guessed_zero(self):
        stats = {("10", "passing"): {"labels": {"C/ATT": "18/29", "YDS": "218"},
                                     "team_abbreviation": "DET"}}
        self.assertEqual(m.nfl_stat_observation(stats, "10", "completions")[0], 18)
        self.assertEqual(m.nfl_stat_observation(stats, "10", "pass attempts")[0], 29)
        self.assertEqual(m.nfl_stat_observation(stats, "10", "passing yards")[0], 218)
        self.assertEqual(m.nfl_stat_observation(stats, "10", "receptions")[1],
                         "CATEGORY_OUTCOME_UNLISTED_UNKNOWN_NOT_ZERO")

    def test_team_mismatch_rejects_even_valid_player_id(self):
        stats = {("10", "passing"): {"labels": {"C/ATT": "18/29", "YDS": "218"},
                                     "team_abbreviation": "DET"}}
        self.assertEqual(m.nfl_stat_observation(stats, "10", "pass attempts", "NE")[1],
                         "OUTCOME_TEAM_MISMATCH")

    def test_tackles_requires_separate_original_stat_parity(self):
        self.assertIn("tackles + assists", m.EXCLUDED_FOR_SCORE)
        stats = {("10", "defensive"): {"labels": {"TOT": "9"}, "team_abbreviation": "DET"}}
        self.assertEqual(m.nfl_stat_observation(stats, "10", "tackles + assists")[1],
                         "ESPN_TOTAL_TACKLES_PARITY_UNVERIFIED")

    def test_model_forecast_created_after_kickoff_is_blocked(self):
        row = {"event_start_at": "2026-11-15T18:00:00+00:00",
               "S2_original_source_model": {
                   "forecast_created_at": "2026-11-15T18:00:01+00:00",
                   "p_over_given_no_push": .6,
                   "distribution_support_mass": [[1, 1.0]]}}
        result = m._model_distributions(row, 1, .5)
        self.assertEqual(result["S2"]["status"], "MODEL_BLOCKED")

    def test_pushed_contract_has_crps_but_not_binary_brier(self):
        row = {"event_start_at": "2026-11-15T18:00:00+00:00",
               "S2_original_source_model": {
                   "forecast_created_at": "2026-11-15T17:50:00+00:00",
                   "p_over_given_no_push": .7,
                   "distribution_support_mass": [[1, .5], [3, .5]]}}
        result = m._model_distributions(row, 2, 2)["S2"]
        self.assertEqual(result["status"], "SCORED")
        self.assertNotIn("brier", result["metrics"])
        self.assertIn("crps", result["metrics"])

    def test_market_no_push_is_not_fake_three_way(self):
        row = {"event_start_at": "2026-11-15T18:00:00+00:00",
               "C2_original_market_reference": {
                   "forecast_at": "2026-11-15T17:50:00+00:00",
                   "q_push": None, "p_over_given_no_push": .55}}
        result = m._model_distributions(row, 3, 2)["C2"]
        self.assertIn("brier", result["metrics"])
        self.assertNotIn("crps", result["metrics"])

    def test_no_original_nfl_ledger_is_explicit_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            outcome = m.nfl_validation(Path(tmp), Path(tmp))
        self.assertEqual(outcome["status"], "BLOCKED_MISSING_ORIGINAL_WS6_LEDGER")

    def test_missing_kickoff_preserves_rejection_not_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=m.fetch_final("https://example.test","missing",None,Path(tmp))
            self.assertEqual(r["status"],"MISSING_OR_INVALID_ORIGINAL_KICKOFF")

    def test_first_original_capture_not_backfilled(self):
        # The NBA candidate denominator remains absent without FIRST_CAPTURE.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = m.nba_validation(root, root)
            self.assertEqual(report["original_slot_count"], 10)
            self.assertEqual(report["slot_state_denominators"]["NO_GENUINE_PREGAME_CAPTURE"], 10)

    def test_source_final_gate_and_identity(self):
        document = {"header": {"competitions": [{"id": "1",
            "date": "2026-11-15T18:00:00+00:00",
            "status": {"type": {"completed": True, "name": "STATUS_FINAL"}},
            "competitors": [{"team": {"id": "10", "abbreviation": "DET"}},
                            {"team": {"id": "17", "abbreviation": "NE"}}]}]}}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(m, "utcnow", return_value=datetime(2026, 11, 16, tzinfo=timezone.utc)):
                r = m.fetch_final("https://example.test", "1", document["header"]["competitions"][0]["date"],
                                  Path(tmp), fetch=lambda _: json.dumps(document).encode())
                self.assertEqual(r["status"], "FINAL")
                self.assertTrue(list(Path(tmp).glob("1_*.json.gz")))
                document["header"]["competitions"][0]["status"]["type"]["completed"] = False
                blocked = m.fetch_final("https://example.test", "1", "2026-11-15T18:00:00+00:00",
                                       Path(tmp), fetch=lambda _: json.dumps(document).encode())
                self.assertEqual(blocked["status"], "NOT_FINAL")

    def test_append_only_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            m.make_once(path, {"value": 1})
            with self.assertRaises(FileExistsError):
                m.make_once(path, {"value": 2})
            self.assertEqual(json.loads(path.read_text())["value"], 1)


if __name__ == "__main__":
    unittest.main()
