"""The legacy 56-58% ranking floors must not authorize modern high-conviction labels."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import tier_quality as q


class TierQualityTests(unittest.TestCase):
    def test_legacy_floor_rejected_for_all_actual_tiers(self):
        for label in ("Tier 1","Tier 2","Tier 3"):
            d=q.assess(label,.58,blend_validated=True)
            self.assertFalse(d["eligible"])
            self.assertEqual(d["reason"],"BELOW_TIER_MODEL_PROBABILITY_FLOOR")

    def test_tier3_remarkable_and_tier2_elite(self):
        self.assertFalse(q.assess("Tier 3",.69)["eligible"])
        self.assertTrue(q.assess("Tier 3",.70)["eligible"])
        self.assertFalse(q.assess("Tier 2",.80)["eligible"])
        self.assertTrue(q.assess("Tier 2",.81)["eligible"])
        self.assertTrue(q.assess("Tier 2",.81)["target_is_observed"] is False)
        self.assertFalse(q.assess("Tier 2",.81)["empirical_hit_rate_certified"])

    def test_unicorn_needs_ninety_pct_and_calibrated_blend(self):
        self.assertFalse(q.assess("Tier 1",.89,blend_validated=True)["eligible"])
        self.assertFalse(q.assess("Tier 1",.91,blend_validated=False)["eligible"])
        self.assertTrue(q.assess("Tier 1",.91,blend_validated=True)["eligible"])

    def test_unknown_or_nonfinite_probability_never_passes(self):
        for p in (None,float("nan"),float("inf"),True,-1,1.1):
            self.assertFalse(q.assess("Tier 2",p)["eligible"])
        self.assertFalse(q.assess("Research Tier 2",.99)["eligible"])


if __name__=="__main__":
    unittest.main()
