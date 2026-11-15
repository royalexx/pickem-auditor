# November 15 NFL Workstream 2: inexpensive marginal shadows

Status: **implemented, tested, shadow-only; prospective forecasts blocked by Workstream 1 source eligibility; hosted native-adapter execution additionally blocked by Deepnote capacity**. Governing authority: `PA-V25-MASTER-2026-11-09 / v1.1`, with explicit user authorization for this bounded Workstream 2 experiment. No production release, Tier publication, collector, NUTS training, production weight change, or source-archive rewrite is part of this PR.

`research/nfl_ws2/experiment.json` is the experiment declaration, written before model execution. Models are deterministic. No decay, shrinkage, hurdle threshold, calibration coefficient or dispersion parameter is optimized on November 15 outcomes. This work is a Phase 1 marginal baseline harness plus individually authorized cheap Phase 2/3 and market-calibration research. The existing general Phase 1.5 investment gate remains in force for expensive architectures.

## Implemented versions and boundaries

| Version | Applicable observations | Predictive law and frozen parameters |
|---|---|---|
| `S1-role-eb-empirical-v1` | Integer counts, signed integer yardage, binary TD events | Player empirical law mixed with equal-player role/position peer empirical laws. Peer weight `4/(n+4)`, own weight `n/(n+4)`. Mean is the empirical-Bayes per-appearance rate estimate. |
| `S2-ew-empirical-hl4-v1` | Same families | Empirical probability masses weighted `2^(-appearance_age/4)`, latest 20 eligible appearances. Report Kish ESS, rather than pretending weighted observations are independent extra games. |
| `S3-eb-poisson-v1` | Nonnegative integer counts; excludes binary events and signed yardage | Gamma prior estimated from other players, posterior mean rate plugged into Poisson. |
| `S4-eb-gamma-poisson-v1` | Same as S3 | Integrate the **same posterior rate**: NB shape `alpha`, success probability `beta/(beta+1)`. Mean `alpha/beta`, variance `alpha/beta + alpha/beta²`. Extra variance isolates parameter uncertainty, not estimated game-level overdispersion. |
| `S5-hurdle-geometric-v1` | Counts with at least 25% observed zeros, plus identified own/peer positive production | Smoothed zero probability and separate shifted-geometric distribution on positive counts. Four equivalent prior games for zero frequency and positive-count mean. This is a scoring/positive-production hurdle **conditional on appearance**, not a DNP model. |
| `S6-fixed-market-logit-v1` | Original coherent same-contract 60/40 and no-vig market | `sigmoid(.5*logit(p_model)+.5*logit(p_market))`, clip `1e-9`, no fitting. Market-only retained. |
| `S7-neutral-10-v1` | Original coherent same-contract 60/40 | `0.9*p_original + 0.1*0.5` on the conditional nonpush probability. Untrained sensitivity. |
| `S7-neutral-25-v1` | Same as preceding row | `0.75*p_original + 0.25*0.5`. Untrained sensitivity. |

There are **eight implemented candidate versions across seven requested families**. Synthetic fixtures demonstrate eight distinct successful predictions on an applicable count contract. There are **zero prospective Sunday predictions so far**. Real-slate successful versions and distinct versions are calculated from actual output, never assumed from this list. Identical predictions within each contract are labeled `identical_prediction_to` and excluded from `distinct_versions_somewhere`. The identical-prediction comparison rounds numeric output to 14 decimal places.

A minimum of three eligible player appearances is required; peer-dependent candidates require five other players with at least three eligible appearances each. Histories are ordered by recorded game end, limited to the latest 40 appearances per player. Peers match the original stat, period, role and position. A player's history never contributes to their peer prior. Missing peers can block S1/S3/S4/S5 while S2 remains available.

