#!/usr/bin/env python3
"""Verify actual committed assembly objects, not ignored working-tree copies.

This is publication integrity only; no source authentication or G1 acceptance.
The original d46 assembly must remain a reproducible negative control.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

G0='59d28dc23be97de2a6a82d22be8338151e31f5b6'
P0_BASE='7ca4269c98a27def485eaa8122ea7148cd0c2c0a'
MAP='docs/nba_architecture/g1_exact_owner_assembly_v4_20261116.json'


def verify(repo, assembly):
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args])
    def tree(sha):
        result={}
        for row in git('ls-tree','-rz','--full-tree',sha).split(b'\0'):
            if row:
                meta,path=row.split(b'\t',1);mode,kind,oid=meta.decode().split()
                result[path.decode()]=(mode,kind,oid)
        return result
    actual=tree(assembly);base=tree(G0)
    manifest=json.loads(git('show',assembly+':'+MAP));pins=manifest['pins']
    assert set(pins)=={'P0','P1','P2','P3','P4','P5'},'OWNER_POPULATION'
    assert manifest['g0']==G0,'ACCEPTED_G0_PIN'
    expected={}
    for owner,pin in pins.items():
        source=tree(pin);parent=P0_BASE if owner=='P0' else G0
        for row in git('diff','--name-status',parent,pin).decode().splitlines():
            status,path=row.split('\t');assert status in ('A','M'),('DELETE_OR_RENAME',row)
            if path in expected:
                assert expected[path]['entry']==source[path],('OWNER_COLLISION',path)
                expected[path]['owners'].append(owner)
            else:expected[path]=dict(entry=source[path],owners=[owner],source=pin)
    errors=[];checks=[]
    if set(manifest['files'])!=set(expected):errors.append(dict(code='SOURCE_MAP_POPULATION',missing=sorted(set(expected)-set(manifest['files'])),unexpected=sorted(set(manifest['files'])-set(expected))))
    for path,exp in sorted(expected.items()):
        promised=manifest['files'].get(path)
        if not promised:continue
        assert set(promised['owners'])==set(exp['owners']),('OWNER_IDENTITY',path)
        assert promised['source_commit'] in [pins[x] for x in exp['owners']],('SOURCE_COMMIT',path)
        raw=git('cat-file','blob',exp['entry'][2]);h=hashlib.sha256(raw).hexdigest()
        assert h==promised['raw_sha256'] and promised['git_mode']==exp['entry'][0],('PROMISED_SOURCE',path)
        if path not in actual:
            errors.append(dict(code='PROMISED_FILE_NOT_PUBLISHED',path=path,source_commit=promised['source_commit'],raw_sha256=h));continue
        if actual[path]!=exp['entry']:
            errors.append(dict(code='PUBLISHED_OWNER_BLOB_OR_MODE_DRIFT',path=path,expected=exp['entry'],actual=actual[path]));continue
        checks.append(dict(path=path,source_commit=promised['source_commit'],git_blob=actual[path][2],git_mode=actual[path][0],raw_sha256=h))
    extras=set(actual)-(set(base)|set(expected)|{MAP})
    if extras:errors.append(dict(code='UNMAPPED_PUBLISHED_FILES',paths=sorted(extras)))
    inherited=[p for p in base if p.startswith(('v2/nba_architecture/','tests/nba_architecture/'))]
    for path in inherited:assert actual.get(path)==base[path],('INHERITED_G0_CHANGED',path)
    assert MAP in actual,'MAP_NOT_PUBLISHED'
    return dict(schema='NBA_G1_COMMITTED_ASSEMBLY_PUBLICATION_CHECK_V4',assembly=assembly,owner_pins=pins,source_map_raw_sha256=hashlib.sha256(git('show',assembly+':'+MAP)).hexdigest(),expected_owner_files=len(expected),published_owner_files_checked=len(checks),inherited_g0_files=len(inherited),errors=errors,checks=checks,all_pass=not errors,independent_gate_acceptance=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--assembly',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert len(a.assembly)==40 and all(x in '0123456789abcdef' for x in a.assembly),'EXACT_ASSEMBLY_COMMIT_REQUIRED'
    result=verify(a.repo.resolve(),a.assembly);result['qa_verifier_raw_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('checks','owner_pins')}))
    return 0 if result['all_pass'] else 2

if __name__=='__main__':raise SystemExit(main())
