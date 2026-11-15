"""Separate numerical pass on synthetic fixtures; no independent human review claim."""
import json
import math
from pathlib import Path
import numpy as np
from .models import OpportunityModel, canonical, freeze_output, sha
from .test_models import fixture

def review(root):
    packet=fixture();model=OpportunityModel(packet,8192);report=model.run()
    report['status']='SYNTHETIC_FIXTURE_ONLY_NOT_SUNDAY_FORECAST'
    issues=[];checked=0
    for row in report['rows']:
        if row['status']!='forecast':continue
        dist=row['predictive_distribution_conditional'];values=dist['values'];mass=dist['masses']
        line=row['contract']['line']
        if abs(sum(mass)-1)>1e-12:issues.append('mass')
        mean=sum(v*p for v,p in zip(values,mass))
        if abs(mean-row['workload_conditional']['mean'])>1e-10:issues.append('mean')
        # Independent PMF summation; does not call model's O/U/P extractor.
        direct={'over':sum(p for v,p in zip(values,mass) if v>line),
                'under':sum(p for v,p in zip(values,mass) if v<line),
                'push':sum(p for v,p in zip(values,mass) if v==line)}
        if any(abs(direct[k]-row['probabilities_conditional'][k])>1e-12 for k in direct):issues.append('side')
        checked+=1
    event=packet['events'][0];env=model.environment(event)
    defender=next(r for r in packet['roster'] if r['player_id']=='Ad')
    vals,mask,diag=model.defender(event,defender,env['B'])
    # Fixture has 8 prior eligible games, each 55 snaps and 7 combined credits;
    # latest two games supply Beta(111,21) share, involvement prior adds 120 snaps
    # and four categories receive 0.5 pseudo-count apiece.
    analytic=env['B']['plays'].mean()*(111/132)*((56+120*(7/55)+1.5)/(440+120+2))*.95
    empirical=vals['tackles + assists'].mean()
    se=vals['tackles + assists'].std()/math.sqrt(model.n)
    if abs(analytic-empirical)>5*se:issues.append('defensive_analytic_moment')
    qb={'historical_share':.95,'old_v4_beta_expectation':(12+35*.95)/59,
        'v41_beta_expectation':(1+60*.95)/62,'O3_beta_expectation':.95}
    result={'status':'PASS' if not issues else 'FAIL','evidence_type':'SYNTHETIC_FIXTURE_NUMERICAL_REVIEW',
        'draws':8192,'pmf_mean_side_checks':checked,'issues':issues,
        'tackle_analytic_mean':float(analytic),'tackle_empirical_mean':float(empirical),
        'tackle_mean_monte_carlo_se':float(se),'qb_beta_control':qb,
        'team_conservation_max_error':max(x['conservation_max_error'] for x in report['team_opportunities']),
        'review_independence':'Separate numerical calculation by same agent; no independent reviewer or prospective validation'}
    assert not issues,result
    synthetic_receipt=freeze_output(report,Path(root)/'synthetic_test')
    numerical_receipt=freeze_output(result,Path(root)/'numerical_review')
    return {'synthetic_receipt':synthetic_receipt,'numerical_receipt':numerical_receipt,'review':result}

if __name__=='__main__':
    print(json.dumps(review('reports/nfl_20261115_prospective/opportunity_models'),sort_keys=True))
