"""Offline tests: the benchmark must not silently widen the cohort or enable production."""
from __future__ import annotations
import argparse
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import precision_sampler_benchmark as b


def opts(**changes):
    v=dict(sampler="pymc",stat="hits",as_of="2026-10-29",
           max_per_position=12,draws=400,tune=400,chains=4,
           cores=2,target_accept=.99,out=Path("tmp.json"))
    v.update(changes)
    return argparse.Namespace(**v)


class BenchmarkContract(unittest.TestCase):
    def test_backends_and_markets(self):
        self.assertEqual(b.BACKENDS,("pymc","nutpie","numpyro"))
        self.assertEqual(b.MARKETS,("hits","shots on goal","blocked shots","saves"))

    def test_accepts_matching_budgets(self):
        b.validate_options(opts())
        b.validate_options(opts(sampler="nutpie"))
        b.validate_options(opts(sampler="numpyro"))

    def test_refuses_unbounded_cohort(self):
        with self.assertRaises(ValueError):
            b.validate_options(opts(max_per_position=0))

    def test_refuses_bad_resource_budget_and_future_cutoff(self):
        for updates in ({"cores":5},{"chains":1},{"draws":20},{"tune":20},
                        {"as_of":"2099-01-01"},{"stat":"NBA points"}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                b.validate_options(opts(**updates))

    def test_failed_sampler_writes_explicit_nonproduction_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            a=opts(out=Path(d)/"trial.json")
            with patch.object(b,"select_data",side_effect=RuntimeError("benchmark-source-unavailable")):
                self.assertEqual(b.execute(a),2)
            result=json.loads(a.out.read_text(encoding="utf-8"))
            self.assertEqual(result["status"],"failed")
            self.assertFalse(result["backend_approved"])
            self.assertFalse(result["production_use"])
            self.assertFalse(result["publication_eligible"])


if __name__ == "__main__":
    unittest.main()
