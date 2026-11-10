# NFL 2025 repaired-opportunity chronological replay

This is a retrospective, week-by-week research test of the repaired eight-count
baseline, under rules 1–5, 11–16 of the November 8 directional research contract.
It is **not an untouched season holdout**. `v2/experiment.py` already records
2025 fitting/model-selection exposure, and
`docs/BLIND_HISTORICAL_CAMPAIGN_SCOREBOARD.md` records a completed 2025 pilot
(100 games, 2,616 forecasts). No previously fitted 2025 posterior or NUTS
artifact is used by this replay. Excluding such artifacts cannot undo prior
human/model-development exposure.

## Frozen experiment

`config/experiment_specs/v25_opportunity_2025_chronological.json` defines the
experiment before new-run scores are examined. It preserves the count model
chosen on 2024: appearance-matched player means, role shrinkage and predictive
count variance. The year support is an explicit argument defaulting to 2024;
the old 2024 forecast boundary and replay artifacts remain intact.

There are two parameter controls and three probability methods:

| Control | Count history | Candidate and synthetic line history | Calibration |
|---|---|---|---|
| `expanding` | 2021–2024 plus completed earlier 2025 weeks | Earlier games only | Raw, global, role |
| `frozen_2024` | 2021–2024 only | Same weekly universe as expanding | Raw, global, role |

The common candidate universe is the previous two observed team appearances.
It does not certify current participation or starter status. A synthetic line
is floor(median(last eight prior observed player-market values)) + 0.5. Both
controls see the exact same line. Rookies lacking pre-2025 observations can
receive an expanding forecast after their first observed game; the frozen
control explicitly abstains. Paired comparisons use intersections and report
coverage separately.

Calibration cold-starts from identity in 2025, using only completed earlier
weeks. It retains the existing 80-label minimum and existing regularized
global/role Platt maps. The calibrator is not initialized from a 2025 fit or
from newly tuned historical thresholds. This separates count adaptation from
calibration and from roster/coverage changes.

## Execution and leakage boundary

The orchestrator owns the retrospectively fetched full oracle; child
forecasters receive only whitelisted schedule identity and completed earlier
weeks. No within-week updates occur. Before scoring the current week, the run
saves full sample arrays, exact synthetic contracts, complete calibration
parameters and probabilities. Then it saves exact-team settlement and only
afterward adds observed boxes to the expanding history. Code bytes are frozen
once and every child executes that same copy. Existing run directories and
source files cannot be overwritten by the CLI.

2,048 samples, fixed seed 20261110, 18 regular-season weekly origins and all
272 scheduled games are prescribed. No model/threshold selection occurs during
the run. The rejected joint allocator and yard replacements are not retested
or silently selected into this count experiment. Production consensus and
market columns remain unavailable without original same-contract forecasts
and real offers. There is no production or Tier promotion.

```bash
python scripts/v25_opportunity_2025_replay.py run \
  --prior-source player_stats_2021_2024.json.gz \
  --oracle-source player_stats_2025.json.gz \
  --schedule schedule_2025.json.gz \
  --protocol config/experiment_specs/v25_opportunity_2025_chronological.json \
  --output-dir NEW_IMMUTABLE_2025_RUN

python scripts/v25_opportunity_2025_audit.py \
  --folder NEW_IMMUTABLE_2025_RUN \
  --oracle-source player_stats_2025.json.gz \
  --output NEW_IMMUTABLE_2025_RUN/INDEPENDENT_AUDIT.json
```

## Independent review and interpretation

The separate audit imports no fitting or forecasting code. It checks code and
weekly file hashes, exact source outcomes, prior-only input/line construction,
calibration sample counts/cutoffs, frozen probability arithmetic, sample CRPS,
aggregate scores, missing/push states and identical week-one controls.
Adversarial tests reject current/future history, hidden outcomes, duplicate
schedule identity, changed frozen code and changed report receipts. A saved
canary verifies future-outcome mutations cannot change the forecaster's
sanitized input or frozen prediction.

Report weekly and seasonal Brier/log loss, count CRPS, bias, interval coverage,
Over/Under direction, confidence bins, threshold cohorts and abstentions.
Compare paired game- and week-cluster uncertainty rather than treating props
as independent observations. Absolute CRPS across different stat units must
not be used as a meaningful pooled skill ranking. Late-season changes also
require same-market/role and coverage checks; a smaller selective cohort does
not demonstrate better raw predictions.

These sources were retrieved after the season. Current roster/injury/status
publication times are uncertified. Missing player-game records remain
unmatched, not zero or DNP. Original 2024/2025 data and earlier predictions are
preserved. This test can expose reproducibility, adaptation, confidence and
directional weaknesses; it cannot establish prospective reliability or a
real-market economic edge.
