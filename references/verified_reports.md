# Verified reports and usable baseline results

Automatic feeds are not the only availability path. When a feed is empty, the
researching agent can read an explicit league/team game-day report, a coach
confirmation, or a credentialed beat report, then import that verified evidence.
This is an evidence-entry workflow, not automatic webpage verification.

Generate a template from the actual packet identity:

```bash
python3 scripts/verified_reports.py --packet RUN/research_DATE.json --template --player 'Exact indexed player name' --out RUN/report-input.json
```

Fill the template only after reading the source. Record the actual source URL,
short supporting quote (maximum 25 words), publication and retrieval timestamps
with timezone, source kind (`league`, `team`, `beat`), reviewer, and status
(`active`, `out`, `questionable`, `doubtful`). Set `source_read` true only after
reading the page. The accepted `basis` values are `explicit_game_report`,
`coach_confirmation`, and `official_inactives`. The latter can establish Out,
never Active by omission. Projected lines, generic roster membership and search
snippets cannot establish availability. Identity must match the player ID, sport,
team, game and slate date already in the packet.

An explicit starting announcement additionally supports `starting_confirmed: true`
and `starting_role: goalie` (NHL) or `starting_role: quarterback` (NFL). Use a
quote that supports both status and starting role. These facts apply to that
player, not every goalie or quarterback on the team.

If the source establishes an absence's root event identity and effective time,
include `event_id` and `effective_at`. Do not substitute retrieval time for injury
onset. Conflicting statuses require `conflict_resolution` explaining the actual
source-supported resolution. Previous conflicting evidence is retained.

```bash
python3 scripts/verified_reports.py --packet RUN/research_DATE.json --reports RUN/report-input.json --out RUN/research-reviewed.json
PICKEM_DATA_DIR=RUN python3 scripts/research_packet.py audit --packet RUN/research-reviewed.json --prep RUN/prep.jsonl
```

The importer validates every entry before writing a distinct output file. It
accepts no opportunities, conversion, coefficients, or manual numeric uplifts.
It does not assert completion of adversarial research. Existing stale packet
facts must still be refreshed; importing one report does not refresh other facts.

## Unsupported absence comparisons

The strict joint-roster comparison is now an optional quantitative adjustment,
not a prerequisite for displaying the source baseline. When verified absence
facts lack effective-time metadata or adequate comparison histories, the tool
can retain the unadjusted baseline as **Watchlist only**, subject to all ordinary
availability, weather, market, sample and source checks. The output identifies
`CONTEXT_UNSUPPORTED_BASELINE_ONLY` and never describes its probability as
injury-adjusted. Unknown subject availability still blocks publication. Out,
invalid facts, duplicate effects and numeric injection cannot use this fallback.
No Tier 1/2/3 is awarded for an unsupported material context effect.

When no material event adjustment is needed, verified evidence and historical
sources can produce Tier 2/3 under the existing rules. Tier 1 still requires both
reliable engines and a validated blend. The exact-roster and sample requirements
remain safeguards for the optional numeric allocation; they are not claimed to
be a generally available or validated model of injury effects.

## Historical freshness

Collector-owned completed-game histories remain usable within the same Toronto
evaluation day, at most 24 hours after collection, with checksums, identities and
pregame observation cutoffs intact. Refresh on a new day and whenever a source
correction or newly completed game is known. This does not relax the independent
freshness checks for prices, status, lineups or weather.
