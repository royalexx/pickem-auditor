from copy import deepcopy
import unittest
from v2.nba_architecture.p1_bounded_demo_v1 import demonstrate, classify_rows
from tests.nba_architecture.test_p1_listed_source_v1 import inputs


class BoundedDemoTests(unittest.TestCase):
    def test_actual_source_counts_and_original_fields_preserved(self):
        result=demonstrate(*inputs())
        self.assertEqual((result['attempted_rows'],result['included_rows'],result['explicit_dnp_rows'],result['excluded_rows']),(26,24,2,0))
        self.assertEqual([r['source_row'] for r in result['rows']],result['source_admission']['rows'])
        self.assertIsNone(result['target_eligible_roster_count'])
        self.assertEqual(result['G1'],'NO-GO')

    def test_policy_boundary_matrix_not_admitted_source_evidence(self):
        rows=[dict(state='PLAYED',exact_seconds=s,stats={'points':3},player_id=str(s)) for s in (-1,0,1,29,30,49,2880,2881,None)]
        rows += [dict(state='PLAYED_ZERO_MINUTES',exact_seconds=0,stats={'points':1}),dict(state='DNP',exact_seconds=None,stats={}),dict(state='UNKNOWN',exact_seconds=None,stats={})]
        original=deepcopy(rows);result=classify_rows(rows,2880)
        self.assertEqual(rows,original)
        self.assertEqual([r['disposition'] for r in result],['EXCLUDED']*4+['INCLUDED']*3+['EXCLUDED']*3+['DNP','EXCLUDED'])
        self.assertEqual(len(result),12)

    def test_no_partial_acceptance_for_corrupt_source_or_late_request(self):
        args=inputs();args[2]+=b' '
        result=demonstrate(*args)
        self.assertEqual(result['status'],'REJECTED_WHOLE_SOURCE')
        self.assertEqual(result['admission']['rejected_rows'],26)
        result=demonstrate(*inputs(),input_freeze_at='2018-10-19T23:45:00Z')
        self.assertEqual(result['status'],'REJECTED_WHOLE_SOURCE')
        self.assertEqual(result['admission']['rejected_rows'],26)
