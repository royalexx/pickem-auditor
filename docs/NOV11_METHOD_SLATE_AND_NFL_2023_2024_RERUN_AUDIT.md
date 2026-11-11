# November 11, 2026 — Methodology, last-slate scoring and 2023–24 NFL rerun decision

**Audit type:** independent, read-only research decision; source evidence is retained without modifying model probabilities. **Outcome:** allow 2023 and 2024 NFL chronological *regression/diagnostic* replay on the repaired framework; do **not** describe the already inspected years as fresh blind validation, authorize production changes, restart NUTS or release Tier 1/2. The next valid performance test must use new original pregame quotes and source availability, prospectively captured.

## A. What “last night” actually means

The original November 10, 2026 (Tuesday) NBA/NHL source-qualified **afternoon** batch was created before games. The final official-settlement audit on November 11 covers 1,314 attempted prop **side** records; 712 source-certified sides; 602 rejected at source/market gates; 356 unique accepted player–stat–line contracts; **354 official verified settlements** (NBA 250 from five games; NHL SOG 104 from seven games); two unverifiable NHL contracts. This is **one** calendar slate date, not 354 independent experiments.

**Separate cohorts MUST stay separate.** November 11's scheduled morning job recovered a different *earliest archived* original batch, 1,310 side rows and 1,248 settled side rows representing 624 paired contracts (NBA 502, NHL 122). Its *old* report has tautological 50% average hit and model probability from scoring both Over and Under. A corrected canonical-contract scorer and online coherent Over-v2 posterior were merged in PR #110 and connected Deepnote was updated **after that historical morning run**; do not mislabel the morning output as having already used the newly updated code. The earlier cohort is not retrocertified by the later strict 712-side batch.

Independent canonical final sidecar:
`reports/phase15_Nov11_original_certified_final_consensus_independent_model_audit_v3.json` (SHA `25dbe8152c1572d0d91689f94b2e79cf0c3d03becabb82514dd79d4633201ed0`). Original source sidecar:
`pickem_runs/2026-11-10/20261110T180409Z/model_comparisons.jsonl` (SHA `65ec6f549d32aa735999841c42f10941cd75aa811ddd7e9d9d2ee8e98ba67921`).
Strict original bundle: SHA `76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6`.
Verified real source and model receipts: `reports/phase15_20261111_full_independent_NBA_NHL_audit.json` and `docs/V25_FULL_NOV11_FORENSIC_AUDIT_AND_PHASE2_GATE.md`.

### Proper probability scores by model, original exact matched market comparison

Lower Brier is better. Market comparisons below are computed **only on exactly matched model-eligible contracts**, not across different eligibility subsets.

| Sport | Original model | Scored | Model Brier | Brier difference vs same-contract median book | Interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| NBA | Final 60/40 consensus | 146 | 0.239755 | **−0.006808** | descriptive tentative improvement |
| NBA | Bayesian B | 225 | 0.238575 | **−0.010406** | best measured market-relative NBA Bayesian shadow |
| NBA | Bayesian A | 221 | 0.240822 | **−0.007648** | tentative improvement |
| NBA | Engine A | 250 | 0.260115 | **+0.011515** | weaker than same offers |
| NBA | Engine B | 250 | 0.250223 | **+0.001624** | close to but worse than market |
| NHL SOG | Final 60/40 consensus | 102 | 0.263987 | **+0.013588** | weaker than market in 6/7 event clusters |
| NHL SOG | Engine A | 104 | 0.255701 | **+0.006148** | weaker than matched market |
| NHL SOG | Engine B | 103 | 0.272385 | **+0.021991** | weaker than matched market in **7/7 event clusters** |
| NHL SOG | Bayesian B | 102 | 0.260809 | **+0.010411** | weaker than same offers |
| NHL SOG | Bayesian A | 102 | 0.264915 | **+0.014516** | weaker than same offers |

**No statistical edge claim:** NBA only five games, NHL only seven, one calendar date; same player/game NBA combination stats overlap. The NBA 60/40 consensus was available only on 146/250 official NBA contracts; its lower Brier cannot be extrapolated to all 250. Source rejects are 602/1,314 (=45.8%) side attempts. Both NUTS models are unavailable on the original source cohort; do not impute their output. Bayesian A/B NBA refuse 29/25 lines respectively due to negative-support invalidity; do not silently clip them. There are zero ≥80% original final 60/40 consensus forecasts on these accepted scored cohorts; historical simple controls with 80%+ probabilities substantially underperformed their claims. Current financial/pick'em operator payout evidence is insufficient to infer profit.

## B. Mathematical and engineering audit

