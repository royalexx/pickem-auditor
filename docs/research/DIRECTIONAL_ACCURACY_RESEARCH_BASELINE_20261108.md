# Directional accuracy: canonical research baseline

**User-approved reference date: November 8, 2026.**
**Authority:** Full Deep Research report, *Amélioration de la précision directionnelle des prévisions de props — audit méthodologique, littérature et comparaison avec LosingLoonies*, approved in the Pick'em Auditor conversation. This document is its **enforceable engineering translation**. The complete original narrative lives in the research conversation; do not falsely represent this engineering translation as a word-for-word copy.

## Mandatory principles for EVERY future model change

1. Separate **directional accuracy** (correct over/under side against the exact original line) from **probability calibration** (predicted frequencies versus observed outcomes). Post-hoc confidence shrinkage alone does not repair a biased opportunity or expected-stat projection.
2. Retain the existing production 60% eligible historical ensemble / 40% verified Engine B as a **frozen reference/control**. The control is not empirically certified as calibrated. Phase 1 has **zero** authority to change production weights, probabilities, ranks, Tier eligibility, posterior acceptance thresholds, previously frozen forecasts or Dell NUTS jobs.
3. Strict point-in-time integrity: independently record data event time, public-availability time, source retrieval time, prediction time, model training cutoff and fixture start. Every input used for a claimed pregame forecast must demonstrably have been available by its decision time. Missing or future availability evidence causes an explicit block, never retroactive imputation.
4. Reconcile exact sport/fixture/player ID/team/stat/line/side/run and timestamp, with an archived market-price source when present. A contract contains two paired sides and is counted **once**. Missing, void, DNP, and push remain separate from hits and misses. Original forecasts cannot be regenerated from postgame histories.
5. Maintain Engine A, Engine B, Bayesian A, Bayesian B, strict NUTS, market and 60/40 consensus as separately identified model columns with provenance and explicit missing reasons. Market is a benchmark, not covert training information or a substituted model. Compare every candidate on the same verified contracts, plus separately show each model's coverage.
6. Do not assume historical engines are statistically independent. Diagnose correlated residuals, shared data, duplicated prior information and consensus reversals. Only train ensemble weights on **historically out-of-fold** forecasts; test constrained stacking, ridge/logistic meta-models and correlation-aware Bayesian ensembles as research challengers. No automatic promotion.
7. Prioritize an **opportunity-first generative decomposition**: expected exposure/opportunities × production per opportunity, including uncertainty in exposure. Player role, position, current lineup, official injury/inactive status, expected team pace, score-state, opponent, weather and venue require timestamped evidence; unsupported assumptions cannot be sold as positive scouting.
8. Hierarchical priors must pool within meaningful **position × role × season** contexts, not treat every NFL stat participant as interchangeable. Include player, team/opponent effects, dynamic role states, sample-size sensitivity and posterior predictive checks when data supports them.
9. Use appropriate market distributions and exposure: count markets may require negative-binomial, hurdle or zero-inflated likelihoods; passing/receiving yardage may need different robust tails. Do not replace all distributions with one count family or make simultaneous players independent when opportunities are shared.
10. Evaluate real opponent and lineup context against **permuted and disabled-feature controls**. A contextual adjustment is approved only if genuine chronological out-of-sample predictions improve relative to those controls, not merely because it sounds plausible.
11. Judge challengers by pre-registered proper Brier and log scores, directional accuracy, expected versus observed over share, side/market/role performance, coverage/abstention, game/slate-clustered uncertainty, and independent no-vig market performance. If odds are available, model expected value separately from raw hit percentage.
12. Fit logistic/temperature, Beta, isotonic or Venn–Abers calibrators only on chronological calibration folds, comparing each to uncalibrated predictions. No calibration method is automatically assumed beneficial; it must preserve meaningful directional ability and improve held-out proper scores.
13. Prevent selection and survivorship bias. Report every source-supported contract and unavailable reason, not just top-ten. Build train → validation → sealed forward holdout without same-game leakage. Bootstrap entire game/slate clusters, not independent contract rows.
14. No new model is promoted to production/Tier without transparent results on multiple sealed chronological windows and adequate independent games, robust clustered uncertainty, matched model coverage, and an explicit approval decision. Single-slate gains cannot certify success.
15. Keep read-only SHA-256 receipts, policy/model version, game identifiers, source timing, observed actuals, push/void distinctions, missingness and all comparisons. Never overwrite source frozen data with newly computed forecasts. Do not interrupt the Dell's running training or invoke GitHub AI agents.
16. Every research or model PR must cite the relevant rule in **this file**, identify the hypothesis, define its negative control, report matched-cohort Brier/log loss/directional metrics and data/time boundaries, and disclose any failure. If deliberately deviating from the approved report, record an amendment and ask for separate authorization.

## Evidence and unresolved hypotheses

Frozen November 8 NFL 1 PM: 257 unique contract lines covering six games (514 two-side rows), 68 with a 60/40 forecast, 67 verified and one not scored because the player was inactive. Consensus correct 25/67 (37.3%) versus ~38.1 expected. In the same 67-settled cohort, Engine A and B each hit 31; Bayesian A and B each hit 28. Consensus directions: 46 unders, 21 overs; actual outcomes: 32 unders, 35 overs. That sample is game-correlated; do not misrepresent independent-row Poisson-binomial significance as dependence-adjusted. Confirmatory investigations found exact blending arithmetic on 136 side rows, 209 source-pinned tests passed, and no pregame snapshot timestamp violation. These facts do **not** establish accurate predictive training or exonerate older priors.

