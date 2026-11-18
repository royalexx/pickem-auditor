"""Independent restricted-demonstration public-path and boundary controls."""
import copy,json,pathlib,unittest
from v2.nba_architecture.p1_bounded_demo_v1 import demonstrate,classify_rows
ROOT=pathlib.Path(__file__).resolve().parents[4]
S=ROOT/'docs/nba_architecture/substantive_remediation_20261117/source_search'
def inputs():
 pdf=(S/'nba_pdf.raw').read_bytes();pr=json.loads((S/'nba_pdf.receipt.json').read_bytes());pr['raw_sha256']=pr['sha256']
 return [pdf,pr,(S/'espn2018.raw').read_bytes(),json.loads((S/'espn2018.receipt.json').read_bytes())]
class IndependentDemo(unittest.TestCase):
 def test_actual_native_source_handoff(self):
  x=demonstrate(*inputs());self.assertEqual((x['attempted_rows'],x['included_rows'],x['explicit_dnp_rows'],x['excluded_rows']),(26,24,2,0))
  self.assertEqual(x['attempted_rows'],x['included_rows']+x['explicit_dnp_rows']+x['excluded_rows'])
  self.assertEqual([r['source_row'] for r in x['rows']],x['source_admission']['rows'])
  self.assertEqual(len({r['source_row']['player_id'] for r in x['rows']}),26)
  self.assertTrue(all(r['source_row']['exact_seconds']>=30 for r in x['rows'] if r['disposition']=='INCLUDED'))
  self.assertTrue(all(r['source_row']['stats']=={} for r in x['rows'] if r['disposition']=='DNP'))
  self.assertIsNone(x['target_eligible_roster_count']);self.assertEqual((x['B_P1_01'],x['B_P1_02'],x['G1']),('BLOCKED','BLOCKED','NO-GO'))
  for r in x['rows']:self.assertIsNone(r['source_row']['genuine_participation_probability']);self.assertIsNone(r['source_row']['target_eligible'])
  print(json.dumps(x,sort_keys=True))
 def test_untrusted_boundary_policy_keeps_all_rows(self):
  cases=[('PLAYED',s) for s in [-1,0,1,29,30,49,2880,2881,True,29.9,'30',None]]+[('PLAYED_ZERO_MINUTES',0),('UNKNOWN',120),('DNP',None)]
  rows=[dict(state=state,exact_seconds=s,stats={} if state=='DNP' else {'points':3},player_id=str(i)) for i,(state,s) in enumerate(cases)]
  before=copy.deepcopy(rows);x=classify_rows(rows,2880);self.assertEqual(rows,before);self.assertEqual(len(x),len(rows))
  self.assertEqual([r['source_row'] for r in x],before)
  self.assertEqual([i for i,r in enumerate(x) if r['disposition']=='INCLUDED'],[4,5,6])
  self.assertEqual(x[-1]['disposition'],'DNP');self.assertTrue(all(r['reason'] for r in x))
  # Policy helper is explicitly untrusted: these rows are never passed as admitted input.
 def test_filtering_cannot_admit_bad_sources(self):
  for kind in ['altered','missing','duplicate','wrong_game','late','false_completeness']:
   args=inputs();kw={}
   if kind=='altered':args[2]+=b' '
   elif kind=='late':kw['input_freeze_at']='2018-10-19T23:45:00Z'
   elif kind=='false_completeness':args[3]['correction_history_complete']=True
   else:
    x=json.loads(args[2]);people=x['boxscore']['players'][0]['statistics'][0]['athletes']
    if kind=='missing':people.pop()
    if kind=='duplicate':people.append(copy.deepcopy(people[0]))
    if kind=='wrong_game':x['header']['id']='999'
    args[2]=json.dumps(x).encode()
   x=demonstrate(*args,**kw)
   with self.subTest(kind=kind):
    self.assertEqual(x['status'],'REJECTED_WHOLE_SOURCE');self.assertEqual(x['included_rows'],0)
    self.assertEqual(x['admission']['attempted_rows'],25 if kind=='missing' else 27 if kind=='duplicate' else 26)
    self.assertEqual(x['admission']['accepted_rows'],0);self.assertEqual(x['admission']['rejected_rows'],x['admission']['attempted_rows'])
    self.assertIsNone(x['target_eligible_roster_count'])
if __name__=='__main__':unittest.main(verbosity=2)
