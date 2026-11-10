# Phase 2 — genuine historical participation repair and 2024 sequential evaluation

**Status:** SHADOW RESEARCH; pregame publication authenticity unverified, not production-admissible. Development is stacked on Phase 2 draft #95; Phase 0R, Phase 1 and Phase 1.5 investment gates remain independent. This experiment evaluates *statistical learning*, not odds, money, betting edge or pick profitability.

## Specific correction to the abandoned pooling-only workaround

The previous target-only experiment chose the "roster" from players with historical target boxes in the last two games. It treated every target belonging to older-only receivers as permanently unassigned. This produced 98.2% Unders among ≥80% confidence forecasts and underpredicted high-confidence player targets.

**The replacement does not derive a player's availability from his own past targets.** It uses season/week/team/player identifiers from **previous weekly NFL roster snapshots**, joined to the actual GSIS player registry. It uses **previous finished games' PFR offensive snaps** as exposure labels after joining unambiguous PFR↔GSIS identities. Dated current-game injury reports are filtered strictly to the model's per-game cutoff (two hours pre-kickoff) and marked as **retrospectively retrieved, original capture unverified**. Unknown and newly arrived players retain wide role priors or are outside the candidate universe, rather than being confidently classified inactive.

The real data inventory recovered 46,921 WR/RB/TE weekly roster records and 24,673 unambiguous PFR/GSIS prior-snap records across 2021–2024; the bridge also has 1,527 dated 2024 injury modification records, all explicitly filtered per game. None of these source counts proves original 2024 acquisition timestamps or current-game receiver routes.

## Model stages: feature / mechanism / checkpoint

| Stage | Mechanism | Integrity guard |
|---|---|---|
| Team state P2-01 | Baseline team's existing 2021–23, then 2024 prior-week-only negative-binomial attempts sampler. | Existing shared team attempts replay remains unchanged for comparisons. |
| Pregame availability P2-02 | Candidate roster: lagged previous-week identity, latest transfer/team state, date-filtered *uncertified retrospective* injury; unknown player candidate abstains. | Never read 2024 current-week weekly roster. "Out" in a 2026-read historical injury table cannot be called a verified originally captured Out. |
| Participation P2-02 | P(active) partially pooled from past snap-playing examples and role prior; separately sample binary activity, uncertain workload, and active-but-zero-target outcomes. | A missing current target is never considered evidence of pregame inactivity. Snaps are previous-game exposures, NOT receiver routes. |
| Workload variance P2-02 | Project team plays, then player offensive snap fraction using a Beta posterior of previous snaps and role exposure; target-per-snap draws also use an uncertain Beta distribution. | No current-game realized snaps/routes/plays. |
| Role opportunity P2-03/04 | Team's full prior WR/TE/RB target roles estimated from *all past players*, not the last-two-game roster. Sample common role target shares game by game; allocate within each role by participant and workload, with independent unrepresented-receiver and non-target pools. | Every scenario: team attempts = known player targets + unknown player targets + non-target attempts; target count ≤ projected offensive snaps. |
| Hurdle ablation | **Participation_snap** vs **participation_no_hurdle**, same attempt source, historical data and precommitted random seed. | Isolates role participation from count-pool effects; cannot prove actual route forecasts. |
| Calibrated confidence | Frozen raw, ridge-logistic global Platt, and role-conditional intercept calibration from earlier 2024 weeks ONLY. | Calibrator launched as a separate process and is given no current-week label; first week identity/no fit. |
| Historical evaluation P2-06 | All 18 2024 weeks with one immutable forecast file and one immutable calibrator output file per week. | Reveal results only after forecast and calibration SHA receipt; original archive remains unchanged. |
| Controls | Same archived 2024 research target lines and team games against original updated 10-game target-only model, no-refit baseline and independent Poisson. | Compare matched event/player contracts, log unmatched source count, report CRPS, Brier/log loss, 70/80/90/95 confidence, Over/Under split and coverage. |

### Statistical limitations and guarantees

- Dataset 2024 was inspected to **design** this repair; it is not untouched future evidence even when forecast inputs are temporally isolated.
- PFR offensive snaps are not routes; no actual independent route history was available with sufficient as-of publication proof.
- Weekly roster status extracted in 2026 has no original 2024 capture; it is lagged to prior games but historical source possession remains uncertified.
- Retrospective original injury status can have a recorded modified time before kickoff, but cannot establish our 2024 collector actually captured it. Its influence is therefore probabilistic (not an absolute deterministic Out) and clearly tagged.
- Missing rookie/transfer documentation must reduce source coverage or increase uncertainty, not trigger high-confidence Unders.
- Proper-score and high-confidence improvement alone will **not** promote the model. The model must eventually demonstrate real originally captured pregame information and out-of-development data generalization.
- This research uses synthetic diagnostic thresholds, not originally verified sportsbook quotes; no payout model, odds or financial conclusion is involved.

## Source, entrypoints and tests

- scripts/v25_phase2_participation_source_bridge.py — build historical as-of real data context, PFR↔GSIS, per-game source cutoff
- scripts/v25_phase2_asof_participation_source_gate.py — separate fail-closed **certified** pregame source contract
- scripts/v25_phase2_participation_snap_forecast.py — isolated participation/snap workload/target simulator
- scripts/v25_phase2_online_probability_calibration.py — strictly lagged calibration by model
- scripts/v25_phase2_role_repair_2024_replay.py — now uses the actual participation/snap model, not the previous role-only pooling module
- scripts/v25_phase2_independent_2024_confidence_audit.py — independently rescore frozen 18-week receipts, source cutoffs, model coverage and side-specific confidence.
- tests/test_v25_phase2_true_participation.py and tests/test_v25_phase2_asof_source_gate.py — adversarial leakage, transfer, missing source, snap≠route and conservation properties.

The existing role-pooling-only prototype remains an **obsolete exploratory sensitivity analysis**, not the approved Phase 2 repair. The probability calibration is fitted strictly to already scored prior-week rows, and must be evaluated against **the new model's frozen raw distributions**, not confused with a change to predictive counts.

## Explicit acceptance logic

1. Stage integrity: zero current/future-week records in child input, zero unauthorized source timestamps, zero illegal target/attempt/snap allocations; original frozen receipts immutable.
2. Learning skill: matched team attempt and target CRPS; expected target bias, proper scores and nominal predictive interval reliability. No credit for withholding hard examples without reporting reduced candidate coverage.
3. Confidence: on each of Weeks 1–18, report Under versus Over counts, realized accuracy versus claimed probabilities, 70/80/90/95 reliability, ECE/Brier/log-loss and cohort split.
4. Causal mechanism ablation: compare participation hurdle on/off, independent Poisson and original target-only allocator on identical eligible event/player/stat contracts.
5. Clear decision: a 2024 result here is **descriptive exploratory only**. Do not promote or declare the full Phase 2 true route model complete without originally captured pregame roster/route evidence and a genuinely independent untouched forward season.
