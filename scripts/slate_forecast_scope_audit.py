#!/usr/bin/env python3
"""Audit *all* sourced prop contracts before using any top-10 shortlist.

The production model, frozen probabilities and candidate ranks are read-only.
Every source contract in the selected frozen slate must have a corresponding
row for EVERY model (a forecast or a sourced unavailable reason).

The current provider pipeline uses the primary comparable price line for each
player/stat and excludes unsupported, unpriced or unmodelable source rows.
This receipt exposes those exclusions; it never invents a missing forecast.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from odds_providers import quotes_for_row, primary_price
from fetch_slate import _pipeline_ready
from nuts_slate_shadow import identity
from live_pool_exchange import pick_latest

VERSION = "slate-forecast-universe-audit-v1"
MODEL_NAMES = ("Engine_A", "Engine_B", "Bayesian_A", "Bayesian_B",
               "NUTS", "NUTS_provisional", "Market", "Consensus")


def read_jsonl(path):
    file = Path(path)
    if not file.is_file():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def contract(row):
    # Report records contain line as well as reference_line.
    return identity({**row, "reference_line": row.get("reference_line", row.get("line"))})


def _sources(rows, quotes, date):
    totals = Counter()
    by_stat = defaultdict(Counter)
    nonprimary_lines = 0
    for row in rows:
        if row.get("game_date") != date:
            continue
        stat = f"{row.get('sport')}|{row.get('stat')}"
        totals["source_player_stat_rows"] += 1
        by_stat[stat]["source"] += 1
        if not _pipeline_ready(row):
            reason = "historical_distribution_or_sample_unavailable"
        else:
            matches = quotes_for_row(quotes, row)
            picked = primary_price(matches)
            if not picked or picked.get("line") is None:
                reason = "no_usable_two_sided_primary_quote"
            else:
                reason = "ready_primary_quoted_line"
                # Alternative quoted levels are NOT silently counted as
                # independently forecast contracts in the current pipeline.
                other = {float(q["line"]) for q in matches
                         if type(q.get("line")) in (int, float)
                         and float(q["line"]) != float(picked["line"])}
                nonprimary_lines += len(other)
        totals[reason] += 1
        by_stat[stat][reason] += 1
    return (dict(sorted(totals.items())),
            {key: dict(sorted(group.items())) for key, group in sorted(by_stat.items())},
            nonprimary_lines)


def audit(*, day, source_rows, quotes, frozen_rows, comparison, top10=None,
          attempt_receipt=None):
    selected, run_id = pick_latest(frozen_rows, day)
    if not selected or not run_id:
        raise ValueError("no_frozen_slate_forecast_universe")
    if comparison.get("schema") != "slate-model-comparison-v1":
        raise ValueError("unexpected_comparison_schema")
    info = comparison.get("metadata") or {}
    if info.get("day") != day or info.get("run_id") != run_id:
        raise ValueError("different_frozen_slate_run_in_comparison")
    rows = comparison.get("picks")
    if not isinstance(rows, list):
        raise ValueError("comparison_rows_missing")
    expected = [contract(r) for r in selected]
    observed = [contract(r) for r in rows]
    if len(expected) != len(set(expected)):
        raise ValueError("duplicate_frozen_prop_contracts")
    if len(observed) != len(set(observed)):
        raise ValueError("duplicate_comparison_prop_contracts")
    if set(expected) != set(observed) or len(rows) != len(selected):
        missing = len(set(expected) - set(observed))
        extra = len(set(observed) - set(expected))
        raise ValueError(f"full_slate_comparison_incomplete:missing={missing}:extra={extra}")

    counts = {m: Counter() for m in MODEL_NAMES}
    reasons = {m: Counter() for m in MODEL_NAMES}
    by_sport = Counter()
    by_stat = Counter()
    model_per_stat = defaultdict(lambda: defaultdict(Counter))
    current = {contract(r): r for r in rows}
    for key in expected:
        record = current[key]
        sport = record.get("sport")
        stat = record.get("stat")
        by_sport[str(sport)] += 1
        by_stat[f"{sport}|{stat}"] += 1
        models = record.get("models")
        if not isinstance(models, dict):
            raise ValueError("model_comparison_detail_missing")
        for name in MODEL_NAMES:
            model = models.get(name)
            if not isinstance(model, dict) or model.get("status") not in ("forecast", "unavailable"):
                raise ValueError("model_status_missing:" + name)
            prob = model.get("probability")
            st = model["status"]
            if st == "forecast":
                if type(prob) not in (float, int) or not 0 <= prob <= 1:
                    raise ValueError("model_forecast_probability_invalid:" + name)
            elif prob is not None:
                raise ValueError("unavailable_model_cannot_supply_probability:" + name)
            counts[name][st] += 1
            model_per_stat[f"{sport}|{stat}"][name][st] += 1
            if st == "unavailable":
                why = str(model.get("reason") or "unavailable_reason_not_supplied")
                reasons[name][why] += 1
    top_counts = {}
    if top10 is not None:
        if top10.get("date") != day:
            raise ValueError("top10_date_mismatch")
        for sport, picks in (top10.get("top_10_by_sport") or {}).items():
            if len(picks) > 10:
                raise ValueError("shortlist_over_ten_for_sport")
            top_counts[sport] = len(picks)
            for pick in picks:
                if contract(pick) not in current:
                    raise ValueError("top10_contains_non_frozen_contract")
    source_summary, source_stats, other_lines = _sources(source_rows, quotes, day)
    attempted = None
    if attempt_receipt is not None:
        if (attempt_receipt.get("schema")!="all_prepared_props_attempts_v1"
                or attempt_receipt.get("date")!=day
                or attempt_receipt.get("run_id")!=run_id
                or attempt_receipt.get("all_prepared_contracts_attempted") is not True
                or attempt_receipt.get("no_top10_or_triage_pre_filter") is not True):
            raise ValueError("prepared_prop_attempt_receipt_not_matching_frozen_run")
        attempts=attempt_receipt.get("attempts")
        if (not isinstance(attempts,list)
                or len(attempts)!=attempt_receipt.get("prepared_contracts")
                or any(x.get("status") not in ("forecast","unavailable") for x in attempts)):
            raise ValueError("prepared_prop_attempt_receipt_incomplete")
        attempted={
            "prepared_contracts":len(attempts),
            "forecast":sum(x["status"]=="forecast" for x in attempts),
            "unavailable":sum(x["status"]=="unavailable" for x in attempts),
            "reasons":attempt_receipt.get("unavailable_reasons",{}),
            "all_prepared_contracts_attempted":True,
            "no_candidate_preselection":True}
        if (attempted["forecast"]!=attempt_receipt.get("forecast_contracts")
                or attempted["unavailable"]!=attempt_receipt.get("unavailable_contracts")):
            raise ValueError("prepared_prop_attempt_count_mismatch")
    return {
        "schema": VERSION, "game_date": day, "frozen_run_id": run_id,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "population_scope": "all_same_run_pregame_shadow_contracts_not_top10",
        "pricing_scope": "primary_compatible_two_sided_line_per_player_stat",
        "not_supported_yet": "independent_forecasts_for_alternate_lines",
        "frozen_contract_count": len(selected),
        "comparison_contract_count": len(rows),
        "full_contract_coverage": True,
        "no_probability_substitution": True,
        "pipeline_attempts": attempted,
        "by_sport": dict(sorted(by_sport.items())),
        "by_stat": dict(sorted(by_stat.items())),
        "model_coverage": {
            m: {"forecast": counts[m]["forecast"],
                "unavailable": counts[m]["unavailable"],
                "total": sum(counts[m].values()),
                "unavailable_reasons": dict(reasons[m].most_common(20))}
            for m in MODEL_NAMES},
        "model_by_stat": {
            stat: {m: dict(c) for m,c in sorted(models.items())}
            for stat,models in sorted(model_per_stat.items())},
        "source": {
            "counts": source_summary, "by_stat": source_stats,
            "two_sided_quote_rows": len(quotes),
            "alternate_quoted_line_levels_not_forecast": other_lines,
            "note": ("Source player/stat rows without valid historical distributions "
                     "or a compatible two-sided quote are reported but cannot "
                     "be assigned a fabricated model probability. Started games "
                     "and pipeline eligibility vetoes may also reduce the "
                     "frozen pregame universe.")},
        "top10": {
            "view_only": True, "not_used_to_select_model_inputs": True,
            "counts_by_sport": top_counts}
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--date", required=True)
    p.add_argument("--comparison", type=Path)
    p.add_argument("--top10", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--require-attempt-receipt", action="store_true")
    args = p.parse_args(argv)
    root=args.root
    path=args.comparison or (root/"reports/slate_model_comparisons.json")
    top=args.top10 or (path.parent/"slate_top10_evidence.json")
    out=args.out or (root/"reports/slate_forecast_scope_audit.json")
    attempts_path=root/"reports/all_prepared_props_attempts.json"
    if args.require_attempt_receipt and not attempts_path.is_file():
        raise ValueError("no_production_universe_attempt_receipt")
    result=audit(
        day=args.date,
        source_rows=read_jsonl(root/"data/slate_fetch.jsonl"),
        quotes=read_jsonl(root/"data/odds_quotes.jsonl"),
        frozen_rows=read_jsonl(root/"data/prop_snapshots.jsonl"),
        comparison=json.loads(path.read_text(encoding="utf-8")),
        top10=json.loads(top.read_text(encoding="utf-8")) if top.is_file() else None,
        attempt_receipt=(json.loads(attempts_path.read_text(encoding="utf-8"))
                         if attempts_path.is_file() else None))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n",
                   encoding="utf-8")
    print("SLATE_FORECAST_SCOPE_AUDIT "+json.dumps({
        "status":"complete","date":args.date,
        "frozen_contracts":result["frozen_contract_count"],
        "prepared_contracts_attempted": (result["pipeline_attempts"] or {}).get("prepared_contracts"),
        "model_coverage":{k:{"forecast":v["forecast"],"unavailable":v["unavailable"]}
                          for k,v in result["model_coverage"].items()},
        "by_sport":result["by_sport"],
        "alternate_quote_levels_not_forecast":
            result["source"]["alternate_quoted_line_levels_not_forecast"],
        "top10_view_only":True},sort_keys=True),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
