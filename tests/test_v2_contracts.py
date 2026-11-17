"""Compatibility exports for legacy sibling imports during root discovery.

Only reusable fixture helpers are exported. The canonical test cases remain
in nba_architecture.test_v2_contracts and are collected there exactly once.
"""
from nba_architecture.test_v2_contracts import evaluation, reissue
