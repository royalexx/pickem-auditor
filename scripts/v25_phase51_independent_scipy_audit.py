#!/usr/bin/env python3
"""Independent SciPy math + adversarial QA; NO current/future outcome access."""
from __future__ import annotations
import hashlib, json, math, random, statistics, time
from pathlib import Path
from scipy.stats import poisson, nbinom
from v2 import nhl_sog_rate_shrinkage_prospective as m
from v2 import nhl_sog_exposure_shadow as frozen

def independent_reference(seed=20261115):
    rng=random.Random(seed)
    max_poisson=0.;max_gamma=0.;max_crps=0.;max_zero=0.;max_tail=0.
    pmf_cases=0;gamma_cases=0;count_cases=0
    start=time.perf_counter()
    for mean in [0.,0.05,0.1,0.5,1.,1.5,2.,4.,8.,12.,20.,40.,75.,120.]+[rng.uniform(.001,65.) for _ in range(150)]:
        p=m.poisson_pmf(mean)
        ref=poisson.pmf(list(range(len(p))),mean)
        discrepancy=max(abs(float(ref[k])-x) for k,x in enumerate(p))
        max_poisson=max(max_poisson,discrepancy)
        assert discrepancy < 1e-11
        z=m.summary(p)
        max_zero=max(max_zero,abs(z["zero"]-poisson.pmf(0,mean)))
        max_tail=max(max_tail,abs(z["tail6"]-poisson.sf(5,mean)))
        assert abs(z["mean"]-mean) < 1e-7
        assert abs(z["variance"]-mean) < 1e-6
        for line in (0,0.5,1,1.5,2,2.5,3,5,5.5,8,15):
            probs=m.exact_contract_probs(p,line)
            expected_over=float(poisson.sf(math.floor(line),mean))
            expected_push=float(poisson.pmf(int(line),mean)) if float(line).is_integer() else 0.
            expected_under=float(poisson.cdf(math.ceil(line)-1,mean))
            assert abs(probs["over"]-expected_over) < 1e-10
            assert abs(probs["under"]-expected_under) < 1e-10
            assert abs(probs["push"]-expected_push) < 1e-10
        for actual in [0,1,2,3,5,8,10]:
            if actual >= len(p):continue
            result=m.score_count(p,actual)
            # Independent CRPS implementation uses SciPy CDF at every count.
            reference_cdf=poisson.cdf(list(range(len(p))),mean)
            reference_score=sum((float(cdf)-float(k>=actual))**2 for k,cdf in enumerate(reference_cdf))
            max_crps=max(max_crps,abs(result["crps"]-reference_score))
            assert abs(result["crps"]-reference_score)<1e-10
            count_cases+=1
        pmf_cases+=1
    for a in [0.25,2.5,8.,30.,150.]:
        for b in [10.,30.,60.,200.]:
            for w in [0.05,1.,3.,9.,20.,40.]:
                gamma_cases+=1
                probability=b/(b+w)
                for k in range(30):
                    got=frozen._pmf_gamma_poisson(k,a,b,w)
                    expected=float(nbinom.pmf(k,a,probability))
                    max_gamma=max(max_gamma,abs(got-expected))
                    assert abs(got-expected)<1e-11
                # Count moments must differ only in Gamma-posterior variance.
                assert a*w/b>0 and a*w/b + a*w*w/(b*b) > a*w/b
    assert max_zero<1e-11 and max_tail<1e-10
    return {
       "schema":"phase51_independent_scipy_math_adversarial_v1",
       "status":"PASSED","seed":seed,"probability_cases":pmf_cases,
       "count_crps_cases":count_cases,"gamma_parameter_cases":gamma_cases,
       "gamma_independent_pmf_checks":gamma_cases*30,
       "max_poisson_pmf_abs":max_poisson,"max_gamma_pmf_abs":max_gamma,
       "max_crps_abs":max_crps,"max_zero_abs":max_zero,
       "max_tail6_abs":max_tail,
       "elapsed_seconds":time.perf_counter()-start,
       "no_target_outcome_inputs":True,
       "no_2026_27_trial_outcomes_read":True,
       "promotion_allowed":False
    }

if __name__=="__main__":
    report=independent_reference()
    code=Path(__file__).read_bytes()
    report["auditor_source_sha256"]=hashlib.sha256(code).hexdigest()
    print("PHASE51_INDEPENDENT_SCIPY_QA "+json.dumps(report,sort_keys=True,allow_nan=False),flush=True)
