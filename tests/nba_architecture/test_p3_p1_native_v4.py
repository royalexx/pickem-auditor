"""P1 native transport boundary; all bytes are declared synthetic exports."""
import base64
from copy import deepcopy
import hashlib
import unittest

from test_p3_o_family import inputs
from v2.nba_architecture.v2_contracts import canonical, ContractError
from v2.nba_o_p1_native import consume_p1_context


def native_fixture():
    p, _, _ = inputs()
    person = p['players'][0]
    assertion = dict(kind='pregame_roster', game_id=p['game_id'],
        player_id=person['player_id'], team_id=person['team_id'],
        effective_at=p['input_freeze_at'], legal_eligibility=None, availability='unknown')
    raw = canonical(dict(schema='nba-p1-dated-context/1.0.0', assertions=[assertion]))
    sha = hashlib.sha256(raw).hexdigest()
    at = p['input_freeze_at']
    source = dict(provider_url='https://site.api.espn.com/synthetic-reviewed-export',
        raw_sha256=sha, raw_base64=base64.b64encode(raw).decode(),
        hash_domain='EXACT_SUPPLIED_EXPORT_BYTES_NOT_ORIGINAL_PROVIDER_HTTP',
        origin='original_capture', admission_basis=None, admission_status='REVIEW_REQUIRED',
        clocks=dict(provider_published_at=None, first_defensible_available_at=None,
                    adapter_asserted_available_at=at,
                    collector_observed_at=at, retrieved_at=None, ingested_at=at))
    row = dict(player_id=person['player_id'], team_id=person['team_id'],
        legal_eligibility=None, observed_availability='unknown',
        availability_evidence=dict(raw_sha256=sha, available_at=at, status='UNADMITTED_ASSERTION'),
        membership=None, role=None, role_evidence=None, role_uncertainty='UNKNOWN',
        participation_probability=None, participation_authentication=None)
    export = dict(schema='nba-p1-native-handoff/1.0.0', kind='pregame_context_export',
        profile='unadmitted_adapter_export',source_profile='unadmitted_adapter_export',
        admission_status='BLOCKED', missing_requirements=[
            'INDEPENDENT_SOURCE_ADMISSION', 'COMPLETE_ORIGINAL_PREGAME_ROSTER',
            'DATED_MEMBERSHIP_EVIDENCE', 'SOURCE_BOUND_HOME_IDENTITY',
            'SOURCE_BOUND_ROLE_EVIDENCE', 'ADMISSIBLE_PARTICIPATION_AND_MINUTE_PRIORS'],
        game_id=p['game_id'], team_ids=p['team_ids'], event_start_at=p['event_start_at'],
        input_freeze_at=at, home_team_id=None, home_identity_evidence=None,
        players=[row], sources=[source],
        roster_completeness=dict(status='UNPROVEN',proof_references=[]),
        candidate_denominator=dict(observed_candidates=1,complete_population=None,admitted=0),
        source_context_status='SOURCE_BOUND_REQUIRES_INDEPENDENT_REVIEW')
    return p, export


class NativeP1Boundary(unittest.TestCase):
    def test_exact_bound_native_candidates_preserve_unknown_and_block(self):
        p, export = native_fixture()
        result = consume_p1_context(export, frozen_pregame=p)
        self.assertEqual(result['status'], 'BLOCKED')
        self.assertEqual(result['reason'], 'INDEPENDENT_SOURCE_ADMISSION')
        self.assertEqual(result['p1_export'], export)
        self.assertIsNone(result['players'][0]['participation_probability'])
        self.assertEqual(result['roster_completeness']['status'], 'UNPROVEN')

    def test_forged_admission_and_false_participation_reject(self):
        for mutate in (lambda x:x.update(admission_status='PASS'),
                       lambda x:x['sources'][0].update(admission_status='VERIFIED'),
                       lambda x:x['players'][0].update(participation_probability=.8),
                       lambda x:x['roster_completeness'].update(status='COMPLETE')):
            p, export = native_fixture(); mutate(export)
            with self.assertRaises(ContractError):
                consume_p1_context(export, frozen_pregame=p)

    def test_corrupt_raw_or_resealed_summary_does_not_pass(self):
        for mutate in (lambda x:x['sources'][0].update(raw_base64=base64.b64encode(b'{}').decode()),
                       lambda x:x['players'][0].update(team_id='espn:team:wrong'),
                       lambda x:x['players'][0].update(observed_availability='available'),
                       lambda x:x['candidate_denominator'].update(observed_candidates=99)):
            p, export = native_fixture(); mutate(export)
            with self.assertRaises(ContractError):
                consume_p1_context(export, frozen_pregame=p)

    def test_postfreeze_and_wrong_target_identity_reject(self):
        for mutate in (lambda x:x.update(game_id='espn:game:wrong'),
                       lambda x:x['sources'][0]['clocks'].update(adapter_asserted_available_at='2099-01-01T00:00:00Z')):
            p, export = native_fixture(); mutate(export)
            with self.assertRaises(ContractError):
                consume_p1_context(export, frozen_pregame=p)

    def test_missing_population_is_explicit_and_no_sampling_occurs(self):
        p, export = native_fixture()
        export['sources']=[];export['players']=[]
        export['candidate_denominator']['observed_candidates']=0
        export['source_context_status']='BLOCKED_NO_AUTHENTICATED_PREGAME_CONTEXT'
        result = consume_p1_context(export, frozen_pregame=p)
        self.assertEqual(result['reason'], 'INDEPENDENT_SOURCE_ADMISSION')
        self.assertEqual(result['players'], [])
        self.assertEqual(result['scenario_generation'], 'NOT_ATTEMPTED')
