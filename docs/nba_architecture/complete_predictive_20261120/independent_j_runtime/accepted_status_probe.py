from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tests.nba_joint.test_residual_events_v1 import fixture
from v2.nba_joint.residual_events_v1 import simulate
from v2.nba_joint.residual_audit_v1 import audit_run
from v2.nba_architecture.p1_subset_handoff_v1 import digest,canonical
r=simulate(fixture(),seed=41,n=1);r['scenarios'][0]['proposals'][-1]['status']='REJECT_EXECUTION';r.pop('payload_sha256');r['payload_sha256']=digest(canonical(r))
try:print(json.dumps({'attack':'accepted_last_proposal_relabelled_REJECT_EXECUTION','status':'RED_REJECTED_PATH_ACCEPTED','audit':audit_run(r)}));raise SystemExit(1)
except ValueError as e:print(json.dumps({'attack':'accepted_last_proposal_relabelled_REJECT_EXECUTION','status':'REJECTED','reason':str(e)}))
