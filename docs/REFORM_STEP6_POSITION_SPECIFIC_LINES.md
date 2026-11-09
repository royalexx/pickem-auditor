# Step 6 research update — frozen position-specific tackles + assists lines

**Scope:** Shadow validation only; no sportsbook lines, production forecasts,
Tier ranks, 60/40 ensemble, Bayesian training, or NUTS posteriors modified.

## Purpose and design

The original research comparison used one synthetic line of **5.5 tackles +
assists for all defensive positions**. That produces trivially favorable
Under outcomes for some roles and makes a cross-position aggregate Brier score
difficult to interpret.

New `scripts/nfl_tackle_snap_share.py` policy
`--line-policy position_training_median_v1`:

1. Uses the existing source-reconciled 2025 NFL defensive snaps,
   credit counts, and PBP team plays. Only games with estimated availability
   **at or before the predetermined holdout cutoff** contribute to thresholds.
   For this research replay the cutoff was **2025-10-01T00:00:00Z**.
2. Groups original recorded defensive position labels into explicit categories.
   The model does **not** infer actual off-ball versus edge alignment from
   the ambiguous "OLB" label. "S", "FS", "SS" are combined as safety; "DB"
   is an unclassified category, **not** silently assigned to safety.
3. Calculates the historical **median tackles + assists per player-game**
   in each category and selects the half-integer line immediately above
   the floor of that median. This is a fixed, model-neutral rule; **no
   threshold is optimized for high predicted accuracy, model advantage or
   holdout returns.**
4. Requires a minimum of 40 historical player-games, 12 distinct games and
   10 distinct defenders for a category. Unsupported categories abstain.
   These requirements are research screening thresholds, not a guarantee
   of adequate statistical power.
5. **Freezes** each threshold for the entire subsequent holdout.
   A holdout player's category is determined from its *prior* player game
   history, never from that player's current-game or end-of-season role.
   Both the challenger and its original team-play-rate control are scored
   at the **same frozen threshold on the same player-game**.
6. Preserves the original fixed-5.5 evaluation as `--line-policy fixed`
   for replication. It is not overwritten or compared on mismatched outcome
   definitions. All outputs remain marked `production_eligible=false`.

## Frozen thresholds (2025 pre-October 1 only)

| Research position group | PFR / public position labels | Historical player-games | Derived synthetic line |
| --- | --- | ---: | ---: |
| Off-ball linebacker label | LB, MLB, ILB | 471 | **3.5** |
| Outside linebacker, alignment unclassified | OLB | 42 | **3.5** |
| Cornerback | CB | 294 | **2.5** |
| Defensive end | DE | 316 | **2.5** |
| Interior defensive line | DT, NT | 361 | **2.5** |
| Unclassified defensive back | DB | 40 | **3.5** |
| Safety | S, FS, SS | 24 | **No line: insufficient history** |

These are **population baselines**, not pick'em sportsbook quotes or
player-specific recommendations. A full-time middle linebacker may have
a much higher actual line than 3.5 because rotational linebackers
affect the population distribution. Future research should compare
**pregame predicted usage classes within each position**, without choosing
new thresholds based on these holdout results.

## Real historical result — research only

Data: public free NFL 2025 player stats, weekly defensive snaps,
schedule and play-by-play joined with the existing conservative
`nfl_context_data.normalize` pipeline. It produced 6,732 usable
defender-game records across 272 games and 835 distinct defenders.

**4,163 evaluated player-games across 59 dates** from the
October 1, 2025 holdout start. Both models used the same fixed 65-team-plays
scenario, unchanged historical information cutoff and the same fixed
negative-binomial dispersion. This is a **retrospective**
start+18-hours-availability approximation, not original pregame source
publication evidence.

| Proper score (lower is better) | Snap-share challenger | Historical team-play-rate control |
| --- | ---: | ---: |
| Brier score | **0.220775** | 0.224458 |
| Log loss | **0.631440** | 0.643497 |

Challenger-minus-control Brier = **-0.003683**; log loss =
**-0.012057**. Date-clustered paired, descriptive 95% intervals:
Brier **[-0.005748, -0.001442]** and log loss
**[-0.017667, -0.005634]**. These intervals do *not* account for
retrospective source timing, fixed-alpha model error, alternative threshold
choices, or real sportsbook selection.

### Role-level, same-contract results

