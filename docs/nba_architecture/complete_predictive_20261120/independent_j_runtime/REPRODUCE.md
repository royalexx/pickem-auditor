# Independent J reproduction

Run from repository root using implementation20f79e89ae1365235fc2a7549b85d2997dd3338b, with this independent directory. Diagnostic-label control additionally requires9fd0355447a8590ad1e13d70b6293f756ce079b0. These controls do not create a fit, a new issued forecast or an outcome score.

```sh
PYTHONPATH=. python docs/nba_architecture/complete_predictive_20261120/independent_j_runtime/public_probe.py
PYTHONPATH=. python docs/nba_architecture/complete_predictive_20261120/independent_j_runtime/actual_probe.py
PYTHONPATH=. python docs/nba_architecture/complete_predictive_20261120/independent_j_runtime/moment_witness_probe.py
PYTHONPATH=. python docs/nba_architecture/complete_predictive_20261120/independent_j_runtime/clock_period_red.py
PYTHONPATH=. python docs/nba_architecture/complete_predictive_20261120/independent_j_runtime/accepted_status_probe.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_j_runtime/SHA256SUMS
```

public_probe.py is the 5-method synthetic engineering suite; actual_probe.py is the 2-method deterministic actual-source run and 56-diagnostic numerical replay. tests.* and actual.* retain their original stdout/stderr; ENGINEERING_RESULTS.json and ACTUAL_RESULTS.json preserve complete results. The actual probe replays frozen20f diagnostic bytes, including their original field name, and does not replace them. A later field-only correction is separately tested in diagnostic-label.stdout and bound by DIAGNOSTIC_LIMITS.json. The supplied scripts write their diagnostic artifacts; copy the directory before rerunning to keep the earlier receipts untouched. No scheduled work or live network call is needed.

moment_witness_probe.py is independent of owner compatibility code. It uses exact-integer factorial checks and100/180-digit Decimal log products from exact binary64 parameters bound to actual_full_forecast/forecast.json. MOMENT_RESULTS.json retains all 14 long-precision witnesses. The theoretical proof and necessary/common-moment assumptions are in REVIEW.md.

The clock/period sensitivity command returned exit1 at14440b7a/c21c12ee with two accepted invalid paths; it now returns exit0 with both rejected. accepted_status_probe returned an invalid acceptance at cba058f4 and now rejects at20f79e89. The rate-exhaustion probe's original raw receipt atcba058f4 records zero retained fixed-scenario records/rate proposals; public_probe.py tests repaired fixed_partial/4096-vector retention at5d3babe5 and later. Reproduce original reds only in isolated old-commit checkouts with the same review scripts. initial_setup_probe.py/initial-setup.* and initial_runner_probe.py/initial-runner.* retain reviewer-harness errors; they are not implementation red cases or passed tests.

SHA256SUMS binds exact current reviewed code, protocol/model/admission/fit receipts, actual run/cohort/diagnostic/physics/execution files, their original raw domains, mathematical witnesses and independent results. Raw RUN.json hash covers every canonical serialized accepted and rejected event path; event-model hashes cover exact saved working-parameter bytes; receipt hashes cover original UTF-8 JSON; model/data/clock ancestry is not conferred by those hashes alone. The owner has the full raw 7.3MB actual run and this review does not duplicate or rewrite it.
