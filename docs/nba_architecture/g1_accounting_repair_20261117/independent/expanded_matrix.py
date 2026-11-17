#!/usr/bin/env python3
"""New cross-consumer raw/display matrix; synthetic source copies only.

P1's actual raw-Fraction adjudication is the comparison, not an invented date
or availability claim. P5 prior attachment and public outcome validation are
challenged separately. The original independent red probe remains unchanged.
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
    from v2.nba_architecture.p1_handoff import decode_evidence_bundle,export_prior_game
    from v2.nba_architecture.p1_history import HistoryIntegrityError
    from v2.nba_architecture.v2_contracts import canonical,digest,seal
    from v2.nba_s_family.p1_native import inspect_p1_export
    from v2.nba_s_family.model import SFError
    from v2.nba_c.native_adapters import NativeForecastArchive,validate_p1_export
    from v2.nba_c.warehouse import WarehouseError
    helper=ExactSourceMinuteTests();pregame=helper.pregame();rows=[]
    outcome=json.loads((root/'tests/nba_c/fixtures/native_p1_outcome_synthetic_v1.json').read_bytes())
    def packing(x,raw):
        node=x['evidence_bundle'];node['raw_base64']=base64.b64encode(raw).decode();node['capture']['raw_sha256']=hashlib.sha256(raw).hexdigest()
        x['exposure'].update(raw_sha256=node['capture']['raw_sha256'],receipt_sha256=digest(node['capture']))
    def descriptor(x):return dict(capture=x['capture'],prior=[descriptor(y) for y in x['prior']])
    with tempfile.TemporaryDirectory() as d:
        c=NativeForecastArchive(d)
        exacts=['PT0M0S','PT0M0.'+'0'*399+'1S','PT0M15S','PT0M29.9999999999999999S','PT0M30S','PT25M30S','PT48M0S','PT48M0.0000000000000001S']
        displays=[-.1,0,5e-324,1e-18,.1,.25,.5,.5000000000000001,1,25,26,48,48.00000000000001,True]
        credit_names={'points':'points','rebounds':'reboundsTotal','assists':'assists','threes':'threePointersMade','fgm':'fieldGoalsMade','fga':'fieldGoalsAttempted','fg3a':'threePointersAttempted','ftm':'freeThrowsMade','fta':'freeThrowsAttempted','oreb':'reboundsOffensive','dreb':'reboundsDefensive','steals':'steals','blocks':'blocks','turnovers':'turnovers','personal_fouls':'foulsPersonal'}
        for hidden,raw_name in credit_names.items():
            retained_stat='assists' if hidden!='assists' else 'rebounds'
            raw_retained=credit_names[retained_stat]
            for exact in exacts:
                parts=exact[2:-1].split('M');minutes=Fraction(parts[0])+Fraction(parts[1])/60
                for display in displays:
                    for subset in (False,True):
                        x=helper.minutes_export(exact,display);g=json.loads(base64.b64decode(x['evidence_bundle']['raw_base64']))
                        g['game']['homeTeam']['players'][0]['statistics']={'minutes':exact,raw_name:1,raw_retained:0}
                        packing(x,canonical(g));stats={retained_stat:0} if subset else {retained_stat:0,hidden:1};x['exposure']['stats']=stats
                        e=x['exposure'];data={k:e[k] for k in ('game_id','player_id','team_id','opponent_id','game_date','stats','participation')};data['minutes']=display
                        errors={};valid={}
                        try:export_prior_game(data,decode_evidence_bundle(x['evidence_bundle']),ingested_at=x['clocks']['ingested_at'],source_profile='synthetic_engineering');valid['P1']=True
                        except HistoryIntegrityError as exc:valid['P1']=False;errors['P1']=str(exc)
                        try:inspect_p1_export(x,pregame=pregame,stat=retained_stat);valid['P2']=True
                        except SFError as exc:valid['P2']=False;errors['P2']=str(exc)
                        try:c._source_attachment(x,pregame,{'training_cutoff_at':pregame['training_cutoff_at']});valid['P5_prior']=True
                        except WarehouseError as exc:valid['P5_prior']=False;errors['P5_prior']=str(exc)
                        y=copy.deepcopy(outcome);revision=y['revisions'][-1];node=revision['accounting_evidence'];og=json.loads(base64.b64decode(node['raw_base64']))
                        og['game']['homeTeam']['players'][0]['statistics']={'minutes':exact,raw_name:1,raw_retained:0}
                        raw=canonical(og);h=hashlib.sha256(raw).hexdigest();node['raw_base64']=base64.b64encode(raw).decode();node['capture']['raw_sha256']=h
                        revision.update(source_raw_base64=base64.b64encode(raw).decode(),source_raw_sha256=h)
                        state='PLAYED_ZERO_MINUTES' if display==0 else 'PLAYED';record=revision['record']
                        record.update(source_raw_sha256=h,accounting_evidence=descriptor(node),minutes=display,state=state,stats=stats)
                        record=seal({k:v for k,v in record.items() if k!='content_hash'});revision['record']=record;record_raw=canonical(record)+b'\n'
                        revision.update(record_raw_base64=base64.b64encode(record_raw).decode(),record_raw_sha256=hashlib.sha256(record_raw).hexdigest())
                        y.update(displayed_minutes=display,exact_minutes=float(minutes),participation=state,stats=stats)
                        try:validate_p1_export(y,outcome=True);valid['P5_outcome']=True
                        except WarehouseError as exc:valid['P5_outcome']=False;errors['P5_outcome']=str(exc)
                        row=dict(hidden_credit=hidden,exact_raw_clock=exact,displayed_minutes=display,retained_zero_subset=subset,valid=valid,errors=errors)
                        row['P2_agrees_with_P1']=valid['P2']==valid['P1'];row['P5_prior_agrees_with_P1']=valid['P5_prior']==valid['P1'];row['P5_outcome_agrees_with_P1']=valid['P5_outcome']==valid['P1'];rows.append(row)
    totals={key:sum(not x[key] for x in rows) for key in ('P2_agrees_with_P1','P5_prior_agrees_with_P1','P5_outcome_agrees_with_P1')}
    result=dict(schema='NBA_P6_INDEPENDENT_ALL_RAW_CREDIT_MATRIX_V1',qa_source_origin='independently expanded from immutable matrix d1ca72f; new file raw hash identifies executed bytes',qa_source_raw_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),assembly_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),source_raw_sha256={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in ('v2/nba_s_family/p1_native.py','v2/nba_architecture/p1_evidence.py','v2/nba_c/native_adapters.py')},synthetic_only=True,cases=len(rows),mismatch_counts=totals,rows=rows,source_admission_still_blocked=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
    return 2 if any(totals.values()) else 0


if __name__=='__main__':raise SystemExit(main())
