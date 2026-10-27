"""Offline tests for the slate fetch parser and flag rule."""

import io
import json
import sys
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "tests"))
sys.path.insert(0, str(SKILL_DIR / "scripts"))
from skill_docs import skill_corpus
import fetch_slate as fs
import odds_providers as op

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_json(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def load_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class FlagRuleTests(unittest.TestCase):
    def test_pace_above_the_clamp_is_the_pace_channel(self):
        at_clamp = fs.serious_flag("shots on goal", 3.0, None, 1.10, 1.0, None)
        self.assertFalse(at_clamp["flag"])
        above = fs.serious_flag("shots on goal", 3.0, None, 1.11, 1.0, None)
        self.assertTrue(above["flag"])
        self.assertEqual(above["channel"], "pace")
        self.assertEqual(above["flag_reasons"], ["pace_above_league"])

    def test_shots_against_above_the_clamp_is_opponent_environment(self):
        at_clamp = fs.serious_flag("goalie saves", 25.0, None, None, 1.15, None)
        self.assertFalse(at_clamp["flag"])
        above = fs.serious_flag("goalie saves", 25.0, None, None, 1.16, None)
        self.assertTrue(above["flag"])
        self.assertEqual(above["channel"], "opponent environment")

    def test_two_pace_facts_do_not_invent_a_second_channel(self):
        decision = fs.serious_flag("receptions", 5.0, None, 1.20, None, 0.90)
        self.assertIn("pace_above_league", decision["flag_reasons"])
        self.assertIn("large_snap_share", decision["flag_reasons"])
        self.assertEqual(decision["channel"], "pace")
        self.assertNotEqual(decision["channel"], "opponent environment")

    def test_large_snap_share_flags_without_becoming_a_channel(self):
        thin = fs.serious_flag("tackles + assists", 8.0, None, None, None, 0.79)
        self.assertFalse(thin["flag"])
        large = fs.serious_flag("tackles + assists", 8.0, None, None, None, 0.80)
        self.assertTrue(large["flag"])
        self.assertIsNone(large["channel"])
        self.assertEqual(large["flag_reasons"], ["large_snap_share"])

    def test_line_gaps_use_the_skill_distances(self):
        self.assertFalse(fs.line_gap_is_serious("shots on goal", 3.0, 2.6))
        self.assertTrue(fs.line_gap_is_serious("shots on goal", 3.0, 2.5))
        self.assertFalse(fs.line_gap_is_serious("points", 22.0, 20.1))
        self.assertTrue(fs.line_gap_is_serious("points", 22.0, 20.0))
        self.assertTrue(fs.line_gap_is_serious("pra", 30.0, 28.0))
        self.assertFalse(fs.line_gap_is_serious("receiving yards", 60.0, 52.1))
        self.assertTrue(fs.line_gap_is_serious("receiving yards", 60.0, 52.0))
        self.assertTrue(fs.line_gap_is_serious("rushing yards", 80.0, 70.0))
        self.assertFalse(fs.line_gap_is_serious("passing yards", 250.0, 235.1))
        self.assertTrue(fs.line_gap_is_serious("passing yards", 250.0, 235.0))
        gap_only = fs.serious_flag("receptions", 6.0, 5.0, None, None, None)
        self.assertTrue(gap_only["flag"])
        self.assertIsNone(gap_only["channel"])

    def test_both_rate_channels_keep_both_reasons(self):
        decision = fs.serious_flag("shots on goal", 3.0, None, 1.20, 1.20, None)
        self.assertEqual(decision["flag_reasons"], ["pace_above_league", "shots_against_above_league"])
        self.assertEqual(decision["channel"], "pace")


class NhlParserTests(unittest.TestCase):
    def test_schedule_and_summaries_build_slate_rows(self):
        rows = fs.nhl_rows_from_summaries(
            fs.games_from_schedule(load_json("nhl_schedule.json"), "2026-10-22"),
            load_json("nhl_skaters.json"),
            load_json("nhl_goalies.json"),
            load_json("nhl_teams.json"),
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NHL_STATS_SKATER,
        )
        names = [row["player"] for row in rows]
        self.assertIn("Example Bruins Wing", names)
        self.assertNotIn("Other League Wing", names)
        wing = next(row for row in rows if row["player"] == "Example Bruins Wing")
        self.assertEqual(wing["sport"], "NHL")
        self.assertEqual(wing["team"], "BOS")
        self.assertEqual(wing["opponent"], "NSH")
        self.assertEqual(wing["stat"], "shots on goal")
        self.assertAlmostEqual(wing["baseline_mean"], 3.0)
        self.assertEqual(wing["sample_size"], 10)
        self.assertEqual(wing["funnel_rate_name"], "shots_against")
        self.assertAlmostEqual(wing["funnel_rate"], 30.0)
        self.assertAlmostEqual(wing["ice_time_per_game"], 20.0)
        self.assertNotIn("teammate_splits", wing)
        self.assertTrue(wing["flag"])
        self.assertIn("pace_above_league", wing["flag_reasons"])
        self.assertIn("shots_against_above_league", wing["flag_reasons"])
        self.assertIsNone(wing["book"])
        self.assertIsNone(wing["line"])
        self.assertNotIn("graded", wing)
        self.assertNotIn("q_grade", wing)
        goalie = next(row for row in rows if row["stat"] == "goalie saves")
        self.assertEqual(goalie["player"], "Example Bruins Goalie")
        self.assertEqual(goalie["games_started"], 8)
        self.assertAlmostEqual(goalie["baseline_mean"], 25.0)

    def test_weekly_schedule_shape_and_club_stats_fallback(self):
        weekly = {
            "gameWeek": [
                {"date": "2026-10-21", "games": []},
                load_json("nhl_schedule.json")["games"] and {
                    "date": "2026-10-22",
                    "games": load_json("nhl_schedule.json")["games"],
                },
            ]
        }
        self.assertEqual(len(fs.games_from_schedule(weekly, "2026-10-22")), 1)
        skaters, goalies, team = fs.club_stats_to_summaries(load_json("nhl_club_stats.json"), "BOS")
        self.assertEqual(skaters[0]["skaterFullName"], "Club Skater")
        self.assertEqual(skaters[0]["timeOnIcePerGame"], 18 * 60 + 30)
        self.assertEqual(goalies[0]["gamesStarted"], 3)
        self.assertAlmostEqual(team["shotsAgainstPerGame"], 110 / 4)

    def test_failed_client_call_uses_urllib_for_that_call_only(self):
        class BoomSchedule:
            def daily_schedule(self, date=None):
                raise RuntimeError("schedule down")

        class Client:
            schedule = BoomSchedule()

        fetched = []

        def fake_fetch(url, timeout=30, headers=None):
            fetched.append(url)
            if url.endswith("/schedule/2026-10-22"):
                return load_json("nhl_schedule.json")
            raise RuntimeError("not this call")

        payload, note = fs._call_nhl(
            Client(),
            "schedule.daily_schedule",
            lambda: Client().schedule.daily_schedule(date="2026-10-22"),
            lambda: fake_fetch("https://api-web.nhle.com/v1/schedule/2026-10-22"),
        )
        self.assertEqual(payload["date"], "2026-10-22")
        self.assertIn("urllib", note)
        self.assertEqual(fetched, ["https://api-web.nhle.com/v1/schedule/2026-10-22"])


class NflParserTests(unittest.TestCase):
    def rows(self):
        return fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            fs.read_csv(load_text("nfl_stats.csv")),
            fs.read_csv(load_text("nfl_snaps.csv")),
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "https://example.test/stats.csv",
        )

    def test_slate_players_means_and_flags(self):
        rows = self.rows()
        players = {row["player"] for row in rows}
        self.assertIn("Example Receiver", players)
        self.assertIn("Example Back", players)
        self.assertIn("Example Linebacker", players)
        self.assertNotIn("Example Kicker", players)
        self.assertNotIn("Other Week Player", players)
        receiver = next(row for row in rows if row["player"] == "Example Receiver" and row["stat"] == "receptions")
        self.assertEqual(receiver["team"], "NE")
        self.assertEqual(receiver["opponent"], "CHI")
        self.assertAlmostEqual(receiver["baseline_mean"], 5.0)
        self.assertEqual(receiver["sample_size"], 6)
        self.assertEqual(receiver["funnel_rate_name"], "target_share")
        self.assertAlmostEqual(receiver["target_share"], 0.32)
        self.assertGreater(receiver["pace_ratio"], 1.10)
        self.assertGreaterEqual(receiver["snap_share"], 0.80)
        self.assertAlmostEqual(receiver["offense_snaps_per_game"], 70.0)
        self.assertAlmostEqual(receiver["defense_snaps_per_game"], 0.0)
        self.assertIsNone(receiver["teammate_splits"])
        self.assertNotIn("routes_per_game", receiver)
        self.assertNotIn("route_share", receiver)
        self.assertNotIn("alignment", receiver)
        self.assertNotIn("workload_ratio", receiver)
        self.assertTrue(receiver["flag"])
        self.assertEqual(receiver["channel"], "pace")
        yards = next(row for row in rows if row["player"] == "Example Receiver" and row["stat"] == "receiving yards")
        self.assertAlmostEqual(yards["baseline_mean"], 60.0)
        tackles = next(row for row in rows if row["player"] == "Example Linebacker" and row["stat"] == "tackles + assists")
        self.assertAlmostEqual(tackles["baseline_mean"], 10.0)
        self.assertAlmostEqual(tackles["defense_snaps_per_game"], 60.0)
        back = next(row for row in rows if row["player"] == "Example Back" and row["stat"] == "rush attempts")
        self.assertEqual(back["team"], "CHI")
        self.assertEqual(back["opponent"], "NE")
        self.assertFalse(back["flag"])
        self.assertIsNone(back["channel"])
        self.assertIsNone(back["snap_share"])
        self.assertNotIn("offense_snaps_per_game", back)


