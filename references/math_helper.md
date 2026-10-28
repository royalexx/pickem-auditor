# Ranking

For verified published picks, see [mechanism-quality policy](mechanism_quality.md): audited source evidence imposes a Tier ceiling instead of the legacy count of named mechanisms. The numeric probability bands below are unchanged.

Ranks, from strongest to weakest: Tier 1 (Unicorn), Tier 2, Tier 3, Watchlist, Reject, Unranked.

The probability floors are fixed. Do not lower them to produce more names.

| Rank | `q_grade`, the model's unconditional P(win) |
|---|---|
| Tier 1 numeric band | 58.0% or higher, and the comparable market benchmark is also at least 58.0% |
| Tier 2 numeric band | 57.0% to 57.9% |
| Tier 3 numeric band | 56.0% to 56.9% |
| Watchlist | 52.0% to 55.9%, or any stronger number capped by flags or by a gap of 8.0 points or more |
| Reject | Model P(win) below 52%, or a hard veto |
| Unranked | The market or the player sample is too thin to grade |

`q_grade` is the model's unconditional chance of winning. It is not the lower of the model and the market, and it is not a calibrated true probability. The market is a separate benchmark. A gap above 3.0 points adds a flag. A gap of 8.0 points or more caps the rank at Watchlist. A model at 57% can still be Tier 2 when the market is a few points lower. A model at 53% does not become a play because the price is short. Tier 1 still requires both numbers to clear 58%.

The numeric band is not the final rank. Soft flags cap the rank. The Unicorn checklist in Stage H is required before the word Tier 1 is used. A hot streak, a juiced price, or a model printout of 58% is not, by itself, Tier 1.

| Soft flags after `grade` | Maximum rank |
|---|---|
| 0 | Tier 1 |
| 1 | Tier 2 |
| 2 | Tier 3 |
| 3 or more | Watchlist |

A strong Under is eligible for Tier 1. Low minutes, low ice time, or a small snap share is a reason to look at an Under, not a reason to discard it.

# Engine A: history-v5

`scripts/pickem_math.py project` uses historical numbers only. It accepts old context
arguments for compatibility, emits CONTEXT_EXCLUDED_FROM_ENGINE_A, and excludes
workload, rate, opponent, pace and funnel multipliers from the forecast.
The legacy output name `shrunk_mean` now means the historical forecast mean.

For a stable role with disjoint baseline, recent and capped same-role prior windows:

    mean = (n_base * mean_base + n_recent * mean_recent + n_prior * mean_prior) / N
    N = n_base + n_recent + min(n_prior, 20)

The prior numerator uses the capped count too. Windows cannot overlap. Recent windows
below five games are ignored unless a confirmed historical role change applies.
For a historical role change with r recent games, the old-role prior has total weight 8:

    mean = (r * mean_recent + 8 * mean_old) / (r + 8)
    effective_n = (r + 8)^2 / (r + 8^2 / n_old)

This Kish count is an approximation under independent equal-variance observations;
serial dependence and old/new role variance changes are not estimated here.
`current_role_n` excludes prior-season games. No current-role sample is Unranked;
upcoming workload expectations cannot bypass that block.

Normal `sd_used` stays the observed input sd. No coefficient-of-variation rescaling
is inferred from a change in mean. A negative Normal tail above 2% blocks grading.
Poisson uses mean=variance. Negative binomial uses variance=var_ratio*mean;
1.10 or less means use poisson. Ratios above 3 are capped with a flag.

`q_win`, `q_push`, `q_loss` are unconditional, mutually exclusive probabilities.
A push is never a win. Integer-valued Normal approximations use continuity correction.
`q_win_robust` integrates uncertainty in the mean. Poisson uses exact Gamma-Poisson
negative-binomial prediction; Normal uses exact convolution with variance
sd^2 + mean_se^2. Negative binomial retains 41-point Gamma quantile integration.
This is a moment-based uncertainty approximation, not full Bayesian inference.

# Engine B: scouting-v7

Current reliable Engine B uses the collector-owned history path in
`shared_context.md`. The following scenario path is retained as **diagnostics only**.

`scripts/scouting_engine.py` can inspect qualitative research on matchup, opportunity,
injuries, and game_script. It requires fresh confirmed fact objects with citations
for all four dimensions. Neutral evidence is valid; unknown evidence means abstain.
The engine receives no Engine A mean, and no sportsbook probability.

