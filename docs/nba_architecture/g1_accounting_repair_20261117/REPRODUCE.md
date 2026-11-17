# Exact accounting repair reproduction

Reviewed code candidate: `bafbcf2a09add125247c91c1cc8fc8d98987b5e9`.
Base: exact owner assembly `6dee6e09fa786479dc2e163a33e14257f207b35e`.
Authority: PA-V25-MASTER-2026-11-09 / v1.1; accepted G0
`59d28dc23be97de2a6a82d22be8338151e31f5b6`, unchanged.

Use a clean checkout of the reviewed candidate, with its Git history and the
original upstream objects available (the J loader reads exact committed bytes).
See environment.json for observed runtime versions. Set OPENBLAS_NUM_THREADS=1,
OMP_NUM_THREADS=1 and PYTHONPATH=.:tests/nba_architecture. Run:

```bash
python -m unittest discover -s tests/nba_s_family -v
python -m unittest discover -s tests/nba_c -v
python -m unittest discover -s tests/nba_architecture -v
```

Expected: S68, C76, architecture513, zero failures/errors/skips. Suites overlap.
The seven inherited ExactSourceMinuteTests in S include inherited controls;
counts are test methods, not independent games.

Run the four `scripts/nba_g1_repair_*_20261117.py` programs with a new output
path, using `--owner-root "$PWD"` for true_zero_display_adversary and
`--assembly "$PWD"` for the other three. Exact commands and hashes are in
`exact/receipt.json`. All four expect exit0. The matrix covers224 cases;
the public program covers10 and the status program4. Old audit scripts and
outputs at b7ca289 remain unchanged. `before/` captures fresh baseline6dee
executions, all exit2; these are expected reds, not repair failures.

`independent/` contains the separate reviewer's exact candidate commands,
expanded3360-case matrix, baseline sensitivity and independent disposition.
It records its own finite scope; it is not a rerun of every historical audit.

Native21: invoke scripts/nba_p5_native_handoff_verify_v1.py with --repo pointing
to this clone, --p1-sha 50d2b3874c7c14c9b73bdf13e441957986b88acd,
--p2-sha ae956315db9162315d16bdd0a6fe0b4c8afbfe1c, --p3-sha
 eb0882b5011f2004c5eaf27cccfdc6297704f261, --p4-sha equal to the reviewed
candidate above, and --output a new directory. Use spaces between flag/value.
`native/results.json` retains all21 cases and extracted source hashes.

No historical predictive training, evaluation, warehouse decompression,
weight fitting, source certification, G2, merge, deployment or Tier release.
Raw source hash, canonical JSON hash, Git blob and semantic replay are separate
domains. Synthetic fixture fitting does not establish authentic fitted models.
Rollback: discard this repair branch; original owner branches and accepted G0
have not moved. Do not replace old evidence with new results.
