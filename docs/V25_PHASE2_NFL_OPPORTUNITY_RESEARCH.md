# V2.5 Phase 2 — NFL opportunity research (isolated shadow branch)

**Status:** Research prototype implemented and under independent testing. **Not promoted.**
**Parent:** Phase 1 draft PR #90, not `main`. **Phase 0R:** still independently gated.
**Source of requirements:** `Pickem_Auditor_V2_5_Master_Implementation_Plan_2026-11-09.md`, Section 7, Phase 2 (P2-01 through P2-06) and Section 4.2.

## Scientific hypothesis and exact scope

Test whether **market-optional probabilistic team passing volume, player route/participation uncertainty, and a finite attempt allocation pool** improve NFL target and QB-pass-attempt distributions versus:
1. As-of independent player Poisson target counts (historical control; may violate a team-total conservation rule).
2. Standard Dirichlet–multinomial (DM) allocations.
3. The proposed hierarchical logistic-normal allocation (first constrained champion *candidate*, not production champion).
4. Zero-inflated DM (ZIDM) only where independently labeled structural inactivity histories exist.

Phase 3 receptions/yards/defensive tackle likelihoods and Phase 4 full-game multivariate dependent simulations remain **out of scope**. QB **pass attempts and dropbacks are included**; QB completions and passing yards remain Phase 3.

## Implemented work by ticket

| Ticket | Shadow implementation | Evidence / limitation |
|---|---|---|
| **P2-01** | `state.py` fits a pooled team/league posterior for possessions, plays, dropbacks and pass attempts. Shared team scenarios preserve attempts ≤ dropbacks ≤ plays. Optional game-spread sensitivity is fitted from prior originally pregame spread history only. | The no-market model always exists when training labels suffice; a quote or historical spread missing => game-market challenger **abstains**. No player-prop anchoring. No claim that fitted market sensitivity improves forecasts. |
| **P2-02** | `allocation.py` fits as-of player and role peer posteriors for participation, route share of dropbacks, and targets per route. New players inherit an uncertain role prior, not an arbitrary zero. | All routes are **latent pregame** projections. Does not feed realized current-game snaps, routes or targets. |
| **P2-03** | Draw shared team attempts once and allocate mutually exclusive targets from logistic-normal relative intensities plus an explicit residual/unattributed attempt slot. Exhaustion of projected routes removes a player from subsequent choices. | Conservation is checked on *every* simulated scenario; this does not guarantee improved calibration. |
| **P2-04** | A `verified_out` receiver gets exactly zero routes/targets and is removed before normalized allocation. Conditional role-uplift ratios are learned only from sufficiently observed **previously available, explicitly verified** affected-versus-normal role-transition examples. | If the role transition is not identifiable, use **no uplift**, report an abstention. No imported power-grid 120% capacity or 60% imbalance thresholds. |
| **P2-05** | DM gamma-normalized simplex challenger, explicitly labeled ZIDM variant requiring at least four structural labels per active role, and independent Poisson control. | DM concentration and empirical Bayes prior strengths are research hyperparameters, **not calibrated**. EFDM/continuous-categorical are not added without a data/compute justification. |
| **P2-06** | `replay.py` scores sealed-as-of NFL scenarios against separate postgame outcomes, with player target CRPS, team attempt CRPS, complete case/event ledgers, short-role and high-usage verified-absence cohorts, event/date cluster comparisons. | The included input is **entirely synthetic**. No real historical 2024 quote cohort or Phase 0R-certified NFL source archive has yet proven improved predictive performance. |

The synthetic example includes a new receiver, a high-usage verified absence, historical position-transition labels and a future game *withheld by the chronological freeze*. It is a software test fixture, **not** real NFL data or a sports betting result.

## Mathematical construction

As-of team rows `g` yield posterior parameters from cumulative past plays, dropbacks and attempts. The league prior and team observations are combined with declared pooling strengths. For simulation `m`:

```text
common state:      P_m = possessions; O_m = offensive plays
                   D_m ~ Binomial(O_m, p_dropback_m)
                   A_m ~ Binomial(D_m, p_attempt_given_dropback_m)

for each eligible player i:
  participation_mi ~ empirical Beta-Bernoulli role prior
  routes_mi ~ Binomial(D_m, p_route_mi) if active, else 0
  target propensity_mi ~ Beta(player/role target-per-route posterior)
  log relative weight_mi = log(route propensity_mi × target propensity_mi)
                           + Normal(0, estimated logit uncertainty)
  verified out => no route or target; omitted from all eligible player weights

include residual weight w_unassigned_m > 0
draw individual pass-attempt allocations from normalized eligible weights
a receiver with no remaining routes has zero subsequent target capacity

A_m = sum_i targets_mi + unassigned_attempts_m
0 ≤ targets_mi ≤ routes_mi ≤ D_m
0 ≤ A_m ≤ D_m ≤ O_m
QB pass attempts = A_m
```

The residual slot includes throwaways, spikes and other attempts without a target **credited to one of the represented players**; it is not a separate invented receiver.

The no-market team-state sample is shared *exactly* across logistic-normal, DM, ZIDM and the independent Poisson control in scenario index `m`. Only their allocation draw differs. The market-conditioned game-state version is kept as a **separate** research model if genuine as-of spread training is available.

