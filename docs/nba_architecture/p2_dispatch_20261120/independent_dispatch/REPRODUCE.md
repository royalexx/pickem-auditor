# Reproduce the independent dispatcher review

The exact reviewed implementation is `3669bf79273463eb34c1b76a1ef5a1e9151ca3b3`. Use that candidate's five implementation/test files and unchanged accepted original files. The later review-only commit supplies `independent_probe.py` and evidence; it must not be substituted for a different implementation. Python/numpy/scipy/pytest/jsonschema versions are recorded in `environment.json`.

From repository root, first verify this packet:

```bash
cd docs/nba_architecture/p2_dispatch_20261120/independent_dispatch
sha256sum -c SHA256SUMS
cd ../../../..
```

Before the frozen target's `2026-11-20T01:00Z` start, run the independent probe into a fresh directory. It creates an actual current-clock public CLI run, performs nine public review methods, retains exact argv/stdout/stderr/receipts/archives, and performs no fitting or scoring:

```bash
mkdir -p /tmp/nba-p2-independent-review
NBA_P2_REVIEW_OUTPUT=/tmp/nba-p2-independent-review \
  python docs/nba_architecture/p2_dispatch_20261120/independent_dispatch/independent_probe.py \
  > /tmp/nba-p2-independent-review/probe.stdout \
  2> /tmp/nba-p2-independent-review/probe.stderr
```

The directory `/tmp/nba-p2-independent-review/actual_current_cli` must be absent initially because the CLI refuses overwrites. After target start, do not relabel a historical clock as current: the probe's current-clock CLI is expected to fail closed. To rerun the complete independent positive/negative review with an explicitly recorded clock:

```bash
mkdir -p /tmp/nba-p2-independent-recorded-review
NBA_P2_REVIEW_OUTPUT=/tmp/nba-p2-independent-recorded-review \
NBA_P2_REVIEW_FORECAST_AT=2026-11-20T00:22:38.008017+00:00 \
  python docs/nba_architecture/p2_dispatch_20261120/independent_dispatch/independent_probe.py \
  > /tmp/nba-p2-independent-recorded-review/probe.stdout \
  2> /tmp/nba-p2-independent-recorded-review/probe.stderr
```

Its CLI output folder is `recorded_replay_cli`; its receipt must say `RECORDED_CLOCK_REPLAY`. An execution of this final reusable reviewer script is retained under `recorded_reproduction/`. To run only the public CLI recorded replay:

```bash
python scripts/nba_subset_p2_dispatch.py \
  --capture docs/nba_architecture/p1_subset_acceptance_20261119/initial_tonight_capture \
  --cohort docs/nba_architecture/p1_p5_handoffs_20261119/PROSPECTIVE_COHORT.json \
  --history docs/nba_architecture/p1_p5_handoffs_20261119/prospective_inputs \
  --forecast-at 2026-11-20T00:22:38.008017+00:00 \
  --output /tmp/nba-p2-explicit-recorded-replay
```

That output directory must also be absent. Its receipt must say `RECORDED_CLOCK_REPLAY`; it is not a new historical pregame forecast. Deterministic source/native/dispatch outputs should match the original clock's output wires; execution receipts retain actual operation clocks.

The candidate's own dispatcher and archive regressions can be rerun at any later time because they use explicit recorded inputs:

```bash
python -m pytest -v tests/nba_architecture/test_subset_p2_dispatch_v1.py
python -m pytest -v tests/nba_c/test_subset_dispatch_archive_v1.py
```

The independent probe exercises an existing frozen synthetic S fixture through the public structural wrapper. It observes native prediction and write-once calls, independently sums integer support for Over/Under/Push checks, tests source/model/role/training/clock and output mutations, inventories rejected supplied files, checks exact old reader bytes, and reconstructs the new archive while blocking original input paths. All archive mutation controls act on temporary copies. There is no model fitting, training/holdout decompression, target outcome retrieval or scoring.

`RESULTS.json` contains the exact tested SHA, code hashes, native structural result, actual command clocks, complete real-data counts, archive manifest and checksum counts. `actual_cli.stdout`/`.stderr` and `probe.stdout`/`.stderr` are raw successful command streams. `reproduction/` is another current-clock execution; `recorded_reproduction/` executes the final reusable probe's explicit replay path. Earlier reviewer-only failures are retained as described in `REVIEWER_FAILURES.md`.

Dispatch wire hashes cover canonical compact JSON. Archive record IDs cover canonical compact JSON **plus one LF**. Archived source/model/code objects hash exact file bytes. Each CLI tree has its own recursive SHA256SUMS; this review packet's SHA256SUMS covers every retained file except itself. Hash-domain equality is not general source or model admission.
