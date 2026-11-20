"""Actual coherent artifact verification; one in-memory replay, never fit writer."""
from pathlib import Path
from datetime import datetime,timezone
from fractions import Fraction
from unittest.mock import patch
import copy,json,math,subprocess,sys,unittest
from scipy.special import betaln,gammaln
from scipy.stats import nbinom,betabinom
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_joint import coherent_components_v1 as F
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset
from v2.nba_architecture.conditional_c_v1 import read_native_outcomes
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
P=ROOT/'docs/nba_architecture/coherent_opportunity_20261120';H=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/complete_predictive_20261120';ARCHIVE=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive';INPUTS=frozen_inputs(ARCHIVE);RESULT={}
RAW=(P/'fitted/model.json').read_bytes();MODEL=json.loads(RAW);RECEIPT=json.loads((P/'fitted/FIT_RECEIPT.json').read_bytes());APPROVAL=json.loads((P/'independent_prefit/PREFIT_APPROVAL.json').read_bytes());OLDMODEL=json.loads((OLD/'fitted_j/event_model.json').read_bytes())
SOURCE=dict(raw_dir=OLD/'raw',population_path=OLD/'PBP_POPULATION.json',original_raw_dir=INPUTS['raw_dir'],spec_path=INPUTS['spec_path'],profile_path=OLD/'independent_c_profile/DECISION.json')
def stats(rows):
 values={k:0 for k in ('twoPA','twoPM','threePA','threePM','FTA','FTM','TO')}
 for r in rows:
  c=r['official_counts'];v=(c['fieldGoalsAttempted']-c['threePointersAttempted'],c['fieldGoalsMade']-c['threePointersMade'],c['threePointersAttempted'],c['threePointersMade'],c['freeThrowsAttempted'],c['freeThrowsMade'],c['turnovers'])
  for key,x in zip(values,v):values[key]+=x
 return dict(rows=len(rows),minutes=Fraction(sum(r['exact_seconds'] for r in rows),60),counts=values)