class NbaAndOddsTests(unittest.TestCase):
    def test_nba_parser_keeps_slate_teams_only(self):
        scoreboard = load_json("nba_scoreboard.json")
        matchups = fs.matchups_from_scoreboard(scoreboard)
        self.assertEqual(matchups, {"BOS": "NYK", "NYK": "BOS"})
        rows = fs.nba_rows_from_stats(
            load_json("nba_stats.json"),
            matchups,
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NBA_SOURCE,
        )
        players = {row["player"] for row in rows}
        self.assertEqual(players, {"Example Wing"})
        by_stat = {row["stat"]: row for row in rows if row["player"] == "Example Wing"}
        self.assertEqual(set(by_stat), {"points", "rebounds", "assists", "threes"})
        self.assertAlmostEqual(by_stat["points"]["baseline_mean"], 22.5)
        self.assertAlmostEqual(by_stat["rebounds"]["baseline_mean"], 6.0)
        self.assertAlmostEqual(by_stat["assists"]["baseline_mean"], 4.0)
        self.assertAlmostEqual(by_stat["threes"]["baseline_mean"], 3.1)
        points = by_stat["points"]
        self.assertEqual(points["sample_size"], 10)
        self.assertEqual(points["team"], "BOS")
        self.assertEqual(points["opponent"], "NYK")
        self.assertAlmostEqual(points["minutes"], 34.5)
        self.assertNotIn("teammate_splits", points)
        self.assertEqual(points["source_url"], fs.NBA_SOURCE)
        self.assertIsNone(points["book"])
        self.assertIsNone(points["line"])
        self.assertIsNone(points["over_odds"])
        self.assertIsNone(points["under_odds"])

    def test_missing_average_name_skips_that_stat_only(self):
        payload = {
            "categories": [
                {"name": "general", "names": ["gamesPlayed", "avgMinutes", "avgRebounds"]},
                {"name": "offensive", "names": ["avgPoints", "avgAssists"]},
            ],
            "athletes": [
                {
                    "athlete": {
                        "displayName": "Example Wing",
                        "teamId": "2",
                        "teams": [{"id": "2", "abbreviation": "BOS"}],
                    },
                    "categories": [
                        {"name": "general", "values": [8, 30.0]},
                        {"name": "offensive", "values": [19.0, 5.0]},
                    ],
                }
            ],
        }
        rows = fs.nba_rows_from_stats(
            payload,
            {"BOS": "NYK", "NYK": "BOS"},
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NBA_SOURCE,
        )
        stats = {row["stat"] for row in rows}
        self.assertEqual(stats, {"points", "assists"})
        self.assertAlmostEqual(rows[0]["minutes"], 30.0)
        self.assertIsNone(rows[0]["pace_per_game"])

    def test_espn_abbreviation_joins_league_dash_pace(self):
        payload = {
            "categories": [
                {"name": "general", "names": ["gamesPlayed", "avgMinutes", "avgRebounds"]},
                {"name": "offensive", "names": ["avgPoints", "avgAssists", "avgThreePointFieldGoalsMade"]},
            ],
            "athletes": [
                {
                    "athlete": {
                        "displayName": "Example Guard",
                        "teamId": "9",
                        "teamShortName": "GS",
                        "teams": [{"id": "9", "abbreviation": "GS"}],
                    },
                    "categories": [
                        {"name": "general", "values": [4, 32.0, 4.0]},
                        {"name": "offensive", "values": [21.0, 6.0, 4.0]},
                    ],
                }
            ],
        }
        scoreboard = {
            "events": [
                {
                    "competitions": [
                        {
                            "odds": [{"overUnder": 230.5, "provider": {"name": "DraftKings"}}],
                            "competitors": [
                                {"homeAway": "home", "team": {"abbreviation": "LAL"}},
                                {"homeAway": "away", "team": {"abbreviation": "GS"}},
                            ],
                        }
                    ]
                }
            ]
        }
        rows = fs.nba_rows_from_stats(
            payload,
            fs.matchups_from_scoreboard(scoreboard),
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NBA_SOURCE,
            {"GSW": {"pace": 103.5, "possessions": 101.0}, "LAL": {"pace": 98.0, "possessions": 97.0}},
        )
        points = next(row for row in rows if row["stat"] == "points")
        self.assertEqual(points["team"], "GSW")
        self.assertEqual(points["opponent"], "LAL")
        self.assertAlmostEqual(points["pace_per_game"], 103.5)
        self.assertAlmostEqual(points["possessions"], 101.0)
        self.assertIsNone(points["line"])

    def test_pace_table_prefers_pace_then_estimated_pace(self):
        table = fs.team_pace_table(
            {
                "resultSets": [
                    {
                        "headers": ["TEAM_ABBREVIATION", "PACE", "E_PACE", "POSS"],
                        "rowSet": [
                            ["BOS", 112.0, 108.0, 102.0],
                            ["NYK", None, 100.0, 99.0],
                        ],
                    }
                ]
            }
        )
        self.assertEqual(table["BOS"]["pace"], 112.0)
        self.assertEqual(table["BOS"]["possessions"], 102.0)
        self.assertEqual(table["NYK"]["pace"], 100.0)
        self.assertEqual(table["NYK"]["possessions"], 99.0)

    def test_game_odds_are_not_player_prices(self):
        payload = load_json("odds_game_only.json")
        self.assertEqual(
            op.quotes_from_api_payload(
                payload,
                sport="NBA",
                retrieved_at="2026-10-22T16:00:00Z",
                source_url="https://example.test/game",
            ),
            [],
        )

    def test_player_prop_needs_both_sides(self):
        quotes = op.quotes_from_records(
            [
                {
                    "sport": "NHL",
                    "player": "Example Bruins Wing",
                    "team": "BOS",
                    "stat": "shots on goal",
                    "book": "FanDuel",
                    "line": 2.5,
                    "over_odds": -130,
                    "under_odds": 110,
                    "retrieved_at": "2026-10-22T16:00:00Z",
                    "source_url": "https://example.test/odds",
                },
                {
                    "sport": "NHL",
                    "player": "One Sided",
                    "team": "BOS",
                    "stat": "shots on goal",
                    "book": "FanDuel",
                    "line": 1.5,
                    "over_odds": -120,
                    "source_url": "https://example.test/odds",
                },
                {
                    "sport": "NHL",
                    "player": "Example Bruins Wing",
                    "team": "BOS",
                    "stat": "shots on goal",
                    "book": "Underdog",
                    "line": 2.5,
                    "over_odds": -110,
                    "under_odds": -110,
                    "source_url": "https://example.test/odds",
                },
            ]
        )
        self.assertEqual([quote["player"] for quote in quotes], ["Example Bruins Wing"])
        rows = fs.nhl_rows_from_summaries(
            fs.games_from_schedule(load_json("nhl_schedule.json"), "2026-10-22"),
            load_json("nhl_skaters.json"),
            [],
            load_json("nhl_teams.json"),
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NHL_STATS_SKATER,
        )
        fs.attach_prices(rows, quotes)
        wing = next(row for row in rows if row["player"] == "Example Bruins Wing")
        self.assertEqual(wing["book"], "FanDuel")
        self.assertEqual(wing["line"], 2.5)
        self.assertEqual(wing["over_odds"], -130)
        self.assertEqual(wing["under_odds"], 110)
        self.assertEqual(wing["n_books"], 1)
        self.assertFalse(wing["lines_disagree"])
        self.assertIn("line_gap", wing["flag_reasons"])
        blob = json.dumps(wing)
        self.assertNotIn("+EV", blob)
        self.assertNotIn("underdog", blob.lower())


class ClientFailureTests(unittest.TestCase):
    def _fetch_espn(self, stats_payload=None, stats_error=None, scoreboard_error=None):
        calls = []

        def fake_fetch(url, timeout=15, headers=None):
            calls.append((url, timeout))
            if "scoreboard" in url:
                if scoreboard_error:
                    raise scoreboard_error
                return load_json("nba_scoreboard.json")
            if "statistics/byathlete" in url:
                if stats_error:
                    raise stats_error
                if "page=" in url:
                    raise AssertionError(url)
                return stats_payload if stats_payload is not None else load_json("nba_stats.json")
            if "/gamelog" in url:
                return {"names": ["minutes", "points"], "events": {}, "seasonTypes": []}
            raise AssertionError(url)

        return fake_fetch, calls

    def test_nba_fake_espn_payload_is_offline_and_flags_pace(self):
        fake_fetch, calls = self._fetch_espn()

        class FakePace:
            def __init__(self):
                self.season = None

            def team_pace(self, season):
                self.season = season
                return {
                    "BOS": {"pace": 112.0, "possessions": 102.0},
                    "NYK": {"pace": 100.0, "possessions": 99.0},
                    "DEN": {"pace": 90.0, "possessions": 95.0},
                }

        pace = FakePace()
        rows, note = fs.fetch_nba(
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fetch=fake_fetch,
            pace_client=pace,
        )
        self.assertIsNone(note)
        self.assertEqual(pace.season, "2026-27")
        self.assertEqual(fs.nba_espn_season_year("2026-10-22"), 2027)
        self.assertEqual(fs.nba_espn_season_year("2026-04-10"), 2026)
        urls = [url for url, timeout in calls]
        self.assertEqual(
            urls,
            [
                "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261022",
                "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete?season=2027&seasontype=2&limit=500",
                "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/1/gamelog?season=2027",
                "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/1/gamelog?season=2026",
            ],
        )
        self.assertTrue(all(timeout == 15 for _url, timeout in calls))
        points = next(row for row in rows if row["stat"] == "points")
        self.assertEqual(points["player"], "Example Wing")
        self.assertEqual(points["source_url"], fs.NBA_SOURCE)
        self.assertAlmostEqual(points["minutes"], 34.5)
        self.assertAlmostEqual(points["pace_per_game"], 112.0)
        self.assertAlmostEqual(points["possessions"], 102.0)
        self.assertGreater(points["pace_ratio"], 1.10)
        self.assertEqual(points["channel"], "pace")
        self.assertTrue(points["flag"])
        self.assertIsNone(points["book"])
        self.assertIsNone(points["line"])

    def test_nba_second_byathlete_page_is_included(self):
        first = load_json("nba_stats.json")
        first["pagination"] = {"count": 2, "limit": 500, "page": 1, "pages": 2}
        first["athletes"] = [first["athletes"][0]]
        second_player = {
            "athlete": {
                "id": "9",
                "displayName": "Example Guard",
                "teamId": "18",
                "teams": [{"id": "18", "abbreviation": "NY"}],
            },
            "categories": [
                {"name": "general", "values": [3.0, 6, 28.0]},
                {"name": "offensive", "values": [7.0, 2.5, 16.0]},
            ],
        }

        def fake_fetch(url, timeout=15, headers=None):
            if "scoreboard" in url:
                return load_json("nba_scoreboard.json")
            if url.endswith("&page=2"):
                return {"athletes": [second_player]}
            if "statistics/byathlete" in url:
                return first
            if "/gamelog" in url:
                return {"names": ["minutes", "points"], "events": {}, "seasonTypes": []}
            raise AssertionError(url)

        class FakePace:
            def team_pace(self, season):
                return {}

        rows, note = fs.fetch_nba(
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fetch=fake_fetch,
            pace_client=FakePace(),
        )
        self.assertIsNone(note)
        players = {row["player"] for row in rows}
        self.assertEqual(players, {"Example Wing", "Example Guard"})
        guard = next(row for row in rows if row["player"] == "Example Guard" and row["stat"] == "points")
        self.assertEqual(guard["team"], "NYK")
        self.assertAlmostEqual(guard["baseline_mean"], 16.0)
        self.assertAlmostEqual(guard["sample_size"], 6)

    def test_nba_names_the_failed_endpoint_and_invents_nothing(self):
        fake_fetch, _calls = self._fetch_espn(scoreboard_error=TimeoutError("timed out"))
        rows, note = fs.fetch_nba("2026-10-22", "2026-10-22T16:00:00Z", fetch=fake_fetch, pace_client=object())
        self.assertEqual(rows, [])
        self.assertIn("ESPN scoreboard", note)
        self.assertIn("TimeoutError", note)

        fake_fetch, _calls = self._fetch_espn(stats_error=TimeoutError("timed out"))

        class UnusedPace:
            def team_pace(self, season):
                raise AssertionError("pace should not run when counting stats fail")

        rows, note = fs.fetch_nba(
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fetch=fake_fetch,
            pace_client=UnusedPace(),
        )
        self.assertEqual(rows, [])
        self.assertIn("statistics/byathlete", note)
        self.assertIn("TimeoutError", note)

        fake_fetch, _calls = self._fetch_espn()

        class NoPace:
            def team_pace(self, season):
                raise TimeoutError("timed out")

        rows, note = fs.fetch_nba(
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fetch=fake_fetch,
            pace_client=NoPace(),
        )
        self.assertIn("LeagueDashTeamStats", note)
        self.assertIn("TimeoutError", note)
        self.assertIn("Pace and possessions left null", note)
        self.assertTrue(rows)
        self.assertTrue(all(row["pace_per_game"] is None and row["possessions"] is None for row in rows))
        self.assertEqual({row["player"] for row in rows}, {"Example Wing"})

    def test_counting_payload_without_averages_invents_nothing(self):
        fake_fetch, _calls = self._fetch_espn(stats_payload={"athletes": [{"athlete": {"displayName": "Nobody"}}]})

        class UnusedPace:
            def team_pace(self, season):
                raise AssertionError("pace should not run when averages are absent")

        rows, note = fs.fetch_nba(
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fetch=fake_fetch,
            pace_client=UnusedPace(),
        )
        self.assertEqual(rows, [])
        self.assertIn("did not include season averages", note)

    def test_pace_http_timeout_is_capped_at_20_seconds(self):
        self.assertEqual(fs.NbaPaceClient(timeout=120).timeout, 20)
        self.assertEqual(fs.NbaPaceClient(timeout=5).timeout, 5)
        self.assertEqual(fs.NbaPaceClient().timeout, 20)

    def test_nfl_loader_stays_offline_and_names_failures(self):
        class Frame:
            def __init__(self, rows):
                self._rows = rows

            def to_dicts(self):
                return self._rows

        games = fs.read_csv(load_text("nfl_games.csv"))
        stats = fs.read_csv(load_text("nfl_stats.csv"))
        snaps = fs.read_csv(load_text("nfl_snaps.csv"))
        teams = [
            {"team": "NE", "season": 2026, "season_type": "REG", "games": 2, "plays": 140},
            {"team": "DAL", "season": 2026, "season_type": "REG", "games": 2, "plays": 100},
        ]

        class Loader:
            def load_schedules(self, seasons=None):
                return Frame(games)

            def load_player_stats(self, seasons=None, summary_level="reg"):
                return Frame(stats)

            def load_snap_counts(self, seasons=None):
                return Frame(snaps)

            def load_team_stats(self, seasons=None, summary_level="reg"):
                return Frame(teams)

            def load_ftn_charting(self, seasons=None):
                return Frame([])

            def load_pbp(self, seasons=None):
                return Frame([])

        rows, notes = fs.fetch_nfl("2026-10-22", "2026-10-22T16:00:00Z", loader=Loader())
        self.assertEqual(notes, [])
        receiver = next(row for row in rows if row["player"] == "Example Receiver" and row["stat"] == "receptions")
        self.assertEqual(receiver["source_url"], "nflreadpy.load_player_stats")
        self.assertAlmostEqual(receiver["pace_per_game"], 70.0)
        self.assertGreater(receiver["pace_ratio"], 1.10)
        self.assertIsNone(receiver["teammate_splits"])
        self.assertNotIn("routes_per_game", receiver)
        self.assertNotIn("first_read_target_share", receiver)
        self.assertNotIn("checkdown_multiplier", receiver)

        class NoStats(Loader):
            def load_player_stats(self, seasons=None, summary_level="reg"):
                raise OSError("download failed")

        rows, notes = fs.fetch_nfl("2026-10-22", "2026-10-22T16:00:00Z", loader=NoStats())
        self.assertEqual(rows, [])
        self.assertIn("load_player_stats", notes[0])

        class NoSnaps(Loader):
            def load_snap_counts(self, seasons=None):
                raise OSError("snap file missing")

        rows, notes = fs.fetch_nfl("2026-10-22", "2026-10-22T16:00:00Z", loader=NoSnaps())
        self.assertTrue(rows)
        self.assertIn("load_snap_counts", notes[0])
        self.assertTrue(all(row["snap_share"] is None for row in rows))

        class NoPlays(Loader):
            def load_team_stats(self, seasons=None, summary_level="reg"):
                raise OSError("team stats missing")

        rows, notes = fs.fetch_nfl("2026-10-22", "2026-10-22T16:00:00Z", loader=NoPlays())
        self.assertTrue(rows)
        self.assertIn("load_team_stats", notes[0])
        self.assertTrue(all(row["pace_per_game"] is None for row in rows))
        self.assertIsNotNone(rows[0]["snap_share"])


