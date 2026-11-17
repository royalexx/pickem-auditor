# NBA V2.5 P6 independent G1 remediation re-audit — v3

**Decision: G1 NO-GO.** P1 **BLOCKED**, P2 **FAIL**, P3 **BLOCKED**, P4 **BLOCKED**, P5 **FAIL**, P6 independent QA **PASS** within the finite engineering scope below. The original P1/P5 counterexamples and synthetic P2 duration-cap defect are repaired, but two new independent boundary failures remain. Mandatory authentic-source and latest-owner handoff evidence is still missing. **G2, P8–P11, historical accuracy evaluation, historical weight fitting, production and Tier promotion remain closed.**

Audit date: November 16, 2026 Toronto / November 17 UTC. Governing authority: **PA-V25-MASTER-2026-11-09 / v1.1**. Accepted G0 remains **PASS only at `59d28dc23be97de2a6a82d22be8338151e31f5b6`**. This report adds evidence; it does not replace or amend PR #168's prior NO-GO decision.

## Exact sources and isolation

The independent QA branch is `audit/nba-p6-g1-remediation-recheck-v3-20261116`, based on prior report commit `31435bd571ae1b4a9b7f1e1bbf05e55cef61126f`. All owner implementations ran from detached disposable checkouts. No P1–P5 implementation was repaired, modified or committed by P6. No alternative forecasting model was built. Synthetic statistical/optimizer fixtures are engineering tests, not historical model fits.

| Family / PR | Prior independently tested head in #168 | New fetched and tested exact head |
|---|---|---|
| P1 / #167 | `e0b8703887d327c8d8ac34807078e75e7b59a540` | `201ff0aacbd398c7a260f1af3b1c16f4dd8abaa3` |
| P2 / #165 | `96d210a6100085640e7e82928ab1c864839fc454` | `7ca4269c98a27def485eaa8122ea7148cd0c2c0a` |
| P3 / #166 | `80dbed35f983839f962250ad1c0236061dc6ee00` | `191b3f654b3a3ca7dc813edbfc9aacdf35729dff` |
| P4 / #164 | `b3729c53509cb063e2e451b7e4feb0ac2c6a9552` | `cf5483a16279b8af606caef415e9abacc8c41aab` |
| P5 / #163 | `1d7b8471a85e9d3dafaf809acacfeca6e980dc81` | `e46abacecc4f3147aa28d5351515aeca07c17f48` |

All heads were re-fetched through GitHub after execution and were unchanged. PR #168 remained at its supplied report SHA. Main was independently read as `912bc7010058092ea735dcda0aa941429194474b`; it was not changed. The training pause marker remained `paused=true`; no production operation or schedule was changed. This audit makes no live Deepnote runtime certification claim.

Owner PR descriptions, discussions, remediation handoffs, new tests, interfaces, remaining blockers and available source receipts were inspected. [Comparison](p6_remediation_reaudit_v3_20261116/comparison.json) records every changed path and raw digest; **all inherited G0 implementation and test blobs match the accepted G0 commit on all five heads**. [Owner source inventory](p6_remediation_reaudit_v3_20261116/owner_source_inventory.json) records the actual code/test/source bytes used. The original probe remains byte-identical:

`fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52`.

## Independent test results

Environment: Python **3.12.14**, NumPy **2.3.5**, SciPy **1.17.0**, jsonschema **4.26.0**, CPU only. Tests were independently executed locally; owner-reported test counts are not substituted for these results.

| Exact owner head | G0 plus owner architecture | Unchanged independent P6 | Additional family tests | Total in this row |
|---|---:|---:|---:|---:|
| P1 | 331 PASS | 83 PASS | 9 preflight PASS | **423 PASS** |
| P2 | 267 PASS | 83 PASS | 30 S PASS | **380 PASS** |
| P3 | 306 PASS | 83 PASS | included in architecture | **389 PASS** |
| P4 | 321 PASS | 83 PASS | included in architecture | **404 PASS** |
| P5 | 267 PASS | 83 PASS | 48 C PASS | **398 PASS** |

