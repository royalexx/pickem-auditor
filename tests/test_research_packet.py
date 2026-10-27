"""Tests for research packet validation and pipeline merge."""

import json
import sys
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import research_packet as rp

NOW = datetime(2026, 10, 22, 16, 10, tzinfo=timezone.utc)
NOW_ISO = "2026-10-22T16:10:00Z"
STALE_ISO = "2026-10-22T14:00:00Z"


def make_fact(
    value,
    *,
    url="https://www.nba.com/injury",
    retrieved_at=NOW_ISO,
    quote="Official report lists status.",
):
    return {
        "fact": "test",
        "value": value,
        "source_url": url,
        "source_name": "NBA",
        "retrieved_at": retrieved_at,
        "quote": quote,
        "confidence": "confirmed",
    }


def minimal_packet(**overrides):
    base = {
        "date": "2026-10-22",
        "index": {
            "by_player": {
                "Test Player": {"team": "BOS", "game": "BOS@NSH", "sport": "NHL"},
            }
        },
        "availability": {
            "Test Player": {
                "status": make_fact("active"),
                "primary_source": make_fact("league"),
            }
        },
        "lineup": {
            "BOS": {
                "projected_lines": make_fact("line1"),
                "pairs": make_fact("pair1"),
                "pp1": make_fact("pp1"),
                "goalie_confirmed": make_fact(True),
            }
        },
        "weather": {
            "BOS@NSH": {
                "indoor": make_fact(True),
                "sustained_wind_mph": None,
                "gust_mph": None,
                "precip_prob": None,
                "precip_intensity": None,
                "window": make_fact("drop+3h"),
            }
        },
        "environment": {
            "BOS@NSH": {
                "spread": make_fact(-1.5),
                "total": make_fact(6.5),
                "back_to_back": make_fact(False),
                "rest_days": make_fact(1),
            }
        },
        "mechanisms": {},
        "role_changes": {},
        "player_context": {},
    }
    base.update(overrides)
    return base


class ValidatePacketTests(unittest.TestCase):
    def test_valid_packet_passes(self):
        validated, issues = rp.validate_packet(minimal_packet(), now=NOW)
        self.assertEqual(issues, [])
        self.assertIsNotNone(validated)

    def test_missing_source_url_rejected(self):
        packet = minimal_packet()
        packet["availability"]["Test Player"]["status"] = make_fact("active", url="")
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any("source_url" in i.message for i in issues))

    def test_unparseable_retrieved_at_rejected(self):
        packet = minimal_packet()
        packet["availability"]["Test Player"]["status"]["retrieved_at"] = "not-a-date"
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any("retrieved_at" in i.message for i in issues))

    def test_stale_availability_rejected(self):
        packet = minimal_packet()
        packet["availability"]["Test Player"]["status"] = make_fact("active", retrieved_at=STALE_ISO)
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any("older than 60" in i.message for i in issues))

    def test_stale_lineup_rejected(self):
        packet = minimal_packet()
        packet["lineup"]["BOS"]["pp1"] = make_fact("x", retrieved_at=STALE_ISO)
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any("lineup.BOS.pp1" in i.path for i in issues))

    def test_stale_weather_rejected(self):
        packet = minimal_packet()
        packet["weather"]["BOS@NSH"]["window"] = make_fact("w", retrieved_at=STALE_ISO)
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any("weather.BOS@NSH.window" in i.path for i in issues))

    def test_environment_requires_freshness(self):
        packet = minimal_packet()
        packet["environment"]["BOS@NSH"]["spread"] = make_fact(-3, retrieved_at=STALE_ISO)
        validated, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any('older than' in i.message for i in issues))
        self.assertIsNone(validated)

    def test_underdog_url_rejected(self):
        packet = minimal_packet()
        packet["availability"]["Test Player"]["status"] = make_fact(
            "active", url="https://underdogfantasy.com/lines"
        )
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any("underdog" in i.message for i in issues))

    def test_quote_over_25_words_rejected(self):
        packet = minimal_packet()
        packet["availability"]["Test Player"]["status"] = make_fact(
            "active", quote=" ".join(f"w{i}" for i in range(30))
        )
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any("quote exceeds" in i.message for i in issues))

    def test_role_change_primary_without_league_url_rejected(self):
        packet = minimal_packet()
        packet["role_changes"] = {
            "Test Player": {
                "confirmed_by_primary_source": True,
                "old_role_n": make_fact(20, url="https://example.com/blog"),
                "new_role_n": make_fact(5, url="https://example.com/blog2"),
            }
        }
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertTrue(any("primary-domain" in i.message for i in issues))

    def test_role_change_primary_with_league_url_passes(self):
        packet = minimal_packet()
        packet["role_changes"] = {
            "Test Player": {
                "confirmed_by_primary_source": True,
                "old_role_n": make_fact(20, url="https://www.nhl.com/news"),
                "new_role_n": make_fact(5, url="https://www.nhl.com/roster"),
            }
        }
        validated, issues = rp.validate_packet(packet, now=NOW)
        self.assertEqual(issues, [])
        self.assertIsNotNone(validated)

    def test_one_url_can_support_two_independent_events(self):
        url = "https://www.nhl.com/stats"
        packet = minimal_packet()
        packet["mechanisms"] = {
            "NHL|Test Player|shots on goal|over": [
                {
                    "description": "pace",
                    "type": "pace",
                    "supports_side": "over",
                    "sources": [make_fact(1, url=url), make_fact(2, url=url)],
                }
            ]
        }
        _, issues = rp.validate_packet(packet, now=NOW)
        self.assertEqual(issues, []) # two citations of the same URL in one event are allowed
        self.assertEqual(len(rp.validate_packet(packet, now=NOW)[0].mechanisms[
            "NHL|Test Player|shots on goal|over"]), 1)

    def test_null_not_found_allowed(self):
        packet = minimal_packet()
        packet["weather"]["BOS@NSH"]["gust_mph"] = None
        validated, issues = rp.validate_packet(packet, now=NOW)
        self.assertEqual(issues, [])
        self.assertNotIn("weather.BOS@NSH.gust_mph", validated.facts)


