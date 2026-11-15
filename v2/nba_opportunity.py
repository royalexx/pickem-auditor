"""NBA WS2 v1: isolated, shadow-only conditional minutes and team allocation.

No canonical collector, outcome likelihood, production policy or WS1 dependency.
Active roster eligibility and game participation are distinct. All times UTC aware.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Protocol, Sequence, TypedDict
import numpy as np
from scipy.special import betainc, ndtr, ndtri

VERSION = 'NBAOpportunityForecast/1.0.0'
STATUSES = ('confirmed_inactive', 'confirmed_active', 'probable_participant',
            'questionable_participant', 'unverified')
FEATURES = ('median5', 'mean10', 'mean3', 'sd10', 'trend', 'rest_days',
            'back_to_back', 'return_gap', 'team_change', 'home', 'prior_n',
            'role_high', 'role_low')


class NBAOpportunityForecast(TypedDict):
    """Versioned outcome-sampler handoff. Quantiles/moments are played-conditioned.

    Unconditional zero probability is 1-participation_probability only when
    participation has been independently supplied. Product voids stay separate.
    Scenario references are populated only for valid team-consistent scenarios.
    """
    schema: str
    forecast_id: str
    game_id: str
    player_id: str
    team_id: str
    opponent_id: str
    event_start_at: str
    forecast_at: str
    input_freeze_at: str
    source_available_at: str
    source_ingested_at: str
    source_sha256: str
    training_cutoff_at: str
    participation_status: str
    participation_probability: float | None
    participation_probability_interval: tuple[float, float] | None
    active_roster_eligible: bool | None
    expected_minutes_given_played: float
    variance_minutes_given_played: float
    quantiles_given_played: dict[str, float]
    numerical_omitted_ot_mass: float
    distribution: dict
    role: dict
    scenario_ids: list[str]
    seed: int
    product_eligibility: dict
    provenance: dict
    abstention_reasons: list[str]
    reliability_reasons: list[str]
    status: str


class FutureOutcomeSampler(Protocol):
    """WS3/WS4 may consume these exposures without WS2 owning stat production."""
    def sample_given_opportunity(self, *, forecast: NBAOpportunityForecast,
                                 minutes: float, scenario_id: str,
                                 seed: int) -> dict: ...


def utc(value: str) -> datetime:
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None or t.utcoffset().total_seconds() != 0:
        raise ValueError('UTC_TIMESTAMP_REQUIRED')
    return t


@dataclass(frozen=True)
class PregameOpportunityInput:
    game_id: str
    player_id: str
    team_id: str
    opponent_id: str
    event_start_at: str
    forecast_at: str
    input_freeze_at: str
    source_available_at: str
    source_ingested_at: str
    training_cutoff_at: str
    source_sha256: str
    features: dict[str, float]
    position: str
    participation_status: str = 'unverified'
    participation_probability: float | None = None
    participation_probability_interval: tuple[float, float] | None = None
    active_roster_eligible: bool | None = None
    product_eligibility: dict = field(default_factory=dict)
    reliability_reasons: tuple[str, ...] = ()

    def validate(self):
        if not all((self.game_id, self.player_id, self.team_id, self.opponent_id)) or self.team_id == self.opponent_id:
            raise ValueError('INVALID_IDENTITY')
        a, i, z, f, e, t = map(utc, (self.source_available_at, self.source_ingested_at,
            self.input_freeze_at, self.forecast_at, self.event_start_at, self.training_cutoff_at))
        if not (a <= i <= z <= f < e and t <= z):
            raise ValueError('POST_EVENT_OR_FUTURE_INPUT')
        if len(self.source_sha256) != 64 or any(c not in '0123456789abcdef' for c in self.source_sha256):
            raise ValueError('SOURCE_HASH_REQUIRED')
        if self.participation_status not in STATUSES:
            raise ValueError('UNKNOWN_PARTICIPATION_STATUS')
        if set(self.features) != set(FEATURES) or not all(math.isfinite(v) for v in self.features.values()):
            raise ValueError('INVALID_FEATURES_OR_POSTGAME_FIELD')
        p = self.participation_probability
        if p is not None and (not math.isfinite(p) or not 0 <= p <= 1):
            raise ValueError('INVALID_PARTICIPATION_PROBABILITY')
        if self.participation_status == 'confirmed_inactive' and p not in (None, 0):
            raise ValueError('INACTIVE_PARTICIPATION_CONFLICT')
        ci = self.participation_probability_interval
        if ci is not None and (p is None or not 0 <= ci[0] <= p <= ci[1] <= 1):
            raise ValueError('INVALID_PARTICIPATION_INTERVAL')
        if self.active_roster_eligible is False and p not in (None, 0):
            raise ValueError('ROSTER_PARTICIPATION_CONFLICT')


class OpportunityFeatureAdapter(Protocol):
    """WS1 or deterministic fixtures supply independently verified pregame data."""
    def for_player(self, game_id: str, player_id: str) -> PregameOpportunityInput: ...


def role(mean: float) -> str:
    return 'high' if mean >= 28 else 'low' if mean < 14 else 'mid'


def position_group(position: str) -> str:
    return {'PG': 'G', 'SG': 'G', 'SF': 'F', 'PF': 'F'}.get(position, position)


def causal_features(history: Sequence[dict], *, game_date: str, team: str,
                    home: bool, prior_team_games_missed: int = 0) -> dict[str, float]:
    """History must be source verified; date-only reconstructions are exploratory.

    Same-day records excluded, not ordered using arbitrary game IDs. No starter,
    final-score, foul, teammate-absence or realized-OT variable is accepted.
    """
    past = sorted((r for r in history if r['game_date'] < game_date), key=lambda r: (r['game_date'], r['game_id']))[-10:]
    if len(past) < 5:
        raise ValueError('INSUFFICIENT_PRIOR_APPEARANCES')
    x = np.array([r['workload'] for r in past], dtype=float)
    if np.any(~np.isfinite(x)) or np.any(x <= 0):
        raise ValueError('DNP_NOT_CONDITIONAL_MINUTES')
    rest = (datetime.fromisoformat(game_date) - datetime.fromisoformat(past[-1]['game_date'])).days
    mean = float(x.mean())
    return dict(zip(FEATURES, [float(np.median(x[-5:])), mean, float(x[-3:].mean()),
        float(x.std(ddof=1)), float(x[-3:].mean()-mean), float(min(rest, 14)),
        float(rest == 1), float(min(prior_team_games_missed, 5)),
        float(team != past[-1]['team']), float(home), float(len(past)),
        float(mean >= 28), float(mean < 14)]))


@dataclass(frozen=True)
class MinuteLaw:
    """Positive share of game length, beta or truncated-lognormal OT mixture.

    OT count is zero-inflated geometric with unlimited theoretical support.
    Numerical CDF truncates only below a reported 1e-12 probability tolerance.
    This is a marginal research law; joint scenarios use shared game OT.
    """
    mean: float
    variance: float
    ot_probability: float
    ot_continuation: float
    family: str = 'beta'

    def __post_init__(self):
        if not (math.isfinite(self.mean) and 0 < self.mean < 48 and
                math.isfinite(self.variance) and self.variance > 0 and
                0 <= self.ot_probability < 1 and 0 < self.ot_continuation < 1):
            raise ValueError('INVALID_MINUTE_LAW')
        if self.family not in ('beta', 'truncated_lognormal'):
            raise ValueError('UNKNOWN_FAMILY')

    def ot_components(self):
        p, q = self.ot_probability, self.ot_continuation
        result = [(48., 1-p)]
        k = 1
        while p*q**(k-1) > 1e-12:
            result.append((48.+5*k, p*(1-q)*q**(k-1)))
            k += 1
        return result

    def shape(self):
        p, q = self.ot_probability, self.ot_continuation
        ek = p/(1-q)
        ek2 = p*(1+q)/(1-q)**2
        el, el2 = 48+5*ek, 2304+480*ek+25*ek2
        share = self.mean/el
        vk = ek2-ek*ek
        sv = max(1e-6, (self.variance-share*share*25*vk)/el2)
        sv = min(sv, .95*share*(1-share))
        concentration = share*(1-share)/sv-1
        return share*concentration, (1-share)*concentration

    def cdf(self, values):
        x = np.asarray(values, dtype=float)
        out = np.zeros_like(x)
        a,b = self.shape()
        for length, weight in self.ot_components():
            u = np.clip(x/length, 0, 1)
            if self.family == 'beta':
                c = betainc(a,b,u)
            else:
                share = a/(a+b)
                var = a*b/((a+b)**2*(a+b+1))
                s = math.sqrt(math.log1p(var/share**2))
                loc = math.log(share)-s*s/2
                c = ndtr((np.log(np.maximum(u, 1e-300))-loc)/s)/ndtr(-loc/s)
                c = np.where(x <= 0, 0, np.where(x >= length, 1, c))
            out += weight*c
        return np.clip(out, 0, 1)

    def sample_at_length(self, rng, length: float):
        a,b = self.shape()
        if self.family == 'beta':
            return float(length*rng.beta(a,b))
        share=a/(a+b); var=a*b/((a+b)**2*(a+b+1))
        s=math.sqrt(math.log1p(var/share**2)); loc=math.log(share)-s*s/2
        return float(length*np.exp(loc+s*ndtri(rng.random()*ndtr(-loc/s))))

    def summary(self):
        # Extend numerically to all OT components retained by the tolerance.
        grid = np.linspace(0, self.ot_components()[-1][0], 2049)
        c = self.cdf(grid)
        qs = {str(q):float(np.interp(q,c,grid)) for q in (.05,.1,.25,.5,.75,.9,.95)}
        a,b=self.shape(); comps=self.ot_components()
        el=sum(l*w for l,w in comps); el2=sum(l*l*w for l,w in comps)
        actual_mean=el*a/(a+b)
        actual_var=el2*a*(a+1)/((a+b)*(a+b+1))-actual_mean**2
        return {'expected_minutes_given_played':actual_mean,
                'variance_minutes_given_played':actual_var, 'quantiles_given_played':qs,
                'numerical_omitted_ot_mass':max(0.,1-sum(w for _,w in comps))}


@dataclass
class MinutesModel:
    """JSON serializable, frozen empirical-Bayes/ridge parameters."""
    cohorts: dict
    residual_variance: dict
    center: list
    scale: list
    ridge_coef: list
    ridge_intercept: float
    ot_probability: float
    ot_continuation: float
    training_cutoff_at: str
    training_manifest_sha256: str
    code_commit: str
    family: str = 'beta'

    def parameters(self, name: str, features: dict, position: str):
        cohort = self.cohorts.get(position_group(position)+'/'+role(features['mean10']), self.cohorts['ALL'])
        n=features['prior_n']
        if name == 'M0':
            mean=features['median5']
        elif name == 'M1':
            mean=(n*features['mean10']+5*cohort['mean'])/(n+5)
        elif name in ('M2', 'M2_disabled'):
            f=np.array([features[k] for k in FEATURES],dtype=float)
            if name == 'M2_disabled':
                f[2:]=np.array(self.center)[2:]
            mean=self.ridge_intercept+np.dot((f-self.center)/self.scale,self.ridge_coef)
        else:
            raise ValueError('UNKNOWN_MODEL')
        cv=self.residual_variance[name if name != 'M2_disabled' else 'M2'].get(role(features['mean10']), 64.)
        variance=cv if name == 'M0' else (n*features['sd10']**2+10*cv)/(n+10)
        if features['team_change'] or features['return_gap'] >= 2:
            variance=max(variance,cv)  # uncertainty, never a fabricated injury penalty
        return float(np.clip(mean,.1,47.9)), float(max(variance,4.))

    def law(self,name,features,position):
        mean,var=self.parameters(name,features,position)
        return MinuteLaw(mean,var,self.ot_probability,self.ot_continuation,self.family)

    def save(self,path):
        Path(path).write_text(json.dumps(asdict(self),sort_keys=True,indent=2,allow_nan=False)+'\n')

    @classmethod
    def load(cls,path):
        return cls(**json.loads(Path(path).read_text()))

    def forecast(self, name: str, item: PregameOpportunityInput, seed: int) -> NBAOpportunityForecast:
        item.validate()
        if utc(self.training_cutoff_at) > utc(item.training_cutoff_at):
            raise ValueError('MODEL_NEWER_THAN_DECLARED_CUTOFF')
        law=self.law(name,item.features,item.position)
        p=item.participation_probability
        reasons=list(item.reliability_reasons)
        abstain=[]
        if item.participation_status == 'confirmed_inactive' or item.active_roster_eligible is False:
            p=0.; abstain.append('INACTIVE_OR_INELIGIBLE')
        if p is None:
            reasons.append('PARTICIPATION_PROBABILITY_UNVERIFIED')
            abstain.append('UNCONDITIONAL_OPPORTUNITY_UNAVAILABLE')
        if item.participation_status in ('unverified','questionable_participant'):
            reasons.append('AVAILABILITY_UNCERTAIN')
        payload=dict(schema=VERSION,game_id=item.game_id,player_id=item.player_id,
            team_id=item.team_id,opponent_id=item.opponent_id,
            forecast_at=item.forecast_at,event_start_at=item.event_start_at,
            input_freeze_at=item.input_freeze_at,source_available_at=item.source_available_at,
            source_ingested_at=item.source_ingested_at,source_sha256=item.source_sha256,
            training_cutoff_at=self.training_cutoff_at,
            participation_status=item.participation_status,participation_probability=p,
            participation_probability_interval=item.participation_probability_interval,
            active_roster_eligible=item.active_roster_eligible,
            **law.summary(),distribution=asdict(law),
            role={'historical_workload_state':role(item.features['mean10']),
                  'position':item.position,'features':item.features},
            scenario_ids=[],seed=int(seed),product_eligibility=item.product_eligibility,
            provenance={'model':name,'code_commit':self.code_commit,
                        'training_manifest_sha256':self.training_manifest_sha256,
                        'artifact_sha256':hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()},
            abstention_reasons=abstain,reliability_reasons=reasons,status='UNCERTIFIED/SHADOW')
        payload['forecast_id']=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        return payload


def capped_allocation(desired, caps, total):
    """Euclidean projection onto box/simplex; caps are actual game lengths or
    externally supplied early-exit scenario limits, never generic player caps.
    """
    x=np.asarray(desired,dtype=float); cap=np.asarray(caps,dtype=float)
    if x.ndim != 1 or cap.shape != x.shape or not np.all(np.isfinite(x)) or not np.all(np.isfinite(cap)) or np.any(cap < 0) or not math.isfinite(total) or total < 0 or cap.sum() < total-1e-9:
        raise ValueError('INFEASIBLE_TEAM_ROTATION')
    low=float(np.min(x-cap))-total-1; high=float(np.max(x))+total+1
    for _ in range(80):
        mid=(low+high)/2
        if np.clip(x-mid,0,cap).sum() > total: low=mid
        else: high=mid
    return np.clip(x-(low+high)/2,0,cap)


def lineup_segments(minutes, length):
    """Construct a five-on-court witness, not a learned substitution chain.

    Lay intervals consecutively across five copies of game clock and wrap
    onto one clock. Each player appears at most once at any instant because
    its total is <= length. The resulting interval coverage is exactly five.
    """
    m=np.asarray(minutes,dtype=float)
    if np.any(~np.isfinite(m)) or np.any(m < -1e-8) or np.any(m > length+1e-8) or abs(m.sum()-5*length)>1e-7:
        raise ValueError('INVALID_TEAM_MINUTES')
    intervals=[]; start=0.
    for i,duration in enumerate(m):
        end=start+duration
        if duration > 1e-8:
            s=start%length; e=s+duration
            intervals.append((i,s,min(e,length)))
            if e>length+1e-8:intervals.append((i,0.,e-length))
        start=end
    cuts=sorted(set([0.,float(length)]+[v for _,s,e in intervals for v in (s,e)]))
    segments=[]
    for s,e in zip(cuts,cuts[1:]):
        if e-s<1e-7:continue
        mid=(s+e)/2; players=sorted({i for i,a,b in intervals if a<=mid<b})
        if len(players)!=5:raise ValueError('FIVE_ON_COURT_VIOLATION')
        segments.append({'start':s,'end':e,'player_indices':players})
    return segments


def sample_team(forecasts: Sequence[dict], *, seed: int, n: int = 1,
                ot_probability: float, ot_continuation: float,
                unusual_rotation_probability: float = 0.):
    """One team in a shared game scenario. For two teams supply identical seed
    and OT parameters: OT is drawn first from an independent game RNG stream.
    Reject underfilled sampled rosters explicitly; never force uncertain players
    active. Returned invalid scenarios remain in the attempted denominator.
    Projection changes marginal laws: these team scenarios need separate validation.
    """
    if not forecasts or n < 1 or not 0 <= ot_probability < 1 or not 0 < ot_continuation < 1 or not 0 <= unusual_rotation_probability <= 1:
        raise ValueError('INVALID_SCENARIO_CONFIGURATION')
    ids=[f['player_id'] for f in forecasts]
    if len(set(ids)) != len(ids):raise ValueError('DUPLICATE_PLAYER')
    if len({(f['game_id'],f['team_id']) for f in forecasts}) != 1:
        raise ValueError('MIXED_TEAM_GAME')
    if any(f['participation_probability'] is None or f['active_roster_eligible'] is None for f in forecasts):
        raise ValueError('UNVERIFIED_ROSTER_OR_PARTICIPATION')
    for f in forecasts:
        probability=f['participation_probability']
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('INVALID_PARTICIPATION_PROBABILITY')
        if not isinstance(f['active_roster_eligible'], bool):
            raise ValueError('UNVERIFIED_ROSTER_OR_PARTICIPATION')
        if not f['active_roster_eligible'] and probability != 0:
            raise ValueError('ROSTER_PARTICIPATION_CONFLICT')
    team=forecasts[0]['team_id']; game=forecasts[0]['game_id']
    team_seed=int.from_bytes(hashlib.sha256(f'{seed}/{game}/{team}'.encode()).digest()[:8],'little')
    rng=np.random.default_rng(team_seed)
    game_seed=int.from_bytes(hashlib.sha256(f'{seed}/{game}'.encode()).digest()[:8],'little')
    grng=np.random.default_rng(game_seed)
    result=[]
    for j in range(n):
        ot=int(grng.geometric(1-ot_continuation)) if grng.random()<ot_probability else 0
        length=48+5*ot; total=5*length
        active=np.array([f['active_roster_eligible'] and rng.random()<f['participation_probability'] for f in forecasts])
        scenario={'scenario_id':f'{game}/{team}/{seed}/{j}', 'game_scenario_id':f'{game}/{seed}/{j}',
                  'seed':seed,'overtime_periods':ot,'game_length':length,'player_ids':ids}
        if active.sum()<5:
            result.append({**scenario,'valid':False,'reason':'FEWER_THAN_FIVE_PARTICIPANTS'});continue
        desired=np.array([MinuteLaw(**f['distribution']).sample_at_length(rng,length) if a else 0. for f,a in zip(forecasts,active)])
        unusual=rng.random()<unusual_rotation_probability
        if unusual:desired = np.minimum(length, desired*rng.lognormal(0,.5,len(desired)))
        caps=active.astype(float)*length
        allocation=capped_allocation(desired,caps,total)
        segments=lineup_segments(allocation,length)
        result.append({**scenario,'valid':True,'rotation_state':'unusual' if unusual else 'normal',
            'minutes':allocation.tolist(),'independent_minutes':desired.tolist(),
            'independent_team_total':float(desired.sum()),'team_total':float(allocation.sum()),
            'lineup_segments':segments})
    return result


def freeze_shadow(path: str | Path, forecasts: Sequence[dict]):
    """Exclusive creation: reruns cannot overwrite a previous shadow freeze."""
    payload=''.join(json.dumps(f,sort_keys=True,allow_nan=False)+'\n' for f in forecasts)
    with Path(path).open('x') as handle:handle.write(payload)
    return hashlib.sha256(payload.encode()).hexdigest()
