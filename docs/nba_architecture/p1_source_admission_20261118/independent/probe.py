"""Independent public reader probes; no implementation repairs."""
import copy, hashlib, json, pathlib, tempfile, unittest
from unittest.mock import patch
import v2.nba_architecture.p1_listed_source_v1 as reader
ROOT=pathlib.Path(__file__).resolve().parents[4]
SOURCE=ROOT/'docs/nba_architecture/substantive_remediation_20261117/source_search'
class Review(unittest.TestCase):
 def setUp(self):
  self.pdf=(SOURCE/'nba_pdf.raw').read_bytes();self.pr=json.loads((SOURCE/'nba_pdf.receipt.json').read_bytes());self.pr['raw_sha256']=self.pr['sha256']
  self.espn=(SOURCE/'espn2018.raw').read_bytes();self.er=json.loads((SOURCE/'espn2018.receipt.json').read_bytes())
 def call(self,**kw):
  args=dict(pdf=self.pdf,pdf_receipt=self.pr,espn=self.espn,receipt=self.er);args.update(kw);return reader.read_listed_population(**args)
 def test_positive_unknowns(self):
  x=self.call();self.assertEqual(len(x['rows']),26);self.assertEqual(sum(r['state']=='DNP' for r in x['rows']),2)
  for r in x['rows']:self.assertIsNone(r['target_eligible']);self.assertIsNone(r['genuine_participation_probability'])
  for k in ['source_published_at','original_pregame_available_at','correction_history_complete','target_eligible_roster_count']:self.assertIsNone(x[k])
 def test_source_mutations(self):
  original=json.loads(self.espn)
  def missing(x):x['boxscore']['players'][0]['statistics'][0]['athletes'].pop()
  def duplicate(x):x['boxscore']['players'][0]['statistics'][0]['athletes'].append(copy.deepcopy(x['boxscore']['players'][0]['statistics'][0]['athletes'][0]))
  def wrong_game(x):x['header']['id']='999'
  def wrong_team(x):x['boxscore']['players'][0]['team']['id']='999'
  def collide(x):x['boxscore']['players'][0]['statistics'][0]['athletes'][1]['athlete']['id']=x['boxscore']['players'][0]['statistics'][0]['athletes'][0]['athlete']['id']
  for mutation in [missing,duplicate,wrong_game,wrong_team,collide]:
   x=copy.deepcopy(original);mutation(x);raw=json.dumps(x).encode();receipt=dict(self.er,raw_sha256=hashlib.sha256(raw).hexdigest())
   with self.subTest(mutation=mutation.__name__),self.assertRaises(Exception):self.call(espn=raw,receipt=receipt)
 def test_receipt_assertions(self):
  for k,v in [('retrieved_at','2018-10-16T00:00:00Z'),('published_at','2018-10-16T00:00:00Z'),('correction_history_complete',True),('predecessor_sha256','0'*64),('approved',True),('reviewer','independent'),('complete_roster',True)]:
   with self.subTest(field=k),self.assertRaises(Exception):self.call(receipt=dict(self.er,**{k:v}))
 def test_capability(self):
  for capability in ['COMPLETE_ROSTER','ORIGINAL_PREGAME_AVAILABILITY','FITTED_MODEL','OFFICIAL_EXTERNAL_IDS']:
   with self.subTest(capability=capability),self.assertRaises(Exception):self.call(required_capability=capability)
 def test_pregame_request(self):
  for freeze in ['2018-10-19T23:45:00Z','2026-11-19T00:00:00Z']:
   with self.subTest(freeze=freeze),self.assertRaises(Exception):self.call(input_freeze_at=freeze)
 def test_denominators(self):
  for delta in [-1,0,1]:
   x=json.loads(self.espn);people=x['boxscore']['players'][0]['statistics'][0]['athletes']
   if delta==-1:people.pop()
   if delta==1:people.append(copy.deepcopy(people[0]))
   raw=self.espn if delta==0 else json.dumps(x).encode()
   result=reader.listed_population_receipt(self.pdf,self.pr,raw,self.er)
   self.assertEqual(result['attempted_rows'],26+delta)
   self.assertEqual(result['accepted_rows'],26 if delta==0 else 0)
   self.assertEqual(result['rejected_rows'],0 if delta==0 else 26+delta)
   self.assertIsNone(result['target_eligible_roster_count'])
 def test_root_tamper(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);(p/'installed_identity_root.json').write_text('{}')
   with patch.object(reader,'PACKET',p),self.assertRaises(Exception):self.call()
 def test_reader_binding_mutant(self):
  original=pathlib.Path.read_bytes
  def altered(path):
   raw=original(path)
   return raw+b'\n# independent mutant' if path.name=='p1_listed_source_v1.py' else raw
  with patch.object(pathlib.Path,'read_bytes',altered),self.assertRaises(Exception):self.call()
 def test_pdf_mutation(self):
  with self.assertRaises(Exception):self.call(pdf=self.pdf+b'altered')
if __name__=='__main__':unittest.main(verbosity=2)
