# P6 independent NBA/NHL SOG integration release gate — 2026-11-21 (Toronto)

**Disposition: NO-GO for cutover and merge. Research-only QA.** This packet records independent live repository, notebook-run and automation inspection, as well as new adversarial calculations. Neither a synthetic pass nor an implementation-owner statement constitutes original prospective certification. This QA branch does not modify any original collector/model, P0–P5 source code, NFL, legacy 60/40, NUTS pause, Tier or production configuration.

## Source inventory and exact revisions (inspected 2026-11-21)

| Authority | Actual writer / expected consumer | Draft PR / HEAD | Verified state |
|---|---|---|---|
| Common nine record contracts and source identity | P0 v2/p0_integrity/contracts.py; P1–P5 strict readers | #198 c14de84839161f207d6fd7524c18d68b13707365 | 63/63 owner tests and detached cross-run persistence; unmerged |
| Shared source/model/forecast vault | P0 v2/p0_integrity/storage.py; P5 warehouse reader | #198 same | Read-only P0 inventory: 0 original NBA and 0 NHL SOG forecasts |
| Old NBA Phase8C storage gateway | Existing single collector pinned ceddb41e8e13029849ec82ba2b537faab0ee0a24 | proposed bridge #199 99ee844bb2cc860791b32c44077d5e2185fecc4b | Nov21 real run failed DURABLE_STORAGE_NOT_ATTESTED; bridge not integrated |
| NBA source-listed and point-in-time snapshots | Existing WS1 collector invoked by P1 research/nba_p1_original/rolling.py | #200 cf71e6662347755020217c78a04642a5b36ec5a9 | 45 staged tests against earlier commit; zero original prospective model forecasts |
| NHL signed original source, histories, quote bridge | P2 research/p2_nhl_sog/source_pipeline.py (reuse C03, not competing collector) | #201 24b0159682a19d344b0baa6cd1f6e5a24db4802d | 49-suite previous run errored 4; no fresh exact-head PASS; original official canary HTTP error |
| NBA S/O/J complete distribution + P0 freeze | P3 research/nba_p3_frozen; existing accepted WS5 native witness still required | #203 2280c751e4385400f681d19c5acaf6bce09c8423 | synthetic 27/27; J true-original source route blocked |
| NHL Poisson, Gamma–Poisson, NB2 distribution staging | P4 v2/nhl_sog_p4_forecasts.py; native registered NB2 retains original launcher | #202 786f3c900922b1bc8a11de85659bc97150369a4f | independently run 16 tests: 15 pass, 1 ERROR |
| Official NBA FINAL | Existing v2/official_nba_nhl_capture.py parser → P5 official_adapters | #204 c02568c5ea8cd3f7a61508679ea415076a56fb08 | synthetic only for new P5 canonical warehouse |
| Official NHL FINAL | Existing official NHL original result source → P5 official_adapters | #204 same | actual old independent NHL consumer says frozen daily ledger missing |
| P5 frozen forecast warehouse, independent settlement and proper scores | research/p5_daily/warehouse.py, workflow.py, scoring.py | #204 same | synthetic 39/39; genuine canonical original ledger empty |
| NBA C complete pipelines / W0-W4 | research/p5_daily/complete_pipelines.py; S/O/J are connected layers not independent votes | #204 same; native G0/C bridge unmerged | synthetic tests, no qualified comparative forward cohort; W4 remains blocked |
| NHL C10 experiment and native NB2 | locked existing C10/Gamma/C03; P5 matched_native_nhl_pair read-only audit | #204; native launcher SHA 71d70b2ad7287b4876be082d0653e368eef47536 | 40-date registered cohort not reached/verified; no interim winner |
| Daily model updates and registry | P5 registry and explicit optional P3/P4 owner fit callbacks | #204 same | synthetic train->version->rollback tested; NO REAL fitted model update or model publication |
| Existing recurring operations | Existing three ChatGPT automations and distinct original daily NHL collector | live task definitions | no cutover made; NFL untouched |

