"""P1 native engineering transport, with no source-admission authority.

Exact raw bytes and unknown evidence survive handoffs. Hash/URL consistency is
not authentication. These exports cannot admit a real roster, source or fitted
prior. Outcome export requires an explicitly injected isolated vault; pregame
entrypoints never import or access the vault.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from .p1_history import fail
from .p1_evidence import _capture, prior_game_exposure
from .p1_context import pregame_candidates
from .v2_contracts import canonical, instant

VERSION = 'nba-p1-native-handoff/1.0.0'
PROFILES = frozenset({'unadmitted_source_reconstruction', 'synthetic_engineering'})


def _profile(value):
    if value not in PROFILES:
        fail('HANDOFF_UNSUPPORTED_SOURCE_PROFILE')
    return value


def _pack(bundle):
    return dict(capture=dict(bundle['capture']),
                raw_base64=base64.b64encode(bundle['raw']).decode('ascii'),
                prior=[_pack(x) for x in bundle['prior']])


def decode_evidence_bundle(value):
    """Decode and recheck all original bytes/ancestors; never authenticate them."""
    def unpack(node):
        if not isinstance(node, dict) or set(node) != {'capture','raw_base64','prior'} or not isinstance(node['prior'], list):
            fail('HANDOFF_EVIDENCE_FIELDS')
        try:
            raw=base64.b64decode(node['raw_base64'],validate=True)
        except (ValueError,TypeError) as exc:
            raise ValueError('HANDOFF_INVALID_BASE64') from exc
        return dict(capture=node['capture'],raw=raw,prior=[unpack(x) for x in node['prior']])
    result=unpack(value)
    _capture(result)
    return result


def export_prior_game(data, bundle, *, ingested_at,
                      source_profile='unadmitted_source_reconstruction'):
    """Transport a prior row; authenticity/outcome release/roles stay missing.

    No model fitting, training cutoff inference or pregame timestamp backfill
    occurs. Even a positive byte-consistency check leaves admission BLOCKED.
    """
    profile=_profile(source_profile)
    exposure=prior_game_exposure(data,bundle)
    game=_capture(bundle)
    retrieved=bundle['capture']['retrieved_at']
    if instant(ingested_at)<instant(retrieved):
        fail('HANDOFF_INGESTION_BEFORE_RETRIEVAL')
    return dict(schema=VERSION,kind='prior_game_export',profile=profile,
        source_profile=profile,admission_status='BLOCKED',
        missing_requirements=['INDEPENDENT_SOURCE_ADMISSION',
            'ORIGINAL_OR_FIRST_DEFENSIBLE_AVAILABILITY',
            'SOURCE_BOUND_OUTCOME_RELEASE_CLOCK','DATED_ROLE_EVIDENCE'],
        evidence_bundle=_pack(bundle),exposure=exposure,
        game_start_at=game['gameTimeUTC'],
        clocks=dict(provider_published_at=None,first_defensible_available_at=None,
                    collector_observed_at=None,retrieved_at=retrieved,
                    ingested_at=ingested_at,outcome_available_at=None),
        role=None,role_evidence=None,
        uncertainty=dict(participation=exposure['participation'],
                         source_admission='UNKNOWN',role='UNKNOWN'),
        candidate_denominator=dict(attempted=1,admitted=0,quarantined=1))


def export_pregame_context(*, game_id, team_ids, event_start_at,
                           input_freeze_at, bundles, ingested_at):
    """Transport reviewed-export-shaped assertions without claiming admission.

    The currently supplied source population proves no complete pregame roster,
    dated membership, source-bound home or fitted participation. Explicit nulls
    and UNPROVEN completeness prevent a candidate subset becoming a full roster.
    """
    # Both assertion evaluation and byte transport traverse this population.
    # A one-shot iterator would otherwise lose all raw bundles on the latter.
    if not isinstance(bundles, (list, tuple)):
        fail('HANDOFF_CONTEXT_BUNDLES')
    context=pregame_candidates(game_id=game_id,team_ids=team_ids,
        event_start_at=event_start_at,input_freeze_at=input_freeze_at,bundles=bundles)
    sources=[]
    for b in bundles:
        if instant(ingested_at)<max(instant(b['observed_at']),instant(b['available_at'])):
            fail('HANDOFF_INGESTION_BEFORE_SOURCE')
        sources.append(dict(provider_url=b['source_url'],raw_sha256=b['raw_sha256'],
            raw_base64=base64.b64encode(b['raw']).decode('ascii'),
            hash_domain='EXACT_SUPPLIED_EXPORT_BYTES_NOT_ORIGINAL_PROVIDER_HTTP',
            origin=b['origin'],admission_basis=None,admission_status='REVIEW_REQUIRED',
            clocks=dict(provider_published_at=None,
                first_defensible_available_at=None,
                adapter_asserted_available_at=b['available_at'],
                collector_observed_at=b['observed_at'],retrieved_at=None,
                ingested_at=ingested_at)))
    players=[]
    for p in context['players']:
        players.append(dict(player_id=p['player_id'],team_id=p['team_id'],
            legal_eligibility=p['legal_eligibility'],
            observed_availability=p['availability'],
            availability_evidence=dict(raw_sha256=p['raw_sha256'],available_at=p['available_at'],
                                       status='UNADMITTED_ASSERTION'),
            membership=None,role=None,role_evidence=None,role_uncertainty='UNKNOWN',
            participation_probability=None,participation_authentication=None))
    return dict(schema=VERSION,kind='pregame_context_export',
        profile='unadmitted_adapter_export',source_profile='unadmitted_adapter_export',
        admission_status='BLOCKED',missing_requirements=[
            'INDEPENDENT_SOURCE_ADMISSION','COMPLETE_ORIGINAL_PREGAME_ROSTER',
            'DATED_MEMBERSHIP_EVIDENCE','SOURCE_BOUND_HOME_IDENTITY',
            'SOURCE_BOUND_ROLE_EVIDENCE','ADMISSIBLE_PARTICIPATION_AND_MINUTE_PRIORS'],
        game_id=game_id,team_ids=list(team_ids),event_start_at=event_start_at,
        input_freeze_at=input_freeze_at,home_team_id=None,
        home_identity_evidence=None,players=players,sources=sources,
        roster_completeness=dict(status='UNPROVEN',proof_references=[]),
        candidate_denominator=dict(observed_candidates=len(players),
                                   complete_population=None,admitted=0),
        source_context_status=context['status'])


def export_outcome(vault, game_id, player_id):
    """Read isolated immutable vault versions, preserving every missing clock.

    An observed-at receipt is not an official release/end clock. No scoring
    permission follows from an export. The consumer must independently admit
    sources and source-bound event/end/release clocks before evaluation.
    """
    all_rows=vault.records()
    rows=sorted([r for r in all_rows if r['game_id']==game_id and r['player_id']==player_id],key=lambda r:r['revision'])
    revisions=[]
    event_start=None
    for row in rows:
        raw=(Path(vault.root)/(row['content_hash']+'.json')).read_bytes()
        source=(Path(vault.root)/'sources'/(row['source_raw_sha256']+'.raw')).read_bytes()
        if raw != canonical(row)+b'\n' or hashlib.sha256(source).hexdigest()!=row['source_raw_sha256']:
            fail('HANDOFF_VAULT_BYTES_CHANGED')
        evidence=None
        if row.get('accounting_evidence') is not None:
            bundle=vault._load_evidence(row['accounting_evidence'])
            game=_capture(bundle)
            if event_start is not None and instant(event_start)!=instant(game['gameTimeUTC']):
                fail('HANDOFF_VAULT_EVENT_START_CONFLICT')
            event_start=game['gameTimeUTC']
            evidence=_pack(bundle)
        revisions.append(dict(record=row,
            record_raw_sha256=hashlib.sha256(raw).hexdigest(),
            record_raw_base64=base64.b64encode(raw).decode('ascii'),
            source_raw_sha256=row['source_raw_sha256'],
            source_raw_base64=base64.b64encode(source).decode('ascii'),
            accounting_evidence=evidence))
    latest=rows[-1] if rows else None
    exact=None
    if latest and latest.get('accounting_evidence') is not None:
        bundle=vault._load_evidence(latest['accounting_evidence'])
        game=_capture(bundle)
        other=next('nba:team:'+str(game[k]['teamId']) for k in ('homeTeam','awayTeam')
                   if 'nba:team:'+str(game[k]['teamId'])!=latest['team_id'])
        from .p1_evidence import duration
        d=duration(bundle,game_id=game_id)
        ex=prior_game_exposure(dict(game_id=game_id,player_id=player_id,
            team_id=latest['team_id'],opponent_id=other,game_date=d['game_date'],
            minutes=latest['minutes'],stats=latest['stats'],
            participation='played' if latest['state'] in ('PLAYED','PLAYED_ZERO_MINUTES')
                          else 'dnp' if latest['state']=='DNP' else 'unknown'),bundle)
        exact=ex['exact_minutes']
    return dict(schema=VERSION,kind='outcome_export',game_id=game_id,player_id=player_id,
        team_id=latest['team_id'] if latest else None,
        source_profile='unadmitted_isolated_outcome_vault',admission_status='BLOCKED',
        missing_requirements=['INDEPENDENT_SOURCE_ADMISSION','SOURCE_BOUND_EVENT_END',
                              'SOURCE_BOUND_OUTCOME_RELEASE_CLOCK']+
                             ([] if latest else ['OFFICIAL_OUTCOME_MISSING']),
        status='UNADMITTED' if latest else 'UNRESOLVED',
        participation=latest['state'] if latest else 'UNRESOLVED',
        stats=dict(latest['stats']) if latest else {},official_count=None,
        displayed_minutes=latest['minutes'] if latest else None,exact_minutes=exact,
        event_start_at=event_start,event_end_at=None,outcome_released_at=None,
        vault_schema=latest['schema'] if latest else None,revisions=revisions,
        correction_version=latest['revision'] if latest else None,
        scoring_authorized=False)
