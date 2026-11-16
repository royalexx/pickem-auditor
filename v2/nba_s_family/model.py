"""Research-only NBA S0/S1/S2/S3 conditional count models.

S0: observed past-game Poisson control (S_ONLY, assumes appearance).
S1: cross-player shrinkage + Gamma-Poisson conditional per-minute rate.
S2: predeclared dispersion NB2 conditional per-minute challenger.
S3: Beta-binomial made-threes conversion given *projected* 3PA (J kernel).

No source collector, participant/minute model, fitted NUTS, outcome scorer,
optimization, production decision, or independent S/O/J model voting here.
Historic completed games' minutes are training exposures only. Target actual
minutes, actual 3PA and final game outcomes are forbidden prediction inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import hashlib
import json
import math

import numpy as np
from scipy.stats import betabinom, nbinom, poisson

from v2.nba_architecture.v2_contracts import (
    VERSION, ContractError, instant, seal, verify, threshold_triplet,
    validate_pregame, validate_distribution,
)

STATS = ("points", "rebounds", "assists", "threes")
FAMILIES = ("S0", "S1", "S2", "S3")
TAIL_TARGET = 1e-11
MAX_SUPPORT = 4096


class SFError(ValueError):
    """Fail-closed typed research blocker."""
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def utc(v):
    try:
        return instant(v)
    except (ContractError, TypeError, AttributeError) as exc:
        raise SFError("INVALID_OR_MISSING_UTC_TIME") from exc


def finite(x, *, minimum=0):
    if type(x) not in (float, int) or not math.isfinite(x) or x < minimum:
        raise SFError("INVALID_NUMERIC_EXPOSURE_OR_COUNT")
    return float(x)


def count(x):
    if type(x) is not int or x < 0:
        raise SFError("INVALID_INTEGER_COUNT")
    return x


def sha(x):
    if not isinstance(x, str) or len(x) != 64 or any(c not in '0123456789abcdef' for c in x):
        raise SFError("INVALID_SOURCE_SHA256")
    return x


@dataclass(frozen=True)
class FittedS:
    """Content-addressed immutable artifact, independent of mutable input rows."""
    payload: bytes

    @property
    def artifact_sha256(self):
        return digest(self.payload)

    @property
    def data(self):
        return json.loads(self.payload)


@dataclass(frozen=True)
class Prediction:
    distribution: Optional[dict]
    abstain_reason: Optional[str]
    parameters: Optional[dict]
    uncertainty: Optional[dict]


def fit(history_rows, *, asof_cutoff_utc, source_manifest, stat,
        family="S1", hyperparameters=None, seed=0):
    """Fit only finished, source-proven prior games, excluding all later labels.

    source_manifest maps exact P1 receipt hashes to verified raw-data hash and
    first-known-available timestamp. P1 owns authentication of those claims.
    Every history row must be complete and refer to a manifest entry. S itself
    never accesses a network, CSV archive, market or postgame outcome vault.
    """
    if family not in FAMILIES or stat not in STATS or (family == 'S3' and stat != 'threes'):
        raise SFError("UNSUPPORTED_FAMILY_STAT")
    if type(seed) is not int or seed < 0:
        raise SFError("INVALID_SEED")
    cutoff = utc(asof_cutoff_utc)
    h = hyperparameters or {}
    if not isinstance(h, dict) or set(h) - {"prior_minutes", "prior_attempts", "dispersion", "min_player_games"}:
        raise SFError("INVALID_HYPERPARAMETERS")
    prior_minutes = finite(h.get('prior_minutes', 180.), minimum=1e-12)
    prior_attempts = finite(h.get('prior_attempts', 40.), minimum=1e-12)
    dispersion = finite(h.get('dispersion', 12.), minimum=1e-12)
    minimum_games = h.get('min_player_games', 2)
    if type(minimum_games) is not int or minimum_games < 1:
        raise SFError("INVALID_MIN_PLAYER_GAMES")
    if not isinstance(source_manifest, dict) or not source_manifest:
        raise SFError("SOURCE_MANIFEST_MISSING")
    if not isinstance(history_rows, (tuple, list)) or not history_rows:
        raise SFError("EMPTY_TRAINING_POOL")
    rows, seen, sources_used = [], set(), set()
    forbidden = {"target_actual_minutes", "target_final_usage", "future_games",
                 "target_game_outcome", "target_actual_three_attempts", "target_result",
                 "actual_target_minutes", "actual_target_usage", "actual_minutes"}
    required = {"game_id", "player_id", "team_id", "stat", "role",
                "game_start_at", "outcome_available_at", "source_receipt_sha256",
                "source_raw_sha256", "count", "minutes", "three_attempts"}
    for raw in history_rows:
        if not isinstance(raw, dict) or set(raw) != required or set(raw) & forbidden:
            raise SFError("UNSAFE_OR_INCOMPLETE_HISTORY_ROW")
        r = dict(raw)
        if r['stat'] != stat:
            raise SFError("STAT_IDENTITY_MISMATCH")
        if any(not isinstance(r[k], str) or not r[k].strip() for k in ('game_id','player_id','team_id','role')):
            raise SFError("PLAYER_OR_GAME_IDENTITY_MISSING")
        k = (r['game_id'], r['player_id'], r['stat'])
        if k in seen:
            raise SFError("DUPLICATE_GAME_PLAYER_STAT")
        seen.add(k)
        start, available = utc(r['game_start_at']), utc(r['outcome_available_at'])
        if start >= cutoff or available > cutoff or available <= start:
            raise SFError("FUTURE_OR_UNRELEASED_OUTCOME")
        receipt = sha(r['source_receipt_sha256'])
        source = source_manifest.get(receipt)
        if not isinstance(source, dict) or set(source) != {'raw_sha256','available_at','status'}:
            raise SFError("SOURCE_RECEIPT_MISSING")
        if source['status'] != 'P1_VERIFIED':
            raise SFError("SOURCE_NOT_VERIFIED_BY_P1")
        if sha(source['raw_sha256']) != sha(r['source_raw_sha256']):
            raise SFError("RAW_SOURCE_SHA_MISMATCH")
        src_time = utc(source['available_at'])
        if src_time > cutoff or src_time < available:
            raise SFError("SOURCE_LATE_OR_INCONSISTENT")
        y = count(r['count'])
        minutes = finite(r['minutes'])
        if minutes > 53 or (minutes == 0 and y > 0):
            raise SFError("HISTORICAL_EXPOSURE_PHYSICS")
        if family in ('S1','S2','S3') and minutes == 0:
            raise SFError("TRAINING_GAME_ZERO_EXPOSURE")
        if r['three_attempts'] is not None:
            attempts = count(r['three_attempts'])
            if stat == 'threes' and y > attempts:
                raise SFError("THREES_EXCEED_ATTEMPTS")
        elif family == 'S3':
            raise SFError("MISSING_HISTORICAL_THREE_ATTEMPTS")
        r['minutes'] = minutes
        rows.append(r)
        sources_used.add(receipt)
    rows.sort(key=lambda r:(r['game_start_at'],r['game_id'],r['player_id']))
    # Forbid any subsequently supplied mixed game chronology in the artifact.
    if len({r['game_id'] for r in rows}) == 0:
        raise SFError("EMPTY_TRAINING_POOL")
    artifact = {
        'version':'nba-v25-S/1.0.0', 'family':family, 'stat':stat,
        'training_cutoff_at':asof_cutoff_utc,
        'last_game_start_at':max(r['game_start_at'] for r in rows),
        'last_outcome_available_at':max(r['outcome_available_at'] for r in rows),
        'source_receipts':sorted(sources_used),
        'source_manifest_sha256':digest(canonical({k:source_manifest[k] for k in sorted(sources_used)})),
        'code_sha256':digest(Path(__file__).read_bytes()),
        'training_rows':rows,
        'hyperparameters':{'prior_minutes':prior_minutes, 'prior_attempts':prior_attempts,
                           'dispersion':dispersion, 'min_player_games':minimum_games},
        'seed':seed,
        'availability_basis':'P1_verified_receipts_no_target_final',
        'research_only':True,
    }
    return FittedS(canonical(artifact))


def _rate_parameters(artifact, player_id, role):
    rows=artifact['training_rows']
    own=[r for r in rows if r['player_id']==player_id]
    peers=[r for r in rows if r['player_id']!=player_id and r['role']==role]
    if not peers:
        raise SFError("INSUFFICIENT_PEER_HISTORY")
    if len(own) < artifact['hyperparameters']['min_player_games']:
        raise SFError("INSUFFICIENT_PLAYER_HISTORY")
    # Do not re-count target history as an independent peer hyperprior.
    peer_exposure=math.fsum(r['minutes'] for r in peers)
    if peer_exposure <= 0:
        raise SFError("PEER_EXPOSURE_MISSING")
    peer_rate=math.fsum(r['count'] for r in peers)/peer_exposure
    prior_minutes=artifact['hyperparameters']['prior_minutes']
    alpha=prior_minutes*max(peer_rate,1e-10)+math.fsum(r['count'] for r in own)
    beta=prior_minutes+math.fsum(r['minutes'] for r in own)
    return {'alpha':alpha, 'beta':beta, 'rate_mean':alpha/beta,
            'rate_posterior_sd':math.sqrt(alpha)/beta,
            'peer_rate':peer_rate,'player_games':len(own),'peer_games':len(peers),
            'historical_teams':sorted({r['team_id'] for r in own})}


def _conversion_parameters(artifact, player_id, role):
    rows=artifact['training_rows']
    own=[r for r in rows if r['player_id']==player_id]
    peers=[r for r in rows if r['player_id']!=player_id and r['role']==role]
    if len(own)<artifact['hyperparameters']['min_player_games'] or not peers:
        raise SFError("INSUFFICIENT_CONVERSION_HISTORY")
    peer_attempts=sum(r['three_attempts'] for r in peers)
    if peer_attempts <= 0:
        raise SFError("ZERO_PEER_ATTEMPTS")
    q=sum(r['count'] for r in peers)/peer_attempts
    n=artifact['hyperparameters']['prior_attempts']
    alpha=n*max(q,1e-9)+sum(r['count'] for r in own)
    beta=n*max(1-q,1e-9)+sum(r['three_attempts']-r['count'] for r in own)
    return {'alpha':alpha,'beta':beta,'success_mean':alpha/(alpha+beta),
            'success_probability_posterior_sd':math.sqrt(alpha*beta/((alpha+beta)**2*(alpha+beta+1))),
            'player_games':len(own),'peer_games':len(peers)}


def _pmf(law, params, exposure, *, target=TAIL_TARGET):
    """Exact analytic law up to certified SF tail; conditional truncation explicit."""
    if law=='S3':
        if type(exposure) is not int:
            raise SFError("PROJECTED_3PA_INTEGER_REQUIRED")
        if exposure < 0 or exposure > MAX_SUPPORT:
            raise SFError("PROJECTED_3PA_OUT_OF_RANGE")
        values=np.arange(exposure+1)
        mass=betabinom.pmf(values, exposure, params['alpha'], params['beta'])
        tail=0.
    else:
        minutes=finite(exposure)
        if minutes>100:
            raise SFError("UNPHYSICAL_PROJECTED_MINUTES")
        if law=='S0':
            mu=params['game_mean']
            distribution=poisson(mu)
        elif law=='S1':
            # Poisson(lambda * m), lambda ~ Gamma(alpha, rate=beta).
            alpha,beta=params['alpha'],params['beta']
            distribution=nbinom(alpha,beta/(beta+minutes))
        elif law=='S2':
            mu=params['rate_mean']*minutes
            k=params['dispersion']
            distribution=nbinom(k,k/(k+mu))
        else:
            raise SFError("UNSUPPORTED_LIKELIHOOD")
        if law in ('S1','S2') and minutes==0:
            return [1.],0.
        if law=='S0' and mu==0:
            return [1.],0.
        # sf gives the actual omitted mass, not an unquantified CDF claim.
        hi=min(MAX_SUPPORT, max(16,int(math.ceil(distribution.mean()+10*math.sqrt(distribution.var()+1)))))
        while distribution.sf(hi)>target and hi<MAX_SUPPORT:
            hi=min(MAX_SUPPORT,max(hi+1,int(hi*1.5)))
        tail=float(distribution.sf(hi))
        if not math.isfinite(tail) or tail>target:
            raise SFError("UNCONTROLLED_RIGHT_TAIL")
        mass=distribution.pmf(np.arange(hi+1))
    raw=np.asarray(mass,dtype=np.float64)
    total=float(math.fsum(float(x) for x in raw))
    if not np.all(np.isfinite(raw)) or total<=0 or abs((1-total)-tail)>1e-8:
        raise SFError("PMF_NUMERICAL_INTEGRITY")
    # This is the explicitly disclosed, tail-bounded *conditional-on-retained*
    # law. No hidden cutoff, and no discarded tail claimed to be exact zero.
    return [float(x/total) for x in raw],tail


def conditional_pmf(artifact, *, player_id, role, opportunity,
                    statistic=None):
    """S-only conditional kernel for J; J owns scenario sampling and covariance.

    For S1/S2 opportunity is projected minutes. For S3 it is projected 3PA.
    S0 ignores opportunity and returns the historical per-game count control.
    """
    a=artifact.data if isinstance(artifact,FittedS) else None
    if a is None or artifact.artifact_sha256!=digest(artifact.payload):
        raise SFError("MODEL_ARTIFACT_INVALID")
    if a.get('code_sha256') != digest(Path(__file__).read_bytes()):
        raise SFError("MODEL_CODE_VERSION_DRIFT")
    if statistic is not None and statistic!=a['stat']:
        raise SFError("STAT_IDENTITY_MISMATCH")
    if a['family']=='S0':
        own=[r['count'] for r in a['training_rows'] if r['player_id']==player_id]
        if len(own)<a['hyperparameters']['min_player_games']:
            raise SFError("INSUFFICIENT_PLAYER_HISTORY")
        params={'game_mean':math.fsum(own)/len(own),'player_games':len(own)}
        distribution,tail=_pmf('S0',params,0)
    elif a['family']=='S3':
        params=_conversion_parameters(a,player_id,role)
        distribution,tail=_pmf('S3',params,opportunity)
    else:
        params=_rate_parameters(a,player_id,role)
        if a['family']=='S2':
            params['dispersion']=a['hyperparameters']['dispersion']
        distribution,tail=_pmf(a['family'],params,opportunity)
    return distribution, tail, params


def predict_conditional(fitted, *, player_id, role, projected_exposure, statistic=None):
    """Stable pure callable for J's shared draw; no scenario self-generation."""
    try:
        masses,tail,params=conditional_pmf(fitted,player_id=player_id,role=role,
                   opportunity=projected_exposure,statistic=statistic)
        return Prediction(None,None,{'support':[{'value':i,'mass':p} for i,p in enumerate(masses)],
                     'tail_mass_upper_bound':tail, **params},
                     {'p0':masses[0],'tail_mass_upper_bound':tail})
    except (SFError,ContractError) as exc:
        return Prediction(None,getattr(exc,'reason',str(exc)),None,None)


