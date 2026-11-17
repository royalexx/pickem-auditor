"""Strict prospective boundary. Historical reconstruction never enters WS1."""
import json
from pathlib import Path
from v2.nba_ws1 import NBAPregameFeatureSnapshot
from v2.nba_ws1.store import digest
from .common import instant, sha


def derive_players(data,model,participation_evidence,source_bytes_hex):
    """Derive every modeling feature from accepted WS1 histories, never caller rates."""
    from v2.nba_opportunity import causal_features
    from zoneinfo import ZoneInfo
    day=instant(data['game']['event_start_at']).astimezone(ZoneInfo('America/Toronto')).date().isoformat()
    result=[]
    for p in data['players']:
        h=[r for r in p['history'] if r['participation']=='played' and r['minutes']>0]
        history=[{**r,'workload':r['minutes'],'team':r['team_id']} for r in h]
        if any(r['game_date']>=day or r['game_id']==data['game']['game_id'] for r in h):raise ValueError('FUTURE_OR_SAME_GAME_SOURCE')
        features=causal_features(history,game_date=day,team=p['team_id'],home=p['home'])
        recent=h[-20:];total=sum(r['minutes'] for r in recent)
        if any(any(k not in r['stats'] for k in ('points','rebounds','assists','threes')) for r in recent):raise ValueError('SOURCE_OUTCOME_HISTORY_INCOMPLETE')
        rates={k:(sum(r['stats'][k] for r in recent)+48*model['prior_rates'][k])/(total+48) for k in ('points','rebounds','assists','threes')}
        evidence=participation_evidence.get(p['player_id'])
        if evidence is None:raise ValueError('PARTICIPATION_EVIDENCE_UNAVAILABLE')
        raw=bytes.fromhex(source_bytes_hex.get(evidence['sha256'],''))
        if digest(raw)!=evidence['sha256']:raise ValueError('PARTICIPATION_SOURCE_HASH')
        prob=json.loads(raw)['probability']
        inactive=any(r['status'].lower() in ('out','inactive','suspended','unavailable','confirmed_inactive') for r in p['availability'])
        if inactive and prob!=0:raise ValueError('SOURCE_INACTIVE_PARTICIPATION_CONFLICT')
        result.append(dict(player_id=p['player_id'],team_id=p['team_id'],opponent_id=p['opponent_id'],position='ALL',eligible=not inactive,participation_probability=prob,
            minute_features=features,last_observation_date=h[-1]['game_date'],history_game_ids=[r['game_id'] for r in recent],rates=rates,
            history_stats={k:[r['stats'][k] for r in recent] for k in rates},availability='supplied_source_evidence'))
    return result


def adapt_snapshot(snapshot_json,model,source_bytes_hex,participation_evidence):
    from zoneinfo import ZoneInfo
    snap=NBAPregameFeatureSnapshot.from_json(snapshot_json)
    d=snap.require_usable(required_player_features=['ELIGIBILITY_UNCERTAIN','AVAILABILITY_UNAVAILABLE'])
    g=d['game'];game=dict(schema='NBAJointInput/1',game_id=g['game_id'],teams=[g['home_team_id'],g['away_team_id']],
        game_date=instant(g['event_start_at']).astimezone(ZoneInfo('America/Toronto')).date().isoformat(),event_start_at=g['event_start_at'],analysis_cutoff_at=d['input_freeze_at'],input_freeze_at=d['input_freeze_at'],forecast_at=d['forecast_at'],
        mode='prospective',conditional_on_roster=False,source_hashes=[r['raw_sha256'] for r in d['receipts']],source_cutoffs={'available_at':d['source_available_at'],'input_freeze_at':d['input_freeze_at']},
        ws1_snapshot_json=snapshot_json,source_bytes_hex=source_bytes_hex,participation_evidence=participation_evidence,
        players=derive_players(d,model,participation_evidence,source_bytes_hex))
    validate_prospective(game,model)
    return game


