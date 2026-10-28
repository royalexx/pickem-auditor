# Phase 4 — Historical and prospective predictive validation

**Version:** chronological-validation-v1. **Effect:** read-only; never changes weights, tiers, grading or research gates.

## Sources, provenance and integrity

The sole source of settled outcomes is data/prop_snapshots.jsonl. Each qualifying forecast needs a timezone-aware original pregame timestamp, game start, settlement timestamp on or after start, finite actual stat, and outcome consistent with its original side and line. Event/player IDs are mandatory. The earliest pregame snapshot is selected for repeated event/player/stat/line/side; subsequent forecasts cannot replace it.

Bayesian and Monte Carlo predictions require pregame sidecars from the same original forecast identity, a supported model version, valid parent source digest, an explicit publication veto, and a full probability vector. MC must agree with the stored analytic parent probability. No forecast is reconstructed using later data. Missing Bayesian history remains missing, even when archived historical legacy predictions have settled.

## Chronological scoring procedure

Use the earliest 70% of distinct qualifying game dates as the initial historical period and later 30% as the held-out test period. Dates never cross the partition. Report unconditional win/push/loss log loss, three-class Brier, calibration reliability bins and win-probability expected calibration error; slice by sport, sport/stat, original Tier, side, and explicit role-change/context flags.

Compare Engine A legacy vs Bayesian A, Engine B legacy vs Bayesian B, Bayesian analytic vs Monte Carlo, and legacy/Bayesian/MC diagnostic mixtures of 70% A and 30% B. The diagnostic mixture must not be described as deployed. Only paired same-forecast test observations contribute to challenger-minus-control differences. Negative delta means the challenger scores better. Date-cluster bootstrap resamples whole dates to preserve correlated same-day picks; report a 95% interval only after 100 common forecasts and 20 held-out dates.

An independent walk-forward calibration experiment selects a three-outcome temperature on prior settled outcomes; minimum 300 historical observations and 20 prior game dates. Each training outcome must have been officially settled before the earliest forecast being scored on the evaluation day. No same-day or future settlement can train that day's calibration. Calibrated and original scores are compared on the same prospective test events; the fitted temperatures are never written to production configuration.

At least 300 distinct initial training forecasts on at least 20 dates plus 100 test forecasts on 20 later dates are required before the overall holdout receives a descriptive coverage-qualified status. This is **not approval to promote weights, models or tiers**. Sport/stat and Tier bins with fewer than 30 outcomes are descriptive.

Closing-market diagnostics separate original-to-closing line movement from binary market probabilities. Closing-line and reference line must match exactly to quote a same-line non-push closing probability; never directly compare a binary market score with unconditional three-way model log loss.

## Limitations

Historical archived pre-Bayesian forecasts do not count as Bayesian retrospective performance. A/B are correlated because they share game histories; the simulation is not a third independent evidence source. Date clustering is conservative but does not resolve selection bias, multiple comparisons, external context-source failures or venue/game-level dependence. No calculation implies calibrated real-world predictive accuracy without prospective evidence.

## Operation

The successful morning settlement workflow calls:

    python scripts/phase4_validation.py --original data/prop_snapshots.jsonl --a-dir data/bayesian_shadow --b-dir data/bayesian_b_shadow --mc-dir data/posterior_mc --out reports/phase4_validation.json

The report and summary receipt are GitHub Actions artifacts. It recomputes from durable original and immutable shadow snapshots; it does not write outcomes, forecasts or calibration weights. Offline tests:

    python -m unittest discover -s tests -p test_phase4_validation.py -q
    python -m unittest discover -s tests -q
