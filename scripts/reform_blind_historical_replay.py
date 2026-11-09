"""Strict blind historical NFL tackle-opportunity replay, research only.

Three explicit stages: prepare (source/outcomes access), forecast (reads
ONLY sanitized frozen packets with no slate outcomes), settle (requires
immutable forecast SHA receipt, then reads isolated outcome vault).
Neither NUTS retraining nor sportsbook market-line reconstruction.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import argparse
import hashlib
import json
import math
from pathlib import Path

from nfl_tackle_snap_share import (
    VERSION as TACKLE_VERSION,POSITION_ROLE_GROUPS,normalize_bundles,
    derive_frozen_position_lines,index_research_history,predict,
    score_probability,positive,parse_stamp,
)

SCHEMA="pickem-blind-historical-tackle-v1"
FORBIDDEN_PACKET_KEYS={"outcome","actual","tackles_assists","value","hit",
                       "settlement","final_score","home_score","away_score"}
# Historical training rows MUST have tackles_assists; only upcoming fixtures
# and candidate rows are barred from containing it.
FORBIDDEN_TARGET_KEYS=FORBIDDEN_PACKET_KEYS|{"workload","player_defensive_snaps",
                                          "team_defensive_plays"}


class BlindReplayError(ValueError):
    pass


def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(",",":"),
                       allow_nan=False,ensure_ascii=True)+"\n").encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()


def write_once(path,body):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=encode(body)
    if path.exists() and path.read_bytes()!=raw:
        raise BlindReplayError("would_rewrite_immutable_replay_artifact:"+str(path))
    if not path.exists():path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def read_receipt(path):
    raw=Path(path).read_bytes()
    return json.loads(raw),hashlib.sha256(raw).hexdigest()


def prepare(bundles, *, from_day,through_day,packet_dir,vault_file,
            max_slates=25):
    """Only source-aware preparer sees target outcomes; forecast doesn't.

    Pre-game candidate roster is inferred from recent PRIOR defender rows,
    NOT the actual current game's boxscore, so a player who never appears
    remains a candidate and is NOT silently labeled a loss.
    """
    beginning=parse_stamp(from_day+"T00:00:00+00:00","holdout_from")
    ending=parse_stamp(through_day+"T00:00:00+00:00","holdout_through")
    if not beginning<ending:raise BlindReplayError("bad_holdout_window")
    history=normalize_bundles(bundles)
    allrows=history["rows"]
    # Team-game fixtures derived from schedule, not final boxscore.
    games={}
    for bundle in bundles:
        for row in bundle["teams"]:
            t=parse_stamp(row["start_time"],"event_start")
            if not beginning<=t<ending:continue
            key=(str(row["game_id"]),str(row["team"]))
            if key in games:raise BlindReplayError("duplicate_team_fixture")
            games[key]={"game_id":str(row["game_id"]),
                        "team":str(row["team"]),"opponent":str(row["opponent"]),
                        "event_start":t.isoformat()}
    by_day=defaultdict(list)
    for fixture in games.values():
        day=fixture["event_start"][:10]
        by_day[day].append(fixture)
    packets=[]
    target_labels=[]
    all_days=sorted(by_day)[:max_slates]
    if not all_days:raise BlindReplayError("no_fixture_slate_days")
    for day in all_days:
        fixtures=sorted(by_day[day],key=lambda x:(
            x["event_start"],x["game_id"],x["team"]))
        # An entire slate's forecasts share ONE cutoff prior to the FIRST
        # event in that slate: no early-game outcome can leak to later games.
        first=min(parse_stamp(x["event_start"],"first_kickoff") for x in fixtures)
        cutoff=first-timedelta(hours=2)
        prior=[r for r in allrows if parse_stamp(r["available_at"],"prior_availability")<cutoff
               and parse_stamp(r["start_time"],"prior_start")<first]
        if not prior:
            continue
        at_time=cutoff.isoformat()
        h={"schema":TACKLE_VERSION,"rows":prior,
           "time_provenance":history["time_provenance"],
           "history_source_digests":history["history_source_digests"],
           "source_quality_counts":history.get("source_quality_counts",{}),
           "production_eligible":False}
        frozen=derive_frozen_position_lines(h,before=at_time)
        by_team=defaultdict(list)
        for row in prior:by_team[row["team"]].append(row)
        candidates=[]
        for fixture in fixtures:
            team=fixture["team"]
            recent_by_player=defaultdict(list)
            for row in by_team[team]:
                recent_by_player[row["player_id"]].append(row)
            for player_id,rows in recent_by_player.items():
                rows.sort(key=lambda r:r["start_time"])
                if len(rows)<3:continue
                last=parse_stamp(rows[-1]["start_time"],"last_prior_player_game")
                if (first-last)>timedelta(days=35):continue
                position=Counter(r["position"] for r in rows[-12:]).most_common(1)[0][0]
                role=POSITION_ROLE_GROUPS.get(position)
                line=frozen["role_lines"].get(role,{}).get("line")
                if line is None:continue
                candidate={"game_id":fixture["game_id"],
                           "event_start":fixture["event_start"],
                           "player_id":str(player_id),
                           "team":team,"opponent":fixture["opponent"],
                           "prior_position":position,"prior_role":role,
                           "research_line":line}
                if FORBIDDEN_TARGET_KEYS.intersection(candidate):
                    raise BlindReplayError("target_result_in_candidate")
                candidates.append(candidate)
        if not candidates:continue
        event_ids={f["game_id"] for f in fixtures}
        if any(r["game_id"] in event_ids for r in prior):
            raise BlindReplayError("target_slate_outcome_entered_training_history")
        packet={"schema":SCHEMA,"stage":"pregame_packet",
                "slate_date":day,"cutoff":at_time,
                "history":h,
                "fixtures":fixtures,
                "candidates":sorted(candidates,key=lambda x:(
                    x["game_id"],x["team"],x["player_id"])),
                "line_policy":"pregame_training_only_position_median",
                "target_outcomes_in_packet":False,
                "production_eligible":False}
        packet_path=Path(packet_dir)/(day+".json")
        packet_sha=write_once(packet_path,packet)
        packets.append({"slate_date":day,"filename":day+".json",
                        "sha256":packet_sha,"candidates":len(candidates),
                        "training_rows":len(prior)})
        for r in allrows:
            if r["game_id"] not in event_ids:continue
            if (r["team"],r["player_id"]) not in {
                (c["team"],c["player_id"]) for c in candidates}:continue
            target_labels.append({"slate_date":day,"game_id":r["game_id"],
                                  "team":r["team"],"player_id":r["player_id"],
                                  "actual":r["tackles_assists"],
                                  "actual_snaps":r["player_defensive_snaps"]})
    vault={"schema":SCHEMA,"stage":"sealed_outcomes",
           "label_scope":"participating_players_only",
           "labels":target_labels,"source_approximation":history["time_provenance"]}
    vault_sha=write_once(vault_file,vault)
    manifest={"schema":SCHEMA,"stage":"prepared","packets":packets,
              "slate_days":len(packets),
              "target_label_vault_sha256":vault_sha,
              "raw_source_history_digests":history["history_source_digests"],
              "training_started":False,
              "target_outcomes_in_forecast_packet":False}
    write_once(Path(packet_dir)/"MANIFEST.json",manifest)
    return manifest


def forecast(packet_dir,forecast_file):
    """This worker only receives packets. No outcome vault path or data."""
    directory=Path(packet_dir)
    manifest,manifest_sha=read_receipt(directory/"MANIFEST.json")
    if manifest.get("stage")!="prepared":raise BlindReplayError("unfrozen_packet_manifest")
    predictions=[]
    for receipt in manifest["packets"]:
        path=directory/receipt["filename"]
        packet,sha=read_receipt(path)
        if sha!=receipt["sha256"]:raise BlindReplayError("modified_pregame_packet")
        if packet.get("target_outcomes_in_packet") is not False:
            raise BlindReplayError("target_outcome_not_hidden")
        candidates=packet["candidates"]
        for candidate in candidates:
            if FORBIDDEN_TARGET_KEYS.intersection(candidate):
                raise BlindReplayError("target_has_result_in_forecast_worker")
        cutoff=parse_stamp(packet["cutoff"],"forecast_cutoff")
        for fixture in packet["fixtures"]:
            if not cutoff<parse_stamp(fixture["event_start"],"event_start"):
                raise BlindReplayError("forecast_not_pregame")
        history=packet["history"]
        target_games={x["game_id"] for x in packet["fixtures"]}
        if any(parse_stamp(r["available_at"],"prior_time")>=cutoff or
               r["game_id"] in target_games for r in history["rows"]):
            raise BlindReplayError("future_history_in_pregame_packet")
        idx=index_research_history(history)
        for item in candidates:
            p=predict(idx,player_id=item["player_id"],team=item["team"],
                      game_id=item["game_id"],forecast_at=packet["cutoff"],
                      event_start=item["event_start"],
                      line=item["research_line"],expected_defensive_plays=65.,
                      share_prior_mode="evidence_adaptive_v2")
            if p.get("status")!="research_forecast":
                continue
            baseline=score_probability(
                p["projection_components"]["team_play_rate_control_expected_tackles"],
                item["research_line"])
            predictions.append({
                "slate_date":packet["slate_date"],
                "game_id":item["game_id"],"team":item["team"],
                "player_id":item["player_id"],"stat":"tackles + assists",
                "line":item["research_line"],"prior_role":item["prior_role"],
                "forecast_at":packet["cutoff"],
                "p_over_challenger":p["q_over"],
                "p_over_control":baseline["q_over"],
                "prior_player_games":p["player_games"],
                "expected_tackles":p["projection_components"]["expected_tackles_assists"],
                "training_row_count":len(history["rows"]),
                "training_cutoff_verified":True})
    frozen={"schema":SCHEMA,"stage":"frozen_blind_forecasts",
            "prepared_manifest_sha256":manifest_sha,
            "n_predicted":len(predictions),"predictions":predictions,
            "source_market_lines_available":False,
            "target_outcomes_read":False,
            "production_eligible":False,"training_started":False}
    digest_value=write_once(forecast_file,frozen)
    receipt={"schema":SCHEMA,"stage":"locked_forecast_receipt",
             "forecast_sha256":digest_value,"forecast_count":len(predictions),
             "prepared_manifest_sha256":manifest_sha,
             "target_outcomes_read":False,"production_eligible":False}
    write_once(str(forecast_file)+".locked.sha256.json",receipt)
    return receipt


def settle(forecast_file,vault_file,output_file):
    """Only AFTER immutable forecast receipt exists can labels be opened."""
    receipt, _=read_receipt(str(forecast_file)+".locked.sha256.json")
    frozen,sha=read_receipt(forecast_file)
    if sha!=receipt["forecast_sha256"]:
        raise BlindReplayError("forecast_modified_after_lock_before_settlement")
    if frozen["stage"]!="frozen_blind_forecasts" or frozen["target_outcomes_read"]:
        raise BlindReplayError("forecast_was_not_originally_blind")
    vault,vhash=read_receipt(vault_file)
    if vault.get("stage")!="sealed_outcomes":
        raise BlindReplayError("outcome_vault_integrity")
    original_packets=Path(forecast_file).parent/"packets"/"MANIFEST.json"
    manifest,_=read_receipt(original_packets)
    if vault is None or vhash!=manifest["target_label_vault_sha256"]:
        raise BlindReplayError("outcome_vault_changed_after_pregame_packet_freeze")
    key=lambda x:(x["slate_date"],x["game_id"],x["team"],x["player_id"])
    labels={key(x):x for x in vault["labels"]}
    if len(labels)!=len(vault["labels"]):
        raise BlindReplayError("duplicate_settlement_player_game")
    scored=[];missing=0
    for p in frozen["predictions"]:
        label=labels.get(key(p))
        if label is None:
            missing+=1
            continue
        y=int(label["actual"]>p["line"])
        scored.append({"slate_date":p["slate_date"],"game_id":p["game_id"],
                       "team":p["team"],"player_id":p["player_id"],
                       "prior_role":p["prior_role"],"line":p["line"],
                       "y":y,"p_challenger":p["p_over_challenger"],
                       "p_control":p["p_over_control"]})
    if not scored:raise BlindReplayError("no_matching_official_results")
    def metrics(model):
        n=len(scored)
        p=[x[model] for x in scored]
        y=[x["y"] for x in scored]
        def ll(q,v):
            q=max(1e-12,min(1-1e-12,q))
            return -v*math.log(q)-(1-v)*math.log1p(-q)
        return {"n":n,"brier":sum((a-b)**2 for a,b in zip(p,y))/n,
                "log_loss":sum(ll(a,b) for a,b in zip(p,y))/n,
                "mean_p_over":sum(p)/n,"actual_over_share":sum(y)/n,
                "directional_accuracy":sum((a>=.5)==bool(b) for a,b in zip(p,y))/n}
    report={"schema":SCHEMA,"stage":"settled_blind_replay",
            "locked_prediction_sha256":sha,"outcomes_vault_sha256":vhash,
            "slate_days":len({x["slate_date"] for x in scored}),
            "games":len({x["game_id"] for x in scored}),
            "forecasted":len(frozen["predictions"]),"scored":len(scored),
            "unmatched_predicted_nonparticipants":missing,
            "challenger":metrics("p_challenger"),
            "control":metrics("p_control"),
            "real_bookmaker_line_validation":False,
            "market_and_60_40_production_comparator_available":False,
            "strict_no_target_results_passed_to_forecaster":True,
            "source_history_availability":"retrospective_start_plus_18h",
            "production_eligible":False,"training_started":False}
    write_once(output_file,report)
    return report


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("stage",choices=("prepare","forecast","settle"))
    ap.add_argument("--bundles",type=Path)
    ap.add_argument("--from-day")
    ap.add_argument("--through-day")
    ap.add_argument("--max-slates",type=int,default=25)
    ap.add_argument("--packet-dir",type=Path)
    ap.add_argument("--vault",type=Path)
    ap.add_argument("--forecast-file",type=Path)
    ap.add_argument("--report-file",type=Path)
    args=ap.parse_args(argv)
    if args.stage=="prepare":
        if not all((args.bundles,args.from_day,args.through_day,args.packet_dir,args.vault)):
            ap.error("prepare requires bundles, day window, packets and vault")
        result=prepare(json.loads(args.bundles.read_text()),from_day=args.from_day,
                       through_day=args.through_day,packet_dir=args.packet_dir,
                       vault_file=args.vault,max_slates=args.max_slates)
    elif args.stage=="forecast":
        if not args.packet_dir or not args.forecast_file:
            ap.error("forecast requires only sanitized packet dir and forecast destination")
        result=forecast(args.packet_dir,args.forecast_file)
    else:
        if not all((args.forecast_file,args.vault,args.report_file)):
            ap.error("settle requires previously locked forecast, vault and report")
        result=settle(args.forecast_file,args.vault,args.report_file)
    print(json.dumps(result,sort_keys=True,allow_nan=False))


if __name__=="__main__":
    main()
