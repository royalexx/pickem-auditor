"""Independent finite P1->P2 abstention-boundary acceptance, not real S inference."""
import copy,json,pathlib,unittest
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest,export_requests
from v2.nba_architecture.subset_p2_v1 import run_p2,read_p2
ROOT=pathlib.Path(__file__).resolve().parents[5];CAP=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441';C=json.loads((ROOT/'docs/nba_architecture/p1_prospective_20261118/COHORT.json').read_bytes())
class IndependentP2(unittest.TestCase):
 def test_actual_historical_all_stat_attempts(self):
  s=canonical(export_requests(CAP,C));x=run_p2(s,CAP,C);self.assertEqual(read_p2(canonical(x),source_raw=s,capture_dir=CAP,cohort=C),x);self.assertEqual((x['candidate_denominator'],x['attempt_denominator'],x['forecasted_rows'],x['abstained_rows']),(36,144,0,144));self.assertEqual(sum(r['reason']=='SAVED_S_ARTIFACT_UNAVAILABLE' for r in x['rows']),104);self.assertEqual(sum(r['reason']=='P1_SOURCE_ABSTENTION' for r in x['rows']),40);self.assertEqual(len({(r['player_id'],r['statistic']) for r in x['rows']}),144)
  self.assertTrue(all(r['forecast'] is None and r['participation_probability'] is None and not r['actual_native_model_executed'] for r in x['rows']))
 def test_current_compatible_source_still_does_not_invent_s(self):
  cap=ROOT/'docs/nba_architecture/p1_subset_acceptance_20261119/independent/current_capture';c=json.loads((ROOT/'docs/nba_architecture/p1_subset_acceptance_20261119/TONIGHT_COHORT.json').read_bytes());s=canonical(export_requests(cap,c));x=run_p2(s,cap,c);self.assertEqual(x['attempt_denominator'],144);self.assertEqual(sum(r['reason']=='SAVED_S_ARTIFACT_UNAVAILABLE' for r in x['rows']),100);self.assertEqual(sum(r['reason']=='P1_SOURCE_ABSTENTION' for r in x['rows']),44);self.assertEqual(x['admitted_model_count'],0)
 def test_resealed_mutations_rejected(self):
  s=canonical(export_requests(CAP,C));base=run_p2(s,CAP,C)
  for kind in ['q','eligibility','forecast','model','stat','player','drop','approval','cutoff']:
   x=copy.deepcopy(base);r=x['rows'][0]
   if kind=='q':r['participation_probability']=1
   if kind=='eligibility':r['legal_eligibility']=True
   if kind=='forecast':r['forecast']={'p_over':1}
   if kind=='model':r['actual_native_model_executed']=True
   if kind=='stat':r['statistic']='wrong'
   if kind=='player':r['player_id']='espn:player:999'
   if kind=='drop':x['rows'].pop()
   if kind=='approval':x['reviewer']='independent';x['approved']=True
   if kind=='cutoff':r['model_training_cutoff_at']='2024-01-01T00:00:00Z'
   del x['payload_sha256'];x['payload_sha256']=digest(canonical(x))
   with self.subTest(kind=kind),self.assertRaises(ValueError):read_p2(canonical(x),source_raw=s,capture_dir=CAP,cohort=C)
 def test_duplicate_and_nonfinite_wire_rejected(self):
  s=canonical(export_requests(CAP,C));wire=canonical(run_p2(s,CAP,C))
  for x in [b'{"forecasted_rows":1,'+wire[1:],b'{"row":{"q":1,"q":null}}',b'{"q":NaN}',b'{"q":Infinity}']:
   with self.subTest(wire=x[:40]),self.assertRaises(ValueError):read_p2(x,source_raw=s,capture_dir=CAP,cohort=C)
if __name__=='__main__':unittest.main(verbosity=2)
