# Pick’em Auditor V2.5 — P5 daily settlement and research learning: P6 engineering handoff

**Document:** PA-V25-P5-P6-HANDOFF-20261121  
**Date:** 2026-11-21 (America/Toronto)  
**Branch:** `integration/p5-nba-nhl-daily-settlement-learning-20261121`  
**Base:** P0 `integration/p0-nba-nhl-contract-storage-20261121`, commit `c14de84839161f207d6fd7524c18d68b13707365`  
**Repository:** `royalexx/pickem-auditor`; GitHub connection reported visibility **public** during this audit despite the user's description as private. Do not put secrets, quotes containing credentials or private source bodies in the repo.  
**Deepnote project:** `9cc31536-93be-44db-bdeb-06fba3f61410`  
**Disposition:** **ENGINEERING_ONLY; P6 INDEPENDENT AUDIT REQUIRED; NOT OPERATIONALLY READY.** No PR merge, collector pin update, active scheduler change, trusted Tier, production/research 60/40 weight change or NUTS restart is authorized.

## A. Verified upstream handoff inventory (exact pinned commits)

|Owner|Draft PR|Current inspected branch commit|Integration classification|Required recovery|
|---|---|---|---|---|
|P0 common nine-schema contracts and attested storage|#198|`c14de84839161f207d6fd7524c18d68b13707365`|ENGINEERING_ONLY|Native owner-to-P0 warehouse evidence and P6 review|
|P1 NBA original capture, source-listed subset|#200|`cf71e6662347755020217c78a04642a5b36ec5a9`|BLOCKED_BY_SOURCE|Actual next-game original source snapshot; source-listed participation, eligibility and original model entry|
|P2 NHL signed original-source capture|#201|`24b0159682a19d344b0baa6cd1f6e5a24db4802d`|BLOCKED_BY_SOURCE|Fresh 49-case test receipt, authenticated official signed histories, native P4 source manifest|
|P3 NBA S/O/J distributions and frozen P0 forecast|#203|`2280c751e4385400f681d19c5acaf6bce09c8423`|BLOCKED_BY_MODEL|Approved original J physical witness; participation and P0–G0 C bridge; accepted original fit|
|P4 NHL Poisson/Gamma–Poisson/NB2|#202|`786f3c900922b1bc8a11de85659bc97150369a4f`|BLOCKED_BY_MODEL|Execute 16 authored tests, verify native original Gamma and registered NB2 comparator, P0 daily ingest|
|Existing main|`main`|`912bc7010058092ea735dcda0aa941429194474b`|PRESERVED|No production or NFL changes|

All upstream PRs above were draft/unmerged when inspected. P1/P2/P3 stack on P0, whereas P4 starts from `main`. This P5 PR intentionally stacks on P0 only, with owner interfaces consumed through optional strict adapters. Do not merge owner branches to invent cross-owner acceptance.

**Governing contracts:** P0 `PA-P0/1`; P1 feature contract `PA-NBA-P1/1`; P2 source bundle `PA-P2-NHL-SOG-SOURCE-BUNDLE/1`; P3 frozen P0 full-count forecast; P4 forecast `v25_nhl_sog_p4_full_count_v1`; P4 adaptive `v25_nhl_sog_p4_adaptive_gamma_rate_v1`; existing canonical registry `v25-stat-registry-1`; P5 model registry `PA-P5-REGISTRY/1`, settlement `PA-P5-SETTLEMENT/1`. P4's native model is not automatically P0-admitted simply because its staging SHA verifies. A P0-to-native G0/C witness bridge remains absent and **must not be replaced with field renaming or a synthetic witness**.

**Recorded upstream independent evidence:** P0 Deepnote run `b57d7efa-0972-4bb9-b615-64e299232951`, 63/63 success (project-attested). P3 run `3825c447-47dc-4d0c-a018-e995c7e2a180`, 27/27 synthetic research QA success. P2 `8088b89e-c7ae-4de7-a5cd-1c2c5c2588bb`: 49 cases, 4 KeyError errors and subsequent patch without an exact current-head rerun at the time of inspection. P4 Deepnote execution blocked by Team Trial parallel-project limit; 16 authored tests are **not** evidence of code-level PASS. Independent NBA G1 PR173 was **NO-GO** (26 PASS/2 FAIL/8 BLOCKED); later draft branches do not override that decision.

