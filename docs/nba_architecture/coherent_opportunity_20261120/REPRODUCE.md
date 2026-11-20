# Exact source, model and replay reproduction

Check out this published branch/commit. The base is PR192/d029747c, not main.
Install `requirements-nba-research-tests.txt` in an isolated Python3.12
environment. Actual prediction used Python3.12.14, NumPy2.3.5, SciPy1.17.0 and
zlib1.3.2. Library versions are recorded in the immutable execution receipt;
the replay rejects incompatible NumPy/SciPy versions rather than changing its
saved random draws silently.

Read-only public replay, using a fresh create-only output directory:

```sh
python scripts/nba_coherent.py replay --output /tmp/coherent-S4-J-replay-fresh
python -m unittest tests.nba_joint.test_coherent_predictive_v1 -v
python -m unittest discover -s tests -q
sha256sum -c docs/nba_architecture/coherent_opportunity_20261120/SHA256SUMS
```

Replay verifies the exact independently reviewed bank/model/receipt roots,
all7 runtime code files, all5 issued artifacts, actual recorded clock chain,
source population,64 fixedG/O/parameter draws, every compressed/uncompressed
trace, hard accounting, exact saved projections and336 paired queries. It
does not invoke fitting, generation, new issuance or current-time pregame
gates, and is safe to run after the target. It returns140 primitive requests
with56 support/84 abstentions,280 total requests with112 support/168
abstentions, and0 scores/280 pending outcomes. Source states and unknown clocks
remain as in the original source root.

The actual one-time write commands were:

```sh
python scripts/nba_coherent.py fit --output docs/nba_architecture/coherent_opportunity_20261120/fitted
python scripts/nba_coherent.py predict --output docs/nba_architecture/coherent_opportunity_20261120/actual
```

These are provenance records, not instructions to replace those directories
or repeat the approved fit. Both are create-only. One prospective fit and one
declared64-scenario execution were performed. Their actual commands, clocks,
commits, stdout/stderr and hashes are in `execution/`, `fitted/FIT_RECEIPT.json`
and `actual/EXECUTION_RECEIPT.json`.

Actual bank SHA256:
`318bb9b2317ae120b6b51852a88b97177424fc0caeba36ed8b38b4f6ead01d88`.
Actual execution-receipt SHA256:
`dc7f7cdab93129c3b11c7157bd6222fa67e4f71e024487ef8685f4939a30d459`.
Actual fitted-model SHA256:
`f1f6dd4a4d3753042c28b71fa9b7949628d69ccdad8f38ece47bb2ccdc6ffa2a`.

Raw JSON hashes cover exact saved UTF8 canonical bytes. Semantic payload hashes
cover only the specific canonical structure documented by that producer; they
are not substitutes for raw hashes. Trace receipts separately hash exact
gzip bytes and exact decompressed generated JSON bytes. Gzip uses level9,
mtime0 and no filename. These are newly generated simulation traces, not a
historical holdout archive. Source-body hashes remain exact original HTTP
response bytes; receipts preserve separate actual observation/retrieval/
ingestion clocks and null source publication/end/correction-history fields.

The checksum manifest uses repository-root relative paths and binds this
packet, source inputs and runtime code. Historical manifests remain bound to
their own reviewed versions. Do not modify old evidence to make another
version's check pass. To rerun independent probes, use a fresh detached
worktree so their own result-writing code cannot replace original receipts.
The prefit probe requires the exact closed compiler from162ea849; its only
later authorized activation is the one PREFIT_SHA constant. Each independent
packet provides its exact invocation and replay scope. No source fetch,
historical fitting/evaluation, holdout decompression or NUTS is needed.
