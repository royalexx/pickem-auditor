"""Full-marginal, sufficient primal certificate; never an authenticity claim.

Version1 interprets serialized numbers as exact decimal rationals, normalizes
mass in that domain, and retains G0's 1e-7 minute conservation tolerance.
It certifies simultaneous bound attainment only; unsupported cases are explicit.
The accepted exposure_v2 implementation and its budget failures are untouched.
"""
from collections import defaultdict
from fractions import Fraction
import math

from .v2_contracts import req, verify

VERSION = 'nba-full-law-primal-certificate/1.0.0'
MINUTE_TOLERANCE = Fraction(1, 10_000_000)
MAX_CERTIFICATE_COLUMNS = 4096


def rational(value):
    req(type(value) in (int, float) and math.isfinite(value), 'CERT_NONFINITE_OR_TYPE')
    return Fraction(str(value))


def certify(o, p, g, *, required_positive=None):
    """Check the full declared laws using the existing positive G/O columns.

    Exact equalities establish a feasible primal. q<=1 is a universal dual
    bound, so a feasible measure attaining all unknown q=1 proves their maxima.
    This API never changes declared participation probabilities or minute atoms.
    Structural envelope validation is performed by families_certified_v1.
    """
    from .families_certified_v1 import validate_opportunity_structure
    validate_opportunity_structure(o,p,g)
    for obj in (o, p, g): verify(obj)
    req(o['source_snapshot_sha256']==p['content_hash'] and
        o['game_state_sha256']==g['content_hash'] and o['game_id']==p['game_id']==g['game_id'],
        'CERT_ENVELOPE_BINDING')
    roster={r['player_id']:r for r in p['players']}
    people={r['player_id']:r for r in o['players']}
    req(len(roster)==len(p['players']) and len(people)==len(o['players']) and
        set(people)==set(roster),'CERT_ROSTER_POPULATION')
    gs={s['scenario_id']:s for s in g['scenarios']}
    os={s['scenario_id']:s for s in o['scenarios']}
    req(len(gs)==len(g['scenarios']) and len(os)==len(o['scenarios']) and
        set(gs)==set(os) and 0<len(gs)<=MAX_CERTIFICATE_COLUMNS,'CERT_SCENARIO_POPULATION')
    gw={k:rational(s['weight']) for k,s in gs.items()}
    ow={k:rational(s['weight']) for k,s in os.items()}
    req(all(w>=0 for w in gw.values()) and all(w>=0 for w in ow.values()) and
        sum(gw.values())>0 and sum(ow.values())>0,'CERT_WEIGHT_SUPPORT')
    gw={k:w/sum(gw.values()) for k,w in gw.items()}
    ow={k:w/sum(ow.values()) for k,w in ow.items()}
    req(gw==ow,'CERT_G_O_EXACT_WEIGHT_BINDING')
    atoms={};played=defaultdict(Fraction);marginal=defaultdict(Fraction)
    for pid,person in people.items():
        req(person['team_id']==roster[pid]['team_id'],'CERT_TEAM_IDENTITY')
        law=person['minutes_law']
        req(law['family']=='discrete_minutes','CERT_DISCRETE_LAW_REQUIRED')
        raw=law['parameters']['support'];law_atoms={rational(a['minutes']):rational(a['mass']) for a in raw}
        req(len(law_atoms)==len(raw) and law_atoms and all(m>=0 and w>=0 for m,w in law_atoms.items()) and sum(law_atoms.values())>0,'CERT_ATOM_POPULATION')
        norm=sum(law_atoms.values());atoms[pid]={m:w/norm for m,w in law_atoms.items()}
    residuals=[]
    for sid,sc in os.items():
        w=ow[sid];ot=sc['overtime_periods']
        req(type(ot) is int and ot>=0 and ot==gs[sid]['overtime_periods'],'CERT_OT_BINDING')
        rows={r['player_id']:r for r in sc['players']}
        req(len(rows)==len(sc['players']) and set(rows)==set(roster),'CERT_WITNESS_POPULATION')
        totals=defaultdict(Fraction);cap=48+5*ot
        for pid,row in rows.items():
            mn=rational(row['minutes']);state=row['participation'];team=roster[pid]['team_id']
            req(row['team_id']==team and team in p['team_ids'],'CERT_WITNESS_IDENTITY')
            req(0<=mn<=cap and ((state=='PLAYED' and mn>0) or
                (state in ('DNP','PLAYED_ZERO_MINUTES') and mn==0)), 'CERT_STATE_SUPPORT')
            excluded=roster[pid]['legal_eligibility'] is False or roster[pid]['availability']=='out'
            req(not excluded or state=='DNP','CERT_EXCLUDED_PLAYED')
            if w>0 and state!='DNP':
                req(atoms[pid].get(mn,0)>0,'CERT_WITNESS_ATOM_SUPPORT')
                played[pid]+=w;marginal[pid,mn]+=w
            totals[team]+=mn
        if w>0:
            for team in p['team_ids']:
                residual=abs(totals[team]-5*cap);residuals.append(residual)
                req(residual<=MINUTE_TOLERANCE,'CERT_MINUTE_CONSERVATION')
    bounds={};exact_bounds={}
    for pid,person in people.items():
        q=person['participation_probability'];excluded=roster[pid]['legal_eligibility'] is False or roster[pid]['availability']=='out'
        if excluded:q=0
        if q is None:
            req(played[pid]==1,'CERT_BOUND_NOT_ATTAINED')
            maximum=Fraction(1)
        else:
            maximum=rational(q);req(0<=maximum<=1 and played[pid]==maximum,'CERT_KNOWN_Q_MARGINAL')
        # Every atom, including arbitrarily tiny positive atoms, is checked.
        for mn,mass in atoms[pid].items():
            req(marginal[pid,mn]==maximum*mass,'CERT_FULL_ATOM_MARGINAL')
        positive=sum(mass for mn,mass in atoms[pid].items() if mn>0)
        exact_bounds[pid]=(maximum,maximum*positive)
        bounds[pid]=(float(maximum),float(maximum*positive))
    if required_positive is not None:
        pid,mass=required_positive
        req(pid in bounds and 0<=rational(mass)<=exact_bounds[pid][1],'FORECAST_COUNT_EXCEEDS_EXPOSURE')
    return dict(schema=VERSION,bounds=bounds,exact_bounds={pid:[str(v) for v in values] for pid,values in exact_bounds.items()},source_snapshot_sha256=p['content_hash'],
        game_state_sha256=g['content_hash'],opportunity_sha256=o['content_hash'],
        positive_certificate_columns=sum(w>0 for w in ow.values()),
        max_minute_residual=str(max(residuals,default=Fraction(0))),
        minute_tolerance=str(MINUTE_TOLERANCE),genuine_participation_inferred=False,
        numeric_contract='EXACT_CANONICAL_DECIMAL_MASSES_WITH_DECLARED_MINUTE_TOLERANCE',
        proof='FULL_PRIMAL_EQUALS_UNIVERSAL_Q_UPPER_BOUND',source_admission=False)


def verification_receipt(o,p,g,required_positive=None):
    from .v2_contracts import ContractError
    try:
        result=certify(o,p,g,required_positive=required_positive)
        return dict(route='EXACT_DECIMAL_FULL_MARGINAL_CERTIFICATE',certificate=result,bounds=result['bounds'])
    except ContractError as exc:
        if not exc.code.startswith('CERT_'):raise
        from .exposure_v2 import validate_exposure_coupling as complete
        bounds=complete(o,p,g,required_positive=required_positive)
        return dict(route='ORIGINAL_V2_COMPLETE_FLOAT_LP',certificate_not_applicable=exc.code,
                    numeric_contract='ORIGINAL_V2_FLOAT_LP_AND_RESIDUAL_TOLERANCE',bounds=bounds)


def validate_exposure_coupling(o,p,g,required_positive=None):
    """Compatibility return only; use verification_receipt for route provenance."""
    return verification_receipt(o,p,g,required_positive=required_positive)['bounds']