class DeploymentTests(unittest.TestCase):
    def _games(self):
        return fs.read_csv(load_text("nfl_games.csv"))

    def _season(self, **extra):
        row = {
            "player_display_name": "Example Receiver",
            "player_id": "WR1",
            "position": "WR",
            "season": "2026",
            "recent_team": "NE",
            "games": 12,
            "receptions": 36,
        }
        row.update(extra)
        return row

    def _week(self, name, team, game_id, week, **stats):
        row = {
            "player_display_name": name,
            "team": team,
            "season": 2026,
            "season_type": stats.pop("season_type", "REG"),
            "week": week,
            "game_id": game_id,
        }
        if "player_id" in stats:
            row["player_id"] = stats.pop("player_id")
        row.update(stats)
        return row

    def _receiver_weeks(self):
        rows = []
        for number in range(1, 13):
            catches = 5 if number <= 6 else 1
            rows.append(self._week("E. Receiver", "NE", f"g{number}", number, receptions=catches, routes=9, player_id="WR1"))
            if number <= 6:
                rows.append(self._week("Aaron Blocker", "NE", f"g{number}", number, receptions=1, player_id="OL1"))
                rows.append(self._week("Example Quarterback", "NE", f"g{number}", number, receptions=0, player_id="QB1"))
            if number <= 4:
                rows.append(self._week("Example Slot", "NE", f"g{number}", number, receptions=2))
            rows.append(self._week("Example Tackle", "NE", f"g{number}", number, receptions=0))
            rows.append(self._week("Other Team Guy", "CHI", f"g{number}", number, receptions=9))
        rows.append(self._week(
            "E. Receiver", "NE", "post1", 13, receptions=99, routes=40, player_id="WR1", season_type="POST",
        ))
        return rows

    def test_average_columns_skip_alignment_participation_and_charting(self):
        absent = {
            "route", "slot", "wide", "inline", "alignment",
            "hash", "qb_location", "offense_pct", "offense_snaps", "target_share",
        }
        self.assertEqual(fs.deployment_average_columns(absent), {})
        self.assertEqual(
            fs.deployment_average_columns({"routes", "route", "slot", "wide", "inline"}),
            {"routes": "routes_per_game"},
        )
        self.assertEqual(
            fs.deployment_average_columns({"route_share", "alignment", "hash"}),
            {"route_share": "route_share"},
        )
        self.assertFalse(fs.numeric_column([{"routes": "GO"}, {"routes": 12}], "routes"))
        self.assertFalse(fs.numeric_column([{"route": "SLANT"}], "route"))
        self.assertFalse(fs.numeric_column([{"slot": 0.7, "wide": 0.2, "inline": 0.1}], "slot"))

    def test_string_routes_and_alignment_are_not_stored(self):
        stats = [self._season(routes="GO", route="GO", slot=0.7, wide=0.2, inline=0.1, hash="L", qb_location="S")]
        rows = fs.nfl_rows_from_tables(
            self._games(), stats, [], "2026-10-22", "2026-10-22T16:00:00Z", "nflreadpy.load_player_stats",
        )
        receiver = rows[0]
        self.assertNotIn("routes_per_game", receiver)
        self.assertNotIn("route_share", receiver)
        self.assertNotIn("alignment", receiver)
        self.assertNotIn("slot", receiver)
        self.assertNotIn("wide", receiver)
        self.assertNotIn("inline", receiver)
        self.assertNotIn("route", receiver)
        self.assertNotIn("hash", receiver)
        self.assertNotIn("workload_ratio", receiver)
        self.assertNotIn("workload_expected", receiver)

    def test_numeric_routes_prefer_the_season_total(self):
        stats = [self._season(routes=24, route_share=0.25)]
        rows = fs.nfl_rows_from_tables(
            self._games(),
            stats,
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            week_rows=self._receiver_weeks(),
        )
        receiver = next(row for row in rows if row["stat"] == "receptions")
        self.assertAlmostEqual(receiver["baseline_mean"], 3.0)
        self.assertAlmostEqual(receiver["routes_per_game"], 2.0)
        self.assertAlmostEqual(receiver["route_share"], 0.25)
        self.assertEqual(
            [item["teammate"] for item in receiver["teammate_splits"]],
            ["Aaron Blocker", "Example Quarterback"],
        )
        for item in receiver["teammate_splits"]:
            self.assertEqual(item["with_n"], 6)
            self.assertEqual(item["without_n"], 6)
            self.assertAlmostEqual(item["with_mean"], 5.0)
            self.assertAlmostEqual(item["without_mean"], 1.0)
        self.assertNotIn("workload_ratio", receiver)

    def test_week_routes_are_averaged_when_the_season_column_is_absent(self):
        weeks = [
            self._week("Example Receiver", "NE", "g1", 1, receptions=4, routes=10, player_id="WR1"),
            self._week("Example Receiver", "NE", "g2", 2, receptions=2, routes=6, player_id="WR1"),
            self._week("Teammate", "NE", "g1", 1, receptions=1),
        ]
        rows = fs.nfl_rows_from_tables(
            self._games(),
            [self._season(games=2, receptions=6)],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            week_rows=weeks,
        )
        receiver = next(row for row in rows if row["stat"] == "receptions")
        self.assertAlmostEqual(receiver["routes_per_game"], 8.0)
        self.assertEqual(receiver["teammate_splits"], [])
        self.assertAlmostEqual(receiver["baseline_mean"], 3.0)

    def test_split_gate_is_five_games_on_each_side(self):
        rows = []
        for number in range(1, 10):
            rows.append(self._week("Player", "NE", f"g{number}", number, receptions=2))
            if number <= 5:
                rows.append(self._week("Mate", "NE", f"g{number}", number, receptions=8))
        self.assertEqual(fs.teammate_splits(rows, "NE", "Player", "receptions"), [])
        rows.append(self._week("Player", "NE", "g10", 10, receptions=4))
        splits = fs.teammate_splits(rows, "NE", "Player", "receptions")
        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0]["teammate"], "Mate")
        self.assertEqual(splits[0]["with_n"], 5)
        self.assertEqual(splits[0]["without_n"], 5)
        self.assertAlmostEqual(splits[0]["with_mean"], 2.0)
        self.assertAlmostEqual(splits[0]["without_mean"], 2.4)
        self.assertIsNone(fs.teammate_splits(rows, "NE", "Player", "routes"))
        self.assertIsNone(fs.teammate_splits(None, "NE", "Player", "receptions"))
        self.assertIsNone(fs.teammate_splits([], "NE", "Player", "receptions"))
        self.assertIsNone(fs.teammate_splits([{"player_display_name": "Player", "receptions": 1}], "NE", "Player", "receptions"))
        self.assertEqual(fs.teammate_splits(rows, "NE", "Nobody", "receptions"), [])

    def test_tackle_split_uses_solo_plus_assists(self):
        rows = []
        for number in range(1, 11):
            solo = 4 if number <= 5 else 1
            rows.append(self._week("Backer", "NE", f"g{number}", number, def_tackles_solo=solo, def_tackle_assists=1))
            if number <= 5:
                rows.append(self._week("Mike", "NE", f"g{number}", number, def_tackles_solo=9, def_tackle_assists=9))
        splits = fs.teammate_splits(rows, "NE", "Backer", None)
        self.assertEqual(splits[0]["with_n"], 5)
        self.assertEqual(splits[0]["without_n"], 5)
        self.assertAlmostEqual(splits[0]["with_mean"], 5.0)
        self.assertAlmostEqual(splits[0]["without_mean"], 2.0)

    def test_fetch_wires_the_week_log_and_names_a_week_failure(self):
        class Frame:
            def __init__(self, rows):
                self._rows = rows

            def to_dicts(self):
                return self._rows

        games = self._games()
        stats = [self._season(routes=24, route_share=0.25)]
        weeks = self._receiver_weeks()
        snaps = fs.read_csv(load_text("nfl_snaps.csv"))

        class Loader:
            def load_schedules(self, seasons=None):
                return Frame(games)

            def load_player_stats(self, seasons=None, summary_level="reg"):
                if summary_level == "week":
                    return Frame(weeks)
                return Frame(stats)

            def load_snap_counts(self, seasons=None):
                return Frame(snaps)

            def load_team_stats(self, seasons=None, summary_level="reg"):
                return Frame([])

            def load_ftn_charting(self, seasons=None):
                return Frame([])

            def load_pbp(self, seasons=None):
                return Frame([])

        rows, notes = fs.fetch_nfl("2026-10-22", "2026-10-22T16:00:00Z", loader=Loader())
        self.assertEqual(notes, [])
        receiver = next(row for row in rows if row["player"] == "Example Receiver" and row["stat"] == "receptions")
        self.assertEqual(receiver["player"], "Example Receiver")
        self.assertAlmostEqual(receiver["baseline_mean"], 3.0)
        self.assertAlmostEqual(receiver["routes_per_game"], 2.0)
        self.assertEqual(receiver["teammate_splits"][0]["teammate"], "Aaron Blocker")
        self.assertNotIn("workload_ratio", receiver)

        class NoWeek(Loader):
            def load_player_stats(self, seasons=None, summary_level="reg"):
                if summary_level == "week":
                    raise OSError("week file missing")
                return Frame(stats)

        rows, notes = fs.fetch_nfl("2026-10-22", "2026-10-22T16:00:00Z", loader=NoWeek())
        self.assertTrue(rows)
        self.assertIn("load_player_stats week", notes[0])
        self.assertIsNone(rows[0]["teammate_splits"])
        self.assertAlmostEqual(rows[0]["baseline_mean"], 3.0)


