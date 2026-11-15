# NFL Sunday November 15, 2026 — Workstream 3

Governing version: **PA-V25-MASTER-2026-11-09 / v1.1**. User-authorized bounded opportunity research. Status: **implemented and fixture-tested; shadow-only; real forecasts blocked by original data dependencies**. This directory is isolated from Workstream 2's statistics, Workstream 4's game simulator, baseline code, production configuration, training controls and workflows.

## Models and limitations

| Model | Implemented variant | Dependency or limitation |
|---|---|---|
| O1-context-volume-v1 | Prior ten-game offense and opponent defense play/pass tendencies; shared lognormal-Poisson pace, opposite-sign zero-mean script shocks; pass/rush/sack accounting; observed historical pace resampling | V3-inspired lower-information adaptation, **not** V3's fitted ten-year ridge or its 75/25 V2/V3 calibrated blend. No predicted scoring margin, spread, total or weather effect without timestamped inputs. No future final script. At least three offense and opponent-defense games. |
| O2-position-usage-v1 | Position-pooled target and carry rates; Dirichlet allocation with residual player/throwaway bucket; optional Beta route participation and target-per-route priors when observed; route caps; Beta-binomial reception conversion; signed conditional yardage | Route-free target-per-attempt variant where routes are absent. Routes do not imply a jointly modeled personnel package. Partial roster never exhausts the pool by construction. QB carry competition included; nonstarter QB opportunities remain in residual. |
| O3-qb-mean-preserving-v1 | Only identified pregame starters; starter probability reported separately; team attempts times Beta(60s,60(1-s)) share; completions conditional on attempts; signed yards conditional on completions; QB carry allocation and signed rushing yards | Mean-preserving alternative to V4.1; reports old/V4.1/O3 Beta expectations. Primary projection is **conditional on identified QB starting and participating**. No unknown-backup full workload. Pass depth, designed-run/scramble split require tracking and are **not implemented** in the lower-information variant. |
| O4-defensive-components-v1 | Opponent plays and run/pass distribution from O1; latest two prior played games' snap share; position-shrunk credit involvement; solo, with_assist, tackle_assists and their exact sum | **Marginal defender model**, not joint defender credit allocation. Per-snap involvement pooled across run/pass; no personnel or alignment tracking. Excludes special-teams credit. Any missing component in the recent eight-game played history blocks that defender. Full game official credit beyond the modeled eligible snaps remains a model limitation. |
| O5-role-mixture-v1 | Offensive role sensitivity: reduced/normal/expanded target and carry share states with multipliers [0.6,1,1.25] and frozen weights [0.2,0.6,0.2]; reallocate within the same team pools | Sensitivity assumptions, not estimated Sunday facts or calibrated transition probabilities. Comparison reports conditional mean, P(Over) shift and direction disagreement against stable O2/O3. O5 does not alter defensive snap shares or QB pass share. |

Team exposures obey `plays = pass_attempts + rush_attempts + sacks`. Pass attempts are a subset of dropbacks; scrambles reside in rush totals in the lower-information variant. Targets and carries conserve their own team pools in each sample; the residual is explicit. Receiving completions and QB passing completions are **separate marginal conversion models**: do not treat the combined output as a coherent joint passing/receiving game. No multi-leg probability may be derived from these marginal outputs.

Yardage uses signed integer-rounded heavy-tailed aggregates conditional on positive count, with parameter uncertainty and an exact zero when count is zero. This is a lightweight aggregate approximation, not a fitted pass-depth or marked-play model. No accuracy claim follows from it. Sample standard errors are Monte Carlo precision only, **not calibration or model-validity intervals**.

## Native Workstream 1 handoff

`native_ws1.py` consumes the actual `nfl_20261115_source_control_v1` manifest from branch `chatgpt/nfl-sunday-ws1-source-20261115`. It checks the pinned manifest hash, every original archived source hash and receipt clock. It retains every candidate, including source rejects, books, prices, identity failures, duplicate observations and missing original model controls. Missing source publication truth remains unverified.

The inspected native schema does not supply frozen opportunity history, a model training cutoff, quantified participation probabilities, or verified product settlement/DNP terms. The native consumer therefore **abstains for every model-contract pair**, preserving the full original denominator. It does not convert a source-certified quote into a forecast-certified prediction.

```bash
python -m research.nfl_opportunity_20261115.native_ws1 \
  --manifest ORIGINAL_WS1_CAPTURE_PATH \
  --manifest-sha256 ORIGINAL_FILE_SHA256 \
  --source-root reports/nfl_20261115_prospective
```

