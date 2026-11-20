# Reproduce the independent protocol evidence

From the repository root, run:

```sh
python docs/nba_architecture/complete_predictive_20261120/independent_protocol/evidence_probe.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_protocol/SHA256SUMS
```

The probe requires the exact raw sources pinned in PBP_POPULATION.json and the protected original source/archive population. It only reads source bytes and emits JSON. It neither imports fitting code nor calls fitting or scoring. The raw successful output and empty stderr are retained. The failed first probe's streams are retained separately; the source of that initial probe differed only in asserting unique actionNumber instead of actionId and lacking the grouped actionNumber diagnostic. Its failure does not indicate a source repair. This packet approves a protocol for implementation; it does not claim the newly authored implementation has passed independent review.
