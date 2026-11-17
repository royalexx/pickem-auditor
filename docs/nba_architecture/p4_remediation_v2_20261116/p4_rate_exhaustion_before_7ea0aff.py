import hashlib,json,subprocess
from pathlib import Path
from unittest.mock import patch
from research.nba_p4_latest.fixture import build
from v2.nba_joint.latest_upstream import prepare,load_upstream
from v2.nba_joint.integration_v2 import Prepared
from test_p4_joint import PARAMETERS
pin=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
root=prepare();p,g,o,side,a,m,r=build(root);p2,_=load_upstream(root)
prepared=Prepared(p,g,o,side,a,m,r,p2,42);sid=side['scenarios'][0]['scenario_id']
positive=prepared.players(sid,PARAMETERS)
prepared=Prepared(p,g,o,side,a,m,r,p2,42)
with patch('v2.nba_joint.integration_v2.draw_mixing_rate',return_value=1.) as forced:
 try:prepared.players(sid,PARAMETERS);raise AssertionError('exhaustion should reject')
 except ValueError as e:
  result=dict(scope='SYNTHETIC_BRANCH_COVERAGE_NOT_REPLACEMENT_MODEL_INTEGRATION',P4=pin,source_sha256=hashlib.sha256(Path('v2/nba_joint/integration_v2.py').read_bytes()).hexdigest(),forced_mixing_rates='all1 hence points1<3*threes1',positive_actual_sampler_player_rows=len(positive),observed_exception=type(e).__name__,reason=str(e),exception_metadata=e.__dict__,draw_mixing_calls=forced.call_count,expected_rejected_pairs=4096,observed_audits=prepared._audits)
print(json.dumps(result,indent=2,sort_keys=True))