1. **Opportunity distribution > arbitrary complexity.** Historical median game minutes/TOI and volume are not a full pregame distribution for player on-field participation, role, team opportunities or share. NBA combos reuse shared opportunities; do not model them as independent final counts. NFL carries/targets and teammates must obey a constrained team-volume allocation, with a separate active/available probability. Do not leak target-game snaps, routes, final score, QB injury or game totals into pregame state.
2. **Means versus tail variances need separate hypotheses.** The November 10 Poisson count residual ratios (recent-rate NBA 2.267, NHL 1.889) reflect *both* conditional overdispersion and mean/role misspecification. A cheaper fixed-shape NB2 SOG shadow (shape 4.0, same pregame mean) is correctly a *single-factor* prospective challenger, not a fitted solution. Do not tune NB2 shape on the test slate.
3. **Calibrating a mean probability is not enough.** Selection at 80% must separately report its count, mean claimed confidence, observed hits, both sides, confidence intervals clustered by date/game and coverage. A whole-season Brier improvement may coexist with a useless or heavily Under-biased top tail. No Tier2 shortcut from historical nominal confidence.
4. **Calibration must be genuinely prequential.** Only outcomes from completed **earlier** weeks may alter any probability mapping used for the next week. Logistic/Platt recalibration may reduce signed bias without improving structural opportunity direction; compare both Brier and log loss and keep the raw baseline in parallel. Do not fit a calibrator over the whole retrospective year then evaluate the same year.
5. **Reliable original identities and timestamps.** Preserve original player IDs, team/opponent, stat, period, quote line, bookmaker, event ID, run ID, original capture time, fit cutoff, raw SHA and offer candidates. Original collector possession is not the same as independently proven provider publication. A separate official NHL current-roster pre-event membership check is now implemented as a SOG research shadow; membership is not starting/participation evidence.
6. **Missingness is a forecast event, not score=0.** Retain all prepared candidates, rejected source records, forecast abstentions, postgame nonparticipation and unresolved identity. Score a contract once, not each complementary side as a separate pick, and do not force 0.5 average Over hit/mean P as a directional report. Conditional-no-push probabilities must be complementary.
7. **Economics separate from model Brier.** The sportsbook no-vig reference is an observational baseline; source timestamp and actual executable pick'em operator payout/tie and payout schedule are needed before any profitability/Tier release.

## C. What 2023 and 2024 NFL historical sources already prove and do NOT prove

The existing `docs/BLIND_HISTORICAL_CAMPAIGN_SCOREBOARD.md` and Deepnote sealed runs `b86cbadf-4787-485b-a959-da358a2db1ce` (2023) and `260756a9-2503-442d-adf7-e4672587c765` (2024) verified an isolated forecaster was withheld settlement labels on 45 selected dates per season for NFL **tackles + assists** at fixed synthetic/role-median research thresholds:

| Season | Prepared | Settled | Unmatched | Challenger Brier | Frozen control Brier | Challenger directional accuracy | Control directional accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023 | 4,310 | 2,948 | 1,362 | 0.209249 | 0.211357 | 67.74% | 67.16% |
| 2024 | 4,598 | 2,978 | 1,620 | 0.214904 | 0.215679 | 66.62% | 66.35% |

Brier difference 2023 `−0.002108`, date-cluster 95% CI `[−0.005547,+0.001226]`. Brier difference 2024 `−0.000775`, CI `[−0.003434,+0.001775]`. Neither proves an improvement in *proper probability quality*. Historical source availability approximated postgame kickoff plus 18h, **not authenticated actual pregame availability**; no real bookmaker quotes, original 60/40 or executable lines. The unmatched 31.6% of 2023 and 35.2% of 2024 predictions are not failures or hits and are likely selection-dependent. Even isolated sealed testing does not qualify those seasons as genuinely new holdouts **now**; both years' outcomes have been repeatedly inspected.

The separate **2024 18-week, 11 volume-market** historical research report `reports/v25_2024_all11_volume_global_role_20261110_v2_exact_identity/INDEPENDENT_AGGREGATE_AND_LEAK_AUDIT.json` contains 38,809 matched evaluations. Brier raw `0.249338`, global prior-week calibration `0.242023`, role prior-week calibration `0.241051`. Nevertheless, role-calibrated ≥80% confidence selects **565** at **64.42% actual hits**, **472/565 Under**. This is *not* a validated selection model despite better average scoring. The report explicitly states `historically_exposed_2024=true`, `source_lineage_certified=false`, and synthetic half-integer lines.