For S3/S4, let `m_j` be peer j's mean over `n_j` appearances. The prior center is the equal-player mean of `m_j`; between-player variance is `max(sample_variance(m_j) - mean(m_j/n_j), 1e-9)`. Gamma prior rate `beta0 = clip(center/between, 2, 12)`, shape `alpha0 = center*beta0`. Own observations update `alpha=alpha0+sum(y)`, `beta=beta0+n`. The prior-mean weight is `beta0/(beta0+n)`. These are empirical hyperparameters held fixed during conditional inference, not a fully Bayesian posterior over population hyperparameters. An all-zero peer population blocks S3/S4 instead of introducing an arbitrary positive rate.

S1 and S2 have finite observed support and cannot extrapolate unseen upper tails or negative yardage. This limitation is explicit in every distribution record and should be evaluated with log predictive mass, CRPS and tail diagnostics. They are inexpensive empirical benchmarks, not claims that unprecedented performance is impossible in reality. No Gaussian or Poisson is used for signed yardage. Binary anytime-TD laws use only `{0,1}`; TD **counts** remain distinct from binary events. Fractional sacks are unavailable in this version, because integer-count laws cannot represent half sacks.

S6 and S7 are threshold probabilities, not identified full distributions. Their predicted mean/variance are explicitly `null` with `moment_status=not_identified_by_threshold_probability`. Market-only and S6 do not invent a push rate. S7 preserves a known original 60/40 push rate; its conditional change is rescaled by `1-q_push` when reporting three-way values. These scenarios are not full-distribution challengers and cannot have count CRPS. For S1–S5, all exact-line Over/Under/Push probabilities, mean, variance, parameters, distribution hash and conditional nonpush Over probability are recorded.

## Reconciliation with existing implementations

Inspected at main `912bc7010058092ea735dcda0aa941429194474b`:

- `scripts/bayesian_engine.py`: peer EB Gamma–Poisson, NB likelihood quadrature, and signed Student-t predictive logic. Its function labeled `dist=poisson` already integrates Gamma uncertainty, so it is **not** the S3 plug-in Poisson ablation. The existing Student-t half-integer line path evaluates CDF at the line, while arbitrary other fractional integer-stat lines need lattice boundaries; this standalone work uses exact lattice definitions everywhere and leaves legacy predictions unchanged.
- `scripts/bayesian_usage.py`: positive workload, log-workload Student-t quadrature and conditional conversion. This is a workload model outside this workstream; no exposure simulation is reused or altered.
- `scripts/usage_baseline.py`: checksum-bound usage cache, production scouting-v7, recent-five exposure, optional early-season 40%-weighted same-role prior history. This is a legacy control, not a prospective certification or the new rate law.
- `scripts/fit_blend.py`: walk-forward M0/M1/M2/M3 fitting and source/chronology gates. No call to its fitting/config writer was made.
- `scripts/reform_step8_market_shadow.py`: the fixed unfitted equal-logit formula, retained numerically including its clipping convention. The new tests compare this original formula directly at extreme probabilities.
- `scripts/reform_step10_calibration_shadow.py`: Beta/global stack, 300 prior training contracts/20 dates plus 100 later evaluation contracts/20 dates, original-source gate. November 8 supplied only 50 coherent pairs on one date, so fitting is blocked.
- `scripts/cloud_bayes_incremental.py`: sequential Gamma–Poisson exposure rates and grid logit-offset calibration; preserves V1 versus canonical-Over V2 orientation. The archived November 13 state on `data/live-observations` was independently read and its compressed hash checked. NFL groups have 1–3 dates and at most 30 observations; canonical-Over V2 groups have one date. The code requires 100 observations and 14 days. No NFL posterior qualifies. `research/nfl_ws2/calibration_inspection.json` records the state commit, path, hash and counts. Downstream `source_days` hashes alone would not establish original publisher authentication even with larger samples.
- `v2/contracts.py` and `v2/stat_registry.py`: reused identity, UTC, source receipt, quote, no-vig, and probability validation. New laws remain standalone; no legacy parser, registry, snapshot, or production code is modified.

