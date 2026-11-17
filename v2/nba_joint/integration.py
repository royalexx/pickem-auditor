"""Versioned P2/P3 consumer. Pinned contract-fixture integration, never certification.

P1 has not supplied an authenticated artifact registry. Consequently the only
trust root in v1 is the committed contract-fixture allowlist. Real mode fails
closed even when a caller declares P1_VERIFIED or supplies self-consistent hashes.
No S likelihood is fitted here; conditional laws come from the pinned P2 API.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np

from v2.nba_architecture.v2_contracts import digest, instant, req, seal, verify
from v2.nba_architecture.families_v2 import validate_opportunity
from v2.nba_joint.events import sample_events
from v2.nba_joint.p4 import _simulate_p4, PRIMITIVES

VERSION = 'NBA-P2-P3-to-J/1.0.0'
PINS = {
    'P2': {'commit': '96d210a6100085640e7e82928ab1c864839fc454',
           'path': 'nba_s_family/model.py',
           'sha256': '3fb8ab1c81d1f47a85d022cd4280dfeca92b13f7fbbf4af98d6d1760b1ed921b'},
    'P3': {'commit': '80dbed35f983839f962250ad1c0236061dc6ee00',
           'path': 'nba_o_family.py',
           'sha256': '984914556741462aa6c5d62a628d39a1313fcbd2e9962639f48d4e62f326277d'},
    'P1': {'commit': 'e0b8703887d327c8d8ac34807078e75e7b59a540'},
    'G0': {'commit': '59d28dc23be97de2a6a82d22be8338151e31f5b6'},
    'P6': {'commit': '31435bd571ae1b4a9b7f1e1bbf05e55cef61126f'},
}
FIXTURES = Path(__file__).resolve().parents[2] / 'research/nba_p4_integration/fixtures'
KERNEL_SHA = '40334862379548ac9efd562640580b20e419455728850f2ea6125d1447b1ebec'


def raw_sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load_upstream(root):
    """Load unchanged owner code from an explicit checkout; reject version drift."""
    modules = []
    for owner in ('P2', 'P3'):
        pin = PINS[owner]
        path = Path(root) / pin['path']
        req(path.is_file() and raw_sha(path.read_bytes()) == pin['sha256'],
            'J_UPSTREAM_CODE_PIN_' + owner)
        name = '_nba_p4_pinned_' + owner
        if name not in sys.modules:
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
        module = sys.modules[name]
        req(raw_sha(Path(module.__file__).read_bytes()) == pin['sha256'],
            'J_LOADED_UPSTREAM_CODE_DRIFT')
        modules.append(module)
    return tuple(modules)


def validate_p2_artifacts(p, artifacts, manifest, *, evidence_mode):
    """Allowlist is fixture-only. SHA integrity is never P1 authentication."""
    req(evidence_mode == 'pinned_contract_fixture',
        'J_REAL_INTEGRATION_BLOCKED_P1_AUTHENTICATION_REGISTRY_UNAVAILABLE')
    pins = json.loads((FIXTURES / 'trust.json').read_text())
    req(isinstance(manifest, dict) and digest(manifest) == pins['source_manifest_sha256'], 'J_S_SOURCE_MANIFEST_PIN')
    req(isinstance(artifacts, dict) and set(artifacts) == set(PRIMITIVES) | {'three_conversion'}, 'J_S_ARTIFACT_COVERAGE')
    req(p['game_id'].startswith('espn:game:synthetic-'), 'J_FIXTURE_TARGET_REQUIRED')
    cutoff = instant(p['training_cutoff_at'])
    for stat, artifact in artifacts.items():
        req(hasattr(artifact, 'payload') and type(artifact.payload) is bytes,
            'J_S_FITTED_ARTIFACT_REQUIRED')
        req(raw_sha(artifact.payload) == pins['artifacts'][stat], 'J_S_ARTIFACT_NOT_TRUSTED')
        a = artifact.data
        req(a['code_sha256'] == PINS['P2']['sha256'] and
            a['version'] == 'nba-v25-S/1.0.0', 'J_S_CODE_VERSION')
        expected = 'threes' if stat == 'three_conversion' else stat
        req(a['stat'] == expected and a['family'] in
            (('S3',) if stat == 'three_conversion' else ('S1', 'S2')),
            'J_S_FAMILY_STAT')
        req(instant(a['training_cutoff_at']) <= cutoff, 'J_S_MODEL_CUTOFF')
        used = {k: manifest[k] for k in a['source_receipts'] if k in manifest}
        # P2 uses a raw canonical-byte digest; G0 digest has the same encoding for these ASCII fields.
        req(digest(used) == a['source_manifest_sha256'], 'J_S_MANIFEST_JOIN')
        for row in a['training_rows']:
            req(row['game_id'] != p['game_id'] and
                instant(row['game_start_at']) < instant(a['training_cutoff_at']) and
                instant(row['outcome_available_at']) <= instant(a['training_cutoff_at']),
                'J_S_TARGET_OR_LATE_TRAINING')
            source = used.get(row['source_receipt_sha256'])
            req(source is not None and source['raw_sha256'] == row['source_raw_sha256'] and
                instant(row['outcome_available_at']) <= instant(source['available_at']) <=
                instant(a['training_cutoff_at']), 'J_S_SOURCE_JOIN_OR_LATE')
        for player in p['players']:
            own = [r for r in a['training_rows'] if r['player_id'] == player['player_id']]
            req(bool(own) and all(r['team_id'] == player['team_id'] for r in own),
                'J_S_PLAYER_TEAM_JOIN')
    return True


class _S3RNG:
    """Narrow compatibility seam for the unchanged, SHA-pinned WS5 kernel.

    Its first three binomial calls per team are 2PM, 3PM, FTM. Only the
    second is replaced by P2 S3. This is deliberately coupled to the pinned
    kernel call protocol; any drift or wrong argument shape fails closed.
    All subsequent assist/rebound calls delegate to the same generator.
    """
    def __init__(self, rng, ix, players, p2, artifacts, roles, p3):
        self.rng, self.ix, self.players = rng, ix, players
        self.p2, self.artifacts, self.roles, self.p3 = p2, artifacts, roles, p3
        self.vector_calls = 0
        self.projected_attempts = []

    def __getattr__(self, key):
        return getattr(self.rng, key)

    def binomial(self, n, p, *args, **kwargs):
        if np.ndim(n) == 1:
            call = self.vector_calls
            self.vector_calls += 1
            req(call < 6 and len(n) == len(self.ix[call // 3]), 'J_WS5_CONVERSION_PROTOCOL')
            if call % 3 == 1:
                req(p == self.p3 and not args and not kwargs, 'J_WS5_THREE_PROTOCOL')
                out = []
                for i, attempts in zip(self.ix[call // 3], n):
                    req(isinstance(attempts, np.integer) and attempts >= 0,
                        'J_PROJECTED_ATTEMPTS_INTEGER')
                    pid = self.players[i]['player_id']
                    prediction = self.p2.predict_conditional(
                        self.artifacts['three_conversion'], player_id=pid,
                        role=self.roles[pid], projected_exposure=int(attempts), statistic='threes')
                    req(prediction.abstain_reason is None, 'J_S3_ABSTENTION')
                    support = prediction.parameters['support']
                    value = int(self.rng.choice(len(support), p=[x['mass'] for x in support]))
                    out.append(value)
                    self.projected_attempts.append({'player_id': pid, 'projected_three_pa': int(attempts),
                                                    'made_threes': value})
                return np.asarray(out, dtype=np.int64)
        return self.rng.binomial(n, p, *args, **kwargs)


def validate_event_ledger(counts, ledger, ix):
    """Independent integer accounting for a serialized aggregate kernel draw."""
    matrix = np.asarray(ledger['assist_matrix'])
    req(np.all(np.diag(matrix) == 0) and np.all(matrix >= 0), 'J_SELF_ASSIST')
    req(np.array_equal(matrix.sum(axis=1), counts['assists']), 'J_ASSIST_LEDGER')
    req(np.all(matrix.sum(axis=0) <= counts['two_pm'] + counts['threes']), 'J_EXCESS_ASSISTS')
    for i, team_ix in enumerate(ix):
        other = ix[1-i]
        r = ledger['rebounds'][i]
        req(r['available'] == r['fg_misses'] + r['terminal_ft'] and
            r['credited'] <= r['available'] and
            r['credited'] == r['offensive'] + r['defensive'] and
            r['unattributed'] == r['available'] - r['credited'] and
            int(counts['oreb'][team_ix].sum()) == r['offensive'] and
            int(counts['dreb'][other].sum()) == r['defensive'], 'J_REBOUND_LEDGER')
    req(np.all(matrix[np.ix_(ix[0], ix[1])] == 0) and
        np.all(matrix[np.ix_(ix[1], ix[0])] == 0), 'J_OPPONENT_ASSIST')
    for t, indices in enumerate(ix):
        req(int(counts['assists'][indices].sum()) + ledger['unassisted'][t] ==
            int((counts['two_pm'][indices] + counts['threes'][indices]).sum()),
            'J_ASSIST_UNASSISTED_TOTAL')
        b = ledger['team_budgets'][t]
        req(all(b[k] == int(counts[k][indices].sum()) for k in b), 'J_TEAM_EVENT_BUDGET')
        r = ledger['rebounds'][t]
        req(r['fg_misses'] == b['two_pa'] + b['three_pa'] - b['two_pm'] - b['threes'] and
            0 <= r['terminal_ft'] <= b['fta'] - b['ftm'], 'J_REBOUND_MISS_POOL')
    return True


class _Prepared:
    def __init__(self, p, g, o, sidecar, artifacts, manifest, roles, p2):
        self.p, self.g, self.o, self.sidecar = p, g, o, sidecar
        self.artifacts, self.roles, self.p2 = artifacts, roles, p2
        self.home_team_id = sidecar['home_team_id']
        self._audits = {}
        self._sid = None
        self.manifest = {'version': VERSION, 'owner_pins': PINS,
            'artifacts': {k: a.artifact_sha256 for k, a in artifacts.items()},
            'source_manifest_sha256': digest(manifest), 'roles_sha256': digest(roles),
            'sidecar_sha256': sidecar['content_hash'],
            'law_mapping': 'conditional-mean-and-opportunity-share-projection;S3-given-projected-3PA',
            'real_integration': 'BLOCKED', 'J2_J3_statistically_calibrated': False, 'evidence_mode': 'pinned_contract_fixture'}

    def players(self, sid, events):
        self._sid = sid
        side = next(x for x in self.sidecar['scenarios'] if x['scenario_id'] == sid)
        by_id = {x['player_id']: x for x in side['players']}
        out, laws = [], {}
        for player in self.p['players']:
            pid, team = player['player_id'], player['team_id']
            x = by_id[pid]
            minutes = x['minutes']
            rates, conditional = {}, {}
            for stat in PRIMITIVES:
                pr = self.p2.predict_conditional(self.artifacts[stat], player_id=pid,
                    role=self.roles[pid], projected_exposure=minutes, statistic=stat)
                req(pr.abstain_reason is None, 'J_S_CONDITIONAL_ABSTENTION')
                law = pr.parameters['support']
                req(bool(law) and all(v['value'] == i and math.isfinite(v['mass']) and
                    v['mass'] >= 0 for i, v in enumerate(law)) and
                    abs(math.fsum(v['mass'] for v in law) - 1.) <= 1e-10 and
                    0 <= pr.parameters['tail_mass_upper_bound'] <= 1e-11,
                    'J_S_CONDITIONAL_PMF')
                mean = math.fsum(v['value'] * v['mass'] for v in law)
                req(math.isfinite(mean) and mean >= 0, 'J_S_CONDITIONAL_MEAN')
                conditional[stat] = {'mean': mean, 'pmf': law,
                    'tail_mass_upper_bound': pr.parameters['tail_mass_upper_bound']}
                # P3 opportunity shares shape allocation. No participation/minute draws here.
                team_minutes = 5 * (48 + 5 * side['overtime_periods'])
                rates[stat] = mean / minutes * x['possession_share'] * team_minutes / minutes if minutes else 0.
            req(rates['points'] + 1e-10 >= 3 * rates['threes'], 'J_S_INCOMPATIBLE_POINT_THREE_MEANS')
            conv = self.p2.predict_conditional(self.artifacts['three_conversion'], player_id=pid,
                role=self.roles[pid], projected_exposure=0, statistic='threes')
            req(conv.abstain_reason is None, 'J_S3_ABSTENTION')
            q = conv.parameters['success_mean']
            req(math.isfinite(q) and 0 < q <= 1, 'J_S3_CONVERSION_PARAMETER')
            # WS5 infers projected attempts using pooled p3. Adjust its input so
            # expected attempts use this player's fitted S3 conversion instead.
            nonthree = max(0., rates['points'] - 3 * rates['threes'])
            rates['threes'] *= events['p3'] / q
            rates['points'] = nonthree + 3 * rates['threes']
            out.append({'player_id': pid, 'team_id': team, 'rates': rates})
            laws[pid] = {'conditional_laws': conditional, 'role': self.roles[pid],
                'O_role_state': x['role_state'], 'O_possession_share': x['possession_share'],
                'O_projected_possession_opportunity': x['projected_possession_opportunity'],
                'kernel_rates': rates, 'S3_success_mean': q}
        self._audits[sid] = {'P2_to_J_projection': laws,
            'marginal_laws_preserved_exactly': False,
            'O_lineup_sha256': digest({t: x['lineup_segments'] for t, x in side['teams'].items()})}
        return out

    def sample_events(self, players, minutes, ix, state, spec, rng, *, constrained):
        req(raw_sha(Path(sys.modules[sample_events.__module__].__file__).read_bytes()) ==
            KERNEL_SHA, 'J_WS5_KERNEL_DRIFT')
        proxy = _S3RNG(rng, ix, players, self.p2, self.artifacts, self.roles, spec['events']['p3'])
        counts, ledger = sample_events(players, minutes, ix, state, spec, proxy, constrained=constrained)
        req(proxy.vector_calls == 6, 'J_WS5_CONVERSION_PROTOCOL')
        validate_event_ledger(counts, ledger, ix)
        ledger['S3_projected_attempts'] = proxy.projected_attempts
        ledger['possession_accounting'] = 'aggregate_proxy_not_exact_possession_or_PBP'
        return counts, ledger

    def audit(self, sid):
        return self._audits[sid]


def simulate_integrated(p, g, o, sidecar, artifacts, source_manifest, roles, *,
                        upstream_root, evidence_mode='real', **kwargs):
    """Consume exact P2 FittedS + P3 O/sidecar shapes; never regenerate O draws.

    Real integration remains BLOCKED until a P1 authenticated model/source trust
    registry exists and is independently accepted. Fixture-only output cannot
    authorize G1/G2. kwargs are the existing J0/J1/J2/J3 research parameters.
    """
    validate_opportunity(o, p, g)
    validate_p2_artifacts(p, artifacts, source_manifest, evidence_mode=evidence_mode)
    p2, p3 = load_upstream(upstream_root)
    req(all(isinstance(a, p2.FittedS) for a in artifacts.values()), 'J_P2_ARTIFACT_TYPE')
    p3.validate_sidecar(sidecar, p, g, o)
    req(sidecar['schema'] == 'nba-p3-opportunity/0.1.0' and
        sidecar['kind'] == 'opportunity_scenarios' and sidecar['game_id'] == p['game_id'],
        'J_P3_SCHEMA_IDENTITY')
    req(not any(k.startswith('_') for k in kwargs), 'J_PRIVATE_OVERRIDE_FORBIDDEN')
    pins = json.loads((FIXTURES / 'trust.json').read_text())
    req(digest(roles) == pins['roles_sha256'], 'J_S_ROLE_PIN')
    roster = {x['player_id'] for x in p['players']}
    req(set(roles) == roster and all(isinstance(x, str) and x for x in roles.values()),
        'J_S_ROLE_ROSTER')
    req(all(len(sc['players']) == len(roster) for sc in sidecar['scenarios']), 'J_P3_DUPLICATE_PLAYER')
    for sc in sidecar['scenarios']:
        for team, info in sc['teams'].items():
            rows = sorted((x for x in o['scenarios'][0]['players'] if x['team_id'] == team), key=lambda x:x['player_id'])
            segments = info['lineup_segments']
            end = 0.
            for segment in segments:
                req(abs(segment['start'] - end) < 1e-7 and segment['end'] > segment['start'] and
                    len(set(segment['player_indices'])) == 5 and
                    all(type(i) is int and 0 <= i < len(rows) for i in segment['player_indices']),
                    'J_P3_INVALID_ON_COURT_INTERVAL')
                end = segment['end']
            req(abs(end - (48 + 5*sc['overtime_periods'])) < 1e-7, 'J_P3_INTERVAL_CLOCK')
        for x in sc['players']:
            req(math.isclose(x['projected_possession_opportunity'],
                sc['teams'][next(r['team_id'] for r in p['players'] if r['player_id']==x['player_id'])]['projected_possessions'] *
                x['possession_share'], rel_tol=0, abs_tol=1e-7), 'J_P3_PLAYER_OPPORTUNITY')
            req(isinstance(x['role_state'], str) and bool(x['role_state']), 'J_P3_ROLE_STATE')
    prepared = _Prepared(p, g, o, sidecar, artifacts, source_manifest, roles, p2)
    model = {'model_id': 'research:nba:P2-to-J', 'version': VERSION,
             'artifact_sha256': digest(prepared.manifest),
             'code_sha256': raw_sha(Path(__file__).read_bytes()),
             'training_cutoff_at': p['training_cutoff_at']}
    result = _simulate_p4(p, g, o, {'model': model, 'content_hash': digest(prepared.manifest),
        'players': [{'player_id': r['player_id'], 'rates': {k: 0. for k in PRIMITIVES}}
                    for r in p['players']]}, _integration=prepared, **kwargs)
    result['status'] = 'PINNED_UPSTREAM_CONTRACT_FIXTURE_REAL_INTEGRATION_BLOCKED'
    result['integration_manifest'] = prepared.manifest
    result['input_shas']['O_sidecar'] = sidecar['content_hash']
    return result
