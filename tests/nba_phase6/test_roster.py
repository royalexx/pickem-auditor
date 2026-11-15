import copy
import json
import unittest
from pathlib import Path
from research.nba_phase6.roster import build_roster_contract, require_forecast_ready

class RosterTests(unittest.TestCase):
    def setUp(self):
        self.folder=Path('research/nba_joint_v01/prospective_canary')
        self.model=json.loads(Path('research/nba_joint_v01/results/model.json').read_text())
    def test_original_raw_replay_remains_blocked(self):
        r=build_roster_contract(self.folder,self.model)
        self.assertEqual(r['coverage']['accepted_ws1_candidates'],36)
        self.assertEqual(r['coverage']['eligible'],0)
        self.assertEqual(r['coverage']['forecasts_abstained'],36)
        self.assertTrue(r['source_bytes_verified'])
        self.assertTrue(all(p['participation_probability'] is None for p in r['players']))
        with self.assertRaisesRegex(ValueError,'ROSTER_NOT_FORECAST_READY'):require_forecast_ready(r)
    def test_invented_probability_rejected(self):
        with self.assertRaisesRegex(ValueError,'UNVALIDATED_PARTICIPATION_METHOD'):
            build_roster_contract(self.folder,self.model,participation_evidence={'any':{'probability':1}})
    def test_future_model_rejected(self):
        self.model['training_cutoff_at']='2030-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'MODEL_AFTER_FREEZE'):build_roster_contract(self.folder,self.model)
    def test_stale_roster_preserved_and_blocked(self):
        r=build_roster_contract(self.folder,self.model,max_age_seconds=0)
        self.assertEqual(len(r['players']),36)
        self.assertTrue(all('STALE_GAME_DAY_EVIDENCE' in p['abstention_reasons'] for p in r['players']))
    def test_mutation_does_not_grant_readiness(self):
        r=build_roster_contract(self.folder,self.model);r['status']='shadow_only'
        with self.assertRaisesRegex(ValueError,'ROSTER_CONTRACT_HASH'):require_forecast_ready(r)
