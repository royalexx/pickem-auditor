# NBA V2.5 — P2 statistical S-family engineering handoff

**Research-only; no retrospective predictive scoring, weights, market decisions, production or release.**

## G0 acceptance and P2 scope

The previously blocked pre-G0 audit on PR #158 is preserved as source inventory only. Independently accepted **G0 contract 2.0.0** is pinned to `59d28dc23be97de2a6a82d22be8338151e31f5b6`, with acceptance publication PR #161 and review record `docs/nba_architecture/G0_ACCEPTANCE_AND_DOWNSTREAM_AUTHORIZATION_20261116.json`. G0 permits downstream engineering, not a family G1 pass. A separate NBA parallel prompts packet was not visible in this execution; this handoff applies the user's P2 text and the signed versioned G0 interface. `main` does not contain the accepted contract; this is a stacked research draft targeting the accepted G0 branch.

S owns only conditional player outcome distributions. P1 owns verified source/identity/time stores, G owns game-state, O owns participation/minutes/finite pools, J owns coherent same-draw game outcomes and C owns evaluation and calibration. S/O/J are not votes. Legacy Engine A/B, Bayesian A/B, NUTS, 60/40 remain frozen benchmarks.

## Prior-code audit (actual inspected blobs)

| Implementation | Read-only reuse conclusion |
|---|---|
| `scripts/bayesian_engine.py` blob `3dfe8a94dbd0ed07e7af396cef571e322692a480` | Gamma–Poisson/Poisson/NB posterior and cutoff logic; line-specific shadow output only, not full G0 PMF. Reimplemented as separate deterministic count kernels. |
| `scripts/nba_prior_bridge.py` blob `04079df2397d1ec9138e745194a0a1264c6f488b` | Historical early-season shrinkage and effort/rate decomposition useful as design; its own workload projection is **not** an O input. |
| `v2/nhl_nba_phase1.py` blob `e500b72100e4864ee9ba8f0fa886ad522ec2b058` | Poisson count-rate counterfactual control, not certified original pregame. |
| G0 `v2/nba_architecture/v2_contracts.py` blob `920d10390553f1de5635b5efbc9437d45212db74` | Contract 2.0.0, full integer PMF, `sum(p)=1 ±1e-10`, tail omitted upper bound ≤1e-8, SHA-bound identity/times, exact O/U/P. **Unmodified.** |
| G0 `v2/nba_architecture/families_v2.py` blob `6fc93fa4568523da534da082806e058d4309d967` | O/G/J real validation and exact conservation. S consumes and never edits. |

## Implemented interfaces and scientific assumptions

`v2/nba_s_family/model.py` supplies `fit`, `conditional_pmf`, `predict_conditional`, `predict`, `exact_triplet` and typed `SFError` / `Prediction` / `FittedS`. `fit` accepts strict source-verified prior-game rows with `count`, **historical** minutes, previous outcome availability and source receipt hashes; all rows must precede `asof_cutoff_utc`. It never opens a network, retrieves an official outcome, or reads target-game minutes. Training player histories and other-player role priors are separated, and data are canonical-sorted before content-addressing. Actual source legitimacy must be demonstrated by P1; a `P1_VERIFIED` flag in a synthetic fixture does not create that evidence.

- **S0**, Poisson control, past per-game count mean, *S_ONLY*. Does not silently fill unknown target participation. It assumes known participation for an eligible player and explicitly abstains otherwise. Simple control, not a calibrated champion.
- **S1**, Gamma–Poisson: player-specific rate `λ ~ Gamma(α, rate β)` with cross-player same-role peer shrinkage; for given O minutes `m`, `Y|m ~ NB(α, β/(β+m))`, `E[Y|m]=αm/β`, `Var(Y|m)=E[Y|m]+E[Y|m]^2/α`. Peer games are excluded from the target likelihood. The posterior rate standard deviation is recorded.
- **S2**, conditional NB2 challenger with mean `μ=m α/β`, dispersion `k` fixed and predeclared, variance `μ + μ²/k`. This is a **different statistical hypothesis**, not a separate independent vote or proven superior distribution. No NUTS or learned nonlinear weight fitting.
- **S3**, Beta–binomial `3PM | projected 3PA=n ~ BetaBinomial(n, α, β)` with `0≤3PM≤3PA`. Requires upstream *scenario-projected integer* 3PA; an observed target game's 3PA cannot be supplied by this layer. No S3 standalone pregame PMF is asserted until projected-attempt scenarios are legitimately available from O/J.

Each count law returns a complete nonnegative integer mass representation after numerical truncation with an **explicit bound on omitted positive tail**; the small truncated tail is renormalized *conditionally on retained support*. It therefore does not claim impossible exact zero tail. `p0`, means, variance, source profile, training cutoff, model/artifact digest, RNG seed and input SHA are preserved. `predict` produces the unchanged G0 v2.0.0 `S_ONLY` or `S_O` envelope; `S_O` verifies and uses **the exact supplied G/O scenario IDs, weights, played/DNP state and minutes**, not a new opportunity sampler. `predict_conditional` is a conditional kernel intended for J, not a publication-grade stand-alone forecast. J must verify scenario source, identity and physical caps when generating outcomes. S never produces PR/PA/RA/PRA as independent convolutions or separate votes.

