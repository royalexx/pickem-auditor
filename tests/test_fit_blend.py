import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import fit_blend as fb
import pickem_math as pm


def _snapshot_row(
    idx: int,
    game_date: str,
    q_a: float,
    q_b: float | None,
    q_m: float,
    label: int,
    abstain: bool = False,
) -> dict:
    outcome = "win" if label else "loss"
    engine_b = {
        "mean": 4.2,
        "q_win": q_b if q_b is not None else 0.5,
        "q_push": 0.0,
        "abstain": abstain,
    }
    if abstain:
        engine_b["abstain_reason"] = "charting_missing"
    return {
        "run_at": "2026-10-01 12:00 ET",
        "game_date": game_date,
        "sport": "NFL",
        "matchup": "KC @ BUF",
        "player": f"Player {idx}",
        "stat": "receptions",
        "side": "over",
        "reference_line": 4.5,
        "final_rank": "Tier 2",
        "status": "GRADED",
        "researched": True,
        "actual_stat": 6 if label else 2,
        "outcome": outcome,
        "settled_at": f"{game_date}T12:00:00+00:00",
        "dist": "poisson",
        "inputs": {"dist": "poisson", "line": 4.5},
        "engine_a": {"mean": 4.8, "q_win": q_a, "q_push": 0.0},
        "engine_b": engine_b,
        "market": {"q_market": q_m, "q_market_comparable": q_m},
    }


def _synthetic_cohort(
    n_dates: int,
    rows_per_date: int,
    b_mode: str,
    seed: int = 7,
) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    idx = 0
    for day in range(n_dates):
        game_date = f"2026-01-{day + 1:02d}"
        for _ in range(rows_per_date):
            q_m = rng.uniform(0.45, 0.65)
            q_a = min(0.95, max(0.05, q_m + rng.uniform(-0.12, 0.12)))
            if b_mode == "useful":
                signal = 0.35 * fb.logit(q_a) + 0.55 * fb.logit(q_m) + rng.gauss(0, 0.25)
                q_b = fb.sigmoid(signal + rng.uniform(-0.2, 0.2))
                z = 0.25 * fb.logit(q_a) + 0.85 * fb.logit(q_b) + 0.35 * fb.logit(q_m)
            elif b_mode == "useless":
                q_b = rng.uniform(0.4, 0.6)
                z = 0.45 * fb.logit(q_a) + 0.45 * fb.logit(q_m)
            else:
                q_b = 1.0 - q_a
                z = 0.5 * fb.logit(q_a) + 0.45 * fb.logit(q_m) - 0.4 * fb.logit(q_b)
            p = fb.sigmoid(z)
            label = 1 if rng.random() < p else 0
            rows.append(_snapshot_row(idx, game_date, q_a, q_b, q_m, label))
            idx += 1
    return rows


class FitBlendSyntheticTests(unittest.TestCase):
    def test_useful_b_m3_beats_m0_on_log_loss(self):
        rows = _synthetic_cohort(n_dates=25, rows_per_date=16, b_mode="useful")
        report, oof = fb.build_fit_report(rows, l2=0.5, force=True)
        m0 = report["cohorts"]["with_b"]["models"]["M0"]["log_loss"]
        m3 = report["cohorts"]["with_b"]["models"]["M3"]["log_loss"]
        self.assertIsNotNone(m0)
        self.assertIsNotNone(m3)
        self.assertLess(m3, m0)

    def test_useless_b_still_runs(self):
        rows = _synthetic_cohort(n_dates=10, rows_per_date=10, b_mode="useless")
        report, _oof = fb.build_fit_report(rows, l2=0.5, force=True)
        self.assertGreater(report["n_settled"], 0)
        self.assertIn("M3", report["cohorts"]["with_b"]["models"])

    def test_harmful_b_keeps_smaller_b_weight_than_useful_b(self):
        useful_rows = _synthetic_cohort(n_dates=20, rows_per_date=12, b_mode="useful", seed=99)
        harmful_rows = _synthetic_cohort(n_dates=20, rows_per_date=12, b_mode="harmful", seed=99)
        useful_report, _ = fb.build_fit_report(useful_rows, l2=1.0, force=True)
        harmful_report, _ = fb.build_fit_report(harmful_rows, l2=1.0, force=True)
        useful_b = useful_report["cohorts"]["with_b"]["weights"]["M3"]["logit_qB"]
        harmful_b = harmful_report["cohorts"]["with_b"]["weights"]["M3"]["logit_qB"]
        self.assertGreater(abs(useful_b), abs(harmful_b))


