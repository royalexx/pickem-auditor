# Phase 1: directional forecast validation without retraining

**Research contract:** docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md

**Current phase:** read-only validation foundation. **No trained model, deployment
weight, Tier threshold, ranking gate or running Dell job changes.** Future
opportunity modeling, role priors, stacking and calibration are independent
challengers; none are deemed deployed by this phase.

## Immutable reference

The baseline source manifest is:
  config/directional_research_baseline_20261108.json

It pins:
- the approved full Deep Research study (November 8, 2026);
- the canonical implemented research contract;
- the exact production policy version and Git **blob SHA**, so changing the
  60/40 policy invalidates the baseline;
- the source-pinned November 8 all-sport comparison file **SHA-256**;
- the original frozen source run ID and code SHA;
- the November 8 NFL 1 PM evaluation cohort and negative audit findings.

The frozen archive lives in connected Deepnote:
  Project: 9cc31536-93be-44db-bdeb-06fba3f61410
  Folder: pickem_runs/2026-11-08/20261108T135631Z/
  Frozen: slate_model_comparisons.json
  Settlement: slate_1pm_nfl_settlement_20261108.json

The comparison file is the authoritative frozen **model forecast record**.
Its fingerprint does not prove every original bookmaker/lineup/injury provider
payload was archived; the original source snapshot bundle was incomplete.
Every future slate must archive and checksum those pregame source payloads.

## Reproducible scoped replay

From repository root with Python 3.10+ and the Deepnote frozen JSON files
available locally (no network needed for the script):

    python scripts/directional_phase1_validation.py \
      --comparison /path/to/slate_model_comparisons.json \
      --settlement /path/to/slate_1pm_nfl_settlement_20261108.json \
      --baseline-manifest config/directional_research_baseline_20261108.json \
      --policy config/production_consensus.json \
      --sport NFL \
      --event-start 2026-11-08T18:00:00Z \
      --output /path/to/new/directional_phase1_1pm_receipt.json

The full archive source bytes are SHA-256 verified **before** the evaluation
view is reduced to NFL 1 PM. Other sports/times are not misreported as missing
postgame results. Identical reruns may reuse the same receipt, but overwriting
the receipt with different computed content is blocked.

To run all supported source-provenance checks without settlements, omit
the --settlement flag. To check an independently verified feature sidecar,
pass --features /path/to/feature_receipts.json with an object containing
a features array. Every included feature requires exact frozen contract
identity, verified status, an HTTPS source URL, source ID, published_at and
retrieved_at **at or before the earliest over/under forecast timestamp**.
A missing feature simply isn't authorized as a contextual numerical effect.
Never manufacture evidence or assume last week's status persists.

## Strict rejection behavior

The script returns exit status 2 and does not write an audit receipt for:
- mismatched frozen source or baseline production policy fingerprints;
- duplicate/missing over or under, model status/probability mismatch,
  asymmetric availability, wrong run or incoherent original probabilities;
- unknown timezone, model generation after kickoff, source/market observation
  after original forecast, or retrieved feature after forecast;
- wrong original line/player/event identity, synthetic winning side, duplicated
  settlement, missing official gamebook attribution;
- an unexplained change to original 60/40 historical family eligibility or
  production weights.

It preserves small known NUTS over/under non-unit sidecar probabilities
and their **exact mathematically inherited 60/40 effect**, *only* as explicit
audit warnings. It never rescales the frozen values or changes the winning
direction.

Original paired sides may have slightly different timestamps because they
were recorded sequentially. Both must remain before kickoff and their
snapshots must be within five minutes of each other. This is not authorization
to mix arbitrarily separate market quotes or runs.

## Read-only scorecard definitions

- One player-stat-line-event contract gives one realized over/under.
- Official final actual over/under = compare actual stat to original line;
  **push** is excluded from binary accuracy and reported distinctly.
- Inactive, unverified/missing gamebook and missing settlement remain missing,
  never counted as losses, zero stats or fabricated model predictions.
- Each model uses its original frozen *preferred side* and frozen conditional
  non-push probability; ties and unavailable models abstain.
- Individual-model all-covered results have their own denominators. The
  consensus cohort uses only the verified settled contracts with an
  originally eligible 60/40 probability; never compare raw independent
  sample hit rates as though paired.
- Scores: directional hit rate, Brier and log loss, mean predicted confidence,
  share of predicted overs and observed overs, and abstention/coverage.
- Bootstrap resamples entire official game IDs, never individual props.
  Fewer than eight independent games reports an **insufficient games** flag
  instead of a misleading pseudo-confidence interval.
- A bootstrap interval is descriptive only. No Tier, staking, value,
  promotion, or calibrated-probability certificate is conferred.

## Actual canonical replay at Phase 1 creation

Full November 8 all-sport archive: 2,436 forecast sides, 1,218 paired
player-stat-line contracts, 571 having an eligible consensus across the
whole slate. With NFL 1 PM evaluation window selected: 514 sides,
257 contracts; 253 with verified official actuals and four unverified;
68 consensus forecasts and 67 settled, because an inactive player
cannot be scored as zero.

On the **same 67**: 60/40 **25 hits / 67, Brier 0.2655153**; Engine A
31/67; Engine B 31/67; Bayesian A 28/67; Bayesian B 28/67;
strict NUTS only 5/15; market 36/65. Mean chosen-side consensus
confidence 56.807%; actual accuracy 37.313%. The model selected
21 overs, 46 unders, while 35 outcomes were overs and 32 unders.
The 67 settled forecasts came from only **six independent games**:
the cluster-bootstrap promotion test remains **underpowered**.

Numbers are a retrospective baseline, **not** a backtest on enough games,
and are not proof of causal responsibility or a new profitable side.

## Phase 1 tests and Phase 2 dependency

    python -m unittest discover -s tests -p test_directional_phase1_validation.py -v
    python -m unittest discover -s tests -p test_production_consensus.py -v
    python -m unittest discover -s tests -p test_slate_forecast_scope_audit.py -v

The research intake process for Phase 2 must create versioned, time-indexed
opportunity and lineup sources. Only after those sources are available
**at original forecast time** can they enter a position/role-specific
forecast challenger. Training, recalibration and promotion on retrospectively
reconstructed November 8 forecasts is prohibited.

## Completion criteria

Phase 1 is complete only once the baseline manifest, AGENTS instructions,
the read-only validator, adversarial unit suite and **real source SHA-pinned
replay** all pass on a committed revision. Any missing pregame source
evidence is reported explicitly as a gap; passing time integrity for the
existing model sidecars does not establish future feature completeness.
