# Reform Step 7 / Step 8 — frozen ranking and market-informed shadow

**Date:** November 8, 2026 archives; verified November 9 UTC. **State:**
research challenger implementations and source-pinned preliminary diagnostics.
**Not** independently calibrated production changes.

## Source and execution

The frozen 2026-11-08 `slate_model_comparisons.json`,
`slate_full_universe_research.json`,
`slate_top10_evidence.json`, official 1 PM settlement and pinned
`directional_phase1_1pm_nfl_pinned_receipt_v1.json`
were read **without any reforecasting, data overwrite, training,
market-line mutation or postgame rank selection**. The November 5–7
independent retrospective backtest was kept separate from current 60/40
production.

Original frozen one-contract scoring and provenance checks are reused
from `reform_phase4_scorecard.py` and
`reform_phase5_selection_audit.py`. The original **2,436** forecast
sides, **160** rank-eligible research candidates and **all 30** original
NBA/NHL/NFL top-ten positions were reproduced exactly before testing
new research scenarios.

Independent [Deepnote verification notebook](https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/Steps-7-and-8-frozen-uncertainty-ranking-and-market-logit-diagnostics-f2e30f9b9b1646f19ddad7e0d9421975?utm_content=9cc31536-93be-44db-bdeb-06fba3f61410)
ran both code paths read-only against the exact files.

## Step 7 — uncertainty-adjusted rank *research* challenge

`scripts/reform_step7_uncertainty_shadow.py` reuses **the original
eligibility and display limits** (no more than two picks per player,
four per game, unique player/stat/line). It changes only the contribution
of the frozen model-versus-market edge to the **shadow ranking priority**.

An archived Engine B `relative_se` would be a potential workload
uncertainty input, but **none of the 160 eligible original candidates
has it**. Do not fabricate this variable or reinterpret NUTS
`numerical_mc_se` (Monte Carlo integration error) as predictive
uncertainty. Instead, the implementation explicitly labels
`max(Engine A, B, Bayes A/B) - min(...)` as an
**inter-model disagreement proxy**, *not* a standard error or credible
interval. The engines share information and are not independent.

The declared sensitivity scenarios subtract
`lambda × half_inter_model_range` from the frozen original
consensus-minus-market edge, truncating the effective edge at zero.
Only the original 25-point **edge component** changes; other original
40/25/5/5 priority components and market/model probabilities remain
untouched. Strengths λ=0, 0.5, 1.0, 1.5 were declared as *sensitivity
settings*, not fitted on outcomes. λ=0 exactly reproduces original ranks.

### Original top-10 overlap (not predictive accuracy)

| Penalty strength | NBA | NFL | NHL |
| --- | ---: | ---: | ---: |
| λ=0 (frozen control) | 10/10 | 10/10 | 10/10 |
| λ=0.5 | 8/10 | 10/10 | 10/10 |
| λ=1.0 | 7/10 | 9/10 | 8/10 |
| λ=1.5 | 6/10 | 8/10 | 8/10 |
| Disagreement-permuted negative control within sport (λ=1) | 6/10 | 9/10 | 10/10 |

A shuffled uncertainty proxy also changes the selection order. **Churn
by itself is not evidence of better accuracy or the optimizer's curse.**
The independent officially scored NFL 1 PM subset has only two original
ranked candidates, whereas λ=1 has only **one** originally selected
player/stat in that graded window. It won 1/1 versus the original
2/2, on different player/game contracts. Such tiny, different
sets have no useful comparative confidence interval.

**Step 7 implementation complete, validation not yet conclusive.**
Build prospective candidate-level records including a well-defined
Engine B `relative_se` and its relation to probability uncertainty,
collect all future outcomes without reranking, and compare the unchanged
baseline with fixed challengers on matched sport/stat/market cohorts
with game/date blocks. Do not use the disagreement proxy alone to make
a new Tier-1 claim or automatically shrink probabilities in production.

## Step 8 — market-informed logit mixing

The existing `scripts/fit_blend.py` already supports:

- **M0:** market-only baseline
- **M2:** Engine A and market logit covariates
- **M3:** Engine A, Engine B and market logit covariates

Their training requires a feasible chronological split of at least
**300 earlier contracts on ≥20 distinct dates**, **100 later out-of-fold
contracts on ≥20 dates**, matched contract provenance and date-clustered
proper-score improvement. These are minimum gates, not a universal
statistical sufficiency claim.

`scripts/reform_step8_market_shadow.py` adds an **unfitted equal-logit
scenario** (`sigmoid(0.5×logit(Consensus Over)+0.5×logit(Market Over))`)
to examine whether market blending could matter. This is **not fitted
M2/M3** and does not define production weights. It refuses to
normalize any original noncomplementary two-sided probability and
scores all compared models on the **same original settled contracts**.

### November 8 NFL 1 PM current-production overlap

Of 253 officially settled contracts, 188 lacked either
consensus/market at the exact same line, and 15 were excluded for
noncomplementary two-way probability pairs. **50** contracts across
six independent NFL games remained:

| Same 50 contracts | Selected direction | Brier | Log loss |
| --- | ---: | ---: | ---: |
| Original production consensus | 18/50 (36%) | 0.267215 | 0.726957 |
| Fixed 50/50 *logit*-market mix | 19/50 (38%) | 0.260017 | 0.713014 |
| Market alone | **27/50 (54%)** | **0.256062** | **0.705404** |

The unfitted mix numerically improves on consensus but **does not beat
the market**, nor does the six-game sample permit a reliable model
selection. Do not deploy the mix, infer profit, or use its score to
retroactively reweight November 8 forecasts.

The Nov 8 snapshot has **190** complete Engine A/B/Market paired M3
contracts but only **one independent date**. The Nov 5–7 archive has
three retrospective dates and legacy two-way market probabilities
that do not sum to 1: all 482 originally overlapping Engine A and
market forecasts were rejected by the coherent-two-way gate.
Neither archive has complete original source-published feature bytes.
The combined four dates were **never pooled for training or used as a
surrogate chronological split**.

Both training and fitting **abstain**: no M2/M3 trained coefficients,
weights, calibration or publication configuration was emitted.

## Release and evidence gates

The source code, regression tests and read-only diagnostics are
finished. The **research** components are deployable only as
non-promotable shadow reports. Step 7 needs prospective genuine
uncertainty estimates and enough selected-vs-unselected outcomes.
Step 8 needs a chronologically adequate **uncontaminated, fully archived**
same-contract market cohort and proof of improvement against both
the market alone and frozen 60/40 production in Brier and log loss.

No change to `config/production_consensus.json`, slate ranking
formula, probability scale, historical NUTS artifact, Tier thresholds,
market quotes, original forecasts, or paused training. Retain the
original comparison chart with Engine A, Engine B, Bayesian A,
Bayesian B, NUTS, market and production consensus.
