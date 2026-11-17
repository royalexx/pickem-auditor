#!/usr/bin/env python3
"""Run exact owner-source interoperability in a disposable copy, never merge owners.
Usage: python scripts/nba_p2_integration_check.py /path/to/full/git/repository
Requires pinned objects (git fetch origin SHA if absent). No historical fit.
"""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

PINS={
 'P1':'e0b8703887d327c8d8ac34807078e75e7b59a540',
 'P3':'80dbed35f983839f962250ad1c0236061dc6ee00',
 'P6':'31435bd571ae1b4a9b7f1e1bbf05e55cef61126f'}

def main():
    repo=Path(sys.argv[1]).resolve()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        dst=Path(directory)
        for path in ['v2','tests']:
            shutil.copytree(root/path,dst/path,ignore=shutil.ignore_patterns('__pycache__'))
        files={'P1':['v2/nba_architecture/p1_history.py','v2/nba_architecture/p1_vault.py','tests/nba_architecture/test_p1_history.py'],
               'P3':['v2/nba_opportunity.py','v2/nba_o_family.py','tests/nba_architecture/test_p3_o_family.py'],
               'P6':['scripts/nba_p6_g1_owner_negative_probes_20261116.py']}
        for owner,paths in files.items():
            for path in paths:
                out=dst/path;out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(subprocess.check_output(['git','-C',str(repo),'show',PINS[owner]+':'+path]))
        code=r'''
import json
from tests.nba_architecture.test_p3_o_family import build
from tests.nba_architecture.test_p1_history import build as p1build, make_entry
from tests.nba_s_family.test_statistical import histories, manifest, CUTOFF
from v2.nba_s_family import fit, predict, SFError
from v2.nba_s_family.integration import history_from_p1, joint_conditional
p,g,o,side=build()
f=fit(histories(),asof_cutoff_utc=CUTOFF,source_manifest=manifest(),stat='points')
args=dict(frozen_pregame=p,target_player_id='espn:player:10',role='wing',opportunity=o,game_state=g)
r=predict(f,**args)
assert r.abstain_reason=='UNKNOWN_APPEARANCE_PROBABILITY',r
r=predict(f,**args,conditioning='conditional_on_participation')
assert r.abstain_reason is None,r
j=joint_conditional(f,pregame=p,game_state=g,opportunity=o,scenario_id=o['scenarios'][0]['scenario_id'],player_id='espn:player:10',team_id='espn:team:1',role='wing')
assert j['opportunity_sha256']==o['content_hash']
p1=p1build([make_entry()])
try:
 history_from_p1(p1,annotations={},source_manifest={},stat='points',asof_cutoff_utc=CUTOFF)
 raise AssertionError('missing evidence accepted')
except SFError as e:
 assert e.reason=='P1_CLOCK_ROLE_EVIDENCE_UNRESOLVED',e
# Explicit synthetic annotations prove deterministic transformation only.
s=p1['sources'][0];receipt=s['receipt_sha256'];gid='espn:game:prior-1'
ann={receipt:dict(player_id='espn:player:7',role='wing',game_date='2022-10-21',game_start_at='2022-10-21T00:00:00Z',outcome_available_at='2022-10-22T00:00:00Z')}
m={receipt:dict(raw_sha256=s['raw_sha256'],available_at=s['ingested_at'],status='P1_VERIFIED',games={gid:dict(overtime_periods=0,game_start_at=ann[receipt]['game_start_at'],duration_receipt_sha256=receipt,players={'espn:player:7':'espn:team:1'})})}
a=history_from_p1(p1,annotations=ann,source_manifest=m,stat='points',asof_cutoff_utc='2026-11-17T00:00:00Z')
b=history_from_p1(p1,annotations=ann,source_manifest=m,stat='points',asof_cutoff_utc='2026-11-17T00:00:00Z')
assert a==b and a[0]['count']==11
print(json.dumps(dict(status='PASS_SYNTHETIC_INTEROPERABILITY',P1_rows=len(a),P3_unknown_abstention=True,P3_conditional_mixture=True,S_to_J_sidecar=j['content_hash'],P4='BLOCKED_SYNTHETIC_RATES_ONLY'),sort_keys=True))
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=dst,text=True)
        if result.returncode: return result.returncode
        # Exact old reproducer retained; its regulation fixture now correctly
        # rejects 56 minutes. Positive two-OT witness is in new owner tests.
        return subprocess.run([sys.executable,'scripts/nba_p6_g1_owner_negative_probes_20261116.py','P2'],cwd=dst,env={**__import__('os').environ,'PYTHONPATH':str(dst)}).returncode
if __name__=='__main__': raise SystemExit(main())
