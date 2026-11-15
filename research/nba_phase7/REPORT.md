# NBA Phase 7 — genuine pregame participation infrastructure

November 15, 2026 — America/Toronto. Governing **PA-V25-MASTER-2026-11-09 / v1.1**. Research-only continuation of PRs #140/#141; neither parent merged. Parent pin `4f509d4b9817a130ab78e2d24a03321459cb452d`. No production deployment, weights, Tiers, schedule, archive rewrite, NUTS or paid-data authorization.

**Decision: preserve the source/identity and pilot-execution improvements, leave P1/P2 unfitted, and block source-qualified F.** We have not demonstrated that a genuinely pregame participation model reproduces the oracle gain. That question is currently unmeasured, not disproved. The next bounded workstream is participation/eligibility acquisition and validation, not a new event likelihood or a full simulator redesign.

## 1. Frozen baseline reproduced before integration changes

GitHub main remained `912bc7010058092ea735dcda0aa941429194474b`; #140 remained draft at `cdf926f56e86bc9d25576acff61fd6f091313159`; #141 remained draft at `4f509d4b9817a130ab78e2d24a03321459cb452d`. The warehouse remains `97a8bb566826afe5a3e5a7b8c632043d8a1dca24`. Original governing documents, pause marker, workflow sources, Deepnote project, relevant original notebooks/PR reports and Phase 6 protocol were inspected. Current inspection found morning settlement and the two existing NHL research automations enabled, afternoon slate disabled, and no schedule mutation. The new Phase 7 Deepnote notebook is unscheduled.

Before changing integration code, a fresh untouched full replay reproduced **all 145 original scientific configuration hashes and exact final score bytes**. Fresh Phase 6 execution reproduced exact `summary.json`, count/minute score gzip bytes, candidate ledger bytes, oracle-abstention bytes and all 55 final A/C/D configuration hashes. Unchanged WS4 scoring independently checked 8,488 count distributions with zero CRPS difference, 3,968 constrained boundaries and 7,040 event scenarios. This is independent-code checking performed by the author, not independent scientific signoff.

| Checkpoint | Reproduced |
|---|---|
| Historical matched appearances | 460 |
| Original J2 minutes CRPS | 5.625994 |
| Raw M0 minutes CRPS | 4.061672 |
| Original J2 points CRPS | 3.993858 |
| Raw-exposure J2 points CRPS | 3.625042 |
| Original J2 PRA CRPS | 5.462042 |
| Raw-exposure J2 PRA CRPS | 4.758284 |
| Complete-participant oracle | 141 appearances / 7 games |
| Incomplete-support oracle abstentions | 17 games / 319 original matched rows |
| Certified pregame eligibility / validated positive participation | 0 |

The original 145 hashes, source/model manifests, 460-row development cohort, all Phase 6 artifacts and quarantines are byte-unchanged. A post-integration full 145-config replay also reproduced its exact scientific hashes and score bytes. No oracle participant set enters any real pregame source input. Baseline receipts and runtime manifests are in `evidence/`.

## 2. Source and identity inventory

The existing WS1 capture path uses ESPN scoreboard, per-game summary, team roster and prior FINAL box adapters. It has public HTTPS access, requiring no credential. Official NBA team/player pages are also public and successfully retrieved now. The NBA CDN player-index probe returned HTTP 403, so no unsupported endpoint was treated as available. The connected Deepnote project retained its existing Secrets integration; that name does not verify a PropLine credential or original market-contract availability. No new sportsbook request or quota was consumed.

The new NBA team-page adapter extracts stable `TEAM_ID` and `PLAYER_ID` plus exact original player name, birth date and roster metadata from original `__NEXT_DATA__` bytes. It verifies NBA and ESPN source hosts, raw receipt hashes, retrieval/freeze clocks, route/team identity, full team name and abbreviation, exact player name and birth date, optional jersey consistency, one-to-one uniqueness and bounded freshness. Missing DOB, duplicate identity, ambiguity, wrong team, unknown alias, stale/future map or changed bytes fails closed. Names alone never create a cross-provider join. Effective observation starts at the latest supporting retrieval; a current map never backdates historical knowledge. Source roster membership still grants no legal game-active eligibility.

Measured bounded audit: **17** NBA–ESPN identity bridges for the Clippers, with **three unresolved source-side records** (one NBA record with an unresolved exact name/DOB match and two unmatched ESPN records). All are preserved; no accent/name alias was invented. This is one-team adapter validation, not complete league/game coverage. Crosswalk file SHA-256: `a0dae11df92b034d1394d5cc3b7a9d6bfb06b175f7d3d46cfd7cab88c9167219`.

