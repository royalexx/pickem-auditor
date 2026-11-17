"""Read-only C-family distribution calibration and reliability summaries.

Scored records must be produced AFTER official settlement by scoring.score_official.
No calibrator is fitted, no 2023-24 archive is loaded, and sample size is not
equated with an independent game count.
"""
from __future__ import annotations
from collections import defaultdict
import math

from .scores import ScoreError


def calibration_summary(scored, *, pit_bins=10, min_report_games=1):
    if type(pit_bins) is not int or not 2 <= pit_bins <= 100:
        raise ScoreError("INVALID_PIT_BINS")
    if type(min_report_games) is not int or min_report_games < 1:
        raise ScoreError("INVALID_MIN_REPORT_GAMES")
    rows=list(scored)
    if not rows:
        raise ScoreError("EMPTY_CALIBRATION_COHORT")
    eligible=[]
    rejected=defaultdict(int)
    for x in rows:
        if not isinstance(x,dict):
            raise ScoreError("INVALID_CALIBRATION_RECORD")
        if x.get("scored") is not True:
            rejected[x.get("reason","UNSCORED")]+=1
            continue
        fields=("game_id","crps","nlpd","mean","zero_predicted",
                "zero_observed","tail_predicted","tail_observed","covered",
                "nominal_coverage","pit","signed_bias","absolute_error",
                "squared_error")
        if any(k not in x for k in fields):
            raise ScoreError("CALIBRATION_METRIC_MISSING")
        vals=("crps","mean","zero_predicted","zero_observed","tail_predicted",
              "tail_observed","nominal_coverage","pit","signed_bias",
              "absolute_error","squared_error")
        if any(type(x[k]) not in (int,float,bool) or not math.isfinite(x[k])
               for k in vals):
            raise ScoreError("NONFINITE_CALIBRATION")
        if not 0 <= x["pit"] <= 1:
            raise ScoreError("PIT_OUTSIDE_UNIT_INTERVAL")
        for k in ("zero_predicted","zero_observed","tail_predicted",
                  "tail_observed","nominal_coverage"):
            if not 0 <= x[k] <= 1:
                raise ScoreError("INVALID_EVENT_PROBABILITY")
        eligible.append(x)
    games={x["game_id"] for x in eligible}
    if len(games)<min_report_games:
        raise ScoreError("INSUFFICIENT_DISTINCT_GAMES")
    n=len(eligible)
    buckets=[0]*pit_bins
    for x in eligible:
        buckets[min(int(x["pit"]*pit_bins),pit_bins-1)]+=1
    fractions=[b/n for b in buckets]
    by_coverage=defaultdict(list)
    for x in eligible:
        by_coverage[x["nominal_coverage"]].append(int(x["covered"]))
    mean=lambda key: math.fsum(x[key] for x in eligible)/n
    return {
        "n_forecast_rows":n,"n_distinct_games":len(games),
        "n_input_rows":len(rows),"not_scored_by_reason":dict(sorted(rejected.items())),
        "pit_histogram":buckets,"pit_expected_per_bin":1/pit_bins,
        "pit_l1_uniformity_descriptive":sum(abs(f-1/pit_bins) for f in fractions),
        "quantile_coverage":{str(k):{"observed":sum(v)/len(v),"n_rows":len(v)}
                             for k,v in sorted(by_coverage.items())},
        "zero_probability_mean":mean("zero_predicted"),
        "zero_frequency":mean("zero_observed"),
        "zero_signed_residual":mean("zero_predicted")-mean("zero_observed"),
        "tail_probability_mean":mean("tail_predicted"),
        "tail_frequency":mean("tail_observed"),
        "tail_signed_residual":mean("tail_predicted")-mean("tail_observed"),
        "mae":mean("absolute_error"),
        "rmse":math.sqrt(mean("squared_error")),
        "signed_bias":mean("signed_bias"),
        "mean_crps":mean("crps"),
        "mean_nlpd":math.fsum(x["nlpd"] for x in eligible)/n
                      if all(math.isfinite(x["nlpd"]) for x in eligible)
                      else math.inf,
        "pit_uniformity_is_descriptive_not_significance":True,
        "clustered_uncertainty_must_resample_games_dates":True,
    }
