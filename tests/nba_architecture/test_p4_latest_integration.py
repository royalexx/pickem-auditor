"""Versioned latest P2/P3 native handoff and proposed uncertainty law controls."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from research.nba_p4_latest.fixture import build
from research.nba_p4_latest.numerical_reference import references
from test_p4_joint import PARAMETERS, reseal
from v2.nba_architecture.v2_contracts import ContractError, digest
from v2.nba_architecture.families_v2 import validate_integration
from v2.nba_joint.integration import validate_event_ledger
from v2.nba_joint.integration_v2 import (LAW_PROPOSAL, draw_mixing_rate,
    simulate_latest, validate_artifacts, validate_event_counts)
from v2.nba_joint.latest_upstream import FIXTURES, REGISTRY, load_upstream, prepare, registry
from v2.nba_joint.p4 import scenario_pmfs


class LatestIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = prepare()
        cls.inputs = build(cls.root)
        cls.result = cls.run_inputs(cls.inputs)

    @classmethod
    def run_inputs(cls, inputs, **kwargs):
        return simulate_latest(*inputs, upstream_root=cls.root,
            evidence_mode='latest_synthetic_engineering', event_parameters=PARAMETERS,
            seed=kwargs.pop('seed',42), **kwargs)

    def reject(self, inputs):
        with self.assertRaises(ContractError):
            self.run_inputs(inputs)

    def changed(self, index, mutate):
        data = list(self.inputs)
        data[index] = reseal(data[index], mutate)
        return data

    def test_actual_latest_producers_and_complete_lineage(self):
        p,g,o,side,artifacts,manifest,roles = self.inputs
        p2,p3=load_upstream(self.root)
        self.assertEqual(side['schema'],'nba-p3-opportunity/0.2.0')
        self.assertTrue(all(isinstance(a,p2.FittedS) for a in artifacts.values()))
        self.assertTrue(p3.validate_sidecar(side,p,g,o))
        self.assertTrue(validate_integration(self.result['bundle'],p,g,o))
        self.assertEqual(self.result['integration_manifest']['owner_registry'],registry())
        self.assertEqual(self.result['input_shas']['O_sidecar'],side['content_hash'])
        self.assertEqual(self.result['integration_manifest']['independent_acceptance'],'PENDING')
        self.assertIn('PENDING_INDEPENDENT_ACCEPTANCE',self.result['status'])

    def test_real_mode_remains_unavailable_despite_verified_tokens(self):
        self.assertTrue(all(s['status']=='P1_VERIFIED' for s in self.inputs[5].values()))
        with self.assertRaisesRegex(ContractError,'INDEPENDENT_SOURCE_AND_FIT_ADMISSION_REQUIRED'):
            simulate_latest(*self.inputs,upstream_root=self.root,event_parameters=PARAMETERS)

    def test_all_owner_executable_bytes_pinned_not_only_model(self):
        for owner,path in [('P2','v2/nba_s_family/integration.py'),
                           ('P3','v2/nba_o_bridge.py'),('P3','v2/nba_o_family.py')]:
            with self.subTest(owner=owner,path=path),tempfile.TemporaryDirectory() as d:
                root=prepare(d)
                (root/owner/path).write_bytes(b'corrupted executable')
                with self.assertRaisesRegex(ContractError,'J2_UPSTREAM_CODE_PIN_'+owner):
                    load_upstream(root)

    def test_immutable_artifact_byte_corruption_or_resealed_parameters_reject(self):
        p2,_=load_upstream(self.root)
        for change in [lambda a:a.update(training_cutoff_at='2026-11-16T22:00:00Z'),
                       lambda a:a['training_rows'][0].update(game_id=self.inputs[0]['game_id']),
                       lambda a:a['training_rows'][0].update(count=99999)]:
            artifacts=dict(self.inputs[4]);a=artifacts['points'].data;change(a)
            artifacts['points']=p2.FittedS(p2.canonical(a))
            x=list(self.inputs);x[4]=artifacts;self.reject(x)

    def test_prior_fixture_artifacts_remain_preserved_and_fail_current_code_pin(self):
        p2,_=load_upstream(self.root)
        original=FIXTURES.parent/'fixtures'/'points.json'
        old=p2.FittedS(original.read_bytes())
        self.assertNotEqual(old.data['code_sha256'],self.inputs[4]['points'].data['code_sha256'])
        x=list(self.inputs);x[4]=dict(x[4]);x[4]['points']=old
        self.reject(x)

    def test_dated_historical_team_role_change_is_valid_without_rewriting_history(self):
        from research.nba_p4_latest.post_trade_fixture import create
        with tempfile.TemporaryDirectory() as d:
            profile=Path(d)/'new_synthetic_profile';inputs=create(self.root,profile)
            with patch('v2.nba_joint.integration_v2.FIXTURES',profile):
                result=self.run_inputs(inputs)
            self.assertTrue(validate_integration(result['bundle'],*inputs[:3]))
            old=inputs[4]['points'].data['training_rows'][0]
            self.assertEqual(old['team_id'],'espn:team:former')
            self.assertEqual(old['role'],'previous_role')
            current=next(x for x in inputs[0]['players'] if x['player_id']==old['player_id'])
            self.assertNotEqual(current['team_id'],old['team_id'])
            # Wrong dated membership still rejects even in this explicitly
            # synthetic profile; current target identity is not a substitute.
            bad=list(inputs);bad[5]=deepcopy(inputs[5])
            bad[5][old['source_receipt_sha256']]['games'][old['game_id']]['players'][old['player_id']]='espn:team:wrong'
            with patch('v2.nba_joint.integration_v2.FIXTURES',profile):self.reject(bad)

    def test_raw_sources_and_ancestor_population_cannot_self_hash(self):
        for name in ('raw_sources.json','context.raw'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as d:
                folder=Path(d);shutil.copytree(FIXTURES,folder/'fixture')
                target=folder/'fixture'/name
                target.write_bytes(target.read_bytes()+b'corrupted')
                with patch('v2.nba_joint.integration_v2.FIXTURES',folder/'fixture'):
                    self.reject(self.inputs)

    def test_source_manifest_corruption_or_postcutoff_clock_reject(self):
        for change in [lambda s:s.update(raw_sha256='0'*64),
                       lambda s:s.update(available_at=self.inputs[0]['input_freeze_at'])]:
            x=list(self.inputs);x[5]=deepcopy(x[5]);change(next(iter(x[5].values())))
            self.reject(x)

    def test_roles_and_roster_wrong_identity_reject(self):
        x=list(self.inputs);x[6]=dict(x[6]);x[6][next(iter(x[6]))]='invented_role';self.reject(x)
        for change in [lambda p:p['players'][0].update(player_id='espn:player:invented'),
                       lambda p:p['players'][0].update(team_id=p['team_ids'][1])]:
            self.reject(self.changed(0,change))

    def test_false_participation_certificate_is_rejected_by_actual_p3(self):
        with self.assertRaisesRegex(ContractError,'INDEPENDENT_PARTICIPATION_ATTESTATION_REQUIRED'):
            build(self.root,special=lambda priors:next(iter(priors.values())).update(
                participation_basis='verified_pregame_fit'))

    def test_g_o_scenario_identity_and_weight_attack(self):
        for idx in (1,2,3):
            for key,value in [('scenario_id','synthetic:wrong'),('weight',.9)]:
                self.reject(self.changed(idx,lambda x:x['scenarios'][0].update({key:value})))

    def test_impossible_minutes_or_missing_five_on_floor_reject(self):
        self.reject(self.changed(2,lambda o:o['scenarios'][0]['players'][0].update(minutes=999.)))
        team=self.inputs[0]['team_ids'][0]
        self.reject(self.changed(3,lambda side:side['scenarios'][0]['teams'][team][
            'lineup_segments'][0].update(player_indices=[0,1,2,3])))

    def test_resealed_balanced_role_and_possession_share_tampering_rejects(self):
        def mutate(side):
            a,b=side['scenarios'][0]['players'][:2]
            a['possession_share']+=.01;b['possession_share']-=.01
            team=self.inputs[0]['players'][0]['team_id']
            pool=side['scenarios'][0]['teams'][team]['projected_possessions']
            a['projected_possession_opportunity']=pool*a['possession_share']
            b['projected_possession_opportunity']=pool*b['possession_share']
        self.reject(self.changed(3,mutate))

    def test_exact_o_draws_weights_and_all_same_draw_combinations(self):
        p,g,o,*_=self.inputs
        for sc,upstream in zip(self.result['bundle']['scenarios'],o['scenarios']):
            self.assertEqual(sc['scenario_id'],upstream['scenario_id'])
            self.assertEqual(sc['weight'],upstream['weight'])
            for x,y in zip(sc['players'],upstream['players']):
                for key in ('player_id','team_id','minutes','participation'):
                    self.assertEqual(x[key],y[key])
                s=x['stats']
                for combo,parts in [('pr',('points','rebounds')),('pa',('points','assists')),
                    ('ra',('rebounds','assists')),('pra',('points','rebounds','assists'))]:
                    self.assertEqual(s[combo],sum(s[k] for k in parts))

    def test_full_p2_law_uncertainty_reaches_kernel_not_only_audit(self):
        other=self.run_inputs(self.inputs,seed=43)
        self.assertNotEqual(self.result['scenario_hashes'],other['scenario_hashes'])
        for audit in self.result['audit_rows']:
            self.assertEqual(audit['integration']['law_contract'],LAW_PROPOSAL)
            self.assertTrue(audit['integration']['posterior_or_dispersion_rate_uncertainty_propagated'])
            for row in audit['integration']['P2_to_J_projection'].values():
                self.assertEqual(row['rate_pair_attempts'],len(row['rejected_rate_pairs'])+1)
                self.assertGreaterEqual(row['sampled_mixing_rates']['points'],
                                        3*row['sampled_mixing_rates']['threes'])
                for law in row['conditional_laws'].values():
                    self.assertAlmostEqual(sum(x['mass'] for x in law['pmf']),1.)
                    self.assertLessEqual(law['tail_mass_upper_bound'],1e-11)

    def test_s1_s2_mixing_distribution_moments(self):
        params={'alpha':2.75,'beta':25.,'dispersion':4.,'rate_mean':.11}
        for family,variance in [('S1',2.75/25**2),('S2',.11**2/4.)]:
            rng=np.random.default_rng(100)
            rates=np.array([draw_mixing_rate(params,family,rng) for _ in range(20000)])
            self.assertAlmostEqual(float(rates.mean()),.11,delta=.003)
            self.assertAlmostEqual(float(rates.var()),variance,delta=.0003)

    def test_independent_quadrature_and_exact_incompatibility_bounds(self):
        refs=references()
        # The CLI must emit strict JSON; NumPy scalar booleans are not JSON.
        json.dumps(refs,allow_nan=False)
        self.assertTrue(refs['all_pass'])
        self.assertAlmostEqual(refs['conditioning_distortion_reference']['acceptance'],5/32)
        self.assertGreater(refs['exact_marginal_incompatibility'][
            'minimum_sum_of_marginal_TV_distortions'],.55)

    def test_s3_integer_projected_attempts_make_and_accounting(self):
        for audit,sc in zip(self.result['audit_rows'],self.result['bundle']['scenarios']):
            for draw in audit['event_ledger']['S3_projected_attempts']:
                self.assertIs(type(draw['projected_three_pa']),int)
                self.assertLessEqual(draw['made_threes'],draw['projected_three_pa'])
            for player in sc['players']:
                s=player['stats']
                self.assertEqual(s['points'],2*s['two_pm']+3*s['threes']+s['ftm'])
                self.assertLessEqual(s['threes'],s['three_pa'])
                self.assertLessEqual(s['ftm'],s['fta'])

    def test_shooting_assist_rebound_and_same_draw_corruption_rejects(self):
        p,g,o,*_=self.inputs
        for stat in ('points','threes','rebounds','assists','pra'):
            bad=reseal(self.result['bundle'],lambda b:b['scenarios'][0]['players'][0][
                'stats'].update({stat:99999}))
            with self.assertRaises(ContractError):validate_integration(bad,p,g,o)
        audit=self.result['audit_rows'][0];sc=self.result['bundle']['scenarios'][0]
        keys=('two_pa','two_pm','three_pa','threes','fta','ftm','oreb','dreb','assists')
        counts={k:np.array([x['stats'][k] for x in sc['players']]) for k in keys}
        ix=[[i for i,x in enumerate(sc['players']) if x['team_id']==team] for team in p['team_ids']]
        ledger=deepcopy(audit['event_ledger']);ledger['assist_matrix'][0][0]+=1
        with self.assertRaises(ContractError):validate_event_ledger(counts,ledger,ix)
        ledger=deepcopy(audit['event_ledger']);ledger['rebounds'][0]['available']+=1
        with self.assertRaises(ContractError):validate_event_ledger(counts,ledger,ix)

    def test_complete_normalized_pmf_equals_manual_weighted_counts(self):
        pmfs=scenario_pmfs(self.result,self.inputs[0],frozen_at='2026-11-16T23:03:00Z')
        for pid,stats in pmfs.items():
            for stat,law in stats.items():
                expected={}
                for sc in self.result['bundle']['scenarios']:
                    value=next(p['stats'][stat] for p in sc['players'] if p['player_id']==pid)
                    expected[value]=expected.get(value,0.)+sc['weight']
                self.assertEqual({r['value']:r['mass'] for r in law['pmf'] if r['mass']},expected)
                self.assertAlmostEqual(sum(r['mass'] for r in law['pmf']),1.)

    def test_complete_raw_event_count_guard_and_valid_positive_control(self):
        sc=self.result['bundle']['scenarios'][0]
        ledger=self.result['audit_rows'][0]['event_ledger']
        keys=('two_pa','two_pm','three_pa','threes','fta','ftm','points','oreb','dreb','rebounds','assists')
        counts={k:np.array([x['stats'][k] for x in sc['players']],dtype=np.int64) for k in keys}
        ix=[[i for i,x in enumerate(sc['players']) if x['team_id']==team] for team in self.inputs[0]['team_ids']]
        self.assertTrue(validate_event_counts(counts,ledger,ix))
        for stat,value in [('points',int(counts['points'][0])+1),('rebounds',int(counts['rebounds'][0])+1),
                           ('two_pa',-1),('ftm',999999)]:
            bad={k:v.copy() for k,v in counts.items()};bad[stat][0]=value
            with self.assertRaises(ContractError):validate_event_counts(bad,ledger,ix)

    def test_dictionary_order_and_repeat_replay(self):
        def reverse(x):
            if isinstance(x,dict):return {k:reverse(v) for k,v in reversed(list(x.items()))}
            if isinstance(x,list):return [reverse(v) for v in x]
            return x
        x=[reverse(v) if isinstance(v,dict) else v for v in self.inputs]
        other=self.run_inputs(x)
        self.assertEqual(other['scenario_hashes'],self.result['scenario_hashes'])
        self.assertEqual(other['audit_rows'],self.result['audit_rows'])

    def test_cross_process_python_hash_seed_replay(self):
        code="""import json
