"""Immutable, model-neutral NBA pregame source interface, version 1.0.0.

A hash establishes content integrity, not truth or authenticated publication time.
Callers must retain receipt bytes and supply independently trusted capture clocks.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from zoneinfo import ZoneInfo

VERSION = 'nba-pregame-feature-snapshot/1.0.0'
STATS = ('points','rebounds','assists','threes','steals','blocks','turnovers','pra','pr','pa','ra',
         'fgm','fga','fg3a','ftm','fta','oreb','dreb','personal_fouls')
FIELDS = {
 'schedule': {'game_id','home_team_id','away_team_id','event_start_at','venue','status'},
 'player_game': {'game_id','player_id','team_id','opponent_id','game_date','minutes','participation','starter','stats'},
 'team_game': {'game_id','team_id','opponent_id','game_date','possessions','pace_per_48','stats','opponent_stats'},
 'roster': {'game_id','player_id','team_id','status','uncertainty'},
 'availability': {'game_id','player_id','team_id','status','uncertainty','role','detail'},
 'contract': {'contract_id','quote_id','game_id','player_id','team_id','stat','period','line','quoted_at','book','prices','payout_terms'},
 'game_market': {'game_id','team_id','kind','line','quoted_at','book','period'},
}
REQUIRED = {k: v for k,v in FIELDS.items()}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def instant(value):
    if not isinstance(value,str) or 'T' not in value:
        raise ValueError('INVALID_TIMESTAMP')
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('NAIVE_TIMESTAMP')
    return dt.astimezone(timezone.utc)


def utc(value):
    return instant(value).isoformat(timespec='microseconds').replace('+00:00','Z')


def number(value, *, nonnegative=True):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (nonnegative and value<0):
        raise ValueError('INVALID_NUMBER')


def identity(value,kind):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z][a-z0-9_]*:'+kind+r':[A-Za-z0-9_.-]+',value):
        raise ValueError('INVALID_NAMESPACED_ID:'+kind)


@dataclass(frozen=True)
class Receipt:
    source: str
    raw_sha256: str
    observed_at: str
    source_available_at: str
    origin: str
    receipt_id: str

    @classmethod
    def capture(cls, raw, *, source, observed_at, origin, source_available_at=None):
        if origin not in ('original_capture','retrospective_retrieval','fixture') or not source:
            raise ValueError('INVALID_SOURCE_ORIGIN')
        # Never let a claimed publication time erase actual first observation.
        observed=utc(observed_at)
        available=utc(source_available_at or observed)
        available=max(available,observed)
        data=dict(source=source,raw_sha256=digest(raw),observed_at=observed,source_available_at=available,origin=origin)
        return cls(**data,receipt_id=digest(canonical(data).encode()))

    def verify(self,raw):
        if digest(raw)!=self.raw_sha256:raise ValueError('SOURCE_HASH_MISMATCH')
        data=asdict(self);data.pop('receipt_id')
        if digest(canonical(data).encode())!=self.receipt_id:raise ValueError('RECEIPT_HASH_MISMATCH')
        if utc(self.source_available_at)<utc(self.observed_at):raise ValueError('SOURCE_CLOCK_MANIPULATION')


@dataclass(frozen=True)
class Record:
    kind: str
    receipt_id: str
    payload: str
    revision: int
    supersedes: str | None
    record_id: str

    @property
    def data(self):return json.loads(self.payload)

    @classmethod
    def make(cls,kind,receipt,data,*,revision=1,supersedes=None):
        if kind not in FIELDS or set(data)!=REQUIRED[kind]:raise ValueError('INVALID_RECORD_FIELDS:'+kind)
        if type(revision)!=int or revision<1:raise ValueError('INVALID_REVISION')
        for key in ('game_id','player_id','team_id','opponent_id','home_team_id','away_team_id'):
            if key in data:identity(data[key], 'game' if key=='game_id' else 'player' if key=='player_id' else 'team')
        if 'opponent_id' in data and data['team_id']==data['opponent_id']:raise ValueError('TEAM_COLLISION')
        if kind=='schedule':
            utc(data['event_start_at'])
            if data['home_team_id']==data['away_team_id']:raise ValueError('TEAM_COLLISION')
            if data['status'] not in ('scheduled','postponed','cancelled','live','final'):raise ValueError('INVALID_GAME_STATUS')
        if kind in ('player_game','team_game'):
            date.fromisoformat(data['game_date'])
            for field in ('stats','opponent_stats'):
                if field not in data:continue
                if not isinstance(data[field],dict) or set(data[field])-set(STATS):raise ValueError('INVALID_STATS')
                for value in data[field].values():
                    if value is not None:
                        number(value)
                        if not float(value).is_integer():raise ValueError('FRACTIONAL_BOX_COUNT')
            if kind=='player_game':
                if data['participation'] not in ('played','dnp','unknown'):raise ValueError('INVALID_PARTICIPATION')
                if data['starter'] is not None and type(data['starter'])!=bool:raise ValueError('INVALID_STARTER')
                if data['participation']=='played':number(data['minutes'])
                elif data['minutes'] is not None or data['stats']:raise ValueError('DNP_IS_NOT_ZERO')
            else:
                for field in ('possessions','pace_per_48'):
                    if data[field] is not None:number(data[field])
        if kind in ('roster','availability'):
            if data['uncertainty'] not in ('confirmed','reported','uncertain','unknown'):raise ValueError('INVALID_UNCERTAINTY')
            if not isinstance(data['status'],str) or not data['status']:raise ValueError('INVALID_STATUS')
        if kind in ('contract','game_market'):
            number(data['line'],nonnegative=kind=='contract');utc(data['quoted_at'])
            if not data['book'] or not data['period']:raise ValueError('MISSING_MARKET_IDENTITY')
            if kind=='contract':
                if data['stat'] not in STATS[:11] or not data['contract_id'] or not data['quote_id']:raise ValueError('UNSUPPORTED_CONTRACT')
                if data['prices'] is not None:
                    if set(data['prices'])!={'over','under'}:raise ValueError('INCOMPATIBLE_PRICES')
                    for v in data['prices'].values():
                        number(v)
                        if v<=1:raise ValueError('PRICES_MUST_BE_DECIMAL')
            elif data['kind'] not in ('spread','total','team_total'):raise ValueError('UNSUPPORTED_GAME_MARKET')
        payload=canonical(data)
        body=dict(kind=kind,receipt_id=receipt.receipt_id,payload=payload,revision=revision,supersedes=supersedes)
        return cls(**body,record_id=digest(canonical(body).encode()))


def distribution(values):
    if not values:return dict(n=0,values=[],mean=None,median=None,std_population=None,min=None,max=None)
    return dict(n=len(values),values=values,mean=statistics.mean(values),median=statistics.median(values),
                std_population=statistics.pstdev(values),min=min(values),max=max(values))


@dataclass(frozen=True)
class NBAPregameFeatureSnapshot:
    payload: str
    content_hash: str

    def to_dict(self):return {**json.loads(self.payload),'content_hash':self.content_hash}
    def to_json(self):return canonical(self.to_dict())+'\n'

    def require_usable(self, *, required_player_features=()):
        data=self.to_dict()
        if data['status']=='blocked':raise ValueError('SNAPSHOT_BLOCKED:'+','.join(data['abstention_codes']))
        for player in data['players']:
            if set(required_player_features)&set(player['missing_feature_codes']):raise ValueError('REQUIRED_FEATURE_UNAVAILABLE')
        return data

    @classmethod
    def from_json(cls,raw):
        def pairs(items):
            result={}
            for k,v in items:
                if k in result:raise ValueError('DUPLICATE_JSON_KEY')
                result[k]=v
            return result
        data=json.loads(raw,object_pairs_hook=pairs)
        given=data.pop('content_hash')
        payload=canonical(data)
        if digest(payload.encode())!=given:raise ValueError('SNAPSHOT_HASH_MISMATCH')
        if data['schema_version']!=VERSION:raise ValueError('UNSUPPORTED_SCHEMA_VERSION')
        receipts=[Receipt(**r) for r in data['receipts']]
        records=[Record(**r) for r in data['input_records']]
        rebuilt=build_snapshot(game_id=data['game']['game_id'],forecast_at=data['forecast_at'],input_freeze_at=data['input_freeze_at'],
            model_training_cutoff_at=data['model_training_cutoff_at'],records=records,receipts=receipts,
            quote_max_age_seconds=data['market_context']['quote_max_age_seconds']).to_dict()
        if set(data)!=(set(rebuilt)-{'content_hash'}):raise ValueError('INVALID_SNAPSHOT_FIELDS')
        for key in ('game','players','teams','market_context','future_uncertainty','source_available_at','certification'):
            if canonical(data[key])!=canonical(rebuilt[key]):raise ValueError('SNAPSHOT_DERIVATION_MISMATCH:'+key)
        if not set(data['abstention_codes']).issuperset(rebuilt['abstention_codes']):raise ValueError('ABSTENTION_REMOVED')
        blocking=set(data['abstention_codes'])-{'RECONSTRUCTED_PROXY_HISTORY','FIXTURE_ONLY'}
        if blocking and data['status']!='blocked':raise ValueError('BLOCKED_STATUS_REMOVED')
        ledger=data['ledger']
        if ledger['attempted']!=sum(ledger[k] for k in ('accepted','rejected','duplicates','superseded')) or ledger['rejected']!=len(ledger['rejections']):raise ValueError('INVALID_LEDGER_DENOMINATOR')
        return cls(payload,given)


def record_key(r):
    d=r.data
    if r.kind=='schedule':return (r.kind,d['game_id'])
    if r.kind=='contract':return (r.kind,d['book'],d['quote_id'])
    if r.kind=='game_market':return (r.kind,d['game_id'],d['team_id'],d['kind'],d['book'],d['period'],d['quoted_at'])
    return (r.kind,d['game_id'],d.get('player_id',d.get('team_id')))


def build_snapshot(*,game_id,forecast_at,input_freeze_at,model_training_cutoff_at,records,receipts,quote_max_age_seconds=900):
    forecast,freeze,training=map(utc,(forecast_at,input_freeze_at,model_training_cutoff_at))
    if training>freeze:raise ValueError('TRAINING_AFTER_FREEZE')
    if freeze>forecast:raise ValueError('FREEZE_AFTER_FORECAST')
    if type(quote_max_age_seconds)!=int or quote_max_age_seconds<0:raise ValueError('INVALID_QUOTE_AGE_POLICY')
    receipt_map={}
    for r in receipts:
        data=asdict(r);data.pop('receipt_id')
        if not re.fullmatch(r'[0-9a-f]{64}',r.raw_sha256) or digest(canonical(data).encode())!=r.receipt_id or utc(r.source_available_at)<utc(r.observed_at):raise ValueError('RECEIPT_HASH_OR_CLOCK')
        receipt_map[r.receipt_id]=r
    ledger=dict(attempted=len(records),accepted=0,rejected=0,duplicates=0,superseded=0,rejections=[])
    codes=set(); selected={}; seen_records=set();retained_inputs={}
    def reject(r,code):
        ledger['rejected']+=1;ledger['rejections'].append(dict(record_id=r.record_id,kind=r.kind,code=code))
    for r in sorted(records,key=lambda x:(x.revision,x.record_id)):
        if r.record_id in seen_records:
            ledger['duplicates']+=1;continue
        seen_records.add(r.record_id)
        body=asdict(r);body.pop('record_id')
        if digest(canonical(body).encode())!=r.record_id:raise ValueError('RECORD_HASH_MISMATCH')
        receipt=receipt_map.get(r.receipt_id)
        if receipt is None:reject(r,'SOURCE_RECEIPT_MISSING');continue
        # Revalidate serialized records at the public boundary.
        Record.make(r.kind,receipt,r.data,revision=r.revision,supersedes=r.supersedes)
        if utc(receipt.source_available_at)>freeze or utc(receipt.observed_at)>freeze:
            reject(r,'SOURCE_AFTER_FREEZE');continue
        d=r.data
        if r.kind in ('player_game','team_game'):
            if d['game_id']==game_id:reject(r,'SAME_GAME_OUTCOME');continue
            if date.fromisoformat(d['game_date'])>=instant(freeze).date():reject(r,'FUTURE_OR_SAME_DAY_HISTORY');continue
            if date.fromisoformat(d['game_date'])>=instant(receipt.observed_at).date():reject(r,'OUTCOME_NOT_PROVEN_COMPLETED');continue
        elif d['game_id']!=game_id:reject(r,'TARGET_GAME_MISMATCH');continue
        if r.kind in ('contract','game_market'):
            quote=utc(d['quoted_at'])
            if quote>freeze or quote>receipt.observed_at:reject(r,'QUOTE_AFTER_CAPTURE_OR_FREEZE');continue
            if (instant(freeze)-instant(quote)).total_seconds()>quote_max_age_seconds:reject(r,'QUOTE_STALE');continue
        key=record_key(r)
        old=selected.get(key)
        if old:
            if old.record_id==r.record_id:ledger['duplicates']+=1;continue
            if r.supersedes!=old.record_id or r.revision<=old.revision or utc(receipt.observed_at)<utc(receipt_map[old.receipt_id].observed_at):
                reject(r,'UNLINKED_CORRECTION_OR_COLLISION');codes.add('CONFLICTING_RECORDS')
                if r.kind=='roster':codes.add('ROSTER_COLLISION')
                continue
            ledger['superseded']+=1
        elif r.supersedes is not None:
            reject(r,'CORRECTION_PARENT_MISSING');codes.add('CONFLICTING_RECORDS');continue
        selected[key]=r
        retained_inputs[r.record_id]=r
    chosen=sorted(selected.values(),key=lambda r:r.record_id)
    schedules=[r for r in chosen if r.kind=='schedule']
    if len(schedules)!=1:raise ValueError('SCHEDULE_MISSING_OR_AMBIGUOUS')
    game=schedules[0].data
    if forecast>=utc(game['event_start_at']):raise ValueError('FORECAST_NOT_PREGAME')
    if game['status']!='scheduled':codes.add('EVENT_NOT_SCHEDULED')
    teams={game['home_team_id'],game['away_team_id']}
    # Target player membership comes only from target-game roster evidence.
    rosters=[r for r in chosen if r.kind=='roster']
    players=[];contracts=[];markets=[]
    for r in rosters:
        d=r.data;pid=d['player_id'];team=d['team_id'];missing=[]
        if team not in teams:codes.add('ROSTER_TEAM_MISMATCH');continue
        history=[x for x in chosen if x.kind=='player_game' and x.data['player_id']==pid]
        history.sort(key=lambda x:(x.data['game_date'],x.data['game_id']))
        hist=[{**x.data,'record_id':x.record_id,'receipt_id':x.receipt_id} for x in history]
        played=[x for x in hist if x['participation']=='played']
        recent=played[-5:];long=played[-20:]
        evidence=[{**x.data,'record_id':x.record_id,'receipt_id':x.receipt_id} for x in chosen if x.kind=='availability' and x.data['player_id']==pid]
        if any(x['team_id']!=team for x in evidence):codes.add('AVAILABILITY_TEAM_MISMATCH')
        if not evidence:missing.append('AVAILABILITY_UNAVAILABLE')
        if d['status']!='eligible' or d['uncertainty']!='confirmed':missing.append('ELIGIBILITY_UNCERTAIN')
        if not played:missing.append('PLAYER_HISTORY_UNAVAILABLE')
        previous=hist[-1] if hist else None
        if previous and previous['team_id']!=team:missing.append('ROSTER_TRANSITION_REQUIRES_REVIEW')
        features=dict(games_played=len(played),minutes_recent=distribution([x['minutes'] for x in recent]),
            minutes_long=distribution([x['minutes'] for x in long]),recent_starts=sum(x['starter'] is True for x in recent),
            starts_observed=sum(x['starter'] is not None for x in recent),
            previous_participation=previous['participation'] if previous else None,
            previous_team_id=previous['team_id'] if previous else None,
            historical_team_change=len({x['team_id'] for x in hist})>1,
            statistics={k:{'recent':distribution([x['stats'][k] for x in recent if x['stats'].get(k) is not None]),
                           'long':distribution([x['stats'][k] for x in long if x['stats'].get(k) is not None])} for k in STATS})
        missing += ['STAT_UNAVAILABLE:'+k for k in STATS if features['statistics'][k]['long']['n']==0]
        players.append(dict(player_id=pid,team_id=team,opponent_id=next(iter(teams-{team})),home=team==game['home_team_id'],
                            roster_record_id=r.record_id,features=features,history=hist,availability=evidence,missing_feature_codes=sorted(missing)))
    if not players:codes.add('PREGAME_ROSTER_UNAVAILABLE')
    pmap={p['player_id']:p for p in players}
    if any('ELIGIBILITY_UNCERTAIN' in p['missing_feature_codes'] for p in players):codes.add('ELIGIBILITY_UNCERTAIN')
    team_vectors=[]
    for team in sorted(teams):
        hist=sorted([r for r in chosen if r.kind=='team_game' and r.data['team_id']==team],key=lambda r:(r.data['game_date'],r.data['game_id']))
        last=hist[-1].data if hist else None
        # Calendar rest only; no claim of exact recovery hours.
        rest=max(0,(instant(game['event_start_at']).astimezone(ZoneInfo('America/Toronto')).date()-date.fromisoformat(last['game_date'])).days-1) if last else None
        team_vectors.append(dict(team_id=team,opponent_id=next(iter(teams-{team})),home=team==game['home_team_id'],
            rest_days=rest,back_to_back=(rest==0) if rest is not None else None,
            history=[{**r.data,'record_id':r.record_id,'receipt_id':r.receipt_id} for r in hist],
            possessions=distribution([r.data['possessions'] for r in hist[-20:] if r.data['possessions'] is not None]),
            pace_per_48=distribution([r.data['pace_per_48'] for r in hist[-20:] if r.data['pace_per_48'] is not None]),
            offensive_profile={k:distribution([r.data['stats'][k] for r in hist[-20:] if r.data['stats'].get(k) is not None]) for k in STATS},
            defensive_profile={k:distribution([r.data['opponent_stats'][k] for r in hist[-20:] if r.data['opponent_stats'].get(k) is not None]) for k in STATS},
            missing_feature_codes=([] if hist else ['TEAM_HISTORY_UNAVAILABLE','REST_UNAVAILABLE'])+
                ([] if any(r.data['possessions'] is not None for r in hist[-20:]) else ['POSSESSIONS_UNAVAILABLE'])+
                ([] if any(r.data['pace_per_48'] is not None for r in hist[-20:]) else ['PACE_UNAVAILABLE'])))
    seen_contracts=set()
    for r in chosen:
        d=r.data
        if r.kind=='contract':
            semantic=(d['book'],d['contract_id'],utc(d['quoted_at']))
            if semantic in seen_contracts:reject(r,'DUPLICATE_MARKET_CONTRACT');continue
            seen_contracts.add(semantic)
            p=pmap.get(d['player_id'])
            if p is None or p['team_id']!=d['team_id']:
                reject(r,'CONTRACT_ROSTER_MISMATCH');continue
            contracts.append({**d,'record_id':r.record_id,'receipt_id':r.receipt_id})
        elif r.kind=='game_market':
            if d['team_id'] not in teams:reject(r,'MARKET_TEAM_MISMATCH');continue
            markets.append({**d,'record_id':r.record_id,'receipt_id':r.receipt_id})
    if not contracts:codes.add('ORIGINAL_CONTRACTS_UNAVAILABLE')
    if any(receipt_map[r.receipt_id].origin=='retrospective_retrieval' for r in chosen):codes.add('RECONSTRUCTED_PROXY_HISTORY')
    if any(receipt_map[r.receipt_id].origin=='fixture' for r in chosen):codes.add('FIXTURE_ONLY')
    # Accepted includes selected and superseded versions, minus contextual rejects.
    ledger['accepted']=ledger['attempted']-ledger['rejected']-ledger['duplicates']-ledger['superseded']
    ledger['rejections'].sort(key=lambda x:(x['record_id'],x['code']))
    payload=canonical(dict(schema_version=VERSION,game=game,forecast_at=forecast,input_freeze_at=freeze,
        model_training_cutoff_at=training,source_available_at=max(receipt_map[r.receipt_id].source_available_at for r in chosen if r.record_id not in {x['record_id'] for x in ledger['rejections']}),
        status='blocked' if codes-{'RECONSTRUCTED_PROXY_HISTORY','FIXTURE_ONLY'} else 'shadow_only',
        certification='not_independently_certified',players=sorted(players,key=lambda p:p['player_id']),teams=team_vectors,
        market_context=dict(original_contracts=contracts,game_markets=markets,quote_max_age_seconds=quote_max_age_seconds),
        future_uncertainty=dict(overtime='unknown_future_outcome'),abstention_codes=sorted(codes),ledger=ledger,
        receipts=[asdict(r) for r in sorted(receipt_map.values(),key=lambda r:r.receipt_id)],
        input_records=[asdict(r) for r in sorted(retained_inputs.values(),key=lambda x:x.record_id) if r.record_id not in {x['record_id'] for x in ledger['rejections']}]))
    return NBAPregameFeatureSnapshot(payload,digest(payload.encode()))


def save_snapshot(snapshot,folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(snapshot.content_hash+'.json');raw=snapshot.to_json()
    try:
        with path.open('x',encoding='utf-8') as f:f.write(raw)
    except FileExistsError:
        if path.read_text()!=raw:raise ValueError('IMMUTABLE_SNAPSHOT_CONFLICT')
    return path