## B. P5 code boundaries and runnable modules

|Path|Purpose|Engineering scope|
|---|---|---|
|`research/p5_daily/scoring.py`|Full nonnegative-integer PMF scoring, analytic Poisson/GP/NB2, random PIT, zero/tails, categorical O/U/Push, Energy and Variogram, cluster paired tests, registered NHL pair guard|Synthetic mathematical QA passed; no real scores|
|`research/p5_daily/workflow.py`|P0 freeze re-admission, independently verified postgame settlement, original quote/contract separation, revision append, training eligibility and strict model callbacks|Synthetic QA passed; no original source/forecast live canary|
|`research/p5_daily/official_adapters.py`|Pure outcome extraction from **existing** `v2.official_nba_nhl_capture` official NHL/NBA final parsers; no HTTP or collection|Synthetic final-box verification passed|
|`research/p5_daily/warehouse.py`|Attested P0 SHA/ID-claim reader, official outcome vault, canonical forecast/outcome identity reconciliation, no-write inventory, isolated morning run|Read-only real P0 storage inventory passed; no original forecast rows|
|`research/p5_daily/complete_pipelines.py`|Valid complete NBA pipeline comparison, W0, W1, W2 global, W3 stat-specific with prior-label/min-cluster gates, W4 blocked|Synthetic matching/weight tests passed; native G0/C scientific interface blocked|
|`research/p5_daily/registry.py`|Append-only official-revision-aware observations, as-of corrected outcome selection, code+training source SHA registry, exclusive SHA writes, file-lock serialized transitions, rollback and as-of model selection|Synthetic registry/concurrency/version lifecycle QA passed|
|`research/p5_daily/native_update_adapters.py`|Optional owner P3 full-refit and P4 adaptive-only Gamma callbacks with verified minutes/TOI and explicit gates|UNEXECUTED against owner integration; missing authentic inputs|
|`scripts/p5_daily_research.py`|Manual **read-only** inventory by default and opt-in research settlement; no scheduler|No production invocation|
|`tests/test_p5_daily.py` and `tests/test_p5_integration.py`|Mathematical, temporal, identity, DNP/push, revision, complete pipeline, native official, model registry and full synthetic lifecycle tests|37 tests passed in detached Deepnote run; expanded correction/idempotence rerun to be reported separately|

The repository code only adds P5 research modules and tests/docs. No original collector, owner model likelihood, P0 shared field, production weight, NFL path or existing automation has been changed.

## C. Original frozen forecast admission and independent settlement

1. Require **original recorded** P0 `ForecastSnapshot`, feature, model, source receipts and optional exact market quote; verify P0 immutable ID claim, canonical body SHA, raw source and model bytes, exact player/event/team/stat identity, and UTC chronology. Invalid, reconstructed and uncertified original populations are not silently promoted.
2. Original A: market-free complete distribution. Original B: verified real quote with matching source, line, side, time and authentic contract. Reconstructed C: separately reported; never counted as genuine originally prospective.
3. Official final: reuse `v2/official_nba_nhl_capture.py` final/identity/played parsers. The P5 pure adapter makes typed P0 source and outcome records **from archived bytes** and requires an independently evidenced official event crosswalk and raw archive; it never fetches another pregame scoreboard. Missing skater/player final row is **UNKNOWN**, not DNP. Played with official zero remains a scoreable zero.
4. Official outcome vault remains independent from the pregame forecast archive. P0 `admit_settlement` rechecks exact official source bytes, availability, finality and identity before settlement.
5. Distributional statistical scoring is separate from original bookmaker line settlement. No real quote: a genuine A full count distribution is still scoreable. Market B: only complete verified original terms permit exact three-way O/U/Push and HIT/MISS/PUSH, while void/DNP rules are external. P5 does not infer missing odds or EV.
6. Corrections append a new `SettlementRecord` version with original frozen forecast SHA unchanged. Settlement timestamps are deterministic from first verifiable official source availability/possession rather than wall clock of rerun. Identical reruns return preexisting exact byte receipt.
7. C10 original NHL prospective paired native NB2 is admitted only with original plugin Poisson from the **same player, event, book, quote, line, source freeze, original mean and outcome**, fixed native shape 4, 40 distinct prospective dates before confirmatory review. Interim scores are descriptive, without tuning or promotion. The Phase 1.5 pooled-peer experiment cannot substitute.

