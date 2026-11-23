"""Regressions for all-skater source coverage and independent quote failures."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from research.p2_nhl_sog import history_bridge, slate


class SlateSourceTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime.now(timezone.utc) + timedelta(hours=1)
        self.freeze = (self.start - timedelta(minutes=20)).isoformat()
        self.game = {"event_id": "2026020300", "start_at": self.start.isoformat(),
                     "scheduled_day": self.start.date().isoformat(),
                     "away_team": "BOS", "home_team": "TOR", "game_state": "FUT"}
        self.members = {"TOR": {
            "1000": {"team_id": "TOR", "position_group": "F"},
            "1001": {"team_id": "TOR", "position_group": "G"},
        }, "BOS": {"1002": {"team_id": "BOS", "position_group": "D"}}}
        self.kwargs = {"game": self.game, "freeze": self.freeze,
                       "signed_history_manifest_path": "history.json",
                       "signed_history_manifest_sha256": "a" * 64,
                       "history_pool": "/work/history"}
        for name, kwargs in (
            ("current_storage", {}),
            ("signed_schedule_game", {"return_value": {"key": "schedule"}}),
            ("capture_two_rosters", {"return_value": ({"key": "rosters"}, self.members)}),
            ("checked_pool", {"return_value": "/work/history"}),
            ("attempt", {"return_value": {"receipt": {"sha256": "b" * 64}}}),
        ):
            patcher = patch.object(slate, name, **kwargs)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def test_quote_rejection_preserves_distribution_and_missing_skater(self):
        self.kwargs["original_quote_by_player"] = {"1000": {"source": {}, "offer": {}}}
        with (patch.object(slate, "load_signed_manifest", return_value={"1000": []}),
              patch.object(slate, "_eligible_history", return_value=("F", [{}])),
              patch.object(slate, "build_bundle", return_value={
                  "manifest": {"source_admission": "SOURCE_READY_LINE_INDEPENDENT_ONLY"},
                  "receipt": {"sha256": "c" * 64}}) as bundle,
              patch.object(slate, "record_quote_candidate", return_value={
                  "status": "REJECTED", "attempt": {"reasons": ["NO_AUTHENTIC_OFFER"]}})):
            result = slate.capture_game_sources("/work", **self.kwargs)

        self.assertEqual(result["status"], "SOURCE_READY")
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual([row["player_id"] for row in result["records"]], ["1000", "1002"])
        frozen, missing = result["records"]
        self.assertEqual(frozen["manifest_sha256"], "c" * 64)
        self.assertEqual(frozen["quote_reasons"], ["NO_AUTHENTIC_OFFER"])
        self.assertIsNone(frozen["quote_manifest_sha256"])
        self.assertEqual(missing["reasons"], ["P2_ORIGINAL_SIGNED_PLAYER_HISTORY_MISSING"])
        self.assertTrue(bundle.call_args.kwargs["include_official_c03_receipts"])

    def test_missing_history_archive_reports_all_roster_skaters(self):
        with patch.object(slate, "load_signed_manifest", side_effect=FileNotFoundError):
            result = slate.capture_game_sources("/work", **self.kwargs)

        self.assertEqual(result["status"], "BLOCKED_SOURCE")
        self.assertEqual(result["status_counts"], {"ABSTAIN_SOURCE_INVALID": 2})
        self.assertTrue(all(row["reasons"] == ["FileNotFoundError"] for row in result["records"]))

    def test_closed_freeze_skips_capture(self):
        self.kwargs["freeze"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        result = slate.capture_game_sources("/work", **self.kwargs)

        self.assertEqual(result["status"], "MISSED_SOURCE_FREEZE_DEADLINE")
        self.signed_schedule_game.assert_not_called()
        self.capture_two_rosters.assert_not_called()


class HistoryBundleTests(unittest.TestCase):
    def test_verified_zip_recovers_from_interrupted_write_without_replacing_bytes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pool = root / "original"
            manifests = pool / "daily_history_manifests"
            manifests.mkdir(parents=True)
            bundles = pool / "history_bundles"
            bundles.mkdir()
            archive = bundles / "initial.zip"
            with zipfile.ZipFile(archive, "w") as source:
                source.writestr("raw_http_body/original.json", b'{"frozen":true}')
            archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            archive = archive.rename(bundles / f"{archive_sha}.zip")
            manifest = manifests / "original.json"
            manifest.write_text(json.dumps({
                "signed_observation_contracts_by_player": {},
                "source_bundle": {
                    "format": "exact_original_receipts_and_derived_zip_v1",
                    "path": f"history_bundles/{archive_sha}.zip", "sha256": archive_sha,
                },
            }))
            manifest_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
            args = root, str(manifest.relative_to(root)), manifest_sha, pool
            first_cache = (root / history_bridge.ROOT_NAMESPACE / "verified_history_bundles" /
                           archive_sha / "raw_http_body" / "original.json")
            first_cache.parent.mkdir(parents=True)
            first_cache.write_bytes(b"partial")
            with patch.object(history_bridge, "current_storage"):
                restored = history_bridge.open_history_sources(*args)
                self.assertEqual((restored / "raw_http_body/original.json").read_bytes(),
                                 b'{"frozen":true}')
                self.assertEqual(first_cache.read_bytes(), b"partial")
                self.assertEqual(restored.parent.name, "verified_history_recovery")
                self.assertEqual(history_bridge.open_history_sources(*args), restored)
                archive.write_bytes(b"altered original archive")
                with self.assertRaisesRegex(ValueError, "P2_SIGNED_HISTORY_BUNDLE_SHA_MISMATCH"):
                    history_bridge.open_history_sources(*args)


if __name__ == "__main__":
    unittest.main()
