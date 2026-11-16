"""Adversarial P1 tests; synthetic evidence only, no historical forecast scoring."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from v2.nba_architecture.v2_contracts import canonical, digest, validate_pregame
from v2.nba_architecture.p1_history import (
    build_historical_pregame, freeze_historical, HistoryIntegrityError,
    validate_ws1_envelope,
)
from v2.nba_architecture.p1_vault import OfficialOutcomeVault

OBS = "2026-11-16T18:00:00Z"
INGEST = "2026-11-16T18:01:00Z"
GAME = "espn:game:target-2023"
TEAMS = ("espn:team:1", "espn:team:2")


def make_entry(*, day="2022-10-21", game="espn:game:prior-1",
               player="espn:player:7", team="espn:team:1",
               status="played", minutes=26, stats=None):
    if stats is None:
        stats = {"points": 11, "rebounds": 5, "assists": 3, "threes": 2}
    payload = dict(
        game_id=game, player_id=player, team_id=team,
        opponent_id=("espn:team:2" if team == TEAMS[0] else TEAMS[0]),
        game_date=day, minutes=minutes, participation=status, starter=None,
        stats=stats)
    raw_source = b"raw-retrospective-summary-fixture"
    rbody = dict(
        source="synthetic:espn", raw_sha256=hashlib.sha256(raw_source).hexdigest(),
        observed_at=OBS, source_available_at=OBS, origin="retrospective_retrieval")
    rbody["receipt_id"] = digest(rbody)
    recbody = dict(
        kind="player_game", receipt_id=rbody["receipt_id"],
        payload=canonical(payload).decode("utf-8"),
        revision=1, supersedes=None)
    recbody["record_id"] = digest(recbody)
    return {"record": recbody, "receipt": rbody}


def build(entries, **overrides):
    args = dict(
        game_id=GAME, team_ids=TEAMS, event_start_at="2023-02-10T01:00:00Z",
        input_freeze_at="2023-02-09T23:45:00Z",
        forecast_at="2023-02-09T23:50:00Z",
        training_cutoff_at="2023-02-08T00:00:00Z",
        decision_local_date="2023-02-09", entries=entries, ingested_at=INGEST)
    args.update(overrides)
    return build_historical_pregame(**args)


class P1HistoryTest(unittest.TestCase):
    def test_g0_acceptance_and_uncertified_flag(self):
        item = build([make_entry()])
        self.assertTrue(validate_pregame(item))
        self.assertEqual(item["certification"], "HISTORICAL_RECONSTRUCTION_UNCERTIFIED")
        self.assertEqual(item["source_profile"], "historical_reconstruction")
        self.assertEqual(item["original_offer_count"], 0)
        self.assertIsNone(item["players"][0]["legal_eligibility"])
        self.assertEqual(item["players"][0]["availability"], "unknown")
        self.assertTrue(all(f["prior_game_date"] == "2022-10-21" for f in item["features"]))
        self.assertTrue(all(f["available_at"] is None for f in item["features"]))

    def test_no_real_snapshot_classification(self):
        item = build([make_entry()])
        self.assertEqual(item["sources"][0]["origin"], "retrospective_retrieval")
        self.assertEqual(item["sources"][0]["asof_basis"], "prior_game_date_only")
        self.assertNotEqual(item["sources"][0]["retrieved_at"], item["input_freeze_at"])

    def test_same_byte_determinism_and_permutation(self):
        a = make_entry(player="espn:player:7")
        b = make_entry(player="espn:player:8")
        x = build([a, b])
        y = build([b, a])
        self.assertEqual(canonical(x), canonical(y))
        self.assertEqual(x["content_hash"], y["content_hash"])

    def test_reject_target_game_outcome(self):
        with self.assertRaisesRegex(HistoryIntegrityError, "TARGET_GAME_OUTCOME_ACCESS"):
            build([make_entry(game=GAME)])

    def test_reject_same_day(self):
        with self.assertRaisesRegex(HistoryIntegrityError, "SAME_DAY_OR_FUTURE_HISTORY"):
            build([make_entry(day="2023-02-09")])

    def test_reject_future_row(self):
        with self.assertRaisesRegex(HistoryIntegrityError, "SAME_DAY_OR_FUTURE_HISTORY"):
            build([make_entry(day="2023-02-10")])

    def test_reject_duplicate_player_game(self):
        e = make_entry()
        with self.assertRaisesRegex(HistoryIntegrityError, "DUPLICATE_OR_CORRECTED_HISTORY_ROW"):
            build([e, e])

    def test_changed_record_hash(self):
        e = make_entry()
        e["record"]["record_id"] = "0" * 64
        with self.assertRaisesRegex(HistoryIntegrityError, "WS1_RECORD_SHA_MISMATCH"):
            build([e])

    def test_changed_receipt_hash(self):
        e = make_entry()
        e["receipt"]["raw_sha256"] = "f" * 64
        with self.assertRaisesRegex(HistoryIntegrityError, "WS1_RECEIPT_SHA_MISMATCH"):
            build([e])

    def test_original_bytes_mismatch(self):
        e = make_entry()
        with self.assertRaisesRegex(HistoryIntegrityError, "ORIGINAL_SOURCE_SHA_MISMATCH"):
            build([e], verified_source_bytes={e["receipt"]["receipt_id"]: b"WRONG"})

    def test_original_bytes_sha_verified(self):
        e = make_entry()
        p = build([e], verified_source_bytes={
            e["receipt"]["receipt_id"]: b"raw-retrospective-summary-fixture"})
        self.assertIn("match their source SHA", p["sources"][0]["asof_limitations"])

    def test_dnp_not_played_zero(self):
        e = make_entry(status="dnp", minutes=None, stats={})
        p = build([e])
        values = [f for f in p["features"] if f["name"].endswith(":participation")]
        self.assertEqual(values[0]["value"], "DNP")
        self.assertIsNone(next(f["value"] for f in p["features"] if
                               f["name"].endswith(":minutes")))

    def test_played_zero_remains_distinct(self):
        e = make_entry(status="played", minutes=0, stats={"points": 0, "threes": 0})
        p = build([e])
        self.assertEqual(next(f["value"] for f in p["features"] if
                              f["name"].endswith(":participation")), "PLAYED_ZERO_MINUTES")

    def test_ambiguous_dnp_is_not_zero(self):
        with self.assertRaisesRegex(HistoryIntegrityError, "DNP_UNKNOWN_NOT_ZERO"):
            build([make_entry(status="unknown", minutes=0, stats={})])

    def test_bad_made_threes_pair_rejected(self):
        with self.assertRaisesRegex(HistoryIntegrityError, "UNSUPPORTED_STAT_DEFINITION"):
            build([make_entry(stats={"3PT": "3-8"})])

    def test_shooting_constraints(self):
        with self.assertRaisesRegex(HistoryIntegrityError, "SHOOTING_ACCOUNTING"):
            build([make_entry(stats={"threes": 4, "fg3a": 2})])

    def test_points_arithmetic(self):
        with self.assertRaisesRegex(HistoryIntegrityError, "POINT_ACCOUNTING"):
            build([make_entry(stats={"points": 17, "fgm": 6, "threes": 2, "ftm": 1})])

    def test_cross_team_duplicate_same_day(self):
        a = make_entry()
        b = make_entry(game="espn:game:prior-2", team="espn:team:2")
        with self.assertRaisesRegex(HistoryIntegrityError, "SAME_DAY_PLAYER_TEAM_CONFLICT"):
            build([a, b])

    def test_freeze_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "frozen.json"
            p = build([make_entry()])
            self.assertEqual(freeze_historical(path, p), p["content_hash"])
            self.assertEqual(freeze_historical(path, p), p["content_hash"])
            newer = build([make_entry(player="espn:player:8")])
            with self.assertRaisesRegex(ValueError, "IMMUTABLE_CONFLICT"):
                freeze_historical(path, newer)

    def test_wrong_target_teams_no_roster(self):
        with self.assertRaisesRegex(HistoryIntegrityError, "NO_DATE_PRIOR_ROSTER_CANDIDATES"):
            build([make_entry()], team_ids=("espn:team:8", "espn:team:9"))


class P1VaultTest(unittest.TestCase):
    def _put(self, vault, **kw):
        defaults = dict(
            game_id=GAME, player_id="espn:player:7", team_id=TEAMS[0],
            state="PLAYED", minutes=25, stats={"points": 11, "threes": 2},
            source_id="nba_official:summary:target", source_bytes=b"official-source",
            observed_at="2023-02-10T05:00:00Z", official_status="final")
        defaults.update(kw)
        return vault.append(**defaults)

    def test_append_replay_and_duplicate(self):
        with tempfile.TemporaryDirectory() as td:
            vault = OfficialOutcomeVault(td)
            p = self._put(vault)
            self.assertEqual(vault.latest(GAME, "espn:player:7")["content_hash"], p["content_hash"])
            with self.assertRaisesRegex(HistoryIntegrityError, "VAULT_DUPLICATE"):
                self._put(vault)

    def test_correction_chain_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            vault = OfficialOutcomeVault(td)
            p = self._put(vault)
            c = self._put(vault, revision=2, supersedes_sha256=p["content_hash"],
                          observed_at="2023-02-11T05:00:00Z",
                          stats={"points": 12, "threes": 2}, source_bytes=b"correction")
            self.assertEqual(vault.latest(GAME, "espn:player:7")["content_hash"], c["content_hash"])
            self.assertEqual(len(vault.records()), 2)

    def test_backdated_correction_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            vault = OfficialOutcomeVault(td)
            p = self._put(vault)
            with self.assertRaisesRegex(HistoryIntegrityError, "VAULT_CORRECTION_BACKDATED"):
                self._put(vault, revision=2, supersedes_sha256=p["content_hash"],
                          observed_at="2023-02-09T05:00:00Z")

    def test_unresolved_is_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            vault = OfficialOutcomeVault(td)
            self.assertIsNone(vault.latest(GAME, "espn:player:7"))
            with self.assertRaisesRegex(HistoryIntegrityError, "VAULT_NONPARTICIPATION_ZERO_FILL"):
                self._put(vault, state="UNRESOLVED", minutes=0, stats={})
            self._put(vault, state="UNRESOLVED", minutes=None, stats={})
            self.assertIsNone(vault.latest(GAME, "espn:player:8"))

    def test_tamper_detection(self):
        with tempfile.TemporaryDirectory() as td:
            vault = OfficialOutcomeVault(td)
            p = self._put(vault)
            path = Path(td) / (p["content_hash"] + ".json")
            path.write_bytes(path.read_bytes().replace(b"11", b"14", 1))
            with self.assertRaises(ValueError):
                vault.records()


if __name__ == "__main__":
    unittest.main()
