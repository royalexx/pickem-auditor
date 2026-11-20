"""Synthetic writer-protocol controls. Native fit body is never executed."""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_s_family import prospective_fit_v1 as writer
from v2.nba_s_family import model as native
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest

HERE=Path(__file__).resolve().parent;PACKET=HERE.parent
DATA=json.loads((HERE/'independent_dataset.json').read_bytes())
APPROVAL=b'SYNTHETIC_PROTOCOL_CONTROL_ONLY_NOT_REAL_PREFIT_APPROVAL'
RESULT=dict(mode='SYNTHETIC_PROTOCOL_ENGINEERING_ONLY',actual_native_fit_executions=0,synthetic_cases=[])

def enter(stack,data=DATA,times=None):
    stack.enter_context(patch.object(writer,'PREFIT_APPROVAL_SHA',digest(APPROVAL)))
    stack.enter_context(patch.object(writer,'APPROVED_READER_SHA',DATA['reader_raw_sha256']))
    stack.enter_context(patch.object(writer,'APPROVED_DATASET_SHA',DATA['payload_sha256']))
    stack.enter_context(patch.object(writer,'build_dataset',return_value=data))
    if times:stack.enter_context(patch.object(writer,'_now',side_effect=times))
    def fake_fit(rows,*,asof_cutoff_utc,source_manifest,stat,family,hyperparameters,seed):
        assert asof_cutoff_utc==DATA['data_cutoff_at'] and source_manifest==DATA['source_manifest']
        assert family=='S1' and seed==20261120
        assert hyperparameters==dict(prior_minutes=180.,prior_attempts=40.,dispersion=12.,min_player_games=2)
        assert rows==DATA['histories'][stat]
        return native.FittedS(canonical(dict(SYNTHETIC_PROTOCOL_STUB_NOT_REAL_MODEL=True,stat=stat,
            last_game_start_at=max(r['game_start_at'] for r in rows),
            last_outcome_available_at=max(r['outcome_available_at'] for r in rows))))
    return stack.enter_context(patch.object(native,'fit',side_effect=fake_fit))

class FitProtocolReview(unittest.TestCase):
    def invoke(self,approval,output):
        return writer.fit_prospective(PACKET/'raw',PACKET/'PREFIT_POPULATION.json',PACKET/'policy/nba_rule5.raw',approval,output)

    def test_01_real_compiled_gate_is_closed_before_any_data_or_native_call(self):
        self.assertIsNone(writer.PREFIT_APPROVAL_SHA);self.assertIsNone(writer.APPROVED_READER_SHA);self.assertIsNone(writer.APPROVED_DATASET_SHA)
        with tempfile.TemporaryDirectory() as t,patch.object(native,'fit',side_effect=AssertionError('REAL_FIT_FORBIDDEN')) as fit,patch.object(writer,'build_dataset',side_effect=AssertionError('DATA_READ_BEFORE_APPROVAL')) as data:
            output=Path(t)/'absent'
            with self.assertRaisesRegex(ValueError,'INDEPENDENT_PREFIT_APPROVAL_NOT_COMPILED'):self.invoke(Path(t)/'absent-approval',output)
            fit.assert_not_called();data.assert_not_called();self.assertFalse(output.exists())

    def test_02_approved_protocol_calls_four_fixed_parameter_stubs_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as t,ExitStack() as stack:
            root=Path(t);approval=root/'approval';approval.write_bytes(APPROVAL)
            fit=enter(stack,times=['2026-11-20T02:00:00Z','2026-11-20T02:00:01Z','2026-11-20T02:00:02Z'])
            output=root/'artifacts';receipt=self.invoke(approval,output)
            self.assertEqual(fit.call_count,4);self.assertEqual(set(receipt['artifacts']),{'points','rebounds','assists','threes'})
            self.assertEqual(receipt['model_admission'],'PENDING_SEPARATE_INDEPENDENT_ARTIFACT_REVIEW')
            self.assertFalse(receipt['tuning']);self.assertFalse(receipt['nuts']);self.assertFalse(receipt['production_release'])
            self.assertEqual(receipt['native_code_sha256'],writer.NATIVE_SHA)
            for line in (output/'SHA256SUMS').read_text().splitlines():
                expected,name=line.split('  ',1);self.assertEqual(digest((output/name).read_bytes()),expected)
            before={p.name:p.read_bytes() for p in output.iterdir()}
            with self.assertRaises(FileExistsError):self.invoke(approval,output)
            self.assertEqual(before,{p.name:p.read_bytes() for p in output.iterdir()});self.assertEqual(fit.call_count,4)
            RESULT['synthetic_cases'].append(dict(case='four_fixed_parameter_stub_calls',mock_native_calls=4,receipt=receipt,
                qualification='This receipt is a mocked-clock mocked-native protocol control, not a fitted model or actual operation chronology.'))

    def test_03_bad_approval_native_bytes_reader_or_dataset_reject_before_output(self):
        for attack in ('approval','native','reader','dataset'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as t,ExitStack() as stack:
                root=Path(t);approval=root/'approval';approval.write_bytes(APPROVAL+(b' ' if attack=='approval' else b''))
                data=copy.deepcopy(DATA)
                if attack=='reader':data['reader_raw_sha256']='0'*64
                if attack=='dataset':data['payload_sha256']='0'*64
                fit=enter(stack,data=data)
                if attack=='native':
                    actual=Path.read_bytes
                    def modified(path,*args,**kwargs):return b'altered native code' if path==Path(native.__file__) else actual(path,*args,**kwargs)
                    stack.enter_context(patch.object(Path,'read_bytes',modified))
                output=root/'artifacts'
                with self.assertRaises(ValueError):self.invoke(approval,output)
                fit.assert_not_called();self.assertFalse(output.exists())

    def test_04_bad_clock_chains_cannot_write_admissible_receipt(self):
        cases=[('before_cutoff',['2026-11-20T01:00:00Z'],0),
            ('completed_reversed',['2026-11-20T02:00:02Z','2026-11-20T02:00:01Z','2026-11-20T02:00:03Z'],4),
            ('verified_reversed',['2026-11-20T02:00:00Z','2026-11-20T02:00:02Z','2026-11-20T02:00:01Z'],4)]
        for name,times,calls in cases:
            with self.subTest(case=name),tempfile.TemporaryDirectory() as t,ExitStack() as stack:
                root=Path(t);approval=root/'approval';approval.write_bytes(APPROVAL)
                fit=enter(stack,times=times);output=root/'artifacts'
                with self.assertRaises(ValueError):self.invoke(approval,output)
                self.assertEqual(fit.call_count,calls);self.assertFalse((output/'fit_receipt.json').exists())
                RESULT['synthetic_cases'].append(dict(case=name,mock_native_calls=calls,admissible_receipt_written=False))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FitProtocolReview))
    RESULT.update(tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        writer_raw_sha256=digest(Path(writer.__file__).read_bytes()),native_raw_sha256=digest(Path(native.__file__).read_bytes()),
        tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),real_model_admission_granted=False)
    (HERE/'FIT_PROTOCOL_RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n')
    sys.exit(not result.wasSuccessful())
