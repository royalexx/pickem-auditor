"""Derive all 96 weighted primitive/combo PMFs from retained synthetic draws."""
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

from v2.nba_architecture.v2_contracts import digest
from v2.nba_architecture.families_v2 import validate_integration

STATS=('points','rebounds','assists','threes','pr','pa','ra','pra')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input-dir',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
    summary=json.loads((args.input_dir/'summary.json').read_bytes())
    fixed=json.loads((args.input_dir/'fixed_inputs.json').read_bytes())
    raw=args.input_dir/'full_seed_outputs.jsonl.gz'
    if hashlib.sha256(raw.read_bytes()).hexdigest()!=summary['raw_full_outputs_gzip_sha256']:
        raise ValueError('COMPRESSED_RAW_OUTPUT_SHA_MISMATCH')
    p,g,o=fixed['pregame'],fixed['G'],fixed['O']
    pooled={x['player_id']:{s:{} for s in STATS} for x in p['players']}
    seeds=set();uncompressed=hashlib.sha256();paths=0
    with gzip.open(raw,'rb') as stream:
        for line in stream:
            uncompressed.update(line);row=json.loads(line);seed=row['seed']
            if seed in seeds:raise ValueError('DUPLICATE_SEED')
            seeds.add(seed);bundle=row['native_result']['bundle']
            validate_integration(bundle,p,g,o)
            for sc in bundle['scenarios']:
                paths+=1
                for person in sc['players']:
                    for stat in STATS:
                        value=person['stats'][stat];law=pooled[person['player_id']][stat]
                        law[value]=law.get(value,0.)+sc['weight']/len(summary['plan']['seeds'])
    if seeds!=set(summary['plan']['seeds']):raise ValueError('SEED_POPULATION_MISMATCH')
    if uncompressed.hexdigest()!=summary['raw_full_outputs_uncompressed_sha256']:
        raise ValueError('UNCOMPRESSED_RAW_OUTPUT_SHA_MISMATCH')
    result={pid:{stat:[{'value':v,'mass':m} for v,m in sorted(law.items())]
            for stat,law in stats.items()} for pid,stats in pooled.items()}
    if not all(abs(math.fsum(x['mass'] for x in law)-1.)<=1e-12 for stats in result.values() for law in stats.values()):
        raise ValueError('POOLED_PMF_NORMALIZATION')
    args.output_dir.mkdir(parents=True,exist_ok=False)
    raw_result=(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode()
    (args.output_dir/'all_96_weighted_pmfs.json').write_bytes(raw_result)
    receipt={'scope':'POOLED_SYNTHETIC_ENGINEERING_J_REPETITIONS_NOT_A_FORECAST',
        'observed_games':0,'producer_P4_commit':summary['exact_tested_P4_commit'],
        'analysis_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'raw_output_gzip_sha256':summary['raw_full_outputs_gzip_sha256'],
        'raw_output_uncompressed_sha256':uncompressed.hexdigest(),
        'seed_repetitions':len(seeds),'weighted_paths':paths,'pmfs':96,
        'all_G0_bundles_validated':True,'all_combos_same_draw':True,
        'all_masses_normalized':True,'pmf_raw_sha256':hashlib.sha256(raw_result).hexdigest(),
        'independent_acceptance':False}
    (args.output_dir/'receipt.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__':main()
