# V2.5 Phase 1.5 — NHL/NBA certified-source diagnostics, Nov 10, 2026

**Decision: Phase 1.5 PRE-SETTLEMENT DIAGNOSTIC EXECUTED AND INDEPENDENTLY VERIFIED; empirical error attribution BLOCKED until official outcomes.** Not a production model, winning-strategy claim, or permission to advance to expensive Phase 2. Full 2026-11-10 NBA/NHL original-game settlement had **not** happened as of this diagnostic (2026-11-10 ~22:59 UTC).

## Inputs and strict evidence boundaries

| Evidence | Exact value |
| --- | --- |
| Original genuine pregame input run | Deepnote `ccd5d53d-6583-4380-97ed-9fda64e90559`, code SHA `e5635d8fd8444a3144174cf019924d2010cdbca8` |
| Frozen original NBA/NHL bundle SHA-256 | `76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6` |
| Original paired Phase 1 merged implementation SHA | `939024a347d648e4479afbe74dc987ce4d0ed15f` |
| Original Phase 1 receipt | Deepnote `reports/phase1_nhl_nba_certified_20261110_original_batch_939024a347d6.json` |
| Original Phase 1 data/report seal | `005abb2980bc2ce38ad5d6e09ca84a26048177fac2fd58841ed0988b21e9c22c` |
| Phase 1.5 tested diagnostic implementation SHA | `3bd693d4df29363909bfacf858348276a2d8a460` |
| Phase 1.5 diagnostic receipt | `reports/phase15_nhl_nba_20261110_certified_diagnostic_3bd693d4df29.json`, Deepnote project `9cc31536-93be-44db-bdeb-06fba3f61410` |
| Phase 1.5 receipt bytes SHA-256 | `cc1041632ae9d53ae1b5b451469351a9519481e9f7314ebefc640068e559310a` |
| Branch tests (9 suites) | Deepnote `8985042c-cf87-4349-ab75-2e12afb68b55`; **134 passed, 0 failed**, including **14 new** Phase 1.5 adversarial tests |
| Independent numerical/red-team review | Deepnote `42cf7d1a-31c0-4bef-8001-3c54218b2185`, `reports/phase15_nhl_nba_20261110_independent_qa.json`; **PASS** |

**Denominator:** 1,314 attempted **forecast sides**; 712 eligible frozen forecast sides and 602 excluded before prediction (438 unpinned context, 164 missing/unverified markets). The 712 accepted sides form **356 unique paired contracts**: **250 NBA** in five games and **106 NHL shots-on-goal** in seven games; there are **12 distinct games and one slate date**, not 356 statistically independent bets. Official results available to this diagnostic: **0/356**; Brier, log loss, calibration, observed directional residual, actual edge and game/date-cluster uncertainty remain **null**.

## A. Probability direction and uncertainty — pregame-only, no outcome scoring

| Forecast model | NBA Over | NBA Under | NBA 80%+ choices | NHL Over | NHL Under | NHL 80%+ choices |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Recent-five per-workload Poisson **counterfactual** | 122/250 (48.8%) | 128/250 (51.2%) | 34/250 | 50/106 (47.2%) | 56/106 (52.8%) | 9/106 |
| All-player same-stat peer shrinkage **counterfactual** | 147/250 (58.8%) | 103/250 (41.2%) | 20/250 | 49/106 (46.2%) | 57/106 (53.8%) | 0/106 |
| Real two-sided book's de-vig **pregame** probability | 102/250 (40.8%) | 136/250 (54.4%) | 0/250 | 40/106 (37.7%) | 63/106 (59.4%) | 0/106 |

**Exact 50/50 ties:** market 12 NBA and three NHL contracts; neither rate control has ties. When computing choice rates, these ties stay in the denominator but are not labeled Over or Under. The high-confidence counts denote *model-generated numerical confidence only*, **not validated tiers** or predicted hit accuracy.

- Average absolute probability disagreement with the real market: NBA **15.405 pp** (naive) versus **11.513 pp** (pooled); NHL SOG **14.190 pp** versus **4.604 pp**. Relative reduction in disagreement: 25.3% NBA and 67.6% NHL. **Market proximity is not proof of skill, and this contrast is not a Brier score.**
- Side disagreements with the market: NBA naive **89/250**, pooled **92/250**; NHL naive **43/106**, pooled **20/106**. NBA pooled's lower average absolute deviation does **not** mean it chooses the same side more often.
- NBA submarkets flag heterogeneity requiring future stratified proper scores: points `n=47` has mean absolute naive-market gap **20.08 pp**; points+rebounds `n=30` has signed naive-minus-market P(Over) **−7.65 pp**; points+rebounds+assists `n=15` shows **+8.87 pp**. Tiny per-market cells, correlated team/game outcomes and multiple exploratory comparisons mean **no significance declaration**.
- The prior **NFL 2024 synthetic-line** 92.85% Under concentration is not transferable to this independent NBA/NHL cohort. This comparison is one of forecast composition only, not a claim that the historical Under directional problem is fixed.

## B. Why accurate scoring is not yet possible

