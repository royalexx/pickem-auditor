"""Offline regression tests for the free odds archive; no network or API keys."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from market_odds_archive import (
    capture_records, evaluate, normalize_quote, no_vig_probability,
)

DAY = "2026-11-03"
OBSERVED = "2026-11-03T16:00:00Z"
START = "2026-11-03T23:00:00Z"


def quote(**changes):
    result = {
        "sport": "NHL", "event_id": "nhl-bos-tor",
        "event_id_namespace": "propline", "event_start": START,
        "game_date": DAY, "team": "BOS", "opponent": "TOR",
        "player": "Sample Player", "player_norm": "sample player",
        "stat": "shots on goal", "book": "FanDuel",
        "line": 2.5, "over_odds": -110, "under_odds": -110,
        "retrieved_at": "2026-11-03T15:55:00Z",
        "source_url": "https://api.prop-line.com/v1/odds?markets=player_shots_on_goal",
    }
    result.update(changes)
    return result


def forecast(**changes):
    result = {
        "game_date": DAY, "sport": "NHL",
        "event_id": "nhl-bos-tor",
        "event_id_namespace": "propline",
        "event_start": START,
        "player": "Sample Player", "team": "BOS",
        "stat": "shots on goal", "side": "over",
        "reference_line": 2.5, "forecast_at": "2026-11-03T16:10:00Z",
        "run_id": "research-afternoon-123",
        "q_model": 0.8, "actual_stat": 4,
        "outcome": "WIN",
    }
    result.update(changes)
    return result


class MarketOddsArchiveTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "odds"
        self.forecasts = Path(self.temp.name) / "forecasts.jsonl"

    def write_forecasts(self, *rows):
        self.forecasts.write_text("".join(json.dumps(r)+"\n" for r in rows),
                                  encoding="utf-8")

    def capture(self, records=None, phase="afternoon", observed=OBSERVED,
                capture_id="job-123"):
        return capture_records(
            records if records is not None else [quote()],
            phase=phase, slate_date=DAY, observed_at=observed,
            archive_root=self.root, capture_id=capture_id,
            source_status="ok")

    def test_immutable_capture_and_calibration(self):
        first = self.capture()
        self.assertEqual(first["quote_count"], 1)
        self.assertEqual(first["status"], "captured")
        self.assertEqual(self.capture(), first)
        self.write_forecasts(forecast())
        report = evaluate(archives=self.root, forecasts=self.forecasts, slate_date=DAY)
        self.assertEqual(report["same_line_market_matches"], 1)
        self.assertEqual(report["settled_nonpush_scored"], 1)
        self.assertEqual(report["by_sport_market"]["NHL:shots on goal"]["model_brier"], .04)
        self.assertEqual(report["by_sport_market"]["NHL:shots on goal"]["market_brier"], .25)
        self.assertFalse(report["changes_model_weights"])
        with self.assertRaisesRegex(ValueError, "immutable_market_odds_capture_conflict"):
            self.capture([quote(over_odds=-120)])

    def test_no_post_prediction_lookahead(self):
        self.capture(phase="pregame", observed="2026-11-03T22:00:00Z",
                     capture_id="job-124")
        self.write_forecasts(forecast())
        report = evaluate(archives=self.root, forecasts=self.forecasts)
        self.assertEqual(report["same_line_market_matches"], 0)
        self.assertIn("no_historical_same_line_market", report["excluded"])

    def test_no_alias_or_line_leakage(self):
        self.capture([quote(player="Different Player", line=3.5)])
        self.write_forecasts(forecast())
        self.assertEqual(evaluate(
            archives=self.root,forecasts=self.forecasts)["same_line_market_matches"], 0)

    def test_missing_stale_or_unapproved_price_fails_closed(self):
        invalid = [
            quote(book="Underdog Fantasy"),
            quote(under_odds=None),
            quote(event_start=None),
            quote(retrieved_at="2026-11-03T17:00:00Z"),
            quote(event_start="2026-11-03T15:30:00Z"),
            quote(game_date="2026-11-02"),
        ]
        receipt = self.capture(invalid)
        self.assertEqual(receipt["quote_count"], 0)
        self.assertEqual(receipt["status"], "no_eligible_market_quotes")
        self.assertEqual(sum(receipt["exclusions"].values()), len(invalid))

    def test_push_and_unsettled_are_not_scored(self):
        self.capture()
        self.write_forecasts(forecast(outcome="PUSH", actual_stat=2.5),
                             forecast(player="Other", actual_stat=None, outcome=""))
        report = evaluate(archives=self.root,forecasts=self.forecasts)
        self.assertEqual(report["same_line_market_matches"], 1)
        self.assertEqual(report["settled_nonpush_scored"], 0)
        self.assertEqual(report["status"], "insufficient_matched_settled_samples")

    def test_snapshot_sha_detects_tampering(self):
        receipt = self.capture()
        path = Path(receipt["archive_path"])
        raw = json.loads(path.read_text())
        raw["quotes"][0]["line"] = 22.5
        path.write_text(json.dumps(raw), encoding="utf-8")
        self.write_forecasts(forecast())
        with self.assertRaisesRegex(ValueError,"modified_market_odds_snapshot"):
            evaluate(archives=self.root, forecasts=self.forecasts)

    def test_separate_books_and_no_vig(self):
        row, state = normalize_quote(quote(),date_text=DAY,
                                     observed=__import__("datetime").datetime.fromisoformat(
                                         OBSERVED.replace("Z","+00:00")))
        self.assertEqual(state,"accepted")
        self.assertAlmostEqual(no_vig_probability(row,"over"),0.5)
        self.assertEqual(row["source_host"],"api.prop-line.com")
        self.assertNotIn("source_url",row)


if __name__ == "__main__":
    unittest.main()
