# Independent NBA WS4 audit — November 15, 2026 (America/Toronto)

**Verdict: GO for review of the standalone research evaluator; NO-GO for production integration or investment in a full NBA joint simulator.** Actual WS1–WS3 scientific acceptance remains BLOCKED-BY-DATA. The old NBA consensus and Bayesian controls show descriptive gains on one historical slate; this does not establish prospective skill or product economic edge.

Governing plan: `PA-V25-MASTER-2026-11-09 / v1.1`. Scope: independent Phase 1/1.5 scoring, calibration research and integration contracts. Base `main`: `912bc7010058092ea735dcda0aa941429194474b`. Branch: `audit/v25-nba-ws4-validation-20261115`. Final implementation SHA and draft PR are supplied in the external handoff receipt; the code/source manifest provides file-level reproducibility.

## Evidence actually executed

The original November 10 certified afternoon bundle, finalized post-shadow comparison file, prepared-attempt ledger, official settlement receipt and five original NBA raw boxscores were read in an isolated Deepnote notebook with project storage mounted read-only. No provider refresh substituted for original evidence. The evaluator independently parsed final provider points/rebounds/assists/3PM, derived combinations, reconciled teams/event starts/provider IDs, and matched exact original lines. All 1,783 embedded source objects were hash/length checked against the pinned compressed original bundle. The original producing revision was independently read from `source_revisions.json`.

Created audit notebook: `5e209a1253b34c06baba0ec11a46d83a`. Successful raw replay runs: `ec3164b8-597e-4d31-aa21-d828e47af857`, `e2ff7ba5-2858-4b2c-9344-87634f48b4bc` (identical original mathematical replay outputs), and `fb88b69d-687d-4b29-810f-1527858a5b60` (v2 adds independently counted attempt metadata and all original attempt rows). Final hardened replay run is recorded in `evidence/replay_execution.json`. Earlier attempts failed closed on an incorrect project mount and unnormalized provider team aliases; they remain visible in run history. Normalizing known provider abbreviations is a documented identity mapping, not retrospective repair of a traded-player roster.

### Original source hashes and versions

| Artifact | SHA-256 / version |
|---|---|
| Original compressed pregame bundle | `76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6` |
| Finalized original model sidecar | `65ec6f549d32aa735999841c42f10941cd75aa811ddd7e9d9d2ee8e98ba67921` |
| Complete prepared-attempt receipt | `b57eb04ba8bdeca2b7c40adde2fcebabb1ff98ee5a6938baf88b3a32c89eb2d2` |
| Original official settlement receipt | `7f61d5933b714756e7f7d5561a2b0ca226cecaaff5b801d5567dc56a2f9970b3` |
| Original forecast-producing code | `e5635d8fd8444a3144174cf019924d2010cdbca8` |
| Settlement implementation recorded by receipt | `f3162e921187870ab776bb4c8f3ef1a9543b8512` |
| Frozen consensus policy | `production-historical-ensemble-60-40-20261108-v1` |

All five provider boxscore byte hashes, file paths and producer/data-branch revisions are retained in `evidence/original_replay_v2.json`. Canonical hashes of both original finalized side records appear per contract. The original preliminary snapshot hashes/files remain in the untouched source bundle; finalized predictions are a later distinct pregame artifact, never rebranded as an earlier preview.

**Unresolved documentation pin failure:** the current scored Phase 1 receipt hashes to `3f417d0e9ba271ca95fd0dcec5e1a4291d84099a6bb50a48077ffbafe9bcb474`. This matches the November 11 final sidecar audit v3 receipt. The forensic markdown instead prints `c6811bebc6cf125211f994ba0228ce9638d2022b428ac9dde60567b295cd3d6c` for the same named report. This audit does not assert byte identity with that markdown pin or silently revise the old document. Reconcile the original report versions separately. Independent raw-source outcome and model-row reproduction succeeds; this is not permission to ignore a release provenance discrepancy.

## Complete denominators

