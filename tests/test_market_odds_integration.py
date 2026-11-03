"""Static workflow contracts for archival player odds without extra requests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OddsArchiveIntegrationTests(unittest.TestCase):
    def test_morning_and_afternoon_record_without_extra_fetch(self):
        source = (ROOT / ".github/workflows/pickem-daily.yml").read_text()
        self.assertIn("market_odds_capture", source)
        self.assertIn("market_odds_settled_calibration", source)
        self.assertIn("market_odds_at_forecast", source)
        self.assertIn("data/market_odds_history/", source)
        self.assertIn("morning_odds:", source)
        self.assertIn("default: false", source)
        self.assertIn("inputs.morning_odds != true", source)
        self.assertNotIn("  schedule:", source)
        self.assertLess(source.index("step('multisport_slate'"),
                        source.index("step('market_odds_capture'"))
        self.assertLess(source.index("step('pregame_engines'"),
                        source.index("step('market_odds_at_forecast'"))

    def test_pregame_reuses_one_price_batch(self):
        source = (ROOT / ".github/workflows/pregame-verification.yml").read_text()
        self.assertEqual(source.count("--refresh-quotes"), 1)
        self.assertIn("--quote-export data/pregame_refreshed_quotes.jsonl", source)
        self.assertIn("--quotes-file data/pregame_refreshed_quotes.jsonl", source)
        self.assertIn("market_odds_pregame_capture.json", source)
        self.assertIn("bash scripts/shadow_store.sh save", source)
        self.assertNotIn("  schedule:", source)

    def test_shadow_history_persists_exact_archive(self):
        source = (ROOT / "scripts/shadow_store.sh").read_text()
        self.assertIn("IMMUTABLE_MARKET_ODDS_SNAPSHOT_CONFLICT", source)
        self.assertIn('cp -an data/market_odds_history/. "$tmpdir/tree/data/market_odds_history/"', source)
        self.assertIn("add -f data/market_odds_history/", source)
        self.assertIn('cp -an "$tmpdir/data/market_odds_history/." data/market_odds_history/', source)

    def test_never_changes_original_forecast_or_trained_model(self):
        source = (ROOT / "scripts/market_odds_archive.py").read_text()
        self.assertIn('"changes_model_weights": False', source)
        self.assertIn('"ranking_allowed": False', source)
        self.assertIn('"no_backfilled_or_post_forecast_odds": True', source)
        self.assertNotIn("puckapi.com", source.lower())
        self.assertNotIn("urllib.request", source)


if __name__ == "__main__":
    unittest.main()
