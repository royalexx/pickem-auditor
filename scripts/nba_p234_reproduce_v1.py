"""Create-only owner receipts. No training or source admission is performed."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--out', required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
out = Path(a.out).resolve()
out.mkdir(parents=True, exist_ok=False)
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
           PYTHONPATH='.:tests/nba_architecture')
commands = {
    'inspection': [sys.executable, 'scripts/nba_p234_artifact_inspection_v1.py'],
    'public': [sys.executable, '-m', 'unittest', 'tests.test_nba_p234_artifact_inspection_v1', '-v'],
    'S': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/nba_s_family', '-v'],
    'architecture': [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/nba_architecture', '-v'],
    'accounting-manifest': ['sha256sum', '-c', 'docs/nba_architecture/g1_accounting_repair_20261117/SHA256SUMS'],
    'coupling-manifest': ['sha256sum', '-c', 'docs/nba_architecture/substantive_remediation_20261117/SHA256SUMS'],
    'preserved-executables': ['git', 'diff', '--exit-code', '9e8145972077a598687eaabdbc559f3cbce5e4d7', '--', 'v2'],
}
receipts = []
for name, command in commands.items():
    with (out/(name+'.stdout')).open('wb') as stdout, (out/(name+'.stderr')).open('wb') as stderr:
        result = subprocess.run(command, cwd=root, env=env, stdout=stdout, stderr=stderr)
    receipts.append(dict(name=name, command=command, cwd=str(root), exit_code=result.returncode))
paths = ['research/nba_ws2/results/model.json', 'scripts/nba_p234_artifact_inspection_v1.py',
         'scripts/nba_p234_reproduce_v1.py', 'tests/test_nba_p234_artifact_inspection_v1.py',
         'research/nba_p4_latest/upstream_registry.json']
receipt = dict(tested_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
               independent_review=False, commands=receipts,
               environment={k:env[k] for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','PYTHONPATH']},
               file_hash_domain='EXACT_REPOSITORY_FILE_BYTES',
               inputs={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in paths},
               outputs={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in out.iterdir()})
(out/'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
sys.exit(0 if all(r['exit_code']==0 for r in receipts) else 1)