Command arguments above are interface documentation. No live file path or hash has been fabricated. A native handoff with zero actual quotes retains that zero; an unavailable handoff has an **unknown** denominator.

## Extended history interchange

`models.py` accepts an explicitly versioned **proposed** WS1 extension, `ws1-nfl-pregame-opportunity-v1`. This is not a claim that Workstream 1 currently produces it. The extension must be built by a source-owned adapter, with original receipts, namespace crosswalk and authentic already-available historical inputs. WS3 must not collect replacements or infer identity through an unverified name join.

The manifest has `producer_workstream=1`, `day=2026-11-15`, `input_freeze_at`, `training_cutoff_at`, `sources`, and `files`. Sources have unique `source_id`, `provider`, `original=true`, relative `path`, SHA-256, `first_available_at`, `ingested_at`. Every raw file is byte-verified; clocks obey availability <= ingestion <= freeze, and historical source ingestion <= training cutoff. A receipt time can conservatively establish known availability, but must never be represented as verified upstream publication.

`files` has exactly five JSON-array tables, each with a relative `path` and SHA-256: `events`, `team_history`, `player_history`, `roster`, `contracts`. All rows reference `source_id`. Allowed fields are explicit constants in `models.py`; unknown feature columns fail closed. Tables must be materialized within the manifest directory tree. Original source files must also be there, or referenced through resolved paths that remain in that tree. No absolute paths, symlink escapes or missing bytes.

- Events: game ID, home/away team IDs, season/week, UTC kickoff, source ID.
- Team history: prior game ID/team/opponent/season/week/end time/source ID, plays, pass attempts, rush attempts and sacks, optional pace seconds. Defensive opponent exposure must use the same canonical scrimmage-play definition.
- Player history: canonical player/team/game IDs, position, season/week/end time/source ID, explicit played/DNP/unknown state and observed fields. Omitted values remain missing. Counts must be nonnegative, yardage may be signed. DNP/unknown rows cannot carry invented zero workloads. Same-team recent history limits stale transfer roles.
- Pregame roster: target game/team/player/position, source ID, available/uncertain/out state and source-derived or explicitly frozen participation probability; QB expected-starter flag and starter probability. Availability conditional on starting must be documented for QB primary props. Injury uncertainty cannot become a guessed certainty. No history beyond 28 days is used as a current role.
- Exact contracts: original unique contract and quote IDs, book, event/team/player/stat/line/period/source, prices where available, original-contract object, explicit DNP policy and original comparison probabilities. Only full-game including overtime contracts with DNP void are currently supported. Other products require a separate terms adapter. Exact books/quote identities are preserved; no new synthetic lines. Original 60/40 and market probabilities are nullable three-outcome objects. A conditional-no-push market number must not be silently converted into a three-outcome distribution. `comparison_probabilities` can preserve other original engine columns without generating unavailable values.

```bash
python -m research.nfl_opportunity_20261115.models \
  --manifest SOURCE_OWNED_EXTENDED_MANIFEST \
  --manifest-sha256 PINNED_FILE_SHA256 --draws 8192
python -m unittest research.nfl_opportunity_20261115.test_models -v
```

Running `models` with no manifest creates a create-once blocked receipt, not an empty forecast universe. Rejected extended packets produce rejected-input receipts. Forecast reports retain empirical predictive mass functions, mean/SD/quantiles, conditional Over/Under/Push, unconditional statistic probabilities, separate DNP mass, role diagnostics, original comparisons and Monte Carlo precision. DNP zeros are **not settled Unders**. Main and code bytes remain unmodified.

## Frozen experiment and acceptance

Hypothesis: improved team opportunity and participation estimates improve identical-contract predictive distributions versus original frozen 60/40. Test each market separately. Primary: paired three-outcome Brier/log loss; opportunity count MAE/CRPS, per-market distribution CRPS, signed Over residual, zero/tail behavior and role-transition coverage are required secondary diagnostics. Compare stable and role mixture on identical original contracts, report every reject/abstention and missing control separately. Bootstrap paired differences by game and week/date after source-verified settlement. No independent-prop confidence intervals, optional stopping, top-pick edge claim, synthetic live market, or best-model selection on Sunday outcomes.

No statistical training, replay, model selection or prospective score has been run on Sunday outcomes. Synthetic tests are development fixtures. Stop before an event's kickoff; never backdate a later forecast. Use create-once content-addressed run directories. No scheduling. Rollback: discard this unmerged branch; all runtime writes are isolated under `reports/nfl_20261115_prospective/opportunity_models/`.