class MergePipelineTests(unittest.TestCase):
    def _prep_row(self, **extra):
        row = {
            "id": "NHL|Test Player|shots on goal|over",
            "dist": "poisson",
            "side": "over",
            "line": 2.5,
            "baseline_mean": 3.0,
            "baseline_n": 30,
            "soft_flags": 0,
            "mechanisms": 0,
            "hard_veto": "no",
            "data_veto": "no",
            "research_checklist": "no",
        }
        row.update(extra)
        return row

    def test_merge_never_fabricates_values(self):
        packet = minimal_packet()
        packet["environment"]["BOS@NSH"]["spread"] = None
        packet["player_context"] = {}
        validated, _ = rp.validate_packet(packet, now=NOW)
        merged = rp.merge_into_pipeline(validated, [self._prep_row()])
        row = merged[0]
        self.assertNotIn("spread", row)
        self.assertNotIn("minutes_tonight", row)
        self.assertNotIn("sustained_wind_mph", row)
        self.assertNotIn("ice_time_tonight", row)

    def test_merge_copies_validated_spread_and_mechanisms(self):
        url_a = "https://www.nhl.com/a"
        url_b = "https://www.nhl.com/b"
        packet = minimal_packet(
            mechanisms={
                "NHL|Test Player|shots on goal|over": [
                    {
                        "description": "shot volume",
                        "type": "pace",
                        "supports_side": "over",
                        "sources": [make_fact("high event", url=url_a)],
                    },
                    {
                        "description": "matchup",
                        "type": "scheme",
                        "supports_side": "over",
                        "sources": [make_fact("soft pk", url=url_b)],
                    },
                    {
                        "description": "other side",
                        "type": "scheme",
                        "supports_side": "under",
                        "sources": [make_fact("x", url="https://www.nhl.com/c")],
                    },
                ]
            },
            player_context={
                "Test Player": {
                    "ice_time_tonight": make_fact(18.5),
                }
            },
        )
        validated, _ = rp.validate_packet(packet, now=NOW)
        merged = rp.merge_into_pipeline(validated, [self._prep_row()])
        row = merged[0]
        self.assertEqual(row["mechanisms"], 2)
        self.assertAlmostEqual(row["spread"], 1.5)
        self.assertAlmostEqual(row["ice_time_tonight"], 18.5)

    def test_outdoor_missing_weather_sets_data_veto(self):
        packet = minimal_packet()
        packet["weather"]["BOS@NSH"] = {
            "indoor": make_fact(False),
            "sustained_wind_mph": None,
            "gust_mph": None,
            "precip_prob": None,
            "precip_intensity": None,
            "window": make_fact("kickoff+3h"),
        }
        validated, _ = rp.validate_packet(packet, now=NOW)
        merged = rp.merge_into_pipeline(validated, [self._prep_row()])
        self.assertEqual(merged[0]["data_veto"], "yes")
        self.assertEqual(merged[0].get("outdoor"), True)

    def test_questionable_player_increments_soft_flags(self):
        packet = minimal_packet()
        packet["availability"]["Test Player"]["status"] = make_fact("questionable")
        validated, _ = rp.validate_packet(packet, now=NOW)
        merged = rp.merge_into_pipeline(validated, [self._prep_row()])
        self.assertEqual(merged[0]["soft_flags"], 1)

    def test_role_change_flag_and_sample_sizes(self):
        packet = minimal_packet()
        packet["role_changes"] = {
            "Test Player": {
                "confirmed_by_primary_source": True,
                "old_role_n": make_fact(25, url="https://www.nhl.com/old"),
                "new_role_n": make_fact(6, url="https://www.nhl.com/new"),
            }
        }
        validated, _ = rp.validate_packet(packet, now=NOW)
        merged = rp.merge_into_pipeline(validated, [self._prep_row()])
        self.assertTrue(merged[0].get("role_change"))
        self.assertEqual(merged[0]["baseline_n"], 30)
        self.assertNotIn("recent_n", merged[0])
        self.assertEqual(merged[0]["role_window_issue"], "ROLE_WINDOWS_NOT_RECOMPUTED")
        self.assertEqual(merged[0]["data_veto"], "yes")


    def test_away_team_spread_is_negated_and_snow_is_merged(self):
        packet = minimal_packet()
        packet["index"]["by_player"]["Away Back"] = {
            "team": "NSH",
            "game": "NSH@BOS",
            "sport": "NFL",
            "is_home": False,
        }
        packet["index"]["by_player"]["Home Back"] = {
            "team": "BOS",
            "game": "NSH@BOS",
            "sport": "NFL",
            "is_home": True,
        }
        packet["weather"]["NSH@BOS"] = {
            "indoor": make_fact(False),
            "sustained_wind_mph": make_fact(12.0),
            "gust_mph": make_fact(18.0),
            "precip_prob": make_fact(60.0),
            "precip_intensity": make_fact("heavy"),
            "snow": make_fact(True),
            "window": make_fact("kickoff+3.5h"),
        }
        packet["environment"]["NSH@BOS"] = {
            "spread": make_fact(-7.0),
            "spread_home": make_fact(-7.0),
            "spread_away": make_fact(7.0),
            "total": make_fact(44.5),
            "back_to_back": make_fact(True),
            "away_back_to_back": make_fact(False),
            "rest_days": make_fact(0),
            "away_rest_days": make_fact(6),
        }
        validated, issues = rp.validate_packet(packet, now=NOW)
        self.assertEqual(issues, [])
        away_row = self._prep_row(id="NFL|Away Back|rushing yards|over")
        home_row = self._prep_row(id="NFL|Home Back|rushing yards|over")
        merged = rp.merge_into_pipeline(validated, [away_row, home_row])
        self.assertAlmostEqual(merged[0]["spread"], 7.0)
        self.assertFalse(merged[0]["back_to_back"])
        self.assertTrue(merged[0]["snow"])
        self.assertAlmostEqual(merged[1]["spread"], -7.0)
        self.assertTrue(merged[1]["back_to_back"])


class CliTests(unittest.TestCase):
    def test_cli_validate_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.json"
            path.write_text(json.dumps(minimal_packet()), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = rp.main(["validate", str(path), "--now", NOW_ISO])
            self.assertEqual(rc, 0)
            bad = minimal_packet()
            bad["availability"]["Test Player"]["status"] = make_fact(
                "active", url="https://underdog.com/x"
            )
            path.write_text(json.dumps(bad), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = rp.main(["validate", str(path), "--now", NOW_ISO])
            self.assertEqual(rc, 1)

    def test_cli_to_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            packet_path = Path(tmp) / "research.json"
            prep_path = Path(tmp) / "prep.jsonl"
            packet_path.write_text(json.dumps(minimal_packet()), encoding="utf-8")
            prep_path.write_text(
                json.dumps(
                    {
                        "id": "NHL|Test Player|shots on goal|over",
                        "soft_flags": 0,
                        "mechanisms": 0,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                rc = rp.main(
                    [
                        "to-pipeline",
                    "--packet",
                    str(packet_path),
                    "--prep",
                    str(prep_path),
                    "--now",
                    NOW_ISO,
                ]
            )
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