The newer `reports/v25_nfl_phase2_2024_true_participation_20261110_rerun/INDEPENDENT_AUDIT.json` shows a useful structural direction: on 4,249 historical 2024 target observations, snap-participation model raw Brier `0.255778` / ECE `0.128688`; *previous-week-only* global Platt calibration improves Brier to `0.238163` / ECE `0.019034`. However `true_original_pregame_capture_verified=false`, `uses_true_pregame_roster=false`, `uses_actual_receiver_routes=false`, `real_market_quotes_not_used=true`. The 2024 cohort was exposed to the model research process. Calibration improvement is therefore **retrospective descriptive evidence**, not a new sportsbook edge or production promotion.

### Rerun decision: narrowly defined YES

**Do not repeat the exact prior 2023/24 training and claim it is blind.** Instead run **one preregistered, strictly as-of 2023/2024 *regression suite*** once code and all source inputs are version-locked:

- **Stage 0 — immutable contract:** freeze comparator code SHA, historical feature/store digests, market list, synthetic line policy, seeds, season/week roster membership rules, full original candidate denominators, selection and exclusion reasons. Separate 2023 and 2024 seasons; label all models as retrospective research. Use all weeks with explicitly recorded data gaps, not cherry-picked good dates. Never manufacture real historical bookmaker odds where no authentic archived timestamped quote exists.
- **Stage 1 — 2023 regression:** initial fit only on seasons **strictly before 2023** (e.g. 2021–22 if original source coverage suffices). Score weeks 1–18 chronologically. Each week may update after the prior week is officially complete. Confirm pregame QB starter identity (backup QBs should not enter startup market pools without independent verification), active/DNP probability, prior snap/route history, role/team opportunity and exact as-of injury provenance. No actual week outcomes or postgame QB changes in features.
- **Stage 2 — 2024 regression:** same frozen models/hypotheses, initial training cutoffs strictly before 2024 (prior 2021–23 history if available), no current/future week observations. Preserve both player-level and team-level target share conservation. Add QB rush attempts and yards only if both source identities, pregame starter/role and genuine historical observation semantics exist. Unsupported market should be *abstained* rather than quietly omitted.
- **Stage 3 — matched multi-family comparison:** same exact player/game/stat/line/side/period and same scoreable denominator for each pair of models. Hold fixed Engine A, Engine B, frozen 60/40, Bayes A/B and appropriate count/participation controls when actually reconstructible; no manufactured historical NUTS or bookmaker probabilities. Report one-contract Brier/log loss, raw and prior-week-only calibrated, calibration by stat/position/role, Over vs Under, winner confidence ≥70/80/90, DNP/absence, coverage, arbitrary threshold and job runtime.
- **Stage 4 — falsification:** direct target and future-week leakage unit tests, shuffled postgame feature exposure, forced inactive backup QB, static versus changing defensive role, missing ID, API market quote identity, shift(-1), in-week rolling mean, current-game snaps and final offensive plays, and all-paired side score invariants. A single future-leak or postgame feature must fail the entire research gate, not produce a selectively improved scorecard.
- **Stage 5 — uncertainty and freeze:** date/week and game-team resampling; season-level replication; multiple-testing guard for 11–16 overlapping market categories and exploratory methods. Publish separate postgame independent audit receipts; retain every rejected candidate. No multiple run-and-pick-best approach after seeing scores.

**What qualifies as progress:** reproducible, leak-free chronology, wider pregame participation coverage, **lower proper scores than frozen comparators on matched contracts in *both* historical years**, no collapse of true confidence≥80%, stable QB starter/position stratification and honest abstention. Even a perfect historical regression **does not authorize production**, because original lines/capture are synthetic/retrospective and outcomes already influenced development. Genuine promotion needs distinct future prospective source-verified lines and independent nights/weeks; profit requires actual operator payouts.

### Decision as of 2026-11-11

**NEXT:** preserve running free Deepnote live prospective collector and the new no-training NHL NB2 research pilot; monitor next morning source-certified one-contract scorecard; prioritize NFL pregame role/participation and calibration source gates. Running the 2023/2024 regression is sensible **as a development QA**, after locking the new hypothesis and source manifest; doing another costly full NUTS or declaring it out-of-sample is not sensible. No historical blind or high-confidence Tier gate is reopened. NFL Phase 2 scientific/production gate remains separately blocked.

**Original source references:** `docs/V25_FULL_NOV11_FORENSIC_AUDIT_AND_PHASE2_GATE.md`, `docs/BLIND_HISTORICAL_CAMPAIGN_SCOREBOARD.md`, `reports/v25_2024_all11_volume_global_role_20261110_v2_exact_identity/INDEPENDENT_AGGREGATE_AND_LEAK_AUDIT.json`, `reports/v25_nfl_phase2_2024_true_participation_20261110_rerun/INDEPENDENT_AUDIT.json` in the connected Deepnote project.
