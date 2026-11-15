#!/usr/bin/env python3
"""Consume the actual WS1 native manifest without changing source eligibility.

WS1 v1 has no certified player history or original control forecasts. Its
rejected/ineligible rows must generate unavailable records, never invented
probabilities. A later eligible manifest still requires the separately
source-bound model-input interface used by nfl_ws2_shadow before inference.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

NATIVE_SCHEMA = 'nfl_20261115_source_control_v1'
IDENTITY_KEYS = ('candidate_id','event_id','player_id','quote_id','stat','period',
                 'line','book','source_sha256','event_start_at','input_freeze_at')


def canonical(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit_native_ws1(raw, *, filename, model_ids, parameters, code_hashes, now):
    obj=json.loads(raw)
    if raw != canonical(obj)+b'\n':
        raise ValueError('WS1_MANIFEST_BYTES_NONCANONICAL')
    if Path(filename).stem != digest(canonical(obj)):
        raise ValueError('WS1_CANONICAL_FILENAME_HASH_MISMATCH')
    if obj.get('schema') != NATIVE_SCHEMA or obj.get('date') != '2026-11-15':
        raise ValueError('WS1_SCHEMA_OR_DATE_MISMATCH')
    if not isinstance(obj.get('candidates'),list):
        raise ValueError('WS1_CANDIDATE_UNIVERSE_MISSING')
    dt=datetime.fromisoformat(now.replace('Z','+00:00'))
    if dt.tzinfo is None:
        raise ValueError('FORECAST_ATTEMPT_CLOCK_NAIVE')
    counts=Counter();markets=defaultdict(Counter);rows=[];seen=set()
    for index,src in enumerate(obj['candidates']):
        ident=src.get('candidate_id')
        reason=src.get('source_validation_failure')
        if ident in seen:
            reason=reason or 'DUPLICATE_ORIGINAL_CANDIDATE_ID'
        seen.add(ident)
        if not src.get('source_certified'):
            reason=reason or 'WS1_SOURCE_NOT_CERTIFIED'
        elif not src.get('forecast_eligible'):
            reason=reason or src.get('forecast_eligibility_reason') or 'WS1_FORECAST_NOT_ELIGIBLE'
        else:
            # Do not launder eligibility into a source-bound history or an
            # originally frozen 60/40 control. Native v1 contains neither.
            reason=reason or 'WS1_CERTIFIED_MODEL_HISTORY_AND_ORIGINAL_CONTROLS_NOT_SUPPLIED'
        counts[reason]+=1
        markets[src.get('stat','unknown')][reason]+=1
        rows.append({'input_index':index,**{k:src.get(k) for k in IDENTITY_KEYS},
            'source_manifest_file_sha256':digest(raw),'attempt_at':now,
            'status':'unavailable','reason':reason,
            'source_certified':src.get('source_certified'),
            'forecast_eligible':src.get('forecast_eligible'),
            'eligibility_status':src.get('eligibility_status'),
            'settlement_semantics':src.get('settlement_semantics'),
            'frozen_control':src.get('frozen_control'),
            'models':{m:{'status':'unavailable','reason':reason,'q_over':None,
                'q_under':None,'q_push':None,'mean':None,'variance':None} for m in model_ids}})
    return {'schema':'nfl-ws2-native-ws1-consumption-v1','target_date':'2026-11-15',
        'status':'blocked_by_source_or_model_inputs','attempt_at':now,
        'source_manifest_canonical_sha256':digest(canonical(obj)),
        'source_manifest_file_sha256':digest(raw),'source_manifest_path':str(filename),
        'source_code_commit':obj.get('code_sha'),'input_freeze_at':obj.get('input_freeze_at'),
        'input_rows':len(rows),'source_certified_rows':sum(s.get('source_certified') is True for s in obj['candidates']),
        'source_forecast_eligible_rows':sum(s.get('forecast_eligible') is True for s in obj['candidates']),
        'forecast_count':0,'unavailable_contracts':len(rows),'distinct_successful_versions':[],
        'implemented_versions':list(model_ids),'parameters':parameters,'code_sha256':code_hashes,
        'parameters_sha256':digest(canonical(parameters)),
        'reason_counts':dict(counts),
        'per_market':{m:{'input_contracts':sum(c.values()),'forecast_count':0,
            'unavailable_contracts':sum(c.values()),'reason_counts':dict(c),
            'comparison_60_40':'unavailable_original_controls_not_frozen',
            'comparison_market_only':'unavailable_source_identity_not_certified'} for m,c in sorted(markets.items())},
        'source_controls_preserved':True,'production_modified':False,
        'evidence_class':'real_prospective_source_capture_consumption; zero eligible predictions; no forecast-performance evidence',
        'rows':rows}


def write_native_audit(report, out_root):
    raw=canonical(report)+b'\n'
    path=Path(out_root)/(digest(raw)+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw)
    return {'path':str(path),'sha256':digest(raw),'bytes':len(raw),
        **{k:report[k] for k in ('source_manifest_file_sha256','input_rows','forecast_count',
            'unavailable_contracts','source_certified_rows','source_forecast_eligible_rows',
            'reason_counts','per_market','parameters_sha256','code_sha256')}}


def main():
    import argparse
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from v2.nfl_marginal_shadow import MODEL_IDS,PARAMETERS
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-manifest',type=Path,required=True)
    p.add_argument('--out-root',type=Path,required=True)
    a=p.parse_args()
    code={name:digest((Path(__file__).resolve().parents[1]/name).read_bytes()) for name in
          ('v2/nfl_marginal_shadow.py','scripts/nfl_ws2_shadow.py','scripts/nfl_ws2_ws1_adapter.py')}
    report=audit_native_ws1(a.source_manifest.read_bytes(),filename=str(a.source_manifest),
        model_ids=MODEL_IDS,parameters=PARAMETERS,code_hashes=code,now=datetime.now(timezone.utc).isoformat())
    print(json.dumps(write_native_audit(report,a.out_root),sort_keys=True))


if __name__=='__main__':main()

# Explicit adapter for WS1 historical wide player/team tables. It deliberately
# requires a source-bound identity crosswalk and actual timestamp columns; it
# never guesses player identity from names or availability from kickoff time.
WIDE_STATS = {
    'attempts': 'pass attempts', 'completions': 'completions',
    'receptions': 'receptions', 'carries': 'carries',
    'passing_yards': 'passing yards', 'receiving_yards': 'receiving yards',
    'rushing_yards': 'rushing yards', 'tackles_plus_assists': 'tackles + assists',
}


def normalize_ws1_tables(packet):
    """Return the existing long marginal schema from a verified WS1 table packet.

    Team rows provide game_end_at, available_at, source_received_at for exact
    (game_id, team) joins. Crosswalks map source_player_id to canonical ESPN ID
    and carry source-bound role/position. Appearance must be supplied by WS1.
    Missing individual stat cells stay missing rather than becoming zero.
    """
    teams={};crosswalk={}
    for t in packet['teams']:
        key=(t['game_id'],t['team'])
        if key in teams:raise ValueError('AMBIGUOUS_HISTORICAL_TEAM_GAME')
        teams[key]=t
    for x in packet['player_crosswalk']:
        key=(x['source_player_id_namespace'],x['source_player_id'])
        if key in crosswalk:raise ValueError('AMBIGUOUS_HISTORICAL_PLAYER_CROSSWALK')
        if x.get('verified') is not True:raise ValueError('UNVERIFIED_HISTORICAL_PLAYER_CROSSWALK')
        crosswalk[key]=x
    observations=[];excluded=Counter()
    for player in packet['historical_players']:
        x=crosswalk.get((player['player_id_namespace'],player['player_id']))
        if x is None:
            excluded['UNMAPPED_HISTORICAL_PLAYER']+=1
            continue
        team=teams.get((player['game_id'],player['team']))
        if team is None:
            excluded['MISSING_HISTORICAL_TEAM_GAME']+=1
            continue
        # A historical player's position/role must come from that appearance,
        # not today's roster or a later-season depth chart.
        role=player.get('role');position=player.get('position')
        for column,stat in WIDE_STATS.items():
            if column not in player or player[column] is None:continue
            observations.append({
                'player_id':x['player_id'],'player_id_namespace':x['player_id_namespace'],
                'event_id':player['game_id'],'team':player['team'],
                'position':position,'role':role,'stat':stat,'period':'full_game',
                'game_end_at':team.get('game_end_at'),
                'available_at':team.get('available_at'),
                'source_received_at':team.get('source_received_at'),
                'appearance':player.get('appearance','unknown'), 'value':player[column],
                'original_historical_player_id':player['player_id'],
                'historical_source_sha256':player.get('source_sha256'),
            })
    return {**packet,'players':observations,'table_adapter_exclusions':dict(excluded)}
