"""Regression tests for frozen Bayesian posterior crash-recovery overlay."""
from __future__ import annotations
import ast
import importlib.util
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch as mock_patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import precision_posterior_safety_patch as repair

# Recreates exact anchor sequences, without building or sampling a PyMC model.
FIXTURE='''MAX_RHAT=1.01
MIN_ESS=400

def fit():
    nuts={"target_accept":.99}
    return None

def _to_values(group):
    values=[]
        if getattr(group,"data_vars",None):
            values.extend(np.asarray(group.to_array(),dtype=float).ravel().tolist())
    return values

def main():
    a.strict_all_effects
    posterior=fit()
    checks=diagnostics(posterior,all_effects=a.strict_all_effects)
    a.out.mkdir(parents=True,exist_ok=True)
    posterior.to_netcdf(a.out/"posterior.nc")
    return checks
'''


class SafetyOverlayTests(unittest.TestCase):
    def test_crash_cause_removed_and_checkpoint_first(self):
        patched=repair.apply_patch(FIXTURE)
        self.assertNotIn("np.asarray(group.to_array()",patched)
        self.assertIn("for variable in group.data_vars.values():",patched)
        self.assertIn("posterior.to_netcdf(pending)",patched)
        self.assertIn("posterior_checkpoint.json",patched)
        self.assertIn("NUTS_POSTERIOR_CHECKPOINT",patched)
        self.assertLess(patched.index("posterior.to_netcdf(pending)"),
                        patched.index("checks=diagnostics(posterior,all_effects=a.strict_all_effects)"))
        self.assertIn("MAX_RHAT=1.01",patched)
        self.assertIn("MIN_ESS=400",patched)
        self.assertIn('nuts={"target_accept":.99}',patched)

    def test_only_expected_frozen_segments_changed(self):
        transformed=repair.apply_patch(FIXTURE)
        reference=FIXTURE.replace(repair.OLD_FLATTEN,repair.NEW_FLATTEN).replace(
            repair.OLD_SAVE,repair.NEW_SAVE)
        self.assertEqual(transformed,reference)
        self.assertEqual(transformed.count("posterior.to_netcdf("),1)

    def test_unexpected_version_refused(self):
        for tampered in (FIXTURE.replace("group.to_array()","group.values()"),
                         FIXTURE.replace('posterior.to_netcdf(a.out/"posterior.nc")',"pass"),
                         FIXTURE.replace('nuts={"target_accept":.99}',"nuts={}") ):
            with self.subTest(tampered=tampered[:70]),self.assertRaises(ValueError):
                repair.apply_patch(tampered)

    def test_patch_is_rejected_when_reapplied(self):
        transformed=repair.apply_patch(FIXTURE)
        with self.assertRaisesRegex(ValueError,"unexpected_frozen_code_patch_anchor"):
            repair.apply_patch(transformed)

    def test_cli_rejects_wrong_frozen_blob_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            src=root/"joint_population_bayes.py"
            src.write_text(FIXTURE,encoding="utf-8")
            out=root/"receipt.json"
            with self.assertRaisesRegex(ValueError,"unrecognized_frozen_model_script_blob"):
                repair.main(["--source",str(src),"--receipt",str(out),
                             "--expected-code-sha",repair.FROZEN_CODE_SHA])
            self.assertEqual(src.read_text(encoding="utf-8"),FIXTURE)
            self.assertFalse(out.exists())

    def test_nonmatching_model_commit_refused(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"x.py"
            src.write_text(FIXTURE,encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"unrecognized_frozen_training_commit"):
                repair.main(["--source",str(src),"--receipt",str(Path(d)/"y.json"),
                             "--expected-code-sha","0"*40])

    def test_atomic_checkpoint_logic_compiles_as_main_source(self):
        # NEW_SAVE code is valid Python when inserted under frozen main().
        src='''def run(a,posterior,diagnostics):
    import json
    '''+repair.NEW_SAVE.replace("\n","\n    ")+'''
    return checks
'''
        ast.parse(src)

    def test_known_blob_git_sha(self):
        s=b"sample"
        self.assertEqual(repair.blob_sha(s),
                         hashlib.sha1(b"blob 6\0sample").hexdigest())


if __name__=="__main__":
    unittest.main()
