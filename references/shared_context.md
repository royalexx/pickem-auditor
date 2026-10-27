# Source baselines and one shared event layer

Current ownership: A (`history-v5`) uses historical production; B (`scouting-v7`)
uses historical usage and production rates. Upcoming injuries, absences and event
effects do not belong in either baseline. The current context operator is `shared-context-v4`. The shared layer transforms the blended
predictive distribution once. Transforming each mixture component with the same
operator and then summing is mathematically the same operation; do not multiply a
win probability by an injury factor.

## Eliminate researcher-entered baseline adjustments

The collector retains the source game observations used for production and workload.
`commit_slate` writes identity-scoped records to `data/usage/` and adds an opaque
`historical_usage` reference to the scouting seed. B reads that fixed collector
location, verifies player/team/stat/date and freshness, rejects duplicate/future
games and computes recent-five workload times pooled production per workload.
Zero-workload source observations remain in the usage window; they do not become
conversion-rate divisions by zero. Conversion still requires positive-exposure
support. NBA workload is minutes, NHL is ice minutes, NFL uses the supplied offensive or
defensive snaps. No researcher opportunities, conversion, scenario weights or injury
narrative can change this path. A's inputs and distribution are checked by
recomputing the collector's historical summary from those same observations.

Both forecasts retain approximate sampling uncertainty. B uses paired historical
game rates, workload variation and a nonzero uncertainty floor. Fewer than ten dated
usable games cannot be reliable; fewer than five produces abstention. Normal
predictive negative mass blocks reliability. These are provisional policy checks,
not a validated prediction model. Old free-scalar and typed research scenarios are
diagnostic only, even when their checklists are complete. Source-unverified A cannot
produce Tier 1/2/3. Unknown date/workload remains unavailable, not guessed.

`PICKEM_DATA_DIR` can configure the runtime data directory when a custom slate
directory is used. It is an operator setting, not a research packet path.
Source data, cache files and import permissions must be controlled operationally;
this is not protection against someone deliberately falsifying raw observations or
modifying the program. It removes the ordinary researcher numeric-adjustment path.

## Subject availability and teammate redistribution

Place `event_context` inside the matching scouting packet. Its only accepted keys
are `subject_status` and `events`. Statuses are fresh confirmed fact objects. A
subject confirmed Out has null contextual probabilities and is ineligible; do not
publish a nonappearance as an under win. Questionable/doubtful status is unresolved.

Each event has `player_id`, `availability` (confirmed Out fact with root `event_id`
or structured `causal_event`), and timezone-aware `effective_at`. Packet integration
also routes confirmed teammate absences with stable IDs. The fact needs an effective
time and root identity; unknown metadata blocks context. A new event must follow
the baseline cutoff. An existing injury already present in the history requires a
clean rebuilt baseline; do not apply the same cause again.

The researcher cannot submit an uplift coefficient, change opportunities, or raise
conversion. `shared_context.py` derives the allocation from source game observations
with complete active rosters. Multiple current absences form one joint state; it
does not multiply independent on/off bonuses. Require at least ten complete games
with all declared teammates present and ten with all absent. Other active comparison
players must match exactly. Different unmodeled rosters block the adjustment.

The observed absent-state production shares are normalized across the eligible
roster, preserving one team resource total. The target absent-state share replaces each component's allocation against its own source-period team budget. Source games must cover
both engines and agree on the player's recorded production. A baseline that has
already absorbed an absence does not receive the full present-to-absent bonus again.
A uses its capped historical observation weights for the team budget; B uses its
recent source-game team budget. Apply the allocation once to both predictive components,
propagate comparison uncertainty, and combine with the same validated weights.
There is no second efficiency/stock bonus. This is an observational association;
opponent, scheme, role and schedule confounding remain. Sparse/unsupported context
is unresolved. No Tier 1 is allowed after an unvalidated context transformation.

## Team source history format

Import explicit source data with:

```bash
python3 scripts/shared_context.py --import-history /path/to/verified_team_history.json
```

