"""Independent public rejection controls for unadmitted new actual population."""
import copy,hashlib,json,pathlib,unittest
from v2.nba_architecture.p1_listed_source_v1 import listed_population_receipt
from v2.nba_architecture.gamebook_v1 import read_final_box
P=next((pathlib.Path(__file__).resolve().parents[1]/'raw').glob('morning-*'))
def inputs():
 p=(P/'official-gamebook/body.raw').read_bytes();pr=json.loads((P/'official-gamebook/receipt.json').read_bytes());pr['retrieved_at']=pr['retrieval_started_at'];e=(P/'target-summary/body.raw').read_bytes();er=json.loads((P/'target-summary/receipt.json').read_bytes());er['retrieved_at']=er['retrieval_started_at'];return [p,pr,e,er]
class PublicControls(unittest.TestCase):
 def test_actual_native_reader_positive_and_old_root_denominator(self):
  args=inputs();box=read_final_box(*args[:2]);self.assertEqual((len(box['rows']),box['duration_minutes'],box['overtime_periods']),(25,'48',0));r=listed_population_receipt(*args);self.assertEqual((r['attempted_rows'],r['accepted_rows'],r['rejected_rows']),(25,0,25));self.assertEqual(r['status'],'REJECTED_WHOLE_BUNDLE')
 def test_resealed_identity_mutations_preserve_reject_counts(self):
  for kind in ['missing','duplicate','game','team']:
   args=inputs();x=json.loads(args[2]);athletes=x['boxscore']['players'][0]['statistics'][0]['athletes']
   if kind=='missing':athletes.pop()
   if kind=='duplicate':athletes.append(copy.deepcopy(athletes[0]))
   if kind=='game':x['header']['id']='401070213'
   if kind=='team':x['boxscore']['players'][0]['team']['id']='999'
   args[2]=json.dumps(x).encode();args[3]['raw_sha256']=hashlib.sha256(args[2]).hexdigest();r=listed_population_receipt(*args)
   with self.subTest(kind=kind):self.assertEqual(r['accepted_rows'],0);self.assertEqual(r['attempted_rows'],24 if kind=='missing' else 26 if kind=='duplicate' else 25);self.assertEqual(r['rejected_rows'],r['attempted_rows']);self.assertIsNone(r['target_eligible_roster_count'])
 def test_claims_and_changed_pdf_do_not_grant_admission(self):
  for extra in [{'approved':True},{'correction_history_complete':True},{'predecessor_sha256':'0'*64},{'source_published_at':'2026-11-18T23:00:00Z'}]:
   args=inputs();args[3].update(extra);r=listed_population_receipt(*args);self.assertEqual(r['accepted_rows'],0)
  args=inputs()
  with self.assertRaises(Exception):read_final_box(args[0]+b'mutated',args[1])
if __name__=='__main__':unittest.main(verbosity=2)
