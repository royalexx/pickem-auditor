# Deepnote input capture_mode: probe | pregame | morning. No model or gate changes.
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.request import Request, urlopen

PIN='aaeb0601c006d55d3812dc64cf29695a72eda58b'
FILES={
 'scripts/nba_p1_prospective_capture.py':'4df0240932dcfed1c4a243b6015b152618a36d69d03bdcd6f505080ca45da68b',
 'docs/nba_architecture/p1_prospective_20261118/COHORT.json':'692d662a8a256d46e36bc416225e2eb22136e5da41f2a486d725469f704e91b9',
 'v2/nba_architecture/p1_capture_v1.py':'581e37de6be49e7a0efe74741dcec5c294e50937bfcd9885226363c7157a5e91',
}
STORE=Path('/work/reports/nba_p1_one_night_20261118')
STORE.mkdir(parents=True,exist_ok=True)
marker=STORE/'storage_probe.json'
previous=json.loads(marker.read_text()) if marker.exists() else None
if previous is None:
    with marker.open('x') as stream:json.dump({'created_at':datetime.now(timezone.utc).isoformat(),'purpose':'P1_SUPPLEMENTAL_STORAGE_PROBE'},stream)
print('P1_STORAGE_PROBE',json.dumps({'prior_marker_seen':previous is not None,'path':str(marker),'mode':capture_mode}),flush=True)
with tempfile.TemporaryDirectory(prefix='p1_fixed_capture_') as tmp:
    root=Path(tmp)
    for relative,expected in FILES.items():
        with urlopen(Request('https://raw.githubusercontent.com/royalexx/pickem-auditor/'+PIN+'/'+relative,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as response:raw=response.read()
        if hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('PINNED_CODE_OR_COHORT_CHANGED:'+relative)
        target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    if capture_mode=='probe':
        print('P1_HOSTED_PINNED_CODE_READY',PIN,flush=True)
    else:
        if capture_mode not in ('pregame','morning'):raise RuntimeError('UNKNOWN_MODE')
        now=datetime.now(timezone.utc)
        if capture_mode=='pregame' and not datetime(2026,11,18,23,0,tzinfo=timezone.utc)<=now<datetime(2026,11,18,23,45,tzinfo=timezone.utc):raise RuntimeError('OUTSIDE_BOUNDED_WORKER_LAUNCH_WINDOW')
        if capture_mode=='morning' and not datetime(2026,11,19,5,0,tzinfo=timezone.utc)<=now<datetime(2026,11,20,5,0,tzinfo=timezone.utc):raise RuntimeError('OUTSIDE_ONE_NIGHT_MORNING_WINDOW')
        claim=STORE/(capture_mode+'_claim.json')
        with claim.open('x') as stream:json.dump({'claimed_at':now.isoformat(),'pin':PIN},stream)
        times=[datetime(2026,11,18,23,30,tzinfo=timezone.utc),datetime(2026,11,18,23,40,tzinfo=timezone.utc)] if capture_mode=='pregame' else [now]
        for due in times:
            while datetime.now(timezone.utc)<due:
                time.sleep(min(30,(due-datetime.now(timezone.utc)).total_seconds()))
            cmd=[sys.executable,str(root/'scripts/nba_p1_prospective_capture.py'),'--stage',capture_mode,'--output',str(STORE/'captures')]
            result=subprocess.run(cmd,cwd=root,env={**os.environ,'PYTHONPATH':str(root)},capture_output=True,text=True,timeout=240)
            stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            (STORE/(stamp+'.stdout')).write_text(result.stdout);(STORE/(stamp+'.stderr')).write_text(result.stderr)
            print('P1_CAPTURE_EXIT',result.returncode,result.stdout,result.stderr[-800:],flush=True)
            if result.returncode:raise RuntimeError('P1_CAPTURE_EXECUTION_FAILED')
            # Export preserved binary evidence through small base64 text chunks for MCP.
            buffer=io.BytesIO()
            with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
                for item in sorted((STORE/'captures').iterdir()):archive.add(item,arcname=item.name)
            raw=buffer.getvalue();encoded=base64.b64encode(raw).decode('ascii')
            export=STORE/('export-'+stamp);export.mkdir()
            chunks=[]
            for i in range(0,len(encoded),32000):
                name='part-%04d.txt'%(i//32000);chunk=encoded[i:i+32000];(export/name).write_text(chunk);chunks.append(name)
            meta={'archive_domain':'GZIP_TAR_OF_UNMODIFIED_CAPTURE_FILES','archive_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'parts':chunks,'capture_mode':capture_mode,'created_at':datetime.now(timezone.utc).isoformat()}
            (export/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
            with (STORE/('latest_'+capture_mode+'.json')).open('w') as stream:json.dump({'export_path':str(export),'manifest':meta},stream,indent=2)
            print('P1_CAPTURE_EXPORT',str(export),json.dumps(meta),flush=True)
        with (STORE/(capture_mode+'_finish.json')).open('x') as stream:json.dump({'completed_at':datetime.now(timezone.utc).isoformat(),'pin':PIN},stream)
