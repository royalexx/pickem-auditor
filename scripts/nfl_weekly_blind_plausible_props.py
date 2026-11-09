"""NFL Experiment B: result-sealed all-market weekly adaptive ML replay.

2021-23 source history -> predict ALL 16 registered markets on 2024 Week 1
-> lock ALL predictions -> decrypt/reveal Week 1 -> update ML sufficient
statistics -> repeat weekly. NO target-week outcome is passed to the
forecast subprocess. Previous-week updates are permitted only after the
complete prior-week lock and settlement receipt exist.

Raw arithmetic-response challenger for retransformation bias testing.
Strict pregame player-market research eligibility; excludes all WR rushing props.
Research-only: no original bookmaker lines, no pre-2024 untouched design
claim, no original NUTS/60-40 substitution, no live betting or ranking.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter, defaultdict
from datetime import date,datetime,timezone,timedelta
import hashlib
import json
import math
from statistics import median
import os
from pathlib import Path
import subprocess
import sys

from population_history import COUNT,CONTINUOUS,market_eligible
from nfl_research_hybrid_lines import hybrid_research_line
from nfl_research_prop_eligibility import position_market_eligible, eligible_pregame_research_candidate

SCHEMA="pickem-nfl-weekly-plausible-props-raw-mean-v3"
MARKETS=(
 "tackles + assists","targets","pass attempts","completions",
 "passing yards","passing touchdowns","receptions","receiving yards",
 "receiving touchdowns","carries","rushing yards","rushing touchdowns",
 "solo tackles","tackle assists","qb hits","passes defended",
)
if set(MARKETS)!=(set(COUNT["NFL"])|set(CONTINUOUS["NFL"])):
    raise RuntimeError("unsupported_or_missing_nfl_market_registry")
DEFENSE=frozenset(("tackles + assists","solo tackles","tackle assists",
                   "qb hits","passes defended"))
DEF_POS=frozenset(("LB","MLB","OLB","ILB","DE","DT","NT","CB","DB","S","FS","SS"))
OFF_POS=frozenset(("QB","RB","WR","TE"))
NUM_FEATURES=9
REG_ALPHA=25.0
NB_DISPERSION=8.0
MIN_TRAIN=80
MIN_ROLE_LINE=15
RANDOMNESS="no_randomized_model_selection"
# Source-informed scale priors declared before scoring, not fit on 2024.
DEFAULT_PRIOR={
 "tackles + assists":3.5,"solo tackles":2.5,"tackle assists":.7,
 "qb hits":.4,"passes defended":.5,"targets":4.0,
 "receptions":2.8,"receiving yards":30.,"receiving touchdowns":.25,
 "pass attempts":30.,"completions":19.,"passing yards":215.,
 "passing touchdowns":1.3,"carries":9.,"rushing yards":38.,
 "rushing touchdowns":.25,
}


class WeeklyReplayError(ValueError):pass


def canonical(data):
    return (json.dumps(data,sort_keys=True,separators=(",",":"),
                       allow_nan=False,ensure_ascii=True)+"\n").encode()


def hash_bytes(blob):
    return hashlib.sha256(blob).hexdigest()


def write_new(path,body):
    p=Path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    data=canonical(body)
    if p.exists():
        if p.read_bytes()!=data:
            raise WeeklyReplayError("immutable_artifact_conflict:"+str(p))
    else:p.write_bytes(data)
    return hash_bytes(data)


def eligible(market,pos):
    return position_market_eligible(market,pos)


def group_games(seasons):
    """Input: already-normalized source rows and schedule from the preparer.

    Only the main orchestrator receives full 2024 labels. The child
    forecaster receives neither this function's source nor the vault key.
    """
    records={}
    fixtures={}
    for year,source in seasons.items():
        if int(year)<2021 or int(year)>2025:
            raise WeeklyReplayError("season_outside_declared_experiment")
        schedule=source["schedule"]
        game_map={}
        for s in schedule:
            if s.get("game_type")!="REG" or s.get("season")!=int(year):
                continue
            week=int(s["week"])
            game=str(s["game_id"])
            if game in game_map:raise WeeklyReplayError("repeated_schedule_game")
            game_map[game]=(week,str(s["gameday"]))
            fixtures.setdefault((int(year),week),[]).append({
                "game_id":game,"gameday":str(s["gameday"]),
                "away_team":str(s["away_team"]),"home_team":str(s["home_team"]),
                "week":week,"season":int(year)})
        group=defaultdict(list)
        for row in source["rows"]:
            gid=row["game_id"]
            if gid not in game_map:
                raise WeeklyReplayError("unmapped_weekly_result_game")
            week,day=game_map[gid]
            if row["game_date"]!=day:
                raise WeeklyReplayError("weekly_result_date_mismatch")
            if row["stat"] not in MARKETS:
                raise WeeklyReplayError("unknown_nfl_market")
            # A legitimate historical observation can exist without being a
            # plausible, routinely offered research prop. Exclude unsupported
            # position/market pairs from both fitting and candidate generation.
            if not eligible(row["stat"],row["position"]):
                continue
            group[week].append({
                "game_id":gid,"gameday":day,"season":int(year),"week":week,
                "team":row["team"],"opponent":row["opponent"],
                "position":row["position"],"player_id":row["player_id"],
                "stat":row["stat"],"value":float(row["value"]),
                "historical_snap_exposure":float(row["workload"])})
        for week,rows in group.items():
            identities=[(r["game_id"],r["stat"],r["player_id"]) for r in rows]
            if len(identities)!=len(set(identities)):
                raise WeeklyReplayError("duplicate_player_market_week")
            records[(int(year),week)]=rows
    return records,fixtures


def mean(values,default):
    return sum(values)/len(values) if values else default


def features(state,*,market,player_id,team,position,game_day,home):
    role=state["role"].get((market,position),[])
    global_values=state["global"].get(market,[])
    prior=DEFAULT_PRIOR[market]
    role_avg=(sum(role)+12*prior)/(len(role)+12) if role else prior
    if not role and global_values:
        role_avg=(sum(global_values)+40*prior)/(len(global_values)+40)
    previous=state["player"].get((market,player_id),[])
    values=[x["value"] for x in previous]
    n=len(values)
    recent3=mean(values[-3:],role_avg)
    recent8=mean(values[-8:],role_avg)
    baseline=(sum(values[-8:])+5*role_avg)/(min(n,8)+5)
    snaps=[x["snaps"] for x in previous[-4:]]
    latest=previous[-1]["gameday"] if previous else None
    gap=(date.fromisoformat(game_day)-date.fromisoformat(latest)).days if latest else 300
    if gap<0:raise WeeklyReplayError("future_game_used_in_player_features")
    x=[1.,math.log1p(max(0.,baseline)),math.log1p(max(0.,role_avg)),
       math.log1p(max(0.,recent3)),math.log1p(max(0.,recent8)),
       math.log1p(max(0.,mean(snaps,45.))),
       min(n,15)/15.,min(gap,300)/300.,float(bool(home))]
    if len(x)!=NUM_FEATURES or any(not math.isfinite(v) for v in x):
        raise WeeklyReplayError("invalid_pregame_feature")
    if any(date.fromisoformat(e["gameday"])>=date.fromisoformat(game_day)
           for e in previous):
        raise WeeklyReplayError("target_or_future_player_result_in_features")
    return x,max(0.,baseline),role_avg


def make_state():
    return {"role":defaultdict(list),"global":defaultdict(list),
            "player":defaultdict(list),"latest":{},
            "xtx":{m:[[0.]*NUM_FEATURES for _ in range(NUM_FEATURES)]
                   for m in MARKETS},
            "xty":{m:[0.]*NUM_FEATURES for m in MARKETS},
            "trained_n":{m:0 for m in MARKETS},
            "sum_resid2":{m:0. for m in MARKETS}}


def update_week(state,rows,fixtures):
    """Reveal all historical results together only AFTER a complete lock."""
    fixture_by_game={f["game_id"]:f for f in fixtures}
    new=[]
    for row in rows:
        fix=fixture_by_game.get(row["game_id"])
        if fix is None:raise WeeklyReplayError("settled_result_not_in_current_week")
        home=row["team"]==fix["home_team"]
        x,baseline,_=features(state,market=row["stat"],player_id=row["player_id"],
            team=row["team"],position=row["position"],game_day=row["gameday"],home=home)
        new.append((row,x,baseline))
    # Don't make any current-week result visible until all feature rows
    # for the SAME week have been computed from previously revealed weeks.
    for row,x,baseline in new:
        m=row["stat"]
        y=float(row["value"])
        if m in COUNT["NFL"] and (y<0 or not y.is_integer()):
            raise WeeklyReplayError("invalid_count_training_result")
        # Signed yardage is valid: do not silently transform negative yards
        # into zero and bias the arithmetic-mean regression upward.
        transformed=y
        for i in range(NUM_FEATURES):
            state["xty"][m][i]+=x[i]*transformed
            for j in range(NUM_FEATURES):
                state["xtx"][m][i][j]+=x[i]*x[j]
        state["trained_n"][m]+=1
        state["sum_resid2"][m]+=(row["value"]-baseline)**2
    for row,x,baseline in new:
        m=row["stat"]
        key=(m,row["player_id"])
        state["player"][key].append({"gameday":row["gameday"],
            "value":row["value"],"snaps":row["historical_snap_exposure"],
            "team":row["team"],"position":row["position"]})
        state["role"][(m,row["position"])].append(row["value"])
        state["global"][m].append(row["value"])
        old=state["latest"].get(row["player_id"])
        if old and date.fromisoformat(old["gameday"])>date.fromisoformat(row["gameday"]):
            raise WeeklyReplayError("nonchronological_player_team_update")
        state["latest"][row["player_id"]]={"gameday":row["gameday"],
            "team":row["team"],"position":row["position"]}
    return {m:sum(row["stat"]==m for row in rows) for m in MARKETS}


def prepare_packet(state,fixtures,week,season=2024):
    """Only previously settled state enters this packet."""
    if not fixtures:raise WeeklyReplayError("missing_week_schedule")
    first=min(date.fromisoformat(f["gameday"]) for f in fixtures)
    teams={team:(f,team==f["home_team"])
           for f in fixtures for team in (f["home_team"],f["away_team"])}
    cutoff=first.isoformat()+"T00:00:00Z"  # conservative day-start cutoff
    candidates={m:[] for m in MARKETS}
    max_age=300 if week==1 else 50
    for player_id,latest in sorted(state["latest"].items()):
        seen=date.fromisoformat(latest["gameday"])
        age=(first-seen).days
        if age<0:raise WeeklyReplayError("future_roster_entry_in_packet")
        if age>max_age or latest["team"] not in teams:continue
        fixture,home=teams[latest["team"]]
        for market in MARKETS:
            permitted,reason=eligible_pregame_research_candidate(
                state,market=market,player_id=player_id,
                position=latest["position"],game_day=first.isoformat())
            if not permitted:continue
            x,baseline,prior=features(state,market=market,player_id=player_id,
                team=latest["team"],position=latest["position"],
                game_day=first.isoformat(),home=home)
            line,line_evidence=hybrid_research_line(
                state,market=market,player_id=player_id,
                position=latest["position"],game_day=first.isoformat())
            method=line_evidence["method"]
            candidates[market].append({
                "player_id":player_id,"team":latest["team"],
                "game_id":fixture["game_id"],"week":week,
                "position":latest["position"],"stat":market,
                "line":line,"line_source":method,"line_evidence":line_evidence,
                "market_eligibility_policy":"position_and_past_usage_only_not_bookmaker",
                "features":x,
                "baseline_mean":baseline,"prior_position_mean":prior})
    market_packets={}
    for m in MARKETS:
        market_packets[m]={
            "trained_n":state["trained_n"][m],
            "xtx":state["xtx"][m],
            "xty":state["xty"][m],
            "historical_residual_sigma":max(7.0,math.sqrt(
                state["sum_resid2"][m]/max(1,state["trained_n"][m]))),
            "candidates":candidates[m]}
    return {"schema":SCHEMA,"stage":"pregame","year":season,"week":week,
            "cutoff":cutoff,
            "markets":list(MARKETS),
            "source_roster":"last_observed_player_team_and_position_prior_weeks_only",
             "market_offer_verified":False,
             "pregame_roster_verified":False,
             "candidate_eligibility_policy":"past_only_structural_and_usage_v1",
            "expected_markets":len(MARKETS),
            "fixtures":[{k:f[k] for k in ("game_id","gameday","home_team",
                           "away_team","week","season")} for f in fixtures],
            "market_packets":market_packets,
            "target_week_results_in_packet":False,
            "policy":"train_all_markets_before_unlocking_any_week_outcome",
            "training_started":False,
            "production_eligible":False}


def probability_over(mean_value,line,market,sigma):
    from scipy.stats import nbinom,norm
    if line is None:return None
    if market in CONTINUOUS["NFL"]:
        return float(norm.sf(line,loc=mean_value,scale=max(7.,sigma)))
    mu=max(1e-8,mean_value)
    return float(nbinom.sf(math.floor(line),NB_DISPERSION,
                           NB_DISPERSION/(NB_DISPERSION+mu)))


def forecast(packet_path,out_path):
    """Forecaster subprocess: no outcome file, key, PBP or nflreadpy."""
    import numpy as np
    packet=json.loads(Path(packet_path).read_bytes())
    if (packet["schema"]!=SCHEMA or packet["stage"]!="pregame"
            or packet["target_week_results_in_packet"] is not False
            or packet["markets"]!=list(MARKETS)):
        raise WeeklyReplayError("invalid_or_incomplete_week_packet")
    if set(packet["market_packets"])!=set(MARKETS):
        raise WeeklyReplayError("not_all_markets_in_packet")
    expected_games={x["game_id"] for x in packet["fixtures"]}
    cutoff=date.fromisoformat(packet["cutoff"][:10])
    if any(date.fromisoformat(x["gameday"])<cutoff
           for x in packet["fixtures"]):
        raise WeeklyReplayError("fixture_before_pregame_cutoff")
    results={}
    for market in MARKETs_ORDER():
        m=packet["market_packets"][market]
        if m["trained_n"]>=MIN_TRAIN:
            matrix=np.asarray(m["xtx"],dtype=float)
            vector=np.asarray(m["xty"],dtype=float)
            penalty=np.eye(NUM_FEATURES)*REG_ALPHA
            penalty[0,0]=0.
            weights=np.linalg.solve(matrix+penalty,vector)
            if not np.all(np.isfinite(weights)):
                raise WeeklyReplayError("nonfinite_trained_regression")
            weight_hash=hash_bytes(weights.tobytes())
            status="trained_machine_learning_ridge_raw_arithmetic_mean"
        else:
            weights=None
            weight_hash=None
            status="abstain_insufficient_prior_training"
        predicted=[];abstained=Counter()
        for item in m["candidates"]:
            if item["game_id"] not in expected_games:
                raise WeeklyReplayError("candidate_not_on_frozen_week_schedule")
            if item["line"] is None:
                abstained["missing_pregame_line_support"]+=1;continue
            if weights is None:
                abstained["missing_prior_training"]+=1;continue
            x=np.asarray(item["features"],dtype=float)
            fitted=max(0.,float(x@weights))  # predict expected STAT directly
            # Declared global ridge shrinkage toward the player-specific
            # historical-rate baseline; no holdout-driven selection.
            mean_val=.7*fitted+.3*item["baseline_mean"]
            # Extremely large outputs mean the research learner is unfit,
            # not an 80% prop that should be ranked.
            if not math.isfinite(mean_val) or mean_val>1000:
                abstained["unreliable_mean"]+=1;continue
            p=probability_over(mean_val,item["line"],market,
                               m["historical_residual_sigma"])
            b=probability_over(item["baseline_mean"],item["line"],market,
                               m["historical_residual_sigma"])
            if p is None or b is None or not (0<=p<=1 and 0<=b<=1):
                raise WeeklyReplayError("nonfinite_binary_model_probability")
            predicted.append({
                "year":packet["year"],"week":packet["week"],
                "game_id":item["game_id"],"player_id":item["player_id"],
                "team":item["team"],"position":item["position"],
                "market":market,"research_line":item["line"],
                "research_line_source":item["line_source"],
                "p_over_model":p,"p_over_baseline":b,
                "mean_model":mean_val,
                "mean_baseline":item["baseline_mean"]})
        results[market]={"status":status,
                         "trained_prior_examples":m["trained_n"],
                         "model_coefficients_sha256":weight_hash,
                         "pregame_candidates":len(m["candidates"]),
                         "abstentions":dict(abstained),
                         "predictions":predicted}
    if list(results)!=list(MARKETS):
        raise WeeklyReplayError("some_markets_failed_before_week_lock")
    output={"schema":SCHEMA,"stage":"all_markets_frozen",
            "year":packet["year"],"week":packet["week"],
            "packet_sha256":hash_bytes(Path(packet_path).read_bytes()),
            "markets_order":list(MARKETS),
            "market_results":results,
            "results_exposed_to_forecaster":False,
            "production_eligible":False}
    sha=write_new(out_path,output)
    return {"sha256":sha,"markets":len(results),
            "predictions":sum(len(v["predictions"]) for v in results.values())}


def MARKETs_ORDER():
    return MARKETS


def settlement(frozen_file,packet_file,encrypted_blob,key,weekly_rows):
    from cryptography.fernet import Fernet
    saved=Path(frozen_file).read_bytes()
    frozen=json.loads(saved)
    packet=json.loads(Path(packet_file).read_bytes())
    if frozen["stage"]!="all_markets_frozen" or not all(
        market in frozen["market_results"] for market in MARKETS):
        raise WeeklyReplayError("unfrozen_or_incomplete_markets")
    if frozen["packet_sha256"]!=hash_bytes(Path(packet_file).read_bytes()):
        raise WeeklyReplayError("changed_original_pregame_packet")
    # Decryption occurs only after all 16 market forecasts are locked.
    plaintext=Fernet(key).decrypt(encrypted_blob)
    vault=json.loads(plaintext)
    if (vault["year"],vault["week"])!=(frozen["year"],frozen["week"]):
        raise WeeklyReplayError("outcome_vault_week_mismatch")
    label={tuple((x["game_id"],x["player_id"],x["stat"])):x["value"]
           for x in vault["observed"]}
    if len(label)!=len(vault["observed"]):
        raise WeeklyReplayError("duplicate_locked_week_outcome")
    if len(label)!=len(weekly_rows):
        raise WeeklyReplayError("outcome_vault_incomplete_or_different")
    by_market={}
    for m in MARKETS:
        market=frozen["market_results"][m]
        preds=market["predictions"]
        scored=[];missing=0
        for pred in preds:
            hit=label.get((pred["game_id"],pred["player_id"],m))
            if hit is None:
                missing+=1
                continue
            yy=int(hit>pred["research_line"])
            scored.append((yy,pred["p_over_model"],pred["p_over_baseline"]))
        def values(index):
            n=len(scored)
            if not n:return {"n":0}
            ps=[row[index] for row in scored];ys=[row[0] for row in scored]
            def ll(p,y):
                p=max(1e-12,min(1-1e-12,p))
                return -y*math.log(p)-(1-y)*math.log1p(-p)
            return {"n":n,"brier":sum((p-y)**2 for p,y in zip(ps,ys))/n,
                    "log_loss":sum(ll(p,y) for p,y in zip(ps,ys))/n,
                    "directional_accuracy":sum((p>=.5)==bool(y)
                                              for p,y in zip(ps,ys))/n,
                    "mean_claimed_over":sum(ps)/n,
                    "actual_over_share":sum(ys)/n}
        by_market[m]={
            "status":market["status"],
            "pregame_candidates":market["pregame_candidates"],
            "forecasted":len(preds),"scored_participants":len(scored),
            "unmatched_nonparticipating_or_unverified":missing,
            "model":values(1),"historical_baseline":values(2)}
    return {"schema":SCHEMA,"stage":"complete_week_settled",
            "year":packet["year"],"week":packet["week"],
            "forecast_sha256":hash_bytes(saved),
            "encrypted_vault_sha256":hash_bytes(encrypted_blob),
            "all_markets_frozen_before_any_result":True,
            "markets_scored":len(by_market),
            "by_market":by_market,
            "total_forecasts":sum(x["forecasted"] for x in by_market.values()),
            "total_scored":sum(x["scored_participants"] for x in by_market.values()),
            "trained_only_after_whole_week_revealed":True,
            "market_lines":"player_last5_last10_role_hybrid_synthetic_not_bookmaker",
            "production_eligible":False}


def replay(source,root,*,min_year=2021,eval_year=2024,
           stop_after_week=None):
    from cryptography.fernet import Fernet
    all_rows,fixtures=group_games(source)
    root=Path(root)
    state=make_state()
    for yr in range(min_year,eval_year):
        for (_,week) in sorted(x for x in fixtures if x[0]==yr):
            rows=all_rows.get((yr,week),[])
            if not rows:continue
            update_week(state,rows,fixtures[(yr,week)])
        print("HISTORICAL_TRAINING_INGESTED",yr,
              {m:state["trained_n"][m] for m in MARKETS},flush=True)
    required=sorted(week for yr,week in fixtures if yr==eval_year)
    if not required or required!=list(range(1,max(required)+1)):
        raise WeeklyReplayError("incomplete_sequential_2024_week_schedule")
    previous_sha=None
    receipts=[]
    for week in required:
        if stop_after_week is not None and week>stop_after_week:break
        fixtures_this=fixtures[(eval_year,week)]
        rows=all_rows.get((eval_year,week),[])
        packet=prepare_packet(state,fixtures_this,week,eval_year)
        packet["previous_week_settlement_sha256"]=previous_sha
        weekdir=root/f"{eval_year}_week_{week:02d}"
        packetfile=weekdir/"pregame_packet.json"
        predictionfile=weekdir/"frozen_all_markets.json"
        sealedfile=weekdir/"encrypted_outcomes.bin"
        lockfile=weekdir/"lock.json"
        settlefile=weekdir/"settlement.json"
        # Encrypt all week results *before* the forecast worker launches.
        # Key remains only in the orchestration parent's RAM until after lock.
        encrypted_plain={"year":eval_year,"week":week,
            "observed":[{k:x[k] for k in ("game_id","player_id","stat","value")}
                        for x in rows]}
        key=Fernet.generate_key()
        cipher=Fernet(key).encrypt(canonical(encrypted_plain))
        weekdir.mkdir(parents=True,exist_ok=True)
        if sealedfile.exists() or predictionfile.exists():
            raise WeeklyReplayError("must_not_overwrite_existing_week_run")
        sealedfile.write_bytes(cipher)
        psha=write_new(packetfile,packet)
        # Forecaster is a fresh process and receives only packet and
        # destination. It does NOT receive source data, encrypted key,
        # target results, outcome path or model-selection feedback.
        args=[sys.executable,str(Path(__file__).resolve()),
              "forecast","--packet",str(packetfile),"--output",str(predictionfile)]
        run=subprocess.run(args,capture_output=True,text=True,
                           timeout=600,check=False,
                           env={k:v for k,v in os.environ.items()
                                if k not in ("FERNET_KEY","CURRENT_OUTCOMES")})
        if run.returncode:
            raise WeeklyReplayError("weekly_forecast_failed_before_unlock:"+
                                    str(week)+":"+run.stderr[-600:])
        fsha=hash_bytes(predictionfile.read_bytes())
        frozen=json.loads(predictionfile.read_bytes())
        if len(frozen["market_results"])!=len(MARKETS):
            raise WeeklyReplayError("incomplete_week_market_lock")
        receipt={"schema":SCHEMA,"stage":"complete_week_market_lock",
            "year":eval_year,"week":week,"packet_sha256":psha,
            "forecast_sha256":fsha,"encrypted_vault_sha256":hash_bytes(cipher),
            "market_count":len(MARKETS),"results_revealed":False,
            "previous_week_settlement_sha256":previous_sha}
        write_new(lockfile,receipt)
        # The entire weekly slate is settled only after lock written.
        checked=json.loads(lockfile.read_bytes())
        if checked["forecast_sha256"]!=hash_bytes(predictionfile.read_bytes()):
            raise WeeklyReplayError("attempted_unlock_without_intact_week_lock")
        settle=settlement(predictionfile,packetfile,cipher,key,rows)
        settle["lock_sha256"]=hash_bytes(lockfile.read_bytes())
        settle["observed_week_rows"]=len(rows)
        settle["prior_train_examples_by_market"]={
            m:packet["market_packets"][m]["trained_n"] for m in MARKETS}
        settle["next_week_model_update"]={
            m:sum(x["stat"]==m for x in rows) for m in MARKETS}
        settle_sha=write_new(settlefile,settle)
        if settle["markets_scored"]!=len(MARKETS):
            raise WeeklyReplayError("would_update_after_partial_week")
        update_week(state,rows,fixtures_this)
        previous_sha=settle_sha
        receipts.append({"week":week,"forecast_sha256":fsha,
              "settlement_sha256":settle_sha,
              "markets":settle["markets_scored"],
              "predictions":settle["total_forecasts"],
              "graded":settle["total_scored"]})
        print("BLIND_WEEK_FINISHED",json.dumps(receipts[-1],sort_keys=True),
              flush=True)
    if not receipts:raise WeeklyReplayError("no_week_completed")
    end={"schema":SCHEMA,"stage":"completed_or_checkpointed",
         "year":eval_year,"weeks":receipts,
         "market_registry":list(MARKETS),
         "final_model_training_count_by_market":state["trained_n"],
         "initial_training_period":f"{min_year}_to_{eval_year-1}_only",
         "each_week_all_16_before_reveal":True,
         "unobserved_candidates_are_not_auto_losses":True,
         "original_bookmaker_lines_available":False,
         "hybrid_line_policy":"prior_history_only_last5_last10_role_v1",
          "market_eligibility":"structural_position_and_preweek_usage_not_market_verified",
         "retrospective_sources_not_immutable_pregame_provider_capture":True,
         "no_original_bayesian_nuts_retraining":True,
         "production_eligible":False}
    write_new(root/"REPLAY_MANIFEST.json",end)
    return end


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("stage",choices=("forecast","replay"))
    p.add_argument("--packet",type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--source-json",type=Path)
    p.add_argument("--root",type=Path)
    p.add_argument("--stop-after-week",type=int)
    a=p.parse_args(argv)
    if a.stage=="forecast":
        if not a.packet or not a.output or a.source_json or a.root:
            p.error("forecaster accepts only sanitized packet and output path")
        print(json.dumps(forecast(a.packet,a.output),sort_keys=True))
    else:
        if not a.source_json or not a.root:
            p.error("replay orchestration needs source and output")
        src=json.loads(a.source_json.read_text())
        print(json.dumps(replay(src,a.root,stop_after_week=a.stop_after_week),
                         sort_keys=True))


if __name__=="__main__":
    main()
