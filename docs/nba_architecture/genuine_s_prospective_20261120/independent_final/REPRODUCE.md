# Reproduce final independent acceptance

The independently tested snapshot is `eda90d77d4cd3c415701a95b5f186e56bc585183`. The source producer at actual forecast time was `76201b7795b718005d82b6443c2ea614e9824310`; corrected archive creation used `30b506f3d5c72af50f0624cf1a52f6e86e52a126`. Subsequent documentation/test publication leaves all covered source files byte-identical. The exact source-file hashes are in `RESULTS.json`. Use that reviewed checkout as the external archive verifier; an archive cannot appoint its own verification code.

From repository root:

```bash
python scripts/nba_genuine_s.py replay-archive \
  docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive \
  --expected-manifest-sha256 934671c7c8ab61293a0c9eadad6d8456d3615f03cdfc558933bf9fe7854a327f

python docs/nba_architecture/genuine_s_prospective_20261120/independent_final/final_probe.py

python -m pytest -v \
  tests/nba_architecture/test_prospective_s_sources_v1.py \
  tests/nba_architecture/test_genuine_prospective_s_v1.py

python docs/nba_architecture/genuine_s_prospective_20261120/independent_final/manifest_population_counterexample.py \
  docs/nba_architecture/genuine_s_prospective_20261120/corrected_archive
```

Offline replay remains valid after the event. It is explicitly not a newly issued historical forecast. The final probe also invokes a deliberately invalid-source current-clock CLI to verify the rejected-batch ledger; its frozen source hash fails before forecasting. It issues no genuine new forecast. All mutations use temporary copies or newly constructed output values. No original archive, model, source or forecast is rewritten.

The probe directly observes real native S/M0 calls, checks the exact 140 identities and exposure joins, independently computes all 56 Gamma–Poisson PMFs/means/triplets, runs the public trusted archive CLI and a separate isolated recomputation, and exercises output/cohort/clock/model/source/code/schema/domain/count/file mutations. `cold_recompute.py` denies all repository reads outside the supplied archived tree, while allowing required installed Python libraries. The standalone recomputation prints its explicitly unverified-code mode; the separate external trusted verifier establishes archive acceptance.

The two manifest-population counterexamples initially ran against the original actual archive and were accepted. Those original raw streams remain in `initial_manifest_population.*`. An intermediate recheck used the preserved old code snapshot and rejected it because trusted code had changed; those streams are retained separately and are not the repair proof. The final explicit `corrected_archive` recheck rejects the two mutations for their intended population/reference-schema reasons. The original actual archive and corrected archive carry identical forecast/model/cohort bytes; the repair receipt explicitly says no forecast was issued or replaced.

`COMMANDS.json` contains raw subprocess argv/clocks/exit codes and streams; `REVIEW_COMMANDS.json` records top-level review commands and inspected owner checks. `INDEPENDENT_FORECAST_CHECKS.csv` includes every forecast/abstention and diagnostic means. `PRESERVATION.json` records old-code/source/workflow/training-pause/model/config comparisons. `CRITERION_LEDGER.json` separates engineering PASS from unestablished scientific and release gates. Check this packet's recursive hashes from this directory with `sha256sum -c SHA256SUMS`.
