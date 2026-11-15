"""Independent native WS1 adapter tests; fake fixtures are never live evidence."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nfl_sunday_ws6_audit as main_audit
import nfl_sunday_ws6_ws1_adapter as adapter


class WS1NativeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "source_control/raw").mkdir(parents=True)
        self.data = b"TEST_ONLY_FAKE_ORIGINAL_WS1_HTTP_RESPONSE"
        self.sha = hashlib.sha256(self.data).hexdigest()
        (self.root / "source_control/raw" / (self.sha + ".bin")).write_bytes(self.data)
        events = []
        for n, (away, home, hhmm) in enumerate(adapter.SCHEDULE):
            dt = datetime.fromisoformat(f"2026-11-15T{hhmm}:00-05:00")
            events.append({"away": away, "home": home,
                           "espn_event_id": "ESPN" + str(n),
                           "fixture_key": f"2026-11-15|{away}|{home}",
                           "scheduled_kickoff": dt.astimezone(timezone.utc).isoformat(),
                           "schedule_verified": True, "source_sha256": self.sha})
        quote = {"sport": "NFL", "line": 5.5, "book": "x",
                 "over_odds": 1.9, "under_odds": 1.9}
        c = {"candidate_id": "C1", "quote_id": "Q1", "event_id": "ESPN0",
             "event_start_at": events[0]["scheduled_kickoff"],
             "player_id": "P1", "player": "Test Player", "stat": "receptions",
             "period": "full_game", "line": 5.5, "book": "x",
             "original_quote": quote, "source_sha256": self.sha,
             "source_received_at": "2026-11-15T13:00:00Z",
             "source_archive_path": f"source_control/raw/{self.sha}.bin",
             "eligibility_status": "ROSTER_MEMBER_GAME_ACTIVE_UNCONFIRMED",
             "source_certified": True, "availability_certified": False,
             "settlement_semantics": "PRODUCT_SPECIFIC_RULES_UNVERIFIED"}
        self.manifest = {
            "schema": adapter.WS1, "date": "2026-11-15",
            "events": events, "candidates": [c], "quote_observations": 1,
            "source_certified_quotes": 1, "forecast_eligible_contracts": 0,
            "sources": {"propline": {"source_bytes_verified": True,
                "source_received_at": "2026-11-15T13:00:00Z",
                "sha256": self.sha, "source_publication_truth_verified": False,
                "archive_path": f"source_control/raw/{self.sha}.bin"}},
            "handoff": {"no_original_source_recapture": True}}
        self.ws1 = self.root / "ws1.json"
        self.save()

    def save(self):
        self.ws1.write_text(json.dumps(self.manifest, sort_keys=True))

    def test_native_mapping_preserves_rejection_and_original_hash(self):
        self.assertEqual(adapter.convert(self.root, self.ws1, self.root / "adapted"), 2)
        report = main_audit.load_json(self.root / "adapted/ws1_adapter_integrity_report.json")
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["derived_accepted_contracts"], 0)
        self.assertEqual(report["source_contract_sha256"], main_audit.file_sha(self.ws1))
        self.assertEqual(report["source_receipt_hash_pass"], 1)
        self.assertIn("PRODUCT_SETTLEMENT_TERMS_UNVERIFIED", report["rejection_reasons"])
        rows = main_audit.load_jsonl(self.root / "adapted/derived_original_quotes.jsonl")
        self.assertFalse(rows[0]["accepted"])
        self.assertIsNone(rows[0].get("over_decimal_odds"))

    def test_tampered_raw_receipt_is_not_blessed(self):
        (self.root / "source_control/raw" / (self.sha + ".bin")).write_bytes(b"FAKE_TAMPERED")
        self.assertEqual(adapter.convert(self.root, self.ws1, self.root / "adapted"), 2)
        report = main_audit.load_json(self.root / "adapted/ws1_adapter_integrity_report.json")
        self.assertEqual(report["source_receipt_hash_pass"], 0)

    def test_unverified_scheduled_event_retained_but_not_certified(self):
        self.manifest["events"][0]["schedule_verified"] = False
        self.save()
        self.assertEqual(adapter.convert(self.root, self.ws1, self.root / "adapted"), 2)
        report = main_audit.load_json(self.root / "adapted/ws1_adapter_integrity_report.json")
        self.assertFalse(report["schedule_identity_verified"])

    def test_wrong_schema_rejected_without_outputs(self):
        self.manifest["schema"] = "old"
        self.save()
        with self.assertRaises(main_audit.IntegrityError):
            adapter.convert(self.root, self.ws1, self.root / "adapted")
        self.assertFalse((self.root / "adapted").exists())

    def test_frozen_source_manifest_does_not_mutate(self):
        original = main_audit.file_sha(self.ws1)
        adapter.convert(self.root, self.ws1, self.root / "adapted")
        self.assertEqual(main_audit.file_sha(self.ws1), original)
        with self.assertRaises(main_audit.IntegrityError):
            adapter.convert(self.root, self.ws1, self.root / "adapted")

    def test_capture_relative_root_guard_rejects_wrong_project_root(self):
        nested = self.root / "reports/nfl_20261115_prospective/source_control/captures"
        nested.mkdir(parents=True)
        capture = nested / "canonical.json"
        capture.write_text(self.ws1.read_text())
        with self.assertRaisesRegex(main_audit.IntegrityError, "WS1_ARCHIVE_ROOT_MISMATCH"):
            adapter.convert(self.root, capture, self.root / "derived")
        self.assertFalse((self.root / "derived").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
