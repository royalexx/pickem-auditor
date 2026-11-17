"""Exact feasibility of partial NBA integer counts; no missing values inferred.

Internal nonnegative integer witnesses must satisfy scoring, shot opportunities,
rebound accounting and same-player PR/PA/RA/PRA. The returned boolean does not
admit source authenticity. Runtime uses a fixed number of integer operations,
not count-size enumeration, numerical optimization or floating tolerances.
"""
VERSION='nba-p1-partial-integer-accounting/1.0.0'


def _ceil_div(a,b):
    return -((-a)//b)


def _point_interval(s):
    """Project R/A equalities and bounds onto integer P exactly.

    At fixed integer P, R/A rows have coefficients (1,0), (0,1), (1,1),
    a totally unimodular matrix. Rational interval feasibility therefore has
    an integer R/A witness. Affine bounds below are (P coefficient, constant).
    """
    lower=0;upper=None
    if 'points' in s:lower=upper=s['points']
    rmin=s.get('oreb',0)+s.get('dreb',0)
    rl=[(0,rmin)];ru=[];al=[(0,0)];au=[]
    if 'oreb' in s and 'dreb' in s:ru.append((0,rmin))
    for key,los,his in (('rebounds',rl,ru),('assists',al,au)):
        if key in s:los.append((0,s[key]));his.append((0,s[key]))
    if 'pr' in s:rl.append((-1,s['pr']));ru.append((-1,s['pr']))
    if 'pa' in s:al.append((-1,s['pa']));au.append((-1,s['pa']))
    sums=[]
    if 'ra' in s:sums.append((0,s['ra']))
    if 'pra' in s:sums.append((-1,s['pra']))
    def le(a,b):
        nonlocal lower,upper
        coefficient=a[0]-b[0];constant=a[1]-b[1]
        if coefficient>0:
            value=(-constant)//coefficient
            upper=value if upper is None else min(upper,value)
        elif coefficient<0:
            lower=max(lower,_ceil_div(constant,-coefficient))
        elif constant>0:
            return False
        return upper is None or lower<=upper
    for los,his in ((rl,ru),(al,au)):
        for a in los:
            for b in his:
                if not le(a,b):return None
    for total in sums:
        for r in rl:
            for a in al:
                if not le((r[0]+a[0],r[1]+a[1]),total):return None
        for r in ru:
            for a in au:
                if not le(total,(r[0]+a[0],r[1]+a[1])):return None
    for a in sums:
        for b in sums:
            if not le(a,b):return None
    return lower,upper


def _shot_progressions(s):
    """Return (first,last,step) for exact field-goal point support.

    X=two-point makes, T=three-point makes. Q=2X+3T. For unknown X/T,
    X=x+3i and T=t+2j with x in0..2,t in0..1 give <=6 progressions
    Q=2x+3t+6(i+j). Attempt constraints are rectangles or X+T<=FGA.
    """
    n=s.get('fga');u=s.get('fg3a');m=s.get('fgm');t=s.get('threes')
    if n is not None and u is not None and u>n:return []
    if m is not None:
        low=0 if t is None else t;high=m if t is None else t
        if low<0 or high>m:return []
        if u is not None:high=min(high,u)
        if n is not None:
            if u is None:
                if m>n:return []
            else:low=max(low,m-(n-u))
        return [(2*m+low,2*m+high,1)] if low<=high else []
    if t is not None:
        if u is not None and t>u:return []
        cap=None if n is None else n-(t if u is None else u)
        if cap is not None and cap<0:return []
        return [(3*t,None if cap is None else 3*t+2*cap,2)]
    result=[]
    for x in range(3):
        for three in range(2):
            first=2*x+3*three
            if n is not None and u is None:
                remaining=n-x-three
                if remaining<0:continue
                last=first+6*(remaining//2)
            else:
                xmax=None if n is None else n-u
                tmax=u
                if (xmax is not None and x>xmax) or (tmax is not None and three>tmax):continue
                ix=None if xmax is None else (xmax-x)//3
                it=None if tmax is None else (tmax-three)//2
                last=None if ix is None or it is None else first+6*(ix+it)
            result.append((first,last,6))
    return result


def partial_counts_feasible(stats):
    """Whether some nonnegative integer completion satisfies all count laws.

    No witness is exported, and absent fields remain absent. Values must already
    be counts; this helper independently rejects booleans/nonintegers/negatives.
    """
    if not isinstance(stats,dict) or any(type(v) is not int or v<0 for v in stats.values()):return False
    point_bounds=_point_interval(stats)
    if point_bounds is None:return False
    low,high=point_bounds
    free=stats.get('ftm')
    fmin=0 if free is None else free
    fmax=stats.get('fta') if free is None else free
    if 'fta' in stats and free is not None and free>stats['fta']:return False
    for first,last,step in _shot_progressions(stats):
        # Adding a contiguous free-throw interval fills progression gaps once
        # its width reaches step-1; smaller widths need at most six offsets.
        if fmax is None:
            candidates=[(first+fmin,None,1)]
        elif fmax-fmin>=step-1:
            candidates=[(first+fmin,None if last is None else last+fmax,1)]
        else:
            candidates=[(first+fmin+j,None if last is None else last+fmin+j,step)
                        for j in range(fmax-fmin+1)]
        for start,end,stride in candidates:
            lower=max(low,start)
            upper=end if high is None else high if end is None else min(high,end)
            value=start+_ceil_div(lower-start,stride)*stride
            if upper is None or value<=upper:return True
    return False
