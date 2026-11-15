#!/usr/bin/env bash
set -euo pipefail
# Run from repository root. Only writes work/ inputs and WS2 results.
mkdir -p work/ws2_input
for season in 2024 2025; do
  git show 97a8bb566826afe5a3e5a7b8c632043d8a1dca24:data/bayesian_warehouse/populations/nba/points/${season}.jsonl.gz > work/ws2_input/${season}.jsonl.gz
done
export OPENBLAS_NUM_THREADS=1
python -m unittest discover -s tests -p test_nba_opportunity.py -v
python -m research.nba_ws2.run_experiment --input work/ws2_input --output research/nba_ws2/results
python -m research.nba_ws2.team_benchmark
python -m research.nba_ws2.context_diagnostic --input work/ws2_input --output research/nba_ws2/results --cache work/ws2_context
python -m research.nba_ws2.supplemental_report