Fable/Carbon findings C04–C08 were **not located** in the checked main tree, all locally fetched Git history messages, or Deepnote file/notebook names. `tests/test_v25_c07_discrete_contracts.py` and the current integer-distribution contract were inspected as supporting C07 implementation evidence; they are not substituted for the missing review reports. Exact report reconciliation remains open pending the source paths. The user was asked for these paths while implementation continued.

### Exposed historical evidence

The November 8 official settlement audit in `docs/REFORM_PHASE4_RESULTS_20261108.md` identifies 257 original contracts, 253 verified settlements and four unverified cases. Production 60/40 was available on 67, scored Brier approximately .2655, and is explicitly not certified calibrated. On the 50 coherent consensus/market pairs used by Step 8: consensus Brier .267215, fixed-logit .260017, market-only .256062. These are previously inspected one-Sunday diagnostics; they are not an untouched validation set or a reason to fit a calibrator.

The completed 175-week Deepnote report supersedes the preliminary two-week V5.6 narrative. On 407,476 paired synthetic historical contracts: V3 Brier .2352119702, V4 .2350776462, V4.1 .2350862723, V5.6 .2429300270. V5.6 loses Brier in 170 of 175 weeks and all ten seasons. Its >=80% cohort claims 85.9065% versus 72.3916% realized hit over 66,994 contracts. Internal source-week chronology and joint accounting passed the original recorded integrity audit; original pregame publisher timestamps and retrospective appearance-based contract selection remain unresolved. These are inspected historical audit receipts, **not a new rerun of 407,476 contracts by WS2**.

Read-only copies of the three small original Deepnote report bodies are under `research/nfl_ws2/historical_v56_*.json`. Original paths are listed in `research/nfl_ws2/evidence_receipt.json`. Per-market distribution scores are retained; mixed count/yardage CRPS is not used for promotion. V5.6 is not promoted.

### Existing unmerged Sunday branch

Inspected `research/nfl-nov15-prospective-shadow-freeze` at `3dc3a2b39b56c0c67d381f1912d63345ecba2250`. Its 13 existing adversarial tests pass independently in an isolated local copy. That confirms its tested behavior, not its adequacy for this workstream. Issues found by direct inspection:

1. The `for a,b in zip((over,under),(over,under))` run-ID comparison compares each row with itself. A later metadata check partially protects this case, but the loop does not test side identity as intended.
2. Forecast times are checked before kickoff but not at or before the new capture time, allowing inherited future-dated forecasts in a purported current capture.
3. Optional period and missing event/quote/contract IDs do not establish the full canonical contract.
4. Paired displayed market probabilities, book labels and inherited timestamps are not original two-sided raw quote-byte authentication.
5. Row exclusions for TD markets and duplicate-side policy do not implement the requested full-family marginal coverage.

The new runner supersedes this narrower prototype for WS2; no code from the branch is merged or copied into production.

## Workstream 1 handoff and execution

A native WS1 capture appeared during this session and was inspected through its original notebook run snapshot. The native schema is `nfl_20261115_source_control_v1`, on branch `chatgpt/nfl-sunday-ws1-source-20261115` at `9c8dcea17365575337b0ab063c34e3f30e51baee`. Its original manifest is `reports/nfl_20261115_prospective/source_control/captures/20ed83fd40787cccc38a242a8698f0a4e09aaaa54f261b923c8a5f4aa232ed10.json`, canonical hash `20ed83fd40787cccc38a242a8698f0a4e09aaaa54f261b923c8a5f4aa232ed10`, file hash `9a7752e70db7c1d56226847df56f7985c1dd4fba79ae6c3b49acc9e7aad6c150`.

WS1 run `cd6e5a7d-bf05-490a-beb2-d0c2c3a3876e` records 12 verified schedule games and **1,845 original offered contracts, 0 source-certified quotes, 0 forecast-eligible contracts**. Every contract has `EVENT_IDENTITY_UNVERIFIABLE`. Its controls are explicitly `NOT_ORIGINALLY_FROZEN`, no historical rows were collected, and product-specific settlement rules remain unverified. These counts are from the original recorded WS1 run, not an independent WS2 rerun of the complete 5.8 MB manifest.

