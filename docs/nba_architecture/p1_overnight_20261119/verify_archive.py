"""Recover original body bytes; transport hash never substitutes source admission."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE=Path(__file__).resolve().parent
m=json.loads((HERE/'export_manifest.json').read_bytes())['manifest']
encoded=''.join((HERE/'transport'/name).read_text().strip() for name in m['parts'])
raw=base64.b64decode(encoded,validate=True)
assert len(raw)==m['bytes']
assert hashlib.sha256(raw).hexdigest()==m['archive_sha256']
(HERE/'original_capture_export.tar.gz').write_bytes(raw)
out=HERE/'raw';already_extracted=out.exists();out.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
    for member in archive.getmembers():
        path=Path(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isfile() or member.isdir()
    if already_extracted:
        for member in archive.getmembers():
            if member.isfile():assert (out/member.name).read_bytes()==archive.extractfile(member).read()
    else:archive.extractall(out,filter='data')
receipts=[]
for manifest in sorted(out.glob('*/SHA256SUMS')):
    verified=0
    for line in manifest.read_text().splitlines():
        expected,name=line.split('  ',1)
        path=manifest.parent/name
        assert path.resolve().is_relative_to(manifest.parent.resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected
        verified+=1
    attempt=json.loads((manifest.parent/'attempt.json').read_bytes())
    for name,r in attempt['sources'].items():
        body=manifest.parent/name/'body.raw'
        if 'raw_sha256' in r:assert hashlib.sha256(body.read_bytes()).hexdigest()==r['raw_sha256']
    receipts.append(dict(path=str(manifest.parent.relative_to(HERE)),stage=attempt['stage'],started_at=attempt['started_at'],completed_at=attempt['completed_at'],status=attempt['status'],errors=attempt['errors'],rows=attempt['returned_roster_rows'],verified_files=verified))
receipt={'archive_bytes':len(raw),'archive_sha256':m['archive_sha256'],'attempts':receipts,'original_pregame_admission':False}
(HERE/'archive_verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
