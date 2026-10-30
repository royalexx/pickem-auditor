# NHL context challenger: architecture and local training runbook

Status: implemented research challenger, **not a promoted or calibrated model**.
The existing converged saves posterior and daily ranking paths are unchanged.
Python/PyMC remains the working implementation; no R migration, GPU dependency,
or changes to Engine A/Engine B blending are part of this work.

## Data boundaries

`scripts/nhl_context_data.py` stores an atomic completed-game bundle containing
three independently keyed tables. This keeps game ingestion transactional while
separating the entities used by the models. All keys are official game/team/player
identities; a player can change teams without changing player ID.

| Entity | Implemented fields | Missing fields remain explicit |
| --- | --- | --- |
| Team/game | SOG for/against, goalie shots against, hits, blocks, home/away, actual duration | xG, situation splits, shot locations, tactical labels |
| Skater/game | TOI, SOG, hits, blocks, F/D position, team/opponent | PP role, shifts, individual xG, injury history |
| Goalie/game | Verified starter flag, TOI, shots faced, saves, goals allowed | Shot-level quality, expected role/pull risk, GSAx |
| Matchup/snapshot | Pregame identities, snapshot timestamp, sourced starter status, injuries payload | No invented lineup confirmation or starter probability |

Every bundle retains the original boxscore SHA256 and retrieval time. PBP-derived
attempts retain a separate source digest. Repeated ingestion is idempotent;
revised sources require an explicit new dataset/review instead of silent edits.
The collector also preserves the original payloads as compressed,
content-addressed source archives and verifies them on resume. Keep these local
or in durable data storage; the new CLI does not push large histories to Git.
Zero-minute goalies are not appearances. Saves + goals allowed must equal shots
faced. Team SOG and goalie shots are **not interchangeable**: empty-net and
unassigned shots remain separate. Regulation, sudden-death OT and shootout game
duration are distinguished; shootout attempts are excluded from attempt counts.

The collector uses the existing official-NHL stdlib HTTP client. It does not
request odds or consume sportsbook API credits. `--with-attempts` fetches PBP for
every game; it is required for the blocks opportunity experiment. Unresolved
shooter/blocker identity fails closed. Missing counts never become zeros.

`save_matchup()` is an integration contract for the existing pregame research
collectors. This change does not pretend to have collected historical injuries
or starting-goalie announcements. Current training is conditional on appearing,
and saves training is conditional on starting. A future live adapter must require
the appropriate pregame evidence. Never multiply expected saves by start
probability and compare that reduced mean to a conditional-on-start prop.

## Time and feature contracts

Two availability policies are deliberately different experiments:

- `recorded`: a historical record is eligible only after its actual first
  recorded retrieval time. This supports prospective collection/replay.
- `retrospective_next_day`: core backfilled boxscores become eligible 12 hours
  after game start. This is a conservative operational approximation, **not
  proof of historical publication time**. Statistical corrections can still
  cause revision bias. Label all such evaluations retrospective.

Both policies also exclude the target game and later game starts. Training
targets must be available before the training cutoff, not merely have an earlier
start. Timestamps require timezones. Cutoffs and holdout endings are exclusive.
No random train/test split is used. Full-season aggregates from the future, actual
tonight minutes, tonight saves, tonight shots, final starter labels, current odds
and final lineups are not pregame covariates.

Implemented covariates: home, capped difference in days since last observed game,
player's last-five workload (with three position-prior pseudo-games), and last-20
team/opponent opportunity rates. Rates are exposure-weighted and shrink toward
fixed priors with five pseudo-games. Venue deviations receive ten pseudo-games of
shrinkage toward the corresponding overall rate. Standardization uses training
rows only. The same feature function serves training and forecasting.

| Market | Opportunity covariates | Likelihood |
| --- | --- | --- |
| Saves | Opponent SOG generation and own-team SOG allowance, venue deviations | NB shots faced; beta-binomial saves conditional on faced shots |
| SOG | Own-team SOG generation and opponent SOG allowance | NB SOG with player TOI exposure |
| Hits | Own-team and opponent hit environment, venue deviations | NB hits with player TOI exposure |
| Blocks | Own-team credited blocks and opponent **attempts**, venue deviations | NB blocks with player TOI exposure |

These are observable opportunity proxies, **not measured coaching schemes**.
Hits has no reliable count of all hit opportunities in the implemented data;
do not describe its NB rate model as a measured attempts-to-hits conversion model.
Situation-specific PP/PK/5v5 models, Corsi/Fenwick splits, travel distance,
projected lineup effects and measured tactics remain extensions, not completed
features. Rest currently uses completed observed history, not a full schedule.

