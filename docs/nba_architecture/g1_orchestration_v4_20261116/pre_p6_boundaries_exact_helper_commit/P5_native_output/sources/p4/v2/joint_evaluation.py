"""P1-05: score genuinely archived joint scenario ensembles without refitting.

Energy/VS/CRPS require a full joint predictive ensemble, not marginal
probabilities independently recombined after observing results. Each
ensemble is SHA-bound and time-checked; source possession/publication is
still subject to Phase 0R independent certification.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from .contracts import ContractError, canonical_hash, require_sha, utc, finite
from .evaluation import energy_score, variogram_score, crps_ensemble, _mean, _cluster_interval


def evaluate_joint(records: list[dict], *, baseline_model: str = "frozen_v1",
                   bootstrap_seed: int = 20261109,
                   bootstrap_replicates: int = 1000) -> dict:
    if not isinstance(records, list):
        raise ContractError("joint_records_must_be_list")
    scored = {}
    events = {}
    for raw in records:
        if not isinstance(raw, dict):
            raise ContractError("invalid_joint_record")
        for key in ("event_id","model_id","run_id","forecast_at",
                    "input_freeze_at","model_training_cutoff_at",
                    "event_start_at","settled_at"):
            if not isinstance(raw.get(key),str) or not raw[key]:
                raise ContractError("joint_required_field_missing:"+key)
        original_sha=raw.get("scenarios_sha256")
        require_sha(original_sha,"scenarios_sha256")
        require_sha(raw.get("source_receipt_sha256"),"source_receipt_sha256")
        if not (utc(raw["model_training_cutoff_at"],"training") <=
                utc(raw["input_freeze_at"],"freeze") <=
                utc(raw["forecast_at"],"forecast") <
                utc(raw["event_start_at"],"kickoff") <
                utc(raw["settled_at"],"settlement")):
            raise ContractError("joint_temporal_order_failed")
        raw_scenarios=raw.get("scenarios")
        components=raw.get("components")
        observed=raw.get("observed")
        if (not isinstance(raw_scenarios,list) or not 1 <= len(raw_scenarios) <= 5000
                or not isinstance(components,list) or not 2 <= len(components) <= 60
                or not isinstance(observed,list) or len(observed)!=len(components)):
            raise ContractError("joint_scenario_dimensions_invalid")
        if len({(c.get("player_id"),c.get("stat_key"),c.get("period"))
                for c in components if isinstance(c,dict)}) != len(components):
            raise ContractError("duplicate_joint_component_identity")
        if any(not isinstance(c,dict) or not all(c.get(k) for k in
                ("player_id","stat_key","period")) for c in components):
            raise ContractError("joint_component_missing_identity")
        if any(not isinstance(row,list) or len(row)!=len(components)
               for row in raw_scenarios):
            raise ContractError("joint_member_dimension_mismatch")
        sample=tuple(tuple(finite(x,"joint_sample") for x in row)
                     for row in raw_scenarios)
        y=tuple(finite(x,"joint_actual") for x in observed)
        if canonical_hash({"scenarios":raw_scenarios,
                           "components":components}) != original_sha:
            raise ContractError("original_joint_scenario_bytes_hash_mismatch")
        key=(raw["event_id"],raw["model_id"])
        if key in scored:
            raise ContractError("duplicate_joint_model_event")
        component_ids=tuple((c["player_id"],c["stat_key"],c["period"])
                            for c in components)
        event=(raw["event_id"],component_ids)
        if raw["event_id"] in events and events[raw["event_id"]] != component_ids:
            raise ContractError("incompatible_joint_component_universe")
        events[raw["event_id"]] = component_ids
        row={
            "event_id":raw["event_id"],"model_id":raw["model_id"],
            "run_id":raw["run_id"],"scenarios_sha256":original_sha,
            "source_receipt_sha256":raw["source_receipt_sha256"],
            "n_scenarios":len(sample),"n_components":len(component_ids),
            "energy_score":energy_score(list(sample),y),
            "variogram_score_p05":variogram_score(list(sample),y),
            "mean_marginal_crps":_mean(crps_ensemble([s[j] for s in sample],y[j])
                                       for j in range(len(component_ids))),
            "date_utc":utc(raw["event_start_at"],"event_start").date().isoformat(),
            "counterfactual_recombination_allowed":False,
        }
        scored[key]=row
    models=sorted({m for _e,m in scored})
    summary={}
    for model in models:
        members=[v for (_e,m),v in scored.items() if m==model]
        summary[model]={
            "events":len(members),
            "energy_score":_mean(r["energy_score"] for r in members),
            "variogram_score_p05":_mean(r["variogram_score_p05"] for r in members),
            "mean_marginal_crps":_mean(r["mean_marginal_crps"] for r in members),
        }
    paired={}
    for model in models:
        if model==baseline_model:continue
        common=sorted({e for e,m in scored if m==model}
                      & {e for e,m in scored if m==baseline_model})
        diffs=[(e,scored[(e,model)]["energy_score"]-
                 scored[(e,baseline_model)]["energy_score"]) for e in common]
        ddiffs=[(scored[(e,model)]["date_utc"],d) for e,d in diffs]
        paired[model]={
            "baseline":baseline_model,"matched_events":len(common),
            "energy_difference":_mean(d for _e,d in diffs),
            "energy_game_cluster_interval":_cluster_interval(
                diffs,bootstrap_seed,bootstrap_replicates),
            "energy_date_cluster_interval":_cluster_interval(
                ddiffs,bootstrap_seed,bootstrap_replicates),
        }
    return {
        "schema":"v25-joint-scorecard-shadow-1",
        "event_universe":len(events),"records":len(records),
        "models":summary,"paired":paired,
        "event_receipts":[scored[key] for key in sorted(scored)],
        "production_promotion_authorized":False,
        "source_publication_truth_independently_verified":False,
    }
