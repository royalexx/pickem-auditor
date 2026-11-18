from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import nba_p1_prospective_capture as source


class ProspectiveTests(unittest.TestCase):
    def test_real_rosters_and_hostile_native_rows(self):
        for tid,count in [('5',17),('29',18)]:
            raw=(source.PACKET/('roster-initial-'+tid)/'body.raw').read_bytes()
            rows=source.roster_rows(raw,tid);self.assertEqual(len(rows),count)
            self.assertTrue(all(r['legal_eligibility'] is None for r in rows))
            x=json.loads(raw);x['athletes'].append(deepcopy(x['athletes'][0]))
            with self.assertRaises(ValueError):source.roster_rows(json.dumps(x),tid)
            with self.assertRaises(ValueError):source.roster_rows(raw,'999')

    def test_real_schedule_wrong_game_team_start_and_cancelled(self):
        raw=(source.PACKET/'schedule-initial/body.raw').read_bytes();cohort=json.loads((source.PACKET/'COHORT.json').read_bytes())
        source.validate_schedule(raw,cohort,True)
        for attack in ['missing','team','start','cancel']:
            x=json.loads(raw);e=next(e for e in x['events'] if e['id']==cohort['game_id'])
            if attack=='missing':x['events'].remove(e)
            if attack=='team':e['competitions'][0]['competitors'][0]['team']['id']='999'
            if attack=='start':e['date']='2026-11-20T00:00Z'
            if attack=='cancel':e['status']['type']['name']='STATUS_POSTPONED'
            with self.assertRaises(ValueError):source.validate_schedule(json.dumps(x),cohort,True)

    def test_cohort_mutation_rejected_without_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'COHORT.json').write_text('{}')
            with patch.object(source,'PACKET',path),self.assertRaisesRegex(ValueError,'COHORT_BYTES_CHANGED'):
                source.run('pregame',path/'out')

    def test_late_capture_records_miss_without_network(self):
        from datetime import datetime, timezone
        class LateClock:
            @staticmethod
            def now(tz):return datetime(2026,11,19,0,0,tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp, patch.object(source,'datetime',LateClock), patch.object(source,'capture',side_effect=AssertionError('NO_LATE_NETWORK')):
            attempt=source.run('pregame',Path(tmp))
            x=json.loads((attempt/'attempt.json').read_bytes())
            self.assertIn('MISSED_ORIGINAL_FREEZE',x['errors'])
            self.assertIsNone(x['target_eligible_roster_count'])
