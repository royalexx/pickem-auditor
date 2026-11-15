# NFL Sunday November 15, 2026 — Workstream 3 research review

Status: **lower-information O1–O5 prototypes implemented and locally tested; shadow-only; real-contract execution blocked**. No promotion, Tier, production blend change, competing source collection, expensive training or scheduling occurred.

Governing: `PA-V25-MASTER-2026-11-09 / v1.1`. Bounded opportunity-research authorization comes from the user's Workstream 3 request. This does not close the master plan's independent Phase 1.5 investment or prospective certification gates.

## Prior research verified

The saved Deepnote audit run `e8792910-bfbd-400e-8f65-f4fa8d346c85` completed successfully on November 12. Its outputs independently reconciled 175 saved weekly score files, 407,476 paired synthetic contracts and final report SHA-256 `b18b2aaa42cd477588e053d09fe0ec4afa712cb100f8189c2e148cd63f17be04`. This session inspected that existing audit; it did not rerun the full decade.

| Model | Paired historical Brier | Difference versus V3 |
|---|---:|---:|
| V3 | 0.2352119701576855 | 0 |
| V4 | 0.23507764618094637 | -0.00013432397673912577 |
| V4.1 | 0.235086272259964 | -0.00012569789772148843 |
| V5.6 | 0.24293002704621522 | +0.007718056888529723 |

V5.6 lost on Brier in 170 of 175 weeks; its 66,994 selections at 80%+ stated mean confidence 85.91% but hit 72.39%. Opportunity conservation alone did not ensure predictive quality. The V3 report documents 556,094 original synthetic offers, 410,807 official observation matches and 407,476 paired scores. V3's small decade improvement over V2 weakened over time; the original V3 ridge plus calibrated V2 blend is not a purely independent game-volume component.

These results are **retrospective, synthetic-line, development-exposed and availability-censored**, not independent prospective market validation. Mixed-unit aggregate CRPS must not support market comparisons or promotion. Original archived pregame starters were not authenticated by the decade replay.

V4's old share distribution `Beta(12+35s,12+35(1-s))` has mean 0.766949 at s=0.95. V4.1's `Beta(1+60s,1+60(1-s))` improves that to 0.935484. O3 separately tests the mean-preserving `Beta(60s,60(1-s))` with mean 0.95. This numerical correction is not evidence of prospective accuracy.

The existing tackles source and challenger were inspected. `scripts/population_nfl.py` requires `def_tackles_solo + def_tackles_with_assist + def_tackle_assists`; the new O4 requires every component and rejects fractional counts. The existing snap-share challenger uses prior-only share/rate decomposition, archived teammate-status requirements, retrospective +18-hour source timing and a fixed 65-play research control. Those source-timing approximations and synthetic lines cannot certify Sunday's inputs.

The Fable and Carbon original review documents were not found in the inspected repository documents or Deepnote searches. Their concerns stated in the user's request were applied: role-dependent uncertainty, position pooling, sample-depth disclosure, explicit DNP/unknown states and no availability inference from absent statistics. No claim is made that their original full reviews were inspected.

## Implemented scope

| ID | Version | Implemented behavior | Remaining scope |
|---|---|---|---|
| O1 | context-volume-v1 | Prior offense/opponent play and pass tendencies, shared tempo and opposite script uncertainty, plays/pass/rush/sacks distributions, historical pace when observed | Lower-information V3 adaptation; no fitted scoring margin, timestamped spread/total/weather layer, or original V3 ridge/blend reproduction |
| O2 | position-usage-v1 | Position-pooled shares, residual-bucket finite allocation, route/TPRR priors when available, targets/catches and signed conditional yards, carry competition | Personnel-package route accounting and richer tracking; receiving conversion is marginal relative to QB completions |
| O3 | qb-mean-preserving-v1 | Source-identified starter-only eligibility, separate starter probability, corrected share, attempts/completions/passing yards and shared-pool QB carries/rushing yards | Designed runs versus scrambles and pass depth unavailable; no backup full-starter forecast |
| O4 | defensive-components-v1 | Opponent play/mix forecast, last-two-game defensive share, position-shrunk three-component credit distribution | Player marginal, pooled run/pass involvement, no joint personnel/tackle budget or special-teams credit model |
| O5 | role-mixture-v1 | Reduced/normal/expanded offensive target/carry shares and finite reallocation; matched stable-role sensitivity diagnostics | Frozen sensitivity weights, not learned transitions; QB passing and defensive role mixtures not implemented |

Full distributions and workload summaries exist only for synthetic fixtures. No real team/game volume or player workload has been fabricated. Each model's exact algorithm, assumptions, CLI, extended input schema and limits are documented in `research/nfl_opportunity_20261115/README.md`.

