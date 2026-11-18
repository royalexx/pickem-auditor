"""Existing artifact controls, with no fitting or genuine-model claim."""
import json
import unittest
from pathlib import Path
from scripts.nba_p234_artifact_inspection_v1 import inspect_ws2, MODEL


class ExistingArtifactInspection(unittest.TestCase):
    def setUp(self):
        self.raw = Path(MODEL).read_bytes()

    def test_existing_conditional_artifact_is_not_absent_or_participation(self):
        r = inspect_ws2(self.raw)
        self.assertEqual(r['conditioning'], 'given_played')
        self.assertIsNone(r['genuine_participation_probability'])
        self.assertIn('MODEL_AFTER_DECLARED_CUTOFF', r['blockers'])
        self.assertEqual(r['training_rows_admitted'], 0)

    def test_cutoff_before_equal_after_never_confer_admission(self):
        for cutoff, late in [('2024-04-14T23:59:59Z', True),
                             ('2024-04-15T00:00:00Z', False),
                             ('2024-04-15T00:00:01Z', False)]:
            r = inspect_ws2(self.raw, declared_cutoff=cutoff)
            self.assertEqual('MODEL_AFTER_DECLARED_CUTOFF' in r['blockers'], late)
            self.assertEqual(r['status'], 'EXISTING_BUT_INADMISSIBLE')
            self.assertEqual(r['training_rows_admitted'], 0)

    def test_mutated_bytes_and_resealed_semantics_reject(self):
        for raw in [self.raw+b' ', b'{}', self.raw.replace(b'2024-04-15', b'2018-04-15')]:
            with self.assertRaisesRegex(ValueError, 'ALTERED_OR_UNREVIEWED'):
                inspect_ws2(raw)
        model = json.loads(self.raw)
        model['participation_probability'] = 1
        with self.assertRaisesRegex(ValueError, 'ALTERED_OR_UNREVIEWED'):
            inspect_ws2(json.dumps(model).encode())

    def test_naive_cutoff_rejects(self):
        with self.assertRaisesRegex(ValueError, 'TIMEZONE_REQUIRED'):
            inspect_ws2(self.raw, declared_cutoff='2024-04-15T00:00:00')
