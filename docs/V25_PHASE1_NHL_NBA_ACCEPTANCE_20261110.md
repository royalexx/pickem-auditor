# V2.5 Phase 1 — NBA/NHL scoped infrastructure acceptance (November 10, 2026)

**Decision: INFRASTRUCTURE ACCEPTED for NBA and NHL.** This records implementation/replication of the governing V2.5 Phase 1 tickets P1-01–P1-06 against a genuine Phase 0R-certified live input archive, with **no claim of predictive superiority, release-ready Tier status, or real-money edge**. NFL and full V2.5 joint-game simulation are out of scope.

## Fixed, genuinely pregame source evidence

- Live collection: Deepnote run `ccd5d53d-6583-4380-97ed-9fda64e90559` (success), run stamp `20261110T180409Z`. Original producing commit `e5635d8fd8444a3144174cf019924d2010cdbca8`.
- Original immutable bundle SHA-256: `76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6`.
- Full prepared universe: **1,314 attempted forecast sides**, **712 accepted sides**, **602 rejected sides** (438 unpinned external context; 164 unavailable/unverified markets).
- **356 paired, unique full-game player/line contracts:** NBA 250 (500 original sides), NHL 106 (212 original sides); NHL here is shots on goal only. There were **1,783 SHA-checked frozen source objects**.
- The strict Phase 0R checker is called for every original row, including the original PropLine quote-level URL/event/athlete/stat/book/price/time lineage; any rejection fails the replay rather than disappearing from the denominator.

## Implemented Phase 1 contracts

| Ticket | What is now executable and verified | Scientific/data boundary |
| --- | --- | --- |
| **P1-01** canonical event, sport, stat, period, market, source, distribution, Over/Under/Push | Existing `v2/contracts.py`, `v2/stat_registry.py`, immutable quote/forecast objects and exact support rules; current adapter validates all frozen original row identities | Not a replacement for the underlying real market's settlement rules or source reliability |
| **P1-02** simple, frozen baseline set | New `v2/nhl_nba_phase1.py` computes last-five per-workload Poisson and peer-rate shrinkage using ONLY the frozen game-history bytes, plus original two-sided no-vig market; the frozen 60/40 V1 adapter abstains when source consensus is preliminary | All 356 new simple forecasts are **counterfactual shadow controls computed at replay**, not forecasts historically issued at the original freeze. Original NBA/NHL source lacks verified positions; peer prior is `same_sport_stat` pooled, **not falsely called a position-specific model**. There are 0 finalized V1 probabilities in this particular original batch |
| **P1-03** deterministic full-universe prequential/evaluation harness | `scripts/v25_phase1_nhl_nba.py` reconstructs source archives in an isolated directory, binds all attempted candidates, produces exact source/quote hashes, one score per settled contract, Brier/log-loss, matched comparisons and game/date-cluster intervals; existing `v2/rolling.py` covers time-ordered historical research folds | Genuine real-offer rolling origins beyond Nov 10 and event/date-cluster performance require additional certified daily slates and genuine settlements |
| **P1-04** time/source/support/settlement tests | Original byte tampering, duplicate and missing candidate, precise/date-only history, blocked future history, erroneous preview, exact result, official raw-source digest, invalid outcome, push/period and postgame/original confusion red-team tests | A date-only historical NHL observation is allowed only on a strictly earlier UTC day; same-day requires genuine precise timestamp |
| **P1-05** full-distribution and joint scoring API | Existing `v2/evaluation.py` and `v2/joint_evaluation.py` implement analytical Brier/log-loss, CRPS, Energy Score and `VS_0.5`, with analytic examples and adversarial invariants in `test_v25_phase1*.py` | No authentic, coordinate-matched NHL/NBA joint scenario ensemble is archived for this run; **Energy/Variogram are unavailable rather than fabricated** |
| **P1-06** frozen experiment contract | `config/experiment_specs/v25_phase1_nhl_nba_20261110.json` locks accepted markets, source hashes, cohort, seeds, result handling, baseline logic, independence/rollback and no-promotion caveats | Neither 2024 historical reconstructed synthetic lines nor prior trained-on 2025 are untreated prospective holdouts; no false 2025 independence classification |

## One-command deterministic reproduction

From repo root with Python 3.10+, download/mount the **original** Deepnote project artifacts (never replace them with reconstructed current-day pulls):

```bash
python scripts/v25_phase1_nhl_nba.py \
  --bundle 'pickem_runs/2026-11-10/20261110T180409Z/live_pool_2026-11-10_afternoon_76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6.json.gz' \
  --attempts 'pickem_runs/2026-11-10/20261110T180409Z/all_prepared_props_attempts.json' \
  --code-commit e95cb5009a9c2720db16f039f8122dfb4f54f778 \
  --output 'reports/v25_nhl_nba_Nov10_new_immutable_receipt.json'
```

The `--code-commit` must be the exact implementation revision being run, not a purported historical model-training commit. The original producing SHA is recorded separately inside the receipt. No output may overwrite its input or a prior receipt. Two independent executions with the same code and input produced **byte-identical outputs**. Optional later scoring requires both `--official-settlements` and `--settlement-source-root`, plus exact market identity, a verified provider URL, original raw-source SHA-256 and chronological retrieval/settlement times.

**Saved one-command real-slate receipt** (Deepnote project `9cc31536-93be-44db-bdeb-06fba3f61410`):

`reports/phase1_nhl_nba_certified_20261110_original_batch_e95cb5009a9c.json`

Its actual bytes SHA-256: `1e8dec3661501d1a74e3212e5aacfb91a3c5483cd5565fb68d137a08d88d8949`. All 356 outcomes currently have `pending_official_settlement`, so every numerical proper score is **null**, not zero.

## Independent acceptance evidence

1. Independent Deepnote QA run `5cb468f7-b97a-496b-bf97-2ca1ebc7f94f`: **101/101 targeted tests passed** across seven suites, including 11 new scoped contract/settlement adversarial tests; replay completed twice, identical receipt bytes.
2. Independent mathematical/data verification `6a63a7ff-4e10-4619-8e63-fa0832a1d6fa`: reconstructed all **356 last-five exposure × historical count rates**, all **356 de-vig probabilities**, all **712 original side hashes**; verified 1,783 source objects, all 1,314 attempted rows and 602 specific exclusions. Zero mismatches or future-label consumption. Evidence: `reports/phase1_nhl_nba_20261110_independent_acceptance.json` in Deepnote project.
3. Previously accepted Phase 0R run and original quote audit: strict 712/712 source-bound rows; 1,998 original bookmaker price references linked to the API collection; no synthetic pregame timestamps introduced.

## Explicit hold and next workflow

**P1 NBA/NHL infrastructure status = ACCEPTED.** No scores or prospective skill assertions exist before independent official settlement. The replay cannot test market-versus-model superiority, role-conditional shrinkage, or joint Dependence without authentic pregame positional/ensemble inputs. Preserve the complete eligible/rejected denominator, the current engine comparison chart and frozen original V1 inputs. **Tier 1/2 publication, production weights, Bayesian/NUTS promotion, heavy training, and paid feed acquisition remain blocked.**

After certified morning settlement receipts are available, run a separate read-only outcome replay with the frozen original offers and raw official source hashes. Accumulate independent events/dates before treating clustered confidence intervals as meaningful. Phase 1.5's signed error-priority/power decision remains the independent gate before selecting a Phase 2 expensive modeling pilot.

**Rollback:** omit/disable `v2/nhl_nba_phase1.py` and the new CLI from research usage; no production pipeline wiring, daily automation, model weights or legacy results were modified by this Phase 1 patch.
