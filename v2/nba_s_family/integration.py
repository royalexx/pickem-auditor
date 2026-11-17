"""S integration v1.1; additive sidecars, never changes frozen G0 envelopes."""
from collections import defaultdict
from .model import (SFError, fit, utc, canonical, digest, conditional_pmf,
                    _rate_parameters, _conversion_parameters)
from v2.nba_architecture.v2_contracts import validate_pregame, verify, seal
from v2.nba_architecture.families_v2 import validate_opportunity
from scipy.stats import poisson, nbinom, betabinom

VERSION = 'nba-S-P1-P3-P4/1.1.0'


def history_from_p1(p, *, annotations, source_manifest, stat, asof_cutoff_utc):
    """Deterministic P1 feature pivot. Annotations are P1-authenticated sidecars.

    No invented publication clocks or roles. Return rows only after fit validates
    every receipt, clock, duration and identity. Missing evidence quarantines the
    entire requested pool rather than silently changing its denominator.
    """
    validate_pregame(p); verify(p)
    sources = {s['receipt_sha256']: s for s in p['sources']}
    groups = defaultdict(dict)
    for f in p['features']:
        if not f['name'].startswith('player:'):
            continue
        prefix, field = f['name'].rsplit(':', 1)
        key = (f['source_receipt_sha256'], prefix[len('player:'):])
        if field in groups[key]:
            raise SFError('P1_DUPLICATE_FEATURE')
        groups[key][field] = f['value']
    rows = []
    for (receipt, pid), values in sorted(groups.items()):
        if stat not in values:
            raise SFError('P1_STAT_MISSING')
        a = annotations.get(receipt)
        if not isinstance(a, dict) or set(a) != {
                'role', 'player_id', 'game_date', 'game_start_at', 'outcome_available_at'}:
            raise SFError('P1_CLOCK_ROLE_EVIDENCE_UNRESOLVED')
        if a['player_id'] != pid:
            raise SFError('P1_PLAYER_MISMATCH')
        source = sources[receipt]
        if a['game_date'] != source['historical_game_date']:
            raise SFError('P1_GAME_DATE_MISMATCH')
        if values.get('prior_game_id') == p['game_id']:
            raise SFError('TARGET_GAME_USED_IN_TRAINING')
        rows.append(dict(game_id=values['prior_game_id'],player_id=pid,
            team_id=values['historical_team_id'],stat=stat,role=a['role'],
            game_start_at=a['game_start_at'],outcome_available_at=a['outcome_available_at'],
            source_receipt_sha256=receipt,source_raw_sha256=source['raw_sha256'],
            count=values[stat],minutes=values['minutes'],
            three_attempts=values.get('fg3a')))
    # Validate even when caller only requests transformation, not a model fit.
    fit(rows,asof_cutoff_utc=asof_cutoff_utc,source_manifest=source_manifest,
        stat=stat,family='S3' if stat=='threes' else 'S1')
    return sorted(rows,key=lambda r:(r['game_start_at'],r['game_id'],r['player_id']))


