#!/usr/bin/env python3
"""2025 retrospective as-of depth QB1 rushing research, *not* source-certified.

Original 2025 8-count replay is untouched. The only new diagnostic markets
are QB rushing attempts (nflverse carries) and QB rushing yards (yards).
Depth-chart QB1 is a research proxy with a dated provider field; its original
historical possession/publication cannot be independently verified. No
postgame NFL schedule QB label is used in candidate creation or inference.
"""
from __future__ import annotations
import argparse,collections,datetime,hashlib,json,math,pathlib,platform,subprocess,sys
from zoneinfo import ZoneInfo
import numpy as np
from v25_opportunity_distribution import OpportunityModel,normalise_player_source,seed_for,digest
from v25_opportunity_repair_replay import read,write_once,file_hash,sample_score,probability_score,metrics,paired
from v25_nfl_2024_all_volume_rolling_calibration import fit_from_past,ptransform
from nfl_contract_settlement import index_outcomes,settle
from v25_opportunity_2025_replay import game_paired

SCHEMA="v25-qb1-2025-retrospective-asof-v1"
EXPERIMENT="V25-QB1-RUSHING-2025-RETROSPECTIVE-20261111"
MARKETS={"qb rushing attempts":"carries","qb rushing yards":"rushing yards"}
METHODS=("raw","global","role")
MODELS=("expanding","frozen_2024")
HERE=pathlib.Path(__file__).resolve().parent


def need(x,why):
    if not x:raise ValueError("2025_QB1_RESEARCH_BLOCK:"+why)


def utc(x):
    need(isinstance(x,str),"clock_not_string")
    try:d=datetime.datetime.fromisoformat(x.replace("Z","+00:00"))
    except ValueError as e:raise ValueError("2025_QB1_RESEARCH_BLOCK:bad_clock") from e
    need(d.tzinfo is not None and d.utcoffset() is not None,"naive_clock")
    return d.astimezone(datetime.timezone.utc)


def kickoff(row):
    need(row.get("gameday") and row.get("gametime"),"schedule_missing_start")
    local=datetime.datetime.fromisoformat(str(row["gameday"])+"T"+str(row["gametime"]))
    return local.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(datetime.timezone.utc)


def asof_depth_qb1(depth_rows,schedule,*,hours_before=2,max_age_days=10):
    """Select solely from depth records issued before intended game freeze.

    A 2026 retrieval of a historically dated record is still *retrospective*;
    it cannot be labeled an original pregame capture.
    """
    need(type(hours_before) is int and hours_before>=1,"bad_freeze_hours")
    need(type(max_age_days) is int and max_age_days>=1,"bad_source_age")
    by_team=collections.defaultdict(list)
    for r in depth_rows:
        if r.get("pos_abb")!="QB" or r.get("pos_rank")!=1:continue
        tm=r.get("team");player=r.get("gsis_id")
        if not isinstance(tm,str) or not tm or not isinstance(player,str) or not player:continue
        try:stamp=utc(r["dt"])
        except (ValueError,KeyError):continue
        by_team[tm].append((stamp,player))
    for tm in by_team:by_team[tm].sort()
    output=[];seen=set()
    for g in schedule:
        if g.get("season")!=2025 or g.get("game_type")!="REG":continue
        start=kickoff(g);freeze=start-datetime.timedelta(hours=hours_before)
        for tm,opp in ((g["home_team"],g["away_team"]),(g["away_team"],g["home_team"])):
            key=(g["game_id"],tm)
            need(key not in seen,"duplicate_team_game")
            seen.add(key)
            # Only source-dated depth observations strictly <= synthetic freeze.
            prior=[x for x in by_team[tm] if x[0]<=freeze and freeze-x[0]<=datetime.timedelta(days=max_age_days)]
            selection=None;reason="missing_recent_asof_qb1_depth"
            if prior:
                time=prior[-1][0]
                qbs={player for t,player in prior if t==time}
                if len(qbs)==1:
                    selection=next(iter(qbs));reason=None
                else:reason="conflicting_same_time_qb1_candidates"
            output.append({
                "event_id":g["game_id"],"team":tm,"opponent":opp,
                "week":int(g["week"]),"player_id":selection,
                "reason":reason,"source_dated_at":time.isoformat() if prior else None,
                "forecast_freeze_at":freeze.isoformat(),
                "kickoff_at":start.isoformat(),
                "role_source":"retrospectively_retrieved_dated_QB1_depth_chart",
                "original_pregame_capture_verified":False,
                "is_authoritative_starter_confirmation":False,
            })
    need(len(output)==544 and len(seen)==544,"incomplete_2025_games")
    return output


