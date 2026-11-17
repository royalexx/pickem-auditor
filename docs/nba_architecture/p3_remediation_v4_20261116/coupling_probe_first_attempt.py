"""Reproduce actual O2 bounded verification on immutable synthetic owner input.

This never replaces a model, changes G0 budgets, drops scenarios, or fits data.
The original P4 fixture is read by exact raw SHA; each attempted input is saved
before running the real P3 builder, including the blocked n=32 input.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import time
import traceback

from v2.nba_architecture.v2_contracts import ContractError, canonical, seal
from v2.nba_o_family import build_opportunity

FIXTURE_SHA = '92fc3063445502623d7810421b4de484a743e91ca1a903ad2bd3e4bc8ec61f00'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixture', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    raw = args.fixture.read_bytes()
    if hashlib.sha256(raw).hexdigest() != FIXTURE_SHA:
        raise ValueError('P3_SCALING_FIXTURE_RAW_SHA_MISMATCH')
    args.output.mkdir(parents=True, exist_ok=False)
    data = json.loads(raw)
    rows = []
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    for n in (4, 8, 32):
        p, g, priors = (deepcopy(data[k]) for k in ('pregame', 'game_state', 'priors'))
        original = deepcopy(g['scenarios'])
        g.pop('content_hash')
        g['scenarios'] = []
        for i in range(n):
            sc = deepcopy(original[i % 4])
            sc['scenario_id'] = f'synthetic:integration:{i}'
            sc['weight'] = 1. / n
            g['scenarios'].append(sc)
        g = seal(g)
        case = dict(pregame=p, game_state=g, priors=priors, model=data['O_model'],
                    seed=17, variant='O2', fixture_raw_sha256=FIXTURE_SHA)
        case_raw = canonical(case)
        (args.output / f'O2_n{n}_input.json').write_bytes(case_raw)
        started = time.monotonic()
        try:
            o, sidecar = build_opportunity(p, g, priors, model=data['O_model'], seed=17,
                variant='O2', home_team_id=p['team_ids'][0],
                home_team_source_receipt_sha256=p['sources'][0]['receipt_sha256'])
            (args.output / f'O2_n{n}_output.json').write_bytes(canonical(dict(opportunity=o, sidecar=sidecar)))
            status = 'PASS_FINITE_SYNTHETIC_ONLY'
            error = None
        except ContractError as exc:
            status = 'BLOCKED'
            error = exc.code
            (args.output / f'O2_n{n}_stderr.log').write_text(traceback.format_exc())
        rows.append(dict(n=n, owner_sha=head, status=status, error=error,
                         input_raw_sha256=hashlib.sha256(case_raw).hexdigest(),
                         elapsed_seconds=time.monotonic()-started))
    result = dict(schema='nba-p3-coupling-probe/1.0.0', owner_sha=head,
                  source='EXACT_P4_SYNTHETIC_ENGINEERING_FIXTURE', results=rows,
                  G0_budgets_changed=False, scenarios_discarded=False,
                  independently_accepted=False)
    (args.output/'receipt.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    sums = []
    for path in sorted(args.output.iterdir()):
        sums.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name)
    (args.output/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print(json.dumps(result, indent=2, sort_keys=True))
    if rows[-1]['error'] != 'O_COUPLING_VERIFICATION_BUDGET':
        raise SystemExit('Expected original bounded n=32 rejection was not reproduced')


if __name__ == '__main__':
    main()
