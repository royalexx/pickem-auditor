"""Independent oracles for the shared Student-t probability calculation."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import bayesian_engine as be
import bayesian_usage as bu

try:
    from scipy.stats import t as scipy_t
except ImportError:
    scipy_t = None


class StudentTReferenceTests(unittest.TestCase):
    def test_closed_form_cauchy_and_df_two(self):
        # Neither oracle shares incomplete-beta implementation code.
        for x in [-100., -10., -2., -1.7, -1., -.1, 0., .1, 1., 1.7, 2., 10., 100.]:
            with self.subTest(df=1, x=x):
                self.assertAlmostEqual(be.student_t_cdf(x, 1),
                    .5 + math.atan(x)/math.pi, delta=2e-13)
            with self.subTest(df=2, x=x):
                self.assertAlmostEqual(be.student_t_cdf(x, 2),
                    .5 + x/(2*math.sqrt(2+x*x)), delta=2e-13)

    def test_monotonicity_symmetry_and_branch_continuity(self):
        for df in [1, 2, 5, 11, 30, 100, 1000]:
            xs = [i/100 for i in range(-1000, 1001)]
            probs = [be.student_t_cdf(x, df) for x in xs]
            with self.subTest(df=df):
                self.assertTrue(all(0 <= p <= 1 for p in probs))
                self.assertTrue(all(left <= right for left,right in zip(probs,probs[1:])))
                for left,right in zip(probs,reversed(probs)):
                    self.assertAlmostEqual(left+right, 1., delta=2e-14)
                switch = math.sqrt(3*df/(df+2))
                self.assertLess(abs(be.student_t_cdf(switch+1e-8,df)-
                                    be.student_t_cdf(switch-1e-8,df)), 1e-8)

    @unittest.skipIf(scipy_t is None, 'independent SciPy numerical oracle unavailable')
    def test_independent_scipy_grid_and_branch_edges(self):
        for df in [1, 2, 5, 11, 30, 100, 1000]:
            switch = math.sqrt(3*df/(df+2))
            xs = [i/40 for i in range(-800,801)] + [switch-1e-10,switch+1e-10]
            for x in xs:
                with self.subTest(df=df,x=x):
                    self.assertAlmostEqual(be.student_t_cdf(x,df),
                        float(scipy_t.cdf(x,df)), delta=2e-12)

    @unittest.skipIf(scipy_t is None, 'independent SciPy numerical oracle unavailable')
    def test_normal_predictive_whole_line_mass_near_former_nonmonotone_region(self):
        # df=100, location=92, scale=5 puts line 100's bounds at t=1.5 and 1.7.
        prior=dict(kappa0=6.,alpha0=3.,beta0=25*50*100/101,mean0=92.)
        out=be._normal_predictive([92.]*94,prior,line=100.)
        expected_under=float(scipy_t.cdf(1.5,100))
        expected_upper=float(scipy_t.cdf(1.7,100))
        self.assertAlmostEqual(out['q_under'],expected_under,delta=2e-12)
        self.assertAlmostEqual(out['q_push'],expected_upper-expected_under,delta=2e-12)
        self.assertGreater(out['q_push'],0.)
        self.assertAlmostEqual(out['q_over']+out['q_under']+out['q_push'],1.,delta=2e-14)

    @unittest.skipIf(scipy_t is None, 'independent SciPy numerical oracle unavailable')
    def test_usage_workload_quantiles_against_independent_inverse(self):
        for df in [11,30,100]:
            for i,got in enumerate(bu._t_quantiles(df)):
                expected=float(scipy_t.ppf((i+.5)/bu.GRID_WORKLOAD,df))
                with self.subTest(df=df,i=i):
                    # The x*x beta transform rounds to 1 very near zero;
                    # its existing median plateau is at most 1e-7 here.
                    tolerance=1e-7 if i==bu.GRID_WORKLOAD//2 else 2e-10
                    self.assertAlmostEqual(got,expected,delta=tolerance)

    @unittest.skipIf(scipy_t is None, 'independent SciPy numerical oracle unavailable')
    def test_usage_normal_predictive_whole_and_half_lines(self):
        pairs=[(str(i),float(20+i%7),float(12+i%6)) for i in range(20)]
        peers=[[(str(i),float(18+j+i%7),float(12+i%6)) for i in range(20)]
               for j in range(5)]
        exposure=bu.workload_posterior(pairs,peers)['posterior']
        conversion=bu._normal_conversion(pairs,peers)
        for line in [23.,23.5]:
            out=bu.forecast(pairs,peers,dist='normal',line=line,side='over',
                           stat='receiving yards',sport='NFL')
            under=push=0.
            for i in range(bu.GRID_WORKLOAD):
                z=float(scipy_t.ppf((i+.5)/bu.GRID_WORKLOAD,exposure['df']))
                w=math.exp(exposure['mu']+exposure['predictive_scale']*z)
                loc=w*conversion['mu']
                scale=math.sqrt(conversion['beta']/conversion['alpha']*
                                (1+w*w/conversion['kappa']))
                low=line-.5 if line.is_integer() else line
                below=float(scipy_t.cdf(low,2*conversion['alpha'],loc=loc,scale=scale))
                under+=below
                if line.is_integer():
                    push+=float(scipy_t.cdf(line+.5,2*conversion['alpha'],loc=loc,scale=scale))-below
            under/=bu.GRID_WORKLOAD;push/=bu.GRID_WORKLOAD
            # Allow propagation of the documented sub-1e-7 median plateau.
            self.assertAlmostEqual(out['q_under'],under,delta=2e-9)
            self.assertAlmostEqual(out['q_push'],push,delta=2e-9)
            self.assertAlmostEqual(out['q_over'],1-under-push,delta=2e-9)


if __name__ == '__main__':
    unittest.main()