- Both sports: 1,314 attempted sides, 712 accepted original sides = 356 exact paired contracts, and 602 rejected sides (438 unpinned external context; 164 unavailable/unverified market).
- NBA: 1,058 attempted sides, 500 accepted sides = 250 contracts; the remaining 558 attempted sides stay rejected in the source ledger. No rejection is scored as a losing bet.
- NBA evaluated population: 250 settled contracts, 47 players, five games, one slate date, eight markets. The date is the original Toronto/slate label November 10, not the UTC start date of late games.
- Consensus: 146/250 available (58.4%), 104 explicit reliability abstentions, 37 distinct covered players; 146 selected sides and no probability ties.
- Bayesian A: 221/250 available, 29 negative-support abstentions; Bayesian B: 225/250 available, 25 negative-support abstentions. Strict NUTS: 0/250.
- Engine A: 250 probabilities, 249 selected sides and one exact 0.5 tie; Engine B: 250 probabilities/selected sides. Exact games/dates/players/contracts/selected IDs for every population and top-k are in the machine score receipt.

`evidence/original_attempt_ledger.json` preserves every attempted side and original rejection reason. `evidence/scored_v3/contract_comparison.csv` retains the familiar per-contract control columns, separate first-book and median-market references, and explicit unavailable WS2/WS3 cells.

## Independent proper-score reproduction

Binary scores use the original P(Over | no push), one observed Over result per contract. Every market comparison uses the same model-covered contracts; denominators differ across models and cannot be compared as if coverage were constant.

| Model | NBA n | Brier | Log loss | Same-n median-market Brier | Model minus market Brier |
|---|---:|---:|---:|---:|---:|
| naive_recent_exposure_rate | 250 | 0.285865786 | 0.794041039 | 0.248599621 | 0.037266165 |
| pooled_peer_shrunk_rate | 250 | 0.261735338 | 0.723695518 | 0.248599621 | 0.013135718 |
| Engine_A | 250 | 0.260114861 | 0.726842785 | 0.248599621 | 0.011515240 |
| Engine_B | 250 | 0.250223466 | 0.693477015 | 0.248599621 | 0.001623845 |
| Bayesian_A | 221 | 0.240821626 | 0.675569627 | 0.248469355 | -0.007647728 |
| Bayesian_B | 225 | 0.238575018 | 0.670432508 | 0.248981460 | -0.010406441 |
| Consensus | 146 | 0.239754910 | 0.672942686 | 0.246562477 | -0.006807567 |
| Market | 250 | 0.248599621 | 0.690370995 | 0.248599621 | 0.000000000 |
| first_book_market | 250 | 0.250012016 | 0.693197419 | 0.248599621 | 0.001412396 |
| NUTS | 0 | unavailable | unavailable | unavailable | unavailable |

The 60/40 result reproduces **0.23975491001822946** against **0.24656247692870542** on exactly **146** contracts, delta **−0.006807566910475942**. Bayesian A/B also beat their own matched median reference descriptively. Engine A/B lose descriptively across their full covered population. A single slate cannot resolve selection, correlated errors, model multiplicity or persistent market skill. The full all-model common support is **145** contracts when including both Bayes models and consensus but excluding unavailable strict NUTS; the score receipt provides each control on that exact intersection. Including strict NUTS yields zero common contracts, explicitly unavailable.

The recent and pooled controls are historical source-backed **counterfactual research baselines**, not originally published forecasts. The pooled model uses all available player history plus a small peer exposure prior; it is not a validated position-specific minutes/outcome model. The first-book reference and multi-book median are distinct original benchmarks. Neither is an actual pick’em payout model.

### Selection reliability is a separate question

| Consensus selection | Selected sides | Hits / resolved | Mean confidence | Brier |
|---|---:|---:|---:|---:|
| Top 1 | 1 | 1/1 | 0.790801 | 0.043764 |
| Top 5 | 5 | 3/5 | 0.736003 | 0.254529 |
| Top 10 | 10 | 5/10 | 0.707972 | 0.282487 |

Top-10 consensus is 5/10 despite mean confidence about 70.8%; this is descriptive, underpowered and development-exposed. It cannot certify a ranking failure mechanism or Tier reliability. The top-k rule is fixed confidence ranking per slate, not a reconstructed record of issued bets. All models have their own selected-ID and eligible-population ledgers; push/void/pending selections stay selected and remain outside resolved hit-rate denominators.

