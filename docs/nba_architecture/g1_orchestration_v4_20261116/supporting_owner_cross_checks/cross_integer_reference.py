import hashlib,importlib.util,json,random,subprocess,tempfile
from pathlib import Path
from v2.nba_s_family.source_accounting import validate_count_feasibility
from v2.nba_s_family.model import SFError
pin='542d91a7d6c134441ce8cb9bb54312095b186833';path='v2/nba_architecture/p1_integer_accounting.py'
raw=subprocess.check_output(['git','show',pin+':'+path]);rng=random.Random(14817);cases=[];failures=[]
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'p1.py';p.write_bytes(raw);spec=importlib.util.spec_from_file_location('p1_integer_reference',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 for i in range(5000):
  fga=rng.randrange(6);a3=rng.randrange(fga+1);t=rng.randrange(a3+1);two=rng.randrange(fga-a3+1);fta=rng.randrange(6);ftm=rng.randrange(fta+1);oreb=rng.randrange(5);dreb=rng.randrange(5);ast=rng.randrange(5)
  whole=dict(points=2*two+3*t+ftm,fgm=two+t,fga=fga,threes=t,fg3a=a3,ftm=ftm,fta=fta,rebounds=oreb+dreb,oreb=oreb,dreb=dreb,assists=ast)
  whole.update(pr=whole['points']+whole['rebounds'],pa=whole['points']+ast,ra=whole['rebounds']+ast,pra=whole['points']+whole['rebounds']+ast)
  subset={k:v for k,v in whole.items() if rng.random()<.5}
  if subset and i%2:
   k=rng.choice(list(subset));subset[k]=max(0,subset[k]+rng.choice([-1,1]))
  p1=module.partial_counts_feasible(subset)
  try:p2=validate_count_feasibility(subset)
  except SFError as e:
   if e.reason!='P1_NATIVE_INTEGER_ACCOUNTING_INFEASIBLE':raise
   p2=False
  cases.append(dict(input=subset,P1=p1,P2=p2))
  if p1!=p2:failures.append(cases[-1])
result=dict(scope='SUPPORTING_SYNTHETIC_DIFFERENTIAL_QC_NOT_INDEPENDENT_ACCEPTANCE',P1=pin,P1_source_sha256=hashlib.sha256(raw).hexdigest(),P2_source_sha256=hashlib.sha256(Path('v2/nba_s_family/source_accounting.py').read_bytes()).hexdigest(),seed=14817,cases=len(cases),input_output_sha256=hashlib.sha256(json.dumps(cases,sort_keys=True,separators=(',',':')).encode()).hexdigest(),failures=failures)
Path('work/cross_integer_reference_cases.json').write_text(json.dumps(cases,sort_keys=True,indent=2)+'\n')
print(json.dumps(result,sort_keys=True,indent=2));raise SystemExit(bool(failures))
