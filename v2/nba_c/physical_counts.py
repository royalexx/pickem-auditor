"""Exact partial basketball-count feasibility, without filling missing fields.

This transport validator is independent of P1's residue enumeration. It uses
exact RREF for P/R/A and closed forms for bounded two/three/free-throw sums.
All loops have fixed size; even very large integer counts use no float solver.
"""
from fractions import Fraction

ROWS={'points':(1,0,0),'rebounds':(0,1,0),'assists':(0,0,1),
      'pr':(1,1,0),'pa':(1,0,1),'ra':(0,1,1),'pra':(1,1,1)}


def _interval(lo,hi,other_lo,other_hi):
    low=max(lo,other_lo)
    highs=[x for x in (hi,other_hi) if x is not None]
    return not highs or low<=min(highs)


def _ap(lo,hi,start,end,step):
    low=max(lo,start)
    first=start+max(0,(low-start+step-1)//step)*step
    return (hi is None or first<=hi) and (end is None or first<=end)


def _points_interval(stats):
    # Rebounds are OREB+DREB. Subtract known component minima before RREF;
    # if both are known, the remaining rebound component is exactly zero.
    rebound_min=stats.get('oreb',0)+stats.get('dreb',0)
    values={key:stats[key] for key in ROWS if key in stats}
    if 'oreb' in stats and 'dreb' in stats:
        if 'rebounds' in values and values['rebounds']!=rebound_min:return None
        values['rebounds']=rebound_min
    rows=[[Fraction(x) for x in ROWS[key]]+[Fraction(value-ROWS[key][1]*rebound_min)]
          for key,value in values.items()]
    pivot=0;pivots=[]
    for col in range(3):
        found=next((i for i in range(pivot,len(rows)) if rows[i][col]),None)
        if found is None:continue
        rows[pivot],rows[found]=rows[found],rows[pivot]
        divisor=rows[pivot][col];rows[pivot]=[x/divisor for x in rows[pivot]]
        for i in range(len(rows)):
            if i!=pivot and rows[i][col]:
                scale=rows[i][col]
                rows[i]=[x-scale*y for x,y in zip(rows[i],rows[pivot])]
        pivots.append(col);pivot+=1
    if any(not any(row[:3]) and row[3] for row in rows):return None
    if pivot==0:return (0,None)
    if pivot==3:
        values=[rows[i][3] for i in range(3)]
        if any(x.denominator!=1 or x<0 for x in values):return None
        p=int(values[0]);return (p,p)
    if pivot==1:
        row=rows[0];total=row[3]
        if total<0 or total.denominator!=1:return None
        if not row[0]:return (0,None)
        if not any(row[1:3]):return (int(total),int(total))
        return (0,int(total))
    free=next(c for c in range(3) if c not in pivots)
    expressions={free:(Fraction(0),Fraction(1))}
    for i,col in enumerate(pivots):expressions[col]=(rows[i][3],-rows[i][free])
    low=0;high=None
    for intercept,slope in expressions.values():
        # Every rank-two minor of the seven P/R/A rows is 0 or +/-1.
        assert intercept.denominator==1 and slope.denominator==1
        a,b=int(intercept),int(slope)
        if b>0:low=max(low,(-a+b-1)//b)
        elif b<0:
            bound=a//(-b);high=bound if high is None else min(high,bound)
        elif a<0:return None
    if high is not None and low>high:return None
    a,b=map(int,expressions[0])
    if b==0:return (a,a)
    if b>0:return (a+b*low,None if high is None else a+b*high)
    assert high is not None
    return (a+b*high,a+b*low)


def _add_free_interval(lo,hi,start,end,step,free_max):
    if free_max is None:return hi is None or hi>=start
    if free_max>=step-1:
        return _interval(lo,hi,start,None if end is None else end+free_max)
    return any(_ap(lo,hi,start+j,None if end is None else end+j,step)
               for j in range(free_max+1))


def partial_counts_feasible(stats):
    """Existence of a nonnegative integer completion; returns no imputation."""
    if any(type(value) is not int or value<0 for value in stats.values()):return False
    interval=_points_interval(stats)
    if interval is None:return False
    lo,hi=interval
    fg=stats.get('fgm');fa=stats.get('fga');three=stats.get('threes');ta=stats.get('fg3a')
    ft=stats.get('ftm');fta=stats.get('fta')
    if fa is not None and ta is not None and ta>fa:return False
    if ft is not None and fta is not None and ft>fta:return False
    shift=ft if ft is not None else 0
    free_max=0 if ft is not None else fta
    lo=max(0,lo-shift);hi=None if hi is None else hi-shift
    if hi is not None and hi<0:return False
    if fg is not None:
        if fa is not None and fg>fa:return False
        cmin=three if three is not None else 0
        cmax=three if three is not None else fg
        cmax=min(cmax,fg,ta if ta is not None else cmax)
        if fa is not None and ta is not None:cmin=max(cmin,fg-(fa-ta))
        if cmin>cmax:return False
        return _interval(lo,hi,2*fg+cmin,None if free_max is None else 2*fg+cmax+free_max)
    if three is not None:
        if (ta is not None and three>ta) or (fa is not None and three>fa):return False
        tmax=fa-ta if fa is not None and ta is not None else fa-three if fa is not None else None
        return _add_free_interval(lo,hi,3*three,None if tmax is None else 3*three+2*tmax,2,free_max)
    if fa is not None and ta is None:
        # At most fa total made field goals: {0} union [2,3*fa].
        if free_max is None:return True
        if free_max>=1:return _interval(lo,hi,0,3*fa+free_max)
        return _interval(lo,hi,0,0) or fa>=1 and _interval(lo,hi,2,3*fa)
    tmax=fa-ta if fa is not None else None
    cmax=ta
    if cmax==0:
        return _add_free_interval(lo,hi,0,None if tmax is None else 2*tmax,2,free_max)
    if tmax==0:
        return _add_free_interval(lo,hi,0,None if cmax is None else 3*cmax,3,free_max)
    maximum=None if tmax is None or cmax is None else 2*tmax+3*cmax
    if free_max is None:return True
    if free_max>=1:return _interval(lo,hi,0,None if maximum is None else maximum+free_max)
    if tmax==1:
        return _ap(lo,hi,0,None if cmax is None else 3*cmax,3) or _ap(lo,hi,2,maximum,3)
    # With >=2 two-point makes and >=1 three available the only holes are
    # one point, and one below the finite maximum.
    candidate=lo
    if candidate==1:candidate=2
    if maximum is not None and candidate==maximum-1:candidate=maximum
    return (hi is None or candidate<=hi) and (maximum is None or candidate<=maximum)
