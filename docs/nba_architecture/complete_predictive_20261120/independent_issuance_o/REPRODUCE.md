# Reproduce

Use the exact code and input hashes from DECISION.json, the full issue files and protected original corrected archive.

```sh
python docs/nba_architecture/complete_predictive_20261120/independent_issuance_o/review_probe.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_issuance_o/SHA256SUMS
```

Preserve original result receipts before reproduction because real review timestamps change. The seed is fixed for the336 exposure/witness checks. The script never issues a valid new forecast, fits a new artifact, samples J count events or scores outcomes. Its issuer call uses only an existing output directory to verify write-once rejection.
