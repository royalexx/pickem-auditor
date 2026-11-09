# Reform Phase 4 — contract-level settled-forecast audit (November 8, 2026)

**Status:** Completed as a **read-only, descriptive** audit. Not a calibrated
production model, model-selection certificate, profit estimate, or promotion.

## Immutable input evidence

All figures in this report were computed with
`scripts/reform_phase4_scorecard.py` from two **separate** cohorts:

1. **Prospective frozen 60/40 NFL 1 PM slate on 2026-11-08.** Frozen comparison
   `pickem_runs/2026-11-08/20261108T135631Z/slate_model_comparisons.json`,
   SHA-256 `78983420bd4b7b08044a840d23168714b9ffc31ecd8e574c66dad72a18f27960`.
   Official settlement
   `slate_1pm_nfl_settlement_20261108.json`, SHA-256
   `5838b4854763f078c150829708ed6440da71ef3b62cbfd56bb4645a21f617f99`.
   Both match the previously pinned official Phase 1 receipt, which validated
   the 60/40 policy, pair identities, kickoff chronology and official game
   sources. **Full original feature/source archives were not independently
   recovered**; the Phase 1 receipt says so explicitly.
2. **Archived November 5–7 research comparison.** Original backtest file
   `independent_2026_nov5_nov7_backtest.json`, SHA-256
   `9ea9b695419a0d065f50eac8f272d4356b20fbf60170e049c2f02c41b108070a`.
   The scoring code authenticates its three original CSV archive hashes,
   matches pre-kickoff forecast times against recorded final events (including
   Final/OT and Final/SO), and checks player-stat actual versus winning side.
   These outcomes were matched retrospectively to official boxscores; source
   publication times and all original feature bytes are **not** independently
   archived. Do not merge this with the current 60/40 prospective result.

No game is counted twice because its Over and Under snapshots are
complementary. Each independently settled, non-push **player/stat/line**
contract contributes at most one directional observation **per model**.
Unavailable models and tied directional probabilities abstain. A same-cohort
comparison includes only the **identical** contracts with both models.

## November 8 prospective NFL 1 PM

There were 257 frozen market contracts, 253 officially verified and four
unverified exclusions. Current production consensus was available on only
67 of the 253; the remaining contracts are not recorded as production failures.

| Model | Scored contracts | Hits | Directional accuracy | Brier | Log loss | Mean confidence minus hit rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Engine A | 252 | 141 | 56.0% | .2735 | .8226 | +7.8 pp |
| Engine B | 218 | 119 | 54.6% | .2516 | .7005 | +5.6 pp |
| Bayesian A | 220 | 116 | 52.7% | .2562 | .7074 | +9.7 pp |
| Bayesian B | 213 | 114 | 53.5% | .2540 | .7020 | +7.7 pp |
| Strict NUTS | 55 | 31 | 56.4% | .2268 | .6416 | +8.4 pp |
| **Production consensus** | **67** | **25** | **37.3%** | **.2655** | **.7238** | **+19.5 pp** |
| Market | 220 | 127 | 57.7% | .2492 | .6916 | -4.1 pp |

**These rows have different coverage and are not head-to-head league tables.**

The strictly matched consensus/market subset contains **65 contracts from only
six independent NFL games**:

| Metric | Consensus | Market |
| --- | ---: | ---: |
| Correct direction | 24/65 (36.9%) | 36/65 (55.4%) |
| Brier | .2658 | .2568 |
| Log loss | .7243 | .7071 |
| Average selected probability | 56.9% | 53.6% |
| Selected Over | 32.3% | 41.5% |
| Actual Over on this identical set | 52.3% | 52.3% |

