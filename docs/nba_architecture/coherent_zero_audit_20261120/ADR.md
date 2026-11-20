# G1 continuation — S4/J zero-state prior audit (shadow only)

**Parent:** PR #193 published commit `7ed800d86b6f3f3e97314d2339dd8016f104d744`.
**Authority:** PA-V25-MASTER-2026-11-09 / v1.1, and November 19
`source_listed_subset` amendment. This is a new isolated *read-only*
auditing branch. The saved PR193 model, 64-scenario bank, original source
captures, forecasts, accepted review receipts, old S1 and physical simulation
code are not edited. No historical refit, forecast issuance, settlement,
holdout scoring, optimizer training, deployment, or production scheduling.

## Unresolved issue

The adopted S4/J law draws a latent independent
`Z~Beta(.5,49.5)` for each named player and scenario in
`v2/nba_joint/residual_opportunity_v1.py:draw_team`.
With a circular uniform quantile `U`, the player's zero-minute event is
`U <= Z`. Consequently its *unconditional O-prior* zero-minute marginal
is `E[Z]=0.01`, not zero. The phrase **all 14 named participate** therefore
must not be interpreted as an unconditional guarantee that all named actors
play positive minutes in every sampled world; nor does `model_participation_conditioned`
establish a true game-day participation probability.

For beta-minute shape parameters `a,b`, game duration `G`, and
a chosen fixed zero weight `z`, the prior CDF on `0 <= t < G` is:

```text
P(M <= t | z,G) = z + (1-z) * I_(t/G)(a,b)
P(M = 0 | z,G) = z.
```

A fixed `z=.01` matches the original beta-mixture's *single-player
marginal CDF*. It does not generally preserve the *joint* minute distribution,
correlation of zero states, anonymous residual allocations, distribution of
downstream events, or S4/J probabilities. A simple 64-draw bank is not enough
to certify joint numerical sensitivity or market calibration.

## Implementation boundaries

- `v2/nba_joint/coherent_zero_audit_v1.py` computes a deterministic
  analytic grid at regulation (48 min) and one-overtime (53 min) durations,
  over z = 0, .005, .01, .02, .05 and thresholds 0, .5, 1 minute.
  This is an **O-prior diagnostic** only. It also audits each *frozen*
  accepted path's exact named-player zero-minute rows for impossible
  credited box-score events, retaining every scenario and identity.
- `scripts/nba_coherent_zero_audit.py` is a read-only entrypoint. It
  requires the exact original BANK and fitted-model SHA256 and their
  semantic join. By default it prints a versioned receipt to standard output.
  Optional output uses exclusive-create mode, never overwrites the frozen
  packet. The script does not fit or generate a model/forecast.
- `tests/nba_joint/test_coherent_zero_audit_v1.py` covers analytic
  monotonicity, zero support, duplicate/invalid weights, missed identities,
  zero-minute credited stats, immutable-frozen input hashes and bank population.

Run from the repository root on this branch:

```sh
python -m unittest tests.nba_joint.test_coherent_zero_audit_v1 -v
python scripts/nba_coherent_zero_audit.py --output /tmp/nba-s4-zero-audit-new.json
python -m unittest discover -s tests -q
```

The precise original bytes are restricted to the published PR193 roots:
model `f1f6dd4a4d3753042c28b71fa9b7949628d69ccdad8f38ece47bb2ccdc6ffa2a`;
bank `318bb9b2317ae120b6b51852a88b97177424fc0caeba36ed8b38b4f6ead01d88`.
This receipt does not assert that those frozen source inputs or
participation probabilities are scientifically certified.

## Stop/go and next scientific tickets

**Potential G1 contract mismatch**: if the saved bank contains named
zero-minute draws, the strict all-14-positive-minutes reading is refuted by
an executable counterexample. Regardless of realized zero count, the law
assigns positive prior probability to zero minutes and does not represent
observed legal participation. Do not silently relabel this conditioning as
validated `played` or certify target outcomes/lines.

The remaining **full S4/J zero-state sensitivity** requires a separately
versioned, preregistered common-random-number event-path experiment with
zero-weight alternatives and fixed cutoffs, including rejected paths,
complete denominators, query-level probability shifts and appropriate Monte
Carlo uncertainty. It must not overwrite or recycle the originally frozen
64 forecasts. The analytic audit does *not* close that later experiment.

Genuine player-day participation/eligibility, official prospective target
settlement, original historical pregame S4 inputs, coherent holdout scoring,
family optimization, G1/G2 approval and Tier/production promotion remain
**BLOCKED/SHADOW**. Rollback is to stop invoking this new audit reader,
leaving the old branch and its immutable receipts untouched.
