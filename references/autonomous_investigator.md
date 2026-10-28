# Autonomous research investigator — source-provenance contract

The bounded investigator in scripts/autonomous_investigator.py runs automatically
after the afternoon research triage and again before eligible games, via
.github/workflows/pickem-daily.yml and pregame-verification.yml.

## What is autonomous

- Selects no more than 10 afternoon subjects, or 30 in a recheck, using the
  *same original forecast* and priority-queue identity/time checks used by
  the verifier. It will not investigate or approve already-started games.
- Uses the existing ESPN scoreboard, game summary, injury and goalie resolver
  for official, game-specific pregame status and venue information. No
  "not on the injury report = active" inference.
- Independently downloads the NHL player game-log endpoint or the ESPN NBA
  athlete game-log endpoint. Each response has its exact HTTPS source URL,
  retrieval time, SHA-256 of the provider JSON and league game IDs. Stat
  values are parsed using the project’s tested sport-specific parsers,
  restricted to completed games prior to the slate date. A negative value,
  duplicate game ID, malformed date or game on/after the slate is rejected.
- Counts both historical winning and losing outcomes against the *exact*
  candidate side and reference line; distinguishes pushes and stores actual
  source game IDs and the observed numeric values. These are descriptive
  past results **not estimated current win probabilities**.
- When the collector-owned history cache is available, validates its
  content hash and player/team/stat/date identity and independently compares
  individual game IDs/values to the separately requested league feed.
  Conflicts are retained as blockers; insufficient overlap is not described
  as successful corroboration.
- Searches a bounded ESPN sport-news feed once per relevant sport and finds
  exact full-name matches in the provider's headline or description. Saves
  only a short verbatim excerpt, direct ESPN story URL, original article
  publication timestamp and source-field path. These are *investigation
  leads*, not verified qualitative claims, current injuries, or a
  reviewer-read report.
- Deduplicates player history requests across stat/side candidates and
  records each attempted URL, result/exception and retrieved timestamp.
- Issues zero PropLine requests. Existing market collection and quote guards
  remain independent.

## Outputs

The workflow writes reports/autonomous_investigation.json. The current
research packet gains a distinct _autonomous_investigation sidecar, used for
verifier diagnostics and source provenance. The independent snapshot remains
untouched. reports/pick_verification.json includes digest-matched summaries
of the source, historically supporting/opposing game counts, and ESPN
article mentions.

Statuses are partial_source_research or source_research_blocked. A retrieved
response *never* sets source_read_by_human, research_attested,
promotion_authorized, publication_eligible or research_complete to true.

Stat-specific qualitative checks left missing after the machine pass include
line assignments, opponent schemes and positional funnel effects, injury
redistribution, matchup-specific script, and scenario frequencies unless
separate authoritative evidence really supports them. NHL and NBA player
history can be independently checked. NFL player IDs are not assumed to be
ESPN athlete IDs; without an identity-resolved official event history,
NFL standalone player game-log research abstains rather than making a
cross-provider identity guess.

The downstream Tier rules, historical forecast fields, original Engine A
and B outputs, 70/30 diagnostic weights and calibration thresholds are
unchanged. A real reviewer may use the dossier to complete the separate
sourced game-day/scouting reviews, with mandatory supporting and
counterevidence. Automated source collection alone never fabricates a
reviewer's signature or grants a pick.

## Local and CI tests

    python -m unittest discover -s tests -p test_autonomous_investigator.py -v
    python -m unittest discover -s tests -p test_pick_verification.py -v

GitHub CI also validates these within the full existing unit test suite.

Run only against *today's pregame* data; the CLI checks the Toronto slate
date and refuses to backfill picks after a game starts:

    python scripts/autonomous_investigator.py --date YYYY-MM-DD \
        --phase initial --limit 10 \
        --queue reports/research_triage.json \
        --snapshots data/prop_snapshots.jsonl \
        --packet data/research_YYYY-MM-DD.json \
        --data-root data --out reports/autonomous_investigation.json

Pregame GitHub Actions automatically uses its saved current research packet,
phase recheck, limit 30 and the fixture-specific 25–55 minute window.
