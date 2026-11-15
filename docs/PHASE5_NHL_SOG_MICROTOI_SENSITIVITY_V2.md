# Phase 5 NHL SOG: minimum positive TOI-bin sensitivity (V2, post-hoc)

**Class:** research-only, retrospective event-time sensitivity. **Not** a prospective as-of certification, independent holdout, original sportsbook benchmark or release candidate.

## Why this bounded repair exists

The frozen November 14 M0–M4 study EXP-P5-NHL-SOG-HIST-20261114 used NHL historical records collected in November 2026. It generated 21,569 candidate player-games, 20,333 sealed forecasts, 17,723 scored played-games and 1,236 abstentions. Of these, **1,222** arose from EXPOSURE_BIN_INVALID: a legitimate played three-second (0.05-minute) TOI on March 3, 2026 was positive but rounded to zero by a half-minute grid. The original fail-closed record is retained unchanged.

Original registered frozen forecast SHA-256:
12c267b7ca629d75a69f8cfd429a5a55e8510f4be7cb914ec5860c18097553dc

The original frozen study and both prospective NHL SOG experiments remain unchanged.

## One and only one candidate rule

For observed **prior** played games with 0 < TOI_minutes < 0.25, use the minimum positive **0.5-minute** bin *inside the empirical exposure PMF only*. Preserve raw actual TOI in shooting-rate, Gamma posterior shape/rate, own-rate, and historic-TOI summaries. Existing half-up bins above or equal to 0.25 minutes and all M0–M4 forecast distributions are otherwise unchanged. Zero, negative, nonfinite and unsupported TOI remain invalid.

This is a robustness hypothesis motivated **after** studying the failed 2026 historical observation. No hypothesis test, p-value, market edge, or model superiority claim follows. The observation is not a target-game DNP and may not be silently dropped.

## Reproducibility and anti-contamination constraints

- Script: scripts/v25_phase5_microtoi_sensitivity.py
- Tests: tests/test_v25_phase5_microtoi_sensitivity.py
- The script requires exact SHA-256 of the archived November 14 observations, schedule, sealed forecasts, scored rows and score report before execution.
- It requires the old replay implementation to match an exact structural signature. It constructs a **separate isolated source copy**, replacing exactly three exposure binning calls in build_params; its experiment ID and artifact lineage are different. The frozen probability implementation is not modified.
- Historical time filters, source limitations, player eligibility, original source bytes and scored target outcomes remain unchanged.
- Candidate outputs are written in a new append-only research folder. No original file is overwritten.
- The comparison fails closed if **any** previously scored player-game is lost or its model scores change. Newly scored rows are described as recovered *coverage*, never automatically improved predictive skill.
- Count CRPS and NLL can be shown descriptively for the expanded cohort, **not** as valid paired model-improvement inference when cohort membership changes.
- The 40-date prospective exposure trial, fixed-shape NB2 study, legacy 60/40, Tiers, publication settings, NUTS artifacts and automations are untouched.

## Acceptance and scientific limits

An acceptable engineering result would reduce the 1,222 prior-bin abstentions, preserve the original 17,723 scored outcomes identically, keep the 21,569 candidate denominator, report additional scored/unscored outcomes, retain finite distributions, and record complete hashes.

Independent prospective source-certified validation and preregistered assessment remain mandatory before any use in decision-making. **No production promotion is authorized.**

Branch: research/phase5-microtoi-sensitivity-v2-20261114. Any eventual merge is research tooling only, gated on QA and separate review.


## Executed archive-only evidence — 2026-11-15 UTC

**Deepnote full sensitivity run:** 605ba6be-44eb-439f-a1b4-51290aae171e (success); **independent SciPy and identity run:** 78799cdc-0daf-4c59-ad53-7109b770a3ee (success). Six new adversarial tests passed, and GitHub offline tests on draft PR #128 head d5ba9ac30208570047fe19fd536438dce8bc0cfa passed.

Immutable output root:
reports/phase5_nhl_sog_historical/20261114T222036350236Z/microtoi_posthoc_sensitivity_v2_20261115T025720017227Z/e17697159f480406a297/

Observed from the same 21,569 candidate player-games:

| Measure | Original frozen | V2 sensitivity |
|---|---:|---:|
| Forecasted | 20,333 | 21,555 |
| Played and scored | 17,723 | 18,790 |
| Unscored forecasts | 2,610 | 2,765 |
| Invalid exposure bin abstentions | 1,222 | 0 |
| Inadequate own history abstentions | 14 | 14 |

All **20,333** original *forecasted* player-game distributions and fitted parameter fields, including the 17,723 scored outcomes, were independently verified unchanged. The 1,222 new forecasts all occur strictly after the March 3, 2026 micro-TOI source game. Of these, 1,067 had official played-game SOG settlement records; the remaining 155 were unscored, not coded as zeros or bookmaker voids. This is a coverage repair, not improved same-contract predictive accuracy.

Independent archived numerical audit: 30,550 SciPy PMF checks, maximum absolute discrepancy 2.0594637106796654e−14; new matched NLL maximum difference zero. Original source observations, schedule, sealed forecast and score hashes were rechecked. Independent receipt SHA-256: **64513e46f01a73a31c08058aa8948798695a3af38bf2966782ffd63bab5333a5**.

| Count CRPS | Original 17,723 | Repaired cohort 18,790 |
|---|---:|---:|
| M0 | 0.719662 | 0.720283 |
| M1 | 0.719222 | 0.719542 |
| M2 | 0.714701 | **0.715131** |
| M3 | 0.715737 | 0.715900 |
| M4 | 0.722642 | 0.723181 |

These column means have **different scored membership**; they cannot be interpreted as same-contract model improvement or regression. On only the newly scored 1,067 played-games M3 had CRPS 0.718608 and M2 had 0.722278. This is a posthoc, selectively recovered subgroup, not prespecified confirmatory skill.

**Result:** engineering and isolated retrospective statistical invariants PASS. Historical as-of source authentication, independent prospectively unused evaluation, bookmaker D2 comparison, economic edge, model promotion and Tier release remain **BLOCKED**. Research draft PR #128 should not change any production or prospective model configuration. Its merge is a separate code-integrity decision.
