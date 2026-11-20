"""Independent exact-parameter, high-precision necessary-condition witnesses."""
from pathlib import Path
from decimal import Decimal,localcontext
import json,math,sys
ROOT=Path(__file__).resolve().parents[4];P=ROOT/'docs/nba_architecture/complete_predictive_20261120';HERE=Path(__file__).resolve().parent
w=json.loads((P/'S_J_COMPATIBILITY.json').read_bytes());f=json.loads((P/'actual_full_forecast/forecast.json').read_bytes());ref={(r['player_id'],r['statistic']):r['model'] for r in f['law_payload']['rows']};results=[];pointwise=0
for y in range(41):
 for order in range(1,36):
  fall=lambda n:math.factorial(n)//math.factorial(n-order) if n>=order else 0
  for extra in range(4):assert fall(3*y+extra)>=3**order*fall(y);pointwise+=1
for row in w['rows']:
 pid=row['player_id'];v=row['witness'];r=v['order'];a=ref[(pid,'points')];b=ref[(pid,'threes')];assert a['minute_parameters']==b['minute_parameters'];assert a['zero_prior_mean']==b['zero_prior_mean']<1;assert a['rate_parameters']==v['points_rate_parameters'];assert b['rate_parameters']==v['threes_rate_parameters'];checks=[]
 for precision in (100,180):
  with localcontext() as ctx:
   ctx.prec=precision;ap=Decimal.from_float(a['rate_parameters']['alpha']);at=Decimal.from_float(b['rate_parameters']['alpha']);bp=Decimal.from_float(a['rate_parameters']['beta']);bt=Decimal.from_float(b['rate_parameters']['beta']);lr=sum(((ap+j).ln()-(at+j).ln() for j in range(r)),Decimal(0))+r*(bt.ln()-bp.ln()-Decimal(3).ln());checks.append(lr)
 assert abs(checks[0]-checks[1])<Decimal('1e-90');assert checks[1]<Decimal(-1);assert abs(float(checks[1])-v['log_factorial_moment_ratio'])<1e-9
 results.append({'player_id':pid,'order':r,'log_ratio_180_decimal_digits':str(checks[1]),'owner_log_ratio':v['log_factorial_moment_ratio'],'exact_reference_parameters_match':True,'common_minutes_and_zero_prior_verified':True,'necessary_condition_violated':True})
assert len(results)==14
result={'status':'VERIFIED14_NECESSARY_FACTORIAL_MOMENT_VIOLATIONS','source_forecast_raw_sha256':__import__('hashlib').sha256((P/'actual_full_forecast/forecast.json').read_bytes()).hexdigest(),'arithmetic':'PythonDecimal ln, exact binary64 parameter values, independent 100/180-digit summation','pointwise_integer_cases_checked':pointwise,'proof':'For integer y>=r every factor 3y-j >= 3(y-j), otherwise (y)_r=0; (x)_r is nondecreasing on nonnegative integer x. Integrate finite nonnegative factorial moments. Common nonzero minute/zero-mixture factor cancels.','finite_moments':'Gamma rates and beta-scaled geometric-OT durations have finite moments of every finite integer order.','rows':results,'TV_lower_bound_claimed':False,'approximate_coupling_impossibility_claimed':False,'predictive_quality_claimed':False}
(HERE/'MOMENT_RESULTS.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps({'status':result['status'],'players':len(results),'pointwise_cases':pointwise,'orders':[r['order'] for r in results],'maximum_log_ratio':max(float(r['log_ratio_180_decimal_digits']) for r in results),'TV_lower_bound_claimed':False},indent=2))
