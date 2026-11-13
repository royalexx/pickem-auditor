"""Collector-owned usage histories. Research packets contain references, not totals."""
import hashlib
import json
import math
import os
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
VERSION='usage-history-v2'

def source_stat(stat):
    """Share the pipeline's market identity at collector/cache boundaries."""
    from pickem_math import _optional_stat
    return _optional_stat(stat)

def local_day(value):
    if not isinstance(value,str):raise ValueError('dated source observation required')
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if 'T' in value or ' ' in value:
        if parsed.tzinfo is None:raise ValueError('source timestamp needs timezone')
        return parsed.astimezone(ZoneInfo('America/Toronto')).date()
    return parsed.date()

def validate_rows(rows,candidate,now,*,workload_required=False):
    if not isinstance(rows,list):raise ValueError('history must be a list')
    seen=set();result=[]
    cutoff=min(now.astimezone(ZoneInfo('America/Toronto')).date(),local_day(candidate['game_date']))
    for row in rows:
        ident=row['id']
        if not isinstance(ident,str) or not ident.strip() or ident!=ident.strip() or ident in seen:
            raise ValueError('duplicate/unknown usage observation')
        seen.add(ident);day=local_day(row['date'])
        if day>=cutoff:raise ValueError('usage observation must precede the game and evaluation day')
        value,volume=row['value'],row.get('workload')
        signed_yards=candidate.get('sport')=='NFL' and candidate.get('stat') in ('passing yards','receiving yards','rushing yards')
        if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or (value<0 and not signed_yards):
            raise ValueError('invalid source production')
        if volume is None and not workload_required:pass
        elif isinstance(volume,bool) or not isinstance(volume,(float,int)) or not math.isfinite(volume) or volume<0:
            raise ValueError('invalid source workload')
        if volume==0 and value:raise ValueError('production without workload')
        result.append((day,ident,value,volume))
    return sorted(result)

_data_root=ContextVar('pickem_data_root',default=None)
def directory():return Path(_data_root.get() or os.environ.get('PICKEM_DATA_DIR',ROOT/'data'))/'usage'
@contextmanager
def using_directory(root):
    token=_data_root.set(Path(root))
    try:yield
    finally:_data_root.reset(token)

def key(sport,player_id,stat,game_date):
    return hashlib.sha256(json.dumps([sport,str(player_id),source_stat(stat),game_date]).encode()).hexdigest()


def _tackle_observations_three_component(observations):
    if not isinstance(observations, list) or not observations:
        return False
    fields = ("def_tackles_solo", "def_tackles_with_assist", "def_tackle_assists")
    for item in observations:
        if not isinstance(item, dict):
            return False
        components = item.get("tackle_components")
        if isinstance(components, dict):
            if all(field in components for field in fields):
                continue
            return False
        if not all(field in item for field in fields):
            return False
    return True

def persist(rows,root):
    root=Path(root)/'usage';root.mkdir(parents=True,exist_ok=True)
    for row in rows:
        observations=row.get('usage_observations')
        if not observations or not row.get('player_id'):continue
        ident=key(row['sport'],row['player_id'],row['stat'],row['game_date'])
        data={k:row.get(k) for k in ('sport','player_id','stat','game_date','source_url','retrieved_at','team')}
        data['stat']=source_stat(data['stat'])
        data.update(version=VERSION,observations=observations,prior_observations=row.get('prior_usage_observations',[]))
        if row.get('sport') == 'NFL' and source_stat(row.get('stat')) == 'tackles + assists':
            from nfl_stat_definitions import TACKLE_DERIVED_CACHE_SCHEMA, VERSION as NFL_TACKLE_STAT_VERSION
            if row.get('source_stat_definition_version') != NFL_TACKLE_STAT_VERSION:
                if not _tackle_observations_three_component(observations):
                    raise ValueError('tackle_usage_cache_missing_three_component_evidence')
            data['tackle_derived_cache_schema'] = TACKLE_DERIVED_CACHE_SCHEMA
            data['source_stat_definition_version'] = NFL_TACKLE_STAT_VERSION
        encoded=json.dumps(data,sort_keys=True,allow_nan=False)
        digest=hashlib.sha256(encoded.encode()).hexdigest()
        snapshots=root/'snapshots';snapshots.mkdir(exist_ok=True)
        snapshot=snapshots/(digest+'.json')
        if not snapshot.exists():snapshot.write_text(encoded)
        data['content_sha256']=digest
        path=root/(ident+'.json');tmp=path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data,sort_keys=True));tmp.replace(path)
        row['historical_usage']=ident

