# Experiment B — full 2024 NFL weekly rolling-origin all-market training audit

**Run:** Deepnote notebook `0931d8cd5e98415480882e8ebe29137e`, run `6633e816-b235-49d5-9820-56bf05ed181f` — **success**.  
**Independent receipt audit:** Deepnote notebook `8d23b4ddb1934caab64c093e1bbde283`, run `6b5ce933-f15b-4010-b812-4b45f5899123` — **success**.

**Research only.** Machine-learning challenger: globally regularized nine-feature market-specific ridge learner for 16 NFL markets, with prior-only player and position histories and an unlearned historical-rate control. Existing Bayesian/NUTS artifacts and production 60/40 model were not trained, reweighted, or promoted.

## Experiment protocol

- Ingest pre-2024 data from seasons **2021, 2022 and 2023** for model fitting.
- For **each 2024 week in sequence**, create one pregame packet containing all fixtures, previous-week training state, candidates and all **16** registered player-stat markets.
- A separate subprocess receives the sanitized packet **without any current-week results or outcome key**. It must generate every market's predictions, then freeze all model outputs and original coefficients' hashes before the whole-week settlement begins.
- Current-week outcomes are encrypted in a separate vault; its decryption key is held only by the parent orchestrator until the completed **all-market** forecast has an immutable SHA-256 lock receipt.
- Only **after full-week settlement**, append newly revealed rows to each learner's sufficient statistics for the next week. Independent audit checks 18 linked SHA receipts and every market's exact cumulative pre/post-update training counts.
- Use the **same contract, synthetic pregame training-position-median line and settled observation** for challenger vs historical-rate control. Count unobserved/unmatched forecasts, not as losses; they are outside the scored population.
- Critical: despite result sealing, this is **retrospective pregame simulation**, not independently captured original sportsbook inputs. The overall model was designed after our team had examined some 2024 data, so these 2024 results are not a pristine external holdout.

## Verified full-season coverage

| Measure | Value |
|---|---:|
| Weeks completed | **18 / 18** |
| Registered NFL markets forecast before every reveal | **16 / 16** |
| Forecasts locked across all weeks | **107,319** |
| Forecasts matched to observed weekly player markets | **71,009** |
| Forecasts without a matched observed row | **36,310** |
| Matched-observation proportion | **66.17%** |
| Unmatched forecast proportion | **33.83%** |
| Proven pregame bookmaker quotations | **0 — not available** |
| Production model promotions | **0** |

All 18 original forecast files, corresponding immutable hash-lock receipts,
encrypted outcomes, separately generated settlement files and linked
previous-week training receipts were checked by the independent auditor.

## Overall matched-participant model comparison

| Score | Weekly ridge learner | Frozen historical-rate control | Model minus control |
|---|---:|---:|---:|
| Directional accuracy (higher is better) | **74.538%** | 73.816% | **+0.722 pp** |
| Brier (lower is better) | **0.173086** | 0.175093 | **−0.002007** |
| Log loss (lower is better) | **0.517605** | 0.522235 | **−0.004630** |

Original, same-contract **week-block descriptive** 95% bootstrap intervals
for model-minus-control differences: directional accuracy
**[+0.478 pp, +0.956 pp]**; Brier **[−0.003201, −0.000652]**;
log loss **[−0.008449, −0.000196]**.
These intervals resample only 18 weeks and do not account for model
selection after seeing 2024 development results, correlated market
categories on the same player, original missing participants or
retrospective data-provider availability. They **do not validate live
betting performance** or a genuine production 60/40 model improvement.

## Every market — exact matched contracts

Numbers below compare the same exact scored observations per market.
All Brier differences are challenger minus control. Negative is better.

