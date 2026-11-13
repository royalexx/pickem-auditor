# Pick’em Auditor — V2.5 Master Implementation Plan

**Document ID:** PA-V25-MASTER-2026-11-09  
**Version:** 1.1 — Approved planning amendment (Phase 1.5 and evidence-first gates)  
**Prepared:** 2026-11-09; **revised:** 2026-11-10  
**Status:** Governing architecture and execution plan; Phase 1.5 diagnostic implementation exists in an **unmerged shadow branch** but is **not fully independently validated**, and Phase 0R operational certification is not established  
**Governing principle:** *Predict the game first; allocate opportunities second; generate player outcomes third; evaluate the decision last.*

> **Executive decision, revised November 10.** Keep the distribution-first, opportunity-driven, market-informed **joint game simulator as a conditional research direction**, not a preapproved implementation expense. **Phase 1.5 must determine which error sources warrant further modeling before Phase 2 architecture is selected.** The first objective is certifiable prospective evidence, followed by measurable marginal forecast improvement and separately evaluated economic edge. Preserve the old 60/40 system, Bayesian/NUTS outputs, source ledgers, settlements, and familiar model comparison chart as frozen diagnostic benchmarks. Never allow new complexity, favorable retrospective scores, or converged posterior sampling to substitute for point-in-time data integrity, statistical power, or prospective validation.

---

## 0. How to use this document

1. Treat Sections 1–5 as the **immutable design and statistical contracts** until a change request is accepted.
2. Treat Sections 6–9 as the **evaluation protocol, phased work breakdown, and release/investment gates**. Do not skip a blocking gate even when later modules are code-complete; Phase 1.5 supplies an *investment decision* before Phase 2, not a substitute for Phase 0R certification.
3. Treat Sections 10–12 as the **model experiment, audit, and operational contracts**.
4. Start the next workflow with the **revised, focused launch brief** in Section 13; first diagnose Phase 0R rather than requiring all repairs, a live run, and audit signoff in the first session.
5. Each workflow session must produce an updated status ledger: `completed`, `verified`, `blocked`, `shadow-only`, or `rejected`, linked to commit hashes and evidence. **“Implemented” and “validated” are different statuses.**

**Revision history:** v1.0 (2026-11-09) proposed the original architecture; v1.1 (2026-11-10) adds a mandatory Phase 1.5 diagnostic and Tier power protocol, separates Phase 0R diagnosis from repair, prioritizes parallel source capture, places explicit research stop/go gates before costly challengers, and corrects documentation of the current shadow implementation status. Unchanged v1.0 technical definitions remain in force where not superseded.

**Evidence levels used in this plan:**

- **Established project facts:** previous implementation reports, existing agreed policies, and supplied documents. Where live source state has not been independently re-fetched in this planning session, the next workflow must verify it.
- **Architectural decisions:** intended requirements for V2.5, not empirical performance claims.
- **Research hypotheses:** ZIDM, EFDM, Tweedie, CMP, Schaake/ECC, WDRO, Pathfinder, and more are **candidates**, not assumed upgrades.
- **Release gates:** acceptance requirements; no retrospective evidence may be relabeled prospective.

### 0.1 Current baseline to verify when the next workflow starts

| Item | Latest reported state | Action required |
|---|---|---|
| V2 Phase 0 foundational safeguards | PR #79 reported merged to `main`; 1,221 tests passed, 9 skips | Confirm actual branch/head, files, tests, and deployed behavior |
| Follow-on provenance repair | A later repair reported 1,224 passing tests and 9 skips | Confirm commit/branch/PR state; do not assume the repair was merged solely from test counts |
| Live November 9 afternoon collection | 1,490 forecasts, **0 certified** in the recorded check; 1,387 market quotes accepted, 658 rejected | Inspect exact artifacts and failure codes; execute a fresh certified dry run |
| Specific unresolved evidence | 18 items reached source capture but lacked event IDs; forecasts lacked accepted input-freeze timestamps; earlier failures also involved missing/imprecise `model_training_cutoff_at` | Repair all three fields and trace lineage across every producer/consumer |
| Forecast publication | Unvalidated Tier 1/2 authority suspended; legacy predictions retained as research/shadow | Keep the release gate fail-closed |
| NUTS historical training | Paused because of cost and incomplete validation | Preserve posteriors; do not resume automatically |
| Automation | Morning settlement enabled; afternoon research automation disabled as last reported | Inspect live schedules; do not silently re-enable or duplicate them |
| Deepnote history/bootstrap | Three tests previously could not run in an environment lacking `zstd` | Install/depend on `zstd` in suitable testing environment or mark a genuine environment-specific skip with evidence |
| 2024 rolling-origin evaluation | A subsequent archived synthetic-line replay contains 107,319 contracts, of which 71,009 were scored and 36,310 unmatched; 272 games over 18 weeks | Reconcile source SHA, outcome coverage, experiment exposure and scorer independently; **not** market-edge evidence |
| Phase 1.5 diagnostic implementation (Nov 10) | Isolated GitHub branch `chatgpt/phase15-error-power-diagnostics-20261110`, HEAD `aad99119283c154a9d8d5b7327fe52336dbe2b6a`; `scripts/phase15_diagnostics.py`, adversarial tests and `docs/PHASE_1_5_DIAGNOSTICS.md`; 19/19 tests passed in detached Deepnote run | Perform independent mathematical/code/data review, resolve test gaps, then open/review/merge PR as appropriate. **Not merged or released** by this plan revision |
| Phase 1.5 historical diagnostic result (Nov 10) | Model Brier 0.1928184 vs frozen research baseline 0.1951962; 92.8502% predicted Unders among matched synthetic-line contracts; 71,009 scored | Treat as **diagnostic and potentially development-exposed**, not market edge; reconcile under-skew and coverage; preserve frozen SHA receipts |
| Phase 1.5 structural-opportunity attribution | Oracle/Shapley decomposition code exists, but usable pregame-frozen component forecast inputs were **not available to the initial run** | Instrument valid pregame team volume, participation, share and conditional efficiency forecasts prospectively; **do not fabricate** missing values |

**Interpretation:** Phase 0 is **code substantially implemented, operational certification NOT complete**. The next workflow starts with Phase 0R-A diagnostic inventory and failure-code attribution. Phase 1.5 is **implemented, tested on historical synthetic-line evidence, but still awaiting independent review and authentic component-input validation**. These figures are dated checkpoints, not assumptions about the current live production state.

### 0.2 Evidence-first execution policy (new in v1.1)

Treat the project as three distinct claims: **(1) engineering integrity**—a source-certifiable pregame forecast; **(2) predictive skill**—better matched, chronological proper scores than simple baselines; **(3) economic edge**—prospective performance versus compatible real offers and complete payout terms. Passing one does not establish another.

Proceed on two safe parallel tracks: **Phase 0R-A/B certification repair** and **immutable prospective raw market/forecast source capture**. Raw evidence capture need not wait for every model-certificate defect to be fixed, but uncertified captures must stay explicitly uncertified; old data may never be retro-certified without authentic original evidence. Phase 1 diagnostic work can be done in read-only shadow mode, while no trusted publication or release step bypasses Phase 0R.

**Resource discipline:** Phases 0R, 1, and 1.5 are required foundations. Phase 2/3 are narrowly scoped, precommitted pilots contingent on Phase 1.5 evidence. Phases 4–8 are **research options earned individually**; later NHL/NBA extensions can continue via low-cost data collection even if an NFL simulator does not graduate. A failed or inconclusive challenger remains shadow-only; in the absence of demonstrable prospective edge, conserve compute and continue evidence collection rather than escalating complexity.

---

## 1. Objectives, scope, and hard rules

### 1.1 Primary objective

Produce correctly calibrated, reproducible **full predictive distributions** for player statistics and decision-grade probabilities at **real, captured pregame sportsbook contract lines**, across NFL, NHL, and NBA. The system must predict outcomes and abstain honestly when the data, model, or market evidence is unreliable.

The primary objective is **forecast quality and selective reliability**, not maximizing the number of picks, nominal model hit probability, number of modeled props, or simulation complexity.

### 1.2 Separate the three problems

1. **Forecast generation:** predict opportunity, efficiency, and distribution of the actual player statistic before the game.
2. **Probability extraction:** compute exact contract-specific `P(over)`, `P(under)`, and `P(push)` consistent with the forecast distribution and settlement rules.
3. **Selection/decision:** compare that probability against an actual product's pricing/payout, uncertainty, slate-wide multiplicity, and correlated exposures; choose, watchlist, or abstain.

A better selection policy may lower risk without improving the distribution. A better copula may improve multi-leg dependence without improving individual Brier scores. Evaluate these improvements separately. Phase 1.5 explicitly decomposes **team-volume, participation/role, allocation/share, conditional efficiency, distribution/tails, directional calibration, and selection** errors to identify the first useful modeling investment. Postgame actuals are permitted only in an isolated retrospective oracle **diagnostic**, never as pregame model covariates.

### 1.3 Non-negotiables

- Strict as-of-time reconstruction, immutable forecasts, and original-source receipts.
- Real, timestamped offers for market-performance claims; synthetic lines only for modeling diagnostics.
- Existing 60/40 model preserved unchanged as a frozen baseline; never treated as proven profitable.
- Legacy Engine A, Engine B, Bayesian A, Bayesian B, strict NUTS outputs, and market estimates remain inspectable when they exist.
- No Tier 1/2 certification until the new gate is satisfied on genuinely unseen data. Define all tiers by empirical reliability, not name or aesthetics.
- No conflation of uncertainty about the game outcome (aleatoric) with uncertainty about model parameters, regime, inputs, or estimation (epistemic).
- No paid data dependency. Prefer ESPN, existing Propline access where available, public official sports feeds, legitimate published lineup/injury information, historical collector archives, and the user's Dell CPU/local tooling.
- No reliance on paid GitHub Actions minutes, external coding agents, or repeated all-history NUTS fits to run a slate.
- No automatic production promotion. Versioned shadow experiments must pass locked validation gates. **No automatic escalation from a model pilot to an expensive simulator without a precommitted evidence-based continuation decision.**
- Never invent market implied probabilities from missing odds. Never infer a specific offered contract from a stat line alone.

### 1.4 Minimum scientific success definition

A promoted model must: (a) have zero critical leakage/provenance violations; (b) preserve statistic-specific constraints; (c) improve precommitted proper-score comparisons against a simple baseline on matched chronological data or demonstrate a separately specified, defensible operational advantage; (d) be competitive with a de-vigged market reference where valid two-sided quotes exist; (e) avoid material degradation in calibration and top-k selective reliability; and (f) demonstrate repeatability across independent time blocks and/or prospective slates. Do **not** claim positive financial edge unless payout-aware prospective evaluation supports it.

---

## 2. Architecture: components and interfaces

### 2.1 Canonical dependency graph

