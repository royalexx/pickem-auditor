# NHL SOG Phase 1.5 — Official-roster, fixed-NB2, prospective research pilot

**Implementation date:** November 11, 2026. **Status:** implemented/tested, **not fitted, not live validated, not promoted.** Governing experiment: `config/experiment_specs/EXP_NHL_SOG_P15_RATE_DISPERSION_NEXT_PROSPECTIVE.json`. Full Phase 2, NHL production model promotion, Bayesian/NUTS refits, and Tier 1/2 remain blocked.

### Specific error hypothesis and intervention

The independently settled November 10 original NHL SOG cohort (104 valid contracts from seven games on one date) showed pooled-rate Poisson Brier **0.25616** versus original market **0.25064**, with residual count variability above the Poisson nominal variance. A *single* future challenger therefore keeps the exact same pre-event pooled-history mean `μ` and original line, but changes only the likelihood:

`Y ~ NB2(mean=μ, shape=r=4)`, `Var(Y)=μ+μ²/4`.

**Shape 4.0 is a fixed, predeclared research choice influenced by the November 10 discovery audit, not a fitted optimum.** November 10 cannot be scored as unseen for this challenger. The original rate baseline, same original line, original no-vig sportsbook price, rejected offer ledger, and per-event source hashes remain available for matched assessment. This is not an NBA model or a new NHL performance claim.

### Independent roster authority (source, not model)

The free NHL-hosted URL `https://api-web.nhle.com/v1/roster/{TEAM}/current` exposes `forwards`, `defensemen`, `goalies`, each with numeric player IDs. Official-roster response schema verified against current external documentation and a live Toronto example on Nov 11 (HTTP 200, **29 players**, 26 skaters/3 goalies, raw SHA `31ccf3d8498dcae2eb4bb32e2d6a3bad36a5e4414b37653820f5f78f10e146c6`). The API is documented by the open-source community and is unversioned; external access can fail. This is team membership at *capture time*, not a promise of game appearance or verified starting status.

- `scripts/capture_phase15_nhl_roster.py` fetches each distinct upcoming NHL team's actual raw response, records first locally observed UTC time, exact URL and raw-content SHA, and preserves every source failure in a manifest. Never invent missing membership.
- `v2/phase15_nhl_roster.py` validates both original team and opponent membership, original player ID, timezone, original source bytes and hash, and 6-hour maximum source age measured at the new research forecast time. An opposing-team match, missing player, missing roster, stale receipt or late capture leads to **per-contract abstention**.
- NHL player identity is independently cross-checked **at the new pregame inference time**, fixing the demonstrated *market feed may carry stale traded-team labels* structural defect for the **research shadow path only**. This does not yet change the production runner's own pre-evaluation player roster gate, nor does it confirm line combinations or SOG participation.

### Prospective procedure — order matters

Run on an upcoming slate **while every considered game is still in the future** and after a genuine original bookmaker/source afternoon collection. Never run the generic daily afternoon notebook too early merely to obtain a research sample: the earliest archived original batch is the settlement truth for that day and an early run can lock stale lineup information.

```bash
SHA="$(git rev-parse HEAD)"
DAY="YYYY-MM-DD"       # A real FUTURE local slate date, never Nov10 for promotion

# 1. Independently verify the real original frozen bundle and all prepared
#    attempts using the existing Phase1 source-archive and maths checks.
python scripts/v25_phase1_nhl_nba.py \
  --bundle path/to/original_live_pool_${DAY}.json.gz \
  --attempts path/to/all_prepared_props_attempts.json \
  --code-commit "$SHA" \
  --output reports/p15_${DAY}_pregame_source_checked.json

# 2. Capture authentic provider roster bytes before each event.
python scripts/capture_phase15_nhl_roster.py \
  --phase1 reports/p15_${DAY}_pregame_source_checked.json \
  --code-commit "$SHA" \
  --output-dir reports/p15_${DAY}_pregame_roster_captured

# 3. Freeze research forecast immediately, while roster is <=6h old.
python scripts/p15_nhl_sog_nb2_shadow.py \
  --phase1 reports/p15_${DAY}_pregame_source_checked.json \
  --bundle path/to/original_live_pool_${DAY}.json.gz \
  --attempts path/to/all_prepared_props_attempts.json \
  --roster-manifest reports/p15_${DAY}_pregame_roster_captured/roster_manifest.json \
  --roster-root reports/p15_${DAY}_pregame_roster_captured \
  --experiment-spec config/experiment_specs/EXP_NHL_SOG_P15_RATE_DISPERSION_NEXT_PROSPECTIVE.json \
  --code-commit "$SHA" \
  --output reports/p15_${DAY}_prospective_NB2_shadow.json
```

The last command verifies original live-pool bytes and complete attempt-ledger SHA against the Phase 1 pregame receipt. `v2/phase15_nb2_shadow.py` refuses any contract with a published *actual outcome*, event already started, future input freeze, unavailable historical rate, missing two-sided market, absent independent roster capture, or unverified player membership. All rejected candidates remain in `complete_candidate_attempt_ledger` with explicit reasons.

### Comparison after official events end

Settlement must be attached later through the original exact event/player/stat/line/period official API method; do not modify original research probabilities. Compare fixed NB2 against its *exact same pregame mean* Poisson, original validated median-book market and original final production 60/40 **when present as a genuine pregame separate sidecar**. Primary outcome: paired nonpush Brier across future distinct game dates; secondary: log loss, directional score, coverage, zero/high SOG tails and game/date clustered variation. Release power, bankroll value and Tier accuracy require additional independent dates and compatible payout terms.

### Status and test evidence

- Tests: `tests/test_phase15_nhl_roster.py`, `tests/test_phase15_nb2_shadow.py`; plus existing Phase0R/Phase1, online Bayes and morning scoring suites. Regression checks include raw SHA tampering, wrong-team player, stale/future roster clocks, original bookmaker source mismatch, already-started event, settled label prohibition, incomplete odds, integer pushes, NB2 mass conservation, Poisson limiting behavior and no production authority.
- Deepnote pilot code QA: notebook `05a99e8d7c3a4c80a0902a5abcc8f97b`, run `a468c998-93e1-49b7-8fea-de5803d2dcee`, 11/11 selected test suites passed on branch before the final original-bundle digest addition.
- This implementation does **not** automatically schedule first genuine future trial, claim a prospective data sample already exists, or replace 60/40. A new **future** pregame run is required after this PR is merged, with independent outputs and a separately signed evaluation receipt.

**Rollback:** disable this optional research CLI or revert PR; original archives, production model and daily job schedule are untouched.
