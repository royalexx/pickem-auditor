"""Phase 0 release gate: preserve old forecasts but suspend unvalidated Tiers 1/2.

A numerical P(win) or source-attested lineup is not evidence of a calibrated
real-market >80% hit rate. This policy only governs *publication*, never the
immutable forecast, settlement, model comparison, or Tier 3 research paths.
"""
from __future__ import annotations

import os

VERSION = "pickem-phase0-high-confidence-suspension-v1"
SUSPENDED = frozenset(("Tier 1", "Tier 2"))
REASON = "PHASE0_REAL_MARKET_HIGH_CONFIDENCE_NOT_PROSPECTIVELY_CERTIFIED"


def production_context() -> bool:
    """Explicit workflow/CLI release context. Standalone historical tests stay frozen."""
    return (os.environ.get("PICKEM_PRODUCTION_CONSENSUS") == "1"
            or os.environ.get("PICKEM_PHASE0_RELEASE_GUARD") == "1")


def authorize(tier: str, *, production: bool = False) -> dict:
    blocked = tier in SUSPENDED and (production or production_context())
    return {
        "schema": VERSION,
        "tier": tier,
        "publication_eligible": not blocked,
        "reason": REASON if blocked else None,
        "production_context": bool(production or production_context()),
        "legacy_60_40_preserved_for_comparison": True,
        "calibrated_tier_hit_rate_certified": False,
    }
