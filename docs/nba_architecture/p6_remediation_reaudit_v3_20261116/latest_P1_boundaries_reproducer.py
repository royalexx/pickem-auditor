import sys,json,tempfile
from pathlib import Path
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--p2-root',type=Path,required=True);ap.add_argument('--p3-root',type=Path,required=True);args=ap.parse_args()
import v2
# Load exact latest owner modules; common G0 remains unchanged.
v2.__path__.extend([str(args.p2_root/'v2'),str(args.p3_root/'v2')])
from scripts.nba_p1_build_pregame import execute
from v2.nba_s_family.integration import history_from_p1
from v2.nba_o_bridge import build_p1_opportunity
r=Path('docs/nba_architecture/p1_remediation_20261117')
with tempfile.TemporaryDirectory() as td:
 output=Path(td)/'p.json';receipt=execute(r/'real_ws1_manifest.json',output,source_root=r);p=json.loads(output.read_text())
 try:
  history_from_p1(p,annotations={},source_manifest={},stat='points',asof_cutoff_utc=p['training_cutoff_at']);s={'status':'UNEXPECTED_ACCEPTANCE'}
 except ValueError as e:s={'status':'BLOCKED','code':str(e)}
 o=build_p1_opportunity(p,None,{},raw_sources={},home_team_id=p['team_ids'][0],home_receipt=None,model=None,seed=0)
 print(json.dumps(dict(P1='201ff0aacbd398c7a260f1af3b1c16f4dd8abaa3',P2='7ca4269c98a27def485eaa8122ea7148cd0c2c0a',P3='191b3f654b3a3ca7dc813edbfc9aacdf35729dff',scope='SEPARATE_BOUNDARY_ABSTENTION_TEST_NOT_CONTINUATION_OF_BLOCKED_AUTHENTIC_CASE',P1_receipt=receipt,S_result=s,O_result=o),indent=2,sort_keys=True))
