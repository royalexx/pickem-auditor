# Pick'em Auditor: Is manual tuning the overconfidence fix? — 10-year calibration signal experiment

Date: 2026-11-11 (North America Eastern; run completed 2026-11-12 UTC)
Status: **RESEARCH-ONLY — no production promotion, no tier authorization**

## Research question

Does fixed manual confidence adjustment, supervised model stacking, explicit model-disagreement features, or projected game context improve binary line accuracy and directional accuracy beyond the original frozen V2 and V3?

## Data and chronological protocol

407,476 historical matched 2016–2025 synthetic-line NFL prop contracts, 13 markets, 175 weeks. Historical source publication times not pregame-certified. Train: 2016–2021 (240,390). Select candidate hyperparameters on 2022–2023 (83,161). Refit the candidate using only 2016–2023. Evaluate subsequent 2024–2025 (83,925). The 2024–25 seasons were previously used during development, therefore they are **not an independent untouched scientific holdout**, despite this experiment's strictly chronological fitting and evaluation.

Logistic models used L2 regularization, independently fitted per market:
1. V2 and V3 frozen online probabilities.
2. Manual fixed shrinkage toward 50% (80%, 90%, 95% retain).
3. Platt scaling on V3 logit.
4. Market-specific learned linear log-odds combination of V3, V2 and player-history probabilities.
5. Above plus absolute/signed model-disagreement features.
6. Above plus forecast-only projected team and opponent plays, pass attempts, week and QB proxy-override flag.
7. Per-market model selection using 2022–2023.

No present-week official labels were used as regression covariates. No authentic 2016–2025 actual sportsbook quotes were available.

## Main results on 2024–2025 (n = 83,925 matched)

| Candidate | Brier (lower better) | Directional hit % |
|---|---:|---:|
| Frozen V2 | 0.23440919 | 60.1049% |
| Frozen V3 | 0.23442003 | 60.0346% |
| Fixed 10% confidence shrink of V3 | 0.23464051 | 60.0346% |
| Platt only | 0.23438749 | 60.1144% |
| 3-probability model stacking | 0.23317381 | 60.6804% |
| Stacking plus explicit disagreement terms | **0.23315673** | 60.6792% |
| Stacking plus context features | 0.23324123 | **60.7006%** |
| Per-market selected on 2022–2023 | 0.23318512 | 60.6899% |

New learned stacking vs V3: relative Brier gain about 0.54%, directional hit gain about 0.65 percentage points. The explicit disagreement interaction contributes only -0.00001708 Brier beyond basic stacking, and adds no directional hit improvement. Additional context raises Brier by +0.00008450 compared with disagreement model and adds a negligible +0.021 percentage points to hit rate.

**Interpretation: NO major directional breakthrough established.** An economical 3-probability market-level stacking/calibration layer is a stronger research candidate than arbitrary fixed probability shrinkage or a complex new context correction. More model flexibility remains subject to multiple-testing and chronological validation.

## High-confidence diagnostics (2024–2025 matched contracts)

| Candidate | >=80% selected | Mean claimed | Observed hits |
|---|---:|---:|---:|
| V2 | 364 | 82.68% | 76.92% |
| V3 | 129 | 86.24% | 89.92% |
| Manual shrink 10% | 114 | 83.12% | 88.60% |
| 3-probability stacking | 316 | 82.73% | 84.18% |
| Stacking + disagreement | 333 | 82.98% | 84.68% |
| Stacking + context | 358 | 82.70% | 84.08% |

Not the same selected candidates across methods; a hit-rate improvement may partly be a cohort selection effect. Very small >=90% samples make Tier-level extrapolation inappropriate. Across ALL ten years, previous V3 had 78.5% hit versus 84.2% claimed in >=80% class, which remains an unresolved production blocker.

## Largest selected signals by stat in the development-exposed 2024–2025 retrospective

- Receptions: disagreement stacking increases hit by +1.28 percentage points, lowers Brier -0.001384 versus V3 (9,041 contracts).
- Targets: three-probability stacking increases hit by +0.86 points, lowers Brier -0.001834 (9,371).
- Carries: the extra context version selected using the validation period increases hit by +2.05 points, lowers Brier -0.001804 (2,787); however context gains were not universal, so this is only a local signal hypothesis.
- Solo tackles: three-baseline stack increases hit by +0.405 points, lowers Brier -0.001586 (15,552).
- Tackle assists: disagreement increases hit by +0.643 points, lowers Brier -0.001519 (15,552).
- Passing attempts: extra context yields +0.45 point directional accuracy but **worse Brier (+0.002524)** than V3, so should not be promoted blindly.
- QB rushing yards: simple Platt selection did not improve directional accuracy and worsened Brier +0.000109 versus V3 (888). Retain old model pending more data.

## Decision rules and next tests

- Do not manually revise individual historical picks to make results look better.
- Do not assume universal probability shrinkage corrects an asymmetric/market-specific confidence issue.
- Keep V2/V3 frozen and test a market-specific, regularized three-model stacking calibration layer as a research challenger, with original data cutoff and source provenance.
- Evaluate feature importance/ablation, direction balanced accuracy, reliability diagrams, >=80%/90% cohorts, weekly/game cluster bootstrap, true sportsbook lines and prospective authentic source timestamps.
- A 2024–25 replay cannot become pristine simply because it was held out from this particular fit; new live/forward shadow slates remain necessary for a final decision.
- No production merge, Tier 1/2 permission, market profitability or real ROI is justified here.

## Saved assets

Deepnote:
reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_CALIBRATION_SIGNAL_DISCOVERY_20261111/CALIBRATION_SEARCH_RESULT.json
reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/V3_CALIBRATION_SIGNAL_DISCOVERY_20261111/ALL_CALIBRATION_CANDIDATE_MARKETS.csv
research/nfl_manual_vs_learned_confidence_signal_search_20261111.py

GitHub research branch:
chatgpt/nfl-v3-ten-year-opponent-context-20261111
