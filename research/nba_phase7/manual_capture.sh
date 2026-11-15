#!/usr/bin/env bash
set -euo pipefail
: "${1:?Usage: bash research/nba_phase7/manual_capture.sh SLOT_NUMBER}"
OPENBLAS_NUM_THREADS=1 python -B -m research.nba_phase7.pilot capture --slot "$1" --output reports/nba_phase7_pilot
