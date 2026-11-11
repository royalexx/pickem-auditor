#!/usr/bin/env python3
"""Read-only, no-fit, independent verification of preserved QB1 2025 replay."""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,math,pathlib,statistics
from datetime import datetime
from zoneinfo import ZoneInfo

MODELS={"expanding","frozen_2024"}
METHODS={"raw","global","role"}
MARKETS={"qb rushing attempts":"carries","qb rushing yards":"rushing_yards"}
HISTORY_STAT={"qb rushing attempts":"carries","qb rushing yards":"rushing yards"}
EXPECTED="V25-QB1-RUSHING-2025-RETROSPECTIVE-20261111"


def fail(why):
    raise AssertionError("QB1_INDEPENDENT_AUDIT_FAILED:"+why)


def need(cond,why):
    if not cond:fail(why)


def rawread(path):
    raw=path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix==".gz" else raw)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),
        allow_nan=False).encode()).hexdigest()


def approx(a,b,tolerance=1e-10):
    return math.isclose(float(a),float(b),rel_tol=tolerance,abs_tol=tolerance)


def crps(values,actual):
    x=sorted(float(v) for v in values)
    n=len(x)
    return sum(abs(v-actual) for v in x)/n-sum((2*i-n+1)*v for i,v in enumerate(x))/(n*n)


