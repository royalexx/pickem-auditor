"""Independent restricted-J engineering tests; fixture sources are synthetic."""
from pathlib import Path
import copy,json,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tests.nba_joint.test_residual_events_v1 import fixture
from v2.nba_joint import residual_events_v1 as e
from v2.nba_joint.residual_audit_v1 import audit_path,audit_run
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
HERE=Path(__file__).resolve().parent;RESULT={}
class JEngineering(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.run=e.simulate(fixture(),seed=41,n=1);cls.s=cls.run['scenarios'][0];cls.fixed=cls.s['fixed'];cls.path=cls.s['proposals'][-1]
 def test_01_actual_generator_independent_accounting_determinism(self):
  self.assertEqual(self.run,e.simulate(fixture(),seed=41,n=1));a=audit_run(self.run);self.assertEqual(a['scenarios'],1);self.assertEqual(a['results'][0]['violations'],0);self.assertTrue(all(r['player_id'] is None and r['source_identity_claim'] is False for team in self.fixed['O'].values() for r in team['actors'] if r['kind']=='ANONYMOUS_RESIDUAL_ACTOR_SLOT'));(HERE/'synthetic_positive_run.json').write_bytes(canonical(self.run));RESULT['synthetic_positive']={'scenarios':1,'events':len(self.path['ledger']),'OT':self.fixed['overtime_count'],'source_or_model_admission':False}
 def test_02_raw_count_score_actor_miss_FT_clock_lineup_attacks(self):
  for attack in ('count','score','actor','miss','FT','shotclock','lineup','selfassist','wrongreboundteam','quarter'):
   x=copy.deepcopy(self.path)
   if attack=='count':x['counts']['A'][0]['points']+=1
   if attack=='score':next(r for r in x['ledger'] if r['kind']=='FIELD_GOAL')['score']['A']+=1
   if attack=='actor':next(r for r in x['ledger'] if r['kind']=='FIELD_GOAL')['actor']=999
   if attack=='miss':next(r for r in x['ledger'] if r['kind']=='REBOUND')['miss']=-1
   if attack=='FT':next(r for r in x['ledger'] if r['kind']=='FREE_THROW')['number']=2
   if attack=='shotclock':next(r for r in x['ledger'] if r['kind']=='FIELD_GOAL')['shot_clock_remaining']+=1
   if attack=='lineup':next(r for r in x['ledger'] if r['kind']=='PERIOD_START')['on_court']['A']=[0]*5
   if attack=='selfassist':
    r=next(r for r in x['ledger'] if r['kind']=='FIELD_GOAL' and r['made']);r['assist']=r['actor']
   if attack=='wrongreboundteam':
    r=next(r for r in x['ledger'] if r['kind']=='REBOUND');r['team']='B' if r['team']=='A' else 'A'
   if attack=='quarter':
    r=next(r for r in x['ledger'] if r['kind']=='PERIOD_START' and r['period']==2);r['offense']='B' if r['offense']=='A' else 'A'
   with self.subTest(attack=attack),self.assertRaises(ValueError):audit_path(self.fixed,x)
 def test_03_G_O_rates_fixed_across_genuine_OT_path_rejections(self):
  original=e.fixed_scenario;event=e.event_path;fixed_hashes=[];calls=[]
  def f(*a,**kw):
   result=original(*a,**kw);calls.append(digest(canonical(result)));return result
  def path(fixed,*a,**kw):fixed_hashes.append(digest(canonical(fixed)));return event(fixed,*a,**kw)
  with patch.object(e,'fixed_scenario',f),patch.object(e,'event_path',path):run=e.simulate(fixture(),seed=9,n=1)
  self.assertEqual(run['status'],'ENGINEERING_SAMPLE');self.assertEqual(len(calls),1);self.assertTrue(all(h==calls[0] for h in fixed_hashes));s=run['scenarios'][0];self.assertEqual(s['fixed']['overtime_count'],1);self.assertGreater(s['accepted_attempt'],0);self.assertEqual(len(s['proposals']),s['accepted_attempt']+1);self.assertTrue(all(r['status']=='REJECT_OT_PATTERN' for r in s['proposals'][:-1]));audit_run(run);(HERE/'synthetic_OT_rejection_run.json').write_bytes(canonical(run));RESULT['OT_rejections']={'proposals':len(s['proposals']),'fixed_draw_calls':len(calls),'identical_fixed_hashes':len(set(fixed_hashes))==1}
 def test_04_event_and_rate_exhaustion_retains_failed_whole_run(self):
  run=e.simulate(fixture(),seed=41,n=3,event_budget=5);self.assertEqual(run['status'],'FAILED_WHOLE_RUN');self.assertEqual(len(run['failed']),3);self.assertEqual(len(run['scenarios']),run['scenario_denominator']);self.assertEqual(run['scenarios_dropped'],0);self.assertTrue(all(len(s['proposals'][0]['partial_path']['ledger'])==5 for s in run['scenarios']));
  with self.assertRaises(ValueError):audit_run(run)
  m=fixture()
  for player in m['named_players']:player['rates']['points']={'alpha':1.,'beta':1e12};player['rates']['threes']={'alpha':1.,'beta':1e-12}
  fail=e.simulate(m,seed=41,n=1);self.assertEqual(fail['status'],'FAILED_WHOLE_RUN');self.assertEqual(len(fail['scenarios']),1);partial=fail['scenarios'][0]['fixed_partial'];self.assertEqual(len(partial['rate_rejections']),4096);self.assertTrue(partial['O']);self.assertEqual(fail['scenarios'][0]['proposals'],[])
  with self.assertRaises(ValueError):audit_run(fail)
  (HERE/'synthetic_rate_exhaustion_repaired.json').write_bytes(canonical(fail));RESULT['exhaustion']={'event_scenarios_requested':3,'event_scenarios_preserved':len(run['scenarios']),'rate_scenarios_requested':1,'rate_scenarios_preserved':len(fail['scenarios']),'rate_vectors_retained':len(partial['rate_rejections'])}
 def test_05_rejected_status_and_dropped_run_cannot_pass(self):
  for attack in ('status','drop','failed'):
   x=copy.deepcopy(self.run)
   if attack=='status':x['scenarios'][0]['proposals'][-1]['status']='REJECT_EXECUTION'
   if attack=='drop':x['scenarios']=[]
   if attack=='failed':x['failed']=[{'index':0,'error':'SIMULATED_FAILURE'}]
   x.pop('payload_sha256');x['payload_sha256']=digest(canonical(x))
   with self.subTest(attack=attack),self.assertRaises(ValueError):audit_run(x)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(JEngineering));RESULT.update(methods=result.testsRun,failures=len(result.failures),errors=len(result.errors));(HERE/'ENGINEERING_RESULTS.json').write_text(json.dumps(RESULT,sort_keys=True,indent=2)+'\n');sys.exit(not result.wasSuccessful())
