"""Every prepared prop is evaluated before ranking; dropped inputs are receipted."""
import sys
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import jobs
import pickem_math as pm


class PreparedUniverseTests(unittest.TestCase):
    def test_evaluates_entire_prepared_batch_and_receipts_all_reasons(self):
        now=datetime(2026,11,8,12,tzinfo=timezone.utc)
        def row(i,start=None):
            return {"id":f"NFL|Player {i}|tackles + assists|over",
                    "side":"over","line":5.5,
                    "_run_id":"SUNDAY","_run_at":"2026-11-08 07:00 ET",
                    "_meta":{"sport":"NFL","stat":"tackles + assists",
                             "player_id":str(i),"event_start":(start or (now+timedelta(hours=6))).isoformat()}}
        batch=[row(1),row(2),row(3),row(4,start=now-timedelta(minutes=1))]
        def calculate(candidate, now):
            ident=candidate["id"]
            if "Player 2" in ident:raise pm.PickemError("unverified_data")
            if "Player 3" in ident:return {"ok":False,"reason":"unrankable"}
            return {"ok":True,"id":ident}
        attempts=[]
        with patch.object(jobs,"_pipeline_input",side_effect=lambda x:{"id":x["id"]}),\
             patch.object(jobs.pm,"evaluate_candidate",side_effect=calculate),\
             patch.object(jobs,"pipeline_to_snapshot",side_effect=lambda *args,**kw:{"ok":True}):
            forecasts, errors=jobs.run_pipeline_batch(batch,now=now,attempt_receipts=attempts)
        self.assertEqual(len(forecasts),1)
        self.assertEqual(errors,2)
        self.assertEqual(len(attempts),4)
        self.assertEqual([x["status"] for x in attempts],
                         ["forecast","unavailable","unavailable","unavailable"])
        self.assertEqual(attempts[1]["reason"],"pipeline_exception:unverified_data")
        self.assertEqual(attempts[2]["reason"],"pipeline_not_ok:unrankable")
        self.assertEqual(attempts[3]["reason"],"event_started_before_evaluation")
        self.assertTrue(all("line" in a and "stat" in a and "player_id" in a for a in attempts))


if __name__=="__main__":
    unittest.main()
