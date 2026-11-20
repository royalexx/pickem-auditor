"""Record exact commands, streams and unchanged tested runtime byte manifest."""
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import subprocess,sys

root=Path(__file__).resolve().parents[4];out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
def clock():return datetime.now(timezone.utc).isoformat()
def files():
    paths=subprocess.check_output(['git','ls-files','--','*.py'],cwd=root,text=True).splitlines()
    return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths if not p.startswith('docs/')}
before=files();sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
argv=[sys.executable,'-m','unittest','discover','-s','tests','-q'];started=clock()
with (out/'stdout').open('wb') as stdout,(out/'stderr').open('wb') as stderr:
    result=subprocess.run(argv,cwd=root,env=dict(os.environ,PYTHONPATH='.'),stdout=stdout,stderr=stderr)
after=files();receipt=dict(tested_commit=sha,argv=argv,cwd=str(root),started_at=started,completed_at=clock(),
    exit_code=result.returncode,runtime_python_bytes_unchanged=before==after,runtime_python_raw_sha256=before,
    stdout_raw_sha256=hashlib.sha256((out/'stdout').read_bytes()).hexdigest(),stderr_raw_sha256=hashlib.sha256((out/'stderr').read_bytes()).hexdigest(),
    byte_domain='EXACT_REPOSITORY_FILE_AND_REDIRECTED_PROCESS_STREAM_BYTES',no_fitting_or_live_network_requested=True)
(out/'COMMAND.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items() if k!='runtime_python_raw_sha256'},indent=2))
sys.exit(result.returncode if before==after else 3)
