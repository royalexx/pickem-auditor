# V2.5 Phase 2 — scope correction: pooling is not a participation repair

**State:** Provenance gate and negative controls implemented. **Actual pregame roster/role/route-aware model is NOT complete.** No revised confidence-accuracy result is approved.

The agreed five changes were (1) timestamped pregame roster/availability/role changes and new entrants; (2) hierarchical cold starts and a participation/zero hurdle; (3) game-to-game role volatility; (4) calibration using only previously revealed weeks, including Over and Under separately; (5) matched chronological evaluation of all challengers, with honest full-universe coverage and an independent future period.

The earlier role pooling prototype still constructs eligible players from *previous-game target box scores*. This is a weak roster proxy and does not distinguish inactive, zero-target-active, injured, traded or new-role receivers. It cannot be claimed to satisfy the agreed plan. That exploratory study is quarantined; neither it nor its 2024 retrospective score is proof of a repaired Phase 2 model.

## Audited source availability (actual inspected 2023–2024 rows)

Read-only Deepnote run ca2b26e0-82cb-46b3-951b-83f0297ecf9b:

| Source | Rows | Timing/identity limitation |
|---|---:|---|
| Weekly rosters | 92,234 | Team, week, player GSIS ID and ACT/INA/etc. status; **no individual publication or original archive capture timestamp** |
| Injury reports | 11,814 | Injury/practice status plus date_modified; potential as-of historical approximation, but retrieval in 2026 is not original 2024 capture proof |
| Snap counts | 53,155 | Postgame offensive snap totals, PFR player IDs; only **prior games** can train new forecasts, and snaps are NOT receiver routes |
| Depth charts | 74,639 | Week/team/player GSIS/role without row-level original capture timestamp |
| Participation data | 92,087 | Plays, players and some route charting; source documentation says 2023+ FTN participation arrives after postseason, so 2024 in-season training use is disallowed |

Week number alone does not certify in-week roster availability. End-of-game inactive status can itself be hindsight. An injury date_modified timestamp is useful in historical study, but cannot establish that this project actually possessed the record before the original 2024 kickoff.

## Action completed: real input/source gate

The new isolated file scripts/v25_phase2_asof_participation_source_gate.py enforces:

- Pregame status requires original named player, role, exact source publication and **original capture** timestamps, and source SHA; any record later than freeze fails.
- If no verified current-game roster evidence exists, the player's status is **unknown/abstain**, not verified inactive and not an automatic Under.
- Verified-out zero requires a valid source; contradictory equal-time statuses or backdated retrospective source claims fail.
- Prior-game snaps and verified routes have distinct types, game IDs, source timestamps and hashes. Current-event realized snaps and any past label published or captured after freeze fail.
- A retrospective weekly roster without original capture is **not** retrospectively promoted into a certified pregame record.

Read-only Deepnote run 22a9b3d2-7e85-4dff-8ba4-fc3f40f72ec0 passed 11 new adversarial source-gate tests and nine existing target-only input isolation tests.

**What the tests do not establish:** The gate has not yet been integrated into a complete latent player-availability model, the route-aware scenario sampler, or an 18-week matched real-roster replay. Those outputs cannot be claimed as complete.

## Remaining actual architecture work

1. Ingest genuine timestamped original roster/injury/lineup receipts or mark each player/market as retrospectively unverified. Never impute the actual pregame active roster from after-game targets or snap counts.
2. Model available/uncertain/out/unknown status and role-change transitions with explicit participation uncertainty and cold-start hierarchical priors. Separate active-zero-target and verified-inactive cases.
3. Use only previously available snaps/routes to estimate workload with game-to-game variance, conditional target rate and a real residual/unseen receiver category. Preserve physical team constraints; do not recycle a fixed share of departed players by hand.
4. Train confidence calibration using previous weeks' outcomes only, with distinct reliability reporting for Under/Over, early-season/short-role, and roster-turnover cohorts.
5. Run a matched full-universe chronological comparison with independently valid data, preserving abstentions in the denominator. The 2024 cohort has been used for model design and cannot be called untouched out-of-sample validation.

**Release gate: BLOCKED.** The earlier role-pooling experiment is a sensitivity study only. Code readiness and high synthetic scores cannot replace historical source integrity and a demonstrated prospective gain.