**Git main at audit:** `912bc7010058092ea735dcda0aa941429194474b`. All six P0–P5 PRs above are DRAFT, OPEN, UNMERGED. P0 is base of P1/P2/P3/P5; P4 is based on older main. Source owner/baseline NBA G1 independent #173 was NO-GO (26 pass, 2 fail, 8 blocked) and is not superseded by owner revisions. GitHub currently reports repository visibility public; no credential/raw private source is added here.

## New independently executable checks

**Exact-head stage:** P3 source HEAD 2280c... file `research/nba_p3_frozen/distributions.py` staged in Deepnote P6 directory; SHA256 `42f6a4727d89b4b26a029edb711d55c920f5ce2b8bf469f7837476b7ab1c41c1`. P5 source HEAD c025... file `research/p5_daily/scoring.py` SHA256 `a32b19afabbb02762e108cf84182722f3fe703fd42c13bf8d91a0ff38f85b6cc`. P4 source HEAD 786f... SHA256 `01e3ed5ab8a854016de70cb4472dce5e17d46e458afffae79047ba885ccf29cf`. No original source collections were modified by staging these audit copies.

**P6 mathematical reference** Deepnote notebook `02c0d511a3494e089691cc45de1ff42c`, run `62e11afc-8863-40c7-85a3-d8e7c7bd9b65`: 17 independently authored tests, **16 PASS, 1 FAIL** in 0.200s unittest / 3.449s subprocess wall. References: SciPy Poisson/NB2/Gamma–Poisson PMF, analytical means/variances, full CRPS via E|X−y|−0.5E|X−X'|, exact 3-way categorical Brier/log loss including integer push, analytic joint Energy Score on 2-particle law, forbidden synthetic quote, randomized PIT fixed seed, NBA same-path combo and clustered game-based counts, native r=4. Receipt path `/work/research/p6_qa_20261121/receipts/8c789bc8d3863a495ff3ad5aa05501284662dacc28d9b59025484de4b79a72b4.json`; SHA256 `8c789bc8d3863a495ff3ad5aa05501284662dacc28d9b59025484de4b79a72b4`.

**P6 P4 exact-head execution** Deepnote notebook `9a23f84be7f646159d3965b379ed069e`, run `488cdd67-b6c7-46b7-a4b0-f6f2665ca7e5`. Independently asserted `/work/v2/nhl_sog_p4_forecasts.py` has the same SHA256 `01e3ed5...` as GitHub staged exact head, then invoked `python -B -m unittest discover -s tests -p test_nhl_sog_p4_forecasts.py -v` in a detached readonly run. **15 PASS, 1 ERROR** in 0.392s test time / 24.122s subprocess wall (startup overhead). The failed case is test_13_full_forecast_freeze_and_restore.

### P6-DEFECT-01 — NHL P4 exact-head regression suite is red

- Owner: P4. Branch: `chatgpt/p4-nhl-sog-model-artifacts-20261121`. Commit: `786f3c900922b1bc8a11de85659bc97150369a4f`.
- Severity: release-blocking QA integration defect, not yet demonstrated model-likelihood error.
- Reproduction: above exact-head P4 test run; test file `tests/test_nhl_sog_p4_forecasts.py` line ~186.
- Observed: `P4Blocked: UNKNOWN_MODEL_KIND` in `freeze_forecast` at `v2/nhl_sog_p4_forecasts.py` line ~336.
- Expected: freeze-and-read-back synthetic Gamma-exposure mixture is accepted and byte-identical on repeated writes.
- Cause evident in code: test passes `kind="gamma_exposure_mixture"`, but production `freeze_forecast` accepts `set(MODELS.values())`; its valid corresponding value is `full_gamma_poisson_exposure`. The production original signed-loop uses accepted value names. Owner must correct the fixture/accepted API naming through a reviewed commit, then run all 16 exact-head tests and the P5 reader bridge. Never silently change the registered Gamma maths.
- Gate impact: P4 engineering FAIL suite; NHL original operational BLOCKED independently.

