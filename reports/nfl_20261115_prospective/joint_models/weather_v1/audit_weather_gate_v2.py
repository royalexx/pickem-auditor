"""Outcome-blind audit, never a simulator, collector, or forecast generator.

Copies frozen neutral fields verbatim; unavailable challenger/delta cells are null.
Only a source-owned weather schema and a validated historical fit can unblock a
future, separately versioned prediction implementation. This audit cannot do so.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import math
import json
from pathlib import Path
import sys

VERSION = 'ws4-weather-evidence-gate-v2'
SOURCE_SHA = '5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71'

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode() + b'\n'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_frozen(path):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != Path(path).stem:
        raise ValueError('IMMUTABLE_NEUTRAL_HASH_MISMATCH')
    obj = json.loads(raw)
    if obj['canonical_ws1_sha256'] != SOURCE_SHA:
        raise ValueError('ORIGINAL_WS1_CHANGED')
    return obj

WEATHER_PIN_SHA = '273da5a6f5456e99e9b5bd4f2172abce1bf77c7bfbe82d38199886fcad612807'

def stamp(value):
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('NAIVE_WEATHER_CLOCK')
    return t

def bound_file(root, receipt):
    path = (root / receipt['path']).resolve()
    if not path.is_relative_to(root.resolve()) or digest(path) != receipt['sha256']:
        raise ValueError('WEATHER_SOURCE_HASH_OR_PATH_MISMATCH')
    return path

def load_weather(root, source):
    path = root/'reports/nfl_20261115_prospective/weather_v2/WEATHER_FEATURE_PIN.json'
    if digest(path) != WEATHER_PIN_SHA:
        raise ValueError('WEATHER_PIN_HASH_MISMATCH')
    pin = json.loads(path.read_bytes())
    if (pin['schema'] != 'ws1-nfl-pregame-weather-v2' or
        pin['producer_workstream'] != 1 or pin['source_owner'] != 'WS1_ONLY' or
        pin['canonical_ws1_manifest_sha256'] != SOURCE_SHA):
        raise ValueError('UNCERTIFIED_WEATHER_PRODUCER_OR_SOURCE')
    for rec in pin['dependencies']:
        bound_file(root, rec)
    table = bound_file(root, pin['event_table'])
    if [json.loads(line) for line in table.read_text().splitlines()] != pin['events']:
        raise ValueError('WEATHER_TABLE_PIN_DISAGREEMENT')
    events = {str(e['espn_event_id']):e for e in source['events']}
    out = {}
    for row in pin['events']:
        gid = row['game_id']
        if gid not in events or gid in out:
            raise ValueError('WEATHER_UNKNOWN_OR_DUPLICATE_EVENT')
        event = events[gid]
        if (stamp(row['kickoff_at']) != stamp(event['scheduled_kickoff']) or
            row['fixture_key'] != event['fixture_key']):
            raise ValueError('WEATHER_EVENT_OR_KICKOFF_MISMATCH')
        if row['status'] == 'EXCLUDED_ALREADY_STARTED':
            if row['normalized'] or row['weather_feature_freeze_at'] is not None:
                raise ValueError('POSTKICKOFF_WEATHER_BACKFILL')
            out[gid] = row
            continue
        if row['kind'] != 'forecast' or row['status'] != 'VERIFIED_FORECAST':
            raise ValueError('WEATHER_NOT_VERIFIED_FORECAST')
        issued, retrieved, freeze, kickoff = map(stamp, (row['forecast_issued_at'],
            row['retrieved_at'],row['weather_feature_freeze_at'],row['kickoff_at']))
        if not issued <= retrieved <= freeze < kickoff or freeze > datetime.now(timezone.utc):
            raise ValueError('WEATHER_CHRONOLOGY')
        for rec in row['sources']:
            if rec['status'] == 'OK':
                bound_file(root, rec)
            if stamp(rec['retrieved_at']) > freeze:
                raise ValueError('WEATHER_RECEIPT_AFTER_FREEZE')
        grid = next(r for r in row['sources'] if r.get('sha256') == row['weather_source_sha256'])
        props = json.loads(bound_file(root, grid).read_bytes())['properties']
        if props['updateTime'] != row['forecast_issued_at'] or grid['retrieved_at'] != row['retrieved_at']:
            raise ValueError('WEATHER_ISSUANCE_OR_RETRIEVAL_CHANGED')
        for field, native in row['native'].items():
            selected = native['selected']
            if selected:
                raw = {k:v for k,v in selected.items() if k in ('validTime','value')}
                if raw not in props[field]['values'] or native['unitCode'] != props[field].get('uom'):
                    raise ValueError('WEATHER_NATIVE_VALUE_NOT_IN_SOURCE')
                if not stamp(selected['valid_start_at']) <= kickoff < stamp(selected['valid_end_at']):
                    raise ValueError('WEATHER_VALIDITY_MISSES_KICKOFF')
        for field,key in (('windSpeed','wind_m_s'),('windGust','gust_m_s'),
                          ('temperature','temperature_c'),
                          ('quantitativePrecipitation','precipitation_interval_average_mm_h')):
            native=row['native'][field]; selected=native['selected']
            value=selected.get('value') if selected else None
            if value is not None:
                unit=native['unitCode']
                if field in ('windSpeed','windGust'):
                    factor={'wmoUnit:km_h-1':1/3.6,'wmoUnit:m_s-1':1.,
                            'wmoUnit:mi_h-1':.44704,'wmoUnit:kn':.514444}[unit]
                    value*=factor
                    if value < 0: raise ValueError('NEGATIVE_WIND')
                elif field=='temperature':
                    if unit=='wmoUnit:degF': value=(value-32)*5/9
                    elif unit!='wmoUnit:degC': raise ValueError('TEMPERATURE_UNIT')
                else:
                    if unit!='wmoUnit:mm': raise ValueError('PRECIPITATION_UNIT')
                    hours=(stamp(selected['valid_end_at'])-stamp(selected['valid_start_at'])).total_seconds()/3600
                    value/=hours
                    if value < 0: raise ValueError('NEGATIVE_PRECIPITATION')
                if not math.isfinite(value) or not math.isclose(value,row['normalized'][key],abs_tol=1e-10):
                    raise ValueError('WEATHER_NORMALIZATION_CHANGED')
            elif row['normalized'][key] is not None:
                raise ValueError('MISSING_WEATHER_IMPUTED')
        schedule = json.loads(bound_file(root,row['venue_evidence']).read_bytes())
        scheduled = next(e for e in schedule['events'] if str(e['id']) == gid)
        if row['original_venue'] != scheduled['competitions'][0]['venue']:
            raise ValueError('WEATHER_VENUE_CHANGED')
        roof=row['roof_status']; exposure=row['exposure']; stadium=row['stadium_type']
        if roof != 'unknown' or exposure == 'SHELTERED_CONFIRMED_CLOSED_ROOF':
            raise ValueError('UNSUPPORTED_GAME_DAY_ROOF_CONFIRMATION')
        expected = {'outdoor':'EXPOSED_OUTDOOR','fixed_indoor':'SHELTERED_INDOOR',
                    'retractable':'RETRACTABLE_ROOF_STATUS_UNKNOWN','unverified':'EXPOSURE_UNVERIFIED'}
        if exposure != expected[stadium]:
            raise ValueError('WEATHER_EXPOSURE_INCONSISTENT')
        out[gid] = deepcopy(row)
    if len(out) != 12:
        raise ValueError('WEATHER_EVENT_DENOMINATOR_CHANGED')
    return pin, out

def pair_rows(obj, file_sha, candidates):
    """Existing distributions only: no rerun, re-estimation, zero-effect copy or delta."""
    packet = obj['input_packet']
    event = packet['events'][0]
    rows = []
    for row in obj['model_output']['contracts']:
        if row['model_id'] not in ('J1', 'J2') or row['draws'] != 4096:
            raise ValueError('NEUTRAL_MODEL_OR_DRAWS_CHANGED')
        c = next(c for c in packet['contracts'] if c['contract_id'] == row['contract_id'])
        original = candidates[c['contract_id']]
        if any(c[k] != row[k] for k in ('contract_id','event_id','player_id','team_id',
                                       'stat_key','period','line','original_quote_id')):
            raise ValueError('EXACT_CONTRACT_CHANGED')
        rows.append({'contract': deepcopy(c), 'original_sportsbook': original['book'],
            'neutral_model': row['model_id'], 'neutral_file_sha256': file_sha,
            'neutral_forecast_at': obj['model_output']['forecast_created_at'],
            'kickoff': event['event_start_at'], 'neutral_distribution': deepcopy(row),
            'weather_challenger_version': None, 'weather_forecast_at': None,
            'weather_distribution': None, 'weather_source_sha256': None,
            'weather_exposure': 'UNVERIFIED_NO_CERTIFIED_WEATHER_HANDOFF',
            'weather_parameter_uncertainty': None,
            'delta_mean': None, 'delta_variance': None, 'delta_p_over': None,
            'delta_p_under': None, 'delta_p_push': None, 'delta_tails': None,
            'delta_team_allocations': None, 'paired_mc_uncertainty': None,
            'pair_status': 'ABSTAIN_WEATHER_NO_VALIDATED_INPUT_AND_FIT'})
    return rows

def seal_new(directory, obj):
    body = canonical(obj); sha = hashlib.sha256(body).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / (sha + '.json')
    with dest.open('xb') as f:
        f.write(body)
    if digest(dest) != sha:
        raise ValueError('SEAL_FAILED')
    return dest, sha

def run(root, run_id):
    root = root.resolve(); p = root/'reports/nfl_20261115_prospective'; j = p/'joint_models'
    sys.path.insert(0, str(p/'independent_validation'))
    import ws4_original_contract_audit as audit
    src = p/'source_control/captures/ab2eebf29ea0dfcf9b2cc4ff5287b898e6b7b15238ea059a11df3ac399ccc6c8.json'
    assert digest(src) == SOURCE_SHA
    source = json.loads(src.read_bytes()); candidates = {c['candidate_id']:c for c in source['candidates']}
    files = sorted((j/'real_original_qb_attempts_multievent_v031').glob('*.json'))
    assert len(files) == 11, 'FROZEN_EVENT_COUNT_CHANGED'
    before = {str(f.relative_to(root)): digest(f) for f in files}
    # Record discovery, not an invented WS1 interchange or assumed certification.
    wx = [root/x for x in (
        'reports/nfl_20261115_prospective/weather_v2/WEATHER_FEATURE_PIN.json',
        'reports/nfl_20261115_prospective/weather_v2/events.jsonl',
        'reports/nfl_20261115_prospective/weather_v2/SHA256SUMS.json',
        'research/nfl_opportunity_20261115/WEATHER.md') if (root/x).is_file()]
    pins = [f for f in wx if f.name == 'WEATHER_FEATURE_PIN.json']
    inventory = [{'path':str(f.relative_to(root)), 'sha256':digest(f), 'bytes':f.stat().st_size}
                 for f in wx]
    pin, weather = load_weather(root, source)
    events=[]; pairs=[]; audits=[]
    for f in files:
        audited = audit.verify(f, src)  # Checks source/contract/time, PMF and numerical constraints.
        obj=load_frozen(f); packet=obj['input_packet']; event=packet['events'][0]
        new_rows=pair_rows(obj, f.stem, candidates)
        wxrow=weather[event['event_id']]
        for row in new_rows:
            row.update(weather_source_sha256=wxrow['weather_source_sha256'],
                weather_pin_sha256=WEATHER_PIN_SHA, weather_exposure=wxrow['exposure'],
                weather_issued_at=wxrow['forecast_issued_at'],
                weather_retrieved_at=wxrow['retrieved_at'],
                weather_feature_freeze_at=wxrow['weather_feature_freeze_at'],
                weather_available_after_neutral_forecast=stamp(wxrow['retrieved_at']) > stamp(row['neutral_forecast_at']),
                pair_status='ABSTAIN_WEATHER_NO_VALIDATED_HISTORICAL_FIT')
        pairs.extend(new_rows); audits.append(audited)
        events.append({'event_id':event['event_id'], 'kickoff':event['event_start_at'],
            'neutral_forecast_at':obj['model_output']['forecast_created_at'],
            'neutral_file_sha256':f.stem, 'input_sha256':obj['source_input_sha256'],
            'model_version':obj['model_output']['model_version'],
            'team_inputs_verbatim':deepcopy(event['teams']),
            'historical_parameter_lineage_verbatim':deepcopy(obj['historical_parameter_provenance']),
            'source_receipts_verbatim':deepcopy(obj['source_receipts']),
            'weather_source_verbatim':deepcopy(wxrow),
            'weather_issued_at':wxrow['forecast_issued_at'],
            'weather_retrieved_at':wxrow['retrieved_at'],
            'venue_and_roof_verification':wxrow['exposure'],
            'weather_effect_on_opportunities_pass_run_sacks_qb_allocation_scenarios':'NOT_ESTIMATED',
            'team_allocation_draws':'NOT_ARCHIVED_IN_NEUTRAL_OUTPUT; DO_NOT_REGENERATE',
            'j3':'ABSTAIN_NO_CERTIFIED_ORIGINAL_PREGAME_SPREAD'})
    assert Counter(r['neutral_model'] for r in pairs)=={'J1':58,'J2':58}
    assert len({r['contract']['contract_id'] for r in pairs})==58
    assert before == {str(f.relative_to(root)):digest(f) for f in files}
    blockers = ['NO_AUTHORIZED_HISTORICAL_FORECAST_VINTAGE_WEATHER_TRAINING_ROWS',
                'NO_VALIDATED_HISTORICAL_WEATHER_RESPONSE_FIT',
                'NO_CERTIFIED_ORIGINAL_PREGAME_SPREAD_FOR_J3']
    report={'schema':VERSION, 'audit_at':datetime.now(timezone.utc).isoformat(),
        'audit_run_id':run_id, 'governing_plan':'PA-V25-MASTER-2026-11-09 / v1.1',
        'status':'BLOCKED_BY_DATA_SHADOW_ONLY', 'blockers':blockers,
        'canonical_ws1_sha256':SOURCE_SHA,'audit_code_sha256':digest(__file__),
        'neutral_simulator_code_sha256':digest(j/'joint_simulator.py'),
        'neutral_adapter_code_sha256':digest(j/'ws4_original_contract_adapter.py'),
        'frozen_neutral_files_before_and_after':before, 'original_source_denominator':len(candidates),
        'counts':{'neutral_J1':58,'neutral_J2':58,'weather_J1':0,'weather_J2':0,
                  'J3':0,'paired_neutral_weather_contracts':0,'fallback_copies':0},
        'draws_each_neutral':4096, 'new_forecasts_generated':0,
        'weather_pin_paths':[str(f.relative_to(root)) for f in pins],
        'weather_evidence_inventory':inventory, 'weather_pin_sha256':WEATHER_PIN_SHA,
        'weather_producer_run_id':'7dfe59cf-01cb-42b9-9eae-51515ba59051',
        'weather_historical_evidence_verbatim':pin['historical_weather'],
        'weather_source_coverage_events':11,
        'weather_exposure_counts':dict(Counter(weather[e['event_id']]['exposure'] for e in events)),
        'weather_fit':None,
        'weather_coefficient_uncertainty':None,'forecast_weather_uncertainty_distribution':None,
        'material_improvement':'NOT_IDENTIFIABLE_NO_VALID_WEATHER_CHALLENGER',
        'events':events,'paired_contract_coverage':pairs,'neutral_independent_audits':audits,
        'J4':'DEPENDENCE_DIAGNOSTIC_ONLY', 'production_promotion':False,
        'previous_forecast_run_id':'33231250-59f2-4859-9e8f-94adaa06db4e',
        'previous_independent_audit_run_id':'0d255b78-fcf9-4c0f-ac2d-60cd933b6c56',
        'previous_67_test_run_id':'b55d19c9-fc2a-4850-b653-bab309daf318'}
    dest,sha=seal_new(j/'weather_v1/ledgers',report)
    summary={k:report[k] for k in ('schema','audit_at','audit_run_id','status','blockers',
        'canonical_ws1_sha256','audit_code_sha256','counts','draws_each_neutral',
        'new_forecasts_generated','weather_pin_sha256','weather_producer_run_id',
        'weather_historical_evidence_verbatim','weather_exposure_counts',
        'weather_coefficient_uncertainty','previous_forecast_run_id',
        'previous_independent_audit_run_id','previous_67_test_run_id')}
    summary['ledger_sha256']=sha
    summary['ledger_path']=str(dest.relative_to(root))
    summary['events']=[{'event_id':e['event_id'],'kickoff':e['kickoff'],
        'neutral_forecast_at':e['neutral_forecast_at'],
        'neutral_file_sha256':e['neutral_file_sha256'],'input_sha256':e['input_sha256'],
        'weather_issued_at':e['weather_issued_at'],
        'weather_retrieved_at':e['weather_retrieved_at'],
        'weather_freeze_at':e['weather_source_verbatim']['weather_feature_freeze_at'],
        'weather_source_sha256':e['weather_source_verbatim']['weather_source_sha256'],
        'exposure':e['venue_and_roof_verification'],
        'roof_status':e['weather_source_verbatim']['roof_status'],
        'venue':e['weather_source_verbatim']['original_venue']} for e in events]
    summary_dest,summary_sha=seal_new(j/'weather_v1/summaries',summary)
    print('DELIVERY_SUMMARY',str(summary_dest.relative_to(root)),summary_sha,flush=True)
    print(json.dumps({'status':report['status'],'ledger_path':str(dest.relative_to(root)),
          'ledger_sha256':sha,'counts':report['counts'],'blockers':blockers,
          'weather_pin_paths':report['weather_pin_paths'],'audit_at':report['audit_at']}),flush=True)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path.cwd())
    parser.add_argument('--run-id',required=True);args=parser.parse_args()
    run(args.root,args.run_id)