The S/O predictive mixture is mathematically exact **for the finite supplied weighted O scenario law**, but it does not certify the O scenario approximation itself or the coverage of all possible rosters/roles. `opportunity_scenario_ess` is a descriptive weighted scenario diagnostic, **not independent observed games**. Uncertainty is explicitly divided into distributional mean/variance, rate-posterior uncertainty for S1, finite weighted O law, and unavailable externally calibrated accuracy. Target-game cap constraints from shot/rebound/team accounting require J. S is a statistical kernel, not a complete physically conserving whole-game simulator.

## Fail-closed rules

Reject missing/naive UTC, source late after fit, source SHA mismatch, mismatched player/game/stat identity, duplicate game-player-stat observations, noninteger/negative counts, training data from target or future game, zero historical exposure with positive count, 3PM greater than 3PA, missing/unknown pregame participation for S0, missing G/O evidence for S1/S2, altered G/O content hashes, no played conditional scenario, invalid or unsafe tail. Returned `Prediction.abstain_reason` records the exact model guard; no fabricated zero or optimistic timestamp.

## Reproduction

Install project-required `numpy`, `scipy`, `jsonschema`. From root:

```bash
python -m unittest discover -s tests/nba_s_family -p 'test_*.py' -v
python scripts/nba_p2_s_family_example.py
python -m unittest discover -s tests/nba_architecture -p 'test_*.py' -v
```

The four-stat example is synthetic only; `P1_VERIFIED` there is an illustrative interface value, not a real P1 approval. Local isolated test results that use minimal substitute G0 stubs **cannot** count as exact-G0 conformance. The authoritative tests require a checkout of the accepted contract SHA with original G0 validators and `tests/nba_architecture/golden_v2.py`. See execution receipt for what actually ran.

## Gate disposition and downstream handoff

**P2 code status:** implemented, research-only, G1 not independently accepted. **G0:** accepted at exact SHA for P2 starting permission; **P1 live source coverage:** unavailable here; **P3 O real participant scenario feed:** not provided; **P4 J real shared scenario adapter:** not supplied; **P5/P6 independent exact-SHA scoring and adversarial QA:** pending. No retrospective accuracy, no weight fitting, no promotion or Tier claimed. S2/S3 remain shadow challengers until a separately preregistered historical experiment establishes whether they are useful. NUTS/nonlinear methods remain deferred. This PR should remain **draft and unmerged**.

**Required handoffs:** P1 supply immutable P1-verifiable authentic observation rows and pregame source; O provide timestamped probability and lawful minutes/scenario support; J use `predict_conditional` only after authoritative G/O validation, with bounded physical event opportunities and same-scenario sums; P6 rerun independent math, leakage and G0 contract tests at the exact P2 branch commit. A P2 G1 PASS is not an author self-approval.

## Subsequent exact-G0 verification (November 16, 2026)

The research Deepnote clone actually executed against the accepted G0 source at PR head `f3a249258f72dea900a74b7061d4e78c19992a2b`: **22/22 new S tests PASS** (detached run `10143798-7d8b-434c-a255-0a0bab82f106`; 1.024s Python subprocess) and **267/267 original G0 tests PASS** (live run `26c33ec8-b1a1-4121-a430-f709dfb2c8fd`; 7.828s subprocess). Test execution used Python 3.12.16, NumPy 1.26.4, SciPy 1.15.3 and jsonschema 4.23.0, with no test failures/errors/skips. These are **engineering conformance tests**, not validation of actual NBA predictions.

The first attempt at running `python scripts/nba_p2_s_family_example.py` on that research clone failed with a `ModuleNotFoundError` from executable-path import discovery. It was fixed **only in the standalone example script** at commit `229a53d316cb9aec68f21ad8cc697075bbef4d8b` and passed a local smoke test from a foreign cwd. No S model, S test or G0 file changed after the successful exact-G0 run. A subsequent remote run attempt was rate-limited; full final-HEAD execution remains to be recorded if feasible. See `reports/P2_S_LOCAL_EXECUTION_RECEIPT_20261116.json` and local performance benchmark. No independent P6 acceptance was made.

## Local numerical throughput (bounded synthetic receipt)

Python 3.13.5 on the isolated local CPU container: 500 S1 conditional PMF evaluations for each of four statistics took **1.1408 s points**, **1.1271 s rebounds**, **1.1176 s assists**, and **1.0854 s threes** (roughly 2.2 ms per conditional PMF), under `tracemalloc` overhead; peak traced Python memory about **4.91 MB**. Six-row fixture fits per stat completed in under a millisecond. These are **small synthetic-kernel measurements only**, not training on historical NBA or whole-game forecast latency. Complete machine-readable receipt: `reports/P2_S_LOCAL_BENCHMARK_20261116.json`.
