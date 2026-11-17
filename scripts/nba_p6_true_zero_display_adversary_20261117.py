#!/usr/bin/env python3
"""Fresh source-accounting attack; no owner fixture or implementation edits.

An exact raw zero clock with positive credits cannot be reconciled by making
the caller's displayed minutes a positive value within the rounding tolerance.
All inputs here are explicitly synthetic and preserve fail-closed admission.
"""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback


def main():
    p=argparse.ArgumentParser();p.add_argument('--owner-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.owner_root.resolve();sys.path[:0]=[str(root),str(root/'tests/nba_architecture')]
    from tests.nba_s_family.test_p1_native_v1 import ExactSourceMinuteTests
    from v2.nba_s_family.model import SFError
    from v2.nba_architecture.p1_handoff import decode_evidence_bundle,export_prior_game
    from v2.nba_architecture.p1_history import HistoryIntegrityError
    helper=ExactSourceMinuteTests();rows=[]
    for exact,display,expect in [('PT0M15S',0,'STRUCTURALLY_VALID_BUT_UNADMITTED'),
        ('PT0M15S',.25,'STRUCTURALLY_VALID_BUT_UNADMITTED'),
        ('PT0M0S',0,'ZERO_MINUTE_CREDIT_UNRESOLVED'),
        ('PT0M0S',.25,'ZERO_MINUTE_CREDIT_UNRESOLVED'),
        ('PT0M0S',.5,'ZERO_MINUTE_CREDIT_UNRESOLVED')]:
        x=helper.minutes_export(exact,display)
        e=x['exposure'];data={k:e[k] for k in ('game_id','player_id','team_id','opponent_id','game_date','stats','participation')};data['minutes']=display
        p1=None;p2=None;error=None
        try:positive=export_prior_game(data,decode_evidence_bundle(x['evidence_bundle']),ingested_at=x['clocks']['ingested_at'],source_profile='synthetic_engineering');p1=positive['exposure']['accounting_status']
        except HistoryIntegrityError as exc:p1=str(exc)
        try:
            result=helper.inspect(x)
            p2=dict(status=result['status'],denominator=result['denominator'],preserved_accounting_status=result['preserved_export']['exposure']['accounting_status'],training_rows=result['training_rows'])
        except SFError as exc:error=str(exc)
        expected_valid=expect=='STRUCTURALLY_VALID_BUT_UNADMITTED'
        passed=(error is None and p2['denominator']['structurally_checked']==1) if expected_valid else error is not None and 'ZERO_MINUTE_CREDIT_UNRESOLVED' in error
        if expected_valid:assert p1 in ('ADJUDICATED_ROUNDED_SUBMINUTE','OFFICIAL_BOX_RECONCILED')
        else:assert p1=='ZERO_MINUTE_CREDIT_UNRESOLVED'
        rows.append(dict(exact_raw_minutes=exact,displayed_minutes=display,expected=expect,input=x,input_raw_sha256=hashlib.sha256((json.dumps(x,sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest(),P1_actual_result=p1,P2_actual_result=p2,P2_error=error,status='PASS' if passed else 'FAIL'))
    source=Path(root/'v2/nba_s_family/p1_native.py').read_bytes()
    receipt=dict(schema='NBA_P6_TRUE_ZERO_POSITIVE_DISPLAY_ADVERSARY_V1',qa_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1]).decode().strip(),qa_script_raw_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),tested_checkout_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),P2_source_sha='fe46965394ea0f48ef5e9da501ec8ca9e441ce47',P2_native_source_raw_sha256=hashlib.sha256(source).hexdigest(),synthetic_only=True,source_authentication_still_blocked=True,cases=rows,all_expected_rejections=all(x['status']=='PASS' for x in rows))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(dict(all_expected_rejections=receipt['all_expected_rejections'],cases=[{k:v for k,v in x.items() if k!='input'} for x in rows]),sort_keys=True))
    return 0 if receipt['all_expected_rejections'] else 2


if __name__=='__main__':raise SystemExit(main())
