# NHL context challenger implementation audit — 2026-10-30

Source inspected: `royalexx/pickem-auditor` main
`79403b03543134bf7e2a319699112d6e1e132123`.
Scope: the next model structure and local training plan from the Bayesian
Training discussion. Existing production rankings and the converged saves
posterior are not replaced. No large local training job was dispatched.

## Delivered

- Separate team, skater and goalie contracts in atomic game bundles; independently
  stored pregame matchup snapshots, plus provider/version-aware xG inputs.
- Source-preserving, resumable official boxscore/PBP collection, raw compressed
  source archives, immutable normalized games, coverage audit against supplied
  IDs and conservative count/identity checks.
- Pregame-only rolling features, partial pooling of venue splits, bounded player
  exposure and stat-specific opportunity covariates.
- Joint hierarchical saves model: workload -> shots faced -> saves. SOG, hits and
  blocks have their own count-rate definitions. Missing attempts block the
  contextual blocks experiment.
- Explicit plan/collect/audit/freeze/fit/evaluate lifecycle, frozen training and
  holdout input universes, design/posterior/source checksums, and sampling receipts.
- Exact-cohort refit adapter for the existing hierarchical model, with the same
  all-effect convergence gates. No reuse of a future-trained posterior on old
  holdouts and no silent shrinking of paired comparison populations.
- Native Windows training instructions, pilot/full-history campaign, ablations,
  chronological evaluation plan and requirements for eventual promotion.

Implementation details and runnable commands:
[NHL_CONTEXT_CHALLENGER.md](NHL_CONTEXT_CHALLENGER.md).

## Sampling actually performed

**All new training here used synthetic data, not real NHL observations.**
Two small four-chain saves fits each used 224 training goalie starts from 112
synthetic games, eight goalies and four teams. Each chain retained 1,000 draws
after 1,000 warmup iterations; two chains ran concurrently. Both posteriors were
saved, reloaded and independently rechecked with all stochastic variables,
derived player/team effects and off-diagonal LKJ correlation included.

| Diagnostic | Context features | Base features |
| --- | ---: | ---: |
| Maximum R-hat | 1.003971 | 1.005481 |
| Minimum bulk ESS | 1,020.37 | 702.42 |
| Minimum tail ESS | 1,107.45 | 739.85 |
| Divergences | 0 | 0 |
| Minimum BFMI | 0.7804 | 0.8219 |
| Max-tree-depth hits | 0 | 0 |
| Four-chain strict convergence check | Pass | Pass |
| Initial fit wall time, compilation included | 96.2 s | 81.8 s |

These timings describe this tiny synthetic CPU dataset only. They are not an
estimate of full NHL training speed on the laptop. First graph compilation took
longer during the separate smoke test; compiler cache state matters.

## Holdout actually evaluated

The frozen synthetic holdout contained 76 starts from 38 games. Both models used
the same exclusive training cutoff and the same 25.5 research threshold. Each
forecast integrated 2,000 latent draws. No candidates were lost to unseen IDs.

| Synthetic holdout metric | Context challenger | Base challenger | Gamma-Poisson control |
| --- | ---: | ---: | ---: |
| Brier score | 0.27810 | 0.27743 | 0.27920 |
| Binary log loss | 0.76115 | 0.75904 | 0.75977 |
| Mean negative count log density | 3.55138 | 3.55219 | 3.72858 |
| Nominal 90% interval coverage | 80.3% | 78.9% | Not calculated |

Context minus base Brier difference: **+0.000665**, with game-cluster bootstrap
95% interval **[-0.001242, +0.002736]**. The interval spans zero. The control is a
transparent frozen gamma-Poisson benchmark, not the old converged hierarchical
posterior. The exact-cohort incumbent adapter is implemented and its row
conversion is tested; no full real-NHL incumbent/challenger comparison was run.

The synthetic results are mixed and the outcome intervals under-cover in this
small test. They do **not** establish that adding context improves prediction.
Workload tails, removal risk and calibration require explicit investigation
before any promotion. Do not tune a model to make this particular holdout pass.

Machine-readable receipt:
[nhl_context_synthetic_2026-10-30.json](../validation/nhl_context_synthetic_2026-10-30.json).

