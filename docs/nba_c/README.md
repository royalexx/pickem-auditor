# NBA C-family engineering, P5 (research only)

**Immutable base**: accepted G0 `59d28dc23be97de2a6a82d22be8338151e31f5b6`; **source authority**: PA-V25-MASTER-2026-11-09 / v1.1.

Modules:
- `scores.py`: strict full-count PMF, CRPS (fast identity + independent quadratic reference), NLPD, MAE/RMSE/bias, seeded PIT, central coverage, zero/tail calibration, exact/sampled Energy Score and VS_0.5.
- `warehouse.py`: append-only content-addressed distribution and G0 source objects; J demands actual G/O/J witnesses; separate immutable official outcome vault.
- `scoring.py`: explicit G0 `validate_evaluation` join; postgame official counts only, DNP/void/unmatched fail closed, same-scenario joint score.
- `experiment.py`: date/game-locked chronological fold metadata with label release time, W0 simple, W1 equal, synthetic-only W2 global and W3 stat-shrunk regularized simplex, disabled W4, seeded Dirichlet weight exploration, cached CRPS quadratic, paired game/date-block bootstrap and 5,000-versus-20,000 synthetic precision probe.

Run: `python -m unittest discover -s tests/nba_c -p 'test_*.py' -v` from repo root with `numpy`, `scipy`, and G0 `jsonschema` dependencies available. No data API requests, model training, downloaded official outcomes, or sportsbook quotes.

`CachedCohort` intentionally accepts only `authorization='SYNTHETIC_UNIT_TEST'` plus `source_profile='SYNTHETIC'`. Historical real-result weight fitting is NOT implemented/authorized by P5. Before future P8/P9, a reviewed authorization boundary must be added, not bypassed. Do not blend primitive S, O, or J stage outputs as independent models.

Independent engineering QA/P6 signoff is not represented by author tests. No production or Tier authority.
\nAdditional `calibration.py` summarizes official postgame PIT histograms, quantile coverage, zero/tail residuals and unscored denominators without fitting a calibrator.\n\nExact tested-source SHA-256 receipts and 298 passing unit/regression tests are frozen in `P5_EXECUTION_RECEIPT_20261116.json`; the receipt pins the tested code commit rather than claiming a self-referential documentation commit SHA.\n