```text
Raw, timestamped sources / sportsbook quotes / historical outcomes
      |
      v
Immutable receipts + as-of-time feature store + contract/stat identity
      |
      +---------------------------> frozen V1 diagnostic predictions
      |
      v
Pregame context: lineup availability, role, opponent, weather, scheduled event
      |
      v
Latent game-state forecast: pace, possessions, score differential, pass/run,
                            special teams, overtime/period exposure
      |
      v
Finite opportunity pool: team attempts, routes, snaps, TOI, NBA minutes,
                         goalie shots faced, play/opportunity denominators
      |
      v
Constrained player allocation + structural participation/role changes
      |
      v
Conditional player outcomes: target -> catch -> yards; attempt -> shot;
                             shots-against -> saves; minutes -> event counts
      |
      v
Constraint-preserving joint game ensembles + conditional dependence
      |
      +--------> optional validated copula correction / source-linked news update
      |
      v
Distribution evaluation / market-informed *regularized* scenario weighting
      |
      v
Exact Over/Under/Push probabilities + parameter/input uncertainty
      |
      v
Chronological calibration + robust ranking + exposure controls + abstention
      |
      v
Immutable slate report / legacy comparison chart / next-morning settlement
      |
      v
Walk-forward scorecard, challenger tests, promotion or rollback decision
```

**No module may silently overwrite a distribution or alter already frozen predictions.** A transformation must be explicit, versioned, and audited.

### 2.2 Proposed repository layout (adapt to verified existing tree)

The exact folders are proposals, not assertions that they already exist:

```text
v2/
  contracts/{identity.py,source_receipts.py,market_quote.py,forecast.py,settlement.py}
  data/{asof_store.py,feature_builder.py,identity_map.py,validations.py}
  context/{source_registry.py,availability.py,role_updates.py}
  state/{nfl_state.py,nhl_state.py,nba_state.py,market_conditioning.py}
  opportunity/{nfl_allocator.py,nhl_allocator.py,nba_allocator.py,
               logistic_normal.py,zidm_challenger.py,role_transition.py}
  outcomes/{discrete.py,compound_yardage.py,nfl.py,nhl.py,nba.py}
  simulation/{scenario.py,nfl_joint.py,nhl_joint.py,nba_joint.py,
              conservation.py,copula_challengers.py}
  inference/{priors.py,pathfinder_benchmark.py,posterior_contract.py}
  calibration/{walk_forward.py,probability.py,regime_diagnostics.py}
  decision/{robust_rank.py,expected_value.py,portfolio.py,abstain.py}
  evaluation/{prequential.py,proper_scores.py,joint_scores.py,
              topk.py,confidence_intervals.py,leakage_tests.py}
  reporting/{comparison.py,research_audit.py,validation_manifest.py}
  registry/{candidate_registry.py,promotion.py,rollback.py}
  orchestration/{afternoon.py,morning.py,manual_run.py}
  tests/{fixtures,contract,integration,property,adversarial,statistical}
  configs/{experiment_specs,release_gates,model_manifests}
  docs/{V2_5_MASTER_PLAN.md,ADR,runbooks,source_inventory.md}
```

Reuse existing collector, settlement, and reporting functions rather than duplicating them. Keep a compatibility adapter to produce the existing comparison chart during migration.

### 2.3 Model families are plug-ins, not votes

- **Champion:** simple, leakage-safe historical rate or hierarchical baseline for the relevant statistic.
- **Candidate:** a statistically motivated improvement to a named mechanism (opportunity, outcome likelihood, dependence, context, or decision).
- **Research-only:** an advanced method without adequate data, evidence, or inference diagnostics.
- **Legacy V1:** frozen historical reference, never silently re-optimized as part of V2 development.

Do **not** average correlated candidates because they happen to exist. If stacking is later tested, it must be cross-fitted, regularized, trained strictly on prior out-of-fold predictions, and scored against simpler alternatives.

---

## 3. Data, probability, and reproducibility contracts

### 3.1 The immutable `ForecastSnapshot`

Each published or shadow forecast must include, at minimum:

| Category | Required fields and semantics |
|---|---|
| Identity | `forecast_id`, `run_id`, `model_id`, `model_version`, `contract_id`, `sport`, `league`, `season`, `event_id`, `player_id`, `team_id`, `opponent_id`, `stat_key`, `period`, `side`, `line` |
| Temporal | `event_start_at`, `forecast_at`, `decision_cutoff_at`, `input_freeze_at`, `model_training_cutoff_at`, `ingested_at`; all timezone-aware UTC timestamps |
| Market | `book`, `product_type`, `quote_id`, `quote_timestamp`, raw line, available payout/odds/multiplier and terms, quote receipt hash, de-vig method or `not_available` |
| Source lineage | Versioned feature manifest; source URLs/IDs; first-known-available timestamps; `published_at` where trustworthy; ingestion timestamps; SHA-256 content hashes |
| Model lineage | Training data manifest, last training observation, code commit SHA, model artifact checksum, hyperparameters, random seed, inference method, calibration version |
| Distribution | Named statistic support, mean, variance, quantiles, integer masses or CDF, scenario reference, prediction interval, `q_over`, `q_under`, `q_push` |
| Uncertainty | Epistemic intervals/sensitivity, source-confidence flags, scenario disagreement, effective sample size, calibration sample size |
| Decision | Eligibility, side, market probability if defensible, edge, uncertainty-adjusted grade, Tier/watchlist/abstain, explicit reason codes |
| Integrity | Schema version, read-only freeze hash, source-receipt status, time-leakage audit result, contract-complementarity audit result |

A **snapshot is never edited in place**. A later quote/news event creates a new forecast version; append a supersession link rather than replacing the original. A late settlement correction creates a new settlement version, preserving prior versions.

### 3.2 Timestamp protocol

For every feature record, use the **first defensible time at which it was accessible to the forecaster**. For official delayed statistics, publication and ingestion times may differ. An event's final result is not made available by virtue of its game-start date.

Enforce:

```text
source_available_at <= input_freeze_at <= forecast_at < event_start_at
model_training_cutoff_at <= input_freeze_at
quote_timestamp <= forecast_at
all model-selection/calibration labels end before that specific forecast
```

A timestamp may be absent only when the feature is explicitly excluded from eligibility. Never replace missing timestamps with optimistic defaults. Normalize precision and timezone before comparison. A model trained after a target event cannot be retroactively portrayed as having predicted it.

### 3.3 `MarketQuote` and quote policy

- Distinguish sportsbook offered prop price from market reference, consensus line, synthetic line, inferred fair probability, and hypothetical line.
- For the same player/stat/period, a `contract_id` must identify the **exact offered terms**; two books or changed lines create separate quote identities.
- Preserve all accepted and rejected quotes with reason and timestamp; duplicates must be deterministically resolved and logged.
- De-vig only where there are legitimate compatible two-sided quotes and a specified method; record whether a purported market probability is unavailable.
- Pick’em payouts are product-specific and can involve correlated legs, ties, voids, insurance/flex rules, or variable multipliers; do not treat an offered Over/Under line as a -110 wager by default.
- Retain offer availability, limits/eligibility if known, and quote age; older cached offers are not equivalent to live executable prices.

### 3.4 Probability and settlement policy

For the actual statistic `Y`, offered line `L`, and matching settlement convention:

```text
q_over  = P(Y > L)
q_under = P(Y < L)
q_push  = P(Y = L)
q_over + q_under + q_push = 1
```

Compute three probabilities from **one distribution and one frozen forecast**, not independently seeded Monte Carlo estimators. If using a finite ensemble, estimate both sides from the same exact sample and retain finite-M approximation uncertainty. Numeric analytic CDF evaluation is preferred where available.

- Document whether regulation/overtime counts, DNP/void, partial games, official corrections, combined tackle credits, goalkeeper status, and period markets are eligible.
- Never call voids pushes unless the actual product settles them that way.
- Check integer versus fractional lines, inclusive threshold definitions, zero support, possible negative yardage, and stat-specific caps.
- Record cross-provider stat discrepancies; use one authorized canonical settlement policy with an exception ledger.

### 3.5 Source verification and research extraction

Context analysis may use a source-linked LLM to **extract claims** such as `OUT`, `starter`, `probable`, expected role, line combination, game-day scratches, coordinator comments, and weather conditions. The LLM is **not permitted to invent percentage adjustments**. Every derived factor needs a documented typed transformation, provenance, timestamp, and uncertainty.

If no lineup report exists, use verified previously observed patterns (such as last 3–5 starting lineups) only as a **probabilistic prior**, never as confirmation of tonight's lineup. Conflicting sources increase uncertainty or trigger abstention.

### 3.6 Data-quality failure codes

At least: `MISSING_EVENT_ID`, `SOURCE_RECEIPT_MISSING`, `TRAINING_CUTOFF_MISSING`, `INVALID_INPUT_FREEZE`, `POST_EVENT_FEATURE`, `QUOTE_STALE`, `QUOTE_UNAVAILABLE`, `CONTRACT_IDENTITY_MISMATCH`, `DUPLICATE_FORECAST_ID`, `UNSETTLED_CONTRACT`, `STAT_POLICY_MISMATCH`, `MODEL_ARTIFACT_MISSING`, `SIMULATION_CONSTRAINT_VIOLATION`, `PROBABILITY_INTEGRITY_FAILURE`, `MODEL_UNVALIDATED`, `ROLE_UNCERTAIN`, `MARKET_NOT_COMPARABLE`.

Fail-closed means the relevant candidate is not certified; it **does not** mean deleting the record or quietly dropping it from evaluation denominators.

---

## 4. Statistical design specifications

### 4.1 Game-state forecast: the upstream distribution

The simulator must model a **distribution**, not a single deterministic pace assumption:

- **NFL:** offensive/defensive possessions, drives, team plays, pass/dropback tendency, attempts, sacks/throwaways, rush attempts, red-zone state, expected score differential, game clock, home/away, weather/roof, available personnel, and potential overtime.
- **NHL:** strength state, shots attempted/on-goal, even-strength/special-teams TOI, opponent shot generation, goalie starts/pulls, regulation and overtime exposure, team shot pace.
- **NBA:** possessions, team minutes (five players on court in regulation), rotation probabilities, overtime, shot opportunities, rebounds available, assists, team scoring environment.

Separate **pregame predictive inputs** from in-game realized state. Realized pass attempts, final score, playing time, and team totals are **outcomes**, not pregame features. If a market-informed conditioning layer is used, feed only an actually recorded pregame market quote or market aggregate.

#### 4.1.1 Market conditioning

Start with a physical/base distribution `P` from historical statistics and verified pregame context. When real market anchors exist, construct an optional, **regularized and limited** market-conditioned challenger `Q` by a KL/entropic projection:

\[
Q^* = \arg\min_Q D_{KL}(Q\|P) + \lambda\,\mathcal L_{market}(Q),
\]

