# Reproduce the closed protocol review

Use the exact closed compiler from50022b13dea208ec519d7fef146b5e151d6f19e1 and the raw input pins in PREFIT_APPROVAL.json. After activation, use an isolated closed-code checkout with these review files and frozen sources.

```sh
python docs/nba_architecture/complete_predictive_20261120/independent_j_prefit/prefit_probe.py
python docs/nba_architecture/complete_predictive_20261120/independent_j_prefit/source_binding_probe.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_j_prefit/SHA256SUMS
```

The successful compile uses synthetic new parameter computations and a review-only mock approval in a temporary directory. The source attack stops before any parameter compilation. Preserve original timestamped receipts before reproducing; new result timestamps and current Git provenance may differ. No actual J working model, forecast or outcome score is produced.
