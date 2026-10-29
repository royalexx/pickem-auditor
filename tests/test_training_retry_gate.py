"""Fail-closed offline tests for research-only NUTS retry eligibility."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from training_retry_gate import retry_eligible


def manifest(*,rhat=1.016,ess=262.,bfmi=.72,divergences=0):
    return {
        "schema":"multisport_joint_fit_manifest_v1",
        "model_version":"multisport-joint-bayes-v1",
        "sport":"NBA","stat":"assists",
        "training_cutoff_exclusive":"2023-12-10",
        "diagnostics":{
            "status":"sampling_diagnostics_failed",
            "posterior_sampling_ok":False,
            "max_rhat":rhat,"min_bulk_ess":ess,
            "minimum_bfmi":bfmi,"divergences":divergences
        },
    }


class RetryGate(unittest.TestCase):
    def check(self,record,expected):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"manifest.json"
            path.write_text(json.dumps(record))
            self.assertEqual(
                retry_eligible(path,sport="NBA",stat="assists",
                               cutoff="2023-12-10"),expected)

    def test_only_posterior_convergence_failures_can_retry(self):
        self.check(manifest(),True)
        self.check(manifest(rhat=1.000,ess=248),True)
        self.check(manifest(rhat=1.005,ess=500),False)
        self.check(manifest(divergences=1),False)
        self.check(manifest(bfmi=.25),False)
        self.check(manifest(rhat=float("inf")),False)

    def test_other_failures_and_source_mismatch_block(self):
        for key,val in (
            ("schema","wrong"),("model_version","wrong"),
            ("stat","points"),("training_cutoff_exclusive","2024-01-01")):
            with self.subTest(key=key):
                row=manifest()
                row[key]=val
                self.check(row,False)
        for key,val in (
            ("status","sampling_exception"),("posterior_sampling_ok",True),
            ("min_bulk_ess",float("nan"))):
            with self.subTest(key=key):
                row=manifest()
                row["diagnostics"][key]=val
                self.check(row,False)

    def test_missing_and_malformed_manifest_block(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"missing.json"
            self.assertFalse(retry_eligible(path,sport="NBA",stat="assists",
                                            cutoff="2023-12-10"))
            path.write_text("{")
            self.assertFalse(retry_eligible(path,sport="NBA",stat="assists",
                                            cutoff="2023-12-10"))


if __name__=="__main__":
    unittest.main()
