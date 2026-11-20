# Reproduce independent pre-fit review

The frozen source population was introduced at `178eafa99602e52f4807e96d307c4c3eecbea14a`. Reader review targets `6b0887848b16633b1c952446b9409bc13c574efc`; its exact source bytes remain unchanged by writer-only commits. Closed writer review targets `ef360a88f847da27a456ddab3ba8c93e45f0a042`. Use those implementation versions plus these later review-only scripts. The writer's real approval constants must remain None when reproducing its closed-gate test; a later activation intentionally changes that condition.

From repository root:

```bash
python docs/nba_architecture/genuine_s_prospective_20261120/independent_prefit/fresh_population_probe.py
python docs/nba_architecture/genuine_s_prospective_20261120/independent_prefit/reader_probe.py
python docs/nba_architecture/genuine_s_prospective_20261120/independent_prefit/fit_protocol_probe.py
python -m pytest -v tests/nba_architecture/test_prospective_s_sources_v1.py
```

The population probe reads the frozen 60 source captures without importing the candidate reader or fitter. The reader probe reconstructs a full canonical `independent_dataset.json`, compares it with the owner's repaired dataset and independent 698-row source ledger, checks all transformations and attempts, and instruments native.fit to forbid real fitting. It performs source mutations through temporary in-memory read substitution; original sources are not written.

The protocol probe uses temporary directories, explicitly synthetic approval bytes, mocked clocks and mocked native-fit return values. The actual native fit function body never runs. Its positive is an engineering protocol control, not a fit, admission or forecast. Both reversal cases retain no admissible fit receipt. The genuine compiled gate remains closed throughout this review.

Raw commands and streams are listed in `READER_COMMANDS.json`; exact tested code/data hashes and outcomes are in `READER_RESULTS.json` and `FIT_PROTOCOL_RESULTS.json`. `PREFIT_APPROVAL.json` contains exact activation limits, fixed parameters and the separate mandatory artifact-admission gate. `POPULATION_COMMANDS.json`, `POPULATION_DECISION.md` and the raw population streams preserve the earlier source review and reviewer-only tricode assumption failure. All old files from that checkpoint remain unchanged.

The independent dataset hash covers canonical compact JSON including its payload hash; its payload hash instead covers the canonical object before that field is added. Source/model/reader hashes cover exact original bytes. The recursive `SHA256SUMS` covers all current review files except itself. No training or holdout archives need decompression, and none may be scored by these commands.
