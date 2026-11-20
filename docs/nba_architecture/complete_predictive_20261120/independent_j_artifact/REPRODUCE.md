# Reproduce the independent artifact review

Use the source/model/receipt/compiler pins in ARTIFACT_ADMISSION.json and the frozen original corrected archive inputs.

```sh
python docs/nba_architecture/complete_predictive_20261120/independent_j_artifact/artifact_probe.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_j_artifact/SHA256SUMS
```

The script reconstructs the complete model in memory and compares canonical bytes. It never calls the one-time compiler again. Preserve original timestamped RESULTS before reproducing; new review timestamps differ. No model artifact or forecast is written.
