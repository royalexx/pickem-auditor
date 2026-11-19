"""Persist an original captured raw body and HMAC proof in one exact-byte packet.

Only storage packaging changes. The original signed transport runs locally;
its original receipt, raw SHA, timestamps, and proof bytes remain unchanged.
A packet is durable before the acquisition callback returns it as available.
"""
from pathlib import Path
import hashlib,io,zipfile,threading
_ready=set()
_lock=threading.Lock()


def persist_packet(canonical_pool,local_pool,receipt):
    members=(receipt['archive_path'],receipt['collector_proof_archive_path'])
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(members):
            p=Path(rel)
            if p.is_absolute() or '..' in p.parts or '\\' in rel:raise ValueError('UNSAFE_PACKET_MEMBER')
            info=zipfile.ZipInfo(rel,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,(Path(local_pool)/rel).read_bytes())
    raw=buf.getvalue();sha=hashlib.sha256(raw).hexdigest()
    folder=Path(canonical_pool)/'source_packets'
    if str(folder) not in _ready:
        with _lock:
            if str(folder) not in _ready:
                folder.mkdir(parents=True,exist_ok=True);_ready.add(str(folder))
    path=folder/(sha+'.zip')
    try:
        with path.open('xb') as f:f.write(raw)
    except FileExistsError:pass
    if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('SOURCE_PACKET_HASH_DRIFT')
    return {'path':'source_packets/'+sha+'.zip','sha256':sha}
