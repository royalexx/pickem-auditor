# NFL likelihood independence and opponent-adjustment research — November 9, 2026

Status: research-only. No production blend changes, training restarts, ranking/Tier changes or historical archive rewrites.

## Governing methodology
See docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md (rules 1, 3, 4, 6–8, 10–14 and 16).

## Likelihood audit
Reviewed scripts/nfl_context_model.py, scripts/nhl_context_model.py, scripts/joint_nhl_bayes.py, scripts/joint_population_bayes.py, references/bayesian_engine_b.md, scripts/historical_ensemble.py and scripts/probability_blend.py. Workload observations and outcomes conditional on workload are distinct observed variables and valid likelihood factorizations. Goalie shots faced and saves conditional on shots faced also factor correctly. No demonstrated Rome-style duplicate observation likelihood was found in these inspected model graphs; not a repo-wide proof.

Historical-ensemble code averages available Engine A, Bayesian A, Bayesian B and strict NUTS at equal weights, then mixes historical 60% with Engine B 40%. These forecasts share historical evidence; averaging does not make them independent observations.

On exactly 67 settled original November 8 NFL production-consensus contracts across six games, Bayesian A vs Bayesian B predicted P(Over) Pearson correlation was 0.92734, same-side fraction 0.82090 and mean absolute P(Over) difference 0.03683. Engine A vs Bayesian A correlation was 0.35808. Such correlation is evidence of forecast dependence, not proof of likelihood double-counting. Only one calendar date is represented.

## Opponent × position × market shadow
Source: original SHA-256 617b8693b6dbd17923c88b461789bfa7a3c50ec67b3b10783ce1e51f8526ff9b. All lines are synthetic preweek position medians, NOT sourced sportsbook lines or the current 60/40 production consensus.

Historical proposals: 107,319; graded: 71,009. Exact common evaluation cohort: 56,184 graded player-stat contracts in 208 games, NFL weeks 5–18 of 2024.

The original frozen model scores were chronologically amended using only prior-week residuals (actual_over minus model_p_over), with fixed nested partial-pooling pseudocounts by market 300, position×market 200, and opponent×position×market 60. This is a lightweight empirical-Bayes-style residual correction, NOT a new joint Bayesian NUTS model. The shuffled-opponent placebo deterministically permutes team labels without access to outcomes. There is no same-week training leakage by construction.

| Arm | Brier ↓ | Log loss ↓ | Direction correct ↑ | Mean P(Over) |
| --- | ---: | ---: | ---: | ---: |
| Original | 0.1926460 | 0.5613059 | 70.13029% | 0.2814778 |
| Historical baseline | 0.1957327 | 0.5668074 | 68.47679% | 0.3352774 |
| Position/market only | 0.1855235 | **0.5433287** | **70.75324%** | 0.3184953 |
| Position/market/opponent | **0.1854063** | 0.5434025 | 70.74078% | 0.3189572 |
| Shuffled-opponent placebo | 0.1861676 | 0.5451488 | 70.53966% | 0.3187994 |

Actual Over frequency: 0.3125623. Original predicted Over selection fraction: 0.0732059; corrected opponent selection fraction: 0.1506835. Selection fractions need not equal observed outcome fractions for a calibrated model: mean P(Over) compared with observed Over is the more appropriate aggregate bias check.

Opponent minus position-only Brier: -0.00011718 (12k full-week bootstrap 95% CI [-0.0003347, +0.0000990]); log-loss: +0.00007387 (95% CI [-0.0006151, +0.0008077]). Neither interval excludes zero. Real opponent outperforms shuffled opponent by 0.00076126 Brier and 0.00174630 log loss, but does not show a reliable incremental gain over position-only.

The original November 8 production forecast SHA-256: 78983420bd4b7b08044a840d23168714b9ffc31ecd8e574c66dad72a18f27960.

## Evidence limits
Only positions, not verified slot/outside/backfield/subpackage roles or route participation, were available in this test. No original source-provider pregame publication receipts, matched actual bookmaker lines, chronologically separate seasons, independent market quote control or calibrated EV analysis were available for this replay. Unmatched players were excluded from outcome scoring, not imputed as zero. The existing production 60/40 was not used as the 2024 baseline. The 14-week bootstrap is descriptive; no production/Tier approval.

## Reproducible run notebooks
- https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/2024-opponent-x-position-x-prop-challenger-chronological-empirical-Bayes-and-negative-control-Nov-9-1d2dccb86833455299312701d5b56a63
- https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/Nov-8-original-production-paired-engine-residual-dependence-read-only-audit-0d0375002ba74abc9a74d6c9d219fb32

Both notebooks successfully executed in read-only detached Deepnote runs.

## Acceptance decision
No promotion. Improve verified opportunity and position/role prior estimates first; then validate true opponent incremental signal on source-timestamped pregame real-market contracts with chronological independent seasons and opponent-shuffled/disabled negative controls. Cross-fit any model stacking weights, accounting for observed Bayesian A/B dependence.
