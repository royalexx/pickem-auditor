"""Adversarial, read-only O zero-prior diagnostics; no S4/J model replacement."""
import copy
import unittest

from tests.nba_joint.test_coherent_predictive_v1 import coherent_fixture
from v2.nba_joint.coherent_zero_audit_v1 import (
    analytic_minute_grid, assert_zero_exposure_no_credited_events,
    audit_saved_bank,
)
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest


class CoherentZeroAuditTests(unittest.TestCase):
    def test_analytic_prior_is_monotone_and_original_mean_is_one_percent(self):
        model,_=coherent_fixture()
        x=analytic_minute_grid(model,zero_weights=(0.,.01,.05),
                               thresholds_minutes=(0.,.5,1.))
        self.assertEqual((x['population_named'],len(x['rows'])),(14,42))
        self.assertEqual(x['original_expected_zero_weight'],.01)
        self.assertFalse(x['joint_law_equivalence_claim'])
        self.assertFalse(x['event_path_conditional_result'])
        for i in range(0,42,3):
            a,b,c=x['rows'][i:i+3]
            self.assertEqual([a['zero_weight'],b['zero_weight'],c['zero_weight']],
                             [0.,.01,.05])
            for t in ('0.0','0.5','1.0'):
                self.assertLessEqual(a['cdf_at_minutes'][t],
                                     b['cdf_at_minutes'][t])
                self.assertLessEqual(b['cdf_at_minutes'][t],
                                     c['cdf_at_minutes'][t])
            for row in (a,b,c):
                self.assertEqual(row['cdf_at_minutes']['0.0'],
                                 row['exact_zero_probability'])
                self.assertLessEqual(row['cdf_at_minutes']['0.0'],
                                     row['cdf_at_minutes']['0.5'])
                self.assertLessEqual(row['cdf_at_minutes']['0.5'],
                                     row['cdf_at_minutes']['1.0'])

    def test_invalid_grid_and_duplicate_weights_fail_closed(self):
        model,_=coherent_fixture()
        for kw in (
            {'zero_weights':(0.,0.)},
            {'zero_weights':(-.01,)},
            {'zero_weights':(1.,)},
            {'duration_minutes':47.},
            {'thresholds_minutes':(48.,)},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                analytic_minute_grid(model,**kw)

    def test_zero_minutes_cannot_have_credited_boxscore_count(self):
        fixed={'actors':{},'O':{}}
        accepted={'counts':{}}
        for team in ('A','B'):
            actors=[{'identity':{'player_id':f'{team}{i}'},'index':i}
                    for i in range(7)]
            fixed['actors'][team]=actors
            fixed['O'][team]={'minutes':[0. if i==0 else 10. for i in range(7)]}
            accepted['counts'][team]=[{'points':0,'threes':0,'rebounds':0,
                                     'assists':0} for _ in range(7)]
        r=assert_zero_exposure_no_credited_events(fixed,accepted)
        self.assertEqual((r['named_players'],r['zero_minutes']),(14,2))
        self.assertEqual(r['zero_player_ids'],['A0','B0'])
        bad=copy.deepcopy(accepted)
        bad['counts']['A'][0]['points']=3
        with self.assertRaisesRegex(ValueError,'ZERO_AUDIT_ZERO_MINUTE_ACTOR_HAS_STATS'):
            assert_zero_exposure_no_credited_events(fixed,bad)
        bad=copy.deepcopy(accepted)
        bad['counts']['B'][0]['rebounds']=-1
        with self.assertRaises(ValueError):
            assert_zero_exposure_no_credited_events(fixed,bad)

    def test_bad_population_and_missing_team_fail_closed(self):
        fixed={'actors':{'A':[{'identity':{'player_id':'A0'},'index':0}]},
               'O':{'A':{'minutes':[0.]}}}
        accepted={'counts':{'A':[{'points':0}]}}
        with self.assertRaisesRegex(ValueError,'ZERO_AUDIT_NAMED_POPULATION'):
            assert_zero_exposure_no_credited_events(fixed,accepted)
        with self.assertRaisesRegex(ValueError,'ZERO_AUDIT_TEAM_JOIN'):
            assert_zero_exposure_no_credited_events(fixed,{'counts':{}})

    def test_actual_frozen_bank_scope_is_read_only(self):
        from pathlib import Path
        from v2.nba_architecture.subset_contract_v1 import strict_json
        p=Path('docs/nba_architecture/coherent_opportunity_20261120/actual/BANK.json')
        raw=p.read_bytes()
        self.assertEqual(digest(raw),
            '318bb9b2317ae120b6b51852a88b97177424fc0caeba36ed8b38b4f6ead01d88')
        bank=strict_json(raw)
        before=digest(canonical(bank))
        result=audit_saved_bank(bank)
        self.assertEqual(digest(canonical(bank)),before)
        self.assertEqual((result['scenarios'],result['named_slot_denominator']),
                         (64,896))
        self.assertEqual(len(result['per_scenario']),64)
        self.assertTrue(result['no_new_forecast_issued'])
        self.assertFalse(result['full_S4_J_sensitivity_evaluated'])
        self.assertFalse(result['release'])


if __name__=='__main__':
    unittest.main()
