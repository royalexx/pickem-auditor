"""Offline tests for immutable catalog identity and NFL-first routing."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import precision_campaign_catalog as original
import precision_campaign_route as routed


class FrozenScheduleTests(unittest.TestCase):
    def test_sog_is_unchanged_and_next_market_is_nfl(self):
        self.assertEqual(routed.get_market(0)["fit_id"], original.get_market(0)["fit_id"])
        self.assertEqual(routed.get_market(0)["next_index"], 1)
        self.assertEqual(routed.get_market(1)["sport"], "NFL")
        self.assertEqual(routed.get_market(1)["stat"], "pass attempts")
        self.assertEqual(routed.get_market(1)["source_index"], 15)
        self.assertEqual(routed.get_market(1)["next_index"], 2)

    def test_all_nfl_first_no_missing_duplicate_and_31_markets(self):
        routing = [routed.get_market(i) for i in range(31)]
        self.assertEqual(len(routing), 31)
        self.assertTrue(all(x["sport"] == "NFL" for x in routing[1:17]))
        self.assertTrue(all(x["sport"] != "NFL" for x in routing[17:]))
        self.assertEqual(len({x["fit_id"] for x in routing}), 31)
        self.assertEqual({x["fit_id"] for x in routing},
                         {original.get_market(i)["fit_id"] for i in range(31)})
        self.assertEqual(routing[30]["next_index"], None)
        self.assertEqual({x["routing_sha256"] for x in routing}, {routing[0]["routing_sha256"]})

    def test_source_index_preserves_frozen_market(self):
        for i in range(31):
            item = routed.get_market(i)
            orig = original.get_market(item["source_index"])
            for key in ("sport", "stat", "fit_id", "train_from"):
                self.assertEqual(item[key], orig[key])

    def test_invalid_indices(self):
        for idx in (-1, 31, 100, True):
            with self.subTest(idx=idx), self.assertRaises(ValueError):
                routed.get_market(idx)


if __name__ == "__main__":
    unittest.main()
