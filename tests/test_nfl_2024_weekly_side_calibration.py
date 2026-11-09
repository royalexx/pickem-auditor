"""Leakage-safe rolling side-market calibration tests (no sportsbook data)."""
import math
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import nfl_2024_weekly_side_calibration as c


def case(week,market,side,conf,win):
    """Synthetic side-conditioned training example."""
    p=conf if side=="over" else 1-conf
    # Actual stat at a half-integer line: binary no push.
    over=win if side=="over" else not win
    return {"week":week,"market":market,"p_over_hurdle":p,
            "actual_stat":2 if over else 1,
            "research_line":1.5}


class ChronologicalCalibrationTests(unittest.TestCase):
    def training(self):
        rows=[]
        for wk in range(1,5):
            for side in ("over","under"):
                for j in range(120):
                    # High model confidence but only 2/3 selected sides win.
                    rows.append(case(wk,"pass attempts",side,.92,j%3!=0))
        return rows

    def test_same_week_or_future_calibration_leak_blocked(self):
        rows=self.training()
        with self.assertRaisesRegex(RuntimeError,"current_or_future"):
            c.fit_prior_weeks(rows,4)

    def test_over_and_under_market_models_are_separate(self):
        fit=c.fit_prior_weeks(self.training(),5)
        self.assertIsNotNone(fit["markets"][("under","pass attempts")])
        self.assertIsNotNone(fit["markets"][("over","pass attempts")])
        self.assertEqual(fit["trained_through_week"],4)
        for side in ("over","under"):
            item=case(5,"pass attempts",side,.92,True)
            x=c.predict(item,fit)
            self.assertEqual(x["scope"],"market_side")
            self.assertGreater(x["p_over_calibrated"],0)
            self.assertLess(x["p_over_calibrated"],1)
            conf=(x["p_over_calibrated"] if side=="over"
                  else 1-x["p_over_calibrated"])
            self.assertLess(conf,.92)
            self.assertGreater(conf,.5)

    def test_history_is_only_first_four_weeks(self):
        fit=c.fit_prior_weeks(self.training(),5)
        for r in self.training():
            self.assertLess(r["week"],5)
        with self.assertRaisesRegex(RuntimeError,"this_or_future"):
            c.predict(case(4,"pass attempts","under",.9,True),fit)

    def test_push_is_not_mislabeled_under(self):
        row=case(2,"targets","under",.8,True)
        row["actual_stat"]=row["research_line"]
        self.assertIsNone(c.choice(row))


if __name__=="__main__":
    unittest.main()
