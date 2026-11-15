"""Append-only WS6 export. Does not read or change existing comparison ledgers."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import json
from . import models as m
from .ws1_feature_adapter import MANIFEST,PIN,checked

def export(root,directory,run_id,prior_reports=()):
    root=Path(root);d=Path(directory);report=json.loads((d/'report.json').read_bytes())
    assert m.sha((d/'report.json').read_bytes())==d.name
    pin=json.loads(checked(root,'reports/nfl_20261115_prospective/FORECAST_FEATURE_PIN.json',PIN))
    native=json.loads(checked(root,pin['canonical_source_manifest_path'],MANIFEST))
    originals={c['candidate_id']:c for c in native['candidates']}
    choices={}
    source_reports=[(d,run_id,report)]
    for directory,prior_run in prior_reports:
        path=Path(directory);old=json.loads((path/'report.json').read_bytes())
        assert m.sha((path/'report.json').read_bytes())==path.name
        source_reports.append((path,prior_run,old))
    for path,rid,rep in sorted(source_reports,key=lambda x:x[2]['forecast_completed_at']):
        for row in rep['rows']:
            if row['status']=='forecast':choices.setdefault((row['contract']['contract_id'],row['model']),(row,rep,path.name,rid))
    rows=[]
    for r in report['rows']:
        r,origin,origin_sha,origin_run=choices.get((r['contract']['contract_id'],r['model']),(r,report,d.name,run_id))
        cid=r['contract']['contract_id'];c=originals[cid]
        rows.append({'original_contract_id':cid,'original_contract':c,'model_id':r['model'],
            'status':r['status'],'reason_codes':r.get('reason_codes',[r['reason']] if r.get('reason') else []),
            'forecast_at':origin['forecast_at'] if r['status']=='forecast' else None,
            'forecast_completed_at':origin['forecast_completed_at'] if r['status']=='forecast' else None,
            'event_start_at':c.get('event_start_at'),'feature_pin_sha256':PIN,'source_manifest_sha256':MANIFEST,
            'model_training_cutoff_at':report['training_cutoff_at'],'input_freeze_at':report['input_freeze_at'],
            'probabilities':r.get('probabilities_conditional'),'conditioning':r.get('conditioning'),
            'expected_stat':r.get('expected_stat'),'variance_stat':r.get('variance_stat'),
            'predictive_distribution':r.get('predictive_distribution_conditional'),
            'mc_standard_error_bound':r.get('max_mc_standard_error'),
            'dnp_probability':None,'product_terms_verified':False,'release_authority':False,
            'model_output_sha256':origin_sha,'deepnote_run_id':origin_run})
    assert len(rows)==1845*5 and len({(r['original_contract_id'],r['model_id']) for r in rows})==len(rows)
    data=b''.join(m.canonical(r) for r in rows)
    dest=d/('first_forecasts.jsonl' if prior_reports else 'ws6_handoff.jsonl')
    with dest.open('xb') as f:f.write(data)
    ix={'schema':'ws3-ws6-research-handoff-v1','created_at':datetime.now(timezone.utc).isoformat(),
        'deepnote_run_id':run_id,'original_contracts':1845,'model_contract_rows':len(rows),
        'model_counts':[{ 'model':model,'status':status,'n':n} for (model,status),n in sorted(Counter((r['model_id'],r['status']) for r in rows).items())],
        'report_sha256':d.name,'packet_sha256':report['adapter_packet_sha256'],'code_files_sha256':report['code_files_sha256'],
        'ws6_handoff_sha256':m.sha(data),'ws6_handoff_path':str(dest.relative_to(root)),
        'source_manifest_sha256':MANIFEST,'feature_pin_sha256':PIN,
        'first_forecast_at':min(x['forecast_at'] for x in rows if x['status']=='forecast'),
        'last_forecast_completed_at':max(x['forecast_completed_at'] for x in rows if x['status']=='forecast'),
        'source_reports':[{'report_sha256':path.name,'run_id':rid,'packet_sha256':rep['adapter_packet_sha256'],'code_files_sha256':rep['code_files_sha256']} for path,rid,rep in source_reports],
        'team_distributions':len(report['team_opportunities']),'coverage':report['coverage'],
        'limitations':report['adapter_audit']['conditional_assumption'],'production_modified':False,
        'existing_ws6_comparison_modified':False,'numerical_audit':report['numerical_audit']}
    with (d/('FIRST_FORECAST_INDEX.json' if prior_reports else 'WS6_INDEX.json')).open('xb') as f:f.write(m.canonical(ix))
    print(json.dumps(ix))
    return ix
