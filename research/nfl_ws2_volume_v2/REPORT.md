# WS2 V2.5 genuine NFL volume-distribution execution

Implemented, tested, and executed in prospective research shadow. All eleven markets are represented; ten have supported distributions. T+A remains blocked by source accounting. No production, Tier, calibration, outcome, or model-quality promotion.

## Real populations

Forecast creation: **2026-11-15T16:47:55.900754+00:00**; numerical completion: **2026-11-15T16:48:03.250296+00:00**. Earliest included kickoff was 18:00 UTC. NE–DET was already started and excluded from new forecasts. Historical acquisition was verified before the 16:17:30.185351 UTC WS1 freeze; no historical as-of availability claim is made.

- **1,788 distinct player-game-stat combinations**, each forecast by EW and uniform empirical variants: **3,576 real distributions**.
- **1,371** of those combinations have no evaluable original contract. They still receive distributions.
- **1,469 authentic original contracts per model**, **2,938 probability rows total**. Two models on one contract do not create independent offers.
- Full source denominators: **3,570 player-stat candidates**, **1,845 original contracts**. The model population retains **28,554 abstention rows** alongside 3,576 distributions (nine model versions per player-stat). Each active variant abstains on 1,782 candidates.
- **10 real first-player market canaries** preceded bulk generation. Targets: Chris Blair; both composites: Chris Blair RR and Michael Penix Jr. PR. T+A canary explicitly unavailable.
- Original **1,672 S2 v1 forecasts preserved byte-for-byte**, including the original tackle forecasts; this extension does not retroactively certify their tackle accounting.

## Coverage

Counts below apply separately to **each** new empirical variant. Contracts are exact original offers, with no invented targets/composite thresholds.

| Canonical market | Source candidates | Distributions per model | Abstentions per model | Original contract probabilities per model | QB1 distributions per model |
| --- | ---: | ---: | ---: | ---: | ---: |
| pass_attempts | 24 | 19 | 5 | 49 | 19 |
| pass_completions | 24 | 19 | 5 | 49 | 19 |
| passing_yards | 24 | 19 | 5 | 70 | 19 |
| rush_attempts | 261 | 214 | 47 | 83 | 19 |
| rushing_yards | 261 | 214 | 47 | 199 | 19 |
| receiving_targets | 511 | 321 | 190 | 0 | 0 |
| receptions | 511 | 321 | 190 | 503 | 0 |
| receiving_yards | 511 | 321 | 190 | 516 | 0 |
| tackles_assists | 908 | 0 | 908 | 0 | 0 |
| rushing_receiving_yards | 511 | 321 | 190 | 0 | 0 |
| passing_rushing_yards | 24 | 19 | 5 | 0 | 19 |

Variants: `S2-ew-source-paired-hl4-v2` and `S2-uniform-source-paired-v2`. EW preserves half-life 4, while the new version discloses the ten-observation WS1 window and source starter filtering. Uniform is a separately identified simple benchmark. The old S2 implementation is unchanged.

Every S1/S3/S4/S5 market abstains because source-bound historical role peers are absent. Every S6 and both S7 sensitivity market abstains because original frozen production controls are absent. The full **99-entry model × market matrix**, with explicit counts, is in `HANDOFF_WS6.json` and `EXECUTION_RECEIPT.json`. Calibration remains unavailable for all variants: no chronologically validated frozen calibrator is supplied.

## Source and statistical checks

All 24 historical feature files and 48 roster/depth sources were hash verified. All **3,603 target-history records** passed raw receptions ≤ targets and team passing-opportunity checks; **zero** lacked an exposure denominator. **174/321** target distributions per model preserve positive mass at zero. Missing observations are never changed to zero.

Official schedule starter IDs filter QB histories; archived expected-QB1 depth order is checked independently against raw source bytes. Each of the 19 expected starters has rushing attempts, rushing yards and passing+rushing yard distributions. All forecasts remain conditional on appearing; QB forecasts additionally condition on starting. No backup is treated as a full-game QB1, and no current active-status probability is invented.

Both composite laws reconstruct actual same-game source pairs and preserve the exact sum for every joint outcome. There is no independent convolution. Standalone marginal histories can have different missing-data windows, so composite simulation must use its recorded joint outcomes.

