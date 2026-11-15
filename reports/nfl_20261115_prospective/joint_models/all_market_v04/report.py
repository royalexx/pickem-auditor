"""Versioned WS6 ledger and independently reproducible coverage aggregation."""
import collections,datetime as dt,hashlib,json,pathlib,sys
import numpy as np
J=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(J))
import ws4_original_contract_adapter as ad
from all_market_v04.conditional import MARKETS
from all_market_v04.execute import MAP
NORMAL={'completions':'pass_completions','rushing_attempts':'rush_attempts','targets':'receiving_targets'}

def report():
    root=J/'all_market_v04/frozen'
    objs=[]
    for p in root.glob('*.json'):
        if '.' in p.stem:continue
        o=json.loads(p.read_bytes())
        if o.get('schema')=='PA_WS4_ALL_MARKET_EVENT_v04':objs.append((p,o))
    # Latest prospective version per event; keep earlier canary bytes intact.
    latest={}
    rejected_versions={'ws4_all_market_v0.4.1':'CURRENT_HISTORY_TRAINING_CUTOFF_METADATA_NOT_ADVANCED'}
    for p,o in objs:
        if o.get('model_version') in rejected_versions:continue
        eid=o['input_packet']['events'][0]['event_id']
        if eid not in latest or o['forecast_created_at']>latest[eid][1]['forecast_created_at']:latest[eid]=(p,o)
    m=ad.load_inputs(ad.ROOT)[0]
    original=m['candidates'];coverage=[];rows=[];distribution_counts=collections.Counter();abstention_counts=collections.Counter();composites=[]
    for p,o in latest.values():
        for r in o['distributions']:
            distribution_counts[(r['model_id'],r['stat_key'])]+=1
            if 'composite_diagnostics' in r:composites.append(dict(event_id=r['event_id'],model_id=r['model_id'],player_id=r['player_id'],stat_key=r['stat_key'],**r['composite_diagnostics']))
        e=o['input_packet']['events'][0]
        for miss in o['player_abstentions']:
            stats=['rushing_attempts','rushing_yards','passing_rushing_yards'] if miss['reason'].startswith('QB_RUSH_HISTORY') else ['tackles_assists'] if 'DEFENDER' in miss['reason'] else (['pass_attempts','completions','passing_yards','rushing_attempts','rushing_yards','passing_rushing_yards'] if miss['position']=='QB' else ['rushing_attempts','rushing_yards','targets','receptions','receiving_yards','rushing_receiving_yards'])
            for model in ('J1','J2'):
                for stat in stats:abstention_counts[(model,stat)]+=1
    for model in ('J1','J2','J3'):
        byid={r['candidate_id']:(p,o,r) for p,o in latest.values() for r in o['contracts'] if r['model_id']==model}
        for c in original:
            row=dict(candidate_id=c['candidate_id'],model_id=model,normalized_market=NORMAL.get(MAP.get(c['stat']),MAP.get(c['stat'])),event_id=c['event_id'],player_id=c['player_id'],player_id_namespace='espn',status='ABSTAIN',original_record=c.get('original_quote'),original_source_validation_failure=c.get('source_validation_failure'),source_sha256=c.get('source_sha256'),source_received_at=c.get('source_received_at'),quote_id=c.get('quote_id'),line=c.get('line'),period=c.get('period'))
            if c['candidate_id'] in byid:
                p,o,r=byid[c['candidate_id']];row.update(r);row['forecast_file_sha256']=p.stem
                row['original_record']=c['original_quote']
                e=o['input_packet']['events'][0]
                row['gsis_id']=next((p['gsis_id'] for par in e['all_market_parameters'].values() for p in par['players'] if p['player_id']==c['player_id']),None)
            else:row['reason']='NO_CERTIFIED_PREGAME_GAME_SCRIPT_PARAMETERS' if model=='J3' else ('MISSING_EVENT_START' if not c.get('event_start_at') else ('KICKOFF_ALREADY_CLOSED' if ad.parse_time(c['event_start_at'])<=ad.now() else 'NO_VALID_EVENT_ROLE_PARAMETERS'))
            rows.append(row)
        for market in MARKETS:
            cs=[r for r in rows if r['model_id']==model and r['normalized_market']==NORMAL.get(market,market)]
            n=distribution_counts[(model,market)]
            coverage.append(dict(model=model,market=NORMAL.get(market,market),distributions=n,
               player_stat_abstentions=abstention_counts[(model,market)] if model!='J3' else sum(distribution_counts[('J1',market)]+abstention_counts[('J1',market)] for _ in [0]),
               original_contracts=len(cs),contract_forecasts=sum(r['status']=='FORECAST' for r in cs),contract_abstentions=sum(r['status']!='FORECAST' for r in cs)))
    report=dict(schema='PA_WS4_WS6_ALL_MARKET_HANDOFF_v04.1',generated_at=ad.now().isoformat(),classification='UNCERTIFIED_SHADOW',
      forecast_files=[dict(path=str(p.relative_to(J)),sha256=p.stem,created_at=o['forecast_created_at'],kickoff=o['input_packet']['events'][0]['event_start_at']) for p,o in latest.values()],
      rejected_versions=rejected_versions,rejected_files=[dict(path=str(p.relative_to(J)),sha256=p.stem,reason=rejected_versions[o['model_version']]) for p,o in objs if o.get('model_version') in rejected_versions],coverage=coverage,composite_diagnostics=composites,weather_neutral_distributions=sum(distribution_counts.values()),weather_estimated_distributions=0,
      original_contract_observations=len(original),contract_model_rows=len(rows),original_event_exclusions=['401873053'],
      limitations=['J3 and defensive T+A blocked by missing evidence','No marginal or joint accuracy promotion evidence','Existing v031 predictions remain separately frozen controls'],
      frozen_v031_files={str(p.relative_to(J)):ad.digest(p.read_bytes()) for p in (J/'real_original_qb_attempts_multievent_v031').glob('*.json')})
    def seal(obj,suffix):
        raw=ad.canonical(obj)+b'\n';p=root/(ad.digest(raw)+suffix)
        with p.open('xb') as f:f.write(raw)
        return dict(path=str(p.relative_to(J)),sha256=ad.digest(raw))
    cov=seal(report.pop('composite_diagnostics'),'.covariance.json');report['composite_covariance_file']=cov
    report['source_hashes']={'ws1':ad.CANONICAL_WS1,'stats2025':ad.HISTORY_2025_SHA,'crosswalk':ad.CROSSWALK_SHA}
    report['current_history_source_hashes']=sorted({r['sha256'] for p,o in latest.values() for par in o['input_packet']['events'][0]['all_market_parameters'].values() for r in par.get('current_source_receipts',[])})
    report['model_versions']=sorted({o['model_version'] for p,o in latest.values()})
    report['team_draw_conservation_checks']=sum(d['conservation_checks'] for p,o in latest.values() for d in o['draw_records'].values())
    report['parameter_versions']=[dict(event_id=o['input_packet']['events'][0]['event_id'],sha256=o.get('parameter_sha256'),model_version=o['model_version']) for p,o in latest.values()]
    ledger=seal(rows,'.ledger.json');report['original_contract_ledger']=ledger
    receipt=seal(report,'.summary.json')
    print(json.dumps(dict(receipt=receipt,coverage=coverage,files=len(latest),weather_neutral=report['weather_neutral_distributions'],weather_estimated=0)))
    return report

if __name__=='__main__':report()
