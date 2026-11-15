import json
from pathlib import Path
import tempfile
import unittest
from v2.nba_ws1.capture import capture

class CaptureTests(unittest.TestCase):
    def test_missed_deadline_no_network(self):
        calls=[]
        with tempfile.TemporaryDirectory() as d:
            r=capture('2026-11-16',Path(d)/'capture',game_id='espn:game:2',freeze_deadline_at='2026-11-16T23:30:00Z',
                clock=lambda:'2026-11-16T23:31:00Z',fetch_bytes=lambda url:calls.append(url),fixture=True)
            self.assertEqual(r['status'],'blocked');self.assertIn('FREEZE_DEADLINE_MISSED',str(r));self.assertEqual(calls,[])
    def test_injected_transport_cannot_claim_original(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'FIXTURE_TRANSPORT_REQUIRED'):
                capture('2026-11-16',Path(d)/'capture',fetch_bytes=lambda u:b'{}')
    def test_history_lookback_is_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            for value in (0,11,True):
                with self.subTest(value=value),self.assertRaisesRegex(ValueError,'HISTORY_LOOKBACK_BOUND'):
                    capture('2026-11-16',Path(d)/'capture',history_games_per_team=value)