Optional `--feature-set xg --xg FILE.json` adds opponent and own-team lagged
xG/SOG quality covariates to **save conversion**. The input is a JSON list of rows
with `game_id`, `team`, `xgf`, `xga`, `provider`, `model_version`,
`model_trained_through` (timezone timestamp), `available_at` (timezone timestamp),
`source_url`, `source_sha256`. A single provider/version is required per experiment.
Both availability and model training vintage must precede the prediction. Missing
quality history is an omission, never fabricated average xG. A downloadable
current xG model retrospectively applied to old games is not automatically a
valid point-in-time feature. A provider adapter and permission/coverage review
are still needed before collecting MoneyPuck or another provider's data. No
unverified historical xG has been used in this implementation.

## Generative model and uncertainty

Player effects on workload and rate/save ability share an inferred LKJ covariance.
Team generation and suppression effects are separate, centered, noncentered
hierarchies. Multi-season data add centered season workload and rate effects;
single-season fits fix those effects to zero without claiming to identify a
season variance. An unseen season requires an identified multi-season hierarchy.
Unseen players or teams require a future verified mapping rather than guessing.

The exposure model is normal on continuity-corrected logit(TOI/game duration).
Forecast exposure is transformed back and bounded by simulated game duration.
Durations are sampled from unique training games, avoiding player-row weighting
of OT frequency. This is a first bounded model, not a claim to model the causal
process of injury, early goalie removal, empty-net pulling, or overtime.

For saves, the joint likelihood factors as:

`p(minutes | context, goalie) × p(shots faced | minutes, teams, context)
 × p(saves | shots faced, goalie, supported quality context)`.

There is no extra team-SOG likelihood reusing the same goalie shots. Future
minutes and beta-distributed game save probability are marginalized. Conditional
NB/binomial thinning gives an exact NB saves distribution at each latent draw,
so the forecast integrates count CDFs rather than unnecessarily sampling shots
and saves again. Posterior parameters always retain their joint chain/draw pairing.
Outputs include over, under, push, expected exposure, expected saves, outcome
intervals and an integration MC error. That MC error is **not** an ESS-adjusted
posterior error or calibration interval. Conditional-probability intervals include
latent game variation, not just parameter uncertainty.

Remaining model risks to test: exposure distribution tails, endogeneity of early
pulling and poor performance, persistent goalie skill across seasons, shared
game pace dependence between the two goalies, and quality/volume dependence.
Player/team season-varying effects, goalie shot-quality calibration and exposure
mixtures should be added only after the first ablations establish a need.

## Reproducible local sequence (Windows PowerShell)

Use the existing Windows Python/G++ setup in `PRECISION_NHL_FULL.md` and
`PRECISION_LOCAL_BAYES.md`. Keep each experiment in a new output folder. Run one
new challenger model at a time initially; the existing four-market campaign can
already occupy the laptop. No large training job was dispatched by this change.

```powershell
python -m pip install -r requirements-joint-bayes.txt
python scripts/history_warehouse_load.py

# Discover official game IDs from the existing saves history; this does not
# verify schedule completeness or reconstruct absent team stats from saves.
python scripts/nhl_context_train.py plan --train-from 2023-10-01T00:00:00Z --until 2026-10-29T12:00:00Z --out reports/context_game_ids.json

# This can take hours for full history. It resumes without refetching saved games.
# Include PBP from the start if blocks is a later target.
python scripts/nhl_context_data.py --game-ids reports/context_game_ids.json --with-attempts
python scripts/nhl_context_train.py audit-collection --expected-game-ids reports/context_game_ids.json --out reports/context_collection_audit.json

# Freeze a small, TRAINING-ONLY latest-200-game cohort first.
python scripts/nhl_context_train.py freeze --train-from 2023-10-01T00:00:00Z --cutoff 2026-09-01T00:00:00Z --market saves --feature-set context --policy retrospective_next_day --pilot-games 200 --out reports/context_saves_pilot

$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python scripts/nhl_context_train.py fit --folder reports/context_saves_pilot --chains 4 --cores 2 --draws 1500 --tune 1500
python scripts/nhl_context_train.py evaluate --folder reports/context_saves_pilot --until 2026-10-29T12:00:00Z --line 25.5
```

An existing bundle collected without attempts cannot be silently replaced with
an enriched bundle. For a separate blocks dataset, pass `--root PATH` consistently
to collector and freeze; keep source revisions as separate experiments.

Archive `design.json`, `preflight.json`, `manifest.json`, `posterior.nc`,
`frozen_bundles.json`, `frozen_xg.json`, `training_rows.json` and holdout outputs.
Do not commit large posterior files to Git. The manifest records source/design
digests, posterior SHA256, script hashes, code SHA, versions, seed and runtime.
Evaluation rechecks the hashes and recomputes diagnostics. Frozen input universes
mean a later warehouse backfill cannot rewrite a previous holdout's feature set.

