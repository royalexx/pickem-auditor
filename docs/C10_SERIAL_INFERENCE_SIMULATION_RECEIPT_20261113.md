# C10 — 2026-11-13 fixed-horizon inference execution receipt

**Status: exploratory; not approved for confirmatory inference.**
**Governance:** PA-V25-MASTER-2026-11-09/v1.1 and
EXP-V25-NHL-SOG-EXPOSURE-EB-001 unchanged.
**Branch:** work/v25-c10-dependence-inference (stacked on draft #120).
**Original preregistration:** unchanged; this is an unapproved **candidate
amendment**, not an alteration to an already-running evaluation.

## Executed code
- \`v2/c10_serial_inference.py\`: fixed-lag-3 date-equal weighted HAC statistic.
- One-sided threshold selected by the **largest** 97.5% null quantile from
  36 *predefined* scenarios: AR1 correlation 0/0.3/0.6, Gaussian/centered
  lognormal/heavy-tail shocks, constant vs alternating heteroskedasticity,
  thin vs mixed within-date game/contract clusters.
- Separate calibration and validation seeds; no sports outcomes used.
- \`tests/test_v25_c10_serial_inference.py\`: deterministic scenario coverage,
  monotonicity and explicit insufficient-power block.

## Independent mathematical stress test

A separate NumPy + SciPy implementation (NOT importing the repo module)
was executed with:
- 40 date means, no prospective sports outcomes;
- 2,400 null calibration replicates **per scenario**, separate seed
  20261113; 4,500 validation replicates **per scenario**, seed 21261116;
- one-sided nominal alpha .025 and hypothetical delta −.002 Brier;
- date-level AR1 innovations, centered-lognormal skew and t3 tail,
  deterministic alternating date volatility and stochastic counts of
  game/contract clusters;
- fixed Bartlett HAC lag 3.

**Results:**
- Worst-grid Monte Carlo cutoff on −HAC t: **4.396849429886022**.
- Held-out maximum Type I estimate: **0.027333333333333334**.
- Worst-scenario power at −.002: **0.0**.
- Median-scenario power at −.002: **0.006222222222222223**.
- Independent validation file: \`/mnt/data/v25_c10_independent_simulation_20261113.json\`.
- SHA256: \`50ffa6152a34bfef7bb6cac0fdfb2511e7f8a4cbf6f1f39e6e31208b1ba709ab\`.
- Independent script: \`/mnt/data/c10_independent_numpy_validation.py\`.

The worst-grid cutoff preserves approximately nominal size **only within this
specified simulation family**, to Monte Carlo accuracy. This is NOT a proof
for unbounded unknown nonstationarity, missingness, adaptive eligibility,
arbitrary game correlation, season drift or true historical date variance.

The low power means the currently proposed 40-date fixed horizon is **NOT
adequately powered** for a −0.002 confirmation under tested scale scenarios.
The alternative must NOT be silently substituted for the original t test.

## Decision and strict no-leak gates

- Do not read or optimize on outcomes from the final evaluation period.
- Do not retrospectively change eligibility, candidate universe, primary
  estimand (equal-weight dates), or final horizon.
- No final single primary inferential method is approved yet.
- Future fixed-horizon confirmatory design requires preregistered amendment,
  independent validation and demonstrable power, *before* the first eligible
  primary outcome. Otherwise mark experiment exploratory.
- Existing shadow capture, numerical ablations, evaluation ledgers and
  reporting may continue without Tier/promotion/economic-edge claims.
