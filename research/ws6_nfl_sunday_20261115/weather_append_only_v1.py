"""Missing-weather audit overlay. Never generates, fits or reconstructs forecasts.

The reference ledger addresses each original row by immutable parent digest and
zero-based row index. Materialization requires the original parent bytes; a
reference freeze does not claim those bytes were independently rehashed.
"""
import argparse
import hashlib
import json
from pathlib import Path

PARENT_SHA = '242c4404a6b1505844528ee7096f86060f459df6517f0420f618deef8888fbba'
PARENT_PATH = ('reports/nfl_20261115_ws6_real_comparison/'
               'canonical_s2_c2_j1_j2_original_forecast_comparison_v1/'
               'comparison_ledger_1845.jsonl')
TOTAL = 1845
COMPONENTS = ('team_opportunity_volume', 'pass_run_allocation', 'player_usage',
              'conditional_efficiency', 'defensive_involvement',
              'role_game_state_uncertainty', 'joint_simulation')
MODEL_COLUMNS = {'S2': 'S2_original_source_model',
                 'C2': 'C2_original_market_reference',
                 'J1': 'J1_original_joint_game_model',
                 'J2': 'J2_original_joint_game_model'}
COUNTS = {'S2': 1672, 'C2': 1767, 'J1': 58, 'J2': 58}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(obj):
    return (json.dumps(obj, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def parse(raw):
    def bad(value):
        raise ValueError('NONFINITE_JSON')
    return json.loads(raw, object_pairs_hook=unique, parse_constant=bad)


def overlay(index, parent_sha=PARENT_SHA):
    return {'parent_ledger_sha256': parent_sha, 'parent_observation_index': index,
            'weather_audit_v1': {
                'status': 'WEATHER_EFFECT_NOT_ESTIMATED',
                'reason': 'NO_AUTHENTICATED_FITTED_WEATHER_PREDICTIONS_DELIVERED',
                'weather_forecasts': None, 'unchanged_fallback_forecasts': None,
                'weather_source_sha256': None, 'weather_feature_sha256': None,
                'exposure': 'UNVERIFIED', 'matched_weather_pairs': 0,
                'distribution_changes': None, 'postgame_score_changes': None}}


def materialize(parent_raw, patches, expected_sha=PARENT_SHA, total=TOTAL,
                expected_counts=COUNTS):
    if sha(parent_raw) != expected_sha:
        raise ValueError('PARENT_SHA_MISMATCH')
    rows = [parse(line) for line in parent_raw.splitlines()]
    if len(rows) != total or len(patches) != total:
        raise ValueError('DENOMINATOR_CHANGED')
    if expected_counts is not None:
        for model, count in expected_counts.items():
            if sum(r[MODEL_COLUMNS[model]] is not None for r in rows) != count:
                raise ValueError('PARENT_MODEL_COUNTS_CHANGED')
        if sum(all(r[col] is not None for col in MODEL_COLUMNS.values())
               for r in rows) != 49:
            raise ValueError('PARENT_EXACT_INTERSECTION_CHANGED')
    result = []
    for i, (row, patch) in enumerate(zip(rows, patches)):
        if patch != overlay(i, expected_sha):
            raise ValueError('INVALID_OR_REORDERED_OVERLAY')
        if row['observation_index'] != i or 'weather_audit_v1' in row:
            raise ValueError('PARENT_INDEX_OR_OVERWRITE')
        result.append({**row, 'weather_audit_v1': patch['weather_audit_v1']})
    return result


def freeze(destination, report, parent=None):
    # Refuse all updates, even identical bytes. Never mutate prior freezes.
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('IMMUTABLE_DESTINATION_EXISTS')
    patches = [overlay(i) for i in range(TOTAL)]
    materialized = materialize(Path(parent).read_bytes(), patches) if parent else None
    destination.mkdir(parents=True, exist_ok=False)
    artifacts = {
        'comparison_reference_ledger_1845.jsonl': b''.join(map(encode, patches)),
        'independent_weather_audit_report.json': encode(report)}
    if materialized is not None:
        artifacts['comparison_ledger_1845.jsonl'] = b''.join(map(encode, materialized))
    for name, raw in artifacts.items():
        with (destination / name).open('xb') as stream:
            stream.write(raw)
    index = {'schema': 'WS6_WEATHER_APPEND_ONLY_FREEZE_V1',
             'status': 'BLOCKED_BY_DATA_SHADOW_ONLY',
             'parent_path': PARENT_PATH, 'parent_sha256': PARENT_SHA,
             'original_observations': TOTAL,
             'parent_bytes_rehashed_this_execution': parent is not None,
             'full_comparison_materialized': materialized is not None,
             'reference_semantics': 'parent SHA256 plus zero-based row index; all original fields inherited',
             'artifacts': {name: sha(raw) for name, raw in artifacts.items()},
             'production_promotion': False, 'postgame_scores': False}
    with (destination / 'freeze_index.json').open('xb') as stream:
        stream.write(encode(index))
    return {**index['artifacts'], 'freeze_index.json': sha(encode(index))}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report', required=True)
    ap.add_argument('--destination', required=True)
    ap.add_argument('--parent', help='Original immutable ledger, never regenerated')
    args = ap.parse_args()
    print(json.dumps(freeze(args.destination, parse(Path(args.report).read_bytes()),
                            args.parent), sort_keys=True))
