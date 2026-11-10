"""Phase 1.5 NHL/NBA: source-locked diagnostic of frozen Phase 1 contracts.

Never confuses model-versus-market disagreement with demonstrated forecast
error, uses reconstructed counterfactual controls as genuine older picks, or
claims an empirical result before a settlement is available. No training.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone

from .contracts import ContractError

SCHEMA = "v25-phase15-nhl-nba-error-investment-v1"
MODELS = ("naive_recent_exposure_rate", "pooled_peer_shrunk_rate",
          "real_no_vig_market")
ALL_MODELS = MODELS + ("frozen_v1_60_40", "Engine_A_original",
                       "Engine_B_original", "Bayesian_A", "Bayesian_B", "NUTS")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def probability(x, label):
    if isinstance(x, bool):
        raise ContractError("boolean_probability:" + label)
    try:
        n = float(x)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ContractError("missing_probability:" + label) from exc
    if not math.isfinite(n) or not 0 <= n <= 1:
        raise ContractError("invalid_probability:" + label)
    return n


def finite(x, label):
    if isinstance(x, bool):
        raise ContractError("boolean_numeric:" + label)
    try:
        n = float(x)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ContractError("invalid_numeric:" + label) from exc
    if not math.isfinite(n):
        raise ContractError("nonfinite_numeric:" + label)
    return n


def instant(s, label):
    if not isinstance(s, str) or "T" not in s:
        raise ContractError("missing_timestamp:" + label)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError("invalid_timestamp:" + label) from exc
    if dt.tzinfo is None:
        raise ContractError("naive_timestamp:" + label)
    return dt.astimezone(timezone.utc)


def avg(xs):
    return sum(xs)/len(xs) if xs else None


def _scores(rows, model):
    data = []
    selected = []
    for c in rows:
        o = c["outcome"]
        if o["status"] not in ("over", "under"):
            continue
        ob = int(o["status"] == "over")
        p = probability(c["models"][model].get("p_over_nonpush"), model)
        selected_prob = max(p, 1-p)
        data.append({"p": p, "y": ob,
                     "brier": (p-ob)**2,
                     "logloss": -(ob*math.log(max(p,1e-12)) +
                                  (1-ob)*math.log(max(1-p,1e-12))),
                     "event": c["event_id"],
                     "date": c["event_start"][:10],
                     "stat": c["stat"], "sport": c["sport"]})
        if p != .5:
            selected.append({"selected_p": selected_prob,
                             "hit": int((p>.5)==bool(ob)),
                             "under": p<.5})
    return {
        "n": len(data), "distinct_games":len({r["event"] for r in data}),
        "distinct_dates":len({r["date"] for r in data}),
        "brier": avg([r["brier"] for r in data]),
        "log_loss": avg([r["logloss"] for r in data]),
        "signed_over_error":avg([r["p"]-r["y"] for r in data]),
        "observed_over_frequency":avg([r["y"] for r in data]),
        "directional_hit_rate":avg([r["hit"] for r in selected]),
        "80plus_n":sum(r["selected_p"]>=.8 for r in selected),
        "80plus_hits":sum(r["hit"] for r in selected if r["selected_p"]>=.8),
        "selected_under_n":sum(r["under"] for r in selected),
        "selected_over_n":sum(not r["under"] for r in selected),
        "unscored_must_not_equal_zero":not bool(data),
    }


def _rates(rows, label):
    n=len(rows)
    if not n:
        return {"n":0}
    ps=[probability(c["models"][label].get("p_over_nonpush"),label) for c in rows]
    p_ge=[max(v,1-v) for v in ps]
    return {
        "n":n, "over_n":sum(p>.5 for p in ps),
        "under_n":sum(p<.5 for p in ps),
        "tie_n":sum(p==.5 for p in ps),
        "under_share_of_all_contracts":sum(p<.5 for p in ps)/n,
        "over_share_of_all_contracts":sum(p>.5 for p in ps)/n,
        "mean_p_over":avg(ps),
        "mean_selected_confidence":avg(p_ge),
        "selected_confidence_ge80_n":sum(p>=.80 for p in p_ge),
        "selected_confidence_ge90_n":sum(p>=.90 for p in p_ge),
        "high80_over_n":sum(p>=.8 for p in ps),
        "high80_under_n":sum(p<=.2 for p in ps),
        "mean_probability_claim_not_observed_accuracy":True,
        "min_p_over":min(ps), "max_p_over":max(ps),
        "empirical_scores":_scores(rows,label),
    }


def _comparison(rows, other, ref="real_no_vig_market"):
    vals=[]
    for c in rows:
        a=probability(c["models"][other].get("p_over_nonpush"),other)
        b=probability(c["models"][ref].get("p_over_nonpush"),ref)
        vals.append((a,b,c))
    observed=[(a,b,int(c["outcome"]["status"]=="over"))
              for a,b,c in vals if c["outcome"]["status"] in ("over","under")]
    def ll(p, y):
        p=max(1e-12,min(1-1e-12,p))
        return -(y*math.log(p)+(1-y)*math.log1p(-p))
    return {
        "n":len(vals),
        "mean_signed_over_probability_difference":avg([a-b for a,b,_ in vals]),
        "mean_absolute_over_probability_difference":avg([abs(a-b) for a,b,_ in vals]),
        "direction_disagreement_n":sum((a-.5)*(b-.5)<0 for a,b,_ in vals),
        "market_at_50_n":sum(b==.5 for _,b,_ in vals),
        "mean_absolute_probability_difference_is_not_accuracy":True,
        "matched_scored_contracts":len(observed),
        "model_vs_market_brier_difference":avg([
            (a-y)**2-(b-y)**2 for a,b,y in observed]),
        "model_vs_market_logloss_difference":avg([
            ll(a,y)-ll(b,y) for a,b,y in observed]),
        "negative_difference_favors_model":True,
        "game_and_date_clustered_inference_status":
            "descriptive_only_requires_multiple_independent_games_and_dates"
            if observed else "BLOCKED_NO_SETTLEMENT",
    }


def _coverage(rows):
    n=len(rows)
    return {
        "contracts":n,
        "game_clusters":len({r["event_id"] for r in rows}),
        "calendar_dates":len({r["event_start"][:10] for r in rows}),
        "player_games":len({(r["event_id"],r["player_id"]) for r in rows}),
        "distinct_players":len({r["player_id"] for r in rows}),
        "exposure_projected_from_historical_median_n":sum(
            r["opportunity"].get("projected_workload_origin") ==
            "median_of_last5_originally_archived_pregame_games" for r in rows),
        "position_verified_n":sum(r["opportunity"].get("peer_position_known") is True
                                  for r in rows),
        "prior_season_history_used_n":sum(
            r["opportunity"].get("prior_season_history_used") is True for r in rows),
        "median_predicted_workload":statistics.median(
            finite(r["opportunity"]["projected_workload"],"workload")
            for r in rows) if rows else None,
    }


def diagnose(source: dict, *, seed=20261110, power=None):
    if not isinstance(source, dict) or source.get("schema") != "v25-phase1-nhl-nba-certified-replay-v1":
        raise ContractError("invalid_phase1_source")
    actual_hash=source.get("report_sha256")
    if not isinstance(actual_hash,str) or actual_hash != digest(
            {k:v for k,v in source.items() if k!="report_sha256"}):
        raise ContractError("tampered_phase1_receipt_digest")
    if source.get("model_promotion_authorized") is not False or source.get(
            "tier1_tier2_publication_allowed") is not False:
        raise ContractError("phase1_promotion_flag_must_be_false")
    if type(seed) is not int or seed<0:
        raise ContractError("invalid_seed")
    expected=source.get("prepared_attempt_statuses") or {}
    if (expected.get("forecast") != source.get("original_forecast_rows")
            or expected.get("forecast",0)+expected.get("unavailable",0)
            != source.get("prepared_attempt_count")):
        raise ContractError("attempted_universe_denominator_not_reconciled")
    contracts=source.get("contracts")
    if not isinstance(contracts,list) or not contracts:
        raise ContractError("missing_original_phase1_contracts")
    if len(contracts)!=source.get("retained_paired_contracts") or len(contracts)*2!=source.get("original_forecast_rows"):
        raise ContractError("original_pair_count_mismatch")
    keys=set()
    by_sport=defaultdict(list)
    by_stat=defaultdict(list)
    state=Counter()
    model_states=defaultdict(Counter)
    for c in contracts:
        if not isinstance(c,dict) or c.get("sport") not in ("NBA","NHL"):
            raise ContractError("unexpected_contract_sport")
        key=(c["sport"],str(c["event_id"]),str(c["player_id"]),
             c["stat"],finite(c["line"],"line"),c.get("period"))
        if key in keys:
            raise ContractError("duplicate_phase15_exact_contract")
        keys.add(key)
        if c.get("period")!="full":
            raise ContractError("unsupported_phase15_period")
        if instant(c["input_freeze_at"],"freeze")>=instant(c["event_start"],"event_start"):
            raise ContractError("nonpregame_phase15_freeze")
        for fld in ("original_over_snapshot_sha256","original_under_snapshot_sha256"):
            val=c.get(fld)
            if not isinstance(val,str) or len(val)!=64 or any(z not in "0123456789abcdef" for z in val):
                raise ContractError("original_side_sha_missing")
        if not isinstance(c.get("models"),dict) or set(ALL_MODELS)-set(c["models"]):
            raise ContractError("phase15_model_columns_missing")
        for m in ALL_MODELS:
            model_states[m][c["models"][m].get("status")]+=1
        for m in MODELS:
            v=c["models"][m]
            if v["status"] not in ("counterfactual_shadow","available"):
                raise ContractError("phase15_core_model_unavailable:"+m)
            probability(v.get("p_over_nonpush"),m)
            if m!="real_no_vig_market":
                if v.get("originally_published_forecast") is not False:
                    raise ContractError("counterfactual_mislabeled_original")
                ps=[probability(v.get(q),q) for q in ("q_over","q_under","q_push")]
                if abs(sum(ps)-1)>1e-9:
                    raise ContractError("distribution_probabilities_not_normalized")
        o=c["outcome"]
        os=o.get("status")
        if os not in ("pending_official_settlement","over","under","push","void","unavailable"):
            raise ContractError("phase15_invalid_outcome_state")
        if os in ("over","under","push"):
            observed=finite(o.get("actual"),"settlement_actual")
            line=finite(c["line"],"line")
            actual_state="push" if observed==line else "over" if observed>line else "under"
            if actual_state!=os or instant(o["settled_at"],"settled")<instant(c["event_start"],"start"):
                raise ContractError("settlement_semantics_or_time_mismatch")
            if not o.get("source_url"):
                raise ContractError("settlement_source_missing")
        state[os]+=1
        by_sport[c["sport"]].append(c)
        by_stat[c["sport"]+"|"+c["stat"]].append(c)
    if dict(Counter(c["sport"] for c in contracts))!=source.get("by_sport"):
        raise ContractError("phase15_by_sport_count_mismatch")
    if dict(Counter(c["sport"]+"|"+c["stat"] for c in contracts))!=source.get("by_stat"):
        raise ContractError("phase15_by_stat_count_mismatch")
    if dict(state)!=source.get("settlement_states"):
        raise ContractError("phase15_settlement_state_disagreement")
    by_group={}
    for name, rows in [("ALL",contracts)]+sorted(by_sport.items())+sorted(by_stat.items()):
        by_group[name]={
            "coverage":_coverage(rows),
            "forecasts":{m:_rates(rows,m) for m in MODELS},
            "comparisons":{m:_comparison(rows,m) for m in MODELS[:2]},
        }
    settled=state.get("over",0)+state.get("under",0)+state.get("push",0)
    scores=state.get("over",0)+state.get("under",0)
    for m in MODELS:
        expected_score=source.get("models",{}).get(m,{})
        if expected_score.get("scored_contracts")!=scores:
            raise ContractError("phase1_vs_phase15_scoring_denominator_mismatch")
        ours=_scores(contracts,m)
        for metric in ("brier","log_loss"):
            left=expected_score.get(metric)
            right=ours[metric]
            if left is None and right is None:continue
            if (left is None or right is None or
                    not math.isclose(finite(left,metric),right,abs_tol=1e-10,rel_tol=1e-10)):
                raise ContractError("phase1_vs_phase15_score_disagreement:"+m+":"+metric)
    independent_dates=len({c["event_start"][:10] for c in contracts})
    prospective_components=sum(bool(c.get("opportunity",{}).get("pregame_factor_vector_receipt"))
                               for c in contracts)
    gates={
        "A_data_integrity":{"status":"PASS_PHASE1_CERTIFIED_ORIGINAL_ARCHIVE",
            "certified_side_rows":source["original_forecast_rows"],
            "attempted_universe":source["prepared_attempt_count"],
            "rejected_rows":expected.get("unavailable",0)},
        "B_directional_accuracy":{"status":("MEASURED_WITH_OUTCOMES" if scores else
                               "BLOCKED_NO_GENUINE_POSTGAME_SETTLEMENT"),
            "signed_over_residual_available":bool(scores),
            "pre_game_selection_composition_measurable":True,
            "do_not_transplant_NFL_2024_92pct_under_rate":True},
        "C_opportunity_error":{"status":"BLOCKED_NO_ORIGINAL_FOUR_FACTOR_AND_POSTGAME_INPUTS",
            "four_factor_pregame_vectors_present":prospective_components,
            "realized_team_volume_role_share_conversion_measured":False,
            "observed_last5_median_exposure_not_an_error_attribution":True},
        "D_market_edge":{"status":"BLOCKED_NO_SETTLED_MATCHED_PAYOUT" if not scores
                          else "PREGAME_MARKET_REFERENCE_AVAILABLE_PAYOFF_NOT_VERIFIED",
            "actual_pregame_two_sided_market_quotes":len(contracts),
            "pickem_payout_terms_verified":False,
            "bookmaker_no_vig_reference_is_not_pickem_price":True},
        "E_complexity":{"status":"DEFER_EXPENSIVE_MODELS_AWAIT_PROSPECTIVE_SKILL",
            "do_not_train_heavy_NUTS_or_joint_game_model":True,
            "prioritize_next_captured_opportunity_and_real_settlement":True},
    }
    outcome={
        "schema":SCHEMA,
        "source_phase1_sha256":actual_hash,
        "source_original_bundle_sha256":source["input_immutable_bundle_sha256"],
        "source_code_commit":source["code_commit"],
        "analysis_seed":seed,
        "scope":["NBA","NHL"],
        "contracts":len(contracts),
        "attempted_forecast_sides":source["prepared_attempt_count"],
        "accepted_forecast_sides":source["original_forecast_rows"],
        "rejected_forecast_sides":expected.get("unavailable",0),
        "rejection_reasons":source.get("prepared_rejection_reasons"),
        "unique_events":len({(c["sport"],c["event_id"]) for c in contracts}),
        "distinct_calendar_dates":independent_dates,
        "outcome_states":dict(state),
        "actual_scored_contracts":scores,
        "model_availability":{m:dict(x) for m,x in model_states.items()},
        "cohorts":by_group,
        "gates":gates,
        "retrospectively_generated_simple_baselines_are_not_original_forecasts":True,
        "original_60_40_not_substituted_from_preliminary_components":True,
        "strong_claims_permitted":[],
        "power_assumptions":"independent_fixed_n_binomial_only_not_a_tier_release",
        "tier_power":power,
        "investment_decision":"DEFER_PHASE2_AND_HEAVY_COMPUTE_CONTINUE_CAPTURE_AND_SIMPLE_SHADOW",
        "priority_actions":[
            "Preserve original daily frozen NBA/NHL accepted and rejected quote universe",
            "Add immutable pregame opportunity-team/participation/share/efficiency factors only where genuinely available; never infer from box scores",
            "Match official settled actuals with raw source hashes and exact event/player/stat/line/period",
            "Accumulate multiple independent dates before game/date clustered score comparison",
            "Evaluate matched proper scores and signed Over errors before adapting any distribution or Tier rule",
        ],
        "no_model_promotion":True,
        "tier1_tier2_publication_allowed":False,
    }
    outcome["diagnostic_receipt_sha256"]=digest(outcome)
    return outcome
