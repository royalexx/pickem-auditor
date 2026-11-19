"""Independent actual source->serialized request consumer and hostile controls."""
import copy,json,pathlib,shutil,tempfile,unittest
from v2.nba_architecture.p1_subset_handoff_v1 import export_requests,read_requests,conditional_requests,canonical,digest
ROOT=pathlib.Path(__file__).resolve().parents[4];RAW=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw';COHORT=json.loads((ROOT/'docs/nba_architecture/p1_prospective_20261118/COHORT.json').read_bytes());OUT=pathlib.Path(__file__).resolve().parent
class IndependentHandoff(unittest.TestCase):
 def test_both_actual_sources_produce_and_consume_wire(self):
  for cap in sorted(RAW.glob('pregame-*')):
   envelope=export_requests(cap,COHORT);wire=canonical(envelope);before={p:p.read_bytes() for p in cap.glob('*/body.raw')};self.assertEqual(read_requests(wire,cap,COHORT),envelope);consumer=conditional_requests(wire,cap,COHORT)
   self.assertEqual((consumer['candidate_denominator'],len(consumer['requests']),consumer['source_abstentions']),(36,26,10));self.assertFalse(consumer['actual_model_consumer_executed']);self.assertEqual(consumer['forecasted_rows'],0)
   self.assertEqual(len(envelope['requests']['rows']),36);self.assertTrue(all(r['genuine_participation_probability'] is None and r['legal_eligibility'] is None and r['forecast'] is None for r in envelope['requests']['rows']))
   self.assertEqual(before,{p:p.read_bytes() for p in before});(OUT/(cap.name+'.handoff.json')).write_bytes(wire);(OUT/(cap.name+'.consumer.json')).write_text(json.dumps(consumer,indent=2)+'\n')
 def test_resealed_payload_mutations_rejected(self):
  cap=next(RAW.glob('pregame-*'));base=export_requests(cap,COHORT)
  for attack in ['q','eligibility','forecast-row','forecast-count','conditioning','player','team','game','clock','drop','duplicate','approval','model','sourcehash']:
   x=copy.deepcopy(base);r=x['requests']['rows'][0]
   if attack=='q':r['genuine_participation_probability']=1
   if attack=='eligibility':r['legal_eligibility']=True
   if attack=='forecast-row':r['forecast']={'over':1}
   if attack=='forecast-count':x['forecasted_rows']=1
   if attack=='conditioning':r['conditioning']='unconditional'
   if attack=='player':r['player_id']='espn:player:999'
   if attack=='team':r['team_id']='espn:team:999'
   if attack=='game':x['cohort']['game_id']='401070213'
   if attack=='clock':x['cohort']['freeze_at']='2026-11-19T01:00:00Z'
   if attack=='drop':x['requests']['rows'].pop()
   if attack=='duplicate':x['requests']['rows'].append(copy.deepcopy(r))
   if attack=='approval':x['reviewer']='independent';x['approved']=True
   if attack=='model':x['model_attached']=True
   if attack=='sourcehash':x['source_file_hashes']['scoreboard']['body.raw']='0'*64
   del x['payload_sha256'];x['payload_sha256']=digest(canonical(x))
   with self.subTest(attack=attack),self.assertRaises(ValueError):read_requests(canonical(x),cap,COHORT)
 def test_original_wire_rejects_changed_body_or_receipt_bytes(self):
  cap=next(RAW.glob('pregame-*'));wire=canonical(export_requests(cap,COHORT))
  for which in ['body.raw','receipt.json']:
   with self.subTest(which=which),tempfile.TemporaryDirectory() as tmp:
    p=pathlib.Path(tmp)/'cap';shutil.copytree(cap,p);f=p/'roster-5'/which;f.write_bytes(f.read_bytes()+b'\n')
    with self.assertRaises(ValueError):read_requests(wire,p,COHORT)
 def test_duplicate_json_keys_nonfinite_and_no_source_approval(self):
  cap=next(RAW.glob('pregame-*'))
  for wire in [b'{"schema":"x","schema":"x"}',b'{"q":NaN}',b'{"q":Infinity}']:
   with self.subTest(wire=wire),self.assertRaises(ValueError):read_requests(wire,cap,COHORT)
if __name__=='__main__':unittest.main(verbosity=2)
