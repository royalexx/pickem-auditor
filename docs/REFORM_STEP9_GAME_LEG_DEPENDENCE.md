# Pick'em Auditor reform — Step 6 verified tackles+assists and Step 9 game-leg dependence

**Evaluation:** archived 2026-11-08 NFL 1 PM official settlement and
independent November 5–7 retrospective research. **No model refit,
production promotion, entry generator, betting probability, or training.**

## Step 6 source-stat verification (three-component combined tackles)

The normalized NFL weekly history is created by
`scripts/population_nfl.py::normalize_season` before Step 6 reads the
`nfl_context_data.normalize` historical bundles. For the market
`tackles + assists`, this code explicitly calculates:

```python
components = (
    row.get("def_tackles_solo"),
    row.get("def_tackles_with_assist"),
    row.get("def_tackle_assists"),
)
# Missing/noninteger components are excluded; otherwise:
combined_tackles_assists = sum(components)
```

This is **not** just solo tackles and does **not** substitute
`def_tackles_for_loss`. These three fields have separate
stat-ID definitions in the public nflverse player-stat dictionary and
nflfastR implementation. `scripts/nfl_tackle_snap_share.py` reads
only this normalized `tackles + assists` count for historical
per-snap tackle conversion, outcomes, role-specific median lines and
its simple per-team-play rate control.

Added end-to-end source-path regression test
`test_combined_tackles_not_solo_enters_step6_training_and_lines`:
4 solo + 2 tackles-with-assist + 1 assist becomes **7** credited
combined tackles, not **4** solo. It verifies the same value survives
Step 6 bundle normalization, checks the 7/59 per-snap rate, and requires
all three source components (missing assistance means no combined-tackle
observation). The preexisting `test_nfl_verified_defensive_snaps_and_combined_tackles`
also verifies all three source stats.

**Important:** scoring providers can use different definitions for
`tackles + assists`; any real pick'em line must be matched to the
provider's credited settlement definition. The retrospective free dataset
does not independently certify each vendor's settlement. No existing
historical row was rewritten.

## Step 9 objective

Prevent false claims that two or more favorable player props have
probability `p1 × p2 × ...` of jointly winning. That product is valid
only under an appropriate conditional-independence assumption. Legs
from the same game can share team pace, game script, roster changes,
playing time and defensive response.

`scripts/reform_step9_game_leg_dependence.py` reports only
**descriptive** game-clustered dependence measurements from
original frozen pregame probabilities and independently verified
postgame outcomes. It does not learn a copula, estimate a production
covariance matrix, assign per-entry payouts, or infer returns.

It pairs contracts from the same game by:
- same player but different statistic;
- distinct players on the same team;
- players on opposing teams;
- same statistic across distinct players.

It excludes the same player/stat on two different lines, counts each
graded Over/Under contract only once, verifies full-market original
two-sided probability coherence, and refuses unverified, pushed or
missing-source contracts. The entire original November 8 settlement
receipt and archive SHA-256 are checked before any outcomes are used.

For each unique same-game pair, it records:
`observed_both_hit`, `independence_product=p_i*p_j`,
`both_hit_minus_independent` and
`(observed_hit_i - p_i)*(observed_hit_j - p_j)`.
**The latter is a residual-product diagnostic, NOT a learned pair
correlation**. It conflates common outcome variation with shared
directional or calibration errors. Games are **equally weighted** so a
game with 600 leg pairs does not become 600 independent events.
An exploratory same-date, other-game, same-stat negative control
is included but not treated as an exchangeable causal experiment.

Intervals require at least **20 independent games on ≥10 distinct
dates with ≥100 pairs**, and resample **entire dates** (keeping all
correlated games together). These are descriptive screening limits, not
proof of identifiability or production certification.

### Original November 8 1 PM — same-game pair results

| Pregame model/side-selection basis | Settled usable legs | Same-game pair observations | Independent games | Dates | Mean both-hit | Mean `p_i*p_j` | Difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Coherent market | 220 | 4,038 | 6 | 1 | 32.31% | 28.72% | +3.58 pp |
| Coherent original 60/40 consensus | 52 | 219 | 6 | 1 | 12.44% | 32.02% | -19.58 pp |
| Original Engine A | 252 | 5,321 | 6 | 1 | 30.98% | 40.92% | -9.94 pp |

