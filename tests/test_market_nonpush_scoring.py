"""Regression: market and model must be scored on the same outcome event."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from market_odds_archive import capture_records, evaluate
from test_market_odds_archive import quote, forecast, DAY, OBSERVED


class NonpushMarketScoringTests(unittest.TestCase):
    def evaluate_rows(self, *rows):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capture_records([quote(line=2)], phase='afternoon', slate_date=DAY,
                            observed_at=OBSERVED, archive_root=root/'odds',
                            capture_id='nonpush-test', source_status='ok')
            path = root/'forecasts.jsonl'
            path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            return evaluate(archives=root/'odds', forecasts=path)

    def test_balanced_identical_conditional_model_and_market(self):
        result = self.evaluate_rows(
            forecast(reference_line=2, q_model=.4, q_push=.2,
                     run_id='win', outcome='WIN', actual_stat=3),
            forecast(reference_line=2, q_model=.4, q_push=.2,
                     run_id='loss', outcome='LOSS', actual_stat=1))
        summary = result['by_sport_market']['NHL:shots on goal']
        self.assertEqual(summary['model_brier'], .25)
        self.assertEqual(summary['market_brier'], .25)
        self.assertEqual(summary['mean_model_probability'], .5)
        self.assertEqual(result['matches'][0]['model_unconditional_win_probability'], .4)
        self.assertEqual(result['matches'][0]['probability_scale'], 'conditional_on_nonpush')

    def test_invalid_or_unknown_integer_mass_excluded(self):
        for changes in ({'q_push': None}, {'q_push': .8}, {'q_push': -1},
                        {'q_model': True, 'q_push': 0},
                        {'q_model': 0, 'q_push': 1}):
            with self.subTest(changes=changes):
                result = self.evaluate_rows(forecast(reference_line=2, **changes))
                self.assertEqual(result['settled_nonpush_scored'], 0)
                self.assertEqual(result['excluded']['invalid_or_missing_model_win_push_mass'], 1)

    def test_push_outcomes_remain_unscored(self):
        result = self.evaluate_rows(forecast(reference_line=2, q_model=.4, q_push=.2,
                                             outcome='PUSH', actual_stat=2))
        self.assertEqual(result['settled_nonpush_scored'], 0)

    def test_invalid_numbers_keep_report_json_finite(self):
        for changes in ({'q_model': float('nan'), 'q_push': 0},
                        {'q_model': .4, 'q_push': float('inf')},
                        {'q_model': '0.5', 'q_push': 0},
                        {'q_model': .4, 'q_push': '0.2'}):
            with self.subTest(changes=changes):
                result = self.evaluate_rows(forecast(reference_line=2, **changes))
                self.assertEqual(result['settled_nonpush_scored'], 0)
                json.dumps(result, allow_nan=False)


if __name__ == '__main__':
    unittest.main()