### P6-DEFECT-02 — C10 date-unit mismatch under Toronto-slate semantics

- Owner: P5 / NHL C10 protocol custodian. Branch: `integration/p5-nba-nhl-daily-settlement-learning-20261121`. Commit: `c02568c5ea8cd3f7a61508679ea415076a56fb08`.
- Severity: HIGH experiment eligibility/denominator risk; not a predictive-score claim.
- Reproduction: `python -B research/p6_audit/test_reference.py` after staging exact P3/P5 source; case `test_c10_utc_date_is_not_toronto_date_probe`.
- Expected under Toronto-slate counting: starts `2026-11-21T23:30:00Z` and `2026-11-22T00:30:00Z` are **one** Toronto date (Nov21), rather than two independent prospective dates.
- Observed: `matched_native_nhl_pair` returns 2, from `event_start_at[:10]` (UTC grouping). The NBA `fit_chronological_weights` similarly uses this date slicing. If the registered date unit is in fact UTC, the owner must record the authoritative ADR and test it against the locked 40-date protocol; otherwise use original qualified `America/Toronto` slate-date identity with DST handling, and recompute eligibility from immutable source receipts without rewriting observations.
- Acceptance: independent red-to-green same-Toronto-different-UTC boundary test, multi-DST calendar test, distinct original verified pairs, and zero C10 look/promotion until protocol resolved. Original experiment is locked; do NOT redesign horizon, primary endpoint or shape parameter.
- Gate impact: P5 C10 engineering FAIL conditional on Toronto semantics / unconditional protocol ambiguity BLOCKED. No rollout.

### P6-DEFECT-03 — NBA original daily worker rejects valid project mount

- Owner: old Phase8C P0 bridge / NBA capture P1 integration. Existing pinned collector SHA `ceddb41e8e13029849ec82ba2b537faab0ee0a24`; bridge draft #199 SHA `99ee844bb2cc860791b32c44077d5e2185fecc4b`.
- Reproduction live: detached Deepnote run `e40fa050-1327-4137-8840-daa37b78f6b2` on Nov21 failed `ValueError: DURABLE_STORAGE_NOT_ATTESTED` in `research/nba_phase8c/daily.py` line 85. Old gate resolves /work into /datasets/_deepnote_work and rejects literal path. Nov19/20 also reportedly failed.
- Expected: P0 verified persistent project path is admitted via immutable cross-run proof, not environment override; existing NBA collector continues when genuine event-relative window and accepted native source exist.
- Acceptance: independent #199 call-site tests against live original Deepnote mount, one REAL later pregame event source+model freeze and separate recovery; expired Nov16–20 pilot never retroactive.
- Gate: NBA operational BLOCKED.

### P6-DEFECT-04 — NHL P2 exact-head source suite lacks successful current receipt

- Owner P2 #201 `24b0159682a19d344b0baa6cd1f6e5a24db4802d`.
- Observed previous independent source suite run `8088b89e-c7ae-4de7-a5cd-1c2c5c2588bb`: 49 tests, four `KeyError: record_sha256` at source_pipeline.py line ~605 from mock source records. Owner patched later; no verified pass against FINAL HEAD. Follow-up detached launches stopped (capacity/rate limit).
- Acceptance: 49 tests PASS at exact HEAD (record test file SHA); separate live signed NHL schedule, BOTH rosters, historic observation receipts, original native player ID, genuine optional two-sided original offer, and P4 import. P2 original live attempt game `2026020361` failed HTTP; preserve failed attempt, never backfill.
- Gate: NHL original-source operational BLOCKED, engineering not independently accepted.

