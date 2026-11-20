# Reproduce exact engineering transport

Use the reviewed reader/CLI/input/code and artifact pins in DECISION.json. The reader implementation is73a07497212d5cf04a5fce507bb5a32cebcde34a; later source/document publication and review commits preserve its bytes.

```sh
python scripts/nba_complete_predictive.py read-j --output /tmp/independent-j-c-fresh
python docs/nba_architecture/complete_predictive_20261120/independent_j_c/review_probe.py
python docs/nba_architecture/complete_predictive_20261120/independent_j_c/closure_counterexample.py
python docs/nba_architecture/complete_predictive_20261120/independent_j_c/outcome_root_control.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_j_c/SHA256SUMS
```

The probe compares its direct reader against the preserved public_cli/RESULT.json. The sample-result payload is deterministic; its command receipt and newly generated RESULTS carry actual new timestamps. Preserve original receipts before reproduction. The closure counterexample executes only a preserved old reader snapshot against the same genuine frozen artifacts; it simulates a changed helper read without writing implementation files. Mocked root resealing in deeper tests is a rejection control, never a new admission. No run-j, compile-j, fitting, new forecast issuance, network fetch or outcome scoring is part of this workflow.
