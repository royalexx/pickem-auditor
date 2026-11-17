"""Root-discovery compatibility import for the immutable NBA golden fixtures.

Dedicated NBA discovery imports ``golden_v2`` directly from nba_architecture.
Root discovery puts tests/ on sys.path instead; re-export the same fixture
module so both supported unittest entrypoints exercise identical assertions.
The canonical fixture source remains tests/nba_architecture/golden_v2.py.
"""
from nba_architecture.golden_v2 import *  # noqa: F401,F403