def load(candidate,now):
    ident=key(candidate['sport'],candidate['player_id'],candidate['stat'],candidate['game_date'])
    packet=candidate['scouting']
    if packet.get('historical_usage')!=ident:raise ValueError('usage reference identity mismatch')
    data=json.loads((directory()/(ident+'.json')).read_text())
    if (candidate.get('sport') == 'NFL'
            and source_stat(candidate.get('stat')) == 'tackles + assists'):
        from nfl_stat_definitions import STALE_TACKLE_CACHE_SCHEMAS, TACKLE_DERIVED_CACHE_SCHEMA
        schema = data.get('tackle_derived_cache_schema')
        if schema is None or schema in STALE_TACKLE_CACHE_SCHEMAS:
            raise ValueError('stale_tackle_usage_cache_requires_rebuild')
        if schema != TACKLE_DERIVED_CACHE_SCHEMA:
            raise ValueError('unsupported_tackle_usage_cache_schema')
    if not isinstance(data,dict):raise ValueError('collector history must be an object')
    digest=data.pop('content_sha256',None)
    if digest!=hashlib.sha256(json.dumps(data,sort_keys=True,allow_nan=False).encode()).hexdigest():
        raise ValueError('collector history checksum mismatch')
    data['content_sha256']=digest
    if (data.get('version')!=VERSION or str(data.get('player_id'))!=str(candidate['player_id']) or
        source_stat(data.get('stat'))!=source_stat(candidate.get('stat')) or
        any(data.get(k)!=candidate.get(k) for k in ('sport','game_date','team'))):
        raise ValueError('collector history identity mismatch')
    stamp=datetime.fromisoformat(data['retrieved_at'].replace('Z','+00:00'))
    # Completed-game history is not a live injury report. A morning collection
    # remains usable through the same Toronto day; prices/status keep their own
    # stricter freshness gates. Never roll an old snapshot into a new day.
    if (stamp.tzinfo is None or not 0 <= (now-stamp).total_seconds() <= 86400 or
            stamp.astimezone(ZoneInfo('America/Toronto')).date() !=
            now.astimezone(ZoneInfo('America/Toronto')).date()):
        raise ValueError('collector history must be collected on the evaluation day')
    if candidate['sport']=='NFL':
        season=now.year-(now.month<3)
        dbpath=directory().parent/'season'/f'nfl_{season}.sqlite3'
        if dbpath.exists():
            dates={}
            with sqlite3.connect(f'file:{dbpath}?mode=ro',uri=True) as db:
                for gid,payload in db.execute('SELECT game_id,payload FROM plays WHERE season=? GROUP BY game_id',(season,)):
                    p=json.loads(payload)
                    for team in (p.get('posteam'),p.get('defteam')):
                        dates[(str(p.get('week')),team)]=p.get('game_date')
                    dates[(gid,candidate['team'])]=p.get('game_date')
            for observation in data['observations']:
                when=observation['date']
                if isinstance(when,(int,float)) or (isinstance(when,str) and when.isdigit()):
                    observation['date']=dates.get((format(float(when),'g'),candidate['team']),when)
    return data

def verify_a(candidate,now):
    from fetch_slate import summarize_log,SHORT_SEASON_GAMES
    data=load(candidate,now)
    validate_rows(data['observations'],candidate,now)
    validate_rows(data.get('prior_observations',[]),candidate,now)
    def games(rows):return [dict(tie=r['id'],when=r['date'],value=r['value'],workload=r.get('workload')) for r in rows]
    summary=summarize_log(games(data['observations']),candidate['stat'],games(data.get('prior_observations',[])))
    expected={key:summary.get(source) for key,source in {
        'baseline_mean':'baseline_window_mean','baseline_n':'baseline_n','recent_mean':'recent_mean',
        'recent_n':'recent_n','season_n':'season_n','prior_mean':'prior_season_mean','prior_n':'prior_n',
        'sd':'sd','var_ratio':'var_ratio'}.items()}
    for key in ('baseline_mean','baseline_n','recent_mean','recent_n','season_n'):
        if candidate.get(key)!=expected.get(key):return False
    ids=dict(summary.get('observation_ids') or {})
    if not (summary['season_n']<SHORT_SEASON_GAMES and summary.get('prior_n')):ids['prior']=[]
    if candidate.get('observation_ids')!=ids:return False
    if candidate.get('dist')!=summary.get('suggested_dist'):return False
    use_prior=summary['season_n']<SHORT_SEASON_GAMES and bool(summary.get('prior_n'))
    for key in ('prior_mean','prior_n'):
        if candidate.get(key)!=(expected.get(key) if use_prior else None):return False
    for key in ('prior_mean','prior_n','sd','var_ratio'):
        if key in candidate and candidate[key]!=expected.get(key):return False
    if candidate.get('role_change'):return False
    return True

