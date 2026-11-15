# NBA WS5 v0.1 implementation and mathematical audit

Date: November 15, 2026, America/Toronto. Governing: `PA-V25-MASTER-2026-11-09 / v1.1`.

**Decision: implemented and reproducible, research-only. Retain M0; do not adopt the joint engine.** The required mechanics work, but matched historical J2 distributions regress against the simple J0 control. Genuine prospective forecasts remain blocked. No production, Tier, scheduler, archive, NUTS or 60/40 change was made.

## A. Integration audit

| Workstream | Actual branch / pin | PR / decision | Integration |
|---|---|---|---|
| WS1 | research/v25-nba-ws1-feature-store-20261115; `53c01a9eabb9ed09b5c3186eae0d086b07bcc891` | [#137](https://github.com/royalexx/pickem-auditor/pull/137), open draft; not independently source-certified | Unchanged `v2/nba_ws1`, tests and handoff/source artifacts. `require_usable` preserved. |
| WS2 | research/v25-nba-ws2-minutes-opportunity-20261115; `02426dd1b9c2b0cca28eaf69888adadc0021afa5` | [#138](https://github.com/royalexx/pickem-auditor/pull/138), open draft; M0 retained | Exact `MinutesModel`, `MinuteLaw`, capped allocation and lineup witness. Original 25,641-row findings unchanged; M1/M2 remain challengers. |
| WS3 | No NBA branch, PR or Deepnote handoff located in initial or final searches | No unavailable test or acceptance claim | Explicit minimal event baseline substitution. NFL WS3 is unrelated and unused. |
| WS4 | audit/v25-nba-ws4-validation-20261115; `9821694260edb08b7414f02adea8c1fb3fd3b13c` | [#139](https://github.com/royalexx/pickem-auditor/pull/139), newly published open draft | Unchanged package/tests imported. Actual readiness validator, count PMFs, thresholds and clustered bootstrap exercised against new outputs. |

Pinned base main: `912bc7010058092ea735dcda0aa941429194474b`. Warehouse: `97a8bb566826afe5a3e5a7b8c632043d8a1dca24`. Final simulator execution pin: `ca41c79426a90a57e78ca9554a993db326461737`. Exact executed file hashes are in `results/run_receipt.json`; subsequent WS4 bridge/report changes do not alter those engine draws. `results/upstream_and_boundary_verification.json` proves imported WS1/WS2/WS4 trees are byte-identical to their pins and `.github`, `.training-control`, `config` and `scripts` match base main.

WS4 initially existed only in its Deepnote notebook; its PR appeared during final reconciliation and was integrated before completion. Its original replay source block hash is `8afb20eed79a900d86eab4a6c015fd8325bd5b87855ac6a193b0b36e25aec0e8`. The preserved replay has 250 original NBA contracts, 47 players, five games and one date. Its forensic report-pin mismatch, missing morning canonical identities and noncomplementary old online A/B probabilities remain unresolved; no archive was normalized or rewritten. Source hashes prove content, not independently truthful timestamps.

The current user directive specifically authorizes this bounded simulator despite older general later-phase deferrals. It grants no promotion. Detailed scope decisions, interface adaptations, discovered defects and initial results are retained in `INTEGRATION.md`, `experiment.json`, `audit_amendment.json`, `initial_exploratory`, `pre_score_conditioning` and `pre_full_prior_season`.

## B. Implemented engine and boundaries

`v2/nba_joint` contains separate shared-state, WS2 opportunity, event, source, invariant, market, forecast and CLI modules. One scenario-keyed state supplies both teams and every player/stat. The G1 state learns a three-dimensional log covariance for regulation possession proxy and home/away offensive environments from 32 earlier games. OT uses the retained WS2 geometric-mixture duration law. G0 freezes the environment at its training expectation and regulation duration. The possession quantity is explicitly `FGA + 0.44 FTA - OREB + TOV`, averaged across teams and normalized to regulation; it is never called an observed possession identity.

WS2 minute laws consume one shared duration. The adapter calls the exact upstream law, projection and five-player witness; it does not redraw per-player overtime. Conditional research preserves missing appearance probabilities as null. An inactive player receives zero exposure; uncertain roster membership never becomes confirmed participation. A supplied research roster is a conditioning assumption. The feasible lineup witness proves five on court and integrated exposure; it is not a learned substitution process. Early-exit caps are exercised as controlled engineering scenarios, not fitted injury probabilities. Role changes, returns and low-minute outcomes receive separate diagnostics.

The unavailable WS3 implementation is replaced by a small aggregate mechanism with train-only pooled conversions: 2P 0.5383, 3P 0.3651, FT 0.7817. Prior player rates use the last 20 earlier appearances with 48 pooled prior minutes. Non-three-point production is split into two-point and FT opportunities using the train-only FT contribution share, rather than fabricated tracking data. Finite shot pools allocate by minutes/rates; makes are binomial. `PTS=2×2PM+3×3PM+FTM` and the same `3PM` enters points and three-pointer markets.

Rebound opportunities derive from field-goal misses and an explicitly approximate terminal-FT fraction; a residual unattributed/dead-ball category remains. Offensive and defensive credited counts allocate without exceeding available opportunities. Each assist is tied to a scorer's made field goal and allocated to another eligible teammate; unassisted makes remain explicit. Event-time lineups and quarter-by-quarter scoring are not modeled. Steals, blocks and turnovers are extensible but disabled for forecasting until validated.

The final audit found tied completed-game totals in the first aggregate law. The corrected law uses explicit rejection sampling conditional on unequal final scores, retaining every rejected event vector and its scenario ID. It accepted 3,712 default J2 scenarios from 3,758 event draws, rejected 46 tied draws and left **0 tied final scores**. Mean absolute change per player from that conditioning is points 0.0429, rebounds 0.0173, assists 0.0134. The regulation-tie path producing OT is still not modeled; this remains an aggregate game approximation.

PR, PA, RA and PRA are exact sums of shared primitive draws. `NBAJointForecast/1.0.0` includes identities, mode/conditioning, source and model hashes/cutoffs, actual generation time, count PMF, moments/quantiles, scenario seed/count, Over/Under/Push, Monte Carlo intervals and abstention reasons. Integer pushes are preserved; fractional count thresholds have exact zero push. The strict original-market wrapper retains original book, quote, line, terms and receipt, rejects duplicate/late/unsupported contracts and missing settlement terms, and invents no offered line. No calibration, entropy tilting, target-prop anchoring or market-based model fitting is activated.

Mode A is explicitly synthetic. Mode B has true historical outcomes and logically prior features but retrospective source retrieval and actual present-day forecast timestamps. Mode C requires WS1 `require_usable`, source bytes, exact accepted-history feature derivation, real cutoffs and supplied source-backed participation evidence. Newly generated historical forecasts cannot pass the strict WS4 canonical pregame evaluator; they remain blocked rather than receiving invented original clocks.

## C. Verification and reproducibility

| Suite | Run | Passed | Failed/errors | Skipped |
|---|---|---|---|---|
| tests/nba_ws1/test_*.py | 25 | 25 | 0/0 | 0 |
| tests/test_nba_opportunity.py | 25 | 25 | 0/0 | 0 |
| tests/test_nba_joint*.py | 63 | 63 | 0/0 | 0 |
| tests/test_v25_nhl_nba_phase1.py | 11 | 11 | 0/0 | 0 |
| tests/test_v25_official_capture.py | 13 | 13 | 0/0 | 0 |
| tests/test_population_multisport.py | 9 | 9 | 0/0 | 0 |
| tests/nba_ws4/test_*.py | 33 | 33 | 0/0 | 0 |

**Local total: 179 run, 179 passed, 0 failed, 0 errors, 0 skipped.** Deepnote independently reran the environment, not an independent scientific review: 25 WS1 + 25 WS2 + 63 joint tests = **113 passed**, on free Basic CPU (2 vCPU, 5 GiB), detached read-only storage. Final Deepnote run `b856b31c-da89-4aff-8e81-7af304f72a2f`; notebook `63fe224debe44d0a8ee13e51a3323b75`, unscheduled.

Tests mutate temporal cutoffs, same-game/future histories, identities, inactive exposure, underfilled rosters, infeasible exit caps, scenario denominators, OT, covariance, conversion probabilities, shot/point identities, self/opponent assists, rebound accounting, final ties, combo identities, PMFs/thresholds, duplicates, late quotes, DNP terms and immutable output writes. Fast WS5 scores are checked against retained independent reference implementations. Early failing tests and audit defects were repaired; the final counts above exclude archived intermediate failures.

E1 produced 2,688 stress scenarios at 128/512/2,048 draws, including high OT frequency, up to 7 OT periods and a three-minute early-exit cap. Required arithmetic/rotation violations: **zero**. Maximum team-minute residual: 1.71e-13. The independent minute sampler misses team totals by roughly 29–30 player-minutes in this deliberate stress fixture. Across M0/M1/M2/G0, historical replay includes 14,848 constrained configuration scenarios plus 3,712 unconstrained J1 controls; controls are never presented as valid constrained games.

Actual WS4 code checked 3,712 default scenario envelopes and 4,552 matched empirical count distributions. Maximum CRPS disagreement: **0**. It independently supplies date/game clustered comparisons. This passes structure/distribution arithmetic, not prospective source or statistical acceptance.

The complete replay compared 145 game/configuration scientific hashes and identical score bytes: **PASSED**. Runtime/memory are excluded from byte identity. Local model SHA-256: `e424c7f98bba50315dfde81a60978855d6ceb8c72aba8ad0af310eb31283326f`. Per-input and per-output hashes are in `results/input_manifest.json`, `scenario_hashes.json`, `run_receipt.json` and `evidence_manifest.json`.

Cross-runtime integer count SHA-256 matched: `aeb8843df9eb7ba3160110cd8ef21e01b5bb04d8dad136d4ea5038d2a075e483`. Full floating-point hashes differ between NumPy 2.3.5/SciPy 1.17.0 locally and NumPy 1.26.4/SciPy 1.15.3 on Deepnote. Pin versions/platform for bitwise replay of latent state/minutes; cross-version bitwise identity is **not** claimed.

## D. Forecast comparisons and denominators

The primary cohort is the first deterministic game on each of 24 dates from October 22 through November 15, 2024, evaluated with only earlier observations and 2023–24 fitted parameters. It contains 460 matched appearances / 236 distinct players / 24 games / 24 dates. These are development-exposed historical diagnostics, not a blind test or 460 independent experimental units. Repeated players and dates are clustered; effective independent sample size is not asserted. The separate Nov10 2026 cohort uses all available intervening 2025–26 prior-season shards and discloses the warehouse's November 1 onward recent-data gap.

| Population | Candidate attempts | Conditional candidates | Observed appearances | Matched | Unforecasted appearances | Candidates without appearance | Team mismatch |
|---|---|---|---|---|---|---|---|
| test | 900 | 778 | 512 | 460 | 52 | 317 | 1 |
| original | 209 | 172 | 118 | 109 | 9 | 63 | 0 |

All models use the identical matched cohort. Candidate exclusions, unforecasted appearances, uncertain/DNP candidates and identity conflicts remain in `denominator_ledger.json`. Only correctly matched player/team outcomes are scored. No unconditional participation false-positive/false-negative accuracy is claimed. Historical source-scope quarantine exclusions remain explicit.

### E2/E3: count CRPS, lower is better

| Statistic | F0 empirical | J0 marginals | J1 shared | J2 M0 | J2 M1 | J2 M2 | J2 marginal shuffle |
|---|---|---|---|---|---|---|---|
| points | 3.584910 | 3.707883 | 3.632785 | 3.993858 | 3.959115 | 3.887714 | 3.993858 |
| rebounds | 1.425241 | 1.416223 | 1.452700 | 1.558328 | 1.555671 | 1.507227 | 1.558328 |
| assists | 1.038438 | 0.996417 | 1.002175 | 1.055990 | 1.060211 | 1.044780 | 1.055990 |
| threes | 0.664683 | 0.666647 | 0.672399 | 0.706952 | 0.684648 | 0.689428 | 0.706952 |
| pr | 4.205834 | 4.428450 | 4.359161 | 4.936282 | 4.914152 | 4.760476 | 4.969036 |
| pa | 3.931433 | 4.101919 | 4.029826 | 4.511646 | 4.507352 | 4.399296 | 4.530643 |
| ra | 1.954950 | 1.962815 | 1.978896 | 2.190566 | 2.198342 | 2.120827 | 2.190897 |
| pra | 4.619467 | 4.840735 | 4.758684 | 5.462042 | 5.473244 | 5.283115 | 5.532713 |

F0 is a simple independent recent empirical control, not the frozen production engine. J0 is an explicit minimal Gamma–Poisson marginal substitute because a validated WS3 marginal handoff was unavailable. J1 adds shared state with unconstrained exposure. J2 adds constrained exposure/events. `J0_shuffle` independently permutes each J2 player/stat column, exactly preserving single-stat marginals while rederiving combinations. Its equal single-stat CRPS is intentional. Coherent combo arithmetic alone does not establish better probabilities.

| Statistic | J2 − J0 CRPS | Exploratory 95% date-cluster interval | Matched n |
|---|---|---|---|
| points | 0.285975 | [0.098769, 0.492555] | 460 |
| rebounds | 0.142105 | [0.069555, 0.220162] | 460 |
| assists | 0.059573 | [0.018948, 0.103275] | 460 |
| threes | 0.040305 | [0.016402, 0.0629] | 460 |
| pr | 0.507832 | [0.239293, 0.796103] | 460 |
| pa | 0.409726 | [0.155083, 0.67454] | 460 |
| ra | 0.227750 | [0.107209, 0.355247] | 460 |
| pra | 0.621307 | [0.295108, 0.967422] | 460 |

Positive differences are regressions. These descriptive intervals use 24 date clusters, 1,000 resamples and no multiplicity or serial-dependence correction; they do not authorize release. The actual WS4 bridge also recomputes date/game intervals.

### Intervals, zero/tail behavior and moments

| Statistic/model | 50% cover | 80% cover | 90% cover | Mean bias | Variance accuracy ratio | Zero residual | Upper-tail residual | Zero-mass empirical NLPD cases |
|---|---|---|---|---|---|---|---|---|
| points/J0 | 0.439130 | 0.676087 | 0.756522 | 0.054008 | 2.008159 | -0.069582 | -0.069192 | 48 |
| points/J2 | 0.473913 | 0.730435 | 0.836957 | -2.479059 | 1.835926 | 0.049032 | -0.104416 | 35 |
| rebounds/J0 | 0.623913 | 0.847826 | 0.926087 | 0.059018 | 1.126185 | 0.018954 | -0.010224 | 7 |
| rebounds/J2 | 0.584783 | 0.797826 | 0.884783 | -0.868563 | 1.752500 | 0.105961 | -0.073013 | 20 |
| assists/J0 | 0.695652 | 0.891304 | 0.941304 | 0.068020 | 1.178527 | 0.012993 | -0.019260 | 9 |
| assists/J2 | 0.667391 | 0.854348 | 0.915217 | -0.517476 | 1.787653 | 0.094260 | -0.054365 | 16 |
| threes/J0 | 0.743478 | 0.902174 | 0.943478 | -0.046145 | 1.272800 | -0.008696 | -0.025713 | 4 |
| threes/J2 | 0.706522 | 0.869565 | 0.917391 | -0.342816 | 1.866559 | 0.073183 | -0.056878 | 13 |
| pra/J0 | 0.386957 | 0.639130 | 0.719565 | 0.181046 | 2.239820 | -0.018648 | -0.066253 | 77 |
| pra/J2 | 0.426087 | 0.704348 | 0.830435 | -3.865099 | 1.929503 | 0.074474 | -0.105435 | 57 |

Bias is predicted mean minus observed count. The variance accuracy ratio is mean squared mean error divided by mean predictive variance; one is a diagnostic reference, not a sufficient calibration criterion. Zero/tail residuals are predicted minus observed event frequency. Upper-tail events use each forecast's discrete 95th quantile; their predicted probability need not equal 5%. Full means, variance, quantiles, coverage and proper score rows for every market/model remain in the artifacts.

At 128 scenarios, unsmoothed empirical NLPD is infinite when the observed count has no sampled mass. Those failures are counted explicitly; a finite-subset mean is labeled as such and is not a matched proper-log-score comparison. No arbitrary floor or invented smoothing repairs the likelihood. Consequently a reliable full-support J2 NLPD comparison is **unavailable**, not passed.

### E4: matched joint scores

| Model | Energy | VS exponent 0.5 | Synthetic joint-event Brier | Predicted joint-event frequency |
|---|---|---|---|---|
| F0 | 4.390689 | 3.152328 | 0.115798 | 0.073828 |
| J0 | 4.504389 | 3.208635 | 0.113028 | 0.102666 |
| J1 | 4.457266 | 3.211165 | 0.111237 | 0.146026 |
| J2 | 4.859476 | 3.656943 | 0.112566 | 0.073064 |
| J0_shuffle | 4.855469 | 3.472955 | 0.118635 | 0.039164 |

J2 − J0 Energy difference: 0.355087, descriptive date interval [0.1631884675516649, 0.564975647089832]. J2 − exact-marginal shuffle Energy difference: 0.004007, interval [-0.004044655542230719, 0.01135594122313558]. The dependence-only Energy result is **INCONCLUSIVE**. Synthetic joint-event Brier and Variogram disagree in their assessment of coupling; no general dependence improvement is demonstrated. Joint-event thresholds are prior-history medians, not sportsbook offers.

Energy uses raw-count PTS/REB/AST Euclidean coordinates; Variogram uses prespecified exponent 0.5 and unit unordered-pair weights. Identical empirical finite-ensemble conventions are used in every arm. Team/opponent pairs are selected by prior median minutes before seeing target outcomes, and retained in `team_pair_scores.json`. Modeled same-player correlations are in `dependence.json`; signs alone are not calibration evidence.

### E5: exposure ablation with fixed outcome mechanism

| Exposure | Raw minutes CRPS | Allocated minutes CRPS | Predicted minutes | Observed minutes | Allocated 90% cover | Points CRPS | PRA CRPS |
|---|---|---|---|---|---|---|---|
| J2 | 4.061672 | 5.625994 | 17.989736 | 23.710870 | 0.723913 | 3.993858 | 5.462042 |
| J2_M1 | 3.821073 | 5.630496 | 17.814370 | 23.710870 | 0.682609 | 3.959115 | 5.473244 |
| J2_M2 | 3.662156 | 5.237120 | 18.351081 | 23.710870 | 0.697826 | 3.887714 | 5.283115 |

Projection substantially changes both marginal means and variances. M2's relative minute gains transfer to some count-score gains in this small cohort, but do not cure J2's regression against simple controls and do not overturn WS2's non-adoption decision. Low-minute, early-exit, return-gap, changing-role and observed-OT slices are retained in `stress_diagnostics.json`; outcome-conditioned stress slices are not unconditional coverage targets. The full per-player pre/post-allocation shifts are in `opportunity_distortion.json`.

### Separate original Nov10 contract diagnostic

The independent WS4 report of original frozen forecasts was rerun. Newly generated J2 probabilities at the same original contract identities are explicitly **retrospective counterfactuals**, never reconstructed original forecasts. The market provider's event IDs are resolved to ESPN IDs only through WS4's independently verified official-source hash/path mapping. Initial incorrect provider lookups and the corrective reads remain in the amendment/receipt. No quote line, sportsbook price or canonical identity is invented.

| Original control | Exact paired contracts | Original Brier | New J2 counterfactual Brier | Original signed Over residual | New J2 signed Over residual |
|---|---|---|---|---|---|
| Bayesian_A | 221 | 0.240822 | 0.262228 | -0.008122 | -0.111425 |
| Bayesian_B | 225 | 0.238575 | 0.261952 | -0.025978 | -0.109340 |
| Consensus | 146 | 0.239755 | 0.273144 | -0.018305 | -0.109750 |
| Engine_A | 250 | 0.260115 | 0.261054 | 0.036908 | -0.111219 |
| Engine_B | 250 | 0.250223 | 0.261054 | 0.033744 | -0.111219 |
| Market | 250 | 0.248600 | 0.261054 | 0.045811 | -0.111219 |
| first_book_market | 250 | 0.250012 | 0.261054 | 0.041795 | -0.111219 |
| naive_recent_exposure_rate | 250 | 0.285866 | 0.261054 | 0.033974 | -0.111219 |
| pooled_peer_shrunk_rate | 250 | 0.261735 | 0.261054 | 0.062506 | -0.111219 |

Original universe: 250 contracts; J2 available for 250; rejection reasons {}; pushes 0. Strict NUTS has no available original forecast and is not fabricated. Original control coverage differs, so each row above uses its own exact intersection with J2. Log loss, signed residuals and side-conditional calibration are in `audit_summary.json`; original per-contract and new triplet/MC fields remain in `original_market_diagnostic.json.gz`. One exposed date cannot establish prospective market edge, product returns or profitability. DNP/void probabilities remain unavailable.

| Secondary statistic | J0 CRPS | J2 M0 CRPS |
|---|---|---|
| points | 3.304413 | 3.397559 |
| rebounds | 1.419617 | 1.547436 |
| assists | 0.863175 | 0.885656 |
| threes | 0.570118 | 0.628910 |
| pr | 4.163460 | 4.388141 |
| pa | 3.755751 | 3.862862 |
| ra | 1.906470 | 2.066510 |
| pra | 4.629001 | 4.852385 |

## E. Efficiency and Monte Carlo accuracy

| Synthetic scenarios | CPU seconds | Wall seconds | Scenarios/s | Opportunity seconds | Events seconds | Array bytes |
|---|---|---|---|---|---|---|
| 128 | 0.274644 | 0.246276 | 519.742783 | 0.132367 | 0.084732 | 313344 |
| 512 | 1.149294 | 1.028101 | 498.005487 | 0.549978 | 0.356967 | 1253376 |
| 2048 | 4.877388 | 4.374405 | 468.177947 | 2.335905 | 1.542435 | 5013504 |

Complete final 29-game, 145-configuration experiment: CPU 74.40s, wall 74.44s, peak process RSS 391.2 MiB. Default real-size J2 inference averaged 0.309s/game at 128 scenarios. A linear extrapolation for ten games at 2,048 scenarios is about 49.5s of simulation, excluding source collection, I/O, evaluation and platform contention. This is a measured-cost extrapolation, not an operational latency guarantee. Array bytes exclude Python event/lineup objects; peak RSS is measured for the entire experiment, not falsely presented as isolated per-game incremental memory.

At a probability near 0.5, nominal MC standard errors are approximately 4.4%, 2.2% and 1.1% for 128/512/2,048 scenarios. Exact Clopper–Pearson intervals accompany event probabilities, including sampled-zero tails; half-integer pushes are structural zero. E1's rare-tail and combo estimates, intervals and scenario counts are in `engineering.json`. Zero tail hits do not establish zero risk. These bounds quantify simulation error conditional on the model, not model or source uncertainty. 128 historical scenarios are a bounded mechanics/score pilot, not a sufficient production tail budget.

## F. Readiness and prospective canary

| Gate | Status | Reason |
|---|---|---|
| A Engineering | PASSED | Reproducible source-separated engine; all required tested arithmetic/rotation/count/threshold invariants hold. |
| B Source integrity | BLOCKED-BY-DATA | No newly certified original-contract forecast. Authentic clocks, eligibility, participation and model/source independent signoff incomplete. |
| C Marginal reliability | FAILED | J2 regresses against J0 on matched primary targets; retain controls. |
| D Joint reliability | FAILED | Energy/Variogram regress against J0; dependence-only superiority remains inconclusive. |
| E Prospective readiness | BLOCKED-BY-DATA | Collector-independent fixture works and genuine capture attempted; source/participation/quote gates abstain. |
| F Production promotion | BLOCKED-BY-DATA | Future prospective evidence absent; promotion additionally lies outside this directive and requires explicit separate approval. |

E6 used the existing WS1 bounded capture at **2026-11-15 20:19:08 UTC / 15:19:08 Toronto**, before Lakers–Suns at 21:00 UTC. Original snapshot SHA-256: `2a4d359356f9e4a557c79c20914730651cf2abaac3211e587f83b56663e3ca56`. Result: all 36 candidates rejected for `SNAPSHOT_BLOCKED:ELIGIBILITY_UNCERTAIN,ORIGINAL_CONTRACTS_UNAVAILABLE,RECONSTRUCTED_PROXY_HISTORY`. The original bytes, receipt, rejection ledger and upstream errors are preserved. There is no certified prospective model forecast. No current/future injury or player participation probability was invented.

External independent approval of this engine and the new WS4 adapter remains pending. WS4's unchanged code independently checks the structures it implements; running another environment does not make the author's statistical decisions independent. An engineering pass cannot close the source, predictive or release gates.

## G. Reproduction, files and rollback

Integration branch: `research/v25-nba-joint-engine-v01-20261115`. The draft PR and final integration head SHA are recorded in the final delivery receipt after publication. Core engine execution uses the exact pin stated above; the final head adds independent WS4 integration and frozen audit artifacts. `CHANGED_FILES.txt` lists every changed repository path; `results/evidence_manifest.json` covers final evidence bytes.

```bash
OPENBLAS_NUM_THREADS=1 python -m v2.nba_joint --fixture --scenarios 128 --seed 20261115 --output work/nba_joint_fixture_new
OPENBLAS_NUM_THREADS=1 python -m research.nba_joint_v01.reproduce --output work/nba_joint_replay_new
python -m unittest discover -s tests/nba_ws1 -v
python -m unittest discover -s tests -p test_nba_opportunity.py -v
python -m unittest discover -s tests -p 'test_nba_joint*.py' -v
python -m unittest discover -s tests/nba_ws4 -v
```

The replay restores the pinned warehouse shards and preserved official bytes, recreates frozen research inputs and compares all scientific hashes/score bytes. Use a complete Git checkout containing the warehouse pin, exact local dependency versions for floating-point identity, and a fresh output directory. `README.md` supplies the one-game historical command and expected blocked-source CLI command. Outputs use exclusive creation.

Rollback now: stop invoking `v2.nba_joint` and close the draft integration PR. No deployed importer, migration or scheduler needs reversal. If the research PR is merged later, revert that isolated PR while retaining original source and experiment receipts. WS1, WS2 and WS4 PRs themselves remain unmerged by this ticket.

## H. Smallest next research decision

The largest measured limitation is **uncertified roster/appearance conditioning and the resulting minute-marginal distortion**. The broad prior-appearance union includes many players who do not appear, and constrained allocation spreads 240 minutes across that hypothetical roster. On matched actual appearances, M0 minutes are around 18 predicted versus 23.7 observed; projection worsens minute CRPS substantially. Fixing event arithmetic does not repair this source/estimand problem.

Run one small, preregistered 10-game diagnostic across at least five future dates: freeze source-backed game-day eligibility and role evidence, preserve every candidate/DNP/unknown, retain missing appearance probabilities as unknown, and compare frozen M0 distributions before versus after allocation on the same supported conditional cohort. Measure candidate overcoverage, unforecasted appearances, minutes CRPS, zero/low-minute/OT coverage and allocation-induced shifts before adding any outcome complexity. Active-roster membership must still not be assigned appearance probability one. If unconditional appearance evidence remains unavailable, keep that arm blocked. No J3 copula, neural architecture, expensive fit or production promotion is recommended.