class ArtifactReview(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=build_dataset(INPUTS['raw_dir'],INPUTS['spec_path'],INPUTS['policy_path']);cls.included=[r for r in cls.data['records'] if r['fit_included']];cls.outcomes=read_native_outcomes(**SOURCE)
 def test_01_exact_approved_activation_source_and_clock_chain(self):
  closed=subprocess.check_output(['git','show','162ea849:v2/nba_joint/coherent_components_v1.py'],cwd=ROOT);wanted=closed.replace(b'PREFIT_SHA=None',b"PREFIT_SHA='920e576767e4b6b19615f03ee9f141e72c29294943ac32357138753c6fa2b690'")
  self.assertEqual(Path(F.__file__).read_bytes(),wanted);self.assertEqual(digest(wanted),RECEIPT['compiler_raw_sha256']);self.assertEqual(digest(RAW),RECEIPT['model_raw_sha256']);self.assertEqual(digest(RAW),'f1f6dd4a4d3753042c28b71fa9b7949628d69ccdad8f38ece47bb2ccdc6ffa2a')
  self.assertEqual(digest((P/'independent_prefit/PREFIT_APPROVAL.json').read_bytes()),RECEIPT['approval_raw_sha256']);self.assertEqual(self.data['payload_sha256'],RECEIPT['source_dataset_sha256']);self.assertEqual(self.outcomes['payload_sha256'],RECEIPT['source_outcome_payload_sha256'])
  for file,wanted in APPROVAL['exact_input_raw_sha256'].items():self.assertEqual(digest((ROOT/file).read_bytes()),wanted,file)
  for file,wanted in APPROVAL['reviewed_dependency_raw_sha256'].items():
   if file=='v2/nba_joint/coherent_components_v1.py':continue
   self.assertEqual(digest((ROOT/file).read_bytes()),wanted,file)
  for instant in [APPROVAL['decided_at'],json.loads((OLD/'independent_j_artifact/ARTIFACT_ADMISSION.json').read_bytes())['admitted_at']]+[r['ingested_at'] for r in self.outcomes['rows']]:self.assertLessEqual(instant,RECEIPT['started_at'])
  self.assertLessEqual(RECEIPT['started_at'],RECEIPT['completed_at']);self.assertLessEqual(RECEIPT['completed_at'],RECEIPT['verified_at']);self.assertLess(RECEIPT['verified_at'],APPROVAL['target_start']);self.assertEqual((RECEIPT['source_rows'],RECEIPT['ordinary_fit_rows'],RECEIPT['excluded_rows']),(698,456,242))
  command=json.loads((P/'execution/FIT_COMMAND.json').read_bytes());self.assertEqual(command['exit_code'],0);self.assertEqual(command['model_raw_sha256'],digest(RAW));self.assertEqual(command['fit_receipt_raw_sha256'],digest((P/'fitted/FIT_RECEIPT.json').read_bytes()));self.assertEqual(command['stdout_raw_sha256'],digest((P/'execution/FIT.stdout').read_bytes()));self.assertEqual(command['stderr_raw_sha256'],digest((P/'execution/FIT.stderr').read_bytes()));self.assertEqual((P/'execution/FIT.stderr').read_bytes(),b'');self.assertEqual(json.loads((P/'execution/FIT.stdout').read_bytes()),RECEIPT)
  RESULT['actual_fit_receipt']=RECEIPT
 def test_02_complete_model_byte_replay_without_writer(self):
  with patch.object(F,'fit',side_effect=AssertionError('SECOND_WRITER_CALL_FORBIDDEN')) as writer:
   replay=F.assemble(OLDMODEL,self.data['records']);replay['protocol_raw_sha256']=F.PROTOCOL_SHA;replay['protocol_addendum_raw_sha256']=F.ADDENDUM_SHA
  writer.assert_not_called();self.assertEqual(canonical(replay),RAW);RESULT['reconstructed_model_raw_sha256']=digest(canonical(replay));RESULT['in_memory_assembly_verification_replays']=1
 def test_03_independent_rational_source_and_all112_posterior_updates(self):
  named={p['player_id'] for p in MODEL['named_players']};old_named={p['player_id']:p for p in OLDMODEL['named_players']};pools=[];checks=[];maxerror=0.
  for p in MODEL['named_players']:
   own=[r for r in self.included if r['player_id']==p['player_id']];peers=[r for r in self.included if r['player_id']!=p['player_id'] and r['role']==p['role']];pools.append((p['player_id'],p,own,peers));self.assertEqual(p['rates'],{k:old_named[p['player_id']]['rates'][k] for k in ('assists','rebounds')});self.assertEqual(p['minutes'],old_named[p['player_id']]['minutes'])
  for team,p in MODEL['residual_groups'].items():
   own=[r for r in self.included if r['team_id']==team and r['player_id'] not in named];pools.append(('RESIDUAL:'+team,p,own,None));self.assertEqual(p['rates'],{k:OLDMODEL['residual_groups'][team]['rates'][k] for k in ('assists','rebounds')})
  self.assertEqual(len(pools),16)
  for label,spec,own,peers in pools:
   a=stats(own);p=stats(peers) if peers is not None else None;self.assertEqual(spec['sufficient_statistics']['counts'],a['counts']);self.assertEqual(spec['sufficient_statistics']['rows'],a['rows']);self.assertLess(abs(spec['sufficient_statistics']['reported_minutes']-float(a['minutes'])),1e-10)
   if p:
    self.assertEqual(spec['peer_sufficient_statistics']['counts'],p['counts']);self.assertEqual(spec['peer_sufficient_statistics']['rows'],p['rows']);self.assertLess(abs(spec['peer_sufficient_statistics']['reported_minutes']-float(p['minutes'])),1e-10)
   else:self.assertIsNone(spec['peer_sufficient_statistics'])
   for k in ('twoPA','threePA','FTA','TO'):
    pa=Fraction(1,2)+(180*p['counts'][k]/p['minutes'] if p else 0);pb=Fraction(181 if p else 1);expected=dict(alpha=pa+a['counts'][k],beta=pb+a['minutes'],prior_alpha=pa,prior_beta=pb,observed_count=a['counts'][k],exposure_minutes=a['minutes']);actual=spec['attempt_posteriors'][k]
    for field,value in expected.items():
     error=abs(float(value)-actual[field]);maxerror=max(maxerror,error);self.assertLess(error,1e-10,(label,k,field));self.assertGreater(actual['alpha'],0);self.assertGreater(actual['beta'],0)
    checks.append(dict(pool=label,component=k,observed_count=a['counts'][k],kind='GammaPoisson',zero_own_count_retained=a['counts'][k]==0))
   for key,made,attempts in [('conversion2','twoPM','twoPA'),('conversion3','threePM','threePA'),('conversion_ft','FTM','FTA')]:
    q=Fraction(p['counts'][made],p['counts'][attempts]) if p else Fraction(1,2);pa=Fraction(1,2)+(40*q if p else 0);pb=Fraction(1,2)+(40*(1-q) if p else 0);expected=dict(alpha=pa+a['counts'][made],beta=pb+a['counts'][attempts]-a['counts'][made],prior_alpha=pa,prior_beta=pb,observed_makes=a['counts'][made],observed_attempts=a['counts'][attempts]);actual=spec[key]
    for field,value in expected.items():
     error=abs(float(value)-actual[field]);maxerror=max(maxerror,error);self.assertLess(error,1e-10,(label,key,field));self.assertGreater(actual['alpha'],0);self.assertGreater(actual['beta'],0)
    checks.append(dict(pool=label,component=key,observed_attempts=a['counts'][attempts],kind='BetaBinomial',zero_own_attempts_retained=a['counts'][attempts]==0))
  self.assertEqual(len(checks),112);RESULT['independent_parameter_checks']=checks;RESULT['max_exact_rational_parameter_difference']=maxerror
 def test_04_all_component_predictive_identities_and_scope(self):
  allspecs=MODEL['named_players']+list(MODEL['residual_groups'].values());checks=0;maxerror=0.
  for spec in allspecs:
   self.assertEqual(set(spec['rates']),{'assists','rebounds'});self.assertNotIn('ft_non3_point_share',spec);self.assertEqual(set(spec['attempt_posteriors']),{'twoPA','threePA','FTA','TO'});self.assertIn('NOT_FULL_EVENT_POSTERIOR',spec['likelihood_scope'])
   for v in spec['attempt_posteriors'].values():
    a,b=v['alpha'],v['beta']
    for m in (0.,.5,20.):
     p=b/(b+m)
     for k in (0,1,5,20):
      expected=(1. if k==0 else 0.) if m==0 else math.exp(gammaln(a+k)-gammaln(a)-gammaln(k+1)+a*math.log(p)+k*math.log1p(-p));actual=float(nbinom.pmf(k,a,p));maxerror=max(maxerror,abs(actual-expected));self.assertLess(abs(actual-expected),1e-10);checks+=1
   for key in ('conversion2','conversion3','conversion_ft'):
    a,b=spec[key]['alpha'],spec[key]['beta']
    for n in (0,1,10):
     masses=[]
     for k in range(n+1):
      expected=math.exp(gammaln(n+1)-gammaln(k+1)-gammaln(n-k+1)+betaln(a+k,b+n-k)-betaln(a,b));actual=float(betabinom.pmf(k,n,a,b));maxerror=max(maxerror,abs(actual-expected));self.assertLess(abs(actual-expected),1e-10);masses.append(actual);checks+=1
     self.assertAlmostEqual(math.fsum(masses),1.,places=11)
  self.assertEqual(checks,1440);self.assertFalse(MODEL['independent_points_or_threes_posteriors']);self.assertFalse(MODEL['posterior_of_joint_event_process']);self.assertFalse(MODEL['production_release']);self.assertIsNone(MODEL['genuine_participation_probability']);self.assertNotIn('s3_artifact_sha256',MODEL);self.assertEqual(MODEL['legacy_S3_comparator_raw_sha256'],OLDMODEL['s3_artifact_sha256'])
  for key in ('pace','events','zero_prior','source_count_totals','source_ft_series','pace_source_rows'):self.assertEqual(MODEL[key],OLDMODEL[key])
  RESULT['component_predictive_checks']=dict(count=checks,max_absolute_difference=maxerror,scope='EXOGENOUS_REPORTED_EXPOSURE_OR_ATTEMPTS_COMPONENT_IDENTITIES_NOT_EVENT_KERNEL_MARGINALS')
if __name__=='__main__':
 RESULT['started_at']=datetime.now(timezone.utc).isoformat();r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ArtifactReview));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=r.testsRun,failures=len(r.failures),errors=len(r.errors),fit_writer_calls=0,new_model_artifacts_created=0,new_J_runs=0,new_forecasts=0,outcome_scores=0)
 (H/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not r.wasSuccessful())
