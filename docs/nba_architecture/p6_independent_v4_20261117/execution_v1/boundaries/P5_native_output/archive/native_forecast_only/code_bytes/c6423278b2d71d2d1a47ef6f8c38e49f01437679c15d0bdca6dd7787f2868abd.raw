"""Latest-owner native integration, with an explicit proposed constrained law.

This module does not amend G0 or admit real sources. The proposed rate mixing
law is a separately versioned engineering experiment. Physical chronology
remains an independent-review prerequisite; aggregate accounting is explicit.
"""
from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np

from v2.nba_architecture.v2_contracts import ContractError, digest, instant, req, seal
from v2.nba_architecture.families_v2 import validate_opportunity
from v2.nba_joint.common import rng_for
from v2.nba_joint.integration import (_Prepared as LegacyPrepared,
    validate_event_ledger as validate_aggregate_ledger)
from v2.nba_joint.latest_upstream import FIXTURES, REGISTRY, ROOT, load_upstream, raw_sha, registry
from v2.nba_joint.p4 import _simulate_p4, PRIMITIVES

VERSION = 'NBA-P2-P3-to-J/2.0.0'
LAW_PROPOSAL = 'NBA-J-CONSTRAINED-LATENT-RATE/0.1.0-PROPOSAL'
RATE_REJECTION_LIMIT = 4096


def validate_event_counts(counts, ledger, ix):
    """Independent complete event-count checks in addition to old budgets.

    G0 already checks the final bundle; this also closes the narrower audit
    seam before publishing raw event-ledger evidence.
    """
    keys = {'two_pa','two_pm','three_pa','threes','fta','ftm','points',
            'oreb','dreb','rebounds','assists'}
    req(isinstance(counts,dict) and set(counts)==keys, 'J2_EVENT_COUNT_SCHEMA')
    arrays = {k:np.asarray(v) for k,v in counts.items()}
    n = len(arrays['points']) if arrays['points'].ndim==1 else 0
    req(n>0 and all(v.ndim==1 and len(v)==n and np.issubdtype(v.dtype,np.integer)
        and np.all(v>=0) for v in arrays.values()), 'J2_EVENT_COUNT_SUPPORT')
    req(isinstance(ix,list) and len(ix)==2 and all(isinstance(x,list) for x in ix)
        and all(type(i) is int for x in ix for i in x) and
        sorted(i for x in ix for i in x)==list(range(n)), 'J2_TEAM_INDEX_POPULATION')
    req(all(np.all(arrays[made]<=arrays[attempt]) for made,attempt in
        [('two_pm','two_pa'),('threes','three_pa'),('ftm','fta')]), 'J2_MAKES_EXCEED_ATTEMPTS')
    req(np.array_equal(arrays['points'],2*arrays['two_pm']+3*arrays['threes']+arrays['ftm'])
        and np.array_equal(arrays['rebounds'],arrays['oreb']+arrays['dreb']),
        'J2_EVENT_COUNT_ARITHMETIC')
    req(isinstance(ledger,dict) and isinstance(ledger.get('assist_matrix'),list),
        'J2_ASSIST_MATRIX_SCHEMA')
    matrix=np.asarray(ledger['assist_matrix'])
    req(matrix.shape==(n,n) and np.issubdtype(matrix.dtype,np.integer) and np.all(matrix>=0),
        'J2_ASSIST_MATRIX_SUPPORT')
    return validate_aggregate_ledger(arrays,ledger,ix)


