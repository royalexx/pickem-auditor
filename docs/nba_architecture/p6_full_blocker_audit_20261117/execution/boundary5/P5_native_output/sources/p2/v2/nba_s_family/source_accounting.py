"""Independent integer feasibility for sparse prior-source NBA counts.

Missing fields remain unknown. A feasible internal witness is never exported as
observed statistics, a source certificate, or a model fit. This validator uses a
small integer feasibility problem, followed by exact integer checks; P1's native
producer uses its separate analytic implementation.
"""
import math
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from .model import SFError

VARIABLES=('points','rebounds','assists','threes','fgm','fga','fg3a','ftm','fta','oreb','dreb','two_pm','two_pa')
OTHER={'steals','blocks','turnovers','personal_fouls'}
COMBOS={'pr':('points','rebounds'),'pa':('points','assists'),'ra':('rebounds','assists'),'pra':('points','rebounds','assists')}
# A numerical representability boundary, never a basketball physical cap.
MAX_NUMERICAL_COUNT=2**48


def validate_count_feasibility(stats):
    if not isinstance(stats,dict) or set(stats)-set(VARIABLES)-OTHER-set(COMBOS):
        raise SFError('P1_NATIVE_ACCOUNTING_STAT_SCHEMA')
    if any(type(v) is not int or v<0 for v in stats.values()):
        raise SFError('P1_NATIVE_ACCOUNTING_INTEGER_SUPPORT')
    if any(v>MAX_NUMERICAL_COUNT for v in stats.values()):
        raise SFError('P1_NATIVE_ACCOUNTING_NUMERICAL_RANGE_UNRESOLVED')
    if not set(stats)&(set(VARIABLES)|set(COMBOS)):return True
    rows=[];lower=[];upper=[]
    def constraint(terms,lo,hi):
        rows.append([terms.get(k,0) for k in VARIABLES]);lower.append(lo);upper.append(hi)
    constraint({'points':1,'two_pm':-2,'threes':-3,'ftm':-1},0,0)
    constraint({'fgm':1,'two_pm':-1,'threes':-1},0,0)
    constraint({'fga':1,'two_pa':-1,'fg3a':-1},0,0)
    constraint({'rebounds':1,'oreb':-1,'dreb':-1},0,0)
    for made,attempt in [('two_pm','two_pa'),('threes','fg3a'),('ftm','fta')]:
        constraint({made:1,attempt:-1},-np.inf,0)
    for key,value in sorted(stats.items()):
        if key in VARIABLES:constraint({key:1},value,value)
        elif key in COMBOS:constraint({k:1 for k in COMBOS[key]},value,value)
    result=milp(c=np.zeros(len(VARIABLES)),integrality=np.ones(len(VARIABLES)),
        bounds=Bounds(np.zeros(len(VARIABLES)),np.full(len(VARIABLES),np.inf)),
        constraints=LinearConstraint(np.asarray(rows,dtype=float),np.asarray(lower,dtype=float),np.asarray(upper,dtype=float)),
        options={'presolve':True,'mip_rel_gap':0.,'time_limit':2.})
    if result.status==2:raise SFError('P1_NATIVE_INTEGER_ACCOUNTING_INFEASIBLE')
    if result.status!=0 or result.x is None or not np.all(np.isfinite(result.x)):
        raise SFError('P1_NATIVE_INTEGER_ACCOUNTING_NUMERICAL_UNRESOLVED')
    witness=[int(round(float(x))) for x in result.x]
    if any(x<0 for x in witness):raise SFError('P1_NATIVE_INTEGER_ACCOUNTING_WITNESS')
    # Floating solver tolerance cannot certify a fractional/incorrect count law.
    for terms,lo,hi in zip(rows,lower,upper):
        value=sum(a*b for a,b in zip(terms,witness))
        if (math.isfinite(lo) and value<lo) or (math.isfinite(hi) and value>hi):
            raise SFError('P1_NATIVE_INTEGER_ACCOUNTING_WITNESS')
    return True