### P6-DEFECT-05 — P5 registry atomic model publication FAILS on actual Deepnote FUSE

- Owner P5 #204, exact commit `c02568c5ea8cd3f7a61508679ea415076a56fb08`, registry file SHA256 `8b648be43303289994cb8602a2bb5cd0588954cb7cffb2f253b50032c9389cb3`.
- Independent detached project-storage run `6386df00-2c83-432e-8848-8d6d382492de` on `9cc31536-93be-44db-bdeb-06fba3f61410`, isolated research-only root `/work/research/p6_qa_20261121/p5_registry_crossrun_synthetic`.
- Reproduction: stage exact GitHub registry source bytes into P6 namespace; call `admit_training_observation` with clearly labeled synthetic P6 NHL SOG played observation and fully chronologically ordered source receipt metadata. This append returned `APPENDED`, observation SHA `46d53bc9862293427909418bc342724a37538e888858392ff46c409c329cbafe`. Call `register_model` for P6 synthetic adaptive Gamma state with a separate validation-passed flag. It raises `ScoreError:ATOMIC_TRANSITION_LINK_UNSUPPORTED` in `_write_transition_once` at `os.link(temp,path,follow_symlinks=False)`.
- Expected: a verified, atomic, no-clobber durable model registry transition that survives a later independent Deepnote run; crash before activation must preserve previous eligible version.
- Observed: **no new research model can be activated** on the actual tested project filesystem with this transition mechanism. Failure is correctly visible, not swallowed. This is a component engineering **FAIL**, not merely missing real data. The probe does not certify real official source or learning.
- Mandatory fix by P5 owner: choose an actually supported crash-consistent immutable publication protocol; demonstrate no overwrite/concurrent-writer corruption, parent-version CAS/recovery and previous-eligible-version survival; rerun live Deepnote writer/readback, interrupted write, independent rollback, and fresh subsequent-game as-of selection. Do not weaken P0 O_EXCL/receipt semantics or use environment bypass. Gate: **NO CUTOVER**.

## Persistent storage and chronology

P0 project root `/work` resolves to `/datasets/_deepnote_work` in connected Deepnote project `9cc31536-93be-44db-bdeb-06fba3f61410`. Writer detached run `207a1a65-1c3b-4d9f-957f-c4568a863ba1`, independent later reader run `d446c692-604d-4c2e-ae14-357dd96278e2`, 4096 bytes content SHA256 `21084d9cb869c6105a0d286ea268b2b8e5375af01790e6fec79309cc54cc6692`, anchor SHA256 `adf238bf36bfefce7adb6374321bdb3adba67945c93e7ec32dd89071b34c4a65`. Writer receipt SHA `e5fe4929c23f8b7aac9680d59e30083ee891ed46755322fb3e8a4220e7140c13`, reader SHA `2ab6fa006b1c18d4c626986d54d089cebf4bf537c887e212318a1b19434bc185`. Independently read later receipt: content/anchor SHA verified; /tmp, invalid mount/symlink/overwrite rejected. P0 unit suite 63/63 owner-authored verified from run `b57d7efa-0972-4bb9-b615-64e299232951`. **Cross-run project path evidence PASS for the P0-tested path**; independent P5 model-registry publication is now **FAIL** on Deepnote FUSE (run 6386df00-2c83-432e-8848-8d6d382492de), with `ATOMIC_TRANSITION_LINK_UNSUPPORTED`. Concurrent restart/rollback remains unverified. No vendor backup/indefinite retention guarantee.

