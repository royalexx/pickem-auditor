"""Offline WS1 repair and existing WS2 law execution, append-only research shadow.

Uses the authoritative WS1 pin, never re-collects or rewrites original evidence.
Book equivalence and independent acceptance are deliberately not inferred.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nfl_stat_definitions import combined_tackles_assists, COMPONENTS, VERSION as STAT_VERSION
from nfl_sunday_feature_store import canonical, sha, stamp, now, unchanged
from v2.nfl_marginal_shadow import fit_laws, MODEL_IDS, VERSION as MODEL_VERSION
VERSION='nfl-tackle-repair-v2.5.2'
FIELDS=COMPONENTS['tackles + assists']

def read(root,ref):
    path=Path(ref.get('raw_path',ref.get('path')))
    if not path.is_absolute():path=root/path
    b=path.read_bytes()
    if sha(b)!=ref['sha256']:raise ValueError('SOURCE_SHA_MISMATCH:'+str(path))
    return b

def jsonl(b):return [json.loads(x) for x in b.splitlines() if x.strip()]
def table(out,name,rows):
    b=b''.join(canonical(x) for x in rows)
    return {**unchanged(out/(name+'_'+sha(b)+'.jsonl'),b),'rows':len(rows)}
def csvrows(root,ref):return list(csv.DictReader(io.StringIO(read(root,ref).decode('utf-8-sig'))))

def snap_crosswalk(players,snaps,games,receipt,freeze):
    bridge=defaultdict(set)
    for p in players:
        if p.get('pfr_id') and p.get('gsis_id'):bridge[p['pfr_id']].add(p['gsis_id'])
    catalog={g['game_id']:g for g in games}
    rows={};reject=[]
    for r in snaps:
        ids=bridge.get(r.get('pfr_player_id'),set());g=catalog.get(r.get('game_id'))
        issue=None;ds=None
        try:
            raw=r.get('defense_snaps');ds=int(raw)
            if str(ds)!=str(raw) or ds<0:issue='INVALID_DEFENSIVE_SNAPS'
        except (ValueError,TypeError):issue='MISSING_OR_INVALID_DEFENSIVE_SNAPS'
        if len(ids)!=1:issue='MISSING_OR_AMBIGUOUS_PFR_GSIS'
        elif not g:issue='MISSING_CANONICAL_GAME'
        elif r.get('team') not in (g.get('home_team'),g.get('away_team')):issue='GAME_TEAM_MISMATCH'
        elif not g.get('gameday') or g['gameday']>='2026-11-15':issue='CURRENT_OR_FUTURE_GAME_EXCLUDED'
        elif not g.get('result'):issue='GAME_COMPLETION_UNVERIFIED'
        elif stamp(receipt['observed_received_at'])>stamp(freeze):issue='FUTURE_SOURCE'
        if issue:reject.append({'provider_player_id':r.get('pfr_player_id'),'game_id':r.get('game_id'),'reason':issue});continue
        pid=next(iter(ids));key=(pid,r['game_id'],r['team'])
        pct=r.get('defense_pct')
        try:
            pct=float(pct)
            if not 0<=pct<=1:pct=None
        except (ValueError,TypeError):pct=None
        row={'player_id':'gsis:'+pid,'provider_player_id':r['pfr_player_id'],'game_id':r['game_id'],
             'team':r['team'],'opponent':g['away_team'] if r['team']==g['home_team'] else g['home_team'],
             'season':g['season'],'week':g['week'],'game_date':g['gameday'],
             'defensive_snaps':ds,'defensive_snap_pct':pct,'special_teams_snaps_raw':r.get('st_snaps'),
             'source_available_at':receipt['observed_received_at'],'source_sha256':receipt['sha256'],
             'join_status':'EXACT_PROVIDER_ID_GAME_TEAM','original_record':r}
        if key in rows:
            if rows[key]!=row:raise ValueError('CONFLICTING_DUPLICATE_SNAP')
            reject.append({'provider_player_id':r['pfr_player_id'],'game_id':r['game_id'],'reason':'IDENTICAL_DUPLICATE_NOT_COUNTED'})
        else:rows[key]=row
    return list(rows.values()),reject

def run(root,out):
    root=root.resolve();out=out.resolve()
    if out.exists():raise ValueError('OUTPUT_ALREADY_EXISTS')
    out.mkdir(parents=True)
    base=root/'reports/nfl_20261115_prospective';ext=base/'market_extension_v2_5_1'
    frozen={p:sha(p.read_bytes()) for p in [base/'source_control/HANDOFF_PIN.json',base/'FORECAST_FEATURE_PIN.json',ext/'FEATURE_PIN.json']}
    pin=json.loads((ext/'FEATURE_PIN.json').read_bytes())
    refs=pin['tables']; hist=jsonl(read(root,refs['internal_tackle_evidence']))
    candidates=[p for p in jsonl(read(root,refs['player_stats'])) if p['normalized_market']=='tackles_assists']
    contracts=[c for c in jsonl(read(root,refs['original_contracts'])) if c['normalized_market']=='tackles_assists']
    source_pin=json.loads((base/'source_control/HANDOFF_PIN.json').read_bytes())
    manifest=read(root,{'path':str(base/source_pin['source_control_manifest_relative_path']),'sha256':source_pin['source_control_manifest_sha256']})
    freeze=now(); receipts=pin['new_public_source_receipts']
    sources={k:csvrows(root,v) for k,v in receipts.items() if v.get('raw_path')}
    # Every original history row remains present, with a classified result.
    history=[];causes=Counter();original=Counter(); source_hashes=Counter()
    for h in hist:
        raw=h['internal_components'];total=combined_tackles_assists(raw)
        if any(raw.get(k) is None for k in FIELDS):reason='MISSING_ORIGINAL_COMPONENT'
        elif total is None:reason='INVALID_ORIGINAL_COMPONENT'
        elif h.get('combined_total') is None:reason='EXPLICIT_NULL_ASSIGNMENT_PENDING_ACCOUNTING'
        else:reason='PREVIOUSLY_AVAILABLE'
        causes[reason]+=1;source_hashes[h['source_sha256']]+=1
        history.append({**h,'original_combined_total':h.get('combined_total'),'combined_total':total,
            'definition_version':STAT_VERSION,'source_count_valid':total is not None,
            'sportsbook_equivalence_verified':False,'gamebook_equivalence_verified':False,
            'repair_reason':reason})
    snaps,rejected=snap_crosswalk(sources['players'],sources['snaps2026'],sources['games2026'],receipts['snaps2026'],freeze)
    by_player=defaultdict(list)
    for h in history:
        if h['source_count_valid'] and h['game_date']<'2026-11-15' and stamp(h['source_available_at'])<=stamp(freeze):by_player[h['player_id']].append(h)
    for h in by_player.values():h.sort(key=lambda x:(x['game_date'],x['game_id']))
    indexed={(s['player_id'],s['game_id']):s for s in snaps}
    positions={c['player_id']:c['position'] for c in candidates}
    for h in history:
        s=indexed.get((h['player_id'],h['game_id']))
        h['defensive_snap_feature']=s
    coverage=[]
    for c in candidates:
        h=by_player.get(c['player_id'],[])
        reasons=[r for r in c['abstention_reasons'] if r not in ('TACKLE_ACCOUNTING_NOT_INDEPENDENTLY_CERTIFIED','INSUFFICIENT_OBSERVED_HISTORY')]
        if len(h)<3:reasons.append('INSUFFICIENT_VERIFIED_COMBINED_HISTORY')
        if stamp(c['event_start_at'])<=stamp(freeze):reasons.append('KICKOFF_PASSED')
        coverage.append({**c,'source_history_games':len(h),'valid_defensive_snap_history_games':sum((c['player_id'],x['game_id']) in indexed for x in h),
            'source_count_model_ready':not reasons,'source_count_abstention_reasons':sorted(set(reasons)),
            'sportsbook_certified':False,'settlement_definition':'NFLVERSE_THREE_COMPONENT_SOURCE_ONLY'})
    tables={'history':table(out,'history',history),'defensive_snaps':table(out,'snaps',snaps),
        'snap_rejections':table(out,'snap_rejections',rejected),'defender_coverage':table(out,'defender_coverage',coverage),
        'original_contracts':table(out,'original_contracts',contracts)}
    handoff={'schema':VERSION,'input_freeze_at':freeze,'stat_definition_version':STAT_VERSION,'tables':tables,
        'parent_pins':{str(p):v for p,v in frozen.items()},'source_manifest_sha256':sha(manifest),
        'source_receipts':receipts,'research_shadow_only':True,'release_authority':False,
        'official_gamebook_reconciliation':'UNVERIFIED','sportsbook_settlement_equivalence':'UNVERIFIED',
        'history_original_pregame_availability_verified':False}
    # A single feature pin for THIS version; canonical Sunday source pin is unchanged.
    handoff_ref=unchanged(out/'HANDOFF_PIN.json',canonical(handoff))
    ready={x['player_stat_id']:x for x in coverage};ledger=[];law_fail=Counter();generated=0
    for c in contracts:
        original[c['original_record'].get('source_certified',False)]+=1
        q=c['original_record'];p=ready.get(c['player_stat_id']);row={'original_contract':c,'candidate_id':c['candidate_id'],
            'quote_id':c['quote_id'],'stat_key':'tackles_assists','period':q['period'],'event_id':q['event_id'],
            'player_id':q['player_id'],'line':q['line'],'book':q['book'],'product_type':q.get('product_type'),
            'event_start_at':q['event_start_at'],'feature_pin_sha256':handoff_ref['sha256'],
            'input_freeze_at':freeze,'WS2':{},'WS3_O4':{'status':'ABSTAIN','reason':'REQUIRED_AUTHENTICATED_OPPONENT_PLAYS_AND_PARTICIPATION_PROJECTION_UNAVAILABLE'},
            'WS3_O4_W':{'status':'ABSTAIN','reason':'WEATHER_EFFECT_NOT_ESTIMATED'},
            'WS4_J1':{'status':'ABSTAIN','reason':'CERTIFIED_DEFENSIVE_RATE_EXPOSURE_ADAPTER_UNAVAILABLE'},
            'WS4_J2':{'status':'ABSTAIN','reason':'CERTIFIED_DEFENSIVE_RATE_EXPOSURE_ADAPTER_UNAVAILABLE'},
            'WS4_J3':{'status':'ABSTAIN','reason':'CERTIFIED_GAME_SCRIPT_PARAMETERS_UNAVAILABLE'},
            'legacy':{'status':'UNAVAILABLE'},'certification':'UNCERTIFIED','independent_acceptance':'PENDING'}
        reason=None
        if not q.get('source_certified') or not q.get('research_shadow_eligible'):reason='ORIGINAL_QUOTE_NOT_SOURCE_ELIGIBLE'
        elif not p:reason='PLAYER_STAT_ID_NOT_MAPPED'
        elif not p['source_count_model_ready']:reason='|'.join(p['source_count_abstention_reasons'])
        if not reason:
            h=by_player[p['player_id']];own=[x['combined_total'] for x in h]
            peers=[[x['combined_total'] for x in xs] for pid,xs in by_player.items() if pid!=p['player_id'] and positions.get(pid)==p['position']]
            try:
                laws,failed,diagnostics=fit_laws(own,peers,stat='tackles + assists')
                model=MODEL_IDS[3]
                if model not in laws:raise ValueError(failed.get(model,'BASELINE_UNAVAILABLE'))
                at=now()
                if stamp(at)>=stamp(q['event_start_at']):raise ValueError('KICKOFF_PASSED_AT_FORECAST')
                rec=laws[model].record(q['line'])
                row['WS2']={'status':'GENERATED_SOURCE_COUNT_SHADOW','model_id':model,'model_version':MODEL_VERSION,
                    'forecast_at':at,'model_training_cutoff_at':max(x['source_available_at'] for xs in by_player.values() for x in xs),
                    'history_last_game':h[-1]['game_date'],'law':rec,'diagnostics':diagnostics,
                    'fallback':'COMBINED_RATE_WITHOUT_SNAP_DENOMINATOR','conditional_on_appearance':True,
                    'limitation':'Rate uncertainty integrated; unmodeled role/exposure shifts remain. No estimated weather effect.',
                    'source_hashes':sorted(set(x['source_sha256'] for x in h))}
                generated+=1
            except (ValueError,KeyError) as e:reason=str(e)
        if reason:row['WS2']={'status':'ABSTAIN','reason':reason};law_fail[reason]+=1
        ledger.append(row)
    tables_out={'comparison_ledger':table(out,'comparison_ledger',ledger)}
    first=base/'simple_models/sunday_first_forecasts_v1/first_forecast_population.jsonl'
    old=[]
    if first.exists():
        for r in jsonl(first.read_bytes()):
            if r.get('original_contract',{}).get('stat')=='tackles + assists':old.append(r)
    report={'schema':VERSION,'generated_at':now(),'seed':20261115,'scope':'SOURCE_COUNT_REPAIR_NOT_SPORTSBOOK_CERTIFICATION',
        'root_causes':dict(causes),'historical_rows':len(hist),'distinct_history_players':len(by_player),
        'distinct_history_games':len({x['game_id'] for x in history}),'valid_combined_totals':sum(x['source_count_valid'] for x in history),
        'source_hash_row_counts':dict(source_hashes),'defender_candidates':len(candidates),'source_count_ready':sum(x['source_count_model_ready'] for x in coverage),
        'defenders_with_snap_history':sum(x['valid_defensive_snap_history_games']>0 for x in coverage),
        'snap_rows':len(snaps),'snap_rejections':dict(Counter(x['reason'] for x in rejected)),
        'original_quotes':len(contracts),'source_certified_quotes':sum(bool(c['original_record'].get('source_certified')) for c in contracts),
        'shadow_eligible_quotes':sum(bool(c['original_record'].get('research_shadow_eligible')) for c in contracts),
        'WS2_source_count_shadow_forecasts':generated,'WS2_abstentions':dict(law_fail),'WS3_O4_forecasts':0,'WS4_J1_J2_J3_forecasts':0,
        'sportsbook_certified_forecasts':0,'independently_accepted_forecasts':0,
        'frozen_first_forecast_file':{'path':str(first),'sha256':sha(first.read_bytes())} if first.exists() else None,
        'old_tackle_rows_by_top_level_stat':len(old),'old_tackle_row_schema':sorted(old[0]) if old else [],
        'handoff':handoff_ref,'outputs':tables_out,
        'historical_performance':'UNAVAILABLE: original pregame source availability not verified; no matched frozen-baseline evaluation claimed',
        'rollback':'Do not consume this version pin; original pins and predictions remain unchanged.'}
    for p,digest in frozen.items():assert sha(p.read_bytes())==digest
    report['original_pin_immutability_passed']=True
    receipt=unchanged(out/'EXECUTION_RECEIPT.json',canonical(report))
    print(json.dumps({'receipt':receipt,'report':report},sort_keys=True))
    return report
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args();run(args.root,args.out)
