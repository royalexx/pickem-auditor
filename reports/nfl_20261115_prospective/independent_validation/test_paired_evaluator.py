import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from paired_evaluator import *

class Scoring(unittest.TestCase):
    def setUp(self):
        self.a=dict(contract_id='C',original_quote_id='Q',event_id='E',player_id='P',team_id='T',stat_key='targets',period='full_game_including_overtime',line=5,model_id='J1',status='FORECAST',p_over=.4,p_under=.5,p_push=.1,pmf={'4':.5,'5':.1,'6':.4})
        self.s={k:v for k,v in self.a.items() if k in ('contract_id','original_quote_id','event_id','player_id','team_id','stat_key','period','line')};self.s.update(status='OFFICIALLY_SETTLED',official_stat=6)
    def test_binary(self):
        r=score_pair(self.a,self.s)
        self.assertAlmostEqual(r['binary_brier'],.36)
        self.assertAlmostEqual(r['three_way_brier'],.36+.25+.01)
    def test_push(self):
        self.s.update(status='PUSH',official_stat=5)
        r=score_pair(self.a,self.s)
        self.assertIsNone(r['binary_brier'])
        self.assertAlmostEqual(r['three_way_brier'],.16+.25+.81)
    def test_invalid_push(self):
        self.s.update(status='PUSH',official_stat=6)
        with self.assertRaisesRegex(ValueError,'PUSH_STATUS'):score_pair(self.a,self.s)
    def test_wrong_contract(self):
        self.s['line']=4.5
        with self.assertRaisesRegex(ValueError,'CONTRACT_IDENTITY'):score_pair(self.a,self.s)
    def test_pmf(self):
        self.assertEqual(crps_count({'2':1},2),0)
        self.assertEqual(crps_count({'2':1},3),1)
    def test_duplicate_forecast(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE_MODEL'):prepare([self.a,self.a],[self.s])
    def test_void_not_scored(self):
        self.s['status']='VOID'
        rows,counts=prepare([self.a],[self.s]);self.assertEqual(len(rows),0)
        self.assertEqual(counts['settlement_VOID'],1)
    def test_missing_compare_no_imputation(self):
        rows,_=prepare([self.a],[self.s]);p=paired(rows,'J1','market_only')
        self.assertEqual(p['status'],'NO_COMMON_SETTLED_COHORT')
    def test_good_paired_zero(self):
        a2=dict(self.a);a2['model_id']='J2'
        rows,_=prepare([self.a,a2],[self.s]);p=paired(rows,'J2','J1')
        self.assertEqual(p['matched'],1);self.assertEqual(p['mean_a_minus_b'],0)
        self.assertIsNone(p['cluster_ci95'])
    def test_invalid_mass(self):
        self.a['p_push']=0
        with self.assertRaisesRegex(ValueError,'COMPLEMENTARITY'):score_pair(self.a,self.s)

if __name__=='__main__':unittest.main(verbosity=2)