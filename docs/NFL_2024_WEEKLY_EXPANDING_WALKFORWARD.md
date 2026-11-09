# 2024 NFL sequential training replay

**Status:** the 2024 walk-forward challenger is research-only and isolated from production. Execution: [Deepnote notebook](https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/NFL-2024-strict-rolling-weekly-training-freeze-week-reveal-results-refit-XGBoost-zero-hurdle-report-accuracy-27c7d296022047f4aef8b981cdc32629). New output root: `pickem_runs/2024_walkforward_expanding_online_v1`.

## Temporal protocol

1. Start clean with pre-2024 player/PBP/NGS history, pre-2024 Optuna hyperparameters, pre-2024 XGBoost model weights and pre-2024 out-of-fold Platt calibrator; 2024 schedule used solely as game fixtures.
2. Before each week's first game, compute the candidate player roster from **only previously observed seasons/weeks**, compute team opportunity XGBoost features with exact weekly as-of date, generate both Bayesian-MC + active-zero hurdle and a no-refit comparator on the same synthetic contract, and write a SHA-locked `FROZEN/week_NN.json`.
3. Only after Week 1 is locked may the separate result-oracle process download the 2024 player stats, snaps and PBP into an isolated private vault. Before grading Week N, a separate subprocess verifies Week N's forecast SHA and exposes only Week N records. Model code never indexes raw future-week outcomes; this is a procedural firewall, **not** independent cryptographic sealing against someone who already has the public 2024 season.
4. Grade matched props without treating missing observations as losses or zeros. Write the full Week N settlement file referencing the original immutable SHA.
5. Append the revealed Week N positive-snap player and team game stats, build hurdle features from pre-Week-N observations, and **refit both team-volume XGBoost estimators and active-zero XGBoost classifier** on the expanding dataset. Keep pre-2024 Optuna hyperparameters and Platt calibration frozen; the Bayesian allocations update from the appended player history automatically.
6. Save new model SHA receipts, training sample counts, model metrics and the weekly report. Repeat from Week 1 through Week 18 in chronological order. Final summary contains scores and learning progression.

## Model comparators

- `p_over_static_player`: original, non-updating December 2023 player prior, evaluated on the **same current-week synthetic line** where a matching historical player exists.
- `p_over_player_prior`: player prior that incorporates prior revealed 2024 games.
- `p_over_no_refit`: 2024-updated Bayesian/player state but XGBoost team and active-zero weights frozen at pre-2024; this directly isolates weekly parameter refitting.
- `p_over`: online trained XGBoost team totals with Bayesian MC, without hurdle.
- `p_over_hurdle`: online trained team XGBoost + Bayesian MC + online trained active-zero hurdle.

**Limitations:** The 2024 post hoc replay cannot prove 2024 feature *publication* timing or genuine 2024 pregame injury/roster information; online roster at Week 1 is inferred from 2023 and later rosters only from previous positive-snap games. NGS remains strictly pre-2024, not retroactively ingested from 2024. The lines are synthetic, not sportsbook odds. This is online historical evaluation, not a prospective betting performance guarantee. The original 2024 frozen audit directory is retained for independent reproducibility but **not used as a 2024 training source**, since only the separately verified pre-2024 model weights and hyperparameters are loaded.

## Validation gates

- All files in the new root are created with write-once semantics; prior runs are not overwritten.
- Same-week and future-week player labels in feature state are rejected; oracle refuses to reveal an unlocked week.
- Hurdle learns zeros only from positive-snap exposures, never DNP.
- Initial 5 unit tests passed before run start. Weekly updates preserve model hashes and outcome references.
- There is **no automatic production promotion**. Compare same-contract direction accuracy, Brier and probability bias across weeks, and test whether refitting truly beats the no-refit counterfactual.
