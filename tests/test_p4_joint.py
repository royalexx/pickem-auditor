"""Optional canonical P4 fixture helpers; root collection remains unique."""
from importlib.util import find_spec

if find_spec('nba_architecture.test_p4_joint') is not None:
    from nba_architecture.test_p4_joint import PARAMETERS, reseal, fixture