def project(candidate,now):
    """Independent, uncertainty-aware scouting from validated usage histories.

    A 3-9 game current-season sample may borrow <=20 verified same-role
    prior-season games, at 40% observation weight. This is a constrained
    early-season bridge, not invented current-season participation.
    """
    import pickem_math as pm
    data=load(candidate,now)
    clean=validate_rows(data['observations'],candidate,now,workload_required=True)
    n=len(clean)
    prior=[];early_prior=False
    if n<10:
        ids=((candidate.get('observation_ids') or {}).get('prior') or [])
        # Missing unused prior workload must not invalidate current exposures.
        # Selected prior support still requires measured exposure on every row.
        history=validate_rows(data.get('prior_observations',[]),candidate,now)
        indexed={r[1]:r for r in history}
        authorized=(n>=3 and 10<=len(ids)<=20
                    and all(ident in indexed and indexed[ident][3] is not None for ident in ids)
                    and verify_a(candidate,now))
        if authorized:
            prior=[indexed[ident] for ident in ids]
            if set(r[1] for r in clean).intersection(ids):
                raise ValueError('prior and current observation IDs overlap')
            if max(r[0] for r in prior)>=min(r[0] for r in clean):
                raise ValueError('prior observations must precede current-season observations')
            early_prior=True
        elif n<5:
            raise ValueError('early season needs 3 current and 10 verified same-role prior observations')
    positive=[r for r in clean if r[3]>0]
    prior_positive=[r for r in prior if r[3]>0]
    if len(positive)+len(prior_positive)<5:
        raise ValueError('need five source-backed positive exposure games')
    if not early_prior and n<5:
        raise ValueError('need at least five dated usage observations')
    recent=clean[-5:]
    if not any(r[3]>0 for r in recent):
        raise ValueError('no observed current-season workload')
    prior_weight=0.4 if early_prior else 0.
    effective_n=n+prior_weight*len(prior)
    if early_prior and effective_n<10:
        raise ValueError('prior support effective sample too small')
    production=sum(r[2] for r in clean)+prior_weight*sum(r[2] for r in prior)
    exposure=sum(r[3] for r in clean)+prior_weight*sum(r[3] for r in prior)
    if exposure<=0:
        raise ValueError('zero measured exposure')
    conversion=production/exposure
    if conversion<=0:
        raise ValueError('no observed production rate')
    volume=mean(r[3] for r in recent)
    if volume<=0:
        raise ValueError('no recent observed workload')
    mu=volume*conversion
    rates=[r[2]/r[3] for r in positive+prior_positive]
    volume_se=(stdev(r[3] for r in recent)/math.sqrt(len(recent))
               if len(recent)>=2 else volume)
    rate_se=(stdev(rates)/math.sqrt(len(rates)) if len(rates)>=2 else conversion)
    mean_se=max(mu/math.sqrt(effective_n),conversion*volume_se+volume*rate_se)
    if early_prior:mean_se*=1.25  # Added drift uncertainty; never claim extra games.
    values=[r[2] for r in clean+prior]
    if len(values)<2:raise ValueError('insufficient distribution observations')
    variance=stdev(values)**2
    dist='normal' if candidate['stat'] in ('points','pra','pr','pa','ra',
        'passing yards','receiving yards','rushing yards','goalie saves','saves') else 'poisson'
    sd=max(math.sqrt(variance),1e-6) if dist=='normal' else None
    vr=None
    if dist=='poisson' and variance/max(mean(values),1e-9)>1.10:
        dist='negbin';vr=min(3.,variance/mean(values))
    q,push=pm.side_probs(dist,mu,candidate['line'],candidate['side'],sd,vr)
    over=q if candidate['side']=='over' else 1-q-push
    under=q if candidate['side']=='under' else 1-q-push
    process_variance=sd**2 if dist=='normal' else mu*(vr or 1)
    robust=pm._robust_win(dist,mu,candidate['line'],sd,vr,
        process_variance/mean_se**2,candidate['side'],over,under,push)
    reasons=[]
    if (not early_prior and len(positive)<10) or (early_prior and effective_n<10):
        reasons.append('thin_usage_history')
    if dist=='normal' and pm.NormalDist(mu,math.hypot(sd,mean_se)).cdf(-.5)>pm.NORMAL_NEGATIVE_MASS:
        reasons.append('normal_predictive_negative_mass')
    return dict(mean_b=mu,q_win_b=robust['q_win_robust'],q_push_b=robust['q_push_robust'],se_b=mean_se,
        abstain=False,abstain_reason=None,reliable=not reasons,version='scouting-v7',calibrated=False,
        history_through=clean[-1][0].isoformat(),baseline_origin='collector_observations',
        quality=dict(reasons=reasons,n=n,weighted_prior_n=prior_weight*len(prior),
            effective_n=effective_n,early_season_prior_supported=early_prior,
            data_sufficient=not reasons,numeric_provenance_complete=True),
        uncertainty='source_verified_prior_drift_and_rate_sampling' if early_prior else 'historical_usage_and_rate_sampling_approximation',
        terms=dict(opportunities=volume,conversion=conversion,observation_ids=[r[1] for r in clean],
            prior_observation_ids=[r[1] for r in prior],prior_weight=prior_weight,
            history_reference=candidate['scouting']['historical_usage'],
            history_digest=data.get('content_sha256'),
            recent_observation_ids=[r[1] for r in recent],
            observed_production={r['id']:r['value'] for r in data['observations']+data.get('prior_observations',[])},
            source_url=data.get('source_url'),effect_ledger=[],
            distribution=dict(dist=dist,sd=sd,var_ratio=vr,mean_se=mean_se),
            units='NBA minutes; NHL ice minutes; NFL snaps/plays as supplied by collector'))
