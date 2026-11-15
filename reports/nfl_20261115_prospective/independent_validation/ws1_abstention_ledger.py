"""Read-only WS1 native original-quote coverage ledger for joint-model abstentions.

This is NOT a probabilistic forecast, certification, simulation or collector.
It preserves all native WS1 quote observations, including source-rejected rows.
No inferred original event/contract IDs, offered lines, player data or prices.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
from collections import Counter

MODEL_IDS=("J1","J2","J3")
REASON="MODEL_READY_POINT_IN_TIME_OPPORTUNITY_PARAMETERS_UNAVAILABLE"
SCHEMA="PA_WS4_WS1_NATIVE_ABSTENTION_v1"


def digest(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()


def freeze(manifest_raw:bytes, audit_raw:bytes)->dict:
    manifest=json.loads(manifest_raw)
    audit=json.loads(audit_raw)
    if not isinstance(manifest,dict) or not isinstance(manifest.get('candidates'),list):
        raise ValueError('MISSING_WS1_ORIGINAL_CANDIDATE_ROWS')
    if audit.get('schema') != 'nfl_ws1_full_slate_independent_source_audit_v1':
        raise ValueError('INVALID_SOURCE_AUDIT_SCHEMA')
    if digest(manifest_raw)!=audit.get('manifest_file_sha256'):
        raise ValueError('SOURCE_FILE_SHA_MISMATCH')
    if audit.get('forecast_eligible_quotes')!=0:
        raise ValueError('SOURCE_ELIGIBILITY_CHANGED_REEVALUATE_PREDECLARED_RESEARCH')
    if len(manifest['candidates'])!=audit.get('original_observations'):
        raise ValueError('SOURCE_DENOMINATOR_MISMATCH')
    rows=[]
    by_market=Counter()
    for index,c in enumerate(manifest['candidates']):
        if not isinstance(c,dict) or not isinstance(c.get('original_quote'),dict) or not c['original_quote']:
            raise ValueError('ORIGINAL_QUOTE_BYTES_NOT_AVAILABLE')
        original=c['original_quote']
        # Stable row index is NOT synthesized into an authentic sportsbook contract ID.
        # Keep the full raw quote to retain its actual provider identity/line evidence.
        st=original.get('stat')
        if not isinstance(st,str) or not st: raise ValueError('MISSING_ORIGINAL_MARKET')
        by_market[st]+=1
        q_sha=digest(json.dumps(original,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
        for model in MODEL_IDS:
            rows.append({'model_id':model,'status':'ABSTAIN','reason':REASON,
                         'original_observation_index':index,'original_quote_sha256':q_sha,
                         'original_quote':original,'source_status_original':c.get('status'),
                         'p_over':None,'p_under':None,'p_push':None,
                         'mean':None,'variance':None,'simulation_draws':0})
    if len(rows)!=len(manifest['candidates'])*len(MODEL_IDS):
        raise ValueError('ABSTENTION_COVERAGE_INCOMPLETE')
    return {'schema':SCHEMA,'classification':'PREGAME_SOURCE_CAPTURE_COHORT_NO_VALID_JOINT_MODEL_FORECAST',
            'scope':'RESEARCH_SHADOW_ONLY_UNCERTIFIED_MODEL','source_capture_sha256':digest(manifest_raw),
            'source_audit_sha256':digest(audit_raw),'source_manifest_canonical_sha256':audit.get('manifest_canonical_sha256'),
            'source_certified_quotes_aggregate_only':audit.get('source_certified_quotes'),
            'source_rejections_aggregate_only':audit.get('source_rejection_reasons'),
            'quote_observations':len(manifest['candidates']),'models':list(MODEL_IDS),
            'total_attempts':len(rows),'total_model_forecasts':0,'total_model_abstentions':len(rows),
            'by_original_market':dict(sorted(by_market.items())),
            'warning':'Row-level source eligibility retained only where native input has a source status; aggregate quote certification is not a forecast readiness attestation. No player outcomes or simulated probabilities.',
            'rows':rows}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--manifest',type=pathlib.Path,required=True)
    ap.add_argument('--audit',type=pathlib.Path,required=True)
    ap.add_argument('--output',type=pathlib.Path,required=True)
    args=ap.parse_args()
    raw=args.manifest.read_bytes();aud=args.audit.read_bytes()
    ledger=freeze(raw,aud)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as f:
        json.dump(ledger,f,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')
    assert digest(args.manifest.read_bytes())==ledger['source_capture_sha256'],'ORIGINAL_SOURCE_MUTATED'
    print(json.dumps({k:v for k,v in ledger.items() if k not in ('rows','warning')},sort_keys=True))
    print('WS4_NATIVE_ABSTENTION_FILE_SHA256',digest(args.output.read_bytes()))

if __name__=='__main__':main()