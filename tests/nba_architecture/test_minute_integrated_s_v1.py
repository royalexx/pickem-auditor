import json
import math
from pathlib import Path
import unittest
from scipy.integrate import quad
from scipy.stats import beta as beta_law,nbinom
from v2.nba_opportunity import MinuteLaw
from v2.nba_architecture.minute_integrated_s_v1 import integrate

PACK=Path(__file__).resolve().parents[2]/'docs/nba_architecture/genuine_s_prospective_20261120'

class MinuteIntegrationTests(unittest.TestCase):
    def test_real_low_and_regular_minute_laws_against_independent_scalar_integral(self):
        original=json.loads((PACK/'actual_forecast/forecast.json').read_bytes())
        for name in ('Cody Williams','Kris Murray','LaMelo Ball'):
            m=next(r for r in original['minutes'] if r['name']==name)['forecast']['distribution']
            rate=next(r for r in original['rows'] if r['name']==name and r['statistic']=='points')['forecast']['parameters']
            x=integrate(rate,m);law=MinuteLaw(**m);a,b=law.shape()
            z=sum(w*beta_law.sf(.5/l,a,b) for l,w in law.ot_components())
            self.assertAlmostEqual(z,x['retained_ordinary_exposure_probability'],places=12)
            for k in (0,1,5):
                expected=sum(w*quad(lambda u:nbinom.pmf(k,rate['alpha'],rate['beta']/(rate['beta']+l*u))*beta_law.pdf(u,a,b),.5/l,1,epsabs=1e-11)[0] for l,w in law.ot_components())/z
                self.assertAlmostEqual(expected,x['support'][k]['mass'],places=8)
            self.assertAlmostEqual(sum(r['mass'] for r in x['support']),1.,places=12)
            self.assertFalse(x['full_played_conditional_distribution'])
            self.assertIsNone(x['participation_probability'])
            self.assertGreater(x['analytic_variance_before_count_truncation'],x['matched_fixed_ordinary_control']['variance'])
            self.assertLess(x['mean_check_absolute_error'],1e-7)
            if name!='LaMelo Ball':self.assertGreater(x['excluded_sub30_probability_within_original_retained_OT'],.19)

    def test_invalid_parameters_and_unsupported_family_reject(self):
        m=dict(mean=20.,variance=64.,ot_probability=.08,ot_continuation=.2,family='beta')
        for a in (0.,-1.,float('nan'),True):
            with self.subTest(alpha=a),self.assertRaises(ValueError):integrate(dict(alpha=a,beta=200.),m)
        with self.assertRaises(ValueError):integrate(dict(alpha=20.,beta=200.),dict(m,family='truncated_lognormal'))
