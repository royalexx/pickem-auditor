"""Independent SciPy reference check for the corrected Student-t CDF."""
import importlib.util
import math
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import bayesian_engine as be


class StudentTCDFRegression(unittest.TestCase):
    def test_student_t_cdf_against_scipy_over_symmetric_tail_grid(self):
        if importlib.util.find_spec("scipy") is None:
            self.skipTest("SciPy is an optional numerical test dependency")
        from scipy.stats import t
        for df in (.5,1,2,4,10,30,100):
            for x in (-50.,-20.,-5.,-2.,-1.,-.1,0.,.1,1.,2.,5.,20.,50.):
                with self.subTest(df=df,x=x):
                    actual=be.student_t_cdf(x,df)
                    expected=float(t.cdf(x,df))
                    self.assertTrue(math.isfinite(actual))
                    self.assertAlmostEqual(actual,expected,delta=2e-10)
                    self.assertAlmostEqual(actual+be.student_t_cdf(-x,df),1.,
                                           delta=2e-10)

    def test_probability_version_bumped_without_automatic_promotion(self):
        self.assertEqual(be.VERSION,"history-bayes-v2-cdf-fixed")


if __name__=="__main__":
    unittest.main()
