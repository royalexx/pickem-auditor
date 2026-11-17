"""Actual latest P2/P3 code over new, explicitly synthetic source fixtures."""
from copy import deepcopy
import json

from v2.nba_architecture.v2_contracts import seal
from v2.nba_joint.latest_upstream import FIXTURES, load_upstream


def build(root, *, n=4, variant='O2', seed=17, special=None):
    p2, p3 = load_upstream(root)
    data = json.loads((FIXTURES / 'inputs.json').read_bytes())
    p, g, priors = deepcopy(data['pregame']), deepcopy(data['game_state']), deepcopy(data['priors'])
    original = deepcopy(g['scenarios'])
    g.pop('content_hash')
    g['scenarios'] = []
    for i in range(n):
        sc = deepcopy(original[i % len(original)])
        sc['scenario_id'] = f'synthetic:latest:{i}'
        sc['weight'] = 1. / n
        g['scenarios'].append(sc)
    g = seal(g)
    if special:
        special(priors)
    o, sidecar = p3.build_opportunity(p, g, priors, model=data['O_model'], seed=seed,
        variant=variant, home_team_id=p['team_ids'][0],
        home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
    artifacts = {k: p2.FittedS((FIXTURES / (k + '.json')).read_bytes())
                 for k in ('points', 'rebounds', 'assists', 'threes', 'three_conversion')}
    return p, g, o, sidecar, artifacts, data['source_manifest'], data['roles']
