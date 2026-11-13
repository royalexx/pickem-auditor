"""Regression tests for NHL identity rejection ledger and roster archival."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_slate as fs

NOW = "2026-11-09T15:00:00Z"


def _nhl_fetcher(*, rows, rejections, roster_receipts=None, failed=False):
    roster_receipts = roster_receipts or []

    def nhl():
        if failed:
            return [], ["nhl: upstream empty"], [], {
                "identity_rejections": rejections,
                "roster_receipts": roster_receipts,
            }
        return rows, [], [], {
            "identity_rejections": rejections,
            "roster_receipts": roster_receipts,
        }

    return nhl


def _stub_row(player="Forward", player_id="1"):
    return {
        "sport": "NHL",
        "player": player,
        "player_id": player_id,
        "team": "BOS",
        "opponent": "NSH",
        "stat": "shots on goal",
        "game_date": "2026-11-09",
    }


class NhlIdentityLedgerPersistence(unittest.TestCase):
    def _collect_commit(self, tmp: Path, *, nhl_rows, rejections, nhl_failed=False):
        out = tmp / "slate_fetch.jsonl"
        quotes = tmp / "odds_quotes.jsonl"
        rejection = {
            "sport": "NHL",
            "kind": "skater",
            "player_id": "9001",
            "player": "Traded Skater",
            "teamAbbrevs": "NJD,WPG",
            "reason": "nhl_team_idle_current_not_on_slate",
        }
        if rejections is True:
            rejections = [rejection]
        else:
            rejections = list(rejections)
        fetchers = {
            "nhl": _nhl_fetcher(rows=nhl_rows, rejections=rejections, failed=nhl_failed),
            "nfl": lambda: ([], None),
            "nba": lambda: ([], None),
            "odds": lambda: ([], None),
        }
        _rows, summary = fs.collect(
            "2026-11-09",
            retrieved_at=NOW,
            fetchers=fetchers,
            clock=lambda: NOW,
            quotes_path=quotes,
        )
        code = fs.commit_slate(_rows, summary, out, clock=lambda: NOW)
        meta = json.loads(fs.meta_path_for(out).read_text(encoding="utf-8"))
        return code, summary, meta, out

    def test_successful_slate_persists_rejected_players(self):
        with tempfile.TemporaryDirectory() as folder:
            code, summary, meta, out = self._collect_commit(
                Path(folder),
                nhl_rows=[_stub_row()],
                rejections=True,
            )
            self.assertEqual(code, 0)
            self.assertIn("nhl_identity_ledger", meta)
            self.assertEqual(meta["feeds"]["nhl"]["identity_rejection_count"], 1)
            ledger = fs.load_nhl_identity_ledger(meta)
            self.assertEqual(ledger["schema"], fs.NHL_IDENTITY_LEDGER_SCHEMA)
            self.assertEqual(ledger["denominators"]["rejected_players"], 1)
            self.assertEqual(ledger["rejections"][0]["reason"], "nhl_team_idle_current_not_on_slate")
            artifact = fs.resolve_nhl_identity_ledger_path(meta["nhl_identity_ledger"])
            self.assertTrue(artifact.is_file())
            self.assertEqual(ledger["collector_run"]["slate_out"], str(out))

    def test_mixed_accepted_and_rejected_players(self):
        with tempfile.TemporaryDirectory() as folder:
            code, summary, meta, _out = self._collect_commit(
                Path(folder),
                nhl_rows=[_stub_row(), _stub_row(player="Other", player_id="2")],
                rejections=True,
            )
            self.assertEqual(code, 0)
            ledger = fs.load_nhl_identity_ledger(meta)
            self.assertEqual(ledger["denominators"]["accepted_nhl_rows"], 2)
            self.assertEqual(ledger["denominators"]["rejected_players"], 1)

    def test_failed_nhl_feed_still_writes_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            code, _summary, meta, out = self._collect_commit(
                Path(folder), nhl_rows=[], rejections=[], nhl_failed=True,
            )
            self.assertEqual(code, 2)
            self.assertEqual(meta["feeds"]["nhl"]["status"], "failed")
            ledger = fs.load_nhl_identity_ledger(meta)
            self.assertIsNotNone(ledger)
            self.assertEqual(ledger["collector_run"]["nhl_feed_status"], "failed")
            self.assertFalse(out.exists())

    def test_meta_roundtrip_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            _code, _summary, meta, _out = self._collect_commit(
                Path(folder), nhl_rows=[_stub_row()], rejections=True,
            )
            meta_path = fs.meta_path_for(_out)
            reloaded = json.loads(meta_path.read_text(encoding="utf-8"))
            self.assertEqual(reloaded["nhl_identity_ledger"], meta["nhl_identity_ledger"])
            ledger = fs.load_nhl_identity_ledger(reloaded)
            self.assertEqual(len(ledger["rejections"]), 1)


class NhlIdentityLedgerImmutability(unittest.TestCase):
    def _minimal_summary(self, tmp: Path, *, rejection_reason: str):
        out = tmp / "slate_fetch.jsonl"
        rejection = {
            "sport": "NHL",
            "kind": "skater",
            "player_id": "9001",
            "reason": rejection_reason,
        }
        return {
            "date": "2026-11-09",
            "retrieved_at": NOW,
            "feeds": {
                "nhl": {
                    "status": "ok",
                    "rows": 1,
                    "started_at": NOW,
                    "finished_at": NOW,
                    "identity_rejections": [rejection],
                    "roster_receipts": [],
                },
            },
        }, out

    def test_two_runs_preserve_both_content_addressed_ledgers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            summary_a, out = self._minimal_summary(root, rejection_reason="reason_a")
            ref_a = fs.persist_nhl_identity_ledger(out, summary_a, clock=lambda: NOW)
            meta_a = {"nhl_identity_ledger": ref_a}
            summary_b, _out = self._minimal_summary(root, rejection_reason="reason_b")
            ref_b = fs.persist_nhl_identity_ledger(out, summary_b, clock=lambda: "2026-11-09T16:00:00Z")
            self.assertNotEqual(ref_a["content_sha256"], ref_b["content_sha256"])
            ledger_a = fs.load_nhl_identity_ledger(meta_a, base=root)
            ledger_b = fs.load_nhl_identity_ledger({"nhl_identity_ledger": ref_b}, base=root)
            self.assertEqual(ledger_a["rejections"][0]["reason"], "reason_a")
            self.assertEqual(ledger_b["rejections"][0]["reason"], "reason_b")
            path_a = fs.resolve_nhl_identity_ledger_path(ref_a, base=root)
            path_b = fs.resolve_nhl_identity_ledger_path(ref_b, base=root)
            self.assertTrue(path_a.is_file() and path_b.is_file())
            self.assertNotEqual(path_a, path_b)

    def test_identical_content_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            summary, out = self._minimal_summary(root, rejection_reason="same")
            ref1 = fs.persist_nhl_identity_ledger(out, summary, clock=lambda: NOW)
            summary2 = copy.deepcopy(summary)
            ref2 = fs.persist_nhl_identity_ledger(out, summary2, clock=lambda: NOW)
            self.assertEqual(ref1["content_sha256"], ref2["content_sha256"])
            self.assertEqual(ref1["archive_path"], ref2["archive_path"])

    def test_tampered_ledger_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            summary, out = self._minimal_summary(root, rejection_reason="tamper_me")
            ref = fs.persist_nhl_identity_ledger(out, summary, clock=lambda: NOW)
            path = fs.resolve_nhl_identity_ledger_path(ref, base=root)
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "nhl_identity_ledger_digest_mismatch"):
                fs.load_nhl_identity_ledger({"nhl_identity_ledger": ref}, base=root)

    def test_missing_referenced_artifact_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            summary, out = self._minimal_summary(root, rejection_reason="gone")
            ref = fs.persist_nhl_identity_ledger(out, summary, clock=lambda: NOW)
            path = fs.resolve_nhl_identity_ledger_path(ref, base=root)
            path.unlink()
            with self.assertRaisesRegex(ValueError, "nhl_identity_ledger_archive_missing"):
                fs.load_nhl_identity_ledger({"nhl_identity_ledger": ref}, base=root)

    def test_conflicting_bytes_at_digest_path_raises(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive_root = fs.nhl_identity_ledger_archive_root(root / "slate_fetch.jsonl")
            archive_root.mkdir(parents=True)
            ledger = {"schema": fs.NHL_IDENTITY_LEDGER_SCHEMA, "k": "v"}
            raw = fs._canonical_identity_ledger_bytes(ledger)
            import hashlib
            digest = hashlib.sha256(raw).hexdigest()
            target = archive_root / f"nhl_identity_rejections/{digest}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"not-the-ledger")
            with self.assertRaisesRegex(ValueError, "nhl_identity_ledger_archive_conflict"):
                fs._write_immutable_collector_json(
                    archive_root, fs.NHL_IDENTITY_LEDGER_ARCHIVE_ROLE, ledger,
                )


class NhlRosterArchiveIntegrity(unittest.TestCase):
    @staticmethod
    def _roster_payload(player_id: int):
        forwards = [{"id": int(player_id)}]
        forwards.extend({"id": 8800 + i} for i in range(11))
        return {
            "forwards": forwards,
            "defensemen": [{"id": 8701}],
            "goalies": [{"id": 8702}],
        }

    def test_roster_receipt_archives_canonical_json_and_reports_representation(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "collector"
            payload = self._roster_payload(9001)
            times = iter(["2026-11-09T15:00:01Z", "2026-11-09T15:00:02Z", "2026-11-09T15:00:03Z"])

            def fetch(_url):
                return payload

            def clock():
                return next(times)

            schedule = [{
                "awayTeam": {"abbrev": "WPG"},
                "homeTeam": {"abbrev": "NJD"},
            }]
            _memberships, _notes, _fetched, receipts = fs.nhl_pregame_roster_memberships(
                schedule,
                fetch,
                archive_root=archive,
                clock=clock,
                require_archived_membership=True,
            )
            self.assertEqual(len(receipts), 2)
            receipt = receipts[0]
            self.assertEqual(
                receipt["byte_representation"],
                "canonical_json_not_raw_http_bytes",
            )
            self.assertTrue(receipt.get("archive_path"))
            blob = archive / receipt["archive_path"]
            self.assertTrue(blob.is_file())
            self.assertEqual(receipt["retrieved_at"], receipt["observed_at"])
            self.assertTrue(receipt["membership_only_not_starter_certified"])

    def test_archive_failure_leaves_no_verified_membership(self):
        payload = self._roster_payload(9001)
        schedule = [{"awayTeam": {"abbrev": "WPG"}, "homeTeam": {"abbrev": "NJD"}}]
        def fetch(_url):
            return payload

        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "collector"
            with patch("phase0_input_capture.preserve", side_effect=ValueError("archive write refused")):
                memberships, notes, fetched, receipts = fs.nhl_pregame_roster_memberships(
                    schedule,
                    fetch,
                    archive_root=archive,
                    clock=lambda: NOW,
                    require_archived_membership=True,
                )
        self.assertEqual(memberships, {})
        self.assertEqual(fetched, set())
        self.assertEqual(receipts, [])
        self.assertTrue(any("unavailable" in note for note in notes))

    def test_no_archive_root_cannot_certify_membership(self):
        payload = self._roster_payload(9001)
        schedule = [{"awayTeam": {"abbrev": "WPG"}, "homeTeam": {"abbrev": "NJD"}}]

        memberships, notes, fetched, receipts = fs.nhl_pregame_roster_memberships(
            schedule,
            lambda _url: payload,
            archive_root=None,
            clock=lambda: NOW,
            require_archived_membership=True,
        )
        self.assertEqual(memberships, {})
        self.assertEqual(fetched, set())
        self.assertTrue(any("research_only_no_archive_root" in note for note in notes))

    def test_successful_archive_allows_membership_and_digest_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "collector"
            payload = self._roster_payload(9001)
            schedule = [{"awayTeam": {"abbrev": "WPG"}, "homeTeam": {"abbrev": "NJD"}}]
            memberships, _notes, fetched, receipts = fs.nhl_pregame_roster_memberships(
                schedule,
                lambda _url: payload,
                archive_root=archive,
                clock=lambda: NOW,
                require_archived_membership=True,
            )
            self.assertIn("WPG", memberships)
            self.assertIn("NJD", memberships)
            self.assertEqual(fetched, {"NJD", "WPG"})
            blob = archive / receipts[0]["archive_path"]
            import hashlib
            self.assertEqual(hashlib.sha256(blob.read_bytes()).hexdigest(), receipts[0]["content_sha256"])


class NhlPregamePlayerIdentity(unittest.TestCase):
    def test_single_team_pregame_requires_player_id(self):
        slate = {"BOS": "NSH", "NSH": "BOS"}
        roster = {"BOS": {"42"}, "NSH": {"99"}}
        team, reason = fs.resolve_nhl_slate_team(
            "BOS", slate, roster_memberships=roster, roster_fetched_teams=set(roster),
        )
        self.assertIsNone(team)
        self.assertEqual(reason, "nhl_team_player_id_required_for_pregame_identity")


if __name__ == "__main__":
    unittest.main()
