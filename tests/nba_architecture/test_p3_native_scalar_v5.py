"""Permanent typed native-source denominator/state controls, synthetic only."""
import base64
import hashlib
import json
import unittest

from test_p3_p1_native_v4 import native_fixture
from v2.nba_architecture.v2_contracts import canonical, ContractError
from v2.nba_o_p1_native import consume_p1_context


def eligibility_fixture(value):
    p, export = native_fixture()
    source = export['sources'][0]
    doc = json.loads(base64.b64decode(source['raw_base64']))
    doc['assertions'][0]['legal_eligibility'] = value
    raw = canonical(doc)
    source['raw_base64'] = base64.b64encode(raw).decode()
    source['raw_sha256'] = hashlib.sha256(raw).hexdigest()
    export['players'][0]['availability_evidence']['raw_sha256'] = source['raw_sha256']
    export['players'][0]['legal_eligibility'] = value
    return p, export


class NativeScalarControls(unittest.TestCase):
    def test_exact_nonnegative_integer_count_positive(self):
        p, export = native_fixture()
        result = consume_p1_context(export, frozen_pregame=p)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['p1_export']['candidate_denominator'],
                         dict(observed_candidates=1, admitted=0, complete_population=None))
        self.assertIs(type(result['p1_export']['candidate_denominator']['observed_candidates']), int)
        self.assertIs(type(result['p1_export']['candidate_denominator']['admitted']), int)

    def test_bool_float_and_invalid_count_types_rejected(self):
        cases = [('observed_candidates', True), ('observed_candidates', 1.0),
                 ('observed_candidates', -1), ('observed_candidates', '1'),
                 ('admitted', False), ('admitted', 0.0), ('admitted', -1),
                 ('admitted', '0'), ('complete_population', 0),
                 ('complete_population', False)]
        for key, value in cases:
            with self.subTest(key=key, value=value, type=type(value).__name__):
                p, export = native_fixture()
                export['candidate_denominator'][key] = value
                with self.assertRaises(ContractError):
                    consume_p1_context(export, frozen_pregame=p)

    def test_count_shape_rejects_missing_extra_and_nonobject(self):
        for shape in ({'observed_candidates': 1, 'admitted': 0},
                      {'observed_candidates': 1, 'admitted': 0, 'complete_population':None, 'ignored':0},
                      [1, 0, None], None):
            with self.subTest(shape=shape):
                p, export = native_fixture()
                export['candidate_denominator'] = shape
                with self.assertRaises(ContractError):
                    consume_p1_context(export, frozen_pregame=p)

    def test_exact_bool_and_null_eligibility_positive(self):
        for value in (True, False, None):
            with self.subTest(value=value):
                p, export = eligibility_fixture(value)
                result = consume_p1_context(export, frozen_pregame=p)
                self.assertIs(result['players'][0]['legal_eligibility'], value)
                self.assertEqual(result['status'], 'BLOCKED')

    def test_numeric_eligibility_summary_cannot_equal_raw_bool(self):
        for value in (0, 0.0, 1, 1.0):
            with self.subTest(value=value, type=type(value).__name__):
                p, export = eligibility_fixture(bool(value))
                export['players'][0]['legal_eligibility'] = value
                with self.assertRaises(ContractError):
                    consume_p1_context(export, frozen_pregame=p)

    def test_numeric_eligibility_raw_assertion_cannot_claim_bool(self):
        for value in (0, 0.0, 1, 1.0):
            with self.subTest(value=value, type=type(value).__name__):
                p, export = eligibility_fixture(value)
                with self.assertRaisesRegex(ContractError, 'O_P1_NATIVE_RAW_STATE_OR_CLOCK'):
                    consume_p1_context(export, frozen_pregame=p)
