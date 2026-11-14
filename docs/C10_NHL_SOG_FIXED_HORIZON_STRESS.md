# C10 — fixed-horizon NHL SOG inference stress audit (not release certification)

**Experiment:** EXP-V25-NHL-SOG-EXPOSURE-EB-001. **Status:** exploratory / confirmatory BLOCKED.
**Prospective data used:** none. **Primary endpoint unchanged:** mean over eligible
slate dates of matched contract-level *three-way Brier challenger-minus-control*,
pushes scored separately. Original 40-date / 2027-01-31 capture horizon
remains a collection goal, not a guarantee of adequate independent information.

## Reproducible alternative and held-out simulation

Implemented \`v2/c10_sog_fixed_horizon.py\` using a fixed bandwidth-5 Bartlett
HAC Studentized mean-date difference. Before any eligible outcomes, estimate
a *conservative grid-calibrated critical value* as the minimum of the lower
1% null t-statistic quantiles across 96 frozen stress scenarios, rather than
using an invalid ordinary t(39) critical value. Use one deterministic seed
family for calibration and disjoint seeds for null and effect evaluation.

Scenarios combine:
- AR(1) date correlation 0, .3, .6, .8;
- Gaussian, negatively skewed exponential, heavy-tail t(3) innovations;
- constant or strongly alternating heteroskedastic date scales;
- sparse 1–3 games x 1–4 contracts versus dense 1–9 x 1–21;
- assumed date SD .01 or .04.

Run: \`python -m v2.c10_sog_fixed_horizon --output /tmp/c10.json
--calibrate-reps 1500 --audit-reps 2500\`. **Research CPU, not production.**

## Independently executed synthetic audit (2026-11-13)

96 scenarios, 1,500 calibration + 2,500 held-out null + 2,500 held-out
alternative replications *per scenario*. Fixed effect is −0.002.

- Lower-tail critical HAC statistic: **−5.4620284431**.
- Largest observed null false-positive fraction: **0.0096** (0.96%),
  against one-sided nominal target 0.025 (2.5%).
- Power at −0.002: minimum **0%**, median **0.28%**, maximum **3.4%**.
- Reproducible canonical JSON hash (excluding digest itself):
  \`1a4205d63c957a931bf92de7e04350a2da4817081638065c109cb68318c58e4d\`.

**Interpretation:** Robust-looking null results across the predeclared
synthetic grid are purchased by unusably low power at the desired effect.
The grid does *not* prove distribution-free Type I control, does not establish
real-world serial dependence, and does not measure actual variance from a
future frozen slate. This alternative does not clear C10's confirmatory gate.

Do not make a one-sided p-value claim using this method on the 40-date study.
No adaptive test switch or hyperparameter change may be selected after
looking at final prospective outcomes. Treat 40-date study as exploratory
unless a separately approved, preregistered and independently validated
inferential amendment is frozen before the first eligible outcome.

## Required independent validation for any future confirmatory claim

- Recreate source-to-score paired-date estimand, identical lines,
  void exclusion but complete attempt denominator.
- Stress Type I error with credible *worst-case* serial dependence and
  partial season drift; include matched games within dates.
- Estimate prospective effective sample size and clinically/financially useful
  power from separately available historical **diagnostics**, never from
  the held-out evaluation period.
- Lock one final primary look and no ad hoc subgroup rescue.
- No new Tier, promotion, live odds claim or scheduling.