## D. Scores, denominators and learning controls

**Full distribution:** `CRPS = sum_{k>=0} [F(k) - 1{k>=y}]^2`; negative log predictive density `-ln p(y)`; mean error, squared error and cohort RMSE; signed bias; randomized discrete PIT `F(y-1)+U*p(y)`; predicted/realized zero, lower and upper tails and coverage. Scores use frozen PMF/parameters with quantified finite tail truncation; P4's bounded upper residual is never silently renormalized. A zero-probability outcome has infinite log loss as mathematically required.

**Original contract:** exact three-way probabilities computed from the same count law, categorical Brier `sum_{s in {O,U,P}}(p_s-I_s)^2`, categorical log loss `-ln(p_observed)`. Verified integer-line pushes are neither wins nor losses; DNP/void cannot be scored as played-zero.

**NBA joint:** shared scenario distributions only, same-scenario PR/PA/RA/PRA accounting, Energy Score, Variogram `VS_(0.5)`. No independent S/O/J votes; W0 frozen champion, W1 eligible complete-pipeline equal mixture, W2 global regularized simplex and W3 stat-specific fit on earlier matched observations. Default minimum 40 independent dates AND 40 games is a **preliminary engineering guard, not a scientific sufficiency declaration**. Cross-fitted calibration/selection and date/game clustered uncertainty require actual eligible matched data. W4 is disabled.

**NHL:** full-count Poisson, Gamma–Poisson and NB2 reference statistics and matched original native pair as defined above; conditional-on-played scores only verified PLAYED outcomes, preserving all DNP and absent denominators. Do not infer unconditional performance from this conditional cohort.

**Training separation:** original official completed-game vault, later eligible training observations, reconstructed historical data, original prospective forecast/outcome scores, locked confirmatory cohorts and adaptive challengers remain distinct. Observations have unique player/game/stat/official-version keys and original official receipt SHAs. As-of selection uses only corrections actually available by the cutoff. A repeated date/game, multiple props or 20,000 Monte Carlo paths never count as independent games. Raw official outcomes without prior forecasts may be training-eligible if independently authenticated and admitted; no missing historical forecasts are invented.

**Update policies:**
- NBA S0/S1/S2: P3 owner reports `PERIODIC_FULL_REFIT_ONLY`; no silent daily online algorithm. Future approved bounded periodic refits require separately verified official minutes, previous cutoff, full origin sample and explicit resource budget.
- NBA O/J: prediction-only until an owner-certified parameter update with fitted participation/game-state evidence is delivered; regenerating simulation paths is not model learning.
- NBA C: append paired evidence, but W2/W3/calibration fitting only after chronological precommitted evidence gates; no automatic production weight change.
- NHL plugin Poisson, locked Gamma and original native NB2: prediction-only. P4 **separate Track B adaptive Gamma** can increment shape by verified official SOG and exposure rate by independently verified TOI using P4's existing owner function; locked original comparators never change.
- A model update requires a genuine previously unseen official observation since its parent cutoff, authenticated immutable training warehouse rows, owner-specific fitting callback, an explicit numerical validation callback, and a state change. Otherwise `UNCHANGED` or `BLOCKED`, **not** `TRAINED`.
- P0 accepted model hash, parent artifact hash, version, training-manifest SHA, cutoff, code SHA, seed, numerical evidence and registry transition must be frozen together. Failed validation or crash before activation leaves previous version eligible. A later rollback is append-only and version selection is locked as of each new forecast freeze.

## E. Executed mathematical QA, synthetic lifecycle and live state

Detached research notebook: `e023e3da94aa4ffb82e6071ffbb3ee54` (unscheduled). Exact P0 and main registry files staged under `/work/research/p5_isolated_dev/staged_checkout`; tests execute in read-only detached mode, separate from all active collector files.

