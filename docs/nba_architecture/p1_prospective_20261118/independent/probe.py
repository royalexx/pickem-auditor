"""Independent native reader and fixed capture-clock controls; synthetic attacks."""
import copy,hashlib,importlib.util,json,pathlib,tempfile,unittest
from datetime import datetime,timezone
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('prospective',ROOT/'scripts/nba_p1_prospective_capture.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
P=ROOT/'docs/nba_architecture/p1_prospective_20261118'
class Control(unittest.TestCase):
 def setUp(self):self.c=json.loads((P/'COHORT.json').read_bytes());self.schedule=(P/'schedule-initial/body.raw').read_bytes()
 def test_actual_rosters_unknowns_and_source_clock(self):
  total=0
  for tid in ['5','29']:
   raw=(P/f'roster-initial-{tid}/body.raw').read_bytes();source=json.loads(raw);rows=m.roster_rows(raw,tid);self.assertEqual(len(rows),len(source['athletes']));total+=len(rows)
   for r in rows:
    self.assertEqual(r['availability'],'UNKNOWN_UNADMITTED');self.assertIsNone(r['legal_eligibility']);self.assertIsNone(r['participation_probability']);self.assertEqual(r['source_generated_at'],source.get('timestamp'));self.assertIsNone(r['source_published_at'])
  self.assertEqual(total,35)
 def test_wrong_and_duplicate_roster(self):
  raw=(P/'roster-initial-5/body.raw').read_bytes()
  with self.assertRaises(ValueError):m.roster_rows(raw,'29')
  x=json.loads(raw);x['athletes'].append(copy.deepcopy(x['athletes'][0]))
  with self.assertRaises(ValueError):m.roster_rows(json.dumps(x).encode(),'5')
 def test_schedule_identity_and_status(self):
  m.validate_schedule(self.schedule,self.c,True)
  for kind in ['missing','duplicate','team','start','live','postponed']:
   x=json.loads(self.schedule);e=next(e for e in x['events'] if e['id']==self.c['game_id'])
   if kind=='missing':x['events'].remove(e)
   elif kind=='duplicate':x['events'].append(copy.deepcopy(e))
   elif kind=='team':e['competitions'][0]['competitors'][0]['team']['id']='999'
   elif kind=='start':e['date']='2026-11-19T01:00Z'
   elif kind=='live':e['status']['type']['state']='in'
   else:e['status']['type']['name']='STATUS_POSTPONED';e['status']['type']['id']='6'
   with self.subTest(kind=kind),self.assertRaises(ValueError):m.validate_schedule(json.dumps(x).encode(),self.c,True)
 def test_cohort_mutation_no_network(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);c=dict(self.c,game_id='999');(p/'COHORT.json').write_text(json.dumps(c))
   with patch.object(m,'PACKET',p),patch.object(m,'capture',side_effect=AssertionError('network aftermutation')),self.assertRaisesRegex(ValueError,'COHORT_BYTES_CHANGED'):m.run('pregame',p/'output')
 def test_rejected_roster_denominator_and_persistence(self):
  source=next((P/'captures').glob('*/attempt.json')).parent
  class Fixed(datetime):
   @classmethod
   def now(cls,tz=None):return cls(2026,11,18,13,0,tzinfo=timezone.utc)
  def fake_capture(url,destination):
   # Synthetic retrieval adapter copies captured raw responses, then mutates one
   # roster and one HTTP status. Never source admission or actual observations.
   dest=pathlib.Path(destination);dest.mkdir();name=dest.name
   old=source/name;raw=(old/'body.raw').read_bytes();r=json.loads((old/'receipt.json').read_bytes())
   if name=='roster-5':
    x=json.loads(raw);x['athletes'].append(copy.deepcopy(x['athletes'][0]));raw=json.dumps(x).encode()
   if name.startswith('injury-pdf-'):r['status']=403
   r['raw_sha256']=hashlib.sha256(raw).hexdigest();(dest/'body.raw').write_bytes(raw);(dest/'receipt.json').write_text(json.dumps(r));return r
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'datetime',Fixed),patch.object(m,'capture',fake_capture):
   first=m.run('initial',tmp);original=(first/'attempt.json').read_bytes();second=m.run('initial',tmp);self.assertNotEqual(first,second);self.assertEqual((first/'attempt.json').read_bytes(),original)
   x=json.loads(original);self.assertEqual(x['roster_denominators']['5'],dict(attempted=18,parsed=0,rejected=18));self.assertEqual(x['roster_denominators']['29'],dict(attempted=18,parsed=18,rejected=0));self.assertTrue(any('injury-pdf-' in e and 'HTTP_CAPTURE_UNAVAILABLE' in e for e in x['errors']))
   for line in (first/'SHA256SUMS').read_text().splitlines():
    digest,path=line.split('  ',1);self.assertEqual(hashlib.sha256((first/path).read_bytes()).hexdigest(),digest)
 def test_missed_freeze_no_network(self):
  class Late(datetime):
   @classmethod
   def now(cls,tz=None):return cls(2026,11,18,23,46,tzinfo=timezone.utc)
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'datetime',Late),patch.object(m,'capture',side_effect=AssertionError('network afterfreeze')):
   p=m.run('pregame',tmp);x=json.loads((p/'attempt.json').read_bytes());self.assertIn('MISSED_ORIGINAL_FREEZE',x['errors']);self.assertEqual(x['sources'],{});self.assertIsNone(x['target_eligible_roster_count'])
if __name__=='__main__':unittest.main(verbosity=2)
