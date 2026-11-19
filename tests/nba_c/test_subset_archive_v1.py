import copy
import json
from pathlib import Path
import tempfile
import unittest

from tests.nba_architecture.test_subset_p3_v1 import CAP,COHORT,HISTORY,MODEL,PACKET
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_c.subset_archive_v1 import SubsetAuditArchive
from v2.nba_c.warehouse import _write_once,WarehouseError

UP=PACKET/'p4_scope_repair/recorded_native_replay'


def outputs():return {s:(UP/(s+'.json')).read_bytes() for s in ('p1','p2','p3','p4')}
def put(archive,wire=None):return archive.put(wire or outputs(),capture_dir=CAP,cohort=COHORT,history_dir=HISTORY,model_path=MODEL)


class SubsetArchiveTests(unittest.TestCase):
    def test_actual_public_source_model_law_to_native_write_once_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=SubsetAuditArchive(tmp);receipt=put(archive);record=archive.read(receipt['record_id']);c=record['counts']
            self.assertTrue(receipt['created']);self.assertEqual((c['candidate_denominator'],c['prior_observation_denominator'],c['total_attempt_records'],c['conditional_minute_forecast_records'],c['explicit_abstention_records']),(36,540,684,36,648))
            self.assertEqual(c['statistic_forecast_records'],0);self.assertFalse(record['scoring_admitted']);self.assertIsNone(record['correction_history_complete'])
            for s,raw in outputs().items():
                ref=record['objects']['outputs/'+s+'.json'];self.assertEqual(ref['sha256'],digest(raw));self.assertEqual(archive._object(ref['sha256']).read_bytes(),raw)
            self.assertEqual(record['objects']['inputs/model.json']['sha256'],digest(MODEL.read_bytes()))

    def test_idempotent_duplicate_preserves_exact_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=SubsetAuditArchive(tmp);one=put(archive);two=put(archive)
            self.assertEqual(one['record_id'],two['record_id']);self.assertFalse(two['created'])
            self.assertEqual(len(list((archive.root/'records').glob('*'))),1)

    def test_altered_or_missing_object_and_native_immutable_collision(self):
        for attack in ('alter','missing'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
                archive=SubsetAuditArchive(tmp);receipt=put(archive);record=archive.read(receipt['record_id']);path=archive._object(record['objects']['inputs/model.json']['sha256'])
                if attack=='alter':path.chmod(0o644);path.write_bytes(path.read_bytes()+b' ')
                else:path.unlink()
                with self.assertRaises(ValueError):archive.read(receipt['record_id'])
                if attack=='alter':
                    with self.assertRaisesRegex(WarehouseError,'IMMUTABLE_COLLISION'):put(archive)

    def test_resealed_manifest_claims_counts_and_path_attacks_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=SubsetAuditArchive(tmp);receipt=put(archive);original=archive.read(receipt['record_id'])
            for attack in ('score','complete','count','path','reader'):
                value=copy.deepcopy(original)
                if attack=='score':value['scoring_admitted']=True;value['approved']=True
                if attack=='complete':value['correction_history_complete']=True
                if attack=='count':value['counts']['explicit_abstention_records']-=1
                if attack=='path':value['objects']['inputs/history/../../escape']=next(iter(value['objects'].values()))
                if attack=='reader':value['objects'].pop('readers/v2/nba_opportunity.py')
                raw=canonical(value)+b'\n';rid=digest(raw);_write_once(archive._record(rid),raw)
                with self.subTest(attack=attack),self.assertRaises(ValueError):archive.read(rid)

    def test_forged_upstream_forecast_and_unknowns_cannot_archive(self):
        for attack in ('q','p2_forecast','drop'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
                archive=SubsetAuditArchive(tmp);wire=outputs();stage='p2' if attack=='p2_forecast' else 'p3';value=json.loads(wire[stage])
                if attack=='q':value['rows'][0]['participation_probability']=1.
                if attack=='p2_forecast':value['rows'][0]['forecast']={'pmf':{'0':1.}}
                if attack=='drop':value['rows'].pop()
                value.pop('payload_sha256');value['payload_sha256']=digest(canonical(value));wire[stage]=canonical(value)
                with self.assertRaises(ValueError):put(archive,wire)
                self.assertFalse((archive.root/'records').exists())

    def test_duplicate_manifest_key_and_invalid_record_ids_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive=SubsetAuditArchive(tmp);receipt=put(archive);raw=archive._record(receipt['record_id']).read_bytes();bad=b'{"scoring_admitted":true,'+raw[1:];rid=digest(bad);_write_once(archive._record(rid),bad)
            with self.assertRaises(ValueError):archive.read(rid)
            for value in ('../escape','g'*64,'x'):
                with self.assertRaises(ValueError):archive.read(value)
