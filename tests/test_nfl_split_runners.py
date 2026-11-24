"""End-to-end fixture for the separate NFL acquisition, inference and validation roles."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import nfl_projected_starters_forecast as runner
import nfl_research_sources as collector

DAY = "2026-11-26"
START = "2026-11-26T21:00:00Z"
PREGAME = collector.utc("2026-11-26T20:40:00Z")
FINAL = collector.utc("2026-11-27T01:00:00Z")


class SplitNFLRunnersTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.comp = {"id": "1234", "date": START,
                     "status": {"type": {"state": "pre", "completed": False}},
                     "competitors": [
                         {"homeAway": "away", "team": {"id": "4", "abbreviation": "CIN"}},
                         {"homeAway": "home", "team": {"id": "28", "abbreviation": "WSH"}},
                     ]}
        self.chart = {"depthchart": [{"name": "Offense", "positions": {"qb": {
            "athletes": [{"id": "11"}, {"id": "12"}]}}}]}
        self.players = [("Example Starter", "00-0000001", "11"), ("Example Backup", "00-0000002", "12")]
        self.slate_rows = [{
            "sport": "NFL", "game_date": DAY, "player": name, "player_id": gsis,
            "team": "CIN", "opponent": "WAS", "stat": "completions",
            "suggested_dist": "poisson", "baseline_window_mean": 22,
            "baseline_n": 12, "season_n": 12,
        } for name, gsis, _ in self.players]
        self.quotes = [{
            "sport": "NFL", "game_date": DAY, "player": name, "player_norm": name.lower(),
            "team": "CIN", "opponent": "WAS", "event_id": "5000",
            "event_id_namespace": "propline", "event_start": START, "stat": "completions",
            "book": book, "line": 20.5, "over_odds": -110, "under_odds": -110,
            "source_url": "https://api.prop-line.com/v1/sports/americanfootball_nfl/odds",
            "retrieved_at": "2026-11-26T20:39:00Z",
        } for name, _, _ in self.players for book in ("Pinnacle", "FanDuel")]
        self.quote_path = self.root / "input.jsonl"
        self.quote_path.write_text("".join(json.dumps(q) + "\n" for q in self.quotes))

    def pregame_fetch(self, url, **kwargs):
        if url == collector.CROSSWALK:
            return ("gsis_id,display_name,espn_id\n" + "".join(
                f"{gsis},{name},{espn}\n" for name, gsis, espn in self.players)).encode()
        if "/scoreboard?" in url:
            return json.dumps({"events": [{"id": "1234", "season": {"type": 2},
                                          "competitions": [self.comp]}]}).encode()
        if url.endswith("/depthcharts"):
            return json.dumps(self.chart if "/teams/4/" in url else {}).encode()
        self.fail("Unexpected acquisition " + url)

    def collect(self):
        with (patch.object(collector, "now", return_value=PREGAME),
              patch.object(collector.slate, "utc_now", return_value=PREGAME.isoformat()),
              patch.object(collector.slate, "fetch_nfl", return_value=(self.slate_rows, [])),
              patch.object(collector.slate, "fetch_odds", side_effect=AssertionError("unexpected odds"))):
            digest, receipt = collector.collect(self.root, DAY, quotes_file=self.quote_path,
                                                fetch=self.pregame_fetch)
        self.assertEqual(receipt["slate_rows"], 2)
        self.assertEqual(receipt["quote_rows"], 4)
        return digest

    def forecast(self, digest, **kwargs):
        with patch("urllib.request.urlopen", side_effect=AssertionError("forecast must be offline")):
            return runner.forecast(self.root, digest, clock=lambda: PREGAME, **kwargs)

    def final_fetch(self, url, **kwargs):
        self.assertEqual(url, collector.SUMMARY + "?event=1234")
        return json.dumps({
            "header": {"id": "1234", "season": {"type": 2}, "competitions": [{
                **self.comp, "status": {"type": {"state": "post", "completed": True}},
            }]},
            "boxscore": {"players": [{"team": {"id": "4"}, "statistics": [{
                "name": "passing", "labels": ["C/ATT", "YDS"], "athletes": [{
                    "athlete": {"id": "11", "displayName": "Example Starter"},
                    "stats": ["21/32", "250"],
                }],
            }]}]},
        }).encode()

    def test_two_runner_flow(self):
        capture = self.collect()
        digest, report = self.forecast(capture)
        self.assertEqual(report["error"], None)
        self.assertEqual(report["abstentions"], {"player_not_projected_starter": 2})
        self.assertEqual(len(report["forecasts"]), 2)
        for row in report["forecasts"]:
            self.assertEqual(row["player"], "Example Starter")
            self.assertTrue(row["projected_starter"])
            self.assertFalse(row["availability_verified"])
            self.assertFalse(row["phase0r_original_source_certified"])
            self.assertFalse(row["publication_eligible"])
        self.assertEqual(self.forecast(capture, evaluate=lambda *a, **k: self.fail("recomputed")),
                         (digest, report))
        original = collector.read(self.root, "forecasts", digest)
        with patch.object(collector, "now", return_value=FINAL):
            _, validation = collector.validate(self.root, digest, fetch=self.final_fetch)
        self.assertEqual(validation["settled"], 2)
        self.assertEqual({row["outcome"] for row in validation["rows"]}, {"win", "loss"})
        self.assertEqual({row["forecast_id"] for row in validation["rows"]},
                         {row["forecast_id"] for row in report["forecasts"]})
        self.assertEqual(collector.read(self.root, "forecasts", digest), original)

    def test_depth_chart_conflict_and_missing_evidence(self):
        self.chart["depthchart"].append({"name": "Offense", "positions": {"qb": {
            "athletes": [{"id": "12"}, {"id": "11"}]}}})
        _, report = self.forecast(self.collect())
        self.assertFalse(report["forecasts"])
        self.assertEqual(report["abstentions"], {"projected_starter_slots_unavailable": 4})

    def test_wrong_event_and_stale_capture(self):
        self.quotes[0]["event_start"] = "2026-11-26T21:01:00Z"
        self.quote_path.write_text("".join(json.dumps(q) + "\n" for q in self.quotes))
        capture = self.collect()
        with self.assertRaisesRegex(ValueError, "stale_or_future_capture"):
            runner.forecast(self.root, capture, clock=lambda: FINAL)
        _, report = self.forecast(capture)
        self.assertFalse(report["forecasts"])
        self.assertEqual(report["abstentions"]["quote_fixture_unverified"], 2)

    def test_final_pending_and_invalid_final_identity_remain_unresolved(self):
        digest, _ = self.forecast(self.collect())
        with patch.object(collector, "now", return_value=PREGAME):
            _, pending = collector.validate(self.root, digest,
                                            fetch=lambda *args, **kwargs: self.fail("pregame final call"))
        self.assertEqual(pending["unresolved"], 2)

        def conflict(url, **kwargs):
            payload = json.loads(self.final_fetch(url))
            payload["header"]["id"] = "9999"
            return json.dumps(payload).encode()

        with patch.object(collector, "now", return_value=FINAL):
            _, result = collector.validate(self.root, digest, fetch=conflict)
        self.assertEqual(result["settled"], 0)
        self.assertEqual({row["reason"] for row in result["rows"]}, {"final_event_identity_conflict"})

    def test_tampered_model_input(self):
        capture = self.collect()
        payload = json.loads(collector.read(self.root, "capture", capture))
        checksum = payload["files"]["slate_fetch.jsonl"]
        (self.root / "model_input" / (checksum + ".bin")).write_text("{}")
        with self.assertRaisesRegex(ValueError, "model_input_hash_mismatch"):
            self.forecast(capture)

    def test_late_commit_retains_rejections_and_does_not_settle_or_recompute(self):
        capture = self.collect()
        clock_at = PREGAME

        def clock():
            return clock_at

        def evaluate(*args, **kwargs):
            nonlocal clock_at
            results = runner.jobs.run_pipeline_batch(*args, **kwargs)
            clock_at = collector.utc(START)
            return results

        digest, report = runner.forecast(self.root, capture, clock=clock, evaluate=evaluate)
        self.assertFalse(report["forecasts"])
        self.assertEqual(report["abstentions"]["forecast_commit_after_kickoff"], 2)
        with patch.object(collector, "now", return_value=FINAL):
            _, post = collector.validate(self.root, digest, fetch=self.final_fetch)
        self.assertEqual(post["settled"], 0)

    def test_missing_scoreboard_skips_history_and_odds_but_saves_failure(self):
        def unavailable(url, **kwargs):
            raise OSError("fixture transport denied")

        with (patch.object(collector.slate, "fetch_odds", side_effect=AssertionError("unexpected odds")),
              patch.object(collector.slate, "fetch_nfl", side_effect=AssertionError("unexpected history"))):
            digest, receipt = collector.collect(self.root, DAY, live_odds=True, fetch=unavailable)
        self.assertEqual(receipt["sources"]["scoreboard"]["error"], "OSError")
        self.assertEqual(receipt["errors"], ["scoreboard_source_unavailable"])
        self.assertTrue(collector.read(self.root, "capture", digest))
