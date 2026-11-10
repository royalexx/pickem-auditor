## V2.5 governance and phase gate (mandatory for project PRs)

**Governing:** [V2.5 Master Implementation Plan v1.1](../docs/Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md) (`PA-V25-MASTER-2026-11-09`, revised Nov 10, 2026)

**Current launch brief:** [V2.5 Next Workflow Launch Brief v1.1](../docs/Pickem_Auditor_V2_5_Next_Workflow_Launch_Brief_v1_1_2026-11-10.md)

- [ ] Read `README.md`, `AGENTS.md`, the V2.5 master plan, and the current launch brief.
- [ ] Reconcile current `main`/branch SHA, relevant live source receipts/runtime/schedules, and existing implementation before asserting status.
- [ ] State phase and ticket (0R, 1, 1.5, or individually evidence-authorized later research); identify prerequisite and acceptance/stop gate.
- [ ] Explain any deviation from the governing plan, record an ADR/authorization as required, and identify superseded older instructions.
- [ ] Confirm whether this PR is *documentation/infrastructure only*, *shadow research*, or a proposed *trusted release*. Code completion is not scientific validation.

### Exact source, temporal and market integrity

- [ ] Original pregame event/player/market/line/period identities, source receipts, UTC timestamps, input freeze, and model training cutoffs are verified where applicable.
- [ ] No future/postgame information is used as a pregame feature. Oracle substitutions remain retrospective diagnostics only.
- [ ] Freeze/source/quote records are immutable; accepted, rejected, unmatched, push/void, and abstention denominators are retained and separately counted.
- [ ] No synthetic-line model score is presented as real-offer sportsbook advantage or as a prospective certified pick.
- [ ] Frozen 60/40, legacy engines/compared probabilities, NUTS artifacts, source/settlement ledgers, and existing comparison output remain inspectable.

### Evaluation, adversarial review and release gates

- [ ] Named hypothesis, simple baseline, same-contract cohort, chronological split, expected improvement, exclusions, and stop/rollback rule were declared *before* statistical results where relevant.
- [ ] Report proper scores, directional Over residual/Under skew, calibration, coverage, uncertainty and clustered comparisons as appropriate to the ticket.
- [ ] Execute relevant negative controls: time leakage, identity mismatch, reversed sides, support/conservation, duplicate selections, and missing data.
- [ ] Document mathematical/independent review evidence, test summary, failures/skips and input/output hashes.
- [ ] No Tier 1/2 unlock, posterior restart, automatic release, schedule reactivation, or claimed economic edge without separate explicit approval and governing evidence gates.
- [ ] For a Phase 2/3 or later modeling ticket, cite the independently reviewed Phase 1.5 error-priority decision and a preregistered bounded experiment. If missing, keep challenger deferred/shadow-only.

### Evidence receipt

- Governing master version / launch brief version:
- Phase and ticket / status:
- Base and head SHAs / changed files:
- Source and output receipts with SHA-256:
- Forecast timestamp/training cutoff/offer provenance:
- Cohort sizes (eligible, scored, unmatched, rejected, abstained, void):
- Baseline, challenger and precommitted metrics:
- Cluster unit, intervals, negative controls, tests:
- Independent adversarial review and unresolved blockers:
- Rollback / deployment decision (default: shadow-only, no promotion):

### Supporting older research

[November 8 directional research contract](../docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md) and `config/directional_research_baseline_20261108.json` remain frozen background. Their requirements apply where compatible with the approved v1.1 V2.5 amendments; they do not override the master plan.