These rows repeat G0/P6 suites; they are **not 1,994 distinct tests**. Each dedicated suite had zero test failures/errors/skips. P4's declared compatibility runner additionally passed **442 executions**: 321 G0/P4, 83 P6, 16 old pinned P3 and 22 old pinned P2. Its old P2/P3 pins are material; this is not a latest-head integration result.

The accepted G0 upstream suites were independently reexecuted at their original pins: WS1 `53c01a9eabb9ed09b5c3186eae0d086b07bcc891` **25/25**, WS2 `02426dd1b9c2b0cca28eaf69888adadc0021afa5` **25/25**, WS4 `9821694260edb08b7414f02adea8c1fb3fd3b13c` **33/33**, WS5 `cdf926f56e86bc9d25576acff61fd6f091313159` **63/63**. Total **146/146 PASS**, without rerunning historical model evaluation.

The new independent v3 program contains **34 finite cases: 32 PASS, 2 FAIL**. P1 7/7; P2 5/6; P3 5/5; P4 6/6; P5 9/10. Some passing cases assert an explicit BLOCKED/abstention boundary; they do not grant family PASS. Expected red exits remain **2** for P2 and P5. New adversarial inputs include fractional multi-OT cap excesses, half-minute rounding boundaries, corrupted ancestor bytes, orphan revisions, duplicate cross-team identity, internally balanced resealed share tampering, small on-court witness gaps, dictionary-order replay, cross-process `PYTHONHASHSEED` changes, nested future clocks/results, nonnormalized PMFs and forged 20,000 ESS on two joint paths.

Raw commands, counts, outputs and SHA-256 are in [suite results](p6_remediation_reaudit_v3_20261116/suite_results.json), [new case results](p6_remediation_reaudit_v3_20261116/independent_v3_results.json), [upstream results](p6_remediation_reaudit_v3_20261116/upstream_results.json), and `SHA256SUMS` in the evidence folder. The portable runner checks exact counts and exact expected red case names; a different failure does not count as reproduction. It was independently exercised through 32 successful expected-outcome commands; their repeated raw outputs are retained in `runner_validation/`.

## Before/after disposition of the original failures

The exact historical script was run both on the prior owner commits and on the new heads. Neither its fixture nor old explanatory labels was rewritten. The old report and red receipts remain unchanged; fresh before/after stdout is added beside this report.

| Prior finding | Prior-head result | New-head independent result | Disposition |
|---|---|---|---|
| F-P1-01 history zero minutes with positive statistics | accepted | `ZERO_MINUTE_CREDIT_UNRESOLVED` | finite defect closed |
| F-P1-01 900 minutes without duration | accepted | `GAME_DURATION_EVIDENCE_REQUIRED` | finite defect closed |
| F-P1-01 vault zero-minute positive statistics | accepted | `ZERO_MINUTE_CREDIT_UNRESOLVED` | finite defect closed |
| F-P2-01 56 minutes without game-duration witness | rejected | rejected | old fixture cannot prove repaired two-OT acceptance |
| F-P2-01 new 56-minute / two-OT witnessed fixture | old fit cannot represent witness | accepts; 58.00001 minutes rejects | synthetic duration-cap defect closed |
| F-P5-01 correctly dated synthetic 2023 event | quarantined | quarantined | retained |
| F-P5-01 same event with only date backdated to 2022 | accepted | `INVALID_CHRONOLOGY` | exact bypass closed |

P1 preserves displayed zero separately from officially shaped exact subminute exposure; 29.999 seconds passes while exact zero positive credits and the 30-second boundary reject. Genuine true-zero dead-ball credit remains unresolved without an authenticated explanation. Legal 0/2/6-OT boundary exposures and owner 0/1/2/3/4/7-OT fixtures pass. Both builder and vault owner tests independently pass valid multi-OT/subminute cases; unrelated vault reads also reject orphan corrections. Those official-shaped fixtures are **synthetic**, so an authentic official exception has not been certified.

