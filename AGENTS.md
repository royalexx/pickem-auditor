# Pick'em Auditor — agent operating instructions

## Required reading before any project task (V2.5, governing v1.1)

This repository is governed by the **November 10, 2026 V2.5 Master Implementation Plan v1.1**. Every ChatGPT-controlled coding, research, validation, audit, and orchestration agent must read, in order:

1. [README.md](README.md) — repository overview, entrypoints, and historical context.
2. [V2.5 Master Implementation Plan v1.1](docs/Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md) — **primary governing architecture, scientific contracts, phase gates, and release policy**. Read the applicable sections in full before making changes.
3. [V2.5 Next Workflow Launch Brief v1.1](docs/Pickem_Auditor_V2_5_Next_Workflow_Launch_Brief_v1_1_2026-11-10.md) — current recorded checkpoint and next-session work instructions. Treat dated numbers as **historical checkpoints**, not verified live state.
4. This `AGENTS.md`, plus the files, phase-specific docs, live status receipts, and original frozen source artifacts relevant to the assigned ticket.
5. [November 8 directional accuracy research baseline](docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md) and [frozen baseline manifest](config/directional_research_baseline_20261108.json) when work intersects forecasting, probabilities, calibration, ranking, or validation. These remain essential **supporting research**, subordinate to the approved V2.5 v1.1 amendments when instructions conflict.

**Precedence:** the governing master plan defines *what is permissible and what evidence is required*; the launch brief describes *what to investigate next*; the README and historical research supply context; phase-specific documents describe implementation details. The actual repository HEAD, currently running jobs, immutable forecast/source receipts, accepted commits, and reproducible test artifacts establish what is **factually true today**. If instructions conflict, do not quietly choose a convenient rule: follow the most recent explicitly approved governing amendment and document the conflict in an architecture decision record (ADR). A dated report never overrides newer verified evidence. User-specific instructions and security constraints continue to apply.

### Mandatory startup checklist for every agent or new workflow

- Read the four top-level onboarding/authority documents above **before** proposing work; report the governing version (`PA-V25-MASTER-2026-11-09 / v1.1`).
- Inspect actual `main` commit, relevant branches/PRs, active workflow schedules, Deepnote source/notebook state when applicable, model training pause markers, and original source hashes. Do **not** infer merge, certification, or deployment from narrative status.
- Classify the requested work by Phase 0R, 1, 1.5, or a conditionally approved later phase; identify prerequisites, the exact bounded ticket, validation method, and rollback.
- Record `implemented`, `tested`, `independently verified`, `blocked-by-data`, `shadow-only`, `rejected`, or `release-approved` with evidence. Do not use `done` when only code or historical diagnostics exist.
- Preserve source/quote reject denominators and failed forecast records, including invalid/missing identities and timestamps. Never retro-certify or silently drop them.
- Do not begin expensive Phase 2–8 modeling simply because a plan lists it. Phase 1.5 error diagnosis and preregistered pilot evidence decide investment; Phase 0R source integrity gates trusted release.

### Non-negotiable development and operational rules

- **Point-in-time integrity first:** use authenticated pregame source, input freeze, model training cutoff, event/contract identity, quote receipt, and immutable snapshot lineage. No future/postgame data in pregame features.
- **Separate integrity, forecast quality, and market edge:** synthetic sportsbook lines and exploratory Brier improvements are diagnostic, never proof of real offered edge, profits, certified forecasts, or high-confidence Tiers.
- **Keep the frozen legacy 60/40 model and Engine A/B, Bayesian A/B, strict NUTS outputs, posteriors, and historical settlement/provenance ledgers** as auditable controls. Existing `config/production_consensus.json` describes legacy behavior; it is **not** evidence that the 60/40 model has validated authority to publish Tier 1/2.
- **Do not restart, alter, or destroy paused/active NUTS training**, rewrite historical forecast records, automatically change weights/thresholds, or re-enable the afternoon publishing schedule without specific authorization and relevant gates.
- **No paid-data dependencies** or GitHub-hosted coding agents/Copilot. Code changes are to be performed by ChatGPT-controlled tooling. Use an isolated branch, appropriate tests, review, and traceable PR/commit; do not equate an infrastructure merge with statistical promotion.
- **No trusted Tier 1/2 publication** before independent prospective, preregistered, dependence-aware reliability evidence and certification. If required receipt/offer/payout evidence is absent, mark output `UNCERTIFIED/SHADOW` or unavailable.
- Test exact Over/Under/Push complementarity, legal support, sport-specific constraints, leakage, role/participation uncertainty, model/source provenance, clustered matched validation, negative controls, and rollback as specified by the governing plan.
- Keep the existing slate comparison chart and report all **available** Engine A, Engine B, Bayesian A, Bayesian B, strict NUTS, frozen 60/40, market, and V2.5 outputs without fabricating missing columns. For each sport report all eligible candidates and a properly explained research top 10; do not confuse a research ranking with an approved pick.

### Current recorded starting point, **not** live certification

The v1.1 launch brief prioritizes bounded **Phase 0R-A** diagnosis of November 9 forecast certification failures (1,490 forecasts / zero certified) and separately 658 rejected quotes, with parallel immutable prospective quote/source capture. **Phase 1.5** code and historical 2024 synthetic-line analysis exist, but independent audit, authentic opportunity-factor inputs, and scientific exit gates remain unresolved as of the document's dated checkpoint. **Phase 1** reproducible baseline/evaluation contracts are required. Choose the first Phase 2/3 modeling pilot only after the signed Phase 1.5 evidence-priority decision. Phase 4–8 research remains individually conditional.

Before acting, re-check the live repository, original artifacts, and runtime: the preceding paragraph is not a claim about today's deployment or merge state.

### Additional research and implementation references

- [Directional research contract](docs/research/DIRECTIONAL_ACCURACY_RESEARCH_BASELINE_20261108.md) — retained as a frozen historical research baseline unless superseded by V2.5.
- [Phase 1 directional validator](docs/PHASE1_DIRECTIONAL_VALIDATION.md) — read-only, not release authorization. No production promotion or Tier changes.
- [Phase 1.5 methodology and tests](docs/PHASE_1_5_DIAGNOSTICS.md) — shadow diagnosis; not validated opportunity decomposition without genuine pregame factor forecasts.
- [Production validation](docs/PRODUCTION_VALIDATION.md) — consult alongside V2.5; older language granting Tier authority does not supersede the master gates.
- [Research/verification ranking](references/evidence_ranking_repair_20261028.md) and [verification policy](references/pick_verification.md) — legacy mechanisms and evidence infrastructure, not exceptions to source/certification rules.

**When reporting work:** include exact branch/commit/PR, source and output hashes, cohort and exclusions, adversarial test results, whether evidence is historical/synthetic/prospective, which gates passed or remain blocked, and the smallest next action. A new agent should be able to resume without relying on chat memory.
