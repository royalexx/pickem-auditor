import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from research.nba_phase7.fixtures import AT,fetch,supplements
from research.nba_phase7.pilot import capture_slot
from research.nba_phase8a.dataset import candidate_table

class ActivationTests(unittest.TestCase):
    def slot(self):
        from tests.nba_phase7.test_pilot import PilotTests
        return PilotTests().slot()
    def test_deadline_after_ledger_blocks_pointer(self):
        from research.nba_phase7.sources import build_game_ledger
        clock=[AT]
        def late(*args):
            result=build_game_ledger(*args);clock[0]='2026-11-16T23:31:00Z';return result
        with tempfile.TemporaryDirectory() as d:
            s=supplements(Path(d)/'supplements')
            with patch('research.nba_phase7.pilot.build_game_ledger',side_effect=late):
                result=capture_slot(self.slot(),Path(d)/'runs',fixture=True,fixture_fetch=fetch,fixture_clock=lambda:clock[0],fixture_supplement=s)
            self.assertEqual(result['status'],'BLOCKED_CAPTURE');self.assertFalse(list(Path(d).rglob('FIRST_CAPTURE.json')))
    def test_dataset_no_outcomes_and_full_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            s=supplements(Path(d)/'supplements')
            capture_slot(self.slot(),Path(d)/'runs',fixture=True,fixture_fetch=fetch,fixture_clock=lambda:AT,fixture_supplement=s)
            ledger=json.loads(next(Path(d).rglob('game_day_ledger.json')).read_text())
            table=ledger['candidate_research_table'];self.assertEqual(len(table['rows']),12)
            self.assertFalse(table['verified_eligible_denominator']);self.assertEqual(table['postgame_records'],0)
            for r in table['rows']:
                self.assertIsNone(r['legal_eligibility']);self.assertIsNone(r['postgame_appearance'])
                self.assertEqual(set(r['prior_participation_history']),{'5','10','20'})
    def test_postgame_feature_injection_rejected(self):
        with self.assertRaisesRegex(ValueError,'POSTGAME_FEATURE'):
            candidate_table({'actual_participants':[1]}, {})
    def test_concurrent_capture_single_owner(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as d:
            s=supplements(Path(d)/'supplements')
            clocks=[AT,'2026-11-16T23:26:00Z']
            def run(at):return capture_slot(self.slot(),Path(d)/'runs',fixture=True,fixture_fetch=fetch,fixture_clock=lambda:at,fixture_supplement=s)
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,clocks))
            self.assertEqual(sum(r['status']=='CAPTURED_F_BLOCKED' for r in results),1)
            self.assertEqual(sum(r['source_attempted'] for r in results),1)
    def test_missing_poppler_is_explicit_failure(self):
        from research.nba_phase7.evidence import injury_pdf
        from v2.nba_ws1.store import Receipt
        raw=b'%PDF fixture';r=Receipt.capture(raw,source='https://ak-static.cms.nba.com/test.pdf',observed_at=AT,origin='fixture')
        with patch('subprocess.check_output',side_effect=FileNotFoundError('pdftotext')):
            with self.assertRaises(FileNotFoundError):injury_pdf(raw,r,freeze_at=AT)
    def test_null_team_directory_record_is_ignored(self):
        from research.nba_phase7.sources import acquire_supplements
        from io import BytesIO
        directory=[{'TEAM_CITY':None,'TEAM_NAME':None,'TEAM_ID':0,'TEAM_SLUG':None},
          {'TEAM_CITY':'Boston','TEAM_NAME':'Celtics','TEAM_ID':1,'TEAM_SLUG':'celtics'}]
        raw=('<script id="__NEXT_DATA__">'+json.dumps({'props':{'pageProps':{'players':directory}}})+'</script>').encode()
        calls=[]
        def source(req,**kw):
            calls.append(req.full_url)
            return BytesIO(raw if req.full_url.endswith('/players') else b'no PDF available')
        board={'competitions':[{'competitors':[{'team':{'displayName':'Boston Celtics'}}]}]}
        with tempfile.TemporaryDirectory() as d, patch('research.nba_phase7.sources.urlopen',side_effect=source):
            result=acquire_supplements(Path(d)/'supplements',board,deadline_at='2099-01-01T00:00:00Z')
        self.assertIn('https://www.nba.com/team/1/celtics',calls)
        self.assertIn('nba_team_roster',[i['kind'] for i in result['items']])