| Research role | n | Challenger Brier | Control Brier | Challenger minus control |
| --- | ---: | ---: | ---: | ---: |
| Off-ball LB | 1,312 | 0.20350 | **0.20189** | **+0.00161** (worse; CI crosses 0) |
| OLB, unclassified | 118 | 0.19531 | **0.17739** | **+0.01792** (worse) |
| CB | 656 | **0.23220** | 0.23975 | -0.00755 (CI crosses 0) |
| DE | 914 | **0.22964** | 0.23636 | -0.00673 |
| DT/NT | 1,048 | **0.22641** | 0.23263 | -0.00622 |
| DB, unclassified | 115 | **0.25705** | 0.27387 | -0.01683 |

Linebacker gains are **not established**, and OLBs are significantly
worse than the simple rate control on this research cohort. The smaller
safety source category does not have an approved benchmark line.

#### High-snap-share off-ball linebacker diagnostic

Using the already-declared 75% **predicted pregame snap-share** boundary,
144 off-ball-LB player-games across 37 dates qualified. The snap-share
challenger's Brier was **0.19119** versus **0.18989** for the control
(difference +0.00130, descriptive date CI
[-0.01083, +0.01133]). Mean predicted Over probability was 70.0% versus
a 66.0% realized Over rate at this research role line.

This is **not an improved or approved full-time linebacker model**.
It also shows why training-only population position lines are a better
research control than 5.5-for-everyone but are insufficient to model actual
player-specific pick'em markets.

## Later predeclared cutoff sensitivity — 2025-11-01 (NOT independent)

To inspect early-season sampling variability, the same unchanged rule was
also frozen at **2025-11-01T00:00:00Z**, then evaluated on the remaining
3,183 defender-game observations across 42 dates. This holdout is **nested
within** October's holdout; treat it as a sensitivity analysis, not fresh
out-of-sample proof or a second independent validation sample.

| Research role | October-frozen line | November-frozen line | November pre-cutoff role observations |
| --- | ---: | ---: | ---: |
| Off-ball LB | 3.5 | 3.5 | 921 |
| OLB, unclassified | 3.5 | 3.5 | 76 |
| CB | 2.5 | **3.5** | 546 |
| DE | 2.5 | 2.5 | 603 |
| DT / NT | 2.5 | 2.5 | 705 |
| DB, unclassified | 3.5 | 3.5 | 89 |
| Safety | Unsupported | **4.5** | 52 |

The safety line of **4.5** arose mechanically from its November training
median of **4.0** and the half-integer rule; it was **not chosen** to
match the user's illustrative example. The safety comparison had only
39 heldout observations and a **worse** challenger Brier difference of
+0.00683. No player- or betting-grade safety prediction follows.

The later-cutoff aggregate research Brier scores were **0.217663**
challenger versus **0.220096** simple control, and log losses were
**0.625173** versus **0.634490**. The date-block descriptive
differences were -0.002433 Brier (95% interval
[-0.004691, -0.000849]) and -0.009317 log loss (interval
[-0.014849, -0.004491]). Off-ball LB (+0.00251 Brier) and
OLB (+0.01643) still performed worse; the first-cutoff weaknesses
were **not** resolved by changing training cutoff. Some lines changed,
notably cornerbacks, because the early-season role population estimate
was unstable. The data is not an archive of contemporaneous market lines.

## Reproducibility and promotion gates

Read-only execution and original evidence:
[Deepnote Step 6 position-line validation](https://deepnote.com/workspace/stonks-a257-e2858df6-426e-479b-a4f8-0376a602f7bb/project/Pickem-Auditor-Daily-Cloud-Inference-9cc31536-93be-44db-bdeb-06fba3f61410/notebook/Step-6-source-frozen-role-specific-tackle-lines-2025-out-of-sample-2e49496f68c746bfacfa865e520e16aa?utm_content=9cc31536-93be-44db-bdeb-06fba3f61410).

Once original `nfl_context_data.normalize` bundle JSON files are
available, run:

```bash
python scripts/nfl_tackle_snap_share.py \
  --normalized-bundles /path/to/frozen_normalized_2025.json \
  --walk-forward-from 2025-10-01T00:00:00+00:00 \
  --line-policy position_training_median_v1 \
  --max-holdout-rows 4200 \
  --share-prior-mode evidence_adaptive_v2
```

Output contains the immutable cutoff, role-to-label mapping, accepted
and abstaining roles, their sample sizes, the generated lines, matched
proper scores, date-clustered descriptive intervals, and role breakdowns.
The original 5.5 benchmark can be rerun with `--line-policy fixed`.

**Never use these research lines as recommended prices or as an input to
production betting.** Market-line testing requires real contemporaneously
archived provider quotes, independent future holdouts, and the matching
frozen Engine A/B/Bayesian/NUTS/consensus forecasts. Role and snap-share
subgroup weaknesses must be resolved or bounded before any promotion.
