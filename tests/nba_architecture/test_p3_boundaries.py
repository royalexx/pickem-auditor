"""Synthetic adversarial source-boundary fixtures, never fitted real evidence."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_p3_o_family import inputs, build
from v2.nba_architecture.v2_contracts import ContractError, canonical, receipt, seal
from v2.nba_o_family import build_opportunity, validate_priors, validate_sidecar, freeze_outputs
from v2.nba_o_bridge import bind_p1_priors, espn_home_team, p1_history_context
from v2.nba_o_consumers import consumer_fixture, dispatch_scenarios, replay


def reseal(x, **changes):
    return seal(dict({k:v for k,v in x.items() if k!='content_hash'}, **changes))


def bound_inputs():
    p,g,priors=inputs()
    team=p['team_ids'][0]
    doc={'events':[{'id':p['game_id'].removeprefix('espn:game:'), 'competitions':[
        {'competitors':[{'homeAway':'home' if t==team else 'away',
                         'team':{'id':t.removeprefix('espn:team:')}} for t in p['team_ids']]}]}],
         'opportunity_priors':{pid:dict(player_id=pid, team_id=a['team_id'],
             prior={k:v for k,v in a.items() if k not in
                    ('source_snapshot_sha256','source_receipt_sha256','source_bindings')})
             for pid,a in priors.items()}}
    raw=canonical(doc)
    src=receipt(dict({k:v for k,v in p['sources'][0].items() if k!='receipt_sha256'},
                     raw_sha256=hashlib.sha256(raw).hexdigest()))
    old=p['sources'][0]['receipt_sha256']; new=src['receipt_sha256']
    p['sources'][0]=src
    for f in p['features']:
        if f['source_receipt_sha256']==old:f['source_receipt_sha256']=new
    for pid,a in priors.items():
        a['source_receipt_sha256']=new; a['source_bindings']=[new]
        body={k:v for k,v in a.items() if k!='source_snapshot_sha256'}
        p['features'].append(dict(p['features'][0], name='player:'+pid+':opportunity_prior',
            value=canonical(dict(player_id=pid,team_id=a['team_id'],prior=body)).decode(),
            kind='pregame_team_context', available_at=a['available_at']))
    p=reseal(p)
    for a in priors.values():a['source_snapshot_sha256']=p['content_hash']
    g=reseal(g,source_snapshot_sha256=p['content_hash'])
    return p,g,priors,{new:raw},new


class BoundaryTests(unittest.TestCase):
    def test_exact_raw_bound_complete_manifest(self):
        p,g,a,raw,r=bound_inputs()
        result=bind_p1_priors(p,a,raw_sources=raw,home_team_id=p['team_ids'][0],home_receipt=r)
        self.assertEqual(result['prior_manifest'],a)
        self.assertEqual(set(result['bindings']),set(a))
        self.assertEqual(espn_home_team(p,r,raw[r]),p['team_ids'][0])
        self.assertIn('NOT_AUTHENTICATED',result['certification'])

    def test_wrong_home_team_even_with_existing_hash(self):
        p,g,a=inputs()
        with self.assertRaisesRegex(ContractError,'O_HOME_TEAM_IDENTITY_UNPROVEN'):
            build_opportunity(p,g,a,model=g['model'],seed=1,home_team_id=p['team_ids'][1],
                              home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])

    def test_wrong_raw_home_team(self):
        p,g,a,raw,r=bound_inputs()
        p['features'][-13]['value']=p['team_ids'][1]  # home feature
        p=reseal(p)
        for row in a.values():row['source_snapshot_sha256']=p['content_hash']
        with self.assertRaisesRegex(ContractError,'O_HOME_TEAM_RAW_MISMATCH'):
            bind_p1_priors(p,a,raw_sources=raw,home_team_id=p['team_ids'][1],home_receipt=r)

    def test_incorrect_source_hash(self):
        p,g,a,raw,r=bound_inputs();raw[r]+=b' '
        with self.assertRaisesRegex(ContractError,'O_RAW_BYTES_MISMATCH'):
            bind_p1_priors(p,a,raw_sources=raw,home_team_id=p['team_ids'][0],home_receipt=r)

    def test_post_trade_identity_mismatch(self):
        p,g,a=inputs();next(iter(a.values()))['team_id']=p['team_ids'][1]
        with self.assertRaisesRegex(ContractError,'O_PRIOR_TEAM_MISMATCH'):
            validate_priors(p,a,variant='O1')

    def test_missing_roster_player(self):
        p,g,a=inputs();a.pop(next(iter(a)))
        with self.assertRaisesRegex(ContractError,'O_PRIOR_ROSTER_COVERAGE'):
            validate_priors(p,a,variant='O1')

    def test_postfreeze_injury_prior(self):
        p,g,a=inputs();next(iter(a.values()))['available_at']=p['event_start_at']
        with self.assertRaisesRegex(ContractError,'O_PRIOR_FUTURE_DATA'):
            validate_priors(p,a,variant='O1')

    def test_false_fit_certification(self):
        p,g,a=inputs();next(iter(a.values()))['participation_basis']='verified_pregame_fit'
        with self.assertRaisesRegex(ContractError,'O_INDEPENDENT_PARTICIPATION_ATTESTATION_REQUIRED'):
            validate_priors(p,a,variant='O1')

    def test_parameter_not_bound_to_feature(self):
        p,g,a,raw,r=bound_inputs();next(iter(a.values()))['scenario_participation_prior']=.2
        with self.assertRaisesRegex(ContractError,'O_PRIOR_RAW_CONTENT_MISMATCH'):
            bind_p1_priors(p,a,raw_sources=raw,home_team_id=p['team_ids'][0],home_receipt=r)

    def test_unknown_observation_and_callable_shared_draw(self):
        p,g,o,s=build('O2'); fixture=consumer_fixture(p,g,o,s)
        def consume_s(draw,sources):
            self.assertTrue(sources)
            self.assertTrue(all(x['observation_state']=='unknown' for x in draw['players']))
            return (draw['scenario_id'],draw['weight'])
        def consume_j(draw,kernels):
            self.assertEqual((draw['scenario_id'],draw['weight']),kernels)
            return draw['overtime_periods']
        rows=dispatch_scenarios(p,g,o,s,s_consumer=consume_s,j_consumer=consume_j)
        self.assertEqual(len(rows),len(fixture['scenarios']))

    def test_resealed_role_seed_and_manifest_tampering(self):
        p,g,o,s=build('O2')
        for field in ('role','seed','prior'):
            bad=copy.deepcopy(s)
            if field=='role':bad['scenarios'][0]['players'][0]['role_state']='invented'
            elif field=='seed':bad['seed']+=1
            else:
                bad['prior_manifest'][next(iter(bad['prior_manifest']))]['possession_intensity']=2
                from v2.nba_architecture.v2_contracts import digest
                bad['prior_sha256']=digest(bad['prior_manifest'])
            with self.subTest(field=field), self.assertRaisesRegex(ContractError,'O_REPLAY_MISMATCH'):
                replay(p,g,o,reseal(bad))

    def test_weight_ot_and_duplicate_player_tampering(self):
        p,g,o,s=build()
        for field in ('weight','ot','duplicate'):
            bad=copy.deepcopy(s)
            if field=='weight':bad['scenarios'][0]['weight']+=.1
            elif field=='ot':bad['scenarios'][0]['overtime_periods']=3
            else:bad['scenarios'][0]['players'].append(copy.deepcopy(bad['scenarios'][0]['players'][0]))
            with self.subTest(field=field),self.assertRaises(ContractError):
                validate_sidecar(reseal(bad),p,g,o)

    def test_unexpected_multiple_overtime_is_shared_and_conserving(self):
        p,g,a=inputs()
        for sc,ot in zip(g['scenarios'],(2,3)):
            sc['overtime_periods']=ot
            sc['possessions_home']+=10*ot;sc['possessions_away']+=10*ot
        g=reseal(g)
        o,s=build_opportunity(p,g,a,model=g['model'],seed=66,variant='O2',
            home_team_id=p['team_ids'][0],home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
        replay(p,g,o,s)
        for sc in o['scenarios']:
            for t in p['team_ids']:
                rows=[x for x in sc['players'] if x['team_id']==t]
                self.assertAlmostEqual(sum(x['minutes'] for x in rows),240+25*sc['overtime_periods'])
                self.assertLessEqual(max(x['minutes'] for x in rows),48+5*sc['overtime_periods'])

    def test_write_once_manifest_and_input_copy(self):
        p,g,o,s=build();original=copy.deepcopy(s)
        with tempfile.TemporaryDirectory() as folder:
            freeze_outputs(folder,p,g,o,s)
            path=Path(folder)/(s['content_hash']+'.json')
            raw=path.read_bytes()
            s['prior_manifest'][next(iter(s['prior_manifest']))]['scenario_participation_prior']=.1
            self.assertEqual(path.read_bytes(),raw)
            self.assertEqual(json.loads(raw),original)
            with self.assertRaises(ContractError):freeze_outputs(folder,p,g,o,s)


class ContextTests(unittest.TestCase):
    def test_historical_p1_is_explicit_abstention(self):
        from golden_v2 import pregame
        from v2.nba_o_bridge import build_p1_opportunity
        p=pregame('historical_reconstruction')
        result=build_p1_opportunity(p,None,{},raw_sources={},home_team_id=p['team_ids'][0],
                                   home_receipt=None,model=None,seed=0)
        self.assertEqual(result['reason'],'HISTORICAL_RECONSTRUCTION_UNCERTIFIED')
        self.assertTrue(all(x['participation_probability'] is None for x in result['context']['players'].values()))

    def test_context_preserves_rest_role_transactions_injury_uncertainty(self):
        p,g,a=inputs();pid=p['players'][0]['player_id']
        values={'role':'bench','rest_days':1,'back_to_back':True,
                'transaction':'trade pending eligibility','injury':'questionable',
                'uncertainty':'rotation unknown'}
        for field,value in values.items():
            p['features'].append(dict(p['features'][0],name='player:'+pid+':'+field,
                                      value=value,kind='pregame_team_context'))
        p=reseal(p);context=p1_history_context(p)['players'][pid]
        self.assertEqual({f['name'].split(':')[-1]:f['value'] for f in context['evidence']},values)
        self.assertIsNone(context['legal_eligibility'])
        self.assertEqual(context['observed_availability'],'unknown')

    def test_build_real_boundary_does_not_fall_back_when_bytes_missing(self):
        from v2.nba_o_bridge import build_p1_opportunity
        p,g,a,raw,r=bound_inputs()
        with self.assertRaisesRegex(ContractError,'O_RAW_SOURCE_REQUIRED'):
            build_p1_opportunity(p,g,a,raw_sources={},home_team_id=p['team_ids'][0],
                                 home_receipt=r,model=g['model'],seed=17)

    def test_source_bound_build_stays_shadow(self):
        from v2.nba_o_bridge import build_p1_opportunity
        p,g,a,raw,r=bound_inputs()
        result=build_p1_opportunity(p,g,a,raw_sources=raw,home_team_id=p['team_ids'][0],
                                   home_receipt=r,model=g['model'],seed=17)
        replay(p,g,result['opportunity'],result['sidecar'])
        self.assertEqual(result['status'],'SHADOW_NOT_CERTIFIED')
        self.assertTrue(all(x['participation_probability'] is None for x in result['opportunity']['players']))


class AdditionalAdversarialTests(unittest.TestCase):
    def test_offer_receipt_cannot_support_participation(self):
        p,g,a=inputs();row=next(iter(a.values()))
        row['source_bindings'].append(p['sources'][1]['receipt_sha256'])
        with self.assertRaisesRegex(ContractError,'O_PRIOR_SOURCE_SCOPE'):
            validate_priors(p,a,variant='O1')

    def test_postfreeze_actual_injury_feature_rejected_by_p1_boundary(self):
        from v2.nba_architecture.v2_contracts import validate_pregame
        p,g,a=inputs()
        p['features'].append(dict(p['features'][0],name='player:espn:player:10:injury',
                                 kind='pregame_availability',value='out',
                                 available_at=p['event_start_at']))
        with self.assertRaises(ContractError):validate_pregame(reseal(p))

    def test_individual_opportunity_cannot_be_redistributed_while_total_is_same(self):
        p,g,o,s=build();bad=copy.deepcopy(s)
        rows=bad['scenarios'][0]['players']
        rows[0]['projected_possession_opportunity']+=1
        rows[1]['projected_possession_opportunity']-=1
        with self.assertRaisesRegex(ContractError,'O_PLAYER_POSSESSION_JOIN'):
            validate_sidecar(reseal(bad),p,g,o)

    def test_p4_reversed_home_order_fails_before_calling_owner(self):
        from v2.nba_o_consumers import call_p4
        p,g,a=inputs()
        next(f for f in p['features'] if f['name']=='home_team_id')['value']=p['team_ids'][1]
        p=reseal(p);g=reseal(g,source_snapshot_sha256=p['content_hash'])
        for row in a.values():row['source_snapshot_sha256']=p['content_hash']
        o,s=build_opportunity(p,g,a,model=g['model'],seed=1,home_team_id=p['team_ids'][1],
            home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
        with self.assertRaisesRegex(ContractError,'O_P4_HOME_ORDER_ADAPTER_REQUIRED'):
            call_p4(p,g,o,s,simulate=lambda *args: self.fail('owner should not be called'),
                    conditional_rates={})

    def test_unknown_dnp_and_played_zero_are_distinct(self):
        def change(a):
            a['espn:player:15']['scenario_participation_prior']=0.
            a['espn:player:25']['scenario_participation_prior']=1.
            a['espn:player:25']['played_zero_probability']=1.
        p,g,o,s=build(change=change)
        for sc in o['scenarios']:
            players={x['player_id']:x for x in sc['players']}
            self.assertEqual(players['espn:player:15']['participation'],'DNP')
            self.assertEqual(players['espn:player:25']['participation'],'PLAYED_ZERO_MINUTES')
            self.assertEqual(players['espn:player:15']['minutes'],0.)
            self.assertEqual(players['espn:player:25']['minutes'],0.)
        self.assertTrue(all(x['participation_evidence']=='unknown' for x in o['players']))
        self.assertTrue(all(x['observation_state']=='unknown' for x in
                            consumer_fixture(p,g,o,s)['scenarios'][0]['players']))
