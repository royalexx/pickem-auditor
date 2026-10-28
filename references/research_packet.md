# Research packet

One JSON file per slate: `data/research_<date>.json`. Fill it from feed output plus targeted web research. Run validation before merge.

```bash
python3 scripts/research_packet.py validate data/research_<date>.json
python3 scripts/research_packet.py to-pipeline --packet data/research_<date>.json --prep data/prep_<date>.jsonl
```

## Fact shape

Every cited value is a fact object (or `null` when not found):

```json
{
  "fact": "short label",
  "value": "<typed payload>",
  "source_url": "https://example.com/page",
  "source_name": "Human-readable source",
  "retrieved_at": "2026-10-22T16:00:00Z",
  "quote": "Up to 25 words copied from the page",
  "confidence": "confirmed"
}
```

`confidence` is `confirmed`, `reported`, or `inferred`. Quotes over 25 words fail validation. URLs whose host contains `underdog` are rejected.

Availability, lineup, weather, environment, and player-context facts must be retrieved within the last 60 minutes at validation time. Generic spread/rest environment facts describe the home team; away-team spread is negated when only the home spread is available, and home rest flags never substitute for missing away rest facts.

## Template

```json
{
  "date": "2026-10-22",
  "index": {
    "by_player": {
      "Example Player": {
        "team": "BOS",
        "game": "BOS@NSH",
        "sport": "NHL"
      }
    }
  },
  "availability": {
    "Example Player": {
      "status": null,
      "primary_source": null
    }
  },
  "lineup": {
    "BOS": {
      "projected_lines": null,
      "pairs": null,
      "pp1": null,
      "goalie_confirmed": null
    }
  },
  "weather": {
    "BOS@NSH": {
      "sustained_wind_mph": null,
      "gust_mph": null,
      "precip_prob": null,
      "precip_intensity": null,
      "window": null,
      "indoor": null
    }
  },
  "environment": {
    "BOS@NSH": {
      "spread": null,
      "total": null,
      "back_to_back": null,
      "rest_days": null
    }
  },
  "mechanisms": {
    "NHL|Example Player|shots on goal|over": []
  },
  "role_changes": {},
  "player_context": {
    "Example Player": {
      "ice_time_tonight": null,
      "role": null
    }
  }
}
```

`index.by_player` links prep row ids (`sport|player|stat|side`) to `team` and `game` keys. Optional `player_context` holds per-player Stage G workload facts (`minutes_tonight`, `ice_time_tonight`, `snap_pct_tonight`, `route_pct_tonight`, `is_starter`, `expected_starting_qb`, `role`, `outdoor`, `snow`, etc.) when feeds do not supply them.

## Sections

| Section | Keys | Notes |
|---|---|---|
| `availability[player]` | `status` (`out` / `doubtful` / `questionable` / `active`), `primary_source` (`league` / `team` / `beat`) | |
| `lineup[team]` | `projected_lines`, `pairs`, `pp1`, `goalie_confirmed` | |
| `weather[game]` | `sustained_wind_mph`, `gust_mph`, `precip_prob`, `precip_intensity`, `window`, `indoor` | Outdoor NFL/NHL only; indoor games use `indoor: true` |
| `environment[game]` | `spread`, `total`, `back_to_back`, `rest_days` | |
| `mechanisms[player_stat_side]` | list of `{description, sources[], type, supports_side}` | `type`: workload, scheme, role, weather, pace; one DISTINCT causal event per mechanism; multiple sources per event are welcome |
| `role_changes[player]` | `confirmed_by_primary_source`, `old_role_n`, `new_role_n` | Primary confirmation needs a league or team domain URL |

Mechanism id matches prep: `sport|player|stat|side`.

The per-row `mechanisms` count is a legacy diagnostic only. It cannot authorize publication. Verified decisions use [causal evidence-quality grading](mechanism_quality.md). Human-reported causal mechanisms can carry structured `causal_validation` with same-event before/after facts, sample sizes, independent sources and sourced counterevidence.


## Search query shapes (Stage C)

Use these as plain query strings (substitute team, opponent, player, date, stadium, city):

