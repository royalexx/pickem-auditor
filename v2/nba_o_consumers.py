"""P3-owned executable S/J handoff; consumers own likelihoods and event draws."""
from copy import deepcopy
from v2.nba_architecture.v2_contracts import req, seal
from v2.nba_o_family import build_opportunity, validate_sidecar


def replay(p, g, o, sidecar):
    """Resealing tampered roles, seed, parameters or shares cannot pass replay."""
    validate_sidecar(sidecar, p, g, o)
    rebuilt, supplementary = build_opportunity(
        p, g, sidecar['prior_manifest'], model=sidecar['model'],
        seed=sidecar['seed'], variant=sidecar['variant'],
        home_team_id=sidecar['home_team_id'],
        home_team_source_receipt_sha256=sidecar['home_team_source_receipt_sha256'])
    req(rebuilt == o and supplementary == sidecar, 'O_REPLAY_MISMATCH')
    return True


def consumer_fixture(p, g, o, sidecar):
    replay(p, g, o, sidecar)
    roster = {r['player_id']:r for r in p['players']}
    marginals = {r['player_id']:r for r in o['players']}
    draws = []
    for sc in sidecar['scenarios']:
        players = []
        for row in sc['players']:
            pid = row['player_id']; prior = sidecar['prior_manifest'][pid]
            players.append(dict(deepcopy(row), team_id=roster[pid]['team_id'],
                legal_eligibility=roster[pid]['legal_eligibility'],
                observed_availability=roster[pid]['availability'],
                observation_state='unknown',
                participation_probability=marginals[pid]['participation_probability'],
                participation_evidence=marginals[pid]['participation_evidence'],
                scenario_participation_prior=prior['scenario_participation_prior'],
                uncertainty_flags=deepcopy(prior['uncertainty_flags']),
                source_receipt_sha256=prior['source_receipt_sha256']))
        draws.append(dict(deepcopy(sc), players=players))
    return seal(dict(kind='p3_s_j_handoff', source_snapshot_sha256=p['content_hash'],
        source_certification=p['certification'], sources=deepcopy(p['sources']),
        game_state_sha256=g['content_hash'], opportunity_sha256=o['content_hash'],
        sidecar_sha256=sidecar['content_hash'], prior_sha256=sidecar['prior_sha256'],
        status='SHADOW_NOT_CERTIFIED', scenarios=draws))


def dispatch_scenarios(p, g, o, sidecar, *, s_consumer, j_consumer):
    """Call owner-provided consumers with the same G/O draw and weight.

    No random draw, rate conversion or likelihood implementation lives here.
    Owners must explicitly map role:<index> using their fitted role dictionary;
    an unknown role must abstain. Passing exposure is not a fit attestation.
    """
    fixture = consumer_fixture(p, g, o, sidecar)
    results = []
    for draw in fixture['scenarios']:
        s = s_consumer(deepcopy(draw), deepcopy(fixture['sources']))
        j = j_consumer(deepcopy(draw), s)
        results.append(dict(scenario_id=draw['scenario_id'], weight=draw['weight'],
                            s=s, j=j))
    return results


def call_p2(p, g, o, sidecar, *, predict, fitted, player_id, role, **options):
    """Call actual P2 predict API; no replacement S likelihood."""
    replay(p, g, o, sidecar)
    return predict(fitted, frozen_pregame=p, target_player_id=player_id, role=role,
                   opportunity=o, game_state=g, **options)


def call_p4(p, g, o, sidecar, *, simulate, conditional_rates, **options):
    """Call actual P4 API. Its current synthetic-only S rate gate is preserved."""
    replay(p, g, o, sidecar)
    req(sidecar["home_team_id"] == p["team_ids"][0],
        "O_P4_HOME_ORDER_ADAPTER_REQUIRED")
    return simulate(p, g, o, conditional_rates, **options)
