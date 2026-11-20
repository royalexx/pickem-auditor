from pathlib import Path
import sys,json,tempfile
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tests.nba_joint.test_coherent_predictive_v1 import coherent_fixture
from v2.nba_joint.coherent_predictive_v1 import generate,rows,validate_bank
m,c=coherent_fixture();p=next(p for p in c['frozen_candidates'] if p['player_id']=='A0');p['team_id']='B'
with tempfile.TemporaryDirectory() as temp:
 try:
  b=generate(m,c,Path(temp)/'trace',seed=5,n=1);validate_bank(b,Path(temp)/'trace',m);r=next(r for r in rows(b) if r['player_id']=='A0' and r['statistic']=='points');print(json.dumps({'status':'RED_WRONG_TEAM_COHORT_ACCEPTED','bank_status':b['status'],'claimed_team':r['team_id'],'generated_actor_team':'A','samples':r['samples']}));raise SystemExit(1)
 except ValueError as e:print(json.dumps({'status':'REJECTED','reason':str(e)}))
