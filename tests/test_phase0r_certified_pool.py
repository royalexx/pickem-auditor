"""Live Phase 0R candidate gate: no unverifiable row enters the forecast pool."""
from __future__ import annotations
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import jobs
from test_phase0r_pre_eval import make_inputs

WHEN = datetime(2026, 11, 9, 14, 15, tzinfo=timezone.utc)


def prepared(root):
    data = root / "collected"
    candidate, _ = make_inputs(data)
    candidate["books"][0]["book"] = "Pinnacle"
    original = {"book": "Pinnacle", "line": 4.5, "over_odds": -110,
                "under_odds": -110, "retrieved_at": "2026-11-09T14:10:00Z",
                "event_id": "event-1"}
    (data / "odds_quotes.jsonl").write_text(json.dumps(original) + "\n")
    candidate["_phase0_market_quotes"] = [original]
    candidate["_run_id"] = "live-certification-test"
    candidate["_run_at"] = "2026-11-09 09:15 ET"
    candidate["_meta"] = {
        "sport": "NFL", "stat": "receptions", "player_id": "pid-1",
        "player": "Example Player", "game_date": "2026-11-09",
        "event_id": "event-1", "team": "BUF", "opponent": "KC",
        "matchup": "KC @ BUF", "event_start": "2026-11-09T18:00:00Z",
    }
    return data, candidate


def mock_model(candidate, *, now):
    return {"ok": True, "id": candidate["id"], "final_rank": "Unranked",
            "engine_a": {"reliable": True}, "engine_b": {"abstain": True},
            "consensus": {"market_valid": True, "line": candidate["line"]},
            "market": {"q_market": .5}, "blend": {}}


class LiveCertifiedOnlyPoolTests(unittest.TestCase):
    def run_live(self, data, rows):
        receipts = []
        with patch.dict(os.environ, {"PICKEM_PRODUCTION_CONSENSUS": "1"}), (
            patch.object(jobs.pm, "evaluate_candidate", side_effect=mock_model)
        ) as evaluated:
            snapshots, errors = jobs.run_pipeline_batch(
                rows, now=WHEN, clock_fn=lambda: WHEN,
                data_root=data, attempt_receipts=receipts)
        return snapshots, errors, receipts, evaluated.call_count

    def test_valid_source_enters_strict_certified_pool(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, row = prepared(Path(tmp))
            snapshots, errors, ledger, calls = self.run_live(data, [row])
            self.assertEqual((errors, calls, len(snapshots)), (0, 1, 1))
            self.assertTrue(snapshots[0]["phase0r_original_source_certified"])
            self.assertEqual(ledger[0]["status"], "forecast")
            from phase0r_contract import strict_snapshot_status
            self.assertTrue(strict_snapshot_status(
                snapshots[0], archive_root=data / "source_archives")[0])

    def test_unpinned_event_context_is_excluded_before_model_not_silently_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, row = prepared(Path(tmp))
            row["event_context"] = {"subject_status": {"value": "questionable"}}
            rows, errors, ledger, calls = self.run_live(data, [row])
            self.assertEqual((rows, errors, calls), ([], 0, 0))
            self.assertEqual(ledger[0]["status"], "unavailable")
            self.assertEqual(ledger[0]["reason"], "pre_eval_external_context_unpinned")
            self.assertIn("event_context", row)

    def test_missing_original_quote_is_excluded_before_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, row = prepared(Path(tmp))
            row["_phase0_market_quotes"] = []
            rows, errors, ledger, calls = self.run_live(data, [row])
            self.assertEqual((rows, errors, calls), ([], 0, 0))
            self.assertEqual(ledger[0]["reason"], "market_unavailable_or_unverified")

    def test_unapproved_or_stale_market_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, row = prepared(Path(tmp))
            row["books"][0]["book"] = "UnknownShop"
            rows, errors, ledger, calls = self.run_live(data, [row])
            self.assertEqual((rows, errors, calls), ([], 0, 0))
            self.assertEqual(ledger[0]["reason"], "market_unavailable_or_unverified")
            data, row = prepared(Path(tmp) / "separate_stale_case")
            row["market_retrieved_at"] = "2026-11-09T13:00:00Z"
            rows, errors, ledger, calls = self.run_live(data, [row])
            self.assertEqual((rows, errors, calls), ([], 0, 0))
            self.assertEqual(ledger[0]["reason"], "market_unavailable_or_unverified")

    def test_quote_cannot_be_matched_to_different_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, row = prepared(Path(tmp))
            row["_phase0_market_quotes"][0]["event_id"] = "other-event"
            rows, errors, ledger, calls = self.run_live(data, [row])
            self.assertEqual((rows, errors, calls), ([], 0, 0))
            self.assertEqual(ledger[0]["reason"], "market_unavailable_or_unverified")

    def test_missing_source_file_cannot_fallback_to_uncertified_shadow(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, row = prepared(Path(tmp))
            for path in (data / "usage").glob("*.json"):
                path.unlink()
            rows, errors, ledger, calls = self.run_live(data, [row])
            self.assertEqual((rows, errors), ([], 0))
            self.assertEqual(calls, 0)
            self.assertIn("phase0r_source_capture_failed:", ledger[0]["reason"])
            self.assertEqual(ledger[0]["status"], "unavailable")

    def test_historical_legacy_run_not_retroactively_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, row = prepared(Path(tmp))
            row["event_context"] = {"events": [{"player_id": "X"}]}
            with patch.dict(os.environ, {
                "PICKEM_PRODUCTION_CONSENSUS": "0",
                "PICKEM_PHASE0_CERTIFIED_ONLY": "0",
                "PICKEM_PHASE0_CAPTURE": "0"
            }), patch.object(jobs.pm, "evaluate_candidate", side_effect=mock_model) as model:
                rows, errors = jobs.run_pipeline_batch([row], now=WHEN,
                                                        clock_fn=lambda: WHEN, data_root=data)
            self.assertEqual((len(rows), errors, model.call_count), (1, 0, 1))
            self.assertIsNone(rows[0].get("phase0r_original_source_certified"))


if __name__ == "__main__":
    unittest.main()
