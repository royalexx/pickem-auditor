"""Read-only zero-state audit of the frozen NBA coherent S4/J research bank.

No fitting, new forecast issuance, simulation, scoring, or file replacement.
Run on the exact pinned PR193 model/bank only; this does not promote G1.
"""
import argparse
import json
import sys
from pathlib import Path

from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_joint.coherent_zero_audit_v1 import analytic_minute_grid,audit_saved_bank

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'docs/nba_architecture/coherent_opportunity_20261120'
MODEL_SHA='f1f6dd4a4d3753042c28b71fa9b7949628d69ccdad8f38ece47bb2ccdc6ffa2a'
BANK_SHA='318bb9b2317ae120b6b51852a88b97177424fc0caeba36ed8b38b4f6ead01d88'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',type=Path,default=PACKET/'fitted/model.json')
    parser.add_argument('--bank',type=Path,default=PACKET/'actual/BANK.json')
    parser.add_argument('--output',type=Path,help='Optional new report path; must not exist')
    args=parser.parse_args()
    model_raw=args.model.read_bytes();bank_raw=args.bank.read_bytes()
    require(digest(model_raw)==MODEL_SHA,'ZERO_AUDIT_WRONG_FROZEN_MODEL_BYTES')
    require(digest(bank_raw)==BANK_SHA,'ZERO_AUDIT_WRONG_FROZEN_BANK_BYTES')
    model=strict_json(model_raw);bank=strict_json(bank_raw)
    require(bank['model_raw_sha256']==digest(canonical(model)),
            'ZERO_AUDIT_WRONG_MODEL_BANK_JOIN')
    frozen=audit_saved_bank(bank)
    result=dict(schema='nba-coherent-zero-prior-readonly-receipt/1',
                accepted_frozen_model_raw_sha256=MODEL_SHA,
                accepted_frozen_bank_raw_sha256=BANK_SHA,
                observed_frozen_bank=frozen,
                regulation_prior_grid=analytic_minute_grid(model,duration_minutes=48),
                overtime_prior_grid=analytic_minute_grid(model,duration_minutes=53),
                statement='O-prior sensitivity only: not S4/J probability, outcome, or historical accuracy validation',
                source_population_unchanged=True,
                actual_forecasts_unchanged=True,
                release_approved=False)
    raw=canonical(result)+b'\n'
    if args.output is None:
        sys.stdout.buffer.write(raw)
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('xb') as f:f.write(raw)
        print(json.dumps(dict(schema=result['schema'],report=str(args.output),
                              report_raw_sha256=digest(raw),zero_named_slots=frozen['observed_zero_minute_named_slots'],
                              scenarios=frozen['scenarios'],new_forecast=False),sort_keys=True))


if __name__=='__main__':
    main()
