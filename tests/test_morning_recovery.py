import sys
import unittest
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from morning_schedule import phase_for_event

class MorningRecoveryTests(unittest.TestCase):
    def at(self,value):
        return datetime.fromisoformat(value.replace('Z','+00:00'))

    def test_dated_push_recovery(self):
        today=self.at('2026-10-29T13:26:00Z')
        path='.github/morning-recovery/2026-10-29.json'
        event={'ref':'refs/heads/main','head_commit':{'message':'ops: recover morning 2026-10-29','added':[path]}}
        self.assertEqual(phase_for_event(event,'push',today)[0],'morning')
        self.assertEqual(phase_for_event(event,'push',self.at('2026-10-30T13:26:00Z'))[0],'skip')
        self.assertEqual(phase_for_event({**event,'ref':'refs/heads/other'},'push',today)[0],'skip')
        self.assertEqual(phase_for_event({**event,'head_commit':{'message':'other','added':[path]}},'push',today)[0],'skip')

    def test_history_trigger_is_safe_and_time_limited(self):
        e={'workflow_run':{'name':'NHL Bayesian history warehouse backfill','conclusion':'success','head_branch':'main'}}
        self.assertEqual(phase_for_event(e,'workflow_run',self.at('2026-10-29T11:35:00Z'))[0],'morning')
        self.assertEqual(phase_for_event(e,'workflow_run',self.at('2026-10-29T23:35:00Z'))[0],'skip')
        self.assertEqual(phase_for_event({'workflow_run':{**e['workflow_run'],'conclusion':'failure'}},'workflow_run',self.at('2026-10-29T11:35:00Z'))[0],'skip')

if __name__=='__main__':
    unittest.main()
