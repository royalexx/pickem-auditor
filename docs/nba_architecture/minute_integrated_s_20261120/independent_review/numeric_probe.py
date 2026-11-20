"""Independent ordinary-mixture checks; no new artifacts, outcomes, or scores."""
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest
from scipy.integrate import quad
from scipy.stats import nbinom

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.minute_integrated_s_v1 import integrate,replay
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest

HERE=Path(__file__).resolve().parent;P=HERE.parent
OLD=ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive'
ORIGINAL=json.loads((OLD/'forecast.json').read_bytes());SAVED=json.loads((P/'execution/candidate.json').read_bytes())
RESULT={};REF={}

def independent_law(d):
    p,q=d['ot_probability'],d['ot_continuation'];ek=p/(1-q);ek2=p*(1+q)/(1-q)**2
    el=48+5*ek;el2=2304+480*ek+25*ek2;share=d['mean']/el
    variance=max(1e-6,(d['variance']-share*share*25*(ek2-ek*ek))/el2)
    variance=min(variance,.95*share*(1-share));concentration=share*(1-share)/variance-1
    a,b=share*concentration,(1-share)*concentration
    parts=[(48.,1-p)];k=1
    while p*q**(k-1)>1e-12:parts.append((48.+5*k,p*(1-q)*q**(k-1)));k+=1
    return a,b,parts

def direct_integral(d,*,power=0,alpha=None,beta=None,count=None):
    a,b,parts=independent_law(d);logB=math.lgamma(a)+math.lgamma(b)-math.lgamma(a+b)
    value=0.;error=0.
    for length,weight in parts:
        lower=.5/length;factor=math.exp(b*math.log1p(-lower)-logB)
        if count is not None:coefficient=math.lgamma(count+alpha)-math.lgamma(alpha)-math.lgamma(count+1)
        def integrand(x):
            u=lower+(1-lower)*x;m=length*u
            out=factor*u**(a-1)*m**power
            if count is not None:out*=math.exp(coefficient+alpha*math.log(beta)+count*math.log(m)-(alpha+count)*math.log(beta+m))
            return out
        estimate,bound=quad(integrand,0.,1.,weight='alg',wvar=(0.,b-1),epsabs=1e-12,epsrel=1e-12,limit=200)
        value+=weight*estimate;error+=weight*bound
    return value,error

class NumericReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_rows={(r['player_id'],r['statistic']):r for r in ORIGINAL['rows']}
        cls.minutes={r['player_id']:r for r in ORIGINAL['minutes']}
        cls.saved_rows={(r['player_id'],r['statistic']):r for r in SAVED['rows']}
        RESULT.update(tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            implementation_raw_sha256=digest((ROOT/'v2/nba_architecture/minute_integrated_s_v1.py').read_bytes()),
            original_forecast_raw_sha256=digest((OLD/'forecast.json').read_bytes()),candidate_raw_sha256=digest((P/'execution/candidate.json').read_bytes()),
            candidate_payload_sha256=SAVED['payload_sha256'],new_forecasts_issued=0,new_artifact_fits=0,holdout_scores=0)

    def test_01_scope_hash_clock_denominators_and_all56_supports(self):
        self.assertEqual((SAVED['candidate_denominator'],SAVED['attempt_denominator'],SAVED['integrated_rows'],SAVED['abstained_rows']),(35,140,56,84))
        self.assertEqual(set(self.saved_rows),set(self.original_rows));self.assertFalse(SAVED['new_forecast_issued'])
        payload={k:v for k,v in SAVED.items() if k not in ('payload_sha256','candidate_computation_started_at','candidate_computation_completed_at','payload_hash_domain')}
        self.assertEqual(digest(canonical(payload)),SAVED['payload_sha256'])
        self.assertLess(ORIGINAL['forecast_at'],SAVED['candidate_computation_started_at'])
        self.assertLessEqual(SAVED['candidate_computation_started_at'],SAVED['candidate_computation_completed_at'])
        max_mean=0.;max_variance=0.;evidence=[]
        for key,original in self.original_rows.items():
            row=self.saved_rows[key];value=row['distribution']
            self.assertEqual(value is not None,original['forecast'] is not None)
            if value is None:self.assertEqual(row['reason'],original['reason']);continue
            self.assertFalse(value['full_played_conditional_distribution']);self.assertFalse(value['joint_law'])
            self.assertIsNone(value['participation_probability']);self.assertIsNone(value['legal_eligibility'])
            self.assertIn('minutes_at_least_0.5',value['conditioning']);self.assertTrue(value['minute_uncertainty_integrated'])
            self.assertFalse(value['quadrature_difference_is_rigorous_bound']);self.assertFalse(value['production_release'])
            support=value['support'];mass=[a['mass'] for a in support]
            self.assertEqual([r['value'] for r in support],list(range(len(support))))
            self.assertTrue(all(math.isfinite(v) and v>=0 for v in mass));self.assertAlmostEqual(math.fsum(mass),1.,places=12)
            self.assertAlmostEqual(value['retained_ordinary_exposure_probability']+value['excluded_sub30_probability_within_original_retained_OT']+value['omitted_OT_mass'],1.,places=12)
            pid=key[0];law=self.minutes[pid]['forecast']['distribution']
            if pid not in REF:REF[pid]=[direct_integral(law,power=i)[0] for i in (0,1,2)]
            z,first,second=REF[pid];em=first/z;em2=second/z
            rate=original['forecast']['parameters'];alpha,beta=rate['alpha'],rate['beta']
            expected=alpha/beta*em;variance=expected+alpha*(alpha+1)/beta**2*em2-expected**2
            self.assertAlmostEqual(z,value['retained_ordinary_exposure_probability'],places=11)
            self.assertLess(abs(expected-value['analytic_mean_before_count_truncation']),1e-9)
            self.assertLess(abs(variance-value['analytic_variance_before_count_truncation']),1e-7)
            numerical=math.fsum(i*p for i,p in enumerate(mass));numerical2=math.fsum(i*i*p for i,p in enumerate(mass))-numerical**2
            self.assertLess(abs(numerical-expected),1e-7);self.assertLess(abs(numerical2-variance),1e-6)
            fixed=value['matched_fixed_ordinary_control'];self.assertAlmostEqual(fixed['mean'],expected,places=9)
            self.assertGreater(variance,fixed['variance'])
            self.assertAlmostEqual(variance-fixed['variance'],alpha*(alpha+1)/beta**2*(em2-em**2),places=8)
            _,_,parts=independent_law(law);tail=float(nbinom.sf(len(mass)-1,alpha,beta/(beta+parts[-1][0])))
            self.assertAlmostEqual(tail,value['count_tail_bound_within_retained_OT'],places=15)
            self.assertLess(tail,1e-12)
            max_mean=max(max_mean,abs(numerical-expected));max_variance=max(max_variance,abs(numerical2-variance))
            evidence.append(dict(player_id=pid,statistic=key[1],ordinary_probability=z,excluded_sub30_probability=value['excluded_sub30_probability_within_original_retained_OT'],
                original_fixed_minutes=self.minutes[pid]['forecast']['expected_minutes_given_played'],ordinary_conditional_minutes=em,
                independent_integrated_mean=expected,independent_integrated_variance=variance,
                omitted_OT_after_ordinary_conditioning_upper_bound=value['omitted_OT_mass']/z))
        RESULT['all56_independent_moments']=evidence;RESULT['max_mean_error']=max_mean;RESULT['max_variance_error']=max_variance

    def test_02_low_and_high_player_pmfs_against_independent_adaptive_weighted_quad(self):
        results=[]
        for name in ('Cody Williams','Kris Murray','LaMelo Ball'):
            m=next(r for r in ORIGINAL['minutes'] if r['name']==name);pid=m['player_id'];law=m['forecast']['distribution'];z=direct_integral(law)[0]
            for stat in ('points','rebounds','assists','threes'):
                original=self.original_rows[pid,stat];parameters=original['forecast']['parameters'];value=self.saved_rows[pid,stat]['distribution']
                for count in (0,1,5,10,30):
                    probability,error=direct_integral(law,alpha=parameters['alpha'],beta=parameters['beta'],count=count)
                    probability/=z;actual=value['support'][count]['mass']
                    self.assertLess(abs(actual-probability),1e-8)
                    results.append(dict(player=name,statistic=stat,count=count,quadrature_candidate_probability=actual,
                        independent_adaptive_quad_probability=probability,absolute_difference=abs(actual-probability),weighted_quad_error_estimate=error/z))
            if name!='LaMelo Ball':self.assertGreater(1-z,.19)
        RESULT['independent_pmf_checks']=results

    def test_03_frozen_input_replay_matches_semantic_payload_without_issuing_forecast(self):
        kwargs=frozen_inputs(OLD);kwargs['forecast_at']=ORIGINAL['forecast_at']
        replayed=replay((OLD/'forecast.json').read_bytes(),**kwargs)
        self.assertEqual(replayed['payload_sha256'],SAVED['payload_sha256']);self.assertFalse(replayed['new_forecast_issued'])
        self.assertEqual((replayed['integrated_rows'],replayed['abstained_rows']),(56,84))
        RESULT['own_replay']=dict(payload_sha256=replayed['payload_sha256'],started=replayed['candidate_computation_started_at'],completed=replayed['candidate_computation_completed_at'],new_forecast_issued=False)

    def test_04_invalid_rates_and_unsupported_minute_family_reject(self):
        d=next(r['forecast']['distribution'] for r in ORIGINAL['minutes'] if r['forecast'])
        for key in ('alpha','beta'):
            for bad in (0.,-1.,float('nan'),float('inf'),True):
                rate=dict(alpha=20.,beta=200.);rate[key]=bad
                with self.subTest(key=key,value=str(bad)),self.assertRaises(ValueError):integrate(rate,d)
        with self.assertRaises(ValueError):integrate(dict(alpha=20.,beta=200.),dict(d,family='truncated_lognormal'))


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NumericReview))
    RESULT.update(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),completed_at=datetime.now(timezone.utc).isoformat())
    (HERE/'RESULTS.json').write_text(json.dumps(RESULT,indent=2,sort_keys=True)+'\n')
    sys.exit(not result.wasSuccessful())
