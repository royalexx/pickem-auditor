"""Native P1 1.0.0 export inspection, without source admission or fitting.

This independently rechecks raw bytes/ancestors and derived fields. It keeps
BLOCKED at the first unavailable evidence boundary. Internal consistency is
never an authentication certificate, and no training row is admitted here.
"""
import base64
import copy
import hashlib
import json
import math
import re
from fractions import Fraction
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

from .model import SFError, utc, canonical, digest, sha, STATS
from .source_accounting import validate_count_feasibility
from v2.nba_architecture.v2_contracts import validate_pregame, verify

VERSION='nba-S-P1-native-inspection/1.0.0'
P1_VERSION='nba-p1-native-handoff/1.0.0'
EVIDENCE_VERSION='nba-p1-prior-game-evidence/1.0.0'
MISSING=['INDEPENDENT_SOURCE_ADMISSION','ORIGINAL_OR_FIRST_DEFENSIBLE_AVAILABILITY',
         'SOURCE_BOUND_OUTCOME_RELEASE_CLOCK','DATED_ROLE_EVIDENCE']
STAT_KEYS={'points':'points','rebounds':'reboundsTotal','assists':'assists',
 'threes':'threePointersMade','fgm':'fieldGoalsMade','fga':'fieldGoalsAttempted',
 'fg3a':'threePointersAttempted','ftm':'freeThrowsMade','fta':'freeThrowsAttempted',
 'oreb':'reboundsOffensive','dreb':'reboundsDefensive','steals':'steals',
 'blocks':'blocks','turnovers':'turnovers','personal_fouls':'foulsPersonal'}


def require(condition, code):
    if not condition:raise SFError(code)


def _seconds(value):
    require(isinstance(value,str),'P1_NATIVE_MINUTE_FORMAT')
    m=re.fullmatch(r'PT(\d+)M(\d+(?:\.\d+)?)S',value)
    require(bool(m) and Fraction(m[2])<60,'P1_NATIVE_MINUTE_FORMAT')
    return Fraction(m[1])*60+Fraction(m[2])


def _pairs(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'P1_NATIVE_DUPLICATE_JSON_KEY');result[key]=value
    return result


def _chain(node):
    require(isinstance(node,dict) and set(node)=={'capture','raw_base64','prior'} and
            isinstance(node['prior'],list),'P1_NATIVE_EVIDENCE_FIELDS')
    previous=None;last_game=None;raws=[]
    for n,item in enumerate(node['prior']+[node],1):
        require(isinstance(item,dict) and set(item)=={'capture','raw_base64','prior'} and
                (item is node or item['prior']==[]),'P1_NATIVE_ANCESTRY_FIELDS')
        c=item['capture']
        require(isinstance(c,dict) and set(c)=={'schema','url','raw_sha256','retrieved_at','revision','supersedes_receipt_sha256'} and c['schema']==EVIDENCE_VERSION,'P1_NATIVE_CAPTURE_FIELDS')
        try:raw=base64.b64decode(item['raw_base64'],validate=True)
        except (ValueError,TypeError) as exc:raise SFError('P1_NATIVE_BASE64') from exc
        require(hashlib.sha256(raw).hexdigest()==sha(c['raw_sha256']),'P1_NATIVE_RAW_SHA_MISMATCH')
        require(type(c['revision']) is int and c['revision']==n and
                c['supersedes_receipt_sha256']==(digest(canonical(previous)) if previous else None),
                'P1_NATIVE_REVISION_ANCESTRY')
        u=urlsplit(c['url'])
        require(u.scheme=='https' and u.netloc=='cdn.nba.com' and not u.query and not u.fragment and
                bool(re.fullmatch(r'/static/json/liveData/boxscore/boxscore_[0-9]{10}\.json',u.path)),
                'P1_NATIVE_PROVIDER_IDENTITY')
        try:game=json.loads(raw,object_pairs_hook=_pairs,parse_constant=lambda x: (_ for _ in ()).throw(SFError('P1_NATIVE_NONFINITE_JSON')))['game']
        except (ValueError,KeyError,TypeError) as exc:raise SFError('P1_NATIVE_RAW_JSON') from exc
        require(u.path.endswith('/boxscore_'+str(game.get('gameId'))+'.json'),'P1_NATIVE_GAME_IDENTITY')
        require(utc(c['retrieved_at'])>utc(game['gameTimeUTC']),'P1_NATIVE_CAPTURE_CHRONOLOGY')
        if previous:
            require(c['url']==previous['url'] and utc(c['retrieved_at'])>utc(previous['retrieved_at']),
                    'P1_NATIVE_REVISION_CHRONOLOGY')
            require(game['gameId']==last_game['gameId'] and all(game[k]['teamId']==last_game[k]['teamId'] for k in ('homeTeam','awayTeam')),'P1_NATIVE_REVISION_IDENTITY')
        previous=c;last_game=game;raws.append(dict(raw_sha256=c['raw_sha256'],receipt_sha256=digest(canonical(c)),revision=n,bytes=len(raw)))
    return last_game,raws


