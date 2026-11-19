"""Independent transport reconstruction and raw archive integrity check.
No fitting/scoring; this only examines the scheduled source-capture archive.
"""
import base64,hashlib,io,json,pathlib,tarfile
P=pathlib.Path(__file__).resolve().parents[1]
x=json.loads((P/'export_manifest.json').read_bytes())['manifest']
parts=x['parts'];assert len(parts)==len(set(parts))==72
encoded=''.join((P/'transport'/name).read_text().strip(' \r\n') for name in parts)
raw=base64.b64decode(encoded,validate=True)
assert len(raw)==x['bytes']==1717132
assert hashlib.sha256(raw).hexdigest()==x['archive_sha256']=='39d9176f2f5cdb4174b56c563aaff7f702b48737d3741702e693538c0e8dfff2'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
 members=archive.getmembers();names=[m.name for m in members];assert len(names)==len(set(names))
 for m in members:
  p=pathlib.PurePosixPath(m.name);assert not p.is_absolute() and '..' not in p.parts
  assert m.isfile() or m.isdir()
 blobs={m.name:archive.extractfile(m).read() for m in members if m.isfile()}
 verified=[]
 for name,body in blobs.items():
  if name.endswith('/SHA256SUMS'):
   base=pathlib.PurePosixPath(name).parent
   for line in body.decode().splitlines():
    digest,relative=line.split('  ',1);r=pathlib.PurePosixPath(relative);assert not r.is_absolute() and '..' not in r.parts
    target=str(base/r);assert hashlib.sha256(blobs[target]).hexdigest()==digest
   verified.append(name)
 attempts={name:json.loads(body) for name,body in blobs.items() if name.endswith('/attempt.json')}
 output={'archive_bytes':len(raw),'archive_sha256':hashlib.sha256(raw).hexdigest(),'transport_parts':len(parts),'safe_members':len(members),'raw_files':len(blobs),'attempt_manifests_verified':verified,'attempts':{name:{k:a.get(k) for k in ['stage','started_at','completed_at','returned_roster_rows','availability_unknown_rows','roster_denominators','status','errors']} for name,a in attempts.items()}}
 print(json.dumps(output,indent=2))