class ReadProgressionTests(unittest.TestCase):
    def test_buckets_match_the_charting_codes(self):
        self.assertEqual(fs.read_bucket("0"), "first_read")
        self.assertEqual(fs.read_bucket("DES"), "designed")
        self.assertEqual(fs.read_bucket("CHK"), "checkdown")
        self.assertEqual(fs.read_bucket("1"), "secondary_read")
        self.assertEqual(fs.read_bucket("2"), "secondary_read")
        self.assertEqual(fs.read_bucket("SD"), "scramble_drill")
        self.assertEqual(fs.read_bucket(0), "first_read")
        self.assertIsNone(fs.read_bucket("HOT"))
        self.assertIsNone(fs.read_bucket(None))
        self.assertIsNone(fs.read_bucket(""))

    def _plays(self, games):
        charting = []
        pbp = []
        for number in range(1, games + 1):
            game = f"2026_0{number}_NE_CHI"
            specs = [
                (1, "0", "WR1", "Example Receiver", 1, 1),
                (2, "DES", "WR2", "Other Receiver", 1, 1),
                (3, "CHK", "WR1", "Example Receiver", 1, 1),
                (4, "1", "WR1", "Example Receiver", 1, 1),
                (5, "0", "WR1", "Example Receiver", 0, 0),
            ]
            for play_id, read, receiver_id, receiver_name, dropback, attempt in specs:
                charting.append(
                    {"nflverse_game_id": game, "nflverse_play_id": play_id, "read_thrown": read}
                )
                pbp.append(
                    {
                        "game_id": game,
                        "play_id": float(play_id),
                        "posteam": "NE",
                        "season_type": "REG",
                        "qb_dropback": dropback,
                        "pass_attempt": attempt,
                        "receiver_player_id": receiver_id,
                        "receiver_player_name": receiver_name,
                        "passer_player_id": "QB1",
                        "passer_player_name": "Example Quarterback",
                    }
                )
        return charting, pbp

    def test_share_math_uses_bucket_throws_and_targets_only(self):
        charting, pbp = self._plays(5)
        # A charted play with no pbp row, and a pbp-only throw, stay out of the sample.
        charting.append({"nflverse_game_id": "2026_09_NE_CHI", "nflverse_play_id": 9, "read_thrown": "CHK"})
        pbp.append(
            {
                "game_id": "2026_10_NE_CHI",
                "play_id": 9.0,
                "posteam": "NE",
                "season_type": "REG",
                "qb_dropback": 1,
                "pass_attempt": 1,
                "receiver_player_id": "WR1",
                "receiver_player_name": "Example Receiver",
                "passer_player_id": "QB1",
                "passer_player_name": "Example Quarterback",
            }
        )
        table = fs.progression_table(charting, pbp)
        self.assertEqual(table["status"], "ok")
        player = table["players"]["NE"]["id:WR1"]
        self.assertAlmostEqual(player["first_read_target_share"], 1.0)
        self.assertEqual(player["first_read_player_games"], 5)
        self.assertEqual(player["first_read_team_games"], 5)
        self.assertAlmostEqual(player["first_read_multiplier"], 1.0)
        self.assertAlmostEqual(player["checkdown_target_share"], 1.0)
        self.assertEqual(player["checkdown_player_games"], 5)
        self.assertEqual(player["checkdown_team_games"], 5)
        self.assertAlmostEqual(player["checkdown_multiplier"], 1.0)
        qb = table["qbs"]["NE"]["id:QB1"]
        self.assertAlmostEqual(qb["qb_checkdown_tendency"], 5 / 20)
        self.assertAlmostEqual(qb["qb_first_read_rate"], 5 / 20)
        self.assertEqual(qb["qb_dropback_games"], 5)
        self.assertIsNone(fs.bucket_target_share(1, 0))
        self.assertAlmostEqual(fs.bucket_target_share(2, 8), 0.25)

    def test_short_sample_stores_the_share_and_passes_no_multiplier(self):
        charting, pbp = self._plays(4)
        table = fs.progression_table(charting, pbp)
        player = table["players"]["NE"]["id:WR1"]
        self.assertAlmostEqual(player["first_read_target_share"], 1.0)
        self.assertAlmostEqual(player["checkdown_target_share"], 1.0)
        self.assertEqual(player["first_read_player_games"], 4)
        self.assertEqual(player["first_read_team_games"], 4)
        self.assertIsNone(player["first_read_multiplier"])
        self.assertIsNone(player["checkdown_multiplier"])
        self.assertIsNone(fs.read_share_multiplier(0.5, 5, 4))
        self.assertIsNone(fs.read_share_multiplier(0.5, 4, 5))
        self.assertEqual(fs.read_share_multiplier(0.5, 5, 5), 0.5)
        rows = fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            [
                {
                    "player_display_name": "Example Receiver",
                    "player_id": "WR1",
                    "position": "WR",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 4,
                    "receptions": 20,
                    "receiving_yards": 200,
                }
            ],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            read_table=table,
        )
        receptions = next(row for row in rows if row["stat"] == "receptions")
        yards = next(row for row in rows if row["stat"] == "receiving yards")
        self.assertAlmostEqual(receptions["baseline_mean"], 5.0)
        self.assertAlmostEqual(yards["baseline_mean"], 50.0)
        self.assertIsNone(receptions["checkdown_multiplier"])
        self.assertAlmostEqual(receptions["checkdown_target_share"], 1.0)
        self.assertNotIn("first_read_multiplier", receptions)
        self.assertIsNone(yards["first_read_multiplier"])
        self.assertAlmostEqual(yards["first_read_target_share"], 1.0)
        self.assertNotIn("checkdown_multiplier", yards)

    def test_long_sample_keeps_the_baseline_mean(self):
        charting, pbp = self._plays(5)
        table = fs.progression_table(charting, pbp)
        rows = fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            [
                {
                    "player_display_name": "Example Receiver",
                    "player_id": "WR1",
                    "position": "WR",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 5,
                    "receptions": 25,
                    "receiving_yards": 250,
                },
                {
                    "player_display_name": "Example Quarterback",
                    "player_id": "QB1",
                    "position": "QB",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 5,
                    "attempts": 20,
                    "completions": 12,
                    "passing_yards": 200,
                },
            ],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            read_table=table,
        )
        yards = next(row for row in rows if row["player"] == "Example Receiver" and row["stat"] == "receiving yards")
        passes = next(row for row in rows if row["stat"] == "pass attempts")
        self.assertAlmostEqual(yards["baseline_mean"], 50.0)
        self.assertAlmostEqual(yards["first_read_multiplier"], 1.0)
        self.assertAlmostEqual(passes["qb_checkdown_tendency"], 5 / 20)
        self.assertAlmostEqual(passes["qb_first_read_rate"], 5 / 20)
        self.assertNotIn("first_read_multiplier", passes)

    def test_missing_charting_or_a_failed_join_omits_the_features(self):
        self.assertIsNone(fs.progression_table(None, [{"game_id": "g", "play_id": 1}]))
        self.assertEqual(fs.progression_table([], [{"game_id": "g", "play_id": 1}])["status"], "missing")
        charting = [{"nflverse_game_id": "missing-game", "nflverse_play_id": 1, "read_thrown": "CHK"}]
        pbp = [{
            "game_id": "other-game",
            "play_id": 1,
            "posteam": "NE",
            "pass_attempt": 1,
            "qb_dropback": 1,
            "receiver_player_id": "WR1",
            "passer_player_id": "QB1",
        }]
        self.assertEqual(fs.progression_table(charting, pbp)["status"], "unmatched")
        self.assertIsNone(fs.progression_table([{"read_thrown": "CHK"}], pbp))
        rows = fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            [{
                "player_display_name": "Example Receiver",
                "player_id": "WR1",
                "position": "WR",
                "season": "2026",
                "recent_team": "NE",
                "games": 5,
                "receptions": 25,
                "receiving_yards": 250,
            }],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            read_table=None,
        )
        self.assertAlmostEqual(rows[0]["baseline_mean"], 5.0)
        self.assertNotIn("checkdown_target_share", rows[0])
        self.assertNotIn("first_read_multiplier", rows[0])

        class Frame:
            def __init__(self, rows):
                self._rows = rows

            def to_dicts(self):
                return self._rows

        games = fs.read_csv(load_text("nfl_games.csv"))
        stats = fs.read_csv(load_text("nfl_stats.csv"))
        snaps = fs.read_csv(load_text("nfl_snaps.csv"))

        class Loader:
            def load_schedules(self, seasons=None):
                return Frame(games)

            def load_player_stats(self, seasons=None, summary_level="reg"):
                return Frame(stats)

            def load_snap_counts(self, seasons=None):
                return Frame(snaps)

            def load_team_stats(self, seasons=None, summary_level="reg"):
                return Frame([])

            def load_ftn_charting(self, seasons=None):
                raise OSError("charting missing")

            def load_pbp(self, seasons=None):
                return Frame([])

        fetched, notes = fs.fetch_nfl("2026-10-22", "2026-10-22T16:00:00Z", loader=Loader())
        self.assertTrue(fetched)
        self.assertTrue(any("load_ftn_charting" in note for note in notes))
        self.assertTrue(all("first_read_target_share" not in row and "checkdown_multiplier" not in row for row in fetched))
        self.assertAlmostEqual(
            next(row for row in fetched if row["player"] == "Example Receiver" and row["stat"] == "receptions")["baseline_mean"],
            5.0,
        )