**None** has a defensible game/date-cluster confidence interval.
The market-selected residual-product average was **-0.00169**,
nearly zero, despite the observed both-hit frequency being 3.58
percentage points higher than the naive product. This illustrates
why **raw joint-hit discrepancy alone cannot establish positive
correlation**. For the original production consensus, the large
negative gap principally reflects its known November 8 model/selection
problems and is **not proof of negatively correlated legs**.

#### Market-side structural slices, November 8

| Pair class | Same-game pairs | Mean both-hit minus product | Mean centered-model residual product |
| --- | ---: | ---: | ---: |
| Same player, different stats | 120 | +8.02 pp | -0.00309 |
| Same team, distinct players | 1,856 | +3.19 pp | -0.00236 |
| Opposing-team players | 2,062 | +3.75 pp | -0.00080 |
| Same stat, distinct players (overlapping with other classes) | 764 | -1.67 pp | -0.01562 |

Only **six games on one date** contributed. The pair-count scale is
*not* the effective statistical sample size. Pair classes overlap:
do not add the same-stat count to the relationship counts.

### Earlier November 5–7 cohort: separate, never pooled

The historic Engine A research cohort supplied **643** usable
original legs over 37 source games (27 games with ≥1 eligible
same-game pair). Those produced **17,519** paired combinations on
only **three dates**, with mean both-hit 24.14% versus model
independence product 42.82% and residual product +0.07083.

This legacy cohort has known directional error and unverified
point-in-time source completeness, and uses a policy different from
the November 8 60/40 production. It cannot be combined with
November 8 to estimate today's game covariance.

The older market field was not a coherent binary probability pair:
483 source records failed the two-sided probability integrity gate,
162 had no market model, leaving **zero** valid historical market
legs for this analysis. No silent normalization was performed.

## Entry-bounds safety rule

The helper `frechet_entry_bounds` accepts 2–20 valid marginal
(nonpush-conditional) leg probabilities and returns only the
mathematically sharp marginal Fréchet bounds

`max(0, sum(p_i) - (n-1)) ≤ P(all hit) ≤ min(p_i)`.

It also displays the independence product **for comparison only**.
For two hypothetical 70% and 60% legs, the independent product is
42%, but the admissible joint-hit probability ranges from **30% to
60%** *without further dependence assumptions*. The bounds are
not odds, payouts, nor a recommendation; sportsbook rules for
pushes, voids and partial entries need separate treatment.

Every Step 9 result explicitly returns
`joint_distribution_fitted=false`,
`multi_leg_probability_authorized=false`,
`entry_independence_product_authorized=false`,
`payout_ev_authorized=false`, and
`production_changed=false`.

## Operational status and next statistical gate

**Step 9 implemented, audited and run against original data.**
**Statistically reliable dependence estimation and an entry
optimizer remain blocked.** Prospectively archive the complete
pregame set of multi-leg candidates with their exact line, side,
source-market quotes, player/game identity, odds/payout schedule and
every result, including excluded or lost candidates, on many separate
NFL/NHL/NBA game dates. Compare predeclared same-game and cross-game
classes, conditional game opportunity and residual covariance;
validate jointly predicted win rates chronologically against both the
original product and bookmaker same-game pricing with game/date
clustered intervals. **Do not promote a single common correlation
coefficient from these short archives.**

Read-only reproduction:
[Step 9 Deepnote audit](https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/Step-9-independent-game-leg-residual-dependence-on-frozen-settles-51e71c558137419097a619b2840f4cc3?utm_content=9cc31536-93be-44db-bdeb-06fba3f61410).
```bash
python scripts/reform_step9_game_leg_dependence.py \
 --frozen pickem_runs/2026-11-08/20261108T135631Z/slate_model_comparisons.json \
 --settlement pickem_runs/2026-11-08/20261108T135631Z/slate_1pm_nfl_settlement_20261108.json \
 --pinned pickem_runs/2026-11-08/20261108T135631Z/directional_phase1_1pm_nfl_pinned_receipt_v1.json \
 --historical pickem_runs/2026-11-08/20261108T135631Z/independent_2026_nov5_nov7_backtest.json \
 --archive-root .
```
