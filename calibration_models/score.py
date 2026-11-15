"""Read-only downstream scoring; never imported by the pregame generator.

WS6 supplies independently verified settlement labels keyed by contract_id.
One paired contract is one observation. Push/void/missing remain exclusions.
"""
from collections import Counter
from .shadow import CONFIG, calibration, reliability_bins, timestamp


def compare(report, settlements):
    indexed = {}
    for value in settlements:
        key = value["contract_id"]
        if key in indexed:
            raise ValueError("duplicate_settlement")
        indexed[key] = value
    names = list(report.get("registry", CONFIG))
    predictions = {name: {} for name in names}
    excluded = Counter()
    for row in report["forecasts"]:
        if row["status"] != "forecast":
            continue
        settlement = indexed.get(row["contract_id"])
        if settlement is None:
            excluded["missing_settlement"] += 1
            continue
        if settlement.get("event_id") != row["event_id"] or settlement.get("identity") != row["identity"]:
            raise ValueError("settlement_identity_conflict")
        outcome = settlement.get("outcome")
        if outcome not in ("over", "under"):
            excluded[str(outcome)] += 1
            continue
        candidate = row["candidate"]
        if row["contract_id"] in predictions[candidate]:
            raise ValueError("duplicate_forecast_for_candidate")
        predictions[candidate][row["contract_id"]] = {
            "date": timestamp(row["event_start_at"]).date().isoformat(),
            "game_id": row["event_id"], "y": int(outcome == "over"),
            "p": row["conditional_no_push"]["over"], "gap": row["model_market_gap"]}
    comparisons = {}
    for candidate in names:
        keys = sorted(set(predictions[candidate]) & set(predictions["C1"]) & set(predictions["C2"]))
        rows = []
        for key in keys:
            item = predictions[candidate][key]
            rows.append({**item, "predictions": {name: predictions[name][key]["p"]
                         for name in {candidate, "C1", "C2"}}})
        names = {candidate, "C1", "C2"}
        metrics = {name: calibration.metric(rows, name) for name in sorted(names)}
        for name in names:
            metrics[name]["reliability_over"] = reliability_bins([(r["predictions"][name], r["y"]) for r in rows])
            metrics[name]["reliability_under"] = reliability_bins([(1-r["predictions"][name], 1-r["y"]) for r in rows])
            metrics[name]["direction_ties"] = sum(abs(r["predictions"][name]-.5) < 1e-12 for r in rows)
            directed = [r for r in rows if abs(r["predictions"][name]-.5) >= 1e-12]
            metrics[name]["directional_accuracy"] = (sum((r["predictions"][name] > .5) == bool(r["y"])
                for r in directed)/len(directed)) if directed else None
            metrics[name]["signed_over_residual"] = (sum(r["predictions"][name]-r["y"] for r in rows)/len(rows)) if rows else None
        intervals = {}
        for unit in ("date", "game_id"):
            clustered = [{**r, "date": r[unit]} for r in rows]
            intervals[unit] = {baseline: {m: calibration.interval(clustered, candidate, baseline, metric_name=m)
                              for m in ("brier", "log_loss")} for baseline in ("C1", "C2")}
        comparisons[candidate] = {"matched_contracts": len(rows), "dates": len({r["date"] for r in rows}),
                                 "games": len({r["game_id"] for r in rows}),
                                 "metrics": metrics, "descriptive_cluster_intervals": intervals}
    gap_slices = {}
    original = predictions["C1"]
    for label, low, high in (("gap_0_to_015", 0, .15), ("gap_015_to_030", .15, .30), ("gap_030_plus", .30, 2)):
        rows = [{**r, "predictions": {"C1": r["p"]}} for r in original.values()
                if r["gap"] is not None and low <= r["gap"] < high]
        gap_slices[label] = {"metrics": calibration.metric(rows, "C1"),
                            "games": len({r["game_id"] for r in rows}), "dates": len({r["date"] for r in rows})}
    standalone = {}
    paired = {}
    for name in predictions:
        own = [{**r, "predictions": {name: r["p"]}} for r in predictions[name].values()]
        standalone[name] = calibration.metric(own, name)
        standalone[name]["reliability_over"] = reliability_bins([(r["p"], r["y"]) for r in own])
        standalone[name]["reliability_under"] = reliability_bins([(1-r["p"], 1-r["y"]) for r in own])
        paired[name] = {}
        for baseline in ("C1", "C2"):
            keys = sorted(set(predictions[name]) & set(predictions[baseline]))
            rows = [{**predictions[name][key], "predictions": {
                name: predictions[name][key]["p"], baseline: predictions[baseline][key]["p"]}} for key in keys]
            paired[name][baseline] = {"matched_contracts": len(keys), "metrics": {
                model: calibration.metric(rows, model) for model in {name, baseline}}}
    return {"standalone_conditional_nonpush": standalone, "pairwise_comparisons": paired,
            "comparisons": comparisons, "C1_disagreement_reliability": gap_slices,
            "excluded_candidate_records": dict(excluded), "settlement_rows": len(settlements),
            "unmatched_settlement_contracts": sorted(set(indexed)-{r["contract_id"] for r in report["forecasts"]}),
            "interpretation": "descriptive_binary_nonpush_one_contract_once_no_promotion"}
