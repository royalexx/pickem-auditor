"""Separate numerical research candidate: S1 mixed over conditional beta minutes.

No new forecast issuance, J admission, participation estimate or scoring authority.
The PR190 source/model/fixed-exposure admission is not extended by this reader.
"""
import math
from pathlib import Path
import numpy as np
from scipy.special import roots_jacobi,betainc,betaln
from scipy.stats import nbinom
from v2.nba_opportunity import MinuteLaw
from .p1_subset_handoff_v1 import canonical,digest
from .subset_p3_v1 import require
from .prospective_s_runtime_v1 import read_forecasts


def integrate(parameters, minute_distribution):
    law=MinuteLaw(**minute_distribution)
    require(law.family=='beta','INTEGRATION_UNREVIEWED_MINUTE_FAMILY')
    alpha,beta=parameters['alpha'],parameters['beta']
    require(all(type(x) in (int,float) and math.isfinite(x) and x>0 for x in (alpha,beta)),
        'INTEGRATION_INVALID_RATE')
    a,b=law.shape();components=law.ot_components()
    retained_ot=math.fsum(w for _,w in components);length=components[-1][0]
    ordinary_mass=math.fsum(w*(1-float(betainc(a,b,.5/length))) for length,w in components)
    excluded_sub30_mass=retained_ot-ordinary_mass
    require(ordinary_mass>0,'INTEGRATION_NO_ORDINARY_EXPOSURE')
    # Stochastic dominance at largest retained exposure controls count tail.
    upper_p=beta/(beta+length)
    cap=max(16,int(nbinom.isf(1e-12,alpha,upper_p)))
    require(cap<4096,'INTEGRATION_COUNT_SUPPORT_EXHAUSTED')
    k=np.arange(cap+1)[:,None]
    def quadrature(order):
        nodes,weights=roots_jacobi(order,b-1,0)
        require(np.all(np.isfinite(weights)) and weights.sum()>0,'INTEGRATION_QUADRATURE_WEIGHTS')
        weights=weights/weights.sum();unit=(nodes+1)/2
        mass=np.zeros(cap+1)
        for duration,weight in components:
            lower=.5/duration;share=lower+(1-lower)*unit
            factor=math.exp(b*math.log1p(-lower)-math.log(b)-betaln(a,b))*share**(a-1)
            probability=beta/(beta+duration*share)
            mass+=weight*(nbinom.pmf(k,alpha,probability)@(weights*factor))
        return mass
    low=quadrature(256);mass=quadrature(512);order=512
    error=float(np.abs(low-mass).sum())
    if error>1e-8:
        low=mass;mass=quadrature(1024);order=1024;error=float(np.abs(low-mass).sum())
    require(error<=1e-8 and np.all(np.isfinite(mass)) and np.all(mass>=0),
        'INTEGRATION_QUADRATURE_NOT_CONVERGED')
    count_tail=float(nbinom.sf(cap,alpha,upper_p))
    raw_sum=float(math.fsum(mass));require(0<raw_sum<=1+1e-10,'INTEGRATION_MASS')
    mass=mass/raw_sum
    em=math.fsum(length*w*(1-float(betainc(a+1,b,.5/length))) for length,w in components)/ordinary_mass*a/(a+b)
    em2=math.fsum(length*length*w*(1-float(betainc(a+2,b,.5/length))) for length,w in components)/ordinary_mass*a*(a+1)/((a+b)*(a+b+1))
    expected=alpha/beta*em
    variance=expected+alpha*(alpha+1)/(beta*beta)*em2-expected**2
    numerical_mean=float(np.arange(len(mass))@mass)
    mean_error=abs(numerical_mean-expected)
    require(mean_error<=1e-7,'INTEGRATION_MEAN_CHECK')
    return dict(kind='MINUTE_INTEGRATED_CONDITIONAL_S1_RESEARCH_CANDIDATE',
        conditioning='conditional_on_participation_AND_minutes_at_least_0.5_AND_retained_OT_and_count_support',
        support=[dict(value=i,mass=float(x)) for i,x in enumerate(mass)],
        retained_mean=numerical_mean,analytic_mean_before_count_truncation=expected,
        analytic_variance_before_count_truncation=variance,
        quadrature_order=order,quadrature_L1_order_difference=error,
        quadrature_difference_is_rigorous_bound=False,mean_check_absolute_error=mean_error,
        count_tail_bound_within_retained_OT=count_tail,
        excluded_sub30_probability_within_original_retained_OT=excluded_sub30_mass,
        retained_ordinary_exposure_probability=ordinary_mass,
        full_played_conditional_distribution=False,
        omitted_OT_mass=max(0.,1-retained_ot),retained_raw_probability_mass=raw_sum,
        participation_probability=None,legal_eligibility=None,
        minute_uncertainty_integrated=True,joint_law=False,
        independent_admission='PENDING_SEPARATE_REVIEW',production_release=False)


def replay(raw,**original_inputs):
    original=read_forecasts(raw,**original_inputs)
    minutes={r['player_id']:r for r in original['minutes']};rows=[]
    for row in original['rows']:
        value=None;reason=row['reason']
        if row['forecast']:
            try:value=integrate(row['forecast']['parameters'],minutes[row['player_id']]['forecast']['distribution'])
            except (ValueError,OverflowError) as error:reason=str(error)
        rows.append(dict(player_id=row['player_id'],team_id=row['team_id'],statistic=row['statistic'],
            status='INTEGRATED_CANDIDATE' if value else 'ABSTAIN',reason=reason,distribution=value))
    payload=dict(schema='nba-minute-integrated-S1-replay/1.0.0',
        kind='RECOMPUTATION_OF_FROZEN_INPUTS_NOT_NEW_FORECAST',new_forecast_issued=False,
        original_forecast_raw_sha256=digest(raw),original_payload_sha256=original['payload_sha256'],
        original_forecast_at=original['forecast_at'],implementation_sha256=digest(Path(__file__).read_bytes()),
        candidate_denominator=original['candidate_denominator'],attempt_denominator=len(rows),
        integrated_rows=sum(r['distribution'] is not None for r in rows),
        abstained_rows=sum(r['distribution'] is None for r in rows),rows=rows,
        J_status='NOT_ADMITTED_REAL_SHARED_G_O_EVENT_COUPLING_REQUIRED',
        C_status='UNSCORED_NO_ADMITTED_EVALUATIONS_FOR_THIS_FUTURE_TARGET',
        historical_predictive_validation=False,full_G1_accepted=False,production_release=False)
    return dict(payload,payload_sha256=digest(canonical(payload)))
