#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the offline Pick'em Auditor toolchain.
# Matches .github/workflows/ci.yml offline-tests: Python 3.12 (image default),
# runtime collectors, pytest, the lightweight NFL inference stack, and PyYAML
# for workflow validation. The paused joint NUTS stack in
# requirements-joint-bayes.txt is intentionally not installed.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

# Archive restore and shadow-store tests call `zstd` and `python`.
# GitHub-hosted Ubuntu provides both; the default Cloud Agent image does not.
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y --no-install-recommends zstd python-is-python3

python3 -m pip install --user \
  -r requirements.txt \
  -r requirements-dev.txt \
  -r requirements-nfl-inference.txt \
  'PyYAML==6.0.2'

# Login shells do not load ~/.bashrc, so console scripts in ~/.local/bin
# would be invisible. Publish them on the default PATH.
if [ -d "${HOME}/.local/bin" ]; then
  shopt -s nullglob
  for cmd in "${HOME}/.local/bin"/*; do
    [ -x "$cmd" ] || continue
    sudo ln -sfn "$cmd" "/usr/local/bin/$(basename "$cmd")"
  done
fi

python3 - <<'PY'
import httpx
import nba_api
import nflreadpy
import nhlpy
import numpy
import polars
import pytest
import scipy
import yaml

print(
    "pickem-auditor imports ok",
    f"numpy={numpy.__version__}",
    f"scipy={scipy.__version__}",
)
PY
