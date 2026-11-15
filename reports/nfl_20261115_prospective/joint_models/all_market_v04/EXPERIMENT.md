# WS4 all-market extension (v0.4.0)

Authority: PA-V25-MASTER-2026-11-09 / v1.1; explicit November 15 user authorization for this bounded WS4 research extension. No production, NUTS, collection schedules or betting-selection changes. Status: implemented/tested/shadow-only; scientific promotion blocked. Supporting research rules 3, 7–9, 11–15 apply.

Hypothesis: shared team opportunities and constrained allocations preserve useful composite covariance. Negative control: independently permute component draw ordering, retaining marginal distributions but removing paired covariance. Evaluation requires future matched chronological proper scores and game/date clusters; no accuracy or edge claim from conservation tests.

The existing `game_once` gains one opt-in dispatch. It still generates shared pace, team pass/rush/sack budgets, and starting-QB attempts. The conditional extension allocates those budgets; it does not separately generate player opportunity totals. v0.3.1 input packets never enter the opt-in dispatch, and the existing seed/version path remains unchanged.

J1 uses fixed historical role and conversion parameters with shared stochastic game volume and finite allocation. J2 retains the existing Gamma pace uncertainty and adds Dirichlet role allocation, Beta catch-rate uncertainty, and empirical game-average yard-mark variation. Concentration 28, Gamma shape 25 and the two-target position pooling strength are frozen sensitivity settings, not empirically calibrated dispersion. J3 requires original certified scenario inputs and abstains for the current sources. J4 remains a diagnostic only.

Historical conditional marks use observed player-game yards/reception and yards/carry. They are **not individual-play tracking**. Signed gains are supported, but this approximation lacks calibrated within-game tails. Spikes/throwaways are in the unallocated attempt bucket, sacks outside official attempts, scrambles/kneels inside official carries. The aggregate source does not identify these separately; no arbitrary rates are assigned. This is aggregate opportunity coherence, not a play-by-play reconstruction.

The source universe comes from all archived ESPN roster identities, irrespective of bookmaker offers. Missing crosswalks, same-team history or expected-QB evidence abstain. No receiver is allocated extra team volume to match an old per-game average. Same-team 2025 histories exclude new-team/rookie role transfers instead of guessing. Active status is unconfirmed: all forecasts remain conditional on appearance. Defensive T+A abstains because authenticated exposure and reconciled official combined credit are missing in the WS1 handoff. No separate defensive outputs are produced by the new path.

Weather: WS1 final certified handoff pin `a80bc6ad4d5059e8db283516fe6c97587803b17fea2247c33af228d39554ef86`; historical weather-vintage fitting rows 0 per WS1 handoff. Weather-neutral execution uses no weather response multipliers. Estimated-weather count 0.

Outputs: create-only, content-addressed JSON contains frozen parameters, source hashes, implementation hashes, exact original quote identity, distributions before contracts, matched draw series, residual/team state arrays, quantiles and MC errors. Composite variance uses population covariance consistently with population predictive variance. Effective simulation draws refer to independent Monte Carlo draws, not statistically independent games or contracts.

Reproduce: `python -m unittest discover -s reports/nfl_20261115_prospective/independent_validation -p 'test_*.py' -q`. Prospective execution requires the authenticated Deepnote source bundle and a future kickoff: `python reports/nfl_20261115_prospective/joint_models/all_market_v04/execute.py --limit 1`. Never rerun historical pregame forecasts after kickoff. Verify frozen results with `audit_all_market_v04.audit(path)` without importing simulator logic.

Rollback: stop calling the opt-in extension; retain every v0.3.1 and v0.4 frozen file. No historical output is replaced.
