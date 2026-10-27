# Verification tasks and regrading

`scan.research_candidates` includes promising sides blocked by missing confirmation, venue/weather, context, or quote freshness. These are research tasks, never published tiers. Statistical sample/distribution failures stay blocked. Existing publication gates and blend mathematics are unchanged.

The unified collection workflow emits `research_queue.json`. It deduplicates shared missing fields, retains candidate-specific blockers and lists source conflicts. Follow the research blueprint for every candidate; do not stop because the publication shortlist is empty. The queue is an agent work plan, not proof that web research occurred.

From repository root:

```bash
python3 scripts/research_tasks.py --packet RUN/research_DATE.json --scan RUN/scan.json --prep RUN/prep.jsonl
```

Use actual paths. Add `--refresh-context --slate RUN/slate_fetch.jsonl` to retry the existing live context collectors and record their returned notes. This performs network requests and must be reserved for an intended live refresh. It does not automatically discover or extract arbitrary web pages. The running research agent must pursue remaining official, team and credentialed beat sources, reconcile opposing evidence, and record exact blockers. Avoid duplicate refreshes of already-current feeds.

After updating the packet, add `--audit` to validate, merge, regrade and reconcile the complete output ID set against prep. Duplicate, missing, substituted or extra IDs fail reconciliation, including equal-count substitutions. Audit failures are errors, not a successful empty board. Canonical `research_packet.py audit` also validates input/output identities and reports reconciliation to stderr. Publication still requires all original checks.

For status conflicts, distinguish report publication time from retrieval time. Optional raw fact metadata `published_at` (ISO timestamp) and `report_type` (`practice_report`, `game_day_report`, `final_active_roster`) may be recorded only after verifying the source's actual report scope and date for this game. The merge gives final game-active rosters precedence over game-day reports, then practice reports, and uses publication time within a report type. These fields are source observations, not model adjustments. They do not raise reported evidence to confirmed confidence.

Contradictory statuses without sufficient report metadata become null, with both observations retained in `_source_conflicts`. Repeated feed refreshes cannot clear an unresolved conflict. A research agent must verify a resolution, record its rationale and sources, update the status fact, and explicitly replace/remove the resolved conflict record before merging again. Never resolve a conflict using only download order, absence from an injury list, or generic roster membership.

Status facts, source conflicts and task completion never add probability directly. Upcoming injuries continue through the single shared-context allocation; A and B source baselines remain isolated from those adjustments.


## Structured resolution and source attempts

The unified collection command now invokes `research_tasks.py --resolve`. On a manual run, add `--resolve` to the task command to fetch sport/date-specific ESPN scoreboards, match exact fixture teams and date, resolve explicit venue indoor fields, and inspect game-specific summary rosters. Only explicit boolean active/inactive flags in a matched pregame game roster can establish availability. Generic roster membership, projected lines and missing injury entries remain insufficient. Inactive means unavailable for this game, not a medical diagnosis.

Requests have bounded timeouts; failures and zero useful results are retained in `_research_attempts`. Publication remains blocked by unverified facts. Final game-roster snapshots use `observed_at`, not an invented publication time; they can resolve prior report ambiguity while retaining competing evidence. No numerical injury uplifts are generated.

After resolution the packet is saved atomically, validated, merged and rescanned. The full audit runs automatically and reconciles IDs. Started candidates receive `GAME_STARTED` and remain Unranked. If existing facts are stale or invalid, the command returns a blocked audit report and a nonzero exit code; it does not silently relabel old information as fresh. Other missing source fields remain explicit agent research work.

Gap generation is conditional: NFL/NBA players do not receive NHL line/pair/PP checks. Goalie confirmation is requested for saves, defensive pairings for blocked shots, and weather details only after a verified outdoor venue. An unknown venue produces a venue-verification task first. NBA environment checks remain applicable.

## Candidate dispositions and task scope

The audit also emits `dispositions`: exactly one record per research candidate,
with `ranked`, `rejected`, `watchlist`, `blocked`, or `excluded`, concrete blockers,
remaining adversarial review, engine diagnostics and numerical-band diagnostics.
A numerical band never replaces `final_rank`. Missing or duplicate audit results
fail rather than silently dropping a candidate. A disposition report alone does
not attest completed source research. Every blocked case must retain its source
attempts and exact missing evidence in the run handoff.

Task `requirement` distinguishes `verification` from `supporting_research`.
Historical Engine B does not require free-form scouting numbers to compute its
baseline. Its advanced questions remain mandatory to investigate as adversarial
research; an unavailable tracking metric must be documented, never invented.
Do not treat all unanswered narrative fields as numerical engine failures, or
claim that populating them will clear actual availability/context gates.

Normalize market aliases before selecting required checks: `goalie saves` and
`saves` both require goalie starter confirmation and goalie-specific evidence,
not skater lines or power-play units. Missing availability remains discoverable
in the scan after venue confirmation, instead of disappearing as generic Unranked.

## ESPN starting-goalie confirmation

The NHL scoreboard endpoint
`https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates=YYYYMMDD`
can expose `events[].competitions[].competitors[].probables[]`. A goalie item
has `name: probableStartingGoalie`; that name alone is NOT confirmation. Only
an explicit `status.type: confirmed`, exactly one confirmed goalie for that
team, a matching named player/team/game, and a verified pregame fixture can set
player-specific `goalie_confirmed: true` and active status. ESPN athlete IDs use
a different namespace from NHL IDs; retain the ESPN ID as provenance rather
than comparing it directly with the NHL ID. No confirmation transfers to backups.

The resolver now consumes this field before checking game-summary rosters. Its
report includes `goalie_observations` and `resolved_goalies`. API retrieval time
is an observation time, not an invented report publication time. Conflicting
Out reports remain unresolved and require source review. Publication still
requires market, history and other relevant checks; this is not a tier override.

If the field is absent or merely probable, use web search to find the dated
Daily Faceoff starting-goalie report and its cited team/beat source. Read the
report, verify Confirmed versus likely/projected, match the fixture and look for
later contradictory updates. Enter the evidence through `verified_reports.py`.
Do not use search snippets or post-start confirmations as pregame evidence.
A successful empty ESPN roster is no longer a reason to stop goalie research.

## Ranking-blocker repairs

Packet merges record their original input fields in `research_merge_base`.
Re-merging after a corrected status or weather report restores those inputs and
recomputes packet-owned vetoes, contextual fields and soft flags. Original
collector/operator vetoes remain. Use original prep when changing operator inputs;
do not edit the generated provenance object to override a failed check.

The canonical audit validates each candidate's relevant packet scope. It retains
same-game availability, including teammate absences, and unknown identity facts.
An invalid fact from a clearly unrelated fixture cannot stop that candidate.
Every requested candidate still produces exactly one result; invalid relevant
facts produce `RESEARCH_PACKET_INVALID` with paths and a nonzero overall exit
status. Valid candidates are evaluated even in a partially invalid batch. Do not
call that partial batch fully complete. Standalone `validate` remains whole-packet
validation; `to-pipeline` remains strict. Structured resolution uses the same
candidate-scoped preparation as the audit.

New prep includes `market_retrieved_at`, the oldest contributing quote timestamp.
Grading recomputes elapsed price age, so time spent researching cannot freeze a
quote's freshness. Live audits require that absolute timestamp. Older prep with
only `retrieved_minutes_ago` must be rebuilt from freshly collected quotes;
never stamp an old price with the current time. Explicit `--now` remains for
retrospective replay at a known evaluation time, not for live publication.
