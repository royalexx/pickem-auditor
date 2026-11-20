"""Independent source population and synthetic conjugacy/algebra checks; no fitting."""
from pathlib import Path
from fractions import Fraction
from datetime import datetime,timezone
import gzip,hashlib,io,json,math,platform,subprocess,sys,unittest
import numpy as np
from scipy.integrate import quad
from scipy.special import betaln
from scipy.stats import gamma,poisson,nbinom,betabinom
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset
P=ROOT/'docs/nba_architecture/coherent_opportunity_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/complete_predictive_20261120';ARCHIVE=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive';RESULT={}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class Review(unittest.TestCase):
 def test_01_frozen_protocol_population_and_source_capability(self):
  card=json.loads((P/'PROTOCOL.json').read_bytes());addendum=json.loads((P/'PROTOCOL_ADDENDUM.json').read_bytes());cohort=json.loads((OLD/'FULL_FORECAST_COHORT.json').read_bytes());model=json.loads((OLD/'fitted_j/event_model.json').read_bytes())
  self.assertEqual(sha(P/'PROTOCOL.json'),'e12290d9021c82340ed75dfe16647d7672c42cbfd581f67273bef40e0eb6d303');self.assertEqual(card['cohort_raw_sha256'],sha(OLD/'FULL_FORECAST_COHORT.json'));self.assertEqual(card['old_model_raw_sha256'],sha(OLD/'fitted_j/event_model.json'));self.assertEqual(card['target'],cohort['game_id']);self.assertEqual(len(cohort['frozen_candidates']),35);self.assertEqual(len({p['player_id'] for p in cohort['frozen_candidates']}),35)
  args=frozen_inputs(ARCHIVE);d=build_dataset(args['raw_dir'],args['spec_path'],args['policy_path']);self.assertEqual(d['payload_sha256'],'e5cb76ef446d6651b718c6279367a7078ffa86f01b621cfbfd9c7b4d74adbd1d');included=[r for r in d['records'] if r['fit_included']]
  self.assertEqual((len(d['records']),len(included)),(698,456));self.assertTrue(all(type(r['exact_seconds']) is int and r['exact_seconds']>=30 for r in included));self.assertEqual(d['role_semantics'],'ESPN_POSITION_BIN_OBSERVED_AT_CAPTURE')
  checks=[]
  for player in model['named_players']:
   own=[r for r in included if r['player_id']==player['player_id']];peers=[r for r in included if r['player_id']!=player['player_id'] and r['role']==player['role']];self.assertGreaterEqual(len(own),5)
   for rows in (own,peers):
    for r in rows:
     c=r['official_counts'];self.assertTrue(0<=c['threePointersMade']<=c['threePointersAttempted']<=c['fieldGoalsAttempted']);self.assertTrue(0<=c['fieldGoalsMade']-c['threePointersMade']<=c['fieldGoalsAttempted']-c['threePointersAttempted']);self.assertTrue(0<=c['freeThrowsMade']<=c['freeThrowsAttempted'])
   self.assertTrue(all(sum(r['official_counts'][key] for r in peers)>0 for key in ('fieldGoalsAttempted','threePointersAttempted','freeThrowsAttempted')))
   checks.append(dict(player_id=player['player_id'],role=player['role'],own_rows=len(own),peer_rows=len(peers)))
  self.assertEqual(len(checks),14);RESULT.update(source_population=dict(records=698,included=456,excluded=242,old_games=20,named_source_capability=checks),protocol_raw_sha256=sha(P/'PROTOCOL.json'),addendum_raw_sha256=sha(P/'PROTOCOL_ADDENDUM.json'))
 def test_02_exact_rational_selector_identity(self):
  count=0
  for x in (Fraction(1,100),Fraction(1,2),Fraction(2)):
   for y in (Fraction(1,100),Fraction(1,2),Fraction(2)):
    for f in (Fraction(1,100),Fraction(1,2),Fraction(2)):
     for p2 in (Fraction(1,10),Fraction(1,2),Fraction(9,10)):
      for p3 in (Fraction(1,10),Fraction(1,2),Fraction(9,10)):
       for pft in (Fraction(1,10),Fraction(1,2),Fraction(9,10)):
        for q3 in (Fraction(0),Fraction(1,3),Fraction(1)):
         three=y*p3;non3=2*x*p2+f*pft;points=3*three+non3;s=f*pft/non3
         self.assertGreater(points,3*three);self.assertEqual(three/p3,y);self.assertEqual((points-3*three)*(1-s)/(2*p2),x);self.assertEqual((points-3*three)*s/(pft*(2+q3)),f/(2+q3));count+=1
  RESULT['exact_rational_branch_checks']=count
 def test_03_synthetic_conjugate_posterior_predictive_identities(self):
  results=[]
  for a0,b0,count,exposure,future in [(.5,1.,0,.5,3.),(36.5,181.,10,60.,20.),(2.5,3.,7,11.,5.)]:
   a,b=a0+count,b0+exposure
   for k in (0,1,5,10):
    reference,error=quad(lambda rate:gamma.pdf(rate,a,scale=1/b)*poisson.pmf(k,rate*future),0,math.inf,epsabs=1e-12,epsrel=1e-11,limit=200)
    analytic=float(nbinom.pmf(k,a,b/(b+future)));self.assertLess(abs(reference-analytic),1e-10);results.append(dict(kind='GammaPoisson',count=k,reference=reference,analytic=analytic,error=error))
  for a0,b0,made,attempts,N in [(.5,.5,0,0,0),(.5,.5,0,3,7),(12.5,28.5,13,20,30)]:
   a,b=a0+made,b0+attempts-made
   for k in range(N+1):
    coefficient=math.comb(N,k)*math.exp(-betaln(a,b))
    reference,error=quad(lambda p:coefficient*p**k*(1-p)**(N-k),0,1,weight='alg',wvar=(a-1,b-1),epsabs=1e-12,epsrel=1e-11)
    analytic=float(betabinom.pmf(k,N,a,b));self.assertLess(abs(reference-analytic),1e-10);results.append(dict(kind='BetaBinomial',count=k,reference=reference,analytic=analytic,error=error))
  RESULT['synthetic_component_predictive_checks']=results
 def test_04_numeric_roundtrip_failure_is_real_and_requires_abstention(self):
  x,y,f,p2,p3,pft=1e-300,1e100,1e-300,.5,.5,.5;three=y*p3;non3=math.fsum((2*x*p2,f*pft));points=math.fsum((3*three,non3));share=f*pft/non3
  recovered=(points-3*three)*(1-share)/(2*p2)
  self.assertGreater(x,0);self.assertEqual(recovered,0.);self.assertFalse(math.isclose(recovered,x,rel_tol=1e-10,abs_tol=0.))
  RESULT['synthetic_roundoff_counterexample']=dict(lambda2PA=x,lambda3PA=y,lambdaFTA=f,direct_non3=non3,reconstructed_non3=points-3*three,required_action='PRESERVE_DRAW_AND_FAIL_WHOLE_RUN_NOT_CLIP_OR_RESAMPLE')
 def test_05_deterministic_gzip_contract_for_synthetic_json(self):
  raw=json.dumps(dict(kind='SYNTHETIC_FORMAT_CONTROL',index=0,attempt=0,counts=[0,1,2]),sort_keys=True,separators=(',',':')).encode()
  a=gzip.compress(raw,compresslevel=9,mtime=0);b=gzip.compress(raw,compresslevel=9,mtime=0)
  self.assertEqual(a,b);self.assertEqual(a[3],0);self.assertEqual(a[4:8],b'\0'*4);self.assertEqual(gzip.decompress(a),raw)
  addendum=json.loads((P/'PROTOCOL_ADDENDUM.json').read_bytes())['trace'];self.assertLess(addendum['per_path_json_bytes'],addendum['total_json_bytes']);self.assertLess(addendum['per_path_gzip_bytes'],addendum['total_gzip_bytes'])
  RESULT['synthetic_gzip_control']=dict(raw_sha256=hashlib.sha256(raw).hexdigest(),gzip_sha256=hashlib.sha256(a).hexdigest(),python_version=platform.python_version(),no_source_or_holdout_archive_decompressed=True)
if __name__=='__main__':
 RESULT['started_at']=datetime.now(timezone.utc).isoformat();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Review));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=r.testsRun,failures=len(r.failures),errors=len(r.errors),new_fit_calls=0,new_artifacts_created=0,new_forecasts=0,new_J_runs=0,outcome_scores=0)
 (H/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not r.wasSuccessful())
