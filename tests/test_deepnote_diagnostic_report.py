"""Offline tests for the opt-in Deepnote report and archive."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import contextlib
import errno
import hashlib
import io
import json
import math
import tempfile
import unittest
from unittest.mock import patch

from scripts import deepnote_diagnostic_report as reports


def fixture(**overrides):
    payload = {
        "run_id": "report-001",
        "deepnote_run_id": "execution-001",
        "notebook_id": "notebook-001",
        "status": "success",
        "sport": "NBA",
        "market": "points",
        "model": "synthetic-pace",
        "model_version": "1",
        "git_sha": "f" * 40,
        "tests": {"passed": 5, "failed": 0, "skipped": 1},
        "counts": {"total": 200, "eligible": 185, "rejected": 7, "missing": 5,
                   "unmatched": 3, "abstained": 9},
        "provenance": {
            "input_sha256": "a" * 64, "output_sha256": "b" * 64,
            "input_uri": "input.json", "output_uri": "forecast.json",
        },
        "metrics": {"brier": 0.192},
        "gates": {"matched_cohort": "passed", "release": "not_applicable"},
        "samples": [{"row": row} for row in range(100)],
        "probabilities": [{"id": "synthetic-player", "over": 0.4, "under": 0.5, "push": 0.1}],
        "issues": [],
        "verbose_log": "debug line\n" * 5000,
    }
    payload.update(overrides)
    return payload


class ReportTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)

    def publish(self, payload=None, **kwargs):
        return reports.publish_report(fixture() if payload is None else payload,
                                      self.root, emit_stdout=False, **kwargs)

    def verify(self, **kwargs):
        return reports.verify_report(self.root, "report-001", **kwargs)

    def test_success_is_compact_and_preserves_full_evidence_across_sports(self):
        for sport in ("NBA", "NHL", "NFL"):
            with self.subTest(sport=sport):
                run_id = sport.lower()
                payload = fixture(sport=sport, run_id=run_id)
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    summary = reports.publish_report(payload, self.root)
                self.assertEqual(1, summary["level"])
                self.assertEqual(summary, json.loads(out.getvalue()))
                self.assertLess(len(out.getvalue()), 2200)
                self.assertEqual(summary["counts"], payload["counts"])
                self.assertEqual([], summary["diagnostics"]["sample_examples"])
                self.assertEqual(payload, reports.verify_report(self.root, run_id)["report"])
                full = (self.root / summary["full_evidence_path"]).read_bytes()
                self.assertEqual(hashlib.sha256(full).hexdigest(), summary["full_evidence_sha256"])

    def test_failure_keeps_every_issue_and_trace_even_with_success_status(self):
        tests = {"passed": 4, "failed": 1, "skipped": 1}
        issues = [{"severity": "error", "stage": "invariants", "test": f"test_{i}",
                   "code": f"E{i}", "message": "bad probability",
                   "traceback": "TRACE START\n" + "x" * 3000 + "\nTERMINAL"} for i in range(8)]
        summary = self.publish(fixture(tests=tests, issues=issues))
        self.assertEqual("success", summary["status"])
        self.assertEqual("failed", summary["validation_status"])
        diagnostics = summary["diagnostics"]
        self.assertEqual(3, len(diagnostics["issues"]))
        self.assertIn("TERMINAL", diagnostics["issues"][0]["traceback_tail"])
        self.assertEqual("test_0", diagnostics["issues"][0]["test"])
        self.assertEqual(issues, self.verify()["report"]["issues"])
        self.assertEqual(2, len(diagnostics["sample_examples"]))

    def test_subtle_matched_regression_with_green_kernel_and_valid_probabilities(self):
        comparison = {"baseline_id": "accepted-reference", "delta": 0.002,
                      "ci_low": 0.0002, "ci_high": 0.0038}
        summary = self.publish(fixture(comparisons={"paired_brier": comparison}))
        self.assertEqual(2, summary["level"])
        self.assertEqual("failed", summary["validation_status"])
        self.assertEqual(comparison, summary["diagnostics"]["comparisons"]["paired_brier"])

    def test_ci_straddling_threshold_does_not_invent_significance(self):
        summary = self.publish(fixture(comparisons={
            "paired_brier": {"baseline_id": "accepted-reference", "delta": 0.002,
                             "ci_low": -0.0002, "ci_high": 0.0038},
        }))
        self.assertEqual(1, summary["level"])

    def test_missing_provenance_and_counts_fail_closed(self):
        summary = self.publish(fixture(provenance={"input_sha256": "invalid"}, counts={}))
        self.assertEqual("blocked", summary["validation_status"])
        codes = {issue["code"] for issue in self.verify()["generated_issues"]}
        self.assertTrue({"INCOMPLETE_PROVENANCE", "INCOMPLETE_COUNTS"} <= codes)

    def test_invalid_probabilities_and_nonfinite_values_remain_recoverable(self):
        summary = self.publish(fixture(metrics={"brier": math.nan, "loss": math.inf},
                                       probabilities=[{"over": .4, "under": .5, "push": .0},
                                                      {"over": 1.2, "under": -.2, "push": .0}]))
        self.assertEqual("failed", summary["validation_status"])
        saved = self.verify()
        self.assertEqual({"brier": "NaN", "loss": "Infinity"}, saved["report"]["metrics"])
        self.assertEqual([["metrics", "brier"], ["metrics", "loss"]], saved["nonfinite_paths"])
        invalid = next(issue for issue in saved["generated_issues"]
                       if issue["code"] == "INVALID_PROBABILITY")
        self.assertEqual([0, 1], invalid["affected_indices"])

    def test_claimed_local_provenance_must_match_archived_content(self):
        payload = fixture()
        payload["provenance"]["input_uri"] = "artifact-" + "a" * 64
        result = self.publish(payload)
        self.assertEqual("blocked", result["validation_status"])
        self.assertIn("UNVERIFIED_PROVENANCE_ARTIFACT", result["diagnostics"]["issue_codes"])

    def test_stop_without_error_and_warning_on_success_escalate(self):
        summary = self.publish(fixture(status="stopped"))
        self.assertTrue(summary["diagnostics"]["diagnostic_gap"])
        warning = self.publish(fixture(run_id="warning", issues=[{"code": "DRIFT",
                                                                 "severity": "warning"}]))
        self.assertEqual(2, warning["level"])
        self.assertEqual("warning", warning["validation_status"])

    def test_artifact_copy_hash_verification_and_failed_recovery(self):
        source = self.root / "original"
        source.write_bytes(b"\x00\xff\n" * 999)
        summary = self.publish(artifacts={"predictive_draws": source})
        source.unlink()
        saved = self.verify()
        descriptor = saved["artifacts"]["predictive_draws"]
        self.assertEqual(b"\x00\xff\n" * 999, (self.root / descriptor["path"]).read_bytes())
        (self.root / descriptor["path"]).write_bytes(b"truncated")
        with self.assertRaisesRegex(reports.EvidenceError, "artifact"):
            self.verify()
        self.assertEqual(1, summary["artifact_count"])

    def test_missing_source_artifact_is_reported_and_remaining_evidence_is_preserved(self):
        summary = self.publish(artifacts={"predictive_draws": self.root / "missing"})
        self.assertEqual("blocked", summary["validation_status"])
        self.assertEqual("predictive_draws", self.verify()["missing_artifacts"][0]["name"])

    def test_summary_failure_leaves_complete_evidence_and_retry_can_recover(self):
        original_write = reports._publish_bytes

        def abort_summary(path, data):
            if path.name.endswith(".summary.json"):
                raise OSError("simulated failure")
            return original_write(path, data)

        with patch.object(reports, "_publish_bytes", side_effect=abort_summary):
            with self.assertRaisesRegex(OSError, "simulated"):
                self.publish()
        with self.assertRaisesRegex(reports.EvidenceError, "missing summary"):
            self.verify()
        self.assertEqual(1, len(list(self.root.glob("*.full.json"))))
        with self.assertRaisesRegex(reports.EvidenceError, "collision"):
            self.publish(fixture(metrics={"brier": .91}))
        full = next(self.root.glob("*.full.json"))
        sha256 = hashlib.sha256(full.read_bytes()).hexdigest()
        with self.assertRaisesRegex(reports.EvidenceError, "digest"):
            reports.recover_summary(self.root, "report-001", expected_sha256="0" * 64)
        reports.recover_summary(self.root, "report-001", expected_sha256=sha256)
        self.publish()
        self.verify()

    def test_truncated_and_modified_report_detected_without_reexecution(self):
        summary = self.publish()
        path = self.root / summary["summary_path"]
        original = path.read_bytes()
        path.write_bytes(original[:70])
        with self.assertRaisesRegex(reports.EvidenceError, "summary"):
            self.verify()
        path.write_text(json.dumps({**summary, "level": 2}))
        with self.assertRaisesRegex(reports.EvidenceError, "summary"):
            self.verify()
        path.write_bytes(original)
        with self.assertRaisesRegex(reports.EvidenceError, "digest"):
            self.verify(expected_sha256="0" * 64)
        (self.root / summary["full_evidence_path"]).write_bytes(b"{}\n")
        with self.assertRaisesRegex(reports.EvidenceError, "digest"):
            self.verify()

    def test_exclusive_create_preserves_evidence_on_linkless_mount(self):
        unsupported = OSError(errno.EOPNOTSUPP, "hard links unavailable")
        with patch.object(reports.os, "link", side_effect=unsupported):
            first = self.publish()
            self.verify()
            self.assertEqual(first, self.publish())
            with self.assertRaisesRegex(reports.EvidenceError, "collision"):
                self.publish(fixture(market="rebounds"))

    def test_interrupted_exclusive_create_cannot_appear_as_a_published_report(self):
        unsupported = OSError(errno.EOPNOTSUPP, "hard links unavailable")

        def interrupt(source, target, **kwargs):
            target.write(source.read(32))
            raise OSError("interrupted copy")

        with patch.object(reports.os, "link", side_effect=unsupported):
            with patch.object(reports.shutil, "copyfileobj", side_effect=interrupt):
                with self.assertRaisesRegex(OSError, "interrupted"):
                    self.publish()
            self.assertFalse((self.root / "report-001.summary.json").exists())
            with self.assertRaisesRegex(reports.EvidenceError, "collision"):
                self.publish()
            with self.assertRaisesRegex(reports.EvidenceError, "full evidence"):
                reports.recover_summary(self.root, "report-001", expected_sha256="0" * 64)

    def test_simultaneous_writers_cannot_overwrite_or_publish_conflicting_reports(self):
        def attempt(index):
            try:
                return self.publish(fixture(metrics={"brier": .19 + index / 100}))
            except reports.EvidenceError:
                return None

        with ThreadPoolExecutor(max_workers=6) as executor:
            summaries = list(executor.map(attempt, range(6)))
        self.assertEqual(1, sum(summary is not None for summary in summaries))
        self.assertEqual(1, len(list(self.root.glob("*.full.json"))))
        self.assertEqual(1, len(list(self.root.glob("*.summary.json"))))
        self.verify()

    def test_summary_remains_bounded_when_diagnostics_and_metrics_are_large(self):
        payload = fixture(metrics={f"metric_{i}": "🐍" * 3000 for i in range(80)},
                          issues=[{"code": "X", "message": "🐍" * 3000, "severity": "error"}] * 10)
        summary = self.publish(payload, max_issues=100, max_samples=100)
        self.assertLessEqual((self.root / summary["summary_path"]).stat().st_size,
                             reports.MAX_SUMMARY_BYTES)
        self.assertTrue(summary["diagnostics"]["omitted_issue_count"])
        self.assertEqual(payload["metrics"], self.verify()["report"]["metrics"])

    def test_bad_paths_fail_and_repeated_run_is_idempotent(self):
        for value in ("../escape", ".", ".."):
            with self.assertRaises(ValueError):
                self.publish(fixture(run_id=value))
        first = self.publish()
        self.assertEqual(first, self.publish())
        with self.assertRaisesRegex(reports.EvidenceError, "collision"):
            self.publish(fixture(status="stopped"))
        with self.assertRaisesRegex(reports.EvidenceError, "execution identity"):
            self.verify(expected_deepnote_run_id="wrong")

    def test_correlation_without_runtime_id_requires_verified_controller_binding(self):
        summary = self.publish(fixture(deepnote_run_id=None))
        self.assertIsNone(summary["deepnote_run_id"])
        with self.assertRaisesRegex(reports.EvidenceError, "execution identity"):
            self.verify(expected_deepnote_run_id="real-run")
        receipt = reports.bind_run(self.root, "report-001", "notebook-001", "real-run")
        self.assertEqual(receipt["full_evidence_sha256"], summary["full_evidence_sha256"])
        self.verify(expected_deepnote_run_id="real-run")
        with self.assertRaisesRegex(reports.EvidenceError, "collision"):
            reports.bind_run(self.root, "report-001", "notebook-001", "wrong")


if __name__ == "__main__":
    unittest.main()
