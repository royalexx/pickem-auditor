"""New group-aware conditional O law; no mutation of accepted G0 coupling.

Circular quantiles preserve each named marginal. A finite wrap-limit test is
a sufficient capacity certificate by monotonicity, not an empirical q estimate.
Residual slots are anonymous latent actors, never source/player identities.
"""
from fractions import Fraction
import math
import numpy as np
from scipy.special import betaincinv
from v2.nba_opportunity import MinuteLaw,lineup_segments
from v2.nba_architecture.subset_p3_v1 import require


def capacity_certificate(players,*,query_budget=1000):
    """Worst-case pi=0 suffices for every nonnegative zero-mixture weight."""
    require(isinstance(players,list) and bool(players),'RESIDUAL_O_PLAYERS')
    teams={p.get('team_id') for p in players}
    require(len(teams)==1 and all(type(t) is str and bool(t) for t in teams),'RESIDUAL_O_SINGLE_TEAM')
    require(all(p['minutes'].get('family','beta')=='beta' for p in players),'RESIDUAL_O_BETA_ONLY')
    ids=sorted(p['player_id'] for p in players)
    require(len(ids)==len(set(ids)),'RESIDUAL_O_DUPLICATE_ID')
    byid={p['player_id']:p for p in players};n=len(ids)
    require(n*n<=query_budget,'RESIDUAL_O_CERTIFICATE_BUDGET')
    offsets={pid:Fraction(i,n) for i,pid in enumerate(ids)};limits=[]
    for wrapping in ids:
        u=(1-offsets[wrapping])%1;total=0.;values={}
        for pid in ids:
            v=(u+offsets[pid])%1
            # Exact rational wrap location. Its left limit is one, not zero.
            probability=1. if v==0 else float(v)
            a,b=MinuteLaw(**byid[pid]['minutes']).shape()
            share=float(betaincinv(a,b,probability))
            require(math.isfinite(share) and 0<=share<=1,'RESIDUAL_O_QUANTILE_NUMERIC')
            values[pid]=share;total+=share
        limits.append(dict(wrapping_player=wrapping,share_sum=total,shares=values))
    upper=max(x['share_sum'] for x in limits)+n*1e-8
    require(upper<=5,'RESIDUAL_O_NO_CAPACITY_CERTIFICATE')
    return dict(schema='conditional-residual-circular-O-certificate/1',
        player_ids=ids,offsets={k:str(v) for k,v in offsets.items()},wrap_limits=limits,
        conservative_numeric_upper_share=upper,queries=n*n,query_budget=query_budget,
        mathematical_basis='SUM_NONDECREASING_BETWEEN_WRAPS_MAXIMUM_AT_LEFT_WRAP_LIMIT',
        scope='SUFFICIENT_NEW_CONTINUOUS_COPULA_NOT_OLD_G0_LP_OR_GENERAL_MAX_Q',
        zero_prior_worst_case=0.,genuine_participation_probability=None,
        numerical_quantile_allowance=1e-8,original_n32_budget_red_unchanged=True)