All Over/Under/Push probabilities at a line come from a **single fixed scenario ensemble**, never independently seeded sides. The empirical Monte Carlo standard error of P(Over) is reported as `sqrt(p(1-p)/M)`; additional parameter, model and data uncertainty is *not* covered by this MC error alone. There is no market-edge calculation or wager ranking.

## Research input contract

One JSON object with `schema="v25-nfl-p2-input-v1"` and:
- `forecast`: immutable run/event/team/opponent/QB identity, kickoff, freeze, complete pregame receiver roster, statuses with published/retrieved times, and **synthetic diagnostic** lines for targets / QB pass attempts. Optional `game_market` requires original pregame source, exact quote clock and SHA.
- `team_history`: historical team possessions, plays, dropbacks, passes attempted and charted targets, each with **game time and actual label-availability time**.
- `player_history`: historical participation/routes/targets/role, actual label availability, *optional explicit* structural inactivity and verified absent teammate role.
- All history known **after** the forecast freeze or belonging to the current event is excluded from fitting. Invalid event identities, source timestamps, physically impossible historical counts and unauthorized current-game realized features fail closed.

The original input SHA-256, code SHA, fitted cutoffs, hyperparameters, random seed, all scenarios, team/player outputs and abstention reasons are bound in an immutable research receipt. **A matching SHA proves archived byte integrity, not upstream provider publication truth**; Phase 0R certification remains independent.

## Commands (local or free Deepnote CPU)

From the repository root on the Phase 2 branch:

```bash
python -m unittest discover -s tests -p 'test_v25_phase2_nfl.py' -v

python scripts/v25_phase2_nfl_research.py \
  --input examples/v25_phase2_nfl_synthetic_case.json \
  --output reports/local_phase2_synthetic_example.json \
  --code-commit <actual-40-character-git-commit-sha> \
  --n-scenarios 512
```

`--summary-only` omits raw scenarios but keeps scenario digests and probability summaries. A repeated command must use a **new** output file; overwriting is forbidden.

For registered chronological research bundles, use `--mode replay` with
`{"schema":"v25-nfl-p2-replay-input-v1","cases":[{"input":<individual as-of input>,"outcome":<settled postgame label>}]}` and a fresh output path. Actual outcomes are never incorporated into the `input` object.

**No network collection, heavy NUTS sampling or paid service is invoked by these research entrypoints.**

## Falsification and ablation requirements before Phase 2 approval

1. On genuine **pregame source-certified** NFL folds, enumerate all eligible team/player opportunity contracts; report uncovered, stale and disallowed sources in the denominator.
2. Split chronologically by 2024 event/week; use outcomes only after official availability. The 2025 cohort is **not an untouched holdout** after prior 2024/2025 training and design exposure.
3. Compare independent Poisson, DM, logistic-normal, ZIDM (when identified), and **no-market versus validated spread-conditioned** state on **identical** eligible contracts.
4. Primary opportunity metrics: team pass-attempt CRPS, player target CRPS, participation false-zero rate, route/exposure prediction errors, and marginal probability calibration. Secondary: discrete Brier/log-loss and **Energy/Variogram scores** on genuinely joint, identically defined event vectors; complete absence/unattributed-target accounting.
5. Mandatory cohorts: rookie/short-role, high-usage verified out, ordinary games, role transition, cold-start teams and quarterback exit uncertainties. Require adequate event/date clusters; bootstrap intervals are descriptive.
6. Negative controls: injected current-game realized pass attempts, `shift(-1)` future outcomes, late roster reports, late market quotes, mislabeled player/team IDs, missing structural inactivity labels and duplicate game contracts. All must abstain or leave as-of predictions unchanged.
7. Conservative decision: **do not promote** if the challenger is less accurate or its cohort coverage is narrower without justification; keep the simple model as champion, investigate data and leakage first.

**Exit not yet met.** The milestone requires real matched chronological score improvements plus independent audit, not merely passing software tests or producing attractive synthetic results.

## Deployment and dependency rules

This branch was created **from Phase 1 draft PR #90's code** as a stacked research branch. A separate **draft PR targets the Phase 1 branch**, not `main`, so it cannot mutate the paused production workflow. Both Phase 0R approval and Phase 1 integration remain prerequisites for any eventual merge of a production model. Tier 1/2 remains blocked; no existing forecast, historical posteriors, probability comparison chart, settlement or benchmark is overwritten.

## Independent audit notes

Proposed independent QA should check:
- Exact team/players/attempt conservation and route caps in every sampled scenario.
- Status timestamp/source leakage and current-game outcome injection.
- New-player uncertainty, verified-out zero exposure, no invented role uplift.
- Structural zero unidentifiability triggers actual challenger abstention.
- Zero lambda produces exactly zero in the independent Poisson control.
- Same random seed + code/data reproduces scenario hashes; different seed changes them.
- Eight-event synthetic time-travel replay produces coherent event-cluster uncertainty, while clearly refusing prospective performance claims.

The local tests confirm **software semantics on synthetic input only**. They cannot certify pregame provider truth, a production-worthy Bayesian posterior, NFL prediction improvements, or profitability.
