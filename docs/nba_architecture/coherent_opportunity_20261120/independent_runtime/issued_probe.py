"""Proposed-root and installed-root public immutable coherent replay controls."""
from pathlib import Path
import contextlib,importlib.util,json,os,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_joint import coherent_issued_v1 as issued
from v2.nba_architecture.p1_subset_handoff_v1 import digest,canonical
P=ROOT/'docs/nba_architecture/coherent_opportunity_20261120';A=P/'actual';OLD=P.parent/'complete_predictive_20261120';HERE=Path(os.environ.get('COHERENT_ISSUED_REVIEW_OUT',Path(__file__).resolve().parent/'issued'));HERE.mkdir(parents=True,exist_ok=True);PROPOSED=os.environ.get('COHERENT_PROPOSED_ROOT')=='1';RESULT={'proposed_root_control_only':PROPOSED}
s=importlib.util.spec_from_file_location('coherent_review_inputs',OLD/'inputs.py');inputs=importlib.util.module_from_spec(s);s.loader.exec_module(inputs)
def replay():return issued.replay(A,model_dir=P/'fitted',source_inputs=inputs.outcome_inputs())
class Issued(unittest.TestCase):
 def test_01_actual_public_readonly_replay_no_fit_or_new_generation(self):
  with patch('v2.nba_joint.coherent_predictive_v1.generate',side_effect=AssertionError('NEW_GENERATION_FORBIDDEN')),patch('v2.nba_joint.coherent_components_v1.fit',side_effect=AssertionError('FIT_FORBIDDEN')),patch('scripts.nba_coherent.now',side_effect=AssertionError('NEW_CLOCK_ISSUE_FORBIDDEN')):r=replay()
  self.assertEqual((r['scenarios'],r['all_market_attempts'],r['supported'],r['abstentions'],r['primitive_attempts'],r['primitive_supported'],r['primitive_abstentions'],r['exact_S4_J_query_pairs']),(64,280,112,168,140,56,84,336));self.assertEqual((r['pending_outcomes'],r['actual_scores']),(280,0));self.assertFalse(r['new_forecast_issued']);self.assertFalse(r['release']);self.assertIsNone(r['participation_probability']);self.assertIsNone(r['legal_eligibility']);self.assertEqual(r['zero_sensitivity_gate'],'PENDING');(HERE/'RESULT.json').write_bytes(canonical(r));RESULT['public_replay']=r
 def test_02_exact_wire_model_receipt_admission_and_artifacts_cannot_reseal(self):
  original=Path.read_bytes
  targets=[A/'BANK.json',A/'EXECUTION_RECEIPT.json',P/'fitted/model.json',P/'fitted/FIT_RECEIPT.json',P/'independent_artifact/ARTIFACT_ADMISSION.json',A/'COHORT.json',A/'MARGINALS.json',A/'COHERENCE.json',A/'REFERENCE_COMPARISON.json']
  for target in targets:
   def changed(path):return original(path)+(b' ' if path.resolve()==target.resolve() else b'')
   with self.subTest(target=str(target)),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):replay()
 def test_03_all_declared_code_bytes_and_library_versions_bound(self):
  receipt=json.loads((A/'EXECUTION_RECEIPT.json').read_bytes());original=Path.read_bytes
  for name in receipt['code_raw_sha256']:
   target=(ROOT/name).resolve()
   def changed(path):return original(path)+(b'\n# byte drift\n' if path.resolve()==target else b'')
   with self.subTest(name=name),patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):replay()
  version=issued.importlib.metadata.version
  with patch.object(issued.importlib.metadata,'version',lambda name:'UNMATCHED' if name=='numpy' else version(name)),self.assertRaises(ValueError):replay()
 def test_04_compressed_trace_bytes_are_part_of_public_read(self):
  first=next((A/'trace').glob('*.gz'));original=Path.read_bytes
  def changed(path):return original(path)+(b'bad' if path.resolve()==first.resolve() else b'')
  with patch.object(Path,'read_bytes',changed),self.assertRaises(ValueError):replay()
if __name__=='__main__':
 with contextlib.ExitStack() as stack:
  if PROPOSED:
   for name,file in [('BANK_SHA',A/'BANK.json'),('RECEIPT_SHA',A/'EXECUTION_RECEIPT.json'),('MODEL_ADMISSION_SHA',P/'independent_artifact/ARTIFACT_ADMISSION.json')]:stack.enter_context(patch.object(issued,name,digest(file.read_bytes())))
  result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Issued));RESULT.update(methods=result.testsRun,errors=len(result.errors),failures=len(result.failures));(HERE/'TEST_RESULTS.json').write_text(json.dumps(RESULT,sort_keys=True,indent=2)+'\n');sys.exit(not result.wasSuccessful())
