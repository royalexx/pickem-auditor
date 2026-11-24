# NFL projected-starter research runners

Governing plan `PA-V25-MASTER-2026-11-09 / v1.1`. This Phase 0R/Phase 1
research path separates source acquisition and postgame validation from
pregame inference. It follows the NHL daily separation between immutable
forecasts and an independent final-stat consumer. The legacy multisport path
and frozen 60/40 policy remain available.

| Owner | Operation | Output |
|---|---|---|
| Collection and validation | Collect NFL history, dated ESPN fixtures, team depth charts, the ESPN–GSIS bridge and an existing quote batch | SHA-addressed source and input receipt |
| Forecast | Read the pinned capture offline, admit supported first-listed depth-chart slots and evaluate their original priced contracts using existing models | Immutable research forecasts and row-level abstentions |
| Collection and validation | Read the exact committed forecast batch, capture an ESPN final for each eligible event, and verify fixture, player and stat before grading | Separate SHA-addressed validation receipt |

Depth-chart starters are projections. Inclusion requires an unambiguous
first-listed player in a supported primary offense or defense slot, matching
team, ESPN/GSIS player, game and current quote. An empty, conflicting or
unsupported slot provides no starter evidence. A season roster, a backup's
prop offer or prior starts provide no eligibility. An explicit inactive or
out designation on the depth row vetoes that slot. The original depth bytes
and possession time are retained. Depth-chart information establishes neither
official game-day activity nor verified participation.

## Manual invocation

Use a separate evidence directory and the Toronto date of a future NFL slate.
The collector can reuse a recent original quote JSONL. A fresh provider fetch
requires both explicit `--live-odds` and the existing
`PICKEM_ODDS_QUOTA_GUARD=1`. Only the collection runner can request it. A missing
or closed schedule avoids odds and history calls.

```bash
python scripts/nfl_research_sources.py --root "$NFL_RESEARCH_ROOT" collect \
  --date "$NFL_SLATE_DATE" --quotes-file "$NFL_ORIGINAL_QUOTES"
PICKEM_PRODUCTION_CONSENSUS=1 python scripts/nfl_projected_starters_forecast.py \
  --root "$NFL_RESEARCH_ROOT" --capture-sha256 "$NFL_CAPTURE_SHA256"
python scripts/nfl_research_sources.py --root "$NFL_RESEARCH_ROOT" validate \
  --forecasts-sha256 "$NFL_FORECAST_SHA256"
```

Pass the printed capture SHA-256 to the forecast runner and the printed
forecast SHA-256 to the validation runner. The forecast runner checks the
capture and model-input hashes and freshness, then uses existing local
Engine A/B evaluation. With the benchmark flag enabled it uses the existing
frozen policy. The runner refuses certified-only mode. The same capture
returns the same committed batch on retry. The commit clock is checked after
forecast bytes are written and verified. Rows that cross their kickoff
during that write retain an abstention in the report.

Validation grades the original line and side once an exact completed ESPN
event and an explicit player statistic are present. Missing/DNP player stats,
pending finals, reschedules, conflicting IDs and unsupported stats remain
unresolved. Combined tackles remain unresolved pending verified equivalence
to the repository's three-component stat policy. The forecast inputs, IDs
and prediction bytes remain intact. The validator can run again once results
become available. Its receipt identifies the final source SHA and all
unresolved rows. This workflow does not certify settlement of sportsbook
product terms.

Both commands are unscheduled. Rollback is to leave these optional commands
unused or revert their isolated change while retaining existing receipts.
Before any operational cutover, run one genuine authorized pregame-to-final
cycle and verify the source bytes, clocks and IDs. Publication and Tier
promotion require the existing governing approvals.
