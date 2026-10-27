import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import report as rp


def _settled_row(**extra):
    base = {
        "game_date": "2026-10-01",
        "player": "A",
        "stat": "points",
        "side": "over",
        "status": "GRADED",
        "actual_stat": 25,
        "outcome": "win",
        "q_grade": 0.61,
        "q_market_comparable": 0.55,
        "q_gap": 0.06,
        "final_rank": "Tier 2",
        "sport": "NBA",
        "settled_at": "2026-10-02T00:00:00+00:00",
    }
    base.update(extra)
    return base


class ReportTests(unittest.TestCase):
    def test_brier_and_reliability_bins(self):
        rows = [
            _settled_row(outcome="win", q_grade=0.61),
            _settled_row(player="B", outcome="loss", q_grade=0.61, actual_stat=10),
            _settled_row(player="C", outcome="win", q_grade=0.51, actual_stat=30),
        ]
        report = rp.build_report(rows)
        self.assertEqual(report["n_settled_graded"], 3)
        self.assertAlmostEqual(report["brier_model"], 0.254767, places=3)
        self.assertIsNotNone(report["brier_market_comparable"])
        bins = {item["bin"]: item for item in report["reliability_by_q_grade"]}
        self.assertEqual(bins["0.60+"]["n"], 2)
        self.assertEqual(bins["0.60+"]["status"], "insufficient")
        self.assertEqual(bins["0.50-0.52"]["n"], 1)

    def test_dedupes_duplicate_side_rows(self):
        rows = [
            _settled_row(settled_at="2026-10-02T00:00:00+00:00"),
            _settled_row(settled_at="2026-10-03T00:00:00+00:00", outcome="loss", actual_stat=10),
        ]
        report = rp.build_report(rows)
        self.assertEqual(report["n_settled_graded"], 1)

    def test_gap_share_counts_eight_point_gaps(self):
        rows = [
            _settled_row(q_gap=0.09),
            _settled_row(player="B", q_gap=0.02, outcome="loss", actual_stat=1),
        ]
        report = rp.build_report(rows)
        self.assertAlmostEqual(report["gap_abs_ge_8pts_share"], 0.5)

    def test_format_marks_calibration_gate(self):
        report = rp.build_report([_settled_row()])
        text = rp.format_report(report)
        self.assertIn("insufficient", text)
        self.assertIn("calibration_gate=need at least 300", text)


    def test_include_shadow_flag_scores_shadow_rows(self):
        shadow_row = _settled_row(run_type="shadow", researched=False, outcome="win", q_grade=0.59)
        self.assertEqual(rp.build_report([shadow_row])["n_settled_graded"], 0)
        self.assertEqual(rp.build_report([shadow_row], include_shadow=True)["n_settled_graded"], 1)


if __name__ == "__main__":
    unittest.main()
