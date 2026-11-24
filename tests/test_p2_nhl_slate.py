"""Regressions for all-skater source coverage and independent quote failures."""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import os
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch
import zipfile

from research.p2_nhl_sog import history_bridge, slate, source_pipeline
from scripts import c03_context_cohorts as c03
from scripts.c03_context_cohorts import archive_response, canonical
from scripts.c03_live_transport import SCHEMA, SECRET_ENV, _mac, _signed_body


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

    def test_poisson_lane_prepares_own_history_and_streams_committed_rows_only(self):
        streamed = []

        def collect(row):
            self.assertEqual(self.attempt.call_args.args[1], "full_slate_player_sources")
            self.assertEqual(row["attempt_sha256"], "b" * 64)
            streamed.append(row)

        with (patch.object(slate, "load_signed_manifest", return_value={"1000": [], "9000": []}),
              patch.object(slate, "_eligible_history", return_value=("F", [{}])) as index,
              patch.object(slate, "_peer_ids") as peers,
              patch.object(slate, "build_bundle", return_value={
                  "manifest": {"source_admission": "SOURCE_READY_LINE_INDEPENDENT_ONLY"},
                  "receipt": {"sha256": "c" * 64}}) as bundle):
            result = slate.capture_game_sources("/work", **self.kwargs,
                                                poisson_only=True, on_bundle=collect)

        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual([row["player_id"] for row in streamed], ["1000"])
        self.assertEqual(index.call_args.kwargs["player_id"], "1000")
        index.assert_called_once()
        peers.assert_not_called()
        self.assertEqual(bundle.call_args.kwargs["peer_entries"], {})

    def test_closed_freeze_skips_capture(self):
        self.kwargs["freeze"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        result = slate.capture_game_sources("/work", **self.kwargs)

        self.assertEqual(result["status"], "MISSED_SOURCE_FREEZE_DEADLINE")
        self.signed_schedule_game.assert_not_called()
        self.capture_two_rosters.assert_not_called()


class SharedScheduleTests(unittest.TestCase):
    def test_simultaneous_games_share_one_scoreboard_but_verify_each_event(self):
        start = datetime.now(timezone.utc) + timedelta(minutes=24)
        freeze = (start - timedelta(minutes=20)).isoformat()
        day = "2026-11-23"
        games = [
            {"event_id": str(2026020379+i), "start_at": source_pipeline.stamp(start),
             "away_team": "LAK", "home_team": "MTL"}
            for i in range(4)
        ]
        scoreboard = {"document": {"games": [
            {"id": int(game["event_id"]), "startTimeUTC": game["start_at"],
             "gameState": "FUT", "awayTeam": {"abbrev": "LAK"},
             "homeTeam": {"abbrev": "MTL"}} for game in games
        ]}, "p0_sha256": "a"*64}
        fetch = source_pipeline.SlateScheduleCapture()
        barrier = Barrier(len(games), timeout=5)

        def capture(game):
            barrier.wait()
            return source_pipeline.signed_schedule_game("/work", game, day=day,
                                                       freeze=freeze, fetch=fetch)

        with (patch.object(source_pipeline, "capture_official", return_value=scoreboard) as http,
              patch.object(source_pipeline, "put_once") as save,
              ThreadPoolExecutor(max_workers=4) as workers):
            self.assertEqual(list(workers.map(capture, games)), [scoreboard]*4)
            http.assert_called_once()
            self.assertEqual(save.call_count, 4)
            with self.assertRaisesRegex(source_pipeline.SourceBlocked, "SIGNED_OFFICIAL_EVENT_NOT_UNIQUE"):
                source_pipeline.signed_schedule_game(
                    "/work", dict(games[0], event_id="999"), day=day, freeze=freeze, fetch=fetch)

    def test_capture_failure_can_retry_and_final_window_gets_a_fresh_capture(self):
        fetch = source_pipeline.SlateScheduleCapture()
        start = datetime.now(timezone.utc) + timedelta(hours=1)
        options = {"event_start_at": start.isoformat(),
                   "input_freeze_at": (start - timedelta(minutes=20)).isoformat()}
        url = source_pipeline.OFFICIAL + "/score/2026-11-23"
        with (patch.object(source_pipeline, "capture_window", return_value="EARLY") as window,
              patch.object(source_pipeline, "capture_official",
                           side_effect=[OSError("first capture failed"), "early", "final"]) as http):
            with self.assertRaises(OSError):
                fetch("/work", url, **options)
            self.assertEqual(fetch("/work", url, **options), "early")
            self.assertEqual(fetch("/work", url, **options), "early")
            window.return_value = "FINAL"
            self.assertEqual(fetch("/work", url, **options), "final")
            self.assertEqual(http.call_count, 3)


class C03ArchiveRaceTests(unittest.TestCase):
    def test_existing_partial_write_is_rechecked_until_complete(self):
        raw = b'{"games":[]}'
        with TemporaryDirectory() as root:
            path = Path(root)/"raw_http_body"/(hashlib.sha256(raw).hexdigest()+".bin")
            path.parent.mkdir()
            now = datetime.now(timezone.utc).isoformat()
            with path.open("xb") as writer:
                writer.write(raw[:5])
                writer.flush()

                def finish_write(delay):
                    writer.write(raw[5:])
                    writer.flush()

                with patch.object(c03, "sleep", side_effect=finish_write) as wait:
                    receipt = archive_response(
                        raw, archive_root=root, source_url="https://api-web.nhle.com/v1/score/2026-11-23",
                        observed_at=now, received_at=now, source_id="nhl:schedule:2026-11-23",
                        source_namespace="nhl_official", http_status=200)
                wait.assert_called_once()
            self.assertEqual(receipt["body_sha256"], path.stem)
            self.assertEqual(path.read_bytes(), raw)

    def test_corrupt_and_abandoned_writes_are_rejected_without_overwrite(self):
        with TemporaryDirectory() as root:
            path = Path(root)/"body.bin"
            for stored, clock in ((b"wrong", [0, 0]), (b"exp", [0, 5])):
                with self.subTest(stored=stored):
                    path.write_bytes(stored)
                    with (patch.object(c03, "monotonic", side_effect=clock),
                          patch.object(c03, "sleep") as wait,
                          self.assertRaisesRegex(c03.CohortError, "RAW_ARCHIVE_MUTATED")):
                        c03.write_archive_bytes(path, b"expected", mismatch="RAW_ARCHIVE_MUTATED")
                    wait.assert_not_called()
                    self.assertEqual(path.read_bytes(), stored)


class HistoryBundleTests(unittest.TestCase):
    def test_split_cache_preserves_raw_and_proof_only_on_persistent_root(self):
        with TemporaryDirectory() as project, TemporaryDirectory() as derived:
            root = Path(project)
            cache = Path(derived)
            pool = root / "source"
            manifests = pool / "daily_history_manifests"
            manifests.mkdir(parents=True)
            bundles = pool / "history_bundles"
            bundles.mkdir()
            paths = {
                "raw_http_body/body.json": b'{"official":true}',
                "c03_collector_receipts/proof.json": b'{"proof":true}',
                "nhl_sog_official_derived/observation.json": b'{"derived":true}',
            }
            archive = bundles / "initial.zip"
            with zipfile.ZipFile(archive, "w") as source:
                for path, raw in paths.items():
                    source.writestr(path, raw)
            archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            archive.rename(bundles / f"{archive_sha}.zip")
            manifest = manifests / "original.json"
            manifest.write_text(json.dumps({
                "signed_observation_contracts_by_player": {},
                "source_bundle": {
                    "format": "exact_original_receipts_and_derived_zip_v1",
                    "path": f"history_bundles/{archive_sha}.zip", "sha256": archive_sha,
                },
            }))
            args = root, str(manifest.relative_to(root)), hashlib.sha256(manifest.read_bytes()).hexdigest(), pool
            with patch.object(history_bridge, "current_storage"):
                raw_pool = history_bridge.open_history_sources(*args, derived_cache=cache)
                self.assertEqual((raw_pool / "raw_http_body/body.json").read_bytes(), paths["raw_http_body/body.json"])
                self.assertTrue((raw_pool / "c03_collector_receipts/proof.json").is_file())
                self.assertTrue((raw_pool / "_verified_raw_archive.json.complete").is_file())
                observation = "nhl_sog_official_derived/observation.json"
                self.assertFalse((raw_pool / observation).exists())
                self.assertEqual((cache / observation).read_bytes(), paths[observation])
                self.assertEqual(history_bridge.open_history_sources(*args, derived_cache=cache), raw_pool)

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

    def test_subset_restores_requested_roster_and_position_peer_reserve(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pool = root / "original"
            manifests = pool / "daily_history_manifests"
            manifests.mkdir(parents=True)
            bundles = pool / "history_bundles"
            bundles.mkdir()
            archive = bundles / "initial.zip"
            players = {}
            with zipfile.ZipFile(archive, "w") as source:
                for number in range(1000, 1033):
                    player_id = str(number)
                    path = f"nhl_sog_official_derived/{player_id}.json"
                    raw = json.dumps({"player_id": player_id, "position_group": "F"}).encode()
                    receipt = {"archive_path": path, "content_sha256": hashlib.sha256(raw).hexdigest()}
                    players[player_id] = [{"observation_receipt": receipt}] * 10
                    source.writestr(path, raw)
            archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            archive.rename(bundles / f"{archive_sha}.zip")
            manifest = manifests / "original.json"
            manifest.write_text(json.dumps({
                "signed_observation_contracts_by_player": players,
                "source_bundle": {
                    "format": "exact_original_receipts_and_derived_zip_v1",
                    "path": f"history_bundles/{archive_sha}.zip", "sha256": archive_sha,
                },
            }))
            args = root, str(manifest.relative_to(root)), hashlib.sha256(manifest.read_bytes()).hexdigest(), pool
            with patch.object(history_bridge, "current_storage"):
                subset = history_bridge.open_history_sources(*args, selected_players={"1031"})
                available = history_bridge.available_history_players(subset)
                self.assertEqual(len(available), 31)
                self.assertIn("1031", available)
                self.assertNotIn("1032", available)
                self.assertFalse((subset / "nhl_sog_official_derived/1032.json").exists())
                self.assertEqual(history_bridge.open_history_sources(*args, selected_players={"1031"}), subset)


class ArchivedGameSourceTests(unittest.TestCase):
    def test_recovery_after_freeze_requires_existing_p0_and_independent_c03(self):
        start = datetime.now(timezone.utc) + timedelta(minutes=5)
        freeze = (start - timedelta(minutes=20)).isoformat()
        day = start.date().isoformat()
        row = {"id": 2026020300, "startTimeUTC": start.isoformat(), "gameState": "FUT",
               "homeTeam": {"abbrev": "TOR"}, "awayTeam": {"abbrev": "BOS"},
               "season": 20262027, "gameType": 2}
        game = source_pipeline.scheduled_games({"games": [row]}, day=day)[0]
        key = hashlib.sha256(b"local archived source test key").digest()
        with TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / source_pipeline.ROOT_NAMESPACE / "c03"
            proofs = folder / "c03_collector_receipts"
            proofs.mkdir(parents=True)
            p0 = {}
            source_urls = [(f"nhl:schedule:{day}", "nhl_schedule", f"score/{day}", {"games": [row]})]
            for team, player in (("TOR", 1000), ("BOS", 2000)):
                source_urls.append((f"nhl:roster:{team}", "nhl_current_roster",
                                    f"roster/{team}/current", {"forwards": [{"id": player}],
                                                              "defensemen": [], "goalies": []}))
            for sid, kind, url, doc in source_urls:
                receipt = archive_response(
                    canonical(doc), archive_root=folder,
                    source_url=f"{source_pipeline.OFFICIAL}/{url}",
                    observed_at=(start - timedelta(minutes=24)).isoformat(),
                    received_at=(start - timedelta(minutes=23)).isoformat(),
                    source_namespace="nhl_official", source_id=sid, http_status=200,
                )
                proof = canonical({"schema": SCHEMA, "receipt_fields": _signed_body(receipt),
                                   "hmac_sha256": _mac(receipt, key)})
                (proofs / (source_pipeline.digest(proof) + ".json")).write_bytes(proof)
                p0_record = source_pipeline._p0_official_source(receipt, source_kind=kind, source_id=sid)
                p0[source_pipeline.digest(source_pipeline.canonical_bytes(p0_record))] = p0_record

            with (patch.object(source_pipeline, "current_storage"),
                  patch.dict(os.environ, {SECRET_ENV: key.hex()}),
                  patch.object(source_pipeline, "verify_immutable_record", side_effect=lambda *args: p0[args[-1]])):
                schedule, rosters, members = source_pipeline.read_archived_game_sources(root, game, freeze=freeze)
                self.assertEqual(schedule["document"], {"games": [row]})
                self.assertEqual(set(members["BOS"]), {"2000"})
                del p0[rosters["BOS"]["p0_sha256"]]
                with self.assertRaisesRegex(ValueError, "P2_ARCHIVED_SIGNED_GAME_SOURCES_INCOMPLETE"):
                    source_pipeline.read_archived_game_sources(root, game, freeze=freeze)


if __name__ == "__main__":
    unittest.main()