Consensus-minus-market Brier difference is **+.0090** and log-loss difference
**+.0172** (both negative for consensus's comparative performance). However,
the paired game-block interval is **unavailable**, with only six independent
games against a minimum of eight; no performance significance or model
promotion is claimed.

Consensus confidence bins (no ≥80% consensus picks in this cohort):

- **50–60% predicted:** 15/51 correct (29.4%), mean predicted 54.3%.
- **60–70% predicted:** 9/15 correct (60.0%), mean predicted 63.9%.
- **70–80% predicted:** 1/1 correct; insufficient evidence.

The apparent calibration failure is primarily in the large, low-confidence
50–60% band, **not** proof that 80%-probability picks are consistently wrong.
The low-confidence sample also has strong directional skew. For all 67
consensus-available props, the model selected Over 31.3% of the time while
Over actually won 52.2%. This suggests an Under-selection hypothesis to
investigate, not a proven cause.

For NFL tackles + assists alone, consensus was available on **28** contracts,
selected Over on **17.9%** versus actual Over **46.4%**, with **42.9%** hit
rate. Bayesian A and Bayesian B also selected relatively few tackle Overs
on their different coverage sets. Actual snap share/defensive opportunity
was not collected on this cohort; no tackle exposure cause can be assigned.

## Older November 5–7 research cohort (NOT current production)

Of **2,024** archived contracts, 645 had independently matched official
final outcomes. Excluded: 1,192 absent from official player boxscores,
183 without a completed matching game, four stats not explicitly verified.
Three original CSV archive digests were checked.

All-availability numbers (not head-to-head):

| Model | Scored contracts | Directional accuracy | Brier | Mean confidence minus hit rate |
| --- | ---: | ---: | ---: | ---: |
| Engine A | 643 | 44.8% | .2882 | +17.9 pp |
| Engine B | 582 | 47.3% | .2667 | +10.3 pp |
| Bayesian A | 577 | 50.1% | .2847 | +11.6 pp |
| Bayesian B | 581 | 47.0% | .2873 | +15.2 pp |
| Market | 483 | 50.3% | .2485 | +2.5 pp |
| Earlier 70/30 diagnostic | 331 | 43.2% | .2751 | +15.8 pp |
| Retrospective counterfactual 60/40 (3 historical families) | 518 | 43.8% | .2737 | +14.4 pp |

On **482 identical** historical contracts where both Engine A and market
made directional predictions, Engine A scored 46.5%, Brier .2802, log loss
.7713, while market scored 50.2%, Brier .2485, log loss .6902.

The backtest's original `original_reliable` field marks **348** contracts
as reliable and **297** as false/missing. This is a historical reliability
flag, **not equivalent** to contemporary Tier publication eligibility.

Within the **273 original-reliable, same-contract** Engine A/market cases:

| Metric | Engine A | Market |
| --- | ---: | ---: |
| Directional accuracy | 46.5% | 53.8% |
| Brier | .2801 | .2464 |
| Log loss | .7614 | .6859 |
| Mean confidence minus hit rate | +13.4 pp | -0.7 pp |

This makes a modeling/selection diagnosis worthwhile even after removing
some low-quality historical forecasts. But there are only **three independent
dates**, far short of the 20 required for date-block inference.

## Methodological warnings and next work

- **Market two-way probabilities:** Older archived market Over and Under
  probabilities often do not add to exactly 1. They were **not** silently
  normalized, and Brier/log loss apply to the originally selected binary
  event, not to a manufactured coherent probability distribution.
- **Consensus nonunit sidecars:** Fifteen of the 65 matched November 8
  consensus/market contracts have nonunit two-way sums propagated from
  the historical NUTS sidecars. This is visible in the audit and deserves
  a separate numerical-invariant repair; it cannot be hidden by normalizing
  past model probabilities.
- **Limited dates, correlated players:** Player props from one NFL game are
  not independent, nor are markets on a date. Only six games are shared by
  the prospective consensus/market cohort and only three days by the
  historical backtest. **Neither has a certification-quality confidence interval.**
- **Historical pregame integrity:** Previous morning aggregate reports scored
  complementary Over/Under rows separately, yielding a mechanical 50% hit
  rate. This audit instead counts one actual binary outcome per contract.
  Missing records are not assigned zero production.
- **No optimizer's curse conclusion:** Top-k selection bias has *not yet*
  been isolated by matching selected to eligible-unselected forecasts
  within equivalent confidence/market strata. This is checklist item 5.
- **No cause identified:** Probability distribution misspecification,
  partial exposure models, opportunity changes, market selection and
  noisy outcomes are still competing hypotheses.

### Reproduction

Run read-only on a Deepnote checkout with the original archived files:

```bash
python scripts/reform_phase4_scorecard.py \
  --frozen pickem_runs/2026-11-08/20261108T135631Z/slate_model_comparisons.json \
  --settlement pickem_runs/2026-11-08/20261108T135631Z/slate_1pm_nfl_settlement_20261108.json \
  --pinned pickem_runs/2026-11-08/20261108T135631Z/directional_phase1_1pm_nfl_pinned_receipt_v1.json \
  --historical pickem_runs/2026-11-08/20261108T135631Z/independent_2026_nov5_nov7_backtest.json \
  --archive-root . \
  --out reports/reform_phase4_scoring.json
```

Run the regression tests without training:

`python -m unittest discover -s tests -p test_reform_phase4_scorecard.py -v`

**Next:** Item 5 (replay top-5 and top-10 historical selection and test winner's
curse), followed by prospective validation of the item 6 NFL tackle
opportunity challenger. Do not change the frozen 60/40 production policy.
