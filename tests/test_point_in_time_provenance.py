"""Adversarial source timing and immutable archive tests for model promotion."""
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import point_in_time_provenance as pit


def verified_row(root):
    fragments = {"a": b"as-of game stats", "b": b"pregame availability", "m": b"original market quotes"}
    for ident, content in fragments.items():
        (root / (ident + ".json")).write_bytes(content)
    receipts = []
    for ident, component in (("a", "Engine_A"), ("b", "Engine_B"), ("m", "Market")):
        receipts.append({
            "source_id": ident,
            "source_url": "https://example.org/immutable/" + ident,
            "archive_path": ident + ".json",
            "content_sha256": hashlib.sha256(fragments[ident]).hexdigest(),
            "status": "verified",
            "model_component": component,
            "observed_at": "2026-11-08T13:00:00+00:00",
            "published_at": "2026-11-08T13:05:00+00:00",
            "retrieved_at": "2026-11-08T14:00:00+00:00",
        })
    return {
        "sport": "NFL", "game_date": "2026-11-08",
        "matchup": "KC @ BUF", "player": "Example Defender",
        "stat": "tackles + assists", "side": "over", "reference_line": 4.5,
        "outcome": "win", "actual_stat": 6, "status": "GRADED",
        "forecast_at": "2026-11-08T15:00:00+00:00",
        "event_start": "2026-11-08T18:00:00+00:00",
        "settled_at": "2026-11-08T22:00:00+00:00",
        "engine_b": {"abstain": False},
        "market": {"q_market": 0.48, "line": 4.5, "retrieved_at": "2026-11-08T14:15:00Z"},
        "source_receipts": receipts,
        "used_source_ids": ["a", "b", "m"],
    }


class PointInTimeProvenanceTests(unittest.TestCase):
    def check_block(self, row, root, reason):
        ok, message = pit.blend_snapshot_status(row, archive_root=root)
        self.assertFalse(ok)
        self.assertIn(reason, message)

    def test_verifies_archived_pregame_contract(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            self.assertEqual(
                pit.blend_snapshot_status(row, archive_root=root),
                (True, "verified_metadata_and_archived_source_receipts"))

    def test_late_market_quote_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            row["market"]["retrieved_at"] = "2026-11-08T16:00:00Z"
            self.check_block(row, root, "post_forecast_market_quote")

    def test_future_lineup_source_rejected_even_if_archived(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            row["source_receipts"][1]["published_at"] = "2026-11-08T16:00:00Z"
            self.check_block(row, root, "source_after_forecast_or_inconsistent_timeline")

    def test_source_bytes_must_match_digest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            (root / "b.json").write_bytes(b"changed after prediction")
            self.check_block(row, root, "source_archive_digest_mismatch")

    def test_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            row["source_receipts"][0]["archive_path"] = "../a.json"
            self.check_block(row, root, "source_archive_path_unsafe")

    def test_missing_component_and_undeclared_source_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            row["source_receipts"][1]["model_component"] = "Market"
            self.check_block(row, root, "missing_engine_or_market_source_receipt")
            row = verified_row(root)
            row["used_source_ids"].pop()
            self.check_block(row, root, "incomplete_or_unused_source_manifest")

    def test_historical_or_postgame_actual_cannot_override_frozen_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            row["actual_stat"] = 2
            self.check_block(row, root, "actual_outcome_mismatch")
            row = verified_row(root)
            row["forecast_at"] = "2026-11-08T23:00:00Z"
            self.check_block(row, root, "poststart_forecast_or_early_settlement")

    def test_naive_source_or_wrong_date_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            row["source_receipts"][0]["retrieved_at"] = "2026-11-08T14:00:00"
            self.check_block(row, root, "naive_timestamp")
            row = verified_row(root)
            row["game_date"] = "2026-11-09"
            self.check_block(row, root, "event_game_date_mismatch")

    def test_missing_frozen_source_files_never_certifies(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = verified_row(root)
            (root / "m.json").unlink()
            self.check_block(row, root, "source_archive_file_unavailable")
            self.check_block(row, None, "source_archive_root_missing")


if __name__ == "__main__":
    unittest.main()