## Audit findings corrected during implementation

1. **Cutoff leakage:** training now requires target availability before cutoff,
   not just an earlier game start. Current and future outcomes are excluded
   before every rolling calculation. Backfilled availability is explicitly an
   approximation, separate from true first-recorded availability.
2. **Count/exposure conflation:** goalie saves reconcile to faced shots and goals;
   team SOG, empty-net/unassigned shots, partial appearances and actual game
   duration are preserved separately. The saves likelihood does not duplicate
   the same events with an additional team-shot likelihood.
3. **Forecast identity mixing:** feature records bind game/player/team/opponent/
   home/position, preventing reuse of another player's or team's same-time features.
4. **Probability bookkeeping:** integer pushes are explicit; binary metrics
   exclude pushes and normalize the remaining probability mass. An independent
   numerical sum verifies the NB/binomial thinning identity to 12 decimal places.
5. **Diagnostic memory blow-up:** `Dataset.to_array()` broadcast unrelated player,
   team and coefficient dimensions into a Cartesian product. This caused a
   recheck process to exhaust its memory during the audit. The new checker and
   the two existing joint-model extraction helpers now flatten each variable
   separately. Diagnostic extrema/thresholds remain the same, with linear rather
   than broadcast-sized extraction. A regression explicitly prohibits that
   broadcasting path. Important derived effects are also checked.
6. **ArviZ/PyMC API compatibility:** the new checker handles PyMC 6 DataTree output
   explicitly; multiple-variable Dataset selection is performed after conversion.
7. **Existing flaky test:** the cached-source integrity test selected an arbitrary
   filesystem entry; it could tamper with a snapshot already excluded by time.
   It now deterministically selects a cutoff-eligible snapshot. Production cache
   selection and integrity behavior are unchanged.
8. **Preparation cost:** player/team/season ID maps and team-history lookup caches
   replace repeated linear searches. Posterior arrays are flattened once per
   evaluation cohort; joint posterior parameter pairing is preserved.

## Executable verification

- Full offline suite in the standard-library production environment: **848 tests,
  pass, six optional-dependency/opt-in skips**.
- Dedicated new-model numerical environment: **one opt-in real NUTS test, pass**;
  all four market graphs, multi-season graph branch, two independent short chains,
  strict rejection of the intentionally under-budget fit, integer push accounting,
  bounded exposure, identity checks and exact posterior file roundtrip.
- Existing isolated joint-model inference/diagnostic suite: **seven tests, pass**,
  including real NHL and NBA/NFL NUTS sampling after the memory extraction fix.
- Two four-chain synthetic fits passed the broader convergence recheck above.
- Python compilation, workflow YAML parsing and patch whitespace checks passed.

The short-chain smoke's diagnostic override exists only inside its test to
exercise scoring interfaces. The CLI always recomputes strict diagnostics and
cannot use that override. Ordinary CI now runs the new numerical smoke in the
existing isolated inference job.

## Remaining boundaries

- The official NHL HTTP endpoint returned **403** from this workspace. No live
  source normalization or real context backfill is claimed. The local collector
  and source-shaped offline fixtures are ready; run the real data collection on
  the existing Windows machine, then inspect schema/coverage failures before fits.
- The old saves/minutes warehouse does not contain the missing contextual inputs;
  listing its game IDs does not magically recover team/PBP history. The collection
  plan and coverage audit do not certify the official schedule is complete.
- xG provider ingestion, situation-specific splits, shot locations, projected
  lineup features and measured tactical schemes are not collected by this patch.
  xG inputs require source, model vintage and actual availability provenance.
- The exposure distribution is a first bounded model, not a fitted removal,
  injury or empty-net decision process. Skill is not yet a player-season random
  walk, and paired goalie game pace is not jointly modeled.
- Fixed research thresholds are not archived sportsbook lines. No market edge,
  real calibration, real predictive superiority or approved picks are claimed.
- Statistical models remain conditional on starting/appearing. Existing research,
  status verification, Engine A/B weights and publication gates are unchanged.

The concrete next step is a source/coverage-verified local saves pilot, followed
by the common-cohort incumbent comparison and predeclared chronological tests.
