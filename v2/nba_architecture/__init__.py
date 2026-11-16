"""NBA S/O/J/C P0 contract-only research boundary; no fitting or release."""
from .contracts import (
    VERSION, ContractError, seal, verify_seal, freeze_once, seed_for,
    validate_pregame, validate_statistical, validate_opportunity,
    validate_game_state, validate_joint, validate_forecast,
    validate_evaluation, validate_bundle, threshold_triplet, joint_stat_pmf,
)
