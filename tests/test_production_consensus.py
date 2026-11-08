import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import probability_blend as blend
import jobs


class ProductionConsensusTests(unittest.TestCase):
    def setUp(self):
        self.policy=blend.production_policy(ROOT)
        self.a={'q_win_robust':.8,'q_push_robust':.1,'observation_ids_verified':True,'sample_block':False}
        self.b={'q_win_b':.4,'q_push_b':.2,'reliable':True,'abstain':False,'baseline_origin':'collector_observations'}

    def test_full_outcome_mixture_not_average_of_conditional_values(self):
        a,b=copy.deepcopy(self.a),copy.deepcopy(self.b)
        result=blend.production_combine(a,b,self.policy)
        self.assertAlmostEqual(result['q_win'],.64)
        self.assertAlmostEqual(result['q_push'],.14)
        self.assertAlmostEqual(result['q_win']+result['q_push']+result['q_loss'],1)
        self.assertTrue(result['available'])
        self.assertTrue(result['preliminary'])
        self.assertFalse(result['ranking_allowed'])
        self.assertFalse(result['validated'])
        self.assertFalse(result['empirically_calibrated'])
        self.assertEqual(a,self.a);self.assertEqual(b,self.b)

    def test_component_failures_abstain(self):
        for change in ({'abstain':True},{'reliable':False},{'baseline_origin':'researcher'},
                       {'q_win_b':None},{'q_win_b':.95},{'q_push_b':float('nan')}):
            result=blend.production_combine(self.a,{**self.b,**change},self.policy)
            self.assertFalse(result['available']);self.assertFalse(result['ranking_allowed'])

    def test_deployed_slate_context_does_not_modify_offline_baseline(self):
        with patch.dict('os.environ',{},clear=True):
            self.assertIsNone(blend.active_production_policy(ROOT))
            with blend.using_production(ROOT):
                self.assertEqual(blend.active_production_policy(ROOT)['weight_a'],.6)
            self.assertIsNone(blend.active_production_policy(ROOT))

    def test_unavailable_consensus_never_serializes_a_as_production(self):
        result={'project':{'q_win_robust':.9,'q_push_robust':0},'grade':None,
                'blend':blend.production_combine(self.a,{**self.b,'abstain':True},self.policy)}
        record=jobs.pipeline_to_snapshot(result,meta={'game_date':'2026-11-08','sport':'NFL',
            'matchup':'A @ B','player':'Player','stat':'receptions'},run_id='test',run_at='now',
            candidate={'side':'over','line':2.5})
        self.assertIsNone(record['q_model']);self.assertIsNone(record['q_win']);self.assertIsNone(record['q_push'])
        self.assertEqual(self.policy['historical_models'],
                         ['Engine_A','Bayesian_A','Bayesian_B','NUTS'])

    def test_policy_version_changes_future_run_identity(self):
        old=jobs.shadow_run_id('2026-11-08')
        with patch('probability_blend.production_policy',return_value={**self.policy,'config_version':'other'}):
            self.assertNotEqual(old,jobs.shadow_run_id('2026-11-08'))
        self.assertEqual(old,jobs.shadow_run_id('2026-11-08'))

    def test_actual_pipeline_uses_production_mixture_and_preserves_tier1_gate(self):
        import pickem_math as pm
        from test_engine_contracts import controlled_candidate
        import scouting_engine as se
        c=controlled_candidate()
        b={**se.project_scout(c),'reliable':True,'baseline_origin':'collector_observations'}
        row=dict(id='NBA|P|points|over',stat='points',dist='poisson',side='over',line=2.5,
                 baseline_mean=3.5,baseline_n=30,observation_ids={'baseline':[str(i) for i in range(30)]},
                 soft_flags=0,mechanisms=2,hard_veto=False,data_veto=False,research_checklist=True,
                 q_market=.65,retrieved_minutes_ago=1,scouting={**c['scouting'],'historical_usage':'fixture'})
        with blend.using_production(ROOT),patch('usage_baseline.verify_a',return_value=True),patch('scouting_engine.project_scout',return_value=b):
            out=pm.evaluate_candidate(row)
        self.assertTrue(out['blend']['production_policy']);self.assertTrue(out['blend']['available'])
        self.assertIsNone(out['grade'])
        self.assertTrue(out['blend']['preliminary'])
        self.assertEqual(out['reason'],'POST_SHADOW_PRODUCTION_PENDING')
        self.assertEqual(out['final_rank'],'Unranked')


if __name__=='__main__':unittest.main()