where `L_market` accounts for quote uncertainty, market validity, feature overlap, feasible moment constraints, and relative weight learned on past folds. For finite scenarios, exponential tilting may be used and must report KL stress, effective sample size after reweighting, constraint fit, and feasibility.

**Never** hard-anchor a player's target prop to its sportsbook price when measuring model-versus-market disagreement. Prefer game-level anchors: spread, totals, team totals, available weather/scoring information. Include an **unconditioned version** to quantify incremental market value. Do not claim a risk-neutral financial martingale measure is a literal probability law of sports outcomes.

### 4.2 Finite opportunity pools and conditional exposure

#### 4.2.1 NFL passing example

```text
Forecast team possessions / plays
  -> team dropbacks / designed pass rate
  -> pass attempts + sacks + scrambles + spikes and related outcomes
  -> routes and receiver availability
  -> targets + throwaways / other unattributed attempts
  -> receptions conditional on targets
  -> receiving yards conditional on completed catches and signed gains
```

The target-allocation mechanism should satisfy `sum(player_targets) <= valid team attempts` under appropriate league accounting and include an unattributed category; receptions never exceed targets. A route projection is pregame latent exposure, not last game's realized routes.

**Research candidate, not an automatic champion:** hierarchical logistic-normal shares conditioned on player roles, personnel groupings, team/game state, availability, opponent and uncertainty. If Phase 1.5 provides adequate evidence that **allocation/share** error is material, test its softmax latent logits and residual category against simple hierarchical rate, independent count, and Dirichlet-multinomial controls. Until an appropriately matched chronological test supports replacement, **the simplest credible baseline remains champion**. If volume, participation, efficiency, tails or calibration dominate, fund those components first instead.

**Challengers:** a zero-inflated Dirichlet-multinomial allocation (ZIDM) for true structural inactivity versus sampling zeros; an EFDM mixture for flexible inter-player dependencies; continuous categorical for continuous shares, only if its likelihood and sampling semantics suit the variable.

**Staged ablations if allocation is justified:** first independent Poisson/NB player targets, standard Dirichlet-multinomial, and logistic-normal; then ZIDM only for material structural-zero failure; EFDM only if simpler alternatives leave a measured dependence/interaction gap and enough observations. Different techniques may win for different sports or stat groups. Do not migrate solely because one paper reported improvement in another domain.

#### 4.2.2 Other NFL opportunity paths

- **QB attempts/completions:** dropbacks and attempt accounting, completion probability conditional on attempt/pass depth, potential early exits, personnel and score conditions.
- **QB passing yards:** completions × signed pass gains, with rare-event tail behavior; avoid Gaussian negative-mass artifacts without prohibiting legitimate negative values.
- **RB carries/rushing yards:** rush-play pool, player carry share, signed per-carry gains, kneel-down handling and stat conventions.
- **NFL tackles + assists:** opponent offensive snaps, player defensive snap share, alignment, tackle opportunities, chance to be credited solo/assisted, scorekeeper effects; shared tackle credit is **not** a simple mutually exclusive receiver-style allocation.
- **Defensive props:** align opportunity sources with pressure, coverage, snap and event structure when public data allow; do not impute tracking-level facts absent from the source.

#### 4.2.3 NHL and NBA paths

- **NHL shots on goal:** roster/line exposure, TOI by strength, team attempts, player share, on-target probability, empty-net/blocked shot definitions, score-state effects.
- **NHL hits/blocks:** TOI, opponent possession and event opportunity, role, official-stat/arena measurement differences. Existing hits NUTS mixing concerns are not proof that hits are inherently unpredictable; require held-out comparisons.
- **NHL goalie saves:** probability of start, goalie exposure, shots against, save probability conditioned on shooter/shot context if available; goalie pull/early exit scenarios explicitly.
- **NBA points/assists/rebounds/combos:** minutes and lineup states, possessions, usage/touches, shot and free-throw volume, conversion, rebound opportunities, assist generation, and correlations. A combo prop should use one coherent joint draw, not a sum of independently estimated probabilities.

### 4.3 Role-transition counterfactuals

Verified lineup and role changes should enter the **same upstream opportunity model**, not separately inflate Engine B after market conditioning. Avoid double-counting injury effects.

Baseline: hierarchical peer/position prior + player old-role history + opportunity-specific event covariates. Research challenger: **distributional synthetic control** using past comparable pre/post role transitions and Wasserstein quantile barycenters. Donor matching and weights must be constructed using only information available at the historical forecast timestamp; no post-transition outcomes from the target game or future donor season may leak.

Never treat pseudo-donor information as additional independent observed player games. Estimate donor and counterfactual uncertainty honestly. The old rigid current-role sample-size rule can be replaced only after showing that calibrated conditional predictions are reliable in early-transition cohorts. If insufficient evidence exists, retain an explicit abstention path.

### 4.4 Conditional outcome distributions

Preserve sport/stat-specific supports and mechanisms:

| Family | Default candidates | Advanced challenger | Key check |
|---|---|---|---|
| Attempts, SOG, blocks, tackles | Poisson/NB, binomial exposures, hurdle where needed | CMP; sparse Poisson-lognormal | Under/overdispersion, structural zero, support and tail mass |
| Targets/receptions | Multinomial allocation + binomial catches | ZIDM/EFDM; beta-binomial conversion | Totals, caps and dependence |
| Receiving/rushing yardage | Signed marked-play mixture, conditional empirical/parametric gains | Tweedie only for nonnegative compatible component | Legitimate negative plays, mass at zero, upper tails |
| Goalie saves | Shots-against distribution + conditional save counts | Hierarchical correlated shot/save model | Shots faced minus allowed goals consistency, pull/empty net conventions |
| NBA points/assists/rebounds | Minutes-conditional event count and conversion | Distributional boosting / correlated residual model | Minutes, overtime, multi-stat correlation |

The report's Tweedie compound Poisson-Gamma is attractive for nonnegative zero-heavy components; **do not** use it to erase negative NFL gains. CMP is an option for count dispersion; do not automatically replace every NB model. A sophisticated distribution is not a substitute for correct opportunity exposure.

### 4.5 Joint simulation and dependence

The default simulator should generate each game's **shared latent state once** and then produce all affected players/stats conditionally. This is the mechanism enforcing coherent game paths.

Add an **empirical dependence challenger** inspired by Schaake Shuffle / ECC / dECC. Recommended initial form: apply rank dependence to compatible, pregame-context-matched latent residuals or other conditional quantities **inside** the simulator. Do not independently shuffle final player target counts if that breaks the team-total allocation.

Template matching must use only previously observed games and pregame-known context. Role-based matching should avoid identity leakage. Train/test historical dates remain separated.

Coupling is evaluated with marginal Brier/log-loss/CRPS **and** multivariate Energy Score, Variogram Score `VS_0.5`, observed multi-leg joint-event calibration, and conservation tests. A finite scenario ensemble is approximate; do not claim machine-precision CDF coverage merely because sample ranks are permuted. Entropic reweighting may change marginal probabilities and must be revalidated after coupling.

### 4.6 Statistical inference and computational policy

1. Reuse validated historical hierarchical posteriors only as **optional priors or diagnostic forecasts**, respecting their original training cutoff and convergence/predictive validation.
2. **Pathfinder benchmark:** compare multi-path Pathfinder to existing accepted NUTS posteriors on selected smaller submodels. Track gradient evaluations, CPU minutes, memory, posterior moments, tail probabilities, PSIS Pareto-k, diagnostics and OOS forecasts. An acceptable Pareto-k is **not** sufficient proof of posterior accuracy.
3. If a model needs NUTS, retain meaningful warmup/adaptation; Pathfinder initialization does not automatically remove that requirement.
4. Avoid repeating multi-season NUTS daily. Freeze/version fitted priors and update current context with cheap prediction steps; retrain only when predetermined drift, schedule, or validation logic justifies it.
5. Research challengers only after prerequisites: sparse Poisson-lognormal networks when data support residual correlation; Hawkes/CHIP only with identifiable event timing or justified aggregated-network structure; Dirichlet Flow Matching only if simpler simplex models demonstrably fail.

**Do not transplant numerical power-grid capacity percentages into sports.** Use learned sport/player capacity effects and physiological constraints only when supported by data.

---

## 5. Calibration, decisions, and reporting

### 5.1 Probability calibration

Validate marginal predictive distributions and threshold-event probabilities separately. Maintain prequential calibration groups by sport, market, line region, side, role stability, sample size, player exposure, and model disagreement; use shrinkage where cohorts are small. Measure directional skew, including the project's prior excessive Under concentration.

Candidate calibrators: uncalibrated distribution, regularized Platt/logit or Beta where appropriate, isotonic only with sufficient data, and distributional calibration when coherent. All calibrators must be **cross-fitted using past predictions**, never trained on the same forecast/outcome pairs being graded. Track whether calibration improves Brier/log-loss and whether it damages tails or small regimes.

Conformal techniques can supply intervals or reliability checks under specified conditions; conformal coverage is **not** inherently a calibrated probability that a particular Over will hit. Regime-switching models are optional challengers with explicit minimum sample and change-point validation.

### 5.2 Conservative decision model

For each eligible contract produce:

- `q_nominal`: calibrated point-estimate event probability.
- `q_interval`: uncertainty over that probability using predictive/bootstrap/posterior uncertainty where defensible.
- `q_robust`: a validated conservative score, initially a simple uncertainty lower bound; Wasserstein DRO is a challenger.
- `p_market`: comparable no-vig probability **only** when identifiable from actual compatible prices; otherwise `null`.
- `edge`: difference between calibrated estimate and comparable market baseline, not a guaranteed profit.
- `EV`: payout-aware expectation computed only if full relevant terms are known.
- `status`: candidate, watchlist, abstain, invalid, or shadow-only; release/Tier status separately.

Implement **Wasserstein distributionally robust optimization** (WDRO) as an experiment around the nominal outcome distribution, with ambiguity radius learned/selected on past folds and conditional on data amount, disagreement, and source uncertainty. Compare it to a simpler confidence-bound ranker. Never advertise WDRO as automatically eliminating the winner's curse.

### 5.3 Ranking

Rank the **complete eligible universe**, not only prefiltered high-confidence outcomes. Preserve the top-10 candidates per sport, including explanations of (i) baseline opportunity, (ii) recent versus longer-window hit and stat history, (iii) role and matchup context, (iv) opposing model probabilities, (v) market reference/terms, (vi) uncertainty and abstention reason, and (vii) correlated exposure to other ranked props.

Report model disagreements without interpreting agreement between redundant historical models as independent confirmation. Analyze top-1, top-5, top-10, every candidate, both Over/Under sides, and abstained contracts. Assess whether selecting many props biases observed hit rates upward or downward.