The retained original official injury PDF was parsed into **100 player/status rows** over seven pages and **15 NOT_YET_SUBMITTED gaps**. Independent plain-text enumeration exactly agrees with the coordinate parser's 100 name/status rows. Original PDF bytes, original retrieval receipt, header publication claim, page/row names, team, game date/time, matchup, status and reason remain available. Four injury rows resolve through the new bridge; 96 remain unresolved, including unbridged teams outside the bounded one-team audit. The report is not a complete active roster. Available, absence from the report, membership and an announced start never imply certain participation.

**Narrative identity correction:** Phase 6's report mislabeled retained ESPN event 401909987 as Warriors–Clippers. Actual retained raw team IDs/metadata prove it was **Charlotte (ESPN 30 / CHA) at Clippers (ESPN 12 / LAC)**, consistent with official CHA@LAC. Phase 7 initially repeated the bad narrative label and alleged a matchup conflict; that metadata/manual rebinding is preserved in `initial_team_label_audit/` and superseded by `source_identity_audit/`. The executable game ledger already derives abbreviations from original source bytes. Do not use narrative labels as identity truth.

The four mapped rows still **cannot** enter the old 16:09 Toronto freeze: the PDF was retrieved later, and the identity bridge was first observed after that game's tipoff. Final old-freeze rebinding correctly retains zero P0 exclusions and four rejected availability records for chronology. No Phase 6 source, score or report was overwritten, and no failed forecast became certified. `INTEGRITY_AMENDMENT.md` documents this correction.

| Evidence | Working source boundary | Remaining acquisition gap |
|---|---|---|
| Schedule and team IDs | Original frozen ESPN registrations replay; five fresh responses agree on all ten selected IDs/starts/teams | Game-day recheck required; any change blocks the original slot |
| Official injury reports | Original PDF extraction, clock claims, preserved rows/gaps and source-bound identity bridge | Complete two-team identity coverage and timely game-specific binding |
| Roster membership | Existing ESPN raw-byte roster replay; official NBA IDs/DOB bridge | Legal game-active eligibility/inactive declarations remain unavailable |
| Announced starters | Contract field remains separate and unknown | No complete stable-ID official pregame starting-lineup adapter |
| Transactions / assignments | Official roster retains HOW_ACQUIRED and supplemental metadata as raw evidence | No dated complete transaction/assignment/recall eligibility chain; no enum interpreted as automatic legal eligibility |
| Conditional M0 history | Existing source parser and causal feature adapter; optional bounded ten-game lookback | M0 needs five prior appearances for every possible participant; missing laws abstain |
| Original contracts | Existing WS1 exact contract semantics preserved | No new compatible original offers/prices/terms; no market edge or payout claim |

## 3. Working roster, participation and opportunity interfaces

`evidence.py` owns source-bound NBA/ESPN mappings and injury extraction. `sources.py` adds bounded one-shot official supplements **before** final WS1 freeze, rebuilds the existing WS1 roster contract from original bytes, retains all resolved/unresolved evidence and creates `NBAPhase7GameDayLedger/1.0.0`. It records original candidate identities, game/team, source/publication/retrieval/freeze/model hashes, unknown legal eligibility, availability, role, probabilities, M0 support and complete rejection denominators.

`v2/nba_ws1/capture.py` remains the collector. Optional arguments add exact target game, original expected schedule, hard deadline, frozen model cutoff, bounded history lookback and explicitly fixture-only transport/clock hooks. Existing defaults stay intact: two prior team games unless explicitly requested. Phase 7 requests at most ten prior games per side to allow the frozen M0's five-appearance prerequisite. This is bounded source acquisition, not a changed minute model. A real caller cannot inject a clock/transport and claim original capture. Late responses retain bytes/receipt and block; no final packet is produced after tipoff or its deadline.

`participation.py` represents P0, P1 and P2 separately from conditional minute distributions:

- **P0:** only timely, identity/game-bound official Out evidence supplies a deterministic source exclusion. It is explicitly not a calibrated positive appearance model. Conflicts, late evidence and unknown/Available cases stay unknown. Legal eligibility stays a separate field.
- **P1:** UNFITTED; the historical archive has no authentic prior eligible-game/candidate denominator. Prior appearances divided by observed played games would manufacture a participation estimator from survivor-only data.
- **P2:** UNFITTED; no validated eligible training universe or complete source-backed role/teammate-status feature set. Ten pilot games cannot support a detailed model. No invented pooling prior, uncertainty interval or percentage is published.

