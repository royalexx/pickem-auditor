"""Canonical P3 native fixture helper for root discovery; no test re-export."""
from importlib.util import find_spec

if find_spec('nba_architecture.test_p3_p1_native_v4') is not None:
    from nba_architecture.test_p3_p1_native_v4 import native_fixture
