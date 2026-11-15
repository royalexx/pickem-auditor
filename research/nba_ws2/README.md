# NBA WS2 handoff

Read [REPORT.md](REPORT.md) for the quantitative decision and complete limitations.

This directory owns only conditional minutes, participation semantics, rotation allocation, local adapter assumptions and research evidence. The implementation is `v2/nba_opportunity.py`; tests are `tests/test_nba_opportunity.py`.

Reproduce the pinned historical comparison and source sample from the repository root:

```bash
bash research/nba_ws2/reproduce.sh
python -m research.nba_ws2.benchmark_forecasts
python -m research.nba_ws2.audit_results
python -m research.nba_ws2.write_report
```

`results/report.json` is the corrected matched numerical receipt. `results/audit_receipt.json` records stress regressions, additional clustered uncertainty and the no-adoption decision. `results/initial_unfiltered/` preserves the superseded evidence. `results/source_identity_exclusions.csv` lists every All-Star row excluded by the local adapter. All forecasts and model scores are exploratory shadow research.

Manual prospective capability:

```bash
python -m research.nba_ws2.shadow --help
```

A real future run requires independently supplied, source-backed adapter records. The CLI generates no injury probabilities or roster assertions. The integration fixture is reproducible with `python -m research.nba_ws2.benchmark_forecasts`; it explicitly labels synthetic inputs and creates zero authentic forecasts.

No production module imports this implementation. Rollback removes `v2/nba_opportunity.py`, its test file and this directory. No source schema, collector, outcome likelihood, independent scoring infrastructure, frozen baseline or production schedule changed.
