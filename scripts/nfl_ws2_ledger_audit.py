#!/usr/bin/env python3
"""Independently verify frozen WS2 probabilities; index first actual forecasts.

This is a post-freeze integrity audit, not new model inference or settlement.
"""
import argparse,hashlib,json,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(x):return (json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def audit(root,out):
 indices=[];selected={};quotes={};checks=Counter();known_models=set()
 for path in sorted((root/'live').glob('*/INDEX.json')):
  raw=path.read_bytes();index=json.loads(raw)
  rows_raw=(path.parent/'forecast_rows.json').read_bytes()
  assert sha(rows_raw)==index['forecast_rows_sha256']
  indices.append({'path':str(path),'sha256':sha(raw),'created_at':index['created_at'],
   'forecast_rows_sha256':sha(rows_raw),'code_commit':index['code_commit']})
  for row in json.loads(rows_raw):
   q=row['original_contract'];cid=q['candidate_id']
   if cid in quotes:assert quotes[cid]==q
   quotes[cid]=q
   for model,p in row['models'].items():
    known_models.add(model)
    if p['status']!='forecast':continue
    assert datetime.fromisoformat(row['forecast_created_at'])<datetime.fromisoformat(q['event_start_at'].replace('Z','+00:00'))
    if p['q_over'] is not None:
     assert abs(math.fsum(p[k] for k in ('q_over','q_under','q_push'))-1)<1e-10
     assert all(0<=p[k]<=1 for k in ('q_over','q_under','q_push'))
    if model.startswith('S2-'):
     masses=p['parameters']['masses'];line=q['line']
     assert abs(math.fsum(w for y,w in masses)-1)<1e-12
     assert all(float(y).is_integer() and w>=0 for y,w in masses)
     for key,fn in [('q_over',lambda y:y>line),('q_under',lambda y:y<line),('q_push',lambda y:y==line)]:
      assert abs(p[key]-math.fsum(w for y,w in masses if fn(y)))<1e-12
     mu=math.fsum(y*w for y,w in masses)
     var=math.fsum(w*(y-mu)**2 for y,w in masses)
     assert abs(mu-p['mean'])<1e-10 and abs(var-p['variance'])<1e-8
     checks['independent_s2_mass_probability_and_moment_checks']+=1
   any_forecast=any(p['status']=='forecast' for p in row['models'].values())
   previous=selected.get(cid)
   if previous is None or (not any(p['status']=='forecast' for p in previous['models'].values())):
    selected[cid]={**row,'original_run_index_path':str(path),'original_run_index_sha256':sha(raw)}
   elif any_forecast:
    # Earliest actual forecast is primary. Later freezes remain separately linked.
    checks['later_forecast_rows_preserved_as_versions']+=1
 coverage=defaultdict(Counter);markets=defaultdict(lambda:defaultdict(Counter));windows=defaultdict(Counter)
 for row in selected.values():
  q=row['original_contract']
  for m,p in row['models'].items():
   coverage[m][p['status']]+=1;markets[q['stat']][m][p['status']]+=1
   if p['status']=='forecast':windows[q['event_start_at']][m]+=1
 for counts in list(coverage.values())+[c for ms in markets.values() for c in ms.values()]:
  counts.setdefault('forecast',0);counts.setdefault('unavailable',0)
 assert len(selected)==1845
 out.mkdir(parents=True,exist_ok=False)
 data=b''.join(canonical(selected[cid]) for cid in sorted(selected))
 with (out/'first_forecast_population.jsonl').open('xb') as f:f.write(data)
 report={'schema':'WS2_SUNDAY_FIRST_FORECAST_INDEX_V1','assembled_at':datetime.now(timezone.utc).isoformat(),
  'assembly_is_not_forecast_creation':True,'input_contracts':len(selected),'runs':indices,
  'population_sha256':sha(data),'per_model':coverage,'per_market':markets,'forecast_counts_by_window':windows,
  'math_checks':checks,'production_modified':False,'research_only':True,
  'audit_code_sha256':sha(Path(__file__).read_bytes())}
 raw=canonical(report)
 with (out/'INDEX.json').open('xb') as f:f.write(raw)
 print(json.dumps({'index_path':str(out/'INDEX.json'),'index_sha256':sha(raw),**report},sort_keys=True))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
 a=p.parse_args();audit(a.root,a.out)
