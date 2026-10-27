#!/usr/bin/env python3
"""Fail closed if any of the original 1,492 pregame forecasts are rewritten.

Settlement may append verified outcomes, but it must not reforecast historical
market prices or change recorded A/B estimates, timestamps and ranks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

BASELINE_ROWS = 1492
BASELINE_IDENTITY_SHA256 = 'ebf5f392ed0113bbf2e2b93b872d667b85a6936509ede26e79d177c15ef3bfa1'
ORIGINAL_KEYS = (
    'forecast_at','run_at','game_date','sport','player','stat','side',
    'reference_line','run_id','engine_a','engine_b','blend',
    'q_model','q_market','final_rank',
)


def check(path: Path, expected_hash: str = BASELINE_IDENTITY_SHA256,
          expected_rows: int = BASELINE_ROWS) -> dict:
    fingerprint = hashlib.sha256()
    total = settled = original = 0
    with path.open(encoding='utf-8') as source:
        for text in source:
            if not text.strip():
                continue
            row = json.loads(text)
            total += 1
            if row.get('actual_stat') is not None:
                settled += 1
            if original < expected_rows:
                selected = {k:row[k] for k in ORIGINAL_KEYS if k in row}
                fingerprint.update((json.dumps(selected,sort_keys=True,
                       separators=(',',':'),ensure_ascii=False)+'\n').encode('utf-8'))
                original += 1
    digest = fingerprint.hexdigest()
    if original < expected_rows:
        status = 'MISSING_ORIGINAL_FORECASTS'
    elif digest != expected_hash:
        status = 'ORIGINAL_FORECAST_INPUT_CHANGED'
    else:
        status = 'verified'
    return {'status':status,'original_forecasts':original,'total_forecasts':total,
            'verified_outcomes':settled,'unresolved':total-settled,
            'original_forecast_identity_sha256':digest}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path',default='data/prop_snapshots.jsonl',type=Path)
    parser.add_argument('--out',default='reports/forecast_invariants.json',type=Path)
    args=parser.parse_args()
    try:
        result=check(args.path)
    except (OSError,ValueError,TypeError) as exc:
        result={'status':'VERIFICATION_ERROR','error':type(exc).__name__}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return 0 if result['status']=='verified' else 2

if __name__=='__main__':
    raise SystemExit(main())