# Reproduce this owner packet

Implementation inspection: b6e97273 (full SHA in git history).
Exact final runner/tested candidate: e28bd18624c345c7e546c6772aa1aca4a99600da.
Publication adds evidence only. No independently accepted implementation is claimed.

From a checkout at the exact tested candidate, run:

```
python scripts/nba_p234_reproduce_v1.py --out /absolute/new-empty-destination
```

Destination must not exist. receipt.json records actual commands, stdout/stderr,
exit codes, tested SHA and exact input/output file hashes. Hash domains are raw
file bytes, except the explicitly labelled decoded synthetic payload and retained
tool-text representation. The WS2 producer/runtime copies are exact git-show
bytes at its declared producer commit; they are inspection evidence, not executed
training. The inspector reads existing fitted bytes and never invokes fit().

The runner invokes original suites, whose fixtures exercise synthetic fitting
and synthetic native S_ONLY/S_O/J paths. Those paths remain the old engineering
versions. These are regression evidence only: zero admitted real handoffs, no
new native consumer closure, no real predictive score, no historical replacement
fit. Counts overlap. See exact/receipt.json and raw files for results.

Also retained: first owner run logs, the failed separate reviewer authentication
attempt, old #173 manifest recheck in its own exact publication checkout and
WP1 fixed-root public probe/manifest recheck in its exact publication checkout.
The first guessed WP1 probe filename failed; its stderr is retained alongside
the corrected successful public command. These are owner reruns of existing
reviewer-authored scripts, not new independent decisions.

Verify published evidence from repository root:

```
sha256sum -c docs/nba_architecture/p234_admission_20261118/SHA256SUMS
```

The manifest excludes itself. The final publication SHA is identified by the PR;
self-referential publication hashes are not fabricated inside their own commit.
Rollback: discard isolated branch. Old readers, runtime registry, accepted G0,
accounting repairs, original n32 red and all prior FAIL/BLOCKED receipts remain.
