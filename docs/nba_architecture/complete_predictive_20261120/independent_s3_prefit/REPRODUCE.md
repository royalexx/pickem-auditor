# Reproduction

The prefit probe requires the closed writer from commit 8730362cce3a04eb8edeaa15388651f1cee240f7. After activation, use an isolated checkout of that commit with this review packet and the frozen original inputs.

```sh
python docs/nba_architecture/complete_predictive_20261120/independent_s3_prefit/prefit_probe.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_s3_prefit/SHA256SUMS
```

The probe imports the native fit function but mocks every call. The temporary mock artifacts are explicitly labeled and discarded. It does not fit a genuine artifact or score any outcome.
