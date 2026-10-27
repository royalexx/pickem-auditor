from datetime import datetime
"""Offline tests for slate context feeds and research packet prefill."""

import json
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import context_feeds as cf
import research_packet as rp

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RETRIEVED = "2026-10-22T16:00:00Z"


def load_json(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class GameMarketTests(unittest.TestCase):
    def test_spread_and_total_from_odds_event(self):
        events = load_json("odds_api_events.json")
        markets = cf.game_markets_from_events(events, "2026-10-22", RETRIEVED)
        self.assertIn("NSH@BOS", markets)
        self.assertAlmostEqual(markets["NSH@BOS"]["spread_home"], -1.5)
        self.assertAlmostEqual(markets["NSH@BOS"]["total"], 6.5)


class WeatherTests(unittest.TestCase):
    def test_hourly_window_picks_peaks(self):
        hourly = load_json("nws_hourly.json")
        start = cf._parse_iso("2026-10-22T21:00:00-04:00")
        facts = cf.weather_from_hourly(hourly, start, 3.0, "https://example.test/hourly", RETRIEVED)
        self.assertAlmostEqual(facts["sustained_wind_mph"]["value"], 15.0)
        self.assertAlmostEqual(facts["gust_mph"]["value"], 22.0)
        self.assertEqual(facts["precip_intensity"]["value"], "light")


class AvailabilityTests(unittest.TestCase):
    def test_nba_injuries_map_to_jsonl_rows(self):
        def fake_fetch(url, timeout=15, headers=None):
            self.assertIn("injuries", url)
            return load_json("espn_nba_injuries.json")

        rows, notes = cf.fetch_nba_injuries(fake_fetch, {"Test NBA Player"}, RETRIEVED)
        self.assertEqual(notes, [])
        self.assertEqual(rows[0]["status"], "out")
        self.assertEqual(rows[0]["source_url"], cf.ESPN_NBA_INJURIES)


class PacketMergeTests(unittest.TestCase):
    def test_no_clobber_keeps_existing_fact(self):
        old = rp.empty_template("2026-10-22")
        old["availability"]["P"] = {
            "status": cf.confirmed_fact("s", "active", "https://a.test", RETRIEVED),
            "primary_source": None,
        }
        new = rp.empty_template("2026-10-22")
        new["availability"]["P"] = {"status": None, "primary_source": None}
        merged = cf.merge_packet_no_clobber(old, new)
        self.assertEqual(merged["availability"]["P"]["status"]["value"], "active")


class CollectContextTests(unittest.TestCase):
    def test_collect_builds_indoor_weather_for_nhl_garden(self):
        rows = [
            {
                "sport": "NHL",
                "player": "Example Bruins Wing",
                "team": "BOS",
                "opponent": "NSH",
                "game_date": "2026-10-22",
            }
        ]
        nhl_games = load_json("nhl_schedule.json")["games"]

        def fake_fetch(url, timeout=15, headers=None):
            if "injuries" in url:
                return {"injuries": []}
            if "gamecenter" in url:
                return load_json("nhl_gamecenter_landing.json")
            if "roster" in url:
                return {"forwards": [], "defensemen": []}
            raise AssertionError(url)

        packet, availability, _notes = cf.collect_context(
            "2026-10-22",
            rows,
            RETRIEVED,
            fetch=fake_fetch,
            odds_events=load_json("odds_api_events.json"),
            nhl_schedule_games=nhl_games,
            nfl_loader=None,
            venues=cf.load_venues(SKILL_DIR / "data" / "venues.json"),
        )
        game_key = "NSH@BOS"
        self.assertIsNone(packet["weather"][game_key]["indoor"])
        self.assertIsNone(packet["environment"][game_key]["total"])
        self.assertTrue(packet["lineup"]["BOS"]["goalie_confirmed"]["value"])


class GapsCommandTests(unittest.TestCase):
    def test_gaps_lists_null_lineup_fields(self):
        packet = rp.empty_template("2026-10-22")
        packet["index"] = {
            "by_player": {"Example Bruins Wing": {"team": "BOS", "game": "NSH@BOS", "sport": "NHL"}}
        }
        packet["weather"]["NSH@BOS"] = {field: None for field in rp.WEATHER_FIELDS}
        packet["weather"]["NSH@BOS"]["indoor"] = cf.confirmed_fact("indoor", True, "https://www.nhl.com/news/venue", RETRIEVED)
        gaps = cf.gap_paths_for_shortlist(
            packet,
            ["NHL|Example Bruins Wing|shots on goal|over"],
            now=datetime.fromisoformat(RETRIEVED.replace("Z","+00:00")),
        )
        paths = {g["path"] for g in gaps}
        self.assertIn("lineup.BOS.projected_lines", paths)
        self.assertNotIn("weather.NSH@BOS.sustained_wind_mph", paths)



    def test_collect_marks_canadian_nhl_arenas_indoor(self):
        rows = [
            {
                "sport": "NHL",
                "player": "Connor McDavid",
                "team": "EDM",
                "opponent": "CAR",
                "game_date": "2026-10-22",
            }
        ]
        nhl_games = [
            {
                "id": 2026020999,
                "season": 20262027,
                "gameState": "FUT",
                "awayTeam": {"id": 12, "abbrev": "CAR"},
                "homeTeam": {"id": 22, "abbrev": "EDM"},
            }
        ]

        def fake_fetch(url, timeout=15, headers=None):
            if "injuries" in url:
                return {"injuries": []}
            if "gamecenter" in url:
                return {"homeTeam": {"abbrev": "EDM"}, "awayTeam": {"abbrev": "CAR"}}
            if "roster" in url:
                return {"forwards": [], "defensemen": [], "goalies": []}
            raise AssertionError(url)

        packet, _avail, _notes = cf.collect_context(
            "2026-10-22",
            rows,
            RETRIEVED,
            fetch=fake_fetch,
            nhl_schedule_games=nhl_games,
            venues=cf.load_venues(SKILL_DIR / "data" / "venues.json"),
        )
        self.assertIsNone(packet["weather"]["CAR@EDM"]["indoor"])
        gaps = cf.gap_paths_for_shortlist(
            packet,
            ["NHL|Connor McDavid|shots on goal|over"],
            now=datetime.fromisoformat(RETRIEVED.replace("Z","+00:00")),
        )
        gap_paths = {g["path"] for g in gaps}
        self.assertIn("weather.CAR@EDM.indoor", gap_paths)

    def test_nhl_availability_fetches_both_rosters_and_handles_v1_dict_names(self):
        games = [
            {
                "sport": "NHL",
                "away": "NSH",
                "home": "BOS",
                "game": "NSH@BOS",
                "nhl_game_id": 2026020154,
                "nhl_season": 20262027,
            }
        ]

        def fake_fetch(url, timeout=15, headers=None):
            if "gamecenter" in url:
                return {
                    "homeTeam": {
                        "abbrev": "BOS",
                        "goalie": {
                            "firstName": {"default": "Jeremy"},
                            "lastName": {"default": "Swayman"},
                            "confirmed": True,
                        },
                    },
                    "awayTeam": {
                        "abbrev": "NSH",
                        "goalie": {
                            "firstName": {"default": "Juuse"},
                            "lastName": {"default": "Saros"},
                            "confirmed": False,
                        },
                    },
                }
            if "/roster/BOS/" in url:
                return {
                    "forwards": [
                        {
                            "firstName": {"default": "Home"},
                            "lastName": {"default": "Skater"},
                            "injury": {"status": "Out"},
                        }
                    ],
                    "defensemen": [],
                    "goalies": [],
                }
            if "/roster/NSH/" in url:
                return {
                    "forwards": [],
                    "defensemen": [],
                    "goalies": [
                        {
                            "firstName": {"default": "Away"},
                            "lastName": {"default": "Goalie"},
                            "injury": {"status": "Questionable"},
                        }
                    ],
                }
            raise AssertionError(url)

        rows, lineup, _notes = cf.fetch_nhl_availability(
            fake_fetch,
            games,
            {"Home Skater", "Away Goalie"},
            RETRIEVED,
        )
        by_player = {r["player"]: r for r in rows}
        self.assertEqual(by_player["Home Skater"]["team"], "BOS")
        self.assertEqual(by_player["Home Skater"]["status"], "out")
        self.assertEqual(by_player["Away Goalie"]["team"], "NSH")
        self.assertEqual(by_player["Away Goalie"]["status"], "questionable")
        self.assertEqual(lineup["BOS"]["goalie_confirmed"]["quote"], "Jeremy Swayman")

    def test_hourly_weather_preserves_peak_intensity_wind_range_and_snow(self):
        hourly = {
            "properties": {
                "periods": [
                    {
                        "startTime": "2026-10-22T21:00:00-04:00",
                        "windSpeed": "10 to 18 mph",
                        "windGust": "25",
                        "probabilityOfPrecipitation": {"value": 75},
                        "shortForecast": "Heavy Snow",
                    },
                    {
                        "startTime": "2026-10-22T22:00:00-04:00",
                        "windSpeed": "8 mph",
                        "windGust": None,
                        "probabilityOfPrecipitation": {"value": 10},
                        "shortForecast": "Partly Cloudy",
                    },
                ]
            }
        }
        start = cf._parse_iso("2026-10-22T21:00:00-04:00")
        facts = cf.weather_from_hourly(hourly, start, 3.0, "https://example.test/hourly", RETRIEVED)
        self.assertAlmostEqual(facts["sustained_wind_mph"]["value"], 18.0)
        self.assertEqual(facts["precip_intensity"]["value"], "heavy")
        self.assertTrue(facts["snow"]["value"])


if __name__ == "__main__":
    unittest.main()
