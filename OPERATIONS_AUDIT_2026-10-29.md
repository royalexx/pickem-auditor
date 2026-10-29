# October 29, 2026 — live operations repair and source-coverage audit

Scope: fix the five October 28 operational-audit findings, independently validate Oct 29 settlement, keep historical pregame forecasts immutable and model/Tier weights unchanged.

## Live morning settlement — FIXED and executed

- The Oct 29 primary/backup morning schedule did not create a substantive daily job; green Oct 28 inactive-schedule job had skipped all substantive stages.
- PR #21 added an independent completed-history-workflow trigger and 09:37 Toronto backup plus an explicitly authorized same-day recovery-push path. Its first live recovery event (run 40883614646) was **green but skipped**, due to GitHub's push payload lacking expected file-added fields. This failure was detected from the actual job steps and fixed in the checked-out-commit recovery validator (main commits 4c8a793, 1cd897).
- The second authorized push created actual **morning** run [40884144700](https://github.com/royalexx/pickem-auditor/actions/runs/40884144700), completed successfully. All 10 required stages passed, including settlement, identity verification and history persistence.
- The run processed **1,368** previously unresolved forecast outcomes, settlement errors **0**, 3,934 total archive forecasts, **3,172 verified outcomes**, 762 unresolved. All three sport feeds verified: NHL 547, NBA 472, NFL 173 rows. Official NHL ingestion reported 0 errors.
- A durable completed marker now exists at `data/shadow-calibration:data/morning_runs/2026-10-29.json`, with `run_id=40884144700`, `settle_ok=true`, `identity_ok=true`. This is authoritative; no future duplicate same-day settlement without explicit force.

## Verification — DIAGNOSED, reporting fixed, evidence still missing

- October 28 research triage: 30 candidates, 0 approved. 29 lacked explicitly game-specific active status; ESPN's five official event-summary roster attempts returned `resolved_players=0` despite successful fetches. A retrieved injury list with no negative designation does **not** prove availability.
- PR #22 merged per-sport blocker counts, source-attempt status, and positive active-roster resolution counts into standard receipts; all tests passed.
- Remaining issue [#25](https://github.com/royalexx/pickem-auditor/issues/25) requires an independently confirmed, timestamped pregame player active-status source. No approval bypass or post-hoc source substitution authorized.

## NBA Bayesian A/B — historical bridge implemented, research-only

- Oct 28 shadow data: 1,388 NBA rows rejected for insufficient current-game history by BOTH independent A/B shadow models. Collected slate: 1,088/2,120 NBA stat rows had 3–4 current games plus >=10 prior observations; others not supported by that bridge.
- PR #24 merged a `nba-source-prior-power-v1` historical bridge for **both** Bayesian Engine A and workload/conversion Engine B: prior-season observations have likelihood weight 0.4, current observations weight 1. Requires 3–4 current, 10–20 prior, >=5 independently verified peers, positive workload, strictly pre-event dates, unique game IDs, bounded workload consistency; fail-closed otherwise.
- Both models remain shadow-only. No production model, Tier or weight changes; CI including both NUTS checks passed. Actual prospective production coverage after this integration has **not yet been measured**; see issue [#27](https://github.com/royalexx/pickem-auditor/issues/27).
- Oct 29 morning Phase4 results on prior production data: zero matched precommitted Bayesian A/B shadows, only one calendar date of newly settled legacy predictions; legacy-A three-class Brier 0.571259 on 1,368 newly settled, log loss 0.803499. These observations are **not** adequate for a new ranking weight, and results on all candidate rows are not a verified picks win rate.

## Fixture home/away — FIXED

- Previously, `team @ opponent` was rendered irrespective of venue. PR #21 now uses source-confirmed provider `event_teams=[home,away]` only when fixture/team identity agrees; otherwise displays a neutral `vs` label. `matchup_orientation_verified` and home/away fields are recorded. Conflicting venues fail closed. Regression includes NJD @ COL game.
- Original pregame forecast identities and settled outcomes are not overwritten by this change.

## NHL hits and blocked shots — source gap clarified, blocks fallback deployed conditionally

- PropLine Oct 28 reported no raw NHL `player_blocked_shots` market even with 4 pregame games. This is **absent upstream market data**, not a dropped normalized quote.
- PropLine and The Odds API standard NHL props do NOT expose player hits. OpticOdds documents hockey `player_hits` as a market, but a separate licensed OpticOdds connection is needed. See [#26](https://github.com/royalexx/pickem-auditor/issues/26); no hit prices are invented or inferred from lines on pick'em services.
- PR #23 added an optional 1-region `player_blocked_shots` per-event fallback from The Odds API, using the independent `ODDS_API_KEY` GitHub Actions secret. It runs only when the primary provider has no normalized blocked shots, is explicitly enabled by afternoon workflow, caps chargeable event calls at **8 per afternoon run**, validates source event/date/teams, requires approved real sportsbook two-sided prices, and redacts credentials. No secret -> no API calls. Tested with no-key, source fidelity and cap scenarios; CI passed.
- **No live The Odds API quote retrieval has been observed since merging the change**; the next actual source-supported afternoon execution determines whether it returns useful blocks.

## Reproducible changes

- [PR #21](https://github.com/royalexx/pickem-auditor/pull/21) morning reliability + venue labels + coverage audit
- [PR #22](https://github.com/royalexx/pickem-auditor/pull/22) research-source blocker observability
- [PR #23](https://github.com/royalexx/pickem-auditor/pull/23) optional capped NHL blocked-shot market fallback
- [PR #24](https://github.com/royalexx/pickem-auditor/pull/24) NBA verified-prior Bayesian A/B shadow historical bridge
- [Run 40884144700](https://github.com/royalexx/pickem-auditor/actions/runs/40884144700) authoritative morning settlement/archived artifacts.

## Compliance and remaining limits

No pregame probability was rewritten after events. No direct Underdog source or payout used. No fabricated active status or sportsbook quote. No promotion from shadow predictions or unsound auto-ranking. External providers and actual publishability must be independently rechecked against fresh, precommitted source evidence.
