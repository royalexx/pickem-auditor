"""No-network, no-PyMC tests for online NUTS diagnostic logging."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from precision_sampling_progress import NUTSProgress, _ChainHealth, _preview_values


def stats(**changes):
    base = {"diverging": False, "reached_max_treedepth": False,
            "mean_tree_accept": .99, "step_size": .05,
            "depth": 7, "tree_size": 60, "energy": 10.0,
            "max_energy_error": .01}
    base.update(changes)
    return base


class OnlineStatsTest(unittest.TestCase):
    def test_warmup_problems_not_counted_as_posterior_divergences(self):
        chain = _ChainHealth()
        chain.observe(tuning=True, stats=stats(diverging=True,
                      reached_max_treedepth=True), now=10)
        chain.observe(tuning=False, stats=stats(diverging=True,
                      reached_max_treedepth=True), now=20)
        item = chain.snapshot(now=21, complete=False, target_accept=.99,
                              stall_seconds=900)
        self.assertEqual(item["warmup_divergences"], 1)
        self.assertEqual(item["posterior_divergences"], 1)
        self.assertEqual(item["posterior_max_treedepth_hits"], 1)
        self.assertIn("posterior_divergence_detected", item["warnings"])
        self.assertIn("posterior_treedepth_saturated", item["warnings"])

    def test_rolling_acceptance_warning_requires_enough_posterior_draws(self):
        chain = _ChainHealth()
        for i in range(99):
            chain.observe(tuning=False, stats=stats(mean_tree_accept=.5), now=i)
        self.assertNotIn("recent_acceptance_below_target", chain.snapshot(
            now=99, complete=False, target_accept=.99, stall_seconds=900)["warnings"])
        chain.observe(tuning=False, stats=stats(mean_tree_accept=.5), now=100)
        self.assertIn("recent_acceptance_below_target", chain.snapshot(
            now=100, complete=False, target_accept=.99, stall_seconds=900)["warnings"])
        self.assertAlmostEqual(chain.snapshot(now=100, complete=False,
            target_accept=.99, stall_seconds=900)["recent_100_posterior_acceptance_mean"], .5)

    def test_ebfmi_provisional_low_energy_movement(self):
        chain = _ChainHealth()
        for i in range(250):
            chain.observe(tuning=False, stats=stats(energy=100.0 + .03 * i), now=i)
        item = chain.snapshot(now=250, complete=False, target_accept=.99,
                              stall_seconds=900)
        self.assertIsNotNone(item["provisional_ebfmi"])
        self.assertLess(item["provisional_ebfmi"], .3)
        self.assertIn("provisional_low_ebfmi", item["warnings"])

    def test_unstarted_chain_not_falsely_stalled(self):
        chain = _ChainHealth()
        item = chain.snapshot(now=999999, complete=False, target_accept=.99,
                              stall_seconds=900)
        self.assertEqual(item["activity"], "not_started")
        self.assertNotIn("active_chain_no_recent_draw", item["warnings"])
        chain.observe(tuning=True, stats=stats(), now=100)
        item = chain.snapshot(now=1100, complete=False, target_accept=.99,
                              stall_seconds=900)
        self.assertIn("active_chain_no_recent_draw", item["warnings"])
        self.assertNotIn("active_chain_no_recent_draw", chain.snapshot(
            now=1100, complete=True, target_accept=.99, stall_seconds=900)["warnings"])

    def test_missing_sampler_stats_and_nonfinite_energy(self):
        chain = _ChainHealth()
        for i in range(50):
            chain.observe(tuning=True, stats=None, now=i)
        item = chain.snapshot(now=50, complete=False, target_accept=.99,
                              stall_seconds=900)
        self.assertIn("nuts_callback_stats_missing", item["warnings"])
        chain.observe(tuning=False, stats=stats(energy=float("nan")), now=51)
        item = chain.snapshot(now=52, complete=False, target_accept=.99,
                              stall_seconds=900)
        self.assertIn("nonfinite_posterior_energy", item["warnings"])
        json.dumps(item, allow_nan=False)


class ProgressIntegrationTest(unittest.TestCase):
    def test_monitor_failure_never_propagates_to_sampling_callback(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td, redirect_stdout(io.StringIO()) as output:
            monitor = NUTSProgress(draws=4, tune=3, chains=2,
                                   output=Path(td) / "progress.json",
                                   sport="NHL", stat="shots on goal", interval_seconds=3600)
            with patch.object(monitor, "_emit", side_effect=OSError("simulated_disk_failure")):
                monitor(trace=None, draw=SimpleNamespace(
                    chain=0, draw_idx=0, tuning=True, stats=[stats()]))
            self.assertTrue(monitor._disabled)
            # A monitor exception does not throw, cancel, or restart NUTS.
            monitor(trace=None, draw=SimpleNamespace(
                chain=0, draw_idx=1, tuning=True, stats=[stats()]))
            monitor.close()
            self.assertIn("sampling continues; telemetry disabled", output.getvalue())

    def test_unexpected_draw_chain_disables_monitor_without_raising(self):
        with tempfile.TemporaryDirectory() as td, redirect_stdout(io.StringIO()):
            monitor = NUTSProgress(draws=4, tune=3, chains=2,
                                   output=Path(td) / "progress.json",
                                   sport="NHL", stat="shots on goal", interval_seconds=3600)
            monitor(trace=None, draw=SimpleNamespace(
                chain=99, draw_idx=0, tuning=True, stats=None))
            self.assertTrue(monitor._disabled)
            monitor.close()

    def test_pair_preview_after_first_two_chains_only(self):
        with tempfile.TemporaryDirectory() as td, redirect_stdout(io.StringIO()) as output:
            root = Path(td)
            monitor = NUTSProgress(draws=8, tune=3, chains=4,
                                   output=root / "progress.json",
                                   sport="NHL", stat="shots on goal", interval_seconds=3600)
            for chain in (0, 1):
                for iteration in range(11):
                    monitor(trace=None, draw=SimpleNamespace(
                        chain=chain, draw_idx=iteration, tuning=iteration < 3,
                        point={"population_workload": [2.0 + .01 * iteration],
                               "population_rate": [-1.1 + .01 * iteration],
                               "home_effect": .05 + .01 * iteration,
                               "player_z": [[99, 88]]},
                        stats=[stats(energy=10 + .1 * iteration)]))
                if chain == 0:
                    self.assertFalse((root / "two_chain_preview.json").exists())
            monitor.close()
            receipt = json.loads((root / "two_chain_preview.json").read_text())
            self.assertEqual(receipt["schema"], "nuts_two_chain_preview_v1")
            self.assertEqual(receipt["chains"], [0, 1])
            self.assertEqual(receipt["draws_per_chain"], 8)
            self.assertIsNone(receipt["model_converged"])
            self.assertFalse(receipt["publication_eligible"])
            self.assertTrue(receipt["advisory_only"])
            self.assertTrue(receipt["all_four_chains_required"])
            self.assertNotIn("player_z", json.dumps(receipt))
            self.assertIn("NUTS_PAIR_PREVIEW", output.getvalue())

    def test_pair_preview_not_created_during_warmup_or_after_one_chain(self):
        with tempfile.TemporaryDirectory() as td, redirect_stdout(io.StringIO()):
            root = Path(td)
            monitor = NUTSProgress(draws=8, tune=3, chains=4,
                                   output=root / "progress.json",
                                   sport="NHL", stat="shots on goal", interval_seconds=3600)
            for i in range(11):
                monitor(trace=None, draw=SimpleNamespace(
                    chain=0, draw_idx=i, tuning=i < 3,
                    point={"home_effect": .2}, stats=[stats()]))
            for i in range(3):
                monitor(trace=None, draw=SimpleNamespace(
                    chain=1, draw_idx=i, tuning=True,
                    point={"home_effect": .2}, stats=[stats()]))
            monitor.close()
            self.assertFalse((root / "two_chain_preview.json").exists())

    def test_preview_has_bounded_parameters_and_ignores_missing_point(self):
        sample = {"population_rate": list(range(100)),
                  "population_workload": list(range(40)),
                  "home_effect": .1, "player_z": [[1] * 200] * 200}
        values = _preview_values(sample)
        self.assertEqual(len(values), 9)
        self.assertNotIn("player_z", str(values))
        self.assertEqual(_preview_values(None), {})

    def test_log_lines_and_json_keep_old_schema_and_new_health(self):
        with tempfile.TemporaryDirectory() as td, redirect_stdout(io.StringIO()) as stdout:
            output = Path(td) / "progress.json"
            reporter = NUTSProgress(draws=4, tune=3, chains=4, output=output,
                                    sport="NHL", stat="shots on goal", interval_seconds=3600)
            for i in range(7):
                reporter(trace=None, draw=SimpleNamespace(
                    chain=0, draw_idx=i, tuning=i < 3,
                    stats=[stats(diverging=(i == 4))]))
            reporter.close()
            record = json.loads(output.read_text())
            self.assertEqual(record["schema"], "pymc_chain_progress_v1")
            self.assertEqual(record["per_chain_iterations"], {"0": 7, "1": 0, "2": 0, "3": 0})
            self.assertEqual(record["health"]["chains"]["0"]["posterior_divergences"], 1)
            self.assertEqual(record["health"]["chains"]["1"]["activity"], "not_started")
            self.assertEqual(record["health"]["diagnostic_status"], "provisional_not_convergence_certification")
            self.assertTrue(record["health"]["final_rhat_ess_bfmi_required"])
            self.assertIn("NUTS_HEALTH", stdout.getvalue())
            self.assertIn("NUTS_PROGRESS", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
