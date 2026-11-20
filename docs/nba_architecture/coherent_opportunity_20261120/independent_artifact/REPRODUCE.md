# Reproduce exact artifact admission

Use the activated compiler/input/artifact pins in ARTIFACT_ADMISSION.json and the preserved original source packets.

```sh
python docs/nba_architecture/coherent_opportunity_20261120/independent_artifact/artifact_probe.py
sha256sum -c docs/nba_architecture/coherent_opportunity_20261120/independent_artifact/SHA256SUMS
```

The script performs one in-memory assembly replay and independent rational/predictive calculations. It never invokes the fit writer again. Preserve original RESULTS before reproducing because review timestamps change. No fitted-model file, J bank, forecast or score is produced.
