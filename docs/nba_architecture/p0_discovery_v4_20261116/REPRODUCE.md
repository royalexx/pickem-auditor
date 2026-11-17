# P0 root-discovery import repair — v4

Authority: PA-V25-MASTER-2026-11-09 / v1.1. This isolated test-custodian change preserves every inherited G0 implementation, fixture and assertion byte. It adds root-level compatibility exports for the same canonical golden fixtures and shared test helpers; it does not suppress failures or collect canonical tests twice.

At baseline P2 SHA `7ca4269c98a27def485eaa8122ea7148cd0c2c0a`, root discovery reproduced ten golden_v2 errors. Fixing that name exposed five sibling-helper errors; fixing two helper exports exposed the remaining `edit` helper. Every intermediate red log is retained. The complete repair returns zero import errors and 1,878 discovered objects at that owner base; the additional permanent regression contributes one more object after it is added. Test counts may increase with other owner additions.

The permanent regression compares the exact canonical NBA test IDs under root versus dedicated discovery and rejects duplicates. Run:

```bash
python -m unittest discover -s tests -p test_nba_root_discovery_v4.py -v
python -m unittest discover -s tests/nba_architecture -v
python -c "import unittest; loader=unittest.TestLoader(); suite=loader.discover('tests'); print(suite.countTestCases()); print(''.join(loader.errors)); raise SystemExit(bool(loader.errors))"
```

`receipt.json` pins implementation commit and all exact-commit commands/output hashes. Ten relevant authorized offline suites were read before invocation: external fetches are mocked, archive restoration uses newly generated synthetic bytes, and the blend optimizer fixture is synthetic. Compilation and shell syntax checks also pass. Unrelated root test bodies, historical evaluation and NUTS sampling were not executed. This is root import/discovery and bounded offline verification, not certification of full repository CI.

Independent P6 review is pending. Rollback by reverting the five added test-support files; preserve these receipts and failed executions. No schedule, production model or gate was changed.