def audit(folder,sources):
    folder=pathlib.Path(folder);report=rawread(folder/"FINAL_QB1_RESEARCH_REPORT.json")
    need(report.get("experiment_id")==EXPECTED,"wrong_experiment")
    need(report.get("status")=="COMPLETED_RETROSPECTIVE_RESEARCH","not_completed")
    need(report.get("production_authorized") is False and
         report.get("tier1_tier2_authorized") is False,"release_claim")
    need(report.get("2025_untouched_holdout") is False and
         report.get("2025_source_depth_chart_qb1_not_actual_captured_pregame") is True,
         "retrospective_source_mislabeled")
    need(digest({k:v for k,v in report.items() if k!="receipt_sha256"})==
         report["receipt_sha256"],"final_report_sha")
    checks=collections.Counter()
    for name,h in report["code_hashes"].items():
        need(sha(folder/"code"/name)==h,"code_changed_after_forecast")
        checks["code_files"]+=1
    for name,path in sources.items():
        need(sha(path)==report["source_hashes"][name],"source_file_changed:"+name)
        checks["original_source_hashes"]+=1
    schedule=rawread(sources["schedule"])["rows"]
    need(len(schedule)==272,"missing_schedule")
    oracle=rawread(sources["oracle_source"])["rows"]
    # Exact event+team+QB original player rows, no final-QB schedule identity.
    obs={}
    for r in oracle:
        if r.get("season_type")!="REG" or r.get("position")!="QB":continue
        if r.get("player_id") is None:continue
        key=(r["game_id"],r["team"],r["player_id"])
        need(key not in obs,"duplicate_QB_oracle_row")
        obs[key]=r
    selection=rawread(folder/"SOURCE_QB1_ASOF_SELECTION.json.gz")["selected"]
    need(len(selection)==544,"incomplete_original_depth_selection")
    selected={(x["event_id"],x["team"]):x for x in selection}
    need(len(selected)==544,"duplicate_original_depth_team")
    check_counts=collections.Counter();scored=collections.defaultdict(list)
    for x in selected.values():
        need(x["original_pregame_capture_verified"] is False and
             x["is_authoritative_starter_confirmation"] is False,
             "source_provenance_falsely_certified")
        check_counts["qb1_selected"]+=x["player_id"] is not None
        check_counts["qb1_source_missing"]+=x["player_id"] is None
        if x["player_id"]:
            t=datetime.fromisoformat(x["source_dated_at"])
            f=datetime.fromisoformat(x["forecast_freeze_at"])
            e=datetime.fromisoformat(x["kickoff_at"])
            need(t<=f<e and f-t<=__import__("datetime").timedelta(days=10),
                 "after_event_or_stale_qb1_source")
    need(len(report["manifest"])==18,"wrong_week_manifest")
    for week,manifest in enumerate(report["manifest"],1):
        need(manifest["week"]==week,"week_order")
        def path(filename):return folder/f"week_{week:02d}_{filename}.json.gz"
        inp=path("asof_input");pred=path("forecast")
        calibration=path("calibration_and_offers");settled=path("settlement")
        for a,b,expected in (
                (inp,"asof_sha",manifest["asof_sha"]),
                (pred,"forecast_sha",manifest["forecast_sha"]),
                (calibration,"calibration_sha",manifest["calibration_sha"]),
                (settled,"settlement_sha",manifest["settlement_sha"])):
            need(sha(a)==expected,"frozen_week_artifact_mutation:"+b)
            checks["week_sha_verified"]+=1
        prior=rawread(inp);f=rawread(pred);cal=rawread(calibration);actual=rawread(settled)
        need(prior["season"]==2025 and prior["week"]==week and
             f["input_content_sha256"]==digest(prior),"child_asof_input")
        need(cal["week"]==week and cal["training_through_week"]==week-1,
             "same_week_calibration_leak")
        # Nothing that looks like the schedule's *known after game* QB identity
        # or actual completed game scores can enter the child.
        need(set(prior)=={"schema","season","week","history","selected_qb1"},
             "child_hidden_factual_outcome")
        need(all(x["season"]<2025 or x["week"]<week for x in prior["history"]),
             "future_game_training_leak")
        need(set(f["contracts"][0])=={
          "season","week","game_id","team","player_id","role","market",
          "source_stat","research_line","source_at","depth_chart_qb1",
          "depth_chart_is_not_confirmed_starter","source_capture_certified",
          "draws","abstentions"} if f["contracts"] else True,
          "forecast_contract_schema_changed")
        single={(c["game_id"],c["team"],c["player_id"],c["market"]):c
                for c in f["contracts"]}
        need(len(single)==len(f["contracts"]),"duplicate_forecast")
        for c in f["contracts"]:
            k=(c["game_id"],c["team"]);sel=selected.get(k)
            need(sel is not None and c["player_id"]==sel["player_id"] and
                 c["market"] in MARKETS and c["role"]=="QB","nonstarter_or_nonQB_market")
            need(sel["week"]==week and c["source_at"]==sel["source_dated_at"],
                 "original_qb1_not_bound_to_contract")
            need(c["source_capture_certified"] is False and
                 c["depth_chart_is_not_confirmed_starter"] is True,
                 "historical_role_certification_false")
            # Independent synthetic line from *prior to forecast* matching QB rows.
            col=HISTORY_STAT[c["market"]]
            prior_values=[x["players"][c["player_id"]]["values"][col]
                          for x in prior["history"] if c["player_id"] in x["players"]
                          and col in x["players"][c["player_id"]]["values"]]
            need(bool(prior_values),"forecast_without_prior_player")
            expected=math.floor(statistics.median(prior_values[-8:]))+.5
            need(approx(expected,c["research_line"]),"outcome_tuned_line")
            checks["contracts"]+=1
        original_offers=collections.Counter()
        for offer in cal["offers"]:
            k=(offer["game_id"],offer["team"],offer["player_id"],offer["market"])
            need(k in single,"offer_for_missing_forecast")
            need(offer["model"] in MODELS and offer["method"] in METHODS,"unknown_model_method")
            c=single[k];values=c["draws"].get(offer["model"])
            need(values is not None,"calibration_on_abstained_model")
            raw=sum(v>c["research_line"] for v in values)/len(values)
            need(approx(raw,offer["raw_q"]),"raw_probability_reconstructed_incorrectly")
            need(0<=float(offer["q"])<=1,"calibration_non_probability")
            original_offers[k,offer["model"],offer["method"]]+=1
            checks["forecast_probabilities"]+=1
        need(all(x==1 for x in original_offers.values()),"duplicate_original_offer")
        actual_scores=actual["scores"]
        for row in actual_scores:
            k=(row["game_id"],row["team"],row["player_id"],row["market"])
            need(k in single,"scored_not_original_forecast")
            c=single[k]
            need(row["market"] in MARKETS,"rb_market_or_unregistered_stat_injected")
            truth=obs.get((row["game_id"],row["team"],row["player_id"]))
            need(truth is not None,"postgame_score_without_exact_QB_observation")
            y=float(truth[MARKETS[c["market"]]])
            need(approx(row["actual"],y),"scored_wrong_outcome")
            side=int(y>c["research_line"])
            need(row["y"]==side and y!=c["research_line"],"wrong_side_or_push")
            draws=c["draws"][row["model"]]
            need(approx(row["mean"],sum(draws)/len(draws)),"scenario_mean_falsified")
            need(approx(row["crps"],crps(draws,y)),"count_CRPS_falsified")
            need(approx(row["brier"],(float(row["q"])-side)**2),"Brier_falsified")
            need(approx(row["raw_q"],sum(v>c["research_line"] for v in draws)/len(draws)),
                 "market_probability_falsified")
            check_counts["scored_"+row["market"]]+=1
            scored[row["market"],row["model"],row["method"]].append(row)
        checks["weeks_replayed"]+=1
    for m,stats in report["markets"].items():
        for control,methods in stats["models"].items():
            for method,metrics in methods.items():
                n=len(scored[m,control,method])
                need(metrics["n"]==n,"aggregate_n_changed")
                if n:
                    for field in ("brier","log_loss","crps","bias"):
                        need(approx(metrics[field],
                            sum(x[field] for x in scored[m,control,method])/n),
                            "aggregate_changed_"+field)
                checks["aggregate_metrics"]+=1
    result={"schema":"v25-qb1-2025-independent-no-fit-rescore-v1",
            "passed":True,"original_research_report_sha256":sha(folder/"FINAL_QB1_RESEARCH_REPORT.json"),
            "original_receipt_sha256":report["receipt_sha256"],
            "checks":dict(checks),"cohorts":dict(check_counts),
            "asof_selection_source_is_retroactive_not_pregame_certified":True,
            "production_authorized":False,"tier1_tier2_authorized":False}
    result["receipt_sha256"]=digest(result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--folder",required=True,type=pathlib.Path)
    p.add_argument("--prior-source",required=True,type=pathlib.Path)
    p.add_argument("--oracle-source",required=True,type=pathlib.Path)
    p.add_argument("--schedule",required=True,type=pathlib.Path)
    p.add_argument("--depth-source",required=True,type=pathlib.Path)
    p.add_argument("--protocol",required=True,type=pathlib.Path)
    p.add_argument("--output",required=True,type=pathlib.Path)
    a=p.parse_args()
    need(not a.output.exists(),"audit_append_only_output")
    result=audit(a.folder,{k:getattr(a,k) for k in ("prior_source","oracle_source","schedule","depth_source","protocol")})
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("x",encoding="utf8") as f:json.dump(result,f,indent=2,sort_keys=True)
    print(json.dumps(result,sort_keys=True))


if __name__=="__main__":main()
