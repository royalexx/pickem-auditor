# NFL Nov 15, 2026 — Independent WS6 Postgame Audit (v1, research shadow)

**Audit date:** 2026-11-16 (America/Toronto)  
**Branch:** `audit/nfl-ws6-postgame-independent-20261116`, based on `audit/nfl-sunday-ws6-20261115`  
**Original main at inspection:** `912bc7010058092ea735dcda0aa941429194474b`  
**Status:** INDEPENDENT RESCORE EXECUTED; **NOT CERTIFIED OR RELEASE APPROVED**. Audit remains open on source-contract equivalence, tackle credit, distribution completeness, and exact exclusions. No forecasting model, weights, historical frozen files, automations, Tiers or production settings changed.

## Source receipts and real execution

The original composite quote comparison `reports/nfl_20261115_prospective/ensemble_20261115_research_shadow/comparison_original_quotes_1845.jsonl` was independently rehashed as SHA-256 **`0e398b781070ce648b7dc46bf726f6eed850b40e67366de355d516ff028ecc8f`** (1,845 observation rows).

The authoritative J v0.4.2/v0.4.3 `all_market_v04/frozen/759dc467ef3bdc589b3588c7adb59254076e5d071dbf35bf167c408447e56431.ledger.json` had SHA-256 **`759dc467ef3bdc589b3588c7adb59254076e5d071dbf35bf167c408447e56431`** (5,535 model/contract/status rows; 1,455 each J1/J2 forecasts). It is not interchangeable with the older **957-per-model** intermediate `3ba79eba...` ledger or the **58-per-model** original WS6 J subset. Separate simulation files were SHA-256 checked, with freeze times directly read from those files and required before each actual kickoff. The archived J conservative training cutoff was checked against recorded pregame input-building and forecast times. This is a **research chronology check, not complete external source certification**.

All 12 2026-11-15 games were independently retrieved as ESPN `STATUS_FINAL`. Original response bytes and their hashes were preserved within the Deepnote project.

**Deepnote execution:** project `9cc31536-93be-44db-bdeb-06fba3f61410`, notebook `db3b4606715249d3aeee24d584f28134`, success run `71ec6676-2978-4c4e-9aa5-4dae513e5a65`. Output directory: `reports/nfl_20261115_prospective/ws6_independent_postgame_20261116_v1/`.

| Deepnote output | SHA-256 |
|---|---|
| `source_manifest.json` | `475537ecfb05c9e88101fac153498b93945fcbfb41eb7aee512f52302e57cdcb` |
| `independent_scorecard.json` | `18ed769513ab7c7ac76afeabd036d82e82817a1eee606ba3729a335841cc0a4f` |
| `duplicate_conflicts.json` | `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570` |
| `top25_errors.csv` | `096f2816e719940452beffa7a3f2ddac95c8e219291ffed722f0867913701542` |

Output manifest embeds raw ESPN source hashes and all J simulation file hashes. The local project artifacts, not this summary, are the audit data of record.

## Independent, descriptive scorecard

Scores use conditional-on-no-push Over probabilities on deduplicated unique game/player/stat/period/line contracts; duplicate bookmaker quotes remain separately present in source observations. ESPN missing athlete or absent category was treated as unknown, *not zero*. Lower proper score is better. All tackles are marked **provisional ESPN TOT**, pending authoritative solo+assists parity.