`participation_aware_j2` uses the existing frozen M0 and J2 simulator. The real-source path requires complete game-day universe, explicit eligibility and validated probabilities; the real validated-method registry is empty, so unsupported F blocks. The fixture-only path is visibly synthetic and never supplies real certification. Any sampled underfilled or infeasible rotation aborts the entire ensemble; no resampling until feasible, no added bench identity, no reallocation of missing players' opportunity. Inactive exposure is zero. A participant missing a source-supported M0 law abstains rather than receiving an invented law. Event rates, pace, conversions, state covariance, OT and event mechanism are unchanged.

Participation entry and M0 minutes conditional on entry are not interchangeable scores. If a future fully supported unconditional research count distribution is produced, no-entry gives structural count zero, while market DNP/void stays a separate settlement state. The current ticket produces no real-source F distribution.

## 4. Prospective pilot readiness and outstanding execution

The exact original registration file SHA-256 is `ab7795753e5ff0e98a4cbaa988897b95c2dc4d6e8371865f3af80cd9167bdf54`. Original selection logic (first two scheduled games by start and stable event ID on each Toronto date) was replayed from preserved source bytes. Five fresh current scoreboard responses verify **all ten** registered identities, times and teams without replacing any slot. These are advance schedule receipts only, not game-day roster freezes.

| Slot | Toronto date | ESPN game ID | Invoke from | Must finish by | Tipoff |
|---|---|---|---|---|---|
| 1 | 2026-11-16 | 401909994 | 18:20 | 18:30 | 19:00 |
| 2 | 2026-11-16 | 401909995 | 18:20 | 18:30 | 19:00 |
| 3 | 2026-11-17 | 401910002 | 18:50 | 19:00 | 19:30 |
| 4 | 2026-11-17 | 401910003 | 19:20 | 19:30 | 20:00 |
| 5 | 2026-11-18 | 401910007 | 18:20 | 18:30 | 19:00 |
| 6 | 2026-11-18 | 401910008 | 18:20 | 18:30 | 19:00 |
| 7 | 2026-11-19 | 401910019 | 19:20 | 19:30 | 20:00 |
| 8 | 2026-11-19 | 401910020 | 19:20 | 19:30 | 20:00 |
| 9 | 2026-11-20 | 401909305 | 18:20 | 18:30 | 19:00 |
| 10 | 2026-11-20 | 401909306 | 18:50 | 19:00 | 19:30 |

Each slot has an executable command and immutable directory design in `RUNBOOK.md`. The acquisition window opens ten minutes before the original T-30 deadline; it must finish by the deadline. Actual source completion/freeze is recorded, never backdated to the target. A not-yet-due invocation makes no live capture; a missed deadline remains missed. Schedule/time/team changes block, never retarget. A single-owner acquisition claim prevents competing collectors; first successful original capture is immutable. Every slot needs a separate future invocation. No unattended execution or new scheduled workflow was created.

At present: **10 NOT_DUE slots, zero due captures, zero new game-day pilot captures, zero F forecasts, zero completed pilot games, zero real settlements, zero original contracts.** Original candidate universes and eventual participation/DNP outcomes remain null until genuinely observed, not fabricated zero-player rosters. Current schedule-only receipts are retained in `evidence/current_schedule_preflight/`. The old original Phase 6 pregame packet remains an unchanged historical receipt; new identity audit retrievals do not become a new original game forecast.

## 5. End-to-end fixture, settlement and matched controls

The safe nonproduction fixture executes exact-game WS1 acquisition, immutable source bytes, roster replay, NBA/ESPN identity mapping, candidate/M0/participation ledger, explicit F abstention on unsupported source evidence, and separately the existing J2 with declared synthetic participation assumptions. Final fixture has 12 candidate source rows, 12 eligibility unknown, zero source-verified positive participation probabilities, zero usable source M0 histories, 12 full-game abstentions and zero original contracts. The separate simulator exercise generates 128 scenarios under the actual frozen model artifact, with **zero conservation/witness violations** and all eight statistics retained. Its synthetic probabilities cannot serve as a fitted participation model or prospective result.

`settlement.py` prepares independently retrieved FINAL outcome parsing through the unchanged WS1 canonical ESPN NBA box adapter. It checks exact source URL/game ID, both teams, start time, FINAL/completed state, original before-tipoff ledger freeze and immutable first-capture hash. Played, played-zero, explicit DNP, unknown/unlisted candidates and missed actual appearances remain separate. Source schedule disagreements block. Market settlement requires exact contract identity, period and explicit DNP/void terms; a missing or null rule blocks. DNP is not automatically Under or push. League-native source parity and external reviewer approval remain open, and source-provider labels are explicit.

