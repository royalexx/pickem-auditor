"""Versioned G1 engineering regressions. Every input here is synthetic."""
from copy import deepcopy
from datetime import datetime, timedelta
import unittest

from test_p3_o_family import inputs
from v2.nba_architecture.v2_contracts import ContractError
from v2.nba_o_family import build_opportunity


class ModelCutoffControls(unittest.TestCase):
    def test_declared_model_cutoff_before_equal_and_one_microsecond_after(self):
        for offset in (-1, 0, 1):
            with self.subTest(offset_microseconds=offset):
                p, g, priors = inputs()
                model = deepcopy(g['model'])
                cutoff = datetime.fromisoformat(p['training_cutoff_at'].replace('Z', '+00:00'))
                model['training_cutoff_at'] = (cutoff + timedelta(microseconds=offset)).isoformat().replace('+00:00', 'Z')
                options = dict(model=model, seed=17, variant='O2',
                               home_team_id=p['team_ids'][0],
                               home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
                if offset > 0:
                    with self.assertRaisesRegex(ContractError, 'MODEL_AFTER_DATA_CUTOFF'):
                        build_opportunity(p, g, priors, **options)
                else:
                    o, sidecar = build_opportunity(p, g, priors, **options)
                    self.assertEqual(o['model'], model)
                    self.assertEqual(sidecar['model'], model)

    def test_declared_prior_cutoff_before_equal_and_one_microsecond_after(self):
        for offset in (-1, 0, 1):
            with self.subTest(offset_microseconds=offset):
                p, g, priors = inputs()
                cutoff = datetime.fromisoformat(p['training_cutoff_at'].replace('Z', '+00:00'))
                for prior in priors.values():
                    prior['training_cutoff_at'] = (cutoff + timedelta(microseconds=offset)).isoformat().replace('+00:00', 'Z')
                options = dict(model=g['model'], seed=17, variant='O2',
                               home_team_id=p['team_ids'][0],
                               home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
                if offset > 0:
                    with self.assertRaisesRegex(ContractError, 'O_PRIOR_AFTER_P1_CUTOFF'):
                        build_opportunity(p, g, priors, **options)
                else:
                    o, sidecar = build_opportunity(p, g, priors, **options)
                    self.assertTrue(o['scenarios'])
                    self.assertEqual(sidecar['prior_manifest'], priors)
