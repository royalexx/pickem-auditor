"""Independent actual archive transport and hostile immutable-byte controls."""
import copy,json,pathlib,tempfile,unittest
from unittest.mock import patch
from v2.nba_c.subset_archive_v1 import SubsetAuditArchive
from v2.nba_c.warehouse import _write_once,WarehouseError
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
ROOT=pathlib.Path(__file__).resolve().parents[5];PACK=ROOT/'docs/nba_architecture/p1_p5_handoffs_20261119';OUT=pathlib.Path(__file__).resolve().parent;P3=PACK/'independent/p3/final_05b44764';CAP=ROOT/'docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture';C=json.loads((PACK/'PROSPECTIVE_COHORT.json').read_bytes());H=PACK/'prospective_inputs';M=ROOT/'research/nba_ws2/results/model.json'
WIRES={s:((P3 if s in ('p1','p3') else PACK/'independent/p4')/(s+'.json')).read_bytes() for s in ('p1','p2','p3','p4')}
def put(a,wires=None):return a.put(WIRES if wires is None else wires,capture_dir=CAP,cohort=C,history_dir=H,model_path=M)
def reseal(a,value):
 raw=canonical(value)+b'\n';rid=digest(raw);_write_once(a._record(rid),raw);return rid
class Review(unittest.TestCase):
 def test_actual_archive_all_originals_native_primitive_and_offline_read(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=SubsetAuditArchive(tmp)
   with patch('v2.nba_c.subset_archive_v1._write_once',wraps=_write_once) as actual:
    receipt=put(a);self.assertGreater(actual.call_count,10)
   record=a.read(receipt['record_id']);counts=record['counts'];self.assertEqual((counts['candidate_denominator'],counts['prior_observation_denominator'],counts['p2_attempts'],counts['p3_attempts'],counts['p4_attempts'],counts['total_attempt_records'],counts['conditional_minute_forecast_records'],counts['explicit_abstention_records']),(36,540,144,108,432,684,36,648));self.assertEqual(counts['statistic_forecast_records'],0)
   for s,raw in WIRES.items():self.assertEqual(a._object(record['objects']['outputs/'+s+'.json']['sha256']).read_bytes(),raw)
   original=pathlib.Path.read_bytes
   def offline(path):
    self.assertFalse(path==M or path==PACK/'PROSPECTIVE_COHORT.json' or CAP in path.parents or H in path.parents,'mutable original unexpectedly reread');return original(path)
   with patch.object(pathlib.Path,'read_bytes',offline):self.assertEqual(a.read(receipt['record_id']),record)
   self.assertFalse(put(a)['created']);self.assertEqual(len(list((a.root/'records').glob('*'))),1)
   for k in ('participation_probability','legal_roster_completeness','correction_history_complete','original_historical_pregame_availability'):self.assertIsNone(record[k])
   self.assertFalse(record['scoring_admitted']);self.assertFalse(record['joint_family_accepted'])
   (OUT/'actual_manifest.json').write_bytes(canonical(record)+b'\n');(OUT/'actual_receipt.json').write_bytes(canonical(receipt)+b'\n');print(json.dumps({'record_id':receipt['record_id'],'object_count':len(record['objects']),'object_bytes':sum(v['bytes'] for v in record['objects'].values()),'counts':counts},indent=2))
 def test_actual_object_missing_altered_collision(self):
  for action in ('missing','altered'):
   with self.subTest(action=action),tempfile.TemporaryDirectory() as tmp:
    a=SubsetAuditArchive(tmp);r=put(a);v=a.read(r['record_id']);p=a._object(v['objects']['inputs/model.json']['sha256'])
    if action=='missing':p.unlink()
    else:p.chmod(0o644);p.write_bytes(p.read_bytes()+b' ')
    with self.assertRaises(ValueError):a.read(r['record_id'])
    if action=='altered':
     with self.assertRaisesRegex(WarehouseError,'IMMUTABLE_COLLISION'):put(a)
 def test_resealed_sources_reader_claims_denominators_and_path(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=SubsetAuditArchive(tmp);r=put(a);v=a.read(r['record_id'])
   for attack in ('count','score','q','correction','path','reader','raw'):
    x=copy.deepcopy(v)
    if attack=='count':x['counts']['total_attempt_records']-=1
    if attack=='score':x['scoring_admitted']=True
    if attack=='q':x['participation_probability']=1
    if attack=='correction':x['correction_history_complete']=True
    if attack=='path':x['objects']['inputs/history/../../escape']=next(iter(x['objects'].values()))
    if attack in ('reader','raw'):
     name='readers/v2/nba_opportunity.py' if attack=='reader' else next(n for n in x['objects'] if n.startswith('inputs/history/') and n.endswith('/body.raw'))
     ref=x['objects'][name];raw=a._object(ref['sha256']).read_bytes()+b' ';ref.update(sha256=digest(raw),bytes=len(raw));_write_once(a._object(digest(raw)),raw)
    with self.subTest(attack=attack),self.assertRaises(ValueError):a.read(reseal(a,x))
 def test_forged_wires_never_create_record(self):
  for action in ('drop','q','forecast','duplicate'):
   with self.subTest(action=action),tempfile.TemporaryDirectory() as tmp:
    a=SubsetAuditArchive(tmp);wire=dict(WIRES);v=json.loads(wire['p3'])
    if action=='drop':v['rows'].pop()
    if action=='q':v['rows'][0]['participation_probability']=1
    if action=='forecast':next(r for r in v['rows'] if r['forecast'])['forecast']['expected_minutes_given_played']+=1
    v.pop('payload_sha256');v['payload_sha256']=digest(canonical(v));wire['p3']=canonical(v)
    if action=='duplicate':wire['p3']=b'{"forecasted_rows":100,'+wire['p3'][1:]
    with self.assertRaises(ValueError):put(a,wire)
    self.assertFalse((a.root/'records').exists())
if __name__=='__main__':unittest.main(verbosity=2)
