# ADR: Composer workstream 4 vs Cloud Agent branch naming (V25-P1.5-07)

**Date:** 2026-11-12  
**Status:** accepted for this ticket only  
**Governing:** PA-V25-MASTER-2026-11-09 / v1.1

## Context

Ticket V25-P1.5-07 (Composer Workstream 4) specifies branch name `work/v25-phase15-factor-capture` and isolated draft execution. The Cursor Cloud Agent default policy requires `cursor/<descriptive-name>-a86b` for automated PR branches.

## Decision

This implementation uses the **ticket branch** `work/v25-phase15-factor-capture` as the authoritative integration branch for P1.5-07. Cloud naming policy is deferred where it conflicts with an explicit V2.5 workstream ticket that already defines branch isolation and primary file ownership.

## Consequences

- PRs for this ticket target `work/v25-phase15-factor-capture` → `main`, not a `cursor/*` branch.
- Future Composer/cloud runs should either align ticket text with cloud branch policy or record a per-ticket ADR like this one.
- No change to production schedules, Tier authority, or model promotion gates.
