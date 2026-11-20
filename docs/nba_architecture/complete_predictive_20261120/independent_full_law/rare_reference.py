"""Independent high precision beta-NB identity for rare public log-PMF queries."""
from pathlib import Path
import sys,json,math,time
import mpmath as mp
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.full_played_s_v1 import FullPlayedLaw
P=ROOT/'docs/nba_architecture/complete_predictive_20261120';HERE=Path(__file__).resolve().parent
x=json.loads((P/'FULL_S_CANDIDATE.json').read_bytes());mp.mp.dps=70
out=[]
for name,stat,k in [('Cody Williams','threes',100),('Cody Williams','threes',1000),('LaMelo Ball','points',1000)]:
 model=next(r['model'] for r in x['rows'] if r['name']==name and r['statistic']==stat)
 law=FullPlayedLaw(**model['rate_parameters'],minutes=model['minute_parameters']);actual=law.logpmf(k)
 d=model['minute_parameters'];p,q=map(mp.mpf,[d['ot_probability'],d['ot_continuation']]);ek=p/(1-q);ek2=p*(1+q)/(1-q)**2
 share=mp.mpf(d['mean'])/(48+5*ek);sv=max(mp.mpf('0.000001'),(mp.mpf(d['variance'])-share**2*25*(ek2-ek**2))/(2304+480*ek+25*ek2));sv=min(sv,mp.mpf('.95')*share*(1-share));c=share*(1-share)/sv-1;a,b=share*c,(1-share)*c
 A,B=map(mp.mpf,[model['rate_parameters']['alpha'],model['rate_parameters']['beta']]);terms=[];started=time.time();n=actual['ot_terms']
 for i in range(n+1):
  L=48+5*i;w=1-p if i==0 else p*(1-q)*q**(i-1)
  h=mp.hyp2f1(A+k,a+k,a+b+k,-L/B)
  assert h>0
  logv=mp.loggamma(k+A)-mp.loggamma(A)-mp.loggamma(k+1)+k*mp.log(L/B)+mp.loggamma(a+k)+mp.loggamma(a+b)-mp.loggamma(a)-mp.loggamma(a+b+k)+mp.log(h)
  terms.append(w*mp.exp(logv))
 probability=(1-mp.mpf('.01'))*mp.fsum(terms);expected=float(mp.log(probability));diff=abs(expected-actual['log_probability'])
 assert diff<5e-7,(name,stat,k,diff)
 out.append(dict(player=name,statistic=stat,count=k,precision_digits=70,ot_terms=n,independent_log_probability=expected,public_log_probability=actual['log_probability'],absolute_log_difference=diff,public_omitted_OT_relative_probability_bound=actual['omitted_OT_relative_probability_bound'],elapsed_seconds=time.time()-started))
print(json.dumps(out,indent=2,sort_keys=True));(HERE/'RARE_RESULTS.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