def validate_prospective(game,model):
    from datetime import datetime,timezone
    from zoneinfo import ZoneInfo
    if 'ws1_snapshot_json' not in game:raise ValueError('SOURCE_CERTIFIED_WS1_PACKAGE_REQUIRED')
    snap=NBAPregameFeatureSnapshot.from_json(game['ws1_snapshot_json'])
    data=snap.require_usable(required_player_features=['ELIGIBILITY_UNCERTAIN','AVAILABILITY_UNAVAILABLE','PLAYER_HISTORY_UNAVAILABLE','ROSTER_TRANSITION_REQUIRES_REVIEW'])
    if any(r['origin']!='original_capture' for r in data['receipts']):raise ValueError('SOURCE_NOT_ORIGINAL')
    if any(digest(bytes.fromhex(game.get('source_bytes_hex',{}).get(r['raw_sha256'],'')))!=r['raw_sha256'] for r in data['receipts']):raise ValueError('SOURCE_BYTES_MISSING_OR_CHANGED')
    g=data['game']
    if game['game_id']!=g['game_id'] or game['teams']!=[g['home_team_id'],g['away_team_id']]:raise ValueError('SOURCE_GAME_IDENTITY_MISMATCH')
    for field in ('forecast_at','input_freeze_at','event_start_at'):
        actual=g[field] if field=='event_start_at' else data[field]
        if instant(game.get(field,''))!=instant(actual):raise ValueError('SOURCE_CLOCK_MISMATCH')
    if instant(game['forecast_at'])>=instant(g['event_start_at']):raise ValueError('POST_EVENT_FORECAST')
    if datetime.now(timezone.utc)>=instant(g['event_start_at']):raise ValueError('PROSPECTIVE_WINDOW_CLOSED')
    if instant(game['analysis_cutoff_at'])!=instant(data['input_freeze_at']):raise ValueError('SOURCE_ANALYSIS_CUTOFF_MISMATCH')
    if game['game_date']!=instant(g['event_start_at']).astimezone(ZoneInfo('America/Toronto')).date().isoformat():raise ValueError('SOURCE_GAME_DATE_MISMATCH')
    if instant(model['training_cutoff_at'])>instant(data['model_training_cutoff_at']):raise ValueError('MODEL_CUTOFF_MISMATCH')
    if game['conditional_on_roster']:raise ValueError('UNCONDITIONAL_PARTICIPATION_REQUIRED_FOR_PROSPECTIVE')
    pmap={p['player_id']:p for p in data['players']}
    if set(pmap)!={p['player_id'] for p in game['players']}:raise ValueError('SOURCE_ROSTER_MISMATCH')
    for p in game['players']:
        if p['team_id']!=pmap[p['player_id']]['team_id']:raise ValueError('SOURCE_PLAYER_IDENTITY')
        evidence=game.get('participation_evidence',{}).get(p['player_id'])
        if evidence is None or p['participation_probability'] is None:raise ValueError('PARTICIPATION_EVIDENCE_UNAVAILABLE')
        raw=bytes.fromhex(game.get('source_bytes_hex',{}).get(evidence['sha256'],''))
        if digest(raw)!=evidence['sha256']:raise ValueError('PARTICIPATION_SOURCE_HASH')
        doc=json.loads(raw)
        if (doc['game_id'],doc['player_id'],doc['probability'])!=(game['game_id'],p['player_id'],p['participation_probability']):raise ValueError('PARTICIPATION_IDENTITY')
        if instant(evidence['observed_at'])>instant(data['input_freeze_at']):raise ValueError('FUTURE_PARTICIPATION_EVIDENCE')
    derived=derive_players(data,model,game['participation_evidence'],game['source_bytes_hex'])
    if sha(derived)!=sha(game['players']):raise ValueError('SOURCE_FEATURE_DERIVATION_MISMATCH')
    # Hashes verify content, not external authenticity. Every output remains shadow.
    return data


def canary(snapshot_path):
    path=Path(snapshot_path)
    try:
        snapshot=NBAPregameFeatureSnapshot.from_json(path.read_text())
        d=snapshot.require_usable(required_player_features=['ELIGIBILITY_UNCERTAIN','AVAILABILITY_UNAVAILABLE'])
        return {'status':'BLOCKED-BY-DATA','reason':'PARTICIPATION_MODEL_AND_INDEPENDENT_SOURCE_CERTIFICATION_PENDING','snapshot_sha256':snapshot.content_hash,'game':d['game'],'accepted':0,'attempted':len(d['players'])}
    except ValueError as exc:
        d=NBAPregameFeatureSnapshot.from_json(path.read_text()).to_dict()
        return {'status':'BLOCKED-BY-DATA','reason':str(exc),'snapshot_sha256':d['content_hash'],'game':d['game'],'attempted':len(d['players']),'accepted':0,'rejected_players':[{'player_id':p['player_id'],'reasons':p['missing_feature_codes']} for p in d['players']],'upstream_ledger':d['ledger']}
