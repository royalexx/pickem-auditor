"""P3-owned source boundary. P1 authenticates sources; hashes prove byte binding only.

No model is fitted here. Missing pregame evidence causes abstention. Historical
P1 prior-boxscore features remain usable as uncertified history, never a roster.
"""
from copy import deepcopy
import hashlib
import json

from v2.nba_architecture.v2_contracts import (
    canonical, digest, instant, req, seal, validate_pregame,
)


def _document(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            req(key not in result, 'O_SOURCE_DUPLICATE_JSON_KEY')
            result[key]=value
        return result
    def constant(_):
        req(False, 'O_SOURCE_NONFINITE_JSON')
    obj=json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
    req(isinstance(obj,dict), 'O_SOURCE_DOCUMENT_REQUIRED')
    return obj


def home_binding(p, team, receipt):
    matches = [f for f in p['features'] if f['name'] == 'home_team_id'
               and f['kind'] == 'schedule' and f['source_receipt_sha256'] == receipt]
    req(len(matches) == 1 and matches[0]['value'] == team,
        'O_HOME_TEAM_IDENTITY_UNPROVEN')
    return matches[0]


def source_bytes(p, receipt_hash, raw):
    sources = [s for s in p['sources'] if s['receipt_sha256'] == receipt_hash]
    req(len(sources) == 1, 'O_SOURCE_RECEIPT_REQUIRED')
    source = sources[0]
    req(isinstance(raw, bytes) and hashlib.sha256(raw).hexdigest() == source['raw_sha256'],
        'O_RAW_BYTES_MISMATCH')
    return source


def espn_home_team(p, receipt_hash, raw):
    """Read ESPN scoreboard/header competitors from exact P1-receipted bytes.

    Identity only: no athletes, box scores, scores or target minutes are read.
    This does not manufacture a new P1 snapshot or authenticate ESPN's origin.
    """
    validate_pregame(p)
    source = source_bytes(p, receipt_hash, raw)
    req(source['scope'] == 'pregame_context', 'O_SCHEDULE_SCOPE')
    data = _document(raw)
    events = data.get('events', [data.get('header', data)])
    event = [e for e in events if 'espn:game:' + str(e.get('id')) == p['game_id']]
    req(len(event) == 1, 'O_SCHEDULE_GAME_IDENTITY')
    competitions = event[0].get('competitions', [])
    req(len(competitions) == 1, 'O_SCHEDULE_COMPETITION')
    competitors = competitions[0].get('competitors', [])
    ids = {'espn:team:' + str(c.get('team', {}).get('id')) for c in competitors}
    home = [c for c in competitors if c.get('homeAway') == 'home']
    req(ids == set(p['team_ids']) and len(home) == 1, 'O_SCHEDULE_TEAM_IDENTITY')
    return 'espn:team:' + str(home[0]['team']['id'])


def p1_history_context(p):
    """Preserve source-supported prior participation, role and team evidence.

    Never converts prior team membership to legal target-game eligibility.
    Rest/B2B are accepted only as original pregame features, never derived from
    an eventual schedule or a target box score. Absence stays null/unknown.
    """
    validate_pregame(p)
    fields = ('participation', 'minutes', 'starter', 'historical_team_id',
              'prior_game_id', 'role', 'rest_days', 'back_to_back',
              'transaction', 'injury', 'uncertainty')
    rows = {}
    for player in p['players']:
        pid = player['player_id']
        selected = [deepcopy(f) for f in p['features']
                    if any(f['name'] == 'player:' + pid + ':' + k for k in fields)]
        rows[pid] = dict(team_id=player['team_id'], legal_eligibility=player['legal_eligibility'],
                         observed_availability=player['availability'],
                         participation_probability=None, observation_state='unknown',
                         evidence=selected)
    return seal(dict(kind='p3_p1_context', source_snapshot_sha256=p['content_hash'],
                     certification=p['certification'], players=rows))


def bind_p1_priors(p, priors, *, raw_sources, home_team_id, home_receipt):
    """Verify bytes, complete roster and original P1 feature-to-prior bindings.

    P1 exports each prior as canonical JSON in player:<id>:opportunity_prior.
    P1 owns authentication and fitting attestations; this adapter deliberately
    makes no independent-fit claim. Existing P1 historical exports do not have
    these fields and return explicit abstention instead of invented parameters.
    """
    from v2.nba_o_family import validate_priors
    validate_pregame(p)
    if p['source_profile'] == 'historical_reconstruction':
        return seal(dict(kind='p3_input_abstention', source_snapshot_sha256=p['content_hash'],
                         reason='HISTORICAL_RECONSTRUCTION_UNCERTIFIED',
                         context=p1_history_context(p)))
    validate_priors(p, priors, variant='O1')
    home_binding(p, home_team_id, home_receipt)
    req(isinstance(raw_sources, dict) and home_receipt in raw_sources,
        'O_RAW_SOURCE_REQUIRED')
    req(espn_home_team(p, home_receipt, raw_sources[home_receipt]) == home_team_id,
        'O_HOME_TEAM_RAW_MISMATCH')
    bindings = {}
    for player in p['players']:
        pid = player['player_id']; prior = priors[pid]
        receipt = prior['source_receipt_sha256']
        req(receipt in raw_sources, 'O_RAW_SOURCE_REQUIRED')
        source = source_bytes(p, receipt, raw_sources[receipt])
        req(source['scope'] == 'pregame_context', 'O_PRIOR_CONTEXT_SOURCE_REQUIRED')
        matches = [f for f in p['features']
                   if f['name'] == 'player:' + pid + ':opportunity_prior']
        req(len(matches) == 1, 'O_P1_PRIOR_FEATURE_REQUIRED')
        f = matches[0]
        # Snapshot hash is intentionally excluded from the embedded prior to
        # avoid a circular content hash. Team identity is explicit in the value.
        body = {k:v for k,v in prior.items() if k != 'source_snapshot_sha256'}
        expected = dict(player_id=pid, team_id=player['team_id'], prior=body)
        document = _document(raw_sources[receipt])
        req(set(document.get('opportunity_priors', {})) == set(priors),
            'O_RAW_PRIOR_ROSTER_COVERAGE')
        raw_expected = dict(player_id=pid, team_id=player['team_id'],
                            prior={k:v for k,v in body.items() if k not in
                                   ('source_receipt_sha256', 'source_bindings')})
        req(document.get('opportunity_priors', {}).get(pid) == raw_expected,
            'O_PRIOR_RAW_CONTENT_MISMATCH')
        req(f['value'] == canonical(expected).decode() and
            f['source_receipt_sha256'] == receipt and
            f['available_at'] == prior['available_at'], 'O_P1_PRIOR_BINDING')
        req(instant(prior['available_at']) >= max(instant(source[k]) for k in
            ('collector_observed_at', 'retrieved_at', 'ingested_at')), 'O_PRIOR_BACKDATED')
        bindings[pid] = digest(f)
    return seal(dict(kind='p3_bound_inputs', source_snapshot_sha256=p['content_hash'],
                     certification='SHADOW_SOURCE_BYTES_BOUND_NOT_AUTHENTICATED',
                     prior_manifest=deepcopy(priors), prior_sha256=digest(priors),
                     bindings=bindings, context=p1_history_context(p)))


def build_p1_opportunity(p, g, priors, *, raw_sources, home_team_id,
                         home_receipt, model, seed, variant='O1'):
    """Real-source entrypoint: source binding precedes any scenario generation.

    Returns a sealed abstention when original historical evidence is absent.
    Raw bytes must come from P1's existing immutable capture, not a new fetch.
    """
    from v2.nba_o_family import build_opportunity
    bound = bind_p1_priors(p, priors, raw_sources=raw_sources,
                          home_team_id=home_team_id, home_receipt=home_receipt)
    if bound['kind'] == 'p3_input_abstention':
        return bound
    o, sidecar = build_opportunity(p,g,priors,model=model,seed=seed,variant=variant,
        home_team_id=home_team_id, home_team_source_receipt_sha256=home_receipt)
    return seal(dict(kind='p3_bound_opportunity', input_binding=bound,
                     opportunity=o, sidecar=sidecar, status='SHADOW_NOT_CERTIFIED'))
