import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from v2.nba_architecture.conditional_c_v1 import read_native_outcomes,replay_and_pending,score_count,threshold_probabilities,empirical_scores
from v2.nba_architecture.full_predictive_replay_v2 import read_issued_forecast

P=Path(__file__).resolve().parents[1]/'docs/nba_architecture/complete_predictive_20261120'
spec=importlib.util.spec_from_file_location('complete_inputs',P/'inputs.py');i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)


class RealSourceTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full=(P/'actual_full_forecast/forecast.json').read_bytes();cls.parent=(i.ARCHIVE/'forecast.json').read_bytes()

    def test_genuine_native_population_and_all_unknowns(self):
        out=read_native_outcomes(**i.outcome_inputs());self.assertEqual(out['source_row_denominator'],698)
        self.assertEqual(out['state_denominators'],dict(PLAYED_REPORTED_POSITIVE=459,DNP_EXPLICIT=68,
            UNKNOWN_PARTICIPATION=5,SOURCE_LISTED_INACTIVE=166))
        self.assertTrue(all(r['official_end_at'] is None and r['source_published_at'] is None and
            r['correction_history_complete'] is None for r in out['rows']))
        self.assertTrue(all(r['played_conditional_counts'] is None for r in out['rows'] if r['participation_state']!='PLAYED_REPORTED_POSITIVE'))

    def test_actual_issued_post_event_transport_no_new_issue_and_no_fabricated_scores(self):
        with patch('v2.nba_architecture.full_predictive_runtime_v1.issue_forecast',side_effect=AssertionError('NEW_ISSUE_FORBIDDEN')):
            result=replay_and_pending(self.full,self.parent,full_inputs=i.full_inputs(),outcome_inputs=i.outcome_inputs())
        self.assertEqual((result['attempt_denominator'],result['forecasted_rows'],result['forecast_abstentions']), (140,56,84))
        self.assertEqual((result['scored_rows'],result['historical_PIT_eligible'],result['pending_outcomes']),(0,0,140))
        self.assertEqual(len({(r['player_id'],r['statistic']) for r in result['rows']}),140)

    def test_mutated_forecast_and_forged_source_root_cannot_admit(self):
        with self.assertRaises(ValueError):read_issued_forecast(self.full+b' ',self.parent,**i.full_inputs())
        with tempfile.TemporaryDirectory() as temp:
            fake=Path(temp)/'approval.json';fake.write_text('{"approved":true,"reviewer":"Independent Reviewer"}')
            inputs=i.outcome_inputs();inputs['profile_path']=fake
            with self.assertRaises(ValueError):read_native_outcomes(**inputs)
            inputs=i.outcome_inputs();inputs['population_path']=fake
            with self.assertRaises(ValueError):read_native_outcomes(**inputs)


class ScoreMechanicsOnlyTests(unittest.TestCase):
    def model(self):return dict(alpha=10.,beta=20.,minutes=dict(mean=20.,variance=8.,ot_probability=.1,ot_continuation=.2))
    def test_log_score_and_integer_halfline_complementarity(self):
        self.assertEqual(score_count(self.model(),7)['status'],'NUMERICAL_SCORE_MECHANICS_ONLY')
        for line in ('0','7','7.5','128'):
            p=threshold_probabilities(self.model(),line);self.assertAlmostEqual(p['over']+p['under']+p['push'],1,9)
        with self.assertRaises(ValueError):score_count(self.model(),True)
        with self.assertRaises(ValueError):score_count(self.model(),-1)
        with self.assertRaises(ValueError):threshold_probabilities(self.model(),'nan')

    def test_unresolved_log_tail_stays_no_score(self):
        result=score_count(self.model(),1000000)
        self.assertEqual(result['status'],'NO_SCORE_NUMERICAL_UNRESOLVED');self.assertIsNone(result['score'])

    def test_empirical_crps_matches_brute_force_and_no_epsilon(self):
        x=[0,2,5,5];y=3;out=empirical_scores(x,y)
        pair=sum(abs(a-b) for a in x for b in x)
        self.assertAlmostEqual(out['empirical_crps'],sum(abs(a-y) for a in x)/4-pair/32)
        self.assertAlmostEqual(out['fair_ensemble_crps'],sum(abs(a-y) for a in x)/4-pair/24)
        self.assertEqual(out['empirical_negative_log_score'],'POSITIVE_INFINITY_EMPIRICAL_MEASURE')
        self.assertFalse(out['population_zero_probability_claim'])


if __name__=='__main__':unittest.main()