A research packet holds `scouting[SPORT|Player|stat|side]` with `evidence`,
`supporting_stats` and `scenarios`. Complete the sport/stat advanced checklist in
`references/advanced_scouting.md`. Each scenario lists sourced `drivers`; missing
supporting categories prevent reliable status. At least two full-game scenarios must have positive weights summing
to one, opportunities, conversion (e.g. yards per target), a distribution and a
written rationale. Supply `sd` for Normal or `var_ratio` for negative binomial.

    mean_s = opportunities_s * conversion_s
    P_B(win) = sum(weight_s * P_s(win))
    P_B(push) = sum(weight_s * P_s(push))

`scope` must be `full_game`. A checkdown/first-read subset is not a total-stat model.
`se_b` combines between-scenario spread and propagated mean uncertainty in stat units;
it is not a probability standard error or a calibrated confidence interval. Scenario probabilities are estimates, not
calibrated facts. Missing B cannot add a contradiction flag or authorize Tier 1.

# Probability blend and publication

The pipeline always uses A's uncertainty-integrated probability and B's full scenario
mixture. Legacy `tier_basis=q_win` is accepted for compatibility but cannot switch
published grades back to point estimates. Scan reports label their effective basis.

For validated weights w:

    q_model = w * P_A(win) + (1-w) * P_B(win)
    q_push  = w * P_A(push) + (1-w) * P_B(push)

The market stays an external comparison. It is not a third prediction engine.
`scripts/probability_blend.py` fits convex weights on earlier settled forecasts,
scores unconditional win/push/loss log loss (including pushes), checks a later
untouched period, and uses date-cluster bootstrap uncertainty on loss improvement. It rejects mixed sport/stat scopes, duplicate forecast IDs,
old engine versions, insufficient data and non-improving holdouts.
Minimums: 300 training observations, 100 holdout observations and 20 holdout dates.
These minimums and model-selection procedure remain provisional.
Config names are `config/probability_blend/SPORT_stat_words.json`.
A failed or missing config means weights A=1/B=0, explicit fallback and no Tier 1.
An old `config/blend_weights.json` is diagnostic-only and cannot activate blending.
`fit_blend.py` remains a legacy comparison tool, not the production weight fitter.

# Market checks and tiering

Use two-way, same-line, explicitly oriented approved quotes. `q_market` is conditional
on no push on a whole line, so `q_market_comparable=q_market*(1-q_push)`.
Tier floors use unconditional strict-win probability. Copy raw JSON floats, never
rounded percentages. Preserve line_match, side_match, timestamp_fresh, hold_ok and
approved_books checks. Direct q_market requires retrieved_minutes_ago; stale prices
cannot be upgraded by market_valid=true. Dispersion and sample failures are Unranked.

`pipeline --batch --stdin` runs all engines and publication gates in one process.
`grade` and `rank` alone do not enforce two-engine eligibility. Never publish their
standalone labels as completed pipeline results. Scan --stdin is a research prefilter.

# Calibration and reproducibility

Interactive picks are not written to a report file. `log --batch --stdin` is for an
explicitly requested record; shadow jobs are separately configured. Persist engine
versions, individual win/push estimates and actual blend metadata with forecasts.
Never retrain using revised postgame information as though it was available pregame.
Reports that exclude pushes use P(win | no push) for Brier, log loss and reliability.
Tier probabilities remain unconditional. Do not mix those scales.


# Version 4 numeric provenance, reliability and uncertainty

A requires source observation IDs for reliable status, in addition to its sample and
distribution gates. Aggregates without IDs remain diagnostic forecasts; they cannot
qualify for a calibrated blend or Tier 1. IDs must be disjoint across every window.
This proves declared identity consistency, not absence of serial correlation.

B separates `coverage.complete` from `quality.numeric_provenance_complete`,
`quality.data_sufficient`, and `calibrated`. Coverage alone never establishes
reliability. The legacy scenario path cannot qualify as a reliable B even with all coverage,
measured inputs and scenario frequencies. Current reliability requires the
collector-owned history path described in `shared_context.md`.
These floors are provisional safeguards, not empirical calibration certificates.

Each scenario's `numeric_inputs` maps controlled fields to fresh confirmed fact
objects. Their `value` has `estimate`, strictly positive `se`, `n`, `unit`, and an
explicit `embedded_event_ids` list. Use an empty list only when no upcoming causal
adjustment is already embedded. Sample sizes below 20 remain diagnostic. For a
manual NBA points scenario, for example (illustrative schema, not real research):