No registered pilot game has completed, so **no real settlement is due or claimed**. Parser tests use retained historical final bytes only as labeled fixtures. Future settlement is a separate manual command and append-only directory; no settlement archive is rewritten. Participation Brier/log loss and future count/minute scores remain unavailable, not zero. Complete eligibility and valid forecasts must exist before scored denominators can be formed; positive-only survivors never become an unconditional participation test population.

Frozen historical controls, all 460 original matched appearances; lower count CRPS is better:

| Statistic | F0 | J0 | J1 | Original J2 / A | Raw-exposure J2 / D |
|---|---|---|---|---|---|
| points | 3.584910 | 3.707883 | 3.632785 | 3.993858 | 3.625042 |
| rebounds | 1.425241 | 1.416223 | 1.452700 | 1.558328 | 1.471599 |
| assists | 1.038438 | 0.996417 | 1.002175 | 1.055990 | 1.002009 |
| threes | 0.664683 | 0.666647 | 0.672399 | 0.706952 | 0.671034 |
| pr | 4.205834 | 4.428450 | 4.359161 | 4.936282 | 4.358059 |
| pa | 3.931433 | 4.101919 | 4.029826 | 4.511646 | 4.028769 |
| ra | 1.954950 | 1.962815 | 1.978896 | 2.190566 | 1.992809 |
| pra | 4.619467 | 4.840735 | 4.758684 | 5.462042 | 4.758284 |

Complete-C oracle remains 141 appearances over seven games, with 17 incomplete-support games abstained. Identical 141-row A/C/D and F0/J0/J1 metrics, full means/bias/variance/intervals/zero/tails and the 460-row controls are preserved in `evidence/frozen_control_comparisons.json`. They are historical diagnostics, not Phase 7 prospective forecasts. Real source-qualified B/F comparisons have **n=0 for every statistic**; no predictive improvement, calibration, market edge or transfer of the oracle gain is asserted.

The >0.10-minute allocated-minus-raw CRPS rule is preregistered as a material screening warning on the identical supported appearance population. F has no qualifying observations yet, so that screen is unmeasured. Original A's known minute regression remains exposed and does not become a Phase 7 pass merely because fixture conservation works.

## 6. Validation, compute and independent review

**247 local targeted methods pass**, zero failures/errors/skips: all 205 original/Phase 6 methods plus 42 Phase 7 methods. Tests cover raw source/DOB/team/collision crosswalk attacks, name-only refusal, future/stale clocks, continuation-page PDF completeness, unknown→certainty, source-out exclusion versus eligibility, late/conflicting status, wrong game, underfilled rotations, missing M0 laws, inactive positive exposure, exact second-game selection, schedule changes, after-tipoff capture, late-response retention, duplicate capture prevention, contract mismatch, DNP/void/unknown, retrospective freeze mislabeling and original raw team metadata overriding narrative labels. Initial failing tests, PDF continuation-page failure and superseded team-label audit are retained with corrections. Existing WS1/WS4 tests retain source mutation, same-game leakage, oracle/real-cohort separation and conservation guards.

The original 145-config scientific replay and Phase 6 byte/scenario comparisons pass; unchanged WS4 independent-code CRPS validation agrees exactly. These are reproducibility checks, not external statistical approval.

One unscheduled Deepnote notebook `c9ed15840a87432a9b97691336b74b43` ran the pinned implementation `af8c0893429034924be40f02aea62582e284bfec` on free **Basic CPU (2 vCPU, 5 GiB)** with project storage read-only and temporary fixture files only. Run **`69d58a26-c4f5-487a-8f55-088bfbb9e562` succeeded**. It passed 37 checks and the 128-scenario fixture. Two PDF tests were explicitly unavailable there because `pdftotext` is absent; both passed locally. This older pinned check precedes the final bounded-history/null-terms/raw-team regression refinements, which are tested locally. The current Cloud runtime has `/usr/bin/pdftotext` and is the ready full-PDF invocation environment. Do not claim the free Deepnote image can run the complete PDF chain without provisioning that dependency. No live source requests, market calls or project-storage changes occurred in that test run. Floating scenario hashes can differ across NumPy/SciPy versions; exact cross-runtime float equality is not claimed.

