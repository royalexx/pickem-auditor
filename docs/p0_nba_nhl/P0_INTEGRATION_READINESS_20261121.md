# Pick'em Auditor V2.5 — P0 NBA/NHL SOG common persistence and integrity handoff

Date: 2026-11-21. Project: Deepnote 9cc31536-93be-44db-bdeb-06fba3f61410.  
Engineering branch: integration/p0-nba-nhl-contract-storage-20261121, based on main 912bc7010058092ea735dcda0aa941429194474b.  
Status: COMMON CONTRACT TESTED; DURABLE PROJECT PATH VERIFIED; FORECAST AND SPORT RELEASE BLOCKED.  
**Do not merge, promote, publish Tier 1/2, retrain NUTS, or change any collector/automation merely because the P0 tests pass.**

## Governing evidence

- Master: PA-V25-MASTER-2026-11-09, v1.1 (November 10 amendment). Original evidence and source availability are prerequisites; model accuracy and economic edge are separate downstream decisions.
- NBA G0: reviewed implementation 59d28dc23be97de2a6a82d22be8338151e31f5b6 (PR157); independent acceptance publication 269efb4050b35368a2642face3a846e09422387a (PR161); receipt SHA a90dbe624b44013d6eaf03163726fcfe1cd9f7055b2d657a7d3fed100d3f519d. G0 PASS is exact-SHA authorization for engineering only.
- NBA G1 independent P6 NO-GO: 26 PASS, 2 FAIL, 8 BLOCKED, audit PR173 SHA b7ca2899ab8d902cda62bfb802ab74dcb5598a30. Later repair/feature PRs remain outside that signoff.
- NBA P1/P2/P3/P4/P5 exact owner SHA/PR: P1 50d2b3874c7c14c9b73bdf13e441957986b88acd (#167); S fe46965394ea0f48ef5e9da501ec8ca9e441ce47 (#165); O eb0882b5011f2004c5eaf27cccfdc6297704f261 (#166); J 865bdb8f4770ac28262e49c3b4901cf1d72a22fb (#164); C cb3ff8279bc7f4cc7b86a519a1e386ddbe37ae93 (#163).
- November 19 source_listed_subset amendment: PR186 SHA 3e293c37f25690a6b33d6c7c9776245bf4a7f3ff, profile file SHA a44dc6fe388cfa089577ff5c2eacb3f0437fe015, ADR SHA 535712a1d9261b627aa988868f60ab7ab5a21a5f. Scoped P1 acceptance PR187 SHA 33842b96093a453e5bdeb49dacc64986e27d5b37, 36 retained candidates, 26 conditional requests, 10 abstentions, **zero model forecasts**. Full-roster gates remain historical blockers but are superseded FOR THIS NARROW PROFILE, never retroactively passed.
- NBA subsequent unmerged research chain PR188–PR197: do not silently combine or promote independent S/O/J/C layers.
- NHL original C03/Poisson/Gamma–Poisson/NB2/C10 controls remain separate. Daily signed-source/settlement repair PR183 SHA 4ba7eef27cc2f29dc18ffd5d0b7bbef1e3af4183 unmerged. Main C10 fixed-horizon stress document declares inferential confirmation blocked; 40 prospective dates by 2027-01-31 is only a planned horizon.
- Legacy 60/40, Engine A/B, Bayesian A/B, NUTS, original forecasts, training history and posteriors remain frozen. Main .training-control/PAUSED.json SHA c98a754be159c944fb72a64530c6629d87c3bd59 requires explicit approval to restart.

## Actual storage proof

Deepnote logical writable /work resolves to /datasets/_deepnote_work. The November 20 NBA worker pinned at ceddb41e8e13029849ec82ba2b537faab0ee0a24 incorrectly compares Path('/work').resolve() against the literal /work; it raises DURABLE_STORAGE_NOT_ATTESTED before capturing. November 19 and November 20 detached runs reproduce the same failure. Do not use NBA_PILOT_DURABLE_STORAGE_ATTESTED=1 as a bypass.

Independent writer notebook 73767f33b6dc4e8f9fbfc9e3a09ecf89, detached run 207a1a65-1c3b-4d9f-957f-c4568a863ba1, wrote 4096 random bytes and fsynced. Independent reader notebook 121795447dec4a65a8b0789e2d26c51c, successful detached run d446c692-604d-4c2e-ae14-357dd96278e2, reread bytes and a pre-existing project anchor. Both receipts were retrieved again via connected Deepnote API:

- Random byte SHA256: 21084d9cb869c6105a0d286ea268b2b8e5375af01790e6fec79309cc54cc6692
- November 15 project anchor SHA256: adf238bf36bfefce7adb6374321bdb3adba67945c93e7ec32dd89071b34c4a65
- First-run receipt SHA256: e5fe4929c23f8b7aac9680d59e30083ee891ed46755322fb3e8a4220e7140c13
- Reader receipt SHA256: 2ab6fa006b1c18d4c626986d54d089cebf4bf537c887e212318a1b19434bc185
- Persistent project files: research/p0_integration_integrity/probe_20261121/first_run_receipt.json and second_run_verification.json
- Rejected: /tmp, unapproved mounts, outer and nested symlinks, overwrite attempts.
- Mount st_dev changed between detached namespaces: not a stable project identifier. Content SHA, project-specific preexisting anchor, approved logical path and provenance are required instead.
- Independent smoke run 069f782b-3c6b-4108-b349-6b6397b9f935 passed nine-schema import and cross-run attestation.
- Latest adversarial run 2df6d21f-5b20-4e14-b05f-d2bdc04a94f2: 53/53 PASS, zero skips/errors. Includes actual project append-once, idempotent readback, conflicting same-ID rejection and no-clobber.

The tested path is persistent across these runs. This is NOT a Deepnote backup, disaster-recovery or indefinite-retention SLA. No live collector pin was changed.

## The nine common contracts

All records have record_type, schema_version PA-P0/1, exact required fields, timezone-aware UTC, deterministic JSON SHA and no unknown fields.

| Kind | Authority and admission |
| --- | --- |
| SourceReceipt | Original source ID/kind, first defensible accessibility or collector possession timestamp, observed timestamp, original byte SHA, relative durable original path |
| PregameFeatureSnapshot | Game/team/player/stat/period, input_freeze_at, original source IDs, feature hash, explicit ORIGINAL or RECONSTRUCTED; same-game final statistics forbidden |
| ModelArtifact | Model ID/version, code SHA, raw artifact path and SHA, training-data SHA, actual training cutoff, creation time |
| ForecastSnapshot | Game/player/team/stat/period, freeze/forecast/event clock, source/model/input/output SHA, seed, distribution, uncertainty, abstention, admission class and optional exact quote |
| MarketQuote | Real or synthetic quote identity, original book/line/side/terms, source SHA, quote timestamp, rejected/accepted status; naked line never yields market probability |
| OutcomeRecord | Official source receipt/hash, player/game/stat identity, FINAL/PENDING/CORRECTED and PLAYED/DNP/UNKNOWN separate from numeric zero |
| SettlementRecord | Original official source bytes independently reverified, disposition, forecast/outcome/contract identity, settlement version and immutable supersedes |
| TrainingUpdateReceipt | Source + accepted settlement linkage, cutoff, prior/new model state hash and update mode; research only |
| ExperimentManifest | Frozen research hypothesis, cohort, controls, primary score, code SHA, precommitted cutoffs, evidence and research-only approval |

Canonical strict ordering:

    source_available_at <= input_freeze_at <= forecast_at < event_start_at
    model_training_cutoff_at <= input_freeze_at
    quote_timestamp <= input_freeze_at <= forecast_at (if B includes quote)
    official_result_available_at <= settlement_at
    settlement_at <= training_observation_cutoff_at <= training_update_at

A = authentic original, market-independent **statistic distribution research**, no quote required. B = same genuine pregame distribution plus actual original sportsbook quote/contract and exact source/line/side/terms; missing odds still block p_market and EV, not A. C = explicitly RETROSPECTIVE reconstructed historical features, never originally captured pregame evidence. An unsupported model or unverified participation causes per-row abstention, not fabricated probabilities. Existing source-listed subset remains per-player conditional-on-participation or abstention; no full-team conservation when roster eligibility is unknown.

API: v2.p0_integrity.contracts.record, validate_record, admit_forecast, admit_settlement, admit_training_update, reject_duplicate_records; storage.attest_project_storage, append_immutable, verify_immutable_record; compat.legacy_source_receipt, legacy_market_quote, legacy_forecast_reference, nba_pregame_feature_adapter. Adapters are deliberate restrictive bridges; some native producer formats still need mapped fields. No universal old historical certification is asserted.

## Ownership: one producer, separate consumers

| Data | Existing authority / producer | Consuming stage |
| --- | --- | --- |
| NBA schedule/events | ESPN original NBA pilot + source-listed P1 event identity (only approved narrow profile) | NBA P1 -> O/S/J + original settle |
| NHL events/schedule | C03 source-signed current schedule and NHL official event corroboration | NHL SOG quote binding + independent final settle |
| NBA pregame player/team | WS1/P1 original source-listed subset, including all rejects, unknowns and duplicate candidates | Immutable feature contract -> S/O/J |
| NHL pregame player/team | C03 original signed provider bytes, NHL official roster/profile/history | Existing Poisson/Gamma/NB2 source gates |
| Sportsbook quotes | Existing PropLine/C03 source collector; other genuine NBA source/offer capture only when actually available | B market quote admission, never an independent P0 collector |
| Historical stats | NBA ESPN WS1/P1, NHL signed official game logs and final gamecenter witness | Strict as-of feature producer; outcomes isolated |
| Pregame features | One canonical NBA P1 producer, one existing NHL source-native feature route | Shared feature receipt checker |
| Model artifacts | NBA original S/O/J research heads, NHL locked Poisson/Gamma/NB2 models | SHA-bound model artifact validator |
| Frozen forecasts | Existing ORIGINAL NBA/NHL producers ONLY | Common forecast vault, next-day consumer |
| Official outcomes | Existing independent ESPN NBA / official NHL FINAL feeds | Outcome verifier and settlement |
| Settlement records | Main morning task; NHL SOG independent postfreeze consumer | Research score history |
| Daily training state | Existing paused/model registry, no new fit trigger | TrainingUpdateReceipt only after admitted settlement |
| Calibration/evaluation history | NBA C complete-pipeline comparisons; NHL locked C10 and paired controls | Experiment manifest + immutable score ledger |

S, O and J are interconnected layers, not independent model votes. C compares COMPLETE valid pipelines. NHL SOG keeps its original Poisson, Gamma–Poisson, fixed-shape NB2 and 40-date C10 comparison unchanged. Preserve legacy reference and existing report columns without altering production weights.

## Daily graph

1. Existing owner receives source schedule/rosters/official historical observations and authentic offered quotes.
2. Source receipt is archived as immutable original bytes with first-known actual availability/possession; retain every rejected/unmatched candidate.
3. Existing per-sport pregame feature producer freezes independent player/stat/event inputs; no actual target minutes, TOI, usage, game outcome or future source.
4. Existing model S/O/J or NHL control is loaded with original artifact SHA and earlier training cutoff. Unknown eligibility or missing source means abstain; NO model fabrication.
5. One frozen A distribution or B exact-quote distribution snapshot is append-only committed before event start. Versioned later news produces a new forecast, never mutates old.
6. After official FINAL, existing independent outcome producer yields source-byte verified official stats, DNP and correction states. Settlement is a NEW append-only version; authentic book-specific void terms required.
7. After accepted prior settlements, C/NHL C10 research scoring and optional cheap TrainingUpdateReceipt proceed. No heavy NUTS, no Tier 1/2, no production reweight.

## Retention / write policy

- Every raw original response, failed attempt, approved/rejected offer, named source, candidate, abstention, forecast, model, settled outcome, later correction, baseline, training pause marker and C10 trial stays immutable; corrections use distinct IDs and supersession links.
- New opt-in root: /work/research/p0_integrity_store/{sources,features,models,forecasts,quotes,outcomes,settlements,training,experiments}. Content-addressed SHA filenames, no symlink, O_EXCL and fsync. Logical ID SHA claim prevents overwrite or conflicting reuse; identical bytes return IDEMPOTENT_EXISTING. A partial write is a FAILED recovery case, never silently deleted.
- Maintain accepted and rejected/unknown/missing/duplicate counts. Do not rewrite source receipts or postdate historical features to cure old certification.
- Keep original large data in approved project storage; preserve small non-secret manifests/hashes in repo. Repo privacy claim requires separate verification because the connector currently reports visibility public.
- Keep research archives unless separately approved retention policy exists; cross-run persistence does not establish guaranteed indefinite vendor backup.

## Automation ownership and schedule, verified November 21

| ID | State | Execution owner |
| --- | --- | --- |
| Automation_12f6ba43eb748191a213917780254329 | ENABLED daily 06:00; last run 2026-11-21T11:03Z | ONE original morning settlement notebook 932674d66d4543c6b10ff2e2c0a4df9c |
| 6afa51eeb1488191956f2d672edf6d33 | ENABLED finite daily DTSTART 20261116T180500, COUNT=6; last Nov20 23:03Z | ONE NBA original source pilot, notebook 84e819fd46d24a6e8eb1bfa87c390b23; pinned failing old guard |
| 6af480bda1448191b892f43091479f8d | ENABLED daily 17:30 America/Toronto | NHL SOG NB2 follow-on, independent Gamma validation/C10; no duplicate source capture |
| Automation_a72c5bb65dfc8191afce31c0c58aa16d | DISABLED | Old standalone NHL Gamma original collector; remain disabled |
| Automation_4f26c27ac4e481918b1b54d38c6e6e93 | DISABLED | Old automatic afternoon publication; remain disabled |
| 6afa51fe96148191a6317640a913cf2c | DISABLED | Old redundant NBA B exact-window capture |
| 6afa711c5614819193bcc288c4c741c7 | ENABLED | NFL ONLY, out of scope; not modified |

Notebook editor timestamps: NBA pilot 2026-11-16T01:14:16.504Z; NHL NB2 2026-11-14T21:07:16.320Z; Gamma validator 2026-11-13T18:54:15.570Z; morning 2026-11-16T03:06:29.109Z. Editor updatedAt is not a cryptographic notebook revision SHA. NBA original runner remains exactly pinned until separately reviewed bridge and update.

## Named blockers / release decision

| Stage | NBA | NHL SOG |
| --- | --- | --- |
| Main original capture | BLOCKED: old pinned runner resolves /work alias then rejects it; 10 November pilot slots recorded NO_GENUINE_PREGAME_CAPTURE | BLOCKED on November 20: no complete original afternoon source freeze; PR183 repair unmerged |
| Sources and per-player scope | November19 narrowed P1 engineering accepted, actual original/source/model readiness still per player | Real quote/original signed peer history/current official roster may be missing |
| Forecast model | S/O/J/C G1 independent NO-GO; later research branches do not override | Gamma/Poisson/NB2 research controls, zero new original NB2 on Nov20 |
| Frozen pregame distributions | No valid November 16–20 pilot forecasts | Missing NHL daily frozen ledger in Nov21 settlement |
| Official settlement | Nov21 morning research completed but NBA 10 original slots had nothing to settle | Nov21 independent NHL consumer succeeded as process, BLOCKED_NO_DAILY_FROZEN_LEDGER |
| C evaluation / retraining | Not enough admitted real pregame model + outcome pairs for promotion; no new training authority | C10 40-date primary still underpowered/blocked; no interim tuning |
| Overall operational gate | BLOCKED | BLOCKED |

Nov21 morning main Deepnote run 86414e6f-c763-4a51-a09d-c7e65cbe79c6 succeeded at process level and reported NBA F_model_scores=0 and slot_states NO_GENUINE_PREGAME_CAPTURE=10. NHL independent settlement run a00e6767-0006-4980-b2d0-7095ce96b9e1 succeeded as process with BLOCKED_NO_DAILY_FROZEN_LEDGER. Do not infer success of forecast certification from process success.

## Test and rollback

Research-only test: python -m unittest discover -s tests -p 'test_p0_nba_nhl_integrity.py' -v  
Deepnote tested: PYTHONPATH=/work python -m unittest discover -s /work/tests -p 'test_p0_nba_nhl_integrity.py' -v

Actual detached result: 53/53 PASS, no skip, with cross-run project proof and durable append-only ID canary. Tests prove gateway behavior on synthetic fixtures, not currently deployed owner pipelines or scientific accuracy.

GATE: P0 common-contract ENGINEERING TESTED / durable path VERIFIED; **global P0 READY-FOR-ACTUAL-PREGAME-CANARY ONLY**, no operational release. The pinned existing NBA collector must receive a narrowly reviewed attestation call-site fix, the task pin must be separately authorized, and a genuine next pregame event must produce immutable forecast/official settlement to reach operational readiness. NHL original source/roster/archive source coverage and settled cohort must separately pass without altering locked NB2/Gamma/C10 protocols. Independent external review of the combined native producers is still pending. Keep all existing automation state, production weights, past failed receipts, NUTS pause and NFL unchanged.

Rollback: do not merge draft PR; or revert new optional gateway and reviewed bridge separately, preserving original SHA receipts and source files. No old forecast rewrite, new collector, unapproved nightly fit, or Tier publication.
