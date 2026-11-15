"""Read-only audit of WS1's actual Nov15 feature pin; no fitting or imputation.

This native JSONL producer schema shares a name with the proposed JSON-array
model interchange but has different semantics. Do not pass it to load_packet.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .models import MODELS, canonical, require, sha, stamp, strict_json
from .native_ws1 import consume
from .weather import digest_file
from .weather_run import CANONICAL

FEATURE_PIN_SHA = '35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a'
PIN_PATH = ('reports/nfl_20261115_prospective/source_control/feature_store/pins/'
            + FEATURE_PIN_SHA + '/FORECAST_FEATURE_PIN.json')


def bound(root, path, expected):
    target = (root / path).resolve()
    require(target.is_relative_to(root.resolve()), 'source_path_escape')
    require(digest_file(target) == expected, 'hash_mismatch:' + path)
    return target


def contract_reasons(c, roster, upcoming):
    reasons = list(c.get('abstention_reasons', []))
    if not upcoming:
        reasons.append('KICKOFF_PASSED')
    if not c.get('status', {}).get('SOURCE_IDENTITY_CERTIFIED'):
        reasons.append('WS1_QUOTE_NOT_SOURCE_CERTIFIED')
    if roster.get('participation_probability') is None:
        reasons.append('MISSING_PARTICIPATION_PROBABILITY')
    if c.get('product_terms') == 'PRODUCT_SPECIFIC_RULES_UNVERIFIED':
        reasons.append('PRODUCT_SPECIFIC_DNP_AND_SETTLEMENT_RULES_UNVERIFIED')
    return sorted(set(reasons))


def audit(root, now=None):
    root = Path(root).resolve()
    now = now or datetime.now(timezone.utc).isoformat()
    pin = strict_json(bound(root, PIN_PATH, FEATURE_PIN_SHA).read_bytes())
    require(pin['canonical_source_manifest_file_sha256'] == CANONICAL, 'wrong_canonical_pin')
    require(stamp(pin['feature_freeze_at']) <= stamp(pin['generated_at']) <= stamp(now),
            'feature_pin_chronology')
    handoff = strict_json(bound(root, pin['original_handoff_pin_path'],
                                pin['original_handoff_pin_sha256']).read_bytes())
    require(handoff['source_control_manifest_sha256'] == CANONICAL, 'handoff_pin_mismatch')
    source = bound(root, pin['canonical_source_manifest_path'], CANONICAL)
    original = strict_json(source.read_bytes())
    native = consume(source, CANONICAL, root/'reports/nfl_20261115_prospective', now)
    require(all(s['status'] != 'blocked' for s in native['source_checks']), 'native_sources_blocked')
    historical_path = bound(root, pin['archived_history_source_manifest_path'],
                            pin['archived_history_manifest_file_sha256'])
    historical = strict_json(historical_path.read_bytes())
    verified_sources = {s['sha256'] for s in original['sources'].values()}
    history_checks = []
    for name, expected in historical['source_files'].items():
        p = historical_path.parent/name
        bound(root, str(p.relative_to(root)), expected)
        verified_sources.add(expected)
        history_checks.append({'path': str(p.relative_to(root)), 'sha256': expected})
    for s in pin['new_raw_source_receipts'].values():
        bound(root, s['raw_path'], s['sha256'])
        require(stamp(s['earliest_forecaster_availability_at']) <=
                stamp(s['observed_received_at']) <= stamp(pin['feature_freeze_at']),
                'new_source_after_feature_freeze')
        verified_sources.add(s['sha256'])
    tables = {}
    table_checks = []
    for name, desc in pin['tables'].items():
        path = bound(root, desc['path'], desc['sha256'])
        rows = [strict_json(line) for line in path.read_bytes().splitlines() if line.strip()]
        require(len(rows) == desc['rows'], 'table_row_count:' + name)
        tables[name] = rows
        table_checks.append({'table': name, 'rows': len(rows), 'sha256': desc['sha256']})
    def verify_row_sources(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('source_sha256', 'source_sha256s', 'roster_receipt_sha256'):
                    hashes = [item] if isinstance(item, str) else item
                    require(isinstance(hashes, list) and set(hashes) <= verified_sources,
                            'unbound_feature_source:' + key)
                elif isinstance(item, (dict, list)):
                    verify_row_sources(item)
        elif isinstance(value, list):
            for item in value:
                verify_row_sources(item)
    for rows in tables.values():
        verify_row_sources(rows)
    for row in tables['ws1-nfl-pregame-opportunity-v1']:
        require(row['source_manifest_file_sha256'] == CANONICAL, 'opportunity_source_binding')
        require(row['feature_freeze_at'] == pin['feature_freeze_at'], 'opportunity_feature_freeze')
        prior = row.get('history_prior')
        if prior:
            require(stamp(prior['history_training_data_cutoff_at']) <=
                    stamp(pin['feature_freeze_at']), 'history_cutoff_after_freeze')
    candidates = {c['candidate_id']: c for c in original['candidates']}
    contracts = tables['original_contracts']
    require(len(candidates) == len(contracts) == len(original['candidates']), 'original_denominator')
    require({c['candidate_id'] for c in contracts} == set(candidates), 'original_contract_universe')
    events = {e['espn_event_id']: e for e in tables['events']}
    roster = {(r['event_id'], r['player_id']): r for r in tables['pregame_roster_availability']}
    history_max_date = None
    for name in ('team_history', 'player_history_last10_by_contract'):
        for row in tables[name]:
            require(row['game_date'] < '2026-11-15', 'same_day_or_future_history')
            require(stamp(row['source_available_at']) <= stamp(pin['feature_freeze_at']),
                    'history_source_after_freeze')
            hashes = row['source_sha256']
            if isinstance(hashes, str): hashes = [hashes]
            require(set(hashes) <= verified_sources, 'unbound_historical_source')
            history_max_date = max(history_max_date or '', row['game_date'])
    team_missing = sum(r.get('team_plays') is None or r.get('sacks') is None
                       for r in tables['team_history'])
    rows = []
    for c in contracts:
        o = candidates[c['candidate_id']]
        for key in ('quote_id', 'book', 'line', 'stat', 'period', 'team', 'player_id', 'event_id',
                    'event_start_at', 'source_sha256'):
            require(c.get(key) == o.get(key), 'original_contract_mismatch:' + key)
        e = events.get(c['event_id'])
        if e is None:
            require(not c.get('status', {}).get('SOURCE_IDENTITY_CERTIFIED'),
                    'certified_contract_missing_event')
            reasons = contract_reasons(c, {}, True)
            reasons.append('MISSING_VERIFIED_EVENT_IDENTITY')
            rows.append({'candidate_id': c['candidate_id'], 'quote_id': c['quote_id'],
                         'event_id': c['event_id'], 'upcoming': False,
                         'kickoff_status': 'UNKNOWN', 'status': 'abstain',
                         'reason_codes': sorted(set(reasons))})
            continue
        require(stamp(c['event_start_at']) == stamp(e['scheduled_kickoff']), 'kickoff_identity')
        require({c['team'], c['opponent']} == {e['home'], e['away']}, 'event_team_identity')
        require(stamp(c['original_quote_observed_at']) <= stamp(pin['original_source_input_freeze_at'])
                <= stamp(c['feature_freeze_at']), 'quote_freeze_chronology')
        require(c['feature_freeze_at'] == pin['feature_freeze_at'], 'contract_feature_freeze')
        r = roster[(c['event_id'], c['player_id'])]
        upcoming = stamp(now) < stamp(e['scheduled_kickoff'])
        reasons = contract_reasons(c, r, upcoming)
        if team_missing:
            reasons.append('INCOMPLETE_TEAM_PLAYS_AND_SACKS_HISTORY')
        # This audit may only record abstentions demonstrated by native data.
        # A newly viable row must go through a separately reviewed adapter/run.
        require(reasons, 'potentially_forecastable_contract_requires_model_adapter')
        rows.append({'candidate_id': c['candidate_id'], 'quote_id': c['quote_id'],
                     'event_id': c['event_id'], 'upcoming': upcoming,
                     'status': 'abstain', 'reason_codes': sorted(set(reasons))})
    weather_pins = sorted(str(p.relative_to(root)) for p in
                          (root/'reports/nfl_20261115_prospective').rglob('WEATHER_FEATURE_PIN*'))
    reasons = Counter(reason for r in rows for reason in r['reason_codes'])
    code_dir = Path(__file__).parent
    return {'schema': 'ws3-weather-native-feature-audit-v1', 'status': 'BLOCKED_BY_DATA',
            'audit_at': now, 'forecast_at': None, 'release_authority': False,
            'canonical_source_sha256': CANONICAL, 'feature_pin_sha256': FEATURE_PIN_SHA,
            'neutral_forecasts': 0, 'fitted_weather_forecasts': 0, 'unchanged_fallback_forecasts': 0,
            'fitted_weather_coefficients': 0, 'matched_pairs': 0,
            'original_contracts': len(rows), 'upcoming_contracts': sum(r['upcoming'] for r in rows),
            'abstained_model_contract_rows': len(rows)*len(MODELS),
            'neutral_versions': list(MODELS), 'reason_counts_contracts': dict(reasons),
            'feature_freeze_at': pin['feature_freeze_at'],
            'historical_evidence': {'max_game_date': history_max_date,
                'original_pregame_availability_verified': pin['history_original_pregame_availability_verified'],
                'historical_manifest_sha256': pin['archived_history_manifest_file_sha256'],
                'verified_source_files': history_checks, 'tables': table_checks,
                'team_rows_missing_plays_or_sacks': team_missing},
            'native_source_checks': native['source_checks'], 'weather_pin_paths': weather_pins,
            'weather_effect_status': 'WEATHER_EFFECT_NOT_ESTIMATED',
            'weather_reason': 'NO_VALIDATED_POINT_IN_TIME_WEATHER_TRAINING_PACKET',
            'model_code_sha256': {name: digest_file(code_dir/name) for name in
                ('models.py','native_ws1.py','weather.py','weather_run.py','feature_handoff_audit.py')},
            'paired_validation': {'status': 'UNAVAILABLE_NO_FITTED_PAIRS', 'folds': 0,
                'brier': None, 'log_loss': None, 'crps': None, 'calibration': None,
                'directional_bias': None, 'mean_error': None, 'dispersion_error': None,
                'coverage': 0, 'paired_uncertainty': None, 'weather_exposure_scores': None},
            'component_effects': {k: None for k in ('volume','allocation','efficiency','role_uncertainty')},
            'rows': rows}
