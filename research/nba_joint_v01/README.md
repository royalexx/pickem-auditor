# NBA WS5 v0.1 research engine

Read `REPORT.md`, `INTEGRATION.md`, `experiment.json` and `audit_amendment.json` before interpreting results. This is an implemented, tested, research-only simulator. M0 remains the exposure benchmark. New J2 distributions fail the measured marginal comparison. No production, Tier or prospective certification is granted.

From the repository root, use a new output directory on every execution:

```bash
OPENBLAS_NUM_THREADS=1 python -m v2.nba_joint --fixture --scenarios 128 --seed 20261115 --output work/nba_joint_fixture_new
OPENBLAS_NUM_THREADS=1 python -m research.nba_joint_v01.reproduce --output work/nba_joint_replay_new
python -m unittest discover -s tests/nba_ws1 -v
python -m unittest discover -s tests -p test_nba_opportunity.py -v
python -m unittest discover -s tests -p 'test_nba_joint*.py' -v
python -m unittest discover -s tests/nba_ws4 -v
```

The replay restores source shards using Git at `97a8bb566826afe5a3e5a7b8c632043d8a1dca24` and exact preserved boxscore bytes. It does not recapture sources or change the model. It compares all 145 scientific scenario hashes and exact score bytes to the frozen results. Fetch that commit from `data/bayesian-history` first if your clone lacks it. Runtime and peak RSS naturally differ and are excluded from scientific equality.

`python -m v2.nba_joint --input research/nba_joint_v01/results/inputs/401704627.json --model research/nba_joint_v01/results/model.json --scenarios 128 --seed 20261115 --output work/nba_joint_historical_single_new` executes one frozen historical research input, with the same explicit retrospective/conditional labels. It writes the full scenarios, empirical distributions and immutable manifest. The CLI does not import any production forecaster or scheduler.

`python -m v2.nba_joint --snapshot research/nba_joint_v01/prospective_canary/snapshots/2a4d359356f9e4a557c79c20914730651cf2abaac3211e587f83b56663e3ca56.json --output work/nba_joint_source_gate_new` writes a rejection receipt and exits 2, as required. Do not weaken `require_usable` to turn it into a forecast. Prospective source adapters additionally require original source bytes, exact feature derivation, model cutoffs and supplied source-backed participation evidence; a caller boolean cannot grant certification.

The independent WS4 bridge runs with `python -m research.nba_joint_v01.ws4_adapter`; its frozen output already exists, so use a fresh copied results directory if rerunning the bridge. It checks actual scenario envelopes, full count PMFs and date/game paired CRPS. Its boundary pass does not retroactively authenticate historical sources or externally approve the model.

Minimal engine dependencies are NumPy/SciPy. Exact local versions are in `requirements-runtime.txt`; full environment details are in `results/audit_summary.json`. WS2's optional research-replay tests also use pandas and scikit-learn. Cross-runtime integer events matched Deepnote, while full float hashes differ; do not claim cross-version bitwise identity.

`initial_exploratory/` preserves first scores. `pre_score_conditioning/` preserves the full pre-final-score-fix run and its reproduction check. `results/` is the final corrected evidence. `inputs/official/` contains lossless compressed retrospective provider bytes. `prospective_canary/` contains original pregame source bytes and its blocked-state receipt. No original production archive is changed.