**Tier policy:** Existing unvalidated probability thresholds remain suspended; provisional tiers may be produced for research only. Promotion requires locked empirical high-confidence cohorts, sufficient **effectively independent** events, calibrated coverage, sensible uncertainty intervals, and payout-aware metrics when odds exist. Tier 1 should remain genuinely exceptional; Tier 2 should not be labeled “>80%” unless that high conditional hit rate is empirically supported. **Phase 1.5 exact-power calculations are planning aids, not Tier approvals**; game/date correlation, adaptive top-k selection, multiple tiers and repeated looks must be addressed in the final preregistered design (Sections 6.6 and 7, Phase 6).

### 5.4 Portfolio/multi-leg analysis

For multi-leg products, compute joint payout expectations from the **same game/league simulations** and the offered product payout matrix; include over/under pushes and correlated legs. Disallow naive multiplication of marginal win probabilities for correlated same-game legs. Enforce stated product availability, disallowed combinations, and incomplete-payout abstention. This may be built after reliable single-contract forecasting; it cannot backfit to retrospectively attractive combinations.

### 5.5 Output contract: familiar comparison chart plus V2.5

A slate report retains one row per offered contract and shows, when available:

```text
sport | event | player | stat | line | side | offer timestamp
Engine A | Engine B | Bayesian A | Bayesian B | strict NUTS | frozen 60/40
market (when defensible) | market gap | V2.5 marginal | V2.5 joint
calibrated probability | robust grade | uncertainty interval | expected value
opportunity estimate | role/news | n_eff | source receipt | status/Tier
settlement | actual statistic | hit/miss/push/void | outcome provenance
```

The report must also include model version, forecast freeze, confidence eligibility, distribution diagnostics, top-10 rationale per sport, aggregate coverage, side imbalance, and separate **uncertified shadow output** versus approved decision output.

---

## 6. Validation methodology: one governing experiment

### 6.1 Primary experiment: chronological rolling-origin / prequential replay

Use **Experiment B** as the governing validation framework, beginning with historical **2024 slates**, as previously requested. For each historical slate:

1. Construct only the actual then-available training pool and pregame source receipts.
2. Fit or load a model with a cutoff strictly before the target slate; document all historical model/feature design exposure.
3. Record every offered contract that is genuinely available in the historical data. If real quotes are missing, mark that cohort as **statistic-distribution diagnostic only**, not bookmaker-edge validation.
4. Forecast every eligible player/market category; include QB, receiver, running back, and defensive props—not only strong candidate picks.
5. Freeze all forecasts, parameters, quote timestamps, candidate universe and selection decisions.
6. Reveal and settle official outcomes only after freeze. Reconcile missing/corrected stat providers.
7. Advance the origin, using only past-released outcomes, and apply precommitted retraining/calibration rules.
8. Aggregate proper scores and decisions over complete denominators and date/game clusters.

**2025 is not automatically untouched** simply because the model evaluates 2024 first. Audit historical training outcomes **and** human/model-design exposure before assigning a season to holdout status. Known November 2026 diagnostic slates are regression cases, not fresh proof. Untouched future slates provide the strongest prospective certification.

### 6.2 Evaluation datasets and denominators

- Preserve complete eligible contract universe, plus separately counted rejected, missing, duplicated, unsupported, stale, uncertified, and unpriced records.
- Use **matched-contract** comparisons: same game, player, line, period, timestamp, and settlement definition for old/new/market.
- Score the full eligible universe separately from top-k selected populations. Never hide abstained cases from total-coverage accounting.
- Distinguish stable-role from new-role cohorts, early-season from mature-season cohorts, team/position/stat subgroups, market-line bins, favorite/underdog regimes, and available versus unavailable market anchors.
- Require common support for all models in each head-to-head table; explain coverage losses.

### 6.3 Required metrics

| Question | Metrics |
|---|---|
| Binary direction | Brier score, log-loss, calibration-in-the-large, reliability curves, Expected Calibration Error as descriptive (bin choice recorded), hit rate by probability band and side |
| Full distributions | Negative log predictive density where computable, CRPS, randomized PIT and quantile coverage, zero/negative mass, quantile/tail error, observed vs predicted means/variances |
| Joint dependence | Energy Score, Variogram Score with pre-specified `p = 0.5` and pair weights, pairwise-event rates, co-occurrence calibration, rank correlation and proper joint log score when tractable |
| Opportunity | Team-pool conservation, workload MAE/CRPS, player share calibration, participation false-zero rate, role-transition cohort error |
| Selective decisions | Coverage-risk curve, top-1/top-5/top-10 hit and Brier/log-loss, selected-versus-overall calibration, conditional side skew, robust grade interval validity |
| Market comparisons | Matched de-vig baseline, line movement context, forecast-vs-market skill, payout-aware realized/expected return *only* with verified full terms |
| Operations | Certified forecast fraction, accepted quote fraction, source receipt completeness, latency, CPU/RAM, runtime, total cost, failed-stage counts |

Use game/date-clustered bootstrap or other dependence-aware uncertainty intervals, paired fold differences, multiplicity discipline for many challengers, and precommitted promotion criteria. Do not convert a non-significant comparison into a claimed win. **Select and disclose the clustering unit before scoring**; game and week replicates are sensitivity checks, not automatically independent experiments. Report covered/uncovered populations and selection denominators with any score.

### 6.3.1 Phase 1.5 diagnostic versus release-grade evaluation (v1.1)

The Nov 10 Phase 1.5 archived 2024 run is a **historical, synthetic-line, research diagnostic**. It scored 71,009/107,319 rows (36,310 `UNMATCHED`) from 272 games and 18 weeks, reporting mean Brier 0.1928184 for the archived challenger vs 0.1951962 for its frozen historical baseline; it selected Under on 92.8502% of matched records. Game/week bootstrap differences are descriptive and do not remove possible 2024 model-development exposure or synthetic-line mismatch with actual sportsbook offers. The 2024 run cannot be used to certify Tier performance, market edge, or prospective model promotion.

For directional diagnostics also report **signed Over residual**: mean predicted P(Over) minus observed Over frequency. In the initial archive these were 0.278598 vs 0.312425, or **−0.033827** (3.38 percentage points underpredicted Over overall). Over-selected and Under-selected confidence-minus-accuracy are different conditional statistics and must not be conflated with unconditional Over residual. Slice by market, side, player/role, line regime, game/week and eligibility, and track the original unmatched rows.

The available archive did **not** include sufficiently verified, originally frozen pregame estimates of all four proposed opportunity factors. Structural oracle/Shapley attribution therefore remains **unmeasured**, not zero. When an appropriate dataset exists, validate factor definitions and the recorded pregame product first; substitute realized team volume, participation, share, and efficiency only in isolated retrospective loss calculations. Shapley allocations of oracle squared-error improvement are diagnostic associations, **not causal explanations, attainable pregame gains, or additive predictive improvements**. Their raw magnitudes may be incomparable across stats with different scales; use prespecified within-market normalizations and uncertainty checks.

### 6.4 Leakage red-team tests

Required adversarial tests include:

- `shift(-1)` or current-row rolling leakage versus strictly `shift(1)` causal features.
- Actual team attempts, final score, realized snaps/routes/minutes/TOI, postgame injuries, or post-event market quote accidentally loaded as pregame covariates.
- Cross-player same-game data joining outcomes into pregame features.
- Entity identity collisions (player/team/date/stat/period) and duplicate rows across partitions.
- Market label leakage from future close/settlement into pregame line or calibration.
- Historical donor, opponent, and role-change information containing future observations.
- Model fit/calibration or model-choice exposure to the supposed holdout season.
- Abnormally good performance under shuffled-feature, timestamp-shifted, label-randomized, and placebo variables.
- Stale model outputs rebranded as forecasts generated at an earlier timestamp.

**Promotion requires zero verified critical leakage.** A time-source defect blocks the affected models/slates, even when prediction metrics look excellent.

### 6.5 Precommit an experiment card before training

Each trial requires:

```yaml
experiment_id: EXP-XXX
hypothesis: measurable change to a named mechanism
code_commit: <exact SHA recorded at execution>
model_and_feature_versions: <exact versions>
train_cutoff_policy: strict time-ordered and recorded
eligible_universe: exact markets/periods/sports; all rejects separately counted
baseline: frozen simple model and V1 on identical matched cases
challenger: one clearly named model change
primary_metric: predeclared proper score or calibrated decision loss
secondary_metrics: coverage, bias, tail, runtime, joint coherence
cohort_and_splits: exact chronological origins and game/date clusters
negative_controls: named and executable
promotion_rule: no leakage, no material regression, positive paired evidence
rollback_rule: specified before results are observed
artifact_manifest: hashes, snapshots, seeds, logs and report locations
```

No implementation ticket is “done” without a corresponding reproducible experiment manifest or a justified non-statistical contract test.

### 6.6 Tier power, dependence and repeated-use protocol (v1.1)

Before advertising Tier 1/2 reliability, preregister **one eligible contract universe**, target selected side/band, null reliability threshold, expected alternative, one-sided significance level, target power, look schedule, distinct game/date clusters, number of simultaneous tests, and decision rule. Count unique settled **contracts** once; both sides of one Over/Under line are not two independent observations. Correlated player props from the same game and repeated player/game contexts need an estimated dependence-aware effective count or clustered resampling design, with explicit uncertainty. Report unmatched, pushes, voids, missing data and abstentions before forming the scored denominator.

At fixed nominal one-sided **α=0.05 and power=80%**, the Phase 1.5 tool calculates the following **exact binomial fixed-sample planning numbers, assuming independent, identically distributed, prespecified Bernoulli outcomes**:

| Null conditional hit rate | Assumed true hit rate | Independent observations for ≥80% power | Interpretation |
|---|---|---:|---|
| 70% | 80% | 119 | Detect +10 percentage points |
| 75% | 80% | 437 | Detect +5 percentage points |
| 80% | 85% | 365 | Detect +5 percentage points |
| 85% | 90% | 281 | Detect +5 percentage points |
| 90% | 95% | 179 | Detect +5 percentage points |

These counts **are not estimated effective NFL samples** and are not confidence intervals or certification thresholds for the current portfolio. For illustration, 365 independent outcomes at 20 genuinely independent events per week requires at least 19 weeks; game clustering or changing selection rules may increase that horizon materially. The tool also reports hypothetical design effects for assumed correlations, which must never be presented as measured dependence. Small cohorts need shrinkage and uncertainty intervals, not guaranteed tiers. Apply multiplicity adjustment or a precommitted sequential/always-valid testing method for repeated monitoring; never take the best retrospective stop date as a confirmed result.

### 6.7 Evidence-based stop, continue and switch rule (v1.1)

