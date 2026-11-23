"""Offline adversarial tests for the opt-in Deepnote diagnostic reporting helper."""
import contextlib
import hashlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from scripts.deepnote_diagnostic_report import publish_report


def fixture(**overrides):
    report = {
        "run_id": "run-test-001",
        "notebook_id": "notebook-test",
        "status": "success",
        "sport": "NBA",
        "market": "points",
        "model": "S-family",
        "git_sha": "f" * 40,
        "tests": {"passed": 12, "failed": 0, "skipped": 1},
        "counts": {"source_rows": 200, "rejected": 7, "unmatched": 3},
        "metrics": {"brier": 0.19, "bias_over": -0.02},
        "provenance": {"input_sha256": "a" * 64, "source_time": "2026-11-23T20:00:00Z"},
        "issues": [],
        "samples": [{"row": i} for i in range(100)],
        "verbose_log": "debug line\n" * 5000,
    }
    report.update(overrides)
    return report


class ReportTests(unittest.TestCase):
    def test_success_is_small_but_full_evidence_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                summary = publish_report(fixture(), folder)
            self.assertEqual(1, len(output.getvalue().splitlines()))
            self.assertLess(len(output.getvalue()), 2200)
            self.assertEqual([], summary["sample_examples"])
            self.assertEqual(100, summary["omitted_sample_count"])
            self.assertEqual(7, summary["counts"]["rejected"])
            self.assertEqual(3, summary["counts"]["unmatched"])
            full_path = Path(summary["full_evidence_path"])
            raw = full_path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), summary["full_evidence_sha256"])
            self.assertEqual(5000, json.loads(raw)["verbose_log"].count("debug line"))
            self.assertEqual("f" * 40, summary["git_sha"])

    def test_failure_gives_diagnosis_and_keeps_every_issue(self):
        failures = [
            {"code": f"E{i}", "message": "bad probability", "traceback": "x" * 3000 + "TERMINAL"}
            for i in range(8)
        ]
        with tempfile.TemporaryDirectory() as folder:
            report = fixture(status="error", tests={"passed": 2, "failed": 1, "skipped": 0},
                             issues=failures)
            summary = publish_report(report, folder, emit_stdout=False)
            self.assertEqual(8, summary["issue_count"])
            self.assertEqual(3, len(summary["issues"]))
            self.assertEqual(5, summary["omitted_issue_count"])
            self.assertEqual(2, len(summary["sample_examples"]))
            self.assertIn("TERMINAL", summary["issues"][0]["traceback_tail"])
            saved = json.loads(Path(summary["full_evidence_path"]).read_text())
            self.assertEqual(8, len(saved["issues"]))
            self.assertEqual(100, len(saved["samples"]))
            self.assertEqual("error", summary["status"])

    def test_failed_checks_cannot_be_hidden_by_success(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                publish_report(fixture(tests={"passed": 1, "failed": 1, "skipped": 0}),
                               folder, emit_stdout=False)
            self.assertEqual([], list(Path(folder).glob("*.full.json")))

    def test_nan_fails_closed_instead_of_emitting_misleading_json(self):
        with tempfile.TemporaryDirectory() as folder:
            for bad in [math.nan, math.inf, -math.inf]:
                with self.assertRaises(ValueError):
                    publish_report(fixture(metrics={"brier": bad}), folder, emit_stdout=False)
            self.assertEqual([], list(Path(folder).glob("*.full.json")))

    def test_missing_diagnostics_are_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            summary = publish_report(fixture(status="blocked"), folder, emit_stdout=False)
            self.assertTrue(summary["diagnostic_gap"])

    def test_repeated_run_is_idempotent_and_versions_are_append_only(self):
        with tempfile.TemporaryDirectory() as folder:
            original = fixture()
            a = publish_report(original, folder, emit_stdout=False)
            b = publish_report(original, folder, emit_stdout=False)
            self.assertEqual(a["full_evidence_sha256"], b["full_evidence_sha256"])
            newer = publish_report(fixture(metrics={"brier": 0.25}), folder, emit_stdout=False)
            self.assertNotEqual(a["full_evidence_path"], newer["full_evidence_path"])
            self.assertEqual(2, len(list(Path(folder).glob("*.full.json"))))
            self.assertEqual(0.19, json.loads(Path(a["full_evidence_path"]).read_text())["metrics"]["brier"])

    def test_path_traversal_and_wrong_shapes_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                publish_report(fixture(run_id="../escape"), folder, emit_stdout=False)
            with self.assertRaises(ValueError):
                publish_report(fixture(counts={"rejected": -1}), folder, emit_stdout=False)
            with self.assertRaises(ValueError):
                publish_report(fixture(issues=["not-an-object"]), folder, emit_stdout=False)

    def test_existing_evidence_cannot_be_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            summary = publish_report(fixture(), folder, emit_stdout=False)
            Path(summary["full_evidence_path"]).write_text("TAMPERED")
            with self.assertRaises(RuntimeError):
                publish_report(fixture(), folder, emit_stdout=False)
            self.assertEqual("TAMPERED", Path(summary["full_evidence_path"]).read_text())


if __name__ == "__main__":
    unittest.main()