### Distribution and signed-bias diagnostics

| Historical control | Count CRPS | NLPD | Nominal 90% coverage | Predicted / observed zeros | Predicted / observed upper-tail events |
|---|---:|---:|---:|---:|---:|
| naive_recent_exposure_rate | 2.818580 | 2.959661 | 74.000% | 4.808% / 2.800% | 7.326% / 14.800% |
| pooled_peer_shrunk_rate | 2.698036 | 2.873050 | 78.400% | 3.529% / 2.800% | 7.450% / 10.800% |

Upper tails are events strictly above each forecast’s discrete 90th percentile, so nominal tail probabilities vary below 10%; this table uses the actual forecast tail probability. CRPS uses the exact untruncated Poisson formula, verified against direct count-CDF sums. The JSON retains randomized PIT and intervals by contract. Missing legacy full distributions are not reverse engineered from a single threshold probability. Aggregated CRPS mixes statistic scales and is descriptive; future primary comparisons must be within one locked statistic.

| NBA market | Recent-control signed Over residual | Consensus signed Over residual (its own coverage) |
|---|---:|---:|
| assists | +18.7752 pp | +10.9337 pp |
| pa | +2.2300 pp | +14.0364 pp |
| points | +7.6166 pp | +23.3762 pp |
| pr | +2.0853 pp | -1.2152 pp |
| pra | +18.7582 pp | +11.3382 pp |
| ra | +7.9507 pp | -1.6642 pp |
| rebounds | -2.1211 pp | -6.2864 pp |
| threes | -14.1149 pp | -21.1558 pp |

Assists and PRA recent-control Over errors reproduce about **+18.78 pp** and **+18.76 pp**; threes reproduces **−14.11 pp**. A universal NBA probability correction would conceal opposite errors. These are posthoc diagnostic slices, not independent significance tests or demonstrated causal mechanisms.

## Morning reporting semantics and adversarial result

The separate first-archived morning file has **1,248 settled side rows** and 624 name-based diagnostic pairs; NBA contributes 502 alias groups. Averaging wins from both opposite sides reproduces exactly **0.5**, a tautology rather than selection accuracy. All 1,248 rows lack canonical player/event/original-forecast hashes, so this archive cannot be upgraded to a trusted contract cohort. Alias grouping is used only to expose the old report error, never to certify outcomes. It is not mixed with the 712-side certified afternoon artifact.

NBA online Bayesian A fails complementarity on **441/441** available diagnostic pairs; B fails on **451/451**. Maximum Over+Under deviations are **0.1210246158** and **0.1699002035**. The original A/B and production consensus pairs in that separate file are complementary. Do not renormalize the online pair or interpret its apparent scores as valid probabilities.

Current repository notebook cell 9 already calls `scripts/morning_contract_metrics.py`, makes contract scores the primary metrics, labels raw both-side summaries as prohibited for selection accuracy, and exports original identity hashes. This is a verified current-code finding, not a claim about a scheduled live editor deployment. The new WS4 implementation remains standalone and adds explicit push/void/pending, registered universe, full-law checks, calibration/selection clock checks and immutable-stage artifacts. No scheduled morning notebook was edited.

**83 targeted tests pass**, including 32 new WS4 test methods with mutation subtests. The suite covers current-game minutes, same/future rolling results, postgame injuries/lineups, wrong trade teams, source/fit clocks, reversed sides, duplicate contracts, exact line/period, push/void/DNP, negative/unnormalized mass, row-bootstrap prohibition, selected-vs-eligible bias, target-game calibration, retrospective rebranding and outcome-dependent model choice. Synthetic no-signal/selection outcome-flip controls verify the selected IDs cannot change after results; the disabled-dispersion control is specified for the future model experiment, since no new outcome model is built here.

## Uncertainty, calibration and six separate verdicts

