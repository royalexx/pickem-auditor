"""C10: outcome-blind fixed-horizon NHL SOG inferential release gate.

This is NOT a new p-value method and cannot certify or release a challenger.
The two existing C10 HAC simulations are preserved separately as diagnostics
(lag-3 on 36 scenarios and lag-5 on 96 scenarios); neither is an approved
replacement for the original paired t(39) candidate.

No realized proper score, paired outcome, signed difference or interim
performance field is used anywhere in the release/feasibility functions.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
from math import ceil, isfinite, sqrt
from statistics import NormalDist
from pathlib import Path
import argparse
import json
import re

SCHEMA = "v25_c10_fixed_horizon_outcome_blind_release_gate_v1"
EXPERIMENT = "EXP-V25-NHL-SOG-EXPOSURE-EB-001"
ACCEPTED_SOURCE = "v25_nhl_sog_daily_prospective_paired_validation_v1"
GOAL_DATES = 40
END_DATE = date(2027, 1, 31)
ONE_SIDED_ALPHA = 0.025
MIN_USEFUL_BRIER = 0.002
POWER_TARGET = 0.80
PLANNING_SDS = (0.01, 0.02, 0.04, 0.08)
PLANNING_RHOS = (0.0, 0.3, 0.6)
PENDING_CANDIDATES = (
    "lag3_bartlett_worstcase_36scenario_grid_alpha_0_025",
    "lag5_bartlett_worstcase_96scenario_grid_tail_0_01",
)
SHA_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class C10GateError(ValueError):
    pass


def _check(value, reason):
    if not value:
        raise C10GateError(reason)


def _as_int(x, key):
    _check(type(x) is int and 0 <= x, "NONNEGATIVE_INTEGER_REQUIRED:" + key)
    return x


def _fixed_time(x, key):
    _check(isinstance(x, str), "SOURCE_TIME_MISSING:" + key)
    try:
        dt = datetime.fromisoformat(x.replace("Z", "+00:00"))
    except ValueError as exc:
        raise C10GateError("SOURCE_TIME_UNPARSEABLE:" + key) from exc
    _check(dt.tzinfo is not None, "SOURCE_TIME_NAIVE:" + key)
    return dt.astimezone(timezone.utc)


def iid_gaussian_planning(*, n=GOAL_DATES, sd, rho=0.0,
                          effect=MIN_USEFUL_BRIER, alpha=ONE_SIDED_ALPHA,
                          target_power=POWER_TARGET):
    """Optimistic *planning approximation*, NOT test or estimated real power.

    n_eff=n*(1-rho)/(1+rho) is an asymptotic AR(1) approximation: it ignores
    finite-n effects, unknown drift, clustered eligibility and variance
    estimation. We do NOT substitute it for the held-out stress grid.
    """
    _check(type(n) is int and n > 1, "BAD_INDEPENDENT_DATE_COUNT")
    _check(all(type(v) in (int, float) and isfinite(float(v))
               for v in (sd, rho, effect, alpha, target_power)),
           "NONFINITE_PLANNING_INPUT")
    _check(sd > 0 and effect > 0 and 0 <= rho < 1 and
           0 < alpha < 0.5 and 0.5 < target_power < 1, "INVALID_PLANNING_ASSUMPTION")
    z = NormalDist()
    n_eff = n * (1.0 - rho) / (1.0 + rho)
    critical = z.inv_cdf(1.0 - alpha)
    z_target = z.inv_cdf(target_power)
    signal = effect * sqrt(n_eff) / sd
    power = z.cdf(signal - critical)
    required = ceil(((critical + z_target) * sd / effect) ** 2
                    * (1 + rho) / (1 - rho))
    return {"n_dates": n, "nominal_alpha": alpha, "assumed_sd": sd,
            "assumed_ar1_rho": rho, "effect_magnitude": effect,
            "target_power": target_power, "approximate_effective_dates": n_eff,
            "optimistic_known_variance_z_power": power,
            "optimistic_dates_for_target_power": required,
            "type": "GAUSSIAN_KNOWN_VARIANCE_PLANNING_ONLY_NOT_INFERENCE"}


def power_feasibility_table():
    return [iid_gaussian_planning(sd=sd, rho=rho)
            for sd in PLANNING_SDS for rho in PLANNING_RHOS]


def blind_metadata_health(source: dict, source_sha256: str):
    """Consumes ONLY status/counters/clock fields, NEVER any scores.

    Complete real-source and settlement identity certification still belongs
    to the prospective collector. A single mutable daily summary cannot prove
    chronological integrity; the release gate therefore never grants approval.
    """
    _check(isinstance(source, dict), "SOURCE_REPORT_NOT_OBJECT")
    _check(isinstance(source_sha256, str) and
           SHA_PATTERN.fullmatch(source_sha256) is not None,
           "SOURCE_MANIFEST_SHA_MISSING")
    _check(source.get("schema") == ACCEPTED_SOURCE and
           source.get("experiment_id") == EXPERIMENT,
           "SOURCE_EXPERIMENT_SCHEMA_MISMATCH")
    clock = _fixed_time(source.get("generated_at_utc"), "generated_at_utc")
    try:
        report_date = date.fromisoformat(source["local_date"])
    except (KeyError, ValueError, TypeError) as exc:
        raise C10GateError("SOURCE_LOCAL_DATE_INVALID") from exc
    _check(source.get("preregistered_research_minimum_dates") == GOAL_DATES,
           "FROZEN_HORIZON_MUTATED")
    for key,expected in {
        "production_modified": False,
        "t1_t2_promotion_allowed": False,
        "never_backdate_pregame_forecasts": True,
        "not_a_model_retraining_workflow": True,
        "source_capture_time_not_provider_publisher_signed": True,
        "evaluation_only_on_independent_official_FINAL": True,
    }.items():
        _check(source.get(key) is expected, "RELEASE_OR_LINEAGE_FLAG_INVALID:" + key)
    n = _as_int(source.get("eligible_date_count"), "eligible_date_count")
    settled = _as_int(source.get("settled_scored_count"), "settled_scored_count")
    original = _as_int(source.get("genuine_original_success_attempts_found"),
                       "genuine_original_success_attempts_found")
    qualifying = _as_int(source.get("frozen_source_qualified"), "frozen_source_qualified")
    _check(n <= GOAL_DATES and settled <= qualifying <= original and
           (settled > 0 or n == 0) and
           (n == 0 or settled >= n),
           "INCONSISTENT_MATCHED_DATE_OR_CONTRACT_DENOMINATOR")
    _check(source.get("scientific_validation_gate") == "NOT_ESTABLISHED",
           "UNAPPROVED_EARLY_INFERENCE_OR_RELEASE_CLAIM")
    _check(_as_int(source.get("synthetic_test_cases_scored"),
                   "synthetic_test_cases_scored") == 0,
           "SYNTHETIC_OUTCOMES_IN_PRIMARY")
    # Deliberately do not access date_equal_GP_minus_poisson,
    # paired_GP_minus_poisson, paired_daily_mean_metrics, model_metrics,
    # scored_outcomes, player-level probabilities or realized outcomes.
    return {
        "source_manifest_sha256": source_sha256,
        "reported_date": report_date.isoformat(),
        "source_report_clock": clock.isoformat(),
        "eligible_slate_dates_reported": n,
        "matched_offered_contracts_reported": settled,
        "genuine_original_success_attempts_reported": original,
        "frozen_source_qualified_reported": qualifying,
        "horizon_progress": f"{n}/{GOAL_DATES}",
        "metadata_source_independently_certified": False,
        "realized_proper_scores_accessed": False,
    }


def decision_for_existing_study(health: dict | None = None, *, as_of: date):
    """Final decision is always blocked pending genuinely independent signoff.

    With outcomes already observed on a running study, no post hoc method
    selection is allowed. Even at 40 eligible dates, neither HAC candidate
    acquires approval from this code. A future confirmatory study requires a
    new preregistration locked before its first candidate and result.
    """
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise C10GateError("AS_OF_MUST_BE_LOCAL_DATE")
    n = 0 if health is None else _as_int(
        health.get("eligible_slate_dates_reported"), "eligible_slate_dates_reported")
    _check(n <= GOAL_DATES, "EXCESS_PRIMARY_ELIGIBLE_DATES")
    incomplete = n < GOAL_DATES
    if incomplete and as_of > END_DATE:
        status = "ADMINISTRATIVELY_INCOMPLETE_40_DATES"
    elif incomplete:
        status = "RESEARCH_COLLECTING_CONFIRMATORY_BLOCKED"
    else:
        status = "FORTY_DATES_MET_NO_APPROVED_INFERENCE"
    return {
        "schema": SCHEMA,
        "experiment_id": EXPERIMENT,
        "status": status,
        "original_fixed_horizon": GOAL_DATES,
        "eligible_date_count": n,
        "missing_eligible_dates": GOAL_DATES - n,
        "fixed_end_date_et": END_DATE.isoformat(),
        "current_primary_estimand": "equal_weight_slate_dates_matched_threeway_Brier_delta",
        "null_hypothesis": "theta >= 0",
        "alternative_hypothesis": "theta < 0",
        "minimum_useful_estimate": -MIN_USEFUL_BRIER,
        "nominal_one_sided_alpha": ONE_SIDED_ALPHA,
        "primary_candidate_t39_independently_validated": False,
        "lag3_or_lag5_confirmatory_method_approved": False,
        "lag3_lag5_reconciled_as_competing_diagnostics_only": True,
        "40_dates_statistically_adequate_power_proven": False,
        "independent_statistical_signoff": False,
        "interim_hypothesis_test_performed": False,
        "p_value": None, "confidence_interval": None,
        "approved_for_promotional_probability_or_tier": False,
        "automatic_model_promotion": False,
        "future_experiment_requires_new_versioned_preoutcome_protocol": True,
        "coverage_metadata_only": health,
    }


def write_research_health_report(source_path: Path, output_path: Path, *,
                                 as_of: date):
    """Append-only C10 health receipt; no statistical test and no model data."""
    _check(source_path.is_file(), "SOURCE_MANIFEST_NOT_FOUND")
    _check(source_path.resolve() != output_path.resolve(), "SOURCE_OUTPUT_ALIASED")
    original = source_path.read_bytes()
    source_sha = sha256(original).hexdigest()
    src = json.loads(original)
    health = blind_metadata_health(src, source_sha)
    result = decision_for_existing_study(health, as_of=as_of)
    result["planning_only"] = power_feasibility_table()
    result["candidate_methods"] = list(PENDING_CANDIDATES)
    payload = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) +
               "\n").encode("utf8")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("xb") as out:
            out.write(payload)
    except FileExistsError:
        _check(output_path.read_bytes() == payload,
               "C10_APPEND_ONLY_HEALTH_REPORT_CONFLICT")
    return result, sha256(payload).hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-validation-manifest", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--as-of-et", required=True, type=date.fromisoformat)
    args = p.parse_args(argv)
    result, digest = write_research_health_report(
        args.source_validation_manifest, args.output, as_of=args.as_of_et)
    print(json.dumps({
        "status": result["status"],
        "eligible_dates": result["eligible_date_count"],
        "missing_dates": result["missing_eligible_dates"],
        "hypothesis_test": False, "p_value": None,
        "promotion_authorized": False,
        "receipt_sha256": digest, "output": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
