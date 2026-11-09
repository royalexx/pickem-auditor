"""Adversarial Step 11 release audit: cannot be fooled by code changes."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import reform_step11_release_audit as check


def fixture(destination):
    destination=Path(destination)
    for name in list(check.REQUIRED_CODE)+list(check.REQUIRED_TESTS)+[
        "config/production_consensus.json",
        ".training-control/PAUSED.json",
    ]+[".github/workflows/"+w for w in check.TRAINING_WORKFLOWS]:
        dst=destination/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,dst)
    return destination


class ReleaseAuditTests(unittest.TestCase):
    def test_real_repo_workflows_policy_and_math_fail_closed(self):
        audit=check.inspect_release(ROOT)
        self.assertEqual(audit["pause_guarded_workflow_count"],11)
        self.assertTrue(audit["full_source_stat_combined_nfl_tackles_verified"])
        self.assertTrue(audit["step4a_paired_probability_guard_exists"])
        self.assertTrue(audit["policy_verified_unchanged_60_40"])
        self.assertFalse(audit["independent_third_party_statistical_audit_performed"])
        self.assertFalse(audit["production_promotion_authorized"])
        self.assertFalse(audit["retraining_started"])
        self.assertEqual(audit["original_pinned_outcome_receipt"]["status"],
                         "no_original_source_paths_supplied")
        self.assertEqual(len(audit["future_evidence_gates"]),8)

    def test_misaligned_manual_training_workflow_cannot_pass_audit(self):
        with tempfile.TemporaryDirectory() as d:
            root=fixture(d)
            path=root/".github/workflows/historical-bayes-training.yml"
            source=path.read_text()
            self.assertIn("TRAINING_PAUSED_FOR_MODEL_REFORM_USER_APPROVAL_REQUIRED",source)
            path.write_text(source.replace(
                "TRAINING_PAUSED_FOR_MODEL_REFORM_USER_APPROVAL_REQUIRED",""))
            with self.assertRaisesRegex(check.ReleaseAuditError,
                                        "missing_early_training_pause_guard"):
                check.inspect_release(root)

    def test_unguarded_second_fit_job_not_hidden_by_guarded_preflight(self):
        with tempfile.TemporaryDirectory() as d:
            root=fixture(d)
            path=root/".github/workflows/full-backend-coverage.yml"
            raw=path.read_text()
            token="TRAINING_PAUSED_FOR_MODEL_REFORM_USER_APPROVAL_REQUIRED"
            self.assertEqual(raw.count(token),2)
            before,after=raw.rsplit(token,1)
            path.write_text(before+after)
            with self.assertRaisesRegex(check.ReleaseAuditError,
                                        "missing_early_training_pause_guard"):
                check.inspect_release(root)

    def test_manual_training_pause_cannot_be_disabled_without_failing(self):
        with tempfile.TemporaryDirectory() as d:
            root=fixture(d)
            path=root/".training-control/PAUSED.json"
            policy=json.loads(path.read_text())
            policy["paused"]=False
            path.write_text(json.dumps(policy))
            with self.assertRaisesRegex(check.ReleaseAuditError,
                                        "user_training_pause_not_enforced"):
                check.inspect_release(root)

    def test_production_blend_weights_and_calibration_flag_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root=fixture(d)
            path=root/"config/production_consensus.json"
            config=json.loads(path.read_text())
            config["weight_a"]=.4
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(check.ReleaseAuditError,
                                        "production_policy_changed_or_weakened"):
                check.inspect_release(root)
            config["weight_a"]=.6
            config["empirically_calibrated"]=True
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(check.ReleaseAuditError,
                                        "production_policy_changed_or_weakened"):
                check.inspect_release(root)

    def test_nfl_tackles_solo_only_regression_blocks_release(self):
        with tempfile.TemporaryDirectory() as d:
            root=fixture(d)
            path=root/"scripts/population_nfl.py"
            source=path.read_text()
            source=source.replace('row.get("def_tackles_with_assist")',
                                   'row.get("def_tackles_approximation")')
            path.write_text(source)
            with self.assertRaisesRegex(check.ReleaseAuditError,
                                        "combined_tackles_components_missing"):
                check.inspect_release(root)

    def test_shadow_production_writer_veto(self):
        with tempfile.TemporaryDirectory() as d:
            root=fixture(d)
            path=root/"scripts/reform_step10_calibration_shadow.py"
            path.write_text(path.read_text()+"\n# --emit-config\n")
            with self.assertRaisesRegex(check.ReleaseAuditError,
                                        "shadow_module_has_production_writer"):
                check.inspect_release(root)

    def test_requires_full_pinned_receipt_set(self):
        with self.assertRaisesRegex(check.ReleaseAuditError,
                                    "partial_original_source_path_set"):
            check.inspect_release(ROOT,frozen=ROOT/"not-present.json")


if __name__=="__main__":
    unittest.main()
