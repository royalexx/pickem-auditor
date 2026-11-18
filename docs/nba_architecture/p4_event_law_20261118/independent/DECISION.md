# Independent B-P4-02 decision

**B-P4-02 remains BLOCKED.** The versioned event implementation at `2fd8080af2ab255a4311fe0323665979594c125d` is independently verified for the bounded synthetic witness paths listed below. It fails the preregistered distributional gate. This review was conducted under PA-V25-MASTER-2026-11-09 / v1.1 by a reviewer who authored no candidate implementation or acceptance limits.

## Independently verified evidence

- The actual native P2 conditional S1 kernels at O2 scenario `synthetic:latest:0`, player `espn:player:15`, require incompatible tails. The independent rational calculation bounds the full negative-binomial tails near 4.76907832567172e-10 for at least 20 made threes and 2.75887290504868e-10 for at least 60 points. The gap lower-bounds the summed marginal TV and KS errors of any physical joint law. The full count tails, archived input SHA and live owner rerun are in `obstruction.json` and `native_obstruction.json`.
- Independent action parsing reconstructs clocked possession continuity, assisted baskets, trip structure, offensive continuation, rebound allocation, lineup credits, player/team totals and score checkpoints. The separate native seed 90901 replays all 323 event attempts across the four fixed scenarios with exact count agreement. All seven event mutations are rejected by both reconstructors. At the fixed three-OT latent profile, an independent team-score convolution gives checkpoint acceptance probability 0.00014881602181545636, with about 98.11% exhaustion probability over 128 proposals. See `candidate_review.json`.
- The raw preregistered study retained 256 seeds, 1,024 fixed-weight scenario paths and 73,116 individual attempts. An independent streaming reconciliation verified every attempt denominator, every rejection checkpoint count, every accepted box via fresh event reduction and every decoded shard SHA. Semantic raw replay covered all 550 accepted attempts and the rejects of the first seed in each of the eight shards, for 2,944 raw attempts total. Only one of the 256 seed packets completed all four scenarios. Regulation/one-OT/two-OT/three-OT scenario completions were 256/243/47/4. No pooled result has authority. See `study_review.json`.
- Two more controls went through the actual P3 builder and pinned P2 reader with explicitly synthetic changed priors. They preserved the provider's `PLAYED_ZERO_MINUTES` and `DNP` distinction with zero credits for both, and integrated a separately drawn early-exit player's 19.2-minute cap. No actual event-time injury exit was supplied. See `native_boundaries.json`.

## Rejection basis

Even the regulation scenario, where all 256 seeds produced an accepted path, fails the preregistered KS distance limit of 0.05. At 17 points for player `espn:player:25`, the independently recovered CDF discrepancy is 0.7794739439164438. Its simultaneous 95% lower error bound under the predeclared method is 0.5966466980293808. The inability of the other scenarios to complete a full forecast packet therefore does not explain this discrepancy. The regression is much larger than the mathematically necessary marginal change. Rare native count-tail equivalence is unresolved. The run also provides no valid test of predictive skill or of the old S3 projected-attempt law as a realized-attempt marginal.

The prototype depends on an explicitly synthetic dead-ball mechanism and its numerical rotation seam interpretation. These enable replay within the chosen generated scope, while actual stoppage times and exact early-exit timestamps remain outside scope. The independent mutation which strips the stoppages from a copied prepared plan passed the original standalone verifier at `2fd8080`. The narrow verifier hardening at `abd732d` rejects the same mutation with `REPLAY_STOPPAGE_LEDGER` and leaves the other replay results unchanged. Both outcomes are retained in `stoppage_followup.json`. An admission-grade reader still needs to bind the effective plan and raw source sidecar before replay. This review independently verified both known inputs and event witnesses.

The contract may be used to reproduce the shadow experiment. Promotion requires a revised, reviewed event law that meets a separately predeclared distributional criterion and a viable fixed-scenario completion policy. A score-block sampler can in principle condition each independent block exactly at fixed latent values, but its finite failure atoms differ from the current whole-path rejection law and would require a new version. A revised sampler alone would leave the regulation distortion unresolved.

Accepted G0 remains at 59d28dc23be97de2a6a82d22be8338151e31f5b6. This decision adds no authentic fitted-input admission, empirical calibration, predictive skill, G1 approval, or release authority.

## Reproduction

From the branch root with exact P2/P3 owner commits fetched and repository numerical dependencies installed:

```bash
review=docs/nba_architecture/p4_event_law_20261118/independent
python "$review/reproduce_obstruction.py"
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python "$review/verify_native_obstruction.py"
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python "$review/review_candidate.py"
# On the exact pre-hardening code, use that checkout on PYTHONPATH to replay the retained red.
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python "$review/review_native_boundaries.py"
PYTHONPATH=. OPENBLAS_NUM_THREADS=1 python "$review/review_study.py" "$(dirname "$review")/native_study"
```