def exact_triplet(masses, line):
    return threshold_triplet([{'value':i,'mass':x} for i,x in enumerate(masses)],line)


def predict(fitted, *, frozen_pregame, target_player_id, role,
            opportunity=None, game_state=None, conditioning='unconditional',
            frozen_at=None, seed=0):
    """Build canonical G0 S_ONLY or S_O law; never S_O_J independently.

    S_O consumes exact G/O scenario identifiers and weights. This is an
    analytic conditional mixture, NOT a second independent vote or a new G/O
    sampler. S3 remains a conditional 3PA-to-3PM kernel for J until a verified
    upstream projected-attempt law is made available.
    """
    try:
        if type(seed) is not int or seed<0:
            raise SFError('INVALID_SEED')
        if conditioning not in ('unconditional','conditional_on_participation'):
            raise SFError('UNSUPPORTED_CONDITIONING')
        a=fitted.data
        if a.get('code_sha256') != digest(Path(__file__).read_bytes()):
            raise SFError('MODEL_CODE_VERSION_DRIFT')
        validate_pregame(frozen_pregame)
        p=frozen_pregame
        verify(p)  # independently protect bytes even if a caller skips validation
        if utc(a['training_cutoff_at'])>utc(p['input_freeze_at']):
            raise SFError('MODEL_FIT_AFTER_FREEZE')
        if any(r['game_id']==p['game_id'] for r in a['training_rows']):
            raise SFError('TARGET_GAME_USED_IN_TRAINING')
        if any(utc(r['outcome_available_at'])>utc(p['input_freeze_at']) for r in a['training_rows']):
            raise SFError('TRAINING_OUTCOME_AFTER_FREEZE')
        target=next((r for r in p['players'] if r['player_id']==target_player_id),None)
        if target is None:
            raise SFError('TARGET_PLAYER_NOT_IN_PREGAME_ROSTER')
        team=target['team_id']
        if a['family']=='S3':
            raise SFError('S3_REQUIRES_PREDECLARED_3PA_J_OPPORTUNITIES')
        if a['family']=='S0' and opportunity is not None:
            raise SFError('S0_CONTROL_IS_S_ONLY')
        if a['family']!='S0' and (opportunity is None or game_state is None):
            raise SFError('PREGAME_G_O_OPPORTUNITY_REQUIRED')
        if a['family']=='S0' and conditioning!='unconditional':
            raise SFError('S0_PARTICIPATION_CONDITION_UNSUPPORTED')
        if target['legal_eligibility'] is False or target['availability']=='out':
            if conditioning=='conditional_on_participation':
                raise SFError('EXCLUDED_PLAYER_CANNOT_CONDITION_ON_PLAYING')
            mass,tail,params=[1.],0.,{'excluded_by_pregame':True}
            mode='S_ONLY' if opportunity is None else 'S_O'
        elif opportunity is None:
            if target['availability'] in ('unknown','questionable'):
                raise SFError('PARTICIPATION_UNRESOLVED_S_ONLY')
            mass,tail,params=conditional_pmf(fitted,player_id=target_player_id,
                                               role=role,opportunity=0)
            mode='S_ONLY'
        else:
            from v2.nba_architecture.families_v2 import validate_opportunity
            verify(game_state)
            verify(opportunity)
            validate_opportunity(opportunity,p,game_state)
            if any(x['minutes_law']['family']!='discrete_minutes' for x in opportunity['players']):
                raise SFError('DIAGNOSTIC_MINUTES_NOT_FORECAST_LAW')
            person=next(x for x in opportunity['players'] if x['player_id']==target_player_id)
            if person['participation_probability'] is None and conditioning=='unconditional':
                raise SFError('UNKNOWN_APPEARANCE_PROBABILITY')
            if person['participation_evidence']=='unknown' and conditioning!='conditional_on_participation':
                raise SFError('UNKNOWN_APPEARANCE_PROBABILITY')
            scenarios=opportunity['scenarios']
            pitems=[]; tail=0.; denominator=0.
            for sc in scenarios:
                x=next(y for y in sc['players'] if y['player_id']==target_player_id)
                if conditioning=='conditional_on_participation' and x['participation']=='DNP':
                    continue
                w=float(sc['weight']); denominator+=w
                if x['participation']=='DNP' or x['minutes']==0:
                    pm,ta=[1.],0.
                else:
                    pm,ta,_=conditional_pmf(fitted,player_id=target_player_id,
                                  role=role,opportunity=float(x['minutes']))
                pitems.append((w,pm));tail+=w*ta
            if denominator<=0:
                raise SFError('NO_PLAYED_SCENARIO_SUPPORT')
            length=max(len(pm) for _,pm in pitems)
            mass=[math.fsum(w*(pm[i] if i<len(pm) else 0.) for w,pm in pitems)/denominator
                  for i in range(length)]
            mass=[x/math.fsum(mass) for x in mass]
            tail/=denominator
            params=(_rate_parameters(a,target_player_id,role))
            if a['family']=='S2':
                params['dispersion']=a['hyperparameters']['dispersion']
            params['opportunity_scenarios']=len(scenarios)
            params['conditioning']=conditioning
            mode='S_O'
        if tail>1e-8 or not math.isclose(math.fsum(mass),1.,rel_tol=0,abs_tol=1e-10):
            raise SFError('DISTRIBUTION_INTEGRITY_FAILURE')
        label={'model_id':'research:nba:'+a['family'], 'version':a['version'],
               'artifact_sha256':fitted.artifact_sha256,
               'code_sha256':a['code_sha256'],
               'training_cutoff_at':a['training_cutoff_at']}
        lineage={'S':label,'O':None,'G':None,'J':None}
        if mode=='S_O':
            lineage['O']=opportunity['model'];lineage['G']=game_state['model']
        payload={'schema':VERSION,'kind':'distribution',
             'source_profile':p['source_profile'], 'source_snapshot_sha256':p['content_hash'],
             'game_id':p['game_id'],'event_start_at':p['event_start_at'],
             'player_id':target_player_id,'team_id':team,'stat':a['stat'],
             'period':'full_game_including_ot','support':'nonnegative_integer',
             'pipeline_mode':mode,'conditioning':conditioning,
             'status':'RESEARCH_RECONSTRUCTION' if p['source_profile']=='historical_reconstruction'
                      else 'UNCERTIFIED_SHADOW',
             'lineage':lineage,'forecast_at':p['forecast_at'],
             'frozen_at':frozen_at or p['forecast_at'],'rng_seed':seed,
             'scenario_bundle_sha256':None,
             'opportunity_output_sha256':None if mode=='S_ONLY' else opportunity['content_hash'],
             'derivation':('past_game_poisson_control' if mode=='S_ONLY' else
                          'same_G_O_scenario_weighted_conditional_count_law'),
             'numerical':{'method':'analytic','scenario_count':None,'max_probability_se':None,
                          'tail_mass_upper_bound':tail,'effective_sample_size':None,
                          'uncertainty_basis':'analytic_exact_or_bound',
                          'zero_event_95_upper_bound':None},
             'pmf':[{'value':i,'mass':float(v)} for i,v in enumerate(mass)],
             'historical_asof_limitations':p['historical_asof_limitations']}
        d=seal(payload)
        if mode=='S_ONLY':
            validate_distribution(d,p)
        else:
            from v2.nba_architecture.families_v2 import validate_forecast
            validate_forecast(d,p,g=game_state,o=opportunity)
        uncertainty={'p_zero':mass[0], 'retained_mean':math.fsum(i*x for i,x in enumerate(mass)),
                     'retained_variance':math.fsum((i**2)*x for i,x in enumerate(mass))-
                                         math.fsum(i*x for i,x in enumerate(mass))**2,
                     'tail_mass_upper_bound':tail,
                     'rate_posterior_sd':params.get('rate_posterior_sd'),
                     'opportunity_scenario_ess':(
                         1. / math.fsum(float(sc['weight'])**2 for sc in opportunity['scenarios'])
                         if opportunity is not None else None),
                     'opportunity_scenario_law_is_input_not_independent_vote':True,
                     'source_certification':p['certification'],
                     'epistemic_basis':'shrinkage_parameters_or_unmeasured_role',
                     'not_predictive_accuracy_evidence':True}
        return Prediction(d,None,params,uncertainty)
    except (SFError,ContractError,OverflowError,ValueError) as exc:
        return Prediction(None,getattr(exc,'reason',str(exc)),None,None)