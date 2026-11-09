# Pick’em Auditor Reform — Item 4a and Item 5

**Evaluation date:** November 8, 2026. **Status:** 4a numerical code fix and
Phase 5 ranking-replay audit implemented, with prospective acceptance still
required before declaring a statistically validated selection advantage.
No Bayesian training, forecast replacement, ranking-weight optimization or
model promotion was performed.

## 4a. Root cause of 16 noncomplementary consensus probability pairs

The original, frozen
`pickem_runs/2026-11-08/20261108T135631Z/slate_model_comparisons.json`
has SHA-256
`78983420bd4b7b08044a840d23168714b9ffc31ecd8e574c66dad72a18f27960`.
Of 257 NFL 1 PM contracts, 68 had complete two-sided production consensus.
**16** of those 68 had `Consensus_over + Consensus_under != 1` to
tolerance `1e-8`. **15** entered the previously reported 67 officially
settled consensus observations; the remaining contract was not verified for
settlement.

Every affected two-sided ensemble contained four historical families
(Engine A, Bayesian A, Bayesian B, and NUTS), equal historical weights of
15% each plus 40% Engine B. Across all 16 affected pairs, Engine A, Engine B,
Bayesian A and Bayesian B were complementary within numerical tolerance.
The **NUTS population receptions sidecar** was not.

The original `scripts/nuts_slate_shadow.py:evaluate` seeded the posterior
integration with `KEYS` minus `side`. `KEYS` nevertheless included
`forecast_at`, independently set milliseconds apart for the two sides of
an otherwise identical contract. Both sides sampled *different random
posterior draws*, so their reported `q_over` and `q_under` were internally
coherent per side but not complementary across the pair. These are
**Monte Carlo integration errors**, not evidence that the NUTS statistical
training failed convergence.

**Observed test:** all 16 original broken pairs had different original
side-specific seeds; all 16 now share an identical corrected seed excluding
both `side` and `forecast_at` while retaining game, player, stat, line,
fixture, event start and frozen run ID. The maximum absolute NUTS pair-sum
error in those 16 was **2.261 percentage points**; after 15% weighting the
maximum absolute production consensus pair-sum discrepancy was **0.339
percentage points**. This cannot, by itself, account for the
approximately 19.5-point confidence/realized-hit discrepancy in the slate.

### Code correction and guard

- `scripts/nuts_slate_shadow.py`: new `shared_contract_seed` excludes
  per-side `forecast_at` and `side`, uses an exact stable
  run/game/player/stat/fixture/line contract, and rejects missing/invalid
  identity.
- `scripts/slate_model_report.py`:
  `enforce_paired_probability_integrity` compares paired original
  non-push `NUTS` and `Consensus` forecast probabilities. If a pair
  does not sum to one within tolerance, both sides of the affected
  consensus are marked `unavailable` for ranking/publication. If NUTS
  is the source, its displayed probability is also withheld, with the
  **original raw pair values recorded** in
  `paired_probability_integrity`. There is no normalization,
  rewriting, unseen opponent adjustment, or hidden substitution.
  This is a conservative forward guard; original snapshots remain
  immutable.
- `tests/test_slate_model_report.py`: verify shared seed despite differing
  forecast timestamps, different seeds for different opponents and lines,
  fail-closed behavior and preservation of valid complementary pairs.

**Actual-posterior acceptance passed, without retraining.** The cached
official NFL receptions joint NUTS posterior (336,264,670 bytes; manifest:
four chains × 2,000 retained draws, diagnostics: R-hat 1.00986,
minimum bulk ESS 460.39, zero divergences) was read with HDF5. The
unchanged `joint_population_bayes.forecast` formula was evaluated twice
on the same original Amon-Ra St. Brown receptions 6.5 contract, using
different original Over and Under `forecast_at` values but the corrected
contract-level seed. Both produced exactly the same `q_over`
**0.4983248289428103**, `q_under` **0.5016751710571896**, and
`q_push` **0**, total exactly **1.0**. The original archived paired NUTS
conditional probabilities totaled **0.9897555945128014**. This is real
posterior integration, not a refit, synthetic forecast, post hoc historical
correction or statistical validation of market accuracy.

**4a numerical defect can be marked repaired:** source bug traced, shared
seed fixed, actual-posterior replay demonstrated, new paired report guard
tested. **The only remaining operational acceptance** is to observe one
fresh integrated pregame sidecar/report from this patched code with no
noncomplementary pairs and no false production eligibility. The user
does **not** need to supply odds, archives, restart training, or manually
reproduce the NUTS run. Historical November 8 rows must never be overwritten.

