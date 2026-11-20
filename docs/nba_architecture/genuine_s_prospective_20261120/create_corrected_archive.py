"""Corrected replay packaging, not a new or replacement forecast execution."""
from pathlib import Path
import json
from datetime import datetime,timezone
import subprocess
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.p1_subset_handoff_v1 import digest
from v2.nba_architecture.prospective_s_archive_v1 import create_archive

root=Path(__file__).resolve().parent
original=root/'actual_forecast'
forecast_raw=(original/'forecast.json').read_bytes();forecast=json.loads(forecast_raw)
started=datetime.now(timezone.utc).isoformat()
record=create_archive(root/'corrected_archive',forecast,forecast_at=forecast['forecast_at'],**frozen_inputs(original))
assert (root/'corrected_archive/forecast.json').read_bytes()==forecast_raw
print(json.dumps(dict(schema='nba-corrected-replay-archive-receipt/1.0.0',kind='CORRECTED_ARCHIVE_OF_UNCHANGED_ORIGINAL_FORECAST',
    original_actual_manifest_raw_sha256=digest((original/'manifest.json').read_bytes()),
    original_forecast_raw_sha256=digest(forecast_raw),original_forecast_at=forecast['forecast_at'],
    archive_creation_started_at=started,archive_creation_completed_at=datetime.now(timezone.utc).isoformat(),
    implementation_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    new_forecast_issued=False,original_forecast_replaced=False,**record),indent=2))
