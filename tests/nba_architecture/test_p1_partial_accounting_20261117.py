"""Necessary partial-source accounting bounds; all fixtures synthetic."""
import json
import tempfile
import unittest
from tests.nba_architecture.test_p1_history import build,make_entry
from tests.nba_architecture.test_p1_remediation import (
    official_fixture,nba_entry,repair_opponent,NBA_GAME,NBA_TEAMS,
)
from v2.nba_architecture.p1_history import _stats
from v2.nba_architecture.p1_handoff import export_prior_game
from v2.nba_architecture.p1_vault import OfficialOutcomeVault


class PartialAccounting(unittest.TestCase):
    def test_partial_points_known_makes_have_necessary_lower_bound(self):
        for stats in ({'points':1,'threes':2},{'points':1,'fgm':1},
                      {'points':1,'ftm':2},{'points':6,'threes':2,'ftm':1},
                      {'points':4,'fgm':2,'threes':1}):
            with self.subTest(stats=stats),self.assertRaisesRegex(ValueError,'POINT_ACCOUNTING'):_stats(stats)

    def test_partial_points_known_shot_and_free_throw_caps(self):
        for stats in ({'points':4,'fgm':1,'ftm':0},
                      {'points':4,'fga':1,'fta':0},
                      {'points':5,'fga':2,'fg3a':0,'fta':0},
                      {'points':6,'fgm':2,'threes':0,'fta':1},
                      {'points':2,'fgm':0,'fta':1}):
            with self.subTest(stats=stats),self.assertRaisesRegex(ValueError,'POINT_ACCOUNTING'):_stats(stats)

    def test_threes_and_two_point_attempt_support(self):
        for stats in ({'threes':2,'fga':1},
                      {'fgm':5,'threes':1,'fga':6,'fg3a':5}):
            with self.subTest(stats=stats),self.assertRaisesRegex(ValueError,'SHOOTING_ACCOUNTING'):_stats(stats)

    def test_partial_rebound_components_cannot_exceed_total(self):
        for stats in ({'rebounds':1,'oreb':2},{'rebounds':1,'dreb':2}):
            with self.subTest(stats=stats),self.assertRaisesRegex(ValueError,'REBOUND_ACCOUNTING'):_stats(stats)

    def test_partial_combinations_bound_known_components(self):
        for stats in ({'pr':1,'points':2},{'pa':1,'assists':2},
                      {'ra':1,'rebounds':2},{'pra':3,'points':2,'assists':2}):
            with self.subTest(stats=stats),self.assertRaisesRegex(ValueError,'COMBINATION_ACCOUNTING'):_stats(stats)

    def test_historical_builder_rejects_partial_impossible_points(self):
        with self.assertRaisesRegex(ValueError,'POINT_ACCOUNTING'):
            build([make_entry(stats={'points':1,'threes':2})])

    def test_actual_raw_native_export_rejects_impossible_scoring(self):
        data=json.loads(repair_opponent(nba_entry(26,stats={'points':1,'threes':2}))['record']['payload'])
        with self.assertRaisesRegex(ValueError,'POINT_ACCOUNTING'):
            export_prior_game(data,official_fixture(points=1),
                ingested_at='2026-11-16T19:00:00Z',source_profile='synthetic_engineering')

    def test_vault_rejects_impossible_scoring_before_write(self):
        b=official_fixture(points=1)
        with tempfile.TemporaryDirectory() as td:
            v=OfficialOutcomeVault(td)
            with self.assertRaisesRegex(ValueError,'POINT_ACCOUNTING'):
                v.append(game_id=NBA_GAME,player_id='nba:player:7',team_id=NBA_TEAMS[0],
                    state='PLAYED',minutes=26,stats={'points':1,'threes':2},
                    source_id='nba:official:box',source_bytes=b['raw'],
                    observed_at='2026-11-16T19:00:00Z',official_status='FINAL',official_game_evidence=b)
            self.assertEqual(v.records(),[])

    def test_legitimate_partial_and_full_positive_controls(self):
        for stats in ({'points':1},{'points':6,'threes':2},
                      {'points':12,'fgm':5,'threes':2},
                      {'points':13,'fgm':5,'threes':2,'ftm':1},
                      {'points':3,'fgm':1,'ftm':0},
                      {'points':5,'fgm':1,'ftm':2},
                      {'points':7,'fga':2,'fg3a':1,'fta':2},
                      {'fgm':5,'threes':4,'fga':6,'fg3a':5},
                      {'rebounds':3,'oreb':2},{'rebounds':3,'oreb':2,'dreb':1},
                      {'pra':4,'points':2,'assists':2},{'pr':5,'points':2,'rebounds':3}):
            with self.subTest(stats=stats):_stats(stats)