P2 accepts a separate duration-receipt witness, includes it in the fitted artifact, and rejects missing evidence and over-cap exposure. A `P1_VERIFIED` fixture label is not external authentication. The unchanged historical probe's printed phrase “schema lacks official OT count” describes its old fixture; it is not a present source-code conclusion. The separate [green-after-fix wrapper](../../scripts/nba_p6_g1_green_after_fix_v3_20261116.py) versions current expectations without modifying the old script.

P5 still accepts valid synthetic pre-holdout examples and rejects historical profiles or missing synthetic authorization. No real 2023–24 outcome was accessed or fitted.

## New correctness findings

### F-P2-02 — conditional sidecar bypasses the declared training cutoff

**FAIL; P2; temporal contract defect.** Exact owner SHA `7ca4269c98a27def485eaa8122ea7148cd0c2c0a`, `v2/nba_s_family/integration.py:joint_conditional`, raw source SHA-256 `cc5ba5d5fab72d762581f831e55d1018dc5a5383ade8f89fb8de9fea03cb51e3`.

A valid synthetic pregame snapshot declares training cutoff **2022-10-09**. The fitted artifact declares **2022-10-10**, still before input freeze. `predict` correctly abstains `MODEL_AFTER_DATA_CUTOFF`; `joint_conditional` emits a sealed S-to-J law from that same artifact. Its entrypoint checks against input freeze but omits the stricter declared P training cutoff. The sidecar is outside the unchanged G0 distribution structural wrapper that catches the regular prediction.

Reproduce in the exact P2 checkout:

```bash
PYTHONPATH=.:tests/nba_architecture python /workspace/work/qa/scripts/nba_p6_g1_remediation_adversarial_v3_20261116.py P2
```

The case `conditional_S_to_J_must_honor_P_training_cutoff_not_just_freeze` fails with `ACCEPTED_ADVERSARIAL_INPUT`. [Complete witness](p6_remediation_reaudit_v3_20261116/F_P2_02_cutoff_witness.json) retains the P/G/O and emitted sidecar. The synthetic history itself contains no demonstrated future target labels; the finding is inconsistent enforcement of the declared training budget.

**Minimal owner repair:** enforce `fitted.training_cutoff_at <= pregame.training_cutoff_at` before any S-to-J conditional evaluation, preserving freeze, source and identity checks. Add valid/equality/late paired controls. P6 did not repair this code.

### F-P5-02 — forbidden target results accepted inside nested forecast inputs

**FAIL; P5; input-quarantine contract defect.** Exact owner SHA `e46abacecc4f3147aa28d5351515aeca07c17f48`, `v2/nba_c/experiment.py:CachedCohort`, raw source SHA-256 `d0a19291d45f37848d533886f76c99163da145661465184f26693ffb9c3ee15c`.

Starting from the owner's valid 2022 synthetic fixture, add only:

```python
row['pipelines']['S0']['model_inputs'] = {
    'actual_minutes': 37,
    'target_game_outcome': {'points': 0},
}
```

`CachedCohort(..., authorization='SYNTHETIC_UNIT_TEST')` accepts it. The guard searches forbidden outcome fields only directly in each pipeline dictionary, while recursive clock and linked-identity checks do not reject these nested keys. This contradicts the declared forecast/outcome separation contract. It **does not** demonstrate actual historical leakage, a changed PMF, or a historical-authorization bypass; those distinctions are retained.

Reproduce with the v3 program's `P5` argument. `nested_target_result_and_actual_minutes_in_forecast_pipeline` is the expected red case. [Complete accepted input and result](p6_remediation_reaudit_v3_20261116/F_P5_02_nested_outcome_witness.json) are preserved.

**Minimal owner repair:** reject forbidden target/outcome fields recursively, or close and validate the allowed nested forecast-input schema. Retain the original backdate rejection, valid synthetic controls and historical-fitting prohibition.

## Source chronology and authentic integration

