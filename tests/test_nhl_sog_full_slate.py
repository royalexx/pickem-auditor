from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch

from scripts.nhl_sog_full_slate import discover_slate, run_game, run_slate


BASE = datetime(2026, 11, 24, tzinfo=timezone.utc)
DAY = "2026-11-23"


def game(event_id="2026020350", state="FUT"):
    return {
        "event_id": event_id,
        "away_team": "CBJ",
        "home_team": "NJD",
        "start_at": BASE.isoformat(),
        "game_state": state,
    }


class TestNhlSogFullSlate(unittest.TestCase):
    def test_official_discovery_keeps_live_and_future_events(self):
        def row(event_id, start_at, state):
            return {"id": int(event_id), "startTimeUTC": start_at.isoformat(),
                    "gameState": state, "awayTeam": {"abbrev": "CBJ"},
                    "homeTeam": {"abbrev": "NJD"}}

        games = discover_slate(DAY, probe=lambda day: {"games": [
            row("2026020350", BASE, "LIVE"),
            row("2026020351", BASE + timedelta(hours=1), "FUT"),
            row("2026020352", BASE + timedelta(days=1), "FUT"),
        ]})
        self.assertEqual([(g["event_id"], g["game_state"]) for g in games],
                         [("2026020350", "LIVE"), ("2026020351", "FUT")])

    def test_early_failure_retries_final_and_keeps_player_outcomes(self):
        clock = BASE - timedelta(minutes=66)

        def sleep(seconds):
            nonlocal clock
            clock += timedelta(seconds=seconds)

        def capture(**kwargs):
            self.assertLess(clock, BASE - timedelta(minutes=20))
            if clock == BASE - timedelta(minutes=65):
                return {"status": "BLOCKED", "records": []}
            self.assertEqual(clock, BASE - timedelta(minutes=25))
            return {"status": "SOURCE_READY", "records": [
                {"status": "SOURCE_READY_LINE_INDEPENDENT_ONLY",
                 "manifest_sha256": "signed", "player_id": "1234567"},
                {"status": "ABSTAIN", "manifest_sha256": None, "player_id": "7654321"},
            ]}

        def forecast(manifest):
            self.assertEqual(clock, BASE - timedelta(minutes=20))
            self.assertEqual(manifest, "signed")
            return {"status": "FROZEN", "forecasts": [{"kind": "plugin_poisson"}]}

        result = run_game(game(), capture=capture, forecast=forecast,
                          now=lambda: clock, sleep=sleep)
        self.assertEqual(result["status"], "FORECASTS_FROZEN")
        self.assertEqual(result["forecast_count"], 1)
        self.assertEqual(len(result["source_attempts"]), 2)
        self.assertEqual(len(result["source_attempts"][1]["records"]), 2)

    def test_missed_window_counts_game_without_fetch_or_forecast(self):
        capture, forecast = Mock(), Mock()
        result = run_game(game(), capture=capture, forecast=forecast,
                          now=lambda: BASE - timedelta(minutes=15))
        self.assertEqual(result["status"], "SOURCE_WINDOW_MISSED")
        capture.assert_not_called()
        forecast.assert_not_called()

    def test_partial_results_do_not_report_complete_slate(self):
        games = [game("2026020350"), game("2026020351"), game("2026020352", "LIVE")]

        def process(item, **kwargs):
            if item["event_id"] == "2026020351":
                raise RuntimeError("fixture failure")
            if item["game_state"] == "LIVE":
                return dict(game=item, status="EVENT_ALREADY_STARTED")
            return dict(game=item, status="FORECASTS_FROZEN", forecast_count=2)

        with patch("scripts.nhl_sog_full_slate.current_storage"), \
             patch("scripts.nhl_sog_full_slate.run_game", side_effect=process), \
             patch("scripts.nhl_sog_full_slate._save", return_value={"sha256": "receipt"}) as save:
            result = run_slate("/work", DAY, capture=Mock(), forecast=Mock(),
                               code_commit="a" * 40, games=games)

        self.assertEqual(result["scheduled_games"], 3)
        self.assertEqual(result["games_with_forecasts"], 1)
        self.assertEqual(result["distribution_forecasts"], 2)
        self.assertFalse(result["complete_forecast_coverage"])
        self.assertEqual([row["status"] for row in result["games"]],
                         ["FORECASTS_FROZEN", "GAME_RUN_FAILED", "EVENT_ALREADY_STARTED"])
        self.assertEqual(save.call_count, 4)
