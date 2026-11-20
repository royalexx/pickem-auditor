import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.nba_architecture.test_subset_p2_dispatch_v1 import real_inputs,UP,FIXTURE
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_p2_dispatch_v1 import run_dispatch
from v2.nba_c.subset_dispatch_archive_v1 import DispatchAuditArchive
from v2.nba_c.warehouse import _write_once,WarehouseError

BASE_ID=json.loads((UP/'receipt.json').read_bytes())['p5_record_id']


def archive_at(path):
    shutil.copytree(UP/'archive/subset_research_audit',Path(path)/'subset_research_audit')
    return DispatchAuditArchive(path)


class DispatchArchiveTests(unittest.TestCase):
    def test_real_exposure_handoff_and_original_archive_remain_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=archive_at(tmp);wire=canonical(run_dispatch(**real_inputs()))
            receipt=archive.put(BASE_ID,wire);record=archive.read(receipt['record_id'])
            self.assertEqual((record['candidate_denominator'],record['dispatch_attempts'],record['exposure_bound_rows'],record['statistic_forecast_records'],record['combined_attempt_records']),(36,144,48,0,828))
            self.assertEqual(archive.base.read(BASE_ID)['counts']['conditional_minute_forecast_records'],36)
            again=archive.put(BASE_ID,wire);self.assertEqual(again['record_id'],receipt['record_id']);self.assertFalse(again['created'])

    def test_supplied_rejected_model_and_unmatched_approval_bytes_are_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);models=root/'models';models.mkdir();(models/'points.json').write_bytes((FIXTURE/'points.json').read_bytes());(models/'approval.json').write_text('{"approved":true}')
            archive=archive_at(root/'archive');wire=canonical(run_dispatch(**real_inputs(models)))
            receipt=archive.put(BASE_ID,wire,model_dir=models);shutil.rmtree(models)
            record=archive.read(receipt['record_id']);self.assertEqual(record['provided_file_denominator'],2)
            self.assertEqual(set(record['model_files']),{'points.json','approval.json'});self.assertFalse(record['model_admission_granted'])

    def test_altered_object_native_collision_and_orphan_base_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=archive_at(tmp);wire=canonical(run_dispatch(**real_inputs()));receipt=archive.put(BASE_ID,wire);record=archive.read(receipt['record_id'])
            path=archive._object(record['dispatch']['sha256']);path.chmod(0o644);path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(ValueError):archive.read(receipt['record_id'])
            with self.assertRaisesRegex(WarehouseError,'IMMUTABLE_COLLISION'):archive.put(BASE_ID,wire)
            with self.assertRaises(FileNotFoundError):archive.put('0'*64,wire)

    def test_resealed_count_admission_model_drop_path_and_duplicate_claims_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=archive_at(tmp);wire=canonical(run_dispatch(**real_inputs()));receipt=archive.put(BASE_ID,wire);record=archive.read(receipt['record_id'])
            for attack in ('count','admit','reader','path','dispatch'):
                value=copy.deepcopy(record)
                if attack=='count':value['dispatch_abstentions']-=1
                if attack=='admit':value['model_admission_granted']=True
                if attack=='reader':value['reader_files'].pop(next(iter(value['reader_files'])))
                if attack=='path':value['model_files']['../escape']=value['dispatch']
                if attack=='dispatch':
                    d=json.loads(wire);d['rows'].pop();d.pop('payload_sha256');d['payload_sha256']=digest(canonical(d));raw=canonical(d);sha=digest(raw);_write_once(archive._object(sha),raw);value['dispatch'].update(sha256=sha,bytes=len(raw))
                raw=canonical(value)+b'\n';rid=digest(raw);_write_once(archive._record(rid),raw)
                with self.subTest(attack=attack),self.assertRaises((ValueError,FileNotFoundError)):archive.read(rid)
            raw=b'{"model_admission_granted":true,'+archive._record(receipt['record_id']).read_bytes()[1:];rid=digest(raw);_write_once(archive._record(rid),raw)
            with self.assertRaises(ValueError):archive.read(rid)