`scripts/nfl_ws2_ws1_adapter.py` now directly accepts that actual native schema, verifies canonical bytes and filename hash, preserves all original identities/control columns/rejections, and creates unavailable records for all eight candidates. It does not set source/forecast eligibility or infer player teams. Even a later eligible flag cannot substitute for source-bound history and controls. The native adapter is independently tested locally. Run it with:

`python scripts/nfl_ws2_ws1_adapter.py --source-manifest ORIGINAL_WS1_CAPTURE.json --out-root NEW_AUDIT_DIRECTORY`

A new unscheduled Deepnote notebook `70fbdcbfbaf844bd8d590068916da1da` contains an exact-hash-bound adapter audit and immutable output writer. The adapter was uploaded to the new path `research/nfl_ws2_20261115/nfl_ws2_ws1_adapter_df891a505157.py`. Its requested detached run was **rejected before receiving a run ID**: “You have reached your Team Trial limit of 5 parallel running projects.” The project machine is stopped. No other project was stopped, no run was claimed successful, and no native per-contract output was claimed written. The notebook is ready to run when capacity exists. The local immutable blocked receipt records this additional operational limitation.

**The structured input schema below is a proposed model-ready supplement, not a schema that WS1 has adopted or produced.** Its purpose is to specify what the marginal engine needs once native WS1 source eligibility is repaired and genuine history/controls are supplied. Do not manufacture canonical input or run a competing collector.

`python scripts/nfl_ws2_shadow.py --manifest PATH/manifest.json --out NEW_PATH/forecast.json`

The forecast clock is the actual UTC clock; there is no CLI backdate flag. The output path is created exclusively. No manifest means an explicit blocked receipt:

`python scripts/nfl_ws2_shadow.py --out NEW_PATH/blocked.json`

Proposed manifest fields:

- `schema=ws1-nfl-source-control-v1`, `owner=workstream1`, `target_date=2026-11-15`, immutable `manifest_id`, `input_freeze_at`, `model_training_cutoff_at`.
- `sources`: original `v2.contracts.SourceReceipt` records. Their project-relative archive paths must exist under the manifest directory, have matching SHA-256, and cannot escape the directory via traversal or symlinks. Source JSON packets carry normalized observations/quotes/controls derived by WS1. Local matching authenticates bytes **relative to the manifest**, not the truth of timestamps or original publisher authorship.
- `contracts`: one record per exact original offered quote, including accepted/rejected original rows. Each has `quote` matching `MarketQuote`, `quote_source_id`, `history_source_ids`, optional `control_source_id`, `position`, `role`, `participation_basis`. Failed or missing inputs remain row-level unavailable records with reasons.
- `quote` includes event/player/team/opponent/stat/period, original book/product/line, quote timestamp, exact settlement policy, raw quote archive path/hash and any original two-sided decimal odds. For the local binary `anytime touchdown` extension, WS2 validates common quote structure with the existing count-TD quote validator and applies separate binary-history support; the original binary stat identity is preserved and never changed in output. Full game and DNP-void appearance conditioning are the only accepted semantics. Other participation/settlement cases abstain.
- The quote source JSON has `quotes: [exact quote objects]` and `eligibility: [{quote, position, role, participation_basis}]`. The item must exactly match these source-bound identities, and the raw provider quote archive must independently match its original hash. This does not itself certify WS1's normalization; independent source review remains necessary.
- History source JSON has `observations` with `sport`, `stat_key`, `period`, `position`, `role`, `event_id`, `player_id`, `observation_id`, `team_id`, `game_end_at`, `available_at`, `appearance`, `value`. All used observations must satisfy game-end <= available <= training-cutoff <= freeze <= actual-forecast < kickoff. History source acquisition must also precede training cutoff. Current **entire slate** event IDs are rejected for all players. DNP/unknown entries are counted but never treated as zero; only `appearance=appeared` enters a law. Per-contract role/position grouping uses the canonical as-of source, not target outcomes.
- Control source JSON has `controls`, each containing the exact complete `quote`, original `model_version`, `forecast_at`, and coherent original `q_over/q_under/q_push`. Wrong contract or future control means S6/S7 unavailable, even if the history models remain available. Control probabilities and original source bytes are copied unchanged.

