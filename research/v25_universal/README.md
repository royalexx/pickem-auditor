# Pick'em Auditor V2.5 — Universal Prospective Validation (research-only)

This workstream implements four bounded changes without changing existing production A/B, Bayesian, NHL collectors, or the pinned NBA ten-game registration.

## 1. Automatic engine registration

Use \`research.v25_universal.registry.create_manifest(...)\` before kickoff. Write a **create-once** batch under \`/work/reports/v25_model_registry/<unique-batch>/\` containing:

- \`manifest.json\`: schema \`V25FrozenResearchManifest/1\`, sport, engine ID, \`first_archived_at\` with actual original runtime timestamp, original JSONL SHA-256 and exact row count.
- \`forecasts.jsonl\`: one \`V25FrozenResearchForecast/1\` per player/game/stat/original contract. Includes frozen source hash, receipt time, freeze time, forecast time, model cutoff, event start, conditionality (\`given_played\`, \`conditional_nonpush\`, \`unconditional\`), and *actual* discrete PMF or NBA minutes-law parameters.

The model name is not hard-coded; O1-O5, J3, future NHL engines, and NBA M0/M1/M2/J0/J1/J2 may register if they truly have original pregame outputs. The registry rejects post-kickoff first registration, changed bytes, duplicate engine/game/player/stat/contract, training leakage, missing source hash, and retrofitted synthetic fixtures. An absent engine is **not** an accepted forecast, and a forecast with an ineligible source is not promoted. The older historical/fixture outputs **must not** be registered as prospective.

Models without a real frozen probability have **ABSTAINED**, not a modeled zero. Full league eligibility, sportsbook payout terms and upstream source-publication truth are **not inferred** from a SHA or claimed timestamp.

## 2. NFL forward collection after November 15

\`research/v25_forward/nfl.py\` is date-agnostic. The fixed November 15 WS1 source remains untouched. A **single detached Deepnote worker per NFL game date**:

- Reads the real ESPN schedule, locates every game in the given Toronto date, and establishes original game/player/line identities
- Waits for each selected game's **T−60 minute** source window; all receipts and the frozen source snapshot must complete **before T−30 minutes**
- Stores original ESPN raw schedule, roster, depth, injury bytes plus one quota-guarded authentic two-sided PropLine offer batch daily, retaining per-source SHA and original clocks
- Rejects unresolved roster mapping, missed deadlines, schedule changes, missing odds, absent credentials, and quote conflicts. No Underdog odds, invented sportsbook prices, game-day active-list proof, probability fitting, or synthetic lines
- Creates event-local exclusive \`ACQUISITION_CLAIM.json\`, immutable source snapshot, and \`FIRST_CAPTURE.json\` SHA pointer in \`/work/reports/nfl_forward_original/YYYY-MM-DD/event_ID/\`; a failed first claim cannot be silently retried
- Adds \`research/v25_forward/scoring.py\`: independently fetches post-start ESPN \`STATUS_FINAL\`, checks event/home/away/player/team/stat identity, and settles original outcomes without treating missing player category as 0 or conflating ESPN \`TOT\` with original tackles+assists
- A second trigger may use \`--resume\` **only when independent Deepnote execution status confirms the earlier worker is no longer active**, with \`NFL_FORWARD_PRIOR_WORKER_INACTIVE_VERIFIED=1\`. Existing original quote receipts must hash-check and all first captures remain untouched. A still-running worker must never be duplicated.

The collector **does not itself create new engine forecasts**; the registration handoff above allows any validated model to publish a true pregame forecast for these original contracts. Coverage, not prediction success, is the first live milestone. This also avoids claiming NFL one-off WS2/WS4 runs automatically generalize to later weeks.

**Free Basic CPU / scheduler caveat:** Scheduled Deepnote is a launched attempt; the detached worker must survive until the final game window. Late-window interruptions are explicit \`MISSED\`/BLOCKED, never retrospectively filled. One ChatGPT task can trigger both early and late game-date runs while preserving the exact original deadline.

## 3. Unified proper-score, calibration and paired reporting

The existing pinned original NFL WS6 S2/C2/J1/J2 immutable first-forecast ledger remains the 1,845-contract benchmark. \`research/v25_morning_validation/score.py\` now invokes \`research/v25_universal.report.build\` *after* its legacy NFL and NBA settlement audit, before its append-only daily report manifest. It automatically reads independently registered additional model freezes and source-qualified future NFL quotes and creates:

- \`registered_model_scoring.jsonl\`: each registered original model's exact outcome join or abstention/block reason
- \`nfl_forward_contract_outcomes.jsonl\`, \`nfl_forward_settlement.json\`
- \`unified_model_comparison.json\`: original candidate denominators, model and market coverage, missing/invalid statuses, Brier, log loss, PMF CRPS, calibration deciles, and **paired same-contract** model differences per sport/market
- Game-cluster rather than individual-bookmaker bootstrap; confidence bands remain null until at least twenty separate games and five dates, and all statistics remain descriptive until a genuine independent prospective temporal holdout is reviewed.

S2, J1, J2 are conditional on playing. C2 is conditional on non-push. They are not interchangeable with unconditional probability or product-specific betting outcome. Several sportsbook quotes referring to one player stat do not count as independent games. Distinct stat units are not combined into one CRPS.

## 4. NBA conditional minutes and count observations

\`score.py\` now emits source-original \`nba_settled_candidates.jsonl\` from independently retrieved ESPN final **raw bytes** and previously frozen Phase 8C first-capture ledgers. A registry row with exact NBA game/player/team/stat and valid pregame timing is scored **only if the original candidate is explicitly PLAYED**:

- M0/M1/M2 \`nba_minutes_law\`: positive-minutes conditional CRPS by deterministic numerical CDF quadrature, absolute mean error, 90% interval coverage and PIT (no re-fitting)
- NBA conditional counting stats and combinations: exact frozen discrete PMF CRPS; Brier/logloss only for a genuine original quoted threshold and non-push observation
- DNP, missing/unlisted player, absent statute, unsupported contract or unfitted J2 F are excluded with explicit separate denominators, not encoded as zero
- Unconditional NBA scoring requires independently verified legal eligibility and a previously frozen participation probability. The existing P1/P2 and J2 gate remains BLOCKED until genuine full-coverage pregame data exists.

The scheduled NBA pilot remains the **sole** pregame NBA collector. This integration does not modify its ten original game slots or SHA.

## Operational rollout

- Research draft stacked on PR #145; never merge or promote automatically
- Deepnote tests: \`python -B -m unittest discover -s tests/v25_universal -v\`, prior \`tests/v25_morning_validation\`, \`tests/nba_phase8c\`
- The existing 06:00 Toronto morning notebook is repinned to the new research SHA after independent Deepnote tests; no additional morning task
- One separate NFL schedule may use the remaining active task capacity for future original-source acquisition, avoiding the old date-hardcoded Sunday collector

**Caution:** A registry and a collector do not themselves create accepted forecasts. New engines need their own frozen real source-to-model adapter. A valid research result means an original pregame model row and a genuine independently sourced final observation on the same identity, not a replay or data-leak artifact.
