# P3 NBA shared-scenario synthetic precision protocol, frozen before execution (2026-11-21)

Owner: NBA P3; experiment type: **synthetic numerical precision**, not empirical predictive calibration or market performance.

Reference code and input: research/nba_p3_frozen/joint.py and tests/test_nba_p3_frozen.py fake_game()/ForecastTests.setUp() on research/nba-p3-soj-frozen-forecast-20261121. The test-created two-team, six-player-per-team game, fitted **synthetic** player efficiency and shared pace/OT parameters are held fixed. Code is pinned for the execution receipt.

- Seed: 20261121. Single run per N, same fixed synthetic inputs. J1 variant. Preset scenario resolutions: N=5,000 and N=20,000. No post hoc resolution chosen from favorable results.
- Primary numerical checks: For player espn:player:0:0 and integer counts of points, rebounds, assists, threes, and same-path PRA, compare probabilities P(Y > L) at lines points 20.5, rebounds 5.5, assists 4.5, threes 2.5, PRA 30.5. Require maximum absolute difference <=0.025. This is a coarse finite Monte Carlo precision threshold **specific to these synthetic diagnostics**, not a calibration criterion.
- Secondary checks: Compare expected points and PRA, P(Y=0), and nearest-rank selected quantiles; report max absolute mean difference; do not predeclare a model-accuracy victory criterion.
- Integrity at both N: all scenarios have 240+25*OT per team, each lineup segment has exactly five players, all shooting/assists/rebound constraints hold; source and model synthetic hashes reported. Sum PMF mass within 1e-10 for the five distributions.
- Resource guard: Each N must complete within 240 seconds on detached Deepnote Basic CPU and bounded process memory. For each N report wall seconds and peak RSS (note ru_maxrss is process-high-water, not per-run isolated peak). A cap test rejects N>20,000.
- Computation provenance: scenario count is computational precision ONLY; it is not an increase in observed independent games. Under no circumstances use this experiment to establish actual NBA value or a Tier.
- Action: Retain N=5,000 as cheaper default if checks pass. If checks fail, mark numerical precision INCONCLUSIVE/FAIL and investigate; do not simply promote N=20,000 without repeat/independent evaluation.

Execution receipt must include pinned exact commit, source/module SHA256, fixture identity and synthetic classification, seed, N, CPU/memory, thresholds, resulting probabilities, tolerance decision and code guard exceptions. An error or timeout is a valid failed receipt and must be retained.
