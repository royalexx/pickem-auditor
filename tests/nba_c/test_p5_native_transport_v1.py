"""Synthetic native transport controls; real source admission stays blocked."""
import base64
from copy import deepcopy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from v2.nba_architecture.v2_contracts import canonical, digest, seal
from v2.nba_c.native_adapters import (NativeForecastArchive, NativeOutcomeArchive,
    P1_VERSION, validate_p1_export, _box_stats)
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
        "missing_requirements": ["INDEPENDENT_SOURCE_ADMISSION", "SOURCE_BOUND_EVENT_END",
                                 "SOURCE_BOUND_OUTCOME_RELEASE_CLOCK", "OFFICIAL_OUTCOME_MISSING"]}


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

    def test_actual_p1_export_summary_claims_rederived_from_source(self):
        # Exact actual P1 export from pinned a3263bc, synthetic source/vault.
        export=json.loads(Path("tests/nba_c/fixtures/native_p1_outcome_synthetic_v1.json").read_bytes())
        validate_p1_export(export,outcome=True)
        claims={"source_profile":"original_prospective", "status":"CERTIFIED",
            "missing_requirements":[], "event_end_at":"2022-10-22T02:00:00Z",
            "outcome_released_at":"2022-10-22T03:00:00Z", "official_count":11,
            "event_start_at":"2020-01-01T00:00:00Z", "exact_minutes":999,
            "displayed_minutes":999, "participation":"DNP", "team_id":"nba:team:99"}
        for key,value in claims.items():
            bad=deepcopy(export);bad[key]=value
            with self.subTest(key=key),self.assertRaises(WarehouseError):
                validate_p1_export(bad,outcome=True)

    def test_unknown_outcome_cannot_acquire_counts_clocks_or_display(self):
        for key,value in {"displayed_minutes":0,"exact_minutes":0,"official_count":0,
                "event_start_at":"2022-10-20T23:00:00Z", "event_end_at":"2022-10-21T01:00:00Z",
                "outcome_released_at":"2022-10-21T02:00:00Z", "status":"UNADMITTED",
                "vault_schema":"nba-p1-official-outcome-vault/1.1.0",
                "missing_requirements":[]}.items():
            bad=missing_outcome();bad[key]=value
            with self.subTest(key=key),self.assertRaises(WarehouseError):
                validate_p1_export(bad,outcome=True)

    def _reseal_record(self,revision):
        record=seal({k:v for k,v in revision["record"].items() if k!="content_hash"})
        revision["record"]=record
        raw=canonical(record)+b"\n"
        revision["record_raw_base64"]=base64.b64encode(raw).decode()
        revision["record_raw_sha256"]=hashlib.sha256(raw).hexdigest()
        return record

    def test_resealed_correction_cannot_change_source_clock_team_stats_descriptor(self):
        source=json.loads(Path("tests/nba_c/fixtures/native_p1_outcome_synthetic_v1.json").read_bytes())
        for attack in ("clock","team","stats","descriptor"):
            bad=deepcopy(source);revision=bad["revisions"][-1]
            if attack=="clock":
                revision["record"]["observed_at"]="2026-11-16T18:59:59Z"
            if attack=="team":
                revision["record"]["team_id"]="nba:team:2";bad["team_id"]="nba:team:2"
            if attack=="stats":
                revision["record"]["stats"]["points"]=12;bad["stats"]["points"]=12
            if attack=="descriptor":
                revision["accounting_evidence"]["capture"]["retrieved_at"]="2026-11-16T21:00:00Z"
            self._reseal_record(revision)
            with self.subTest(attack=attack),self.assertRaises(WarehouseError):
                validate_p1_export(bad,outcome=True)

    def test_raw_duration_and_subminute_decisions_precede_float_rounding(self):
        source=json.loads(Path("tests/nba_c/fixtures/native_p1_outcome_synthetic_v1.json").read_bytes())
        for raw_minutes,display,valid in (("PT48M00S",48,True),
                ("PT48M00.0000000000000000000000000000000000000000000000001S",48,False),
                ("PT00M29.9999999999999999999999999999999999999999999999999S",0,True),
                ("PT00M30.0000000000000000000000000000000000000000000000001S",0,False)):
            bad=deepcopy(source);revision=bad["revisions"][-1]
            bundle=revision["accounting_evidence"]
            game=json.loads(base64.b64decode(bundle["raw_base64"]))
            game["game"]["homeTeam"]["players"][0]["statistics"]["minutes"]=raw_minutes
            raw=canonical(game);sha=hashlib.sha256(raw).hexdigest()
            bundle["raw_base64"]=base64.b64encode(raw).decode();bundle["capture"]["raw_sha256"]=sha
            revision["source_raw_base64"]=base64.b64encode(raw).decode();revision["source_raw_sha256"]=sha
            revision["record"]["source_raw_sha256"]=sha
            revision["record"]["accounting_evidence"]["capture"]=deepcopy(bundle["capture"])
            revision["record"]["minutes"]=display
            revision["record"]["state"]="PLAYED" if display else "PLAYED_ZERO_MINUTES"
            bad["displayed_minutes"]=display;bad["participation"]=revision["record"]["state"]
            from fractions import Fraction
            parts=raw_minutes[2:-1].split("M")
            bad["exact_minutes"]=float(Fraction(parts[0])+Fraction(parts[1])/60)
            self._reseal_record(revision)
            with self.subTest(raw_minutes=raw_minutes):
                if valid:
                    validate_p1_export(bad,outcome=True)
                else:
                    with self.assertRaises(WarehouseError):
                        validate_p1_export(bad,outcome=True)

    def test_nonplayed_raw_credits_minutes_and_unknown_participation_are_not_erased(self):
        source=json.loads(Path("tests/nba_c/fixtures/native_p1_outcome_synthetic_v1.json").read_bytes())
        for state,played,points,rawminutes,valid in (
                ("DNP","0",0,"PT00M00S",True),
                ("UNRESOLVED","unknown",0,"PT00M00S",True),
                ("DNP","0",1,"PT00M00S",False),
                ("DNP","0",0,"PT00M00.0000000000000000000000000000001S",False),
                ("UNRESOLVED","1",0,"PT00M00S",False),
                ("UNRESOLVED","0",0,"PT00M00S",False)):
            bad=deepcopy(source);revision=bad["revisions"][-1]
            bundle=revision["accounting_evidence"]
            rawgame=json.loads(base64.b64decode(bundle["raw_base64"]))
            person=rawgame["game"]["homeTeam"]["players"][0]
            person["played"]=played;person["statistics"]={"minutes":rawminutes,"points":points}
            raw=canonical(rawgame);sha=hashlib.sha256(raw).hexdigest()
            bundle["raw_base64"]=base64.b64encode(raw).decode();bundle["capture"]["raw_sha256"]=sha
            revision["source_raw_base64"]=base64.b64encode(raw).decode();revision["source_raw_sha256"]=sha
            revision["record"].update(source_raw_sha256=sha,state=state,minutes=None,stats={})
            revision["record"]["accounting_evidence"]["capture"]=deepcopy(bundle["capture"])
            bad.update(participation=state,stats={},displayed_minutes=None,exact_minutes=None)
            self._reseal_record(revision)
            with self.subTest(state=state,played=played,points=points,minutes=rawminutes):
                if valid:
                    validate_p1_export(bad,outcome=True)
                else:
                    with self.assertRaises(WarehouseError):
                        validate_p1_export(bad,outcome=True)

    def test_summary_boolean_numeric_equivalence_is_not_admission(self):
        export=json.loads(Path("tests/nba_c/fixtures/native_p1_outcome_synthetic_v1.json").read_bytes())
        for key in ("displayed_minutes","exact_minutes","correction_version"):
            bad=deepcopy(export);bad[key]=True
            with self.subTest(key=key),self.assertRaises(WarehouseError):
                validate_p1_export(bad,outcome=True)
        for good in ({"points":7,"fgm":2,"threes":1,"ftm":2},
                     {"points":6,"threes":2},{"rebounds":7,"oreb":2,"dreb":5}):
            _box_stats(good)
        for bad in ({"points":True},{"points":1,"threes":2},
                    {"fgm":3,"fga":2},{"rebounds":7,"oreb":2,"dreb":4},
                    {"points":8,"rebounds":2,"pr":11}):
            with self.subTest(stats=bad),self.assertRaises(WarehouseError):
                _box_stats(bad)

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
