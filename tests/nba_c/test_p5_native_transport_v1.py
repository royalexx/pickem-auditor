"""Synthetic native transport controls; real source admission stays blocked."""
import base64
from copy import deepcopy
import hashlib
import tempfile
import unittest
from pathlib import Path

from v2.nba_architecture.v2_contracts import canonical, digest
from v2.nba_c.native_adapters import (NativeForecastArchive, NativeOutcomeArchive,
    P1_VERSION, validate_p1_export)
from v2.nba_c.warehouse import WarehouseError


def missing_outcome():
    return {"schema": P1_VERSION, "kind": "outcome_export", "game_id": "nba:test",
        "player_id": "nba:p1", "team_id": None,
        "source_profile": "unadmitted_isolated_outcome_vault",
        "admission_status": "BLOCKED", "status": "UNRESOLVED",
        "participation": "UNRESOLVED", "stats": {}, "official_count": None,
        "displayed_minutes": None, "exact_minutes": None,
        "event_start_at": None, "event_end_at": None, "outcome_released_at": None,
        "vault_schema": None, "revisions": [], "correction_version": None,
        "scoring_authorized": False,
        "missing_requirements": ["OFFICIAL_OUTCOME_MISSING", "SOURCE_BOUND_EVENT_END",
                                 "SOURCE_BOUND_OUTCOME_RELEASE_CLOCK"]}


def source_export():
    raw=b'{"synthetic":true}'
    capture={"raw_sha256": hashlib.sha256(raw).hexdigest(), "revision": 1,
        "supersedes_receipt_sha256": None, "url": "https://example.invalid/prior",
        "retrieved_at": "2022-10-02T00:00:00Z"}
    return {"schema": P1_VERSION, "kind": "prior_game_export",
        "source_profile": "synthetic_engineering", "admission_status": "BLOCKED",
        "evidence_bundle": {"capture": capture, "raw_base64":
            base64.b64encode(raw).decode(), "prior": []}}


class NativeTransportControlsV1(unittest.TestCase):
    def test_missing_outcome_is_immutable_separate_and_unscored(self):
        export=missing_outcome()
        with tempfile.TemporaryDirectory() as root:
            archive=NativeOutcomeArchive(root)
            key=archive.put_p1(export,evidence_mode="synthetic_engineering")
            self.assertEqual(key,archive.put_p1(export,evidence_mode="synthetic_engineering"))
            self.assertEqual(archive.get(key),export)
            export["participation"]="PLAYED"
            self.assertEqual(archive.get(key)["participation"],"UNRESOLVED")
            disposition=archive.scoring_disposition(key)
            self.assertFalse(disposition["scored"])
            self.assertEqual(disposition["status"],"BLOCKED")
            self.assertFalse((Path(root)/"native_forecast_only").exists())
            self.assertFalse((Path(root)/"forecast_only").exists())

    def test_real_outcome_and_forecast_intake_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            for mode in ("", "real", "P1_VERIFIED", "synthetic", "SYNTHETIC_UNIT_TEST"):
                with self.subTest(mode=mode), self.assertRaisesRegex(
                        WarehouseError,"REAL_ADMISSION_REGISTRY_UNAVAILABLE"):
                    NativeOutcomeArchive(root).put_p1(missing_outcome(),evidence_mode=mode)
                with self.subTest(mode=mode), self.assertRaisesRegex(
                        WarehouseError,"REAL_ADMISSION_REGISTRY_UNAVAILABLE"):
                    NativeForecastArchive(root).put_s(None,None,
                        frozen_pregame=None,target_player_id="nba:p1",role="wing",
                        source_manifest={},evidence_mode=mode)

    def test_outcome_export_cannot_enter_forecast_source_argument(self):
        with self.assertRaisesRegex(WarehouseError,"OUTCOME_IN_FORECAST_SOURCE"):
            validate_p1_export(missing_outcome())

    def test_false_admission_or_scoring_authority_rejected(self):
        for key,value in (("admission_status","ACCEPTED"),("scoring_authorized",True),
                          ("schema","nba-p1-native-handoff/0.0.0")):
            export=missing_outcome();export[key]=value
            with self.subTest(key=key),self.assertRaises(WarehouseError):
                validate_p1_export(export,outcome=True)

    def test_exact_raw_ancestor_corruption_and_orphan_revision_reject(self):
        export=source_export();validate_p1_export(export)
        second=deepcopy(export["evidence_bundle"])
        second["prior"]=[deepcopy(export["evidence_bundle"])]
        second["capture"].update(revision=2,
            supersedes_receipt_sha256=digest(second["prior"][0]["capture"]),
            retrieved_at="2022-10-03T00:00:00Z")
        export["evidence_bundle"]=second;validate_p1_export(export)
        for ancestor in (False,True):
            bad=deepcopy(export)
            node=bad["evidence_bundle"]["prior"][0] if ancestor else bad["evidence_bundle"]
            node["raw_base64"]=base64.b64encode(b'corrupt').decode()
            with self.subTest(ancestor=ancestor),self.assertRaisesRegex(
                    WarehouseError,"SOURCE_BYTES_CHANGED"):
                validate_p1_export(bad)
        bad=deepcopy(export);bad["evidence_bundle"]["prior"]=[]
        with self.assertRaisesRegex(WarehouseError,"SOURCE_ANCESTRY"):
            validate_p1_export(bad)
        bad=deepcopy(export);bad["evidence_bundle"]["capture"]["retrieved_at"]="2022-10-01T00:00:00Z"
        with self.assertRaisesRegex(WarehouseError,"REVISION_CLOCK_OR_IDENTITY"):
            validate_p1_export(bad)

    def test_stored_outcome_tampering_detected(self):
        with tempfile.TemporaryDirectory() as root:
            archive=NativeOutcomeArchive(root)
            key=archive.put_p1(missing_outcome(),evidence_mode="synthetic_engineering")
            path=archive.root/(key+".json")
            tampered=missing_outcome();tampered["official_count"]=30
            path.chmod(0o644);path.write_bytes(canonical(tampered)+b"\n")
            with self.assertRaisesRegex(WarehouseError,"OUTCOME_BYTES_CHANGED"):
                archive.get(key)


if __name__ == "__main__":
    unittest.main()
