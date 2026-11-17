#!/usr/bin/env python3
"""A caller's accounting label must not select the raw rounded-credit rule."""
import argparse,base64,copy,hashlib,json,subprocess,sys,tempfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--assembly',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.assembly.resolve();sys.path[:0]=[str(root),str(root/'tests/nba_architecture')]
    from tests.nba_s_family.test_p1_native_v1 import ExactSourceMinuteTests
    from tests.nba_s_family.test_statistical import histories,manifest
    from v2.nba_architecture.p1_handoff import decode_evidence_bundle,export_prior_game
    from v2.nba_architecture.v2_contracts import canonical,digest
    from v2 import nba_s_family as producer
    from v2.nba_c.native_adapters import NativeForecastArchive
    from v2.nba_c.warehouse import WarehouseError
    helper=ExactSourceMinuteTests();pregame=helper.pregame();source_manifest=manifest();fit=producer.fit(histories('points'),asof_cutoff_utc=pregame['training_cutoff_at'],source_manifest=source_manifest,stat='points')
    seed=helper.minutes_export('PT0M15S',0);g=json.loads(base64.b64decode(seed['evidence_bundle']['raw_base64']));g['game']['homeTeam']['players'][0]['statistics']={'minutes':'PT0M15S','points':11,'reboundsTotal':0,'assists':0,'threePointersMade':0};raw=canonical(g);node=seed['evidence_bundle'];node['raw_base64']=base64.b64encode(raw).decode();node['capture']['raw_sha256']=hashlib.sha256(raw).hexdigest();e=seed['exposure'];data={k:e[k] for k in ('game_id','player_id','team_id','opponent_id','game_date','participation')};data.update(minutes=0,stats={'threes':0})
    original=export_prior_game(data,decode_evidence_bundle(node),ingested_at=seed['clocks']['ingested_at'],source_profile='synthetic_engineering');rows=[]
    for exact in ('PT0M15S','PT0M30S'):
        for label in ('ADJUDICATED_ROUNDED_SUBMINUTE','OFFICIAL_BOX_RECONCILED'):
            x=copy.deepcopy(original);g=json.loads(base64.b64decode(x['evidence_bundle']['raw_base64']));g['game']['homeTeam']['players'][0]['statistics']['minutes']=exact;raw=canonical(g);node=x['evidence_bundle'];node['raw_base64']=base64.b64encode(raw).decode();node['capture']['raw_sha256']=hashlib.sha256(raw).hexdigest();x['exposure'].update(raw_sha256=node['capture']['raw_sha256'],receipt_sha256=digest(node['capture']),exact_minutes=.25 if exact=='PT0M15S' else .5,accounting_status=label)
            expected=exact=='PT0M15S' and label=='ADJUDICATED_ROUNDED_SUBMINUTE';error=None;accepted=False
            with tempfile.TemporaryDirectory() as d:
                try:NativeForecastArchive(d).put_s(producer,fit,frozen_pregame=pregame,target_player_id='espn:player:10',role='wing',source_manifest=source_manifest,source_exports=[x],conditioning='played',evidence_mode='synthetic_engineering');accepted=True
                except WarehouseError as exc:error=str(exc)
            rows.append(dict(exact_raw_clock=exact,caller_accounting_status=label,expected_valid=expected,accepted=accepted,error=error,input=x,input_raw_sha256=hashlib.sha256(canonical(x)+b'\n').hexdigest(),status='PASS' if expected==accepted else 'FAIL'))
    result=dict(schema='NBA_P6_ROUNDING_STATUS_ALIAS_ADVERSARY_V1',qa_source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1]).decode().strip(),qa_script_raw_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),assembly_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),P5_source_raw_sha256=hashlib.sha256((root/'v2/nba_c/native_adapters.py').read_bytes()).hexdigest(),synthetic_fitted_artifact_raw_sha256=fit.artifact_sha256,synthetic_fitted_artifact_raw_base64=base64.b64encode(fit.payload).decode(),pregame=pregame,source_manifest=source_manifest,synthetic_only=True,cases=rows,source_admission_still_blocked=True,all_expected_results=all(x['status']=='PASS' for x in rows))
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('cases','synthetic_fitted_artifact_raw_base64','pregame','source_manifest')}|{'cases':[{k:v for k,v in r.items() if k!='input'} for r in rows]},sort_keys=True))
    return 0 if result['all_expected_results'] else 2


if __name__=='__main__':raise SystemExit(main())
