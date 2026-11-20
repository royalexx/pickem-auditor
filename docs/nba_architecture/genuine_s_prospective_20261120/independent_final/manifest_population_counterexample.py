"""Independent archive population/domain controls on a temporary genuine copy."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.prospective_s_archive_v1 import verify_archive
P=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'docs/nba_architecture/genuine_s_prospective_20261120/actual_forecast'
results=[]
for attack in ('extra_nested_manifest','false_file_byte_domain'):
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)/'archive';shutil.copytree(P,root)
        manifest=json.loads((root/'manifest.json').read_bytes())
        if attack=='extra_nested_manifest':
            (root/'inputs/extra').mkdir();(root/'inputs/extra/manifest.json').write_text('{"unlisted":"bytes"}')
        else:
            first=next(iter(manifest['files']));manifest['files'][first]['byte_domain']='FALSE_UNREVIEWED_DOMAIN'
            (root/'manifest.json').write_bytes(canonical(manifest))
        try:
            result=verify_archive(root,expected_manifest_sha256=digest((root/'manifest.json').read_bytes()));outcome='MUTATION_ACCEPTED'
        except Exception as exc:result=dict(error_type=type(exc).__name__,error=str(exc));outcome='MUTATION_REJECTED'
        results.append(dict(attack=attack,outcome=outcome,verification=result))
print(json.dumps(dict(archive_path=str(P),tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    code_raw_sha256=digest((ROOT/'v2/nba_architecture/prospective_s_archive_v1.py').read_bytes()),results=results),indent=2))