```json
{
  "numeric_inputs": {
    "opportunities": {
      "fact": "Measured possession estimate",
      "value": {"estimate": 28, "se": 2, "n": 50, "unit": "possessions", "embedded_event_ids": []},
      "source_url": "https://www.nba.com/stats/",
      "retrieved_at": "REPLACE_WITH_VERIFIED_ISO_TIME",
      "confidence": "confirmed"
    },
    "conversion": {
      "fact": "Measured points per possession estimate",
      "value": {"estimate": 0.9, "se": 0.08, "n": 50, "unit": "points_per_possession", "embedded_event_ids": []},
      "source_url": "https://www.nba.com/stats/",
      "retrieved_at": "REPLACE_WITH_VERIFIED_ISO_TIME",
      "confidence": "confirmed"
    }
  }
}
```

Inspect the actual source and estimator before filling these values. Do not copy
illustrative estimates, sample counts, generic URLs or timestamps into a live packet.
All units are enumerated in `scripts/scouting_inputs.py`. Bounded conversions
(receptions/target, completions/attempt, makes/attempt, saves/shot, etc.) cannot exceed
one. Points and yards per opportunity can exceed one. A source observation being
confirmed does not establish that an estimator is accurate.

For NFL receiving `numeric_inputs` must contain `expected_pass_attempts` (unit
`pass_attempts`) and `conversion` (`receptions_per_target` or `yards_per_target`).
For tackles + assists it contains `expected_defensive_plays` (unit
`defensive_plays`); conversion is computed by the season mechanism. Scalar copies
are optional assertions and must match resolved values. Never supply manual target
volume beside season-generated targets. The combined-credit season mechanism is
incompatible with solo `tackles`; solo props require separate supporting data.

Supply `scenario_weight_evidence` at the scouting packet level as a fresh confirmed
fact with value `{"counts":[40,60],"method":"Describe comparable observed regimes"}`.
Counts must be nonnegative integers matching the scenario weights after dividing
by their total. Fewer than 50 observations cannot qualify as reliable. Two narratives
with arbitrary 40/60 weights remain diagnostics. Do not invent comparable regimes.

Apply numeric context through each scenario's `adjustments`, not pre-adjusted free
scalars or annotation-only `applied_effects`. A change has `factors` keyed by controlled
input, plus a fresh confirmed `evidence` fact with a root `event_id` or `causal_event`.
Its fact value is `{"factors":{"opportunities":1.1},"factor_se":{"opportunities":0.05},"n":50}`.
Evidence factors must match the change; factor SEs are positive. One root event can
change multiple inputs in one joint factor map. The code executes this map and emits
the ledger; repeated roots or roots already embedded in any baseline are rejected.
Changes may recur across mutually exclusive scenarios. Do not add annotation-only
effects to controlled scenarios. Legacy free scalars are untrusted diagnostics, so
unrecorded changes in them cannot promote a published probability.

For each scenario, relative input SEs and the season sampling approximation are
added before integrating uncertainty in the scenario mean. This first-order
approximation permits correlated errors rather than assuming independence; it is
not a guaranteed uncertainty bound or a new fitted prediction model. Existing
Gamma/Normal integration is reused, including the predictive Normal negative-mass
gate. Report both point and predictive probabilities. Between-scenario variation
is mixed once. Dispersion uncertainty and regime transportability remain unvalidated.

Season reliability floors: independent offense targets >=100, recipient targets >=20,
>=3 passer games, known-read coverage >=80%, matched defense targets >=100, and >=10
observations in each used read-bucket comparison. Tackle profiles require >=100 own
and opponent plays, >=20 credits, >=3 credited games, and >=30 own plays per used
category. Sparse raw ratios remain visible without reliable status; they cannot
promote B. Role/play-mix overrides with unmeasured uncertainty also remain diagnostic.
No automatic injury or weather coefficient is fitted.

`scripts/jobs.py weekly` now fits the current per-sport/stat runtime weights. It
retires previously active configs when current evidence fails and reports each scope.
Only current-engine reliable forecasts with timezone-aware `forecast_at` and
`event_start`, with forecast strictly before start, qualify for snapshot conversion.
Unknown start times and legacy records are excluded. Store these fields when logging
manual forecasts too. The fitter uses joint three-outcome log loss; the ordinary
binary report remains explicitly conditional on non-push outcomes. Earlier engine versions and binary-only configs cannot activate this runtime. No validated weights are shipped.


The latest ownership contract is `shared_context.md`: A and B baselines are verified
against collector observations; upcoming event adjustments belong only to the shared
context layer. Free researcher totals cannot authorize any published tier.