def validate_artifacts(p, artifacts, manifest, roles, *, evidence_mode):
    req(evidence_mode == 'latest_synthetic_engineering',
        'J2_REAL_BLOCKED_INDEPENDENT_SOURCE_AND_FIT_ADMISSION_REQUIRED')
    trust = json.loads((FIXTURES / 'trust.json').read_bytes())
    req(trust['basis'] == 'synthetic_engineering_only' and
        trust['source_authentication'] is False, 'J2_TRUST_PROFILE')
    req(p['game_id'].startswith('espn:game:synthetic-') and
        p['content_hash'] == trust['pregame_sha256'], 'J2_SYNTHETIC_PREGAME_PIN')
    req(isinstance(manifest, dict) and digest(manifest) == trust['source_manifest_sha256'],
        'J2_SOURCE_MANIFEST_PIN')
    req(isinstance(roles, dict) and digest(roles) == trust['roles_sha256'] and
        set(roles) == {r['player_id'] for r in p['players']}, 'J2_ROSTER_ROLE_PIN')
    raw_bytes = (FIXTURES / 'raw_sources.json').read_bytes()
    req(raw_sha(raw_bytes) == trust['raw_sources_sha256'], 'J2_RAW_SOURCE_COLLECTION_PIN')
    raw_sources = json.loads(raw_bytes)
    req(set(raw_sources) == set(manifest), 'J2_RAW_SOURCE_POPULATION')
    for key, source in manifest.items():
        req(raw_sha(raw_sources[key].encode('ascii')) == source['raw_sha256'],
            'J2_RAW_SOURCE_BYTES')
    context = (FIXTURES / 'context.raw').read_bytes()
    req(raw_sha(context) == trust['context_raw_sha256'] and
        p['sources'][0]['raw_sha256'] == raw_sha(context), 'J2_CONTEXT_RAW_BYTES')
    req(isinstance(artifacts, dict) and set(artifacts) == set(PRIMITIVES) | {'three_conversion'},
        'J2_ARTIFACT_COVERAGE')
    cutoff, freeze = instant(p['training_cutoff_at']), instant(p['input_freeze_at'])
    req(cutoff <= freeze, 'J2_DECLARED_CUTOFF_AFTER_FREEZE')
    model_sha = registry()['owners']['P2']['files']['v2/nba_s_family/model.py']
    for stat, fitted in artifacts.items():
        req(hasattr(fitted, 'payload') and type(fitted.payload) is bytes,
            'J2_IMMUTABLE_FITTED_ARTIFACT')
        req(raw_sha(fitted.payload) == trust['artifacts'][stat], 'J2_ARTIFACT_BYTES_PIN')
        a = fitted.data
        expected_stat = 'threes' if stat == 'three_conversion' else stat
        req(a['code_sha256'] == model_sha and a['stat'] == expected_stat and
            a['family'] in (('S3',) if stat == 'three_conversion' else ('S1','S2')),
            'J2_ARTIFACT_CODE_FAMILY_STAT')
        req(instant(a['training_cutoff_at']) <= cutoff, 'J2_MODEL_AFTER_DECLARED_CUTOFF')
        used = {k: manifest[k] for k in a['source_receipts'] if k in manifest}
        req(digest(used) == a['source_manifest_sha256'], 'J2_ARTIFACT_MANIFEST_JOIN')
        for row in a['training_rows']:
            req(row['game_id'] != p['game_id'] and
                instant(row['game_start_at']) < instant(a['training_cutoff_at']) and
                instant(row['outcome_available_at']) <= instant(a['training_cutoff_at']),
                'J2_TARGET_OR_POSTCUTOFF_TRAINING')
            source = used.get(row['source_receipt_sha256'])
            req(source is not None and source['raw_sha256'] == row['source_raw_sha256'] and
                instant(row['outcome_available_at']) <= instant(source['available_at']) <=
                instant(a['training_cutoff_at']), 'J2_TRAINING_SOURCE_CLOCK_OR_HASH')
            game = source.get('games', {}).get(row['game_id'])
            req(game is not None and game['players'].get(row['player_id']) == row['team_id'],
                'J2_TRAINING_MEMBERSHIP')
            duration_source = used.get(game['duration_receipt_sha256'])
            req(duration_source is not None and
                instant(duration_source['available_at']) <= instant(a['training_cutoff_at']) and
                0 <= row['minutes'] <= 48 + 5 * game['overtime_periods'],
                'J2_TRAINING_DURATION_WITNESS')
        for player in p['players']:
            own = [r for r in a['training_rows'] if r['player_id'] == player['player_id']]
            # Historical team and role are dated training observations. Their
            # source-bound membership above must not be replaced by today's
            # team/role, which are independently pinned in the target roster.
            req(bool(own), 'J2_PLAYER_HISTORY_MISSING')
    return True


def draw_mixing_rate(parameters, family, rng):
    """The exact nonnegative mixing law underlying the actual P2 count PMF."""
    req(family in ('S1','S2'), 'J2_UNSUPPORTED_MIXING_FAMILY')
    if family == 'S1':
        shape, scale = parameters['alpha'], 1. / parameters['beta']
    else:
        shape = parameters['dispersion']
        scale = parameters['rate_mean'] / shape
    req(math.isfinite(shape) and shape > 0 and math.isfinite(scale) and scale >= 0,
        'J2_MIXING_PARAMETERS')
    return float(rng.gamma(shape, scale)) if scale else 0.