def draw_team(players,length,rng,*,fixed_zero_weight=None):
    certificate=capacity_certificate(players)
    require(type(length) in (int,float) and math.isfinite(length) and length>=48 and
        (length-48)%5==0,'RESIDUAL_O_DURATION')
    byid={p['player_id']:p for p in players};ids=certificate['player_ids'];n=len(ids)
    u=float(rng.random());actors=[];minutes=[]
    for i,pid in enumerate(ids):
        z=float(rng.beta(.5,49.5)) if fixed_zero_weight is None else fixed_zero_weight
        require(type(z) in (int,float) and 0<=z<=1,'RESIDUAL_O_ZERO_PRIOR')
        probability=(u+i/n)%1
        if probability<=z:value=0.
        else:
            a,b=MinuteLaw(**byid[pid]['minutes']).shape()
            value=length*float(betaincinv(a,b,(probability-z)/(1-z)))
        minutes.append(value)
        actors.append(dict(kind='NAMED_SOURCE_PLAYER',player_id=pid,name=byid[pid].get('name'),
            team_id=byid[pid]['team_id'],zero_weight_model_draw=z,
            model_participation_conditioned=True,genuine_participation_probability=None,legal_eligibility=None))
    residual=5*length-math.fsum(minutes)
    require(residual>=-1e-8,'RESIDUAL_O_CAPACITY_VIOLATION')
    residual=max(0.,residual);group_minutes=residual
    for slot in range(5):
        value=min(length,residual);residual-=value;minutes.append(value)
        actors.append(dict(kind='ANONYMOUS_RESIDUAL_ACTOR_SLOT',residual_slot_index=slot,
            residual_group='RESIDUAL_TEAM:'+players[0]['team_id'],team_id=players[0]['team_id'],
            player_id=None,source_identity_claim=False))
    require(residual<1e-7 and abs(math.fsum(minutes)-5*length)<1e-7,'RESIDUAL_O_MINUTE_CONSERVATION')
    original_segments=lineup_segments(minutes,length)
    # The old witness can omit floating-point cuts <1e-7 minutes. Compile a
    # contiguous representation and disclose every boundary adjustment; this
    # never changes the sampled minute vector. Per-actor reconciliation remains
    # bounded by the existing declared 1e-7 minute representation tolerance.
    segments=[];adjustments=[];previous=0.
    for segment in original_segments:
        start=float(segment['start']);end=float(segment['end'])
        require(abs(start-previous)<1e-7,'RESIDUAL_O_WITNESS_GAP')
        if start!=previous:adjustments.append(dict(original=start,represented=previous))
        segments.append(dict(start=previous,end=end,player_indices=segment['player_indices']));previous=end
    require(bool(segments) and abs(previous-length)<1e-7,'RESIDUAL_O_WITNESS_END')
    if previous!=length:adjustments.append(dict(original=previous,represented=length))
    segments[-1]['end']=length
    return dict(schema='conditional-residual-team-O/1',actors=actors,minutes=minutes,
        segments=segments,witness_boundary_roundoff_adjustments=adjustments,
        witness_representation_tolerance_minutes=1e-7,residual_group_minutes=group_minutes,uniform_draw=u,
        capacity_certificate=certificate,latent_zero_dependence='INDEPENDENT_BETA_PER_NAMED_PLAYER_SCENARIO',
        all_stats_share_exact_exposure=True,renormalized_named_exposures=False,
        genuine_participation_probability=None,complete_legal_roster_claim=False)


def audit_team(draw,length):
    require(type(length) in (int,float) and math.isfinite(length) and length>=48 and
        (length-48)%5==0,'RESIDUAL_O_DURATION')
    actors=draw['actors'];minutes=draw['minutes'];segments=draw['segments']
    teams={a.get('team_id') for a in actors}
    require(len(teams)==1 and all(type(t) is str and bool(t) for t in teams),'RESIDUAL_O_SINGLE_TEAM')
    ids=[a['player_id'] for a in actors if a['player_id'] is not None]
    require(len(ids)==len(set(ids)),'RESIDUAL_O_DUPLICATE_ID')
    require(len(actors)==len(minutes) and all(0<=m<=length for m in minutes),'RESIDUAL_O_ACTOR_MINUTES')
    require(abs(math.fsum(minutes)-5*length)<1e-7,'RESIDUAL_O_TOTAL')
    integrated=np.zeros(len(actors));previous=0.
    for segment in segments:
        require(abs(segment['start']-previous)<1e-7 and segment['end']>segment['start'],'RESIDUAL_O_STINT_CLOCK')
        ids=segment['player_indices'];require(len(ids)==len(set(ids))==5,'RESIDUAL_O_FIVE_ON_COURT')
        require(all(type(i) is int and 0<=i<len(actors) for i in ids),'RESIDUAL_O_STINT_ACTORS')
        for i in ids:integrated[i]+=segment['end']-segment['start']
        previous=segment['end']
    require(abs(previous-length)<1e-7 and np.allclose(integrated,minutes,atol=1e-7,rtol=0),
        'RESIDUAL_O_STINT_RECONCILIATION')
    for actor in actors:
        if actor['kind']=='ANONYMOUS_RESIDUAL_ACTOR_SLOT':
            require(actor['player_id'] is None and actor['source_identity_claim'] is False,'RESIDUAL_O_FAKE_PLAYER_ID')
    return dict(violations=0,actors=len(actors),named_players=sum(a['kind']=='NAMED_SOURCE_PLAYER' for a in actors),
        residual_is_group_not_fake_player=True,team_minute_total=math.fsum(minutes))
