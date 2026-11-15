"""Adversarial executable checks for WS6. All data in this file are TEST FIXTURES."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nfl_sunday_ws6_audit as audit

def enc(v):
    return (json.dumps(v, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


class Workstream6AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "raw").mkdir()
        self.raw = b"ORIGINAL_FAKE_PROVIDER_BYTES_FOR_UNIT_TEST_ONLY"
        (self.root / "raw/provider.txt").write_bytes(self.raw)
        self.q = {
            "quote_id": "quote1", "contract_id": "contract1", "event_id": "event1",
            "event_start_at": "2026-11-15T18:00:00Z", "player_id": "player1",
            "stat_key": "targets", "period": "full_game", "line": 5.0,
            "book": "book1", "product_type": "sportsbook_two_sided",
            "quote_kind": "real", "accepted": True, "settlement_policy": "strict_gt_lt_equal_push",
            "source_available_at": "2026-11-15T15:00:00Z",
            "captured_at": "2026-11-15T15:01:00Z",
            "quote_at": "2026-11-15T15:00:00Z",
            "source_archive_path": "raw/provider.txt",
            "source_sha256": hashlib.sha256(self.raw).hexdigest(),
            "source_kind": "provider_publication", "player_eligible_pregame": True,
            "over_decimal_odds": 1.91, "under_decimal_odds": 1.91
        }
        self.m = {
            "schema": audit.EXPECTED_SCHEMA, "slate_date": audit.SLATE,
            "schedule_complete": True, "events": [{
                "event_id": "event1", "start_at": "2026-11-15T18:00:00Z",
                "home_id": "home", "away_id": "away"}],
            "expected_contract_count": 1, "expected_models": ["challenger2"]
        }
        self.f = dict((k, self.q[k]) for k in
                      ("quote_id", "contract_id", "event_id", "player_id",
                       "stat_key", "period", "line", "book", "product_type"))
        self.f.update({
            "model_id": "challenger2", "model_version": "2.0", "model_code_commit": "a"*40,
            "model_artifact_sha256": "b"*64,
            "forecast_at": "2026-11-15T15:04:00Z",
            "input_freeze_at": "2026-11-15T15:03:00Z",
            "model_training_cutoff_at": "2026-11-14T12:00:00Z",
            "forecast_attested_at": "2026-11-15T15:05:00Z",
            "q_over": 0.4, "q_under": 0.4, "q_push": 0.2,
            "distribution": {"kind": "discrete",
                             "masses": [[4.0, 0.4], [5.0, 0.2], [6.0, 0.4]]},
            "selected": True, "selected_side": "over"
        })
        self.prepare()

    def prepare(self):
        (self.root / "quotes.jsonl").write_bytes(enc(self.q))
        self.m["quotes_sha256"] = audit.file_sha(self.root / "quotes.jsonl")
        (self.root / "manifest.json").write_bytes(enc(self.m))
        self.f["input_manifest_sha256"] = audit.file_sha(self.root / "manifest.json")
        (self.root / "f.jsonl").write_bytes(enc(self.f))

    def freeze(self, name="frozen", *, forecasts=True):
        return audit.main(["freeze", "--root", str(self.root),
                           "--manifest", "manifest.json", "--quotes", "quotes.jsonl",
                           "--forecasts"] + (["f.jsonl"] if forecasts else []) +
                          ["--output", str(self.root / name)])

    def settled(self, status="official_final", actual=5):
        raw = b"FAKE_OFFICIAL_FINAL_BYTES_UNIT_TEST_ONLY"
        (self.root / "raw/official.txt").write_bytes(raw)
        o = {"event_id": "event1", "player_id": "player1", "stat_key": "targets",
             "period": "full_game", "status": status, "actual_stat": actual,
             "official_provider": "nfl_gsis",
             "official_source_path": "raw/official.txt",
             "official_source_sha256": hashlib.sha256(raw).hexdigest(),
             "event_start_at": "2026-11-15T18:00:00Z",
             "official_final_at": "2026-11-15T21:30:00Z",
             "official_retrieved_at": "2026-11-15T22:00:00Z"}
        (self.root / "official.jsonl").write_bytes(enc(o))
        return audit.main(["score", "--root", str(self.root),
                           "--frozen", str(self.root / "frozen"),
                           "--outcomes", "official.jsonl",
                           "--output", str(self.root / "settlement")])

    def test_valid_fixture_is_only_structural_not_certified(self):
        self.assertEqual(self.freeze(), 0)
        report = audit.load_json(self.root / "frozen/integrity_report.json")
        self.assertEqual(report["accepted_original_contracts"], 1)
        self.assertEqual(report["forecast_rows_valid_structure"], 1)
        self.assertEqual(report["comparison_status"], "UNVERIFIED_SHADOW_ONLY")

    def test_mandatory_original_quote_hash(self):
        self.m["quotes_sha256"] = "0"*64
        (self.root / "manifest.json").write_bytes(enc(self.m))
        self.assertEqual(self.freeze(), 2)
        self.assertFalse((self.root / "frozen").exists())

    def test_tampered_source_bytes_rejects_quote(self):
        (self.root / "raw/provider.txt").write_bytes(b"TAMPERED")
        self.assertEqual(self.freeze(), 2)
        report = audit.load_json(self.root / "frozen/integrity_report.json")
        self.assertEqual(report["accepted_original_contracts"], 0)

    def test_post_kickoff_forecast_rejected(self):
        self.f["forecast_attested_at"] = "2026-11-15T19:00:00Z"
        self.prepare()
        self.assertEqual(self.freeze(), 2)
        self.assertEqual(audit.load_json(self.root / "frozen/integrity_report.json")["forecast_rejections"], 1)

    def test_naive_source_timestamp_rejected(self):
        self.q["source_available_at"] = "2026-11-15T15:00:00"
        self.prepare()
        self.assertEqual(self.freeze(), 2)

    def test_unconfirmed_player_not_eligible(self):
        self.q["player_eligible_pregame"] = False
        self.prepare()
        self.assertEqual(self.freeze(), 2)

    def test_probabilities_must_normalize(self):
        self.f["q_under"] = 0.5
        self.prepare()
        self.assertEqual(self.freeze(), 2)

    def test_distribution_line_mismatch_rejected(self):
        self.f["q_push"] = 0.0
        self.f["q_under"] = 0.6
        self.prepare()
        self.assertEqual(self.freeze(), 2)

    def test_duplicate_forecast_identity_rejected(self):
        self.prepare()
        with (self.root / "f.jsonl").open("ab") as out:
            out.write(enc(self.f))
        self.assertEqual(self.freeze(), 2)
        self.assertEqual(audit.load_json(self.root / "frozen/integrity_report.json")["forecast_rejections"], 1)

    def test_forecast_contract_mismatch_rejected(self):
        self.f["line"] = 6
        self.prepare()
        self.assertEqual(self.freeze(), 2)

    def test_no_retroactive_overwrite_of_frozen_record(self):
        self.assertEqual(self.freeze(), 0)
        self.assertEqual(self.freeze(), 2)
        self.assertEqual(audit.file_sha(self.root / "frozen/comparison_ledger.jsonl"),
                         audit.load_json(self.root / "frozen/freeze_index.json")["comparison_ledger_sha256"])

    def test_push_scores_three_way_not_binary(self):
        self.assertEqual(self.freeze(), 0)
        self.assertEqual(self.settled(actual=5), 0)
        s = audit.load_json(self.root / "settlement/score_report.json")
        m = s["model_metrics"]["challenger2"]
        self.assertEqual(m["binary_nonpush_count"], 0)
        self.assertAlmostEqual(m["multiclass_brier_half"], 0.48)
        self.assertAlmostEqual(m["crps_mean"], 0.32)

    def test_over_and_under_share_one_contract(self):
        self.assertEqual(self.freeze(), 0)
        self.assertEqual(self.settled(actual=6), 0)
        s = audit.load_json(self.root / "settlement/score_report.json")
        self.assertEqual(s["original_contracts"], 1)
        self.assertEqual(s["model_metrics"]["challenger2"]["count"], 1)

    def test_unfinished_outcomes_never_scored(self):
        self.assertEqual(self.freeze(), 0)
        self.assertEqual(self.settled(status="dnp"), 0)
        s = audit.load_json(self.root / "settlement/score_report.json")
        self.assertEqual(s["model_metrics"], {})
        self.assertEqual(s["settled_over_under_push"], {"dnp": 1})

    def test_source_official_tamper_fails_closed(self):
        self.assertEqual(self.freeze(), 0)
        self.assertEqual(self.settled(actual=6), 0)
        frozen_ledger = self.root / "frozen/comparison_ledger.jsonl"
        frozen_ledger.write_text(frozen_ledger.read_text() + "\n")
        self.assertEqual(audit.main(["score", "--root", str(self.root),
                                     "--frozen", str(self.root / "frozen"),
                                     "--outcomes", "official.jsonl",
                                     "--output", str(self.root / "new")]), 2)

    def test_crps_one_atom(self):
        self.assertEqual(audit.crps_discrete({"kind": "discrete", "masses": [[7, 1]]}, 5), 2)

    def test_market_baseline_conditional_nonpush(self):
        self.assertEqual(self.freeze(), 0)
        self.assertEqual(self.settled(actual=6), 0)
        s = audit.load_json(self.root / "settlement/score_report.json")
        self.assertEqual(s["model_metrics"]["market_no_vig"]["binary_nonpush_count"], 1)
        self.assertIsNone(s["model_metrics"]["market_no_vig"]["multiclass_brier_half"])
        self.assertEqual(s["matched_paired_game_clusters"]["challenger2__vs_market_no_vig"]["paired_n"], 1)

    def test_all_events_must_be_represented(self):
        self.m["events"].append({"event_id": "event2", "start_at": "2026-11-15T20:00:00Z",
                                 "home_id": "team3", "away_id": "team4"})
        self.prepare()
        self.assertEqual(self.freeze(), 2)
        self.assertFalse(audit.load_json(self.root / "frozen/integrity_report.json")[
            "all_scheduled_events_represented_by_original_contract"])

    def test_integer_line_market_never_invents_push(self):
        self.assertEqual(self.freeze(), 0)
        self.assertEqual(self.settled(actual=5), 0)
        s = audit.load_json(self.root / "settlement/score_report.json")
        self.assertEqual(s["model_metrics"].get("market_no_vig"), None)
        self.assertEqual(s["model_metrics"]["challenger2"]["three_way_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
