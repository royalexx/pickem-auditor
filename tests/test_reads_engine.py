"""Tests for the reads-based Engine B."""

import math
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import pickem_math as pm
import reads_engine as re


def _reads_row(**extra):
    row = {
        "sport": "NFL",
        "stat": "receptions",
        "dist": "poisson",
        "side": "over",
        "line": 3.5,
        "team_pass_attempts_expected": 34.0,
        "team_bucket_throw_share": 0.15,
        "checkdown_target_share": 0.30,
        "checkdown_player_games": 8,
        "checkdown_team_games": 9,
        "conversion": 0.80,
        "def_matchup_factor": 1.05,
        "volume_source": "team_pass_attempts_expected",
        "reads_charting_ok": True,
        "reads_join_ok": True,
        "reads_total_stat_validated": True, # synthetic full-stat validated fixture only
    }
    row.update(extra)
    return row


class ReadsEngineTests(unittest.TestCase):
    def test_supported_stat_projects_mean(self):
        row = _reads_row()
        out = re.project_reads(row)
        self.assertFalse(out["abstain"])
        expected = 34.0 * 0.15 * 0.30 * 0.80 * 1.05
        self.assertAlmostEqual(out["mean_b"], expected, places=9)
        self.assertEqual(out["shared_inputs"], ["volume"])
        self.assertGreater(out["q_win_b"], 0.0)
        self.assertGreater(out["se_b"], 0.0)

    def test_abstains_when_bucket_games_are_thin(self):
        out = re.project_reads(_reads_row(checkdown_player_games=4))
        self.assertTrue(out["abstain"])
        self.assertEqual(out["abstain_reason"], "insufficient_bucket_games")

    def test_abstains_when_charting_missing(self):
        out = re.project_reads(_reads_row(reads_charting_ok=False))
        self.assertTrue(out["abstain"])
        self.assertEqual(out["abstain_reason"], "charting_missing")

    def test_abstains_when_join_failed(self):
        out = re.project_reads(_reads_row(reads_join_failed=True))
        self.assertTrue(out["abstain"])
        self.assertEqual(out["abstain_reason"], "join_failed")

    def test_non_receiving_stat_abstains(self):
        nba = _reads_row(sport="NBA", stat="points")
        self.assertTrue(re.project_reads(nba)["abstain"])
        rush = _reads_row(stat="rushing yards")
        self.assertTrue(re.project_reads(rush)["abstain"])

    def test_independence_from_engine_a_baseline(self):
        row = _reads_row()
        first = re.project_reads(row)
        row["baseline_mean"] = 99.0
        second = re.project_reads(row)
        self.assertEqual(first["mean_b"], second["mean_b"])


    def test_normal_distribution_scales_sd_with_baseline_mean(self):
        row = _reads_row(
            stat="receiving yards",
            dist="normal",
            line=55.5,
            sd=20.0,
            baseline_mean=50.0,
            first_read_target_share=0.35,
            first_read_player_games=8,
            first_read_team_games=8,
            conversion=10.0,
        )
        out_scaled = re.project_reads(row)
        row_unscaled = dict(row)
        del row_unscaled["baseline_mean"]
        out_unscaled = re.project_reads(row_unscaled)
        self.assertFalse(out_scaled["abstain"])
        self.assertNotAlmostEqual(out_scaled["se_b"], out_unscaled["se_b"])


class CrosscheckTests(unittest.TestCase):
    def _engines(self, mean_a, mean_b, q_a, q_b, se_b=0.02):
        return (
            {"mean": mean_a, "q_win": q_a, "q_push": 0.0},
            {
                "mean_b": mean_b,
                "q_win_b": q_b,
                "se_b": se_b,
                "abstain": False,
            },
            {"side": "over", "line": 3.5},
        )

    def test_tolerance_is_probability_points_not_stat_se(self):
        a, b, market = self._engines(5.0, 5.0, 0.60, 0.60, se_b=10.0)
        cross = pm.crosscheck(a, b, market)
        self.assertAlmostEqual(cross["tolerance"], 0.08)
        self.assertEqual(cross["b_vote"], "agree")
        a, b, market = self._engines(5.0, 5.0, 0.90, 0.60, se_b=10.0)
        self.assertEqual(pm.crosscheck(a, b, market)["b_vote"], "disagree")

    def test_abstain_is_not_disagree(self):
        b = {"abstain": True, "se_b": 0.02}
        cross = pm.crosscheck({"mean": 4, "q_win": 0.6}, b, {"side": "over", "line": 3.5})
        self.assertEqual(cross["b_vote"], "abstain")

    def test_disagree_when_means_split_the_line(self):
        a, b, market = self._engines(5.0, 2.0, 0.62, 0.40, se_b=0.001)
        cross = pm.crosscheck(a, b, market)
        self.assertEqual(cross["b_vote"], "disagree")
        self.assertFalse(cross["side_agree"])


class EngineBPipelineTests(unittest.TestCase):
    def _pipeline(self, **extra):
        raw = {
            "dist": "poisson",
            "side": "over",
            "line": 3.5,
            "baseline_mean": 4.2,
            "baseline_n": 30,
            "soft_flags": 0,
            "mechanisms": 2,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": True,
            "q_market": 0.55,
            "retrieved_minutes_ago": 5,
            "stat": "receptions",
        }
        raw.update(_reads_row())
        raw.update(extra)
        return pm.evaluate_candidate(raw)

    def test_disagree_adds_crosscheck_flag(self):
        result = self._pipeline(
            baseline_mean=6.0,
            team_pass_attempts_expected=20.0,
            team_bucket_throw_share=0.05,
            checkdown_target_share=0.10,
            conversion=0.50,
        )
        self.assertNotIn("CROSSCHECK_DISAGREE", result["derived_flags"])
        self.assertEqual(result["crosscheck"]["b_vote"], "abstain")
        self.assertEqual(result["engine_b"]["abstain_reason"], "missing_scouting_packet")

    def test_abstain_does_not_add_crosscheck_flag(self):
        result = self._pipeline(sport="NBA", stat="points")
        self.assertTrue(result["engine_b"]["abstain"])
        self.assertNotIn("CROSSCHECK_DISAGREE", result["derived_flags"])
        self.assertEqual(result["crosscheck"]["b_vote"], "abstain")

    def test_engine_b_never_raises_rank(self):
        without = pm.evaluate_candidate({
            "dist": "poisson",
            "side": "over",
            "line": 3.5,
            "baseline_mean": 4.6,
            "baseline_n": 30,
            "soft_flags": 0,
            "mechanisms": 2,
            "hard_veto": False,
            "data_veto": False,
            "research_checklist": True,
            "q_market": 0.52,
            "retrieved_minutes_ago": 5,
        })
        with_reads = self._pipeline(
            baseline_mean=4.6,
            team_pass_attempts_expected=40.0,
            team_bucket_throw_share=0.20,
            checkdown_target_share=0.40,
            conversion=0.90,
        )
        order = pm.FINAL_ORDER
        self.assertGreaterEqual(
            order[without["final_rank"]],
            order[with_reads["final_rank"]],
        )


if __name__ == "__main__":
    unittest.main()
