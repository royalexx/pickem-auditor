"""Authenticated WS1 eleven-market roster adapter; no new collector."""
import csv
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from . import models as m
from . import ws1_feature_adapter as v1
from .full_market_v2 import FullMarketModel,MODELS,MARKETS

VERSION='ws1-full-market-adapter-v2'
EXT_PATH='reports/nfl_20261115_prospective/market_extension_v2_5_1/FEATURE_PIN.json'
EXT_SHA='c3ec93c78fcae413f66afe431f817f4d986f0fd1e884c665caefc5c7a3ed230c'

def build(root,now):
    p,meta=v1.build(root,now) # original pin, original bytes, original cutoffs
    ext=m.strict_json(v1.checked(root,EXT_PATH,EXT_SHA))
    freeze=ext['feature_freeze_at'];m.require(m.stamp(freeze)<=m.stamp(now),'extension_freeze_future')
    m.require(ext['previous_feature_pin']['sha256']==v1.PIN,'extension_parent_pin')
    checks=[];tables={}
    for name,d in ext['tables'].items():
        b=v1.checked(root,d['path'],d['sha256']);rs=[m.strict_json(x) for x in b.splitlines()]
        m.require(len(rs)==d['rows'],'extension_row_count');tables[name]=rs;checks.append(d)
    d=ext['expanded_manifest'];v1.checked(root,d['path'],d['sha256']);checks.append(d)
    for d in ext['source_evidence']:
        v1.checked(root,d['path'],d['sha256']);checks.append(d)
        m.require(m.stamp(d['source_available_at'])<=m.stamp(freeze),'extension_source_future')
    for d in ext['new_public_source_receipts'].values():
        v1.checked(root,d['raw_path'],d['sha256']);checks.append(d)
        m.require(m.stamp(d['observed_received_at'])<=m.stamp(freeze),'extension_receipt_future')
    oldpin,_,oldt,_=v1.authenticate(root)
    # Original source-backed roster/expected starter evidence; no guaranteed appearance.
    availability={(r['event_id'],r['player_id']):r for r in oldt['pregame_roster_availability']}
    bridge=defaultdict(set)
    d=ext['new_public_source_receipts']['players']
    for r in csv.DictReader(v1.checked(root,d['raw_path'],d['sha256']).decode().splitlines()):
        if r.get('espn_id') and r.get('gsis_id'):bridge[r['espn_id'].removesuffix('.0')].add(r['gsis_id'])
    events={e['game_id']:e for e in p['events']};roster={};rejects={}
    for s in tables['player_stats']:
        key=(s['game_id'],s['player_id'].removeprefix('gsis:'))
        reasons=list(s['abstention_reasons'])
        if s['game_id'] not in events:reasons.append('KICKOFF_PASSED_OR_UNVERIFIED_EVENT')
        if not s['model_input_ready']:reasons.append('WS1_INPUT_NOT_READY')
        if bridge.get(s['espn_player_id'])!={key[1]}:reasons.append('IDENTITY_CONFLICT')
        a=availability.get((s['game_id'],s['espn_player_id']))
        if a is None:reasons.append('MISSING_ORIGINAL_ROSTER_EVIDENCE')
        expected=a is not None and a['expected_qb_starter_source_backed'] is True
        if s['position']=='QB' and not expected:reasons.append('QB_STARTER_NOT_VERIFIED')
        if reasons:rejects[s['player_stat_id']]=reasons;continue
        e=events[s['game_id']];team=v1.team_id(s['team'])
        m.require(team in (e['home'],e['away']) and s['event_start_at']==e['event_start'],'stat_event_join')
        r=dict(game_id=key[0],player_id=key[1],team=team,position=s['position'],source_id=a['roster_receipt_sha256'],
               status='uncertain',participation_probability=1.,expected_starter=expected,starter_probability=1. if expected else None)
        m.require(key not in roster or roster[key]==r,'conflicting_roster');roster[key]=r
    # Read authentic weekly player observations for the extended roster, not just quoted players.
    tm={(h['game_id'],h['team']):h for h in p['team_history']}
    histories={(h['game_id'],h['player_id']):h for h in p['player_history']}
    d=ext['new_public_source_receipts']['stats2026']
    mapping={'pass_attempts':'attempts','targets':'targets','receptions':'receptions','receiving_yards':'receiving_yards',
             'carries':'carries','rushing_yards':'rushing_yards','completions':'completions','passing_yards':'passing_yards'}
    ids={r['player_id'] for r in roster.values()}
    for h in csv.DictReader(v1.checked(root,d['raw_path'],d['sha256']).decode().splitlines()):
        key=(h['game_id'],h['team']);pk=(h['game_id'],h['player_id'])
        if h['player_id'] not in ids or key not in tm or pk in histories:continue
        vals={k:v1.numeric(h.get(src)) for k,src in mapping.items()}
        if not any((vals[k] or 0)>0 for k in ('pass_attempts','carries','targets','receptions')):continue
        t=tm[key];row={k:None for k in m.PLAYER_FIELDS}
        row.update(vals,game_id=h['game_id'],player_id=h['player_id'],team=h['team'],position=h['position'],season=2026,
                   week=t['week'],end_at=t['end_at'],source_id=d['sha256'],state='played')
        histories[pk]=row
    p['roster']=list(roster.values());p['player_history']=list(histories.values())
    p['manifest']={'training_cutoff_at':freeze,'input_freeze_at':freeze}
    # Exact original contracts only; absent quotes never get substitute thresholds.
    accepted={(r['game_id'],r['player_id']) for r in p['roster']}
    p['contracts']=[c for c in p['contracts'] if (c['game_id'],c['player_id']) in accepted]
    m.validate(p)
    meta.update(version=VERSION,extension_pin_sha256=EXT_SHA,extension_checks=checks,stat_source_rows=tables['player_stats'],
                stat_source_rejections=rejects,original_checks=meta['checks'])
    return p,meta