- **Integrity stop:** any critical leakage, lineage or contract mismatch blocks the affected trusted release. Repair evidence first; preserve row-level failure counts and immutable history.
- **Diagnostic switch:** before committing to Phase 2, compare team volume, participation/role, share allocation, conditional efficiency, tails/dispersion, directional calibration and selection effects. Prioritize only components that exhibit material, credible loss reduction potential. If source data cannot identify the driver, label it *unmeasured* and instrument prospectively rather than guessing.
- **Pilot stop:** preregister primary matched proper score, minimal useful improvement, exact cohorts, negative controls and compute budget. If a challenger does not improve on the simple baseline with adequate evidence, retain the baseline and **stop investing in that architecture**. If the data are underpowered, classify **inconclusive** rather than proven ineffective; collect additional prospective data before escalation.
- **Dependence exception:** a joint model may earn development budget for a significant preregistered multivariate/joint-event benefit even if marginal Brier barely moves; it may **not** claim improved single-leg edge on that basis.
- **Economic stop:** absent a verified edge versus a *compatible, actual de-vigged market comparator* and payout-aware prospective economics, do not claim profitability or promote trusted high-confidence picks. Failure to prove an edge is not proof no edge exists; it does mean pause costly complexity and focus on source capture and calibration.
- **Conditional expansion:** Phases 4–8 each require their own approved hypothesis, dependency evidence and continuation gate; no eight-phase commitment by inertia.

---

## 7. Implementation phases and ticket-level work breakdown

### Phase 0R — Complete data certification and operational safety **(CURRENT BLOCKER)**

**Objective:** Repair live input lineage so a genuinely pregame snapshot can become certifiable. Keep release restricted while working. **Split execution into Phase 0R-A (diagnose) and 0R-B (repair/certify), with independent continuous raw prospective capture**; this split does **not** weaken any certification rule. The first engineering session is bounded to a source/branch/schedule inventory and row-level root-cause counts, not five unrelated deliverables. A second session addresses the dominant verified causes. Time-box the first recovery attempt, not the evidence standard; if pregame timing is missed, preserve an explicit blocked-state packet and capture the next legitimate window.

**Tickets**

**Track 0R-A — diagnosis first:** P0R-01 plus row-by-row frequency, intersection and upstream cause analysis of **all 1,490 uncertified forecasts** and a **separate breakdown of the 658 rejected quotes**. Establish whether a few repeated defects account for most failures. Return precise named blocker counts and go/no-go repair priority. Do not edit old receipts to manufacture validity.

**Track 0R-B — verified repairs and genuine pregame validation:** P0R-02 through P0R-08 after diagnosis; first address the highest-impact cause(s), rerun the acceptance denominator and preserve all failures. Continuous immutable source/quote collection runs in parallel in shadow mode with explicit `UNCERTIFIED` status until data lineage is complete.

- **P0R-01 Repository reconciliation:** identify `main` HEAD, merged PR #79 contents, all follow-on provenance branches, active Deepnote notebook revisions, active schedules and pause markers. Save an inventory with commit SHAs, generated-data hashes and current test summary.
- **P0R-02 Event identity:** trace missing `event_id` from provider feed to market quote, research packet, forecast row, settlement and comparison chart. Repair mapping without synthetic fallback IDs. Unit tests cover home/away, reschedule, multi-book, postponed and duplicate events.
- **P0R-03 Freeze timestamp contract:** give every accepted forecast an authenticated `input_freeze_at` and validate all source availability times against it; prohibit overwriting it on publish/settle.
- **P0R-04 Training cutoff contract:** supply precise UTC `model_training_cutoff_at` from the actual model artifact/manifests; reject unknown provenance and avoid optimistic defaults. Validate models with multiple trained subcomponents independently.
- **P0R-05 Source receipt closure:** content SHA-256, publication/ingestion time, original-source reference and quote provenance for every certified feature group; distinguish missing from truly non-applicable.
- **P0R-06 Runtime hardening:** normalize timestamp precision, idempotent reruns, duplicate population, optional source HTTP-415 fallback behavior, `zstd`-dependent test coverage, failure-code counters.
- **P0R-07 Live dry run:** run legitimate upcoming pregame slate collection, quote capture, snapshot freeze and provenance audit; retain reject ledger; do not publish Tier 1/2.
- **P0R-08 Independent audit:** adversarial replay of at least one entire frozen run plus tampered-time/absent-source fixtures; cross-check snapshots and ledger bytes/hashes.

**Mandatory acceptance:** 100% of **certified** forecasts have complete validated event identity, timestamps, model cutoff, source receipts and contract integrity; **zero** invalidly certified rows; no missing fields hidden by dropping rows. Ideally achieve material operational certified coverage, but do not invent a numerical quota—publish the full acceptance/rejection denominator and root causes. Phase 0R cannot close on unit tests alone. Keep the 60/40 benchmark read-only, NUTS paused, and Tier 1/2 suspended.

**Outputs:** `phase0r_state.json`, `source_coverage.csv`, `forecast_receipt_manifest.json`, `phase0r_live_certification.md`, test logs, adversarial signoff, active operations runbook.

### Phase 1 — V2.5 core contracts and baseline harness

**Dependencies:** P0R certified data contract for trusted/accepted evaluation; read-only tooling may be prototyped against explicitly uncertified frozen archives in parallel without claiming release eligibility.

**Tickets**

- **P1-01** Implement canonical statistics, contracts, predictive-distribution interface, analytical Over/Under/Push extraction, versioned immutable snapshots and legacy adapters.
- **P1-02** Build frozen baselines: naive recent exposure/rate, role/position-shrunk hierarchical rate, V1 60/40, no-vig market where actually identifiable.
- **P1-03** Build deterministic prequential evaluator and paired, game/date-clustered scorecards; automatically enumerate full eligible universe.
- **P1-04** Add property-based simulation/settlement checks, near-threshold mass, push accounting, signed yardage, time-source sentinels and distribution support tests.
- **P1-05** Add Variogram Score `VS_0.5` and Energy Score alongside existing Brier/log-loss/CRPS; cross-check with small analytically tractable examples.
- **P1-06** Freeze 2024 experiment protocol, determine whether any 2025 cohort is independent, and create immutable experiment manifests.

**Exit:** one command can regenerate a fully versioned baseline evaluation with exact snapshots, stable seeds, intact denominators, and no leakage flags. This is infrastructure acceptance, not V2.5 performance promotion.

### Phase 1.5 — Forecast error decomposition and Tier statistical power **(NEW MANDATORY INVESTMENT GATE)**

**Purpose:** Decide which underlying forecast errors justify a V2.5 challenger **before** choosing a sophisticated opportunity allocator or constructing a heavy joint simulator. Phase 1.5 runs as **read-only research** on existing frozen data and may overlap with Phase 0R/1; it does **not** bypass their certification gates. Its results inform **which pilot to fund**, not whether to publish bets.

**Implementation status at v1.1 (November 10):** Shadow script `scripts/phase15_diagnostics.py`, adversarial tests `tests/test_phase15_diagnostics.py`, and `docs/PHASE_1_5_DIAGNOSTICS.md` exist on isolated branch `chatgpt/phase15-error-power-diagnostics-20261110` (HEAD `aad99119283c154a9d8d5b7327fe52336dbe2b6a`). Detached Deepnote project notebook **“V2.5 Phase 1.5 — frozen error decomposition and tier power (shadow only)”** completed 19/19 unit tests and the initial synthetic-line 2024 analysis. The original pregame opportunity-factor inputs were missing, so the oracle attribution was not run on authentic factor rows. **Independent code/math/data review, component input validation, and branch PR/merge are pending**; call this *implemented and initially tested*, not *fully validated*.

**Tickets**

- **P1.5-01 — Freeze evidence and schemas:** inventory source code SHA, exact frozen CSV/receipt SHA, model versions, capture chronology, validation exposure, outcome/quote type, full eligible denominator, missing/failure reasons and duplicate identity handling. Reproduce the first archived run byte-for-byte where possible; flag discrepancies rather than editing sources.
- **P1.5-02 — Paired directional error audit:** on the identical contract and settlement definition, score model vs archived baseline using Brier and log loss; report signed P(Over) residual, Over/Under selection fractions, top probability bands, side-specific confidence-minus-accuracy, per-stat/role/game/week splits, and all unmatched/push/void cases. No fabricated real market baseline for synthetic lines.
- **P1.5-03 — Determine availability of authentic component forecasts:** verify **pregame-recorded** team attempt/possession forecasts, participation/route/snap projections, player share projections and conditional-efficiency projections. Require event ID, forecast timestamp, source receipts and unambiguous factor definitions for each market. **Do not infer pregame values from realized outcomes or reconstruct hypothetical old models.**
- **P1.5-04 — Quantify the component error where supported:** evaluate forecasted vs realized team volume, participation, allocation and efficiency, plus physical support, zero/tail, distributional and calibration errors. Add isolated postgame oracle factor substitutions and Shapley allocation of squared-error reduction with interaction accounting and within-market normalization. Oracle values **never enter pregame model features**. Do not claim causal explanation or achievable improvement.
- **P1.5-05 — Selection and uncertainty analysis:** compare all eligible contracts, chosen Over vs Under, top-1/top-5/top-10, strong confidence bands, abstentions and unmatched records. Bootstrap **games and weeks as clusters**, paired rather than independently resampled model scores; quantify dependence and instability; document multiple-testing and model-design exposure.
- **P1.5-06 — Tier power analysis:** exact one-sided fixed-sample binomial calculations under explicitly independent assumptions; sensitivity to cluster size/correlation; power by plausible Tier claims, actual selection yield, prospective sample accrual, multiple tiers and optional sequential monitoring. Report **planned independent observations vs raw correlated legs**, never equate them.
- **P1.5-07 — Instrument missing prospective factor receipts:** when authentic archived factor forecasts are not available, design a *minimal* immutable and time-verified logger for team volume, participation, share and conditional rates. Capture alongside regular forecasts only when the Phase 0R source/freeze protocol permits; mark shadow/uncertified until proven.
- **P1.5-08 — Independent verification:** a separate audit of input hashes, metric arithmetic, class/side equality, duplicate detection, altered outcomes/labels, time-travel fixtures, retrospective oracle quarantine, exact binomial power and deterministic clustered resampling. A sequential LLM review is supporting evidence, **not independent replication**; executable tests and frozen inputs have priority.
- **P1.5-09 — Evidence-based go/no-go memo:** rank plausible loss sources (volume, availability/role, allocation, efficiency, distribution/tails, calibration, selection) with effect estimates, uncertainty, data coverage, cost and decision. Choose the smallest credible Phase 2 or 3 pilot, delay unjustified candidates, and register the next experiment before new training.

**Initial, limited result:** the historical 2024 synthetic-line cohort had **107,319 input rows, 71,009 matched/scored, 36,310 unmatched, 272 games, 18 weeks**. Archived model Brier **0.1928184**, baseline Brier **0.1951962**, difference **−0.0023778** on matched rows; predicted Under share **92.8502%**. Mean predicted Over **27.8598%** vs observed Over **31.2425%** is an **−3.3827 percentage point** overall signed bias. The results show an acute **directional/calibration investigation target**, not that a particular factor caused it. Synthetic lines, historical exposure and missing authentic factor inputs block economic or structural-causal conclusions.

