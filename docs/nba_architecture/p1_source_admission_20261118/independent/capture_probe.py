"""Independent actual native capture + create-only persistence check."""
import hashlib,json,sys
from pathlib import Path
from v2.nba_architecture.p1_capture_v1 import capture
url='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401070213'
p=Path(sys.argv[1]);r=capture(url,p)
assert r['status']==200
assert hashlib.sha256((p/'body.raw').read_bytes()).hexdigest()==r['raw_sha256']
assert r['source_published_at'] is None and r['correction_history_complete'] is None and r['admission']=='UNADMITTED'
try:capture(url,p)
except FileExistsError:print('create-only conflict rejected; first bytes preserved')
else:raise AssertionError('overwrite')
print(json.dumps(r,indent=2))