- Initial P5 test run `c0e1e4a9-f841-4c5c-80f1-9a8a9b5c69ea`: 24/25 PASS; test expected MISS for integer-line actual 0/line 0, which is **PUSH**; corrected test not settlement mathematics.
- Successful P5 `7708658f-d410-44b3-a890-168f5f202f34`: 25/25 PASS, 0 skips, wall 0.9901 s, peak RSS 253,316 KiB.
- Expanded P5 `765dac46-f39f-4c52-a65f-a16f99446e54`: core 25/25 PASS in 1.1614 s; additional 12/12 PASS in 0.0591 s, peak RSS 253,392 KiB. Additional test source SHA256 `eea13a32ee7c7f8daf18cbdc672b35ac146aa5dfa12f7f9e080cd2a725bfbb89`. Includes NHL official played-zero and missing unknown, NBA made threes and coherent combos, 40-date and future-label C fit exclusion, synthetic frozen forecast -> official result -> settlement -> research model v2 -> deterministic subsequent law -> rollback v1.
- Later checksum/idempotence and correction-as-of test additions are a new code revision; their exact run evidence must be cited independently, **not inferred from the prior 37 successes**.
- Deepnote machine observed `CPU (Basic)`: 2 vCPUs, 5 GiB memory, 0 GPUs. P3's separate synthetic original shared-bank 5k vs 20k sensitivity previously reported 53.20s / 228.41s, peak 339,228 / 658,580 KiB; these are P3 measurements, not measurements of P5 scoring.
- Actual P0 read-only inventory run `d8bcadf9-0b28-4a67-8971-bad12fc95d8e`: `STORAGE_ATTESTED_FOR_PROJECT_PATH`; **0** original P0 NBA/NHL forecasts, **0** reconstructed P0 forecasts, 0 integrity rejections; `model_updates=DISABLED`, `automation_changes=false`. These are P0 canonical-store counts, **not** an assertion that all older research archives are empty.
- Upstream November 21 main morning `86414e6f-c763-4a51-a09d-c7e65cbe79c6`: process completed with 0 newly original certified NBA research scores. Existing NHL independent settlement `a00e6767-0006-4980-b2d0-7095ce96b9e1`: `BLOCKED_NO_DAILY_FROZEN_LEDGER`. **No genuine P5 original market settlement or new real model-learning receipt exists.** Daily per-model eligible original training observations are 0 from this P0 inventory, updates 0. Unverified older historical data are not counted as P5 training.

**Exact P0 cross-run durability receipts:** random 4096-byte SHA `21084d9cb869c6105a0d286ea268b2b8e5375af01790e6fec79309cc54cc6692`; original project anchor `adf238bf36bfefce7adb6374321bdb3adba67945c93e7ec32dd89071b34c4a65`; attestation writer `e5fe4929c23f8b7aac9680d59e30083ee891ed46755322fb3e8a4220e7140c13`; independent reader `2ab6fa006b1c18d4c626986d54d089cebf4bf537c887e212318a1b19434bc185`. Source receipt proof **does not establish original forecaster timestamps if the live captures never occurred**. No actual original P5 source/model/forecast/settlement hashes can be reported without a genuine row.

## F. Immutable storage and rollback paths

P0 approved root `/work`, with project-attested alias resolving to `/datasets/_deepnote_work`. P0 record store `/work/research/p0_integrity_store/{sources,features,models,forecasts,quotes,outcomes,settlements,training,experiments}`; records are content SHA-addressed and identity claims are O_EXCL. P0 attestation rejects `/tmp`, nested symlinks, unverified roots and overwritten existing bytes. P5 local research-only **opt-in** namespace: `/work/research/p5_daily/{settlements,observations,versions,transitions}`. P5 detached QA stage: `/work/research/p5_isolated_dev/staged_checkout`. Registry real Deepnote write/independent replay is **not yet release-verified**; the synthetic registry's file-level recovery tests ran in isolated temporary storage. Project cross-run durability proof does not constitute guaranteed backups or indefinite retention.

Rollback: do not delete prior model artifact; append a `ROLLBACK` transition with exact prior version+SHA and select by time. On failed atomic activation, the earlier transition stays active; any orphan blob is quarantined for audit. Forecast IDs and original source/model refs remain immutable. In absence of P6 approval, rollback is simply **do not invoke** P5 in the active morning and leave all existing automations untouched.