## Original Sunday contracts and execution

Workstream 1's successful run `cd6e5a7d-bf05-490a-beb2-d0c2c3a3876e` reported 12 source-verified scheduled games and 1,845 original quote contracts in its initial capture. That version reported zero source-certified quotes because all had `EVENT_IDENTITY_UNVERIFIABLE`. Workstream 1 subsequently added an independent roster/depth identity repair on its own branch; this report pins the original capture and does not assume any later repair is certified.

Original capture: `source_control/captures/20ed83fd40787cccc38a242a8698f0a4e09aaaa54f261b923c8a5f4aa232ed10.json`; file SHA-256 `9a7752e70db7c1d56226847df56f7985c1dd4fba79ae6c3b49acc9e7aad6c150`.

| Market | Original WS1 contract rows reported |
|---|---:|
| Completions | 67 |
| Pass attempts | 69 |
| Passing yards | 96 |
| Receiving yards | 584 |
| Receptions | 568 |
| Rush attempts | 98 |
| Rushing yards | 249 |
| Tackles + assists | 114 |
| Total | 1,845 |

The native WS1 consumer is implemented and fixture-tested. It retains every original row and original missing control. However, **WS3 has not successfully executed native byte consumption of the real 1,845-row artifact**. Therefore real WS3 attempted-contract forecasts = 0, real forecasts = 0, and materialized real per-contract abstention rows = 0. The table above is upstream reported coverage, not an invented WS3 forecast ledger.

Deepnote notebook `9f674337fc5f461b87279f03f231a614` contains the bounded offline test, numerical review and original-manifest consumer. First WS3 execution `79d5ceb0-43f7-4f8a-ad92-ed633fdc71fd` stopped before outputs with no error reason. Later Basic CPU detached requests and a full-notebook live request returned `Rate limit exceeded. Please retry later.` No failed request was reported as a successful run. No expensive machine, environment change or automated continuation was started.

Even after runtime access is restored, the inspected native handoff does not contain frozen historical opportunity training tables, a training cutoff, quantified participation/starter probabilities, verified product-specific DNP/settlement terms or original frozen 60/40 controls. Native consumption must abstain rather than manufacture those inputs. The proposed extended schema is a dependency interface, not a claim that WS1 already supplies it. Original source receipt clocks are known-availability bounds, not proof of upstream publication.

## Verification and numerical review

- **18/18 new local tests passed.** Future-week and cutoff rejection, target-game exclusion, starter-only eligibility, duplicate exact contract/team/player checks, distinct-book preservation, range/route/count checks, historical joins, source hashes/clocks, unknown-feature/final-script rejection, explicit DNP/unknown, recent injury-role reduction, empirical probabilities and immutable writes.
- **26/26 existing tackles tests passed.** No existing implementation was edited.
- **8,192-draw synthetic review passed** for all implemented models. There are 52 in-scope synthetic model-contract distributions, with independent PMF summation reproducing mean and Over/Under/Push; no target outcomes are used. All team play conservation errors are zero.
- Separate tackles calculation: analytic mean 6.7387175765 versus simulated 6.7098388672, mean Monte Carlo SE 0.0353037151. Difference is below one SE. Old/V4.1/O3 QB Beta expectation controls also passed independent sampling checks.
- No independent human or separate-agent review is claimed. Tests and a separate numerical calculation were performed by the same agent. No real prospective scoring, calibration result, market edge or incremental-value conclusion is available.

Final local synthetic report SHA-256: `e73c55f660cb93c5ec7a3fb9838e55114df6a22902b0a01d7877e85bc9fec82b`.

Final numerical review SHA-256: `605e451e93fee8678daa002a65c46f842afcae3cadc6a8e12889c0f8e629e37d`.

## Preregistered next evaluation and rollback

Evaluate all original exact contracts, preserving source rejects and abstentions. Use paired three-outcome Brier/log loss, per-market CRPS, workload MAE/CRPS, signed Over residual, calibration, zero/tail and role-transition diagnostics. Compare original frozen 60/40 and market probabilities only where authentically frozen and comparable. Resample by game and week/date, not independent prop rows. Do not use Sunday's outcomes to select the role-mixture weights, tune dispersion or reclassify starters. No ranking or Tier release follows from fixtures.

Smallest next action: restore bounded Deepnote execution and run the pinned native consumer, then have WS1 bind existing historical inputs, namespace crosswalk, probability transformations and exact product rules to a new immutable manifest before kickoff. Tracking-dependent variants remain explicit blockers. No scheduling is created. Rollback is removal of this unmerged research branch; baseline, statistical model directory, joint model directory, posteriors, pause marker and production schedules are untouched.
