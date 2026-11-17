"""WS2 versioned compatibility adapter, preserving shared game duration.

Historical mode calls the exact frozen WS2 law and allocation. It cannot call
WS2.forecast with fabricated old ingestion clocks. Its reconstructed handoff
retains missing participation probabilities and is never source-certified.
"""
import numpy as np
from v2.nba_opportunity import MinutesModel, capped_allocation, lineup_segments

ADAPTER_VERSION='NBAOpportunityForecastAdapter/1.0.0'


def allocate(players, model, state, rng, *, name='M0', constrained=True, conditional=True):
    mm=MinutesModel(**model['minutes'])
    length=state['duration']
    eligible=np.array([p['eligible'] is not False for p in players])
    if conditional:
        # Assumption, not an inferred participation probability. Exported p stays None.
        active=eligible & np.array([p.get('participation_probability')!=0 for p in players])
    else:
        if any(p.get('participation_probability') is None or p.get('eligible') is None for p in players):
            raise ValueError('UNVERIFIED_PARTICIPATION')
        active=eligible & (rng.random(len(players))<np.array([p['participation_probability'] for p in players]))
    if active.sum()<5:raise ValueError('FEWER_THAN_FIVE_PARTICIPANTS')
    desired=np.array([mm.law(name,p['minute_features'],p['position']).sample_at_length(rng,length) if a else 0. for p,a in zip(players,active)])
    caps=active.astype(float)*length
    for i,p in enumerate(players):
        if p.get('scenario_exit_cap') is not None:caps[i]=min(caps[i],p['scenario_exit_cap'])
    if np.any(active & (caps<=0)):raise ValueError('PARTICIPANT_ZERO_CAP')
    if constrained:
        lower=np.where(active,np.finfo(float).eps*length,0.)
        minutes=lower+capped_allocation(desired-lower,caps-lower,5*length-lower.sum())
        segments=lineup_segments(minutes,length)
    else:
        minutes=np.minimum(desired,caps);segments=[]
    return minutes,desired,segments,active
