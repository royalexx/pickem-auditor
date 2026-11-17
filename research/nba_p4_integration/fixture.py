"""Pinned owner contract fixtures. All games, counts and source bytes synthetic."""
import json
from pathlib import Path
from copy import deepcopy

from v2.nba_architecture.v2_contracts import seal
from v2.nba_joint.integration import FIXTURES, load_upstream


def load(root):
    p2, p3 = load_upstream(root)
    data = json.loads((FIXTURES / 'inputs.json').read_text())
    artifacts = {k: p2.FittedS((FIXTURES / (k + '.json')).read_bytes())
                 for k in ('points', 'rebounds', 'assists', 'threes', 'three_conversion')}
    return data, artifacts, p2, p3


def build(root, *, n=4, variant='O2', seed=17, home_reversed=False, special=None):
    data, artifacts, p2, p3 = load(root)
    p, g, priors = deepcopy(data['pregame']), deepcopy(data['game_state']), deepcopy(data['priors'])
    original = deepcopy(g['scenarios'])
    g.pop('content_hash')
    g['scenarios'] = []
    for i in range(n):
        sc = deepcopy(original[i % 4])
        sc['scenario_id'] = f'synthetic:integration:{i}'
        sc['weight'] = 1. / n
        g['scenarios'].append(sc)
    g = seal(g)
    if special:
        special(priors)
    o, side = p3.build_opportunity(p, g, priors, model=data['O_model'], seed=seed,
        variant=variant, home_team_id=p['team_ids'][1 if home_reversed else 0],
        home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
    return p, g, o, side, artifacts, data['source_manifest'], data['roles']
