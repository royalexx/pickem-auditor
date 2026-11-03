"""Regression checks for xarray diagnostic memory and rounded yardage settlement.

The population model is research-only; these tests never promote predictions.
"""
import importlib.util
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import joint_population_bayes as population
import joint_nhl_bayes as nhl


class DiagnosticArrays(unittest.TestCase):
    def test_unrelated_dims_are_not_broadcast(self):
        if importlib.util.find_spec("xarray") is None:
            self.skipTest("xarray optional")
        import numpy as np
        import xarray as xr
        ds = xr.Dataset({
            "player": (("player_dim",), np.array([0.1, 0.2, 0.3])),
            "opponent": (("opponent_dim",), np.array([0.4, 0.5])),
            "season": (("season_dim",), np.array([0.6, 0.7, 0.8, 0.9])),
        })
        expected = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        self.assertEqual(population._to_values(ds), expected)
        self.assertEqual(nhl._diagnostic_values(ds), expected)

    def test_invalid_diagnostic_values_fail_closed(self):
        if importlib.util.find_spec("xarray") is None:
            self.skipTest("xarray optional")
        import xarray as xr
        ds = xr.Dataset({"a": ("x", [1., float("nan")])})
        with self.assertRaises(ValueError):
            population._to_values(ds)


class YardageLattice(unittest.TestCase):
    def test_whole_and_fractional_lines_conserve_probability(self):
        if importlib.util.find_spec("scipy") is None:
            self.skipTest("scipy optional")
        import numpy as np
        from scipy.stats import t
        n = 100
        zeros = np.zeros(n)
        scalar = lambda v: np.full(n, v)
        data = {
            "player_position": {"p": "WR"}, "players": ["p"],
            "positions": ["WR"], "opponents": ["O"], "seasons": ["2025"],
            "family": "yardage", "sport": "NFL", "stat": "receiving yards",
            "source_digest": "test-source", "last_game": "2025-12-01",
        }
        arrays = {
            "player_effect": np.zeros((n, 1, 2)),
            "population_workload": np.zeros((n, 1)),
            "population_rate": np.full((n, 1), 50.0),
            "season_workload": np.zeros((n, 1)),
            "season_rate": np.zeros((n, 1)),
            "opponent_rate": np.zeros((n, 1)),
            "workload_sigma": zeros, "home_effect": zeros,
            "yardage_sigma": scalar(20.0),
        }
        def check(line):
            return population.forecast(None, data, player_id="p", opponent="O",
                season="2025", home=False, line=line, draws=n, seed=7,
                diagnostic={"posterior_sampling_ok": True},
                cache={"count": n, "arrays": arrays})
        whole = check(50)
        half = check(50.5)
        quarter = check(50.25)
        expected_push = t.cdf(50.5, 4, loc=50, scale=20) - t.cdf(
            49.5, 4, loc=50, scale=20)
        self.assertAlmostEqual(whole["q_push"], expected_push, places=10)
        self.assertGreater(whole["q_push"], 0.01)
        self.assertAlmostEqual(whole["q_over"], half["q_over"], places=10)
        self.assertAlmostEqual(whole["q_over"], quarter["q_over"], places=10)
        self.assertEqual(half["q_push"], 0)
        self.assertEqual(quarter["q_push"], 0)
        for row in (whole, half, quarter, check(-2)):
            self.assertAlmostEqual(row["q_over"]+row["q_push"]+row["q_under"],1.0,places=10)
            self.assertFalse(row["publication_eligible"])
            self.assertIn("v2-integer-yardage",row["model_version"])


if __name__ == "__main__":
    unittest.main()
