"""Isolated synthetic P2-to-P4 regression tests; no prospective evidence."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest
from unittest.mock import patch

from research.p5_daily.scoring import score_count
from v2 import nhl_sog_p4_slate as slate
from v2.p0_integrity.contracts import canonical_bytes, record, sha256
from v2.p0_integrity.storage import NAMESPACES
import test_nhl_sog_p4_forecasts


class SlateForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model_fixture = test_nhl_sog_p4_forecasts.P4Tests
        cls.model_fixture.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.model_fixture.tearDownClass()

    def test_canonical_freeze_retry_and_p5_distribution_scoring(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime.now(timezone.utc)
            freeze = slate.stamp(now - timedelta(minutes=1))
            start = slate.stamp(now + timedelta(minutes=30))
            source_raw = b"test-only source bytes"
            (root / "source").write_bytes(source_raw)
            source = record("SourceReceipt", receipt_id="source", source_id="synthetic:test",
                            source_kind="synthetic-test", source_available_at=freeze,
                            collected_at=freeze, source_sha256=hashlib.sha256(source_raw).hexdigest(),
                            archive_path="source", provenance_class="collector_possession")
            features = {"history": {"own": [], "peers": []},
                        "missingness": {"role_transition_uncertain": False}}
            feature = record("PregameFeatureSnapshot", feature_snapshot_id="feature",
                             sport="NHL", event_id="test-game", player_id="test-player",
                             team_id="AAA", opponent_id="BBB", stat_key="shots on goal",
                             period="full", input_freeze_at=freeze, source_receipt_ids=["source"],
                             reconstruction_class="original", feature_sha256=sha256(features),
                             features=features)
            manifest = {
                "event_id": "test-game", "official_nhl_player_id": "test-player",
                "event_start_at": start, "input_freeze_at": freeze,
                "source_admission": "SOURCE_READY_LINE_INDEPENDENT_ONLY",
                "quote_id": None, "P0_quote_record_sha256": None,
                "official_schedule_source_sha256": sha256(source),
                "official_roster_source_sha256": {}, "P0_original_historical_source_record_hashes": [],
                "signed_historical_observation_hashes": [], "own_history_count": 0,
                "peer_history_count": 0, "p0_feature_record_sha256": sha256(feature),
            }
            written = {("SourceReceipt", sha256(source)): source}

            def save(root, kind, value):
                digest = sha256(value)
                field = "model_artifact_id" if kind == "ModelArtifact" else "forecast_id"
                claim = hashlib.sha256((kind + "\x00" + value[field]).encode()).hexdigest()
                base = root / "research/p0_integrity_store" / NAMESPACES[kind]
                (base / "_ids").mkdir(parents=True, exist_ok=True)
                (base / "_ids" / (claim + ".json")).write_bytes(canonical_bytes({"record_sha256": digest}))
                path = base / (digest + ".json")
                path.write_bytes(canonical_bytes(value))
                written[kind, digest] = value
                return {"sha256": digest, "relative_path": str(path.relative_to(root))}

            history = type("FixtureHistory", (), {"root": root, "pool": root / "history",
                                                  "derived_root": root / "cached-derived",
                                                  "sha256": "b" * 64})()
            model = {**self.model_fixture.model, "fit_data_cutoff_at": freeze}
            with (patch.object(slate, "verify_bundle", return_value=(manifest, feature, {sha256(source): source})),
                  patch.object(slate, "_official_identity", return_value=({"official_season": 20262027}, "F")),
                  patch.object(slate, "fit_model", return_value=model),
                  patch.object(slate, "verify_immutable_record", side_effect=lambda _, kind, key: written[kind, key]),
                  patch.object(slate, "append_immutable", side_effect=save) as append):
                options = {"code_commit": "a" * 40, "run_id": "synthetic-test", "history_sources": history}
                first = slate.forecast_bundle(root, "c" * 64, **options)
                retry = slate.forecast_bundle(root, "c" * 64, **options)
                self.assertEqual(first["status"], "FROZEN", first)
                self.assertEqual(first, retry)
                self.assertEqual(append.call_count, 4)
                self.assertEqual({row["kind"] for row in first["forecasts"]}, set(slate.MODELS))
                for row in first["forecasts"]:
                    snapshot = written["ForecastSnapshot", row["sha256"]]
                    self.assertEqual(snapshot["admission_class"], "A")
                    self.assertIsNone(snapshot["quote_id"])
                    score = score_count(snapshot["distribution"], 2)
                    self.assertAlmostEqual(score["mean"], row["mean"], places=9)

    def test_current_source_requires_matching_c03_evidence(self):
        with self.assertRaisesRegex(slate.P4Blocked, "CURRENT_C03_SOURCE_PROOF"):
            slate._current_source("/work", "a" * 64, {}, None, "test", {})

    def test_own_history_poisson_matches_registered_plugin_without_peers(self):
        fixture = self.model_fixture
        model, distributions, laws = slate._fit_plugin(
            fixture.own, archive_root=fixture.root, player_id="101", position_group="F",
            freeze=fixture.freeze, start=fixture.start)
        self.assertEqual(model["schema"], slate.PLUGIN_VERSION)
        self.assertEqual(model["plugin_rate"], fixture.model["plugin_rate"])
        self.assertEqual(model["plugin_exposure"], fixture.model["plugin_exposure"])
        self.assertEqual(distributions, {"plugin_poisson": {
            "kind": "poisson", "parameters": {"rate": laws["plugin_poisson"]["mean"]}}})
        self.assertEqual(len(model["source_manifest"]), len(fixture.own))
