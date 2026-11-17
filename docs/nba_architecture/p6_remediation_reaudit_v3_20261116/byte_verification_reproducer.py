import subprocess,json,hashlib
from pathlib import Path
import argparse
ap=argparse.ArgumentParser();ap.add_argument('--repo',required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();repo=args.repo;out=args.output;out.mkdir(parents=True,exist_ok=False)
sha='53c01a9eabb9ed09b5c3186eae0d086b07bcc891'; warehouse='97a8bb566826afe5a3e5a7b8c632043d8a1dca24'
raw=subprocess.check_output(['git','show',sha+':docs/nba_ws1/coverage.json'],cwd=repo); m=json.loads(raw);(out/'ws1_coverage_manifest.json').write_bytes(raw)
rows=[]
for item in m['source_manifest']:
 b=subprocess.check_output(['git','show',warehouse+':'+item['path']],cwd=repo)
 h=hashlib.sha256(b).hexdigest(); rows.append(dict(path=item['path'],observed_bytes=len(b),observed_sha256=h,expected_sha256=item['sha256'],pass_check=h==item['sha256'] and len(b)==item['bytes']))
r=dict(warehouse_sha=warehouse,manifest_sha=sha,manifest_raw_sha256=hashlib.sha256(raw).hexdigest(),files=len(rows),total_compressed_bytes=sum(x['observed_bytes'] for x in rows),verified=sum(x['pass_check'] for x in rows),files_receipts=rows,decompressed=False,historical_availability_certified=False,note='Opaque compressed-byte integrity only. No holdout outcomes decompressed or scored.')
(out/'independent_archive_bytes.json').write_text(json.dumps(r,indent=2)+'\n'); print({k:v for k,v in r.items() if k!='files_receipts'})
