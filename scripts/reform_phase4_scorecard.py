"""Read-only Phase 4 scoring of original, independently settled prop contracts.

No reforecasting, retraining, market refit, or prospective/retrospective pooling.
An Over/Under pair is one Bernoulli observation, never two independent hits.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

MODELS = ("Engine_A", "Engine_B", "Bayesian_A", "Bayesian_B", "NUTS",
          "Consensus", "Market", "70_30_diagnostic", "counterfactual_60_40_3H")
LIVE_MODELS = MODELS[:7]


class AuditError(ValueError):
    pass


def stamp(raw):
    if not isinstance(raw, str) or "T" not in raw:
        raise AuditError("missing_aware_timestamp")
    try:
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditError("invalid_timestamp") from exc
    if value.tzinfo is None:
        raise AuditError("naive_timestamp")
    return value.astimezone(timezone.utc)


def read_json(path):
    payload = Path(path).read_bytes()
    return json.loads(payload), hashlib.sha256(payload).hexdigest()


def numeric(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 <= number <= 1 else None


def contract_key(row):
    line = row.get("line", row.get("reference_line"))
    if isinstance(line, bool) or line is None:
        raise AuditError("missing_line")
    value = float(line)
    if not math.isfinite(value):
        raise AuditError("nonfinite_line")
    return (str(row.get("sport")), str(row.get("event_start")),
            str(row.get("team")), str(row.get("opponent")),
            str(row.get("player_id")), str(row.get("player")),
            str(row.get("stat")), format(value, ".15g"))


def winner(actual, line):
    if actual == line:
        return "push"
    return "over" if actual > line else "under"


def source_model(over, under):
    a, b = numeric(over), numeric(under)
    if a is None or b is None:
        return None
    return {"over": a, "under": b, "side_sum": a + b}


def chosen(model, outcome):
    if model is None or abs(model["over"] - model["under"]) < 1e-12:
        return None
    side = "over" if model["over"] > model["under"] else "under"
    p = model[side]
    return {"side": side, "p": p, "hit": int(side == outcome),
            "winner": outcome, "over": model["over"], "under": model["under"],
            "side_sum": model["side_sum"]}


def score(rows):
    values = [r for r in rows if r is not None]
    n = len(values)
    if not n:
        return {"n": 0}
    confidence = sum(x["p"] for x in values) / n
    hits = sum(x["hit"] for x in values)
    def logloss(x):
        p = min(1 - 1e-12, max(1e-12, x["p"]))
        return -(x["hit"] * math.log(p) + (1 - x["hit"]) * math.log(1-p))
    return {"n": n, "hits": hits, "directional_accuracy": hits/n,
            "mean_selected_probability": confidence,
            "confidence_minus_hit_rate": confidence-hits/n,
            "brier": sum((x["p"]-x["hit"])**2 for x in values)/n,
            "log_loss": sum(logloss(x) for x in values)/n,
            "predicted_over_share": sum(x["side"] == "over" for x in values)/n,
            "actual_over_share": sum(x["winner"] == "over" for x in values)/n,
            "selected_80plus": sum(x["p"] >= .8 for x in values),
            "selected_80plus_hits": sum(x["hit"] for x in values if x["p"] >= .8),
            "nonunit_probability_pairs": sum(abs(x["side_sum"]-1) > 1e-8 for x in values)}


def models_by_contract(contracts, names):
    output = {}
    for m in names:
        subset = [r["models"].get(m) for r in contracts]
        output[m] = score(subset)
    return output


def matched_pairwise(contracts, model_a, model_b):
    same = [r for r in contracts
            if r["models"].get(model_a) is not None and
               r["models"].get(model_b) is not None]
    left, right = score([r["models"][model_a] for r in same]), score([r["models"][model_b] for r in same])
    if not same:
        return {"n": 0}
    return {"n": len(same), model_a: left, model_b: right,
            "brier_delta_a_minus_b": left["brier"]-right["brier"],
            "logloss_delta_a_minus_b": left["log_loss"]-right["log_loss"]}


def slices(contracts, names, *, min_bucket=8):
    markets, sports, days = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for row in contracts:
        sports[row["sport"]].append(row)
        markets[(row["sport"], row["stat"])].append(row)
        days[row["date"]].append(row)
    return {
        "by_sport": {s: models_by_contract(v, names) for s,v in sorted(sports.items())},
        "by_sport_market": {"/".join(k): models_by_contract(v, names)
                            for k,v in sorted(markets.items()) if len(v) >= min_bucket},
        "by_date": {s: models_by_contract(v, names) for s,v in sorted(days.items())}
    }


def probability_bins(contracts, names):
    cuts=(.5,.6,.7,.8,1.000001)
    out={}
    for m in names:
        cats=collections.defaultdict(list)
        for row in contracts:
            p=row["models"].get(m)
            if p is None:
                continue
            idx=next((i for i in range(4) if cuts[i] <= p["p"] < cuts[i+1]),None)
            label=("50-60%","60-70%","70-80%","80-100%")[idx] if idx is not None else "below_50%"
            cats[label].append(p)
        out[m]={s:score(v) for s,v in sorted(cats.items())}
    return out


def load_nfl_slate(frozen, official, pinned, start="2026-11-08T18:00:00Z"):
    a, sha_a = read_json(frozen)
    b, sha_b = read_json(official)
    receipt,_ = read_json(pinned)
    if (receipt.get("baseline_policy_verified") is not True or
        receipt.get("comparison_sha256") != sha_a or
        receipt.get("settlement_sha256") != sha_b or
        a.get("schema") != "slate-model-comparison-v1" or
        b.get("pregame_run") != a.get("metadata",{}).get("run_id") or
        b.get("code_sha") != a.get("metadata",{}).get("code_sha") or
        b.get("start_window_utc") != start):
        raise AuditError("frozen_source_or_official_receipt_mismatch")
    pairs=collections.defaultdict(dict)
    for row in a["picks"]:
        if row.get("sport") != "NFL" or row.get("event_start") != start:
            continue
        key=contract_key(row)
        side=row.get("side")
        if side not in ("over","under") or side in pairs[key]:
            raise AuditError("duplicate_or_invalid_frozen_side")
        if stamp(row["forecast_at"]) >= stamp(start):
            raise AuditError("post_kickoff_forecast")
        pairs[key][side]=row
    if len(pairs) != receipt["scope"]["contracts"]:
        raise AuditError("frozen_contract_count_changed")
    for key,side in pairs.items():
        if set(side) != {"over","under"}:
            raise AuditError("missing_frozen_counterpart")
        if abs((stamp(side["over"]["forecast_at"])-
                stamp(side["under"]["forecast_at"])).total_seconds()) > 300:
            raise AuditError("paired_forecasts_too_far_apart")
    games={frozenset(g.get("teams") or []):str(g.get("espn_event_id"))
           for g in b.get("games",[]) if g.get("status")=="final"}
    if not games:
        raise AuditError("missing_official_final_game_registry")
    seen=set()
    rows=[]
    exclusions=collections.Counter()
    for c in b["contracts"]:
        if not isinstance(c,dict):
            raise AuditError("invalid_settlement_record")
        key=("NFL",start,str(c.get("team")),str(c.get("opponent")),
             str(c.get("player_id_gsis")),str(c.get("player")),
             str(c.get("stat")),format(float(c["line"]),".15g"))
        if key not in pairs or key in seen:
            raise AuditError("unmatched_or_duplicate_official_settlement")
        seen.add(key)
        if c.get("pregame_forecast_at") not in (
            pairs[key]["over"]["forecast_at"],pairs[key]["under"]["forecast_at"]):
            raise AuditError("settlement_wrong_frozen_forecast_time")
        gid=games.get(frozenset((c.get("team"),c.get("opponent"))))
        if not gid or str(c.get("espn_game_id")) != gid:
            raise AuditError("settlement_missing_official_event")
        if c.get("settlement_status") != "verified":
            exclusions[c.get("settlement_status") or "unverified"]+=1
            continue
        actual=float(c["actual"])
        if not math.isfinite(actual) or actual<0:
            raise AuditError("invalid_official_actual")
        label=winner(actual,float(c["line"]))
        if label != c.get("winning_side"):
            raise AuditError("winning_side_mismatch")
        if label == "push":
            exclusions["push"]+=1
            continue
        sides=pairs[key]
        model_predictions={m:chosen(source_model(
            sides["over"].get(m),sides["under"].get(m)),label)
                           for m in LIVE_MODELS}
        rows.append({"sport":"NFL","stat":c["stat"],"date":"2026-11-08",
                     "game_id":gid,"contract":key,"outcome":label,
                     "actual":actual,"models":model_predictions,
                     "consensus_available":sides["over"].get("Consensus") is not None})
    if (len(rows) != receipt["settlement"]["verified_contracts"] or
        len(seen) != receipt["settlement"]["seen_settlement_contracts"]):
        raise AuditError("pinned_settlement_counts_changed")
    return rows, {"comparisons_sha256":sha_a,"official_sha256":sha_b,
                  "settled_contracts":len(rows),"all_frozen_contracts":len(pairs),
                  "excluded":dict(exclusions),"pinned_run_id":a["metadata"]["run_id"],
                  "source_completeness_verified":False}


def load_historical(path, archive_root):
    src, sha = read_json(path)
    if src.get("schema") != "archived_source_only_research_backtest_v1":
        raise AuditError("wrong_historical_backtest_schema")
    hashes=[]
    for item in src.get("archives",[]):
        archive=Path(archive_root)/"pickem_runs"/item["date"]/Path(item["archive"]).parent.name/Path(item["archive"]).name
        # Source name is a pinned Deepnote run folder; resolve using the
        # relative pickem_runs path rather than trusting an absolute base path.
        raw=str(item["archive"])
        pos=raw.find("pickem_runs/")
        if pos<0:
            raise AuditError("missing_archive_relative_path")
        archive=Path(archive_root)/raw[pos:]
        if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest()!=item["sha256"]:
            raise AuditError("historical_archive_sha256_mismatch")
        hashes.append({"date":item["date"],"sha256":item["sha256"]})
    registry={str(g["id"]):g for g in src.get("sources",[])
              if str(g.get("detail") or "").startswith("Final") and g.get("start")}
    out=[]
    excluded=collections.Counter()
    seen=set()
    for c in src["contracts"]:
        status=c.get("status")
        if status!="settled":
            excluded[status or "unknown"]+=1
            continue
        key=(c["day"],c["sport"],str(c["game_id"]),c["team"],
             c["player"],c["stat"],format(float(c["line"]),".15g"))
        if key in seen: raise AuditError("duplicate_historical_contract")
        seen.add(key)
        game=registry.get(str(c["game_id"]))
        if not game or c["sport"]!=game["sport"] or c["day"]!=game["date"] or stamp(c["forecast_at"])>=stamp(game["start"]):
            raise AuditError("historical_forecast_after_game_or_missing_source")
        actual=float(c["actual"])
        if not math.isfinite(actual) or winner(actual,float(c["line"]))!=c.get("winner") or c["winner"]=="push":
            raise AuditError("invalid_historical_actual")
        model_predictions={}
        for model in ("Engine_A","Engine_B","Bayesian_A","Bayesian_B",
                      "Market","70_30_diagnostic","counterfactual_60_40_3H"):
            x=(c.get("models") or {}).get(model)
            model_predictions[model]=chosen(source_model(x.get("over"),x.get("under")),c["winner"]) if isinstance(x,dict) else None
        out.append({"sport":c["sport"],"stat":c["stat"],"date":c["day"],
                    "game_id":str(c["game_id"]),"contract":key,
                    "outcome":c["winner"],"actual":actual,"models":model_predictions})
    return out, {"source_sha256":sha,"archives":hashes,"settled_contracts":len(out),
                 "excluded":dict(excluded),"source_level":"retrospective_official_result_archive",
                 "source_completeness_verified":False}


def evaluate(nfl, historical):
    models={m:score([r["models"].get(m) for r in nfl]) for m in LIVE_MODELS}
    historical_models=("Engine_A","Engine_B","Bayesian_A","Bayesian_B",
                       "Market","70_30_diagnostic","counterfactual_60_40_3H")
    overlap=[r for r in nfl if r["models"].get("Consensus") is not None and r["models"].get("Market") is not None]
    return {"schema":"pickem_reform_phase4_diagnostic_v1",
            "validated_for_deployment":False,
            "retraining_performed":False,"production_modified":False,
            "sample_granularity":"one_nonpush_contract_not_two_sides",
            "prospective_nfl_1pm":{
                "contract_count":len(nfl),"unique_games":len({r["game_id"] for r in nfl}),
                "production_consensus_coverage":sum(r["models"].get("Consensus") is not None for r in nfl),
                "models":models,"common_consensus_market":matched_pairwise(nfl,"Consensus","Market"),
                "confidence_bins":probability_bins(nfl,LIVE_MODELS),
                "subgroups":slices(nfl,LIVE_MODELS),
            },
            "retrospective_2026_11_05_to_07":{
                "contract_count":len(historical),"unique_games":len({r["game_id"] for r in historical}),
                "models":models_by_contract(historical,historical_models),
                "common_engine_a_market":matched_pairwise(historical,"Engine_A","Market"),
                "confidence_bins":probability_bins(historical,historical_models),
                "subgroups":slices(historical,historical_models),
            },
            "limitations":[
                "Only four slate dates; date-cluster inference and promotion are underpowered",
                "Old November 5-7 sources contain independent retrospective settlement, not fully archived original input bytes",
                "Nov 8 source-feature receipts are incomplete; official outcome audit is distinct from full input provenance",
                "Do not treat 70_30_diagnostic or counterfactual_60_40_3H as November 8 production",
                "Different model coverage requires same-contract paired comparisons",
                "Confidence intervals and high-confidence selection require more independent future slates"]}


def main(argv=None):
    ap=argparse.ArgumentParser()
    for key in ("frozen","settlement","pinned","historical","archive_root"):
        ap.add_argument("--"+key.replace("_","-"),type=Path,required=True)
    ap.add_argument("--out",type=Path,required=False)
    args=ap.parse_args(argv)
    nfl,nmeta=load_nfl_slate(args.frozen,args.settlement,args.pinned)
    hist,hmeta=load_historical(args.historical,args.archive_root)
    report=evaluate(nfl,hist)
    report["provenance"]={"nfl":nmeta,"historical":hmeta}
    serialized=json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n"
    if args.out:
        if args.out.exists() and args.out.read_text()!=serialized:
            raise AuditError("would_overwrite_different_receipt")
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(serialized)
    print(json.dumps({"status":"read_only","new_prospective_contracts":len(nfl),
                      "older_retro_contracts":len(hist),
                      "nfl_consensus":report["prospective_nfl_1pm"]["models"]["Consensus"],
                      "nfl_matched_market":report["prospective_nfl_1pm"]["common_consensus_market"],
                      "older_models":report["retrospective_2026_11_05_to_07"]["models"],
                      "older_matched_market":report["retrospective_2026_11_05_to_07"]["common_engine_a_market"]},sort_keys=True))


if __name__=="__main__":
    main()
