# NUTS sampler checkpoint feasibility — Pick'em Auditor

Status: **investigation and design only; no production code enabled**  
Date: 2026-11-03  
Current campaign: `week-20261102`; current fitting code is pinned to an earlier SHA and MUST NOT be interrupted for checkpoint work.

## Verified existing system

- Source: `scripts/joint_population_bayes.py` calls `pm.sample` once for the entire fit.
- `requirements-joint-bayes.txt`: `pymc==6.3.2`, `arviz==1.3.0`, `arviz-stats==1.3.3`.
- Four independent NUTS chains, two concurrent cores, 1,800 warmup + 2,000 retained iterations per chain, target_accept=0.99.
- `scripts/precision_sampling_progress.py` receives a **per-draw callback** and writes progress.json. It does NOT persist the complete NUTS state.
- The final `posterior.nc` is saved **only after** `pm.sample()` returns. Today's frozen replay cache stores historical code and data, not the sampler's random state.
- No sampler change can recover ten hours of draws from the original aborted SOG run.

## Upstream findings

1. PyMC's `pm.sample()` has a per-draw callback but **no documented full-state resume/checkpoint API**. An upstream PyMC enhancement request for `checkpoint_file` remains open: https://github.com/pymc-devs/pymc/issues/7503
2. PyMC `ZarrTrace` can stream partial samples to disk, but an on-disk trace **alone is not sufficient to resume identical NUTS dynamics**; it doesn't guarantee preservation/restoration of adaptation, sampler internals, and RNG state. See https://www.pymc.io/projects/docs/en/stable/_modules/pymc/sampling/mcmc.html
3. **NumPyro** publicly documents `MCMC.last_state`, `post_warmup_state`, and sequential runs that skip already-completed warmup. A true durable checkpoint must serialize the full state, all per-chain RNG keys, draws, and sample statistics, restore identical compiled model and backend, and verify state integrity: https://num.pyro.ai/en/latest/mcmc.html
4. **BlackJAX** exposes adapted step size and mass matrix plus chain state; custom control loops can checkpoint those alongside RNG keys and posterior chunks: https://blackjax-devs.github.io/blackjax/examples/quickstart.html
5. `pm.sample(nuts_sampler="numpyro")` alone is **not a checkpoint implementation**. For reliable state persistence, an independent driver must operate the underlying sampler and preserve its states and outputs. The current model has continuous **latent** variables (even though count observations are discrete), so JAX NUTS may be feasible, but full-model JAX compilation and performance are **not validated**.

## Recommended development — isolated opt-in challenger

**Phase A: Validate backend without changes to production.**
- Compile the full `joint_population_bayes.build(data)` graph into a JAX-compatible log density.
- Benchmark small NHL SOG and hits cohorts on the Dell. Confirm all latent effects, transforms, deterministic variables, shape/index mapping, 4 independent chains, posterior chain/draw dimensions, and sample-stat fields.
- Confirm that full-player training memory and compilation are stable under 32 GB RAM and two simultaneous chains.
- Compare posterior estimands, R-hat, bulk/tail ESS, divergences, E-BFMI, predictive calibration, and wall-clock/CPU memory to incumbent. No automatic model promotion.

**Phase B: Real checkpoints after completed warmup.**
- Run warmup **once per chain** (1,800 steps); persist final NUTS state, step size, mass matrix, RNG key, and model/input/version checksums.
- Draw posterior in **chunks of approximately 250 iterations per chain** and save each chunk's samples + energy/divergences/treedepth/acceptance stats with an atomic, SHA-256-verified manifest.
- Commit the sampler state and the matching complete chunk together; only advance the durable journal after both have been safely flushed and hashed. An interruption mid-chunk can replay just that uncommitted chunk.
- Resume from the last fully-committed point; do NOT rerun warmup or duplicate sample indices. Preserve the original per-chain RNG stream where deterministic reproduction is supported.
- Write to `~/pickem-training-frozen-cache/campaigns/CAMPAIGN/market-XX/` outside GitHub's cleanup workspace. Report checkpoint phase and per-chain iteration counts.
- Keep disk-size limits, atomic journal rotation, backup checkpoint, and strict prior-state integrity validation. Fail closed on SHA/code/shape/version/environment mismatch rather than silently altering the posterior.
- Reassemble ArviZ samples and sampler stats in original chain order. Existing strict diagnostics remain authoritative; no ranked predictions from incomplete chains.

**Phase C: Investigate mid-warmup checkpoints separately.**
- NumPyro's high-level `post_warmup_state` only makes a *finished* warmup restartable. Recovering partway through warmup also requires the evolving **adaptation state**, warmup window schedule and step counter, chain position, random state and sampler internals.
- Consider a BlackJAX lower-level adaptation loop or a carefully tested NumPyro per-transition control loop with *complete* state serialization. Do not treat repeated short `warmup()` calls as equivalent to an uninterrupted 1,800-step adaptation schedule.
- Until validated, an interruption during warmup still loses incomplete warmup; describe this explicitly in recovery receipts.

## Acceptance gates before replacing current PyMC code

1. A seeded toy NUTS model run without interruption and the same model run with a forced interruption after a posterior chunk produce equivalent, complete chains with matching state continuity; where determinism is supported, compare draw-by-draw, not just distribution summaries.
2. Forced interruption mid-warmup is either **recoverable and independently validated** or explicitly marked restart-warmup; no false claims.
3. Validate interruption during atomic write, corrupted manifest/data, missing checkpoint chunk, wrong model SHA, frozen data SHA, Python package version, and divergent chain dimensions.
4. Compare all retained sample statistics and strict effects-based convergence checks to an uninterrupted reference. No scientific gates weakened.
5. Validate cache size, GitHub runner permissions, Windows PowerShell behavior, 32 GB memory, and CPU time at full SOG dimensionality.
6. Full 4-chain small-cohort benchmark must pass before any NHL/NBA/NFL campaign switch.
7. **Never alter an active frozen campaign run.** The incumbent backend remains default; checkpoint-aware driver is opt-in until pilot comparison passes.

## Practical conclusion

**Yes, safe checkpointing is technically feasible, but it is not currently implemented or verified for the joint PyMC model.**

The least risky useful milestone is **save after full warmup + resume 250-draw posterior chunks**. A later milestone should checkpoint the *adaptation/warmup* phase itself, which matters greatly for 40+ hour training. The existing local frozen-history cache is complementary; it does not preserve Markov chain state.
