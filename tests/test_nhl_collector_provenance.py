"""Regression tests for NHL identity rejection ledger and roster archival."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

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
                schedule, fetch, archive_root=archive, clock=clock,
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