- All **356** November 10 original contracts have status `pending_official_settlement` in the immutable Phase 1 input. Games are scheduled later; the diagnostic cannot legitimately replace unknown actual player-game stats with today's box-score pulls, synthetic outcomes or provider quote-implied results.
- The original 60/40 V1 consensus is **not finalized** in this exact source archive (0/356): use `unavailable`, never a 70/30 preview or original Engine A/B component average. Reliable Engine A original component probabilities are present for **322/356**, Engine B **260/356**. Bayesian A/B and strict NUTS require separately certified pregame sidecar receipts.
- The last-five and pooled-peer Poisson controls are recomputed **after the original run** from source-frozen, pregame-available histories. They are legitimate diagnostic counterfactuals but were **not prospective forecasts originally published on November 10**. They are not eligible for retrospective Tier/payout claims.
- No observed Over/Under outcome means **no empirical signed Over residual, no 80%+ hit calibration, no measured tail or zero-count error, no paired market Brier difference, no honest clustered confidence interval**.

## C. Opportunity factorization — NOT yet measured

The historical-exposure median used by the Phase 1 simple baseline is a recorded pregame source feature, not a verified future role prediction. The Phase 1 contracts do not contain independently timestamped **four-factor** pregame forecasts (team opportunity, active participation, player share/allocation, conditional conversion/efficiency) and do not have observed game outcomes. Accordingly **0/356** qualifies for a genuine postgame Shapley or oracle opportunity decomposition.

A minimal prospective instrumentation handoff should freeze each meaningful factor's stat-specific definition, numerical forecast, scenario/uncertainty, actual-source pointer, retrieval clock and source hash before the event. For NHL SOG, distinguish team attempt/shot volume, projected skater ice time/availability, individual shot opportunity share and shots-on-goal conversion consistently with units. For NBA points/assists/rebounds/combos, freeze minutes and possessions, lineup/role scenarios, opportunities/usage and conditional conversion, with separate component models for composite stats. **Do not impose an incoherent four-way product on all combos**, infer future minutes from actual boxes, or treat missing factor receipts as zero error.

The NBA historical source provides **no verified position in this intake**: the pooled prior is explicitly all-players same-sport/stat, not a position-stratified true hierarchical model. Only **two NHL SOG contracts** used prior-season games in their last-five inputs. None of this is postgame opportunity attribution.

## D. Market, full-universe and Tier power

Actual two-sided bookmaker odds are sourced before the game for all 356 accepted contracts and their no-vig conditional nonpush probabilities are valid *references*. No score or bankroll profitability exists before settlement; sportsbook/no-vig is not a substitute for a pick'em operator's exact payoff terms.

Tier power is an illustrative fixed-`n` one-sided Bernoulli calculation at α=.05, desired power=.80 (independent, prespecified): **70→80: 119; 75→80: 437; 80→85: 365; 85→90: 281; 90→95: 179** independent labeled events. These are ***not*** 119 raw props from one correlated slate. The diagnostic reports sensitivity at ICC assumptions of .05, .15 and .30 using the **29.67 average props per game**, but does not estimate ICC or actual effective n. With 12 games, a single date and zero settlements, **no Tier power gate can pass**.

## E. Investment decision and gates

| Gate | Result | Action |
| --- | --- | --- |
| A — pregame contract/market archive integrity | **PASS** for Phase 1 original source-certified NHL/NBA subset | Keep hash-locked original archives and full attempted/rejected pool |
| B — directional/probability forecast error | **BLOCKED: NO OUTCOMES**; pregame side mix and dispersion measured | Run postgame source-verified outcome scoring on exactly matching contracts |
| C — opportunity contribution (team/role/share/efficiency) | **BLOCKED: 0 four-factor pregame vectors, 0 resolved actuals** | Add selective, cheap immutable factor capture prospectively; no Shapley until eligible |
| D — true payout-relative market edge | **BLOCKED: 0 settled contracts and no pick'em payout receipt** | Continue real two-sided quote capture; do not claim profit |
| E — complexity/Phase 2 investment | **DEFER** | Prioritize verified settlement + final consensus artifact availability + inexpensive distribution/role-sensitivity diagnostics; no heavyweight NUTS, full joint simulator or promotion |

**Investment verdict: `DEFER_PHASE2_AND_HEAVY_COMPUTE_CONTINUE_CAPTURE_AND_SIMPLE_SHADOW`.** Do not misrepresent this as a failed model: empirical performance has not been observed. No daily schedule, Tier 1/2 gate, production engine weights, original November 10 forecasts or historical Bayesian posteriors were modified.

## Reproduce the diagnostic

From the GitHub repository's deployed commit and the immutable original **Deepnote project** Phase 1 receipt (download/mount it unchanged):

```bash
python -m unittest discover -s tests -p test_phase15_nhl_nba.py -v
python scripts/phase15_nhl_nba.py \
  --phase1 reports/phase1_nhl_nba_certified_20261110_original_batch_939024a347d6.json \
  --seed 20261110 \
  --output reports/phase15_nhl_nba_nov10_new_immutable_diagnostic.json
```

The output path must be new; the diagnostic checks the Phase 1 report hash, numerator/denominator and settlement identities, exact model-specific source statuses, pregame time, probability mass and scored Brier/log-loss agreement. Repeated executions are byte-identical. Deepnote historical artifacts are attached to project ID `9cc31536-93be-44db-bdeb-06fba3f61410`, not committed as a synthetic replacement to GitHub.

**Next scientific milestone:** after a real official settlement receipt exists, rerun exactly matching, source-hashed contracts; collect multiple independent NHL/NBA dates, perform precommitted matched proper scores and sign calibration, and re-evaluate the low-cost first pilot only when Gate B/C has measurable evidence. Original final 60/40 model comparison remains blocked until its actual final pregame artifact is separately certified; never backfill it into the existing freeze.
