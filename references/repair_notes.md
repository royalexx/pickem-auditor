# Historical repair notes

These entries document the earlier archive. Current behavior and readiness are in
`../AUDIT.md` and the current math/scouting guides. Retired Engine B statements
below do not describe production scouting-v2.

# Correctness / reliability patch — 2026-10-23

This patch is a **source-code repair**, NOT an assertion of live forecasting profitability, current feed authorization, or calibrated probabilities. Code/fixture validation does not prove a real URL supports a claim. Test with authenticated live sources, preserve evidence, and build out-of-sample settlement before trusting Tier 1 as a frequency claim.

## Remediation matrix vs prior audit

| Audit ID | Current status | Patch / limitation |
|---|---|---|
| F01 Cursor activation | Remediated | Canonical `.cursor/skills/pickem-auditor/SKILL.md` and a description-applied `.cursor/rules` rule, no globs |
| F02 crosscheck units | Remediated | Probability-unit discrepancy tolerance 0.08 (provisional), `se_b` only validated as stat SE |
| F03 source/mechanism confusion | Remediated with manual judgment still required | Count distinct events by `event_id` or fallback type+description, not URLs. Duplicate event validation |
| F04 role-window integrity | Remediated/fail-closed | Counts never overwrite model windows; mismatches result in explicit data veto |
| F05 odds outage masquerades as no props | Remediated | Prep exits nonzero on missing priced sides; structured slate/quote/coverage diagnostics; shadow snapshot fails on missing quotes |
| F06 force-push persistence | Remediated in code; hosted Git validation needed | Single GitHub job + concurrency, restore historical branch, worktree commit, force-add allowlisted JSONL, non-force-push |
| F07 Out/unknown availability | Remediated in research merge | Out hard veto; unknown data veto; questionable/doubtful flag |
| F08 weather coverage | Improved; forecast coverage must still be verified | Indoor/outdoor required; outdoor forecast requires named fields and window, not any one field |
| F09 QB/goalie confirmation | Remediated for passing/saves | Missing starter confirmation is data veto, explicit no is hard veto for BOTH directions |
| F10 URL provenance | Partially remediated | HTTP(S) public link syntax and timestamps validated; verifying live content/claim truth requires retrieval and researcher review |
| F11 same-name identity | Partially remediated | Prep carries player/team/event metadata; optional `index.by_player_id` (`sport|player_id`); conflicts fail closed. Name-only upstream data cannot always be uniquely resolved |
| F12 shortlist gap routing | Remediated | `gaps --scan <scan.json>` consumes actual Stage D shortlist |
| F13 same-date snapshot ID | Remediated | Morning/afternoon ET slots produce distinct run IDs; repeated same-slot job is idempotent |
| F14 closing line move | Remediated | Closing consensus selects current market line rather than requiring the opening reference line |
| F15 calibration evidence | Not yet statistically verifiable | Existing settled-sample gate retained, probabilities explicitly uncalibrated; no empirical outcome file supplied |
| F16 full error budget | Partially mitigated | Unknown essential inputs fail closed; no claimed calibrated role/context uncertainty yet |
| F17 market agreement interpretation | Clarified in references | Market is a benchmark, not a validation test |
| F18 walk-forward validation | Historical workflow repaired, empirical validation pending | Stat/sport side reporting and blend infrastructure retained, requires sufficient new settled observations |
| F19 DST duplicates | Remediated in code | `schedule_gate.py` chooses only genuine Toronto-local slots |
| F20 low-sample weekly CI failures | Remediated | Empty/underpowered fit is diagnostic, no release weights, weekly job stays successful |
| F21 preflight 4xx masquerading as success | Improved | 401/403/429 now fail; 404 root path still only indicates reachability; authenticated odds feed confirmed by actual fetch/coverage |
| F22 inaccurate references | Updated | Root README, skill, and affected references explain changed behavior |
| F23 dirty ZIP | Remediated | Clean package without `.git`, transient caches, research output or credentials |
| F24 trigger research missed | Mitigated | Actual scan shortlist used for packet gap search; unflagged numerical candidates remain eligible; contextual-trigger selection still relies on validated upstream flags |

## Changes in design behavior

- **Engine B for NFL total receptions/receiving yards now abstains** unless the read-bucket projection is validated as a full-stat model with `reads_total_stat_validated=true`. That flag is **never automatically set** in the feed; this prevents partial checkdown/first-read counts from demoting totals.
- NFL kickoff from `nflverse` `gametime` is Eastern local, converted to UTC; ambiguous offset-free ISO timestamps are not assumed UTC.
- `run_snapshot` uses local morning/afternoon buckets for idempotence (09:00/14:00 Toronto). Github checkout + worktree history must be field-tested with a repository token and branch permissions.
- Research facts are syntactically validated and require proper URLs, but **source contents are not independently downloaded and validated by the Python schema**. An agent must retrieve pages and verify the claim itself.
- Persisted snapshots only belong to separately enabled *shadow calibration*. User-facing picks and research should be delivered in conversation, not automatically logged.

## Smoke testing

From the project root:

```bash
python3 -m compileall -q scripts
python3 -m unittest discover -s tests -q
python3 scripts/schedule_gate.py --schedule '0 13 * * *'
```

The time gate uses the execution date to map UTC cron to Toronto time. Production test requires GitHub Actions on a real repo (source reads, a writable `data/shadow-calibration` branch, `ODDS_API_KEY` secret, API access). Calibration validation requires real chronological, settled player-level histories. Do not use fixture successes as a profitability claim.

## 2026-10-27: source recovery, status and grading diagnostics

* A downloaded research packet is not a substitute for verified game facts. `research_recovery.py` restores **same-date, same-identity, fresh, source-backed** facts from a previous research packet. Example replay:
  `python scripts/research_recovery.py --current data/resumed-context/research_2026-10-26.json --prior data/research_2026-10-26.json --out data/recovered-packet.json --now 2026-10-26T21:50:00Z`.
  `--now` is for retrospective reproduction only; never use a past clock to publish live picks. `research_tasks.py --recover-packet path` can load one or more source packets before attempting new structured research.
* NHL injury resolver queries ESPN's explicit league-wide injury designations for pregame fixtures, and ESPN game-summary **explicit active flags**. Missing players in injury data or rosters stay UNKNOWN; projected lines never establish active status. Explicit confirmed probable starting goalies can populate goalie flags only when named and event/team matched.
* `context_feeds.merge_packet_no_clobber` no longer lets a newer download attempt replace a later-timestamped observation from the same field; availability contradictions retain strict conflict treatment. Source conflicts in recovery are left `null` and logged, not guessed.
* `blend.preview_70_30` is an **uncalibrated diagnostic only** and is present only when both engines are reliable and source-verified. Official ranking remains on validated weights (or A-only) until the chronological holdout gate passes. No learning from unplayed or DNP outcomes.
* `grade.gap_review` explains the 8-point market/model discrepancy and required human checks; the Watchlist ceiling remains until independent market consensus, causal evidence, and manual calibration justify a separately tested rule change. Reviewing an apparent edge is not license to fabricate a tier.
* For morning collection, a task being triggered does **not** establish successful data retrieval/persistence. Check the history archive's manifest and timestamps and verify the Library item's version advanced. A snapshot from yesterday is not proof of a collection today.
