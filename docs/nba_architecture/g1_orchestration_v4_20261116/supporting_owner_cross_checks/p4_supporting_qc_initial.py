import hashlib,json,math,subprocess
from pathlib import Path
import numpy as np
from research.nba_p4_latest.fixture import build
from research.nba_p4_latest.numerical_reference import references
from v2.nba_joint.latest_upstream import prepare,load_upstream,registry
from v2.nba_joint.integration_v2 import draw_mixing_rate,Prepared
from test_p4_joint import PARAMETERS

pin=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert pin=='7ea0aff04b04ed209b47e1728b2b52c3e0a1aecb'
root=prepare();p,g,o,side,artifacts,manifest,roles=build(root);p2,p3=load_upstream(root)
checks=[];n=200000
for stat,a in artifacts.items():
 if stat=='three_conversion':continue
 for m in (0.,37.25):
  pred=p2.predict_conditional(a,player_id=p['players'][0]['player_id'],role=roles[p['players'][0]['player_id']],projected_exposure=m,statistic=stat)
  assert pred.abstain_reason is None
  par=pred.parameters;family=a.data['family'];shape=par['alpha'] if family=='S1' else par['dispersion'];scale=1/par['beta'] if family=='S1' else par['rate_mean']/shape
  mass=pred.parameters['support']
  if m==0:ref=[1.]
  else:
   ratio=scale*m/(1+scale*m);ref=[math.exp(-shape*math.log1p(scale*m))]
   for k in range(len(mass)-1):ref.append(ref[-1]*(k+shape)/(k+1)*ratio)
  error=max(abs(x['mass']-q) for x,q in zip(mass,ref));assert error<2e-11
  checks.append(dict(stat=stat,family=family,exposure=m,max_recurrence_error=error,raw_retained_mass=sum(ref),declared_tail=pred.parameters['tail_mass_upper_bound']))
 for family in ('S1','S2'):
  rng=np.random.default_rng(817)
  rates=np.array([draw_mixing_rate(par,family,rng) for _ in range(n)])
  shape=par['alpha'] if family=='S1' else par['dispersion'];scale=1/par['beta'] if family=='S1' else par['rate_mean']/shape
  mu=shape*scale;var=shape*scale**2;mu4=3*var**2+6*shape*scale**4
  mean_se=math.sqrt(var/n);var_se=math.sqrt((mu4-(n-3)/(n-1)*var**2)/n)
  mean_z=abs(float(rates.mean())-mu)/mean_se if mean_se else 0
  var_z=abs(float(rates.var(ddof=1))-var)/var_se if var_se else 0
  assert mean_z<8 and var_z<8
  checks.append(dict(stat=stat,synthetic_mixing_family=family,samples=n,mean_z=mean_z,variance_z=var_z,expected_rate_mean=mu,expected_rate_variance=var))
# Actual S3 interface: zero attempts, integer8, cap4096; no actual attempts.
a=artifacts['three_conversion'];pid=p['players'][0]['player_id'];conv=[]
for attempts in (0,8,4096):
 r=p2.predict_conditional(a,player_id=pid,role=roles[pid],projected_exposure=attempts,statistic='threes');assert r.abstain_reason is None
 par=r.parameters;alpha,beta=par['alpha'],par['beta'];pm=par['support'];mean=sum(x['value']*x['mass'] for x in pm);expected=attempts*alpha/(alpha+beta)
 assert abs(mean-expected)<1e-8 and len(pm)==attempts+1 and par['tail_mass_upper_bound']==0
 conv.append(dict(attempts=attempts,retained_count_support=len(pm),mean_error=mean-expected,tail=0))
assert p2.predict_conditional(a,player_id=pid,role=roles[pid],projected_exposure=8.5,statistic='threes').abstain_reason=='PROJECTED_3PA_INTEGER_REQUIRED'
# Observe actual zero-minute scenario mapping if present; no altered source/model.
z=[]
prepared=Prepared(p,g,o,side,artifacts,manifest,roles,p2,42)
for sc in side['scenarios']:
 players=prepared.players(sc['scenario_id'],PARAMETERS)
 for x,r in zip(sc['players'],players):
  if x['minutes']==0:
   assert all(v==0 for v in r['rates'].values());z.append(dict(player=x['player_id'],scenario=sc['scenario_id'],rates=r['rates']))
refs=references();assert refs['all_pass']
print(json.dumps(dict(scope='IMPLEMENTATION_SUPPORTING_QC_NOT_INDEPENDENT_GATE_ACCEPTANCE',P4=pin,source_hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path('v2/nba_joint/integration_v2.py'),Path('research/nba_p4_latest/numerical_reference.py')]},registry=registry(),checks=checks,S3=conv,zero_exposure_actual_scenarios=z,references=refs,findings=['S1 Gamma(alpha,1/beta) matches P2 Gamma-Poisson law.','S2 Gamma(k,rate_mean/k) matches current P2 NB2 count law; it does not additionally integrate Gamma(alpha,beta) posterior uncertainty.','PTS/3PM compatibility rejection and share/pacing/event allocation change marginals. Proposal retains explicit independent-acceptance pending.','Aggregate possession/free-throw/event co-presence/tied-OT semantics remain mandatory blocked proofs, not established by these checks.']),indent=2,sort_keys=True))
