import copy
import json
from pathlib import Path
import tempfile
import unittest
from research.ws6_nfl_sunday_20261115 import weather_append_only_v1 as audit


class WeatherFreezeTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'observation_index': i, 'original_candidate_id': str(i),
                      'probabilities': [0.3, 0.2, 0.5], 'abstention': i == 1}
                     for i in range(3)]
        self.raw = b''.join(map(audit.encode, self.rows))
        self.digest = audit.sha(self.raw)
        self.patches = [audit.overlay(i, self.digest) for i in range(3)]

    def materialize(self, raw=None, patches=None):
        return audit.materialize(self.raw if raw is None else raw,
                                 self.patches if patches is None else patches,
                                 self.digest, 3, None)

    def test_all_fields_abstentions_and_inputs_preserved(self):
        before = copy.deepcopy(self.patches)
        result = self.materialize()
        for old, new in zip(self.rows, result):
            self.assertEqual(old, {k: v for k, v in new.items() if k != 'weather_audit_v1'})
        self.assertEqual(before, self.patches)

    def test_parent_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError, 'PARENT_SHA'):
            self.materialize(raw=self.raw + b' ')

    def test_reordered_or_missing_reference_rejected(self):
        for patches in [self.patches[::-1], self.patches[:-1], self.patches + self.patches[:1]]:
            with self.subTest(patches=patches), self.assertRaises(ValueError):
                self.materialize(patches=patches)

    def test_forecast_injection_rejected(self):
        patches = copy.deepcopy(self.patches)
        patches[0]['weather_audit_v1']['weather_forecasts'] = {'p_over': 0.7}
        with self.assertRaisesRegex(ValueError, 'INVALID_OR_REORDERED'):
            self.materialize(patches=patches)

    def test_wrong_parent_reference_rejected(self):
        patches = copy.deepcopy(self.patches)
        patches[0]['parent_ledger_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.materialize(patches=patches)

    def test_missing_forecasts_never_zero_delta_or_fake_fallback(self):
        for row in self.materialize():
            audit_row = row['weather_audit_v1']
            self.assertIsNone(audit_row['distribution_changes'])
            self.assertIsNone(audit_row['unchanged_fallback_forecasts'])
            self.assertEqual(audit_row['matched_weather_pairs'], 0)

    def test_strict_json(self):
        for raw in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.assertRaises(ValueError):
                audit.parse(raw)

    def test_immutable_freeze_and_full_original_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'freeze'
            hashes = audit.freeze(target, {'status': 'blocked'})
            lines = (target / 'comparison_reference_ledger_1845.jsonl').read_bytes().splitlines()
            self.assertEqual(len(lines), 1845)
            for name, digest in hashes.items():
                self.assertEqual(audit.sha((target / name).read_bytes()), digest)
            with self.assertRaises(FileExistsError):
                audit.freeze(target, {'status': 'blocked'})


if __name__ == '__main__':
    unittest.main()
