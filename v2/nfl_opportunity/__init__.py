"""NFL Phase 2 opportunity research — CPU-only shadow experiment.

Deliberately separate from Phase 0R certificates, Phase 1 production approval,
Phase 3 catch/yardage likelihoods, and live pick ranking.
"""
from .simulation import simulate_nfl_opportunities
from .replay import replay_nfl_opportunity_cases

__all__ = ("simulate_nfl_opportunities", "replay_nfl_opportunity_cases")
