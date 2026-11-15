"""Restore pinned inputs without network recapture; rerun and compare science hashes."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    base=Path('research/nba_joint_v01');root=Path('work/joint_input');(root/'raw').mkdir(parents=True,exist_ok=True)
    source_manifest=base/'inputs/manifest_v2.json'
    if not source_manifest.exists():source_manifest=base/'inputs/manifest.json'
    manifest=json.loads(source_manifest.read_text())
    def retain(path,raw):
        if path.exists():
            if path.read_bytes()!=raw:raise ValueError('EXISTING_REPRO_INPUT_CONFLICT:'+str(path))
        else:
            with path.open('xb') as f:f.write(raw)
    for source in manifest['shards']:
        path=Path(source['path']);name=path.name;stat,year=name.split('_');year=year.split('.')[0]
        raw=subprocess.check_output(['git','show',manifest['warehouse']+':data/bayesian_warehouse/populations/nba/'+stat+'/'+year+'.jsonl.gz'])
        if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('PINNED_SHARD_HASH_MISMATCH')
        retain(path,raw)
    for source in manifest['raw']:
        raw=gzip.decompress((base/'inputs/official'/(source['game_id']+'.json.gz')).read_bytes())
        if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('PINNED_OFFICIAL_SOURCE_HASH_MISMATCH')
        retain(Path(source['path']),raw)
    retain(root/'manifest.json',source_manifest.read_bytes())
    retain(Path('work/ws4_original_replay.json'),(base/'upstream/ws4_original_replay.json').read_bytes())
    reference=json.loads((base/'results/run_receipt.json').read_text())
    env={**os.environ,'OPENBLAS_NUM_THREADS':'1','PYTHONDONTWRITEBYTECODE':'1'}
    subprocess.run([sys.executable,'-m','research.nba_joint_v01.run','--output',args.output,'--scenarios',str(reference['scenario_count']),'--generated-at',reference['generated_at']],env=env,check=True)
    out=Path(args.output)
    original=json.loads((base/'results/scenario_hashes.json').read_text());rerun=json.loads((out/'scenario_hashes.json').read_text())
    keys=('game_id','model','input_sha256','output_sha256')
    a=[{k:r[k] for k in keys} for r in original];b=[{k:r[k] for k in keys} for r in rerun]
    if a!=b:raise ValueError('NONDETERMINISTIC_SCIENTIFIC_SCENARIO_OUTPUT')
    if (base/'results/results.json').read_bytes()!=(out/'results.json').read_bytes():raise ValueError('NONDETERMINISTIC_SCORE_OUTPUT')
    receipt={'status':'PASSED','model_game_configurations':len(a),'scenario_hashes_identical':True,'score_bytes_identical':True,'reference_receipt_sha256':hashlib.sha256((base/'results/run_receipt.json').read_bytes()).hexdigest(),'reproduction_receipt_sha256':hashlib.sha256((out/'run_receipt.json').read_bytes()).hexdigest(),'differences_excluded':['runtime','peak memory','physical execution commit metadata']}
    with (out/'reproduction_check.json').open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2)
    print(json.dumps(receipt))


if __name__=='__main__':main()
