"""V25-C02 Phase 0R certification integration across split quote archives."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import fetch_slate as fs
import phase0_pre_eval
from phase0_quote_origin import verified_original_api_quote_lineage
from phase0r_contract import strict_snapshot_status
from test_phase0r_pre_eval import START, build_row, make_inputs
from usage_baseline import key as usage_key, load as load_usage
from usage_baseline import persist as persist_usage


API = "https://api.prop-line.com/v1/sports/americanfootball_nfl/odds"


def propline_quotes():
    return [
        {
            "sport": "NFL",
            "event_id": "event-1",
            "event_id_namespace": "propline",
            "event_start": "2026-11-09T18:00:00Z",
            "player": "Darius Acuff Jr.",
            "player_norm": "darius acuff",
            "team": "BUF",
            "stat": "receptions",
            "book": "Pinnacle",
            "line": 4.5,
            "over_odds": -110,
            "under_odds": -110,
            "retrieved_at": "2026-11-09T14:10:00Z",
            "source_url": API + "?markets=player_receptions&bookmakers=pinnacle",
        }
    ]


class Phase0QuoteCertificationIntegration(unittest.TestCase):
    def _prepare_split_archive(self, root: Path):
        data = root / "collected"
        candidate, _ident = make_inputs(data)
        candidate.update(
            player="Darius Acuff Jr.",
            event_id_namespace="propline",
            books=[{
                "book": "Pinnacle", "line": 4.5, "book_side": "over",
                "target": -110, "other": -110,
                "retrieved_at": "2026-11-09T14:10:00Z",
            }],
        )
        original = propline_quotes()
        resolved, _ = fs.attach_prices([], original)
        (data / "odds_quotes_original.jsonl").write_text(
            "".join(json.dumps(q, sort_keys=True) + "\n" for q in original))
        (data / "odds_quotes.jsonl").write_text(
            "".join(json.dumps(q, sort_keys=True) + "\n" for q in resolved))
        with phase0_pre_eval.pin(
            candidate, data_root=data,
            archive_root=data / "source_archives",
            policy_root=root, clock=lambda: START,
        ) as (evidence, _frozen, frozen_candidate):
            row = build_row(frozen_candidate, evidence)
            row.update(
                player="Darius Acuff Jr.",
                event_id_namespace="propline",
                market={
                    "market_valid": True,
                    "line": 4.5,
                    "retrieved_at": "2026-11-09T14:10:00Z",
                    "books": [{
                        "book": "Pinnacle", "line": 4.5,
                        "over": -110, "under": -110,
                        "retrieved_at": "2026-11-09T14:10:00Z",
                    }],
                },
            )
            return row, data / "source_archives", evidence

    def test_new_split_archive_certifies_and_quote_lineage_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            row, archive, evidence = self._prepare_split_archive(Path(tmp))
            self.assertEqual(
                evidence["model_input_binding"]["market_quote_archive_version"],
                "pickem_market_quote_archive_v1_1",
            )
            ok, reason = strict_snapshot_status(row, archive_root=archive)
            self.assertTrue(ok, reason)
            origin_ok, origin_reason = verified_original_api_quote_lineage(
                row, archive_root=archive)
            self.assertTrue(origin_ok, origin_reason)

    def test_legacy_single_file_archive_still_certifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "collected"
            candidate, _ = make_inputs(data)
            with phase0_pre_eval.pin(
                candidate, data_root=data,
                archive_root=data / "source_archives",
                policy_root=root, clock=lambda: START,
            ) as (evidence, _frozen, frozen_candidate):
                row = build_row(frozen_candidate, evidence)
                ok, reason = strict_snapshot_status(
                    row, archive_root=data / "source_archives")
                self.assertTrue(ok, reason)
                self.assertEqual(
                    evidence["model_input_binding"]["market_quote_archive_version"],
                    "pickem_market_quote_archive_v1",
                )

    def test_tampered_original_quote_bytes_fail_strict_certification(self):
        with tempfile.TemporaryDirectory() as tmp:
            row, archive, _evidence = self._prepare_split_archive(Path(tmp))
            for receipt in row["source_receipts"]:
                if str(receipt.get("archive_path", "")).startswith("original_book_quotes/"):
                    (archive / receipt["archive_path"]).write_bytes(b"tampered")
                    break
            ok, reason = strict_snapshot_status(row, archive_root=archive)
            self.assertFalse(ok)
            self.assertIn("digest", reason)

    def test_stale_tackle_usage_cache_is_rejected_on_load(self):
        ident = usage_key("NFL", "pid-1", "tackles + assists", "2026-11-09")
        row = {
            "sport": "NFL", "player_id": "pid-1", "stat": "tackles + assists",
            "game_date": "2026-11-09", "team": "BUF",
            "source_url": "https://example.test", "retrieved_at": "2026-11-08T12:00:00Z",
            "source_stat_definition_version": "nfl-source-stat-v2-three-component-tackles",
            "usage_observations": [{
                "id": "g1", "date": "2026-11-01", "value": 5,
                "tackle_components": {
                    "def_tackles_solo": 3, "def_tackles_with_assist": 1, "def_tackle_assists": 1,
                },
            }],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            persist_usage([row], root)
            usage_path = root / "usage" / (ident + ".json")
            doc = json.loads(usage_path.read_text())
            doc["tackle_derived_cache_schema"] = "nfl-tackles-assists-derived-v1"
            usage_path.write_text(json.dumps(doc, sort_keys=True))
            candidate = {
                "sport": "NFL", "player_id": "pid-1", "stat": "tackles + assists",
                "game_date": "2026-11-09", "team": "BUF",
                "scouting": {"historical_usage": ident},
            }
            from usage_baseline import using_directory
            with using_directory(root):
                with self.assertRaisesRegex(ValueError, "stale_tackle_usage_cache_requires_rebuild"):
                    load_usage(candidate, datetime(2026, 11, 9, 15, tzinfo=timezone.utc))

    def test_pre_change_v1_binding_without_version_field_still_certifies(self):
        """Legacy frozen snapshot: no market_quote_archive_version key, only odds_quotes.jsonl."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "collected"
            candidate, _ = make_inputs(data)
            with phase0_pre_eval.pin(
                candidate, data_root=data,
                archive_root=data / "source_archives",
                policy_root=root, clock=lambda: START,
            ) as (evidence, _frozen, frozen_candidate):
                row = build_row(frozen_candidate, evidence)
                row["model_input_binding"].pop("market_quote_archive_version", None)
                archive = data / "source_archives"
                ok, reason = strict_snapshot_status(row, archive_root=archive)
                self.assertTrue(ok, reason)

    def test_legacy_two_component_tackle_usage_cannot_acquire_v2_on_persist(self):
        row = {
            "sport": "NFL", "player_id": "lb-1", "stat": "tackles + assists",
            "game_date": "2026-11-09", "team": "BUF",
            "source_url": "https://example.test", "retrieved_at": "2026-11-08T12:00:00Z",
            "usage_observations": [{"id": "g1", "date": "2026-11-01", "value": 6}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "tackle_usage_cache_missing_three_component_evidence"):
                persist_usage([row], Path(tmp))


class NhlCollectorIdentityIntegration(unittest.TestCase):
    def _roster_payload(self, primary_id: int):
        forwards = [{"id": int(primary_id)}]
        forwards.extend({"id": 8800 + i} for i in range(11))
        return {
            "forwards": forwards,
            "defensemen": [{"id": 8701}],
            "goalies": [{"id": 8702}],
        }

    def test_fetch_nhl_live_path_abstains_when_only_former_team_plays(self):
        schedule = {
            "gameWeek": [{
                "date": "2026-11-09",
                "games": [{
                    "awayTeam": {"abbrev": "NJD"},
                    "homeTeam": {"abbrev": "BUF"},
                }],
            }],
        }
        skaters = [{
            "skaterFullName": "Traded Forward",
            "playerId": 9001,
            "teamAbbrevs": "NJD,WPG",
            "gamesPlayed": 10,
            "shots": 20,
            "timeOnIcePerGame": 900,
        }]
        roster_payloads = {
            "WPG": self._roster_payload(9001),
            "NJD": self._roster_payload(9002),
            "BUF": self._roster_payload(9003),
        }

        def fetch_json(url, timeout=30, headers=None):
            if "/schedule/" in url:
                return schedule
            for team, payload in roster_payloads.items():
                if f"/v1/roster/{team}/" in url:
                    return payload
            raise AssertionError(url)

        class Stats:
            def skater_stats_summary(self, **_kwargs):
                return skaters
            def goalie_stats_summary(self, **_kwargs):
                return []
            def team_summary(self, **_kwargs):
                return [{"abbrev": "BUF", "gamesPlayed": 5, "shotsForPerGame": 30,
                         "shotsAgainstPerGame": 30}]

        class Schedule:
            def daily_schedule(self, date=None):
                return schedule

        class Client:
            stats = Stats()
            schedule = Schedule()

        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "collector"
            rows, notes, rejections, _rosters = fs.fetch_nhl(
                "2026-11-09",
                "2026-11-09T15:00:00Z",
                client=Client(),
                fetch=fetch_json,
                collector_archive_root=archive,
            )
        self.assertEqual(rows, [])
        self.assertTrue(any("9001" in json.dumps(item) for item in rejections))
        self.assertIn(
            "nhl_team_idle_current_not_on_slate",
            {item["reason"] for item in rejections},
        )
        self.assertTrue(any("nhl_team_identity_rejections:1" in note for note in notes))

    def test_fetch_nhl_live_path_assigns_current_team_when_both_clubs_play(self):
        schedule = {
            "gameWeek": [{
                "date": "2026-11-09",
                "games": [{
                    "awayTeam": {"abbrev": "NJD"},
                    "homeTeam": {"abbrev": "WPG"},
                }],
            }],
        }
        skaters = [{
            "skaterFullName": "Traded Forward",
            "playerId": 9001,
            "teamAbbrevs": "NJD,WPG",
            "gamesPlayed": 10,
            "shots": 20,
            "timeOnIcePerGame": 900,
        }]

        def fetch_json(url, timeout=30, headers=None):
            if "/schedule/" in url:
                return schedule
            if "/v1/roster/WPG/" in url:
                return self._roster_payload(9001)
            if "/v1/roster/NJD/" in url:
                return self._roster_payload(9002)
            raise AssertionError(url)

        class Stats:
            def skater_stats_summary(self, **_kwargs):
                return skaters
            def goalie_stats_summary(self, **_kwargs):
                return []
            def team_summary(self, **_kwargs):
                return [{"abbrev": "WPG", "gamesPlayed": 5, "shotsForPerGame": 30,
                         "shotsAgainstPerGame": 30}]

        class Schedule:
            def daily_schedule(self, date=None):
                return schedule

        class Client:
            stats = Stats()
            schedule = Schedule()

        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / "collector"
            rows, _notes, rejections, _rosters = fs.fetch_nhl(
                "2026-11-09",
                "2026-11-09T15:00:00Z",
                client=Client(),
                fetch=fetch_json,
                collector_archive_root=archive,
            )
        self.assertEqual(rejections, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["team"], "WPG")


class NhlResolverRegression(unittest.TestCase):
    def roster(self, player_id, teams):
        return {team: {str(player_id)} for team in teams}

    def test_idle_current_team_when_roster_fetch_missing_for_current_club(self):
        roster = self.roster(9001, ("WPG", "NJD"))
        team, reason = fs.resolve_nhl_slate_team(
            "NJD,WPG", {"NJD": "BUF"}, player_id=9001,
            roster_memberships=roster, roster_fetched_teams={"NJD"},
        )
        self.assertIsNone(team)
        self.assertEqual(reason, "nhl_team_roster_evidence_incomplete")

    def test_both_teams_on_slate_one_roster_missing(self):
        team, reason = fs.resolve_nhl_slate_team(
            "NJD,WPG", {"NJD": "WPG", "WPG": "NJD"}, player_id=9001,
            roster_memberships={"WPG": {"9001"}}, roster_fetched_teams={"WPG"},
        )
        self.assertIsNone(team)
        self.assertEqual(reason, "nhl_team_roster_evidence_incomplete")

    def test_player_absent_from_every_retrieved_roster(self):
        team, reason = fs.resolve_nhl_slate_team(
            "NJD,WPG", {"WPG": "NJD", "NJD": "WPG"}, player_id=9001,
            roster_memberships={"WPG": {"2"}, "NJD": {"3"}},
            roster_fetched_teams={"WPG", "NJD"},
        )
        self.assertIsNone(team)
        self.assertEqual(reason, "nhl_team_absent_from_verified_rosters")

    def test_player_on_exactly_one_verified_roster(self):
        team, reason = fs.resolve_nhl_slate_team(
            "NJD,WPG", {"WPG": "NJD", "NJD": "WPG"}, player_id=9001,
            roster_memberships={"WPG": {"9001"}, "NJD": {"2"}},
            roster_fetched_teams={"WPG", "NJD"},
        )
        self.assertIsNone(reason)
        self.assertEqual(team, "WPG")

    def test_historical_collector_single_team_string(self):
        team, reason = fs.resolve_nhl_slate_team(
            "BOS", {"BOS": "NSH"}, identity_mode="historical_collector",
        )
        self.assertEqual((team, reason), ("BOS", None))


if __name__ == "__main__":
    unittest.main()
