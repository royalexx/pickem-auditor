"""Adversarial tests for genuinely pre-freeze collector input receipts."""
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

from phase0_input_capture import capture, preserve, source_url
from point_in_time_provenance import pregame_snapshot_status
from usage_baseline import key as usage_key


class LiveCaptureTests(unittest.TestCase):
    def setup_inputs(self, root):
        data = root / "data"
        usage = data / "usage"
        usage.mkdir(parents=True)
        candidate = {
            "sport": "NFL", "player_id": "pid-1", "stat": "receptions",
            "game_date": "2026-11-09", "team": "BUF",
            "line": 4.5, "side": "over",
            "books": [
                {"book": "Pinnacle", "line": 4.5, "over": -110,
                 "under": -110, "retrieved_at": "2026-11-09T14:10:00Z"}
            ],
            "scouting": {"role": "starter"},
        }
        ident = usage_key("NFL", "pid-1", "receptions", "2026-11-09")
        (usage / (ident + ".json")).write_text(json.dumps({
            "sport": "NFL", "player_id": "pid-1", "stat": "receptions",
            "retrieved_at": "2026-11-09T14:00:00Z",
            "source_url": "https://example.org/roster",
            "observations": [{"id": "g-1", "date": "2026-11-02", "value": 5}],
        }))
        (data / "odds_quotes.jsonl").write_text(
            '{"book":"Pinnacle","line":4.5,"retrieved_at":"2026-11-09T14:10:00Z"}\n'
        )
        (data / "research_2026-11-09.json").write_text(
            '{"date":"2026-11-09","source_status":"pre_game"}'
        )
        return data, candidate

    def test_capture_certifies_original_archived_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, candidate = self.setup_inputs(Path(tmp))
            when = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
            result = {"engine_b": {"abstain": False},
                      "market": {"market_valid": True,
                                 "line": 4.5, "retrieved_at": "2026-11-09T14:10:00Z"}}
            evidence = capture(candidate, result, data_root=data,
                               archive_root=data / "source_archives", clock=lambda: when)
            self.assertEqual(len(evidence["source_receipts"]), 6)
            self.assertEqual(evidence["model_training_cutoff_at"],
                             "2026-11-09T15:00:00Z")
            self.assertTrue(all(
                (data / "source_archives" / x["archive_path"]).is_file()
                for x in evidence["source_receipts"]))
            self.assertFalse(any("secretvalue" in json.dumps(x)
                                 for x in evidence["source_receipts"]))
            row = {**evidence, "forecast_at": "2026-11-09T15:01:00Z",
                   "event_start": "2026-11-09T18:00:00Z", "game_date": "2026-11-09",
                   "run_id": "id-1", "sport": "NFL", "event_id": "evt-1",
                   "player_id": "pid-1", "stat": "receptions",
                   "side": "over", "reference_line": 4.5,
                   "engine_b": result["engine_b"],
                   "market": {**result["market"], "books": candidate["books"]}}
            self.assertTrue(pregame_snapshot_status(
                row, archive_root=data / "source_archives")[0])
            target = data / "source_archives" / evidence["source_receipts"][0]["archive_path"]
            target.write_text("tampered")
            self.assertEqual(pregame_snapshot_status(
                row, archive_root=data / "source_archives")[1],
                "source_archive_digest_mismatch")

    def test_nba_candidate_with_no_sport_uses_verified_slate_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, candidate = self.setup_inputs(Path(tmp))
            candidate.pop("sport")
            candidate["id"] = "NFL|Example|receptions|over"
            result = {"engine_b": {"abstain": True},
                      "market": {"market_valid": True, "line": 4.5}}
            when = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
            evidence = capture(candidate, result, data_root=data,
                               archive_root=data / "source_archives",
                               clock=lambda: when,
                               identity={"sport": "NFL", "player_id": "pid-1",
                                         "stat": "receptions", "game_date": "2026-11-09"})
            self.assertGreater(len(evidence["source_receipts"]), 2)
            with self.assertRaisesRegex(ValueError, "identity_mismatch"):
                capture(candidate, result, data_root=data,
                        archive_root=data / "source_archives",
                        clock=lambda: when,
                        identity={"sport": "NHL", "player_id": "pid-1",
                                  "stat": "receptions", "game_date": "2026-11-09"})

    def test_large_original_research_is_content_addressed_and_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, candidate = self.setup_inputs(Path(tmp))
            path = data / "research_2026-11-09.json"
            path.write_text(json.dumps({"date": "2026-11-09", "payload": "x" * 12_100_000}))
            when = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
            result = {"engine_b": {"abstain": False},
                      "market": {"market_valid": True, "line": 4.5}}
            first = capture(candidate, result, data_root=data,
                            archive_root=data / "source_archives", clock=lambda: when)
            second = capture(candidate, result, data_root=data,
                             archive_root=data / "source_archives", clock=lambda: when)
            original = next(x for x in first["source_receipts"]
                            if x["source_id"].startswith("Engine_B_original_research_"))
            original_again = next(x for x in second["source_receipts"]
                                  if x["source_id"].startswith("Engine_B_original_research_"))
            self.assertEqual(original, original_again)
            self.assertEqual((data / "source_archives" / original["archive_path"]).stat().st_size,
                             path.stat().st_size)

    def test_reject_future_usage_and_missing_original_market(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, candidate = self.setup_inputs(Path(tmp))
            when = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)
            result = {"engine_b": {"abstain": True}, "market": {}}
            (data / "odds_quotes.jsonl").unlink()
            with self.assertRaises(FileNotFoundError):
                capture(candidate, result, data_root=data,
                        archive_root=data / "source_archives", clock=lambda: when)

    def test_secrets_and_non_https_source_url(self):
        self.assertEqual(source_url("https://example.org/a?q=SECRET"), "https://example.org/a")
        self.assertIsNone(source_url("http://example.org/a"))
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"PROPLINE_API_KEY": "should-not-publish"}):
                stamp = datetime.now(timezone.utc)
                with self.assertRaisesRegex(ValueError, "contains_secret"):
                    preserve(Path(tmp), "Market", "raw", b"should-not-publish",
                             captured=stamp, retrieved=stamp)


if __name__ == "__main__":
    unittest.main()
