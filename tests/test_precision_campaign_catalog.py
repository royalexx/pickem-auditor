"""Offline contract tests: complete independent stat taxonomy and safe sequential cursor."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import population_history as history
import precision_campaign_catalog as catalog
import precision_training_driver as driver

class HistoricalTrainingCampaignTest(unittest.TestCase):
    def test_exact_supported_market_catalog(self):
        catalog.catalog_check()
        self.assertEqual(len(catalog.MARKETS), 31)
        actual = {(s, stat) for s, stat, _ in catalog.MARKETS}
        expected = {(sport, st) for sport in history.SPORTS
                    for st in (*history.COUNT[sport], *history.CONTINUOUS.get(sport, ()))}
        self.assertEqual(actual, expected)

    def test_exactly_one_market_and_next_one(self):
        self.assertEqual(catalog.get_market(0)["stat"], "shots on goal")
        self.assertEqual(catalog.get_market(0)["next_index"], 1)
        self.assertEqual(catalog.get_market(30)["next_index"], None)
        self.assertEqual(catalog.get_market(30)["stat"], "rushing yards")

    def test_invalid_indices_rejected(self):
        for index in (-1, 31, 1000, True):
            with self.subTest(index=index), self.assertRaises(ValueError):
                catalog.get_market(index)

    def test_no_full_cohort_capping_and_all_seasons(self):
        from datetime import date
        cfg = driver.settings({
            "SPORT":"NHL", "STAT":"shots on goal", "MODE":"pregame_fit",
            "TRAIN_FROM":"2018-10-01", "CUTOFF":"2026-10-29",
            "HOLDOUT_UNTIL":"2026-10-29", "LINE":"2.5",
            "MAX_PER_POSITION":"0", "MAX_SEASONS":"12"
        })
        self.assertEqual(cfg["max_per_position"], 0)
        self.assertEqual(cfg["max_seasons"], 12)

if __name__ == "__main__":
    unittest.main()