**Mandatory exit:** (a) tests and an independent audit pass, with original inputs/SHA and full coverage ledger; (b) historical directional/source results independently reproduced and uncertainty reported; (c) original pregame component attribution either validated on genuine factors **or transparently marked blocked with a specific prospective instrumentation ticket**; (d) exact Tier planning/power receipt completed with dependence caveats; (e) a documented *invest / defer / retain simple baseline* decision for the next modeling ticket. An unavailable opportunity-factor dataset must not be silently replaced by invented values. Phase 1.5 can **close its diagnostic ticket as limited/blocked-by-data**, but cannot be declared scientifically complete or justify a particular allocator until that evidence is supplied.

**Outputs:** `reports/phase15_*/frozen_2024_diagnostic_receipt.json`, full cohort/coverage summaries, component-input availability ledger, oracle receipt when authentic data permit, Tier power table, clustered comparison and error-priority memo, audit/tests report, exact branch/PR/merge receipt.

### Phase 2 — NFL market-optional game state and constrained opportunities

**Dependencies:** Phase 1 evaluator, time-frozen NFL historical exposure and identity, **Phase 1.5 error-priority/gating memo and approved, bounded experiment card**. Prospective certification is required for trusted promotion, not for read-only research.

**Initial scope, conditional on Phase 1.5:** NFL team pass volume, player participation/routes, targets and the unassigned attempt category **only where diagnostics support investing there**. If observed error is predominantly calibration, availability, or conditional efficiency, the first challenger may instead focus on that mechanism. Include QB outputs in the eligible forecast universe even when a pilot focuses on targets.

**Tickets**

- **P2-01** Fit probabilistic team possessions, attempts, dropbacks, pass tendency and game-script scenarios with pregame-only covariates; maintain independent/no-market state baseline.
- **P2-02** Model route/snap participation, lineup and role uncertainty using hierarchical priors, not realized game exposures.
- **P2-03** **If allocation/share error is material and measurable in Phase 1.5**, prototype hierarchical logistic-normal target shares with residual/unassigned attempt handling; otherwise retain simple allocation and mark this ticket *deferred* rather than automatically building it.
- **P2-04** Implement replayable verified-absence redistribution with capacity and positional changes **estimated from data**, not borrowed power-grid constants.
- **P2-05** Prototype standard DM and ZIDM challengers; EFDM/CC only if their computational and cohort needs justify them.
- **P2-06** Test short-role and high-usage absence cohorts separately, with uncertainty/abstention.

**Exit/investment gate:** zero illegal allocations; improvement in the **specific precommitted deficit** (team volume, participation or target distribution) over a simple baseline on matched chronological cohorts with clustered uncertainty and negative controls. Document null and adverse experiments. If improvement is absent or underpowered, keep the simple baseline champion; do not automatically proceed to Phase 3/4 based on code completion. A joint simulation may still proceed later under a *separately precommitted dependence benefit* hypothesis.

### Phase 3 — NFL conditional outcome likelihoods

**Dependencies:** credible opportunity-factor forecasts or an explicitly validated simple alternative, Phase 1.5 prioritization, existing model fitting and scoring contracts. Phase 3 research modules can be developed in parallel with Phase 2 only when inputs are versioned and not falsely claimed validated.

**Tickets**

- **P3-01** Targets-to-receptions conditional distribution with route/target/catch consistency.
- **P3-02** Conditional signed receiving-yardage marked-play distribution, with explicit mass at zero and occasional negative gains; Tweedie challenger only on suitable nonnegative components.
- **P3-03** QB attempts/completions/passing yards; propagate game-state and receiver-allocation dependence.
- **P3-04** RB carries/rushing yards with game-state and negative-yardage support.
- **P3-05** Defensive snaps and tackle opportunity model; separately evaluate solo/assisted and official combined credit; NB vs CMP challenger if dispersion indicates.
- **P3-06** Full-stat diagnostic report across all represented NFL prop types, not only model-favored markets.

**Exit:** support/zero/tail checks pass; distribution accuracy improves or remains demonstrably competitive versus simple baselines; no change degrades QB/defensive calibration without an explicit rejected/disabled challenger path.

### Phase 4 — Joint game simulation and dependence validation

**Dependencies:** validated or stable conditional outcome distributions and common game-state mechanisms, **plus explicit Phase 1.5/2–3 evidence that dependence error or a preregistered multi-leg use case justifies joint simulation complexity**.

**Tickets**

- **P4-01** Generate coherent NFL game scenarios with common latent state, participation and team pools.
- **P4-02** Property tests for totals, attempts/targets/receptions, simultaneous player availability, signed gains and period/overtime rules.
- **P4-03** Implement dependence benchmarks: independence, native shared-state simulator, similarity-matched historical Schaake, optional ECC/dECC residual correction.
- **P4-04** Build history-only context matching using pregame spread/total/role/style; ensure matched game IDs never cross the target cutoff.
- **P4-05** Measure marginal score drift after coupling and after any later entropic reweighting.
- **P4-06** Joint-event reporting for same-team, QB–receiver, two-receiver, RB/WR, and relevant opposing-team relationships, with prespecified pair families.

**Exit:** no conservation violations, credible marginal accuracy, and measurable **precommitted** joint-event improvement versus independence/native-state baselines on matched chronological folds. Prefer simpler native dependence if copula correction adds no value; do not justify Phase 4 spending merely because Phase 3 code is finished.

### Phase 5 — Market information and stable calibration

**Dependencies:** reliable real market quote receipts, statistically supported underlying model or simpler reference, rolling-origin evaluator; advanced coherent scenario tilting is conditional on Phase 4 itself being justified. Standalone calibration may be studied with simple validated distributions sooner, under strict chronology.

**Tickets**

- **P5-01** Capture compatible game-level spread, total and team total anchors with timestamps; document de-vig validity and information overlap.
- **P5-02** Implement limited regularized exponential tilting; test unconstrained, market-conditioned, and simple linear context alternatives.
- **P5-03** Report KL stress, weighted ESS, infeasible constraints, scenario support failure, effective market contribution, and marginals post-tilt.
- **P5-04** Train calibration only on earlier out-of-fold predictions; compare no calibration, regularized probability calibration and distributional calibration where coherent.
- **P5-05** Audit Over/Under directional imbalance, favorite/underdog patterns, extreme `>90%` Under predictions, and top-selected miscalibration.

**Exit:** market conditioning demonstrates incremental pregame value beyond a prior-only model on **actual time-matched market data** and does not erase meaningful market-vs-model comparisons. Calibration must improve or not materially degrade locked proper scores. Missing anchors result in a flagged no-market path, not artificial input values.

### Phase 6 — Robust decision layer and Tier policy

**Dependencies:** Phase 5 scoring/calibration, adequate independent selection cohorts.

**Tickets**

- **P6-01** Implement calibrated nominal probability and simple uncertainty lower-bound score.
- **P6-02** Prototype WDRO with radius selected strictly on prior validation folds; compare against simple conservative ranker and nominal edge ranker.
- **P6-03** Compute correct product-specific EV where full terms exist; otherwise show probability/uncertainty with `EV unavailable`.
- **P6-04** Audit top-1, top-5, top-10, all eligible, all abstained, both sides and correlation within ranked picks.
- **P6-05** Re-specify Tier 1/2/3 policies from observed conditional reliability, not legacy fixed point estimates; require sufficient **effectively independent** events and conservative confidence bounds.
- **P6-07 (v1.1)** Pre-register Tier-specific null/alternative, one-sided α, power, multiplicity/repeated-look rules, game/date-clustered dependence strategy, effective sample count, expected weekly accrual, minimum verification horizon and selection/abstention denominator; integrate Phase 1.5 exact-power tool without turning theoretical sample sizes into a release certificate.
- **P6-06** Formalize model promotion, shadow operation, conservative abstention, rollback and decision trace.

**Exit:** improved or non-inferior selective reliability on untouched data, no unsupported 80–90% confidence claims, documented coverage tradeoff, and explicit distinction between probability quality and realized profitability. Keep high-confidence publication disabled until genuine prospective gates pass.

### Phase 7 — NHL and NBA expansion

**Dependencies:** the shared pipeline is stable and sport-specific data receipts are adequate. May proceed in parallel with Phase 5–6 infrastructure, but **not** by skipping their publication safeguards.

**NHL work items:** goalie starter/exposure and shot-against→save model first; SOG then blocks/hits with distinct opportunity and scoring-definition audits; goalie/empty-net and line/TOI role constraints; verified historic artifacts used as baselines, not automatically promoted.

**NBA work items:** minutes/rotation and overtime model first; possession/usage decomposition for points, rebounds and assists; coherent same-player combos; structural role changes/trades and zero/limit regimes.

**Exit:** each sport's markets pass the same point-in-time, distribution, marginal/joint, selection, coverage and settlement audits. Do not assume that an NFL-validated copula or count likelihood transfers unchanged to NBA or NHL.

### Phase 8 — Optional advanced inference and representation challengers

**Dependencies:** stable simple model; identified residual deficiency; explicit experiment card.

Candidate priorities:

1. Multi-Path Pathfinder vs existing NUTS posterior benchmark (runtime and tail fidelity).
2. Distributional synthetic control for newly promoted roles, with donor uncertainty.
3. Sparse Poisson-lognormal network if correlation residuals persist after shared-state and compositional allocation.
4. Regime-switching/conformal coverage diagnostics if drift is measurable and enough state-specific calibration data exist.
5. Small PBP encoder or state-space model if publicly accessible time-ordered plays measurably improve known failures.
6. Hawkes event processes only with identifiable event data and corrected kernel parameterization.
7. Dirichlet flow matching, conditional flows, or attention copulas only if less costly baselines show stubborn, material joint forecasting errors.

**Exit:** independent chronological incremental evidence with model/runtime/coverage comparisons. No promotion for novelty alone.

---

## 8. Prioritized research registry and falsifiable hypotheses

| ID | Hypothesis | Challenger vs baseline | Primary failure to test | Earliest phase |
|---|---|---|---|---|
| R01 | **If Phase 1.5 finds material allocation error**, constrained allocation improves player opportunities | Logistic-normal vs independent and DM | impossible sums, negative competition, changing roles; priority conditional on verified decomposition | 2 after 1.5 |
| R02 | Explicit structural inactivity helps | ZIDM vs logistic-normal/hurdle | zero target with routes vs no routes | 2 |
| R03 | Flexible simplex interactions add value | EFDM vs logistic-normal | correlated slot/perimeter role shifts | 2/8 |
| R04 | Outcome-support correction improves probabilities | Signed marked yardage vs Normal/Tweedie | zero/negative mass and right tail | 3 |
| R05 | CMP better handles select dispersion regimes | CMP vs Poisson/NB | NFL tackles and low-cap counts | 3 |
| R06 | Historical rank templates improve dependence | Schaake/ECC vs native state simulator | co-occurrence and variogram | 4 |
| R07 | Market-conditioned game state improves future probabilities | regularized tilt vs unconditioned/simpler anchor | redundant market double-counting | 5 |
| R08 | Probabilistic role priors beat hard n-game veto | hierarchical/DSC vs hard gate | first 0–9 games of new role | 2/8 |
| R09 | Robust selection reduces exaggerated top-k confidence | WDRO vs simple lower bound vs nominal | optimizer/winner's curse | 6 |
| R10 | Faster inference preserves predictive tails | Pathfinder vs accepted NUTS | approximate posterior distortion | 8 |
| R11 | Sparse residual networks improve joint predictions | ZIPLN vs state/alloc model | unexplained pair dependence | 8 |
| R12 | Regime-aware uncertainty helps under drift | switching/conformal vs fixed calibrator | post-trade, coaching and injury transitions | 8 |

