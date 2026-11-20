# NBA S4/J Step 1 — preregistered numerical sensitivity protocol

**Research-only protocol locked before any new event-path experiment.**
Governing authority: PA-V25-MASTER-2026-11-09/v1.1, Nov 19
`source_listed_subset` amendment. Base is PR194 head
`0be160921ba8ddcec84ff0119e1ba1e647315ada`;
original PR193 S4/J implementation and 64-scenario frozen forecast are
immutable controls. This is *not* an approval to release predictions.

## Fixed population and scientific question

- Target: ESPN NBA 401910026, MEM–MIN scheduled 2026-11-22T01:00Z.
- Training inputs: the exact PR193 model and 35-player source-listed cohort.
  No additional results, quotes, lineups or later model updates are admitted.
- Frozen model raw SHA-256:
  `f1f6dd4a4d3753042c28b71fa9b7949628d69ccdad8f38ece47bb2ccdc6ffa2a`.
  Frozen cohort raw SHA-256:
  `930715bcd2cb55ecca60bff433ea310c452ce4004791029989e1842a9286a969`.
- 14 named players and 21 source/model abstentions; 112 supported
  player-stat/combo queries and 168 abstained requests. Never create a
  complete-roster assertion.
- Question: what is the **numerical** and **prior-assumption** sensitivity of
  the new coherent S4/J event simulator to zero-minute mixture assumptions?
  No new data are fit, no actual outcomes are consulted.

## Precommitted variants and common random numbers

One original working prior `Z_i~Beta(.5,49.5)` per player/scenario
and five fixed alternatives: `z_i=0, .005, .01, .02, .05`.
The baseline is *not* fixed .01: equality of one-player minute marginals
does not imply equality of the joint opportunity or downstream event law.

Use a new research seed `2026112001` and scenario IDs `0..N-1`.
For each index, use exactly the old `rng_for(seed,game,index,
'coherent-fixed-G-O-components/1')` and identical chronological
`event_path(fixed,seed,attempt)` random-stream identifiers.
For fixed-z alternatives still consume and discard the original
Beta(.5,49.5) draw at each named player in the *same* order, so
global G/OT, pace, parameter draws and unrelated RNG streams remain paired.
Only the O zero-mixture value changes, and any consequential changes
in lineup/minutes or event paths are retained, not corrected.

Enforce an exact fixture identity check: the original baseline
`coherent_predictive_v1.fixed_scenario` must equal the new baseline
fixed-scenario object byte-for-byte on selected seeds and scenario indices.
The new experiment is not permitted to edit that original implementation.

## MC staged execution and stopping

Declared stages: source/parameter fixture smoke (n=3), n=64 initial
research runtime, then n=256 and n=1024 for numerical stability;
n=5,000 and n=20,000 **only when runtime, trace/data size,
failure counts and resources permit**. Each size is a separate
create-only experiment receipt and no favorable seed/variant is selected.
No stage's results justify retrofitting the protocol or dropping bad
scenarios. Report every failed scenario, variant, OT-path rejection,
resource-cap encounter and denominator.

Default path budget: 4,096 proposals per (variant, scenario).
Default event budget: 4,096 rows per path.
Keep fixed G/O/parameters constant through OT rejection. Fail the
whole variant for any exhausted scenario, but retain failure receipts;
never average only successfully completed scenarios or claim an
unconditional law conditional on successful finite execution.

The 64-path historical benchmark required about a minute; six
variants at n=20,000 could cost many hours and exceed a free CPU
budget. Before a long execution, publish measured runtime/size
forecast and classify the stage as feasible, deferred-by-cost or
failed; **do not claim 5k/20k were executed if they were not**.

## Full-count precision and comparisons

For every player/stat `PTS, REB, AST, 3PM, PR, PA, RA, PRA`,
report exact n-sample empirical integer PMF, mean, standard deviation,
mass at zero, 50/90/95/99% sample quantiles and the full empirical CDF.
Use one common coherent path for each stat and combination.
Never multiply marginal combo probabilities. Report for each
alternative versus baseline the supremum empirical CDF difference,
paired mean difference, and (where defined) nonparametric
paired MC standard error on aligned scenario indices.

Define full-family (all six variants × 112 supported marginals)
conservative DKW CDF numerical error:
`epsilon(n) = sqrt(log(2*6*112/0.05)/(2*n))`
under **iid exact-kernel samples**. This is not predictive calibration;
finite-budget success selection and the shared OT rejection process
can violate assumptions. For exact fixed count thresholds, use
beta-binomial/Clopper–Pearson-style Monte Carlo intervals with
explicit multiplicity, not fabricated certainty from zero sampled
tail hits. Predeclared diagnostic thresholds, not sportsbook offers:
PTS >=40, REB >=15, AST >=12, 3PM >=6, PR >=50, PA >=50,
RA >=25, PRA >=65. These threshold counts are never labeled
market probabilities or payout edges.

Compare the nested n=64,256,1024,5000,20000 prefixes of the
same new sequence, with full denominators. Track n-dependent CDF
differences and tail hit counts; indicate when only numerical
uncertainty is measured. The target n=20k family DKW epsilon is
~0.016, and even that conservative band can be larger than a 1%
tail: do not promise simultaneous 99th-percentile precision.

## Independent engineering and go/no-go

- Physical tests: five-on-court, team-minute sums 240+25/OT,
  player identity, basketball score/shot constraints, same-path
  combinations, zero-minute counts, held OT parameters.
- Adversarial: wrong cohort/model SHA, swapped actor IDs, mutated
  source/trace, invalid z, changed seed/rate paths, silent scenario
  drop, OT rejection exhaustion, and conditional participation.
- All outputs are append-only, include code and source raw hashes,
  executable reproduction commands and exact version/clock/seed.
- Independent P6 validation must separately review the new
  stochastic law, test reproducibility and completion selection.
  An author's tests plus CI are not independent signoff.
- A real outcome, market edge, historical predictive skill,
  G1/G2 acceptance, weight fitting and Tier/production promotion
  **cannot** be inferred from Step 1's numerical checks.
