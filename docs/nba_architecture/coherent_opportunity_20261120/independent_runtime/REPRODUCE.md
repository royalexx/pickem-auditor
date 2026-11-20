# Reproduce independent coherent runtime review

Use producer8d8df996a44b00ba9af3f9e58325539b75641802 for actual generation-byte reproduction and installed reader4b464906782e02d1ea630c6cbd1dbd99f440317a for public replay, with this independent directory. The original positive source run is actual/. Do not overwrite it. No fit command is needed.

```sh
COHERENT_REVIEW_OUT=/tmp/fresh-coherent-engineering PYTHONPATH=. python docs/nba_architecture/coherent_opportunity_20261120/independent_runtime/public_probe.py
PYTHONPATH=. python docs/nba_architecture/coherent_opportunity_20261120/independent_runtime/actual_probe.py
COHERENT_ISSUED_REVIEW_OUT=/tmp/fresh-coherent-reader PYTHONPATH=. python docs/nba_architecture/coherent_opportunity_20261120/independent_runtime/issued_probe.py
PYTHONPATH=. python scripts/nba_coherent.py replay --output /tmp/fresh-coherent-cli-replay
sha256sum -c docs/nba_architecture/coherent_opportunity_20261120/independent_runtime/SHA256SUMS
```

Use fresh directories. actual_probe.py writes its diagnostic results in this review directory; copy the independent directory first to preserve originals. It regenerates the already frozen bank with the original fixed cohort/seed into a temporary directory, compares exact bytes, then removes that temporary replay. It never invokes fitting or issues a new cohort. Query/reference checks use the same saved old-S1 artifact, not held-out outcome files. Gzip decompression is solely the authorized simulated path trace, not a holdout archive.

Raw streams are final_4b/tests.*, actual.*, issued_installed/tests.* and cli-replay.*. Initial engineering passes and both red/repair pairs are retained separately. The proposed-root test used COHERENT_PROPOSED_ROOT=1 and wrote issued_proposed/; it is explicitly not installed admission. PREINSTALL_DECISION.json approves only three exact constant replacements and ACTIVATION_CHECK.json verifies the installed file equals those replacements. The final reader test has no root mocks.

identity_red.py returned exit1 at291c4481, then exit0 after player/team binding. trace_metadata_red.py returned exit1 at65dfa4f3, then exit0 after aggregate reconciliation. Reproduce historical reds in isolated old-commit checkouts; do not edit current source files. The final public suite includes both regression controls and additional mutations. public_probe.py uses no fitted genuine artifact and confers no source admission.

failed_cli_probe.py is a separately annotated fault-injection test. It uses a fresh failed_cli_control directory and forces event budget5 after verifying the public CLI requested4096. The result is a failed batch, never a new positive forecast; the original actual64 run is untouched. It requires a fresh output directory if rerun. Its raw controlled stdout, rejection ledger, partial bank/traces and exit2 are retained. The existing-output CLI negative confirms create-only behavior and byte preservation.

SHA256SUMS hashes exact file bytes. The original model and bank JSON, canonical serialized query/results, original receipt JSON, compressed gzip frames and uncompressed trace JSON are distinct domains. Both compressed/uncompressed path hashes and byte lengths are validated. The complete original source population is bound by the separately admitted component/source records and their existing manifests; this review adds runtime/issuance bindings, not source authenticity inferred from a digest. Python/zlib/numpy/scipy versions are recorded in the actual execution receipt. Numerical replay requires the recorded numpy/scipy versions; exact gzip regeneration also uses the recorded Python/zlib behavior.

All original nba_joint hard-physics files compare byte-identically with base d029747c. This review does not change old S1/J decisions, source completeness claims, genuine q, pending zero sensitivity, historical validation or release policy.