def inspect_p1_export(export, *, pregame, stat):
    """Return a lossless blocked inspection or reject inconsistent transport.

    No source flag, role string, matching digest or synthetic frequency can
    create a real admission. P1 1.0.0 supplies no independent admission path.
    """
    validate_pregame(pregame);verify(pregame)
    require(stat in STATS,'P1_NATIVE_STAT')
    keys={'schema','kind','profile','source_profile','admission_status','missing_requirements',
          'evidence_bundle','exposure','game_start_at','clocks','role','role_evidence',
          'uncertainty','candidate_denominator'}
    require(isinstance(export,dict) and set(export)==keys and export['schema']==P1_VERSION and export['kind']=='prior_game_export','P1_NATIVE_EXPORT_SCHEMA')
    require(export['profile'] in ('synthetic_engineering','unadmitted_source_reconstruction') and export['source_profile']==export['profile'],'P1_NATIVE_SOURCE_PROFILE')
    require(export['admission_status']=='BLOCKED' and export['missing_requirements']==MISSING and export['role'] is None and export['role_evidence'] is None,'P1_NATIVE_UNSUPPORTED_ADMISSION_CLAIM')
    require(export['candidate_denominator']==dict(attempted=1,admitted=0,quarantined=1) and all(type(v) is int for v in export['candidate_denominator'].values()),'P1_NATIVE_DENOMINATOR')
    game,raws=_chain(export['evidence_bundle']);e=export['exposure']
    require(isinstance(e,dict) and set(e)=={'schema','game_id','game_date','overtime_periods','duration_minutes','source_status','raw_sha256','receipt_sha256','retrieved_at','original_pregame_available_at','certification','player_id','team_id','opponent_id','participation','displayed_minutes','exact_minutes','accounting_status','stats'},'P1_NATIVE_EXPOSURE_FIELDS')
    require(e.get('game_id')=='nba:game:'+str(game['gameId']) and e['game_id']!=pregame['game_id'],'P1_NATIVE_TARGET_OR_GAME_IDENTITY')
    require(export['game_start_at']==game['gameTimeUTC'] and utc(export['game_start_at'])<utc(pregame['training_cutoff_at']),'P1_NATIVE_TRAINING_GAME_CUTOFF')
    require(game.get('gameStatus')==3 and type(game.get('period')) is int and game['period']>=4 and _seconds(game.get('gameClock'))==0,'P1_NATIVE_COMPLETED_GAME_REQUIRED')
    ot=game['period']-4;cap=48+5*ot
    require(e.get('schema')==EVIDENCE_VERSION and type(e.get('overtime_periods')) is int and e['overtime_periods']==ot and type(e.get('duration_minutes')) is int and e['duration_minutes']==cap,'P1_NATIVE_DURATION_MISMATCH')
    day=utc(game['gameTimeUTC']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
    require(e.get('game_date')==day,'P1_NATIVE_GAME_DATE')
    require(e.get('raw_sha256')==raws[-1]['raw_sha256'] and e.get('receipt_sha256')==raws[-1]['receipt_sha256'],'P1_NATIVE_HASH_DOMAIN_OR_RECEIPT')
    require(e.get('source_status')=='OFFICIAL_BYTES_CONSISTENT_AUTHENTICITY_REVIEW_REQUIRED' and e.get('certification')=='HISTORICAL_RECONSTRUCTION_UNCERTIFIED' and e.get('original_pregame_available_at') is None,'P1_NATIVE_UNSUPPORTED_ADMISSION_CLAIM')
    people=[]
    for teamkey in ('homeTeam','awayTeam'):
        team=game[teamkey]
        require(type(team['teamId']) is int and team['teamId']>0,'P1_NATIVE_TEAM_IDENTITY')
        for player in team.get('players',[]):
            if 'nba:player:'+str(player.get('personId'))==e.get('player_id'):people.append((team,player))
    require(len(people)==1 and e.get('team_id')=='nba:team:'+str(people[0][0]['teamId']),'P1_NATIVE_PLAYER_TEAM_IDENTITY')
    opponent=next(game[k] for k in ('homeTeam','awayTeam') if game[k] is not people[0][0])
    require(e.get('opponent_id')=='nba:team:'+str(opponent['teamId']) and e['team_id']!=e['opponent_id'],'P1_NATIVE_OPPONENT_IDENTITY')
    player=people[0][1];statistics=player.get('statistics',{})
    normalized={k:statistics[v] for k,v in STAT_KEYS.items() if v in statistics}
    require(all(type(v) is int and v>=0 for v in normalized.values()),'P1_NATIVE_RAW_STAT_TYPE_OR_SUPPORT')
    for combo,parts in {'pr':('points','rebounds'),'pa':('points','assists'),'ra':('rebounds','assists'),'pra':('points','rebounds','assists')}.items():
        if all(k in normalized for k in parts):normalized[combo]=sum(normalized[k] for k in parts)
    require(isinstance(e.get('stats'),dict) and all(k in normalized and type(v) is int and v>=0 and normalized[k]==v for k,v in e['stats'].items()),'P1_NATIVE_STAT_MISMATCH')
    validate_count_feasibility(normalized)
    participation=e.get('participation')
    require(participation in ('played','dnp','unknown'),'P1_NATIVE_PARTICIPATION')
    if participation=='played':
        exact_source=_seconds(statistics.get('minutes'))/60
        require(exact_source!=0 or not any(normalized.values()),'P1_NATIVE_ZERO_MINUTE_CREDIT_UNRESOLVED')
        exact=float(exact_source);display=e.get('displayed_minutes')
        require(player.get('played')=='1' and type(display) in (int,float) and math.isfinite(display) and 0<=display<=cap and 0<=exact_source<=cap,'P1_NATIVE_EXPOSURE_PHYSICS')
        require(type(e.get('exact_minutes')) in (int,float) and e['exact_minutes']==exact and abs(Fraction(str(display))-exact_source)<=Fraction(1,2),'P1_NATIVE_EXACT_MINUTES_MISMATCH')
        rounded=display==0 and any(normalized.values())
        require(not rounded or 0<exact_source<Fraction(1,2),'P1_NATIVE_ZERO_MINUTE_CREDIT_UNRESOLVED')
        require(e.get('accounting_status')==('ADJUDICATED_ROUNDED_SUBMINUTE' if rounded else 'OFFICIAL_BOX_RECONCILED'),'P1_NATIVE_ACCOUNTING_STATUS')
        require(stat in e['stats'],'P1_NATIVE_STAT_MISSING')
    else:
        require(e.get('exact_minutes') is None and e.get('accounting_status')=='NONPARTICIPATION_OR_UNKNOWN','P1_NATIVE_DNP_IS_NOT_ZERO')
        require(e.get('displayed_minutes') is None and e['stats']=={},'P1_NATIVE_NONPLAYED_ROW_CREDIT_OR_MINUTES')
        require(not any(normalized.values()),'P1_NATIVE_NONPLAYED_RAW_POSITIVE_CREDIT')
        raw_minutes=statistics.get('minutes')
        require(raw_minutes is None or _seconds(raw_minutes)==0,'P1_NATIVE_NONPLAYED_RAW_EXPOSURE')
        require(participation!='dnp' or player.get('played')=='0','P1_NATIVE_DNP_CONFLICT')
        require(participation!='unknown' or player.get('played') in (None,'unknown'),'P1_NATIVE_UNKNOWN_CONFLICT')
    clocks=export['clocks'];retrieved=export['evidence_bundle']['capture']['retrieved_at']
    require(isinstance(clocks,dict) and set(clocks)=={'provider_published_at','first_defensible_available_at','collector_observed_at','retrieved_at','ingested_at','outcome_available_at'},'P1_NATIVE_CLOCK_FIELDS')
    require(all(clocks[k] is None for k in ('provider_published_at','first_defensible_available_at','collector_observed_at','outcome_available_at')),'P1_NATIVE_UNSUPPORTED_AVAILABILITY_CLAIM')
    require(clocks['retrieved_at']==retrieved==e.get('retrieved_at') and utc(clocks['ingested_at'])>=utc(retrieved),'P1_NATIVE_RETRIEVAL_INGESTION')
    require(export['uncertainty']==dict(participation=participation,source_admission='UNKNOWN',role='UNKNOWN'),'P1_NATIVE_UNCERTAINTY_MISMATCH')
    reasons=list(MISSING)
    if utc(retrieved)>utc(pregame['training_cutoff_at']):reasons.append('RETRIEVAL_AFTER_MODEL_TRAINING_CUTOFF')
    if utc(clocks['ingested_at'])>utc(pregame['input_freeze_at']):reasons.append('INGESTION_AFTER_INPUT_FREEZE')
    return dict(schema=VERSION,status='BLOCKED',reason='P1_INDEPENDENT_SOURCE_ADMISSION_REQUIRED',
        source_snapshot_sha256=pregame['content_hash'],source_profile=export['source_profile'],
        original_vs_reconstructed_or_synthetic=export['profile'],source_admission='UNAVAILABLE',
        missing_requirements=reasons,denominator=dict(attempted=1,structurally_checked=1,admitted=0,quarantined=1),
        training_rows=[],raw_sources=raws,preserved_export=copy.deepcopy(export),
        synthetic_compatibility_only=export['profile']=='synthetic_engineering')
