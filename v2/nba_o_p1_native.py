"""Versioned P3 consumer of P1's native, explicitly unadmitted transport.

Raw binding is checked independently of P1's derived fields. No evidence label,
hash, candidate subset or numeric participation guess can enable certification.
This module performs no sampling and imports no outcome vault or model fitter.
"""
import base64
from copy import deepcopy
import hashlib
import json
from urllib.parse import urlsplit

from v2.nba_architecture.v2_contracts import digest, instant, req, seal, validate_pregame
from v2.nba_o_bridge import _document

VERSION = 'nba-p3-p1-native-consumer/1.0.0'
P1_VERSION = 'nba-p1-native-handoff/1.0.0'
MISSING = [
    'INDEPENDENT_SOURCE_ADMISSION', 'COMPLETE_ORIGINAL_PREGAME_ROSTER',
    'DATED_MEMBERSHIP_EVIDENCE', 'SOURCE_BOUND_HOME_IDENTITY',
    'SOURCE_BOUND_ROLE_EVIDENCE', 'ADMISSIBLE_PARTICIPATION_AND_MINUTE_PRIORS',
]


def consume_p1_context(export, *, frozen_pregame):
    """Validate actual P1 transport and stop at its first missing prerequisite.

    Original source admission, complete roster, dated membership, role/home and
    fitted priors are unavailable in P1 v1.0.0. A future admission API requires
    its own independently reviewed version; callers cannot assert one here.
    """
    p = frozen_pregame
    validate_pregame(p)
    req(isinstance(export, dict) and set(export) == {
        'schema','kind','profile','source_profile','admission_status','missing_requirements',
        'game_id','team_ids','event_start_at','input_freeze_at','home_team_id',
        'home_identity_evidence','players','sources','roster_completeness',
        'candidate_denominator','source_context_status'}, 'O_P1_NATIVE_FIELDS')
    req(export['schema'] == P1_VERSION and export['kind'] == 'pregame_context_export',
        'O_P1_NATIVE_VERSION')
    req(export['game_id'] == p['game_id'] and set(export['team_ids']) == set(p['team_ids'])
        and len(export['team_ids']) == 2 and
        instant(export['event_start_at']) == instant(p['event_start_at']) and
        instant(export['input_freeze_at']) == instant(p['input_freeze_at']),
        'O_P1_NATIVE_TARGET_JOIN')
    req(export['profile'] == export['source_profile'] == 'unadmitted_adapter_export' and
        export['admission_status'] == 'BLOCKED' and export['missing_requirements'] == MISSING,
        'O_P1_NATIVE_UNSUPPORTED_ADMISSION')
    req(export['home_team_id'] is None and export['home_identity_evidence'] is None and
        export['roster_completeness'] == {'status':'UNPROVEN','proof_references':[]},
        'O_P1_NATIVE_UNPROVEN_POPULATION')
    req(isinstance(export['sources'], list) and isinstance(export['players'], list),
        'O_P1_NATIVE_SOURCE_POPULATION')
    freeze = instant(p['input_freeze_at'])
    raw_players = {}
    for source in export['sources']:
        req(isinstance(source, dict) and set(source) == {'provider_url','raw_sha256',
            'raw_base64','hash_domain','origin','admission_basis','admission_status','clocks'},
            'O_P1_NATIVE_SOURCE_FIELDS')
        provider = urlsplit(source['provider_url'])
        req(provider.scheme == 'https' and provider.netloc in
            ('www.nba.com','cdn.nba.com','official.nba.com','site.api.espn.com'),
            'O_P1_NATIVE_PROVIDER_IDENTITY')
        req(source['hash_domain'] == 'EXACT_SUPPLIED_EXPORT_BYTES_NOT_ORIGINAL_PROVIDER_HTTP'
            and source['origin'] == 'original_capture' and source['admission_basis'] is None
            and source['admission_status'] == 'REVIEW_REQUIRED',
            'O_P1_NATIVE_SOURCE_NOT_ADMITTED')
        try:
            raw = base64.b64decode(source['raw_base64'], validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError('O_P1_NATIVE_RAW_BASE64') from exc
        req(hashlib.sha256(raw).hexdigest() == source['raw_sha256'],
            'O_P1_NATIVE_RAW_SHA')
        clocks = source['clocks']
        req(isinstance(clocks, dict) and set(clocks) == {'provider_published_at',
            'first_defensible_available_at','adapter_asserted_available_at',
            'collector_observed_at','retrieved_at','ingested_at'},
            'O_P1_NATIVE_CLOCK_FIELDS')
        req(clocks['provider_published_at'] is None and clocks['retrieved_at'] is None and
            clocks['first_defensible_available_at'] is None,
            'O_P1_NATIVE_UNPROVEN_CLOCK_ASSERTION')
        observed = instant(clocks['collector_observed_at'])
        available = instant(clocks['adapter_asserted_available_at'])
        req(observed <= available <= freeze and instant(clocks['ingested_at']) >= available,
            'O_P1_NATIVE_POSTFREEZE_OR_BACKDATED')
        doc = _document(raw)
        req(set(doc) == {'schema','assertions'} and doc['schema'] == 'nba-p1-dated-context/1.0.0'
            and isinstance(doc['assertions'], list), 'O_P1_NATIVE_RAW_EXPORT_SCHEMA')
        for a in doc['assertions']:
            req(isinstance(a, dict) and set(a) == {'kind','game_id','player_id','team_id',
                'effective_at','legal_eligibility','availability'} and a['kind'] == 'pregame_roster',
                'O_P1_NATIVE_RAW_ASSERTION_FIELDS')
            pid = a['player_id']
            req(isinstance(pid, str) and ':' in pid and pid not in raw_players and
                a['game_id'] == p['game_id'] and a['team_id'] in p['team_ids'],
                'O_P1_NATIVE_RAW_IDENTITY')
            req(instant(a['effective_at']) <= freeze and
                (a['legal_eligibility'] is None or type(a['legal_eligibility']) is bool) and
                a['availability'] in ('unknown','available','out','questionable','limited'),
                'O_P1_NATIVE_RAW_STATE_OR_CLOCK')
            raw_players[pid] = dict(player_id=pid, team_id=a['team_id'],
                legal_eligibility=a['legal_eligibility'], observed_availability=a['availability'],
                availability_evidence=dict(raw_sha256=source['raw_sha256'],
                    available_at=clocks['adapter_asserted_available_at'],
                    status='UNADMITTED_ASSERTION'),
                membership=None,role=None,role_evidence=None,role_uncertainty='UNKNOWN',
                participation_probability=None,participation_authentication=None)
    expected = [raw_players[pid] for pid in sorted(raw_players)]
    req(export['players'] == expected, 'O_P1_NATIVE_RAW_SUMMARY_MISMATCH')
    roster = {r['player_id']:r for r in p['players']}
    req(all(pid in roster and roster[pid]['team_id'] == row['team_id']
            for pid,row in raw_players.items()), 'O_P1_NATIVE_PREGAME_ROSTER_JOIN')
    req(export['candidate_denominator'] == dict(observed_candidates=len(expected),
        complete_population=None,admitted=0), 'O_P1_NATIVE_DENOMINATOR')
    req(export['source_context_status'] == ('SOURCE_BOUND_REQUIRES_INDEPENDENT_REVIEW'
        if expected else 'BLOCKED_NO_AUTHENTICATED_PREGAME_CONTEXT'), 'O_P1_NATIVE_CONTEXT_STATUS')
    return seal(dict(schema=VERSION, kind='p3_native_input_abstention', status='BLOCKED',
        reason=MISSING[0], missing_requirements=list(MISSING),
        source_snapshot_sha256=p['content_hash'], p1_export_sha256=digest(export),
        p1_export=deepcopy(export),players=deepcopy(expected),
        roster_completeness=deepcopy(export['roster_completeness']),
        source_status='BYTES_BOUND_AUTHENTICITY_UNADMITTED',
        original_http_bytes_authenticated=False, scenario_generation='NOT_ATTEMPTED'))
