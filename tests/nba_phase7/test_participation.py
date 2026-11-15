import copy
import unittest
import numpy as np
from v2.nba_joint import synthetic_fixture,audit
from v2.nba_joint.common import sha
from research.nba_phase7.participation import participation_aware_j2,require_participation_ready

class ParticipationTests(unittest.TestCase):
    def setUp(self):
        self.g,self.m=synthetic_fixture();self.layer={'game_id':self.g['game_id'],'evidence_kind':'synthetic_fixture','players':[
            {'player_id':p['player_id'],'team_id':p['team_id'],'eligible':True,'probability':1.} for p in self.g['players']]}
    def test_full_fixture_uses_unchanged_model(self):
        h=sha(self.m);o=participation_aware_j2(self.g,self.m,layer=self.layer,n=32,fixture=True)
        self.assertEqual(sha(o['model']),h);self.assertEqual(audit(o)['violations'],0)
    def test_inactive_zero_minutes_and_events(self):
        self.layer['players'][0].update(eligible=False,probability=0.)
        o=participation_aware_j2(self.g,self.m,layer=self.layer,n=8,fixture=True)
        self.assertTrue(np.all(o['minutes'][:,0]==0));self.assertTrue(np.all(o['stats']['points'][:,0]==0))
    def test_unknown_never_certain(self):
        self.layer['players'][0]['probability']=None
        with self.assertRaisesRegex(ValueError,'PARTICIPATION_UNKNOWN'):participation_aware_j2(self.g,self.m,layer=self.layer,n=8,fixture=True)
    def test_underfilled_sets_abort_no_rejection_conditioning(self):
        for r in self.layer['players'][:5]:r['probability']=0.
        with self.assertRaisesRegex(ValueError,'FEWER_THAN_FIVE_PARTICIPANTS'):participation_aware_j2(self.g,self.m,layer=self.layer,n=8,fixture=True)
    def test_missing_law_rejected(self):
        self.g['players'][0]['minute_features']={}
        with self.assertRaisesRegex(ValueError,'M0_LAW_UNAVAILABLE'):participation_aware_j2(self.g,self.m,layer=self.layer,fixture=True)
    def test_fixture_cannot_label_real(self):
        self.g['mode']='prospective'
        with self.assertRaisesRegex(ValueError,'FIXTURE_NOT_REAL_SOURCE'):participation_aware_j2(self.g,self.m,layer=self.layer,fixture=True)
    def test_inactive_nonzero_rejected(self):
        self.layer['players'][0]['eligible']=False
        with self.assertRaisesRegex(ValueError,'INACTIVE_PARTICIPATION_CONFLICT'):participation_aware_j2(self.g,self.m,layer=self.layer,fixture=True)
    def test_all_real_methods_remain_blocked(self):
        with self.assertRaisesRegex(ValueError,'COMPLETE_GAME_DAY_UNIVERSE_UNAVAILABLE'):require_participation_ready({'complete_game_day_universe':False})
