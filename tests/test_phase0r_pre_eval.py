"""Phase 0R strict input binding: actual frozen evaluation, not post-hoc receipts."""
import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import jobs
import phase0_pre_eval
from phase0_preflight import audit
from phase0r_contract import strict_snapshot_status
from point_in_time_provenance import pregame_snapshot_status
from usage_baseline import key as usage_key, directory

START = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)


def make_inputs(root):
    root.mkdir(parents=True, exist_ok=True)
    ident = usage_key("NFL", "pid-1", "receptions", "2026-11-09")
    usage = root / "usage"
    usage.mkdir()
    (usage / (ident + ".json")).write_text(json.dumps({
        "sport": "NFL", "player_id": "pid-1", "stat": "receptions",
        "game_date": "2026-11-09", "retrieved_at": "2026-11-09T14:00:00Z",
        "source_url": "https://example.org/source",
        "observations": [{"id": "old-game", "date": "2026-11-02", "value": 5}],
    }))
    (root / "odds_quotes.jsonl").write_text(json.dumps({
        "book": "ExampleBook", "line": 4.5,
        "over_odds": -110, "under_odds": -110,
        "retrieved_at": "2026-11-09T14:10:00Z"}) + "\n")
    (root / "research_2026-11-09.json").write_text(
        '{"date":"2026-11-09","source":"original"}')
    candidate = {
        "id": "NFL|Example Player|receptions|over", "sport": "NFL",
        "stat": "receptions", "player_id": "pid-1", "team": "BUF",
        "game_date": "2026-11-09", "event_id": "event-1",
        "line": 4.5, "side": "over",
        "books": [{"book": "ExampleBook", "line": 4.5,
                   "book_side": "over", "target": -110, "other": -110}],
        "market_retrieved_at": "2026-11-09T14:10:00Z",
        "scouting": {"historical_usage": ident},
    }
    return candidate, ident


def build_row(candidate, evidence):
    freeze = evidence["input_freeze_at"]
    return {
        **evidence, "run_id": "original-run", "game_date": "2026-11-09",
        "event_start": "2026-11-09T18:00:00Z",
        "forecast_at": "2026-11-09T15:01:00Z",
        "model_evaluation_started_at": freeze,
        "model_fit_receipts": [
            {"component": "Engine_A", "fit_mode": "on_demand",
             "training_data_cutoff_at": freeze},
            {"component": "Engine_B", "fit_mode": "rule_based",
             "training_data_cutoff_at": freeze},
        ],
        "sport": "NFL", "player_id": "pid-1", "event_id": "event-1",
        "stat": "receptions", "side": "over", "reference_line": 4.5,
        "inputs": candidate, "engine_b": {"abstain": False},
        "market": {
            "market_valid": True, "line": 4.5,
            "retrieved_at": "2026-11-09T14:10:00Z",
            "books": [{"book": "ExampleBook", "line": 4.5,
                       "retrieved_at": "2026-11-09T14:10:00Z"}],
        },
        "blend": {"production_policy": False},
    }


