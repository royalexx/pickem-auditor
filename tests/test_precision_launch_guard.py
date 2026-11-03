"""Offline validation for safe one-time Windows training launches."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from precision_launch_guard import resolve_request, validate_skip_payload, verify_skip_receipt

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


    def test_skip_requires_ledger_and_exact_frozen_inputs(self):
        q=request()
        q.update(index=1, code_sha=SHA_A)
        skip={
            "from_index":0,
            "failed_run_id":41571885953,
            "failure_class":"model_nonconvergence",
            "repair_status":"no_safe_repair",
            "reason":"NUTS convergence diagnostics failed for frozen market zero",
            "as_of":q["as_of"],
            "code_sha":SHA_A,
            "source_sha":SHA_B,
            "report_path":".training-control/skips/market-00.json",
        }
        q["skip"]=skip
        validated=resolve_request(q,event_sha="c"*40)
        self.assertEqual(validated["INDEX"],"1")
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/skip["report_path"]
            path.parent.mkdir(parents=True)
            receipt=dict(skip, schema="pickem_precision_market_skip_v1",
                         campaign_id=q["campaign_id"],to_index=1)
            path.write_text(json.dumps(receipt),encoding="utf-8")
            actual_path=validate_skip_payload(
                q,index=1,code_sha=SHA_A,source_sha=SHA_B,cutoff=q["as_of"])
            verify_skip_receipt(q,report_path=actual_path,root=Path(td))
            receipt["to_index"]=2
            path.write_text(json.dumps(receipt),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"invalid_skip_failure_ledger"):
                verify_skip_receipt(q,report_path=actual_path,root=Path(td))

    def test_no_unsafe_skip_or_freeze_drift(self):
        q=request()
        q.update(index=1,code_sha=SHA_A)
        q["skip"]={
            "from_index":0,
            "failed_run_id":123,
            "failure_class":"market_specific_runtime",
            "repair_status":"attempt_failed",
            "reason":"Native Windows market-specific training crashed repeatedly",
            "as_of":q["as_of"],"code_sha":SHA_A,"source_sha":SHA_B,
            "report_path":".training-control/skips/market-00.json"
        }
        for change in (
            {"from_index":-1}, {"from_index":1},
            {"code_sha":"c"*40}, {"source_sha":"c"*40},
            {"failure_class":"systemic_runner_offline"},
            {"repair_status":"unchecked"},
            {"reason":"bad"},
            {"report_path":".training-control/skips/other.json"},
        ):
            changed=dict(q,skip=dict(q["skip"],**change))
            with self.subTest(change=change),self.assertRaises(ValueError):
                resolve_request(changed,event_sha="d"*40)



if __name__=="__main__":
    unittest.main()
