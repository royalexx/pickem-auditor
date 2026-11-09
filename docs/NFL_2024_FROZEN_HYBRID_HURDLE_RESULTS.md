# NFL 2024 frozen validation: pre-2024 hybrid vs active-zero hurdle

**Research-only. Do not promote to production.** All 18 weeks of 2024 predictions were locked before grading. Freeze model and forecast manifest SHA256: e416676f803022dda60d715a45e4a3206b2fb771f5631fd8859aee57b87e6b41. Training data cut off before 2024-01-01. Scored after fixing a calibration-file extension verifier bug, without any retraining or changed 2024 predictions. Successful Deepnote scoring run: 7747bfe3-65b7-4a7a-b04f-5b92a93344e4; independent read-only audit: 34a661ba-ce3e-42b1-92b2-6b8abffc9b99.

## Data and reproducibility

- Pre-2024: 229,076 player-market training rows, 1,598 team-game PBP aggregates, historical NGS, with FTN archive quarantined.
- Zero-hurdle active-snap fit: 76,802 historical observations, including 12,995 verified zero-stat outcomes. Optuna TPE 8 trials, 3 chronological folds, pre-2024 out-of-fold-only Platt calibration. Internal CV log loss: 0.365974; this is not the 2024 score.
- Team volume XGBoost: fitted pre-2024 pass attempts and rushing attempts, eight Optuna trials each.
- 2024 prediction packets: 66,793 forecasts, 18/18 weeks locked, 26,952 matched/grading-eligible, **39,841 unmatched (59.65%)**. Never turn unmatched into zero or a loss.
- Historical synthetic player lines and 2023-carried-forward, unverified 2024 rosters. No verified sportsbook quotes, so not actual betting performance.

## Overall 2024 matched-sample results

| Forecast variant | Direction accuracy | Brier score (lower better) | Log loss (lower better) | Predicted Under share |
|---|---:|---:|---:|---:|
| Recent-player prior | 56.4633% | **0.247801** | **0.692143** | 69.55% |
| Team XGB + Bayesian Monte Carlo | 56.5784% | 0.255488 | 0.722423 | 82.90% |
| Team XGB + Bayesian MC + hurdle | **56.9754%** | 0.254041 | 0.720351 | 82.12% |
| Always Under | 54.3707% | n/a | n/a | 100% |

The hurdle improves the hybrid's accuracy by **0.397 percentage points** and Brier by **0.001447**, but is **0.006240 worse Brier than the simple recent-player prior**. Approximate 95% intervals from 400 whole-game bootstrap replicates across 272 games: hurdle-minus-hybrid directional accuracy [+0.174,+0.633] percentage points, Brier [-0.001732,-0.001108]; hurdle-minus-prior directional accuracy [-0.148,+1.161] percentage points, Brier [+0.004056,+0.007916] (worse). Same-player cross-week dependence could narrow these intervals artificially. All comparisons use exactly the same matched synthetic offers.

## Per-market 2024 Brier score

| Market | Matched | Prior | Hybrid | Hybrid+hurdle |
|---|---:|---:|---:|---:|
| Pass attempts | 378 | **0.27372** | 0.35274 | 0.35289 |
| Completions | 378 | **0.27691** | 0.32880 | 0.32924 |
| Passing yards | 378 | **0.26392** | 0.31466 | 0.31424 |
| Targets | 2,996 | **0.23742** | 0.24421 | 0.24392 |
| Receptions | 2,996 | **0.24143** | 0.25090 | 0.24982 |
| Receiving yards | 2,996 | 0.25869 | 0.25075 | **0.24862** |
| Carries | 1,176 | **0.25169** | 0.26545 | 0.26562 |
| Rushing yards | 1,176 | **0.25984** | 0.27091 | 0.27031 |
| Tackles + assists | 4,826 | 0.25087 | 0.25143 | **0.25070** |
| Solo tackles | 4,826 | **0.24009** | 0.24656 | 0.24416 |
| Tackle assists | 4,826 | **0.24663** | 0.25709 | 0.25441 |

## Decision

**Do not deploy.** The active-zero hurdle adds useful incremental structure to the experimental hybrid, and receiving yards is an interesting submarket, but the global Brier and log loss remain worse than a simple prior. The extreme 82.12% predicted Unders versus only 54.37% actual Unders is a directional-bias warning. The 59.65% unmatched roster/prop population and synthetic, non-bookmaker lines severely constrain interpretation.

Priority: audit unmatched contracts and 2024 actual active roster provenance; confirm line availability; independently validate active-zero conditional calibration; reexamine QB team-volume allocation and global Under tilt; prospectively test unchanged candidates on real archived pregame offers, with DNP/void logic handled separately. 2024 remains a held-out measurement set and must not be repurposed for tuning this frozen experiment.
