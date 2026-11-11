# NFL Phase 2 — Independent 2024–25 QB rushing component audit (November 11, 2026)

**Evidence:** Immutable Deepnote original model report `reports/v25_qb_rushing_components_2024_2025_20261111/REPLAY_20261111T193823Z/FINAL_COMPONENT_2024_2025_REPORT.json` and separately executed independent audit `reports/v25_qb_rushing_components_2024_2025_20261111/INDEPENDENT_SHA_AND_OFFICIAL_QB_AUDIT_20261111.json`, independent receipt SHA256 **`31941cbefd844bb394cd7c7488f9e225d1cedea753b66c00f86cfc749c90a6b4`**. Read-only independent audit ran in Deepnote notebook `6c18917b44ea41a4abdf6d181dde85c7`, run `fc656756-d2b2-475d-bb8a-6b3072148392`, and **PASSED**.

**Scope:** Two previously exposed retrospective 2024–25 seasons. Per-player synthetic historical-median-plus-0.5 research lines; depth rankings are retrospective proxies, **not independently authenticated original pregame starting-QB confirmations**. No actual bookmaker payouts, no profit or Tier gate. Does not update weights/production.

## Independent source and score reconstruction

Independent implementation (no call to model scorer) verified all **36 weekly forecast/settlement sequences** and 108 hashed week artifacts, all model code SHA checks, historical preweek player/PBP source boundaries, every selected QB's source-only original event/team/player/line identity, official NFLverse QB box statistics on original player/line, no current week labels in forecast packets, Jeffreys `(over_count + 0.5)/(draw_count+1)` probabilities, and sample CRPS/Brier/means. It independently recomputed all four market×season paired model scores and reconciled them to the frozen report.

| Original season | QB market | Matched original contracts | Type-specific Brier | Player-prior Brier | Type-specific CRPS | Player-prior CRPS | Paired Δ Brier (new − old) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | Rushing attempts | 425 | 0.228302 | **0.224970** | 1.276234 | 1.277272 | **+0.003332** |
| 2024 | Rushing yards | 425 | **0.245215** | 0.269856 | **9.436644** | 10.150063 | **−0.024641** |
| 2025 | Rushing attempts | 494 | **0.224587** | 0.230951 | **1.238309** | 1.250090 | **−0.006364** |
| 2025 | Rushing yards | 494 | **0.240226** | 0.278168 | **8.154373** | 8.760950 | **−0.037942** |

A negative Brier difference favors the type-specific challenger. NBA and NHL scores are outside this experiment. QB attempts are mixed: 2024 worse, 2025 better; neither season's paired game-cluster descriptive 95% interval excludes zero for attempts. QB rushing yards improve on both years, with the historical research game-cluster intervals excluding zero (2024 `[−0.040826,−0.008971]`, 2025 `[−0.054388,−0.021245]`). **Because the methods were developed using exposed history, these are descriptive retrospective intervals, not fresh prospective confirmatory tests.**

### Selection and tails

- 2025 type-specific QB rushing yards ≥80% confidence: **13** choices, mean claimed **85.11%**, observed **84.62%**. Historical player prior: **90** ≥80% picks, mean claimed **95.30%**, observed **55.56%**. This is reduction of overconfident unsupported certainty, not certification of 85% future accuracy from 13 correlated observations.
- 2024 type-specific QB rushing yards ≥80%: **6**, mean claimed **85.28%**, observed **83.33%**; historical player prior **61** with 92.36% mean claimed versus 59.02% hits.
- 2025 type-specific QB rushing attempts ≥80%: **32**, 85.06% mean confidence, 84.38% observed. 2024 attempts **33**, 85.09% mean confidence, 78.79% observed.
- The old player-prior yards simulation had **0% average probability assigned to exact zero yards**, despite 11.29% actual zero yards in 2024 and 10.53% in 2025. The component model produced 7.69% and 8.11% zero-yard probability respectively—still imperfect but materially more realistic.
- Nominal central 80% interval coverage: rushing yards 2024 **79.76%** vs old **70.35%**; 2025 **86.03%** vs old **70.24%**. Slightly wide 2025 intervals may still need calibration.

### Denominator and missingness

2024: 544 game-team candidate opportunities, **35** upstream QB1/market abstentions, **850** settled contracts, **168** unmatched. 2025: 544 game-team opportunities, **6** upstream abstentions, **988** settled, **94** unmatched. The unmatched contracts are not imputed as Unders, wins, losses or DNPs. Predictions are QB1-proxy research; this neither proves starting availability nor solves absent-starter risk.

## Root-cause finding and decision

The original empirical-yards-residual sample lacked an exact zero atom and produced spurious finite-support near-certainty. Separating QB scrambling, designed runs, kneels and other rushes produces a coherent event-type count/yards distribution, with realistic zero and signed-negative outcomes and no postgame reconstruction of starting QB. **Retain as an unpromoted Phase 2 research challenger for QB rushing yards.** For QB rushing attempts retain BOTH models until future paired, pregame verified evidence establishes which has lower proper scores. Do not switch production to type-specific model or release Tier 1/2 from this backtest.

## New 10-season study

The follow-up experiment `EXP_NFL_DECADE_2016_2025_ALL13_PREQUENTIAL_V1` uses exactly eleven original markets (passing attempts, completions, passing yards; targets, receptions, receiving yards; carries, rushing yards; tackles plus assists, solo tackles, tackle assists) **plus QB rushing attempts and QB rushing yards**. One simulated pregame team pass/rush volume is shared across QB work, receiver target/catch/yard distributions, RB carry/yard distributions, and QB scramble intensity; all player markets have a separate same-contract player-history control. Defensive tackle components share a joint modeled tackle total.

The source archive: `reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111/source_bundle/` (2014–15 initial history, 2016–25 prediction years); 2014–20 PBP in `qb_pbp_components_2014_2020`, 2021–25 PBP in `reports/v25_qb_rushing_components_2024_2025_20261111/sources_v2/`. Some old rows have no player ID, including sporadic **nonzero defensive tackles**. They are individually source-hashed and quarantined, not fabricated.

**Chronology:** before every week freeze the full allowed prior three-season rolling historical state, league roster/QB-depth selector, source SHAs, each probability and draw, and the calibration state. Score official outcomes only after freeze, append-only. Update market/role binomial calibration only after all of that week's outcomes are scored, with 0.995/week forgetting factor. Plot and compare season-level matched Brier, CRPS, log loss, source coverage, 80% confidence/actual hit and opportunity conservation. Old sources are retrieved in 2026; this is development regression, never a new betting edge or a real 2016–25 offer backtest.

**Run:** connected Deepnote notebook `3fd445aedfbf4019b5327461daee2ba1`, detached run `3c2a534f-824c-4706-9c91-27a6f1bbd0f4`. Code branch `chatgpt/nfl-2016-2025-prequential-10yr-study-20261111`. If results are absent, the experiment is still running/blocked; **do not claim a completed decade score**.

**Policy:** no production model promotion, no paid compute, no new NUTS fit, no Tier activation, no profits inferred from synthetic odds.
