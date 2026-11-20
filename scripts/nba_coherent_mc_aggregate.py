"""Validate/aggregate complete append-only S4/J Monte Carlo global-index shards.

Usage:
  python scripts/nba_coherent_mc_aggregate.py --root /datasets/.../boundedQ/n20000 --total-n 20000

Never collect outcomes, fit models or update a production artifact.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from scripts.nba_coherent_mc_pimh import admitted_inputs
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_joint.coherent_sensitivity_aggregate_v1 import aggregate_complete_shards


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--total-n',type=int,required=True)
    parser.add_argument('--rare-sampler',choices=('sequential','pimh'),default='sequential')
    args=parser.parse_args()
    model,cohort=admitted_inputs()
    result=aggregate_complete_shards(args.root,model,cohort,
                    expected_n=args.total_n,rare_sampler=args.rare_sampler)
    receipt=(args.root/'AGGREGATE_RECEIPT.json').read_bytes()
    summary=dict(schema=result['schema'],status=result['status'],
                 raw_sha256=digest(receipt),total_n=args.total_n,
                 total_rows=result['totals']['accepted'],
                 source_actor_score_rows=result['totals']['score_assignment_rows'],
                 rare_ot_tv_envelope=result['rare_OT_prior_probability_bound'],
                 simultaneous_CDF_bound=result[
                    'nominal_95pct_familywise_iid_DKW_plus_rareOT_tv'].get(str(args.total_n)),
                 unconditional_numeric_only=True,independent_p6_accepted=False,
                 release=False)
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
