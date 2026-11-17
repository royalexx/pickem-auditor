"""Versioned P3/P4 source-backed identity and pregame-context handoff.

Consumes immutable assertions exported by a reviewed source adapter, not final
box scores. Exact raw bytes MUST themselves contain the assertion list. This
interface verifies binding/timing; it cannot authenticate a caller's collector.
It is deliberately separate from the G0 historical candidate-only envelope.
"""
import hashlib
from urllib.parse import urlsplit
from .p1_history import fail, _strict_json
from .v2_contracts import instant

VERSION = 'nba-p1-dated-context/1.0.0'


def _assertions(bundle, cutoff):
    if set(bundle) != {'source_url', 'raw', 'raw_sha256', 'observed_at', 'available_at', 'origin'}:
        fail('CONTEXT_SOURCE_FIELDS')
    u = urlsplit(bundle['source_url'])
    if u.scheme != 'https' or u.netloc not in ('www.nba.com', 'cdn.nba.com', 'official.nba.com', 'site.api.espn.com'):
        fail('CONTEXT_SOURCE_IDENTITY')
    if not isinstance(bundle['raw'], bytes) or hashlib.sha256(bundle['raw']).hexdigest() != bundle['raw_sha256']:
        fail('CONTEXT_SOURCE_SHA_MISMATCH')
    if bundle['origin'] != 'original_capture':
        fail('CONTEXT_ORIGINAL_PREGAME_CAPTURE_REQUIRED')
    observed, available = instant(bundle['observed_at']), instant(bundle['available_at'])
    if observed > available or available > instant(cutoff):
        fail('CONTEXT_POST_FREEZE_OR_BACKDATED')
    raw = _strict_json(bundle['raw'])
    if set(raw) != {'schema', 'assertions'} or raw['schema'] != VERSION or not isinstance(raw['assertions'], list):
        fail('CONTEXT_REVIEWED_ASSERTION_EXPORT_REQUIRED')
    return raw['assertions']


def resolve_dated_identity(provider_id, kind, at, bundles, *, input_freeze_at):
    """Exact namespaced crosswalk, effective [from,to), observed before freeze.

    Missing/overlapping mappings block. Team membership changes require dated
    source evidence; a player's next box score is never transaction evidence.
    """
    matches = []
    for b in bundles:
        for a in _assertions(b, input_freeze_at):
            if set(a) != {'kind', 'provider_id', 'canonical_id', 'valid_from', 'valid_to'}:
                fail('IDENTITY_ASSERTION_FIELDS')
            if a['kind'] not in ('player', 'team', 'game', 'membership'):
                fail('IDENTITY_ASSERTION_KIND')
            if a['kind'] != kind or a['provider_id'] != provider_id:
                continue
            for k in ('provider_id','canonical_id'):
                if not isinstance(a[k],str) or a[k].strip()!=a[k] or ':' not in a[k]:
                    fail('CONTEXT_NONCANONICAL_ID')
            start = instant(a['valid_from'])
            end = instant(a['valid_to']) if a['valid_to'] is not None else None
            if end is not None and end <= start:
                fail('IDENTITY_EFFECTIVE_INTERVAL')
            if start <= instant(at) and (end is None or instant(at) < end):
                matches.append(dict(canonical_id=a['canonical_id'], raw_sha256=b['raw_sha256']))
    if len(matches) != 1:
        fail('DATED_IDENTITY_MISSING_OR_AMBIGUOUS')
    return dict(schema=VERSION, **matches[0], source_status='SOURCE_BOUND_AUTHENTICITY_REVIEW_REQUIRED')


def pregame_candidates(*, game_id, team_ids, event_start_at, input_freeze_at, bundles):
    """Roster membership, eligibility and availability without outcome access.

    No bundles => explicit unknown / BLOCKED, never inferred eligibility.
    This export schema is an adapter interface; no historical NBA source in the
    legacy warehouse currently supplies these authenticated assertions.
    """
    if instant(input_freeze_at) >= instant(event_start_at) or len(set(team_ids)) != 2:
        fail('CONTEXT_EVENT_CLOCK_OR_TEAMS')
    players = {}
    for b in bundles:
        for a in _assertions(b, input_freeze_at):
            if set(a) != {'kind','game_id','player_id','team_id','effective_at','legal_eligibility','availability'} or a['kind'] != 'pregame_roster':
                fail('PREGAME_CONTEXT_OUTCOME_OR_FIELDS')
            if a['game_id'] != game_id or a['team_id'] not in team_ids:
                fail('PREGAME_CONTEXT_IDENTITY')
            if instant(a['effective_at']) > instant(input_freeze_at):
                fail('TRADE_OR_ROSTER_NOT_YET_EFFECTIVE')
            if a['legal_eligibility'] is not None and type(a['legal_eligibility']) is not bool:
                fail('CONTEXT_ELIGIBILITY')
            if a['availability'] not in ('unknown','available','out','questionable','limited'):
                fail('CONTEXT_AVAILABILITY')
            pid = a['player_id']
            if not isinstance(pid,str) or ':' not in pid or pid in players:
                fail('CONTEXT_DUPLICATE_OR_PLAYER_IDENTITY')
            players[pid] = dict(player_id=pid,team_id=a['team_id'],
                legal_eligibility=a['legal_eligibility'],availability=a['availability'],
                raw_sha256=b['raw_sha256'],available_at=b['available_at'])
    return dict(schema=VERSION, game_id=game_id, players=[players[k] for k in sorted(players)],
                status='SOURCE_BOUND_REQUIRES_INDEPENDENT_REVIEW' if players else 'BLOCKED_NO_AUTHENTICATED_PREGAME_CONTEXT',
                certification='HISTORICAL_RECONSTRUCTION_UNCERTIFIED')
