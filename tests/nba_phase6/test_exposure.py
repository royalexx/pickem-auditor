import copy
import unittest
import numpy as np
from v2.nba_joint import simulate, synthetic_fixture, audit, extract_forecast
from v2.nba_joint.common import sha

class ExposureTests(unittest.TestCase):
    def setUp(self):
        self.g,self.m=synthetic_fixture()
        self.a=simulate(self.g,self.m,n=8)
    def plan(self,kind='raw_m0_diagnostic'):
        return dict(kind=kind,minutes=self.a['independent_minutes'].copy(),raw_minutes=self.a['independent_minutes'].copy(),parent_input_sha256=sha(self.g))
    def test_raw_keeps_event_mechanism_and_draws(self):
        d=simulate(self.g,self.m,n=8,research_minutes=self.plan())
        self.assertEqual(d['dependence'],'J2')
        np.testing.assert_array_equal(d['minutes'],self.a['independent_minutes'])
        np.testing.assert_array_equal(d['state']['duration'],self.a['state']['duration'])
        self.assertEqual(d['model_sha256'],self.a['model_sha256'])
        with self.assertRaisesRegex(ValueError,'DIAGNOSTIC_NOT_FORECAST'):extract_forecast(d,0,'points')
        with self.assertRaises(ValueError):audit(d)
    def test_prospective_injection_fails(self):
        g=copy.deepcopy(self.g);g['mode']='prospective'
        with self.assertRaisesRegex(ValueError,'RESEARCH_EXPOSURE_MODE'):simulate(g,self.m,n=8,research_minutes=self.plan())
    def test_parent_identity_fails(self):
        p=self.plan();p['parent_input_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'RESEARCH_EXPOSURE_PARENT'):simulate(self.g,self.m,n=8,research_minutes=p)
    def test_bad_exposure_fails(self):
        for change in ('negative','nan','cap','shape','unknown_kind'):
            p=self.plan()
            if change=='negative':p['minutes'][0,0]=-1
            elif change=='nan':p['minutes'][0,0]=np.nan
            elif change=='cap':p['minutes'][0,0]=10000
            elif change=='shape':p['minutes']=p['minutes'][:2]
            else:p['kind']='pretend_pregame'
            with self.subTest(change=change),self.assertRaises(ValueError):simulate(self.g,self.m,n=8,research_minutes=p)
    def test_raw_cannot_be_reallocated(self):
        p=self.plan();p['minutes'][0,0]+=1
        with self.assertRaisesRegex(ValueError,'RAW_EXPOSURE_CHANGED'):simulate(self.g,self.m,n=8,research_minutes=p)
    def test_oracle_requires_valid_witness(self):
        p=self.plan('postgame_appearance_oracle')
        with self.assertRaises(ValueError):simulate(self.g,self.m,n=8,research_minutes=p)
    def test_default_unchanged(self):
        b=simulate(self.g,self.m,n=8)
        self.assertEqual(self.a['output_sha256'],b['output_sha256'])
        self.assertNotIn('research_opportunity',b)
