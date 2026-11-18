# Prospective acquisition reproduction and handoff

Authority PA-V25-MASTER-2026-11-09 / v1.1. Frozen56fe25fb, profileceb3630b.
Exact current testedaaeb0601; CLI bytes unchanged from5714dca3.

```sh
python -m unittest tests.nba_architecture.test_p1_prospective_capture -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture python -m unittest discover -s tests/nba_architecture -v
python scripts/nba_p1_prospective_capture.py --stage pregame
```

The last command is real acquisition: creates new timestamp+UUID attempt, never
overwrites; late calls record MISSED_ORIGINAL_FREEZE without network. For morning
use --stage morning only after target start. Capture is not source admission.
Actual initial capture inputs/outputs are under captures/; original initial
scoreboard/rosters are separately frozen. Native roster reader retains every
listed member and source-declared generated timestamp; publication stays unknown.
Both initial native runs35rows/no fetch gaps are not proof of legal completeness.
Old blocked historical paths stay unchanged. Stage SHA256SUMS is relative to each
attempt directory, covering exact body/receipt/output bytes. Top SHA256SUMS is
relative to repository root. Receipt canonical hashes from old roots are separate.

Automation must verify exact scriptSHA4df0240932dcfed1c4a243b6015b152618a36d69d03bdcd6f505080ca45da68b
and cohortSHA692d662a8a256d46e36bc416225e2eb22136e5da41f2a486d725469f704e91b9.
Fetch capture/p1-prospective-20261118, create isolated worktree at its current
remote head, verify pins, run script, commit only new captures/receipts and push
fast-forward to that evidence branch. No main merge. If push conflicts, preserve
local results and rebase evidence-only commit; never force push or replace data.
The existing Phase8C primary worker and all production automations stay intact.

Morning job must capture outcome evidence, verify earlier prefreeze ingestion,
reconcile35roster candidates with final listed participants/DNP/missing/unknown,
extract only actually supplied seconds/duration or reject unsupported units,
check observed correction links without claiming all revisions, implement/review
additional native handoffs if evidence supports them, and obtain a separate
independent B-P1-01/B-P1-02 decision. Any missing legal roster/membership or fullgame
exception evidence blocks the relevant criterion. No automatic GO or promise
that one prospective night repairs2018 missing source availability.

No fitting, historical scoring/holdout decompression, weight changes, NUTS,
production schedule changes, merges/deployment/Tier promotion. Rollback: pause
only these bounded new tasks; discard evidence branch, preserve original records.
