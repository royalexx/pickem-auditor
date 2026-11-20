"""Independent harmless forged-archive control; no models, source data or fit."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.prospective_s_archive_v1 import verify_archive

with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);script=root/'reader/scripts/nba_genuine_s.py';script.parent.mkdir(parents=True)
    body=b'print(\'{"payload_sha256":"'+b'0'*64+b'"}\')\n';script.write_bytes(body)
    manifest=dict(schema='nba-genuine-S-offline-archive/1.0.0',files={
        'reader/scripts/nba_genuine_s.py':dict(sha256=digest(body),bytes=len(body),byte_domain='EXACT_ARCHIVED_FILE_BYTES')},
        candidate_denominator=35,attempt_denominator=140,forecasted_rows=140,abstained_rows=0,
        payload_sha256='0'*64,production_release=False)
    raw=canonical(manifest);(root/'manifest.json').write_bytes(raw)
    try:result=verify_archive(root,expected_manifest_sha256=digest(raw));outcome='FORGED_ARCHIVE_ACCEPTED'
    except Exception as exc:result=dict(error_type=type(exc).__name__,error=str(exc));outcome='FORGED_ARCHIVE_REJECTED'
    print(json.dumps(dict(outcome=outcome,verification=result,
        tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        archive_code_raw_sha256=digest((ROOT/'v2/nba_architecture/prospective_s_archive_v1.py').read_bytes()),
        qualification='No genuine source, admitted model, forecast, fit or score exists in this synthetic forged archive.'),indent=2))
