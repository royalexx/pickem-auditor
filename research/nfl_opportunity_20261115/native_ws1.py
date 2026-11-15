"""Consume the actual WS1 source-control manifest without collecting or recertifying.

The current native handoff contains quotes/roster source lineage but no frozen
team/player opportunity training tables. Retain every original row and abstain;
never fabricate training cutoffs, probabilities, DNP rules or model controls.
"""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from .models import DAY, MODELS, VERSION, GateError, canonical, require, sha, stamp, freeze_output, strict_json

NATIVE_SCHEMA='nfl_20261115_source_control_v1'

def consume(path, expected_sha, source_root, now):
    raw=Path(path).read_bytes()
    require(sha(raw)==expected_sha,'manifest_hash_mismatch')
    m=strict_json(raw)
    require(m.get('schema')==NATIVE_SCHEMA and m.get('date')==DAY,'wrong_native_ws1_schema')
    require(m.get('handoff',{}).get('source_control_immutable') is True,'not_immutable_ws1_handoff')
    require(m.get('runtime',{}).get('source_owner')=='NFL_SUNDAY_WS1_ONLY','wrong_source_owner')
    freeze=stamp(m.get('input_freeze_at')); now=stamp(now)
    require(freeze<=now,'native_freeze_in_future')
    source_root=Path(source_root).resolve()
    checks=[]
    for name,s in sorted(m.get('sources',{}).items()):
        reason=None
        try:
            require(isinstance(s.get('archive_path'),str),'missing_source_path')
            target=(source_root/s['archive_path']).resolve()
            require(target.is_relative_to(source_root) and target.is_file(),'missing_original_source_bytes')
            require(sha(target.read_bytes())==s.get('sha256'),'original_source_hash_mismatch')
            require(stamp(s.get('source_received_at'))<=freeze,'source_after_freeze')
            require(s.get('source_bytes_verified') is True,'WS1_source_bytes_unverified')
        except GateError as exc:
            reason=str(exc)
        checks.append({'source':name,'sha256':s.get('sha256'),'status':'verified_bytes_and_receipt_clock' if reason is None else 'blocked',
                       'reason':reason,'publication_truth_verified':s.get('source_publication_truth_verified') is True})
    candidates=m.get('candidates')
    require(isinstance(candidates,list),'missing_native_candidate_universe')
    require(m.get('attempted_contracts')==len(candidates),'native_denominator_mismatch')
    rows=[]
    for index,c in enumerate(candidates):
        issues=[]
        if c.get('source_validation_failure'):issues.append(c['source_validation_failure'])
        if not c.get('source_certified'):issues.append('WS1_QUOTE_NOT_SOURCE_CERTIFIED')
        if any(x['status']=='blocked' for x in checks):issues.append('ORIGINAL_SOURCE_VERIFICATION_BLOCKED')
        if not c.get('event_start_at'):
            issues.append('MISSING_EVENT_START')
        elif now>=stamp(c['event_start_at']):issues.append('KICKOFF_PASSED')
        if c.get('model_training_cutoff_at') is None:issues.append('MISSING_FROZEN_TRAINING_CUTOFF')
        issues.append('MISSING_WS1_FROZEN_TEAM_PLAYER_OPPORTUNITY_HISTORY')
        if c.get('availability_certified') is not True:issues.append('PARTICIPATION_NOT_QUANTIFIED_OR_CERTIFIED')
        if c.get('position')=='QB' and c.get('eligibility_status')!='EXPECTED_STARTER_SOURCE_BACKED':
            issues.append('QB_NOT_IDENTIFIED_PREGAME_STARTER')
        issues.append('PRODUCT_SPECIFIC_DNP_AND_SETTLEMENT_RULES_UNVERIFIED')
        identity={k:c.get(k) for k in ('candidate_id','quote_id','event_id','provider_event_id',
            'player_id','player_id_namespace','nflverse_player_id','team','opponent','player','position',
            'stat','period','line','book','over_odds','under_odds','source_sha256','event_start_at')}
        for model in MODELS:
            rows.append({'original_row_index':index,'contract':identity,'model':model,
                         'status':'abstain','reason_codes':list(dict.fromkeys(issues)),
                         'probabilities':None,'frozen_controls_original':c.get('frozen_control'),
                         'eligibility_status_original':c.get('eligibility_status')})
    count=Counter((r['model'],r['contract']['stat']) for r in rows)
    reasons=Counter(code for r in rows for code in r['reason_codes'])
    return {'schema':VERSION,'status':'BLOCKED_BY_DATA_NATIVE_WS1_CONSUMED','day':DAY,
        'manifest_sha256':expected_sha,'native_manifest_schema':NATIVE_SCHEMA,
        'forecast_at':now.isoformat(),'input_freeze_at':m['input_freeze_at'],
        'training_cutoff_at':None,'source_checks':checks,
        'original_contracts_attempted':len(candidates),'forecast_count':0,'abstained_model_contract_rows':len(rows),
        'original_market_coverage':m.get('market_coverage'),
        'original_source_failure_counts':m.get('failures'),
        'counts_by_market_model_status':[{'model':model,'market':market,'status':'abstain','n':n}
                                       for (model,market),n in sorted(count.items())],
        'reason_code_counts_model_contract_rows':dict(sorted(reasons.items())),
        'rows':rows,'team_opportunities':None,'player_workloads':None,
        'exact_contract_universe':'all native WS1 rows retained, including source rejects and duplicates',
        'known_availability_semantics':'original receipt clock only; not upstream publication certification',
        'no_collector_run':True,'no_baseline_modified':True,'release_authority':'NONE',
        'next_dependency':'WS1 hash-bound history, namespace crosswalk, pregame participation/starter probabilities and product rules'}

def main(argv=None):
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--source-root',required=True,type=Path)
    p.add_argument('--output',type=Path,default=Path('reports/nfl_20261115_prospective/opportunity_models'))
    a=p.parse_args(argv)
    report=consume(a.manifest,a.manifest_sha256,a.source_root,datetime.now(timezone.utc).isoformat())
    print(json.dumps(freeze_output(report,a.output),sort_keys=True))

if __name__=='__main__':main()
