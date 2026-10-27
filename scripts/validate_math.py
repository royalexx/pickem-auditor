"""Optional independent numerical checks; requires scipy, never accesses feeds."""
import json
import math
from scipy.stats import poisson, nbinom, norm, gamma
from scipy.integrate import quad
import pickem_math as pm


def main():
    errors={'poisson_point':0.0,'negbin_point':0.0,
            'poisson_predictive':0.0,'normal_predictive':0.0,'negbin_quadrature':0.0,
            'gamma_quantile_relative':0.0,'point_push_under':0.0}
    counts={key:0 for key in errors}
    for shape in (.001,.01,.03,.1,.5,1,3,100,10000):
        for probability in (.5/41,.1,.5,.9,40.5/41):
            expected=gamma.ppf(probability,shape)
            actual=pm._gamma_ppf(probability,shape,1)
            error=abs(actual/expected-1) if expected else abs(actual)
            errors['gamma_quantile_relative']=max(errors['gamma_quantile_relative'],float(error))
            counts['gamma_quantile_relative']+=1
    for mu in (.1,.5,3,20,200):
        for line in (0,.5,2,2.5,20,200):
            for dist,kw,oracle in [('poisson',{},poisson(mu)),('negbin',{'r':2},nbinom(mu,.5)),
                                   ('normal',{'sd':max(mu/4,.1)},norm(mu,max(mu/4,.1)))]:
                got,push=pm.side_probs(dist,mu,line,'under',**kw)
                whole=line==int(line)
                if dist=='normal':
                    expected=oracle.cdf(math.ceil(line)-.5)
                    expected_push=oracle.cdf(line+.5)-oracle.cdf(line-.5) if whole else 0
                else:
                    expected=oracle.cdf(math.ceil(line)-1)
                    expected_push=oracle.pmf(line) if whole else 0
                errors['point_push_under']=max(errors['point_push_under'],float(abs(got-expected)),float(abs(push-expected_push)))
                counts['point_push_under']+=2
    for mean in (.1,.5,1,3,10,50,200):
        for n in (1,5,20,100):
            for line in (0,.5,2,2.5,10,50,200):
                over,push=pm.side_probs('poisson',mean,line,'over')
                expected=poisson.sf(math.floor(line),mean)
                errors['poisson_point']=max(errors['poisson_point'],abs(over-expected))
                out=pm.project('poisson','over',line,mean,n)
                expected=nbinom.sf(math.floor(line),mean*n,n/(n+1))
                errors['poisson_predictive']=max(errors['poisson_predictive'],abs(out['q_win_robust']-expected))
                q,_=pm.side_probs('negbin',mean,line,'over',r=2)
                errors['negbin_point']=max(errors['negbin_point'],abs(q-nbinom.sf(math.floor(line),mean,.5)))
                for key in ('poisson_point','poisson_predictive','negbin_point'):counts[key]+=1
    for mean in (3,20,100):
        for n in (1,5,20,100):
            for line in (0,2,2.5,20,100):
                sd=mean/4
                out=pm.project('normal','over',line,mean,n,sd=sd)
                expected=norm.sf(math.floor(line)+.5,loc=mean,scale=sd*math.sqrt(1+1/n))
                errors['normal_predictive']=max(errors['normal_predictive'],abs(out['q_win_robust']-expected))
                counts['normal_predictive']+=1
    # Independent adaptive integration for NB mean uncertainty; approximate method.
    for mean in (.5,3,10):
        for n in (5,20):
            for line in (0,2.5,10):
                ratio=2
                shape=mean*n/ratio;rate=n/ratio
                expected=quad(lambda mu:nbinom.sf(math.floor(line),mu/(ratio-1),1/ratio)*gamma.pdf(mu,shape,scale=1/rate),
                              0,math.inf,epsabs=1e-10)[0]
                out=pm.project('negbin','over',line,mean,n,var_ratio=ratio)
                errors['negbin_quadrature']=max(errors['negbin_quadrature'],abs(out['q_win_robust']-expected))
                counts['negbin_quadrature']+=1
    limits={key:1e-8 for key in errors};limits['negbin_quadrature']=.002
    result=dict(counts=counts,max_absolute_errors={k:float(v) for k,v in errors.items()},
                tolerances=limits,passed=all(errors[k]<=limits[k] for k in errors))
    print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
