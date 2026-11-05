# Frozen 31-market campaign: SOG, then NFL

Status: configured in GitHub workflow for **successor jobs**; active NHL SOG run is unaffected.
Campaign: `week-20261102`. Statistical model SHA and population history SHA remain pinned by the original launch request.

## Sequence

- Logical index **0**: NHL shots on goal (already sampling; never relaunch or alter this run).
- Logical indices **1–16**: all **16 NFL** markets, starting with **pass attempts**.
- Logical indices **17–19**: NHL hits, blocked shots and goalie saves.
- Logical indices **20–30**: all **11 NBA** markets.

The original catalog in frozen `scripts/precision_campaign_catalog.py` remains unchanged. `scripts/precision_campaign_route.py` maps logical indices to immutable source indices and includes source identity, routing schema and SHA256 of the ordered catalog in `routing_receipt.json`. Never confuse the logical market index with the original frozen source index when restarting or auditing a run.

The workflow stages the routing helper from the *triggering main checkout*, checks a pinned git-blob SHA and runs offline tests **before** it checks out the frozen model commit. It then runs the staged router from the runner temporary directory, loads frozen identities from the original catalog, and writes only corresponding `SPORT`, `STAT`, `TRAIN_FROM`, `FIT_ID` and next logical index values into the GitHub job environment. It does not change PyMC model code, priors, data, eligibility rules, cutoff or sampling budget.

**Scheduling gate remains unchanged:** the next logical market is automatically dispatched only when the prior market's full four-chain fit and final convergence diagnostics pass, and the workflow's output/upload steps succeed. A failed, nonconverged or cancelled market stops automatic progression. No automatic skip, restart, restart-from-checkpoint, or training cancellation has been introduced.

## Early two-chain inspection

The separately pinned observational monitor now emits **one** `NUTS_PAIR_PREVIEW` log event when two chains finish warmup and all posterior draws. It also saves a `two_chain_preview.json` report under the per-market training-report directory. The preview is based on a small bounded subset of global parameters from the PyMC draw callback, not the complete posterior.

It attempts provisional rank-normalized R-hat and bulk ESS with the existing ArviZ statistics stack, and also includes chain means and sampler-health summaries. If callback point values or diagnostic libraries are unavailable, the preview explicitly records why; **training continues unchanged**. The report is provisional, may omit high-dimensional effects, does not certify convergence or predictive quality, and cannot change ranking/validation gates. Final four-chain diagnostics remain mandatory.

The preview is printed during sampling and saved locally; the existing workflow artifact upload occurs **after** the whole job finishes. This is not a NUTS state checkpoint and does not make sampling resumable.

## Predictive validation of NFL

A shorter NFL dataset may reduce fit time, but 17 games per team and NFL model dimensions do not guarantee a specific speedup. The current frozen NFL models do **not** include passer read-progression or defensive coverage features. They use per-game outcome, workload, player/position/season/opponent/home effects. Passing-read extensions require a separately validated feature pipeline and model.

**Convergence is not predictive performance.** The current campaign uses `MODE=pregame_fit` and does not automatically score held-out game outcomes versus betting-market lines. Forecast-vs-final-scores calibration and Brier/log loss require a separate evaluation with time-safe held-out games and aligned prop lines; do not interpret faster NUTS convergence as a predictive win.
