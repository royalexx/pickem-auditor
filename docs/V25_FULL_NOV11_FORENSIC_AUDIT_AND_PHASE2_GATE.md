# V2.5 full November 11 forensic audit — Why the NBA/NHL forecasts fail, and Phase 2 decision

**Decision, Wednesday November 11, 2026: NO-GO for a full Phase 2 architecture, production promotion, Tier 1/2 release or expensive NUTS restart. CONDITIONAL GO only for a tiny, preregistered and independently scored NBA/NHL shadow challenger using *future* dates and truly pregame factors.** The governing V2.5 master plan's formal **Phase 2 is NFL team-state/opportunity allocation**, not an automatically unlocked NBA/NHL simulator. No separate NFL Phase 2 scientific signoff is provided by this NBA/NHL audit.

**Evidence scope:** the first strictly source-certified 2026-11-10 NHL/NBA afternoon batch, not a synthetic or reoptimized backtest, plus its original separately archived, pregame finalized post-shadow production-model comparison file. Models are scored strictly on their original lines against official final player stats; source snapshots, real odds and all original exclusions are unchanged.

## 1. Immutable evidence, independent audit, repairs

| Artifact | Independent identification |
| --- | --- |
| Source strictly certified pregame bundle | `pickem_runs/2026-11-10/20261110T180409Z/live_pool_2026-11-10_afternoon_76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6.json.gz`; SHA-256 `76f8cabc512977ce33017e73c72b7708d452e5f5ec962b33d3ee7f91c75285e6` |
| Producing forecast code | Original `main` `e5635d8fd8444a3144174cf019924d2010cdbca8`, run stamp `20261110T180409Z` |
| Full source-verified official settlement collector | Deepnote `reports/phase15_Nov10_FULL_REAL_FINAL_official_capture_20261111_f3162e921187/` with source bytes, event/player/stat identity, SHA-256 and observed postgame collection clock. Audit repair code SHA `f3162e921187870ab776bb4c8f3ef1a9543b8512` |
| Fully settled Phase 1 replay | `reports/phase15_Nov10_FULL_REAL_FINAL_scored_phase1_20261111_f3162e921187.json`; bytes SHA-256 `c6811bebc6cf125211f994ba0228ce9638d2022b428ac9dde60567b295cd3d6c` |
| Phase 1.5 descriptive scoring | `reports/phase15_Nov10_FULL_REAL_FINAL_scored_phase15_20261111_f3162e921187.json`; bytes SHA-256 `e1636a40ffad609cd8dabbbd8f405ce37fb1a7867be10fec4b1046a883c62bd7` |
| Independent source-byte, player-stat, calibration, count-variance and historical-exposure replication | Deepnote `reports/phase15_20261111_full_independent_NBA_NHL_audit.json`; bytes SHA-256 `e136f283a369ec373703675fee5eee2b6cee08e7bb599d561079091d0e73fa90`; 354 official outcomes independently recalculated; 12 distinct game clusters, one slate date |
| Original pregame post-shadow final 60/40/Engines/Bayes/Market artifact | `pickem_runs/2026-11-10/20261110T180409Z/model_comparisons.jsonl`; original SHA-256 `65ec6f549d32aa735999841c42f10941cd75aa811ddd7e9d9d2ee8e98ba67921`; 712 exact paired side records, originally archived ~18:10:52 UTC before every event start |
| Independent final production sidecar model scores with both-side binding | Deepnote `reports/phase15_Nov11_original_certified_final_consensus_independent_model_audit_v3.json`; SHA-256 `25dbe8152c1572d0d91689f94b2e79cf0c3d03becabb82514dd79d4633201ed0` |
| Separate morning reporting audit, **a different first-archived cohort** | `reports/phase15_morning_first_archived_nov10_anti_tautology_audit_20261111.json` and `reports/phase15_morning_policy_complement_and_market_pair_audit_20261111.json` in Deepnote. **Do not merge its 1,310 original side rows with the later certified 712-side sample.** |

**All 356 original paired player/line contracts remain in the denominator**: NBA 250, NHL SOG 106, from 1,314 prepared forecast sides (712 accepted, 602 excluded before scoring). Strict source/odds filtering removed **45.81% of proposed sides**: 438 unpinned external context, 164 missing/unverified market. Excluded candidates were **never counted as failed bets or silently dropped from the attempted ledger**.

**354/356 real official settlements**: 250 NBA and 104 NHL, 160 Overs and 194 Unders. Two NHL cases are quarantined without manufacturing zero: (1) original Dawson Mercer `8482110` offered as **NJD**, but official final roster has **WPG** (source market and original frozen quote supplied the stale team); (2) NHL `8476979` absent from the official final game boxscore; status is unknown/DNP, not scored. Source snapshots cannot be retroedited.