def execute(root,canary=False):
    now=datetime.now(timezone.utc).isoformat();p,meta=build(root,now)
    if canary:
        # Simulate the entire authentic team roster to conserve allocation, then select one player.
        c=next(c for c in p['contracts'] if c['stat']=='pass attempts')
        p['events']=[e for e in p['events'] if e['game_id']==c['game_id']]
        p['roster']=[r for r in p['roster'] if r['game_id']==c['game_id']]
        p['contracts']=[c]
    report=FullMarketModel(p,8192).run()
    if canary:
        report['player_stat_rows']=[r for r in report['player_stat_rows'] if r['player_id']==c['player_id']]
        m.require(any(r['status']=='forecast' and r['market']=='passing_rushing_yards' for r in report['player_stat_rows']),'canary_composite_failed')
    else:
        # Preserve WS1 rejection denominators for each supported model/market.
        from .full_market_v2 import eligible
        emitted={(r['game_id'],r['player_id'],r['model'],r['market']) for r in report['player_stat_rows']}
        for s in meta['stat_source_rows']:
            for i in range(1,5):
                key=(s['game_id'],s['player_id'].removeprefix('gsis:'),MODELS[i],s['normalized_market'])
                if key in emitted or not eligible(i,s['position'],s['normalized_market']):continue
                report['player_stat_rows'].append(dict(game_id=key[0],player_id=key[1],model=key[2],market=key[3],team=s['team'],
                    variant='neutral',status='abstain',reason=';'.join(meta['stat_source_rejections'].get(s['player_stat_id'],['MODEL_DEPENDENCY_UNAVAILABLE']))))
        present={(r['contract']['contract_id'],r['model']) for r in report['contract_rows']}
        for c in meta['originals']:
            for model in MODELS:
                if (c['candidate_id'],model) not in present:
                    report['contract_rows'].append(dict(contract={'contract_id':c['candidate_id'],'original_contract':c},model=model,
                        market=None,variant='neutral',status='abstain',reason='ADAPTER_EXCLUSION:'+','.join(meta['rejections'].get(c['candidate_id'],['WS1_INPUT_NOT_READY']))))
    report['forecast_completed_at']=datetime.now(timezone.utc).isoformat()
    for e in p['events']:m.require(m.stamp(report['forecast_completed_at'])<m.stamp(e['event_start']),'completed_after_kickoff')
    report['adapter_version']=VERSION
    report['adapter_audit']={k:v for k,v in meta.items() if k not in {'originals','stat_source_rows'}}
    report['input_packet_sha256']=m.sha(m.canonical(p))
    report['counts']=[dict(model=model,market=market,status=status,n=n) for (model,market,status),n in sorted(Counter((r['model'],r['market'],r['status']) for r in report['player_stat_rows']).items())]
    report['stage']='single_player_canary' if canary else 'full_eligible_execution'
    receipt=m.freeze_output(report,Path(root)/'reports/nfl_20261115_prospective/opportunity_models/full_market_v2')
    out=Path(receipt['directory'])
    with (out/'adapter_packet.json').open('xb') as f:f.write(m.canonical(p))
    # Separate populations, exact source original retained in contract rows for WS6.
    for name,rows in [('player_stat_distributions',report['player_stat_rows']),('original_contract_evaluations',report['contract_rows'])]:
        with (out/(name+'.jsonl')).open('xb') as f:
            for row in rows:f.write(m.canonical(row))
    summary={'receipt':receipt,'counts':report['counts'],'teams':len(report['team_opportunities']),
             'contract_forecasts':dict(Counter(r['model'] for r in report['contract_rows'] if r['status']=='forecast')),
             'unique_contracts_forecast':len({r['contract']['contract_id'] for r in report['contract_rows'] if r['status']=='forecast'}),
             'neutral_stat_forecasts':dict(Counter(r['model'] for r in report['player_stat_rows'] if r['status']=='forecast')),
             'weather_forecasts':0,'completed_at':report['forecast_completed_at'],
             'handoff_files':{f.name:m.sha(f.read_bytes()) for f in out.glob('*.jsonl')}}
    with (out/'SUMMARY.json').open('xb') as f:f.write(m.canonical(summary))
    return summary
