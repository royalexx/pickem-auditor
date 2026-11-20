"""Explicit new research issuance from an actually later approved freeze."""
from pathlib import Path
import json
from scripts.nba_genuine_s import frozen_inputs
from v2.nba_architecture.full_predictive_runtime_v1 import issue_forecast

p=Path(__file__).resolve().parent;a=p.parent/'genuine_s_prospective_20261120/corrected_archive'
parent=(a/'forecast.json').read_bytes();old=json.loads(parent)
print(json.dumps(issue_forecast(p/'actual_full_forecast',parent,
    cohort=json.loads((p/'FULL_FORECAST_COHORT.json').read_bytes()),
    admission_path=p/'independent_full_law/ADMISSION.json',
    original_inputs=dict(frozen_inputs(a),forecast_at=old['forecast_at']),
    pbp_raw_dir=p/'raw',pbp_population_path=p/'PBP_POPULATION.json',
    model_card_path=p/'FULL_PLAYED_MODEL_CARD.json',protocol_path=p/'independent_protocol/DECISION.json'),indent=2))
