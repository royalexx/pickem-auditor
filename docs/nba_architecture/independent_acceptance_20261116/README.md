# Independent P0/G0 acceptance — November 16, 2026

**P0 GO / independent technical G0 PASS for exact implementation SHA `59d28dc23be97de2a6a82d22be8338151e31f5b6`, PR #157.**

The independent ChatGPT/Codex audit session reviewed and tested this implementation without making implementation repairs. It previously rejected `e1983b2d0b94742dfb1bf411694dc46c7cad1ac6`; that rejection remains valid and all earlier FAIL/BLOCKED records remain unchanged. This packet publishes the completed independent review and the user's subsequent authorization to proceed with downstream engineering. It is not a repair-author self-approval.

Authoritative current status: `../P0_CURRENT_STATUS.json`. User authorization: `../G0_ACCEPTANCE_AND_DOWNSTREAM_AUTHORIZATION_20261116.json`. Immutable independent acceptance: `audit_receipt.json`.

## Executed evidence

| Check | Independent observation |
|---|---|
| Exact candidate suite | 267/267 PASS, no failures/errors/skips |
| Prior independent campaign | 47/47 expected outcomes |
| New rational-oracle cases | 1,060/1,060 expected outcomes |
| New full-boundary cases | 198/198 expected outcomes |
| Total independent cases | 1,305 matched: 653 valid acceptances and 652 invalid rejections; no execution errors |
| Pinned original upstream regressions | 146/146 PASS, no skips; original-version evidence only |
| Rejected-SHA red reproduction | Six methods, 21 expected failing assertions, no unexpected errors |
| Repair-boundary mutations | Both detected in temporary implementation copies |
| Schema and goldens | Draft202012 and all five golden reproductions PASS |
| Preservation | 93 prior files byte-identical |
| Registry | All 27 groups' test references resolved; current check inventory matched source |

F1 is independently verified repaired at O, full forecast acceptance, and C. The new oracle tests include three players sharing 48 minutes on support {0,24,48}: pair-allocation masses are determined exactly by x_ij=(b_i+b_j-b_k)/2, where b_i is the declared 24-minute probability. These cases distinguish individually attainable atoms and correct expected minutes from existence of a conserving joint measure. Additional cases exercise unknown participation, positive sampled support, overtime probabilities and player permutations.

F2 is independently verified repaired across all eight markets, all three declared conditionings, analytic and empirical forecasts, and full original-quote-bound C acceptance. Valid zero-count counterparts and legitimate finite-sampling variation remain accepted. The inherited source, model/identity, strict-ingestion, correction-chain, numerical and immutability challenges were also rerun. No unresolved material G0 violation was found within the documented contract scope.

## Provenance and reproduction

The artifact bytes copied here are the original independent execution artifacts. `artifact_manifest.json` verifies the original scripts, results, fixtures and logs. It intentionally excludes itself and `audit_receipt.json`; the receipt includes its manifest hash. The receipt digest is computed from canonical sorted JSON excluding `receipt_sha256`:

`a90dbe624b44013d6eaf03163726fcfe1cd9f7055b2d657a7d3fed100d3f519d`

The candidate unittest log hash is:

`03f441cb1de9c0eb3e3c37de35edbe2e2073f4019288d2a6db3a75266904cd82`

Use the exact reviewed implementation checkout, not this evidence branch's HEAD, for reproduction. With its pinned requirements installed, run its `docs/nba_architecture/law_repair_20261116/reproduce.py --out` with a fresh output directory. This executes schema, golden, preserved-byte, reference and full-suite checks. `reproduction/receipt.json` records the independently executed command and environment.

The independent executable campaigns are `prior_campaign.py`, `new_oracles.py`, and `full_boundary_cases.py`; their result ledgers and constructed fixtures are in the corresponding subdirectories. The original latter two scripts contain the execution workspace's absolute output prefix `/workspace/work/evidence157`. `reproduce_independent.py` verifies these published script hashes, changes only that output prefix in temporary copies, and executes all 1,305 cases against a specified clean reviewed checkout. It requires a fresh output directory and writes no implementation files.

Example, when invoked from this packet directory with a separate clean reviewed checkout at `/tmp/nba-g0-reviewed`:

```bash
python reproduce_independent.py --checkout /tmp/nba-g0-reviewed --out /tmp/nba-g0-independent-fresh
```

`red-exact-sha.log`, `red-tests/`, `guard-mutations/`, `upstream.json`, and the WS*.log files preserve the rejected-code, sensitivity and original-version checks. Red and mutant failures are expected negative evidence, not failures in the accepted implementation. The receipt's original `artifact_delivery` and `remote_writes` fields describe the audit at execution time, before this later user-authorized publication; the original receipt is preserved unchanged.

## Downstream authority and limits

The G0-only start blocker for P1–P6 engineering/conformance work is removed. G1 family acceptance is not asserted; all real adapter/source/model/settlement owner evidence remains required. G2 preparation may proceed, but integrated acceptance requires all six families to satisfy G1 and the end-to-end checks. P8–P11 remain subject to their applicable gates and separate authorization.

This is synthetic engineering-contract acceptance, not real-source authenticity, fitted-model quality, predictive skill, chronological rotation/possession proof, product-rule authentication, global storage uniqueness, or production readiness. The documented finite-law verification budgets and numerical certification limits remain applicable. No training, historical performance scoring, model/forecast-weight fitting, archive rewriting, notebook or schedule change, merge, deployment or production/Tier release is authorized by this publication.

The accepted implementation SHA remains unchanged. This separate branch adds documentation and audit artifacts only. Substantive contract changes require affected checks and renewed independent review. There is no cryptographic reviewer identity signature; SHA-256 values identify artifact bytes and are not external signatures or source-authenticity attestations.
