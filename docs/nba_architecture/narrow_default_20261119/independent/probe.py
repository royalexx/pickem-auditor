"""Independent actual default path and local-abstention controls."""
import copy,hashlib,json,pathlib,re,shutil,subprocess,tempfile,unittest
from v2.nba_architecture.research_profile_v1 import build_requests,CONFIG
ROOT=pathlib.Path(__file__).resolve().parents[4];CAP=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441';COHORT=json.loads((ROOT/'docs/nba_architecture/p1_prospective_20261118/COHORT.json').read_bytes())
def change(path,fn):
 f=path/'roster-5/body.raw';x=json.loads(f.read_bytes());fn(x);f.write_text(json.dumps(x));r=path/'roster-5/receipt.json';x=json.loads(r.read_bytes());x['raw_sha256']=hashlib.sha256(f.read_bytes()).hexdigest();r.write_text(json.dumps(x))
class IndependentSubset(unittest.TestCase):
 def check(self,x):
  self.assertEqual(x['profile'],'source_listed_subset');self.assertEqual(x['source_candidate_rows'],x['source_ready_rows']+x['abstained_source_rows']);self.assertEqual(len(x['rows']),x['source_candidate_rows']);self.assertEqual(x['forecasted_rows'],0);self.assertFalse(x['complete_legal_roster_required']);self.assertIsNone(x['legal_eligible_population_count']);self.assertEqual(x['historical_full_population_gates'],'SUPERSEDED_FOR_THIS_PROFILE');self.assertFalse(x['production_release'])
  for r in x['rows']:self.assertIsNone(r['legal_eligibility']);self.assertIsNone(r['genuine_participation_probability']);self.assertIsNone(r['forecast']);self.assertEqual(r['conditioning'],'conditional_on_participation')
 def test_actual_default(self):
  self.assertEqual(json.loads(CONFIG.read_bytes())['default_profile'],'source_listed_subset');x=build_requests(CAP,COHORT);self.check(x);self.assertEqual((x['source_candidate_rows'],x['source_ready_rows'],x['abstained_source_rows']),(36,26,10));self.assertEqual(sum('SOURCE_DECLARED_OUT' in r['issues'] for r in x['rows']),9);self.assertEqual(sum('CAPTURED_ROSTER_DISAGREEMENT' in r['issues'] for r in x['rows']),1)
 def test_per_member_failure_preserves_other_ready_rows(self):
  for field,value in [('id','bad'),('displayName',' '),('injuries',None),('injuries',['not-an-object'])]:
   with self.subTest(field=field,value=value),tempfile.TemporaryDirectory() as tmp:
    p=pathlib.Path(tmp)/'cap';shutil.copytree(CAP,p);change(p,lambda x:x['athletes'][0].update({field:value}));x=build_requests(p,COHORT);self.check(x);self.assertEqual(x['source_candidate_rows'],37 if field=='displayName' else 36);self.assertEqual(x['source_ready_rows'],25)
 def test_duplicate_and_missing_populations(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'cap';shutil.copytree(CAP,p);change(p,lambda x:x['athletes'].append(copy.deepcopy(x['athletes'][0])));x=build_requests(p,COHORT);self.check(x);self.assertEqual(x['source_candidate_rows'],37);self.assertEqual(sum('DUPLICATE_PLAYER_IDENTITY' in r['issues'] for r in x['rows']),2);self.assertGreater(x['source_ready_rows'],0)
   shutil.rmtree(p/'roster-5');x=build_requests(p,COHORT);self.check(x);self.assertEqual(x['source_candidate_rows'],35);self.assertTrue(x['missing_source_population']);self.assertIsNone(x['coverage'][0]['attempted_rows']);self.assertGreater(x['source_ready_rows'],0)
 def test_invalid_shared_source_stays_local_to_team(self):
  for attack in ['bytes','late','wrongteam','clock-null','receipt-null','population-object']:
   with self.subTest(attack=attack),tempfile.TemporaryDirectory() as tmp:
    p=pathlib.Path(tmp)/'cap';shutil.copytree(CAP,p)
    if attack=='bytes':f=p/'roster-5/body.raw';f.write_bytes(f.read_bytes()+b' ')
    if attack=='wrongteam':change(p,lambda x:x['team'].update(id='999'))
    if attack=='population-object':change(p,lambda x:x.update(athletes={'fabricated-key':1}))
    if attack in ['late','clock-null','receipt-null']:
     f=p/'roster-5/receipt.json';x=json.loads(f.read_bytes())
     if attack=='late':x['ingested_at']='2026-11-19T00:01:00Z'
     if attack=='clock-null':x['ingested_at']=None
     if attack=='receipt-null':x=None
     f.write_text(json.dumps(x))
    x=build_requests(p,COHORT);self.check(x);self.assertGreater(x['source_ready_rows'],0);self.assertTrue(all(r['source_request_status']=='ABSTAIN' for r in x['rows'] if r['team_id']=='espn:team:5'))
    if attack=='population-object':self.assertEqual(x['source_candidate_rows'],35);self.assertTrue(x['missing_source_population'])
 def test_optional_source_corruption_retains_valid_other_team(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'cap';shutil.copytree(CAP,p);f=p/'official-cle-roster/body.raw';raw=f.read_text();match=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw,re.S);x=json.loads(match[1]);x['props']['pageProps']['team']['name']=None;f.write_text(raw[:match.start(1)]+json.dumps(x)+raw[match.end(1):]);r=p/'official-cle-roster/receipt.json';x=json.loads(r.read_bytes());x['raw_sha256']=hashlib.sha256(f.read_bytes()).hexdigest();r.write_text(json.dumps(x));x=build_requests(p,COHORT);self.check(x);self.assertEqual(x['source_candidate_rows'],36);self.assertGreater(x['source_ready_rows'],0);self.assertTrue(all(r['source_request_status']=='ABSTAIN' for r in x['rows'] if r['team_id']=='espn:team:5'))
 def test_malformed_optional_population_is_contained(self):
  for population in [None,{'not-a-list':1},[None],[{'bad':'member'}]]:
   with self.subTest(population=population),tempfile.TemporaryDirectory() as tmp:
    p=pathlib.Path(tmp)/'cap';shutil.copytree(CAP,p);f=p/'official-cle-roster/body.raw';raw=f.read_text();match=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw,re.S);x=json.loads(match[1]);x['props']['pageProps']['rosterData']['roster']=population;f.write_text(raw[:match.start(1)]+json.dumps(x)+raw[match.end(1):]);r=p/'official-cle-roster/receipt.json';x=json.loads(r.read_bytes());x['raw_sha256']=hashlib.sha256(f.read_bytes()).hexdigest();r.write_text(json.dumps(x));x=build_requests(p,COHORT);self.check(x);self.assertEqual(x['source_candidate_rows'],36);self.assertGreater(x['source_ready_rows'],0)
 def test_official_only_candidates_keep_native_ids(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'cap';shutil.copytree(CAP,p);change(p,lambda x:x['athletes'].pop(0));x=build_requests(p,COHORT);self.check(x);self.assertEqual(x['source_candidate_rows'],36);unmatched=[r for r in x['rows'] if 'UNMATCHED_OFFICIAL_SOURCE_IDENTITY' in r['issues']];self.assertEqual(len(unmatched),1);self.assertTrue(unmatched[0]['player_id'].startswith('nba:player:'));self.assertTrue(unmatched[0]['team_id'].startswith('nba:team:'));self.assertEqual(unmatched[0]['source_request_status'],'ABSTAIN')
 def test_claims_do_not_create_forecasts_or_known_q(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp)/'cap';shutil.copytree(CAP,p);change(p,lambda x:x['athletes'][0].update(legal_eligibility=True,genuine_participation_probability=1,forecast={'p_over':1},approved=True));x=build_requests(p,COHORT);self.check(x)
 def test_historical_implementation_and_receipts_preserved(self):
  for f in ['v2/nba_architecture/contracts.py','v2/nba_architecture/v2_contracts.py','v2/nba_architecture/admission_v1.py','v2/nba_architecture/p1_listed_source_v1.py','docs/nba_architecture/p1_source_admission_20261118/installed_identity_root.json','docs/nba_architecture/p1_overnight_20261119/independent/FINAL_DECISION.md']:
   self.assertEqual((ROOT/f).read_bytes(),subprocess.check_output(['git','show','d809c39c:'+f],cwd=ROOT))
if __name__=='__main__':unittest.main(verbosity=2)
