"""Outcome-blind Sunday NFL fixed market-logit shadow: adversarial tests."""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import nfl_sunday_prospective_shadow as shadow

DAY = "2026-11-15"
START = "2026-11-15T14:30:00Z"   # early Munich Sunday game, 9:30 ET
FORECAST = "2026-11-15T11:30:00Z"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
POLICY = "production-historical-ensemble-60-40-20261108-v1"


def sample():
    rows = []
    for side, consensus, market in (("over", .7, .6), ("under", .3, .4)):
        rows.append({
            "sport": "NFL", "team": "NE", "opponent": "DET",
            "player_id": "P1", "player": "Fixture Player",
            "stat": "targets", "line": 5.5, "side": side,
            "game_date": DAY, "event_start": START, "forecast_at": FORECAST,
            "run_id": "original-pregame-run-1", "Consensus": consensus,
            "Market": market,
            "models": {
                "Consensus": {
                    "status": "forecast",
                    "probability": consensus,
                    "version": POLICY,
                    "generated_at": FORECAST,
                },
                "Market": {
                    "status": "forecast", "probability": market,
                    "books": ["BetMGM", "DraftKings"],
                    "observed_at": "2026-11-15T11:20:00Z",
                    "version": "normalized-paired-American-odds-median-v1",
                },
            }
        })
    return {
        "metadata": {
            "comparison_schema": "slate-model-comparison-v1",
            "day": DAY, "production_policy_version": POLICY,
            "run_id": "original-pregame-run-1",
            "code_sha": "c" * 40, "snapshots_sha256": "a" * 64,
        }, "picks": rows
    }


class SundayResearchShadowTests(unittest.TestCase):
    def test_valid_matched_earliest_kickoff(self):
        result = shadow.build(sample(), day=DAY, now=NOW)
        self.assertEqual(result["original_nfl_side_rows"], 2)
        self.assertEqual(result["unique_contracts_in_scope"], 1)
        self.assertEqual(result["eligible_contracts"], 1)
        self.assertEqual(result["abstained_contracts"], 0)
        r = result["forecast_rows"][0]
        self.assertGreater(r["model_probabilities_conditional_no_push"]["fixed_50_50_logit"]["over"], .6)
        self.assertLess(r["model_probabilities_conditional_no_push"]["fixed_50_50_logit"]["over"], .7)
        self.assertAlmostEqual(sum(r["model_probabilities_conditional_no_push"]["fixed_50_50_logit"].values()), 1)
        self.assertFalse(result["no_production_modification"] is False)
        self.assertTrue(result["no_results_inspected"])
        self.assertEqual(r["release_authority"], "RESEARCH_ONLY_NEVER_TIERS")

    def test_after_kickoff_never_backfill_predictions(self):
        result = shadow.build(sample(), day=DAY, now="2026-11-15T14:31:00Z")
        self.assertEqual(result["eligible_contracts"], 0)
        self.assertEqual(result["rejection_counts"]["shadow_capture_not_pregame"], 1)

    def test_mismatched_output_timestamp_is_rejected(self):
        p = sample()
        p["picks"][1]["forecast_at"] = "2026-11-15T11:35:00Z"
        r = shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(r["eligible_contracts"], 0)
        self.assertEqual(r["rejection_counts"]["side_freeze_timestamp_mismatch"], 1)

    def test_noncomplementary_frozen_consensus_is_not_normalized(self):
        p = sample()
        p["picks"][1]["Consensus"] = .31
        p["picks"][1]["models"]["Consensus"]["probability"] = .31
        r = shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(r["eligible_contracts"], 0)
        self.assertEqual(r["rejection_counts"]["Consensus_pair_noncomplementary"], 1)

    def test_unavailable_market_fails_closed(self):
        p = sample()
        p["picks"][1]["Market"] = None
        p["picks"][1]["models"]["Market"]["status"] = "unavailable"
        p["picks"][1]["models"]["Market"]["probability"] = None
        r = shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(r["eligible_contracts"], 0)
        self.assertEqual(r["rejection_counts"]["Market_unavailable_or_invalid"], 1)

    def test_market_quote_not_before_original_freeze(self):
        p = sample()
        for row in p["picks"]:
            row["models"]["Market"]["observed_at"] = "2026-11-15T12:30:00Z"
        r = shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(r["rejection_counts"]["market_quote_after_frozen_forecast"], 1)

    def test_one_book_does_not_create_two_book_consensus(self):
        p = sample()
        for row in p["picks"]:
            row["models"]["Market"]["books"] = ["DraftKings"]
        r = shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(r["rejection_counts"]["insufficient_compatible_market_books"], 1)

    def test_no_legacy_60_40_mutation(self):
        p = sample()
        original = copy.deepcopy(p)
        shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(p, original)

    def test_missing_one_side_is_not_repriced(self):
        p = sample()
        p["picks"].pop()
        r = shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(r["rejection_counts"]["missing_complementary_side"], 1)

    def test_duplicate_side_cannot_inflate_contracts(self):
        p = sample()
        p["picks"].append(copy.deepcopy(p["picks"][0]))
        r = shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(r["rejection_counts"]["duplicate_contract_side"], 1)
        # One identical duplicate is explicitly counted, not scored twice.
        self.assertEqual(r["eligible_contracts"], 1)
        self.assertEqual(r["original_nfl_side_rows"], 3)

    def test_no_touchdown_projections(self):
        p = sample()
        for row in p["picks"]: row["stat"] = "rushing touchdowns"
        r = shadow.build(p, day=DAY, now=NOW)
        self.assertEqual(r["eligible_contracts"], 0)
        self.assertEqual(r["rejection_counts"]["excluded_nonvolume_market"], 2)

    def test_wrong_policy_rejects_whole_source(self):
        p = sample()
        p["metadata"]["production_policy_version"] = "unknown"
        with self.assertRaisesRegex(ValueError, "wrong_frozen_day_or_policy"):
            shadow.build(p, day=DAY, now=NOW)

    def test_append_only_receipts_and_sha(self):
        r = shadow.build(sample(), day=DAY, now=NOW)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "freeze.json"
            receipt = shadow.freeze(r, path, "f" * 64)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), receipt["sha256"])
            disk = json.loads(path.read_text())
            self.assertEqual(disk["input_comparison_sha256"], "f" * 64)
            self.assertEqual(disk["eligible_contracts"], 1)
            with self.assertRaisesRegex(FileExistsError, "append_only"):
                shadow.freeze(r, path, "f" * 64)


if __name__ == "__main__":
    unittest.main()
