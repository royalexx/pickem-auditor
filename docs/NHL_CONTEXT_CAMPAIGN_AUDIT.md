# Local campaign follow-up audit — 2026-10-30

This follow-up completes the local orchestration around the contextual NHL
challenger described in `NHL_CONTEXT_CHALLENGER.md`. NHL saves is the first
real-data pilot; shots, blocks, and hits remain separate later experiments.

Changes audited here:

- A bounded collection plan selects training games, holdout games and their
  prior team-game dependencies without using outcome magnitudes for selection.
- Multi-season pilot selection prevents expensive sampling of a model that
  cannot score its first unseen-season holdout.
- Raw boxscore/PBP replay detects consistent but forged normalized counts.
- Frozen training allowlists bind planning to the actual fitted cohort.
- Campaign OS locks, configuration/code/runtime identity and output hashes
  prevent duplicate sampling and unsafe reuse after changes.
- The incumbent refit validates source outcomes and frozen input digests.
- Holdout scoring excludes targets unavailable at the evaluation endpoint;
  this is independent of the pregame feature-availability checks.

Verification performed during this follow-up:

- Full standard-library offline suite before the final endpoint-availability
  regression: 861 tests, pass, six skips.
- Updated campaign suite after that change: 14 tests, pass, including the
  exclusive endpoint boundary and successful availability one second later.
- Isolated real sampler smoke: one test passed in 22.8 seconds, exercising
  all four market graphs, multiseason branches, short saves sampling, posterior
  roundtrip, bounded minutes and rejection of insufficient convergence.
- The sampler smoke intentionally uses only 25 warmup and 25 retained draws
  in two chains. It establishes executable interfaces, not convergence or
  predictive quality. The earlier larger synthetic fits are documented in
  `NHL_CONTEXT_AUDIT_2026-10-30.md` and were not rerun for this follow-up.

No real NHL contextual training was run here. Real-source coverage and schema
must first pass locally; the previously observed workspace NHL HTTP restriction
remains an unresolved boundary. The campaign restores IDs from existing history,
so missing recent-history IDs must be backfilled before the pilot can run.
No new evidence establishes predictive superiority or market edge. Production
rankings, Engine A/B blending and the published converged saves posterior are
unchanged. No GitHub Actions training job was dispatched.