**Important corrections to the source report:**

- Its specific claims of 10–30% or 38% improvement in other disciplines are **not promises for this project**.
- Hawkes kernel as written is internally inconsistent about its branching ratio; fix parameterization before any trial.
- 120% load caps and 60% imbalance cutoffs borrowed from electrical engineering have no direct empirical sports authority.
- Over/Under complementarity requires a single coherent CDF/settlement contract; quantile shuffling alone does not guarantee analytic threshold precision after finite sampling/reweighting.
- WDRO mitigates selected-model uncertainty if appropriately specified; it does not automatically eliminate selection bias.
- A low PSIS Pareto-k does not by itself validate an approximate posterior or justify skipping all NUTS adaptation.
- Distributional synthetic control and conformal procedures cannot create independent observations or ensure individual event probabilities.

---

## 9. Promotion, safety, migration, and rollback

### 9.1 Gates by severity

**Hard integrity blockers (zero tolerance):** temporal leakage, missing source/model cutoff on a certified forecast, invalid event/stat identity, broken offer/settlement equivalence, forecast mutability, impossible generated states, incorrectly paired probabilities, unlogged retrospective selection, corrupted baselines.

**Performance blockers:** challenger fails locked primary score or has material calibrated coverage regression, top-k selection deterioration, missing adequate sample/uncertainty, unacceptable tail behavior, or cannot be compared on matching contracts. **Research-budget blocker:** absent a documented Phase 1.5 error mechanism and a preregistered minimum useful benefit, do not start an expensive Phase 2–4 architecture. No claimed real-market edge without genuine time-matched offers, de-vig where possible, full payout terms and prospective scoring.

**Operational blockers:** excessive CPU/memory relative to local budget without justification, non-reproducible model artifact, inability to run from local environment/free resources, untraceable model versions or missing rollback path.

### 9.2 Promotion ladder

```text
IDEA -> IMPLEMENTED -> TESTED -> HISTORICAL SHADOW -> PROSPECTIVE SHADOW
     -> LIMITED VALIDATED RELEASE -> FULL VALIDATED RELEASE
```

Each transition requires a signed receipt: exact commit, artifact SHA, input cutoff, experiment ID, matched evaluation, failure log, known limitations, and independent adversarial review. Retrospective repair cannot retroactively turn previously uncertified forecasts into genuine pregame forecasts when evidence is unavailable.

### 9.3 Rollback

Maintain separately versioned frozen V1 and V2.5 champion artifacts. Preserve all raw receipts and model outputs. If a new candidate violates integrity or material calibration gates, immediately disable its decision authority, preserve the failed evidence, re-enable the last certified champion when one exists, and continue shadow evaluation. Avoid silently changing weights or dates to improve reported results.

### 9.4 Repository execution policy

- Make code changes through ChatGPT-controlled workflows, not external GitHub coding agents.
- Use isolated branches/PRs with small diff scopes. A reviewer must inspect the changed mathematical assumptions, time availability and tests; author/reviewer separation should be maintained even when tasks are performed sequentially.
- Never automatically merge a research challenger into trusted release configuration.
- No deletion of old posteriors, models, frozen forecasts, historical reports or training receipts until separately approved archival/migration verification.
- Keep GitHub Actions cost controlled; use local Dell for heavy modeling and free Deepnote CPU where suitable. Do not schedule heavyweight retraining in the daily slate path.

---

## 10. Workflow roles, task protocol, and audit artifacts

### 10.1 Specialized workstreams (all performed by ChatGPT-controlled work)

| Role | Responsibilities | Independent reviewer |
|---|---|---|
| Orchestrator / release custodian | Dependencies, versioned status ledger, scope, commit/PR and rollback | Adversarial auditor |
| Data/provenance engineer | Source receipts, time semantics, event/contract identities, market offers, settlement | Data integrity red team |
| Mathematical architect | Conditional distributions, simplex allocation, constraint derivations, probability extraction | Statistical validator |
| NFL/NHL/NBA domain analyst | Play/shot/minute mechanisms, stat semantics, eligible market scope | Mathematical architect |
| Computational inference engineer | Fitting, posterior diagnostics, Pathfinder/NUTS, local memory and runtime | Statistical validator |
| Experiment and calibration engineer | Rolling-origin studies, proper scores, selection bias, cohort uncertainty | Adversarial evaluator |
| Software/QA engineer | Integration/property tests, reproducibility, release automation and reporting | Orchestrator + red team |
| Adversarial auditor | Attempts to break timeline, probability, selection, market, and settlement logic | Reports independently; cannot approve own fixes |

If parallel subagents are not available, execute those roles **sequentially with separate evidence/review passes**. Do not claim independent review by nonexistent workers. Automated property tests, timestamp mutation fixtures, input/output hash comparisons, negative controls and blinded matched scoring carry more evidentiary weight than narrative AI self-audits. A separate reviewer is still useful for checking assumptions but cannot certify statistical independence merely by changing roles.

### 10.2 Per-ticket workflow

**Risk-proportionate enforcement (v1.1):** The full sequence below is mandatory for integrity-critical fixes, production policy changes, and any model promotion. Small shadow-only prototypes may use a **lightweight ticket**: fixed input/hash, stated hypothesis, unit/property tests, short experiment receipt, and explicit no-release label. They do not need a separate lengthy narrative audit packet per edit. A full adversarial pass is required **before** the shadow result becomes a decision or an accepted code release.

1. **Inspect** actual code, source docs, manifests and artifacts; do not trust plan path names over repository evidence.
2. **State hypothesis, threat model, and change boundaries.** Identify which outputs may change.
3. **Write failing tests first** for the specific bug/invariant; preserve reproducer and seeds.
4. **Implement minimal change** with traceable logs, typed inputs, explicit error codes and documentation.
5. **Run unit/property/integration tests** plus relevant historical replay and negative controls.
6. **Audit mathematics:** support, conditioning, independence, conservations, parameterization, uncertainty, numerics.
7. **Adversarial pass:** source-time leak, holdout contamination, identity misjoin, reversed side, edge selection, invalid quote, stale forecast.
8. **Produce evidence receipt:** commit SHA, files touched, test counts, exclusions, runtime, comparisons, remaining blockers.
9. **Decide:** accept infrastructure fix, keep statistical challenger in shadow, reject, or roll back.
10. **Update master status ledger**, preserving unresolved tasks and next dependency. No ambiguous “done” labels.

### 10.3 Standard artifacts per phase

- `status_ledger.md` — phase, ticket, owner/role, exact status, commit, blockers, next action.
- `architecture_decisions/ADR-*.md` — accepted/rejected material decisions and alternatives.
- `model_registry.json` — versions, training data and cutoff, code/artifact hash, inference, validation eligibility.
- `source_registry.json` — provider, record type, timezone, source freshness and failure modes.
- `experiment_manifest.json` — fixed protocol before outcomes, matched universe and primary scores.
- `validation_packet.md` — numerical results, uncertainty intervals, data coverage and adverse tests.
- `adversarial_audit.md` — audit of independent assumptions, test reproductions, unresolved concerns.
- `rollback_receipt.md` — last safe version and exact restoration mechanism.
- `slate_report` and `settlement_report` — immutable pregame/prospective evidence.

---

## 11. Runtime, compute, and daily operations

### 11.1 Compute approach

Use the local Dell workstation for heavier fits (reported 32 GB RAM, RTX 2000 Ada 8 GB); do not assume PyMC/Stan NUTS uses GPU simply because the laptop has one. Prefer vectorized CPU algorithms, bounded memory, checkpointed small jobs, and frozen/posterior-predictive inference during slate runs. Compare algorithm speed at equal forecast quality rather than relying on published speedup factors.

- Slate runtime budget is driven by source verification and market freshness. Build deterministic timeouts and explicit partial-coverage reporting.
- Historical fitting operates separately from morning/afternoon collection.
- Do not start unattended large local computations without verified user-controlled environment and an explicit way to monitor/stop them.
- Deepnote is suitable for small, reproducible free-CPU collection/settlement jobs where resources allow; GitHub Actions should not become an expensive retraining service.

### 11.2 Daily schedule behavior

**Morning:** settle the prior slate, check official stat corrections, reconcile every posted forecast, refresh calibration diagnostics only using now-released results, and archive all evidence. Keep one authoritative source ledger.

**Afternoon:** capture current offers/news/lineups, generate versioned game-state/role distributions, run models and simulation, freeze forecasts and show uncertified shadow comparisons where needed. No implicit future backfill into the pregame snapshot.

As last reported, the morning settlement automation is enabled and the afternoon automated process is disabled. Check active schedules before any changes; do not create duplicate automation or quietly re-enable the afternoon task. A workflow can be run manually while development proceeds, provided it is labeled correctly.

### 11.3 Continuous audit counters

**Priority for remaining NFL 2026 prospective slates:** archive authentic offer/quote and payout receipts (including all rejection reasons), forecast/source timestamps, player/event/stat identities, frozen pregame factor projections when available, and outcomes as they are settled. This raw capture runs **in parallel with Phase 0R** and does not imply certified forecast status; failed certification remains explicit. The 658 November 9 rejected quotes must be broken down by reason **separately** from the forecast rejection codes. Track run-level counts for offers seen, accepted, rejected by reason, eligible contracts, forecasts generated, frozen, integrity-certified, decision-certified, Tier-approved, voided, settled, and still unresolved. Preserve any disagreement between provider and official source. Report distribution/ranking diagnostic regressions and model latency. Failure of any integrity gate must be visible even if the overall pipeline successfully completes.

---

## 12. Master acceptance checklist and definition of complete

### 12.1 Global architecture checklist

