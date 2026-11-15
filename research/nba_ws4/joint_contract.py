"""Versioned WS1/WS2/WS3 boundary fixture, not a simulator or sampler."""
import hashlib
import math
from .evaluator import require, digest, time
from .metrics import threshold

VERSION='nba-joint-readiness-v1'


def seed_for(master, event_id, scenario_id, component_version):
    require(all(isinstance(v,str) and v and '|' not in v for v in (event_id,scenario_id,component_version)),'AMBIGUOUS_SEED_ID')
    require(isinstance(master,int) and not isinstance(master,bool) and master>=0,'INVALID_MASTER_SEED')
    return int.from_bytes(hashlib.sha256(f'{VERSION}|{master}|{event_id}|{scenario_id}|{component_version}'.encode()).digest()[:8],'big')


def validate_fixture(features, opportunity, outcomes):
    require(features['schema']==opportunity['schema']==outcomes['schema']==VERSION,'SCHEMA_VERSION_MISMATCH')
    for field in ('event_id','scenario_id','seed','source_manifest_sha256','input_freeze_at'):
        require(features[field]==opportunity[field]==outcomes[field],'SHARED_STATE_MISMATCH:'+field)
    require(time(features['input_freeze_at'])<time(features['event_start']),'FEATURE_FREEZE')
    require(features['market_anchor'] in ('none','explicit_separate_arm'),'COVERT_MARKET_ANCHOR')
    for obj in (features,opportunity,outcomes):
        require(len(obj['code_sha'])==40 and len(obj['artifact_sha256'])==64,'PROVENANCE_MISSING')
        require(time(obj['training_cutoff'])<=time(features['input_freeze_at']),'MODEL_CUTOFF')
    ot=opportunity['overtime_periods']; require(isinstance(ot,int) and not isinstance(ot,bool) and ot>=0,'INVALID_OVERTIME')
    game_minutes=48+5*ot
    players=opportunity['players']; require(len({p['player_id'] for p in players})==len(players),'DUPLICATE_PLAYER')
    teams=features['team_ids']; require(len(teams)==2 and len(set(teams))==2,'TWO_TEAMS_REQUIRED')
    require({p['team_id'] for p in players}==set(teams),'TEAM_IDENTITY')
    for p in players:
        require(isinstance(p['minutes'],(int,float)) and not isinstance(p['minutes'],bool) and math.isfinite(p['minutes']) and 0<=p['minutes']<=game_minutes,'INVALID_PLAYER_MINUTES')
        require(isinstance(p['active'],bool) and (p['active'] or p['minutes']==0),'DNP_EXPOSURE')
    for team in teams:
        require(abs(sum(p['minutes'] for p in players if p['team_id']==team)-5*game_minutes)<1e-8,'TEAM_MINUTE_CONSERVATION')
    stats=outcomes['players']; require({s['player_id'] for s in stats}=={p['player_id'] for p in players} and len(stats)==len(players),'PLAYER_STATE_MISMATCH')
    out=[]
    for p in players:
        s=next(s for s in stats if s['player_id']==p['player_id'])
        require(s['team_id']==p['team_id'],'OUTCOME_TEAM_MISMATCH')
        for k in ('points','rebounds','assists','threes','fgm','fga','ftm','fta'):
            require(isinstance(s[k],int) and not isinstance(s[k],bool) and s[k]>=0,'INVALID_COUNT_SUPPORT')
        require(s['threes']<=s['fgm']<=s['fga'] and s['ftm']<=s['fta'],'SHOT_CONSERVATION')
        require(s['points']==2*s['fgm']+s['threes']+s['ftm'],'SCORING_IDENTITY')
        require(p['active'] or all(s[k]==0 for k in ('points','rebounds','assists','threes','fgm','fga','ftm','fta')),'DNP_OUTCOMES')
        require(p['minutes']>0 or all(s[k]==0 for k in ('points','rebounds','assists','threes','fgm','fga','ftm','fta')),'ZERO_EXPOSURE_OUTCOME')
        combo={'pr':s['points']+s['rebounds'],'pa':s['points']+s['assists'],'ra':s['rebounds']+s['assists'],
               'pra':s['points']+s['rebounds']+s['assists']}
        for key,value in combo.items():
            if key in s:require(s[key]==value,'INDEPENDENT_COMBO_DERIVATION')
        out.append({**s,**combo})
    for team in teams:
        ps=[s for s in out if s['team_id']==team]
        require(sum(s['points'] for s in ps)==outcomes['team_points'][team],'TEAM_POINTS_CONSERVATION')
        require(sum(s['assists'] for s in ps)<=sum(s['fgm'] for s in ps),'ASSISTS_EXCEED_MADE_BASKETS')
    return {'schema':VERSION,'scenario_id':features['scenario_id'],'event_id':features['event_id'],
            'players':out,'fixture_hash':digest([features,opportunity,outcomes]),'simulator_built':False}
