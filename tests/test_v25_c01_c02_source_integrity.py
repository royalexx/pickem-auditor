"""V25-C01/C02 mandatory regression tests for source integrity repairs."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import fetch_slate as fs
import nfl_stat_definitions as definitions
import odds_providers as op
import settle
from reform_step11_release_audit import inspect_release


FROZEN_ARCHIVE_SAMPLE = ROOT / "tests" / "fixtures" / "nhl_skaters.json"


class C01NflTacklesTests(unittest.TestCase):
    def test_mandatory_synthetic_row_is_nine_not_six(self):
        row = dict(def_tackles_solo=4, def_tackles_with_assist=3, def_tackle_assists=2)
        self.assertEqual(definitions.strict_source_stat(row, "tackles + assists").value, 9)
        result = definitions.reconcile(row, ("tackles + assists",))[0]
        self.assertEqual(result["legacy_source_formula_value"], 6)
        self.assertEqual(result["strict_minus_legacy"], 3)

    def test_mandatory_missing_each_component_is_unavailable(self):
        complete = dict(def_tackles_solo=1, def_tackles_with_assist=1, def_tackle_assists=1)
        for key in complete:
            row = dict(complete)
            del row[key]
            self.assertEqual(
                definitions.strict_source_stat(row, "tackles + assists").status,
                "unavailable",
            )

    def test_mandatory_all_zero_is_observed_zero(self):
        row = dict(def_tackles_solo=0, def_tackles_with_assist=0, def_tackle_assists=0)
        self.assertEqual(definitions.combined_tackles_assists(row), 0)

    def test_mandatory_collector_and_settler_use_same_definition(self):
        row = dict(
            player="P",
            player_id="p",
            team="T",
            season=2026,
            week=8,
            def_tackles_solo=4,
            def_tackles_with_assist=3,
            def_tackle_assists=2,
        )
        games = [dict(
            game_id="g", gameday="2026-10-25", game_type="REG", season=2026, week=8,
            home_team="T", away_team="X", result=1,
        )]
        collector_total = definitions.combined_tackles_assists(row)
        self.assertEqual(
            settle._nfl_value([row], games, "P", "tackles + assists", "2026-10-25"),
            float(collector_total),
        )
        game_rows = [row]
        self.assertEqual(fs._game_stat(game_rows, None), float(collector_total))

    def test_mandatory_frozen_fixture_bytes_unchanged(self):
        before = FROZEN_ARCHIVE_SAMPLE.read_bytes()
        digest = hashlib.sha256(before).hexdigest()
        self.assertEqual(digest, "bc6e7694bbc47b10beb7a647fc271a40061757821556025641be279ba0157cea")
        _ = json.loads(before.decode())
        self.assertEqual(FROZEN_ARCHIVE_SAMPLE.read_bytes(), before)


class C02NhlIdentityAndQuoteProvenanceTests(unittest.TestCase):
    def roster(self):
        return {
            "WPG": {"9001"},
            "NJD": {"9002"},
        }

    def slate_wpg_njd(self):
        return {"WPG": "NJD", "NJD": "WPG"}

    def slate_njd_only(self):
        return {"NJD": "BUF", "BUF": "NJD"}

    def test_mandatory_traded_player_current_team_when_both_play(self):
        roster = self.roster()
        team, reason = fs.resolve_nhl_slate_team(
            "NJD,WPG", self.slate_wpg_njd(), player_id=9001,
            roster_memberships=roster, roster_fetched_teams=set(roster),
        )
        self.assertIsNone(reason)
        self.assertEqual(team, "WPG")
        wrong, _ = fs.resolve_nhl_slate_team(
            "NJD,WPG", self.slate_wpg_njd(), player_id=9001,
        )
        self.assertIsNone(wrong)

    def test_mandatory_idle_current_team_abstains(self):
        roster = self.roster()
        team, reason = fs.resolve_nhl_slate_team(
            "NJD,WPG", self.slate_njd_only(), player_id=9001,
            roster_memberships=roster, roster_fetched_teams=set(roster),
        )
        self.assertIsNone(team)
        self.assertEqual(reason, "nhl_team_idle_current_not_on_slate")

    def test_mandatory_ambiguous_without_roster_abstains(self):
        team, reason = fs.resolve_nhl_slate_team("NJD,WPG", self.slate_wpg_njd(), player_id=9001)
        self.assertIsNone(team)
        self.assertEqual(reason, "nhl_team_roster_evidence_incomplete")

    def test_mandatory_pregame_single_team_requires_player_id(self):
        roster = {"BOS": {"42"}}
        team, reason = fs.resolve_nhl_slate_team(
            "BOS", {"BOS": "NSH", "NSH": "BOS"},
            roster_memberships=roster, roster_fetched_teams=set(roster),
        )
        self.assertIsNone(team)
        self.assertEqual(reason, "nhl_team_player_id_required_for_pregame_identity")

    def test_mandatory_blank_provider_team_stays_in_original_archive(self):
        quotes = op.provider_quote_snapshot([
            dict(sport="NHL", player="Example", team="", stat="shots on goal", book="FanDuel", line=2.5),
        ])
        self.assertEqual(quotes[0]["team"], "")
        resolved, _ = op.resolve_quote_teams(quotes, [])
        self.assertEqual(resolved[0]["provider_team"], "")
        self.assertNotIn("team_resolution_provenance", resolved[0])

    def test_mandatory_inference_provenance_does_not_overwrite_provider_team(self):
        rows = [dict(sport="NHL", player="Alex Smith", team="BOS", opponent="NSH", stat="shots on goal")]
        quotes = op.provider_quote_snapshot([
            dict(sport="NHL", player="Alex Smith", team="", stat="shots on goal", book="FanDuel", line=2.5),
        ])
        resolved, _ = op.resolve_quote_teams(quotes, rows)
        item = resolved[0]
        self.assertEqual(item["provider_team"], "")
        self.assertEqual(item["team"], "BOS")
        self.assertEqual(item["team_resolution_provenance"]["schema"], op.QUOTE_PROVENANCE_SCHEMA)

    def test_mandatory_altered_quote_archive_bytes_detected(self):
        quotes = [dict(sport="NHL", player="X", team="BOS", stat="shots on goal", book="FanDuel", line=1.5)]
        digest = op.quote_payload_digest(quotes)
        tampered = copy.deepcopy(quotes)
        tampered[0]["team"] = "NSH"
        self.assertNotEqual(op.quote_payload_digest(tampered), digest)

    def test_mandatory_legacy_quotes_without_provenance_still_resolve(self):
        legacy = [dict(sport="NBA", player="Test Player", team="MEM", stat="points", book="FanDuel", line=10.5)]
        rows = [dict(sport="NBA", player="Test Player", team="MEM", opponent="LAL", stat="points")]
        resolved, unmatched = op.resolve_quote_teams(legacy, rows)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["team"], "MEM")
        self.assertIsNone(resolved[0].get("team_resolution_provenance"))
        self.assertEqual(unmatched, [])


class C01ReleaseAuditSmoke(unittest.TestCase):
    def test_release_audit_verifies_collector_and_settlement_paths(self):
        result = inspect_release(ROOT)
        self.assertTrue(result["full_source_stat_combined_nfl_tackles_verified"])


class C02Phase0QuoteArchiveSeparation(unittest.TestCase):
    def test_phase0_pins_original_and_derived_quotes_separately(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "archive"
            archive.mkdir()
            original = (
                '{"sport":"NHL","player":"A","team":"","stat":"shots on goal","book":"FD","line":1.5}\n'
            )
            derived = (
                '{"sport":"NHL","player":"A","team":"BOS","provider_team":"",'
                '"stat":"shots on goal","book":"FD","line":1.5,'
                f'"team_resolution_provenance":{{"schema":"{op.QUOTE_PROVENANCE_SCHEMA}"}}}}\n'
            )
            (root / "odds_quotes_original.jsonl").write_text(original)
            (root / "odds_quotes.jsonl").write_text(derived)
            from usage_baseline import key as usage_key
            (root / "usage").mkdir()
            ident = usage_key("NHL", "1", "shots on goal", "2026-11-08")
            (root / "usage" / (ident + ".json")).write_text(json.dumps({
                "retrieved_at": "2026-11-08T12:00:00Z",
                "source_url": "https://example.test/usage",
            }))
            candidate = dict(
                sport="NHL", player_id="1", stat="shots on goal", game_date="2026-11-08", team="BOS",
            )
            from datetime import datetime, timezone
            from phase0_pre_eval import pin
            clock = lambda: datetime(2026, 11, 8, 14, 0, tzinfo=timezone.utc)
            with pin(candidate, data_root=root, archive_root=archive, policy_root=ROOT, clock=clock) as (evidence, *_):
                roles = {item["archive_path"].split("/", 1)[0] for item in evidence["source_receipts"]}
            self.assertIn("original_book_quotes", roles)
            self.assertIn("collector_resolved_book_quotes", roles)


if __name__ == "__main__":
    unittest.main()