- `"[Team] injury report [date]"` and `"[Team] starting lineup [date]"`
- `"[Opponent] injury report [date]"` and `"[Opponent] starting lineup [date]"`
- `"[Out player] out [date]"` for every Out, Doubtful, or returning player on either team
- Outdoor weather (US): `"[Stadium] weather [date] kickoff wind"` and `"NWS [city] hourly forecast [date]"` (non-US: that country's national meteorological service)
- `"[Away] [Home] spread total [date]"`
- NFL scheme: `"[Team] pass rate over expected"`, `"two-high safety rate [Opponent]"`, `"[Coach] offensive tendencies"`
- NBA scheme: `"[Team] pace possessions"`, `"[Opponent] drop coverage"`, `"[Coach] rotation minutes"`
- NHL scheme: `"[Opponent] shots against per 60"`, `"[Team] PP1"`, `"[Goalie] confirmed starter"`
- Rest: `"[Team] back to back"` or `"[Team] short week"`

## How to fill

1. Copy the template to `data/research_<date>.json` and set `date`.
2. After `fetch_slate.py` and `prep`, fill `index.by_player` for every shortlisted player.
3. Slate pass: league injury reports, schedule, one odds board for spreads/totals, outdoor weather from official forecasts.
4. Team pass: scheme cluster per team (not per player).
5. Player pass: mechanisms and role changes for serious candidates only.
6. Write `null` for any required fact you cannot find; do not invent numbers.
7. Run `validate`. Fix every reported path until exit 0.
8. Run `to-pipeline` and pipe the JSONL into `pickem_math.py pipeline --batch --stdin`.

`to-pipeline` copies only validated facts into pipeline context fields, sets `mechanisms` to the count of distinct causal mechanisms supporting that side, sets `role_change` when primary-confirmed, bumps `soft_flags` for questionable players/teammates, and sets `data_veto` when an outdoor game lacks weather facts. It never guesses missing values.

## Validated event mechanisms, identity and role windows

An optional stable `event_id` identifies the underlying causal event. Multiple articles on the same injury/role switch belong in **one mechanism** with several sources. A single article supporting two independently described events is allowed. If there is no `event_id`, identical normalized `type` + `description` deduplicates conservatively. Distinctness of two differently described but correlated events still requires adversarial human review. A nonempty description and at least one valid source are required. URLs must be public absolute HTTP(S) links; structural validation **cannot prove** that a page actually supports the claim — check the page, date, player, stat and game manually.

`index.by_player_id` can optionally key `sport|player_id` to team, game, event_id and sport; the merge prefers this to name-only `index.by_player`. Where a prep team, sport or event conflicts with the resolved context identity, the row is blocked (not assigned another player's injury). Keep `availability` identity consistent with the index.

Role-change sample-count facts NEVER overwrite `baseline_n` or `recent_n`; those statistics must be recomputed together from non-overlapping game logs. Inconsistent/missing windows receive `ROLE_WINDOWS_NOT_RECOMPUTED` and a data veto. `out` produces a hard veto; unknown availability a data veto; questionable/doubtful adds a soft flag. Indoor/outdoor classification must be known for weather-sensitive markets; outdoor forecast facts require a full window, sustained wind, gust, chance, and intensity. Unavailable data is not interpreted as benign.

For shortlist-based gap queries, save the JSON output of Stage D `scan` and call `research_packet.py gaps --packet PATH --scan STAGE_D_SCAN.json`. Do not use the complete prepared slate to expand your research workload.

## Current scouting integration

`scouting` is keyed by the exact prep ID (`SPORT|Player|stat|side`). Each entry has:

- `evidence`: four fact objects named `matchup`, `opportunity`, `injuries`, `game_script`.
  Each requires `fact`, `value`, source URL, retrieval time, and confirmed confidence.
  All four must be fresh within 60 minutes. A source can be neutral; unknown remains null.
- `scenarios`: at least two justified estimates covering the full game. Each has
  `scope: "full_game"`, `weight`, `opportunities`, `conversion`, `dist`, `rationale`,
  and `sd` for Normal or `var_ratio` for negative binomial. Weights sum to one.
  These are research judgments supported by the cited evidence, not observed facts.

A scenario with 8 targets and 0.65 receptions per target has mean 5.2 receptions.
For yards, conversion is yards per target. Choose opportunities and conversion in
compatible units. Never use a partial read-bucket mean as a full-game estimate.

Run the complete offline merge/evaluation step:

```bash
python3 scripts/research_packet.py audit --packet data/research_DATE.json --prep /tmp/prep.jsonl
```

This command validates first, merges the packet into the matching candidates, and
returns pipeline JSONL to stdout. It does not fabricate research, automatically
attest to the checklist, or save a board. `gaps --scan` includes missing scouting
requirements. The scheduled shadow job also consumes the packet produced by its
fetch. Missing packets yield explicitly unranked shadow forecasts; invalid packets
stop that job. Packets from different dates cannot carry research forward.

The collector can prefill publicly available structured facts. Matchup interpretation
and scenario construction still require a research pass. Automatic integration is
implemented; autonomous factual verification of arbitrary webpages is not.

## Advanced supporting statistics

Read `references/advanced_scouting.md`. `scouting_checklist.py` creates per-sport,
per-stat requirements in `supporting_stats`. Fill each category with a sourced fact
object, or leave it null. The collector seeds these categories and forwards existing
feed diagnostics as unverified hints. Missing categories appear in the gap report.

Each scenario must also include `drivers`, a nonempty list of sourced supporting-stat
category names. These identify which observations justify that scenario. No missing
advanced category can be silently called neutral; incomplete coverage makes B
unreliable and prevents Tier 1 and use of validated B weights. A newly stricter B
contract changes the version to `scouting-v4`; earlier B records cannot validate it.


Version 4: use `numeric_inputs`, sourced `scenario_weight_evidence`, and executable
`adjustments` as defined in `math_helper.md`. Free-scalar scenarios still evaluate
for diagnostics but cannot qualify as reliable. `gaps` reuses the B evaluator to
report stale facts, incompatible stat/mode selections, numerical conflicts, missing
provenance and insufficient samples. Supply `--prep` for exact candidate identities
and lines when available. Static venue hints leave indoor/roof confirmation null;
verify the actual game venue from a public source. Refreshing a seed never attests
to advanced-stat research or measured uncertainty on your behalf.


The subsequent shared-context change supersedes scenario eligibility above.
Read `shared_context.md`. The collector now attaches `historical_usage` references.
Do not replace this with a numeric scenario. `scouting[ID].event_context` accepts
sourced statuses/events; the packet merger also routes confirmed teammate absences
with stable IDs to the shared layer. Absence facts need a root event identity and
`effective_at`; otherwise context remains unresolved. Availability Out for the
subject nulls eligibility. Complete lineup history is a separate source import;
the research packet cannot inject an uplift factor or a replacement history path.
