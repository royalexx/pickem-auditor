"""Permanent F-P5-01 controls. Entirely synthetic; no historical outcomes."""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest

from v2.nba_c import experiment as e, scores
from tests.nba_c.test_p5_c_family import fixture


class TemporalIntegrity(unittest.TestCase):
    def cache(self, rows):
        return e.CachedCohort(rows, authorization="SYNTHETIC_UNIT_TEST")

    def reject(self, row, pattern=None):
        if pattern:
            with self.assertRaisesRegex(e.ExperimentError, pattern):
                self.cache([row])
        else:
            with self.assertRaises(e.ExperimentError):
                self.cache([row])

    def test_exact_original_p6_input(self):
        # Original fixture bytes, not a regenerated upgraded witness fixture.
        row=json.loads(Path('tests/nba_c/fixtures/p6_f_p5_01_backdated.json').read_text())
        # JSON object keys are strings; restore the original integer PMF support.
        for item in row['pipelines'].values():
            item['pmf']={int(k):v for k,v in item['pmf'].items()}
        self.reject(row, 'INVALID_CHRONOLOGY')
        with self.assertRaisesRegex(e.ExperimentError, 'INVALID_CHRONOLOGY'):
            e.make_walk_forward_folds([row], min_train_dates=1)

    def test_valid_2022_all_statistics_and_complete_pipelines(self):
        rows=[fixture(stat=stat, actual=3) for stat in e.STATS]
        c=self.cache(rows)
        self.assertEqual(c.game_count, 1)
        self.assertEqual(c.date_count, 1)
        self.assertEqual(c.cached_pmf_count, 24)
        self.assertEqual(set(c.modes.values()), set(e.MODES))

    def test_single_field_mutations(self):
        cases={
            'date':'2021-10-20T00:00:00Z',
            'frozen_at':'2021-10-20T17:00:00Z',
            'event_start_at':'2022-10-20T22:00:00Z',
            'event_end_at':'2022-10-20T23:30:00Z',
            'official_available_at':'2022-10-20T23:30:00Z',
            'game_id':'nba:wrong', 'player_id':'nba:wrong',
            'stat':'rebounds', 'source_profile':'historical_reconstruction',
            'actual':True,
        }
        for key, value in cases.items():
            row=fixture()
            row[key]=value
            with self.subTest(field=key):
                self.reject(row)

    def test_utc_date_semantics(self):
        for date in ('2022-10-19T00:00:00Z','2022-10-20T01:00:00Z',
                     '2022-10-20T00:00:00-04:00','2022-10-20T00:00:00'):
            with self.subTest(date=date):
                row=fixture(); row['date']=date
                self.reject(row)
        row=fixture(); row['event_start_at']='2022-10-21T00:01:00Z'
        self.reject(row, 'INVALID_CHRONOLOGY')

    def test_holdout_backdating_multiple_redundant_fields(self):
        for fields in ((), ('date',), ('date','frozen_at'),
                       ('date','frozen_at','event_start_at'),
                       ('date','frozen_at','event_start_at','event_end_at','official_available_at')):
            row=fixture(date='2023-11-20T00:00:00Z')
            old=fixture()
            for field in fields:
                row[field]=old[field]
            with self.subTest(fields=fields):
                self.reject(row)
        row=fixture()
        row['event_metadata']['season']='2023-24'
        self.reject(row, 'SEASON_MISMATCH')

    def test_every_clock_is_checked_independently(self):
        clock_names=('source_available_at','available_at','published_at','retrieved_at',
                     'ingested_at','input_freeze_at','decision_cutoff_at',
                     'model_training_cutoff_at','training_cutoff_at',
                     'asof_cutoff_utc','cutoff_at','feature_cutoff_at')
        for name in clock_names:
            for location in ('row','source','pipeline','nested'):
                row=fixture()
                target={'row':row, 'source':row['source_lineage'][0],
                        'pipeline':row['pipelines']['S0'],
                        'nested':row.setdefault('model_lineage',{})}[location]
                target[name]='2022-10-20T18:00:00Z'
                with self.subTest(clock=name, location=location):
                    self.reject(row, 'POST_FREEZE')
        row=fixture(); row['unexpected_at']='2022-10-20T16:00:00Z'
        self.reject(row, 'UNSUPPORTED_TIME')
        for value in ('2022-10-20T16:00:00Z','2022-10-20T23:00:00Z'):
            row=fixture(); row['pipelines']['S0']['forecast_at']=value
            self.reject(row, 'INVALID_FORECAST_TIME')

    def test_malformed_cutoffs_never_skip_time_validation(self):
        for value in ({}, [], None, False, 2022, "2022-10-20T16:00:00"):
            row=fixture(); row['model_lineage']={'training_cutoff_at':value}
            with self.subTest(value=value):
                self.reject(row)

    def test_required_witnesses_and_source_lineage(self):
        for key in ('event_end_at','event_metadata','source_lineage','actual_stats'):
            row=fixture(); del row[key]
            with self.subTest(missing=key):
                self.reject(row, 'MISSING')
        for change in ({'sha256':'bad'}, {'source_id':''},
                       {'retrieved_at':'2022-10-20T15:00:00Z'},
                       {'game_id':'nba:wrong'}, {'source_profile':'original_prospective'}):
            row=fixture(); row['source_lineage'][0].update(change)
            with self.subTest(change=change):
                self.reject(row)
        row=fixture(); row['source_lineage'].append(deepcopy(row['source_lineage'][0]))
        self.reject(row, 'SOURCE_LINEAGE')
        row=fixture(); row['source_lineage']=[]
        self.reject(row, 'SOURCE_LINEAGE')

    def test_pipeline_identity_membership_and_mode(self):
        for name,value in (('game_id','nba:wrong'),('player_id','nba:wrong'),
                           ('stat','pra'),('pipeline_id','other'),('source_ids',[]),
                           ('mode','S'),('source_profile','historical_reconstruction')):
            row=fixture(); row['pipelines']['S0'][name]=value
            with self.subTest(name=name):
                self.reject(row)
        rows=[fixture(game='nba:g1'),fixture(game='nba:g2')]
        del rows[1]['pipelines']['J0']
        with self.assertRaisesRegex(e.ExperimentError,'INCOMPLETE_MATCHED'):
            self.cache(rows)
        rows=[fixture(game='nba:g1'),fixture(game='nba:g2')]
        rows[1]['pipelines']['S0']['mode']='S_O'
        with self.assertRaisesRegex(e.ExperimentError,'MODE_CHANGED'):
            self.cache(rows)

    def test_outcome_end_and_statistical_accounting(self):
        row=fixture(); row['official_available_at']=row['event_start_at']
        self.reject(row, 'OUTCOME_BEFORE_GAME_END')
        row=fixture(); row['event_end_at']=row['event_start_at']
        self.reject(row, 'OUTCOME_BEFORE_GAME_END')
        for stat in ('points','pr','pa','ra','pra'):
            row=fixture(stat=stat,actual=3); row['actual_stats']['assists']=-1
            with self.subTest(stat=stat):
                self.reject(row, 'STATISTICAL_WITNESS')
            row=fixture(stat=stat,actual=3); row['actual']=4
            self.reject(row, 'OUTCOME_STAT_IDENTITY')
        row=fixture(); row['actual_stats']['threes']=1
        self.reject(row, 'POINT_ACCOUNTING')
        for stat in ('POINTS','points+rebounds','minutes',None):
            row=fixture(); row['stat']=stat
            self.reject(row, 'INVALID_STAT')

    def test_duplicates_and_game_metadata(self):
        row=fixture()
        with self.assertRaisesRegex(e.ExperimentError,'DUPLICATE'):
            self.cache([row,deepcopy(row)])
        # Same game at different dates cannot inflate the observed-game count.
        second=fixture(stat='assists',date='2022-10-21T00:00:00Z')
        with self.assertRaisesRegex(e.ExperimentError,'INCONSISTENT_GAME'):
            self.cache([row,second])
        with self.assertRaisesRegex(e.ExperimentError,'INCONSISTENT_GAME'):
            e.make_walk_forward_folds([row,second])
        for field in ('game_id','player_id'):
            row=fixture(); row[field]=''
            self.reject(row, 'INVALID_IDENTITY')

    def test_outcome_evidence_cannot_enter_forecast_pipeline(self):
        for field,value in (('actual',0),('actual_stats',{}),('actual_minutes',20),
                            ('event_end_at','2022-10-20T23:59:00Z'),
                            ('official_available_at','2022-10-21T00:00:00+00:00'),
                            ('target_game_outcome',False)):
            row=fixture(); row['pipelines']['S0'][field]=value
            with self.subTest(field=field):
                self.reject(row, 'OUTCOME_IN_FORECAST_PIPELINE')

    def test_invalid_pmfs(self):
        for pmf in ({0:.5}, {0:-.1,1:1.1}, {0:float('nan')},
                    {-1:1}, {1.5:1}, [(0,.5),(0,.5)]):
            row=fixture(); row['pipelines']['S0']['pmf']=pmf
            with self.subTest(pmf=pmf), self.assertRaises(scores.ScoreError):
                self.cache([row])

    def test_historical_and_w3_fallback_cannot_bypass_validation(self):
        for authorization in ('','HISTORICAL','G1','SYNTHETIC','SYNTHETIC_UNIT_TEST '):
            with self.subTest(authorization=authorization), self.assertRaisesRegex(
                    e.ExperimentError,'NOT_AUTHORIZED'):
                e.CachedCohort([fixture()],authorization=authorization)
        for profile in ('historical_reconstruction','original_prospective','SYNTHETIC_UNIT_TEST'):
            row=fixture(); row['source_profile']=profile
            self.reject(row, 'ONLY_SYNTHETIC')
        row=fixture(date='2023-11-20T00:00:00Z')
        with self.assertRaisesRegex(e.ExperimentError,'HOLDOUT'):
            e.w3_by_stat([row],global_weights={'S0':1.,'SO0':0.,'J0':0.},min_games=20)

    def test_caller_mutations_cannot_change_cached_inputs(self):
        row=fixture(); cache=self.cache([row])
        before=cache.nll_for([0.,0.,1.])
        row['pipelines']['SO0']['pmf']={0:1.}
        row['actual']=50
        self.assertEqual(cache.nll_for([0.,0.,1.]),before)
        self.assertEqual(cache.rows[0]['actual'],0)

    def test_chronological_release_checks_and_prior_day_freeze(self):
        rows=[fixture(date=f'2022-10-{20+i:02d}T00:00:00Z',game=f'nba:g{i}') for i in range(4)]
        rows[0]['official_available_at']='2022-10-23T18:00:00Z'
        folds=e.make_walk_forward_folds(rows,min_train_dates=2)
        self.assertTrue(folds)
        self.assertTrue(all(r['game_id']!='nba:g0' for f in folds for r in f['train']))
        # Date is UTC game date, not required to precede the forecast freeze.
        row=fixture(); row['frozen_at']='2022-10-19T17:00:00Z'
        row['source_lineage'][0].update(source_available_at='2022-10-19T15:00:00Z',
                                       retrieved_at='2022-10-19T16:00:00Z')
        for item in row['pipelines'].values():
            item.update(frozen_at=row['frozen_at'],forecast_at=row['frozen_at'],
                        model_training_cutoff_at='2022-10-19T14:00:00Z')
        self.assertEqual(self.cache([row]).game_count,1)

    def test_independent_p6_numerical_oracles(self):
        # Independent analytic targets, not internal reference_crps().
        pois={k:math.exp(-1-math.lgamma(k+1)) for k in range(30)}
        nb={k:(k+1)/2**(k+2) for k in range(120)}
        joint=[((0,0),.5),((2,2),.5)]
        for actual,expected in ((scores.crps(pois,0),.47622238819739127),
                                (scores.crps(nb,0),26/27),
                                (scores.energy_score(joint,(0,2)),2-math.sqrt(2)/2),
                                (scores.variogram_score(joint,(0,2)),2)):
            self.assertAlmostEqual(actual,expected,places=11)


if __name__=='__main__':
    unittest.main()
