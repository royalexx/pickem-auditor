"""P2 adversarial source-only tests. All identities, quotations, and clocks are
synthetic TEST fixtures; none can be admitted to genuine prospective cohorts.
"""
import copy
import hashlib
import hmac
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from research.p2_nhl_sog import source_pipeline as s
from research.p2_nhl_sog import market_capture as m
from v2.p0_integrity.contracts import validate_record, sha256


EVENT = {
    "event_id": "2026020999", "away_team": "BOS", "home_team": "MTL",
    "start_at": "2026-11-21T23:00:00Z", "scheduled_day": "2026-11-21",
    "local_date": "2026-11-21", "game_state": "FUT",
    "official_season": 20262027, "game_type": 2
}
FREEZE = "2026-11-21T22:40:00Z"
RECEIVED = "2026-11-21T22:10:00Z"
KEY = b"K" * 32


def fake_document():
    return {"games": [
        {"id": 2026020999, "gameState": "FUT",
         "startTimeUTC": EVENT["start_at"], "gameDate": "2026-11-21",
         "homeTeam": {"abbrev": "MTL"}, "awayTeam": {"abbrev": "BOS"}},
        {"id": 2026020998, "gameState": "OFF",
         "startTimeUTC": "2026-11-21T17:00:00Z",
         "homeTeam": {"abbrev": "TOR"}, "awayTeam": {"abbrev": "NYR"}}
    ]}


def raw_offer():
    return {"events": [{
        "id": "prov-event-1", "bookmakers": [{"key": "testbook",
        "markets": [{"key": "player_shots_on_goal", "outcomes": [
           {"name": "Over", "player_id": "prov-player-1",
            "description": "Alice Smith", "point": 2.5, "price": -125},
           {"name": "Under", "player_id": "prov-player-1",
            "description": "Alice Smith", "point": 2.5, "price": 105}
        ]}]}]
    }]}


def synthetic_quote_record():
    return {
      "fixture_kind": "synthetic", "official_event_id": EVENT["event_id"],
      "provider_event_id": "prov-event-1", "native_nhl_player_id": "8471234",
      "provider_player_id": "prov-player-1", "provider_player_name": "Alice Smith",
      "team": "MTL", "opponent": "BOS", "stat": "player_shots_on_goal",
      "period": "full", "product_type": "sportsbook_two_sided",
      "line": 2.5, "book": "testbook", "over_odds": -125,
      "under_odds": 105, "crosswalk_source_sha256": "a" * 64
    }


def fixture_provider(root):
    body = s.canonical_bytes(raw_offer())
    path = s.ROOT_NAMESPACE + "/provider/" + s.digest(body) + ".json"
    s.put_once(root, path, body)
    rec = {
        "schema": m.PROOF_SCHEMA, "source_url": m.URL + "?markets=player_shots_on_goal&bookmakers=draftkings",
        "source_kind": "original_provider_http_bytes",
        "received_at": RECEIVED, "archive_path": path,
        "sha256": s.digest(body), "bytes": len(body),
        "http_status": 200, "transport_semantics": "collector_tls_possession_only"
    }
    rec["hmac_sha256"] = hmac.new(KEY,
        s.canonical_bytes(m.proof_payload(rec)), hashlib.sha256).hexdigest()
    proof = s.canonical_bytes(rec)
    p = s.ROOT_NAMESPACE + "/provider_proofs/" + s.digest(proof) + ".json"
    s.put_once(root, p, proof)
    rec["proof_archive_path"] = p
    rec["proof_sha256"] = s.digest(proof)
    return rec


