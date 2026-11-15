"""Negative controls for the native feature audit; never forecast evidence."""
import tempfile
from pathlib import Path
import unittest
from .feature_handoff_audit import bound, contract_reasons
from .models import GateError, sha


class FeatureAuditTests(unittest.TestCase):
    def test_corruption_and_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)/'root'
            root.mkdir()
            p = root/'source'
            p.write_bytes(b'original')
            self.assertEqual(bound(root, 'source', sha(b'original')), p)
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(GateError, 'hash_mismatch'):
                bound(root, 'source', sha(b'original'))
            (Path(d)/'outside').write_bytes(b'original')
            with self.assertRaisesRegex(GateError, 'source_path_escape'):
                bound(root, '../outside', sha(b'original'))

    def test_expired_game_retained_with_original_rejects(self):
        c = {'abstention_reasons': ['ORIGINAL_ID_REJECT'],
             'status': {'SOURCE_IDENTITY_CERTIFIED': False},
             'product_terms': 'PRODUCT_SPECIFIC_RULES_UNVERIFIED'}
        reasons = contract_reasons(c, {'participation_probability': None}, False)
        self.assertIn('KICKOFF_PASSED', reasons)
        self.assertIn('ORIGINAL_ID_REJECT', reasons)
        self.assertIn('MISSING_PARTICIPATION_PROBABILITY', reasons)
        self.assertIn('WS1_QUOTE_NOT_SOURCE_CERTIFIED', reasons)
        self.assertIn('PRODUCT_SPECIFIC_DNP_AND_SETTLEMENT_RULES_UNVERIFIED', reasons)

    def test_valid_numeric_zero_is_not_missing_or_imputed(self):
        c = {'status': {'SOURCE_IDENTITY_CERTIFIED': True}, 'product_terms': 'verified'}
        self.assertEqual(contract_reasons(c, {'participation_probability': 0.0}, True), [])
        self.assertEqual(contract_reasons(c, {}, True), ['MISSING_PARTICIPATION_PROBABILITY'])


if __name__ == '__main__':
    unittest.main()
