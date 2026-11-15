"""Adversarial integrity and numerical checks; real integration runs in Deepnote."""
import copy
from pathlib import Path
import tempfile
import unittest
import numpy as np
from . import models as m
from .ws1_feature_adapter import checked, audit_report, team_id

class AdapterTests(unittest.TestCase):
    def test_toronto_sunday_night_and_actual_kickoff_gate(self):
        from .test_models import fixture
        p=fixture();p["events"][0]["event_start"]="2026-11-16T01:20:00Z"
        m.validate(p)
        p["forecast_at"]="2026-11-16T01:20:00Z"
        with self.assertRaises(m.GateError):m.validate(p)

    def test_team_namespace_alias(self):
        self.assertEqual(team_id("LAR"),"LA")
        self.assertEqual(team_id("BAL"),"BAL")
        self.assertNotEqual(team_id("NYJ"),"NYG")

    def test_hash_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'source';p.write_bytes(b'original')
            self.assertEqual(checked(d,'source',m.sha(b'original')),b'original')
            p.write_bytes(b'corrupt')
            with self.assertRaises(m.GateError):checked(d,'source',m.sha(b'original'))
    def test_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(m.GateError):checked(d,'../escape','0'*64)
    def test_integer_push_and_signed_moments(self):
        x=np.array([-2,0,1,1,3,5])
        r={'status':'forecast','contract':{'line':1},'predictive_distribution_conditional':m.distribution(x),'workload_conditional':m.summary(x),'probabilities_conditional':m.oup(x,1)}
        self.assertEqual(audit_report({'rows':[r]})['mass_mean_variance_push_reconstructions'],1)
        self.assertEqual(r['probabilities_conditional']['push'],2/6)
        r['probabilities_conditional']['push']=0
        with self.assertRaises(m.GateError):audit_report({'rows':[r]})
    def test_corrupt_moments_fail(self):
        x=np.arange(20)
        r={'status':'forecast','contract':{'line':4.5},'predictive_distribution_conditional':m.distribution(x),'workload_conditional':m.summary(x),'probabilities_conditional':m.oup(x,4.5)}
        r['workload_conditional']['sd']+=1
        with self.assertRaises(m.GateError):audit_report({'rows':[r]})

if __name__=='__main__':unittest.main()
