"""Exact joins for separately registered fixed research transformations.

Input is a hash-pinned bound forecast export (not a fitted calibrator). Every
row must disclose the original upstream forecast/model/feature IDs and times.
No row is treated as the original production 60/40 forecast.
"""
from collections import Counter
from pathlib import Path
import json
from . import shadow as s
from .native_ws1 import EXACT, CANONICAL_SHA


def load(path, expected_sha, *, feature_path, feature_sha):
    raw, feature = Path(path).read_bytes(), Path(feature_path).read_bytes()
    if s.sha(raw) != expected_sha or s.sha(feature) != feature_sha:
        raise ValueError('frozen_forecast_or_feature_hash_mismatch')
    packet = json.loads(raw)
    if packet.get('schema') != 'ws5-bound-statistical-forecast-v1':
        raise ValueError('unrecognized_frozen_forecast_export_schema')
    if packet.get('feature_sha256') != feature_sha:
        raise ValueError('forecast_feature_dependency_conflict')
    if packet.get('source_manifest_sha256') != CANONICAL_SHA:
        raise ValueError('not_corrected_canonical_source_dependency')
    packet['artifact_sha256'] = expected_sha
    return packet


def bind_ws2(index_path, expected_sha, *, source_root):
    """Read actual nfl_ws2_live INDEX/forecast_rows, preserving native provenance.

    INDEX is WS2's create-once commit marker. Partial writes are never admitted.
    A content-addressed row ID is disclosed as such, not an originally assigned ID.
    """
    root = Path(source_root).resolve()
    path = Path(index_path).resolve()
    raw = path.read_bytes()
    if s.sha(raw) != expected_sha:
        raise ValueError('WS2_index_hash_mismatch')
    index = json.loads(raw)
    if index.get('source_manifest_sha256') != CANONICAL_SHA:
        raise ValueError('WS2_wrong_canonical_source')
    rows_raw = (path.parent/'forecast_rows.json').read_bytes()
    if s.sha(rows_raw) != index['forecast_rows_sha256']:
        raise ValueError('WS2_forecast_rows_hash_mismatch')
    ref = index['feature_packet']
    feature_path = (root/ref['path']).resolve()
    if not feature_path.is_relative_to(root):
        raise ValueError('WS2_feature_path_escape')
    feature_raw = feature_path.read_bytes()
    if s.sha(feature_raw) != ref['sha256']:
        raise ValueError('WS2_feature_packet_hash_mismatch')
    feature = json.loads(feature_raw)
    if feature.get('owner') != 'workstream1' or feature['input_freeze_at'] != index['feature_freeze_at']:
        # Compare instants, since WS2 normalizes UTC spelling.
        if feature.get('owner') != 'workstream1' or s.timestamp(feature['input_freeze_at']) != s.timestamp(index['feature_freeze_at']):
            raise ValueError('WS2_feature_freeze_conflict')
    model = 'S2-ew-empirical-hl4-v1'
    bound = []
    for native in json.loads(rows_raw):
        pred = native['models'].get(model, {})
        if pred.get('status') != 'forecast':
            continue
        c = native['original_contract']
        triple = {k:pred.get('q_'+k) for k in ('over','under','push')}
        if all(v is None for v in triple.values()):
            triple = None
        conditional = pred['p_over_given_no_push']
        # Statistical raw records are immutable dependencies, not 60/40 controls.
        bound.append({**{k:c.get(k) for k in (*EXACT,'quote_id')},
            'contract_id':c['candidate_id'],'event_start_at':c['event_start_at'],
            'family':'WS2_S2','model_id':model,
            'forecast_id':'sha256:'+s.sha(s.canonical(native)),
            'forecast_id_semantics':'content_addressed_original_WS2_row',
            'forecast_at':native['forecast_created_at'],
            'input_freeze_at':index['feature_freeze_at'],
            'feature_available_at':feature['input_freeze_at'],
            'feature_sha256':ref['sha256'],
            'model_training_cutoff_at':index['model_training_cutoff_at'],
            'conditional_no_push':{'over':conditional,'under':1-conditional},
            'unconditional':triple,'stat_support':'integer',
            'upstream_model_code_sha256':index['model_code_sha256'],
            'upstream_parameters':index['parameters']})
    return {'schema':'ws5-bound-statistical-forecast-v1',
        'artifact_sha256':s.sha(rows_raw),'feature_sha256':ref['sha256'],
        'source_manifest_sha256':CANONICAL_SHA,'forecasts':bound,
        'upstream_index_sha256':expected_sha,'upstream_index':index,
        'binding_code_sha256':s.sha(Path(__file__).read_bytes())}


