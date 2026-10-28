# Evidence-gated ranking repair — 2026-10-28

## Problem confirmed in actual afternoon production artifacts

GitHub Actions run https://github.com/royalexx/pickem-auditor/actions/runs/40763081752 generated 1,248 immutable shadow forecasts (1,084 NBA, 164 NHL); 122 had usable numeric grading probabilities. Research triage generated 22 candidates and checked 10, but zero approved Tier 1–3 picks. Model and market probabilities are NOT independent active-roster proof.

**Independent root causes, not one engine bug:**

1. Research triage sorted by decreasing model-minus-market gap. The numerical engine's `GAP_WATCH_CAP=0.08` forces *any* such candidate to Watchlist regardless of further scouting. 13 of 22 queued NHL candidates exceeded the cap, and the first ten selected for independent checking were all among those 13. Verification spent scarce source calls on candidates that had no legal route to a Tier.
2. The automated 15-game source-audited workload mechanism could never evaluate many healthy players early in October: several had 10–14 games in the 2026–27 season. The prior 2025–26 regular-season official game log is now independently fetched and identity+date+SHA256 validated when necessary, and is **re-fetched and SHA verified again** during automated review. The numerical 15-game requirement was **not weakened**. Old observations are not treated as current-season deployment.
3. ESPN NHL pregame summaries did not give explicit `roster[].active` flags for the 2026-10-28 fixtures. Independent official NHL `gamecenter/{id}/boxscore` inspection before game start showed `gameState=FUT` and empty `playerByGameStats` and scratches for all four games. None authorizes a pregame active-player claim. The former 25–55-minute-only recheck window could not incorporate roster announcements near puck drop; it now also accepts the final **1–8 minutes before start**, and the verification schedule includes targeted `:27` and `:57` final evening triggers. Started games still fail closed.
4. Initially just ten per slate were investigated/verified despite 22 queue candidates. The afternoon workflow now investigates and verifies up to 30 prioritized candidates (not 30 paid odds pulls). Existing independent-book and evidence requirements remain unchanged.

## Real immutable forecast replay

Source evidence: https://github.com/royalexx/pickem-auditor/actions/runs/40766493614. Reproduced the actual persisted `2026-10-28` afternoon batch under the new code: `forecasts_evaluated=1248`, `review_queue_count=22`, **10 were below the forced Watchlist gap**, and all ten were selected first. 22 current-season official historical observations were crosschecked with the independent collector, and 21 players received independently verified source-digested previous-season logs (including actual 2025–26 seasons). The remaining one lacked a valid sufficient prior-season population. No facts were fabricated and zero unverified events were promoted.

Official four-game NHL source inspection: https://github.com/royalexx/pickem-auditor/actions/runs/40766576987.

## Safeguards retained

- Source timestamps must precede puck drop, and original forecast digest remains immutable.
- Exact athlete ID, sport, both teams, event start, sample game IDs and source content digests cannot mismatch. One prior season does not verify tonight's position, role, active status, lineup, or matchup.
- At least two independent approved book prices at the same line, with current timestamps, and both engines reliable before consideration.
- Large model–market gaps stay capped at **Watchlist** (no made-up override). The new queue **prioritizes** the eligible group without relaxing this rule.
- Machine-only scouting can never claim a human read or assign Tier 1/2 through its own overlapping historical evidence; any machine-approved tier is capped by source-quality constraints.
- Tier 1–3 still require all numeric, current market, active game-day identity and scouting/adversarial evidence. The verified board remains the only published pick list. Other candidates remain research queue or Watchlist, not falsely approved.
- No betting accounts, wagers, paid odds quotas, Engine A/B weights or model promotion were changed.

## Remaining real-world source dependency

Before an official game-day lineup or equivalent explicitly confirmed player-active report is made available, a trustworthy verified Tier for that NHL skater **cannot** be emitted by the existing strict rules. Official roster/boxscore feeds may publish only very close to game start or after it, and GitHub scheduled jobs are best-effort. Late-source monitoring improves coverage but does not guarantee a populated feed. If game-specific active evidence remains unavailable, leave the candidate unranked for *verified picks* and expose the cause. Never equate absence from an injury list, a projected lineup or a historical appearance with confirmed active status.
