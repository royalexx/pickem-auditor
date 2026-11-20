"""Independent synthetic public auditor mutation sensitivity, no actual model run."""
from pathlib import Path
import sys,copy,json
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tests.nba_joint.test_residual_events_v1 import fixture
from v2.nba_joint.residual_events_v1 import simulate
from v2.nba_joint.residual_audit_v1 import audit_path
m=fixture()
r=simulate(m,seed=41,n=1);s=r['scenarios'][0];base=s['proposals'][-1];result=[]
for attack in ('hold_shot_clock_before','missing_final_period_end_duplicate_prior'):
 x=copy.deepcopy(base)
 if attack=='hold_shot_clock_before':next(row for row in x['ledger'] if row['kind']=='PERIOD_HOLD_END')['shot_clock_before']+=100.
 else:
  old=x['ledger'];new=[]
  for row in old:
   if row['kind']=='PERIOD_END' and row['period']==4:continue
   new.append(row)
   if row['kind']=='PERIOD_END' and row['period']==3:new.append(copy.deepcopy(row))
  positions={row['index']:n for n,row in enumerate(new)}
  for n,row in enumerate(new):
   row['index']=n
   if row['kind']=='FREE_THROW':row['foul']=positions[row['foul']]
   if row['kind']=='REBOUND':row['miss']=positions[row['miss']]
  x['ledger']=new;x['period_scores']=[row['score'] for row in new if row['kind']=='PERIOD_END']
 try:out=audit_path(s['fixed'],x);result.append({'attack':attack,'status':'RED_INVALID_PATH_ACCEPTED','audit':out})
 except ValueError as e:result.append({'attack':attack,'status':'REJECTED','reason':str(e)})
print(json.dumps({'synthetic_only':True,'mutations':result},indent=2));sys.exit(any(x['status'].startswith('RED') for x in result))
