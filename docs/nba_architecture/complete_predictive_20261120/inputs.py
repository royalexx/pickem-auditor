"""Explicit input bindings for this frozen cohort; no source discovery or fit."""
import json
from pathlib import Path
from scripts.nba_genuine_s import frozen_inputs

PACKET=Path(__file__).resolve().parent
ARCHIVE=PACKET.parent/'genuine_s_prospective_20261120/corrected_archive'


def full_inputs():
    parent=json.loads((ARCHIVE/'forecast.json').read_bytes())
    return dict(law_snapshot_path=PACKET/'FULL_S_CANDIDATE.json',
        cohort=json.loads((PACKET/'FULL_FORECAST_COHORT.json').read_bytes()),
        admission_path=PACKET/'independent_full_law/ADMISSION.json',
        original_inputs=dict(frozen_inputs(ARCHIVE),forecast_at=parent['forecast_at']),
        pbp_raw_dir=PACKET/'raw',pbp_population_path=PACKET/'PBP_POPULATION.json',
        model_card_path=PACKET/'FULL_PLAYED_MODEL_CARD.json',protocol_path=PACKET/'independent_protocol/DECISION.json')


def outcome_inputs():
    return dict(raw_dir=PACKET/'raw',population_path=PACKET/'PBP_POPULATION.json',
        original_raw_dir=ARCHIVE/'inputs/raw',spec_path=ARCHIVE/'inputs/spec.json',
        profile_path=PACKET/'independent_c_profile/DECISION.json')
