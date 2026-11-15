"""Offline neutral-first WS3 weather execution. Never fetches sources."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from .models import (GateError, canonical, freeze_output, load_packet, require,
                     sha, stamp, strict_json)
from .native_ws1 import consume
from .weather import load_weather_pin, run_pair, digest_file, read_bound

CANONICAL = '5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71'

def execute(base, history_manifest=None, history_sha256=None, weather_pin=None,
            weather_sha256=None, draws=8192):
    base = Path(base).resolve()
    now = datetime.now(timezone.utc).isoformat()
    pin = strict_json((base/'source_control/HANDOFF_PIN.json').read_bytes())
    require(pin['source_control_manifest_sha256'] == CANONICAL, 'canonical_source_pin_mismatch')
    src = read_bound(base, {'path': pin['source_control_manifest_relative_path'], 'sha256': CANONICAL})
    native = consume(src, CANONICAL, base, now)
    require(all(c['status'] != 'blocked' for c in native['source_checks']), 'original_source_verification_blocked')
    if history_manifest is None:
        report = {'schema': 'ws3-weather-fallback-v1', 'status': 'BLOCKED_BY_DATA',
                  'audit_at': now, 'forecast_at': None, 'actual_forecasts': 0,
                  'weather_estimated_forecasts': 0, 'deepnote_run_id': None,
                  'canonical_manifest_sha256': CANONICAL,
                  'original_contracts_attempted': native['original_contracts_attempted'],
                  'reason': 'MISSING_WS1_IMMUTABLE_HISTORY_MANIFEST_AND_HASH',
                  'weather_reason': 'WEATHER_PIN_NOT_SUPPLIED' if weather_pin is None else 'HISTORY_BLOCKS_FORECASTING',
                  'paired_contract_table': [], 'native_source_checks': native['source_checks'],
                  'native_abstentions': native['rows']}
        return {'blocker': freeze_output(report, base/'opportunity_models/weather')}
    require(history_sha256 is not None, 'missing_history_pin')
    packet = load_packet(history_manifest, history_sha256, now)
    require(packet['manifest'].get('canonical_source_manifest_sha256') == CANONICAL,
            'history_not_bound_to_canonical_source')
    # Original exact markets/lines and the crosswalk must be preserved by WS1.
    original = strict_json(src.read_bytes())
    candidates = {c['candidate_id']: c for c in original['candidates']}
    events = {e['game_id']: e for e in packet['events']}
    for c in packet['contracts']:
        o = candidates.get(c['contract_id'])
        require(o is not None and o.get('source_certified') is True, 'contract_not_source_certified')
        for key in ('quote_id', 'book', 'line', 'stat', 'period', 'team'):
            require(c.get(key) == o.get(key), 'original_contract_mismatch_' + key)
        require(c['player_id'] == (o.get('nflverse_player_id') or o.get('player_id')),
                'original_player_crosswalk_mismatch')
        require(stamp(events[c['game_id']]['event_start']) == stamp(o['event_start_at']),
                'original_kickoff_mismatch')
    # Activate/freeze the neutral run before touching optional weather evidence.
    from .models import OpportunityModel
    neutral = OpportunityModel(packet, draws).run()
    neutral_completed = datetime.now(timezone.utc).isoformat()
    require(all(stamp(neutral_completed) < stamp(e['event_start']) for e in packet['events']),
            'kickoff_passed_before_neutral_freeze')
    neutral['forecast_completed_at'] = neutral_completed
    neutral_receipt = freeze_output(neutral, base/'opportunity_models/weather/neutral_control')
    wx, failure = None, None
    if weather_pin is not None:
        try:
            wx = load_weather_pin(weather_pin, weather_sha256, packet['events'], now)
        except (GateError, KeyError, OSError, ValueError, TypeError) as exc:
            failure = 'WEATHER_REJECTED:' + str(exc)
    else:
        failure = 'WEATHER_PIN_NOT_SUPPLIED'
    from .weather import pair_control, PARAMETERS, digest_file
    deps = {'canonical_source': CANONICAL, 'features': history_sha256,
            'weather': (wx or {}).get('sha256'),
            'neutral_code': digest_file(Path(__file__).with_name('models.py')),
            'native_source_validator_code': digest_file(Path(__file__).with_name('native_ws1.py')),
            'weather_code': digest_file(Path(__file__).with_name('weather.py')),
            'parameters': sha(canonical(PARAMETERS)),
            'runner_code': digest_file(__file__), 'weather_pin_attempted_sha256': weather_sha256}
    report = pair_control(neutral, deps, wx, failure)
    # Actual completion time, not a start timestamp, is the pregame freeze gate.
    completed = datetime.now(timezone.utc).isoformat()
    require(all(stamp(completed) < stamp(e['event_start']) for e in packet['events']),
            'kickoff_passed_before_weather_freeze')
    report['forecast_completed_at'] = completed
    report['neutral_receipt'] = neutral_receipt
    return {'neutral': neutral_receipt,
            'weather': freeze_output(report, base/'opportunity_models/weather/paired')}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=Path('reports/nfl_20261115_prospective'))
    parser.add_argument('--history-manifest', type=Path)
    parser.add_argument('--history-sha256')
    parser.add_argument('--weather-pin', type=Path)
    parser.add_argument('--weather-sha256')
    parser.add_argument('--draws', type=int, default=8192)
    args = parser.parse_args()
    print(json.dumps(execute(**vars(args)), sort_keys=True))

if __name__ == '__main__':
    main()
