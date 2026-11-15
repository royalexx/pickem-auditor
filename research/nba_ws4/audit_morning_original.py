"""Diagnostic only: identity-incomplete morning cohort is never certified."""
from collections import defaultdict, Counter
import hashlib
import json
from pathlib import Path


def audit(root):
    root=Path(root)
    path='pickem_runs/2026-11-10/20261111T110422Z/settled_model_predictions.jsonl'
    raw=(root/path).read_bytes(); rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
    groups=defaultdict(dict); duplicate=0
    # Alias-only grouping diagnoses the historical report; it is PROHIBITED for
    # trusted canonical scoring. Missing IDs cannot be retrospectively invented.
    for r in rows:
        k=tuple(str(r.get(f)) for f in ('sport','game_date','player','stat','line'))
        if r['side'] in groups[k]:duplicate+=1
        groups[k][r['side']]=r
    models=('engine_a','engine_b','bayesian_a','bayesian_b','production_consensus','market_raw_novig','online_bayesian_a','online_bayesian_b')
    counts={}
    for sport in ('NBA','NHL'):
        pairs=[v for k,v in groups.items() if k[0]==sport and set(v)=={'over','under'}]
        result={}
        for model in models:
            vals=[(v['over'].get(model),v['under'].get(model)) for v in pairs]
            vals=[(a,b) for a,b in vals if isinstance(a,(int,float)) and isinstance(b,(int,float))]
            result[model]={'available_alias_pairs':len(vals),'noncomplementary':sum(abs(a+b-1)>1e-8 for a,b in vals),
                           'max_sum_deviation':max((abs(a+b-1) for a,b in vals),default=None)}
        counts[sport]={'alias_pairs_not_certified_contracts':len(pairs),'models':result}
    revisions=(root/'pickem_runs/2026-11-10/20261110T180409Z/source_revisions.json').read_bytes()
    return {'schema':'nba-ws4-morning-original-diagnostic-v1','raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_rows':len(rows),
        'legacy_both_side_win_fraction':sum(r.get('outcome')=='win' for r in rows)/len(rows),
        'alias_groups':len(groups),'duplicate_alias_sides':duplicate,
        'missing_canonical_ids':{f:sum(not r.get(f) for r in rows) for f in ('player_id','event_id','original_forecast_sha256')},
        'diagnostics':counts,'canonical_scoring_gate':'BLOCKED-BY-DATA','no_alias_based_trusted_metrics':True,
        'source_revisions':json.loads(revisions),'source_revisions_sha256':hashlib.sha256(revisions).hexdigest()}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    with a.output.open('x') as f:json.dump(audit(a.root),f,indent=2,sort_keys=True)
