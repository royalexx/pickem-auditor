# Reproduce

Use the exact activated writer/native/reader/artifact pins in ARTIFACT_ADMISSION.json, original corrected archive inputs and source files. From the repository root:

```sh
python docs/nba_architecture/complete_predictive_20261120/independent_s3_artifact/artifact_probe.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_s3_artifact/SHA256SUMS
```

Reproduction creates only an in-memory deterministic artifact for equality verification and a freshly timestamped result receipt. Preserve the original result bytes before reproducing. It does not write a fitted model, forecast or outcome score.
