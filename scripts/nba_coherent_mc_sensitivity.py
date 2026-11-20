"""Execute fixed-source coherent S4/J MC sensitivity without changing original data.

Usage: python scripts/nba_coherent_mc_sensitivity.py --n 64 --output /tmp/s4mc-64
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from v2.nba_architecture.p1_subset_handoff_v1 import canonical, digest
from v2.nba_architecture.subset_contract_v1 import strict_json
from v2.nba_architecture.subset_p3_v1 import require
from v2.nba_joint.coherent_sensitivity_v1 import (
    SEED, VARIANTS, simulate_sensitivity)

ROOT=Path(__file__).resolve().parents[1]
PACKET=ROOT/'docs/nba_architecture/coherent_opportunity_20261120'
MODEL_SHA='f1f6dd4a4d3753042c28b71fa9b7949628d69ccdad8f38ece47bb2ccdc6ffa2a'
COHORT_SHA='930715bcd2cb55ecca60bff433ea310c452ce4004791029989e1842a9286a969'
PINNED_RUNTIME={
    'v2/nba_architecture/conditional_c_v1.py':'a6e2aa7d540d01e2492ce4984a20fc2d6e40a1778d2228d89598632e4ab03687',
    'v2/nba_joint/coherent_components_v1.py':'7f5ad29ce603af69491e6046f78567d98e06f4460e9d8333bebdb605b1bf5973',
    'v2/nba_joint/coherent_predictive_v1.py':'7d1d722bc37fca565daed5b98582f92bb5c7aba3c186f9fe3b18d5576eddea0f',
    'v2/nba_joint/common.py':'35df67a2e76cad1f978f35693924ba6c63c43ec7b519c93289a3c8e13a912478',
    'v2/nba_joint/residual_audit_v1.py':'5d99e90df7f9b5164d66f92e70b0e894d3e0d5540131354d8f85cd89560f5197',
    'v2/nba_joint/residual_events_v1.py':'75be57a993360b693d61dfd5acde07dad92a28e831ed6b781c068b793fce01ee',
    'v2/nba_joint/residual_opportunity_v1.py':'d53627276ba972cd23ce91bd4d9cb212f28fa141e45d44ea6f5a276b41215803',
}


def admitted_inputs():
    for path,sha in PINNED_RUNTIME.items():
        require(digest((ROOT/path).read_bytes())==sha,
                'S4_SENS_ORIGINAL_RUNTIME_DRIFT:'+path)
    mraw=(PACKET/'fitted/model.json').read_bytes()
    craw=(PACKET/'actual/COHORT.json').read_bytes()
    require(digest(mraw)==MODEL_SHA,'S4_SENS_FROZEN_MODEL_SHA')
    require(digest(craw)==COHORT_SHA,'S4_SENS_FROZEN_COHORT_SHA')
    model=strict_json(mraw);cohort=strict_json(craw)
    require(digest(canonical(model))==MODEL_SHA and
            digest(canonical(cohort))==COHORT_SHA,
            'S4_SENS_CANONICAL_MODEL_OR_COHORT')
    return model,cohort


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--n',type=int,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--seed',type=int,default=SEED)
    ap.add_argument('--max-wall-seconds',type=float,default=None)
    ap.add_argument('--chunk-size',type=int,default=16)
    ap.add_argument('--path-budget',type=int,default=4096)
    ap.add_argument('--event-budget',type=int,default=4096)
    args=ap.parse_args()
    target=args.output.resolve()
    require(not (target==PACKET.resolve() or PACKET.resolve() in target.parents),
            'S4_SENS_REFUSE_ORIGINAL_PACKET_OVERWRITE')
    model,cohort=admitted_inputs()
    result=simulate_sensitivity(
        model,cohort,args.output,seed=args.seed,n=args.n,variants=VARIANTS,
        path_budget=args.path_budget,event_budget=args.event_budget,
        chunk_size=args.chunk_size,max_wall_seconds=args.max_wall_seconds)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    concise=dict(branch_execution_head=head,
                 receipt_raw_sha256=digest((target/'RECEIPT.json').read_bytes()),
                 requested_scenarios_per_variant=args.n,variants=len(VARIANTS),
                 completed={name:x['completed'] for name,x in result['by_variant'].items()},
                 failed={name:x['failed'] for name,x in result['by_variant'].items()},
                 total_ot_rejections=sum(x['ot_rejections'] for x in result['by_variant'].values()),
                 wall_seconds=result['wall_seconds'],
                 status=result['scientific_status'],
                 full_family_dkw_epsilon=(result.get('prefix_scores',{}).get(str(args.n),{})
                                          .get('dkw_family_epsilon_ideal_iid')),
                 numerical_research_only=True,actual_outcome_scores=0,
                 release=False)
    print(json.dumps(concise,sort_keys=True))
    return 0 if result['completed_variants'] else 2


if __name__=='__main__':
    raise SystemExit(main())