- [ ] Exact repository state and active schedules reconciled before code changes.
- [ ] All certified forecasts have reproducible event/market identity and pregame source/model cutoff receipts.
- [ ] Data, forecast and settlement records are append-only/versioned with historical corrections preserved.
- [ ] Frozen V1 baseline and all legacy comparison columns remain reproducible.
- [ ] Real-book offers, odds, and payout terms are differentiated from inferred or synthetic lines.
- [ ] All model training, selection and calibration obey strict rolling-origin time cutoffs.
- [ ] Team/player opportunity conservation and cross-stat physical constraints pass property tests.
- [ ] Every stat's support, push, overtime, DNP and settlement policies are exact.
- [ ] Sport-appropriate conditional full distributions produce plausible mass, zero, signed and tail behavior.
- [ ] Both analytic/marginal and joint forecast diagnostics are generated and versioned.
- [ ] All known outcome/data exposure and holdout contamination are disclosed.
- [ ] Every challenger is evaluated against a simple baseline on matched cohorts with uncertainty intervals.
- [ ] Phase 1.5 independent diagnostic review, original archived-projection provenance and data-availability ledger completed; attribution without authentic factor inputs remains clearly **unmeasured**.
- [ ] Signed Over bias, selected-side imbalance, market/position-specific weaknesses, zero/tail failures and unmatched rows are explained or explicitly constrained by evidence.
- [ ] A precommitted Phase 2/3 priority memo identifies the simplest credible improvement before investing in logistic-normal and simulator complexity.
- [ ] Tier exact-power planning distinguishes raw legs from independent events, adjusts for clustering, selection and repeated looks, and never retroactively validates high-confidence claims.
- [ ] Prospective real quote collection continues even when forecast integrity certification or model promotion is blocked.
- [ ] All eligible markets, top-k selections, rejected offers and abstentions are represented in coverage denominators.
- [ ] Market conditioning is ablated, regularized, and not used to force agreement at the player prop threshold.
- [ ] Calibration, side skew, selective ranking and payout-aware EV are evaluated separately.
- [ ] No unvalidated high-confidence Tier publication occurs.
- [ ] New models have an artifact registry, runtime budget, independent audit and rollback path.
- [ ] A prospective validation tranche has been completed before any trusted promotion.

### 12.2 Definition of project complete (not just software feature complete)

V2.5 is **production-validated** only if a pre-registered and source-certifiable prospective evaluation demonstrates reliable calibration, adequate market coverage, proper-score performance against the frozen baseline, acceptable high-confidence selective behavior, reproducible operation, and no critical leakage or settlement errors. No single backtest win, 100% NUTS completion, or conference-paper similarity closes the project.

---

## 13. Next workflow launch brief — diagnose Phase 0R, validate Phase 1.5, then choose the pilot

**Purpose:** Execute the next bounded engineering task rather than restarting a master-planning exercise. Use the companion **`Pickem_Auditor_V2_5_Next_Workflow_Launch_Brief_v1_1_2026-11-10.md`**; it supersedes the November 9 v1.0 brief. Relevant phases may run in parallel in read-only shadow mode, but no trusted downstream promotion bypasses Phase 0R or Phase 1.5 investment gates.

### Initial brief to paste into the next ChatGPT Work/engineering conversation

> **PROJECT:** Pick’em Auditor V2.5. **GOVERNING PLAN:** `Pickem_Auditor_V2_5_Master_Implementation_Plan_v1_1_2026-11-10.md`, v1.1. Changes made by ChatGPT-controlled tools only; no GitHub coding agents. Preserve legacy baseline, forecast/settlement receipts, posterior archive, training pause and comparison chart.
>
> **IMMEDIATE TICKET P0R-A (DIAGNOSE):** Independently inspect live `main`, PR/commit status, Deepnote and schedules; reconcile November 9 checkpoint of 1,490 forecasts/0 certified and 1,387 accepted/658 rejected quotes. Deliver (a) full forecast failure-code and *co-occurrence* counts and (b) a **separate** rejected-quote reason breakdown, with source hashes, root causes, prioritized fixes, no silent row drops, and no false certification. Do not require completed repairs or a live game in this **first** diagnostic session.
>
> **IN PARALLEL, RAW CAPTURE:** Preserve genuine timestamped pregame market quote/source/factor forecasts from upcoming slates even if certification is blocked; label uncertified accurately and do not claim real-market edge or retro-certify prior predictions.
>
> **PHASE 1.5 STATUS/WORK:** On Nov 10, isolated branch `chatgpt/phase15-error-power-diagnostics-20261110` (HEAD `aad99119283c154a9d8d5b7327fe52336dbe2b6a`) contains script, 19 passing adversarial tests and documentation. Detached Deepnote shadow run scored 71,009/107,319 synthetic-line 2024 contracts, not a live market proof. **Independently audit/replay** that receipt, assess directional Under skew and signed Over bias, verify test gaps, then review/merge through a PR if valid. Authentic frozen pregame four-factor inputs for opportunity oracle attribution remain missing; instrument them prospectively, **never synthesize them**. Tier power is theoretical until dependence/selection and prospective cohorts are measured.
>
> **AFTER THE DIAGNOSTIC:** Repair the highest-impact Phase 0R defects with property/time-travel tests and obtain the next authentic pregame dry-run packet where possible. If no legitimate window is available, report a blocked state and exact next capture action. Validate Phase 1 contracts; finalize a Phase 1.5 *error-priority and power* decision card. **Only then** authorize a narrowly scoped Phase 2/3 modeling pilot for the demonstrated failure mode. A logistic-normal allocator is a challenger, not a mandated first build; heavier Phases 4–8 are individually conditional.
>
> **EVERY RELEASE-CANDIDATE CHANGE:** Test source identity/timestamp/probability invariants, compare against simple baselines on matched time-ordered cohorts with game/week-clustered uncertainty, record hashes, exclusions and rollback, and conduct a separate adversarial check. Small shadow-only experiments use proportional lightweight tickets; no automatic promotion, Tier 1/2, NUTS restart or afternoon publication.

### Exactly what the **first** working session should return

1. Verified tree/commit/schedule and Deepnote inventory, including Phase 1.5 branch state and freeze hashes.
2. Forecast-certification failure-code counts/intersections across the reported 1,490, **plus separate quote rejection categories** for 658 recorded rejects; explanation of discrepancies with live data.
3. Prioritized Phase 0R repair ticket(s), owner/assignee if applicable, root-cause evidence and no-go safety status; do not make a speculative multi-file repair before classification.
4. Raw prospective capture health and next legitimate pregame opportunity; if none, an explicit blocked-state record rather than fabricated live evidence.
5. Phase 1.5 independent-review plan/result where feasible, exact current status and missing component inputs; an evidence-based next milestone without spending on an unearned simulator.

**Second session and beyond:** execute proven fixes, verify authentic certification and independent audit, close remaining Phase 1.5 gaps, complete Phase 1 evaluator, and make the signed Phase 2/3 investment decision. Neither 0R nor 1.5 is considered fully closed by unit tests alone.

---

## 14. Source and decision provenance

### Project materials used

- **Pick’em Auditor — Rebuild Plan V2** (`Analyse bayésienne des prédictions.txt`): distribution-first, opportunity-driven simulations; frozen 60/40 benchmark; NUTS preservation; source/market point-in-time validation; original Phase 0–4 plan.
- **Cross-Disciplinary Mathematical Architectures for Next-Generation Probabilistic Forecasting**, 24-page uploaded research report: ZIDM/EFDM/CC, Tweedie/CMP, Schaake/ECC, Variogram Score, entropic tilting, Pathfinder, synthetic controls, WDRO, conformal/régime ideas. Claims are treated as research hypotheses unless independently established in Pick’em Auditor.
- **Agreed V2.5 direction:** market-conditioned but not market-enslaved game state, hierarchical logistic-normal/simplex allocation, shared latent scenarios and causal opportunity accounting, calibrated decision and uncertainty/abstention, sequential sport-specific extension.
- **Recent Phase 0 work reports:** PR #79 baseline and subsequent source provenance/quote/training-cutoff repair and failing live certification; live repository state still requires verification in the next execution session.
- **External architectural review (November 10):** recommended early error decomposition, a no-edge/complexity investment stop rule, time-critical no-paid-data prospective collection, explicit Tier statistical power, narrower immediate sprint, and executable audits rather than merely sequential AI reviews. These are incorporated as governance changes, not independent empirical proof.
- **Phase 1.5 Nov 10 code/evidence:** isolated GitHub branch `chatgpt/phase15-error-power-diagnostics-20261110` and detached Deepnote shadow notebook; 19/19 tests and synthetic-line 2024 receipt. Independent code/data audit and four-factor input attribution remain outstanding. Only original verified pregame components can support the latter.

### Decision record

| Decision | Status | Rationale |
|---|---|---|
| V2.5 joint simulation | **Conditional research option, not preapproved spend** | May enforce joint constraints and improve dependence when Phase 1.5/2–3 evidence establishes a benefit |
| Frozen 60/40 and old engines | Retain as benchmark, not selection authority | Avoids losing diagnostic evidence or treating correlated votes as independent |
| Logistic-normal opportunity allocation | **Conditional challenger** | Enter after measured allocation deficit and preregistered paired baseline test; otherwise favor the identified failure source |
| ZIDM, EFDM, CC | Shadow research | Evaluate only if incremental behavior and data quality warrant |
| Native shared-state dependence | Default first implementation | Preserves constraints and provides clear causal accounting |
| Schaake/ECC | Priority shadow challenger | Cheap multivariate benchmark if applied without breaking constraints |
| Variogram Score | Adopt for evaluation | Detects dependence failures missed by individual-event scores |
| Regularized entropic tilting | V2.5 challenger | Incorporates macro information with KL/ESS safeguards |
| WDRO | Decision-layer challenger | May reduce overconfident top-k selection, but no mathematical guarantee of eliminating bias |
| Pathfinder | Computational benchmark | Potentially cheaper inference, but must match predictive quality |
| Hawkes/flow/advanced GNN/Transformer | Defer | Higher complexity and/or identification costs than justified before baseline validation |
| Rigid translated engineering capacities | Reject | Non-sports thresholds are not valid sports parameters |
| Paid historical odds / paid tracking | Exclude from critical path | User's no-paid-data constraint |
| Phase 1.5 error decomposition | **Mandatory investment gate, code in unmerged shadow branch** | Diagnose volume/role/share/efficiency/tails/calibration/selection errors before choosing a costly architecture |
| Frozen 2024 synthetic-line results | **Diagnostic only** | 71,009 scored; Brier better than archived baseline but extreme Under skew and unverified pregame component factors, not real-offer market proof |
| Tier power | **Mandatory pre-registration before claims** | Exact binomial counts need game/date-dependence, selection and repeated-testing corrections |
| 0R split and parallel capture | **Accepted operational amendment** | First diagnose dominant cause(s) and quote rejects separately, preserve early prospective source evidence |
| Phases 4–8 | **Individually conditional** | Stop complexity when simple baselines or market reference cannot be beaten with credible evidence and preregistered metrics |

**Revision policy:** This file becomes a stable workflow reference. A future change to data semantics, primary validation experiment, release tiers, or model promotion criteria requires a documented ADR explaining evidence, backward compatibility, and whether prior heldout data have now been exposed.