**P0/settlement bug fixed:** NHL's public API treats both `FINAL` and `OFF` as completed games. The original collector accepted only `FINAL`, thus left all 106 NHL contracts pending on November 11. Patched *both* schedule-state and boxscore-state final-only gates to `(FINAL,OFF)`, with new tests that `CRIT`/`LIVE` remain unscored. This recovered 104 verified NHL settlements; not a predictive-model change. See NHL public schedule/boxscore API documentation (`api-web.nhle.com`). 13 initial targeted suites had passed before the patch; the independent full re-run and additional final/CRIT tests passed on audit branch.

## 2. Honest model performance — one entire, independently source-matched slate

### Shadow simple count baselines vs original single-book no-vig reference

| Sport | Settled | Recent-five Poisson Brier | Pooled historical Poisson Brier | First-book no-vig Brier |
| --- | ---: | ---: | ---: | ---: |
| NBA (8 categories) | 250 | **0.285866** | **0.261735** | **0.250012** |
| NHL shots on goal only | 104 | **0.286591** | **0.256158** | **0.250644** |

All respective simple models lose on both Brier and log loss: NBA log loss `0.7940/0.7237` versus `0.6932`, NHL `0.7814/0.7067` versus `0.6945`. The market is **not** a single homogeneous consensus here: Phase 1 selects one originally archived book according to stable book order (187 FanDuel, 161 Pinnacle, eight DraftKings contracts). The later post-shadow comparison file independently contains a *multi-book median* no-vig reference. Do not treat those as interchangeable scores or line histories.

**High-confidence failure (counterfactual controls, not previously issued bets):** NBA recent-history Poisson confidently chooses 34 contracts at ≥80%, averaging **87.91% confidence**, and wins **22/34 = 64.71%**. NBA pooled selects 20 at average **86.07%**, wins **14/20 = 70%**. NHL recent selects eight at average **86.24%**, wins **3/8 = 37.5%**. The pooled NHL rate never crosses 80%. Correlation and one date preclude Tier claims, but **not one of these groups supports Tier publication or model promotion**.

**The overall Over/Under bias is *not* a single global correction.** NBA recent-history forecasts average P(Over) 48.20% versus 44.8% observed, signed error +3.40 pp; NHL 49.35% versus 46.15% observed, +3.19 pp. By NBA market, the signed error varies sharply: **assists +18.78 pp**, **PRA +18.76 pp**, **three-pointers −14.11 pp** (recent-history only, exploratory cells). A single global confidence multiplier or Under/Over correction would conceal opposite per-stat defects.

### Actual original pregame final 60/40/Engine/Bayesian sidecar — **distinct from the simple controls**

The Phase 1 evaluator reported **zero original finalized V1** because its adapter read only the initial **pre-shadow preview**. A separate, archived `model_comparisons.jsonl`, generated *before* the games and independently matched to all 712 original sides, contains a **post-shadow finalized** 60/40 production artifact. This is a distinct historical artifact; scoring it does not rewrite the preliminary original snapshot or assert a result existed earlier than its actual archive time.

| Sport / model | Scorable paired contracts | Brier | Same-contract median bookmaker Brier | Brier difference vs median bookmaker |
| --- | ---: | ---: | ---: | ---: |
| **NBA Consensus 60/40** | **146** | **0.239755** | **0.246562** | **−0.006808** (favors model) |
| **NBA Bayesian B** | **225** | **0.238575** | Matched (see receipt) | **−0.010406** |
| **NBA Bayesian A** | **221** | **0.240822** | Matched (see receipt) | **−0.007648** |
| **NBA Engine A** | **250** | **0.260115** | **0.248600** | **+0.011515** |
| **NBA Engine B** | **250** | **0.250223** | **0.248600** | **+0.001624** |
| **NHL Consensus 60/40** | **102** | **0.263987** | **0.250399** | **+0.013588** |
| **NHL Engine B** | **103** | **0.272385** | Matched (see receipt) | **+0.021991** |
| **NHL Bayesian B** | **102** | **0.260809** | Matched (see receipt) | **+0.010411** |
| **NHL Engine A** | **104** | **0.255701** | **0.249552** | **+0.006148** |

**Do not assert the entire production system is uniformly bad**: the NBA consensus and two NBA Bayes shadows **beat the market descriptively on their own matched, abstention-filtered contracts**. NBA consensus beats the median bookmaker in four out of five games; NHL consensus loses in six out of seven games and NHL Engine B loses in **seven out of seven**. These are **one-date exploratory results**, with market-relative gains that can reflect selection, noise, multiple model comparisons or one event. They are not proof of predictive edge or a go-live green light. NUTS remains unavailable on all **356** original contracts.

