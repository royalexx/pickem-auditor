# Full-slate forecasting before ranking

Status: **implemented for existing daily A/B and independent shadow forecasters**. This is an inference-scope and audit change, not a deployment of the proposed future ensemble or weather-conditioned Engine B.

## Contract universe and stage order

1. `fetch_slate.py` collects every player/stat supported by its feeds for games in the requested slate and obtains matching two-sided PropLine prices. `market_coverage_audit.py` independently reports missing/unsupported provider markets.
2. `prepare_pipeline` builds **both over and under** for the primary comparable price line of **each** player/stat with a usable, source-verified game-history distribution. There is no top-10 or researcher-candidate whitelist. An unsupported market, an unpriced player, an incomplete history, an already-started game or an invalid input is **not assigned a made-up probability**.
3. `jobs.run_pipeline_batch` attempts every remaining prepared contract, retaining one explicit `forecast` or `unavailable` record per input in `reports/all_prepared_props_attempts.json`. This stage remains the production **70% historical Engine A / 30% historical workload-and-conversion Engine B** blend under its existing reliability gate. Weather and other game context retain their current source-verification/risk checks; the proposed trained weather-conditioned B and multi-model ensemble are not yet production.
4. Bayesian A, Bayesian B, and the NUTS research adapters read the **full frozen snapshot**. Missing model support, incomplete peer data, insufficient convergence, no matching player or unverified kickoff are shown as **unavailable**; challengers are never silently treated as production consensus.
5. `slate_model_report.py` constructs one row for every snapshot and every model column **before** `slate_candidate_ranking.py` produces a top-10-per-sport **display**. The full JSON/CSV report is not truncated to the top 10.
6. **Required deployment gate:** `slate_forecast_scope_audit.py` reconciles the latest frozen run, the full comparison, each model column, the pre-shortlist attempt receipt, and the top-10 subset. Any missing/duplicate contract, missing model status, fabricated unavailable probability, run mismatch or unrelated ranked pick **fails publication**.
7. The immutable shared live-data archive is published **after** this coverage audit passes. Tomorrow's special 7 a.m. Sunday pregame run and normal afternoon runs use the same notebook flow.

## What 'all props' means today

- All **source-supported, eligible, price-matched player–stat contracts**, each in both directions at its primary quoted line, are considered. Both unranked and ranked predictions are archived and comparable.
- This is **not** currently every alternative market threshold. The primary-line collector can receive other quote levels, but the current prediction contract and ID scheme use a single canonical line per player/stat. `slate_forecast_scope_audit.json` now counts those alternate levels explicitly as `alternate_quoted_line_levels_not_forecast`. Supporting full alternate lines would require new immutable per-line identifiers, odds/settlement tests and source reconciliation before activation.
- Unsupported provider markets (for example the Propline NHL hits feed), absent prices, insufficient game-history statistics and models that have not been trained/converged are **reported as gaps**, not silently substituted.
- Neither the top-ten shortlist nor the limited research triage queue restricts the A/B, empirical Bayes or eligible NUTS source-contract forecasting universe. The top ten is only where detailed written scouting is prioritized.
- This audit does **not** imply Engine B is weather-adjusted or that all empirical Bayes/NUTS models have a usable posterior for all players/markets. Its scope guarantee is **every available contract is attempted and every model is represented with a forecast or reason**.

## Run receipts

- `reports/market_coverage.json`: provider, sport and stat availability.
- `reports/all_prepared_props_attempts.json`: pre-top-ten attempted contracts and why any failed.
- `reports/slate_forecast_scope_audit.json`: full exact-contract reconciliation, per-stat model forecast/unavailable coverage, source exclusions and alternate-line count.
- `slate_model_comparisons.json` and `.csv`: all frozen contracts; `slate_top10_evidence.json` is only the research view.

Regression tests: `tests/test_all_prepared_prop_attempts.py` and `tests/test_slate_forecast_scope_audit.py`, run via connected Deepnote before deployment. No Dell NUTS sampling configuration is modified.
