from pathlib import Path
import sys,json,tempfile
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tests.nba_joint.test_coherent_predictive_v1 import coherent_fixture
from v2.nba_joint.coherent_predictive_v1 import generate,validate_bank
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
m,c=coherent_fixture()
with tempfile.TemporaryDirectory() as temp:
 b=generate(m,c,Path(temp)/'trace',seed=5,n=1);b['trace_json_bytes']+=1;b['trace_gzip_bytes']+=1;b.pop('payload_sha256');b['payload_sha256']=digest(canonical(b))
 try:print(json.dumps({'status':'RED_FALSE_TRACE_BYTE_TOTALS_ACCEPTED','audit':validate_bank(b,Path(temp)/'trace',m)}));raise SystemExit(1)
 except ValueError as e:print(json.dumps({'status':'REJECTED','reason':str(e)}))