Chronology admitted for *no genuine target forecast* in canonical P0 warehouse. All source/freeze/model/quote/final/settlement/learning timeline rows for genuine new pipeline are therefore **NOT AVAILABLE**; absolute chronology tests exist against synthetic owner fixtures, cannot prove original certification. P5 current source-read inventory Deepnote run `d8bcadf9-0b28-4a67-8971-bad12fc95d8e`: 0 original original NBA/NHL forecasts, no real settlement nor model update. P3 synthetic 27/27 at run `3825c447-47dc-4d0c-a018-e995c7e2a180`; 5000 vs 20000 MC precision study was synthetic (53.1982s / 228.4138s, peak 339228 / 658580 KiB); simulation paths are not games. P5 owner synthetic 26+13=39/39 at run `d6ce795d-f817-4f30-9404-fe6d1e0ffb5d` with peak ~253316 KiB; this is not a real prospective lifecycle. P1 actual 45/45 tests at staging SHA 1dfca36169fdfb43f2c9939e06a72708e91067ed, distinct from final PR200 head: require exact-head consistency proof.

## Fault-injection coverage — independent release criteria

Statuses are **independently reproduced**, **owner fixture only**, or **not done**, never silently inferred from successful code execution.

| # | Injection | Current evidence / gate |
|---:|---|---|
| 1 | Deepnote worker termination | Existing interrupted/stopped runs observed; restart+resume exact model and immutable receipt NOT done |
| 2 | Missing durable storage | Actual NBA old-pin rejection observed; P0 synthetic invalid mount PASS; integrated recovery BLOCKED |
| 3 | Corrupted source bytes | P0 owner fixture test; canonical genuine archive mutation NOT done |
| 4 | Invalid C03 signature | P2 owner synthetic suite failed prior run; exact-head signed evidence BLOCKED |
| 5 | Missing NBA roster evidence | P1 synthetic abstention; original player eligibility BLOCKED |
| 6 | Missing original Gamma artifact | Genuine NHL NB2 abstention `NO_ORIGINAL_GAMMA_GENERATOR_YET` observed |
| 7 | Missing original sportsbook quote | Original NHL comparison abstention; no fabricated forecast |
| 8 | Expired deadline | Owner timestamp fixtures, genuine next-game fallback NOT demonstrated |
| 9 | Forecast after tipoff | P0/P3 owner fail-closed fixture; no genuine missed-run fallback |
| 10 | Duplicate forecast ID | P0 O_EXCL/ID fixture pass; cross-detached competing writers NOT fully exercised |
| 11 | Partial forecast ledger write | P0 preserves incomplete claim; tested recovery of canonical current ledger NOT done |
| 12 | Missing official FINAL | P5 synthetic pending; no genuine canonical target forecast |
| 13 | Incorrect DNP settlement | P5 owner fixtures + P6 opportunity/score reference; full original game crosswalk blocked |
| 14 | Corrupted model artifact | P0/P3 synthetic reject; full live registered model byte proof blocked |
| 15 | Failed model training update | P5 synthetic unchanged/blocked validation; genuine update blocked |
| 16 | Failed registry publication | **INDEPENDENTLY REPRODUCED FAIL** actual Deepnote FUSE hardlink unsupported; transition not published; separate restart check pending |
| 17 | Repeated morning run | Legacy runs observed, canonical P5 idempotent dual-run recovery NOT done |
| 18 | Simultaneous source workers | P0/P1 tests; real overlapping Deepnote writer race NOT done |
| 19 | Concurrent registry readers/writers | P5 fcntl fixture only; same physical mounted registry race NOT done |
| 20 | One sport fails, other succeeds | Independent sport gates available; integrated partial-success isolation NOT done |
| 21 | Failed external GitHub publication | No fault injected; archive/publisher recovery NOT done |
| 22 | Rollback older research model | P5 synthetic rollback passes; persistent cross-run rollback and new next-slate selection NOT done |

## Automated operations — actual state and ownership