**Independent byte result:** all **99/99** actual compressed shard blobs at warehouse commit `97a8bb566826afe5a3e5a7b8c632043d8a1dca24` match the WS1 manifest at `53c01a9eabb9ed09b5c3186eae0d086b07bcc891`, totaling **39,916,715 bytes**. Coverage manifest raw SHA-256 is `cf377a3c3d18fb8147586d4d3553092e0c23a51066af338a7f49ddd92ec3d2a7`. [Each observed byte digest](p6_remediation_reaudit_v3_20261116/independent_archive_bytes.json) is published. No shard was decompressed in this byte audit; especially no validation outcomes were opened.

This establishes neither contemporary pregame availability nor original provider-byte identity. P1's archive `source_sha256` hashes canonical parsed provider JSON; the matching old original HTTP bytes and their correction chain are absent. Its modern retained ESPN raw sample differs from the archive revision. Modern retrieval clocks and analyst-chosen historical replay cutoffs remain distinct. Independently reexecuted P1 fixture/CLI tests preserve **13 candidates, 338 features and 13 unresolved exposures**; strict official-evidence mode blocks without writing a snapshot. Historical candidates retain nullable eligibility and unknown availability.

P1's reported cohort row/player counts and its zero authenticated-duration/original-context/correction populations are **owner inventory**, not newly reconstructed historical denominators in this audit. Season-ending 2019–2022 includes the entire 2021–22 season and must not be labeled strict calendar-before-2022 training. DNP/played-zero/roster completeness cannot be inferred from a warehouse selecting positive workloads. The owner-recorded NBA endpoint HTTP 403 is not represented as a new independent network retrieval here. Missing authentic official evidence remains BLOCKED.

| Dependency boundary | Independently observed result | G1 implication |
|---|---|---|
| P1 real retained reconstruction → strict source admission | rejects `OFFICIAL_SOURCE_EVIDENCE_REQUIRED`; no output written | authentic integrated case stops here |
| Latest P1 unaugmented feature output → latest P2 | rejects `P1_CLOCK_ROLE_EVIDENCE_UNRESOLVED` | no invented OT/event/role/availability supplement |
| Latest P1 historical reconstruction → latest P3 source-bound route | sealed `HISTORICAL_RECONSTRUCTION_UNCERTIFIED` abstention | no target active roster or fitted participation certification |
| Latest P3 → latest P2 | actual owner O2 output consumed; unknown unconditional participation abstains; played-conditional mixture matches independently reconstructed exact O-scenario mixture with **maximum PMF error 0.0** | synthetic callable compatibility only |
| P4 → its declared old P2/P3 pins | actual `FittedS`/conditional APIs and O producer run; complete weighted PMFs and shared lineage validate | genuine owner code, but synthetic artifacts and old versions |
| Latest P2/P3 → latest P4 | `J_UPSTREAM_CODE_PIN_P2`; P4 also declares P3 sidecar `0.1.0`, latest is `0.2.0` | latest-owner handoff BLOCKED; pins were not bypassed |
| P4 real mode | `J_REAL_INTEGRATION_BLOCKED_P1_AUTHENTICATION_REGISTRY_UNAVAILABLE` | caller strings/hashes cannot authorize authenticity |
| Authentic P1/P2/P4 → P5 | no admitted native event/end/release/vault/distribution adapter graph supplied | immutable synthetic scorer tests cannot substitute |

The authentic integrated case stopped upstream. Remaining rows are separate bounded compatibility/abstention tests, not fabricated continuation of that case. No target-game boxscore was retrieved, no source receipt was invented as genuine and no alternative model was introduced.

P4 now calls real owner APIs rather than merely accepting new rate labels, and rejects arbitrary real-mode declarations. Nevertheless its event allocator consumes a **mean/opportunity-share projection** of S1/S2, not their full conditional uncertainty. Retaining complete PMFs in an audit does not propagate variance, dispersion or tails into the generated J law. Marginal preservation is explicitly false; four-draw descriptive distortion is not an adequacy certificate. S3 does consume fitted beta-binomial conversion after integer projected attempts; target realized 3PA remains prohibited.