| Execution | CPU seconds | Wall seconds | Peak process RSS MiB |
|---|---|---|---|
| Original 145-config reproduction | 50.236 | 50.260 | 390.496 |
| Fresh Phase 6 A/C/D reproduction | 22.781 | 22.824 | 194.910 |
| Final local capture-ledger / 128-scenario fixture | 0.276 | 0.276 | 82.566 |

Peak RSS is the measured process high-water mark, not incremental per-game memory. Different workloads are not a speedup comparison. Deepnote's fixture CPU 0.583s, wall 0.702s and process peak 497.18 MiB include that environment's initial process/import state. Source network latency is separately bounded by request timeouts and the hard freeze; future successful capture latency is unmeasured. No fitting, GPU, NUTS, paid source or hosted training was used.

**Independent scientific review remains pending.** The author ran a separate adversarial pass and unchanged WS4 code; another runtime does not constitute separate statistical approval. The reviewer runbook explicitly requires original-source, complete-denominator, probability-conditioning, minute-distortion and independent settlement review before any acceptance decision.

## 7. Gates, exact lineage, rollback and next decision

| Gate | Classification | Evidence/limit |
|---|---|---|
| A — Evidence | BLOCKED-BY-DATA | Advance schedule receipts valid, but all registered game-day windows are future; complete eligibility/availability receipts absent. |
| B — Identity | INCONCLUSIVE | 17 source-bound NBA–ESPN identities and four official injury rows resolved; remaining records and complete two-team/game coverage unverified. |
| C — Participation | PASSED | Unknown remains unknown; P0 exclusions require exact source/game/as-of evidence; P1/P2 unfitted and unsupported real F generation blocks. Positive calibrated estimation remains unavailable. |
| D — Opportunity | BLOCKED-BY-DATA | 128-scenario fixture conserves minutes with zero violations; real F sample is zero, so allocation distortion cannot be screened. Original A regression is preserved. |
| E — Predictive quality | BLOCKED-BY-DATA | Frozen F0/J0/J1/A/C/D comparisons reproduced; no source-qualified F distribution or matched future outcome exists. |
| F — Prospective | BLOCKED-BY-DATA | Ten immutable registrations/runbook ready; zero genuine game-day pilot captures or later settlements. |
| G — Adoption | BLOCKED-BY-DATA | External independent statistical review, adequate prospective evidence and reliability gates absent. J2 remains unadopted. |

Frozen model canonical SHA-256: `e424c7f98bba50315dfde81a60978855d6ceb8c72aba8ad0af310eb31283326f`. Original registration SHA-256 is stated above. Source/model/output and implementation-file hashes are recorded in the final evidence manifest and publication receipt; crosswalk rows each retain both source receipts and exact raw hashes. The original source PDF SHA-256 remains `0522cbd3b3e7ddb62a9a2ad965ae873ab1fa2d3bb7354f52c4267d6997a53673`. Source and timing receipt domains are distinct from canonical model hashes. Preregistration commit: `8af6123a0622b1c663cb6c14c8d3c675e644e533`; separate scientific implementation/Deepnote pin stated above. Final draft PR URL/head and verified archive hash are published after packaging, avoiding self-referential commit hashes.

Protected production config, global schedules/workflows, training pause, original source/settlement archives, original joint/Phase 6 evidence (including quarantines), WS2 M0 and J2 event/state/allocation code remain byte-unchanged. The only upstream integration edit is optional bounded WS1 acquisition parameters; its source schema, raw parsers and certification rules are unchanged. Branch is `research/v25-nba-phase7-pregame-participation-20261115`, stacked on #141. No parent draft is merged.

Rollback before merge: close the Phase 7 draft and stop invoking `research.nba_phase7`; retain all genuine first captures, source bytes and failures. If later merged as research, revert Phase 7 commits and optional WS1 capture parameters to `4f509d4b9817a130ab78e2d24a03321459cb452d` after pinning opt-in consumers back. There is no production migration or scheduled job to reverse. The new unscheduled test notebook/run can remain as audit evidence; no running job remains.

The next bounded experiment should target **source-backed eligibility and participation**: obtain complete game-day active/inactive evidence, resolve both teams' identities before freeze, retain at least five authenticated prior appearances for every possible M0 participant, and accumulate all candidate entry/DNP outcomes. Only after an adequate genuine eligible training universe exists should a simple pooled P1 be fitted and chronologically validated. Ten games remain feasibility evidence. If validated source-backed F later exceeds the >0.10-minute distortion tolerance, isolate allocation; if minute forecasts improve but matched stat calibration fails, isolate the conditional event likelihood next. Neither switch is earned by the current n=0 F cohort.