| Task | State Nov21 | Existing schedule | Observed role and blockers |
|---|---|---|---|
| NBA capture `6afa51eeb1488191956f2d672edf6d33` | DISABLED | `DTSTART:20261116T180500;FREQ=DAILY;COUNT=6` — expired limited pilot | Old Phase8C pin `ceddb41...`, last run 2026-11-21 failed storage attestation; never amend old evidence to pass |
| NHL SOG shadow `6af480bda1448191b892f43091479f8d` | ENABLED | 17:30 America/Toronto DAILY | NB2 native/settlement/C10 research work, NOT sole original Gamma collector; no original Gamma, 0 native NB2 forecasts; late consumer blocked no daily ledger. Nov21 Gamma/C10 retries were rate-limited |
| Morning `Automation_12f6ba43eb748191a213917780254329` | ENABLED | 06:00 America/Toronto DAILY | Legacy morning Deepnote run `86414e6f-c763-4a51-a09d-c7e65cbe79c6` SUCCESS but 0 original source forecast bundles, 0 scored contract rows for Nov20; NHL daily consumer blocked; P5 not integrated |

**Note:** This inventory intentionally does not modify any task. The NHL task ID is the one given in the project instructions; verify exact name/ID from the task source before pasting a replacement. Existing original 16:45 Gamma provider capture and 17:30 NB2 shadow/consumer are separate and must not be replaced by an overlapping new source writer. NFL collector/task ownership untouched.

## Readiness matrix (separate engineering, prospective, daily learning)

| Component | Engineering | Genuine original pregame | Daily learning |
|---|---|---|---|
| P0 data/storage contract | PARTIAL PASS: common contracts, cross-run store | BLOCKED: no complete certified forecast | BLOCKED |
| NBA P1 source/feature | CONDITIONAL synthetic | BLOCKED: old pin, native WS1/capture and participation | BLOCKED |
| NBA S Poisson/NB2 | INDEPENDENT reference PASS on tested regimes; no full native G1 acceptance | BLOCKED | PERIODIC_FULL_REFIT_ONLY, no approved daily S fitting |
| NBA O participation/opportunity | OWNER synthetic only, G1 no-go | BLOCKED (unknown p_play/roster) | prediction-only |
| NBA J shared scenarios | OWNER synthetic only, C native scenario witness missing | BLOCKED | prediction-only |
| NBA C pipelines/weights | OWNER synthetic W0–W3 tests, no forward matched labels; W4 disabled | BLOCKED | no weight learning authorization |
| NHL P2 original sources | FAIL prior exact run; latest head untested | BLOCKED no full authentic signed source | BLOCKED |
| NHL P4 Poisson | 15/16 shared suite pass; failing freeze fixture | BLOCKED no genuine admitted frozen ledger | prediction-only |
| NHL P4 Gamma–Poisson | 15/16 shared suite pass; failing freeze fixture | BLOCKED original Gamma artifact / P0 ingest | locked original prediction-only |
| NHL native NB2 r=4 | Independent fixed-shape reference PASS; source-specific eligibility unproven | BLOCKED no original Gamma/control/offer | locked, prediction-only |
| NHL C10 registered comparison | Date convention defect/ambiguity; locked horizon retained | BLOCKED no complete native matched dates | no premature outcome-based update |
| P5 official/settlement | Owner synthetic 39/39; no live canonical source to settle | BLOCKED | BLOCKED |
| P5 registry and adaptive Track B | **FAIL** actual project FUSE atomic transition; owner synthetic rollback passes only in other environment | BLOCKED | **FAIL** publication unavailable even for synthetic validated state; no real SOG+TOI |
| Existing automation cutover | PENDING; no attempted mutation | NOT ACTIVATED | NOT ACTIVATED |

## True operational evidence as of audit

