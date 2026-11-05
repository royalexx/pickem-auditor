# Pick'em Auditor: Deepnote to GitHub shared live-data pool

Status: Manual Deepnote inference/settlement and future historical-training import are implemented, but the first authenticated end-to-end publication still requires Deepnote secrets. No automatic NUTS model promotion.

## Branches
- Code: main.
- Existing historical calibration: data/shadow-calibration, unchanged.
- Existing archived population warehouse: existing historical data source, unchanged.
- New append-only live data: data/live-observations, at data/live_pool/YYYY-MM-DD/{afternoon,morning}/SHA256.json.gz. Each content-addressed bundle is committed using the GitHub Contents API and verified against the SHA-256 of the compressed bytes.
- Execution: Deepnote Free Basic CPU, no Dell, no scheduled GitHub Actions.

## Encrypted Deepnote environment variables
Use Integrations -> Environment variables, attach to Pick'em Auditor Daily Cloud Inference:
1. GITHUB_TOKEN: fine-grained private-repository Contents read AND write. The code writes only to data/live-observations.
2. PROPLINE_API_KEY: used for afternoon two-sided bookmaker odds. No paid odds are needed for morning settlement.

Never paste these values into notebook cells, logs or chat.

## Afternoon
- Restore original calibration history from read-only branch.
- Collect NBA/NFL/NHL slate, player history, market quotes, official lineup context.
- Run production Engine A and B, guarded blend, empirical-Bayes shadow A/B, Monte Carlo, and research verification.
- Append immutable original pregame forecasts, shadow sidecars, market quotes, slate and source metadata to private Git.
- Never rewrite or hindsight-adjust the original prediction.

## Following morning
- Restore yesterday's original, timestamped pregame forecasts from Git, not a reforecast.
- Settle them against actual box scores. Include partial/unresolved outcomes explicitly.
- Collect only completed NHL official gamecenter, NBA ESPN and NFL current-season weekly/snaps source rows for yesterday.
- Normalize long-format 31-category player-game observations with game/player/position/team IDs, workload, measured value, original source URL and SHA.
- Preserve original NHL/NBA and day-filtered NFL source payloads together with normalized rows.
- Report proper Brier and log-loss versus actual wins/losses; exclude pushes and missing outcomes from binary scoring.
- Append settlement/source population to Git. No training in this step.

## Future Bayesian training
After restoring the existing warehouse but before model fitting:
    python scripts/live_pool_exchange.py import --root . --before 2026-11-06

The cutoff is EXCLUSIVE. If the model was frozen Nov 5 it cannot use observations from Nov 5 or later. Models holding out a historic date also cannot import post-cutoff observations.

Normalized accepted observations merge into existing per-sport/stat/season population shards via the shared population_history.persist routine. Deduplication identity is (sport, stat, game_id, player_id). Repeated measurements from multiple providers count as ONE game. Conflicts in stats/workload/context are rejected for human review rather than averaged or counted twice. Source URL and digest remain attached to training rows. Missing/incomplete data is never treated as observed zero.

The existing manual historical Bayesian workflow imports this shared data before window preflight. The currently running frozen 31-market NUTS campaign is NOT changed. Future precision training must explicitly import and freeze the shared data as part of its new campaign; it does not retroactively alter an existing fit.

The daily collector supplements the historical population, not a full substitute for NFL reads or richer game schemes. New providers must pass source-specific validators. A successful training import does not authorize model promotion without convergence and chronological holdout checks.

## Testing and limits
Offline checks:
    python -m unittest discover -s tests -p test_live_pool_exchange.py -v

No source rows have been published yet; the Deepnote GITHUB_TOKEN is not configured. A run only reports published after a successful GitHub upload.

Deepnote Free does not include native recurring scheduling. A ChatGPT scheduled task can potentially launch the connected Deepnote notebook, but this must be tested after credentials are configured; never assume a future automation succeeded without checking its run receipt.
