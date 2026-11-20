# Reproduce the closed fitter review

Use exact closed compiler162ea8490958f2ab5f4704505d79aab64e9c33e5 and the source/input pins in PREFIT_APPROVAL.json. After activation, use a separate closed-code checkout for these tests.

```sh
python docs/nba_architecture/coherent_opportunity_20261120/independent_prefit/prefit_probe.py
sha256sum -c docs/nba_architecture/coherent_opportunity_20261120/independent_prefit/SHA256SUMS
```

Real source calculations stop at sufficient statistics. Posterior/assembler numerical tests use synthetic fixtures. The public fitter success mocks assembly and writes only a labeled temporary synthetic payload; no real fit is performed. Preserve original RESULTS before reproduction because actual review/temporary mock receipt timestamps change. Do not call the actual one-time fit writer as a reproduction command after its authorization has been consumed.
