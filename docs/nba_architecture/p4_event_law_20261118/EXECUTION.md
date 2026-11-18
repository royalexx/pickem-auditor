# P4/P0 clocked possession execution and disposition

**B-P4-02 remains blocked.** The new proposal runs a clocked event kernel and reconstructs legal paths in a synthetic setting. The preregistered native comparison fails on path completion and distributional distance. The candidate has no authority to replace the old J law or amend accepted G0.

## Review and pins

Governance is PA-V25-MASTER-2026-11-09 / v1.1, Phase 4 shadow engineering. The frozen P4 base is `865bdb8f4770ac28262e49c3b4901cf1d72a22fb`. Main was inspected at `912bc7010058092ea735dcda0aa941429194474b`. Accepted G0 remains `59d28dc23be97de2a6a82d22be8338151e31f5b6`. Existing constrained-law artifacts, the accepted G0 implementation, workflow settings, and training controls receive no changes.

- Initial proposal and materiality limits were committed at `367dd99`. Pre-execution amendments through `86dfc79` specify timestamp order, scope, finite normalizers, the numerical bridge and completion bias. The original proposal and each amendment are retained.
- An independent reviewer provided [contract critique](independent/CONTRACT_CRITIQUE.md) before candidate execution. See the reviewer files for the independently reproduced obstruction and implementation decision.
- The fixed-seed study executed `2fd8080af2ab255a4311fe0323665979594c125d`. Native P2 `fe46965394ea0f48ef5e9da501ec8ca9e441ce47` and P3 `eb0882b5011f2004c5eaf27cccfdc6297704f261` were loaded through the pinned owner registry. `native_study/inputs.json` includes the frozen G/O envelopes, raw P3 sidecar, operative stints, scenario weights, fitted-artifact identities, all extracted P2 parameters and old full count-law references. Runtime was Python 3.12.14, NumPy 2.3.5 and SciPy 1.17.0.

## Mathematical obstruction

For player 15 in fixed `synthetic:latest:0`, the P2 conditional laws give `Pr(3PM >= 20) ≈ 4.7690783257e-10` and `Pr(PTS >= 60) ≈ 2.7588729050e-10`. A lawful joint outcome has `PTS = 2 × 2PM + 3 × 3PM + FTM`, so the first event is a subset of the second. Their probability gap of about `2.0102054206e-10` lower-bounds the sum of marginal TV distances for any physical replacement. The same bound holds for the sum of KS distances because both events are upper tails. The recurrence and its rigorous omitted-tail bounds are retained under [independent](independent/obstruction.json), together with the extractor that checks the pinned live P2 parameters. This is a counterexample to simultaneous exact preservation in a fixed scenario. It gives no support for the much larger observed discrepancies.

## Event and clock proof

Replaying a possession starts with the designated team in control. The opening action is a turnover, one legal trip, or a single FG opportunity. An unresolved rim-contact miss transitions to exactly one named or unattributed recovery. A terminal defensive recovery transfers control. Offensive recovery retains the same possession and allows one bounded continuation. A nonterminal or retained FT miss never enters the recovery state. A made FG has at most one assist from its distinct teammate on the same five-player lineup. A made shot adds the points and exactly one make to its attempt type. These local transitions enforce integer counters and the scoring identity by induction from zero. Team totals are credited across the same states. A separate reader validates the prefix after every attempted path and reconstructs each player's PTS/REB/AST/3PM and PR/PA/RA/PRA from events.

The effective schedule preserves P3 roster order and checks residence for each player against the inherited 1e-7 minute budget. Raw and effective endpoints are both included. The synthetic retained out-of-bounds assumption makes interior substitutions occur after a dead ball, and no source timestamp or exact early-exit time is inferred. Each possession starts at the previous transfer or period tip. Scheduled slot lengths and the four-second opening offset bound time from acquisition through the last action by 24 seconds. A retained rim miss extends play by at most four seconds. The terminal horn and substitution precedence are explicit. A separately counted empty horn possession closes a period when time remains. Ordinary quarter boundaries reset control with no score restriction. Q4 and nonfinal OTs require a tie if another OT follows, and the final period must end non-tied.

