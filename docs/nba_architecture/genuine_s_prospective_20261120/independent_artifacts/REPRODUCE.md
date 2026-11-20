# Reproduce independent artifact review

Use the exact committed source population, reader and fitted artifacts published at `14e2018cabd52421644a1d28037b08a02db754b4`. The approved activation is `2e2bab6220636ad93d1dd18a03daa0d323f31770`; the corrected intervening-game runtime is `7938073b57542ebfd3073bc96938417d28a8b5ab` or its byte-identical later version. These later review-only scripts provide the independent checks.

```bash
python docs/nba_architecture/genuine_s_prospective_20261120/independent_artifacts/artifact_probe.py
python docs/nba_architecture/genuine_s_prospective_20261120/independent_artifacts/archive_counterexample.py
```

The artifact probe reconstructs the exact source dataset, verifies the approved writer activation and real command/fit chronology, checks every saved hash, and performs four deterministic native artifact-construction replays in memory. It stores no replacement fitted artifacts and performs no scoring or model selection. It also checks real-artifact numerical kernels against independent Gamma–Poisson arithmetic. The intervening-game regression substitutes a native M0 stub and issues no genuine forecast.

The harmless archive counterexample creates a temporary fake archive with one script printing a fixed hash and no source/model inputs. The original verifier accepted it; the repaired trusted verifier must reject it. Its original and repaired raw streams remain separate. Final legitimate-archive and actual forecast tests require the later accepted runtime/registry/cohort and actual forecast archive; they are outside this model admission decision.

Exact tested commits, raw argv and streams are in `COMMANDS.json`, `ARTIFACT_RESULTS.json` and the counterexample outputs. `ARTIFACT_ADMISSION.json` contains the actual independent admission time and exact model/source/receipt pins. Its raw SHA256, not a caller-authored reviewer name or approval label, is the code-reviewed admission reference. The review packet SHA256SUMS hashes every retained file except itself.
