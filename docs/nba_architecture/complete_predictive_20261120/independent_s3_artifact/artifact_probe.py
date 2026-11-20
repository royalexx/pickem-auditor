"""Independent one-artifact deterministic replay and public S3 kernel checks."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,math,subprocess,sys,unittest
from scipy.special import betaln,gammaln
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_s_family import model as native
from v2.nba_s_family import prospective_s3_fit_v1 as writer
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';HERE=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive'
INPUTS=frozen_inputs(OLD);RESULT={}
class ArtifactReview(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=build_dataset(INPUTS['raw_dir'],INPUTS['spec_path'],INPUTS['policy_path']);cls.raw=(P/'fitted_s3/three_conversion.json').read_bytes();cls.artifact=native.FittedS(cls.raw);cls.receipt=json.loads((P/'fitted_s3/FIT_RECEIPT.json').read_bytes());cls.approval=json.loads((P/'independent_s3_prefit/PREFIT_APPROVAL.json').read_bytes())
 def test_01_exact_activation_receipt_sources_and_clocks(self):
  closed=subprocess.check_output(['git','show','8730362cce3a04eb8edeaa15388651f1cee240f7:v2/nba_s_family/prospective_s3_fit_v1.py'],cwd=ROOT)
  activated=closed.replace(b'APPROVAL_SHA=None',b"APPROVAL_SHA='1e8e21143d8aba0afc53483f85e82af22c941c85f64091e9bd32a83bde734cd5'")
  self.assertEqual(Path(writer.__file__).read_bytes(),activated);r=self.receipt;d=self.data
  self.assertEqual(digest(self.raw),r['artifact_raw_sha256']);self.assertEqual(digest(self.raw),'04ffd94a6cf2a1bc00d3052aebcab98ac3aef77bac1d764ed9f0190c86812b18')
  self.assertEqual(r['writer_raw_sha256'],digest(activated));self.assertEqual(r['prefit_approval_raw_sha256'],digest((P/'independent_s3_prefit/PREFIT_APPROVAL.json').read_bytes()))
  self.assertEqual(r['source_reader_raw_sha256'],d['reader_raw_sha256']);self.assertEqual(r['source_dataset_sha256'],d['payload_sha256']);self.assertEqual(r['source_manifest_raw_sha256'],digest(canonical(d['source_manifest'])));self.assertEqual(r['source_body_map_raw_sha256'],digest(canonical(d['raw_sources'])))
  self.assertEqual(r['native_raw_sha256'],digest(Path(native.__file__).read_bytes()));self.assertEqual(r['hyperparameters'],self.approval['hyperparameters']);self.assertEqual(r['seed'],self.approval['seed']);self.assertEqual(r['source_role_semantics'],self.approval['role_semantics'])
  self.assertLess(self.approval['decided_at'],r['fit_started_at']);self.assertLessEqual(r['training_cutoff_at'],r['fit_started_at']);self.assertLessEqual(r['fit_started_at'],r['fit_completed_at']);self.assertLessEqual(r['fit_completed_at'],r['artifact_verified_at'])
  command=json.loads((P/'s3_execution/COMMAND.json').read_bytes());self.assertEqual(command['exit_code'],0);self.assertLessEqual(command['started_at'],r['fit_started_at']);self.assertLessEqual(r['artifact_verified_at'],command['completed_at']);self.assertEqual((P/'s3_execution/stderr').read_bytes(),b'')
  self.assertEqual(r['training_rows'],456);self.assertEqual(r['source_observations'],698);self.assertFalse(r['J_admitted']);self.assertFalse(r['historical_scoring'])
  RESULT['actual_receipt']=r
 def test_02_native_exact_artifact_byte_reproduction(self):
  replicated=native.fit(self.data['histories']['threes'],asof_cutoff_utc=self.data['data_cutoff_at'],source_manifest=self.data['source_manifest'],stat='threes',family='S3',hyperparameters=self.approval['hyperparameters'],seed=self.approval['seed'])
  self.assertEqual(replicated.payload,self.raw);self.assertEqual(self.artifact.data['training_rows'],replicated.data['training_rows']);self.assertEqual(self.artifact.data['family'],'S3');self.assertEqual(self.artifact.data['stat'],'threes');self.assertEqual(self.artifact.data['hyperparameters'],self.approval['hyperparameters'])
  RESULT['in_memory_deterministic_fit_verification_replays']=1;RESULT['reproduced_raw_sha256']=replicated.artifact_sha256
 def test_03_all14_native_beta_binomial_kernels_independent_formula(self):
  candidate=json.loads((P/'FULL_S_CANDIDATE.json').read_bytes());dataset=self.data['histories']['threes'];checks=[]
  for row in candidate['rows']:
   if row['statistic']!='threes' or not row['model']:continue
   pid=row['player_id'];own=[r for r in dataset if r['player_id']==pid];roles={r['role'] for r in own};self.assertEqual(len(roles),1);role=next(iter(roles));peers=[r for r in dataset if r['player_id']!=pid and r['role']==role]
   attempts=sum(r['three_attempts'] for r in peers);made=sum(r['count'] for r in peers);self.assertGreater(attempts,0);q=made/attempts;self.assertTrue(0<q<1)
   parent=json.loads((OLD/'forecast.json').read_bytes());binding=next(r['binding'] for r in parent['rows'] if r['player_id']==pid and r['statistic']=='threes')
   self.assertEqual(role,'ESPN_POSITION_BIN_AT_CAPTURE:'+binding['role_features']['position'])
   A=40*q+sum(r['count'] for r in own);B=40*(1-q)+sum(r['three_attempts']-r['count'] for r in own)
   for n in (0,1,5,25,100,4096):
    output=native.predict_conditional(self.artifact,player_id=pid,role=role,projected_exposure=n,statistic='threes');self.assertIsNone(output.abstain_reason);params=output.parameters;self.assertAlmostEqual(params['alpha'],A,places=12);self.assertAlmostEqual(params['beta'],B,places=12)
    support=params['support'];self.assertEqual([k['value'] for k in support],list(range(n+1)));mass=[k['mass'] for k in support];self.assertAlmostEqual(math.fsum(mass),1.,places=12);self.assertEqual(params['tail_mass_upper_bound'],0.)
    independent=[math.exp(gammaln(n+1)-gammaln(k+1)-gammaln(n-k+1)+betaln(k+A,n-k+B)-betaln(A,B)) for k in range(n+1)]
    difference=max(abs(p-q) for p,q in zip(mass,independent));self.assertLess(difference,1e-9)
    mean=math.fsum(k*p for k,p in enumerate(mass));variance=math.fsum((k-mean)**2*p for k,p in enumerate(mass));expected=n*A/(A+B);var=n*A*B*(A+B+n)/((A+B)**2*(A+B+1))
    self.assertAlmostEqual(mean,expected,places=7);self.assertLess(abs(variance-var),max(1e-8,abs(var)*1e-9))
    checks.append(dict(player=row['name'],player_id=pid,role=role,projected_3PA=n,alpha=A,beta=B,own_games=len(own),peer_games=len(peers),max_pmf_difference=difference,mean_error=abs(mean-expected),variance_error=abs(variance-var)))
  self.assertEqual(len(checks),84);RESULT['public_beta_binomial_checks']=checks
 def test_04_public_abstentions_and_immutable_artifact(self):
  pid=self.data['histories']['threes'][0]['player_id'];role=self.data['histories']['threes'][0]['role']
  for exposure in (-1,True,1.,4097):
   result=native.predict_conditional(self.artifact,player_id=pid,role=role,projected_exposure=exposure,statistic='threes');self.assertIsNotNone(result.abstain_reason)
  for bad in ('unknown-role',None):
   result=native.predict_conditional(self.artifact,player_id=pid,role=bad,projected_exposure=5,statistic='threes');self.assertIsNotNone(result.abstain_reason)
  self.assertIsNotNone(native.predict_conditional(self.artifact,player_id='not-in-trained-population',role=role,projected_exposure=5,statistic='threes').abstain_reason)
  self.assertIsNotNone(native.predict_conditional(self.artifact,player_id=pid,role=role,projected_exposure=5,statistic='points').abstain_reason)
  copied=self.artifact.data;copied['family']='S1';self.assertEqual(self.artifact.data['family'],'S3');self.assertEqual(self.artifact.payload,self.raw)
  copied=self.artifact.data;copied['code_sha256']='0'*64;bad=native.FittedS(canonical(copied));self.assertEqual(native.predict_conditional(bad,player_id=pid,role=role,projected_exposure=5,statistic='threes').abstain_reason,'MODEL_CODE_VERSION_DRIFT')
if __name__=='__main__':
 RESULT['started_at']=datetime.now(timezone.utc).isoformat();result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ArtifactReview));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),new_fit_artifacts_created=0,outcome_scores=0)
 (HERE/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not result.wasSuccessful())
