#!/usr/bin/env python3
"""Pinned disposable native P1/P2/P3-to-C verification, synthetic only.

No collector, historical backfill, validation outcome or weight fit is run.
Owners are materialized from git objects; live worktree edits are never imported.
"""
from __future__ import annotations
import argparse
import base64
from copy import deepcopy
import hashlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def materialize(repo, sha, root, paths):
    exact=subprocess.check_output(['git','-C',str(repo),'rev-parse',sha+'^{commit}'],text=True).strip()
    if exact!=sha:
        raise ValueError('EXACT_OWNER_COMMIT_REQUIRED')
    raw=subprocess.check_output(['git','-C',str(repo),'archive',sha,*paths])
    root.mkdir()
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        archive.extractall(root,filter='data')
    return {'commit':exact,'archive_raw_sha256':hashlib.sha256(raw).hexdigest(),
            'paths':paths}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    for owner in ('p1','p2','p3'):
        parser.add_argument('--'+owner+'-sha',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    work=args.output/'sources';work.mkdir()
    paths={
      'p1':['v2/nba_architecture','tests/nba_architecture/test_p1_remediation.py','tests/nba_architecture/test_p1_history.py'],
      'p2':['v2/nba_s_family','tests/nba_s_family/test_statistical.py'],
      'p3':['v2/nba_o_family.py','v2/nba_o_bridge.py','v2/nba_opportunity.py','tests/nba_architecture/test_p3_o_family.py','tests/nba_architecture/golden_v2/joint_same_draw.json']}
    pins={name:materialize(args.repo,getattr(args,name+'_sha'),work/name,files)
          for name,files in paths.items()}
    # G0 remains the C branch's accepted inherited implementation. The native
    # owner modules below are the exact bytes extracted from submitted SHAs.
    import v2
    import v2.nba_architecture
    import tests
    import tests.nba_architecture
    for name in paths:
        v2.__path__.append(str(work/name/'v2'))
    v2.nba_architecture.__path__.append(str(work/'p1/v2/nba_architecture'))
    tests.nba_architecture.__path__.append(str(work/'p1/tests/nba_architecture'))
    tests.nba_architecture.__path__.append(str(work/'p3/tests/nba_architecture'))
    tests.__path__.append(str(work/'p2/tests'))
    from v2.nba_architecture import p1_handoff
    from v2.nba_architecture.p1_vault import OfficialOutcomeVault
    from v2.nba_s_family import model as p2
    from v2.nba_o_family import build_opportunity
    from tests.nba_s_family.test_statistical import histories,manifest,CUTOFF,frozen_pregame_with_active
    from tests.nba_architecture.test_p3_o_family import build as build_p3
    from tests.nba_architecture.test_p1_remediation import official_fixture,NBA_GAME,NBA_TEAMS
    from v2.nba_c.native_adapters import NativeForecastArchive,NativeOutcomeArchive,WarehouseError
    from v2.nba_architecture.v2_contracts import canonical
    results=[]

    def check(name, function):
        try:
            detail=function()
            results.append({'case':name,'status':'PASS','detail':detail})
        except Exception as exc:
            results.append({'case':name,'status':'FAIL','error':type(exc).__name__+': '+str(exc)})

    def must_reject(function, reason):
        try:
            function()
        except Exception as exc:
            assert reason in str(exc),(reason,str(exc))
            return {'rejection':str(exc)}
        raise AssertionError('ACCEPTED_ADVERSARIAL_INPUT')

    store=NativeForecastArchive(args.output/'archive')
    # Actual P2 synthetic fit: engineering fitting is allowed, never historical.
    f0=p2.fit(histories(),asof_cutoff_utc=CUTOFF,source_manifest=manifest(),stat='points',family='S0')
    active=frozen_pregame_with_active()
    context=p1_handoff.export_pregame_context(game_id=active['game_id'],team_ids=active['team_ids'],
        event_start_at=active['event_start_at'],input_freeze_at=active['input_freeze_at'],
        bundles=[],ingested_at=active['input_freeze_at'])
    kwargs=dict(frozen_pregame=active,target_player_id=active['players'][0]['player_id'],
        role='wing',source_manifest=manifest(),source_exports=[context],evidence_mode='synthetic_engineering')
    def actual_s0():
        key,receipt=store.put_s(p2,f0,**kwargs)
        replay,objects=store.get_s(key)
        assert replay==receipt and receipt['produced']==1
        assert objects['fitted_artifact_bytes']==f0.payload
        assert objects['p1_source_exports']==[context]
        assert objects['native_prediction']['uncertainty']['not_predictive_accuracy_evidence']
        assert receipt['source_admission']=='BLOCKED'
        return {'intake_sha256':key,'distribution_sha256':objects['native_prediction']['distribution']['content_hash'],
                'source_profile':objects['pregame']['source_profile'],'real_source_admitted':False}
    check('actual_P1_context_and_P2_S_ONLY_immutable_intake',actual_s0)
    check('real_S_intake_stays_closed',lambda:must_reject(
        lambda:store.put_s(p2,f0,**dict(kwargs,evidence_mode='real')),'REAL_ADMISSION'))
    check('source_manifest_tamper_rejects',lambda:must_reject(
        lambda:store.put_s(p2,f0,**dict(kwargs,source_manifest={})), 'SOURCE_MANIFEST_JOIN'))
    check('outcome_export_cannot_be_forecast_input',lambda:must_reject(
        lambda:store.put_s(p2,f0,**dict(kwargs,source_exports=[p1_handoff.export_outcome(
            OfficialOutcomeVault(args.output/'empty_vault'),NBA_GAME,'nba:player:7')])),
        'OUTCOME_IN_FORECAST_SOURCE'))
    p,g,o,side=build_p3('O2',seed=17)
    fs=p2.fit(histories(),asof_cutoff_utc=CUTOFF,source_manifest=manifest(),stat='points',family='S1')
    soargs=dict(frozen_pregame=p,target_player_id=p['players'][0]['player_id'],role='wing',
        source_manifest=manifest(),opportunity=o,game_state=g,evidence_mode='synthetic_engineering')
    def actual_so():
        key,receipt=store.put_s(p2,fs,**dict(soargs,conditioning='conditional_on_participation'))
        _,objects=store.get_s(key)
        assert receipt['produced']==1
        distribution=objects['native_prediction']['distribution']
        assert distribution['opportunity_output_sha256']==o['content_hash']
        assert objects['opportunity']==o and objects['game_state']==g
        assert all(x['participation_probability'] is None for x in o['players'])
        return {'intake_sha256':key,'G':g['content_hash'],'O':o['content_hash'],
            'distribution_sha256':distribution['content_hash'],'conditioning':distribution['conditioning'],
            'scenario_ids':[s['scenario_id'] for s in o['scenarios']],
            'scenario_weights':[s['weight'] for s in o['scenarios']]}
    check('actual_P3_O2_to_P2_S_O_to_C_conditional',actual_so)
    def unknown_abstention():
        key,receipt=store.put_s(p2,fs,**soargs)
        _,objects=store.get_s(key)
        assert receipt['produced']==0 and receipt['abstained']==1
        reason=objects['native_prediction']['abstain_reason']
        assert reason=='UNKNOWN_APPEARANCE_PROBABILITY',reason
        return {'intake_sha256':key,'abstain_reason':reason,'attempted':1,'produced':0,'abstained':1}
    check('actual_unknown_participation_abstention_retained',unknown_abstention)
    outcome_store=NativeOutcomeArchive(args.output/'archive')
    def actual_outcome():
        vault=OfficialOutcomeVault(args.output/'p1_synthetic_vault')
        b=official_fixture()
        kw=dict(game_id=NBA_GAME,player_id='nba:player:7',team_id=NBA_TEAMS[0],state='PLAYED',
            minutes=26,stats={'points':11,'rebounds':5,'assists':3,'threes':2},
            source_id='nba:official:synthetic-box',source_bytes=b['raw'],official_status='FINAL',
            official_game_evidence=b)
        first=vault.append(**kw,observed_at='2026-11-16T19:00:00Z')
        vault.append(**kw,observed_at='2026-11-16T20:00:00Z',revision=2,supersedes_sha256=first['content_hash'])
        before={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in Path(vault.root).rglob('*') if x.is_file()}
        export=p1_handoff.export_outcome(vault,NBA_GAME,'nba:player:7')
        key=outcome_store.put_p1(export,evidence_mode='synthetic_engineering')
        assert outcome_store.get(key)==export
        assert len(export['revisions'])==2 and export['event_end_at'] is None and export['outcome_released_at'] is None
        assert not outcome_store.scoring_disposition(key)['scored']
        after={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in Path(vault.root).rglob('*') if x.is_file()}
        assert before==after
        (args.output/'actual_p1_outcome_export.json').write_bytes(canonical(export)+b'\n')
        return {'native_outcome_sha256':key,'correction_version':2,'scored':False,
            'missing_requirements':export['missing_requirements'],'vault_unchanged':True}
    check('actual_P1_vault_two_revisions_preserve_raw_and_no_score',actual_outcome)
    def missing():
        export=p1_handoff.export_outcome(OfficialOutcomeVault(args.output/'empty_vault'),NBA_GAME,'nba:missing')
        key=outcome_store.put_p1(export,evidence_mode='synthetic_engineering')
        assert outcome_store.get(key)['participation']=='UNRESOLVED'
        return outcome_store.scoring_disposition(key)
    check('actual_P1_missing_outcome_remains_unresolved',missing)
    report={'schema':'nba-p5-native-owner-verification/1.0.0','pins':pins,'scope':'SYNTHETIC_ENGINEERING_ONLY',
        'G1_acceptance':'NOT_AWARDED_OWNER_EXECUTION','historical_fitting':False,'historical_scoring':False,
        'cases':results,'pass':sum(x['status']=='PASS' for x in results),'fail':sum(x['status']=='FAIL' for x in results)}
    (args.output/'results.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,sort_keys=True))
    return bool(report['fail'])

if __name__=='__main__':
    raise SystemExit(main())