| Model | Scored unique | Brier | Log loss | Quote-level originally forecast |
|---|---:|---:|---:|---:|
| S2 original | 843 | 0.289768 | 1.179825 | 1,672 |
| S2 exponentially weighted | 687 | 0.297649 | 1.031561 | 1,469 |
| S2 uniform | 687 | 0.290334 | 1.009465 | 1,469 |
| O2 | 535 | 0.268762 | 0.768485 | 1,191 |
| O3 | 134 | 0.267291 | 0.730162 | 236 |
| O5 | 669 | 0.267242 | 0.756861 | 1,427 |
| J1 v0.4 | 688 | 0.289504 | 0.935049 | 1,455 |
| J2 v0.4 | 688 | 0.280582 | 0.791041 | 1,455 |
| J1 original (earlier, not v0.4) | 33 | 0.240048 | 0.660485 | 58 |
| J2 original (earlier, not v0.4) | 33 | 0.227790 | 0.640015 | 58 |
| Repaired tackles S4 | 91 | 0.262400 | 0.724981 | 91 |
| Repaired tackles O4 | 48 | 0.303669 | 0.847028 | 48 |
| Repaired tackles J1 | 48 | 0.309125 | 0.876883 | 48 |
| Repaired tackles J2 | 48 | 0.305712 | 0.852017 | 48 |
| Repaired tackles J3 | 48 | 0.300963 | 0.843390 | 48 |

**Do not compare unpaired raw averages as model superiority.** No genuine non-tackle J3 v0.4 forecasts exist (all abstained). Earlier postgame preliminary J2/J1 denominators of 692 require reconciliation with independent 688: five quote-level missing ESPN category rows and 66 quote-level absent ESPN athlete rows were quarantined per model, rather than setting zero. The baseline source ledger preserves 78 observations lacking event identity, as well as 1,845 source attempts, 1,695 with a source-timestamped model and 1,477 with descriptive cross-family agreement.

**Quote-level-to-unique reconciliation for J1/J2:** 1,455 quote forecasts; 66 PLAYER_NOT_BOXED and 5 CATEGORY_NOT_BOXED quote rows; 1,384 boxed quote rows reduce by 696 excess identical-contract bookmaker observations to **688 unique scored**. O5: 1,427 − 58 − 13 − 687 = **669**. S2 original: 1,672 − 72 − 13 − 744 = **843**. No conflicting probabilities among collapsed duplicate quotes were detected by this scorer. The 139 J raw quote rows with unresolved original distribution series are **not binary score exclusions**, but reduce the available CRPS/interval subset and require repair of the archive join.

## Same-original-contract paired differences

Difference convention is first model Brier minus second model Brier (positive favors second). All confidence intervals are descriptive **game**-cluster bootstrap percentiles over 11 distinct games and 3,000 resamples, fixed seed. There is only **one event date**, so date-clustered uncertainty cannot be estimated.

| Matched comparison | n | Paired Brier difference | Game-cluster 95% interval |
|---|---:|---:|---|
| J1 − J2 | 688 | +0.008922 | [−0.003406, +0.021625] |
| S2 original − J2 | 656 | +0.025144 | [+0.004099, +0.049876] |
| S2 EW − J2 | 662 | +0.018653 | [+0.000501, +0.039465] |
| O5 − J2 | 652 | −0.019483 | [−0.042866, +0.005195] |
| S2 original − O5 | 663 | +0.034575 | [+0.009755, +0.059150] |
| Repaired S4 − repaired tackle J2 | 48 | −0.024471 | [−0.050986, +0.004774] |

The positive S2-to-J2 and S2-to-O5 deltas are suggestive **on this single-slate, model-development-exposed sample**; simultaneous comparisons, selection, source-contract defects and lack of independent dates rule out promotion-grade claims. J1-v-J2 and O5-v-J2 intervals span zero.

## Distribution and confidence stress

On 615 **draw-backed deduplicated quote contracts**, J1's empirical predictive-interval coverage at nominal 50/80/90/95% was **40.00 / 61.95 / 73.66 / 80.49%**; J2's was **50.57 / 76.10 / 89.76 / 92.85%**. Mean empirical draw CRPS over the same available J1/J2 subset was respectively **16.1078** and **15.6408** in mixed-market physical units; these **must not be compared or interpreted as an aggregate proper-score winner** until one player/stat distribution is counted once and CRPS normalized or stratified by market. The preliminary full-slate J1 76.4% and J2 90.7% nominal 90% coverage are not exactly reproduced on this subset; the 73 missing draw-backed unique contracts need explicit keyed-distribution reconciliation and selection-bias study. Raw model-scoring duplicates and distribution series identity remain separate audits.

