# Reproduction and byte domains

From repository root, at reviewed `cec3f5bf` plus these independent review files:

```sh
PYTHONPATH=. python docs/nba_architecture/complete_predictive_20261120/independent_c_profile/profile_probe.py
sha256sum -c docs/nba_architecture/complete_predictive_20261120/independent_c_profile/SHA256SUMS
```

The exact command ran with stdout in tests.stdout and stderr in tests.stderr; four methods passed, eight mutation subcases. This probe invokes existing structural PBP/source parsers and raw byte checks only; it does not fit/re-fit models, issue forecasts, score outcomes or access network data. RESULTS.json records original input body/receipt hashes and the complete twenty-game ledger. Raw HTTP response bodies are the body hash byte domain; capture receipts are original UTF-8 JSON file bytes; forecast SHA hashes the exact saved raw forecast file, independently matching the issue receipt. SHA256SUMS hashes repository file bytes and includes all source/parser/profile/forecast inputs reviewed, as well as independent outputs. The test helper returns process success even on an assertion failure because unittest uses exit=False to save diagnostics; consult raw unittest result rather than shell status. The recorded run is unambiguously four tests OK with no failures.

No source was fetched or backfilled for this review. The historical eligibility conclusion applies to the exact twenty-game source population and actual supplied new-model forecast packet, not to an unbounded search of all possible archives. The target remains unplayed at this review; future evidence must be appended and reviewed separately.