class DefenseReadTests(unittest.TestCase):
    def _throw(self, offense, defense, read, receiver_id, dropback=1, attempt=1, air=None):
        play = {
            "team": offense,
            "defense": defense,
            "bucket": fs.read_bucket(read),
            "is_throw": bool(attempt),
            "is_dropback": bool(dropback),
            "receiver_id": receiver_id,
            "receiver_name": "",
        }
        if air is not None:
            play["air_yards"] = air
        return play

    def _sample(self, with_air=True):
        plays = []
        chi = [("CHK", "RB1")] * 40 + [("0", "WR1")] * 30 + [("1", "WR9")] * 30
        for index, (read, receiver) in enumerate(chi):
            air = 1.0 if read == "CHK" else 9.0
            plays.append(self._throw(
                "NE", "CHI", read, receiver,
                dropback=1 if index < 75 else 0,
                air=air if with_air else None,
            ))
        dal = [("CHK", "RB9")] * 10 + [("0", "WR9")] * 80 + [("1", "WR8")] * 10
        for read, receiver in dal:
            air = 1.0 if read == "CHK" else 9.0
            plays.append(self._throw("PHI", "DAL", read, receiver, air=air if with_air else None))
        for _ in range(50):
            plays.append(self._throw("PHI", "DAL", None, None, dropback=1, attempt=0, air=None if not with_air else None))
        positions = {"id:RB1": "RB", "id:WR1": "WR", "id:WR9": "WR", "id:WR8": "WR", "id:RB9": "RB"}
        return plays, positions

    def test_three_rates_shrink_and_clamp(self):
        plays, positions = self._sample()
        table = fs.defense_read_rates(plays, positions)
        league = table["league"]
        self.assertAlmostEqual(league["def_forced_checkdown_rate"], 0.25)
        self.assertAlmostEqual(league["def_first_read_suppression_rate"], 0.45)
        self.assertAlmostEqual(league["def_rb_target_funnel_share"], 0.25)
        chi = table["teams"]["CHI"]
        self.assertAlmostEqual(chi["def_forced_checkdown_rate"], 0.4)
        self.assertAlmostEqual(chi["def_first_read_suppression_rate"], 0.7)
        self.assertAlmostEqual(chi["def_rb_target_funnel_share"], 0.4)
        self.assertEqual(chi["dropbacks"], 75)
        self.assertAlmostEqual(chi["def_forced_checkdown_rate_shrunk"], 0.325)
        self.assertAlmostEqual(chi["def_checkdown_multiplier"], 1.3)
        stacked = chi["def_checkdown_multiplier"] * chi["def_suppression_multiplier"]
        self.assertAlmostEqual(chi["def_matchup_ratio"], stacked, places=5)
        self.assertGreater(chi["def_matchup_ratio"], 1.15)
        self.assertAlmostEqual(chi["def_matchup_factor"], 1.15)
        dal = table["teams"]["DAL"]
        self.assertEqual(dal["dropbacks"], 150)
        self.assertAlmostEqual(dal["def_forced_checkdown_rate_shrunk"], 0.1)
        self.assertLess(dal["def_matchup_ratio"], 0.85)
        self.assertAlmostEqual(dal["def_matchup_factor"], 0.85)
        raw, clamped = fs.stack_matchup_factor(1.3, 1.4)
        self.assertAlmostEqual(raw, 1.82)
        self.assertAlmostEqual(clamped, 1.15)
        raw, clamped = fs.stack_matchup_factor(0.5, 0.5)
        self.assertAlmostEqual(raw, 0.25)
        self.assertAlmostEqual(clamped, 0.85)
        self.assertEqual(fs.stack_matchup_factor(None, 1.2), (None, None))
        self.assertAlmostEqual(fs.shrink_to_league(0.4, 0, 0.25), 0.25)
        self.assertAlmostEqual(fs.shrink_to_league(0.4, 75, 0.25), 0.325)
        self.assertAlmostEqual(fs.shrink_to_league(0.4, 150, 0.25), 0.4)
        self.assertAlmostEqual(fs.shrink_to_league(0.4, 200, 0.25), 0.4)
        self.assertEqual(fs.shrunk_rate_ratio(0.8, 0, 0.25)[0], 1.0)
        self.assertNotEqual(fs.shrunk_rate_ratio(0.4, 75, 0.25)[0], 1.0)
        self.assertEqual(fs.clamp_opponent_factor(1.3), 1.15)
        self.assertEqual(fs.clamp_opponent_factor(0.4), 0.85)
        self.assertEqual(fs.clamp_opponent_factor(1.02), 1.02)
        self.assertEqual(fs.OPPONENT_FACTOR_CLAMP, (0.85, 1.15))

    def test_split_shares_stay_on_each_player(self):
        charting = []
        pbp = []
        for game in range(1, 6):
            for play_id, read, receiver in ((1, "0", "WR1"), (2, "0", "WR2"), (3, "CHK", "WR1"), (4, "CHK", "TE1")):
                game_id = f"2026_0{game}_NE_CHI"
                charting.append({"nflverse_game_id": game_id, "nflverse_play_id": play_id, "read_thrown": read})
                pbp.append({
                    "game_id": game_id,
                    "play_id": float(play_id),
                    "posteam": "NE",
                    "defteam": "CHI",
                    "season_type": "REG",
                    "qb_dropback": 1,
                    "pass_attempt": 1,
                    "receiver_player_id": receiver,
                    "receiver_player_name": receiver,
                    "passer_player_id": "QB1",
                    "passer_player_name": "Quarterback",
                })
        table = fs.progression_table(charting, pbp, positions={"id:WR1": "WR", "id:WR2": "WR", "id:TE1": "TE"})
        players = table["players"]["NE"]
        self.assertAlmostEqual(players["id:WR1"]["first_read_target_share"], 0.5)
        self.assertAlmostEqual(players["id:WR2"]["first_read_target_share"], 0.5)
        self.assertAlmostEqual(players["id:WR1"]["checkdown_target_share"], 0.5)
        self.assertAlmostEqual(players["id:TE1"]["checkdown_target_share"], 0.5)
        self.assertNotIn("rerouted_first_read_share", players["id:WR1"])
        self.assertIsNone(fs.progression_table(None, pbp))

    def test_receptions_can_rise_and_yards_do_not_take_that_boost(self):
        plays, positions = self._sample()
        defenses = fs.defense_read_rates(plays, positions)
        read_table = {
            "status": "ok",
            "players": {
                "NE": {
                    "id:RB1": {
                        "first_read_target_share": None,
                        "first_read_player_games": 2,
                        "first_read_team_games": 2,
                        "first_read_multiplier": None,
                        "checkdown_target_share": 0.40,
                        "checkdown_player_games": 2,
                        "checkdown_team_games": 2,
                        "checkdown_multiplier": None,
                    },
                    "id:WR1": {
                        "first_read_target_share": 0.50,
                        "first_read_player_games": 5,
                        "first_read_team_games": 5,
                        "first_read_multiplier": 0.50,
                        "checkdown_target_share": 0.10,
                        "checkdown_player_games": 5,
                        "checkdown_team_games": 5,
                        "checkdown_multiplier": 0.10,
                    },
                    "id:TE1": {
                        "first_read_target_share": 0.20,
                        "first_read_player_games": 5,
                        "first_read_team_games": 5,
                        "first_read_multiplier": 0.20,
                        "checkdown_target_share": None,
                        "checkdown_player_games": 0,
                        "checkdown_team_games": 5,
                        "checkdown_multiplier": None,
                    },
                }
            },
            "qbs": {
                "NE": {
                    "id:QB1": {
                        "qb_checkdown_tendency": 0.2,
                        "qb_first_read_rate": 0.4,
                        "qb_dropback_games": 5,
                    }
                }
            },
            "defenses": defenses,
        }
        rows = fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            [
                {
                    "player_display_name": "Example Back",
                    "player_id": "RB1",
                    "position": "RB",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 5,
                    "receptions": 20,
                    "receiving_yards": 100,
                },
                {
                    "player_display_name": "Example Receiver",
                    "player_id": "WR1",
                    "position": "WR",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 5,
                    "receptions": 25,
                    "receiving_yards": 250,
                },
                {
                    "player_display_name": "Example Tight End",
                    "player_id": "TE1",
                    "position": "TE",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 5,
                    "receptions": 15,
                    "receiving_yards": 120,
                },
                {
                    "player_display_name": "Example Quarterback",
                    "player_id": "QB1",
                    "position": "QB",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 5,
                    "attempts": 100,
                    "completions": 60,
                    "passing_yards": 700,
                },
            ],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            read_table=read_table,
        )
        back_rec = next(row for row in rows if row["player"] == "Example Back" and row["stat"] == "receptions")
        back_yards = next(row for row in rows if row["player"] == "Example Back" and row["stat"] == "receiving yards")
        wr_yards = next(row for row in rows if row["player"] == "Example Receiver" and row["stat"] == "receiving yards")
        te_yards = next(row for row in rows if row["player"] == "Example Tight End" and row["stat"] == "receiving yards")
        pass_yards = next(row for row in rows if row["stat"] == "passing yards")
        completions = next(row for row in rows if row["stat"] == "completions")
        factor = defenses["teams"]["CHI"]["def_matchup_factor"]
        ratio = defenses["teams"]["CHI"]["def_matchup_ratio"]
        self.assertAlmostEqual(back_rec["baseline_mean"], 4.0)
        self.assertEqual(back_rec["checkdown_target_share"], 0.40)
        self.assertIsNone(back_rec["checkdown_multiplier"])
        self.assertAlmostEqual(back_rec["def_matchup_ratio"], ratio)
        self.assertAlmostEqual(back_rec["def_matchup_factor"], factor)
        self.assertAlmostEqual(back_yards["def_matchup_factor"], factor)
        self.assertAlmostEqual(wr_yards["first_read_target_share"], 0.50)
        self.assertAlmostEqual(wr_yards["first_read_multiplier"], 0.50)
        self.assertNotEqual(wr_yards["first_read_multiplier"], factor)
        self.assertAlmostEqual(wr_yards["def_matchup_factor"], factor)
        self.assertAlmostEqual(te_yards["first_read_target_share"], 0.20)
        self.assertAlmostEqual(te_yards["def_matchup_factor"], factor)
        self.assertAlmostEqual(pass_yards["def_matchup_factor"], factor)
        self.assertAlmostEqual(completions["def_matchup_factor"], factor)
        self.assertNotIn("rb_checkdown_targets", back_rec)
        self.assertNotIn("rerouted_first_read_share", wr_yards)
        self.assertNotIn("rerouted_first_read_share", te_yards)
        self.assertNotIn("n_blitzers", pass_yards)

    def test_player_checkdown_multiplier_is_not_stacked(self):
        plays, positions = self._sample()
        defenses = fs.defense_read_rates(plays, positions)
        read_table = {
            "status": "ok",
            "players": {
                "NE": {
                    "id:RB1": {
                        "first_read_target_share": None,
                        "first_read_player_games": 0,
                        "first_read_team_games": 5,
                        "first_read_multiplier": None,
                        "checkdown_target_share": 0.5,
                        "checkdown_player_games": 5,
                        "checkdown_team_games": 5,
                        "checkdown_multiplier": 0.5,
                    }
                }
            },
            "qbs": {},
            "defenses": defenses,
        }
        rows = fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            [{
                "player_display_name": "Example Back",
                "player_id": "RB1",
                "position": "RB",
                "season": "2026",
                "recent_team": "NE",
                "games": 5,
                "receptions": 20,
            }],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            read_table=read_table,
        )
        receptions = rows[0]
        self.assertEqual(receptions["checkdown_multiplier"], 0.5)
        self.assertEqual(receptions["checkdown_target_share"], 0.5)
        self.assertAlmostEqual(receptions["def_matchup_factor"], defenses["teams"]["CHI"]["def_matchup_factor"])
        self.assertNotEqual(receptions["checkdown_multiplier"], receptions["def_matchup_factor"])
        self.assertNotIn("rb_checkdown_targets", receptions)
        self.assertNotIn("rerouted_first_read_share", receptions)

    def test_missing_charting_and_missing_air_yards_omit_the_factors(self):
        self.assertIsNone(fs.defense_read_rates([]))
        self.assertIsNone(fs.defense_read_rates([
            {"team": "NE", "defense": "CHI", "bucket": None, "is_throw": False, "is_dropback": True,
             "receiver_id": None, "receiver_name": "", "air_yards": None}
        ]))
        rows = fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            [{
                "player_display_name": "Example Back",
                "player_id": "RB1",
                "position": "RB",
                "season": "2026",
                "recent_team": "NE",
                "games": 5,
                "receptions": 20,
                "receiving_yards": 80,
            }],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            read_table=None,
        )
        self.assertAlmostEqual(rows[0]["baseline_mean"], 4.0)
        self.assertNotIn("def_matchup_factor", rows[0])
        self.assertNotIn("def_matchup_ratio", rows[0])
        self.assertNotIn("rb_checkdown_targets", rows[0])
        self.assertNotIn("rerouted_first_read_share", rows[0])


    def test_nfl_reads_flow_through_prepare_pipeline_into_engine_b(self):
        import pickem_math as pm

        plays, positions = self._sample()
        defenses = fs.defense_read_rates(plays, positions)
        read_table = {
            "status": "ok",
            "players": {
                "NE": {
                    "id:RB1": {
                        "first_read_target_share": 0.20,
                        "first_read_player_games": 6,
                        "first_read_team_games": 6,
                        "first_read_multiplier": 0.20,
                        "checkdown_target_share": 0.50,
                        "checkdown_player_games": 6,
                        "checkdown_team_games": 6,
                        "checkdown_multiplier": 0.50,
                    }
                }
            },
            "qbs": {
                "NE": {
                    "id:QB1": {
                        "qb_checkdown_tendency": 0.20,
                        "qb_first_read_rate": 0.45,
                        "qb_dropback_games": 6,
                    }
                }
            },
            "defenses": defenses,
        }
        rows = fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            [
                {
                    "player_display_name": "Example Back",
                    "player_id": "RB1",
                    "position": "RB",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 6,
                    "receptions": 24,
                    "targets": 30,
                    "receiving_yards": 180,
                },
                {
                    "player_display_name": "Example Quarterback",
                    "player_id": "QB1",
                    "position": "QB",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 6,
                    "attempts": 204,
                    "completions": 132,
                    "passing_yards": 1500,
                },
            ],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            read_table=read_table,
        )
        rec_row = next(r for r in rows if r["player"] == "Example Back" and r["stat"] == "receptions")
        self.assertAlmostEqual(rec_row["team_pass_attempts_expected"], 34.0)
        self.assertAlmostEqual(rec_row["team_bucket_throw_share"], 0.20)
        self.assertAlmostEqual(rec_row["conversion"], 0.80)
        rec_row.update({
            "suggested_dist": "poisson",
            "baseline_window_mean": 4.0,
            "baseline_n": 6,
            "season_n": 6,
        })
        quotes = [
            op.make_quote(
                sport="NFL",
                event_id="evt-nfl",
                team="NE",
                opponent="CHI",
                player="Example Back",
                stat="receptions",
                book="Pinnacle",
                line=3.5,
                over_odds=-115,
                under_odds=-105,
                retrieved_at="2026-10-22T16:00:00Z",
                source_url="https://example.test/odds",
            ),
            op.make_quote(
                sport="NFL",
                event_id="evt-nfl",
                team="NE",
                opponent="CHI",
                player="Example Back",
                stat="receptions",
                book="FanDuel",
                line=3.5,
                over_odds=-120,
                under_odds=100,
                retrieved_at="2026-10-22T16:00:00Z",
                source_url="https://example.test/odds",
            ),
        ]
        prep = fs.prepare_pipeline([rec_row], quotes, now="2026-10-22T16:05:00Z")
        self.assertEqual(len(prep), 2)
        over_cand = next(p for p in prep if p["side"] == "over")
        evaluated = pm.evaluate_candidate(over_cand)
        self.assertTrue(evaluated["engine_b"]["abstain"])
        self.assertEqual(evaluated["engine_b"]["abstain_reason"], "missing_scouting_packet")
        self.assertIsNone(evaluated["engine_b"]["mean"])


