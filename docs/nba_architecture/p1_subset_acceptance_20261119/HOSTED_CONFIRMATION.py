# Inputs confirmation_mode=probe or capture; research source confirmation only.
import base64
from datetime import datetime,timezone
import hashlib,io,json,pathlib,sys,tarfile,tempfile
from urllib.request import Request,urlopen
PIN='84c577dbe382673da016d79362836b0eb8944694'
STORE=pathlib.Path('/work/reports/p1_subset_confirmation_20261119')
STORE.mkdir(parents=True,exist_ok=True)
FILES={'scripts/nba_p1_capture_subset.py': '541e1c5cf14e18722a894e71217d86b77304b1483933b9a47af6d1cdbea8cd48', 'scripts/nba_p1_prospective_capture.py': '4df0240932dcfed1c4a243b6015b152618a36d69d03bdcd6f505080ca45da68b', 'v2/nba_architecture/p1_subset_capture_v1.py': '41bec1d26e6a63d1fb8bb5c135574a50f05aadb3dfab84bc43be4db29348d0d9', 'v2/nba_architecture/p1_subset_handoff_v1.py': '745c333f110dea7d16ec74aca3a6179cc9bc043468c1f0bf081157946d48ff68', 'v2/nba_architecture/research_profile_v1.py': 'bc25182f07f86f695ae0fefdf4a3a0b8924808c67bbcd809484824337e7ee070', 'v2/nba_architecture/p1_capture_v1.py': '581e37de6be49e7a0efe74741dcec5c294e50937bfcd9885226363c7157a5e91', 'v2/nba_architecture/gamebook_identity_v1.py': '51ebbe20652a8beb776e2bfcf887825e9b7a441bda3532420181d4465670fe55', 'v2/nba_architecture/v2_contracts.py': 'e3b703ef7630e50f9778bf469506ebce2d0841698d5878b825448a3cd70afeb4', 'config/nba_research_profile.json': '951cb869d0fb8e83f272f1d4d3964bee602353ffd47c723c3147c42044087b50', 'docs/nba_architecture/p1_subset_acceptance_20261119/TONIGHT_COHORT.json': '22899006400a656dc6f7997aaaabcf201430d5eebe0c65704b35729c168a378f'}
with tempfile.TemporaryDirectory(prefix='p1_subset_confirmation_') as tmp:
    root=pathlib.Path(tmp)
    for name,expected in FILES.items():
        with urlopen(Request('https://raw.githubusercontent.com/royalexx/pickem-auditor/'+PIN+'/'+name,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as response:raw=response.read()
        if hashlib.sha256(raw).hexdigest()!=expected:raise RuntimeError('PINNED_BYTES_CHANGED:'+name)
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    sys.path.insert(0,str(root))
    from v2.nba_architecture.p1_subset_capture_v1 import capture_subset
    cohort=json.loads((root/'docs/nba_architecture/p1_subset_acceptance_20261119/TONIGHT_COHORT.json').read_bytes())
    if confirmation_mode=='probe':
        marker=STORE/'storage_probe.json'
        if not marker.exists():
            with marker.open('x') as stream:json.dump({'created_at':datetime.now(timezone.utc).isoformat(),'pin':PIN},stream)
        print('P1_SUBSET_CONFIRMATION_PROBE_READY',PIN,cohort['game_id'],flush=True)
    elif confirmation_mode=='capture':
        now=datetime.now(timezone.utc)
        if not datetime(2026,11,19,23,0,tzinfo=timezone.utc)<=now<datetime(2026,11,19,23,15,tzinfo=timezone.utc):raise RuntimeError('OUTSIDE_PREREGISTERED_CONFIRMATION_WINDOW')
        with (STORE/'claim.json').open('x') as stream:json.dump({'claimed_at':now.isoformat(),'pin':PIN},stream)
        result=capture_subset(cohort,STORE/'capture')
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w:gz') as archive:archive.add(STORE/'capture',arcname='capture')
        raw=buffer.getvalue();encoded=base64.b64encode(raw).decode('ascii');parts=[]
        for i in range(0,len(encoded),32000):
            name='part-%04d.txt'%(i//32000);(STORE/name).write_text(encoded[i:i+32000]);parts.append(name)
        manifest={'archive_domain':'GZIP_TAR_OF_RAW_CAPTURE_AND_REQUEST_OUTPUTS','archive_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'parts':parts,'capture_result':result}
        with (STORE/'finish.json').open('x') as stream:json.dump(manifest,stream,indent=2)
        print('P1_SUBSET_OPERATIONAL_CONFIRMATION',json.dumps(manifest),flush=True)
    else:raise RuntimeError('UNKNOWN_CONFIRMATION_MODE')