| Question | Finding |
|---|---|
| Engineering correctness | Standalone framework and synthetic interface checks PASSED; original report pin discrepancy FAILED; real new WS artifacts unavailable |
| Distribution quality | Old count-law diagnostics measured; new WS3 quality BLOCKED-BY-DATA |
| Threshold calibration | Original signed bias and scores measured; calibrated improvement BLOCKED-BY-DATA |
| Selective ranking | Full and top-1/5/10 diagnostics implemented; prospective reliability INCONCLUSIVE |
| Market-relative skill | Own-coverage paired descriptive scores reproduced; superiority INCONCLUSIVE |
| Product economic edge | BLOCKED-BY-DATA: original execution/payout/void/correlation terms and prospective power absent |

The date bootstrap returns a null interval for this one-date cohort. Five-game bootstrap intervals, retained in the score JSON, are labeled descriptive sensitivity only. They are not date-cluster confidence claims. Cross-date serial dependence, fixed stopping and multiplicity must be preregistered for future confirmatory research. Shared model inputs mean agreement is not independent evidence.

No calibrator is fitted to November 10 as if it were untouched. None/regularized Platt/Beta/isotonic challengers exist as an earlier-OOF, stat/model-specific research framework; adequate prior dates are absent here. Future improvement/noninferiority requires untouched-fold paired proper scores, registered margins, coverage/tail checks, dependence/multiplicity review and a separate integration decision.

## Integration readiness and smallest next action

The versioned boundary specification is `JOINT_ENGINE_READINESS_V1.md`; executable `sample_joint_fixture.json` accepts separate WS1/WS2/WS3-shaped envelopes without merging their branches. It checks shared state, source/model lineage fields, overtime, participation, team-minute/point/shot invariants and same-player PRA/PR/PA/RA. It is not a simulator or proof of predictive minutes calibration. Required future Energy/Variogram scores, original joint-event outcomes, market anchor separation and abstention rules are specified.

Every WS1/WS2/WS3 gate is recorded individually in `ACCEPTANCE_MATRIX.md` and `acceptance_matrix.json`, with PASSED/FAILED/INCONCLUSIVE/BLOCKED-BY-DATA and concrete requirements. No new immutable workstream handoff/forecast manifests were supplied or merged; the WS1 archive-replay notebook was inspected for source location context, not treated as acceptance of new features. Actual integrated runtime and market coverage remain blocked.

**First next-engine experiment:** a one-market NBA points support/tail pilot, holding frozen WS2 opportunity draws constant while WS3 supplies a support-valid Poisson control and one preregistered NB2 challenger. Points accounts for 16/25 Bayesian B support abstentions and 19/29 Bayesian A support abstentions. This supports a small coverage/likelihood investigation, not a presumption of NB2 superiority. Full design, prior-only fit, untouched future dates, margins, stop rule, resource caps and frozen controls are in `NEXT_EXPERIMENT.md`. Keep calibration secondary to that isolated likelihood comparison. Do not build the entire joint simulator because code exists.

## Runtime, reproducibility and rollback

Local 83-test execution: about **1.45 seconds**, peak child RSS **117,940 KiB**. Local original-row score construction: about **1.08 seconds**, process peak RSS **82,676 KiB**; identical score payload on repeat. Measurements are environment-specific and describe evaluation only, not joint-simulation cost. Environment/package versions and file hashes are in the manifest.

Follow `README.md` commands to regenerate scores or rerun against original Deepnote files. The primary report is `evidence/scored_v3/scores.json`. `evidence/scored_v3/contract_comparison.csv` is the familiar row comparison. Raw-byte replay requires original source mounts; the compact source-matched rows allow offline rescoring immediately.

GitHub workflow source remains manually dispatched/paused for expensive training, `.training-control/PAUSED.json` remains true, and NUTS smoke jobs remain disabled. The Deepnote project inventory reported no scheduled notebooks; this does not prove the absence of externally managed morning automation. Current live scheduling/editor deployment cannot be inferred from an exported notebook. No job was restarted, no schedule changed, no archive modified and no production ranking/Tier/consensus or WS1–WS3 implementation edited.

Rollback: stop invoking the standalone package; close the draft audit PR. If later merged for research, revert its audit commit. Retain all failed and successful receipts and frozen legacy controls. No production migration is needed because the package has no scheduled wiring.

This is independent replay of other model authors’ artifacts. The new evaluator’s tests and mathematical review were performed by the same author in separate passes; a separate external code reviewer has not approved it. Do not treat self-run tests as independent release approval.
