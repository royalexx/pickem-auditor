import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from v2.nba_architecture.p1_bounded_demo_v1 import demonstrate
from tests.nba_architecture.test_p1_listed_source_v1 import inputs

out=Path(__file__).resolve().parent
receipt={'tested_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'commands':[]}
for name,args in [('positive',{}),('late',{'input_freeze_at':'2018-10-19T23:45:00Z'})]:
    result=demonstrate(*inputs(),**args)
    (out/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
a=inputs();a[2]+=b' '
(out/'altered.json').write_text(json.dumps(demonstrate(*a),indent=2)+'\n')
commands=[[sys.executable,'-m','unittest','tests.nba_architecture.test_p1_bounded_demo_v1','-v'],[sys.executable,'-m','unittest','discover','-s','tests/nba_architecture','-v']]
for i,cmd in enumerate(commands):
    p=subprocess.run(cmd,capture_output=True,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONPATH='.:tests/nba_architecture'))
    (out/f'{i}.stdout').write_bytes(p.stdout);(out/f'{i}.stderr').write_bytes(p.stderr)
    receipt['commands'].append({'argv':cmd,'exit':p.returncode})
    print(i,p.returncode,p.stderr.decode()[-100:],flush=True)
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
