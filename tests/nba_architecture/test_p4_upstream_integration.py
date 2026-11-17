"""Owner API integration and adversarial contract tests; zero real source examples."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import numpy as np
from scipy.stats import betabinom

from v2.nba_architecture.v2_contracts import ContractError, seal, digest
from v2.nba_architecture.families_v2 import validate_integration
from v2.nba_joint.integration import (simulate_integrated, load_upstream, validate_p2_artifacts,
                                     _S3RNG, FIXTURES, validate_event_ledger)
from v2.nba_joint.p4 import scenario_pmfs, simulate_p4
from research.nba_p4_integration.fixture import build
from research.nba_p4_integration.prepare import prepare
from test_p4_joint import PARAMETERS, reseal, fixture


class UpstreamIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = prepare()
        cls.inputs = build(cls.root)
        cls.p, cls.g, cls.o, cls.side, cls.artifacts, cls.manifest, cls.roles = cls.inputs
        cls.result = cls.run_inputs(cls.inputs)

    @classmethod
    def run_inputs(cls, inputs, **kwargs):
        return simulate_integrated(*inputs, upstream_root=cls.root,
            evidence_mode='pinned_contract_fixture', event_parameters=PARAMETERS, seed=42, **kwargs)

    def reject(self, inputs, code=None, **kwargs):
        with self.assertRaises(ContractError) as exc:
            self.run_inputs(inputs, **kwargs)
        if code:
            self.assertEqual(exc.exception.code, code)

    def changed(self, index, change):
        x = list(self.inputs)
        x[index] = reseal(x[index], change)
        return x

    def test_actual_p2_and_p3_shapes_and_exact_lineage(self):
        p2, p3 = load_upstream(self.root)
        self.assertTrue(all(isinstance(a, p2.FittedS) for a in self.artifacts.values()))
        self.assertTrue(p3.validate_sidecar(self.side, self.p, self.g, self.o))
        self.assertTrue(validate_integration(self.result['bundle'], self.p, self.g, self.o))
        self.assertEqual(self.result['input_shas']['O_sidecar'], self.side['content_hash'])
        self.assertEqual(self.result['integration_manifest']['artifacts'],
                         {k:a.artifact_sha256 for k,a in self.artifacts.items()})
        self.assertIn('BLOCKED', self.result['status'])

    def test_default_real_mode_cannot_be_caller_authenticated(self):
        with self.assertRaisesRegex(ContractError, 'J_REAL_INTEGRATION_BLOCKED'):
            simulate_integrated(*self.inputs, upstream_root=self.root, event_parameters=PARAMETERS)
        self.assertTrue(all(x['status'] == 'P1_VERIFIED' for x in self.manifest.values()))

    def test_legacy_rate_adapter_cannot_declare_real(self):
        p,g,o,s=fixture()
        s=reseal(s,lambda x:x.update(adapter_basis='real'))
        with self.assertRaisesRegex(ContractError,'P4_S_REAL_LIKELIHOOD_ADAPTER_NOT_ACCEPTED'):
            simulate_p4(p,g,o,s,event_parameters=PARAMETERS)

    def test_missing_artifact_rejects(self):
        x=list(self.inputs);x[4]=dict(self.artifacts);del x[4]['points']
        self.reject(x,'J_S_ARTIFACT_COVERAGE')

    def test_rate_dict_in_place_of_fitted_artifact_rejects(self):
        x=list(self.inputs);x[4]=dict(self.artifacts);x[4]['points']={'rates':.6}
        self.reject(x,'J_S_FITTED_ARTIFACT_REQUIRED')

    def test_forged_fitted_parameters_cannot_self_hash(self):
        p2,_=load_upstream(self.root)
        a=self.artifacts['points'].data;a['training_rows'][0]['count']=900
        x=list(self.inputs);x[4]=dict(self.artifacts);x[4]['points']=p2.FittedS(p2.canonical(a))
        self.reject(x,'J_S_ARTIFACT_NOT_TRUSTED')

    def test_future_model_cutoff_and_wrong_stat_and_source_are_not_trusted(self):
        p2,_=load_upstream(self.root)
        for key,value in [('training_cutoff_at',self.p['event_start_at']),('stat','threes'),
                          ('source_manifest_sha256','0'*64)]:
            with self.subTest(key=key):
                a=self.artifacts['points'].data;a[key]=value
                x=list(self.inputs);x[4]=dict(self.artifacts);x[4]['points']=p2.FittedS(p2.canonical(a))
                self.reject(x,'J_S_ARTIFACT_NOT_TRUSTED')

    def test_training_cutoff_must_match_target_budget_not_just_freeze(self):
        x=list(self.inputs);x[0]=reseal(self.p,lambda p:p.update(training_cutoff_at='2026-11-15T20:00:00Z'))
        # Rebind G/O without discarding exact pregame identity checks.
        with self.assertRaises(ContractError):
            validate_p2_artifacts(x[0],self.artifacts,self.manifest,evidence_mode='pinned_contract_fixture')

    def test_late_source_evidence_rejects_even_when_self_consistent(self):
        x=list(self.inputs);x[5]=deepcopy(self.manifest)
        next(iter(x[5].values()))['available_at']=self.p['event_start_at']
        self.reject(x,'J_S_SOURCE_MANIFEST_PIN')

    def test_wrong_team_and_player_rejects(self):
        for change in [lambda p:p['players'][0].update(team_id=p['team_ids'][1]),
                       lambda p:p['players'][0].update(player_id='espn:player:forged')]:
            p=reseal(self.p,change)
            with self.assertRaises(ContractError):
                validate_p2_artifacts(p,self.artifacts,self.manifest,evidence_mode='pinned_contract_fixture')

    def test_wrong_roles_rejects(self):
        x=list(self.inputs);x[6]=dict(self.roles);x[6][next(iter(x[6]))]='forged'
        self.reject(x,'J_S_ROLE_PIN')

    def test_wrong_g_scenario_and_weight_rejects(self):
        for change in [lambda g:g['scenarios'][0].update(scenario_id='synthetic:bad'),
                       lambda g:g['scenarios'][0].update(weight=.9)]:
            self.reject(self.changed(1,change))

    def test_wrong_o_scenario_and_nonconserving_minutes_rejects(self):
        for change in [lambda o:o['scenarios'][0].update(scenario_id='synthetic:bad'),
                       lambda o:o['scenarios'][0]['players'][0].update(minutes=0.)]:
            self.reject(self.changed(2,change))

    def test_sidecar_identity_and_duplicate_roster_rejects(self):
        self.reject(self.changed(3,lambda s:s.update(game_id='espn:game:wrong')))
        self.reject(self.changed(3,lambda s:s['scenarios'][0]['players'].append(
            deepcopy(s['scenarios'][0]['players'][0]))))

    def test_sidecar_exact_weights_and_pools_rejects(self):
        self.reject(self.changed(3,lambda s:s['scenarios'][0].update(weight=.7)))
        self.reject(self.changed(3,lambda s:s['scenarios'][0]['teams'][self.p['team_ids'][0]].update(projected_possessions=9.)))

    def test_player_opportunity_must_equal_share_times_pool(self):
        def change(s):
            rows=s['scenarios'][0]['players'];rows[0]['projected_possession_opportunity']+=1
            rows[1]['projected_possession_opportunity']-=1
        self.reject(self.changed(3,change),'J_P3_PLAYER_OPPORTUNITY')

    def test_invalid_lineup_clock_and_duplicate_index_rejects(self):
        for change in [lambda seg:seg.update(start=-1.),
                       lambda seg:seg.update(end=seg['start']),
                       lambda seg:seg.update(player_indices=[0,0,1,2,3])]:
            self.reject(self.changed(3,lambda s:change(s['scenarios'][0]['teams'][
                self.p['team_ids'][0]]['lineup_segments'][0])))

    def test_exact_o_minutes_and_participation_no_j_resampling(self):
        for sc in self.result['bundle']['scenarios']:
            upstream=next(s for s in self.o['scenarios'] if s['scenario_id']==sc['scenario_id'])
            self.assertEqual([{k:x[k] for k in ('player_id','team_id','minutes','participation')}
                              for x in sc['players']],upstream['players'])
            self.assertEqual(sc['weight'],upstream['weight'])

    def test_zero_through_three_ot_and_physics(self):
        self.assertEqual([s['overtime_periods'] for s in self.result['bundle']['scenarios']],[0,1,2,3])
        for sc in self.result['bundle']['scenarios']:
            for team in self.p['team_ids']:
                people=[x for x in sc['players'] if x['team_id']==team]
                self.assertAlmostEqual(sum(x['minutes'] for x in people),240+25*sc['overtime_periods'])
                self.assertEqual(sum(x['stats']['points'] for x in people),sc['team_points'][team])
            for person in sc['players']:
                s=person['stats']
                self.assertLessEqual(s['threes'],s['three_pa'])
                self.assertLessEqual(s['two_pm'],s['two_pa'])
                self.assertLessEqual(s['ftm'],s['fta'])
                self.assertEqual(s['points'],2*s['two_pm']+3*s['threes']+s['ftm'])
                for combo,parts in [('pr',('points','rebounds')),('pa',('points','assists')),
                                    ('ra',('rebounds','assists')),('pra',('points','rebounds','assists'))]:
                    self.assertEqual(s[combo],sum(s[k] for k in parts))

    def test_ledger_has_no_self_assists_or_excess_rebounds(self):
        for audit in self.result['audit_rows']:
            ledger=audit['event_ledger']
            self.assertEqual(sum(np.diag(ledger['assist_matrix'])),0)
            for r in ledger['rebounds']:
                self.assertLessEqual(r['credited'],r['available'])
                self.assertEqual(r['credited'],r['offensive']+r['defensive'])
            self.assertEqual(digest(ledger),audit['event_ledger_sha256'])
            self.assertIn('not_exact',ledger['possession_accounting'])

    def test_s3_uses_projected_integer_attempts_and_p2_beta_binomial(self):
        p2,_=load_upstream(self.root)
        a=self.artifacts['three_conversion']
        pid=next(iter(self.roles))
        pr=p2.predict_conditional(a,player_id=pid,role=self.roles[pid],projected_exposure=7,statistic='threes')
        expected=betabinom.pmf(np.arange(8),7,pr.parameters['alpha'],pr.parameters['beta'])
        np.testing.assert_allclose([x['mass'] for x in pr.parameters['support']],expected,rtol=1e-12)
        for audit in self.result['audit_rows']:
            draws=audit['event_ledger']['S3_projected_attempts']
            self.assertEqual(len(draws),len(self.p['players']))
            for row in draws:
                self.assertIs(type(row['projected_three_pa']),int)
                self.assertLessEqual(row['made_threes'],row['projected_three_pa'])

    def test_s3_protocol_fails_closed_on_noninteger_attempts(self):
        p2,_=load_upstream(self.root)
        players=self.p['players'];ix=[list(range(6)),list(range(6,12))]
        proxy=_S3RNG(np.random.default_rng(1),ix,players,p2,self.artifacts,self.roles,.36)
        proxy.binomial(np.ones(6,dtype=int),.54)
        with self.assertRaisesRegex(ContractError,'J_PROJECTED_ATTEMPTS_INTEGER'):
            proxy.binomial(np.ones(6),.36)

    def test_target_realized_attempts_key_is_rejected(self):
        self.reject(self.changed(2,lambda o:o['scenarios'][0]['players'][0].update(target_actual_three_attempts=9)))

    def test_projection_is_explicit_and_retains_complete_p2_laws(self):
        for audit in self.result['audit_rows']:
            mapping=audit['integration']
            self.assertIs(mapping['marginal_laws_preserved_exactly'],False)
            for person in mapping['P2_to_J_projection'].values():
                for law in person['conditional_laws'].values():
                    self.assertAlmostEqual(sum(x['mass'] for x in law['pmf']),1.)
                    self.assertLessEqual(law['tail_mass_upper_bound'],1e-11)

    def test_pmfs_are_exact_weighted_same_draw_for_all_players_and_stats(self):
        pmfs=scenario_pmfs(self.result,self.p,frozen_at='2026-11-16T23:03:00Z',seed=42)
        for pid,stats in pmfs.items():
            self.assertEqual(set(stats),{'points','rebounds','assists','threes','pr','pa','ra','pra'})
            for stat,law in stats.items():
                expected={}
                for sc in self.result['bundle']['scenarios']:
                    value=next(x['stats'][stat] for x in sc['players'] if x['player_id']==pid)
                    expected[value]=expected.get(value,0.)+sc['weight']
                self.assertEqual({r['value']:r['mass'] for r in law['pmf'] if r['mass']},expected)

    def test_deterministic_seed_hash_replay(self):
        other=self.run_inputs(self.inputs)
        self.assertEqual(other['bundle']['content_hash'],self.result['bundle']['content_hash'])
        self.assertEqual(other['audit_rows'],self.result['audit_rows'])
        self.assertEqual(other['scenario_hashes'],self.result['scenario_hashes'])

    def test_home_identity_is_taken_from_p3_not_roster_order(self):
        x=build(self.root,home_reversed=True)
        result=self.run_inputs(x)
        self.assertEqual(x[3]['home_team_id'],self.p['team_ids'][1])
        self.assertNotEqual(result['scenario_hashes'],self.result['scenario_hashes'])

    def test_dnp_and_played_zero_preserved_with_zero_events(self):
        for status in ('DNP','PLAYED_ZERO_MINUTES'):
            def change(priors):
                for pid in ('espn:player:15','espn:player:25'):
                    priors[pid]['scenario_participation_prior']=0. if status=='DNP' else 1.
                    priors[pid]['played_zero_probability']=1. if status=='PLAYED_ZERO_MINUTES' else 0.
            x=build(self.root,special=change)
            result=self.run_inputs(x)
            for sc in result['bundle']['scenarios']:
                for pid in ('espn:player:15','espn:player:25'):
                    row=next(x for x in sc['players'] if x['player_id']==pid)
                    self.assertEqual(row['participation'],status)
                    self.assertEqual(row['minutes'],0.)
                    self.assertTrue(all(v==0 for v in row['stats'].values()))

    def test_early_exit_total_cap_and_role_state_consumed(self):
        def change(priors):
            priors['espn:player:10']['early_exit_probability']=1.
        x=build(self.root,special=change)
        result=self.run_inputs(x)
        for sc,audit in zip(result['bundle']['scenarios'],result['audit_rows']):
            row=next(x for x in sc['players'] if x['player_id']=='espn:player:10')
            self.assertLessEqual(row['minutes'],.25*(48+5*sc['overtime_periods'])+1e-9)
            self.assertEqual(audit['integration']['P2_to_J_projection']['espn:player:10']['O_role_state'],'early_exit')

    def test_j0_j1_j2_j3_boundaries(self):
        with self.assertRaisesRegex(ContractError,'P4_UNDECLARED_EXTRA_UNCERTAINTY'):
            self.run_inputs(self.inputs,role_sigma=.1)
        with self.assertRaisesRegex(ContractError,'P4_J3_PRECOMMITMENT_REQUIRED'):
            self.run_inputs(self.inputs,variant='J3')
        labels={sc['scenario_id']:'declared' for sc in self.g['scenarios']}
        for variant,kwargs in [('J0',{}),('J2',{'role_sigma':.1,'efficiency_sigma':.08}),
            ('J3',{'enable_j3':True,'scenario_regimes':labels,'regime_multipliers':{'declared':1.1}})]:
            result=self.run_inputs(self.inputs,variant=variant,**kwargs)
            self.assertTrue(validate_integration(result['bundle'],self.p,self.g,self.o))

    def test_impossible_score_composite_and_excess_counts_reject(self):
        for stat in ('points','pra','threes','rebounds'):
            bad=reseal(self.result['bundle'],lambda b:b['scenarios'][0]['players'][0]['stats'].update({stat:9999}))
            with self.assertRaises(ContractError):
                validate_integration(bad,self.p,self.g,self.o)

    def test_adversarial_self_assist_excess_rebound_and_budget_ledgers(self):
        audit=self.result['audit_rows'][0]
        sc=self.result['bundle']['scenarios'][0]
        keys=('two_pa','two_pm','three_pa','threes','fta','ftm','oreb','dreb','assists')
        counts={k:np.array([x['stats'][k] for x in sc['players']],dtype=np.int64) for k in keys}
        ix=[[i for i,x in enumerate(sc['players']) if x['team_id']==team] for team in self.p['team_ids']]
        self.assertTrue(validate_event_ledger(counts,audit['event_ledger'],ix))
        mutations=[lambda l:l['assist_matrix'][0].__setitem__(0,1),
                   lambda l:l['rebounds'][0].update(credited=999999),
                   lambda l:l['rebounds'][0].update(fg_misses=999999),
                   lambda l:l['team_budgets'][0].update(two_pa=999999),
                   lambda l:l['unassisted'].__setitem__(0,999999)]
        for mutation in mutations:
            ledger=deepcopy(audit['event_ledger']);mutation(ledger)
            with self.assertRaises(ContractError):
                validate_event_ledger(counts,ledger,ix)

    def test_wrong_upstream_code_pin_rejects(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'nba_s_family/model.py';path.parent.mkdir();path.write_text('forged')
            with self.assertRaisesRegex(ContractError,'J_UPSTREAM_CODE_PIN_P2'):
                load_upstream(d)


if __name__ == '__main__':
    unittest.main()