class ScheduleAndClockTests(unittest.TestCase):
    def test_valid_and_finished_ignored(self):
        rows = s.scheduled_games(fake_document(), day="2026-11-21")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_id"], EVENT["event_id"])

    def test_duplicate_event(self):
        d = fake_document()
        d["games"].append(copy.deepcopy(d["games"][0]))
        with self.assertRaisesRegex(s.SourceBlocked, "DUPLICATE_NHL_EVENT_ID"):
            s.scheduled_games(d, day="2026-11-21")

    def test_wrong_team(self):
        d = fake_document()
        d["games"][0]["awayTeam"]["abbrev"] = "MTL"
        with self.assertRaisesRegex(s.SourceBlocked, "OFFICIAL_EVENT_TEAMS_INVALID"):
            s.scheduled_games(d, day="2026-11-21")

    def test_naive_clock(self):
        with self.assertRaises(s.SourceBlocked):
            s.clock("2026-11-21T22:10:00")

    def test_final_window(self):
        t = datetime(2026, 11, 21, 22, 37, tzinfo=timezone.utc)
        self.assertEqual(s.capture_window(EVENT["start_at"], t), "FINAL")

    def test_early_window(self):
        t = datetime(2026, 11, 21, 22, 0, tzinfo=timezone.utc)
        self.assertEqual(s.capture_window(EVENT["start_at"], t), "EARLY")

    def test_missed_deadline(self):
        t = datetime(2026, 11, 21, 22, 41, tzinfo=timezone.utc)
        self.assertEqual(s.capture_window(EVENT["start_at"], t),
                         "MISSED_SOURCE_FREEZE_DEADLINE")

    def test_matinee_support(self):
        d = fake_document()
        d["games"][0]["startTimeUTC"] = "2026-11-21T18:00:00Z"
        rows = s.scheduled_games(d, day="2026-11-21")
        self.assertEqual(rows[0]["local_date"], "2026-11-21")

    def test_roster_has_no_played_assumption(self):
        roster = {"forwards": [{"id": 8471234}],
                  "defensemen": [{"id": 8475678}], "goalies": [{"id": 8479999}]}
        ids = s.parse_roster(roster, "MTL")
        self.assertEqual(ids["8471234"]["participation_status"], "UNKNOWN")
        self.assertEqual(ids["8479999"]["position_group"], "G")

    def test_duplicate_roster_identity(self):
        r = {"forwards": [{"id": 8471234}],
             "defensemen": [{"id": 8471234}], "goalies": []}
        with self.assertRaisesRegex(s.SourceBlocked, "DUPLICATE_PLAYER"):
            s.parse_roster(r, "MTL")

    def test_untrusted_missing_roster(self):
        with self.assertRaisesRegex(s.SourceBlocked, "GROUP_MISSING"):
            s.parse_roster({"forwards": [], "goalies": []}, "MTL")


class ImmutableAndProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_idempotent_raw_bytes(self):
        a = s.put_once(self.root, "a/b.json", b"unchanged")
        b = s.put_once(self.root, "a/b.json", b"unchanged")
        self.assertEqual(a, b)

    def test_reject_replacement(self):
        s.put_once(self.root, "a/b.json", b"original")
        with self.assertRaisesRegex(s.SourceBlocked, "IMMUTABLE_SOURCE_COLLISION"):
            s.put_once(self.root, "a/b.json", b"tampered")

    def test_cannot_escape_root(self):
        for path in ("../evidence", "/tmp/out", "a/../../outside"):
            with self.subTest(path=path):
                with self.assertRaises(s.SourceBlocked):
                    s.safe_relative(self.root, path)

    def test_concurrent_same_content(self):
        from concurrent.futures import ThreadPoolExecutor
        def f(_):
            return s.put_once(self.root, "parallel/file.json", b"same")
        with ThreadPoolExecutor(max_workers=8) as p:
            results = list(p.map(f, range(24)))
        self.assertEqual(len({x["sha256"] for x in results}), 1)

    def test_attempt_receipt_hash(self):
        x = s.attempt(self.root, "source", "REJECTED", ["MISSING_C03"])
        self.assertEqual(x["receipt"]["sha256"],
                         s.digest(s.safe_relative(self.root, x["receipt"]["relative_path"]).read_bytes()))

    def test_fake_c03_proof_cannot_pass(self):
        with patch.object(s, "current_storage"):
            with self.assertRaises(s.SourceBlocked):
                s.capture_official(
                    self.root, s.OFFICIAL + "/score/2026-11-21",
                    event_start_at="2026-11-21T23:00:00Z",
                    input_freeze_at="2020-01-01T00:00:00Z",
                    source_kind="nhl_schedule", source_id="nhl:test")

    def test_signed_source_missing_proof_rejected(self):
        with self.assertRaisesRegex(s.SourceBlocked, "SOURCE_RECEIPT_BUNDLE_MISSING"):
            s.retrieve_source(self.root, {}, freeze=FREEZE, event_start=EVENT["start_at"])


class ProviderQuoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.ref = fixture_provider(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def verified(self):
        return m.verify_original_provider(self.root, self.ref, freeze=FREEZE,
                         event_start=EVENT["start_at"], key_func=lambda: KEY)

    def bind(self, o, ref=None):
        with patch.object(m, "signing_key", return_value=KEY):
            return s.quote_from_archived_raw(
                self.root, ref if ref is not None else self.ref, o,
                player_id="8471234", team="MTL", opponent="BOS",
                event_id=EVENT["event_id"], start=EVENT["start_at"],
                freeze=FREEZE, official_name="Alice Smith")

    def test_synthetic_never_genuine(self):
        with self.assertRaisesRegex(s.SourceBlocked, "SYNTHETIC_QUOTE_FORBIDDEN"):
            self.bind(synthetic_quote_record())

    def test_valid_synthetic_format_only_inside_negative_fixture(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        # Modelled data only in a test, never persisted as genuine evidence.
        q = self.bind(row)
        self.assertEqual((q["over_american"], q["under_american"]), (-125, 105))

    def test_wrong_player_id(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        row["native_nhl_player_id"] = "8474321"
        with self.assertRaisesRegex(s.SourceBlocked, "CROSSWALK_MISSING"):
            self.bind(row)

    def test_wrong_event_id(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        row["official_event_id"] = "2026020001"
        with self.assertRaisesRegex(s.SourceBlocked, "TEAM_CROSSWALK_MISMATCH"):
            self.bind(row)

    def test_wrong_team(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        row["team"] = "BOS"
        with self.assertRaises(s.SourceBlocked):
            self.bind(row)

    def test_wrong_market(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        row["stat"] = "player_shots"
        with self.assertRaisesRegex(s.SourceBlocked, "INCOMPATIBLE_SOG_MARKET"):
            self.bind(row)

    def test_missing_under(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        row.pop("under_odds")
        with self.assertRaisesRegex(s.SourceBlocked, "UNDER_PRICE"):
            self.bind(row)

    def test_mutated_odds(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        row["over_odds"] = -110
        with self.assertRaisesRegex(s.SourceBlocked, "ROW_MISMATCH"):
            self.bind(row)

    def test_wrong_name(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        row["provider_player_name"] = "Another Player"
        with self.assertRaisesRegex(s.SourceBlocked, "NAME_MISMATCH"):
            self.bind(row)

    def test_invalid_hmac(self):
        r = dict(self.ref)
        r["hmac_sha256"] = "0" * 64
        with self.assertRaisesRegex(s.SourceBlocked, "PROVIDER_HMAC_INVALID"):
            self.bind(dict(synthetic_quote_record(), fixture_kind="raw"), r)

    def test_proof_missing(self):
        r = dict(self.ref)
        r["proof_archive_path"] = None
        with self.assertRaises(s.SourceBlocked):
            self.bind(dict(synthetic_quote_record(), fixture_kind="raw"), r)

    def test_late_quote(self):
        with self.assertRaisesRegex(s.SourceBlocked, "PROVIDER_SOURCE_AFTER_FREEZE"):
            m.verify_original_provider(self.root, self.ref,
               freeze="2026-11-21T21:55:00Z",
               event_start=EVENT["start_at"], key_func=lambda: KEY)

    def test_post_event_quote(self):
        with self.assertRaisesRegex(s.SourceBlocked, "PROVIDER_SOURCE_AFTER_FREEZE"):
            m.verify_original_provider(self.root, self.ref,
               freeze="2026-11-21T23:01:00Z",
               event_start=EVENT["start_at"], key_func=lambda: KEY)

    def test_provider_body_modified(self):
        path = s.safe_relative(self.root, self.ref["archive_path"])
        path.write_bytes(b"tampered")
        with self.assertRaisesRegex(s.SourceBlocked, "PROVIDER_BODY_CORRUPT"):
            self.verified()

    def test_missing_crosswalk_source(self):
        row = synthetic_quote_record()
        row.pop("fixture_kind")
        row["crosswalk_source_sha256"] = ""
        with self.assertRaisesRegex(s.SourceBlocked, "CROSSWALK_EVIDENCE_MISSING"):
            self.bind(row)


class FeatureContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = lambda kind: {
            "p0_sha256": kind * 64,
            "p0_receipt": {"receipt_id": "p2:" + kind,
                           "collected_at": RECEIVED}}
        self.members = {
            "MTL": {"8471234": {"position_group": "F"}},
            "BOS": {"8472222": {"position_group": "F"}}}
        self.history = [{
            "game_id": "2026020123", "game_date": "2026-11-20",
            "historical_team": "MTL", "shots_on_goal": 3,
            "toi_minutes": 17.5, "derived_observation_sha256": "d" * 64,
            "derived_archive_path": "fixture", "signed_profile_proof_sha256": "a" * 64,
            "signed_log_proof_sha256": "b" * 64,
            "signed_final_proof_sha256": "c" * 64
        }]

    def tearDown(self):
        self.temp.cleanup()

    def make(self, experiment=None):
        with (patch.object(s, "current_storage"),
              patch.object(s, "retrieve_source"),
              patch.object(s, "verified_history", return_value=self.history),
              patch.object(s, "append_immutable", return_value={"sha256": "f" * 64})):
            return s.build_bundle(
                self.root, game=EVENT, schedule_source=self.source("a"),
                rosters={"MTL": self.source("b"), "BOS": self.source("c")},
                roster_members=self.members, player_id="8471234",
                history_entries=[], freeze=FREEZE, required_experiment=experiment)

    def test_market_free_accepted_separately(self):
        b = self.make()
        self.assertEqual(b["manifest"]["source_admission"],
                         "SOURCE_READY_LINE_INDEPENDENT_ONLY")
        self.assertIsNone(b["feature"]["features"]["market"])
        self.assertFalse(b["manifest"]["model_predictions_present"])

    def test_market_registered_experiment_must_abstain(self):
        b = self.make("EXP-V25-NHL-SOG-EXPOSURE-EB-001")
        self.assertEqual(b["manifest"]["source_admission"],
                         "ABSTAIN_GENUINE_TWO_SIDED_QUOTE_MISSING")

    def test_goalie_rejected(self):
        self.members["MTL"]["8471234"]["position_group"] = "G"
        with self.assertRaisesRegex(s.SourceBlocked, "UNSUPPORTED_SOG_POSITION"):
            self.make()

    def test_missing_roster_identity_rejected(self):
        self.members["MTL"] = {}
        with self.assertRaisesRegex(s.SourceBlocked, "PLAYER_NOT_IN_CURRENT"):
            self.make()

    def test_opponent_roster_duplication(self):
        self.members["BOS"]["8471234"] = {"position_group": "F"}
        with self.assertRaisesRegex(s.SourceBlocked, "PLAYER_IN_OPPONENT_ROSTER"):
            self.make()

    def test_stale_roster_rejected(self):
        old = self.source("b")
        old["p0_receipt"]["collected_at"] = "2026-11-21T10:00:00Z"
        with patch.object(s, "current_storage"), patch.object(s, "retrieve_source"):
            with self.assertRaisesRegex(s.SourceBlocked, "ROSTER_SOURCE_STALE"):
                s.build_bundle(
                    self.root, game=EVENT, schedule_source=self.source("a"),
                    rosters={"MTL": old, "BOS": self.source("c")},
                    roster_members=self.members, player_id="8471234",
                    history_entries=[], freeze=FREEZE)

    def test_repeat_bundle_immutable(self):
        x = self.make()
        y = self.make()
        self.assertEqual(x["receipt"]["sha256"], y["receipt"]["sha256"])

    def test_manifest_tamper(self):
        x = self.make()
        path = s.safe_relative(self.root, x["receipt"]["relative_path"])
        path.write_bytes(b"corrupted")
        with patch.object(s, "current_storage"):
            with self.assertRaisesRegex(s.SourceBlocked, "SOURCE_BUNDLE_CORRUPT"):
                s.verify_bundle(self.root, x["receipt"]["sha256"])


if __name__ == "__main__":
    unittest.main()