def joint_conditional(fitted, *, pregame, game_state, opportunity,
                      scenario_id, player_id, team_id, role, projected_attempts=None):
    """Source-bound S-to-J conditional law on the exact P3 scenario.

    J supplies 3PA from its shared shot allocation, before conversion; this
    function never obtains an observed target attempt count. P4's existing
    synthetic-rate simulator cannot consume this law without an owner change.
    """
    validate_pregame(pregame); verify(pregame)
    verify(game_state); verify(opportunity)
    validate_opportunity(opportunity,pregame,game_state)
    a=fitted.data
    if utc(a['training_cutoff_at']) > utc(pregame['input_freeze_at']):
        raise SFError('MODEL_FIT_AFTER_FREEZE')
    if any(r['game_id']==pregame['game_id'] for r in a['training_rows']):
        raise SFError('TARGET_GAME_USED_IN_TRAINING')
    roster={r['player_id']:r['team_id'] for r in pregame['players']}
    if roster.get(player_id)!=team_id:
        raise SFError('TARGET_PLAYER_TEAM_MISMATCH')
    scenarios=[s for s in opportunity['scenarios'] if s['scenario_id']==scenario_id]
    if len(scenarios)!=1:
        raise SFError('SCENARIO_ID_UNRESOLVED')
    row=next(r for r in scenarios[0]['players'] if r['player_id']==player_id)
    exposure=row['minutes']
    if a['family']=='S3':
        if not isinstance(projected_attempts, dict):
            raise SFError('PROJECTED_ATTEMPT_EVIDENCE_REQUIRED')
        verify(projected_attempts)
        expected={'schema','content_hash','basis','source_snapshot_sha256',
                  'opportunity_sha256','scenario_id','player_id','team_id','three_pa'}
        if set(projected_attempts)!=expected or projected_attempts['schema']!=VERSION:
            raise SFError('PROJECTED_ATTEMPT_SCHEMA')
        joins={'basis':'projected_shared_shot_allocation',
               'source_snapshot_sha256':pregame['content_hash'],
               'opportunity_sha256':opportunity['content_hash'],
               'scenario_id':scenario_id,'player_id':player_id,'team_id':team_id}
        if any(projected_attempts[k]!=v for k,v in joins.items()):
            raise SFError('PROJECTED_ATTEMPT_SOURCE_JOIN')
        exposure=projected_attempts['three_pa']
    if a['family']=='S3' and (type(exposure) is not int or exposure<0):
        raise SFError('PROJECTED_3PA_INTEGER_REQUIRED')
    if (row['participation']=='DNP' or row['minutes']==0) and exposure!=0:
        raise SFError('ATTEMPTS_WITHOUT_EXPOSURE')
    masses,tail,params=conditional_pmf(fitted,player_id=player_id,role=role,
                                     opportunity=exposure)
    if row['participation']=='DNP' or row['minutes']==0:
        masses,tail=[1.],0.
    return seal(dict(schema=VERSION,kind='S_to_J_conditional',
        game_id=pregame['game_id'],player_id=player_id,team_id=team_id,
        source_snapshot_sha256=pregame['content_hash'],
        game_state_sha256=game_state['content_hash'],
        opportunity_sha256=opportunity['content_hash'],scenario_id=scenario_id,
        scenario_sha256=digest(canonical(scenarios[0])),
        model_artifact_sha256=fitted.artifact_sha256,
        training_cutoff_at=a['training_cutoff_at'],source_receipts=a['source_receipts'],
        family=a['family'],stat=a['stat'],projected_exposure=exposure,
        projected_attempt_sha256=None if projected_attempts is None else projected_attempts['content_hash'],
        pmf=[dict(value=i,mass=p) for i,p in enumerate(masses)],
        tail_mass_upper_bound=tail,parameters=params,
        status='SHADOW_CONDITIONAL_KERNEL_NOT_P4_ACCEPTED'))


def full_count_law(fitted, *, player_id, role, projected_exposure):
    """Return analytic frozen law: pmf(k), sf(k), mean(), var(), full support.

    This supplements G0's bounded finite representation. No tail is discarded
    in analytic queries; the finite PMF remains explicitly conditional-retained.
    """
    _,_,p=conditional_pmf(fitted,player_id=player_id,role=role,
                          opportunity=projected_exposure)
    family=fitted.data['family']
    if family=='S0': return poisson(p['game_mean'])
    if family=='S3': return betabinom(projected_exposure,p['alpha'],p['beta'])
    if projected_exposure==0: return poisson(0)
    if family=='S1': return nbinom(p['alpha'],p['beta']/(p['beta']+projected_exposure))
    mu=p['rate_mean']*projected_exposure
    return nbinom(p['dispersion'],p['dispersion']/(p['dispersion']+mu))
