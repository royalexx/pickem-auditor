from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from v2.nba_architecture.research_profile_v1 import build_requests, ROOT

CAP=ROOT/'docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441'
COHORT=json.loads((ROOT/'docs/nba_architecture/p1_prospective_20261118/COHORT.json').read_bytes())

def change(path,fn):
    p=path/'roster-5/body.raw';x=json.loads(p.read_bytes());fn(x);p.write_text(json.dumps(x));r=path/'roster-5/receipt.json';q=json.loads(r.read_bytes());q['raw_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();r.write_text(json.dumps(q))

class ProfileTests(unittest.TestCase):
    def test_real_default_partial_scope_and_unknowns(self):
        x=build_requests(CAP,COHORT)
        self.assertEqual(x['profile'],'source_listed_subset');self.assertEqual(x['source_candidate_rows'],36)
        self.assertGreater(x['source_ready_rows'],0);self.assertEqual(x['source_ready_rows']+x['abstained_source_rows'],36)
        self.assertFalse(x['complete_legal_roster_required']);self.assertIsNone(x['legal_eligible_population_count'])
        self.assertEqual(x['forecasted_rows'],0);self.assertTrue(all(r['genuine_participation_probability'] is None for r in x['rows']))
        minix=next(r for r in x['rows'] if r['name']=='Riley Minix');self.assertIn('CAPTURED_ROSTER_DISAGREEMENT',minix['issues'])

    def test_invalid_member_does_not_block_valid_others(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'capture';shutil.copytree(CAP,p)
            change(p,lambda x:x['athletes'][0].update(id='bad'))
            x=build_requests(p,COHORT);self.assertEqual(x['source_candidate_rows'],36);self.assertGreater(x['source_ready_rows'],0)
            self.assertTrue(any('INVALID_PLAYER_ID' in r['issues'] for r in x['rows']))

    def test_duplicate_missing_and_malformed_population_denominators(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'capture';shutil.copytree(CAP,p)
            change(p,lambda x:x['athletes'].append(deepcopy(x['athletes'][0])))
            x=build_requests(p,COHORT);self.assertEqual(x['source_candidate_rows'],37)
            self.assertEqual(sum('DUPLICATE_PLAYER_IDENTITY' in r['issues'] for r in x['rows']),2)
            shutil.rmtree(p/'roster-5');x=build_requests(p,COHORT);self.assertTrue(x['missing_source_population']);self.assertEqual(x['source_candidate_rows'],35);self.assertGreater(x['source_ready_rows'],0)

    def test_bad_optional_row_is_local(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'capture';shutil.copytree(CAP,p);change(p,lambda x:x['athletes'][0].update(injuries=None))
            x=build_requests(p,COHORT);self.assertGreater(x['source_ready_rows'],0);self.assertTrue(any('INVALID_INJURY_LIST' in r['issues'] for r in x['rows']))

    def test_altered_bytes_late_clocks_and_wrong_team_abstain_source(self):
        for attack in ('bytes','late','team'):
            with self.subTest(attack=attack),tempfile.TemporaryDirectory() as t:
                p=Path(t)/'capture';shutil.copytree(CAP,p)
                if attack=='bytes':f=p/'roster-5/body.raw';f.write_bytes(f.read_bytes()+b' ')
                if attack=='late':f=p/'roster-5/receipt.json';x=json.loads(f.read_bytes());x['ingested_at']='2026-11-19T00:01:00Z';f.write_text(json.dumps(x))
                if attack=='team':change(p,lambda x:x['team'].update(id='999'))
                x=build_requests(p,COHORT);cle=[r for r in x['rows'] if r['team_id']=='espn:team:5'];self.assertTrue(all(r['source_request_status']=='ABSTAIN' for r in cle));self.assertGreater(x['source_ready_rows'],0)

    def test_corrupt_optional_team_name_does_not_abort_other_team(self):
        import re
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'capture';shutil.copytree(CAP,p)
            folder=p/'official-cle-roster';f=folder/'body.raw';text=f.read_text();m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',text,re.S);obj=json.loads(m[1]);obj['props']['pageProps']['team']['name']=None
            f.write_text(text[:m.start(1)]+json.dumps(obj)+text[m.end(1):]);r=folder/'receipt.json';receipt=json.loads(r.read_bytes());receipt['raw_sha256']=hashlib.sha256(f.read_bytes()).hexdigest();r.write_text(json.dumps(receipt))
            x=build_requests(p,COHORT);self.assertEqual(x['source_candidate_rows'],36);self.assertGreater(x['source_ready_rows'],0)
            self.assertTrue(all(r['source_request_status']=='ABSTAIN' for r in x['rows'] if r['team_id']=='espn:team:5'))

    def test_official_only_candidate_is_retained_unmatched(self):
        import re
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'capture';shutil.copytree(CAP,p);folder=p/'official-cle-roster';f=folder/'body.raw';text=f.read_text();m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',text,re.S);obj=json.loads(m[1]);obj['props']['pageProps']['rosterData']['roster'].append({'id':9999999,'name':'Unmatched Source Player'})
            f.write_text(text[:m.start(1)]+json.dumps(obj)+text[m.end(1):]);r=folder/'receipt.json';receipt=json.loads(r.read_bytes());receipt['raw_sha256']=hashlib.sha256(f.read_bytes()).hexdigest();r.write_text(json.dumps(receipt))
            x=build_requests(p,COHORT);self.assertEqual(x['source_candidate_rows'],37);extra=next(r for r in x['rows'] if r['name']=='Unmatched Source Player');self.assertIn('UNMATCHED_OFFICIAL_SOURCE_IDENTITY',extra['issues']);self.assertEqual(extra['source_request_status'],'ABSTAIN');self.assertGreater(x['source_ready_rows'],0)