def transform(packet, market_report, *, now):
    """Return a NEW ledger. Never modify the previously frozen C2 ledger."""
    clock = s.timestamp(now)
    report = s.build({'input_freeze_at': now}, {}, [], [], now=now)
    report['registry'] = {}
    report['forecasts'] = []
    report['dependency_graph'] = {}
    report['upstream_provenance'] = {k:v for k,v in packet.items() if k != 'forecasts'}
    market = {r['contract_id']: r for r in market_report['forecasts']
              if r['candidate'] == 'C2' and r['status'] == 'forecast'}
    records = packet['forecasts']
    counts = Counter((r.get('contract_id'), r.get('model_id')) for r in records)
    for row in records:
        family = row.get('family')
        model = row.get('model_id')
        # Only unblended statistical inputs; S6/S7 are not independent new models.
        if family not in ('WS2_S2', 'WS3_OPPORTUNITY') or not isinstance(model, str) or not model:
            raise ValueError('unregistered_upstream_statistical_family')
        names = ('C3','C4','C4_sensitivity_050','C4_sensitivity_090','C7')
        for base in names:
            name = base+'_'+family+'_v1'
            config = {'base_configuration': s.CONFIG[base], 'upstream_model_id': model,
                      'upstream_family': family, 'production_control': False}
            model_hash = s.sha(s.canonical({'configuration':config,'sources':report['source_code_sha256'],
                'transform_code_sha256':s.sha(Path(__file__).read_bytes()),
                'upstream_artifact_sha256':packet['artifact_sha256'],'feature_sha256':packet['feature_sha256'],
                'upstream_index_sha256':packet.get('upstream_index_sha256')}))
            registry_key = name+'_'+s.sha(model.encode())[:12]
            report['registry'][registry_key] = {'model_id':name+':'+model_hash,'configuration':config}
            result = dict(candidate=registry_key,model_id=name+':'+model_hash,
                          contract_id=row.get('contract_id'),status='abstain')
            reference = None
            try:
                if counts[(row.get('contract_id'),model)] != 1:
                    raise ValueError('duplicate_upstream_forecast_identity')
                start = s.timestamp(row['event_start_at'])
                freeze, forecast = s.timestamp(row['input_freeze_at']), s.timestamp(row['forecast_at'])
                if not s.timestamp(row['model_training_cutoff_at']) <= freeze <= forecast <= clock < start:
                    raise ValueError('upstream_or_current_forecast_not_pregame')
                if s.timestamp(row['feature_available_at']) > freeze:
                    raise ValueError('features_after_upstream_freeze')
                if row['feature_sha256'] != packet['feature_sha256'] or not row.get('forecast_id'):
                    raise ValueError('missing_or_conflicting_upstream_dependency')
                reference = market.get(row['contract_id'])
                if reference is None:
                    raise ValueError('no_valid_frozen_market_reference')
                if any(row.get(k) != reference['identity'].get(k) for k in (*EXACT,'quote_id')):
                    raise ValueError('upstream_exact_quote_identity_conflict')
                if s.timestamp(reference['event_start_at']) != start:
                    raise ValueError('upstream_kickoff_conflict')
                p = row['conditional_no_push']['over']
                if not s.proper_pair(row['conditional_no_push']):
                    raise ValueError('noncomplementary_upstream_conditional')
                triple = row.get('unconditional')
                push = None
                if triple is not None:
                    vals = [triple.get(k) for k in ('over','under','push')]
                    if not all(s.calibration.finite_probability(v) for v in vals) or abs(sum(vals)-1)>1e-8 or vals[2]>=1:
                        raise ValueError('invalid_upstream_three_way')
                    push = vals[2]
                    if abs(triple['over']/(1-push)-p)>1e-8:
                        raise ValueError('conflicting_upstream_probability_forms')
                    if row.get('stat_support') == 'integer' and row['line']%1 and push:
                        raise ValueError('impossible_fractional_line_push')
                prob = s.probabilities(p,reference['conditional_no_push']['over'],{})[base]
                result.update(status='forecast',event_id=row['event_id'],identity=reference['identity'],
                    event_start_at=row['event_start_at'],forecast_at=now,input_freeze_at=row['input_freeze_at'],
                    conditional_no_push={'over':prob,'under':1-prob},
                    unconditional=None if push is None else {'over':(1-push)*prob,'under':(1-push)*(1-prob),'push':push},
                    push_policy='unconditional_unavailable' if push is None else 'upstream_push_mass_preserved',
                    upstream_forecast_id=row['forecast_id'],upstream_model_id=model,
                    upstream_forecast_at=row['forecast_at'],feature_sha256=packet['feature_sha256'],
                    upstream_artifact_sha256=packet['artifact_sha256'],
                    model_market_gap=abs(p-reference['conditional_no_push']['over']))
            except (KeyError,TypeError,ValueError) as exc:
                result['reason']=str(exc)
            report['dependency_graph'][registry_key] = [packet['artifact_sha256'],packet['feature_sha256'],reference['model_id'] if reference else 'C2_unavailable']
            report['forecasts'].append(result)
    report['coverage']={name:{'input_contracts':sum(r['candidate']==name for r in report['forecasts']),
        'forecast_contracts':sum(r['candidate']==name and r['status']=='forecast' for r in report['forecasts']),
        'abstentions':dict(Counter(r['reason'] for r in report['forecasts'] if r['candidate']==name and r['status']=='abstain'))}
        for name in report['registry']}
    return report


def main(argv=None):
    import argparse
    from datetime import datetime, timezone
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('forecast', 'forecast-sha256', 'features', 'features-sha256', 'market-ledger', 'market-ledger-sha256', 'out'):
        parser.add_argument('--'+key, required=True)
    args = parser.parse_args(argv)
    packet = load(args.forecast, args.forecast_sha256, feature_path=args.features, feature_sha=args.features_sha256)
    raw = Path(args.market_ledger).read_bytes()
    if s.sha(raw) != args.market_ledger_sha256:
        raise ValueError('market_ledger_hash_mismatch')
    market = json.loads(raw)
    if market.get('input_manifest_sha256') != CANONICAL_SHA:
        raise ValueError('market_not_from_corrected_source')
    out = Path(args.out).resolve()
    if not out.is_relative_to((Path.cwd()/'calibration_models').resolve()):
        raise ValueError('output_must_be_in_calibration_models')
    report = transform(packet, market, now=datetime.now(timezone.utc).isoformat())
    report['market_ledger_sha256'] = args.market_ledger_sha256
    s.finalize_emission(report)
    print(json.dumps({'sha256':s.write_exclusive(out,report),'coverage':report['coverage']},sort_keys=True))


if __name__ == '__main__':
    main()
