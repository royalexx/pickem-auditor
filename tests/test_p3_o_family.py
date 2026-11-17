"""Optional P3 fixture helper exports for root unittest discovery.

Owner implementations live on isolated branches. When P3 is present, import
its canonical helpers and propagate any import error. With no P3 suite there
are no P3 helper imports to resolve. No test cases are re-exported.
"""
from importlib.util import find_spec

if find_spec('nba_architecture.test_p3_o_family') is not None:
    from nba_architecture.test_p3_o_family import inputs, build
