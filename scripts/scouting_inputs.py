"""Typed, sourced baseline estimates and executable one-event transformations.

All researcher numeric scenarios remain diagnostics. These typed estimates
provide auditable diagnostic transformations, not eligible production baselines.
Sample floors are operational safeguards, not evidence of calibration.
"""
import math
from effect_ledger import canonical, fact_events

UNITS = {
    'receptions': ('targets', 'receptions_per_target'),
    'receiving yards': ('targets', 'yards_per_target'),
    'completions': ('pass_attempts', 'completions_per_attempt'),
    'passing yards': ('pass_attempts', 'yards_per_attempt'),
    'rushing yards': ('carries', 'yards_per_carry'),
    'rush attempts': ('team_plays', 'carries_per_play'),
    'pass attempts': ('team_plays', 'attempts_per_play'),
    'tackles': ('defensive_plays', 'solo_tackles_per_play'),
    'tackles + assists': ('defensive_plays', 'credits_per_play'),
    'points': ('possessions', 'points_per_possession'),
    'pra': ('possessions', 'pra_per_possession'),
    'pr': ('possessions', 'pr_per_possession'),
    'pa': ('possessions', 'pa_per_possession'),
    'ra': ('possessions', 'ra_per_possession'),
    'threes': ('three_point_attempts', 'makes_per_attempt'),
    'assists': ('potential_assists', 'assists_per_chance'),
    'rebounds': ('rebound_chances', 'rebounds_per_chance'),
    'saves': ('shots_against', 'saves_per_shot'),
    'shots on goal': ('shot_attempts', 'on_target_per_attempt'),
    'blocked shots': ('block_chances', 'blocks_per_chance'),
}


def estimate(fact, unit, now):
    from nfl_opportunity import checked_fact, finite
    value = checked_fact(fact, now)
    if not isinstance(value, dict) or value.get('unit') != unit:
        raise ValueError('numeric estimate needs unit '+unit)
    mean=finite(value.get('estimate'),'estimate')
    se=finite(value.get('se'),'se')
    n=finite(value.get('n'),'n')
    embedded=value.get('embedded_event_ids')
    if mean<=0 or se<=0 or n<1 or not isinstance(embedded,list):
        raise ValueError('estimate requires positive estimate, uncertainty, sample size and embedded_event_ids')
    return dict(value=mean,se=se,n=n,embedded=[canonical(x) for x in embedded])


def resolve(row, candidate, now):
    """Return resolved estimates or None for a legacy diagnostic scenario."""
    supplied=row.get('numeric_inputs')
    if supplied is None:
        if row.get('adjustments'):
            raise ValueError('adjustments require controlled numeric_inputs')
        return None
    units=UNITS.get(candidate.get('stat'))
    if units is None or not isinstance(supplied,dict):
        raise ValueError('unsupported numeric input units')
    spec=row.get('season_projection')
    if spec:
        volume_key='expected_pass_attempts' if spec['mode']=='receiving' else 'expected_defensive_plays'
        expected={volume_key: 'pass_attempts' if spec['mode']=='receiving' else 'defensive_plays'}
        if spec['mode']=='receiving':expected['conversion']=units[1]
    else:
        expected={'opportunities':units[0],'conversion':units[1]}
    if set(supplied)!=set(expected):
        raise ValueError('numeric_inputs must cover exactly '+','.join(expected))
    estimates={k:estimate(supplied[k],u,now) for k,u in expected.items()}
    embedded=set(row.get('embedded_event_ids',[]))
    for v in estimates.values():embedded.update(v['embedded'])
    embedded={canonical(x) for x in embedded}
    effects=[]
    sufficient=all(v['n']>=20 for v in estimates.values())
    adjustments=row.get('adjustments',[])
    if not isinstance(adjustments,list):raise ValueError('adjustments must be a list')
    if row.get('applied_effects'):
        raise ValueError('controlled inputs generate effects; do not supply annotation-only applied_effects')
    for change in adjustments:
        # One joint factor map for a single causal event; never repeat that event
        # in a second change, even when the affected input names differ.
        factors=change.get('factors')
        if not isinstance(factors,dict) or not factors or set(factors)-set(estimates):
            raise ValueError('adjustment must name controlled inputs')
        fact=change.get('evidence')
        from nfl_opportunity import checked_fact,finite
        value=checked_fact(fact,now)
        if not isinstance(value,dict) or value.get('factors')!=factors:
            raise ValueError('sourced adjustment must match factor map')
        errors=value.get('factor_se')
        if not isinstance(errors,dict) or set(errors)!=set(factors):
            raise ValueError('adjustment requires sourced factor uncertainty')
        n=finite(value.get('n'),'adjustment sample size')
        if n<1:raise ValueError('adjustment sample size must be positive')
        sufficient=sufficient and n>=20
        events=fact_events(fact)
        for event in events:
            effects.append(dict(event_id=event,inputs=list(factors),applied_by='controlled_numeric_transform'))
        for k,factor in factors.items():
            factor=finite(factor,'adjustment factor')
            error=finite(errors[k],'factor se')
            if factor<=0 or error<=0:raise ValueError('adjustment factor and se must be positive')
            estimates[k]['se']=estimates[k]['se']*factor+estimates[k]['value']*error
            estimates[k]['value']*=factor
    # Supplied scalar values are assertions, never a second numerical input.
    for key,v in estimates.items():
        asserted=(spec or {}).get(key) if key.startswith('expected_') else row.get(key)
        if asserted is not None and (isinstance(asserted,bool) or not isinstance(asserted,(int,float)) or
                not math.isclose(asserted,v['value'],rel_tol=1e-9)):
            raise ValueError('scalar conflicts with controlled estimate: '+key)
    return dict(estimates=estimates,effects=effects,embedded=sorted(embedded),
                sufficient=sufficient)