| Market | Matched n | Direction learner | Direction control | Brier learner | Brier control | Difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Tackles + assists | 7,555 | 67.50% | 67.60% | 0.20990 | 0.21066 | −0.00076 |
| Targets | 4,632 | 75.54% | 75.80% | 0.16588 | 0.17248 | −0.00660 |
| QB pass attempts | 597 | 54.27% | 53.94% | 0.25826 | 0.25032 | **+0.00794** |
| QB completions | 597 | 58.29% | 58.46% | 0.24409 | 0.23656 | **+0.00754** |
| Passing yards | 597 | 61.14% | 64.15% | 0.23431 | 0.22411 | **+0.01020** |
| Passing TD | 597 | 62.14% | 63.32% | 0.22815 | 0.22397 | **+0.00418** |
| Receptions | 4,632 | 73.29% | 74.07% | 0.17717 | 0.18231 | −0.00514 |
| Receiving yards | 4,632 | **71.87%** | 63.60% | **0.20004** | 0.21922 | −0.01918 |
| Receiving TD | 4,632 | 85.21% | 85.25% | 0.11750 | 0.11756 | −0.00006 |
| Carries | 4,106 | 81.59% | 82.42% | 0.13080 | 0.12927 | +0.00153 |
| Rushing yards | 4,106 | **73.60%** | 63.20% | **0.21954** | 0.23485 | −0.01530 |
| Rushing TD | 4,106 | 90.36% | 90.50% | 0.07103 | 0.07020 | +0.00082 |
| Solo tackles | 7,555 | 67.29% | 68.22% | 0.20567 | 0.20310 | **+0.00257** |
| Tackle assists | 7,555 | 69.25% | 70.19% | 0.20626 | 0.20247 | **+0.00379** |
| QB hits | 7,555 | 76.93% | 77.07% | 0.15319 | 0.15319 | −0.000002 |
| Passes defended | 7,555 | 79.96% | 80.28% | 0.14155 | 0.14233 | −0.00079 |

**No universal NFL improvement.** Clear strengths in the retrospective
research sample were receiving and rushing yards; multiple QB and
defensive markets deteriorated in Brier; tackles + assists had
essentially unchanged directional accuracy.

The extremely high directional hit rates in low-count touchdown or
defensive markets can arise from synthetic low event rates and
dominant Under selections. They are **not** 80%+ independently
validated market bets.

## Critical limitations and follow-ups

1. **Participation conditioning remains severe:** 36,310 of 107,319
   forecasts lacked a matched weekly player-stat row. Those were
   excluded, making scores conditional on observed participation.
   This must be modeled explicitly or graded via authoritative
   game-specific source status, not retroactively called losses.
2. **Synthetic thresholds, not betting markets:** thresholds are
   role-/market-specific half-integers derived from historical
   training medians, not actual original sportsbook quotations.
   A QB pass-attempt or tackle line may differ drastically from
   an offered prop; model-vs-market profit cannot be inferred.
3. **Historical-source timestamps:** official pregame provider
   receipts, injuries, opponent coverages, exact defensive alignments
   and market quote publication timing were not retrospectively
   available. The candidate roster is inferred from prior
   appearance, not a verified live lineup.
4. **Exposure and selection:** model design was adjusted after
   examining 2024 outcomes in other Pick'em Auditor research;
   sealing this *specific run* prevents direct target-label leakage
   but does **not** erase historical design-selection exposure.
5. **Statistical dependence:** 71,009 player-market rows are not
   71,009 independent experiments; all 16 categories are clustered
   into 18 weekly cohorts, and several stats on the same player
   share identical game/opportunity information.
6. **Real original model family remains untested:** these newly
   trained market-specific ridge learners are *research challengers*,
   not historical Engine A, Engine B, Bayesian A/B or converged
   NUTS production inferencers.
7. **No holdout-based tuning:** do not adjust ridge shrinkage,
   market selection or confidence thresholds using this 2024
   settlement and then reuse these 18 weeks as a final confirmation.
   Use a predeclared forward test with authentic sportsbook lines
   for production decisions.

## Reproduce / independent audit

Project storage directory:
`pickem_runs/experimentB_nfl_2024_all16_weekly_full/`.

```bash
python scripts/nfl_weekly_blind_multimarket_audit.py \
  --root pickem_runs/experimentB_nfl_2024_all16_weekly_full \
  --weeks 18 \
  --out pickem_runs/experimentB_nfl_2024_all16_weekly_full/independent_week18_audit.json
```

The independent run returned `all_lock_chain_verified=true` and
`training_updated_only_after_previous_settlement=true`, with no
invalid market/contract count and no production promotion.

[Full 2024 Deepnote run](https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/Experiment-B-entire-2024-NFL-season-16-market-weekly-blind-training-0931d8cd5e98415480882e8ebe29137e?utm_content=9cc31536-93be-44db-bdeb-06fba3f61410).

No Dell runner, paid training instance, Bayesian refit,
production probability change or Tier promotion was performed.