## G. Automation dependency and operational release gate

Existing morning settlement task `Automation_12f6ba43eb748191a213917780254329`, NBA source `6afa51eeb1488191956f2d672edf6d33`, NHL SOG `6af480bda1448191b892f43091479f8d`. NFL source task `6afa711c5614819193bcc288c4c741c7` is **outside ownership and unchanged**. No extra ChatGPT automation, GitHub Action, Deepnote schedule or paid dependency has been created. Before release, P6 must verify exact owner notebook pins, actual run/cutoff sources, no duplicate schedule/collector, supported source-listed subset vs unverified participation and the morning settlement ordering. The current manual runner defaults to a **read-only** inventory.

Required operational sequence after P6: P0 storage attestation -> frozen forecast replay -> official original bytes from existing owner -> official outcome vault -> independent identity/finality -> immutable settlement -> CRPS/NLPD/joint/paired score report -> admitted new official observations -> approved owner-specific lightweight update -> independently validated serialized state -> append-only registry transition -> next forecast selects exact state+SHA prior to its freeze. Failures in one sport must not suppress the other. P6 must independently test repeated runs, partial writes/claims, source late arrivals, corrections, wrong player/team/stat, DNP, source tamper, future training, concurrent registry writers and whole bank physics.

## H. P6 verdict matrix, fail-closed

|Component|NBA|NHL SOG|P6 decision|
|---|---|---|---|
|Common P0 attested storage access|PASS engineering read-only|PASS engineering read-only|Independently reverify|
|P0 original pregame source and daily ledger|BLOCKED_BY_SOURCE|BLOCKED_BY_SOURCE|No original P5 rows|
|Complete original forecast distribution|BLOCKED_BY_MODEL|BLOCKED_BY_MODEL|P1–P4 owner integration needed|
|P5 mathematical marginal and contract scoring|PASS synthetic|PASS synthetic|Independent numerical red-team|
|P5 original official final adapter|PASS synthetic|PASS synthetic|Live original event/ID canary pending|
|P5 immutable statistical settlement|PASS synthetic|PASS synthetic|Live original bytes/ledger pending|
|NBA complete-pipeline C and joint witness|ENGINEERING_ONLY; native bridge BLOCKED|Not applicable|No W2/W3 performance promotion|
|Registered native NB2/Poisson C10|Not applicable|PASS rule tests; ORIGINAL PAIR BLOCKED|No confirmatory analysis before 40 original dates|
|As-of training and official revision store|PASS synthetic|PASS synthetic|Live official SHA/exposure needed|
|Owner-specific new model fit|BLOCKED_BY_MODEL|BLOCKED_BY_MODEL|No genuine state change|
|Model registry/rollback/next selection|PASS synthetic|PASS synthetic|P6 Deepnote persistent-write/restore audit required|
|Morning automation activation|BLOCKED_PENDING_P6|BLOCKED_PENDING_P6|No edits|
|Operational genuine pregame->settle->learn|BLOCKED|BLOCKED|NO-GO|
|Production/Tiers/economic edge|NOT AUTHORIZED|NOT AUTHORIZED|NO-GO|

**P6 critical checks:** independently review exact P5 PR commit, compare P0/owner interfaces byte-for-byte, test whole official source and shadow cohort against stamped real original records, run the latest tests as a fresh independent detached QA (including negative control), benchmark CPU/RAM on actual daily denominators, check P0 and P5 logical ID claims under failure, validate official correction precedence, enforce training-data/version cutoff across all model components, ensure C weights use complete matched distributions and date/game blocked uncertainty and never recompute frozen forecasts. Missing native NBA C witnesses, unverified current P1/P2 genuine captures, unexecuted P4 source suite, no original Gamma and no 40-date C10 remain hard blockers.

**No independent release approval is requested by passing synthetic P5 code.** The next bounded integration ticket is a genuine source-qualified P1+P3 NBA or P2+P4 NHL pregame original forecast written into the attested P0 store before its event, then independently recovered and settled after official final. Only after that can P6 verify a true original model-update transition and authorize a schedule pin change.