For fixed latents, probabilities of a slot scoring 0–6 points follow by summing the FG mixture and FT trip transitions with the offensive recovery continuation. Signed convolution gives the score difference of each checkpoint block. Required preceding ties reset the difference to zero, so the product of the block probabilities gives fixed-latent acceptance probability Z. The maximum nonnegative convolution normalization residual was `1.94e-14`. An exact rational Cartesian enumeration checks the single-slot recurrence, and exact rational signed-score probabilities check the regulation-plus-OT control. The finite failure probability is `(1−Z)^128` conditional on latents. Neither a fixed-latent Z nor its execution failure probability is an unconditional native player-tail estimate.

## Fixed-seed results

256 independent master-seed clusters, each with four fixed O2 scenarios of weight 0.25. No historical games were observed. No G/O scenario or latent set was redrawn to make an incompatible checkpoint feasible.

| Shared OT | Complete scenarios | Exhausted scenarios | All attempts | Retained rejected attempts |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 256 | 0 | 264 | 8 |
| 1 | 243 | 13 | 10,607 | 10,364 |
| 2 | 47 | 209 | 29,704 | 29,657 |
| 3 | 4 | 252 | 32,541 | 32,537 |
| Total | 550 | 474 | 73,116 | 72,566 |

Only 1 of 256 seed packets completed all four scenarios. The study publishes no pooled forecast PMF. Descriptive per-scenario PMFs for all eight player statistics, including covariance, means, variance, zero counts and named tails, retain each completion denominator in [summary.json](native_study/summary.json). These describe the conditional-on-completion law. Fixed O participation statuses are all played in this cohort. The distinct DNP and played-zero statuses are exercised in an explicitly separate scripted engineering fixture.

In the regulation scenario, player 25 PTS has a mean of 11.2734 against 23.8602 in the fixed-scenario S comparator, a gap of 12.5868 against a mean tolerance of 1.1930. The mean Hoeffding interval is too wide to make that a simultaneous mean rejection by itself. The KS estimate is 0.77947 and its simultaneous lower error bound is 0.59665, exceeding the limit of 0.05. This uses 256 completed seeds for that scenario. The union bound covers 676,800 entries for the regulation comparison and overcounts its declared support and scalar metrics. For the same row, 0 of 256 draws reached 60 PTS, and its unadjusted one-sided 95% upper bound is 0.01163. That supplies no 1e-6 native rare-tail equivalence result. No legacy combo distribution follows from the marginal model, and no combo fit claim is made.

These outcomes reject the present candidate under its preregistration. Native synthetic integration bypasses no source admission guard. Unavailable evidence includes admitted P2 fitted inputs, complete authentic P3 participation and rotations, real event/stoppage timestamps, and predictive validation. G1 remains NO-GO. The fixed pacing, engineered stoppages and event coefficients are properties of this pilot.

## Reproduce and roll back

From the candidate checkout, fetch the pinned owner commits and legacy P2/P3/P6 comparator commits if your clone is shallow.

```bash
git fetch origin fe46965394ea0f48ef5e9da501ec8ca9e441ce47 eb0882b5011f2004c5eaf27cccfdc6297704f261 59d28dc23be97de2a6a82d22be8338151e31f5b6 96d210a6100085640e7e82928ab1c864839fc454 80dbed35f983839f962250ad1c0236061dc6ee00 31435bd571ae1b4a9b7f1e1bbf05e55cef61126f
export OPENBLAS_NUM_THREADS=1
PYTHONPATH=.:tests/nba_architecture python -m unittest discover -s tests/nba_architecture -v
python -m research.nba_p4_clocked.study work/new-clocked-study
(cd docs/nba_architecture/p4_event_law_20261118/native_study && sha256sum -c SHA256SUMS)
```

The native study directory retains all accepted and rejected event prefixes as eight independently decodable Zstandard shards. Each JSONL record contains a seed packet in seed order. It references plans in `inputs.json` by scenario identity. Decoded JSONL hashes identify the exact bytes from the original gzip writer. No outcome changes were made in transcoding. Each attempted path also has a cumulative score checkpoint and every action needed to replay the player and team totals. The compressed denominator file includes owner replay totals for each successful scenario and exact attempt counts for all seeds. Failed path prefixes have no exported outcome totals.

This branch is additive shadow research. Existing systems keep their existing bindings. Close the draft or revert the additive executable commits to remove the pilot while retaining the published evidence. Adopting a future law requires explicit review and a separate versioned routing decision. No production runtime or reader migration occurs here.
