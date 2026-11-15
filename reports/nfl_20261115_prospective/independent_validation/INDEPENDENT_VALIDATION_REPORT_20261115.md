# WS4 independent validation packet — synthetic and native source integrity

**Scope:** Source-bound abstention, signed opportunity/sample validity, exact side complementarity, model coverage and independent numerical score formulas. **Research only.** No external verifier or statistically independent human reviewer engaged; a separate numerical implementation and adversarial tests provide partial independent arithmetic checks, not independent scientific certification.

## Evidence reviewed

- Original V5.6 frozen independent 175-week score report: synthetic cohort 407,476, V5.6 significantly worse descriptive Brier/log loss; overconfidence at >=90%; 175-week original time/constraint forensic report classified `PASS_RESEARCH_ONLY` and explicitly lacked original source first-seen timestamps.
- Actual WS1 isolated source-control manifest and independent source audit: only quote/roster source certification, 1,845 raw original quote observations and zero model-forecast-ready quotes. The original source remains outside all WS4 writes.
- New J1/J2/J3 joint-model candidate with J4 pairwise dependence outputs, 128-/512-draw synthetic fixtures, independent per-row numerical audit and 57 automated local adversarial/mathematical tests.

## Negative controls and observed dispositions

| Attack / issue | Expected behavior | Synthetic test observation |
|---|---|---|
| Input schema replaced or missing real source certification | Fail closed | Passed |
| Future source, quote or model-training cutoff | Fail closed | Passed |
| Naive UTC, kickoff-before-freeze | Fail closed | Passed |
| Duplicate exact quote or player; player-team/event mismatch | Fail closed | Passed |
| Unconfirmed QB, backup QB forecast eligibility | Block/abstain | Passed applicable fixture checks; full real QB roster still missing |
| Negative shares, invalid pass rate, nonfinite original line | Fail closed | Passed |
| Count negative, targets > passes, catches > targets, QB completions > passes, carries > team rush pool | Violations zero | Passed synthetic generated-state checks |
| Combined tackle double credit | Combined is solo+assists; distinct assisted players per tackle event | Passed synthetic accounting; official tackle definition not independently validated |
| Integer-line Push and fractional-line zero Push | One exact distribution | Passed |
| Same seed/frozen identity and draw-prefix stability | Deterministic | Passed |
| Coherent scenario weights | Sum one, fixed before settlement | Passed |
| Game-vector Energy Score and Variogram Score(0.5) | Known hand-computable cases; no cross-unit mixing without fixed scales | Passed |
| Independent-marginal permutation | Preserve each empirical marginal, break dependence without changing team simulation | Passed scoring-null control; shuffled vectors are not used as physical game outcomes |
| Source WS1 hash, original 1,845 denominator, nonzero forecast-ready change | Rejection if contract deviates; all 3 models explicit abstain while 0 forecast-ready | Seven synthetic source-contract tests passed; actual file passed a successful detached Deepnote run |
| Missing baseline forecasts or incompatible market quote | Missing rather than zero or substituted | Passed evaluator synthetic tests |

## Scores and denominators

All numbers before authentic Sunday settlement are engineering canary measurements, **not predictive proper scores on football games**. Local 57 unit and numerical adversarial tests pass. Original Deepnote free CPU run `e6ec25d6-cd02-4412-824f-84823a86b7e4`: 37 original tests, 180 forecast-row numerical checks. Supplemental Deepnote run `52d6704b-2a0d-478a-bc48-403cf395e067`: 49 tests, independent analytically computable Energy/Variogram cases. Deepnote v0.2 run `66d3e578-15ef-4cd4-92bc-6d654aaf361e` succeeded, passing 57/57 tests, generating 180/180 numerically checked fixture rows and writing 5,535 original-quote/model abstentions from the authentic 1,845-row WS1 source; zero actual J1/J2/J3 probabilities were generated. SHA-256 of this native read-only abstention output is `c879a225f739e5420cceb2f275ea6f8ded065f346ccb2c116e04eb33029a082c`. The WS1 source file SHA was pinned to `5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`, and no original source file was changed.

The `paired_evaluator.py` preserves offered/rejected/unmatched/DNP/void/push/unsettled denominators; scores only strict exact quote/stat/period/line matches; treats pushes separately in binary and three-way scoring; validates PMFs; requires genuinely prior-frozen top-five/ten candidate ranks. Primary uncertainty unit: game-cluster pairs; date/week sensitivity if sufficiently many games. It has no legitimate real 2026-11-15 settlement inputs yet. All comparative engine columns remain unavailable unless actually frozen.

## Explicit gaps

1. Historical game-state factor/replay decomposition independently regenerated from original immutable raw weekly game draws: **not executed**. Existing independent 175-week audit inspected only.
2. Model means, roles, shares, conditional rates and defense credit calibrated on point-in-time source inputs: **not available**. No verified original training cutoff artifacts for Sunday J1–J3.
3. Official NFL scoring edge cases such as kneels, no-plays, QB relief, special teams, assisted tackle opportunities and DNP/push payout conventions: **not completely modeled**.
4. Real 2026-11-15 original-book player quote two-sided prices, no-vig probabilities and full payout/entry semantics: **not demonstrated as a model-ready compatible comparator**.
5. Prospective independent forecast-vs-outcome Brier/log loss/CRPS, J4 multivariate Energy/Variogram and realized joint-event calibration: **no settled model-eligible contract data**.
6. Adequate game/day-clustered power: **one Sunday is underpowered** even if all valid future forecasts settle.

**Decision:** research implementation and numerical/contract canaries testable; keep shadow-only, blocked by model-ready input data and independent external evaluation. PR #130 is not a release approval.