def asof_packet(history,week,selected):
    eligible=[x for x in selected if x["week"]==week]
    need(eligible and len({(x["event_id"],x["team"]) for x in eligible})==len(eligible),"bad_qb1_week")
    need(all(x.get("original_pregame_capture_verified") is False and
             x.get("is_authoritative_starter_confirmation") is False for x in eligible),
             "forbidden_original_source_certification")
    need(all(x["player_id"] is None or isinstance(x["player_id"],str) for x in eligible),
             "invalid_depth_qb_identity")
    return {"schema":SCHEMA,"week":week,"season":2025,
            "history":history,"selected_qb1":eligible}


def child_forecast(packet,*,samples=512,seed=20261111):
    need(set(packet)=={"schema","week","season","history","selected_qb1"},"hidden_child_field")
    need(packet["schema"]==SCHEMA and packet["season"]==2025,"wrong_child_schema")
    week=packet["week"];need(type(week) is int and 1<=week<=18,"bad_week")
    need(type(samples) is int and 128<=samples<=4096,"bad_samples")
    hist=packet["history"]
    updated=OpportunityModel(hist,week,forecast_season=2025)
    frozen=OpportunityModel([x for x in hist if x["season"]<2025],week,forecast_season=2025)
    contracts=[];rejected=[];seen=set()
    for g in packet["selected_qb1"]:
        need(set(g)=={"event_id","team","opponent","week","player_id","reason",
                      "source_dated_at","forecast_freeze_at","kickoff_at",
                      "role_source","original_pregame_capture_verified",
                      "is_authoritative_starter_confirmation"},"unregistered_depth_field")
        key=(g["event_id"],g["team"])
        need(key not in seen and g["week"]==week,"wrong_week_or_duplicate")
        seen.add(key)
        start=utc(g["kickoff_at"]);freeze=utc(g["forecast_freeze_at"])
        need(freeze<start,"freeze_after_kickoff")
        pid=g["player_id"]
        if pid:
            need(g["reason"] is None and g["source_dated_at"],"bad_source_selection")
            source=utc(g["source_dated_at"])
            need(source<=freeze and freeze-source<=datetime.timedelta(days=10),"source_future_or_stale")
        else:
            need(g["reason"] in ("missing_recent_asof_qb1_depth","conflicting_same_time_qb1_candidates"),
                 "missing_depth_reason")
            rejected.append({**{k:g[k] for k in ("event_id","team","week")},
                             "reason":g["reason"],"markets":list(MARKETS)})
            continue
        # This is the ONLY QB whose props are considered for this team-game.
        for name,original in MARKETS.items():
            past=updated._player_rows(pid,original)
            if not past:
                rejected.append({"event_id":g["event_id"],"team":g["team"],
                    "week":week,"player_id":pid,"market":name,"reason":"qb1_without_prior_stat"})
                continue
            line=math.floor(float(np.median([p["values"][original] for _,p in past])))+0.5
            forecast_draws={};abstentions={}
            for kind,model in (("expanding",updated),("frozen_2024",frozen)):
                rng=np.random.default_rng(seed_for(seed,week,g["event_id"],g["team"],pid,name,"paired"))
                arr=model.independent(g["team"],pid,"QB",original,rng,samples)
                if arr is None:abstentions[kind]="no_asof_prior"
                else:forecast_draws[kind]=arr.tolist()
            contracts.append({"season":2025,"week":week,"game_id":g["event_id"],
                  "team":g["team"],"player_id":pid,"role":"QB",
                  "market":name,"source_stat":original,"research_line":line,
                  "source_at":g["source_dated_at"],"depth_chart_qb1":True,
                  "depth_chart_is_not_confirmed_starter":True,
                  "source_capture_certified":False,"draws":forecast_draws,
                  "abstentions":abstentions})
    return {"schema":"v25-qb1-2025-forecast-v1","week":week,
            "input_content_sha256":digest(packet),"contracts":contracts,"rejected":rejected,
            "no_backup_or_package_qb_candidates_generated":True,
            "no_postgame_schedule_qb_used":True,
            "authentic_pregame_capture_verified":False,
            "production_authorized":False,"tier_authorized":False}


