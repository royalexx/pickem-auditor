# Formal NBA integration acceptance matrix — November 15, 2026

Gate statuses concern the precise scope named. A fixture pass does not pass the corresponding real-model gate. No new workstream is rejected merely because its artifacts were unavailable.

| Scope | Gate | Status | Concrete receipt / remaining requirement |
|---|---|---|---|
| WS4 | Original benchmark replay | PASSED | evidence/original_replay_v2.json; 250 contracts, 47 players, five games; 1783 source objects; five raw NBA boxscores. Original hashes, exact identity/outcomes and paired denominators reproduced |
| WS4 | Original scored receipt documentation pin | FAILED | Observed 3f417d0e9ba271ca95fd0dcec5e1a4291d84099a6bb50a48077ffbafe9bcb474; forensic markdown cites c6811bebc6cf125211f994ba0228ce9638d2022b428ac9dde60567b295cd3d6c. Reconcile the two report versions without rewriting archives; current raw-source scoring is separately verified |
| WS4 | Legacy morning original canonical identities | BLOCKED-BY-DATA | evidence/morning_diagnostic.json; all 1248 rows missing event/player/original hash. Authenticated canonical identities needed; never infer from names |
| WS4 | Legacy morning online Bayesian A/B paired validity | FAILED | NBA 441/441 and 451/451 diagnostic pairs noncomplementary. Both sides from one valid probability law; no posthoc normalization |
| WS4 | Standalone evaluation engineering | PASSED | evidence/test_execution.json; 83 targeted tests; tests/nba_ws4/test_evaluator.py. One-contract outcomes, full ledger, chronology, complementarity, negative controls and append-only artifacts |
| WS4 | Independent review of new audit implementation | INCONCLUSIVE | Author-run tests and separate mathematical review pass; no independent external code reviewer. Separate reviewer before accepted integration; no self release approval |
| WS1 | New source/identity/timestamp integrity | BLOCKED-BY-DATA | No immutable new WS1 handoff manifest supplied; original Nov10 verified separately. Original raw bytes, event/player/team/quote identity and authenticated availability clocks by freeze |
| WS1 | Authentic historical versus retrospective evidence | BLOCKED-BY-DATA | Original Nov10 only; new WS1 historical availability not established. Classify each source by original/retrieved-later provenance; prohibit retrospective certification |
| WS1 | Complete new reject/abstention reporting | BLOCKED-BY-DATA | Legacy 1314-side attempt ledger retained; new WS1 ledger not supplied. All attempts hash-bound before targets; exact accept/reject reasons and model abstentions |
| WS2 | Minutes calibration | BLOCKED-BY-DATA | No original WS2 OOF minutes distributions/outcomes. CRPS, interval/PIT and role/availability slices on untouched multi-date matched folds |
| WS2 | Participation correctness | BLOCKED-BY-DATA | No WS2 pregame activity probabilities. Participation Brier/log loss, false-zero and DNP policy checks with source-backed status |
| WS2 | Team-minute conservation on actual artifacts | BLOCKED-BY-DATA | Synthetic fixture passes 240/265 team-minute tests only. Every actual scenario conserves 5*(48+5*OT), supports player/lineup constraints |
| WS2 | Matched gain over simple exposure baseline | BLOCKED-BY-DATA | No WS2 prospective matched forecasts. Fixed paired player/game/date cohort, proper-score improvement or registered noninferiority |
| WS3 | Distribution support on actual artifacts | BLOCKED-BY-DATA | Legacy A/B negative Normal mass abstentions 29/25; no new WS3 law supplied. Nonnegative count support, normalized mass, exact shared-law thresholds; no clipping repair |
| WS3 | Calibration and tail behavior | BLOCKED-BY-DATA | Old Poisson interval/tail diagnostics in evidence/scored_v3/scores.json; no WS3 forecasts. Untouched PIT/zeros/tails/interval and market/stat-specific probability reliability |
| WS3 | Matched proper-score gain | BLOCKED-BY-DATA | No source-matched WS3 eligible predictions. Paired count CRPS/NLPD and threshold Brier/log-loss with coverage and dependence |
| WS3 | Valid conditional sampling | BLOCKED-BY-DATA | Boundary fixture only. Conditional draws match law and supplied opportunity; support/conservation checked over full scenarios |
| Foundation | Deterministic end-to-end fixture | PASSED | sample_joint_fixture.json; fixture digest 186001346386110d9095e283365c83feb42e8e78316ec0d48aed42ab29bdada4. Shared game/scenario/seed, minute/shot/point conservation and same-player combos |
| Foundation | Actual integrated deterministic replay | BLOCKED-BY-DATA | No WS1/WS2/WS3 runtime artifact triple. Frozen source-to-threshold replay identical across repeats and worker order |
| Foundation | No invalid source/probability states | BLOCKED-BY-DATA | New validator negative controls pass; actual integrated universe not supplied. Zero critical violations, full attempt/rejection accounting, no repaired-in-place source/probability |
| Foundation | Contract identity and settlement | PASSED | 250 original NBA raw-source outcomes independently reconstructed; source-binding and DNP/push tests. Separate retrospective original test from future artifact acceptance |
| Foundation | Matched comparison against frozen models | PASSED | evidence/scored_v3/scores.json and contract_comparison.csv; 145-contract common support without unavailable NUTS. Preserve original models and explicit missing columns; no new averaging |
| Foundation | Predictive superiority | INCONCLUSIVE | One development-exposed date, five games; consensus descriptive delta -0.006807566910475942. Untouched prospective multi-date matched proper scores and prespecified dependence/multiplicity gates |
| Foundation | Quantified computation for evaluator | PASSED | evidence/replay_execution.json; local score build 1.08 seconds, peak RSS 82676 KiB. Bounded evaluation resource receipt only; no joint-simulator extrapolation |
| Foundation | Quantified actual integrated runtime | BLOCKED-BY-DATA | No joint/WS2/WS3 runtime artifact. Measure CPU, wall latency, memory, failed paths and Monte Carlo precision on matching real workload |
| Foundation | No unnecessary new market coverage reduction | BLOCKED-BY-DATA | Original 250 contracts retained; new model coverage unknown. Zero unexplained loss relative to locked universe; explicit abstention reasons and subgroup comparisons |
| Calibration | Untouched calibrated improvement | BLOCKED-BY-DATA | One exposed date; no earlier eligible OOF calibration dates. Locked stat/model/version, earlier OOF only; assess_untouched improvement/noninferiority and tail/coverage review |
| Economics | Product-specific edge | BLOCKED-BY-DATA | No original pickem execution/payout/void/correlation terms. Authentic compatible offered terms plus prospective dependence-aware economic evaluation |
| Joint engine | Original multivariate score | BLOCKED-BY-DATA | No original coherent NBA joint scenario ensemble. Frozen coordinates/weights/scales; Energy and VS_0.5 plus joint-event tests |
| Release | Production integration / full simulator | BLOCKED-BY-DATA | Source/runtime handoffs, scientific gates and separate release decision absent. Keep research-only; no automatic branch merge, Tier/weights/schedule change or NUTS restart |
