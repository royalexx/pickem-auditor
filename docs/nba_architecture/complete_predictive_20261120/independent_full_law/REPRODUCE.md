# Reproduce the accepted review

Use the exact code file hashes and source/candidate pins in ADMISSION.json. The implementation commit is90d2aebe72e3bcd34b39bede94f65f0ee9cb622a; later independent review commits add only review files. All raw PBP sources and the protected original corrected archive are required.

```sh
python docs/nba_architecture/complete_predictive_20261120/independent_full_law/review_probe.py
python docs/nba_architecture/complete_predictive_20261120/independent_full_law/rare_reference.py
python docs/nba_architecture/complete_predictive_20261120/independent_full_law/tail_and_source_controls.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_full_law/SHA256SUMS
```

The test probe writes fresh timestamped RESULTS and the rare reference records elapsed times; preserve the original receipt files and compare substantive results in a copied review directory rather than expecting regenerated receipts to have identical bytes. The candidate semantic replay excludes actual compute clocks and is compared byte-for-byte by canonical payload hash. No new fit artifact, forecast or outcome score is produced. Review raw streams and preserved failure explanations in REVIEW.md.
