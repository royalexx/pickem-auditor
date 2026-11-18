"""Synthetic-only consumer of the existing native P2 and P3 public interfaces."""
from math import isfinite

from v2.nba_architecture.families_v2 import validate_opportunity
from v2.nba_architecture.v2_contracts import ContractError, req
from v2.nba_joint.clocked import LAW, STATS, execute, schedule, tagged_failure
from v2.nba_joint.common import rng_for
from v2.nba_joint.clocked_reference import checkpoint_normalizer
from v2.nba_joint.integration_v2 import draw_mixing_rate, validate_artifacts
from v2.nba_joint.latest_upstream import load_upstream


def prepare_native(p, g, o, sidecar, artifacts, manifest, roles, *, upstream_root,
                   evidence_mode='real'):
    req(evidence_mode == 'latest_synthetic_engineering', 'CLOCKED_REAL_INPUTS_UNADMITTED')
    validate_opportunity(o, p, g)
    p2, p3 = load_upstream(upstream_root)
    validate_artifacts(p, artifacts, manifest, roles, evidence_mode=evidence_mode)
    req(all(isinstance(a, p2.FittedS) for a in artifacts.values()), 'CLOCKED_NATIVE_ARTIFACT')
    p3.validate_sidecar(sidecar, p, g, o)
    req(sidecar['schema'] == 'nba-p3-opportunity/0.2.0', 'CLOCKED_NATIVE_SIDECAR')
    home = sidecar['home_team_id']
    teams = [home, next(t for t in p['team_ids'] if t != home)]
    populations = {team: sorted(r['player_id'] for r in p['players'] if r['team_id'] == team)
                   for team in teams}
    specs = []
    for gs, os in zip(g['scenarios'], sidecar['scenarios'], strict=True):
        sid = gs['scenario_id']
        req(os['scenario_id'] == sid and os['weight'] == gs['weight'], 'CLOCKED_SCENARIO_JOIN')
        try:
            plan = schedule(gs, teams, populations, os)
            params = {}
            for pid, row in plan['players'].items():
                params[pid] = {}
                for stat in (*STATS, 'three_conversion'):
                    response = p2.predict_conditional(
                        artifacts[stat], player_id=pid, role=roles[pid],
                        projected_exposure=row['minutes'] if stat in STATS else 0,
                        statistic=stat if stat in STATS else 'threes')
                    req(response.abstain_reason is None, 'CLOCKED_S_CONDITIONAL_ABSTAIN')
                    params[pid][stat] = {
                        'family': artifacts[stat].data['family'],
                        'parameters': {k: v for k, v in response.parameters.items() if k != 'support'}}
        except ContractError as error:
            specs.append({'weight': gs['weight'], **tagged_failure(error, sid)})
        else:
            specs.append({'scenario_id': sid, 'weight': gs['weight'],
                          'plan': plan, 'parameters': params})
    return {'law': LAW, 'game_id': p['game_id'], 'scenarios': specs,
            'evidence': 'ENGINEERING_SYNTHETIC_NATIVE_P2_P3',
            'inputs': {**{k: value['content_hash'] for k, value in
                          zip(('pregame', 'G', 'O', 'O_sidecar'), (p, g, o, sidecar))},
                       'S': {k: a.artifact_sha256 for k, a in artifacts.items()}}}


def run_seed(prepared, seed):
    game_id = prepared['game_id']
    attempts = []
    for spec in prepared['scenarios']:
        if 'plan' not in spec:
            attempts.append(spec)
            continue
        sid, plan = spec['scenario_id'], spec['plan']
        latents = {}
        for pid, inputs in spec['parameters'].items():
            row = plan['players'][pid]
            rng = rng_for(seed, game_id, sid, LAW + '/latents/' + pid)
            values = {k: draw_mixing_rate(inputs[k]['parameters'], inputs[k]['family'], rng)
                      for k in STATS}
            conversion = inputs['three_conversion']['parameters']
            q = float(rng.beta(conversion['alpha'], conversion['beta']))
            points = values['points']
            values['three_conversion'] = q
            values['three_attempt'] = min(.8, 2 * values['threes'] / points) if points else 0.
            values['shooter'] = points * row['possession_share'] / row['minutes'] if row['minutes'] else 0.
            req(all(isfinite(v) and v >= 0 for v in values.values()), 'CLOCKED_LATENT_SUPPORT')
            latents[pid] = values
        attempts.append({'weight': spec['weight'],
                         'normalizer': checkpoint_normalizer(plan, latents),
                         **execute(game_id, sid, plan, latents, seed)})
    return {'law': LAW, 'seed': seed, 'inputs': prepared['inputs'], 'paths': attempts,
            'status': 'accepted' if all(a['status'] == 'accepted' for a in attempts)
            else 'failed_no_forecast'}