For the 688 scored unique J2 original-contracts, **56/103** selected sides with stated confidence ≥80% were correct (**54.37%**), versus 90/153 (**58.82%**) for J1. These are **not independent Bernoulli trials**. Even the descriptive deficit of >25 points from the ≥80% claim is enough to block premium confidence use pending future validation. The preliminary J2 58/105 discrepancy may reflect 4 excluded contracts and needs line-level reconciliation; the scorer did not silently force the preliminary count.

## Adversarial execution and known gaps

**GitHub test source:** `tests/test_ws6_independent_postgame_20261116.py`. **12/12 passed** in Deepnote independent notebook `5aeea806602440619912d3a29253b336`, run `527509e5-c6f7-47db-8a61-222a9fcd8c7d`, with `python -m unittest discover -s tests -p test_ws6_independent_postgame_20261116.py -v`. An earlier direct-script invocation initially failed on its Python package search path, not on any scoring assertion; the corrected invocation passed. Tests challenge reversed outcomes, three-way integer pushes, conditional non-push probabilities, invalid probabilities, duplicate quote conflicts, wrong-event and wrong-player IDs, name collisions, absent categories, non-final events, deterministic CRPS and clustered paired differences.

Remaining scientific blockers, **not repaired or certified**:

1. The recorded WS5 provider-metadata audit found **1,599/1,845** problematic original provider quote identity/line/price reproductions. Time-stamped forecasts and official game outcomes do not establish actual executable sportsbook terms. No market edge, EV, or Tier.
2. ESPN defensive `TOT` was parsed, but independently authorized GSIS combined solo+assists rules/credit parity have not been fully confirmed across all 12 games. Repaired S4/O4/J tackle scores remain provisional.
3. Source certification is incomplete beyond the recorded temporal comparisons: S2/O2/O3/O5 training cutoff, availability, starter verification, provider player-team-and-period matching, and field-level first-receipt pedigree need separate original artifact cross-checks.
4. For J, only 615/688 scored contracts resolved to original predictive draw series; interval/CRPS comparisons exclude 73 unique contracts. Additional per-stat per-game sample/coverage heterogeneity remains. O-family archived full distribution outputs must be independently adapted for CRPS/coverage where available.
5. 25 largest *point forecast errors* are serialized in `top25_errors.csv` with original file references and official outcomes; these are errors, **not causally attributed pregame-assumption mechanisms**. Examples: Ja'Marr Chase ESPN receiving yards 231 vs J1 mean 74.014 (−156.986) and J2 77.352 (−153.648); Joe Burrow ESPN passing yards 409 vs J1 263.391 (−145.609), J2 265.987 (−143.013). Team volume, player role, allocation share and efficiency attribution requires their own authentic pregame component vectors; no after-game oracle substitute is labeled an attainable pregame forecast.
6. Missing/absent player official rows, backup-QB identity, alternate-line settlement definitions, overtime/period rules, and disputed source-book identities still require a row-level independent case audit. The current scorer does **not** justify treating all 1,845 quotes as legitimate offers or bets.
7. Output is initially create-once; a later second identical invocation requires idempotent handling of the `top25_errors.csv` writer to re-execute without an output-exists error. The initial receipt is immutable and was not overwritten.

**Release decision: NO-GO / SHADOW ONLY / SCIENTIFIC AUDIT INCOMPLETE.** The output establishes a reproducible first independent baseline and adverse high-confidence signal, but does not meet original full acceptance, independently certify product settlements, justify model changes or auto-release. Reconcile source/period/team and official combined tackle parity first, recover missing J draw keys, independently validate original frozen factors, then accumulate more distinct prospective dates. Keep models, weights, source files, automation and Tiers unchanged.
