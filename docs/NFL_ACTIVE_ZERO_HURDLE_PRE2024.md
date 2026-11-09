# NFL active-player zero-hurdle challenger — strict pre-2024 validation

Status: **research only**, isolated branch `chatgpt/nfl-nflverse-unified-active-zero-hurdle`. Production rankings and 2024 validation history remain unchanged.

## Objective and null hypothesis

Our combined team-XGBoost + hierarchical Bayesian allocation + Monte Carlo model already represents possible zero player events from finite, correlated team opportunities. The **incremental active-zero hurdle** must demonstrate improved out-of-sample Brier/log-loss and measured conditional-zero calibration on the **exact same frozen 2024 research contracts** before any use in rankings. Do not assume high Under success from high zero rates.

The hurdle labels are `1{player recorded exactly zero events | player had confirmed positive game snap exposure}`. **DNP, no snaps, nonparticipation, void, or an unmatched 2024 observation are not zeros**. A published sportsbook market, quote, and event-day active confirmation remain separately required.

## Registered zero-stage markets

- Direct conditional-zero model: **targets, carries, tackles + assists, solo tackles, tackle assists**.
- Derived/no independent zero gate: receptions and receiving yards inherit zero through targets/catches; rushing yards inherit zero through carries.
- Pass attempts/completions and passing yards do not get an emergency-only gate. Such a gate would require reliable pregame QB participation evidence.
- Other NFL markets (touchdowns, QB hits, passes defended) remain excluded from ranking by production policy.

## Pre-2024 data contract

**Dec 31, 2023 inclusive is the final training date.** All games actually played on or after 2024-01-01 are forbidden, including the January 2024 games belonging to the 2023 season. `nflreadpy.load_player_stats`, `load_snap_counts`, `load_schedules`, `load_pbp`, `load_nextgen_stats`, `load_injuries`, and supported `load_participation` are unified in the source gateway and upstream collector.

- Prior *three actual appearances*: player snap-exposure mean and newest minus previous-two snaps. This is observed workload, not a verified snap-share without team snaps as denominator.
- Prior *three appearances* in **2021–2022 NGS participation**: player on-field fraction of team QB dropbacks. This is **not true routes run**. A drop from 70% to 30% is represented as -0.4 only when all three as-of participation rows are available. Missing/stale observations remain NaN with a missing-coverage flag.
- Opponent offense historical **11-personnel** rate (1 RB, 1 TE, 3 WR), used as a defensive matchup input for tackles. The 2024 opponent's forthcoming personnel mix is NOT known in a strict pre-2024 evaluation.
- `load_injuries` **Questionable/Doubtful** flags only from official `date_modified` preceding the subject game. `Out` excludes the forecast rather than being mislabeled as a profitable zero. An active-but-emergency-only designation or early-drive exit is **not** an independently sourced public NFLverse field.
- **2023+ FTN participation is released after the season and therefore quarantined**, even though 2023 game dates precede Jan 1, 2024. The publicly obtained FTN 2022/2023 charting carried post-cutoff retrieval timestamps and is also excluded. Sources: nflverse participation and FTN data dictionaries and release schedule.

## Model training

A cross-market `XGBClassifier(binary:logistic)` predicts `P(observed zero | confirmed prior snap exposure, selected market, feature vector)`. The classifier is tuned by Optuna TPE with expanding chronological 2021–2023 folds. A one-dimensional Platt recalibration is optionally fitted **only from pre-2024 out-of-fold probabilities**; calibration coefficients are SHA-archived alongside the model. Hyperparameters, features, and calibration never change in the 2024 evaluation.

The model is NOT trained to infer a fixed injury, 11-personnel, or route-drop multiplier. Any substantial influence of such a feature must emerge from pre-2024, chronologically validated evidence. Missing signals cannot become fabricated positive evidence.

## Posterior predictive integration

The existing team XGBoost forecasts pass/rush totals with dispersion. An independent 2024-frozen hurdle-enabled Monte Carlo challenger adjusts Bernoulli zero allocations to targets and carries, moving events between eligible players and the explicit unlisted-player bucket so every simulated team's opportunities are conserved exactly. Direct defense totals may be zero-conditioned while solo/assists remain consistent with the total.

This is a distinct **paired challenger** against the original no-hurdle Dirichlet allocation, on the same synthetic lines and exactly the same frozen candidate universe. Receptions/yardage are generated after the opportunity allocation, not subjected to a second hurdle.

**Limitations:** the hurdle transport step changes the positive-count tail and still requires prospective score calibration. PBP-derived route-presence rates are not certified routes. A large injury-based zero boost could simply learn historical selection bias; restrict effect assessment to proper chronological holdouts. Active 2024 roster and injuries are absent by design.

## 2024 holdout gates

1. Confirm all code, sources, feature observations, model-fit labels, CV, and Platt calibration exclude events dated on/after 2024-01-01.
2. Fit team XGB and hurdle on 2021–2023 pre-cutoff histories only.
3. Generate all **18 weekly 2024 prediction packets** using only the known 2024 schedule and pre-2024 model state. Hash and lock each packet before opening any 2024 player result.
4. Verify packet identities, source/feature timestamps, model and calibration SHA256 digests.
5. Only then read 2024 player statistics for settlement and report **matched/unmatched**, per-market and weekly Brier, log-loss, calibration buckets, zero-vs-positive sensitivity, coverage and Under share on identical contracts.
6. **No deployment** unless the hurdle improves objective out-of-sample proper scoring and conditional-zero calibration with acceptable robustness, valid offers, and real availability. There is no forced top-ten quota and no asserted 90% hit rate.

## Implementation files

- `scripts/nflverse_pre2024_hurdle_gateway.py`
- `scripts/nfl_pre2024_active_zero_hurdle.py`
- `scripts/nfl_pre2024_hybrid_bayesian_mc.py` (optional hurdle, baseline preserved)
- `scripts/nfl_pre2024_team_xgb_hybrid_replay.py` (all-18-week frozen paired comparison)
- `tests/test_nfl_pre2024_active_zero_hurdle.py`

Real-data smoke audit initially uncovered numeric play-ID representation mismatch (PBP `40.0` vs participation `40`), fixed by canonical integer IDs. Following correction, the 2021–2022 NGS-participation gateway returned **1,319 historical player IDs** with dropback-presence data, **32 offense personnel team profiles**, and **15,814 pre-2024 injury player-week records**; no 2023 FTN participation was used.

The pre-2024 hurdle/2024 SHA replay must report real fit and settlement status from Deepnote; do not infer results from compilation or tests.
