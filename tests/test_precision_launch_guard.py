"""Offline validation for safe one-time Windows training launches."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from precision_launch_guard import resolve_request

SHA_A="a"*40
SHA_B="b"*40

def request():
    return {"schema":"pickem_precision_campaign_launch_v1",
            "campaign_id":"week-20261102","index":0,"max_per_position":"0",
            "as_of":"2026-10-29","code_sha":"","source_sha":SHA_B}


class LaunchGuardTest(unittest.TestCase):
    def test_first_job_pins_code_and_history(self):
        v=resolve_request(request(),event_sha=SHA_A)
        self.assertEqual(v["CODE_HEAD"], SHA_A)
        self.assertEqual(v["SOURCE_FREEZE_SHA"], SHA_B)
        self.assertEqual(v["INDEX"], "0")

    def test_recovery_uses_original_freeze(self):
        q=request()
        q.update(index=3,code_sha=SHA_A)
        v=resolve_request(q,event_sha="c"*40)
        self.assertEqual((v["INDEX"],v["CODE_HEAD"],v["SOURCE_FREEZE_SHA"]),("3",SHA_A,SHA_B))

    def test_bad_inputs_fail_closed(self):
        for key,val in (("index",True),("index",31),("source_sha",""),
                        ("code_sha","xyz"),("max_per_position","999"),
                        ("as_of","2030-01-01"),("campaign_id","bad\nvalue")):
            q=request()
            q[key]=val
            with self.subTest(key=key), self.assertRaises(ValueError):
                resolve_request(q,event_sha=SHA_A)


if __name__=="__main__":
    unittest.main()