The input object has `sport`, `team`, `stat`, and `games`. Each game has `id`, ISO
`date`, public `source_url`, `roster_complete: true`, `active_players` (stable IDs),
`production` (player ID to the selected stat's value), and `team_total`. Player
production must sum to that total. Include active zero-production players; missing
players in a partial table are not confirmed absences. For tackle+assist totals,
deduplicate each player's credit per play; the team credit budget can exceed team
plays because different players can receive credits. Do not use team plays as that
credit total. Solo tackles and combined credits are separate stats.

This importer is a source-adapter boundary, not autonomous collection or verification
of arbitrary webpages. Full roster and tracking adapters are not all implemented.
NFL raw PBP does not itself establish every inactive/active roster member. Use
verified complete box scores/participation and tracking where needed.

Optional per-game `features` maps named metrics to entity/count mappings. Supported
names are `three_point_attempts`, `drives`, `passes_to`, `targets`, `first_read_targets`,
`checkdown_targets`, `designed_targets`, `defensive_snaps`, `ice_time`, `shot_attempts`,
`tackle_opportunities`, `potential_assists`, and `rebound_chances`. Passing-edge
entity IDs may be `passer>recipient`. Only features and entities present throughout
both cohorts produce observed with/without averages and deltas. No observation
means no inferred first read, pass edge, drive, coverage shell, alignment or attempt.

These deltas explain the single joint allocation; they are not additional numeric
effects. Thus extra 3PT attempts, passes to a shooter and drives can describe one
teammate absence without tripling its projection uplift. The same applies to a
linebacker's increased defensive involvement or an NHL player's deployment/shots.

## Validation boundary

No current blend or context accuracy certificate is shipped. The weekly fitter
scores current source-only pregame A/B forecasts with joint win/push/loss log loss.
It excludes older engines, missing pregame timestamps and context-adjusted rows.
Context forecasts need their own prospective validation before Tier 1 eligibility.
Do not backfill postgame histories as if they were pregame forecasts.


## Automatic collection and prospective validation

`lineup_feeds.py` collects final regular-season NBA ESPN box scores and NHL official
box scores. It validates all participant rows and team totals, normalizes team codes,
filters future/preseason games, caches completed older games, refreshes recent games
and retains the previous complete history if a new collection is incomplete.
Counting box scores supply 3PT attempts and ice time where explicit; they do not
invent drives, pass edges, routes, coverage or alignment. ESPN's `active` flag is not
a participation indicator. Played bench players are included. Explicit coach-decision
DNPs are available zero-production participants, not inferred injured absences.

```bash
python3 scripts/lineup_feeds.py --sport NBA --team UTA --stat threes --date YYYY-MM-DD
python3 scripts/lineup_feeds.py --sport NHL --team CHI --stat 'shots on goal' --date YYYY-MM-DD
python3 scripts/research_packet.py audit --packet data/research_DATE.json --prep /tmp/prep.jsonl --collect-lineups
python3 scripts/context_validation.py --snapshots data/prop_snapshots.jsonl
```

An audit is offline by default; `--collect-lineups` explicitly enables the live
collection pass for needed teammate-absence candidates. Shadow jobs perform that
pass automatically. Collection errors are reported and never turn missing players
into absent players. NFL requires a complete active roster plus an ESPN/GSIS ID map;
the tested ESPN summary lacks that roster and the automatic path reports unsupported.
A verified complete NFL history can still use the import interface. Detailed tracking
remains an explicit source-data requirement, not an implemented free-data collector.

Runtime data directories are scoped to the packet/slate, including custom paths.
Collector snapshots are content-addressed and retained; a mutable cache checksum is
verified on read. Forecast diagnostics record the history digest. Source timestamps
use Toronto calendar dates, including UTC-midnight crossings. A's IDs and historical
values are both verified; future prior rows cannot pass the check. NFL prior workload
cannot borrow current-season snaps for an identically numbered week.

Weekly jobs now evaluate the fixed context operator separately from the baseline
blend. Context evaluation uses chronological earlier/later periods, the actual earliest
pregame forecast timestamp, joint win/push/loss log loss, date-cluster uncertainty,
and a deployed-blend fingerprint. It does not fit another prediction model. A current
matching holdout improvement certificate can remove the context-specific Tier 1 cap;
all original engine/blend/research gates still apply. No such certificate is shipped.
New engine/context versions invalidate older evidence. Missing evidence remains
underpowered, not silently approved.

Settlement now requires the correct completed NFL game/week, preserves solo-versus-
combined tackle meaning, checks participation for NBA/NHL and uses local NBA dates.
A DNP or unknown participation remains unsettled; it is not an under win. Predictions
and outcomes must accumulate prospectively before any accuracy claim is justified.


Validated baseline deployments are retained with a stable fingerprint so their
prospective context cohort can accumulate. Explicitly version/retire a deployed
configuration before replacing it. A context certificate is scoped to the actual
deployed fingerprint; older A-only or other-weight observations do not validate a
new mixture. Weekly status distinguishes retained deployments from underpowered
new scopes. Relative holdout improvement is evidence of usefulness, not proof of
absolute probability calibration or future profitability.

Live collection also uses ESPN team season schedules: the tested scoreboard
range endpoint rejects multi-day ranges. NHL uses the official club schedule.
NFL's tested summary and core roster endpoints do not supply the required complete
active roster. That missing-source condition remains explicit rather than becoming
an invented inactive-player list.

### Verified NFL game-active roster import

When the live summary has no complete roster, import a separately verified manifest.
Use game-specific active rosters, not season membership, weekly practice status or
positive snap/stat rows. The importer checks identity, uniqueness and source metadata;
the operator must verify that the cited source actually establishes all active players.
Use ESPN event IDs and GSIS player IDs:

```json
{"version":"nfl-active-rosters-v1","games":[{
  "event_id":"401000001","game_id":"2026_04_CHI_NYG","team":"CHI","date":"2026-10-01",
  "source_url":"https://www.nfl.com/REPLACE_WITH_ACTUAL_GAME_ROSTER",
  "roster_complete":true,"active_players":["00-0000001","00-0000002"]
}]}
```

This is a schema example, not real data. Supply every active player and the actual
source URL. Never import the example as evidence. `--active-rosters` validates and
installs the complete manifest into the configured data directory:

```bash
python3 scripts/lineup_feeds.py --sport NFL --team CHI --stat 'tackles + assists' --date 2026-10-26 --active-rosters /path/to/verified_rosters.json
```

The ID bridge still comes from nflreadpy, or `--id-map` with verified ESPN-to-GSIS
mapping. Subsequent packet/job collection reads the installed manifest automatically.
Importing a manifest replaces it in full; retain the earlier game rows when extending
coverage. Each game/team/date must match its box score. Known active zero-stat players
are retained; unmapped or inconsistent participants block collection. Roster provenance
is retained separately from the box-score URL. The automatic full-roster source is
still unavailable; this import removes the runtime dead end without guessing rosters.

Provide the verified nflverse `game_id` alongside the ESPN `event_id` for shared
context. The lineup history uses that canonical game ID to join Engine A/B source
observations; it retains the ESPN ID separately as `source_event_id`. An older
manifest without `game_id` remains importable for collection diagnostics but cannot
establish this cross-provider context join. Changed roster/game mappings refresh
cached observations. Weekly stats now receive sourced game dates and IDs for both
current and prior seasons, rather than storing a numeric week as if it were a date.

NHL collection accepts the slate's canonical `goalie saves` stat and collects every
season touched by the requested lookback. Feed-v2 cache stamps prevent reuse of older
collector rows after these repairs. Lookback/game limits and cohort support gates
still apply; successful collection alone does not establish a reliable projection.

Usage cache keys and lineup paths canonicalize market aliases just as the pipeline
does (`goalie saves` becomes `saves`). Refresh collector usage data after upgrading;
previous goalie references must not be reused as if they were current snapshots.

Unsupported comparison data can expose the unchanged source baseline as Watchlist only; see `verified_reports.md`. This does not authorize a numeric adjustment or bypass availability checks.
