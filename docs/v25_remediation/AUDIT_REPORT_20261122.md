# Pick’em Auditor V2.5 — P0–P6 remediation and independent integration report

**Report date:** Sunday, November 22, 2026 (America/Toronto)  
**Release decision:** **NO-GO for operational cutover, production promotion and merge**  
**Scope:** NBA / NHL shots on goal research-only. NFL collection, NFL automation, legacy comparison artifacts and all trusted Tier/weight settings were left unchanged.  
**Repository:** `royalexx/pickem-auditor`; **Deepnote project:** `9cc31536-93be-44db-bdeb-06fba3f61410`.  
**Independent reviewed code under test:** `001ec263ac1e6f4ee7e45ab3c629167c679a70fb`. Later commits containing only documentation do **not** change that tested code, but are not mislabeled as newly executed test SHAs.  
**Reviewable work:** draft [PR #206](https://github.com/royalexx/pickem-auditor/pull/206) on branch `integration/v25-p0-p6-remediation-20261122`, based on verified P0, **not merged**.

## Executive findings

Five previously observed deterministic defect groups were addressed using their existing component owners rather than an alternative modeling architecture:

1. **P4 Gamma–Poisson model kind:** corrected two wrong test fixture labels from `gamma_exposure_mixture` to the registered `full_gamma_poisson_exposure`, without relaxing `UNKNOWN_MODEL_KIND` or altering the likelihood.
2. **P5 NHL C10 time unit:** replaced raw UTC date slices with `America/Toronto` calendar-day conversion, with winter, summer, daylight-saving, midnight and independently authored P6 regression checks. The registered 40-date horizon and native NB2 shape 4 remain unchanged.
3. **P5 actual Deepnote model-registry publication:** replaced unsupported `os.link()` transition with fsynced immutable prepared records and an exclusive-create zero-byte commit marker. Added independent read-only lock selection and exact repeat-write idempotence, preserving parent compare-and-swap checks.
4. **P2 `record_sha256` suite:** verified final corrected source tests **49/49**; the old 41-case result is not used for certification.
5. **P1 NBA original-source retries:** repaired a genuine second same-day invocation failure `IMMUTABLE_COLLISION` by making daily and repeated claim-attempt manifests separately immutable and content-addressed. Previous immutable files and missed old pilot evidence remain untouched.

The updated unified P0–P6 branch passed **261/261** relevant component and independent mathematical-reference tests against the same exact source revision. Real Deepnote project-FUSE synthetic-registry tests additionally proved two distinct competing writer processes do not both claim a parent revision, a forced pre-commit failure does not replace the prior eligible model, orphan files remain invisible, and committed model versions and rollback are recoverable in a later detached read-only execution.

A genuinely captured NBA original **schedule only** was independently verified and recovered. A player-specific qualifying source, frozen original forecast, independently verified official FINAL settlement, actual fitted research model update and later real forecast are **not present**. The NHL signed complete source bundle is likewise missing. The original **NO-GO remains justified**.

## A. Repository integration, owner boundaries and exact commits

`main` was verified unchanged at `912bc7010058092ea735dcda0aa941429194474b`. All historical owner PRs #198–#205 remain unmerged drafts; old audit #205 and its negative receipts were preserved.

| Owner | PR | Latest source head used / verified |
|---|---|---|
| P0 shared contracts | #198 | `c14de84839161f207d6fd7524c18d68b13707365` |
| Old Phase8C bridge, separate dependency | #199 | `99ee844bb2cc860791b32c44077d5e2185fecc4b` (NOT merged or activated) |
| P1 NBA + same-day retry remediation | #200 | `9a3ff231d5649edda93d5c39da13149f7b02ca40` |
| P2 NHL source | #201 | `24b0159682a19d344b0baa6cd1f6e5a24db4802d` |
| P4 NHL math/registered fixture | #202 | `df3171b1aa2e457c89037a830d857c5f76238b1f` |
| P3 NBA distributions | #203 | `2280c751e4385400f681d19c5acaf6bce09c8423` |
| P5 settlement/registry remediation | #204 | `cf1655253e18cdd5b24615215307909f5d8ccfc5` |
| P6 independent QA | #205 | `14902fe786038698d259a1ae28295cb3ae4f756e` |

The native NBA WS1 source files were selected from PR #144's exact older research head `ceddb41e8e13029849ec82ba2b537faab0ee0a24`. The new integration branch was created directly from P0 `c14de848...`; a **single-parent selective source-tree commit** `84b4e966b1e56709852449adf077421dc3f78a05` imported 59 owner-owned blobs. The following commits integrated corrected P5 and P1 files without treating PR #199's old research stack, P4's previous-main base or native G1 owner branches as automatically compatible. The complete verified original blob list, each owner SHA, overlays, parent commits and resolved non-overlap are in [INTEGRATION_MANIFEST_20261122.json](INTEGRATION_MANIFEST_20261122.json). **No broad blind merge, no unrelated code change on main and no production cutover occurred.**

The P0 legacy Phase8C worker bridge remains an explicit dependency exception. Its old fixed-date pilot cannot be backfilled, and importing its separate research stack merely to eliminate a green-check dependency would violate the release rules. The current research rolling collector directly reuses native WS1; it is not a second live collector.

## B. Unified mathematical/software tests

The exact code revision `001ec263ac1e6f4ee7e45ab3c629167c679a70fb` was checked out in a **fresh detached Deepnote run**, with the original native modules in one sparse checkout and P6's original independently authored reference tests pointed to the exact new P3/P5 source bytes (not the stale November 21 audit staging folder). The first integration trial's sparse-test fixture omissions were preserved and repaired in the test environment, not masked by code modifications.

| Test family | Passed | Failed / errors | Actual measured subprocess wall time |
|---|---:|---:|---:|
| P0 nine record contracts and writable-project storage | 63 | 0 | 18.46 s |
| P1 NBA original rolling/source/feature tests, including new repeat tests | 47 | 0 | 3.00 s |
| P2 complete original NHL source/provenance suite | 49 | 0 | 27.40 s |
| P3 NBA distribution / joint synthetic suite | 27 | 0 | 2.24 s |
| P4 NHL model / frozen readback suite | 16 | 0 | 2.02 s |
| P5 settlement/registry and lifecycle suites | 42 | 0 | 1.08 s |
| P6 independent Poisson/NB2/Gamma, C10, 3-way scores and joint numerical suite | 17 | 0 | 1.56 s |
| **Total** | **261** | **0** | — |

- Exact detached test run: `17213080-970b-4d1e-b19f-70ba35836401`.
- Verified saved test receipt: `/work/research/v25_remediation_20261122/unified_component_test_receipt_v3.json`.
- Receipt SHA-256: `c4809fbcaeab3b3e762c8ef5e094cb504ef9945da5c5ba7e1ad62d336b9f483a`.
- Sparse checkout/test preparation elapsed 57.687 s; reported Python parent-process peak RSS 250,248 KiB (not a measurement of all model worker processes or a future resource guarantee).
- The previous failing P6 C10 UTC/Toronto reference was **not deleted or weakened**. When independently pointed to the corrected integrated scoring source, it passed.

This is regression and mathematical correctness evidence, not statistically significant predictive improvement, source qualification or economic edge.

## C. Real Deepnote persistent storage and model-registry tests

P0's attested logical `/work` is confirmed to resolve to `/datasets/_deepnote_work`. A final unified P0 63-test execution passed on a **real writable project mount**. Its existing cross-detached attestation proofs remain authoritative; no environment variable was used to bypass them.

P5's prior `ATOMIC_TRANSITION_LINK_UNSUPPORTED` caused by `os.link()` remains in the preserved November 21 audit. A revised exclusive-create marker protocol was then tested on the actual FUSE project mount in a strictly synthetic namespace:

- **Writer run** `e3037d58-583e-4dbc-90fb-946178f26b22`, project root `/work/research/v25_remediation_registry_canary_20261122/experiment_B`.
- **Independent detached readonly reader** `2e6e9b45-bdcc-4d7a-93c9-381939aaa345`.
- Receipt `fuse_stress_receipt.json`, SHA-256 `eb024cce51a7f6fb84e599e200503c19fd4dd403d8662b5218279bbbdc39ca51`.
- Two distinct operating-system writer processes attempted the same model parent: one committed version 2, one received `REGISTRY_PARENT_VERSION_RACE`.
- A repeated byte-equivalent registration returned `IDEMPOTENT_EXISTING`; an injected failure before marker creation left an orphan but did **not** displace version 2.
- Recovery committed version 3 while preserving the orphan, followed by an immutable rollback transition.
- The later readonly process verified **four** committed transitions, all linked artifact SHAs and the exact as-of version sequence **1 → 2 → 3 → 1**, with orphan prepared bytes still present.

A previous smaller synthetic canary did publish two versions but its optional orphan-test script terminated on an unrelated test-harness path-construction typo; that failure and the earlier read-only lock issue were kept in notebook run evidence rather than reinterpreted as an unconditional success.

**Limitations:** these are synthetic state parameters and synthetic observations; zero authentic official-result fitting operations occurred. The tests cover observed FUSE namespace, process locking, cross-run recovery and error injection, not a physical power-cycle durability guarantee, all possible external filesystem failures or indefinitely retained backups. Model-validation, prospective accuracy and authorization remain separate gates.

## D. Original source and model evidence — independently checked counts

A fresh read-only inventory of `/work/research/p0_integrity_store` was performed in run `15af45d2-eeaf-4999-8f8d-645c37a05a98` at **2026-11-22 16:11 UTC**:

| Canonical P0 record | Number verified |
|---|---:|
| SourceReceipt | 0 |
| PregameFeatureSnapshot | 0 |
| ModelArtifact | 0 |
| ForecastSnapshot | 0 |
| MarketQuote | 0 |
| OutcomeRecord | 0 |
| SettlementRecord | 0 |
| TrainingUpdateReceipt | 0 |
| ExperimentManifest | 8 NBA records |

These counts are limited to that **canonical** P0 inventory time and do not erase older research archives elsewhere or deny future captures. The eight experiment manifests are **not** eight original forecasts.

**NBA schedule-only genuine source:** An unscheduled, real-clock November 22 P1 research attempt, after full native dependency repair, captured a genuine ESPN schedule document with **7 unique scheduled NBA games** and **14 event-phase windows classified NOT_DUE**. It produced **zero player-specific pregame feature bundles, zero frozen distributions and zero market offers**. Original schedule bytes SHA-256 `ac1014d1fd8af2511814e634d58838eab7177f975bc3ebfc0bc08539922f4906`, P1 development P0-compatible SourceReceipt SHA-256 `28ec2c98e199fcda2aa86ce30a6a764f3e8007ecec23da675fb6e56de6d0a5ba`, daily immutable manifest SHA-256 `2e25b65d7c83f844e08e8d450c56f7e627785a12b2ff1c6170a8f3e8f7fbdd34`. Source writer run `ec7c7aaa-7daf-424b-99d5-ad11e2858455`; a **separate readonly detached recovery** verified original bytes, receipt, identities, clock ordering and manifest in run `179d7168-9fc7-42cb-bd1c-791f8bcd3d53`. The source timestamp is supported as **collector possession**, not independently authenticated ESPN publisher publication.

The earlier NBA source-only runs are preserved: the first sparse checkout omitted original `population_normalizers.py`, an integration harness dependency; after restoring its existing scripts, the second run exposed the genuine fixed manifest collision, corrected in owner code. No missed pilot or old source bytes were rewritten.

**NHL source-only:** P2's November 22 genuine clock run `ec7c7aaa-7daf-424b-99d5-ad11e2858455` reported **zero capture-window admissions, zero roster-source bundles, zero quote-qualified observations and zero frozen predictions**, with no invented fallback and no recorded rejection at that time. The append-only P2 run SHA is `858ce60f99ed3ae7a59f04377b87fb293b33b97e39e9a5026d602f2543f1f500`. The earlier independently observed NHL official HTTP failure is not erased by a no-admission day; a signed event+both-roster+historical SOG/TOI canary is still required.

Thus **NBA source discovery is genuine and independently recovered; NBA player pregame forecasts are not**. NHL source/model operational certification is not reached.

## E. Models and scientific integrity

- **NBA S0:** existing Poisson/NB2 complete-count infrastructure passed source-independent synthetic tests, but an original S0 frozen forecast with actual eligible model and as-of provenance has not been generated. Conditional-on-played distributions must never be scored as unconditional appearance probabilities.
- **NBA S1–S4:** retained research pipelines. The original native G1 independent audit reported **26 pass, 2 fail and 8 blocked**; this remediation did not automatically replace those native cases with P3's synthetic joint model. Their complete native G0/C interface is still unaccepted.
- **NBA O/J:** original full-team roster, participation/minute constraints, and complete immutable same-scenario witnesses remain gated. A fixed P0 row name cannot create native source or joint scenario evidence. S/O/J remain connected stages, not separate votes.
- **NHL Poisson / original Gamma–Poisson:** mathematical distributions and readback pass the 16-case suite; no new genuine source-bound original Gamma fit / original plugin-Poisson control has yet been frozen and published in canonical P0.
- **NHL registered native NB2:** fixed `shape=4`, original Gamma-derived plugin-Poisson mean, genuine original book/line/side prices, exact identity and locked evaluation remain mandatory. Neither the older Phase 1.5 pooled-peer alternative nor an interim dispersion estimate substitutes for them.
- **NHL C10:** authoritative local slate-date grouping now passes winter/summer/midnight/DST and independent P6 tests. No claimed qualified 40-date result; prospective quote and pairing denominator is zero in the newly verified canonical pipeline.
- **P5 scores:** analytical references for count CRPS, NLPD, three-way Over/Under/Push scores, randomized PIT, NBA two-particle Energy Score, joint Variogram and correct sample/game interpretation pass. No authentic new official settlement was available; therefore no genuine calibration or superiority number is reported.
- **Adaptation:** synthetic research registry state mutations passed, but **official eligible training observations = 0** and **genuine validated fitting updates = 0**. Never call synthetic state changes real online learning. Keep locked Poisson/Gamma/NB2 comparators and legacy 60/40/NUTS archives unchanged.

The [machine-readable status ledger](STATUS_LEDGER_20261122.json) distinguishes previous status, actual remediation, exact SHA, owner tests, authentic evidence, model family gates, next action and engineering / prospective / daily learning verdicts.

## F. P6 adversarial coverage and independent release decision

The independent historical #205 NO-GO remains preserved, with the original reproducible hardlink, P4 fixture and C10 date failures. The exact-owner P6 independent **17/17** mathematical and temporal tests now pass against the unified source revision.

The larger 22-case fault matrix is **not all independently executed**. [P6_FAULT_MATRIX_20261122.json](P6_FAULT_MATRIX_20261122.json) records:
- **3 limited actual-mount independently reproduced PASS cases:** failed registry publication (repaired), concurrent registry writers/readers, and immutable rollback/recovery, all with synthetic model state;
- **13 owner-test evidence only** cases;
- **4 not yet executed** cases;
- **2 blocked by external original-source availability** cases.

The matrix deliberately does not convert owner's synthetic tests into 22 independent full-pipeline passes. Genuine official-source mutation/correction, worker termination/replay, full original forecast ledger recovery, combined NBA/NHL failure isolation, GitHub publication failure, real morning idempotence and original DNP scoring still require isolated independent fault injection.

**Independent mathematical-reference gate: PASS. Full P6 engineering/release gate: BLOCKED. Prospective P6: BLOCKED. Research daily-learning P6: BLOCKED.**

## G. Phase acceptance matrix

| Phase | Narrow verified engineering evidence | Overall engineering gate | Prospective operational | Daily learning |
|---|---|---|---|---|
| P0 | 63/63; real Deepnote common-storage and contracts | PASS for common foundation | BLOCKED, canonical original ledger empty | BLOCKED |
| P1 | 47/47; native WS1 reused; original NBA schedule SHA and readback | BLOCKED, original player source/feature freeze absent | BLOCKED | BLOCKED |
| P2 | 49/49 source tests | PASS for source contracts, live signed bundle still gated | BLOCKED | BLOCKED |
| P3 | 27/27 synthetic distributions | BLOCKED, native G1/O/J/C missing | BLOCKED | BLOCKED |
| P4 | 16/16 registered mathematics/freeze | PASS for distribution/freeze subsystem | BLOCKED, P2 original Gamma inputs absent | BLOCKED |
| P5 | 42/42 + physical synthetic FUSE transition/recovery | BLOCKED as complete original settlement/learning pipeline | BLOCKED | BLOCKED |
| P6 | 17/17 independent references; 3/22 limited FUSE cases | BLOCKED, incomplete 22-case matrix | BLOCKED | BLOCKED |

An engineering PASS for a **named narrow component** never implies its phase is fully operational or production-ready. The overall disposition for the unified research workflow is **NO-GO**.

## H. Existing automations, rollback and next genuine opportunity

No task was created, enabled, disabled, rescheduled, rewritten or repinned. Connected automation definitions were inspected again on November 22:

| Task | ID | Current enabled state | Next existing execution |
|---|---|---|---|
| NBA original six-day pilot | `6afa51eeb1488191956f2d672edf6d33` | Disabled/expired, old pin preserved | None |
| NHL SOG shadow | `6af480bda1448191b892f43091479f8d` | Enabled, old registered experiments unchanged | November 22, 17:30 EST |
| Morning settlement | `Automation_12f6ba43eb748191a213917780254329` | Enabled, NFL/legacy responsibilities unchanged | November 23, 06:00 EST |

The **exact full prompts, schedules, enabled statuses and current pins** were saved **privately to the connected Deepnote project only**, never into the public GitHub repository, at `/work/research/v25_remediation_20261122/private_automation_rollback_snapshot.json`. Independent read-only run `a770d0d8-e34c-407b-8a48-aa634b5b441f` verified 3 complete task definitions; SHA-256 `2d3ec761af2d19179688c2c10eb3ca71702400f162f2b510cf03811b9d0cd36f`. This is a rollback snapshot, **not evidence of cutover**.

For the next directly observed eligible NBA game, the actual source archive lists `espn:game:401910029` for November 22, 2026 at **20:30 UTC (15:30 Toronto EST)**. Existing P1 event-relative windows, subject to verifying that the official schedule did not change, are **19:20–19:40 UTC** (early) and **19:55–20:10 UTC** (final). A source-only command executed before those windows correctly returns `NOT_DUE`; execution after the deadline must report `MISSED_FREEZE`. An accepted genuine source capture in those windows can begin the missing evidence lifecycle **without modifying the old six-day pilot**.

The [research-only runbook](RESEARCH_ONLY_RUNBOOK_20261122.md) contains actual current entry points, root and provenance checks, current no-go conditions, eligible morning read-only inventory, failure isolation, mandatory activation gates, exact owner tasks and rollback discipline. It is not an automation deployment claim.

## I. Remaining independent gates, in dependency order

1. **NBA live player sources and S0:** in a genuine next pregame window, execute original P1/WS1 roster/history capture, verify all player/game original receipts and participation-unknown semantics, complete P0 promotion and freeze an accepted SHA-bound S0 count distribution before tipoff. Independently reopen the bytes in another process.
2. **NHL official signed source:** reproduce a successful current official NHL event and two-roster capture with bounded legitimate HTTP handling, sign C03 lineage, bind eligible historical SOG/TOI; qualify quote-free distribution sources separately from market-linked native NB2 offers.
3. **Native NBA G1/C:** independently reproduce the prior 2 fails and 8 blocked cases on owner branches, preserve math/physical constraints, and implement accepted full-scenario identity/witness adapter without inventing participation or whole-team inputs.
4. **Genuine forecast lifecycle:** freeze an original P3/P4 eligible model per sport, await independent official FINAL and DNP/play-zero reconciliation, calculate proper scores, append immutable settlement revisions and retain the rejected/unmatched denominator.
5. **Real research update:** only after new verified eligible official observations and an approved fit callback, demonstrate a reproducible *actual* state change, training cutoff/SHA, validated registry publication, later-only selection and rollback. Otherwise issue `NO_ELIGIBLE_UPDATE` or `UPDATE_METHOD_NOT_APPROVED`, not a training success.
6. **Full P6 independent faults:** complete the remaining 19 cases under their specified classification and independently review FUSE crash/publication claims and the exact final unified code SHA. Retain original negative tests.
7. **Authorize task cutover separately:** protect and re-inspect existing automation definitions, use event-relative pregame dispatch that actually covers matinees, preserve NHL C10/r=4 and NFL responsibilities, and validate a subsequent actual Deepnote execution before declaring active operation.

**Final decision:** concrete code remediation, exact-Git integration, mathematical regression and synthetic real-mount registry engineering have advanced materially. Genuine original full player forecasts and official research learning are still unavailable; the responsible final state is **research-only draft, no activation and no model promotion**.