class Phase0RPreEvalTests(unittest.TestCase):
    def test_immutable_copy_is_consumed_after_capture_not_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "collected"
            candidate, ident = make_inputs(original)
            times = iter([START, START + timedelta(seconds=2)])
            with phase0_pre_eval.pin(candidate, data_root=original,
                    archive_root=original / "source_archives",
                    policy_root=root / "policy", clock=lambda: next(times)) as (evidence, frozen, actual):
                self.assertEqual(actual, candidate)
                self.assertEqual(evidence["input_freeze_at"],
                                 "2026-11-09T15:00:02Z")
                self.assertTrue((frozen / "usage" / (ident + ".json")).is_file())
                immutable = (frozen / "usage" / (ident + ".json")).read_bytes()
                (original / "usage" / (ident + ".json")).write_text("MUTATED")
                self.assertEqual(
                    (frozen / "usage" / (ident + ".json")).read_bytes(), immutable)
                self.assertEqual(phase0_pre_eval.canonical_bytes(actual),
                                 (frozen / "model_input_candidate.json").read_bytes())
                row = build_row(candidate, evidence)
                self.assertEqual(strict_snapshot_status(
                    row, archive_root=original / "source_archives")[0], True)

    def test_strict_checker_catches_post_snapshot_tampering_and_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = root / "collected"
            candidate, _ = make_inputs(original)
            with phase0_pre_eval.pin(candidate, data_root=original,
                    archive_root=original / "source_archives", policy_root=root,
                    clock=lambda: START) as (evidence, _frozen, actual):
                row = build_row(actual, evidence)
                archive = original / "source_archives"
                self.assertTrue(strict_snapshot_status(row, archive_root=archive)[0])
                source = dict(row)
                source.pop("model_input_binding")
                self.assertTrue(pregame_snapshot_status(source, archive_root=archive)[0])
                self.assertEqual(strict_snapshot_status(source, archive_root=archive)[1],
                                 "pre_eval_input_binding_missing")
                altered = dict(row)
                altered["inputs"] = {**actual, "line": 5.5}
                self.assertEqual(strict_snapshot_status(altered, archive_root=archive)[1],
                                 "frozen_numerical_candidate_digest_mismatch")
                altered = dict(row)
                altered["model_fit_receipts"] = [
                    {**row["model_fit_receipts"][0],
                     "training_data_cutoff_at": "2026-11-09T15:02:00Z"},
                    row["model_fit_receipts"][1],
                ]
                self.assertEqual(strict_snapshot_status(altered, archive_root=archive)[1],
                                 "model_fit_cutoff_inconsistent")
                target = archive / evidence["source_receipts"][0]["archive_path"]
                target.write_bytes(b"tampered")
                self.assertEqual(strict_snapshot_status(row, archive_root=archive)[1],
                                 "source_archive_digest_mismatch")

    def test_batch_audit_defaults_to_strict_not_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            candidate, _ = make_inputs(data)
            with phase0_pre_eval.pin(candidate, data_root=data,
                    archive_root=data / "source_archives", policy_root=root,
                    clock=lambda: START) as (evidence, _frozen, actual):
                row = build_row(actual, evidence)
            path = root / "original_forecasts.jsonl"
            path.write_text(json.dumps(row) + "\n")
            report = audit(path, slate_date="2026-11-09",
                           archive_root=data / "source_archives")
            self.assertEqual(report["certified_rows"], 1)
            self.assertEqual(report["metadata_verified_rows"], 1)
            no_binding = dict(row)
            no_binding.pop("model_input_binding")
            path.write_text(json.dumps(no_binding) + "\n")
            legacy = audit(path, slate_date="2026-11-09",
                           archive_root=data / "source_archives")
            self.assertEqual(legacy["metadata_verified_rows"], 1)
            self.assertEqual(legacy["certified_rows"], 0)
            self.assertEqual(legacy["uncertified_reasons"],
                             {"pre_eval_input_binding_missing": 1})

    def test_actual_job_evaluator_receives_frozen_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "collected"
            candidate, ident = make_inputs(data)
            meta = {
                "sport": "NFL", "stat": "receptions", "player_id": "pid-1",
                "player": "Example Player", "game_date": "2026-11-09",
                "event_id": "event-1", "team": "BUF", "opponent": "KC",
                "event_start": "2026-11-09T18:00:00Z", "matchup": "KC @ BUF"
            }
            values = [START + timedelta(seconds=n) for n in range(4)]
            clocks = iter(values)
            recorded = []
            def model(actual, *, now):
                loaded = json.loads((directory() / (ident + ".json")).read_text())
                self.assertEqual(loaded["source_url"], "https://example.org/source")
                self.assertNotEqual(directory().parent.resolve(), data.resolve())
                self.assertEqual(actual, candidate)
                self.assertGreaterEqual(now, START)
                recorded.append(str(directory()))
                return {
                    "ok": True, "id": candidate["id"], "final_rank": "Unranked",
                    "engine_b": {"abstain": True}, "consensus": {
                        "market_valid": True, "line": 4.5},
                    "market": {"q_market": 0.5}, "blend": {},
                }
            with patch.dict(os.environ, {"PICKEM_PHASE0_CAPTURE": "1"}), (
                patch.object(jobs.pm, "evaluate_candidate", side_effect=model)
            ):
                rows, errors = jobs.run_pipeline_batch([
                    {**candidate, "_meta": meta, "_run_id": "original-run",
                     "_run_at": "2026-11-09 10:00 ET"}
                ], now=START, data_root=data,
                    clock_fn=lambda: next(clocks))
            self.assertEqual(errors, 0)
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(recorded), 1)
            self.assertTrue(rows[0]["model_input_binding"])
            self.assertTrue(strict_snapshot_status(
                rows[0], archive_root=data / "source_archives")[0])

    def test_unavailable_source_fails_closed_without_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "collected"
            candidate, ident = make_inputs(data)
            (data / "usage" / (ident + ".json")).unlink()
            with self.assertRaises(FileNotFoundError):
                with phase0_pre_eval.pin(candidate, data_root=data,
                        archive_root=data / "source_archives", policy_root=root,
                        clock=lambda: START):
                    self.fail("should not evaluate without original source")


if __name__ == "__main__":
    unittest.main()