Each candidate gets an explicit forecast/unavailable status for every original input. Failed contract counts and per-model availability counts are retained. A candidate is never filtered for disagreement with market. The output is `UNCERTIFIED_SHADOW` even when every local source/identity/time test passes; source certification is separate from model validity. Parameter/code/source hashes are recorded. No existing board/report is changed.

## Mathematical verification and postsettlement scoring

The new 45 tests independently verify PMFs against closed formulas and SciPy, Gamma–Poisson density integration, normalization and first two moments, integer/fractional/negative line boundaries, exact zero mass, same S3/S4 mean with different variance/tails, empirical shrinkage and EW ESS, binary support, signed yardage, no invented positive-production hurdle, and count CRPS against pairwise absolute expectations. Source tests cover future observations, other-player target-game leakage, source acquisition after freeze, original raw quote tampering, exact line/player/team/event swaps, missing peers, DNP exclusion, duplicate observations/quotes, noncomparable market, future capture refusal and exclusive immutable writes. Existing legacy/reform tests are also run; see the evidence receipt for actual results.

Count CRPS is `sum_k (F(k)-1[y<=k])²` on the nonnegative integer lattice. The algorithm uses survival probabilities in the upper tail and stops only with an explicit tail-error bound <=1e-10, or returns unavailable after 100,000 terms. For k above the realized y, remaining squared-tail mass is bounded by `S(k)*E[X]`. Signed-yardage CRPS is not computed by this count function. No CRPS is attributed to a probability-only S6/S7/market control.

The separate offline postsettlement scorer does not enter the forecast import path:

`python scripts/nfl_ws2_score.py --forecast ORIGINAL_FORECAST.json --settlements VERIFIED_LABELS.json --out NEW_SCORE.json`

Labels are a list of `{quote: EXACT_ORIGINAL_QUOTE, status: verified|void, actual: INTEGER_FOR_VERIFIED, source_id: ORIGINAL_OFFICIAL_SOURCE_ID}`. Duplicate labels are rejected. Missing, unverified, void and push cases are retained in separate denominators. The scorer checks identity and support; it does not independently authenticate official provider bodies. It reports binary no-push Brier/log loss/signed Over residual, full-distribution three-outcome Brier/log loss, count CRPS and predictive mass diagnostics, **per market**, with strictly matched 60/40 and market-only comparisons. Ties remain in proper scoring. Every single-slate result is descriptive; no IID prop confidence interval or promotion is emitted. Multi-date cluster inference requires a separate preregistered protocol.

## Open gates and rollback

- Missing Fable/Carbon C04–C08 original review reports: report-level reconciliation open.
- Native WS1 source universe: 1,845 contracts, all source-rejected, zero forecast-eligible. No genuine Sunday predictions can be produced from this capture. No synthetic fixture is presented as Sunday output.
- Native schema compatibility: adapter implemented/tested. Hosted whole-manifest execution: blocked by five-project Deepnote concurrency limit; no run ID or native ledger exists. Genuine model-ready history, source-authority review, original controls and verified settlement semantics remain missing.
- Independently certified chronological fitted calibration: abstained; archived NFL sample below its own gate.
- Predictive improvement, calibrated probabilities, prospective reliability and market edge: unestablished.

Rollback is deletion/reversion of these standalone research files. Original legacy engine, production weights, paused training marker, trusted board, source archives and historical forecasts remain byte-identical to base. No merge or deployment is requested by this PR.
