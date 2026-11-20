"""Actual-clock computation of a new candidate; never forecast issuance."""
from pathlib import Path
import json,subprocess,sys
from datetime import datetime,timezone
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.minute_integrated_s_v1 import replay

p=Path(__file__).resolve().parent
out=p/'execution';out.mkdir(exist_ok=False)
a=p.parent/'genuine_s_prospective_20261120/corrected_archive'
parent=json.loads((a/'forecast.json').read_bytes())
value=replay((a/'forecast.json').read_bytes(),forecast_at=parent['forecast_at'],**frozen_inputs(a))
(out/'candidate.json').write_text(json.dumps(value,sort_keys=True,separators=(',',':')))
command=[sys.executable,'-m','pytest','-v','tests/nba_architecture/test_minute_integrated_s_v1.py']
with (out/'tests.stdout').open('x') as stdout,(out/'tests.stderr').open('x') as stderr:r=subprocess.run(command,stdout=stdout,stderr=stderr)
receipt=dict(implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    invocation=[sys.executable,__file__],tests_command=command,test_exit_code=r.returncode,
    completed_at=datetime.now(timezone.utc).isoformat(),new_forecast_issued=False,
    attempts=value['attempt_denominator'],integrated=value['integrated_rows'],abstained=value['abstained_rows'])
(out/'COMMANDS.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt));raise SystemExit(r.returncode)
