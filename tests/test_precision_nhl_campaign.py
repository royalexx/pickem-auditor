"""Offline regression tests for NHL-only progress, resource cap and strict research contract."""
from __future__ import annotations
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import precision_nhl_campaign as nhl
from precision_sampling_progress import NUTSProgress


class NHLFourMarketTests(unittest.TestCase):
    def test_exact_four_nhl_volume_stats_and_unique_destinations(self):
        self.assertEqual(nhl.STATS,("shots on goal","hits","blocked shots","saves"))
        self.assertEqual(len(set(nhl.SLUGS.values())),4)

    def test_sampling_callback_outputs_json_and_noninteractive_progress_bar(self):
        with tempfile.TemporaryDirectory() as d:
            report=Path(d)/"progress.json"
            with redirect_stdout(io.StringIO()) as console:
                callback=NUTSProgress(draws=10,tune=5,chains=4,output=report,
                                      sport="NHL",stat="shots on goal",interval_seconds=1000)
                # Two active chains; the other two are still queued.
                callback(trace=None,draw=SimpleNamespace(chain=0,draw_idx=4,tuning=True))
                callback(trace=None,draw=SimpleNamespace(chain=1,draw_idx=7,tuning=False))
                callback.close()
            value=json.loads(report.read_text())
            self.assertEqual(value["chains"],4)
            self.assertEqual(value["completed_iterations"],13)
            self.assertEqual(value["target_iterations"],60)
            self.assertEqual(value["per_chain_iterations"]["1"],8)
            self.assertEqual(value["stage"],"done")
            self.assertIn("NUTS_PROGRESS",console.getvalue())
            self.assertIn("[",console.getvalue())

    def test_campaign_summary_preserves_ongoing_and_final_statuses(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"reports/precision_training/manual/shots-on-goal").mkdir(parents=True)
            snapshot={"percent":75,"stage":"warmup",
                      "per_chain_iterations":{"0":300,"1":250,"2":200,"3":150}}
            (root/"reports/precision_training/manual/shots-on-goal/progress.json").write_text(json.dumps(snapshot))
            result=nhl.summary(root,"manual",{"shots on goal":"running"},max_parallel=4)
            self.assertEqual(result["models"]["shots on goal"]["progress_percent"],75)
            self.assertEqual(result["completed_success"],0)
            self.assertEqual(result["market_count"],4)
            self.assertEqual(result["max_parallel_cpu_chains"],16)

    def test_resource_guard_rejects_invalid_parallelism(self):
        with self.assertRaises(ValueError):
            nhl.campaign(Path("."),max_parallel=5)
        with self.assertRaises(ValueError):
            nhl.campaign(Path("."),max_parallel=2,min_free_mb=2048)


if __name__=="__main__":
    unittest.main()
