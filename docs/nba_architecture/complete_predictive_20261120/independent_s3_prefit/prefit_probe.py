"""Independent S3 protocol tests; native fitting is mocked throughout."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime,timezone
import json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_s_family import prospective_s3_fit_v1 as writer
from v2.nba_architecture.p1_subset_handoff_v1 import digest,canonical
from v2.nba_architecture.prospective_s_sources_v1 import build_dataset
HERE=Path(__file__).resolve().parent;OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive';INPUTS=frozen_inputs(OLD);RESULT={}
class Prefit(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=build_dataset(INPUTS['raw_dir'],INPUTS['spec_path'],INPUTS['policy_path'])
  RESULT.update(dataset_payload_sha256=cls.data['payload_sha256'],reader_sha256=cls.data['reader_raw_sha256'],writer_raw_sha256=digest(Path(writer.__file__).read_bytes()),native_raw_sha256=digest(Path(writer.native.__file__).read_bytes()))
 def test_01_exact_source_dataset_and_roles(self):
  self.assertEqual(self.data['payload_sha256'],writer.DATASET_SHA);self.assertEqual(self.data['reader_raw_sha256'],writer.READER_SHA)
  self.assertEqual(self.data['data_cutoff_at'],writer.CUTOFF);self.assertEqual(self.data['role_semantics'],'ESPN_POSITION_BIN_OBSERVED_AT_CAPTURE');self.assertEqual(len(self.data['histories']['threes']),456)
  self.assertEqual(writer.PARAMETERS,dict(prior_minutes=180.,prior_attempts=40.,dispersion=12.,min_player_games=2));self.assertEqual(writer.SEED,20261120)
 def test_02_closed_gate_precedes_source_fit_and_output(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(writer.native,'fit') as native,patch.object(writer,'build_dataset') as build:
   out=Path(tmp)/'out'
   with self.assertRaisesRegex(ValueError,'PREFIT_CLOSED'):writer.fit_new_s3('absent','absent','absent','absent',out)
   native.assert_not_called();build.assert_not_called();self.assertFalse(out.exists())
 def test_03_synthetic_activation_one_exact_fit_call_and_create_only(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);approval=tmp/'approval';approval.write_bytes(b'REVIEW-MOCK-ONLY-NOT-ACTUAL-AUTHORIZATION');mockraw=b'REVIEW-MOCK-NO-REAL-S3-ARTIFACT'
   with patch.object(writer,'APPROVAL_SHA',digest(approval.read_bytes())),patch.object(writer,'build_dataset',return_value=self.data),patch.object(writer.native,'fit',return_value=SimpleNamespace(payload=mockraw,artifact_sha256=digest(mockraw))) as fit:
    out=tmp/'mock_output';receipt=writer.fit_new_s3(INPUTS['raw_dir'],INPUTS['spec_path'],INPUTS['policy_path'],approval,out)
    fit.assert_called_once_with(self.data['histories']['threes'],asof_cutoff_utc=writer.CUTOFF,source_manifest=self.data['source_manifest'],stat='threes',family='S3',hyperparameters=writer.PARAMETERS,seed=writer.SEED)
    self.assertEqual(receipt['artifact_raw_sha256'],digest(mockraw));self.assertLessEqual(receipt['fit_started_at'],receipt['fit_completed_at']);self.assertLessEqual(receipt['fit_completed_at'],receipt['artifact_verified_at'])
    self.assertFalse(receipt['J_admitted']);self.assertFalse(receipt['historical_scoring']);self.assertEqual(receipt['model_admission'],'PENDING_SEPARATE_REAL_ARTIFACT_REVIEW')
    before={p.name:p.read_bytes() for p in out.iterdir()}
    with self.assertRaises(FileExistsError):writer.fit_new_s3(INPUTS['raw_dir'],INPUTS['spec_path'],INPUTS['policy_path'],approval,out)
    self.assertEqual({p.name:p.read_bytes() for p in out.iterdir()},before);self.assertEqual(fit.call_count,1)
    RESULT['mock_receipt']=receipt
 def test_04_native_hash_and_clock_fail_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);approval=tmp/'approval';approval.write_bytes(b'REVIEW-MOCK')
   with patch.object(writer,'APPROVAL_SHA',digest(approval.read_bytes())),patch.object(writer,'NATIVE_SHA','0'*64),patch.object(writer.native,'fit') as fit,patch.object(writer,'build_dataset') as build:
    with self.assertRaisesRegex(ValueError,'NATIVE_FIT_CODE'):writer.fit_new_s3('absent','absent','absent',approval,tmp/'badcode')
    fit.assert_not_called();build.assert_not_called();self.assertFalse((tmp/'badcode').exists())
   mockraw=b'MOCK'
   with patch.object(writer,'APPROVAL_SHA',digest(approval.read_bytes())),patch.object(writer,'build_dataset',return_value=self.data),patch.object(writer.native,'fit',return_value=SimpleNamespace(payload=mockraw,artifact_sha256=digest(mockraw))),patch.object(writer,'now',side_effect=['2026-11-20T03:00:01+00:00','2026-11-20T03:00:00+00:00','2026-11-20T03:00:02+00:00']):
    with self.assertRaisesRegex(ValueError,'CLOCK_REVERSED'):writer.fit_new_s3('unused','unused','unused',approval,tmp/'badclock')
    self.assertFalse((tmp/'badclock/FIT_RECEIPT.json').exists())
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Prefit));RESULT.update(completed_at=datetime.now(timezone.utc).isoformat(),test_methods=result.testsRun,failures=len(result.failures),errors=len(result.errors),real_native_fit_calls=0,real_fit_artifacts_created=0)
 (HERE/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n');sys.exit(not result.wasSuccessful())
