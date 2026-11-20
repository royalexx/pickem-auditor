# Reproduce exact independent C review

Repository root, exact implementation 1818407a9591ec6ec8b355ec90165f8360afe606 plus these independent files:

```sh
PYTHONPATH=. python docs/nba_architecture/complete_predictive_20261120/independent_c_implementation/public_probe.py
PYTHONPATH=. python docs/nba_architecture/complete_predictive_20261120/independent_c_implementation/reader_drift_red.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_c_implementation/SHA256SUMS
```

The first command's stdout/stderr are tests.stdout/tests.stderr. It exits nonzero on failed assertions. RESULTS.json retains method counts and public-result metadata; native_outcomes.json and actual_pending_replay.json are exact canonical public output wires. The probe rewrites those diagnostic files when rerun; use a copy to retain original receipts. No source capture, forecast issuance, outcome scoring join or persisted model fitting is performed.

The drift command is a sensitivity control: at d98a2443 it returned exit1 with RED_SOURCE_READER_BYTE_DRIFT_NOT_REJECTED (reader-drift-red.stdout/stderr); at repaired 1818407a it returned exit0 with C_SOURCE_HELPER_CODE rejection (reader-drift-repair.stdout/stderr). To reproduce the historical red, use an isolated checkout at d98a2443 with the same raw packet and review script, never overwrite the current source implementation. The control patches bytes returned when reading the parser file, not the source capture or parser behavior.

Hash domains are exact repository/input file bytes, captured HTTP response body bytes, original UTF-8 receipt bytes, and exact canonical serialized output bytes. Existing source-profile SHA256SUMS binds the full twenty-game raw population; this review's manifest adds all new C/replay/parser helper code, profile/spec/forecast/snapshot bindings and independent records. Current operation time does not rewrite original forecast clocks. The event remains future at this review; replay does not invoke the pre-event generation gate, allowing unchanged issued bytes to be checked after the event.
