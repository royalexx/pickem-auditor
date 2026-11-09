# Reform Step 10 — Beta calibration and global market stack

**Scope:** research-only challenger implementations. No trained calibration
coefficients, historical revisions, new sportsbook quotes, Tier promotions,
NUTS training, or changes to the frozen production 60/40 blend.

## Methods and mathematics

`scripts/reform_step10_calibration_shadow.py` evaluates two global,
regularized, **predeclared** alternatives when enough source-certified,
same-contract, chronological nonpush observations eventually exist:

1. **Beta calibration of production consensus**
   `sigmoid(c + a*log(p_over) - b*log(1-p_over))` with nonnegative
   `a,b`. The parametric family contains the identity exactly at
   `a=b=1,c=0`; it can leave an already calibrated classifier alone.
   Optimization uses the existing `fit_blend.fit_logistic` with L2
   penalty 20 toward that identity, and rejects negative/nonmonotone
   solutions rather than deploying them.
2. **Global logistic market stack**
   `sigmoid(intercept + w_model*logit(p_consensus_over) +
   w_market*logit(p_market_over))`. The L2 prior is
   `intercept=0,w_model=w_market=.5`. This is global partial-pooling
   regularization, not a position/market segmented mixture of experts.
   Market-only is represented within the stack family at
   `w_model=0,w_market=1,intercept=0`.

The research candidates are evaluated against **both the original
production consensus and the same-contract market**, with binary Brier
and log loss, directional accuracy and mean predicted/realized Over share
on the *identical* later holdout contracts. Paired uncertainty resamples
**entire future dates**, never individual correlated legs.

Beta and stack are for **P(Over | no push)**. They do not repair push
probabilities or three-outcome count distributions. Pushes, voids,
noncomplementary pairs and unavailable market/consensus quotes are
excluded rather than silently relabeled as Unders. A future 3-class
push-aware calibration would require separate predeclared math.

## Strict fitting/validation gates

- Minimum **300** chronological training contracts from at least
  **20 independent dates**, plus **100** later untouched evaluation
  contracts from at least **20 further dates**. This is a *minimum*, not
  a universal sample sufficiency guarantee.
- Model and market must be original, coherent two-sided probabilities
  on the **same official settled player/stat/line/game contract**.
- Immutable original provider feature/market publication bytes,
  pregame retrieval times, identity and hashes must be independently
  verified. Pinned downstream results alone are not sufficient.
- Model parameters use training results only; the holdout cannot
  influence fitting, cohort segmentation, confidence cutoffs, or
  model selection.
- The code contains **no production writer or config-emission path**.
  Even a research winner is not independently audited production
  approval. The existing M2/M3 stack in `fit_blend.py` retains its
  separate source/chronological promotion guard.
- No by-position or by-stat Beta calibrators are fitted before a
  substantially larger source-certified cohort supports partial
  pooling and independent external holdout evaluation.

## Executed original November 8 NFL 1 PM archive

The exact SHA-pinned settlement and production comparison were read
through `reform_phase4_scorecard.load_nfl_slate` in a detached,
read-only Deepnote run.

| Evidence quantity | Result |
| --- | ---: |
| Original official settled contracts | 253 |
| Coherent, same-contract original consensus and market pairs | **50** |
| Missing or noncomplementary comparison pairs | **203** |
| Independent future evaluation dates | **1** |
| Full point-in-time feature source coverage verified | **No** |
| Beta parameters fitted | **No** |
| Stacking parameters fitted | **No** |
| Any production model/tier/weight changed | **No** |

The earlier standalone Step 8 fixed 50/50 logit scenario showed
consensus Brier .267215, equal-logit scenario .260017 and market-only
.256062 on its 50 same-contract NFL outcomes. These were
**unfitted** descriptive probabilities; the market-only baseline
remained better. Step 10 does not post-hoc fit a calibrator to improve
that one-slate result.

## Independent method tests

Tests exercise the exact Beta identity, monotonic beta slopes, the
market-only stack identity, no duplicate contract or invalid
two-sided pair, pushes excluded rather than Under, 900 observations
on one date failing the chronology gate, 39 training/evaluation
dates failing, source-integrity failure on a synthetic 1,600-contract
cohort, feasible fully verified 45-date synthetic fitting with
non-exported coefficients, proper-score/date-block intervals,
and **changing every heldout label does not change the training
coefficients**. These synthetic tests validate mathematical code paths,
not real player-prop predictive accuracy.

## Next source-dependent acceptance

Continue freezing pregame original A/B/Bayesian/NUTS/consensus/market
forecasts, all market and lineup provider receipt bytes and official
outcomes for many separate slates. Once the data volume and
point-in-time archives are adequate, independently verify all split
gates and score improvement over *both* market and production
with paired game/date clustered uncertainty. Any promotion must
also survive sample-selection, state/push and calibration checks.

The current research stage is **implemented but blocked from
inference/promotion** due to inadequate source-valid training
and holdout data. This is a correct safety result, not a failure
of an authorized Bayesian training run.

Deepnote forensic run:
[Original archive calibration-gate verification](https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/Reform-10-archived-probabilities-Beta-and-global-stacking-hard-gates-38ac4ad71a5845d283252beabcb660ed).
