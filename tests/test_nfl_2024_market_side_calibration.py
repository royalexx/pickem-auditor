"""Point-in-time market/side confidence calibration regression tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_2024_market_side_calibration as cal


class MarketSideCalibrationTests(unittest.TestCase):
    def row(self,week,side,market="pass attempts",p=.92,win=1):
        return dict(week=week,side=side,market=market,raw=p,win=win,
                    game_id="g"+str(week),player_id="p")

    def test_future_or_same_week_calibration_fit_veto(self):
        prev=[self.row(1,"Under"),self.row(2,"Over")]
        with self.assertRaisesRegex(RuntimeError,"future_week_or_same_week"):
            cal.fit_for_week(prev,2)
        with self.assertRaisesRegex(RuntimeError,"future_week_or_same_week"):
            cal.fit_for_week(prev,1)

    def test_unfitted_week_returns_raw_and_no_over_under_side_change(self):
        r=self.row(1,"Under",p=.98)
        f=cal.fit_for_week([],1)
        p,source,_=cal.calibrated(r,f)
        self.assertEqual(p,.98)
        self.assertEqual(source,"unfitted_raw")
        with self.assertRaisesRegex(RuntimeError,"calibrator_uses_future_labels"):
            cal.calibrated(self.row(2,"Under"),f)

    def test_separate_over_and_under_fits_are_independent(self):
        prev=[self.row(1,"Under",p=.95,win=i%2) for i in range(200)]
        over=[self.row(1,"Over",p=.95,win=1) for _ in range(200)]
        f=cal.fit_for_week(prev,2)
        self.assertIsNotNone(f["side"]["Under"])
        self.assertIsNone(f["side"]["Over"])
        r=self.row(2,"Under")
        original=cal.calibrated(r,f)
        f2=cal.fit_for_week(prev+over,2)
        self.assertAlmostEqual(original[0],cal.calibrated(r,f2)[0])

    def test_market_partial_pool_shrinks_small_market(self):
        under=[self.row(1,"Under",market="pass attempts",p=.9,win=i%2)
               for i in range(250)]
        under.extend(self.row(1,"Under",market="solo tackles",p=.9,win=(i%4==0))
                     for i in range(90))
        f=cal.fit_for_week(under,2)
        self.assertIn(("Under","solo tackles"),f["market"])
        r=self.row(2,"Under",market="solo tackles",p=.9)
        p,source,w=cal.calibrated(r,f)
        self.assertEqual(source,"side_market_partial_pool")
        self.assertAlmostEqual(w,90/(90+cal.MARKET_PSEUDO))
        self.assertTrue(0<p<1)

    def test_side_correctness_from_frozen_over_probability(self):
        a=cal.normalize(dict(week=2,game_id="a",player_id="x",
                             market="targets",p_over_hurdle=.02,actual_over=1))
        self.assertEqual(a["side"],"Under")
        self.assertEqual(a["win"],0)
        self.assertAlmostEqual(a["raw"],.98)
        b=cal.normalize(dict(week=2,game_id="a",player_id="y",
                             market="targets",p_over_hurdle=.97,actual_over=1))
        self.assertEqual(b["side"],"Over")
        self.assertEqual(b["win"],1)
        self.assertAlmostEqual(b["raw"],.97)


if __name__=="__main__":
    unittest.main()