P4's aggregate possession/FT and OT paths do not establish an exact chronological possession law or tied regulation/OT endpoints. Five-on-floor minute intervals do not establish scorer/assister event-time co-presence; early-exit total-minute caps do not establish actual exit clocks. These are disclosed missing mandatory proofs/accepted approximation contracts, not newly alleged hidden bugs.

Independently repeated O0 benchmarks at 8/32/64 scenarios × J0/J1/J2 have **all nine exact bundle/audit replays** and 96 detailed player/stat PMFs. At 64 scenarios elapsed times were approximately **4.363 / 4.314 / 4.459 seconds**. The original stochastic **O2 n=32** rejection remains `O_COUPLING_VERIFICATION_BUDGET` in independently rerun tests. O0 timings cannot certify O2 scalability. No solver budget or owner model was changed.

## Independent numerical references

These are analytical/synthetic engineering comparisons, not retrospective predictive-performance results.

- Unchanged direct P5 oracles: Poisson(1), y=0 CRPS **0.47622238819739127**; NB(2, 0.5), y=0 CRPS **26/27 = 0.962962962962963**; two-atom ES **1.2928932188134525**; VS_0.5 **2**.
- New sparse law `{0:.17, 2:.31, 7:.29, 19:.23}`: mean **7.02**, zero mass **.17**, mass at/above 7 **.52**. Independent full integer-CDF CRPS at y=0/2/5/23 is **3.3646 / 2.0446 / 1.9246 / 12.3246**. NLPD at 0/2 is **1.7719568419318752 / 1.171182981502945**; missing-support outcomes have **+infinity**, never epsilon clipping. Point errors use 7.02, not simulated draw loss. Randomized PIT uses `F(y-) + u*p(y)`; e.g. y=7 and u=.43 yields **.6047**.
- Independently enumerated unequal-weight three-dimensional joint law: **ES 2.451043183774045**, weighted **VS_0.5 1.4811219807550753**.
- Separate exhaustive active-face KKT optimizer reference, using independently assembled primitive CDFs on eight synthetic games: W2 weights in sorted `J0,S0,SO0` order **[.14511798499124895, .7517194599106876, .10316255509806346]**. Owner maximum weight error **4.22e-7**. W3 maximum errors: points **1.11e-16**, rebounds **3.30e-9**; the points solution includes an active zero-weight boundary. No historical optimizer ran.
- P2 S1/S2 independent recurrence at fractional 37.25 projected minutes: maximum PMF errors **1.53e-16 / 1.67e-16**, valid mass plus tails and predictive moments.
- Same-draw PRA and all 96 empirical PMFs match manual weighted histograms. Resealed incorrect PRA/shooting/rebound/assist ledgers and nonnormalized PMFs reject in owner plus independent controls.
- 5,000/20,000 precision controls pass; the known-law standard-error ratio is **2**. Replicating rows 1/5,000/20,000 times leaves distinct-game accounting at **2**, and a forged ESS=20,000 on two J paths rejects. Paths remain integration units, not NBA observations. No claim of guaranteed finite-run error improvement is made.

Cross-process O/J/PIT outputs match under Python hash seeds 3 and 8357; input-order J replay also matches. Numerical details are retained in the per-family v3 outputs and [benchmark artifacts](p6_remediation_reaudit_v3_20261116/P4_benchmark/benchmark.json).

## Remaining criteria, ownership and minimal next actions

[The machine-readable criterion ledger](p6_remediation_reaudit_v3_20261116/criterion_ledger.json) supplies exact owner SHA, reproducible command, reason, classification and minimal repair for **every** failing/blocked criterion.

