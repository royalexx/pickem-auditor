"""Targeted regressions for the new opt-in research cohort and morning audit."""
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import Mock, patch

from research.p2_nhl_sog import source_pipeline as source
from research.p2_nhl_sog.slate_selection import decisions, injury_index, recent_games
from scripts import nhl_sog_full_slate as slate, nhl_sog_slate_morning as morning


START = "2026-11-25T01:00:00Z"
FREEZE = "2026-11-25T00:15:00Z"
DAY = "2026-11-24"


def listed_player(pid, name):
    first, last = name.split()
    return {"id": int(pid), "firstName": {"default": first}, "lastName": {"default": last}}


def official_game(event, away, home, start=START):
    return {"id": int(event), "startTimeUTC": start, "gameState": "FUT", "season": 20262027,
            "gameType": 2, "awayTeam": {"abbrev": away}, "homeTeam": {"abbrev": home}}


class SlateSelectionTests(unittest.TestCase):
    def test_regular_low_line_player_passes_and_rotation_and_injury_are_explicit(self):
        members = {str(i): {"team_id": "VGK", "position_group": group}
                   for i, group in [(1, "F"), (2, "F"), (3, "D"), (4, "F"), (5, "F")]}
        roster = {"forwards": [listed_player(i, f"Name Player{i}") for i in (1, 2, 4, 5)],
                  "defensemen": [listed_player(3, "Name Player3")], "goalies": []}
        feed = {"injuries": [{"id": "1", "injuries": [{"athlete": {
            "displayName": "Name Player2", "team": {"id": "1", "abbreviation": "VEG"}}}]}]}
        feed["injuries"].append({"id": "2", "injuries": [
            {"athlete": {"team": {"id": "3", "abbreviation": "NYR"}}},
            {"athlete": {"team": {"id": "2", "abbreviation": "MTL"}}},
        ]})
        injuries = injury_index(feed, ("VGK", "EDM"))
        recent = [{pid: {"observed_workload_minutes": value}
                   for pid, value in {"1": 9, "2": 14, "3": 7, "4": 11 if i else 2}.items()}
                  for i in range(5)]
        for game in recent[1:]:
            game["5"] = {"observed_workload_minutes": 15}
        assessment = decisions(members, roster, injuries["VGK"], recent)
        self.assertIsNone(assessment["1"]["reason"])
        self.assertEqual(assessment["2"]["reason"], "PREGAME_INJURY_STATUS_CONFLICT")
        self.assertEqual(assessment["3"]["reason"], "RECENT_WORKLOAD_UNCERTAIN")
        self.assertEqual(assessment["4"]["reason"], "RECENT_WORKLOAD_UNCERTAIN")
        self.assertEqual(assessment["5"]["reason"], "RECENT_DRESSING_UNCERTAIN")
        with self.assertRaisesRegex(ValueError, "INJURY_NAME_CROSSWALK_UNRESOLVED"):
            decisions(members, roster, {"unmatchedinjury"}, recent)

    def test_ambiguous_names_abstain_without_blocking_unrelated_skaters(self):
        members = {str(pid): {"team_id": "VGK", "position_group": "F"} for pid in (1, 2, 3)}
        roster = {"forwards": [listed_player(1, "Same Name"), listed_player(2, "Same Name"),
                               listed_player(3, "Different Name")],
                  "defensemen": [], "goalies": []}
        recent = [{pid: {"observed_workload_minutes": 12} for pid in members} for _ in range(5)]
        result = decisions(members, roster, {"samename"}, recent)
        self.assertEqual(result["1"]["reason"], "ROSTER_NAME_IDENTITY_AMBIGUOUS")
        self.assertEqual(result["2"]["reason"], "ROSTER_NAME_IDENTITY_AMBIGUOUS")
        self.assertIsNone(result["3"]["reason"])

    def test_team_history_uses_prior_final_and_never_target_or_future(self):
        final_games = []
        for i in range(1, 7):
            started = (source.clock(FREEZE) - timedelta(days=i)).isoformat()
            final_games.append(dict(official_game(i, "VGK", "DAL", started), gameState="OFF"))
        recent = recent_games({"games": [dict(official_game(9, "VGK", "EDM"), gameState="OFF")] +
                               final_games[::-1]}, "VGK", FREEZE)
        self.assertEqual([g["id"] for g in recent], [1, 2, 3, 4, 5])

    def test_four_staggered_games_reuse_one_scoreboard_and_recheck_identity(self):
        raw = [official_game(10 + i, away, home,
                             (source.clock(START) + timedelta(hours=i)).isoformat())
               for i, (away, home) in enumerate((("VGK", "EDM"), ("LAK", "MTL"),
                                                ("CGY", "OTT"), ("TOR", "NYI")))]
        document = {"games": raw}
        url = f"{source.OFFICIAL}/score/{DAY}"
        with (patch.object(slate, "_now", return_value=source.clock(FREEZE) - timedelta(minutes=20)),
              patch.object(slate, "capture_official", return_value={"c03_receipt": {"source_url": url,
                               "received_at": "2026-11-24T23:10:00Z"},
                           "p0_sha256": "a" * 64, "document": document}) as collect,
              TemporaryDirectory() as root):
            games, earliest, fetch, sha = slate.capture_slate_scoreboard(root, DAY, FREEZE)
            self.assertEqual(earliest, START)
            for game in games:
                result = source.signed_schedule_game(root, game, day=DAY, freeze=FREEZE, fetch=fetch)
                self.assertEqual(result["p0_sha256"], sha)
            with self.assertRaisesRegex(ValueError, "SCHEDULE_REVISED_AFTER_DISCOVERY"):
                source.signed_schedule_game(root, dict(games[2], away_team="CBJ"),
                                            day=DAY, freeze=FREEZE, fetch=fetch)
            collect.assert_called_once()
            self.assertEqual(len(list(Path(root).glob("**/schedule_versions/*/*.json.complete"))), 4)

    def test_single_window_captures_now_and_freezes_once(self):
        now = source.clock(FREEZE) - timedelta(minutes=60)
        game = source.scheduled_games({"games": [official_game(11, "VGK", "EDM")]}, day=DAY)[0]
        capture = Mock(return_value={"records": [{"player_id": "10", "manifest_sha256": "a",
                                                  "status": "SOURCE_READY_LINE_INDEPENDENT_ONLY"}]})
        forecast = Mock(return_value={"status": "FROZEN", "forecasts": ["forecast"]})
        def sleep(seconds):
            nonlocal now
            now += timedelta(seconds=seconds)
        result = slate.run_game(game, capture=capture, forecast=forecast, now=lambda: now,
                                sleep=sleep, slate_freeze=FREEZE)
        capture.assert_called_once_with(game=game, freeze=FREEZE)
        forecast.assert_called_once_with("a")
        self.assertEqual(now, source.clock(FREEZE))
        self.assertEqual(result["forecast_count"], 1)

    def test_1845_toronto_freeze_covers_1900_and_reports_every_game(self):
        freeze = "2026-11-24T23:45:00Z"
        early_start = "2026-11-24T23:30:00Z"
        starts = [early_start, "2026-11-25T00:00:00Z", "2026-11-25T00:00:00Z",
                  "2026-11-25T00:00:00Z", "2026-11-25T01:00:00Z",
                  "2026-11-25T02:15:00Z", "2026-11-25T03:00:00Z"]
        games = source.scheduled_games({"games": [official_game(i, "VGK", "EDM", start)
                                                  for i, start in enumerate(starts, 20)]}, day=DAY)
        cutoffs = {}
        def process(item, **options):
            self.assertEqual(options["slate_freeze"], freeze)
            cutoff = source.stamp(slate.game_freeze(item, options["slate_freeze"]))
            cutoffs[item["event_id"]] = cutoff
            if item["event_id"] == "20":
                return {"game": item, "status": "SOURCE_WINDOW_MISSED"}
            return {"game": item, "status": "FORECASTS_FROZEN", "forecast_count": 2, "source_players": 1}
        with (patch.object(slate, "current_storage"), patch.object(slate, "run_game", side_effect=process),
              TemporaryDirectory() as root):
            manifest = slate.run_slate(root, DAY, games=games, capture=Mock(), forecast=Mock(),
                                       code_commit="a" * 40, slate_freeze=freeze)
            self.assertEqual(manifest["scheduled_event_ids"], [str(i) for i in range(20, 27)])
            self.assertEqual(manifest["attempted_games"], 7)
            self.assertEqual(manifest["games_without_forecasts"], ["20"])
            self.assertEqual(manifest["games_without_verified_sources"], ["20"])
            self.assertEqual(len(list(Path(root).glob("**/games/*/*.complete"))), 7)
        self.assertEqual(cutoffs["20"], "2026-11-24T23:15:00Z")
        self.assertEqual({cutoffs[str(i)] for i in range(21, 27)}, {freeze})

    def test_morning_reports_played_zero_and_abstained_without_play(self):
        event = "10"
        fixture = official_game(event, "VGK", "EDM")
        game = source.scheduled_games({"games": [fixture]}, day=DAY)[0]
        fixture["gameState"] = "OFF"
        fixture["playerByGameStats"] = {
            "awayTeam": {"forwards": [{"playerId": 101, "sog": 0, "toi": "09:02"}], "defense": []},
            "homeTeam": {"forwards": [{"playerId": 103, "sog": 2, "toi": "12:10"}], "defense": []}}
        players = [{"player_id": str(pid), "team_id": "VGK", "status": status, "reasons": [],
                    "manifest_sha256": "f" if pid == 101 else None, "attempt_sha256": "p"}
                   for pid, status in [(101, "SOURCE_READY_LINE_INDEPENDENT_ONLY"),
                                       (102, "ABSTAIN_ROSTER_UNCERTAIN")]]
        with TemporaryDirectory() as root:
            receipt = slate._save(root, DAY, f"games/{event}", {
                "game": game, "status": "FORECASTS_FROZEN", "source_attempts": [{
                    "records": players, "selection_eligible": 1, "candidate_count": 2}]})
            result = morning.read_game(root, DAY, game, {"receipt": receipt}, [],
                                       fetch=lambda _: ("official", json.dumps(fixture).encode()))
            self.assertEqual(result["settlement"], "OFFICIAL_FINAL_VERIFIED")
            self.assertEqual(result["players"]["101"]["shots_on_goal"], 0)
            self.assertEqual(result["players"]["102"]["outcome"], "NO_PLAYED_APPEARANCE_IN_FINAL")
            self.assertEqual(result["played_outside_pregame_roster"], ["103"])
            box = Path(root) / result["boxscore"]["relative_path"]
            self.assertEqual(box.with_name(box.name + ".complete").read_text(),
                             result["boxscore"]["sha256"])


if __name__ == "__main__":
    unittest.main()
