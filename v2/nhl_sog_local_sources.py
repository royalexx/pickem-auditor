"""Exact-byte local verification snapshots, durably anchored by an immutable ZIP.

Copying is not acquisition: original received_at, raw hashes and HMACs remain.
No signature is minted here. Source consumers still run all existing verifiers.
"""
from pathlib import Path,PurePosixPath
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,tempfile,zipfile,os


def safe(root,relative):
    p=PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts or '\\' in relative or '\x00' in relative:
        raise ValueError('UNSAFE_SOURCE_MEMBER')
    target=Path(root).joinpath(*p.parts)
    if not target.resolve().is_relative_to(Path(root).resolve()):raise ValueError('SOURCE_MEMBER_ESCAPE')
    return target


def copy_members(original,local,rels):
    """Expected path names are archive-relative, never arbitrary absolute paths."""
    original=Path(original)
    def one(rel):
        # Do not resolve a remote deep directory repeatedly. Reject all path
        # traversal first; source bytes must subsequently satisfy signed hashes.
        p=PurePosixPath(rel)
        if p.is_absolute() or '..' in p.parts or '\\' in rel:raise ValueError('UNSAFE_SOURCE_MEMBER')
        raw=(original/rel).read_bytes();dest=safe(local,rel);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(raw)
    members=sorted(set(rels))
    if len(members)<=8:
        for member in members:one(member)
    else:
        with ThreadPoolExecutor(max_workers=8) as ex:list(ex.map(one,members))


def stage_pool(pool,*,include_derived=False):
    local=Path(tempfile.mkdtemp(prefix='nhl_sog_source_snapshot_'))
    rels=[]
    folders=('raw_http_body','c03_collector_receipts')+(('nhl_sog_official_derived',) if include_derived else ())
    for folder in folders:
        for p in (Path(pool)/folder).glob('*'):
            if p.suffix in ('.json','.bin'):rels.append(folder+'/'+p.name)
    copy_members(pool,local,rels)
    return local


def publish_bundle(pool,local,manifest):
    """Package only source/derived files, with deterministic metadata and names."""
    local=Path(local);fd,tmp=tempfile.mkstemp(suffix='.zip');os.close(fd)
    try:
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for folder in ('raw_http_body','c03_collector_receipts','nhl_sog_official_derived'):
                for p in sorted((local/folder).glob('*')):
                    info=zipfile.ZipInfo(folder+'/'+p.name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                    z.writestr(info,p.read_bytes())
        raw=Path(tmp).read_bytes();sha=hashlib.sha256(raw).hexdigest();rel='history_bundles/'+sha+'.zip'
        target=Path(pool)/rel;target.parent.mkdir(parents=True,exist_ok=True)
        try:
            with target.open('xb') as f:f.write(raw)
        except FileExistsError:pass
        if hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise ValueError('SOURCE_BUNDLE_HASH_DRIFT')
        doc={**manifest,'source_bundle':{'path':rel,'sha256':sha,'format':'exact_original_receipts_and_derived_zip_v1'}}
        payload=json.dumps(doc,sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=hashlib.sha256(payload).hexdigest()
        p=Path(pool)/'daily_history_manifests'/(digest+'.json');p.parent.mkdir(parents=True,exist_ok=True)
        with p.open('xb') as f:f.write(payload)
        return doc,{'path':str(p),'sha256':digest}
    finally:os.unlink(tmp)


def open_history_sources(pool,manifest):
    bundle=manifest.get('source_bundle')
    if not bundle:return stage_pool(pool,include_derived=True)
    raw=safe(pool,bundle['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=bundle['sha256']:raise ValueError('SOURCE_BUNDLE_HASH_DRIFT')
    local=Path(tempfile.mkdtemp(prefix='nhl_sog_verified_bundle_'))
    import io
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist())>1_000_000_000:raise ValueError('SOURCE_BUNDLE_TOO_LARGE')
        for info in z.infolist():
            dest=safe(local,info.filename)
            if info.is_dir():dest.mkdir(parents=True,exist_ok=True)
            else:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(info))
    return local


def stage_packets(pool):
    """Rehydrate only completed original response packets; partial ones abstain."""
    local=Path(tempfile.mkdtemp(prefix='nhl_original_packets_',dir='/tmp'))
    rejected=[]
    def one(path):
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=path.stem:
            rejected.append(path.name);return
        import io
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for member in z.infolist():
                dest=safe(local,member.filename);dest.parent.mkdir(parents=True,exist_ok=True)
                # Concurrent packets may share identical content-addressed bodies.
                data=z.read(member)
                try:
                    with dest.open('xb') as f:f.write(data)
                except FileExistsError:pass
    with ThreadPoolExecutor(max_workers=8) as ex:list(ex.map(one,sorted((Path(pool)/'source_packets').glob('*.zip'))))
    return local,rejected
