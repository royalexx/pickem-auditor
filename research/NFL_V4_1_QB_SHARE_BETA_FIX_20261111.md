# Pick'em Auditor V4.1 — QB starter opportunity Beta-prior correction

Research date: November 11–12, 2026.
Branch: chatgpt/nfl-v4-1-qb-opportunity-repair-20261111
Status: **RESEARCH ONLY, production and Tier 1/2 promotion blocked**

## Mathematics: identified shrinkage problem

The inherited V3/V4 contextual QB simulator drew share of a team's passing attempts using:

`share_sample ~ Beta(12 + 35*s, 12 + 35*(1-s))`

where `s` was the estimated prior-depth starter's observed historical share of team attempts.

By the expectation of a Beta random variable, that prior implies

`E[share_sample] = (12+35s)/(24+35)`.

For a reliable selected QB with historical 95% share, this produces ~0.766949, strongly shrinking the quarterback toward 50%. It can underproject QB attempts, completions and passing yards even if the team passing total forecast is reasonable. This is a mathematical modeling assumption, not Bayesian uncertainty magically resolved by more years.

## Repair without postgame knowledge

V4.1 instead draws

`share_sample ~ Beta(1 + 60*s, 1 + 60*(1-s))`

so the expected share for `s=.95` is ~0.93548, modestly regularized but far closer to the observed prior. The empirical rate `s` is estimated from already-played QB exposures with prior pseudo-attempts, not from current-game outcomes.

QB passing attempts draw from a Binomial with the *same sampled team pass opportunities*; the completions model draws a posterior completion rate from earlier QB games; passing yards are regenerated conditional on those completions. QB rushing attempts and yards are also conditioned on corrected passing opportunity and bounded by total team rushing opportunity.

Strict prior-depth QB1 eligibility remains a hard gate. The fix does not allow an unconfirmed backup to appear in model forecasts merely because it later took snaps after an injury.

## Diagnostic performance

A small multiweek 124-QB example found average current V4 QB pass attempts 29.89 versus actual 34.56 (bias -4.68); this made the shrinkage issue a priority for independent repair.

2016 season, 398 matched QB contracts per passing market: *uncalibrated pure context profile* raw binary Brier

| Stat | V4 recent | V4.1 recent | V4 long | V4.1 long |
|---|---:|---:|---:|---:|
| Pass attempts | .31191 | .23727 | .31151 | .23977 |
| Completions | .31744 | .24548 | .31319 | .24112 |
| Passing yards | .29177 | .23696 | .28619 | .23811 |
| QB rush attempts | .22881 | .23088 | .22859 | .23035 |
| QB rush yards | .23589 | .23083 | .23524 | .23111 |

As expected, QB pass and downstream distributions materially improve, but rushing attempts may worsen slightly. This underscores why full market-specific audit and CRPS are required.

The *final online blended calibrated forecasts* remained identical to frozen V3 at initial weeks because its trust gate had insufficient prior evidence. The result above is for the pure contextual components; no gain in final wagering confidence or live profitability has been established.

These 2016 observations were examined during model development and therefore are **not** a pristine holdout. Do not promote based on this table.

## Reproducibility and full decade

- Frozen baseline unchanged: V2, V3, V4.
- Corrected source code `research/nfl_v4_1_qb_share_repair_model_20261111.py`.
- Independent V4.1 replay `research/nfl_v4_1_qb_repaired_decade_20261111.py`.
- Unit tests `research/tests/test_nfl_v4_1_qb_share_repair.py`, four passing tests.
- Independent paired forensic audit: `research/nfl_v4_1_independent_175_week_audit_20261111.py`.
- Direct profile and QB correction ablation: `research/nfl_v4_1_vs_v4_factor_ablation_20261111.py`.

Both V4 and V4.1 are tested over the same 2016–2025 175 weekly synthetic contracts (556,094 offers, 407,476 historically paired scored contracts). V4.1 uses a separately frozen pre-week factor and stack state and updates it only after official weekly settlement. All source receipts are research-only.

## Release blockers

The real bookmaker line is absent, historical sources were collected retrospectively, original pregame starter availability is unverified and unmatched player offers are excluded from paired scores. Corrections to a mathematical prior can substantially change pure component Brier without proving final selected high-confidence reliability or economic edge.

Require full decade paired Brier, log loss and per-market CRPS; market-specific post-repair biases; prospective authentic as-of lineup and quote collection; clustered game/week uncertainty and repeated later-season validation before any production release.
