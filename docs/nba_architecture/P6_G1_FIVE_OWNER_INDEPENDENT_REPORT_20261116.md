# NBA V2.5 — P6 independent G1 engineering-readiness re-audit
**UTC date:** 2026-11-16. **Decision:** **G1 NO-GO**, with reproducible P1 and P5 negative-case failures. **G0 remains independently PASSED** only for its accepted implementation SHA. Research/QA only; do not merge or promote.

## 1. Audit basis and exact scope

- Governing frozen contract: \`nba-sojc-contract/2.0.0\`, independently accepted code SHA \`59d28dc23be97de2a6a82d22be8338151e31f5b6\` (G0 review PR #161 and issue #149).
- Owner submissions individually inspected and cloned at **exact Git commit SHAs**, all research-only:
  - P1 canonical source PR #167: \`e0b8703887d327c8d8ac34807078e75e7b59a540\`.
  - P2 S models PR #165: \`96d210a6100085640e7e82928ab1c864839fc454\`.
  - P3 O models PR #166: \`80dbed35f983839f962250ad1c0236061dc6ee00\`.
  - P4 J joint simulator PR #164: \`b3729c53509cb063e2e451b7e4feb0ac2c6a9552\`.
  - P5 C scorer and optimizer PR #163: \`1d7b8471a85e9d3dafaf809acacfeca6e980dc81\`.
- P6 original QA branch/PR #159, post-G0 extension PR #162, independent G0-level 350-test controls. These were **copied only into disposable test checkouts**. No source owner implementation was edited.
- Existing G1 evidence tracker: GitHub issue #160. P6 has independent gate authority and cannot sign its own fixes.
- The separately named "NBA parallel execution packet" was not available as an attachment in this audit environment. The explicit P6 assignment, accepted G0 repository contracts, GATE_BOUNDARIES_V2, and owner handoffs governed the assessment.

## 2. Independent execution (not owner self-attestation)

Environment: isolated Python 3.12.16; pinned NumPy 2.3.5, SciPy 1.17.0, jsonschema 4.26.0. Every source was checked out from a specific Git branch and **exact HEAD SHA asserted before running**. All analysis executed from an unscheduled, detached read-only Deepnote notebook; dependency installation was into disposable local target directories. The global Deepnote environment emitted unrelated dependency conflict warnings; the test subprocesses successfully imported pinned versions.

- Five-owner independent test notebook \`8b1cf45f0c2541068aa606359d386cfb\`; complete detached run \`a8cbdc84-70d4-44f8-afb9-bf44df26f6a9\`; complete result manifest SHA-256 \`9bcb46c2659f41b5f885ae4916e03e600c03096e500702094c9073cb5f877ba8\`.
- Exact checked-in negative reproducer: \`scripts/nba_p6_g1_owner_negative_probes_20261116.py\` at QA commit \`31a6ef8e35351e9f8875a759ff474109c7c01418\`, raw SHA-256 \`fa8012e260a21caacb2fcebadc02a2deddaf957bc4425b8128dcae2c83ba9e52\`.
- Separate negative-run notebook \`bd76f801c93c483ca4dfca7ab4c42c81\`; detached read-only run \`048f7dee-f17c-4491-bbf6-f403be5f96ad\`; structured probe summary SHA-256 \`613f12817383b329d155528eb686c0ea3c0926c4f2d9b4a971e22be1ac27c14a\`.

| Family | Independent exact-SHA test commands | Test outcomes | Additional independent red probe |
|---|---|---:|---|
| P1 | G0+P1+P6; P1 shard preflight | **380/380 + 9/9 PASS** | **FAIL**, three suspect accounting inputs accepted |
| P2 | G0+P6; S-family unit suite | **350/350 + 22/22 PASS** | **COVERAGE BLOCK**, legitimate two-OT exposure rejected |
| P3 | G0+P3+P6 | **366/366 PASS** | Full real-source opportunity fitting/eligibility still unverified |
| P4 | G0+P4+P6 | **370/370 PASS** | Real S/O/G bridge not yet available; J tests use synthetic rates |
| P5 | G0+P6; C-family unit suite | **350/350 + 31/31 PASS** | **FAIL**, a backdated-date synthetic holdout bypass |
| P6 | Independent reference and negative controls | **PASS as QA harness** | Owner G1 gate not approved |

**Do not sum tests as 1,878 distinct tests.** Most G0/P6 tests were intentionally rerun independently in every cloned owner branch. These results prove the given finite contract/fixture cases, not untested behaviors or historical forecast quality. The deliberately RED reproducer exits 2 for P1 and P5; that is evidence of defects, not a failed Deepnote execution environment. P2’s script exits 0 while reporting the rejected valid-data probe as a coverage limitation.

## 3. New finding F-P5-01 — C holdout guard bypass (HIGH; reproducible FAIL)

Exact tested file: \`v2/nba_c/experiment.py\` raw SHA-256 \`e98d5b1ce0059283d7ca6919d4eb906256f9a3ef4f9be4f7acb7c0a74ca967f9\`.

The optimizer \`CachedCohort.__init__\` calls \`_row_date(row["date"])\` to enforce a 2023–24 holdout quarantine, but fails to establish that \`row["date"]\` corresponds to \`row["event_start_at"]\` before accepting. P6 independently supplied a **fully synthetic fixture** whose \`event_start_at\` was 2023-11-20 at 23:00 UTC, \`frozen_at\` was 2023-11-20 at 17:00 UTC and \`official_available_at\` was 2023-11-21, while \`date\` was falsely set to 2022-10-20. The cache **ACCEPTED** this 2023–24 event metadata; the identical case correctly dated 2023-11-20 **REJECTED** with \`2023_24_HOLDOUT_QUARANTINED\`. The independent \`make_walk_forward_folds\` entrypoint **REJECTED** the mismatched-date fixture as \`INVALID_CHRONOLOGY\`, demonstrating that the defect is specifically in the cohort/optimizer entrypoint, not the fold validator.

**Required P5 owner repair:** validate canonical identity, event/start/freeze/official-release chronology and \`date\`/event consistency inside \`CachedCohort\`, before holdout gating and objective construction. Add the exact P6 red reproducer as a permanent regression, plus valid prior-date control. Preserve \`SYNTHETIC_UNIT_TEST\` authorization restriction, W0–W4 graph, complete-pipeline scoring, source lineage and frozen holdout prohibition. **Do not use 2023–24 outcomes to test tuning.**

**Scientific caveat:** Current \`CachedCohort\` explicitly accepts only synthetic authorization/source profile. No actual 2023–24 historical outcomes were supplied or accessed, and no real weights were optimized. This is a **guard-implementation error**, not a finding of actual retrospective result contamination.

## 4. New finding F-P1-01 — historical box accounting not fail-closed (HIGH; reproducible FAIL)

Exact tested files:
- \`v2/nba_architecture/p1_history.py\` raw SHA-256 \`297750ce2251da07e7d1c8ec48980c5cf7b9aa87dfab7e939104b5da9ec517f9\`.
- \`v2/nba_architecture/p1_vault.py\` raw SHA-256 \`ed398dd8333c84ab3e3738bf6f733ed403655ff86dc544bad0302573dab3e61b\`.

The independent synthetic WS1-hash-correct fixture was accepted and emitted as historical pregame features when the player was tagged as played with **zero recorded minutes and 11 points, five rebounds, three assists and two made threes**. A similarly SHA-correct **900-minute** history row was accepted without any source game-duration/overtime evidence. The separate official outcome vault accepted and SHA-sealed \`PLAYED_ZERO_MINUTES\` with \`{"points":11}\`.

**Why G1 cannot pass:** G0's backward-looking historical date-only proxy remains explicitly \`HISTORICAL_RECONSTRUCTION_UNCERTIFIED\`, which is correct provenance labeling; however the P1 source adapter and official vault do not quarantine the suspect cross-field time/stat combinations. They lack a defensible actual-game regulation/OT duration witness and a settled policy for zero reported minutes with positive officially credited events. These adversarial examples are **suspicious/unreconciled**, not a claim that the real population archive contains such data, nor a universal claim that zero clock minutes can never coexist with a dead-ball stat or rounded official display time. They must be reconciled from authorized event evidence or reported as unresolved, not silently treated as verified ordinary player-game exposure.

**Required P1 owner repair:** add official game-duration/overtime crosscheck or explicit reject/unknown state; adjudicate minutes zero vs recorded positive events using official clock and PBP policy, and keep original-source revisions/snapshots append-only. Do not simply overwrite suspect minutes or stats with zero. Retain historical-proxy certification status. Implement preserved red/green fixtures in both builder and outcome vault.

Additional P1 G1 blockers: 99 compressed shard hashes were **reported** independently verified by owner; this rerun executed 9 synthetic preflight tests but **did not independently rehash the 99 actual bytes**. Historical source publication/roster/DNP/trade/official correction coverage and the season-wide real date-scoped P1→S/O/J source adapter remain unaccepted. Claims of prospective pregame certification are prohibited.

## 5. New finding F-P2-01 — multi-OT history truncated by incorrect fixed cap (MEDIUM; coverage BLOCKED)

Exact tested file: \`v2/nba_s_family/model.py\` raw SHA-256 \`3fb8ab1c81d1f47a85d022cd4280dfeca92b13f7fbbf4af98d6d1760b1ed921b\`.

An otherwise valid synthetic prior-game point-statistic row with **56 minutes** was rejected by \`fit\` with \`SFError("HISTORICAL_EXPOSURE_PHYSICS")\` because the code imposes \`minutes > 53\` as invalid. Under NBA Rule 5, regulation is 48 minutes and each overtime adds five; a two-overtime game permits up to **58** player minutes. See https://official.nba.com/rule-no-5-scoring-and-timing/.

This is an observed **false rejection / unsupported legal training cohort**, not actual leakage or a case that the model accepted corrupted data. The current P2 training row contract contains no official game overtime count, so merely expanding the cap without source-backed game duration is not a valid repair.

**Required P2 owner repair:** coordinate with P1 to add official historical game-duration/OT metadata to the verified training exposure interface, then check \`0 <= minutes <= 48 + 5*OT\` with correct handling of multiple OTs, and add 0/1/2/3-OT positive and negative controls. Preserve cutoff/manifest source checks and S conditional-distribution mathematics.

## 6. Passing mathematical and structural checks

- The direct P5 scorer matched **independent** references:
  - Poisson(λ=1), y=0 full CRPS \`0.47622238819739127\`.
  - NB(r=2, p=0.5), y=0 CRPS \`26/27 = 0.962962962962963\`.
  - Two-atom joint energy \`2 - sqrt(2)/2 = 1.2928932188134525\`.
  - Two-atom joint variogram VS_0.5 \`2.0000000000000004\` (floating-point equality to 2).
- P3 O synthetic laws and P4 J scenarios pass G0 positive-participation, team-minute law/coupling, 240+25×OT, same-scenario PR/PA/RA/PRA, made-three ≤ attempted three, source/game-state SHA joins and repeatable seeded checks at their exact branch SHAs.
- P3/P4 witnessed legal five-on-court intervals in synthetic fixtures; these are **not** substitutes for authenticated real-game active rosters and full source-time/rotation evidence.
- P5 implementation constrains W0/W1/W2/W3 to **complete** S_ONLY, S_O and S_O_J distributions, not independent votes from S/O/J stages. W4 remains conditional/disabled. Paired bootstrap resamples games or dates, not 5,000/20,000 Monte Carlo paths; MC paths are numerical integration units, not new NBA observations.
- The **C date guard failure overrides C mathematical score PASS for G1 readiness**. Proper scores alone cannot compensate for a temporal integrity loophole.

## 7. G1 family verdict and acceptance tasks

| Family | Synthetic code/QA | Actual G1 verdict | Evidence required |
|---|---|---|---|
| **G0** | PASS | **PASS for frozen SHA only** | New G0 version requires separate review |
| **P1 source** | 389 unit/regression tests PASS; independent P1 negative cases RED | **FAIL / BLOCKED** | Correct cross-field minutes/stat/OT and vault quarantine; independent raw source-chain identity/time/season sample QA |
| **P2 S** | 372 unit/regression tests PASS | **BLOCKED** | Fix legal multi-OT history handling; real P1 source and O scenarios; complete four-stat fitted outputs with signed cutoffs |
| **P3 O** | 366 unit/regression tests PASS | **BLOCKED**, synthetic scenario interface usable | Original source-verified participation priors, live roster/role/eligible/DNP/time evidence; integrated full O law with S/J |
| **P4 J** | 370 unit/regression tests PASS | **BLOCKED**, synthetic simulator interface usable | Real S conditional kernels (P4 currently only accepts \`synthetic_fixture\` rate adapter), P3 scenario evidence, original G, event-level accounting/source replay |
| **P5 C** | 381 unit/regression tests PASS; analytic oracle PASS; independent date guard RED | **FAIL** | Fix \`CachedCohort\` holdout/identity chronology; preserve W0–W4 graph and anti-path pseudo-replication; end-to-end scorer on valid owner source distributions |
| **P6 independent QA** | New owner negative probes executed; existing G0/P6 synthetic controls reexecuted in every owner checkout | **QA harness PASS**, G1 overall veto retained | Exact-owner fix regressions, P1/P2/P5 new SHAs, independent reruns |
| **G1 overall** | All submitted families now have code | **NO-GO** | Close verified FAILs, unblock source/integration and pass independent family conformance |
| **G2 and P8–P11** | NOT RUN | **NOT AUTHORIZED** | Full signed G1 and subsequent integrated G2; no accuracy/weight/production claims under P6 |

**Non-authorized actions:** retrospective predictive validation, using known 2022–23 or 2023–24 results to tune weights, hidden use of actual target minutes, product/market scoring, Tier publication, release, model/collector repair by QA, NUTS training, production schedule changes.

## 8. Routing, next exact check and rollback

Route F-P1-01 to P1 [PR #167]; F-P2-01 to P2 [PR #165]; F-P5-01 to P5 [PR #163]. Keep P3 [PR #166] and P4 [PR #164] in synthetic-tested research status, and do not impose G1 PASS merely because source integration is absent. Post the complete issue tracker status to issue #160 with link to this report.

Owners should submit *new* exact SHAs, minimal negative/positive test cases, raw SHA receipts and explicit implementation boundary; independent P6 then reruns on those exact artifacts. Fixes must be implemented by the owners; P6 has not repaired or silently rewritten any likelihood, scorer, source, minute allocator or simulation.

**Rollback:** close the new P6 QA draft PR and leave accepted G0, all five owner PRs, previous QA PRs #152/#159/#162, historical source receipts, V1 benchmark, Deepnote production notebooks and automations untouched. Preserve these new negative receipts verbatim; a future green regression never retroactively changes this FAIL record.

**Formal recommendation: G1 NO-GO. G0 PASS remains valid for its precise accepted SHA; research engineering of P1–P5 may continue under isolated branches, but G2/integrated historical replay and all promotion gates remain closed.**
