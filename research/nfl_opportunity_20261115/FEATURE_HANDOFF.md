# Corrected WS1 feature handoff audit — November 15, 2026

Status: implemented and locally tested; scientific weather fitting remains blocked
pending the original-byte audit receipt. Research only under
PA-V25-MASTER-2026-11-09 / v1.1. No production or neutral parameter changes.

`feature_handoff_audit.audit(project_root)` consumes the immutable native
FORECAST_FEATURE_PIN, pinned to SHA-256
`35a1bf7fe16acca1e115c7be7bcad2c2464ec27cdf7e799df4f2b31adba24c2a`.
The original source SHA remains
`5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71`.

The producer's `ws1-nfl-pregame-opportunity-v1` table is JSONL containing
per-contract priors. It is **not** the proposed five-table JSON-array interchange
accepted by models.load_packet, despite reusing that schema name. This audit is
an explicit native-schema consumer, not a conversion into fabricated model inputs.
It verifies original sources through native_ws1, all historical archive files,
newly collected WS1 source bytes, each table hash/row count, full candidate-ID
coverage, exact quote identity, event/team/kickoff matching and cutoff clocks.
Every source reject and expired event stays in the contract denominator.

Inspected native rows have null participation probabilities, team plays and sacks;
the historical archive explicitly disclaims original pregame availability. These
are not weather estimates and cannot be repaired by adding a wind multiplier.
The audit records null component effects (volume/allocation/efficiency/role), null
validation scores, zero fitted coefficients and zero matched forecast pairs. It
refuses to classify a potentially viable contract without a separate model adapter.
It does not invoke or block the existing neutral runner.

An absent WEATHER_FEATURE_PIN and retrospective schedule wind/temperature columns
cannot establish original forecast-vintage weather. WS1 must deliver immutable
point-in-time weather, exposure and opportunity evidence. No independent weather
collection is authorized. Estimation and validation requirements remain in WEATHER.md:
chronological game/week grouped matched folds, shrinkage, parameter uncertainty,
proper scores and coverage by exposure. No fold is scored with missing predictions;
missing scores are null rather than zero. No Sunday outcome selection is permitted.

Neutral models.py, native_ws1.py, weather.py and weather_run.py are unchanged. The
original neutral-first fallback path still works with a valid producer packet;
unchanged fallback copies never count as fitted or independent forecasts. No new
fitted O1-W–O5-W versions are registered by this audit.

Validation: 31 existing synthetic tests plus 3 new native-audit negative controls
pass locally. These are development evidence, not genuine forecast performance.
A separate unscheduled Deepnote notebook runs the original tests and original-byte
audit and writes only create-once research receipts. Preserve failed runs as well
as successful runs. Rollback: discard the additions on the unmerged PR branch;
source, neutral, production and previous receipts remain unchanged.
