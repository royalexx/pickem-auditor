"""Isolated P2 tests against live NHL code and frozen P0 stat registry.

No global /work/v2 patching, production module changes, or model execution.
The P0 integration branch's original registry is discoverable only in this
test Python process; actual release must merge P0 before promotion.
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import v2
P0 = ROOT / "research/p0_integration_integrity/p0_source_checkout_20261121/v2"
assert (P0 / "stat_registry.py").is_file(), "P0_ISOLATED_STAT_REGISTRY_MISSING"
v2.__path__.append(str(P0))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(ROOT / "research/p2_nhl_sog"),
        pattern="test_p2_nhl_source_pipeline.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("P2_TEST_SUMMARY", {
        "testsRun": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "successful": result.wasSuccessful(),
        "source_schema": "PA-P2-NHL-SOG-SOURCE-BUNDLE/1",
        "p0_schema": "PA-P0/1"
    })
    sys.exit(0 if result.wasSuccessful() else 1)