### Coverage/reliability bias

NBA post-shadow final 60/40 is available on **146/250 = 58.4%** of original certified player/line contracts; the other **104** are withheld by `source_engine_reliability_gate`. NHL finalized 60/40 is available on **104/106** original contracts, of which **102** have safe settled results (two source-identity exclusions). A result for the selected 146 NBA contracts **cannot be generalized to all 250** without explicit abstention/coverage assessment.

NBA Bayesian A abstains on **29/250** and Bayesian B on **25/250** contracts due to `normal_predictive_negative_mass` — a mathematically inappropriate negative-support risk for an unsigned count distribution. NHL Bayesian A/B each abstain on two original contracts for other explicit reliability reasons. The guard correctly prevents invalid predictions, but the **predictive family/support choice sacrifices coverage and is a priority for a proper discrete/nonnegative challenger**. Forecasts with invalid support must remain blocked, not clipped or silently renormalized. The historical NUTS sidecar has no accepted population model.

## 3. Why the simple probability distributions fail

1. **Poisson variability assumption is too narrow for the observed residuals (mechanism plausible, not proven causal).** Independently recomputed exploratory Pearson count-dispersion ratios, `mean[(actual − predicted_mean)^2 / predicted_mean]`, are **2.267 NBA recent** and **1.889 NHL recent** (1.0 is the ideal reference under a correctly specified Poisson mean). Pooled history reduces them to **1.946 NBA** and **1.320 NHL**, but they remain above 1. NBA points 3.293; points+assists 3.704; points+rebounds 3.659; PRA 3.055. The excess includes mean/role misestimation and player heterogeneity, **not exclusively conditional overdispersion**. A NB2/gamma-Poisson or event-level mixture is a reasonable *future shadow hypothesis*, not a proven cure.
2. **Baseline window and nominal peer shrinkage are being confused.** `v2/nhl_nba_phase1.py` builds recent rates from **last five** eligible games but constructs the “pooled peer shrink” using **ALL** available historical player games plus a constant 20-minute peer exposure prior. Independently computed median peer prior effective weight is only **1.049%** (mean 1.547%, range 0.639–8.734%). Thus the pooled baseline's lower Brier is driven primarily by **longer time aggregation**, not materially by role-/position-informed shrinkage. **All 356 position priors are actually unknown**, so the label cannot justify a true hierarchical role-specific model.
3. **Opportunity is a last-five median workload, not a predictive role/lineup distribution.** Freezing old exposure avoids temporal leakage, but it is not a forecast of minutes, injury participation, player share, opponent game state, team possessions or allocation. On the earlier verified 47 NHL contracts, a postgame actual-TOI oracle yielded only modest improvement, indicating TOI error alone was not sufficient in those three games. Actual TOI is not a legitimate pregame feature. No authentic frozen four-factor participation/team-volume/share/efficiency vectors exist for November 10, so Shapley/causal claims remain blocked.
4. **Composite NBA stats are not independent counts.** Points+rebounds, points+assists, rebounds+assists, PRA all reuse the same player's minutes/role and overlapping raw contributions; stand-alone Poisson treatment ignores conditional efficiency, minutes volatility and cross-stat covariance. There are **250 NBA contracts but only 47 distinct players and five games**, so apparent 250-sample calibration is deeply dependent.
5. **Early-season roster/availability identity is not independently cross-checked pregame.** The frozen real-odds market feed itself labeled Dawson Mercer as NJD, while the final NHL source roster had him on WPG. Structural source integrity/bytes passed while the player/team fact was stale. An independent **PRE-EVENT** NHL roster/lineup source is mandatory to exclude those contracts before ranking. The postgame check cannot retrovalidate an old quote.
6. **Unresolved market coverage and missing component forecasts are not random.** Only 356/657 prepared paired contracts survive strict source/market gates, NBA 250/529. The original 602 excluded sides must be reported, and the accepted cohort cannot stand in for the entire offered slate.
7. **The market benchmark is strong but not an economic target by itself.** Original sportsbook de-vig prices are timestamped references, not the pick'em operator's actual available multi-leg payout or selection rules. No eligible/executable payout receipts exist, so there is **no demonstrated bankroll edge**, even if a same-date Brier difference favors one NBA model.

## 4. A separate, serious morning report diagnostic defect

The scheduled morning workflow (Deepnote daily notebook `932674d66d4543c6b10ff2e2c0a4df9c`, code block `335f82164f2742df946876d1c9a2bc4f`) restores the **earliest** Nov 10 archived pregame bundle with **1,310 original side predictions**, not the later repaired strict-certified 712-side source. It writes `settled_model_predictions.jsonl` with **1,248 Over/Under side rows = 624 distinct paired player/line contracts** (NBA 502, NHL 122). That derived table **drops original event_id and player_id fields**, making direct player/team event lineage weaker, although the producing notebook originally uses IDs for joining.

