"""Reproduce structural S execution from frozen synthetic bytes; never fitting."""
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tests.nba_architecture.test_subset_p2_dispatch_v1 import control_inputs
from v2.nba_architecture.p1_subset_handoff_v1 import canonical,digest
from v2.nba_architecture.subset_p2_dispatch_v1 import structural_dispatch_control

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
b,c,a,m,r=control_inputs()
inputs={'binding.json':canonical(b),'contract.json':canonical(asdict(c)),
        'artifact.raw':a,'manifest.raw':m,'raw_sources.raw':r}
for name,raw in inputs.items():(out/name).write_bytes(raw)
result=structural_dispatch_control(b,c,a,m,r);(out/'result.json').write_bytes(canonical(result))
receipt=dict(command=sys.argv,tested_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
    executed_at=datetime.now(timezone.utc).isoformat(),kind='SYNTHETIC_ENGINEERING_NO_ADMISSION_NO_FIT',
    input_hashes={name:digest(raw) for name,raw in inputs.items()},output_sha256=digest(canonical(result)),
    byte_domains={'artifact.raw':'ORIGINAL_FROZEN_SYNTHETIC_MODEL_BYTES','manifest.raw':'CANONICAL_SYNTHETIC_MANIFEST_DERIVED_FROM_FROZEN_INPUTS',
        'raw_sources.raw':'ORIGINAL_FROZEN_SYNTHETIC_BODY_MAP_BYTES','binding.json':'CANONICAL_SYNTHETIC_BINDING',
        'contract.json':'CANONICAL_STRUCTURAL_CONTROL_CONTRACT_NOT_REAL_ADMISSION','result.json':'CANONICAL_ACTUAL_NATIVE_CONTROL_RESULT'})
(out/'receipt.json').write_bytes(canonical(receipt));print(json.dumps(dict(receipt,admitted=result['admitted'],
    actual_native_model_executed=result['result']['actual_native_model_executed']),indent=2))
