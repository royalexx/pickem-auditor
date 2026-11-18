# Reproduce the bounded packet

Exact executable: b5cc4ef582539e9817ecf859a3dd29179f0dea30.
This publication changes evidence only, not v2/scripts/tests. Checkout that SHA
and use Python 3.12.14 with the installed dependency versions recorded by P6.
Run from repository root:

```bash
OPENBLAS_NUM_THREADS=1 python -m unittest discover -s tests/nba_c -v
```

The 76 C tests cover controlled score references, Over/Under/Push, missing/DNP
outcomes, identity and clock mutations, corrections, immutable storage and
synthetic native transport. These overlapping finite fixtures are zero observed
admitted integration games. No fresh historical predictive score is authorized
or produced. c.stdout/c.stderr retain this owner's actual execution.

Review pins.json and the immutable referenced WP1/WP2/WP3 receipts. The latest
P1 bounded branch is intentionally not merged: its accepted scope does not
supply settlement admission. No substitute upstream stages are assembled.
Independent review artifacts describe exact executed public paths separately.
Verify the publication from repository root:

```bash
sha256sum -c docs/nba_c/settlement_admission_20261118/SHA256SUMS
```

SHA256SUMS excludes itself. Publication commit is external to its own manifest.
Rollback: discard this isolated evidence branch. No production runtime changed.