Its `morning_model_validation.json` says `avg_probability: 0.5` and `observed_hit_rate: 0.5` on each two-sided stat market by construction: both opposite sides of the *same* fully settled contract were averaged. **This is a 50% paired-side tautology, not the hit rate of recommended picks.** Brier/log loss on both complementary sides can be mathematically valid, but their display/selection interpretation is not.

After independently pairing all **624** complete original side pairs and recalculating scores, the morning audit also found that the **online Bayesian A/B research shadow** violates `P(Over|nonpush)+P(Under|nonpush)=1` for **100% of its available paired rows**: mean sums of **1.0646/1.0895 in NBA** and **1.0830/1.1015 in NHL** (online A/B respectively). Other engine/bayesian/production-side pairs are coherent. The online models need a single shared nonpush CDF/settlement distribution, or must be marked **invalid for proper paired probability comparison**. These *online* shadows are **not** the actual released 60/40 production policy, so do not blame the production NBA/NHL model for their separate defect.

**Required independent fix ticket before trusting the morning presentation:** preserve original IDs and timestamps in settled per-side export, add canonical one-contract/one-score directional and confidence-band output, audit exact Over/Under complementarity, keep matched coverage/abstentions, and report first-archived historical cohort separately from the later strictly certified batch. Do not reselect whichever archive performed best after looking at outcomes. This report documents the defect, but does **not** modify the scheduled daily notebook during a forensic audit.

## 5. Scientific power and signed Phase 2 decision

**Unit of dependence is game/date and, for NBA combos, player/game — not individual leg.** All 354 completed contracts are from one slate date, five NBA games and seven NHL games. Neither overall “n=354” nor nominal 80% confidence sample counts grant independent Tier power. No valid date-cluster bootstrap exists for *one* date. Five/six/seven event-level game signs are descriptive, not definitive. Multiple exploratory models/statistics and prior design exposure further weaken any naive p-value claim.

**Operational integrity**: complete for source-backed 354 official settlements and all 356 candidate denominators, with two specific pending/identity flags. The NHL `OFF` final-state repair passes negative-control tests. Do not claim a specific source/model is error-free outside this batch.

**Predictive performance**: no broad release. NBA final 60/40 and Bayes A/B have *tentative* same-date positive evidence on matched eligible contracts, while NHL (particularly qualitative Engine B) underperforms. The newest posterior NUTS is unavailable; the role-factor causal decomposition remains unmeasured.

**Economic edge**: **blocked** by genuine operator payout and prospective independent validation.

**Full Phase 2: NO.** The governing Phase 2 concerns **NFL** team/game-state and constrained opportunity modeling. This NBA/NHL one-date audit neither validates that NFL investment nor justifies a broad NBA/NHL multi-agent simulator. **Small research-only challenger: conditional GO**, once model family, training cutoff, stat-specific baseline, original timestamp and independent evaluation horizon are preregistered:

- **NBA**: correct the nonnegative-support likelihood; test count dispersion and heterogeneous minutes/role with a small negative-binomial or hierarchical count challenger; keep legitimate Bayesian B and actual final 60/40 as **read-only benchmarks**, not deleted or promoted. Build only for stats where matched repeated dates identify the failure.
- **NHL SOG**: prioritize independent pregame roster/team identity and rate/TOI evidence; run a constrained distribution/shrinkage shadow challenger on untouched future slates; test Engine B weight/quality versus simple A and market but never tune the 60/40 weight on this single outcome slate.
- **Tier/promotion**: maintain no Tier 1/2 release; independently power by game/date clusters with heldout weeks, selection yield, multiplicity and repeated looks. NUTS/heavy game simulation remain paused.
- **System QA**: repair morning one-sided ranking presentation, ensure coherent online Bayesian distribution or explicit abstention, persist genuine post-shadow final consensus separately from original preliminary snapshots and match it by exact original source/hash.

**Re-entry evidence:** new certified pregame slates on multiple distinct dates, individual source-verified final stats and original eligible/abstained denominators, fixed count-distribution comparison, genuine pregame four-factor receipts where attempting allocation/attribution, and paired uncertainty against the true no-vig market reference plus (separately) exact pick'em payouts for any economic claim.

**Rollback:** no model weights, existing source forecasts, production ranking, NUTS training, daily job schedule or high-confidence release state were changed by this audit. Phase 2 stays blocked in operational status. The only code repair is correctly interpreting completed NHL `OFF` along with `FINAL`, preserving rejection of `LIVE/CRIT` and all original immutable sources.