class Prepared(LegacyPrepared):
    def __init__(self, p, g, o, sidecar, artifacts, manifest, roles, p2, seed):
        self.p, self.g, self.o, self.sidecar = p, g, o, sidecar
        self.artifacts, self.roles, self.p2, self.seed = artifacts, roles, p2, seed
        self.home_team_id = sidecar['home_team_id']
        self._audits, self._sid = {}, None
        self._event_draws, self._current_player_audits = {}, {}
        self.manifest = {'version': VERSION, 'owner_registry': registry(),
            'owner_registry_raw_sha256': raw_sha(REGISTRY.read_bytes()),
            'consumer_code_files': {path: raw_sha((ROOT/path).read_bytes()) for path in (
                'v2/nba_joint/integration_v2.py', 'v2/nba_joint/latest_upstream.py',
                'v2/nba_joint/integration.py', 'v2/nba_joint/p4.py',
                'v2/nba_joint/events.py', 'v2/nba_joint/common.py')},
            'artifacts': {k: raw_sha(a.payload) for k,a in artifacts.items()},
            'source_manifest_sha256': digest(manifest), 'roles_sha256': digest(roles),
            'sidecar_sha256': sidecar['content_hash'], 'law_contract': LAW_PROPOSAL,
            'independent_acceptance': 'PENDING', 'real_integration': 'BLOCKED',
            'evidence_mode': 'latest_synthetic_engineering',
            'law_mapping': 'P2-Gamma-mixing-conditioned-on-point-three-rate-compatibility-then-WS5',
            'physical_chronology': 'AGGREGATE_ONLY_NOT_EVENT_TIME_OR_TIED_OT',
            'rate_rejection_limit': RATE_REJECTION_LIMIT,
            'conditioning': 'P3-feasible-rotation;rate-compatibility;completed-score-not-tied'}

    def failure_receipt(self, code, **witness):
        return seal({'schema':'NBA-J-failed-execution/1.0.0','status':'FAILED_NO_J_RESULT_PUBLISHED',
            'error_code':code,'game_id':self.p['game_id'],'scenario_id':self._sid,'seed':self.seed,
            'input_shas':{'pregame':self.p['content_hash'],'G':self.g['content_hash'],
                'O':self.o['content_hash'],'O_sidecar':self.sidecar['content_hash']},
            'integration_manifest':self.manifest,
            'completed_player_rate_audits':deepcopy(self._current_player_audits),
            'event_draws_by_scenario':deepcopy(self._event_draws),
            'completed_scenario_rate_audits':deepcopy(self._audits),**witness})

    def players(self, sid, events):
        self._sid = sid
        sc = next(x for x in self.sidecar['scenarios'] if x['scenario_id'] == sid)
        by_id = {x['player_id']: x for x in sc['players']}
        out, audits = [], {}
        self._current_player_audits = audits
        for player in self.p['players']:
            pid, team = player['player_id'], player['team_id']
            x = by_id[pid]
            minutes, params, laws = x['minutes'], {}, {}
            for stat in PRIMITIVES:
                pr = self.p2.predict_conditional(self.artifacts[stat], player_id=pid,
                    role=self.roles[pid], projected_exposure=minutes, statistic=stat)
                req(pr.abstain_reason is None, 'J2_CONDITIONAL_ABSTENTION')
                support = pr.parameters['support']
                req(support and all(v['value'] == i and math.isfinite(v['mass']) and
                    v['mass'] >= 0 for i,v in enumerate(support)) and
                    abs(math.fsum(v['mass'] for v in support)-1.) <= 1e-10 and
                    0 <= pr.parameters['tail_mass_upper_bound'] <= 1e-11,
                    'J2_CONDITIONAL_LAW')
                params[stat] = pr.parameters
                laws[stat] = {'pmf': support, 'tail_mass_upper_bound': pr.parameters['tail_mass_upper_bound'],
                    'parameters': {k:v for k,v in pr.parameters.items() if k != 'support'},
                    'family': self.artifacts[stat].data['family']}
            rng = rng_for(self.seed, self.p['game_id'], sid, 'P2-latent-rate/' + pid)
            rejected = []
            rates = {stat: draw_mixing_rate(params[stat], self.artifacts[stat].data['family'], rng)
                     for stat in PRIMITIVES} if minutes else {stat: 0. for stat in PRIMITIVES}
            while rates['points'] < 3 * rates['threes']:
                rejected.append({'points': rates['points'], 'threes': rates['threes']})
                if len(rejected) >= RATE_REJECTION_LIMIT:
                    error=ContractError('J2_RATE_COMPATIBILITY_EXHAUSTED')
                    error.failure_receipt=self.failure_receipt(error.code,player_id=pid,
                        rate_pair_attempts=len(rejected),rejected_pair_count=len(rejected),
                        accepted_pair_count=0,rejection_limit=RATE_REJECTION_LIMIT,
                        sampled_other_rates={k:v for k,v in rates.items() if k not in ('points','threes')},
                        rejected_rate_pairs=deepcopy(rejected),rejected_pairs_sha256=digest(rejected))
                    raise error
                for stat in ('points','threes'):
                    rates[stat] = draw_mixing_rate(params[stat], self.artifacts[stat].data['family'], rng)
            sampled_rates = dict(rates)
            multiplier = (x['possession_share'] * 5 * (48 + 5*sc['overtime_periods']) / minutes
                          if minutes else 0.)
            rates = {stat: value * multiplier for stat,value in rates.items()}
            conversion = self.p2.predict_conditional(self.artifacts['three_conversion'], player_id=pid,
                role=self.roles[pid], projected_exposure=0, statistic='threes')
            req(conversion.abstain_reason is None, 'J2_S3_ABSTENTION')
            q = conversion.parameters['success_mean']
            nonthree = rates['points'] - 3 * rates['threes']
            rates['threes'] *= events['p3'] / q
            rates['points'] = nonthree + 3 * rates['threes']
            out.append({'player_id': pid, 'team_id': team, 'rates': rates})
            audits[pid] = {'conditional_laws': laws, 'sampled_mixing_rates': sampled_rates,
                'rejected_rate_pairs': rejected, 'rate_pair_attempts': len(rejected)+1,
                'O_possession_share': x['possession_share'], 'O_role_state': x['role_state'],
                'O_projected_possession_opportunity': x['projected_possession_opportunity'],
                'role': self.roles[pid], 'kernel_rates': rates, 'S3_success_mean': q}
        self._audits[sid] = {'P2_to_J_projection': audits,
            'marginal_laws_preserved_exactly': False, 'law_contract': LAW_PROPOSAL,
            'posterior_or_dispersion_rate_uncertainty_propagated': True,
            'O_lineup_sha256': digest({t:x['lineup_segments'] for t,x in sc['teams'].items()})}
        return out

    def sample_events(self, players, minutes, ix, state, spec, rng, *, constrained):
        counts,ledger=super().sample_events(players,minutes,ix,state,spec,rng,constrained=constrained)
        self._event_draws.setdefault(self._sid,[]).append({
            'event_attempt':len(self._event_draws.get(self._sid,[])),
            'counts':{k:v.tolist() for k,v in counts.items()},'ledger':deepcopy(ledger)})
        validate_event_counts(counts,ledger,ix)
        return counts,ledger