def run(args):
    need(not args.output_dir.exists(),"append_only_output_exists")
    protocol=read(args.protocol)
    need(protocol.get("experiment_id")==EXPERIMENT and protocol.get("production_authorized") is False,
         "incorrect_protocol_or_release")
    need(protocol.get("samples") in (128,256,512,1024,2048),"bad_protocol_samples")
    need(protocol.get("research_markets")==list(MARKETS),"research_market_scope_mismatch")
    original=read(args.prior_source);future=read(args.oracle_source)
    history=normalise_player_source(original["rows"],rejection_ledger=[])
    oracle=normalise_player_source(future["rows"],rejection_ledger=[],allowed_seasons=(2025,))
    games=read(args.schedule)["rows"]
    need(len(games)==272,"wrong_schedule_size")
    src=read(args.depth_source)
    qbs=asof_depth_qb1(src["rows"],games)
    args.output_dir.mkdir(parents=True)
    code=args.output_dir/"code";code.mkdir()
    filenames=["v25_opportunity_qb1_2025_replay.py","v25_opportunity_distribution.py",
               "v25_opportunity_repair_replay.py","v25_nfl_2024_all_volume_rolling_calibration.py",
               "nfl_contract_settlement.py","v25_opportunity_2025_replay.py"]
    checks={}
    for name in filenames:
        raw=(HERE/name).read_bytes()
        (code/name).write_bytes(raw)
        checks[name]=hashlib.sha256(raw).hexdigest()
    hashes={k:file_hash(getattr(args,k)) for k in
             ("prior_source","oracle_source","schedule","depth_source","protocol")}
    write_once(args.output_dir/"SOURCE_QB1_ASOF_SELECTION.json.gz",
               {"schema":"2025_QB1_asof_selection_research_only","selected":qbs,
                "original_capture_verifiable":False})
    write_once(args.output_dir/"PRE_RUN_FREEZE.json",
               {"source_hashes":hashes,"code_sha256":checks,
                "protocol":protocol,"no_2025_game_results_passed_to_forecast_worker":True})
    byweek=collections.defaultdict(list);score=collections.defaultdict(list)
    weekly=[];manifest=[];counts=collections.Counter()
    for week in range(1,19):
        packet=asof_packet(history,week,qbs)
        inp=args.output_dir/f"week_{week:02d}_asof_input.json.gz"
        pred=args.output_dir/f"week_{week:02d}_forecast.json.gz"
        rawsha=write_once(inp,packet)
        p=subprocess.run([sys.executable,str((code/"v25_opportunity_qb1_2025_replay.py").resolve()),
             "forecast","--input",str(inp),"--output",str(pred),
             "--samples",str(protocol["samples"]),"--seed",str(protocol["seed"])],
             text=True,capture_output=True,timeout=480)
        need(p.returncode==0,"forecast_worker_error:"+p.stderr[-1200:])
        forecast=read(pred)
        need(forecast["input_content_sha256"]==digest(packet),"child_input_mismatch")
        counts["qb1_proposed_contracts"]+=len(forecast["contracts"])
        counts["qb1_abstentions"]+=len(forecast["rejected"])
        # Build from PREVIOUS weeks' outcomes only, before this week's reveal.
        cal={};offered=[]
        for model in MODELS:
            for market in MARKETS:
                past=byweek[model,market]
                need(all(x["week"]<week for x in past),"calibrator_in_week_leak")
                cal[model+"|"+market]=fit_from_past(past)
        for c in forecast["contracts"]:
            for model in MODELS:
                arr=c["draws"].get(model)
                if arr is None:counts[model+":NO_PRIOR"]+=1;continue
                q=sum(y>c["research_line"] for y in arr)/len(arr)
                for method in METHODS:
                    offered.append({**{k:v for k,v in c.items() if k not in ("draws","abstentions")},
                          "model":model,"method":method,"q":ptransform(
                                q,"QB",cal[model+"|"+c["market"]],method),"raw_q":q})
        frozen_cal=args.output_dir/f"week_{week:02d}_calibration_and_offers.json.gz"
        csha=write_once(frozen_cal,{"week":week,"training_through_week":week-1,
                "full_parameter_preimages":cal,"offers":offered})
        actual=[g for g in oracle if g["week"]==week]
        need({(g["event_id"],g["team"]) for g in actual}==
             {(g["event_id"],g["team"]) for g in packet["selected_qb1"]},"oracle_schedule_mismatch")
        labels=[]
        for g in actual:
            for pid,p in g["players"].items():
                if p["role"]!="QB":continue
                for market,col in MARKETS.items():
                    if col in p["values"]:
                        labels.append({"game_id":g["event_id"],"team":g["team"],
                            "player_id":pid,"stat":market,"value":p["values"][col]})
        truth=index_outcomes(labels)
        unique={(c["game_id"],c["team"],c["player_id"],c["market"]):c for c in forecast["contracts"]}
        need(len(unique)==len(forecast["contracts"]),"duplicate_forecast")
        scores=[];states=[]
        for c in forecast["contracts"]:
            st=settle(c,truth)
            states.append({"game_id":c["game_id"],"team":c["team"],
                 "player_id":c["player_id"],"market":c["market"],**st})
            counts["settlement_"+st["state"]]+=1
        for offer in offered:
            st=settle(offer,truth)
            if st["state"]!="SETTLED":continue
            c=unique[offer["game_id"],offer["team"],offer["player_id"],offer["market"]]
            arr=c["draws"][offer["model"]]
            summary=sample_score(arr,st["actual"],c["research_line"])
            if summary["y"] is None or summary["q"] is None:continue
            rec={**offer,**summary,"line":c["research_line"]}
            rec.update(probability_score(offer["q"],summary["y"]))
            scores.append(rec);score[offer["model"],offer["method"],offer["market"]].append(rec)
            if offer["method"]=="raw":
                byweek[offer["model"],offer["market"]].append(
                    {"p":offer["raw_q"],"y":summary["y"],"role":"QB","week":week})
        settlement=args.output_dir/f"week_{week:02d}_settlement.json.gz"
        st_sha=write_once(settlement,{"states":states,"scores":scores,
               "not_graded_as_starter_confirmation":True,
               "historical_schedule_actual_qb_never_used_for_selection":True})
        manifest.append({"week":week,"asof_sha":rawsha,"forecast_sha":file_hash(pred),
          "calibration_sha":csha,"settlement_sha":st_sha})
        weekly.append({"week":week,"selected_qb1":sum(x["player_id"] is not None for x in packet["selected_qb1"]),
           "source_unverified":sum(x["player_id"] is None for x in packet["selected_qb1"]),
           "forecast_contracts":len(forecast["contracts"]),"settlement_states":
           dict(collections.Counter(x["state"] for x in states))})
        history+=actual
        print("QB1_RUSHING_WEEK_FROZEN",week,"contracts",len(forecast["contracts"]),flush=True)
    per_market={}
    for market in MARKETS:
        a=score["expanding","raw",market];b=score["frozen_2024","raw",market]
        per_market[market]={"models":{m:{method:metrics(score[m,method,market])
               for method in METHODS} for m in MODELS},
           "paired_expanding_minus_frozen":{metric:{"week":paired(a,b,metric),
                    "game":game_paired(a,b,metric)}
                   for metric in ("brier","log_loss","crps","bias")}}
    result={"schema":"v25-qb1-rushing-2025-retrospective-completed-v1",
          "experiment_id":EXPERIMENT,"status":"COMPLETED_RETROSPECTIVE_RESEARCH",
          "2025_untouched_holdout":False,
          "2025_source_depth_chart_qb1_not_actual_captured_pregame":True,
          "schedule_actual_qb_not_used_in_forecaster":True,
          "does_not_forecast_backups_or_packages":True,
          "original_2025_eight_market_replay_unchanged":True,
          "no_real_bookmaker_2025_lines":True,
          "production_authorized":False,"tier1_tier2_authorized":False,
          "count_sample_semantics":{"qb rushing attempts":"nflverse_carries",
                                     "qb rushing yards":"nflverse_rushing_yards",
                                     "QB_sacks_not_counted_as_rushes":True},
          "source_hashes":hashes,"code_hashes":checks,
          "coverage":dict(counts),"manifest":manifest,"weekly":weekly,
          "markets":per_market}
    result["receipt_sha256"]=digest(result)
    write_once(args.output_dir/"FINAL_QB1_RESEARCH_REPORT.json",result)
    print("QB1_RESEARCH_COMPLETED",json.dumps({
          "receipt_sha256":result["receipt_sha256"],"markets":per_market,
          "coverage":dict(counts)},sort_keys=True)[:18000],flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    f=sub.add_parser("forecast")
    for name in ("input","output"):f.add_argument("--"+name,type=pathlib.Path,required=True)
    f.add_argument("--samples",type=int,required=True)
    f.add_argument("--seed",type=int,required=True)
    r=sub.add_parser("run")
    for name in ("prior-source","oracle-source","schedule","depth-source","protocol","output-dir"):
        r.add_argument("--"+name,type=pathlib.Path,required=True)
    a=p.parse_args()
    if a.mode=="forecast":write_once(a.output,child_forecast(read(a.input),samples=a.samples,seed=a.seed))
    else:run(a)


if __name__=="__main__":main()
