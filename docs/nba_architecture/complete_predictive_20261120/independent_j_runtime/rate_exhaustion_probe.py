from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tests.nba_joint.test_residual_events_v1 import fixture
from v2.nba_joint.residual_events_v1 import simulate
m=fixture()
for p in m['named_players']:
 p['rates']['points']={'alpha':1.,'beta':1e12};p['rates']['threes']={'alpha':1.,'beta':1e-12}
r=simulate(m,seed=41,n=1)
print(json.dumps({'synthetic_only':True,'scenario_denominator':r['scenario_denominator'],'status':r['status'],'scenario_records':len(r['scenarios']),'failed':r['failed'],'rate_proposals_preserved':sum(len(s.get('fixed',{}).get('rate_rejections',[])) for s in r['scenarios']),'scenarios_dropped':r['scenarios_dropped']},indent=2))