- NBA scheduled/live P1 original prospective model forecasts in canonical P0 warehouse: **0 verified**. No original S/O/J frozen scoreable distributions; 0 canonical P5 settlements; 0 authentic new model versions.
- NHL canonical P0 new original SOG forecasts: **0 verified**; NHL latest independent legacy daily consumer output `BLOCKED_NO_DAILY_FROZEN_LEDGER`. Native original NB2 forecast new count: **0**; original Gamma model-source blocker. A genuine C10 distinct-date count is unavailable, not assumed zero progress for every separate legacy archive.
- 2026-11-21 morning production legacy notebook itself succeeded but returned 0 source forecast bundles, 0 original forecasts, 0 settled rows in its contract audit for Nov20. Do not confuse successful notebook status with successful forecasting settlement.
- Real quote-qualified original P0 NHL and NBA counts: **0 verified**; do not infer any p_market, EV or betting edge.
- No real trained NBA/NHL P5 model version; synthetic training proves only interface functions, not efficacy or future quality.
- No actual timing/CPU/RAM budget measured for a complete genuine P0→P5 event lifecycle. Component synthetic figures above are not full workflow cost estimates.
- C10 interim paired metrics/p-values were deliberately not inspected; no NUTS retraining, trusted tiers or production weight changes authorized.

## Next required work — in dependency order

1. P5 own fix/ADR for immutable Toronto-vs-UTC C10/date cohort semantics; execute independent boundary and DST acceptance. Preserve locked original 40-date EB-001 and shape-4 NB2.
2. P4 owner fix its invalid test_13 kind name without changing the registered model likelihood; rerun 16/16 against new exact SHA. Independently verify exact source/forecaster/P0 ledger bridge.
3. P2 owner rerun 49/49 against final SHA and capture future authenticated official NHL schedule, both lineups, complete signed SOG/TOI histories and original Gamma control. Preserve missing quote as separately abstained distribution-only cohort; do not auto-enroll quote-free rows in C10.
4. P0/P1 owner integrate draft #198 and #199 through reviewed branch, fix the live Phase8C storage path and pin; connect one WS1 source writer, source-listed subset eligibility/unknown participation and P3 model admission. Retain expired Nov16–20 capture record.
5. P3 owner complete original native G0/C witness bridge, S/O/J source/model/physical-law acceptance, team-minute conservation (240 regulation, +25 per 5-minute OT per team) and same-path PR/PA/RA/PRA, without synthetic substitute.
6. P5 owner independently confirm full P0/P4/P3 original SHA transport, output official FINAL settlement, DNP-vs-played-zero, multi-quote isolation, push/void and corrected version append. **Repair verified actual FUSE `ATOMIC_TRANSITION_LINK_UNSUPPORTED`** before further registry acceptance; cross-detached test supported publication, concurrent writers, interruption/rollback.
7. Run P6 new 22-case actual integrated fault matrix and synthetic lifecycle on accepted unified SHA. Owner claims/tests are not a substitute for source-byte independent verification.
8. Obtain separate NBA genuine pregame → frozen forecast and NHL SOG genuine pregame → frozen forecast canaries. After FINAL, replay bytes by independent morning consumer → settle, score and (when approved fitting method and training eligibility exist) version research adaptive model, then verify subsequent-game as-of selection.
9. Only after separate gates pass revise the **existing** NBA, NHL and morning task prompt/pins atomically, keep prior prompts for rollback; do not add competing collectors. Verify actual task returned updated definition and next run receipt. Do not alter 60/40, NFL, locked C10, NUTS, production or Tier policy.

## Rollback and safe freeze

Since no P0–P5 cutover or merge is made, rollback is **preserve existing automation definitions and pins**; preserve the legacy 06:00 morning and 17:30 NHL shadow executions. Keep new QA branch draft. For any future staged cutover, snapshot task text/schedule/old notebook IDs and repo pins before changing; verify original forecast ledgers unmodified; upon fault, restore prior task prompt and prior model registry validation pointer through append-only rollback, never overwrite source/forecast/outcome/settlement receipts.

**Final P6 disposition: NO-GO / insufficient independently reproduced complete original lifecycle.** Engineering is partially demonstrable; neither sport has genuine prospective operational readiness on the new canonical P0–P5 path, and daily continuous research learning remains BLOCKED.