class ScriptBoundaryTests(unittest.TestCase):
    def test_script_does_not_grade_or_request_underdog(self):
        source = (SKILL_DIR / "scripts" / "fetch_slate.py").read_text(encoding="utf-8")
        self.assertNotIn("underdog.com", source.lower())
        self.assertNotIn("import pickem_math", source)
        self.assertIn("odds_providers", source)
        self.assertNotIn("espn_has_player_prop_prices", source)
        self.assertNotIn("player_prices_from_odds", source)
        self.assertIn("nhlpy", source)
        self.assertIn("api-web.nhle.com/v1", source)
        self.assertIn("nba_api", source)
        self.assertIn("LeagueDashTeamStats", source)
        self.assertIn("site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard", source)
        self.assertIn('sport_path="basketball/nba"', source)
        self.assertIn(
            "site.web.api.espn.com/apis/common/v3/sports/basketball/nba/statistics/byathlete",
            source,
        )
        self.assertNotIn("ScoreboardV3", source)
        self.assertNotIn("LeagueDashPlayerStats", source)
        self.assertIn("nflreadpy", source)
        self.assertNotIn("nflverse-data/releases", source)
        self.assertIn("load_ftn_charting", source)
        self.assertIn("read_thrown", source)
        self.assertNotIn("load_participation(", source)
        self.assertNotIn("n_blitzers", source)
        self.assertNotIn("time_to_throw", source)
        skill = skill_corpus()
        for term in ("load_ftn_charting", "first_read_target_share", "checkdown_target_share",
                     "qb_checkdown_tendency", "qb_first_read_rate", "def_forced_checkdown_rate",
                     "def_rb_target_funnel_share", "each side has at least 5 games",
                     "split is too short", "Engine A is a pure historical statistical engine",
                     "Partial bucket production cannot be relabeled full-game production"):
            self.assertIn(term, skill)



def _run_main(argv, **kwargs):
    buf = io.StringIO()
    summary = None
    code = 0
    kwargs.setdefault("context_emitter", lambda *a, **kw: {"status": "offline_fixture"})
    with redirect_stdout(buf):
        try:
            summary = fs.main(argv, **kwargs)
        except SystemExit as exc:
            code = exc.code
    return code, buf.getvalue(), summary


def _slate_row(player="Example Wing", stat="shots on goal", source="https://example.test/nhl"):
    return {
        "player": player,
        "stat": stat,
        "flag": False,
        "sport": "NHL",
        "baseline_mean": 3.0,
        "source_url": source,
    }


class FetchHardenTests(unittest.TestCase):
    def setUp(self):
        self._real_slate = fs.DEFAULT_OUT
        self._real_bytes = self._real_slate.read_bytes() if self._real_slate.exists() else None

    def tearDown(self):
        if self._real_bytes is None:
            return
        self.assertEqual(self._real_slate.read_bytes(), self._real_bytes)

    def test_sidecar_paths_follow_the_default_output(self):
        self.assertEqual(fs.meta_path_for(fs.DEFAULT_OUT), fs.SKILL_ROOT / "data" / "slate_fetch.meta.json")
        self.assertEqual(
            fs.failed_output_path(fs.DEFAULT_OUT),
            fs.SKILL_ROOT / "data" / "slate_fetch.jsonl.failed.json",
        )
        self.assertEqual(fs.FETCH_ATTEMPTS, 3)
        self.assertEqual(fs.FETCH_BACKOFF_SECONDS, (1.0, 2.0, 4.0))

    def test_all_fail_leaves_the_existing_file_untouched(self):
        def boom(name):
            def inner():
                raise TimeoutError(f"{name} timed out")

            return inner

        fetchers = {name: boom(name) for name in ("nhl", "nfl", "nba", "odds")}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "slate_fetch.jsonl"
            out.write_text("KEEP\n", encoding="utf-8")
            before = out.stat()
            original = out.read_bytes()
            code, text, summary = _run_main(
                ["--date", "2026-10-22", "--out", str(out)],
                fetchers=fetchers,
            )
            self.assertEqual(code, 2)
            self.assertIsNone(summary)
            self.assertEqual(out.read_bytes(), original)
            after = out.stat()
            self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
            self.assertEqual(after.st_ino, before.st_ino)
            failed = fs.failed_output_path(out)
            self.assertTrue(failed.exists())
            saved = json.loads(failed.read_text(encoding="utf-8"))
            printed = json.loads(text)
            self.assertFalse(printed["usable"])
            self.assertEqual(printed["missing"], ["nhl", "nfl", "nba", "odds"])
            self.assertEqual(saved["usable"], False)
            self.assertEqual(saved["missing"], printed["missing"])
            self.assertTrue(all(saved["feeds"][name]["status"] == "failed" for name in printed["missing"]))
            self.assertIn("TimeoutError", saved["feeds"]["nhl"]["notes"][0])
            meta = json.loads(fs.meta_path_for(out).read_text(encoding="utf-8"))
            self.assertFalse(meta["usable"])
            for name in ("nhl", "nfl", "nba", "odds"):
                feed = meta["feeds"][name]
                self.assertEqual(
                    set(feed),
                    {"status", "rows", "started_at", "finished_at", "notes", "source_urls"},
                )
                self.assertEqual(feed["status"], "failed")
                self.assertEqual(feed["rows"], 0)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_empty_feeds_do_not_create_a_slate_file(self):
        fetchers = {
            "nhl": lambda: ([], ["nhl: no games"]),
            "nfl": lambda: ([], ["nfl: no games"]),
            "nba": lambda: ([], "nba: no games"),
            "odds": lambda: ({}, "odds: none"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "slate_fetch.jsonl"
            code, text, _summary = _run_main(
                ["--date", "2026-10-22", "--out", str(out)],
                fetchers=fetchers,
            )
            self.assertEqual(code, 2)
            self.assertFalse(out.exists())
            printed = json.loads(text)
            self.assertFalse(printed["usable"])
            self.assertEqual(printed["missing"], ["nhl", "nfl", "nba", "odds"])
            self.assertTrue(fs.failed_output_path(out).exists())

    def test_partial_failure_preserves_rows(self):
        row = _slate_row()

        def nhl():
            return ([row], ["schedule ok"], ["https://example.test/nhl"])

        def nfl():
            return ([], ["nfl: load_schedules returned no REG game"])

        def nba():
            raise TimeoutError("timed out")

        def odds():
            return ({}, "odds: player price fields left null")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "slate_fetch.jsonl"
            out.write_text("OLD SLATE\n", encoding="utf-8")
            failed_marker = fs.failed_output_path(out)
            failed_marker.write_text('{"usable": false}\n', encoding="utf-8")
            code, text, summary = _run_main(
                ["--date", "2026-10-22", "--out", str(out)],
                fetchers={"nhl": nhl, "nfl": nfl, "nba": nba, "odds": odds},
            )
            self.assertEqual(code, 0)
            self.assertIsNotNone(summary)
            self.assertTrue(summary["usable"])
            self.assertEqual(summary["missing"], ["nfl", "nba", "odds"])
            self.assertEqual(summary["feeds"]["nhl"]["status"], "ok")
            self.assertEqual(summary["feeds"]["nhl"]["rows"], 1)
            self.assertEqual(summary["feeds"]["nba"]["status"], "failed")
            self.assertIn("TimeoutError", summary["feeds"]["nba"]["notes"][0])
            self.assertNotIn("OLD SLATE", out.read_text(encoding="utf-8"))
            saved = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(saved["player"], "Example Wing")
            self.assertEqual(saved["stat"], "shots on goal")
            printed = json.loads(text)
            self.assertTrue(printed["usable"])
            self.assertEqual(printed["missing"], ["nfl", "nba", "odds"])
            meta = json.loads(fs.meta_path_for(out).read_text(encoding="utf-8"))
            nhl_feed = meta["feeds"]["nhl"]
            self.assertEqual(nhl_feed["status"], "ok")
            self.assertEqual(nhl_feed["source_urls"], ["https://example.test/nhl"])
            self.assertTrue(nhl_feed["started_at"])
            self.assertTrue(nhl_feed["finished_at"])
            self.assertGreaterEqual(nhl_feed["finished_at"], nhl_feed["started_at"])
            self.assertEqual(meta["feeds"]["nfl"]["status"], "failed")
            self.assertFalse(failed_marker.exists())
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_replace_failure_keeps_the_original_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "slate_fetch.jsonl"
            out.write_text("ORIGINAL\n", encoding="utf-8")

            def boom(src, dst):
                raise OSError("replace failed")

            with self.assertRaises(OSError):
                fs.atomic_write_text(out, "NEW\n", replace=boom)
            self.assertEqual(out.read_text(encoding="utf-8"), "ORIGINAL\n")
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_preflight_works_offline_and_never_raises(self):
        def imports(name):
            if name == "nba_api":
                return False, "ModuleNotFoundError: nba_api"
            return True, ""

        def reach(host):
            if host == "stats.nba.com":
                return False, "dns timeout"
            if host == "github.com":
                raise TimeoutError("timed out")
            return True, "HTTP 200"

        report = fs.preflight(import_check=imports, reach_check=reach)
        self.assertFalse(report["ok"])
        text = fs.format_preflight(report)
        self.assertIn("nba_api", text)
        self.assertIn("stats.nba.com", text)
        self.assertIn("github.com (nflverse)", text)
        self.assertIn("FAIL", text)
        self.assertIn("down: nfl, nba", text)
        self.assertNotIn("down: nhl", text)

        def boom(_name):
            raise RuntimeError("offline")

        exploded = fs.preflight(import_check=boom, reach_check=boom)
        self.assertFalse(exploded["ok"])
        self.assertEqual(len(exploded["checks"]), len(fs.PREFLIGHT_IMPORTS) + len(fs.PREFLIGHT_HOSTS))
        self.assertTrue(all(not item["ok"] for item in exploded["checks"]))
        self.assertIn("RuntimeError", fs.format_preflight(exploded))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "slate_fetch.jsonl"
            code, printed, summary = _run_main(
                ["--preflight", "--out", str(out)],
                import_check=imports,
                reach_check=reach,
            )
            self.assertEqual(code, 1)
            self.assertIsNone(summary)
            self.assertFalse(out.exists())
            self.assertIn("down: nfl, nba", printed)
            self.assertIn("preflight: failed", printed)

            code, printed, summary = _run_main(
                ["--preflight", "--out", str(out)],
                import_check=lambda _name: (True, ""),
                reach_check=lambda _host: (True, "HTTP 200"),
            )
            self.assertEqual(code, 0)
            self.assertIsNone(summary)
            self.assertFalse(out.exists())
            self.assertIn("down: none", printed)
            self.assertIn("preflight: ok", printed)
            self.assertNotIn("FAIL", printed)

    def test_probe_host_stays_offline(self):
        opened = {"yes": False}

        def opener(*_args, **_kwargs):
            opened["yes"] = True
            raise AssertionError("should not open")

        def dns_fail(*_args, **_kwargs):
            raise OSError("no dns")

        ok, detail = fs.probe_host("stats.nba.com", resolver=dns_fail, opener=opener)
        self.assertFalse(ok)
        self.assertFalse(opened["yes"])
        self.assertIn("dns", detail)

        def resolver_ok(*_args, **_kwargs):
            return []

        def http_error(request, timeout=5):
            raise urllib.error.HTTPError(request.full_url, 503, "busy", None, None)

        ok, detail = fs.probe_host("api-web.nhle.com", resolver=resolver_ok, opener=http_error)
        self.assertTrue(ok)
        self.assertIn("503", detail)

        def timed_out(request, timeout=5):
            raise urllib.error.URLError(TimeoutError("timed out"))

        ok, detail = fs.probe_host("api.nhle.com", resolver=resolver_ok, opener=timed_out)
        self.assertFalse(ok)
        self.assertIn("timed out", detail.lower())


class FetchRetryTests(unittest.TestCase):
    def _http_error(self, request, code):
        return urllib.error.HTTPError(request.full_url, code, "status", None, None)

    def test_retries_5xx_and_timeouts_with_backoff_and_jitter(self):
        calls = {"n": 0}

        class Body:
            def __init__(self, payload):
                self._payload = payload

            def read(self):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        def opener(request, timeout=30):
            calls["n"] += 1
            if calls["n"] < 3:
                raise self._http_error(request, 503)
            return Body(b"payload")

        sleeps = []
        body = fs.fetch_bytes(
            "https://example.test/slate",
            opener=opener,
            sleeper=sleeps.append,
            rng=lambda: 0.0,
        )
        self.assertEqual(body, b"payload")
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleeps, [1.0, 2.0])

        calls["n"] = 0

        def opener_jitter(request, timeout=30):
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError("timed out")
            return Body(b"ok")

        sleeps = []
        body = fs.fetch_bytes(
            "https://example.test/slate",
            opener=opener_jitter,
            sleeper=sleeps.append,
            rng=lambda: 1.0,
        )
        self.assertEqual(body, b"ok")
        self.assertEqual(sleeps, [1.0 + fs.FETCH_JITTER_SECONDS])

    def test_does_not_retry_4xx_or_connection_errors(self):
        calls = {"n": 0}

        def missing(request, timeout=30):
            calls["n"] += 1
            raise self._http_error(request, 404)

        sleeps = []
        with self.assertRaises(urllib.error.HTTPError):
            fs.fetch_bytes("https://example.test/missing", opener=missing, sleeper=sleeps.append, rng=lambda: 0.0)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(sleeps, [])

        def refused(request, timeout=30):
            calls["n"] += 1
            raise urllib.error.URLError(ConnectionRefusedError("refused"))

        calls["n"] = 0
        with self.assertRaises(urllib.error.URLError):
            fs.fetch_bytes("https://example.test/refused", opener=refused, sleeper=sleeps.append, rng=lambda: 0.0)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(sleeps, [])

    def test_gives_up_after_three_timeouts(self):
        calls = {"n": 0}

        def opener(request, timeout=30):
            calls["n"] += 1
            raise urllib.error.URLError("The read operation timed out")

        sleeps = []
        with self.assertRaises(urllib.error.URLError):
            fs.fetch_bytes("https://example.test/slow", opener=opener, sleeper=sleeps.append, rng=lambda: 0.0)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleeps, [1.0, 2.0])


