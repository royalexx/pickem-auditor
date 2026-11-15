# WS4 weather evidence audit — research only

Governing plan: PA-V25-MASTER-2026-11-09 / v1.1. This is an authorized bounded
extension of the existing WS4 shadow experiment, not a new simulator or release.

The WS1 v2 pin is `273da5a6f5456e99e9b5bd4f2172abce1bf77c7bfbe82d38199886fcad612807`,
produced by Deepnote run `7dfe59cf-01cb-42b9-9eae-51515ba59051`. It contains 11
pregame forecasts and one already-started exclusion. It also explicitly records
`BLOCKED_NO_AUTHORIZED_VINTAGE_ARCHIVE_IDENTIFIED`, zero authentic historical
training rows, and exclusion of observations/reconstruction. Fitting a response
or forecast-error distribution from this handoff is impossible. No fit, coefficient,
scenario weight, weather uncertainty law or weather-conditioned prediction is invented.

`audit_weather_gate_v2.py` consumes that exact producer schema and pin. It verifies
all dependency and original successful receipt hashes, the event-table/pin identity,
original event/fixture/kickoff and venue, issuance/retrieval/freeze clocks, native
forecast values and validity intervals, wind/temperature/precipitation unit conversions,
and exposure classification. Unknown retractable roofs stay unknown. It does not
call the WS1 producer, any weather endpoint, or the simulator. The original independent
WS4 auditor checks the 11 neutral files and 116 original model rows. Their byte hashes
are checked before and after. Source and original denominator ledgers remain intact.

The new SHA-addressed ledger copies frozen neutral probabilities, moments, PMFs,
quantiles, seeds, Monte Carlo errors, code/input hashes and parameter receipts verbatim.
Every unavailable weather distribution and difference is null. An absence of fitted
response is not an estimated zero effect. There are no fallback copies or extra votes.
It also records that weather retrieval occurred after the old neutral forecast clocks;
those old forecasts are never reinterpreted as weather-conditioned.

Neutral J1: 58. Neutral J2: 58. Weather J1/J2: 0/0. Valid matched neutral/weather
contracts: 0. J3: ABSTAIN (no certified original pregame spread or favorite role).
J4: dependence diagnostic only. Existing 4,096 draws are preserved. The initial
v0.3.0 canary is separate and is not added to the 58-contract denominator.

Game-level opportunity, pass/run, sack, QB and shared-allocation weather effects are
all NOT_ESTIMATED. Team inputs and historical parameter lineage are retained, while
team allocation draws were not archived by the neutral output and must not be regenerated.
J2 dispersion hyperparameters remain the original unvalidated sensitivity assumptions;
Monte Carlo precision does not quantify empirical calibration or fitted parameter uncertainty.

Future fitting requires WS1-authenticated historical forecast vintages, exact games,
pregame venue/roof evidence and original opportunity outcomes. Freeze the design and
chronological folds first; group both teams/all contracts by game and week, and compare
to frozen neutral, disabled and shuffled-weather controls. No Sunday outcome is used
here. These prerequisites are a blocker, not authorization to create unsupported inputs.

Local verification: 67 existing regression/adversarial tests and 9 new audit-gate tests
passed. The delivery receipt records hosted run results and failed attempts separately.
Rollback removes only these new audit files/sidecars. PR #130 remains draft/unmerged;
no production promotion, ranking or betting recommendation.
