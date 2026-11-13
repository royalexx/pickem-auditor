# EXP-V25-NHL-SOG-EXPOSURE-EB-001 — prospective preregistration (shadow)

**Status:** preregistered DESIGN / NOT YET ACQUIRING ELIGIBLE FORECASTS.
**First eligible date:** later than this document's first Git commit and after
C03, authentic quote/roster/source capture and a fully frozen model artifact
are available. Do not backdate Nov 10–12 predictions.
**Deadline:** 2027-01-31 America/Toronto.
**Scope:** NHL regular-season, full-game shots on goal, official-roster-verified
F/D skaters, independent source-neutral C03 Cohort A, played-game conditional
distribution with bookmaker void rules separately verified. Cohort B is a
separate descriptive stratum only; C and D never enter the primary matched score.

## Frozen scientific choices

- Primary baseline: SOG_POISSON_OWN_RATE_V1, latest <=20 legal played
  observations, own SOG/TOI rate, deterministic median latest <=5 TOIs.
- Primary challenger: SOG_EXPOSURE_GAMMA_POISSON_V1, tau=60 minutes, eta=3
  pseudo-games, leave-one-player-out F/D peers, >=20 distinct peers and >=200
  peer-games (<=20 per peer), historical TOI grid 0.5..65 min, half-up binning,
  <=10 recent own played TOIs. All inputs/fit/quote before forecast freeze.
- Secondary ablations: fixed-exposure Gamma–Poisson, exposure-mixture
  plug-in Poisson, and separately frozen fixed-r=4 NB2 only when an original
  same-contract forecast is independently available. No hyperparameter
  tuning, model selection or calibration using prospective outcomes.
- Market baseline: identical real quote/player/stat/period/line, authentic
  compatible two-sided price and frozen time, multiplicative no-vig only
  where applicable; absent otherwise. No synthetic market prices.
- V1 Engine A, Engine B, Bayesian A/B, NUTS, frozen 60/40 are diagnostic
  comparators only when independently frozen, source-matched and nonpreliminary.

## Primary estimand and horizon

Unit is a unique offered player/stat/period/book/line contract, with its
official Over/Under/Push settlement state. Alternate lines count as distinct
offers but correlated observations, never independent player-games.
Score ONLY contracts with both preregistered models, exact matched terms,
pregame archived sources and a verified nonvoid official result. All rejects,
missing quotes, Q/D, DNP, postponed, void, and unmodeled contracts stay in an
append-only complete attempt/coverage denominator.

For each eligible date d, compute mean over matched contracts of:
Δ_id = Σ_{s in {O,U,P}} [(p_challenger,s - 1{Y_i=s})² -
                          (p_control,s - 1{Y_i=s})²].
Primary parameter θ = equally-weighted mean of date-level Δ_d.
Negative is better for challenger. Do NOT secretly switch to contract-weighted
pooled mean. The primary cohort must have exactly 40 eligible slate dates
prior to or on 2027-01-31; eligibility is fixed pre-result for each date.

If fewer than 40 eligible dates are captured by deadline, the experiment is
administratively INCOMPLETE: no confirmatory inference, no extension by
inspecting the realized scores, no Tier/promotion. Future prospective trials
require a new versioned card approved before their forecasts.

**Primary decision:** one final one-sided α=.025 test of θ >= 0 against
θ < 0, with a pre-specified minimum useful point-estimate threshold
θ <= -0.002. A stronger claim "improvement by >=.002" would additionally
require a one-sided upper uncertainty bound below -.002. None of these is
authorization to deploy or bet.

## Dependence, inference, power

The candidate initial fixed-horizon method is paired-date t inference using
39 df if all 40 dates qualify (critical t39=2.02269092), with game-level
dependence subsumed within date averages. This is NOT guaranteed valid under
date-to-date serial dependence, material heteroskedasticity, distributional
skew or adaptive contract selection.

Before collecting the first eligible final-test slate, execute and independently
review a seeded Type I/feasibility simulation spanning date SD assumptions
(.01,.02,.04,.08), AR(1) rhos (0,.3,.6), game clusters and varying contract
counts. The implementation contains fixed_horizon_feasibility_grid and
power_null_simulation. These are scenario tests, not empirical variance estimates.
If nominal .025 size cannot be defended across plausible dependence scenarios,
the confirmatory primary inference status is BLOCKED: no opportunistic switch
to a different method after viewing final outcomes. A new preregistered,
simulation-validated method requires owner/independent approval first.

Do not treat 40 dates, 200 peer-games or total raw props as an effective
independent sample size or a guarantee of useful power. No optional interim
statistical looks. Periodic ingestion/technical health checks cannot inspect
the blinded primary performance comparison.

Secondary Brier/log-loss comparisons across the three prespecified ablations
may be descriptive; if hypothesis tests are requested, apply Holm family-wise
correction within the three secondary comparisons. Legacy and market comparisons
are labeled exploratory unless separately preregistered.

## Secondary diagnostics and negative controls

Report three-way log loss, full-count NLL and CRPS, zero and tail calibration,
Over/Under probability bands, exposure mean/variance, PIT/randomized PIT with
fixed seed, pushes, actual low-TOI played events and early-exit tails, DNP/void
policy, top-k (descriptive), coverage/abstention by date and team, CPU and
peak memory. Keep confidence-band cutoffs frozen at [0,.5), [.5,.6),
[.6,.7), [.7,.8), [.8,.9), [.9,1] for selected-side played conditional
events, with over/under separately when denominators support.

Fail all source-time tamper, postgame injected exposure, duplicate player-game,
traded-player wrong team, missing roster, altered raw quote, future offer, and
source/settlement identity canaries. No actual team attempts, current-game
SOG/TOI, injury after cutoff, or settled result may enter a pregame model.

## Operational and release status

- Full future pregame snapshots must be append-only, hash/version/commit-bound.
- The same fitted predictive distribution is shared by all alternate lines;
  fixed-line adapter snapshots are NOT the full generative artifact.
- Forecast only as SHADOW. Frozen legacy engines and r=4 NB2 pilot unchanged.
- No live automation toggle, NUTS, paid data, ranking weights or Tier changes.
- On integrity failure: record abstention and stop affected trustworthy cohort.
- On statistical failure/underpowering: keep simple baseline, publish research
  comparison only, collect evidence without claiming economic edge.
- Independent implementation, data-integrity and statistical review must sign
  off before any claim of validated improvement or later release proposal.

**Pre-registration source version:** this exact immutable Git file and its
first accepted blob SHA; later changes create a new experiment version and
cannot rewrite prior eligible dates.
