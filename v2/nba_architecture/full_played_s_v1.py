"""Assumption-defined full-played S1 law, with an unupdated zero-state prior.

Positive-minute homogeneous-rate extrapolation and a true-zero delta kernel
are explicit model hypotheses. Source zero probability and genuine q are
unknown. This numerical module does not itself grant source/model admission.
"""
from dataclasses import dataclass
import math
import numpy as np
from scipy.special import roots_jacobi,gammaln,betaln,hyp2f1,logsumexp
from scipy.stats import nbinom
from v2.nba_opportunity import MinuteLaw
from .subset_p3_v1 import require


@dataclass(frozen=True)
class FullPlayedLaw:
    alpha:float
    beta:float
    minutes:dict
    zero_prior_mean:float=.01

    def __post_init__(self):
        require(all(type(x) in (int,float) and math.isfinite(x) and x>0
            for x in (self.alpha,self.beta)), 'FULL_S_RATE_PARAMETERS')
        require(type(self.zero_prior_mean) in (int,float) and math.isfinite(self.zero_prior_mean)
            and 0<=self.zero_prior_mean<=1,'FULL_S_ZERO_PRIOR')
        require(MinuteLaw(**self.minutes).family=='beta','FULL_S_BETA_ONLY')

    def components(self,n=32):
        require(type(n) is int and 1<=n<=512,'FULL_S_OT_QUERY_BUDGET')
        law=MinuteLaw(**self.minutes);p,q=law.ot_probability,law.ot_continuation
        tail=p*q**n
        if p and tail==0:tail=math.nextafter(0.,1.)
        return [(48.,1-p)]+[(48.+5*k,p*(1-q)*q**(k-1)) for k in range(1,n+1)],tail

    def _nodes(self,order):
        a,b=MinuteLaw(**self.minutes).shape();nodes,weights=roots_jacobi(order,b-1,a-1)
        require(np.all(np.isfinite(weights)) and weights.sum()>0,'FULL_S_QUADRATURE')
        return (nodes+1)/2,weights/weights.sum()

    @staticmethod
    def _counts(values):
        require(isinstance(values,(list,tuple)) and bool(values) and all(type(k) is int and k>=0 for k in values),
            'FULL_S_COUNT_SUPPORT')
        return np.asarray(values)[:,None]

    def _evaluate(self,values,kind,order,n):
        counts=self._counts(values);u,weights=self._nodes(order);parts,tail=self.components(n)
        total=np.zeros(len(values))
        for length,weight in parts:
            probability=self.beta/(self.beta+length*u)
            kernel={'pmf':nbinom.pmf,'cdf':nbinom.cdf,'sf':nbinom.sf}[kind](counts,self.alpha,probability)
            total+=weight*(kernel@weights)
        total*=1-self.zero_prior_mean
        total+=self.zero_prior_mean*(np.asarray(values)==0 if kind=='pmf' else np.ones(len(values)) if kind=='cdf' else np.zeros(len(values)))
        return total,(1-self.zero_prior_mean)*tail

    def query(self,values,kind='pmf',*,ot_terms=32):
        require(kind in ('pmf','cdf','sf'),'FULL_S_QUERY_KIND')
        low,_=self._evaluate(values,kind,256,ot_terms);high,tail=self._evaluate(values,kind,512,ot_terms)
        difference=float(np.max(np.abs(high-low)));order=512
        if difference>1e-9:
            low=high;high,tail=self._evaluate(values,kind,1024,ot_terms);order=1024
            difference=float(np.max(np.abs(high-low)))
        require(difference<=1e-9 and np.all(np.isfinite(high)) and np.all(high>=0)
            and np.all(high<=1+1e-10),'FULL_S_QUERY_NOT_CONVERGED')
        return dict(kind=kind,counts=values,probabilities=high.tolist(),quadrature_order=order,
            value_interpretation='NUMERICAL_ESTIMATE_NOT_STRUCTURAL_ZERO_OR_ONE',
            estimated_order_difference=difference,order_difference_is_rigorous_bound=False,
            omitted_OT_probability_bound=tail,count_support_truncated=False,
            count_support_renormalized=False)

    def analytic_pmf(self,k,*,ot_terms=32):
        """Independent hypergeometric identity; unresolved underflow rejects."""
        require(type(k) is int and k>=0,'FULL_S_COUNT_SUPPORT')
        a,b=MinuteLaw(**self.minutes).shape();terms=[];parts,tail=self.components(ot_terms)
        for length,weight in parts:
            if not weight:continue
            hyper=float(hyp2f1(self.alpha+k,a+k,a+b+k,-length/self.beta))
            require(math.isfinite(hyper) and hyper>0,'FULL_S_ANALYTIC_REFERENCE_UNRESOLVED')
            logterm=(math.lgamma(k+self.alpha)-math.lgamma(self.alpha)-math.lgamma(k+1)
                +k*math.log(length/self.beta)+betaln(a+k,b)-betaln(a,b)+math.log(hyper))
            terms.append(weight*math.exp(logterm))
        return dict(probability=(self.zero_prior_mean if k==0 else 0)+(1-self.zero_prior_mean)*math.fsum(terms),
            omitted_OT_probability_bound=(1-self.zero_prior_mean)*tail)

    def logpmf(self,k):
        """Full integer support, explicit failure when relative accuracy unresolved.

        Never replace an unresolved query by zero, epsilon clipping or a void.
        """
        require(type(k) is int and k>=0,'FULL_S_COUNT_SUPPORT')
        previous=None
        for n in (32,64,128,256,512):
            result=[]
            for order in (512,1024):
                u,weights=self._nodes(order);terms=[];parts,tail=self.components(n)
                if self.zero_prior_mean and k==0:terms.append(math.log(self.zero_prior_mean))
                if self.zero_prior_mean<1:
                    for length,weight in parts:
                        if weight:terms.append(math.log1p(-self.zero_prior_mean)+math.log(weight)+
                            float(logsumexp(nbinom.logpmf(k,self.alpha,self.beta/(self.beta+length*u))+np.log(weights))))
                result.append(float(logsumexp(terms)) if terms else -math.inf)
            value=result[-1]
            minute_law=MinuteLaw(**self.minutes)
            log_tail=(math.log1p(-self.zero_prior_mean)+math.log(minute_law.ot_probability)
                +n*math.log(minute_law.ot_continuation)) if minute_law.ot_probability and self.zero_prior_mean<1 else -math.inf
            relative_tail=math.exp(log_tail-value) if math.isfinite(value) and log_tail-value<700 else math.inf
            if value==-math.inf and self.zero_prior_mean==1:
                return dict(log_probability=value,exact_structural_zero=True,numerical_status='RESOLVED')
            if math.isfinite(value) and abs(result[0]-result[1])<=1e-8 and relative_tail<=1e-8:
                return dict(log_probability=value,exact_structural_zero=False,numerical_status='RESOLVED',
                    estimated_log_quadrature_difference=abs(result[0]-result[1]),
                    omitted_OT_relative_probability_bound=relative_tail,ot_terms=n,
                    numerical_difference_is_rigorous_bound=False)
            previous=value
        raise ValueError('FULL_S_LOG_QUERY_UNRESOLVED_NO_SCORE')

    def moments(self):
        law=MinuteLaw(**self.minutes);a,b=law.shape();p,q=law.ot_probability,law.ot_continuation
        ek=p/(1-q);ek2=p*(1+q)/(1-q)**2
        em=(48+5*ek)*a/(a+b)
        em2=(2304+480*ek+25*ek2)*a*(a+1)/((a+b)*(a+b+1))
        mu=self.alpha/self.beta*em
        var=mu+self.alpha*(self.alpha+1)/self.beta**2*em2-mu*mu
        z=self.zero_prior_mean
        return dict(mean=(1-z)*mu,variance=(1-z)*var+z*(1-z)*mu*mu,
            positive_minute_mean=em,positive_count_mean=mu,positive_count_variance=var,
            modeled_zero_state_prior_mean=z,genuine_zero_state_probability=None,
            genuine_participation_probability=None)

    def summary(self,display_max=128):
        require(type(display_max) is int and 0<=display_max<=4096,'FULL_S_DISPLAY_BUDGET')
        pmf=self.query(list(range(display_max+1)));cdf=self.query([display_max],kind='cdf');sf=self.query([display_max],kind='sf')
        return dict(schema='nba-assumption-defined-full-played-S1/1',
            kind='PRIOR_PREDICTIVE_SHADOW_NOT_EMPIRICALLY_IDENTIFIED',
            conditioning='conditional_on_participation_under_declared_model_assumptions',
            assumptions=dict(positive_rate_extrapolation='HOMOGENEOUS_RATE_ALL_M_GT_0',
                zero_state_prior='BASELINE_BETA_0.5_49.5_NO_EMPIRICAL_UPDATE_SENSITIVITY_VALUES_ARE_CHOSEN_SCENARIOS',true_zero_count_kernel='DELTA_ZERO_STRUCTURAL_HYPOTHESIS',
                rate_minutes_factorization='CONDITIONAL_PRODUCT_ASSUMPTION'),
            rate_parameters=dict(alpha=self.alpha,beta=self.beta),minute_parameters=self.minutes,
            zero_prior_mean=self.zero_prior_mean,
            zero_weight_origin='BASELINE_PRIOR_MEAN' if self.zero_prior_mean==.01 else 'CHOSEN_SENSITIVITY_NOT_IDENTIFIED_BOUND',moments=self.moments(),
            displayed_support=[dict(value=k,mass=p) for k,p in zip(pmf['counts'],pmf['probabilities'])],
            probability_beyond_display=sf['probabilities'][0],
            probability_beyond_display_method='DIRECT_NB_SURVIVAL_INTEGRAL_NOT_ONE_MINUS_CDF',
            probability_beyond_display_is_numerical_estimate=True,
            displayed_count_mass=math.fsum(pmf['probabilities']),
            displayed_support_is_not_full_law=True,count_support='ALL_NONNEGATIVE_INTEGERS',
            numerical=dict(pmf=pmf,cdf=cdf,sf=sf),full_model_measure_defined=True,empirical_zero_state_identified=False,
            genuine_participation_probability=None,genuine_zero_state_probability=None,
            source_model_admission='PENDING_SEPARATE_REVIEW',production_release=False)