from research.nba_p4_latest.fixture import build
from v2.nba_joint.latest_upstream import prepare
from v2.nba_joint.integration_v2 import simulate_latest
from test_p4_joint import PARAMETERS
r=prepare();x=simulate_latest(*build(r),upstream_root=r,evidence_mode='latest_synthetic_engineering',event_parameters=PARAMETERS,seed=42)
print(json.dumps(x['scenario_hashes'],sort_keys=True))
"""
        outputs=[]
        for seed in ('3','8357'):
            env=dict(os.environ,PYTHONHASHSEED=seed,PYTHONPATH='.:tests/nba_architecture',OPENBLAS_NUM_THREADS='1')
            outputs.append(subprocess.check_output([sys.executable,'-c',code],env=env,text=True))
        self.assertEqual(outputs[0],outputs[1])

    def test_actual_stochastic_o2_n32_immutable_budget_still_blocks(self):
        with self.assertRaisesRegex(ContractError,'O_COUPLING_VERIFICATION_BUDGET'):
            build(self.root,n=32,variant='O2')

    def test_actual_stochastic_o2_n8_positive_operating_control(self):
        inputs=build(self.root,n=8,variant='O2')
        result=self.run_inputs(inputs)
        self.assertEqual(len(result['bundle']['scenarios']),8)
        self.assertTrue(validate_integration(result['bundle'],*inputs[:3]))
        self.assertAlmostEqual(sum(x['weight'] for x in result['bundle']['scenarios']),1.)

    def test_legal_eleven_ot_current_owner_contract_has_no_arbitrary_100_minute_cap(self):
        from v2.nba_architecture.v2_contracts import seal
        p,g,*_=self.inputs
        data=json.loads((FIXTURES/'inputs.json').read_bytes())
        high=deepcopy(g);high.pop('content_hash')
        high['scenarios']=[dict(high['scenarios'][0],overtime_periods=11,weight=1.)]
        high=seal(high)
        _,p3=load_upstream(self.root)
        priors=deepcopy(data['priors'])
        o,side=p3.build_opportunity(p,high,priors,model=data['O_model'],seed=17,variant='O2',
            home_team_id=p['team_ids'][0],home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
        x=[p,high,o,side,*self.inputs[4:]]
        result=self.run_inputs(x)
        self.assertEqual(result['bundle']['scenarios'][0]['overtime_periods'],11)
        p2,_=load_upstream(self.root)
        direct=p2.predict_conditional(self.inputs[4]['points'],
            player_id=p['players'][0]['player_id'],role=self.inputs[6][p['players'][0]['player_id']],
            projected_exposure=103.,statistic='points')
        self.assertIsNone(direct.abstain_reason)

    def test_latest_dnp_played_zero_and_early_exit_total_cap_remain_distinct(self):
        for status in ('DNP','PLAYED_ZERO_MINUTES'):
            def change(priors):
                for pid in ('espn:player:15','espn:player:25'):
                    priors[pid]['scenario_participation_prior']=0. if status=='DNP' else 1.
                    priors[pid]['played_zero_probability']=1. if status=='PLAYED_ZERO_MINUTES' else 0.
            inputs=build(self.root,special=change);result=self.run_inputs(inputs)
            for sc in result['bundle']['scenarios']:
                for row in sc['players']:
                    if row['player_id'] in ('espn:player:15','espn:player:25'):
                        self.assertEqual(row['participation'],status)
                        self.assertEqual(row['minutes'],0.)
                        self.assertTrue(all(value==0 for value in row['stats'].values()))
        inputs=build(self.root,special=lambda priors:priors['espn:player:10'].update(
            early_exit_probability=1.))
        result=self.run_inputs(inputs)
        for sc in result['bundle']['scenarios']:
            player=next(x for x in sc['players'] if x['player_id']=='espn:player:10')
            self.assertLessEqual(player['minutes'],.25*(48+5*sc['overtime_periods'])+1e-9)
        self.assertEqual(result['integration_manifest']['physical_chronology'],
                         'AGGREGATE_ONLY_NOT_EVENT_TIME_OR_TIED_OT')

    def test_rate_budget_failure_preserves_every_rejected_pair_and_denominator(self):
        # Forced branch coverage only; ordinary positive execution uses actual P2.
        with patch('v2.nba_joint.integration_v2.draw_mixing_rate',return_value=1.):
            with self.assertRaises(ContractError) as exc:self.run_inputs(self.inputs)
        receipt=exc.exception.failure_receipt
        self.assertEqual(exc.exception.code,'J2_RATE_COMPATIBILITY_EXHAUSTED')
        self.assertEqual(receipt['rate_pair_attempts'],4096)
        self.assertEqual(receipt['rejected_pair_count'],4096)
        self.assertEqual(len(receipt['rejected_rate_pairs']),4096)
        self.assertEqual(receipt['accepted_pair_count'],0)
        self.assertEqual(receipt['rejected_pairs_sha256'],digest(receipt['rejected_rate_pairs']))
        self.assertEqual(receipt['seed'],42)
        self.assertEqual(receipt['input_shas']['O'],self.inputs[2]['content_hash'])
        json.dumps(receipt,allow_nan=False)

    def test_tied_event_exhaustion_preserves_raw_draws_and_no_success_bundle(self):
        n=len(self.inputs[0]['players'])
        keys=('two_pa','two_pm','three_pa','threes','fta','ftm','points','oreb','dreb','rebounds','assists')
        counts={k:np.zeros(n,dtype=np.int64) for k in keys}
        ledger={'assist_matrix':np.zeros((n,n),dtype=np.int64).tolist(),'unassisted':[0,0],
            'team_budgets':[{k:0 for k in ('two_pa','two_pm','three_pa','threes','fta','ftm')} for _ in range(2)],
            'rebounds':[{k:0 for k in ('fg_misses','terminal_ft','available','credited','offensive','defensive','unattributed')} for _ in range(2)]}
        # Forced zero-score kernel branch; never substituted for green integration.
        with patch('v2.nba_joint.integration_v2.LegacyPrepared.sample_events',
                   return_value=(counts,ledger)):
            with self.assertRaises(ContractError) as exc:self.run_inputs(self.inputs,max_event_attempts=2)
        receipt=exc.exception.failure_receipt
        self.assertEqual(exc.exception.code,'P4_TIED_COMPLETED_GAME_EXHAUSTED')
        self.assertEqual(receipt['event_attempts'],2)
        self.assertEqual(receipt['rejected_tied_event_draws'],2)
        self.assertEqual(receipt['accepted_event_draws'],0)
        self.assertEqual(len(receipt['event_draws_by_scenario'][receipt['scenario_id']]),2)
        self.assertEqual(receipt['status'],'FAILED_NO_J_RESULT_PUBLISHED')

    def test_repeated_seed_runner_persists_failure_without_partial_success_claim(self):
        from research.nba_p4_latest import repeated_seeds
        error=ContractError('SYNTHETIC_FORCED_FAILURE')
        error.failure_receipt={'error_code':error.code,'rate_pair_attempts':4096,
                               'rejected_pair_count':4096}
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'failed_run'
            with patch.object(repeated_seeds,'simulate_latest',side_effect=error):
                with self.assertRaises(ContractError):repeated_seeds.run(output)
            receipt=json.loads((output/'failed_execution_receipt.json').read_bytes())
            self.assertEqual(receipt['completed_prefix_seed_count'],0)
            self.assertEqual(receipt['failure_receipt']['rate_pair_attempts'],4096)
            self.assertFalse((output/'summary.json').exists())


if __name__=='__main__':unittest.main()
