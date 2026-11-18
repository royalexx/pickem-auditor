"""Run from repository root. Store raw separate streams, commands and exact SHA."""
import json
import os
from pathlib import Path
import subprocess
import sys

OUT=Path(__file__).resolve().parent
commands=[
 [sys.executable,'-m','unittest','tests.nba_architecture.test_p1_listed_source_v1','tests.nba_architecture.test_p1_capture_v1','-v'],
 [sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v'],
 [sys.executable,'-m','unittest','discover','-s','tests/nba_s_family','-v'],
 [sys.executable,'-m','unittest','discover','-s','tests/nba_c','-v']]
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH='.:tests/nba_architecture')
receipt={'tested_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'commands':[]}
for i,command in enumerate(commands):
 p=subprocess.run(command,env=env,capture_output=True)
 (OUT/f'run-{i}.stdout').write_bytes(p.stdout);(OUT/f'run-{i}.stderr').write_bytes(p.stderr)
 receipt['commands'].append({'argv':command,'exit':p.returncode,'stdout':f'run-{i}.stdout','stderr':f'run-{i}.stderr'})
 print(i,p.returncode,p.stderr.decode()[-160:],flush=True)
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