Combined tackle accounting is unverified; solo, with-assist and assist fields are never summed by this extension. T+A and every excluded defensive/specialty market produce no new forecasts.

Each distribution retains moments, PMF, quantiles, zero mass, joint outcomes where applicable, finite-support tail assumptions, sample depth, effective sample size, cutoff, eligibility, exact input/model/source fingerprints, deterministic weighted Bayesian-bootstrap uncertainty representation, and participation/role warnings. Bootstrap intervals are conditional on finite observed support and exchangeability; they do not establish calibrated coverage. Unseen tails, serial dependence and role changes remain limitations.

Target shrinkage/rate/exposure/overdispersion/position-prior candidates are explicitly unavailable where frozen priors, historical role bindings or pregame exposure models are absent. Historical passing exposure was verified for semantics, not relabeled as a prospective exposure forecast. No synthetic experiment is counted as a real prediction.

## Validation and execution evidence

- **88 targeted tests** passed locally and in Deepnote; **22 discrete-contract tests** also passed locally.
- Saved-ledger replay passed all 3,576 laws and 2,938 contract evaluations: exact component sums, probability normalization, support, moments, zero mass, discrete pushes, timestamps and distribution fingerprints. This is separate arithmetic recomputation by the same implementer, **not an independent reviewer signoff**.
- Successful forecast run: `fa78ebc3-21ef-48e4-9933-309a87eefb06`; notebook `c06884f6e23c466694eecf03355426fb` in project `9cc31536-93be-44db-bdeb-06fba3f61410`.
- WS6 transport run: `37379be9-d2f2-4a58-b437-8c4c7071160b`. It retains all 1,845 original contract objects/quotes and links the separate distribution-only population. Original WS6 v1 comparison files are untouched.
- WS6 transport replay `3e83a259-19ae-41cd-9648-0089dd434002` verified every original object/quote in all 1,845 rows and all 2,938 frozen probability records. It passed without regenerating any forecast.
- First full attempt `3f2dff65-6567-4069-bd13-801f7be05200` hit its 240-second execution cap before creating any ledger directory. Duplicate source-file reads were removed, and the successful attempt used one BLAS thread. No forecasts from the failed attempt are claimed. Trial quota/rate errors were resolved using the already-running Basic CPU project machine.

## Immutable handoff and fingerprints

Forecast execution code commit: `b483076e6fa6780835067b2e1dfcf6806428bdb3`. Branch: `research/nfl-nov15-ws2-marginal-models`; draft PR #132.

Model SHA-256: `b5f1601b8f0ba1c683f959dce1ece6ff5f96028c27e930b17a13ab9208173c1c`.

Expanded WS1 feature pin SHA-256: `c3ec93c78fcae413f66afe431f817f4d986f0fd1e884c665caefc5c7a3ed230c`.

Original source reference: `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.

WS2 handoff SHA-256: `a1ac393de822c8466558b6ba2fa983b79e1c0c5558c6ec5cd329ec14e6434341`.

Replay audit SHA-256: `a3d3b87186c74b17832da6a02bf40843da7bab9a28092510ca87f7cdc3c92b9d`.

WS6 transport index SHA-256: `0865a426c2fddce47d9a0f60547d6590ece7724fcacdec353f6dc31dab21b7a1`.

Full JSONL populations remain in Deepnote:

`reports/nfl_20261115_prospective/simple_models/volume_distributions_v2/20261115T164735308318Z/`

`reports/nfl_20261115_prospective/simple_models/volume_ws6_transport_v2/20261115T164735308318Z/`

Small exact-byte handoff, execution and replay receipts are copied to this directory in Git. Each artifact path, SHA-256 and count appears in those receipts. The WS6 transport adapts to original-contract/quote identities and per-model empirical records while retaining the unpriced distribution population separately. It does not claim that the hard-coded WS6 v1 comparison reader automatically consumes v2.

Remaining gates: independent source/accounting reconciliation for T+A; source-bound historical peers and frozen controls for unavailable models; original chronological data and independent validation before any calibration or scientific promotion. Phase 0R certification and trusted Tier authority are not closed by this shadow run.

