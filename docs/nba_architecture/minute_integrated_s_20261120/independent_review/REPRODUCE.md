# Reproduce independent numerical review

Reviewed mathematical module: `8730aad9b20926e0de319c1aded94c16972c6592`, raw SHA256 `3e8de1cfa9d95a5e874d62bbb353f3d220d25cd5ab2a8adf1d4a88706dd93bec`. Actual recorded candidate/test execution: `13a5419f2b1765e68f4c170fbbf3638962d934a3`. Independent test snapshot: `f2306ba07ace50986bbacaa6344d9b09494ddf73`. The original PR190 profile and artifacts remain unchanged.

```bash
python docs/nba_architecture/minute_integrated_s_20261120/independent_review/numeric_probe.py
python -m pytest -v tests/nba_architecture/test_minute_integrated_s_v1.py
```

The independent probe recomputes all 56 exposure moments through adaptive algebraically weighted QUAD, checks all means/variances and ordinary-domain probabilities, evaluates 60 count probabilities through independent log-gamma integration, checks the complete 140-attempt ledger, and reproduces the candidate semantic hash from the original frozen parent inputs. It introduces no new model artifact or target outcome and issues no forecast. The inherited parent reader verifies its already admitted artifact bytes by deterministic construction replay; the integrator trains nothing and no holdout is opened or scored.

`RESULTS.json` contains all numerical comparisons, both low-minute domain examples and operation clocks. `COMMANDS.json` contains exact commands/streams and protected PR190 byte comparisons. The saved candidate wire is `../execution/candidate.json`; its full raw hash includes actual computation clocks, while its documented semantic hash excludes those clocks and the hash/domain metadata. That difference must remain explicit in any later archive.

The 256/512/1024 Jacobi differences are empirical convergence diagnostics. These tests provide independent numerical checks for the bounded current profile, not a rigorous general quadrature theorem or full predictive validation. `GATES.md` and `MISSING_MECHANISMS.json` state the full-played, J, C and historical-release gates. Check this review directory with `sha256sum -c SHA256SUMS`.
