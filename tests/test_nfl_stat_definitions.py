import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import nfl_stat_definitions as definitions


class NFLSourceStatChallengerTests(unittest.TestCase):
    def test_combined_credits_match_population_definition_and_show_legacy_gap(self):
        row = dict(def_tackles_solo=4, def_tackles_with_assist=2, def_tackle_assists=1)
        result = definitions.reconcile(row, ("tackles + assists",))[0]
        self.assertEqual(result["value"], 7)
        self.assertEqual(result["legacy_source_formula_value"], 5)
        self.assertEqual(result["strict_minus_legacy"], 2)
        self.assertFalse(result["ranking_allowed"])
        self.assertFalse(result["forecast_generated"])
        self.assertFalse(result["settlement_written"])

    def test_all_tackle_components_required_and_real_zero_is_available(self):
        complete = dict(def_tackles_solo=0., def_tackles_with_assist=0., def_tackle_assists=0.)
        self.assertEqual(definitions.strict_source_stat(complete, "tackles + assists").value, 0)
        for key in complete:
            for bad in (None, True, "0", -1, .5, float("nan"), float("inf"), 201, 10**500):
                with self.subTest(key=key, bad=bad):
                    row = {**complete, key: bad}
                    value = definitions.strict_source_stat(row, "tackles + assists")
                    self.assertEqual(value.status, "unavailable")
                    self.assertIsNone(value.value)
            row = dict(complete)
            del row[key]
            self.assertEqual(definitions.strict_source_stat(row, "tackles + assists").status, "unavailable")

    def test_targets_null_missing_and_invalid_are_never_observed_zeros(self):
        for row in ({}, {"targets": None}, {"targets": "3"}, {"targets": True},
                    {"targets": -1}, {"targets": 2.5}, {"targets": float("nan")},
                    {"targets": float("inf")}):
            with self.subTest(row=row):
                result = definitions.strict_source_stat(row, "targets")
                self.assertIsNone(result.value)
                self.assertEqual(result.status, "unavailable")
        self.assertEqual(definitions.strict_source_stat({"targets": 0}, "targets").value, 0)
        self.assertEqual(definitions.strict_source_stat({"targets": 7.}, "targets").value, 7)

    def test_no_input_mutation_and_ambiguous_market_not_guessed(self):
        row = {"targets": 3, "player_id": "x", "nested": {"original": True}}
        original = copy.deepcopy(row)
        definitions.reconcile(row, ("targets",))
        self.assertEqual(row, original)
        with self.assertRaises(ValueError):
            definitions.strict_source_stat(row, "tackles")

    def test_reconciliation_preserves_source_and_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "raw.jsonl"
            destination = Path(folder) / "audit.jsonl"
            original = '{"targets":null,"player_id":"x"}\n'
            source.write_text(original)
            result = definitions.reconcile_file(source, destination, stats=("targets",))
            self.assertEqual(source.read_text(), original)
            self.assertEqual(result["statuses"], {"unavailable": 1})
            item = json.loads(destination.read_text())
            self.assertIsNone(item["value"])
            self.assertEqual(item["legacy_source_formula_value"], 0)
            self.assertEqual(item["source_line"], 1)
            before = destination.read_bytes()
            with self.assertRaises(FileExistsError):
                definitions.reconcile_file(source, destination)
            self.assertEqual(destination.read_bytes(), before)
            with self.assertRaises(ValueError):
                definitions.reconcile_file(source, source)
            self.assertEqual(source.read_text(), original)

    def test_malformed_input_cannot_leave_partial_diagnostic_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder) / "raw.jsonl", Path(folder) / "out.jsonl"
            for contents in ('{"targets":1}\nnot JSON\n', '{"targets": NaN}\n', '[]\n'):
                with self.subTest(contents=contents):
                    source.write_text(contents)
                    with self.assertRaises(ValueError):
                        definitions.reconcile_file(source, out)
                    self.assertFalse(out.exists())

    def test_cli_is_offline_and_outputs_only_diagnostic_counts(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder) / "raw.jsonl", Path(folder) / "out.jsonl"
            source.write_text('{"targets":4}\n')
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/nfl_stat_definitions.py"),
                "--input-jsonl", str(source), "--output-jsonl", str(out), "--stat", "targets",
            ], capture_output=True, text=True, check=True)
            receipt = json.loads(result.stdout)
            self.assertFalse(receipt["production_changed"])
            self.assertFalse(receipt["historical_records_changed"])
            self.assertEqual(receipt["diagnostic_rows"], 1)
            self.assertEqual(json.loads(out.read_text())["value"], 4)


if __name__ == "__main__":
    unittest.main()
