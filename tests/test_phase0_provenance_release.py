"""Phase 0 adversarial checks: prospective receipts and release suspension."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import phase0_policy
from phase0_preflight import audit
from point_in_time_provenance import pregame_snapshot_status
from market_odds_archive import normalize_quote
from test_point_in_time_provenance import verified_row
from test_verified_board import decision, receipt, NOW, DATE
from test_pick_verification import build as verification_fixture
from verified_board import build as board_build


def prospective_row(root):
    row = verified_row(root)
    row.update(
        run_id="prospective-1",
        event_id="fixture-123",
        player_id="12345",
        model_training_cutoff_at="2026-11-07T23:59:00Z",
    )
    row["market"]["books"] = [{
        "book": "ExampleBook", "line": 4.5,
        "retrieved_at": "2026-11-08T14:10:00Z",
    }]
    return row


class ProspectiveAttestationTests(unittest.TestCase):
    def test_clean_archived_pregame_forecast_certifies_even_before_settlement(self):
        with tempfile.TemporaryDirectory() as d:
            row = prospective_row(Path(d))
            for key in ("outcome", "actual_stat", "settled_at"):
                row.pop(key, None)
            ok, reason = pregame_snapshot_status(row, archive_root=Path(d))
            self.assertTrue(ok, reason)

    def test_missing_training_cutoff_and_future_fit_are_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            row = prospective_row(Path(d))
            row.pop("model_training_cutoff_at")
            self.assertIn("model_training_cutoff_at",
                          pregame_snapshot_status(row, archive_root=Path(d))[1])
            row = prospective_row(Path(d))
            row["model_training_cutoff_at"] = "2026-11-08T16:00:00Z"
            self.assertEqual(pregame_snapshot_status(row, archive_root=Path(d))[1],
                             "model_trained_after_forecast")

    def test_future_book_prices_and_original_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = prospective_row(root)
            row["market"]["books"][0]["retrieved_at"] = "2026-11-08T16:00:00Z"
            self.assertEqual(pregame_snapshot_status(row, archive_root=root)[1],
                             "post_forecast_book_quote")
            row = prospective_row(root)
            (root / "a.json").write_text("postgame data contamination")
            self.assertEqual(pregame_snapshot_status(row, archive_root=root)[1],
                             "source_archive_digest_mismatch")

    def test_missing_model_source_manifest_cannot_be_reconstructed(self):
        with tempfile.TemporaryDirectory() as d:
            row = prospective_row(Path(d))
            row.pop("source_receipts")
            self.assertEqual(pregame_snapshot_status(row, archive_root=Path(d))[1],
                             "source_manifest_missing")

    def test_batch_receipt_includes_source_digest_and_no_promotions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = prospective_row(root)
            path = root / "forecasts.jsonl"
            path.write_text(json.dumps(row) + "\n")
            report = audit(path, slate_date="2026-11-08", archive_root=root)
            self.assertEqual(report["certified_rows"], 1)
            self.assertEqual(report["uncertified_rows"], 0)
            self.assertFalse(report["publication_eligible"])
            self.assertFalse(report["tier1_tier2_publication_allowed"])
            self.assertEqual(len(report["original_forecast_bytes_sha256"]), 64)

            bad = copy.deepcopy(row)
            bad["source_receipts"] = []
            path.write_text(json.dumps(bad) + "\n")
            blocked = audit(path, slate_date="2026-11-08", archive_root=root)
            self.assertEqual(blocked["status"], "uncertified_research_only")
            self.assertEqual(blocked["uncertified_rows"], 1)

    def test_duplicate_contract_rows_cannot_be_certified(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = prospective_row(root)
            path = root / "dupes.jsonl"
            path.write_text((json.dumps(row) + "\n") * 2)
            report = audit(path, slate_date="2026-11-08", archive_root=root)
            self.assertEqual(report["certified_rows"], 0)
            self.assertEqual(report["uncertified_reasons"],
                             {"duplicate_original_contract_identity": 2})


class ReleaseGuardTests(unittest.TestCase):
    def test_production_high_confidence_blocked_not_recalibrated(self):
        with patch.dict(os.environ, {"PICKEM_PHASE0_RELEASE_GUARD": "1"}):
            for tier in ("Tier 1", "Tier 2"):
                gate = phase0_policy.authorize(tier)
                self.assertFalse(gate["publication_eligible"])
                self.assertFalse(gate["calibrated_tier_hit_rate_certified"])
            self.assertTrue(phase0_policy.authorize("Tier 3")["publication_eligible"])

    def test_verified_board_blocks_legacy_tier2_even_with_attested_source(self):
        rows, _, _ = verification_fixture()
        report = board_build(rows, [receipt(rows[0])], DATE,
                             now=NOW, phase0_enforced=True)
        self.assertEqual(report["verified_picks"], [])
        self.assertEqual(report["excluded"].get(
            "phase0_high_confidence_publication_suspended"), 1)

    def test_verification_cli_and_daily_workflow_enforce_phase0(self):
        verify = (ROOT / "scripts/pick_verification.py").read_text()
        board = (ROOT / "scripts/verified_board.py").read_text()
        workflow = (ROOT / ".github/workflows/pickem-daily.yml").read_text()
        self.assertIn('os.environ["PICKEM_PHASE0_RELEASE_GUARD"] = "1"', verify)
        self.assertIn("phase0_enforced=True", board)
        self.assertIn("step('phase0_pregame_provenance'", workflow)
        self.assertIn("reports/phase0_pregame_provenance.json", workflow)

    def test_no_free_odds_archive_api_call_and_sanitized_source(self):
        quote = {
            "sport": "NFL", "game_date": "2026-11-08",
            "event_id": "match", "event_start": "2026-11-08T18:00:00Z",
            "team": "BUF", "opponent": "MIA", "player": "Example Player",
            "stat": "receptions", "book": "FanDuel", "line": 4.5,
            "over_odds": -110, "under_odds": -110,
            "retrieved_at": "2026-11-08T14:00:00Z",
            "source_url": "https://api.example.com/v1?api_key=SECRET",
        }
        from datetime import datetime, timezone
        observed = datetime(2026, 11, 8, 15, 0, tzinfo=timezone.utc)
        record, reason = normalize_quote(quote, date_text="2026-11-08",
                                         observed=observed)
        self.assertEqual(reason, "accepted")
        self.assertNotIn("SECRET", json.dumps(record))
        self.assertEqual(record["archive_observed_at"], "2026-11-08T15:00:00Z")
        self.assertEqual(record["source_host"], "api.example.com")
        self.assertEqual(len(record["source_url_sha256"]), 64)
        self.assertIn("not_independently_verified", record["source_clock_semantics"])


if __name__ == "__main__":
    unittest.main()
