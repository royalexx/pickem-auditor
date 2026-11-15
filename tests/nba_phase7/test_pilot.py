from datetime import timedelta
from pathlib import Path
import json
import tempfile
import unittest
from research.nba_phase7.fixtures import GAME,AT,fetch,supplements
from research.nba_phase7.pilot import registered_slots,window_state,capture_slot
from v2.nba_ws1.capture import capture

class PilotTests(unittest.TestCase):
    def slot(self):return {'slot':1,'toronto_date':'2026-11-16','game':GAME,'scheduled_freeze_at':'2026-11-16T23:30:00Z'}
    def test_original_ten_registrations(self):
        slots=registered_slots();self.assertEqual(len(slots),10);self.assertEqual(slots[0]['game']['game_id'],'espn:game:401909994')
    def test_window_boundaries(self):
        self.assertEqual(window_state(self.slot(),'2026-11-16T23:19:59Z'),'NOT_DUE')
        self.assertEqual(window_state(self.slot(),'2026-11-16T23:20:00Z'),'ACQUISITION_WINDOW')
        self.assertEqual(window_state(self.slot(),'2026-11-16T23:30:00Z'),'ACQUISITION_WINDOW')
        self.assertEqual(window_state(self.slot(),'2026-11-16T23:30:00.000001Z'),'MISSED_FREEZE')
    def test_nonproduction_capture_to_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            supplement=supplements(Path(d)/'supplements')
            r=capture_slot(self.slot(),Path(d)/'runs',fixture=True,fixture_fetch=fetch,fixture_clock=lambda:AT,fixture_supplement=supplement)
            self.assertEqual(r['status'],'CAPTURED_F_BLOCKED',r);self.assertEqual(r['denominators']['original_candidate_players'],12)
            self.assertEqual(r['forecast_count'],0)
            ledger=next((Path(d)/'runs').rglob('game_day_ledger.json'));data=json.loads(ledger.read_text())
            self.assertEqual(sum(w['verified_identity_count'] for w in data['identity_crosswalks']),12)
    def test_exact_second_game_no_earliest_substitution(self):
        with tempfile.TemporaryDirectory() as d:
            r=capture('2026-11-16',Path(d)/'capture',game_id='espn:game:2',expected_game=GAME,fetch_bytes=fetch,clock=lambda:AT,fixture=True)
            self.assertEqual(r['game']['game_id'],'espn:game:2')
    def test_schedule_change_blocks(self):
        changed={**GAME,'home_team_id':'espn:team:99'}
        with tempfile.TemporaryDirectory() as d:
            r=capture('2026-11-16',Path(d)/'capture',game_id='espn:game:2',expected_game=changed,fetch_bytes=fetch,clock=lambda:AT,fixture=True)
            self.assertEqual(r['status'],'blocked');self.assertIn('REGISTERED_SCHEDULE_CHANGED',str(r))
    def test_capture_after_tipoff_never_backfilled(self):
        with tempfile.TemporaryDirectory() as d:
            r=capture('2026-11-16',Path(d)/'capture',game_id='espn:game:2',fetch_bytes=fetch,clock=lambda:'2026-11-17T01:00:00Z',fixture=True)
            self.assertIn('EXACT_REGISTERED_GAME_NOT_PREGAME',str(r))
    def test_late_response_preserves_raw_receipt(self):
        clocks=iter([AT,AT,'2026-11-16T23:31:00Z','2026-11-16T23:31:00Z'])
        with tempfile.TemporaryDirectory() as d:
            r=capture('2026-11-16',Path(d)/'capture',game_id='espn:game:2',freeze_deadline_at='2026-11-16T23:30:00Z',fetch_bytes=fetch,clock=lambda:next(clocks),fixture=True)
            self.assertEqual(r['status'],'blocked');self.assertEqual(len(r['sources']),1)
    def test_first_capture_not_replaced_by_second_invocation(self):
        with tempfile.TemporaryDirectory() as d:
            supplement=supplements(Path(d)/'supplements')
            a=capture_slot(self.slot(),Path(d)/'runs',fixture=True,fixture_fetch=fetch,fixture_clock=lambda:AT,fixture_supplement=supplement)
            b=capture_slot(self.slot(),Path(d)/'runs',fixture=True,fixture_fetch=fetch,fixture_clock=lambda:'2026-11-16T23:26:00Z',fixture_supplement=supplement)
            self.assertEqual(a['status'],'CAPTURED_F_BLOCKED');self.assertEqual(b['status'],'BLOCKED_ALREADY_CAPTURED')