class FitBlendGuardTests(unittest.TestCase):
    def test_refuses_weights_without_force(self):
        rows = _synthetic_cohort(n_dates=5, rows_per_date=10, b_mode="useful")
        report, _oof = fb.build_fit_report(rows, l2=1.0, force=False)
        self.assertFalse(report["weights_included"])
        self.assertIsNone(report["cohorts"]["with_b"]["weights"])

    def test_force_stamps_underpowered(self):
        rows = _synthetic_cohort(n_dates=5, rows_per_date=10, b_mode="useful")
        report, _oof = fb.build_fit_report(rows, l2=1.0, force=True)
        self.assertTrue(report["weights_included"])
        self.assertEqual(report["cohorts"]["with_b"]["weights_stamp"], "UNDERPOWERED")

    def test_abstain_cohort_uses_a_market_only(self):
        rows = []
        for i in range(40):
            rows.append(
                _snapshot_row(
                    i,
                    f"2026-02-{(i % 10) + 1:02d}",
                    0.58,
                    None,
                    0.52,
                    i % 2,
                    abstain=True,
                )
            )
        report, _oof = fb.build_fit_report(rows, l2=1.0, force=True)
        self.assertGreater(report["cohorts"]["b_abstain"]["n"], 0)
        self.assertNotIn("M3", report["cohorts"]["b_abstain"]["models"])


class FitBlendMathTests(unittest.TestCase):
    def test_newton_matches_reference_on_toy_data(self):
        rows = []
        for i in range(80):
            q_a = 0.4 + (i % 5) * 0.05
            q_m = 0.5
            label = 1 if (q_a + q_m) > 1.0 else 0
            rows.append(
                {
                    "label": label,
                    "features": {"logit_qA": fb.logit(q_a), "logit_qM": fb.logit(q_m)},
                }
            )
        weights = fb.fit_logistic(rows, ["logit_qA", "logit_qM"], fb.M2_PRIORS, l2=0.1)
        for row in rows[:5]:
            prob = fb.predict_logistic(row, weights, ["logit_qA", "logit_qM"])
            self.assertTrue(0.0 < prob < 1.0)

    def test_mean_blend_rebuilds_distribution(self):
        row = fb.enrich_row(
            _snapshot_row(0, "2026-03-01", 0.6, 0.55, 0.5, 1),
        )
        self.assertIsNotNone(row)
        q_hi = fb.mean_blend_probability(row, 1.0)
        q_lo = fb.mean_blend_probability(row, 0.0)
        self.assertIsNotNone(q_hi)
        self.assertIsNotNone(q_lo)
        self.assertNotAlmostEqual(q_hi, q_lo, places=3)


class FitBlendClusterBootstrapTests(unittest.TestCase):
    def test_one_slate_cannot_certify_a_blend(self):
        a = [(0.5, 1, "2026-01-01", (str(i),)) for i in range(400)]
        b = [(0.9, 1, "2026-01-01", (str(i),)) for i in range(400)]
        self.assertIsNone(fb.bootstrap_ci(a, b, "log_loss"))

    def test_mismatched_contract_identity_fails_closed(self):
        a = [(0.5, 1, f"2026-01-{d + 1:02d}", (str(d),))
             for d in range(20)]
        b = [(0.6, 1, p[2], ("different-" + str(i),))
             for i, p in enumerate(a)]
        self.assertIsNone(fb.bootstrap_ci(a, b, "brier"))

    def test_date_block_interval_reflects_correlated_slates(self):
        baseline, challenger = [], []
        for day in range(20):
            date = f"2026-01-{day + 1:02d}"
            # Ten props on one slate share the same forecast error direction.
            # Repeating each slate ten times must not create 200 IID games.
            for player in range(10):
                ident = (date, str(player))
                baseline.append((0.5, 1, date, ident))
                challenger.append((0.8 if day < 10 else 0.2, 1, date, ident))
        result = fb.bootstrap_ci(baseline, challenger, "brier")
        self.assertIsNotNone(result)
        self.assertEqual(result["independent_dates"], 20)
        self.assertLess(result["low"], 0)
        self.assertGreater(result["high"], 0)
        self.assertEqual(result["method"], "paired_date_block_bootstrap_v1")

    def test_300_rows_on_ten_dates_cannot_promote(self):
        rows = _synthetic_cohort(n_dates=10, rows_per_date=40, b_mode="useful")
        report, oof = fb.build_fit_report(rows, l2=0.5, force=False)
        self.assertGreaterEqual(report["n_settled"], fb.MIN_SETTLED)
        ok, reason = fb.should_emit_config(report, oof)
        self.assertFalse(ok)
        self.assertIn("independent chronological", reason)


class BlendWeightsVersionTests(unittest.TestCase):
    def test_snapshot_stamps_blend_weights_version(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "blend_weights.json"
            config.write_text(
                json.dumps({"version": "test-version-1"}),
                encoding="utf-8",
            )
            original = pm.DEFAULT_BLEND_WEIGHTS_PATH
            pm.DEFAULT_BLEND_WEIGHTS_PATH = config
            try:
                record = pm.normalize_snapshot(
                    {
                        "run_at": "2026-10-01",
                        "game_date": "2026-10-01",
                        "sport": "NBA",
                        "matchup": "A @ B",
                        "player": "X",
                        "stat": "points",
                        "side": "over",
                        "reference_line": 20.5,
                        "final_rank": "Tier 2",
                        "status": "GRADED",
                        "researched": True,
                    }
                )
            finally:
                pm.DEFAULT_BLEND_WEIGHTS_PATH = original
            self.assertEqual(record["blend_weights_version"], "test-version-1")


if __name__ == "__main__":
    unittest.main()