The original slate applied no explicit game-specific numerical context adjustment across 514 sides; opponent-specific availability/scenario/weather source verification was unavailable. Bayesian A's NFL tackled-player prior was stat-pooled and generally low relative to an every-down linebacker; historical models shared evidence. NUTS artifacts trained **after** the slate did not influence this slate, but older training specification and stale historical fits remain subjects for validation. Other archived NBA/NFL slates support investigation, not a definitive causal verdict.

Test, do not assume: identity/fixture mixups, stale or postevent feeds, bad stat definitions, unverified DNP, over/under market selection effects, missing opportunities, underdispersion, prior shrinkage to inappropriate roles, dynamic rotation changes, opponent/game-script errors, correlated ensemble dominance, and historical concept drift.

The current production benchmark is pinned in **config/directional_research_baseline_20261108.json**. Its immutable archive originated in Deepnote; GitHub does not contain every original provider source file. A comparison-file SHA is not evidence that the entire original provider source bundle was recovered.

## Research-driven target architecture (future phases)

Opportunity model:
  exposure ~ f(active,role,injuries,lineup,pace,opponent,spread,score-state,rest,weather)
  rate ~ hierarchical(position,role,season,player,team,opponent,context)
  expected count = uncertain exposure × uncertain production rate
  predictive distribution ~ likelihood(exp(mean), dispersion, zero-inflation as justified)
  p_over, p_under, p_push = integrals of predictive distribution around original quote

NFL tackles: projected defensive snaps, opponent plays, run/pass and short pass volume, position and box/slot/deep alignment, tackle-opportunity rate. NFL receptions: routes, target share, opponent/pass design, catch rate and yardage distribution. Rush attempts: projected team carries, backfield allocation, score-state. QB attempts: dropbacks, team pace/pass mix and opponent scenario. NBA: minutes × usage × rate, rotations and lineup interactions. NHL: TOI/shifts, line assignment and shot/hit/block/goalie exposure. The exact source proof and availability time must precede the forecast.

Use a *position → role → player* hierarchy with partial pooling, historical recency/dynamic effects, and separate team/opponent effects. Compare to league-global priors and shuffled-context negative controls. Use uncertainty-aware game-script scenarios, not unsupported deterministic multipliers.

Candidate blending: historical 60/40 frozen baseline versus learned nonnegative stacking, ridge/logistic meta-model, correlated Bayesian ensemble and conditional mixture-of-experts when sufficiently powered. Recalibration is an independent follow-on after directional effectiveness is established.

## Implementation stages and acceptance gates

| Phase | Required deliverables | Can alter production probabilities? |
|---|---|---|
| **1: baseline and integrity** | This canonical contract, frozen policy/source hashes, source-time and no-leakage validator, paired-contract and DNP/push checks, read-only per-engine/game-grouped metrics, negative tests, reproducible receipt | **No** |
| **2: opportunities** | Timestamped NFL/NBA/NHL opportunity and lineup/role history, rate/exposure decomposition, injury and scenario gating, shuffled-feature controls | No |
| **3: prior hierarchy** | Role-/position-/season-specific priors, posterior predictive and prior sensitivity on chronological OOS | No |
| **4: ensemble** | Cross-fitted out-of-fold predictions, dependence-aware constrained stacking/regularized alternatives, same-cohort OOS comparisons | No |
| **5: calibration** | Several calibration candidates using older folds, independent sealed assessment of Brier/log loss/direction | No |
| **6: adversarial validation** | Multi-season holdouts, game-clustered CIs, random controls, data-quality checks, explicit promotion review | Only with separate authorization |

A phase is **not complete** merely because a model trains or a backtest improves in-sample. The validation gate requires no time leakage, no unexplained fixture/settlement mismatch, a frozen matched-cohort benchmark, a sufficient effective number of game clusters and stable results across time. Unpowered cohorts remain descriptive, with no authorized Tier uplift.

## Core papers and transferable LosingLoonies practices

1. Yao, Vehtari, Simpson & Gelman, *Using stacking to average Bayesian predictive distributions* — https://arxiv.org/abs/1704.02030 . Out-of-fold log-score weighting rather than fixed model-voting confidence.
2. Pirš & Štrumbelj, *Bayesian Combination of Probabilistic Classifiers using Multivariate Normal Mixtures* — https://jmlr.org/beta/papers/v20/18-241.html . Dependence among related model probabilities.
3. Whitaker et al., *A Bayesian Approach for Determining Player Abilities in Football* — https://academic.oup.com/jrsssc/article/70/1/174/7033964 . Hierarchies and exposure in association-football research; concept transfer, not a proved NFL tackle model.
4. Skinner & Guy, *A Method for Using Player Tracking Data in Basketball to Learn Player Skills and Predict Team Performance* — https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0136393 . Player/opponent opportunity context.
5. Gneiting & Raftery, *Strictly Proper Scoring Rules, Prediction, and Estimation* — https://sites.stat.washington.edu/raftery/Research/PDF/Gneiting2007jasa.pdf . Brier/log loss and honest uncertainty.
6. Kull, Silva Filho & Flach, *Beta calibration* — https://proceedings.mlr.press/v54/kull17a.html . Calibrator challenger, never assumed gain.
7. Manokhin & Grønhaug (2026), *When Post-Hoc Calibration Hurts* — https://proceedings.mlr.press/v329/manokhin26a.html . Calibration must prove OOS benefit.
8. LosingLoonies research/public repo — https://github.com/LosingLoonies-Youtube/congress-trading-investigation . Use **public disclosure time**, not earlier trade time; random/no-signal baselines; accept negative results. The public LSTM/FFT code is not fully available. Do not copy or claim validation of inaccessible methods, and do not conflate stock prices with player-stat conditional distributions.

This baseline must be reviewed when changing data collection, forecasting, Bayesian training, blending, rankings, calibration, backtests or settlement. Keep revisions explicit and versioned: never quietly rewrite this approved source contract.
