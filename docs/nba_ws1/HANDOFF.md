# NBA WS1 integration handoff and rollback

Governing plan: `PA-V25-MASTER-2026-11-09 / v1.1`. Ticket: NBA WS1, Phase 0R/1 source-integrity foundations. Status: implemented and tested, shadow-only; full source certification and independent review remain open. No statistical prediction model is implemented.

## WS2 — minutes and participation

Consume `players[].history`, actual historical minutes, five/twenty-appearance summaries, explicit starting observations, previous participation, original historical team membership, and separate availability evidence. DNP and played-zero are distinct. A season roster is membership evidence only. Check `ELIGIBILITY_UNCERTAIN`, `ROSTER_TRANSITION_REQUIRES_REVIEW`, availability gaps and roster collision codes before selecting a player.

Do not use descriptive means/standard deviations as already validated predictive parameters. Do not substitute same-game boxscore minutes. The sample has only two recent team games per side, not a populated twenty-game history. Build a WS2 adapter and its own model manifest; provide the true training cutoff to WS1 and verify it externally. WS1 does not require one minutes distribution or one training horizon.

## WS3 — outcome likelihood and future joint simulation

Consume actual prior count vectors, shot/FT attempts where present, prior team/opponent profiles, rest and explicit pace/possession gaps. Preserve source receipts when deriving additional features. Historical starters, attempts and correlated player-game components are available; no future lineup, realized pace, final score or realized overtime is available. The raw prior player-game rows allow WS3 to choose different windows without changing WS1.

Do not equate the empirical arrays to a likelihood or infer possessions from incomplete player tables. True usage percentage, touches, shot tracking and rebound opportunities are not supplied. Any independently sourced possession estimate needs an explicit definition and source adapter. Composite market references remain tied to their original statistic and period; no independent-count modeling assumption is imposed.

## WS4 — independent evaluation and certification

Load through `NBAPregameFeatureSnapshot.from_json`, verify retained source bytes with the replay workflow, call `require_usable`, and retain the full ledger and per-player missingness. Check immutable snapshot, receipt and record hashes, actual downstream training manifests, contract periods/terms, and independent identity/roster evidence. Separate prospective packages, retrospective proxies, missing offers and outcome archives.

The existing Phase 1 evaluator is untouched. Its original November 10 benchmark was reproduced in a separate read-only Deepnote run twice with identical bytes. The output preserves 250 NBA / 106 NHL contracts, 1,314 attempts and two unresolved NHL cases. These are regression cases, not fresh predictive validation. See `benchmark_replay.json` for exact hashes and the retained first failed-run diagnosis.

A new reviewer must independently inspect WS1. This implementation session's sequential adversarial pass and separate runtime do not constitute an independent human or independent-agent approval. No predictive or economic certification follows from these tests.

## Integration commands

From the repository root:

```bash
python -m unittest discover -s tests/nba_ws1 -v
python -m v2.nba_ws1.replay docs/nba_ws1/sample --expect-hash a0532e8c6f26ea47102a9a6867f7c030c9914a79999d6124481066d779a4cf13
python -m v2.nba_ws1.audit --root RESTORED_WAREHOUSE_ROOT --as-of 2026-11-15 --output NEW_AUDIT_PATH.json
```

The last command's uppercase paths are required caller arguments; the archive source is the existing `data/bayesian-history` branch. Use a read-only copy at its pinned SHA, not an altered production archive. The existing collector and warehouse remain authoritative. A deliberate new one-shot pregame capture can be invoked with `python -m v2.nba_ws1.capture --day YYYY-MM-DD --output NEW_DIRECTORY`; it has a small, fixed request scope, creates no scheduler, fetches no paid props and never refits a model.

The legacy population adapter returns `(records, rejection_ledger)`. It defaults to rejecting all game scopes until a caller supplies explicitly approved `eligible_game_ids`, and always rejects non-franchise exhibition teams. Numeric ESPN team IDs and historical abbreviation IDs need an explicit dated crosswalk; never change the namespace or join on a name to make a replay run. Use the quarantine list as an exclusion source, but do not confuse “not quarantined” with independently certified regular-season scope.

## Smallest next work

1. Independently review the new interface and quarantine evidence before accepting the infrastructure PR.
2. Resume the **existing** recent historical collector from its actual November 1 cursor in a separately bounded, authorized execution. Do not introduce a second scheduled collector. Preserve its original files; corrections need separate versions.
3. Reconcile the regular-season game-ID denominator against an independently retrieved league schedule, including canceled/postponed and NBA Cup final classifications. Counts alone are insufficient.
4. Supply dated crosswalk evidence, game-active eligibility and source-authenticated pace/possession data where genuinely available. Capture original compatible quotes only through the established market path; keep missing quotes and payout terms explicit.
5. Have WS2/WS3 adapters declare their own required fields and actual model-training manifests. WS4 independently validates the complete flow before any trusted forecast claim.

## Rollback

There is no deployment, migration, scheduled job, production import change or archive rewrite. The base is main `912bc7010058092ea735dcda0aa941429194474b`; the warehouse read is `97a8bb566826afe5a3e5a7b8c632043d8a1dca24`. Rollback before merge is to close the draft PR and leave consumers on the existing code. After merge, revert this isolated PR commit; remove downstream opt-in adapters or pin their preceding versions first. Do not delete or rewrite original forecast/source archives, training pause markers or the authoritative warehouse.

The new Deepnote notebook is unscheduled and has no production dependency. Its two research run receipts can remain for audit; no running process or new automation needs to be stopped. Exact code commit and PR URL are recorded in the final delivery receipt/PR, avoiding a self-referential commit hash inside its own tree.