| Criterion | Responsible owner | Decision / classification | Minimum requirement |
|---|---|---|---|
| F-P2-02 | P2 #165 | FAIL — correctness | enforce declared P cutoff at conditional S-to-J boundary |
| F-P5-02 | P5 #163 | FAIL — correctness | reject nested target results/actual exposure in forecast inputs |
| B-P1-01/02 | P1 #167 | BLOCKED — unavailable original/official evidence | admit source chronology, identity, roster, corrections and authentic exception/duration evidence |
| B-P2-01 | P2 with P1 | BLOCKED — evidence and unaccepted native handoff | agree latest P1 source/status/clock/role exports and admissible fitted artifacts |
| B-P3-01 | P3 with P1 | BLOCKED — genuine participation/context fit absent | independently admitted original roster/context and fitted prior contract; retain unknowns |
| B-P4-01 | P4 with P1/P2/P3 | BLOCKED — source registry/version gap | version latest-head consumer and authenticated artifact trust path |
| B-P4-02 | P4, with P2/P3/P0 | BLOCKED — mandatory engineering proof | acceptable propagation/approximation and event/accounting contracts with independent evidence |
| B-P4-03 | P4 coordinating P3/P0 | BLOCKED — scaling limit | verified scalable coupling or explicitly accepted bounded operating range |
| B-P5-01 | P5 with P1/P2/P4 | BLOCKED — native authentic integration absent | immutable native vault/event/release/distribution adapters and agreed identities/cutoffs |
| F-DISCOVERY-01 | P0/repository test custodian | FAIL — test discovery | repair root-package imports without suppressing G0 tests |

Root discovery was independently inspected at the exact P2 head: **1,652 discovered objects, 10 import errors**, all `golden_v2` imports. Test bodies from unrelated repository suites were not run, avoiding unrequested retrospective/modeling work. Dedicated G0 remains green and its bytes unchanged. **Repository-wide CI is not certified green.** This is separate from the independent P6 runner and does not retroactively revoke accepted G0 technical results.

Receipt verification matched **94/95 resolvable declared file digests**. The sole mismatch is P3's handoff Markdown, whose digest predates its receipt-only documentation append; all checked executable digests match. The exact expected/actual documentation hashes are preserved in [receipt verification](p6_remediation_reaudit_v3_20261116/owner_receipt_hash_verification.json), rather than silently treating it as matching. A fresh append-only documentation receipt would remove this traceability discrepancy. The raw root-discovery log also ends with an original blank line; it is retained byte-for-byte despite a `git diff --check` whitespace warning. Source, report and structured JSON whitespace checks pass.

P6's first new P2 test attempt referenced the wrong receipt-key spelling and raised a QA `KeyError`; that raw failed attempt is preserved separately. Only the QA assertion was corrected, and the valid separate-duration control then passed. The final red cutoff case and P5 nested-outcome case are independent owner failures, not this corrected harness issue.

## Reproduction, immutable outputs and gate recommendation

[Runnable instructions](p6_remediation_reaudit_v3_20261116/REPRODUCE.md), three additive QA scripts, raw before/after stdout, per-family new-case JSON, exact Git comparisons, source inventories, independent archive byte hashes, benchmark PMFs/ledgers, numerical references and the [consolidated receipt](p6_remediation_reaudit_v3_20261116/receipt.json) accompany this report. File/raw-source/test-output digests are in `SHA256SUMS`. Previous audit files and the original negative script remain unchanged.

**Formal family recommendations:** P1 **BLOCKED**; P2 **FAIL**; P3 **BLOCKED**; P4 **BLOCKED**; P5 **FAIL**; P6 independent finite QA **PASS**. P6 PASS means the audited controls, independent oracles, expected red reproductions, hashes and reporting work; it is not approval of its own implementation repairs or proof of historical accuracy.

**Formal overall G1 recommendation: NO-GO.** Correct the two owner boundary defects and supply/agree the missing engineering and authentic-source handoffs before another exact-SHA re-audit. Green synthetic suites, callable old-pin integration and matching archive digests do not satisfy those requirements. G0 acceptance remains pinned; G2, retrospective training/validation, historical Monte Carlo family-weight fitting, deployment and Tier promotion remain closed.

Rollback: close this isolated draft QA PR. Preserve its negative evidence, PR #168, all prior reports/receipts and all owner branches. No production rollback is needed because P6 changed no production behavior.
