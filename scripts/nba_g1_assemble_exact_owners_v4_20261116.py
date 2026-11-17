#!/usr/bin/env python3
"""Assemble exact owner blobs for G1 synthetic/import QC, never gate acceptance.

No owner implementation is edited or substituted. The source map records every
changed file, origin commit and raw byte hash. G0 implementation/test bytes
must remain identical. The assembly is deliberately a new isolated Git branch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

G0='59d28dc23be97de2a6a82d22be8338151e31f5b6'
P0_BASE='7ca4269c98a27def485eaa8122ea7148cd0c2c0a'


def main():
    ap=argparse.ArgumentParser()
    for k in ('repo','pins','destination'):
        ap.add_argument('--'+k,type=Path,required=True)
    ap.add_argument('--branch',required=True)
    a=ap.parse_args();repo=a.repo.resolve();dst=a.destination.resolve()
    pins=json.loads(a.pins.read_text())
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args])
    subprocess.run(['git','-C',str(repo),'worktree','add','-b',a.branch,str(dst),G0],check=True)
    files={}
    for owner in ('P1','P2','P3','P4','P5','P0'):
        sha=pins[owner]
        if len(sha)!=40 or any(x not in '0123456789abcdef' for x in sha):
            raise ValueError('EXACT_OWNER_COMMIT_REQUIRED')
        base=P0_BASE if owner=='P0' else G0
        for row in git('diff','--name-status',base,sha).decode().splitlines():
            status,path=row.split('\t')
            if status not in ('A','M'):raise ValueError('UNREVIEWED_DELETE_OR_RENAME:'+row)
            raw=git('show',sha+':'+path);digest=hashlib.sha256(raw).hexdigest()
            mode=git('ls-tree',sha,'--',path).decode().split()[0]
            if mode not in ('100644','100755'):raise ValueError('UNREVIEWED_GIT_MODE:'+path)
            if path in files:
                if files[path]['raw_sha256']!=digest or files[path]['git_mode']!=mode:
                    raise ValueError('OWNER_WRITE_COLLISION:'+path)
                files[path]['owners'].append(owner)
            else:
                files[path]=dict(owners=[owner],source_commit=sha,raw_sha256=digest,git_mode=mode)
                target=dst/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);target.chmod(0o755 if mode=='100755' else 0o644)
    for path in git('ls-tree','-r','--name-only',G0,'v2/nba_architecture','tests/nba_architecture').decode().splitlines():
        if (dst/path).read_bytes()!=git('show',G0+':'+path):
            raise ValueError('ACCEPTED_G0_CHANGED:'+path)
    doc=dst/'docs/nba_architecture/g1_exact_owner_assembly_v4_20261116.json'
    doc.write_text(json.dumps(dict(schema='NBA_G1_EXACT_OWNER_ASSEMBLY_V4',assembly_tool_version='4.0.1',assembler_code_commit=git('rev-parse','HEAD').decode().strip(),assembler_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='SYNTHETIC_ENGINEERING_AND_IMPORT_QC_ONLY',independent_acceptance=False,authentic_case_continued=False,g0=G0,pins=pins,files=files),indent=2)+'\n')
    # A tracked owner report may be ignored by the accepted base checkout.
    # Stage only the explicit immutable source population; never scratch files.
    mapped_paths=sorted(files)+[str(doc.relative_to(dst))]
    for offset in range(0,len(mapped_paths),100):
        subprocess.run(['git','add','-f','--',*mapped_paths[offset:offset+100]],cwd=dst,check=True)
    subprocess.run(['git','commit','-q','-m','test(nba): assemble exact owner blobs for isolated G1 conformance QC'],cwd=dst,check=True)
    assembly_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=dst).decode().strip()
    from nba_g1_verify_assembly_publication_v4_20261116 import verify
    published=verify(repo,assembly_sha)
    if not published['all_pass']:
        raise ValueError('COMMITTED_ASSEMBLY_SOURCE_PUBLICATION_FAILED:'+json.dumps(published['errors']))
    print(json.dumps(dict(assembly_sha=assembly_sha,owner_files=len(files),published_owner_files_checked=published['published_owner_files_checked'],committed_tree_verified=True,source_map_sha256=hashlib.sha256(doc.read_bytes()).hexdigest())))

if __name__=='__main__':main()
