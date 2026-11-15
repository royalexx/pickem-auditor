# WS3 weather fallback v1 — research only

This separately registered challenger implements the authorized unchanged-control
option when credible fitted weather coefficients are unavailable. It is **not**
WEATHER_ESTIMATED, a weather scenario, or evidence of forecast improvement.
The existing models.py/native_ws1.py and O1–O5 parameters are unchanged.

## Behavior

Run weather_run with the canonical WS1 handoff and the actual shared history
manifest path/hash. It verifies original source bytes through native_ws1.consume,
loads the existing history interchange, and binds every exact contract to the
canonical candidate ID, sportsbook, quote, market, period, line, player crosswalk
and kickoff. It freezes the neutral control first. Optional weather failures cannot
prevent that neutral output. Both neutral and weather writes check actual completion
time against kickoff. Past events must be excluded by the source-owned packet before
loading; this runner does not reconstruct pregame records for them.

weather.py validates optional WS1 weather sources and registers O1-W through O5-W
with full SHA-256 suffixes over parameters and dependencies. Each weather row is an
exact deep copy of the just-generated control distribution, retaining conditioning,
MC standard error and abstentions. Paired forecast means, variances and all three
probabilities have zero deltas; unavailable forecast cells are null. O1 remains a
team-only distribution; no fictitious O1 player prediction is introduced. Team
distribution comparisons are in team_opportunities; contract comparisons are in
paired_contract_table. Unallocated player opportunities remain in the existing
residual pool. The same role weights and corrected mean-preserving starter share
apply. Defender marginals retain pooled per-snap involvement, all three official
tackle components, and their disclosed lack of joint tackle accounting.

No volume, allocation, efficiency, defender-involvement or role-transition weather
response is applied. This avoids double counting and unsupported assumptions about
wind or QB rushing. An indoor/closed-roof exposure is sheltered; an unknown
retractable roof remains unknown. Even exposed stadiums use the unchanged fallback
until an actual fitted model has been separately implemented and validated.

Counts distinguish unchanged fallback forecasts from weather-estimated forecasts
(always zero here). These copies are matched controls, not independent predictions
or additional evidence. No source collection, production changes or market-edge
inference occurs.

## Proposed WS1 weather interchange — producer not yet observed

The adapter contract is a proposal, not a claim about an existing WS1 schema. A new
producer schema must be explicitly adapted and tested; it must not be guessed.
Pass the actual WEATHER_FEATURE_PIN path and its externally pinned SHA-256 using
--weather-pin and --weather-sha256. No weather source is independently fetched.

The JSON object has exactly these fields:

- schema: ws1-nfl-pregame-weather-v1
- producer_workstream: 1; source_certified: true; day: 2026-11-15
- input_freeze_at: timezone-aware receipt cutoff
- sources: original source descriptors with source_id, project-relative path
  (relative to this manifest), SHA-256, original/source_certified flags,
  issued_at and retrieved_at. All original bytes must be present.
- events: rows with game_id, event_start, source_id, issued_at, retrieved_at,
  valid_at (exact kickoff), kind (forecast), venue (indoor/outdoor/retractable),
  roof_status (open/closed/none/unknown), wind, gust (nullable), wind_unit
  (m/s, km/h or mph), temperature, temperature_unit (C or F), precipitation_type
  (none/rain/snow/freezing_rain/sleet/mixed/unknown), precipitation_intensity,
  precipitation_unit (mm/h).

Rows preserve original units and retrieval clocks alongside normalized SI values.
Issued <= retrieved <= weather freeze <= forecast < kickoff is required. Observed
or postgame weather is forbidden. Missing per-game weather uses a labeled fallback.
Unsupported schema, hashes, units or clocks reject the optional packet and record
the error without modifying the neutral forecast.

The shared history manifest keeps ws1-nfl-pregame-opportunity-v1 and additionally
must bind canonical_source_manifest_sha256 to the canonical WS1 manifest hash.
Existing source-owned candidate IDs must be used as contract_id; player IDs use the
source-owned nflverse crosswalk where available. No fabricated participation values
are inserted to bypass the current neutral model's gates. This preserves its current
abstentions; adding a conditional-only neutral variant remains separate work.

## Historical fitting evidence and next fitting gate

As of this implementation there are **zero inspected legitimate historical weather
training rows**, zero weather fits and zero grouped-validation scores. The visible
Deepnote inventory contains neither the shared Nov15 history packet nor a weather
pin. No coefficients, hyperparameters, sample sizes or fit timestamps are invented.
PARAMETERS is a frozen absence-of-fit/fallback policy; zero effects are not estimated
regression coefficients. The registry rejects any changed parameter object.

Before a nonzero fitted version is implemented, require original prior-game
opportunities, pregame forecast-vintage weather, venue/roof evidence available then,
and valid source clocks linked by exact game ID. Never use final roof status or
target-game observed weather. Freeze the candidate design and chronological folds
before seeing Sunday outcomes. Investigate sustained wind/gust, temperature,
precipitation intensity/type, freezing/snow, exposure and interactions with prior
passing tendencies. Fit regularized changes in team volume and pass/run/sack
allocation against matched neutral controls using earlier games only; group both
teams and all players by game and week, and validate on subsequent weeks. Report
sample coverage, out-of-support weather, coefficient uncertainty and group-level
held-out scores. Do not describe an estimated model as improved until those matched
scores support it. Sufficient coverage/regularization choices must be preregistered
against the delivered dataset, not retro-selected from Sunday outcomes.

Allocation, catch/yardage, defender involvement and role-transition effects need
their own historical evidence and validation. Otherwise a future estimated O1-W
may propagate once through the existing allocation and conversion pipeline while
those conditional parameters remain frozen. That nonzero propagation and fitting
path is deliberately **not implemented or enabled in fallback v1**.

## Execution

    python -m research.nfl_opportunity_20261115.weather_run \
      --history-manifest ACTUAL_WS1_MANIFEST --history-sha256 ACTUAL_SHA256 \
      --weather-pin ACTUAL_WEATHER_FEATURE_PIN --weather-sha256 ACTUAL_SHA256

Default draw count is 8192. Without a delivered history manifest, the runner only
verifies canonical sources and emits a blocker with native abstentions; it does not
claim a real contract integration or forecast ledger. weather_run is separate from
the original WS3 notebook so its development cannot delay neutral activation.

    python -m unittest research.nfl_opportunity_20261115.test_models \
      research.nfl_opportunity_20261115.test_weather -v

All fixtures are explicitly synthetic. They cannot establish fitted weather effects,
authentic Sunday contract coverage, or prospective predictive validity.
