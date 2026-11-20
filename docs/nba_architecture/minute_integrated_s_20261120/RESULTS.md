# Integration progress and complete-pipeline stop gates

Implemented and executed a new S1/minute integration candidate over the exact
PR190 frozen inputs. It propagates conditional-minute uncertainty through the
Gamma–Poisson kernel rather than substituting one minute estimate. All140
attempts remain:56ordinary-conditioned numerical laws and84upstream abstentions.
Original forecasts, models, source bytes, old accepted code and red receipts
are unchanged. This operation computed a candidate, not a new issued forecast.

**The requested complete predictive distribution, valid real J simulation,
C scoring and release-grade historical validation are not complete.**

Independent review found that naive full-beta integration crossed the admitted
S1 exposure domain. The supplied minute law places approximately20%mass below
30seconds for Cody Williams and28%for Kris Murray. That mass is not DNP and
cannot be erased, assigned zero statistics or silently modeled by the ordinary
S1 kernel. The rejected full-beta candidate is retained. The corrected candidate
conditions explicitly on played AND ordinary exposure, with joint OT/exposure
renormalization, excluded mass, analytic moments, numerical diagnostics and a
fixed control at the matched ordinary-conditioned mean.

The calculation explicitly assumes rate-posterior/future-minute factorization
given frozen history/role. It is not an estimated genuine joint posterior.
Quadrature order differences are diagnostics, not rigorous error bounds.
Existing exploratory minute-model and source-admission limitations remain.
Neither this candidate nor the narrower source profile relaxes full-law gates.

Implementation8730aad9b20926e0de319c1aded94c16972c6592; actual candidate and
targeted tests13a5419f2b1765e68f4c170fbbf3638962d934a3. The full offline suite
ran2,312tests with9skipped and no failures/errors; source/test bytes were
unchanged. Two targeted methods/four subtests passed, including independent
scalar integration checks. The separate independent_review/ packet records
mathematical review of all56laws and its exact bounded disposition; numerical
agreement does not grant new model, full-played, J, C or release admission.

## Missing evidence or mechanism and consequence

1. **Played-zero/sub30/early-exit component:** requires a separately specified
   count mechanism and mixture mass, with authentic full-game measurement and
   source-specific display semantics. Continuous positive minutes alone do not
   establish a played-zero atom. Quarter-only examples do not establish a
   full-game exception. Until this is admitted, no complete played-conditional
   law; genuine participation is additionally needed for unconditional output.
2. **Real J integration:** the current integration_v2 entry is explicitly
   synthetic-only. It requires PRIMITIVES plus an admitted S3 three_conversion
   artifact, validated shared G/O scenarios and sidecar, compatible physical
   shot/FT/miss/rebound/assist opportunities, exact same-draw reuse and a bounded
   accepted coupling/marginal-distortion contract. PR190 admits four S1 models,
   not these additional mechanisms. No independent marginal draws are relabeled
   valid J. The original n32 coupling-budget red remains untouched.
3. **C handoff and outcomes:** a versioned canonical adapter must represent the
   actual conditioning, never rename played-and-ordinary to played-only. Official
   count/participation/evaluation/correction receipts must match the frozen
   distribution. The November21target has no supplied official outcome yet.
   No training result is substituted. DOWNSTREAM_STATUS.json retains all140
   attempts with zero J scenarios and zero C-scored rows.
4. **Historical predictive replay:** the new S1 artifacts postdate all20training
   games. They cannot honestly predict those games or the already-started
   November19slate. Required evidence is a preregistered historical target cohort
   with genuinely pre-cutoff model/minute artifacts, source/feature freezes and
   matched official outcomes, plus the governing G1/G2/P8 prerequisites and
   evaluation authorization. Current historical result captures do not prove
   original pregame availability. No holdout was opened, decompressed or scored.
   Engineering replay is not predictive validation. Release remains blocked.

## Required observations and next implementation order

Capture prospective pre-freeze identities, availability/membership and actual
observation clocks separately from source publication. After the event, preserve
official full-game box scores and, where needed, game-clock/substitution evidence
for every played-zero/sub30/DNP/unknown case; retain rejected/missing cases and
source precision rather than inventing exact exposure. Review and freeze the
early-exit/zero component before fitting or admission. Reconcile the complete
minute/count mixture before attempting coupled simulation.

Next admit the real G/O/S3/event coupling through its own exact source/artifact
contracts, test shared draws, physics and distortion budgets, then implement the
compatible C handoff and official evaluation. Freeze the historical replay
cohort, model/source lineage and comparisons before opening any authorized
evaluation. No production release can precede that replay. This ordering does
not require pretending the narrower profile has a complete legal roster; it
requires that each claimed probability and shared mechanism be supported.

[CANDIDATES.csv](CANDIDATES.csv), execution/, [REPRODUCE.md](REPRODUCE.md), the
independent review, full_suite/ and SHA256SUMS provide exact results and receipts.
No new fits, weights, NUTS restart, schedule change, merge, deployment or Tier
promotion occurred. PR190's admission has not been silently extended.