## Training and evaluation campaign

1. **Core collection/preflight:** verify schedule coverage separately against the
   official schedule, team-game pairs, goalie starts, count reconciliation,
   missingness by season/team, and attempt completeness. The game-ID plan is not
   a completeness certificate. Start with recent completed seasons, preserve
   older history for subsequent window tests.
2. **Small pilot:** latest 200 training games, four chains, two concurrent chains,
   1,500 tune + 1,500 retained draws. Record wall time, peak RAM, and ESS/second.
   A limited cohort does not validate all goalie/player populations. Increase
   draws/warmup or reparameterize when diagnostics fail; never lower the gates.
3. **Ablations on the same cohort:** `base`, `context`, then `xg` only after valid
   historical provider data exist. The base model shares the new generative
   architecture, so it is not identical to the old converged posterior. Use a
   common evaluation population and report all coverage differences. Test
   5/10/20-game form choices as separate training-only development experiments,
   not by selecting the best test-period result.
4. **Full local training:** remove `--pilot-games`, initially use the latest 2–3
   complete seasons. Extend to the restored 2018–2026 history only after pilots
   establish RAM/runtime feasibility and older years add holdout value. Fit
   saves first, then SOG, then blocks with complete attempts, then hits. Keep
   a single market per fit, with stat-specific priors and opportunity definitions.
5. **Walk-forward validation:** use multiple predeclared seasonal cutoffs (for
   example train through 2024-09-01, test the 2024–25 season; train through
   2025-09-01, test 2025–26; retain October 2026 as a final recent test). Construct
   every rolling feature as of each game, permitting earlier *completed and
   available* holdout games as context while keeping the fitted posterior frozen.
6. **Direct incumbent comparison:** refit the old hierarchical model at each
   identical cutoff. Today's posterior cannot fairly evaluate earlier games.
   Export its predictions on the exact same player/game/market/line rows, with
   `target`, `start_time`, `training_cutoff_exclusive`, `q_over`, `q_under`,
   `q_push`. Pass the JSON list via `evaluate --incumbent-predictions FILE.json`.
   The comparator rejects missing/extra rows, date/outcome mismatches and
   differing training cutoffs. It does not silently compare a convenient subset.
   `nhl_context_incumbent.py` provides the exact-cohort refit/score adapter: it
   converts the frozen training rows to the existing model's schema, preserves
   IDs/counts/minutes/source hashes, and uses the same all-stochastic, bulk+tail
   ESS and geometry gates. At least 12 training players are required by the
   existing model. It is a refit of the old architecture on the common cohort,
   rather than the already published all-appearance posterior.
7. **Scoring:** paired Brier score and binary log loss on nonpush outcomes,
   normalized for pushes; count predictive log density, 90% predictive coverage,
   calibration bins and Brier-difference bootstrap intervals clustered by game.
   Report coverage/omissions, and inspect home/away, team, goalie, season, early
   season and workload subgroups. The built-in gamma-Poisson baseline is clearly
   labeled a transparent control, not the existing hierarchical posterior.
8. **Market and promotion evidence:** the CLI's fixed line is a research threshold,
   not an archived sportsbook quote. Add immutable historical quote snapshots
   before claiming market advantage. Require prospective shadow results,
   calibrated forecasts and existing lineup/source gates before any ranking
   integration. Disagreement with market probability is not itself a rejection
   criterion. This work does not change provisional 70/30 Engine A/B weights.

All stochastic variables must pass R-hat <= 1.01, bulk **and tail** ESS >= 400,
zero divergences, minimum chain BFMI >= .30, no max-tree-depth hits, and at least
four chains. Constant single-season deterministic offsets are not treated as
random parameters. Passing convergence alone never enables ranking.

After the challenger has produced `holdout_predictions.json`, run the fair
incumbent comparison locally:

```powershell
python scripts/nhl_context_incumbent.py fit --challenger-dir reports/context_saves_pilot --incumbent-dir reports/context_incumbent_pilot --chains 4 --cores 2 --draws 1500 --tune 1500
python scripts/nhl_context_incumbent.py score --challenger-dir reports/context_saves_pilot --incumbent-dir reports/context_incumbent_pilot
python scripts/nhl_context_train.py evaluate --folder reports/context_saves_pilot --until 2026-10-29T12:00:00Z --line 25.5 --incumbent-predictions reports/context_incumbent_pilot/holdout_predictions.json
```

## What was actually verified here

See `NHL_CONTEXT_AUDIT_2026-10-30.md` for executable results and limitations.
Synthetic sampling tests validate code and probability bookkeeping, not predictive
superiority, real NHL calibration or real source coverage. Official NHL live HTTP
access from this workspace returned 403, so production-shaped adapter tests are
offline fixtures and the real context backfill must run on the local machine.
