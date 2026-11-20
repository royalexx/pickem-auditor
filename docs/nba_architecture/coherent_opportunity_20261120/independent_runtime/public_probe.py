"""Independent coherent kernel controls. All fixtures explicitly synthetic."""
from pathlib import Path
import copy,collections,gzip,json,math,os,sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tests.nba_joint.test_coherent_predictive_v1 import coherent_fixture
from v2.nba_joint import coherent_predictive_v1 as k
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
HERE=Path(os.environ.get('COHERENT_REVIEW_OUT',Path(__file__).resolve().parent));HERE.mkdir(parents=True,exist_ok=True);RESULT={}
def seal(x):x.pop('payload_sha256');x['payload_sha256']=digest(canonical(x));return x
class Kernel(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.trace=Path(cls.temp.name)/'trace';cls.model,cls.cohort=coherent_fixture();cls.bank=k.generate(cls.model,cls.cohort,cls.trace,seed=5,n=3)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def test_01_component_to_unchanged_selector_algebra(self):
  spec=self.model['named_players'][0];checks=0
  for seed in range(200):
   d=k.draw_parameters(spec,np.random.default_rng(seed));a=d['attempt_rates'];r=d['rates'];self.assertEqual(set(r),{'points','threes','turnovers','rebounds','assists'});self.assertGreaterEqual(r['points'],3*r['threes']);self.assertAlmostEqual(r['points'],3*a['threePA']*d['p3']+2*a['twoPA']*d['p2']+a['FTA']*d['pft'],12);self.assertAlmostEqual(r['turnovers'],a['TO'],12)
   for q in (.01,.5,.99):
    w3=r['threes']/d['p3'];w2=(r['points']-3*r['threes'])*(1-d['ft_share'])/(2*d['p2']);wft=(r['points']-3*r['threes'])*d['ft_share']/(d['pft']*(2+q));self.assertAlmostEqual(w3,a['threePA'],11);self.assertAlmostEqual(w2,a['twoPA'],11);self.assertAlmostEqual(wft*(2+q),a['FTA'],11);checks+=1
  for attack in ('points','threes','share','missing','badshape'):
   v=copy.deepcopy(spec)
   if attack in ('points','threes'):v['rates'][attack]={'alpha':1.,'beta':1.}
   if attack=='share':v['ft_non3_point_share']={'alpha':1.,'beta':1.}
   if attack=='missing':v['attempt_posteriors'].pop('TO')
   if attack=='badshape':v['attempt_posteriors']['threePA']['alpha']=True
   with self.subTest(attack=attack),self.assertRaises(ValueError):k.draw_parameters(v,np.random.default_rng(1))
  RESULT['branch_weight_checks']=checks
 def test_02_one_measure_all280_rows_combos_and_MC_limits(self):
  self.assertEqual(k.validate_bank(self.bank,self.trace,self.model)['scenarios'],3);rows=k.rows(self.bank);self.assertEqual((len(rows),sum(r['samples'] is not None for r in rows)),(280,112));lookup={(r['player_id'],r['statistic']):r for r in rows};view=k.SharedForecast(self.bank);pairs=0
  for r in rows:
   if r['samples'] is None:self.assertEqual(view.query(player_id=r['player_id'],statistic=r['statistic'],kind='pmf',value=0)['status'],'ABSTAINED');continue
   self.assertEqual(len(r['samples']),3);self.assertEqual(r['scenario_ids'],[0,1,2]);self.assertIsNone(r['genuine_participation_probability']);self.assertIsNone(r['legal_eligibility'])
   for kind,value in (('pmf',0),('cdf',10),('oup',10.5)):
    kw=dict(player_id=r['player_id'],statistic=r['statistic'],kind=kind,value=value);a=view.query(channel='S4',**kw);b=view.query(channel='J',**kw);self.assertEqual(a,b);self.assertFalse(a['independent_vote']);self.assertFalse(a['count_support_truncated']);self.assertFalse(a['population_exact_zero_claim']);self.assertIn('STRUCTURAL',a['validation_scope']);pairs+=1
  for pid in {r['player_id'] for r in rows if r['samples'] is not None}:
   p,r,a=(lookup[(pid,s)]['samples'] for s in ('points','rebounds','assists'));t=lookup[(pid,'threes')]['samples'];self.assertTrue(all(x>=3*y for x,y in zip(p,t)))
   for stat,expected in [('pr',[x+y for x,y in zip(p,r)]),('pa',[x+y for x,y in zip(p,a)]),('ra',[x+y for x,y in zip(r,a)]),('pra',[x+y+z for x,y,z in zip(p,r,a)])]:self.assertEqual(lookup[(pid,stat)]['samples'],expected)
  q=view.query(player_id='A0',statistic='points',kind='pmf',value=1000000);self.assertEqual(q['hits'],[0]);ci=q['componentwise_MC_95_family_intervals'][0];self.assertEqual(ci['lower'],0);self.assertAlmostEqual(ci['upper'],1-.025**(1/3),12);self.assertGreater(ci['upper'],0)
  for r in rows:
   if r['samples'] is not None:
    q=view.query(player_id=r['player_id'],statistic=r['statistic'],kind='cdf',value=0);h=q['hits'][0];ci=q['componentwise_MC_95_family_intervals'][0];n=q['n']
    if 0<h<n:
     self.assertAlmostEqual(sum(math.comb(n,j)*ci['lower']**j*(1-ci['lower'])**(n-j) for j in range(h,n+1)),.025,10);self.assertAlmostEqual(sum(math.comb(n,j)*ci['upper']**j*(1-ci['upper'])**(n-j) for j in range(h+1)),.025,10);break
  RESULT['public_query_pairs']=pairs;RESULT['denominators']={'all':280,'supported':112,'abstained':168,'primitive':140,'primitive_supported':56,'primitive_abstained':84};(HERE/'synthetic_bank.json').write_bytes(canonical(self.bank))
 def test_03_view_snapshot_survives_original_bank_mutation(self):
  bank=copy.deepcopy(self.bank);view=k.SharedForecast(bank);kw=dict(player_id='A0',statistic='points',kind='cdf',value=4);before=view.query(**kw);bank['scenarios'].clear();bank['payload_sha256']='forged';self.assertEqual(view.query(**kw),before)
 def test_04_identity_count_and_false_metadata_mutations_reject(self):
  for attack in ('team','missing','count','drop','tracebytes','duplicated_identity'):
   b=copy.deepcopy(self.bank)
   if attack=='team':next(x for x in b['cohort']['frozen_candidates'] if x['player_id']=='A0')['team_id']='B'
   if attack=='missing':next(x for x in b['cohort']['frozen_candidates'] if x['player_id']=='A0')['player_id']='REPLACED'
   if attack=='count':b['scenarios'][0]['accepted']['counts']['A'][0]['points']+=1
   if attack=='drop':b['scenarios'].pop()
   if attack=='tracebytes':b['trace_json_bytes']+=1;b['trace_gzip_bytes']+=1
   if attack=='duplicated_identity':
    s=b['scenarios'][0];slot=next(j for j,a in enumerate(s['fixed']['O']['B']['actors']) if a['player_id'] is None);identity=s['fixed']['O']['B']['actors'][slot];identity.update(kind='NAMED_SOURCE_PLAYER',player_id='A0');s['fixed']['actors']['B'][slot]['identity']=copy.deepcopy(identity);next(x for x in b['cohort']['frozen_candidates'] if x['player_id']=='A0')['team_id']='B'
   with self.subTest(attack=attack),self.assertRaises(ValueError):k.validate_bank(seal(b),self.trace,self.model if attack=='tracebytes' else None)
  m,c=coherent_fixture();next(x for x in c['frozen_candidates'] if x['player_id']=='A0')['team_id']='B'
  with tempfile.TemporaryDirectory() as temp,self.assertRaises(ValueError):k.generate(m,c,Path(temp)/'t',n=1)
 def test_05_trace_hash_traversal_and_missing_reject(self):
  original=Path.read_bytes;first=self.trace/self.bank['scenarios'][0]['proposals'][0]['path']
  def changed(path):return original(path)+(b'bad' if path==first else b'')
  with patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):k.validate_bank(self.bank,self.trace,self.model)
  b=copy.deepcopy(self.bank);packed=bytearray(first.read_bytes());packed[8]=0;changed_gzip=bytes(packed);b['scenarios'][0]['proposals'][0]['gzip_raw_sha256']=digest(changed_gzip)
  def wrong_header(path):return changed_gzip if path==first else original(path)
  with patch.object(Path,'read_bytes',wrong_header),self.assertRaises(ValueError):k.validate_bank(seal(b),self.trace,self.model)
  b=copy.deepcopy(self.bank);b['scenarios'][0]['proposals'][0]['path']='../../outside.gz'
  with self.assertRaises(ValueError):k.validate_bank(seal(b),self.trace,self.model)
  def missing(path):
   if path==first:raise FileNotFoundError('simulated missing trace')
   return original(path)
  with patch.object(Path,'read_bytes',missing),self.assertRaises((ValueError,OSError)):k.validate_bank(self.bank,self.trace,self.model)
 def test_06_execution_exhaustion_and_partial_fixed_state(self):
  for attack in ('event','resource','fixed'):
   m,c=coherent_fixture()
   if attack=='fixed':m['named_players'][0]['attempt_posteriors']['threePA']['alpha']=0
   with tempfile.TemporaryDirectory() as temp:
    if attack=='resource':
     with patch.object(k.gzip,'compress',return_value=b'x'*524289):b=k.generate(m,c,Path(temp)/'t',n=3)
    else:b=k.generate(m,c,Path(temp)/'t',n=3,event_budget=5 if attack=='event' else 4096)
    self.assertEqual((b['status'],len(b['scenarios']),len(b['failed'])),('FAILED_WHOLE_RUN',3,3));self.assertEqual(b['scenarios_dropped'],0)
    if attack=='fixed':self.assertTrue(all(s['partial_fixed'] is not None for s in b['scenarios']));self.assertTrue(b['scenarios'][0]['partial_fixed']['pending_actor']['parameter_draw']['attempt_rates'])
    if attack=='resource':self.assertTrue(all(s['proposals'][0]['raw_persisted'] is False for s in b['scenarios']))
    if attack=='event':self.assertTrue(all(s['proposals'][0]['status']=='REJECT_EXECUTION' for s in b['scenarios']))
    with self.assertRaises(ValueError):k.SharedForecast(b)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Kernel));RESULT.update(methods=result.testsRun,failures=len(result.failures),errors=len(result.errors));(HERE/'ENGINEERING_RESULTS.json').write_text(json.dumps(RESULT,sort_keys=True,indent=2)+'\n');sys.exit(not result.wasSuccessful())