## 5. Original top-k optimizer’s-curse audit

The original November 8 `slate_model_comparisons.json`,
`slate_full_universe_research.json`, `slate_top10_evidence.json`, and
pinned NFL 1 PM official settlement were evaluated read-only. The original
ranking is a **research priority**, not a model probability or approved
betting Tier.

`scripts/reform_phase5_selection_audit.py` reconstructs the exact initial
screen, using the original 60/40 ensemble, A/B reliability flags,
same-line market status and multiple archived books, the 58% consensus
screen, 3-percentage-point model/market edge floor, the original
40/25/25/5/5 score, historical exposure receipt, and the original
two-per-player / four-per-game display caps. It requires exact frozen
run/timestamp/fixture/player/stat/line/source-review identity and
reproduces the originally saved top-ten board exactly before joining
any outcomes.

### Exact replay results

| Metric | Result |
| --- | ---: |
| Original frozen Over/Under side rows | 2,436 |
| Original candidate pool that passed all screens | 160 |
| Original top-ten selections reproduced, across NBA/NHL/NFL | 30/30 |
| Original NFL eligible full-slate candidates | 33 |
| NFL eligible at the 1 PM officially verified event time | 10 |
| Settled NFL 1 PM eligible candidates | 10 |
| Of those, selected in the **original full-slate NFL top ten** | 2 |
| Originally selected among full-slate NFL top five and settled 1 PM | 0 |

The exact screen rejects **1,294** candidates under the production/research
gate, **688** below the 58% consensus floor, **272** without the two matched
frozen books and **22** below the +3-point edge floor, leaving **160**.

| 1 PM research subset | n | Wins | Mean frozen model-market edge | Brier model | Same-event-side market Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original top-ten selections scored | 2 | 2 | +14.69 pp | .1100 | .2285 |
| Eligible unselected, same kickoff window | 8 | 4 | +8.75 pp | .2819 | .2396 |
| Entire eligible and settled 1 PM subset | 10 | 6 | +9.93 pp | .2475 | .2374 |

There were **zero** exact overlapping strata with both originally selected
and unselected outcomes after matching NFL market/stat, 10-point original
consensus-confidence band and 5-point frozen edge band.

**Conclusion:** Neither an optimizer’s curse nor a ranking benefit is
demonstrated. Selection is subject to game correlation, opportunity and
market-type confounding; 2 settled selected picks and no exact comparators
cannot identify noise amplification. It would be statistically invalid
to estimate or deploy market-edge shrinkage from this snapshot.

The original top ten were selected from the **full-day slate**; the
official independently verified settlement covers **only 1 PM NFL**
from this archive. Eight other original NFL top-ten entries cannot be
scored as losses merely because their event occurred outside the scoped
1 PM results. NBA/NHL top-ten candidates likewise remain excluded until
independently graded.

### Next evidence for a meaningful selection study

Prospectively freeze the exact entire eligible candidate pool, the order
before top-5/top-10 caps, both model/market side quotes, unique run/game
identifiers, Engine B uncertainty (`relative_se` with version/definition),
and official settlement. Reevaluate every completed slate without
reranking after results. Only when enough **independent dates/games**
are available, compare selected versus eligible-unselected forecasts
within sport/stat/market-confidence cohorts, with paired date/game-cluster
uncertainty, market as the baseline and permuted-score negative controls.
Keep the 60/40 consensus and ranking weights frozen until the prospective
evidence supports an explicit challenger promotion.

### Reproduce read-only

```bash
python scripts/reform_phase5_selection_audit.py \
 --frozen pickem_runs/2026-11-08/20261108T135631Z/slate_model_comparisons.json \
 --review pickem_runs/2026-11-08/20261108T135631Z/slate_full_universe_research.json \
 --board pickem_runs/2026-11-08/20261108T135631Z/slate_top10_evidence.json \
 --settlement pickem_runs/2026-11-08/20261108T135631Z/slate_1pm_nfl_settlement_20261108.json \
 --pinned pickem_runs/2026-11-08/20261108T135631Z/directional_phase1_1pm_nfl_pinned_receipt_v1.json
```

Use `--out` only for a new derived audit receipt; never overwrite a
previous receipt with different content. The script does not train,
recalibrate, revise frozen forecasts or assign approved betting Tiers.
