"""Source-bound roster handoff; no collector, inferred probabilities or release authority."""
from collections import Counter
from pathlib import Path
import json
from v2.nba_ws1 import NBAPregameFeatureSnapshot
from v2.nba_ws1.replay import replay
from v2.nba_ws1.store import instant, canonical, digest

VERSION='NBAGameDayRoster/1.0.0'
# No participation estimator has a validated handoff in the frozen repository.
VALIDATED_PARTICIPATION_METHODS=()


def build_roster_contract(folder, model, *, participation_evidence=None, max_age_seconds=21600):
    if participation_evidence:raise ValueError('UNVALIDATED_PARTICIPATION_METHOD')
    if type(max_age_seconds)!=int or max_age_seconds<0:raise ValueError('INVALID_ROSTER_AGE_POLICY')
    folder=Path(folder);receipt=json.loads((folder/'capture_receipt.json').read_text())
    path=(folder/receipt['snapshot_path']).resolve()
    if not path.is_relative_to(folder.resolve()):raise ValueError('SNAPSHOT_PATH_ESCAPE')
    original=NBAPregameFeatureSnapshot.from_json(path.read_text())
    rebuilt=replay(folder)
    if rebuilt.content_hash!=original.content_hash:raise ValueError('RAW_SOURCE_DERIVATION_MISMATCH')
    data=original.to_dict();freeze=instant(data['input_freeze_at']);game=data['game']
    if instant(model['training_cutoff_at'])>freeze or instant(model['minutes']['training_cutoff_at'])>freeze:raise ValueError('MODEL_AFTER_FREEZE')
    if instant(model['training_cutoff_at'])>instant(data['model_training_cutoff_at']):raise ValueError('MODEL_CUTOFF_MISMATCH')
    if not freeze<=instant(data['forecast_at'])<instant(game['event_start_at']):raise ValueError('PREGAME_CLOCK')
    sources={r['receipt_id']:r for r in data['receipts']}
    records={r['record_id']:r for r in data['input_records']}
    rejects={r['record_id']:r['code'] for r in data['ledger']['rejections']}
    result=[]
    for player in data['players']:
        reasons=set();evidence=[];availability=[];start=[]
        roster=records[player['roster_record_id']]
        associated=[roster]+[records[r['record_id']] for r in player['availability']]
        for r in associated:
            s=sources[r['receipt_id']];p=json.loads(r['payload']);published=None
            if r['kind']=='availability' and p.get('detail'):
                detail=json.loads(p['detail']);published=detail.get('reported_at')
            if published is not None and instant(published)>freeze:reasons.add('FUTURE_PUBLICATION')
            if instant(s['observed_at'])>freeze or instant(s['source_available_at'])>freeze:reasons.add('SOURCE_AFTER_FREEZE')
            if (freeze-instant(s['observed_at'])).total_seconds()>max_age_seconds:reasons.add('STALE_GAME_DAY_EVIDENCE')
            if s['origin']!='original_capture':reasons.add('NOT_ORIGINAL_PREGAME_CAPTURE')
            if p['game_id']!=game['game_id'] or p['team_id']!=player['team_id'] or p['player_id']!=player['player_id']:reasons.add('IDENTITY_CONFLICT')
            if r['record_id'] in rejects:reasons.add(rejects[r['record_id']])
            item=dict(record_id=r['record_id'],kind=r['kind'],receipt_id=r['receipt_id'],source=s['source'],raw_sha256=s['raw_sha256'],
                published_at=published,retrieved_at=s['observed_at'],source_available_at=s['source_available_at'],origin=s['origin'],data=p)
            evidence.append(item)
            if r['kind']=='availability':
                availability.append(item)
                if p.get('role') is not None:start.append(item)
        # Current raw ESPN adapter proves season membership only. It cannot certify
        # legal game-active eligibility, even if a source status contains "active".
        reasons.add('GAME_DAY_ELIGIBILITY_UNAVAILABLE')
        reasons.add('PARTICIPATION_METHOD_UNAVAILABLE')
        reasons.update(code for code in data['abstention_codes'] if code in ('CONFLICTING_RECORDS','ROSTER_COLLISION'))
        inactive=any(r['data']['status'].lower() in ('out','inactive','suspended','unavailable','confirmed_inactive') for r in availability)
        result.append(dict(player_id=player['player_id'],team_id=player['team_id'],game_id=game['game_id'],
            forecast_freeze_at=data['input_freeze_at'],eligibility=None,eligibility_evidence=evidence[:1],
            availability='reported_inactive' if inactive else 'uncertain',availability_evidence=availability,starting_role_evidence=start,
            participation_probability=None,participation_method=None,conditional_exposure_model_sha256=digest(canonical(model['minutes']).encode()),
            missing_data_status=sorted(set(player['missing_feature_codes'])|{'COMPLETE_GAME_DAY_COVERAGE_UNVERIFIED'}),
            abstention_reasons=sorted(reasons),source_evidence=evidence,status='BLOCKED-BY-DATA'))
    present={(r['player_id'],r['team_id']) for r in result}
    # Rejected/superseded raw candidates remain visible, including identity conflicts.
    extra=[]
    for r in data['input_records']:
        if r['kind'] not in ('roster','availability'):continue
        p=json.loads(r['payload'])
        if (p['player_id'],p['team_id']) not in present:
            extra.append(dict(player_id=p['player_id'],team_id=p['team_id'],game_id=p['game_id'],record=r,
                abstention_reasons=[rejects.get(r['record_id'],'NOT_IN_ACCEPTED_WS1_ROSTER')]))
    reasons=Counter(code for r in result for code in r['abstention_reasons'])
    out=dict(schema=VERSION,source_adapter='WS1-raw-byte-replay/1.0.0',snapshot_content_hash=original.content_hash,
        snapshot_file_sha256=digest(path.read_bytes()),game=game,input_freeze_at=data['input_freeze_at'],forecast_at=data['forecast_at'],
        model_training_cutoff_at=model['training_cutoff_at'],model_sha256=digest(canonical(model).encode()),source_receipts=data['receipts'],
        players=result,rejected_candidates=extra,upstream_rejections=data['ledger'],validated_participation_methods=list(VALIDATED_PARTICIPATION_METHODS),
        coverage=dict(accepted_ws1_candidates=len(result),additional_rejected_candidates=len(extra),eligible=0,unknown_eligibility=len(result),
            reported_inactive=sum(r['availability']=='reported_inactive' for r in result),participation_supported=0,forecasts_accepted=0,
            forecasts_abstained=len(result),reason_counts=dict(reasons),complete_game_day_universe=False),
        source_bytes_verified=True,status='BLOCKED-BY-DATA',independent_source_certification='pending',
        semantics='eligibility, availability, participation and conditional exposure are distinct; no probability inferred from membership')
    out['content_sha256']=digest(canonical(out).encode())
    return out


def require_forecast_ready(contract):
    expected=contract.copy();given=expected.pop('content_sha256')
    if digest(canonical(expected).encode())!=given:raise ValueError('ROSTER_CONTRACT_HASH')
    if contract['schema']!=VERSION or contract['status']!='shadow_only':raise ValueError('ROSTER_NOT_FORECAST_READY')
    if not contract['coverage']['complete_game_day_universe']:raise ValueError('ROSTER_COVERAGE_UNVERIFIED')
    # Current adapter intentionally cannot return a ready contract.
    if not VALIDATED_PARTICIPATION_METHODS:raise ValueError('UNVALIDATED_PARTICIPATION_METHOD')
    return contract