def simulate_latest(p, g, o, sidecar, artifacts, source_manifest, roles, *,
                    upstream_root, evidence_mode='real', seed=20261116, **kwargs):
    """Consume exact latest P2/P3 objects; proposed law remains unaccepted.

    No O resampling, source inference or final-count repair occurs. This is a
    synthetic engineering proposal, never continuation of an authentic case.
    """
    # Real admission stops before any fixture-dependent code is consulted.
    req(evidence_mode == 'latest_synthetic_engineering',
        'J2_REAL_BLOCKED_INDEPENDENT_SOURCE_AND_FIT_ADMISSION_REQUIRED')
    validate_opportunity(o, p, g)
    p2, p3 = load_upstream(upstream_root)
    validate_artifacts(p, artifacts, source_manifest, roles, evidence_mode=evidence_mode)
    req(all(isinstance(a, p2.FittedS) for a in artifacts.values()), 'J2_FITTED_ARTIFACT_TYPE')
    p3.validate_sidecar(sidecar, p, g, o)
    req(sidecar['schema'] == 'nba-p3-opportunity/0.2.0', 'J2_P3_SIDECAR_VERSION')
    req(not any(k.startswith('_') for k in kwargs), 'J2_PRIVATE_OVERRIDE_FORBIDDEN')
    prepared = Prepared(p, g, o, sidecar, artifacts, source_manifest, roles, p2, seed)
    model = {'model_id': 'research:nba:P2-to-J-latest', 'version': VERSION,
        'artifact_sha256': digest(prepared.manifest), 'code_sha256': raw_sha(Path(__file__).read_bytes()),
        'training_cutoff_at': p['training_cutoff_at']}
    try:
        result = _simulate_p4(p, g, o, {'model': model, 'content_hash': digest(prepared.manifest),
            'players': [{'player_id': r['player_id'], 'rates': {k:0. for k in PRIMITIVES}}
                        for r in p['players']]}, _integration=prepared, seed=seed, **kwargs)
    except ContractError as error:
        if not hasattr(error,'failure_receipt'):
            draws=prepared._event_draws.get(prepared._sid,[])
            error.failure_receipt=prepared.failure_receipt(error.code,event_attempts=len(draws),
                rejected_tied_event_draws=(len(draws) if error.code=='P4_TIED_COMPLETED_GAME_EXHAUSTED' else None),
                accepted_event_draws=0)
        raise
    result['integration_manifest'] = deepcopy(prepared.manifest)
    result['input_shas']['O_sidecar'] = sidecar['content_hash']
    result['status'] = 'SYNTHETIC_PROPOSED_CONSTRAINED_LAW_PENDING_INDEPENDENT_ACCEPTANCE_REAL_BLOCKED'
    return result
