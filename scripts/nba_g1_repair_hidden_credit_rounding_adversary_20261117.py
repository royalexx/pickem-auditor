#!/usr/bin/env python3
"""P5 public-path rounding regression, using actual P1/P2 implementations.

All histories and sources are synthetic. Old owner fixtures are copied, never
edited. Source admission and outcome scoring stay BLOCKED throughout.
"""
import argparse
import base64
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    p=argparse.ArgumentParser();p.add_argument('--assembly',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.assembly.resolve()
    sys.path[:0]=[str(root),str(root/'tests/nba_architecture')]
    from tests.nba_s_family.test_p1_native_v1 import ExactSourceMinuteTests
    from tests.nba_s_family.test_statistical import histories,manifest
    from v2.nba_architecture.p1_handoff import decode_evidence_bundle,export_prior_game
    from v2.nba_architecture.p1_history import HistoryIntegrityError
    from v2.nba_architecture.v2_contracts import canonical,digest,seal
    from v2 import nba_s_family as producer
    from v2.nba_c.native_adapters import NativeForecastArchive,NativeOutcomeArchive,validate_p1_export
    from v2.nba_c.warehouse import WarehouseError
    helper=ExactSourceMinuteTests();pregame=helper.pregame();source_manifest=manifest()
    fitted=producer.fit(histories('points'),asof_cutoff_utc=pregame['training_cutoff_at'],source_manifest=source_manifest,stat='points')
    cases=[]
    def input_prior(exact,subset):
        x=helper.minutes_export(exact,0);g=json.loads(base64.b64decode(x['evidence_bundle']['raw_base64']))
        g['game']['homeTeam']['players'][0]['statistics']={'minutes':exact,'points':11,'reboundsTotal':0,'assists':0,'threePointersMade':0}
        raw=canonical(g);node=x['evidence_bundle'];node['raw_base64']=base64.b64encode(raw).decode();node['capture']['raw_sha256']=hashlib.sha256(raw).hexdigest()
        e=x['exposure'];data={k:e[k] for k in ('game_id','player_id','team_id','opponent_id','game_date','participation')};data.update(minutes=0,stats={'threes':0} if subset else dict(points=11,rebounds=0,assists=0,threes=0))
        return export_prior_game(data,decode_evidence_bundle(node),ingested_at=x['clocks']['ingested_at'],source_profile='synthetic_engineering')
    for exact,subset in [('PT0M15S',False),('PT0M15S',True),('PT0M29.9999999999999999S',True),('PT0M0.'+'0'*399+'1S',True)]:
        export=input_prior(exact,subset);error=None;receipt=None
        with tempfile.TemporaryDirectory() as d:
            try:
                key=NativeForecastArchive(d).put_s(producer,fitted,frozen_pregame=pregame,target_player_id='espn:player:10',role='wing',source_manifest=source_manifest,source_exports=[export],conditioning='played',evidence_mode='synthetic_engineering')
                receipt=str(key)
            except WarehouseError as exc:error=str(exc)
        cases.append(dict(kind='actual_P1_export_to_public_P5_put_s',exact_raw_clock=exact,retained_zero_subset=subset,expected='ACCEPT_UNADMITTED_SOURCE_ATTACHMENT',P1_accounting_status=export['exposure']['accounting_status'],input=export,input_raw_sha256=hashlib.sha256(canonical(export)+b'\n').hexdigest(),P5_receipt=receipt,P5_error=error,status='PASS' if error is None else 'FAIL'))
    base=json.loads((root/'tests/nba_c/fixtures/native_p1_outcome_synthetic_v1.json').read_bytes())
    def descriptor(node):return dict(capture=node['capture'],prior=[descriptor(x) for x in node['prior']])
    for exact,subset,expected in [('PT0M15S',False,True),('PT0M15S',True,True),('PT0M30S',False,False),('PT0M30S',True,False),('PT0M30.0000000000000001S',True,False),('PT0M0S',True,False)]:
        export=copy.deepcopy(base);revision=export['revisions'][-1];node=revision['accounting_evidence'];g=json.loads(base64.b64decode(node['raw_base64']))
        g['game']['homeTeam']['players'][0]['statistics']={'minutes':exact,'points':11,'reboundsTotal':0,'assists':0,'threePointersMade':0}
        raw=canonical(g);h=hashlib.sha256(raw).hexdigest();node['raw_base64']=base64.b64encode(raw).decode();node['capture']['raw_sha256']=h
        revision.update(source_raw_sha256=h,source_raw_base64=base64.b64encode(raw).decode())
        stats={'threes':0} if subset else dict(points=11,rebounds=0,assists=0,threes=0)
        record=revision['record'];record.update(source_raw_sha256=h,accounting_evidence=descriptor(node),minutes=0,state='PLAYED_ZERO_MINUTES',stats=stats)
        record=seal({k:v for k,v in record.items() if k!='content_hash'});revision['record']=record;record_raw=canonical(record)+b'\n'
        revision.update(record_raw_sha256=hashlib.sha256(record_raw).hexdigest(),record_raw_base64=base64.b64encode(record_raw).decode())
        parts=exact[2:-1].split('M');minutes=Fraction(parts[0])+Fraction(parts[1])/60
        export.update(displayed_minutes=0,exact_minutes=float(minutes),participation='PLAYED_ZERO_MINUTES',stats=stats)
        errors={};accepted={};disposition=None
        try:validate_p1_export(export,outcome=True);accepted['validator']=True
        except WarehouseError as exc:accepted['validator']=False;errors['validator']=str(exc)
        with tempfile.TemporaryDirectory() as d:
            try:
                archive=NativeOutcomeArchive(d);key=archive.put_p1(export,evidence_mode='synthetic_engineering');disposition=archive.scoring_disposition(key);accepted['archive']=True
            except WarehouseError as exc:accepted['archive']=False;errors['archive']=str(exc)
        cases.append(dict(kind='public_P5_outcome_validator_and_archive',exact_raw_clock=exact,retained_zero_subset=subset,expected_valid=expected,input=export,input_raw_sha256=hashlib.sha256(canonical(export)+b'\n').hexdigest(),accepted=accepted,errors=errors,scoring_disposition=disposition,status='PASS' if all(v==expected for v in accepted.values()) else 'FAIL'))
    source=Path(__file__)
    receipt=dict(schema='NBA_P6_P5_HIDDEN_CREDIT_ROUNDING_PUBLIC_PATH_V1',qa_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source.parents[1]).decode().strip(),qa_script_raw_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),assembly_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),source_raw_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ('v2/nba_architecture/p1_evidence.py','v2/nba_c/native_adapters.py','v2/nba_s_family/model.py')},fixtures=dict(P2_native_sha256=hashlib.sha256((root/'tests/nba_s_family/fixtures/p1_native_synthetic_v1.json').read_bytes()).hexdigest(),P5_native_outcome_sha256=hashlib.sha256((root/'tests/nba_c/fixtures/native_p1_outcome_synthetic_v1.json').read_bytes()).hexdigest()),fitted_artifact=dict(raw_sha256=fitted.artifact_sha256,raw_base64=base64.b64encode(fitted.payload).decode(),source_manifest=source_manifest),pregame=pregame,synthetic_only=True,cases=cases,all_expected_results=all(x['status']=='PASS' for x in cases),source_authentication_and_scoring_remain_blocked=True)
    with a.output.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(dict(all_expected_results=receipt['all_expected_results'],cases=[{k:v for k,v in x.items() if k not in ('input','P5_receipt')} for x in cases]),sort_keys=True))
    return 0 if receipt['all_expected_results'] else 2


if __name__=='__main__':raise SystemExit(main())