class GameLogTests(unittest.TestCase):
    def test_distribution_table_matches_the_helper_cut(self):
        self.assertEqual(fs.suggested_distribution("shots on goal", 1.10, 4), "poisson")
        self.assertEqual(fs.suggested_distribution("rebounds", 1.10 + 1e-9, 4), "poisson")
        self.assertEqual(fs.suggested_distribution("assists", 1.100002, 4), "negbin")
        self.assertEqual(fs.suggested_distribution("threes", 2.4, None), "negbin")
        self.assertEqual(fs.suggested_distribution("receptions", 0.9, 1), "poisson")
        self.assertEqual(fs.suggested_distribution("rush attempts", 1.5, 1), "negbin")
        self.assertEqual(fs.suggested_distribution("tackles + assists", 1.2, None), "negbin")
        self.assertEqual(fs.suggested_distribution("blocked shots", 1.0, None), "poisson")
        self.assertEqual(fs.suggested_distribution("points", 4, 6), "normal")
        self.assertEqual(fs.suggested_distribution("pra", 4, 6), "normal")
        self.assertEqual(fs.suggested_distribution("receiving yards", None, 12), "normal")
        self.assertEqual(fs.suggested_distribution("pass attempts", None, 3), "normal")
        self.assertEqual(fs.suggested_distribution("completions", 2, 4), "normal")
        self.assertEqual(fs.suggested_distribution("goalie saves", 0.4, 5), "normal")
        self.assertIsNone(fs.suggested_distribution("points", 4, 0))
        self.assertIsNone(fs.suggested_distribution("points", 4, None))
        self.assertIsNone(fs.suggested_distribution("shots on goal", None, 3))

    def test_windows_never_overlap(self):
        for count in range(0, 25):
            games = [{"value": float(index + 1), "workload": 20.0, "when": index + 1} for index in range(count)]
            if count:
                games[0]["workload"] = 30.0
            summary = fs.summarize_log(games, "shots on goal")
            self.assertEqual(summary["season_n"], count)
            baseline_n = summary["baseline_n"]
            recent_n = summary["recent_n"]
            if baseline_n is not None and recent_n is not None:
                self.assertLessEqual(baseline_n + recent_n, count)
                self.assertGreaterEqual(baseline_n, 5)
                self.assertIn(recent_n, (5, 10))
            elif baseline_n is not None:
                self.assertLessEqual(baseline_n, count)
            if summary["role_stable_n"] not in (None, 0) and baseline_n is not None:
                self.assertEqual(baseline_n + (recent_n or 0), summary["role_stable_n"])
                self.assertLessEqual(summary["role_stable_n"], count)
        plain = [{"value": float(index), "workload": None, "when": index} for index in range(1, 13)]
        summary = fs.summarize_log(plain, "receptions")
        self.assertIsNone(summary["role_stable_n"])
        self.assertEqual(summary["baseline_n"] + summary["recent_n"], summary["season_n"])
        self.assertEqual(summary["recent_n"], 5)
        self.assertAlmostEqual(summary["recent_mean"], sum(range(8, 13)) / 5)
        self.assertAlmostEqual(summary["baseline_window_mean"], sum(range(1, 8)) / 7)
        self.assertEqual(summary["workload_tonight"], None)

    def test_role_band_includes_the_20_percent_boundary(self):
        inside = [
            {"value": 1, "workload": 8, "when": 1},
            {"value": 2, "workload": 10, "when": 2},
            {"value": 3, "workload": 12, "when": 3},
        ]
        self.assertEqual(fs.summarize_log(inside, "rebounds")["role_stable_n"], 3)
        outside = [
            {"value": 1, "workload": 7, "when": 1},
            {"value": 2, "workload": 10, "when": 2},
            {"value": 3, "workload": 13, "when": 3},
        ]
        summary = fs.summarize_log(outside, "rebounds")
        self.assertEqual(summary["role_stable_n"], 1)
        self.assertEqual(summary["baseline_n"], 1)
        self.assertEqual(summary["season_n"], 3)
        self.assertLessEqual(summary["baseline_n"], summary["season_n"])
        self.assertIsNone(summary["sd"])
        self.assertEqual(summary["suggested_dist"], "poisson")
        self.assertLessEqual(summary["var_ratio"], 1.10)

    def test_missing_log_stays_null_and_does_not_copy_the_season_rate(self):
        rows = fs.nhl_rows_from_summaries(
            fs.games_from_schedule(load_json("nhl_schedule.json"), "2026-10-22"),
            load_json("nhl_skaters.json"),
            load_json("nhl_goalies.json"),
            load_json("nhl_teams.json"),
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NHL_STATS_SKATER,
        )
        wing = next(row for row in rows if row["player"] == "Example Bruins Wing")
        self.assertTrue(wing["log_missing"])
        self.assertIsNone(wing["season_n"])
        self.assertIsNone(wing["season_mean"])
        self.assertIsNone(wing["baseline_n"])
        self.assertIsNone(wing["recent_mean"])
        self.assertIsNone(wing["recent_n"])
        self.assertIsNone(wing["sd"])
        self.assertIsNone(wing["var_ratio"])
        self.assertIsNone(wing["suggested_dist"])
        self.assertIsNone(wing["baseline_workload"])
        self.assertIsNone(wing["workload_tonight"])
        self.assertIsNone(wing["prior_season_mean"])
        self.assertIsNone(wing["prior_n"])
        self.assertAlmostEqual(wing["baseline_mean"], 3.0)
        self.assertIsNone(fs.nhl_series([{"goals": 1, "toi": "20:00", "gameDate": "2026-01-01"}], "shots on goal"))
        fs.apply_log_summary(wing, None)
        self.assertTrue(wing["log_missing"])
        self.assertIsNone(wing["season_mean"])
        self.assertAlmostEqual(wing["baseline_mean"], 3.0)
        self.assertEqual(fs.nhl_stat_value({"saves": 12, "shotsAgainst": 40, "goalsAgainst": 2}, "goalie saves"), 12)
        self.assertEqual(fs.nhl_stat_value({"shotsAgainst": 30, "goalsAgainst": 5}, "goalie saves"), 25)

    def test_nhl_game_log_windows_hits_and_prior(self):
        self.assertEqual(
            fs.nhl_game_log_url(1, "20262027"),
            "https://api-web.nhle.com/v1/player/1/game-log/20262027/2",
        )
        games = fs.parse_nhl_game_log(load_json("nhl_skater_game_log.json"))
        prior = fs.parse_nhl_game_log(load_json("nhl_prior_game_log.json"))
        self.assertEqual(len(games), 12)
        series = fs.nhl_series(games, "shots on goal")
        older = fs.nhl_series(prior, "shots on goal")
        summary = fs.summarize_log(series, "shots on goal", older)
        self.assertEqual(summary["season_n"], 12)
        self.assertEqual(summary["baseline_n"], 6)
        self.assertEqual(summary["recent_n"], 5)
        self.assertLessEqual(summary["baseline_n"] + summary["recent_n"], summary["season_n"])
        self.assertEqual(summary["role_stable_n"], 11)
        self.assertAlmostEqual(summary["baseline_window_mean"], 2)
        self.assertAlmostEqual(summary["recent_mean"], 4)
        self.assertAlmostEqual(summary["last_5_mean"], 4)
        self.assertAlmostEqual(summary["last_10_mean"], 3)
        self.assertEqual(summary["season_mean"], fs._round(41 / 12))
        self.assertEqual(summary["zero_rate"], 0)
        self.assertEqual(summary["sd"], 0)
        import statistics
        combined = [item["value"] for item in series] + [item["value"] for item in older]
        variance = statistics.variance(combined)
        self.assertEqual(summary["sample_variance"], fs._round(variance))
        self.assertEqual(summary["var_ratio"], fs._round(variance / (sum(combined) / len(combined))))
        self.assertEqual(summary["suggested_dist"], "negbin")
        self.assertGreater(summary["var_ratio"], 1.10)
        self.assertAlmostEqual(summary["baseline_workload"], 20)
        self.assertIsNone(summary["workload_tonight"])
        self.assertEqual(summary["prior_n"], 4)
        self.assertAlmostEqual(summary["prior_season_mean"], 1.5)
        row = {"stat": "shots on goal", "line": 2.5, "baseline_mean": 3.0}
        fs.apply_log_summary(row, series, older)
        self.assertFalse(row["log_missing"])
        self.assertAlmostEqual(row["baseline_mean"], 3.0)
        self.assertEqual(row["hits_over"], 6)
        self.assertEqual(row["hits_under"], 6)
        self.assertEqual(row["pushes"], 0)
        self.assertEqual(row["hit_n"], 12)
        dissimilar = [{"value": 1, "workload": 5, "when": index} for index in range(4)]
        skipped = fs.summarize_log(series, "shots on goal", dissimilar)
        self.assertIsNone(skipped["prior_n"])
        self.assertIsNone(skipped["prior_season_mean"])
        spread = [{"value": value, "workload": 20, "when": index} for index, value in enumerate([0, 0, 0, 0, 0, 0, 10])]
        counted = fs.summarize_log(spread, "assists")
        self.assertEqual(counted["suggested_dist"], "negbin")
        self.assertGreater(counted["var_ratio"], 1.10)
        self.assertLessEqual(counted["baseline_n"], counted["season_n"])
        with_blocks = [dict(game, blockedShots=1 if game.get("shots") == 4 else 0) for game in games]
        slate = fs.nhl_rows_from_summaries(
            fs.games_from_schedule(load_json("nhl_schedule.json"), "2026-10-22"),
            load_json("nhl_skaters.json"),
            [],
            load_json("nhl_teams.json"),
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NHL_STATS_SKATER,
        )
        fs.attach_nhl_game_logs(slate, {"1": with_blocks}, {"1": prior}, "20262027")
        blocked = next(row for row in slate if row["stat"] == "blocked shots")
        self.assertFalse(blocked["log_missing"])
        self.assertGreater(blocked["baseline_mean"], 0)
        self.assertLessEqual(blocked["baseline_n"] + (blocked["recent_n"] or 0), blocked["season_n"])

    def test_goalie_log_uses_shots_against_minus_goals_against(self):
        games = fs.parse_nhl_game_log({"gameLog": load_json("nhl_goalie_game_log.json")})
        summary = fs.summarize_log(fs.nhl_series(games, "goalie saves"), "goalie saves")
        self.assertEqual(summary["season_n"], 6)
        self.assertEqual(summary["baseline_n"], 6)
        self.assertIsNone(summary["recent_n"])
        self.assertLessEqual(summary["baseline_n"], summary["season_n"])
        self.assertAlmostEqual(summary["baseline_window_mean"], 25)
        self.assertAlmostEqual(summary["sample_variance"], 14)
        self.assertEqual(summary["suggested_dist"], "normal")
        self.assertGreater(summary["sd"], 0)
        self.assertAlmostEqual(summary["baseline_workload"], 60)

    def test_nba_gamelog_ignores_preseason_and_builds_combos(self):
        payload = load_json("nba_gamelog.json")
        games = fs.parse_espn_gamelog(payload)
        self.assertEqual(len(games), 12)
        points = fs.nba_series(games, "points")
        summary = fs.summarize_log(points, "points")
        self.assertEqual(summary["season_n"], 12)
        self.assertEqual(summary["baseline_n"], 7)
        self.assertEqual(summary["recent_n"], 5)
        self.assertLessEqual(summary["baseline_n"] + summary["recent_n"], summary["season_n"])
        self.assertAlmostEqual(summary["baseline_window_mean"], 21)
        self.assertAlmostEqual(summary["recent_mean"], 30)
        self.assertAlmostEqual(summary["season_mean"], 24.75)
        self.assertEqual(summary["suggested_dist"], "normal")
        self.assertNotIn(99, summary["stat_log"])
        self.assertNotIn(80, summary["stat_log"])
        rows = fs.nba_rows_from_stats(
            load_json("nba_stats.json"),
            {"BOS": "NYK", "NYK": "BOS"},
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NBA_SOURCE,
        )
        wing = next(row for row in rows if row["stat"] == "points")
        self.assertTrue(wing["log_missing"])
        fs.attach_nba_game_logs(rows, {"1": games}, {}, 2027)
        wing = next(row for row in rows if row["stat"] == "points")
        self.assertAlmostEqual(wing["baseline_mean"], 22.5)
        self.assertFalse(wing["log_missing"])
        self.assertEqual(wing["season_n"], 12)
        self.assertEqual(wing["suggested_dist"], "normal")
        self.assertLessEqual(wing["baseline_n"] + wing["recent_n"], wing["season_n"])
        combos = {row["stat"] for row in rows if row["player"] == "Example Wing"}
        self.assertTrue({"pra", "pr", "pa", "ra"} <= combos)
        pra = next(row for row in rows if row["stat"] == "pra")
        self.assertAlmostEqual(pra["baseline_mean"], 33.75)
        self.assertAlmostEqual(pra["baseline_window_mean"], 30)
        self.assertEqual(pra["suggested_dist"], "normal")
        self.assertEqual(pra["season_n"], 12)
        self.assertLessEqual(pra["baseline_n"] + pra["recent_n"], pra["season_n"])

    def test_nfl_week_log_keeps_the_mixed_mean_and_splits_snaps(self):
        weeks = load_json("nfl_week_log.json")
        prior = []
        for week in range(1, 5):
            prior.append(
                {
                    "player_display_name": "Example Receiver",
                    "player_id": "WR1",
                    "team": "NE",
                    "season": 2025,
                    "season_type": "REG",
                    "week": week,
                    "game_id": f"p{week}",
                    "receptions": 2,
                    "offense_snaps": 40,
                }
            )
        rows = fs.nfl_rows_from_tables(
            fs.read_csv(load_text("nfl_games.csv")),
            [
                {
                    "player_display_name": "Example Receiver",
                    "player_id": "WR1",
                    "position": "WR",
                    "season": "2026",
                    "recent_team": "NE",
                    "games": 12,
                    "receptions": 44,
                }
            ],
            [],
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            "nflreadpy.load_player_stats",
            week_rows=weeks,
            prior_week_rows=prior,
        )
        receiver = next(row for row in rows if row["stat"] == "receptions")
        self.assertEqual(receiver["baseline_mean"], fs._round(44 / 12))
        self.assertFalse(receiver["log_missing"])
        self.assertEqual(receiver["season_n"], 12)
        self.assertEqual(receiver["role_stable_n"], 11)
        self.assertEqual(receiver["baseline_n"], 6)
        self.assertEqual(receiver["recent_n"], 5)
        self.assertLessEqual(receiver["baseline_n"] + receiver["recent_n"], receiver["season_n"])
        self.assertAlmostEqual(receiver["baseline_window_mean"], 5)
        self.assertAlmostEqual(receiver["recent_mean"], 1)
        self.assertAlmostEqual(receiver["last_5_mean"], 1)
        self.assertAlmostEqual(receiver["last_10_mean"], 3)
        self.assertAlmostEqual(receiver["baseline_workload"], 40)
        self.assertIsNone(receiver["workload_tonight"])
        self.assertEqual(receiver["sd"], 0)
        import statistics
        combined = [9] + [5] * 6 + [1] * 5 + [2] * 4
        variance = statistics.variance(combined)
        self.assertEqual(receiver["sample_variance"], fs._round(variance))
        self.assertEqual(receiver["var_ratio"], fs._round(variance / (sum(combined) / len(combined))))
        self.assertEqual(receiver["suggested_dist"], "negbin")
        self.assertEqual(receiver["prior_n"], 4)
        self.assertAlmostEqual(receiver["prior_season_mean"], 2)
        self.assertNotIn(99, receiver["stat_log"])
        self.assertEqual(receiver["teammate_splits"], [])

    def test_fetch_nhl_uses_the_game_log_endpoint_and_keeps_rows_when_it_fails(self):
        class Stats:
            def skater_stats_summary(self, **kwargs):
                return load_json("nhl_skaters.json")

            def goalie_stats_summary(self, **kwargs):
                return load_json("nhl_goalies.json")

            def team_summary(self, **kwargs):
                return load_json("nhl_teams.json")

            def player_game_log(self, player_id, season_id, game_type):
                self.calls.append((str(player_id), str(season_id), game_type))
                if str(season_id) == "20252026":
                    return load_json("nhl_prior_game_log.json") if str(player_id) == "1" else []
                if str(player_id) == "9":
                    return load_json("nhl_goalie_game_log.json")
                return load_json("nhl_skater_game_log.json")

            calls = []

        class Schedule:
            def daily_schedule(self, date=None):
                return load_json("nhl_schedule.json")

        class Client:
            stats = Stats()
            schedule = Schedule()

        urls = []

        def unused(url, timeout=30, headers=None):
            raise AssertionError(url)

        rows, notes = fs.fetch_nhl(
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            client=Client(),
            fetch=unused,
            source_urls=urls,
        )
        self.assertEqual(notes, [])
        self.assertIn("https://api-web.nhle.com/v1/player/1/game-log/20262027/2", urls)
        self.assertIn("https://api-web.nhle.com/v1/player/9/game-log/20262027/2", urls)
        wing = next(row for row in rows if row["player"] == "Example Bruins Wing")
        self.assertFalse(wing["log_missing"])
        self.assertAlmostEqual(wing["baseline_mean"], 3.0)
        self.assertEqual(wing["baseline_n"] + wing["recent_n"], 11)
        self.assertLessEqual(wing["baseline_n"] + wing["recent_n"], wing["season_n"])
        goalie = next(row for row in rows if row["stat"] == "goalie saves")
        self.assertEqual(goalie["suggested_dist"], "normal")
        self.assertAlmostEqual(goalie["baseline_mean"], 25)

        class Down(Stats):
            def player_game_log(self, player_id, season_id, game_type):
                raise RuntimeError("log down")

        class DownClient:
            stats = Down()
            schedule = Schedule()

        def down_fetch(url, timeout=30, headers=None):
            raise RuntimeError("urllib down")

        rows, notes = fs.fetch_nhl(
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            client=DownClient(),
            fetch=down_fetch,
        )
        self.assertTrue(rows)
        self.assertTrue(any("game-log" in note for note in notes))
        wing = next(row for row in rows if row["player"] == "Example Bruins Wing")
        self.assertTrue(wing["log_missing"])
        self.assertIsNone(wing["season_mean"])
        self.assertAlmostEqual(wing["baseline_mean"], 3.0)

    def test_prep_stdout_is_pipeline_json(self):
        import pickem_math as pm

        rows = fs.nhl_rows_from_summaries(
            fs.games_from_schedule(load_json("nhl_schedule.json"), "2026-10-22"),
            load_json("nhl_skaters.json"),
            [],
            load_json("nhl_teams.json"),
            "2026-10-22",
            "2026-10-22T16:00:00Z",
            fs.NHL_STATS_SKATER,
        )
        wing = rows[0]
        games = fs.parse_nhl_game_log(load_json("nhl_skater_game_log.json"))
        prior = fs.parse_nhl_game_log(load_json("nhl_prior_game_log.json"))
        fs.apply_log_summary(
            wing,
            fs.nhl_series(games, "shots on goal"),
            fs.nhl_series(prior, "shots on goal"),
        )
        missing = {
            "sport": "NHL",
            "player": "No Log Wing",
            "team": "BOS",
            "opponent": "NSH",
            "stat": "shots on goal",
            "baseline_mean": 4,
            "log_missing": True,
            "season_n": None,
            "baseline_n": None,
            "baseline_window_mean": None,
            "suggested_dist": None,
        }
        quotes = []
        for player, line, book, over, under in (
            ("Example Bruins Wing", 2.5, "Pinnacle", -130, 110),
            ("Example Bruins Wing", 2.5, "FanDuel", -135, 105),
            ("Example Bruins Wing", 3.5, "DraftKings", -110, -110),
            ("No Log Wing", 2.5, "Pinnacle", -120, 100),
            ("No Log Wing", 2.5, "Circa", -125, 105),
        ):
            quotes.append(
                op.make_quote(
                    sport="NHL",
                    event_id="game",
                    team="BOS",
                    opponent="NSH",
                    player=player,
                    stat="shots on goal",
                    book=book,
                    line=line,
                    over_odds=over,
                    under_odds=under,
                    retrieved_at="2026-10-22T16:00:00Z",
                    source_url="https://example.test/odds",
                )
            )
        now = "2026-10-22T16:05:00Z"
        payloads = fs.prepare_pipeline([wing, missing], quotes, now=now)
        self.assertEqual([item["side"] for item in payloads], ["over", "under"])
        for payload in payloads:
            self.assertEqual(payload["soft_flags"], 0)
            self.assertEqual(payload["mechanisms"], 0)
            self.assertEqual(payload["hard_veto"], "no")
            self.assertEqual(payload["data_veto"], "no")
            self.assertEqual(payload["research_checklist"], "no")
            self.assertEqual(payload["dist"], "negbin")
            self.assertAlmostEqual(payload["baseline_mean"], wing["baseline_window_mean"])
            self.assertNotEqual(payload["baseline_mean"], wing["baseline_mean"])
            self.assertEqual(payload["line"], 2.5)
            self.assertLessEqual(payload["baseline_n"] + payload["recent_n"], payload["season_n"])
            self.assertNotIn("sd", payload)
            self.assertGreater(payload["var_ratio"], 1.10)
            self.assertEqual(payload["var_ratio"], wing["var_ratio"])
            self.assertAlmostEqual(payload["retrieved_minutes_ago"], 5)
            self.assertEqual({book["book_side"] for book in payload["books"]}, {payload["side"]})
            self.assertEqual({book["line"] for book in payload["books"]}, {2.5})
            self.assertEqual({book["book"] for book in payload["books"]}, {"Pinnacle", "FanDuel"})
            for book in payload["books"]:
                spec = op.book_spec(book["book"], book["line"], book["target"], book["other"], book["book_side"])
                self.assertEqual(spec.count(":"), 4)
                self.assertTrue(spec.endswith(":" + payload["side"]))
            result = pm.evaluate_candidate(dict(payload))
            self.assertTrue(result["ok"])
            self.assertIn(result["final_rank"], {"Tier 1", "Tier 2", "Tier 3", "Watchlist", "Reject", "Unranked"})
        overlapped = dict(wing)
        overlapped["player"] = "Example Bruins Wing"
        overlapped["baseline_n"] = 20
        overlapped["recent_n"] = 20
        overlapped["season_n"] = 12
        self.assertEqual(fs.prepare_pipeline([overlapped], quotes, now=now), [])
        with tempfile.TemporaryDirectory() as tmp:
            slate = Path(tmp) / "slate_fetch.jsonl"
            quote_path = Path(tmp) / "odds_quotes.jsonl"
            slate.write_text("".join(json.dumps(row) + "\n" for row in (wing, missing)), encoding="utf-8")
            quote_path.write_text("".join(json.dumps(quote) + "\n" for quote in quotes), encoding="utf-8")
            code, text, summary = _run_main(
                ["prep", "--stdout", "--slate", str(slate), "--quotes", str(quote_path), "--now", now]
            )
        self.assertEqual(code, 0)
        self.assertEqual(summary["rows"], 2)
        lines = [json.loads(line) for line in text.splitlines() if line.strip()]
        self.assertEqual(lines, payloads)
        with redirect_stderr(io.StringIO()):
            code, text, summary = _run_main(
                ["prep", "--stdout", "--slate", str(Path(tmp) / "missing.jsonl")]
            )
        self.assertEqual(code, 1)
        self.assertEqual(text, "")


if __name__ == "__main__":
    unittest.main()
