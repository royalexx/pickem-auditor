"""Offline integrity and replay tests for durable precision frozen-state cache."""
import hashlib
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from precision_frozen_cache import archive_is_verified, history_paths, restore_history, sha256, snapshot, write_json

SHA = "a" * 40
STATES = ("nhl.json", "nhl_recent.json", "nba.json", "nba_recent.json", "nfl.json")


class FreezeCacheTests(unittest.TestCase):
    def make_archive(self, cache, source=SHA):
        archive, manifest = history_paths(cache, source)
        archive.parent.mkdir(parents=True)
        with tempfile.TemporaryDirectory() as td:
            stage = Path(td)
            for name in STATES:
                file = stage / "data" / "bayesian_warehouse" / "states" / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(json.dumps({"schema": "multi-sport-population-cursor-v1",
                                            "cursor": 1}), encoding="utf-8")
            with tarfile.open(archive, "w") as stream:
                stream.add(stage / "data" / "bayesian_warehouse",
                           arcname="data/bayesian_warehouse")
        write_json(manifest, {"schema": "precision_history_cache_v1",
                              "source_sha": source, "size": archive.stat().st_size,
                              "sha256": sha256(archive)})
        return archive

    def test_verified_cache_restores_all_sports_without_git(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cache, root = base / "cache", base / "checkout"
            root.mkdir()
            self.make_archive(cache)
            self.assertEqual(archive_is_verified(cache, SHA), (True, "verified"))
            with patch.dict("os.environ", {"GITHUB_ENV": str(base / "env")}, clear=False):
                self.assertEqual(restore_history(root, cache, SHA), 0)
            for name in STATES:
                self.assertTrue((root / "data" / "bayesian_warehouse" / "states" / name).exists())
            self.assertIn("SOURCE_HEAD=" + SHA, (base / "env").read_text())

    def test_corrupted_archive_is_not_reused(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            archive = self.make_archive(base / "cache")
            with archive.open("ab") as out:
                out.write(b"tampered")
            self.assertEqual(archive_is_verified(base / "cache", SHA)[0], False)
            self.assertEqual(restore_history(base, base / "cache", SHA), 3)

    def test_missing_cache_falls_back_to_source_loader(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self.assertEqual(restore_history(base, base / "cache", SHA), 3)


    def test_skipped_market_can_replay_frozen_receipts_and_source(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            cache, root = base / "cache", base / "checkout"
            root.mkdir()
            self.make_archive(cache)
            runid = "41571885953"
            reports = root / "reports" / "precision_training" / runid
            reports.mkdir(parents=True)
            (reports / "freeze_receipt.json").write_text(
                '{"schema":"precision_campaign_freeze_v1"}\n', encoding="utf-8")
            (reports / "nhl-shots-on-goal").mkdir()
            (reports / "nhl-shots-on-goal" / "progress.json").write_text(
                '{"percent":70,"stage":"sampling"}\n', encoding="utf-8")
            env = {
                "GITHUB_RUN_ID": runid, "INDEX": "0",
                "CAMPAIGN_ID": "week-20261102", "CODE_HEAD": SHA,
                "SOURCE_FREEZE_SHA": SHA, "CUTOFF": "2026-10-29",
                "SPORT": "NHL", "STAT": "shots on goal",
                "VALIDATE_RESULT": "success", "FIT_RESULT": "failure",
            }
            with patch.dict("os.environ", env, clear=False):
                state = snapshot(root, cache, "final")
            self.assertEqual(state["resume_mode"], "restart_market_from_frozen_inputs")
            self.assertFalse(state["nuts_iteration_checkpoint"])
            self.assertEqual(state["fit_outcome"], "failure")
            self.assertTrue(Path(state["local_state_file"]).exists())
            self.assertIn("nhl-shots-on-goal/progress.json", state["output_inventory"])
            self.assertNotIn("freeze_cache.json", state["output_inventory"])
            restored = json.loads((reports / "freeze_cache.json").read_text())
            self.assertEqual(restored["history_archive_sha256"],
                             sha256(cache / "history" / (SHA + ".tar")))



if __name__ == "__main__":
    unittest.main()
