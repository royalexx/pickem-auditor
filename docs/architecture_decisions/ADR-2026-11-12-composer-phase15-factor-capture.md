# ADR: Composer workstream 4 vs Cloud Agent branch naming (V25-P1.5-07)

**Date:** 2026-11-12  
**Status:** proposed / pending (not a repository-wide executor-policy exception)  
**Governing:** PA-V25-MASTER-2026-11-09 / v1.1

## Context

Ticket V25-P1.5-07 (Composer Workstream 4) specifies branch name `work/v25-phase15-factor-capture` and isolated draft execution. The Cursor Cloud Agent default policy requires `cursor/<descriptive-name>-a86b` for automated PR branches.

## Proposed decision (unmerged policy)

For ticket V25-P1.5-07 only, use branch `work/v25-phase15-factor-capture` as the integration branch. This documents a **local naming conflict** with the Cloud Agent `cursor/*` convention; it does **not** approve a general executor-policy override.

## Consequences if adopted

- PR #117 targets `work/v25-phase15-factor-capture` → `main` for this ticket only.
- Repository-wide hygiene (e.g. AGENTS.md / vendor-ban tests) remains owned by separate governance PRs (e.g. #115).
- No change to production schedules, Tier authority, or model promotion gates.
