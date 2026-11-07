#!/usr/bin/env python3
"""Prospective NFL targets forecasts and settlement audit from the verified model.

Independent joint forecasts: no second Engine B/context adjustment, blend rewrite
or tier promotion. Fresh collector context is required; no market API requests.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

import nhl_context_data as common
import nhl_context_train as io
from nfl_context_data import ContextHistory,kickoff,NAMES
from nfl_read_features import ReadHistory,FEATURE_NAMES
import nfl_context_live as live
import nfl_context_release as release
import nfl_context_model as model

ROOT=Path(__file__).resolve().parents[1]
TZ=ZoneInfo("America/Toronto")
VERSION="nfl-targets-context-daily-v1"
IDENTITY=("game_date","sport","player_id","stat","side","reference_line","forecast_at","run_id")


def read_rows(path):
    path=Path(path)
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()] if path.is_file() else []


def source_key(row):return common.digest({k:row.get(k) for k in IDENTITY})


class Adapter:
    def __init__(self,meta,cache,payload,source_hash,now):
        self.meta=meta;self.cache=cache;self.payload=payload;self.source_hash=source_hash;self.now=now
        if payload["season"]!=io.load_json(release.PIN_PATH)["supported_season"]:
            raise ValueError("nfl_release_season_requires_review")
        self.core=ContextHistory([meta["history_seed"],payload["bundle"]],"targets")
        self.reads=ReadHistory([payload["bundle"]],lag_days=7)

    def features(self,row):
        now=self.now;at=common.instant(row["forecast_at"])
        if row.get("line_origin")=="research_threshold" and not row.get("event_start"):
            games=[g for g in self.payload["schedule"] if g["gameday"]==row["game_date"] and
                   {g["home_team"],g["away_team"]}=={row.get("team"),row.get("opponent")}]
            if len(games)!=1:raise ValueError("nfl_projection_schedule_not_unique")
            start=kickoff(games[0])
        else:start=common.instant(row["event_start"])
        if not at<=now<start or at>=start:raise ValueError("nfl_poststart_or_future_snapshot")
        if start.astimezone(TZ).date().isoformat()!=row["game_date"]:
            raise ValueError("nfl_snapshot_calendar_mismatch")
        quote=common.instant(row.get("retrieved_at") or (row.get("market") or {}).get("retrieved_at") or "")
        if not 0<=(now-quote).total_seconds()<=3600:raise ValueError("nfl_reference_source_stale_or_future")
        if row.get("side") not in ("over","under","higher","lower"):raise ValueError("invalid_nfl_side")
        pid=str(row.get("player_id") or "");d=self.meta["design"]
        if pid not in d["players"]:raise ValueError("nfl_unseen_player_requires_population_review")
        person=self.payload["catalog"].get(pid)
        if not person or person["team"]!=row.get("team") or person["position"]!=d["player_position"][pid]:
            raise ValueError("nfl_current_source_identity_or_role_mismatch")
        matches=[g for g in self.payload["schedule"] if
            {g["home_team"],g["away_team"]}=={row.get("team"),row.get("opponent")} and kickoff(g)==start]
        if len(matches)!=1:raise ValueError("nfl_schedule_identity_or_start_mismatch")
        game=matches[0]
        p={"game_id":str(game["game_id"]),"player_id":pid,"team":row["team"],"opponent":row["opponent"],
           "position":person["position"],"season":str(game["season"]),"home":row["team"]==game["home_team"],
           "start_time":start.isoformat(),"stat":"targets"}
        p.update(self.core.features(p,as_of=now.isoformat()))
        values,meta=self.reads.features(p,as_of=now.isoformat())
        p["x"]+=values;p["feature_names"]=NAMES+FEATURE_NAMES;p["read_context"]=meta
        if p["feature_names"]!=d["feature_names"]:raise ValueError("nfl_live_feature_contract_changed")
        return p

    def evaluate(self,row):
        p=self.features(row)
        forecast=model.forecast(self.cache,self.meta["design"],p,line=row["reference_line"],
                                 draws=4000,diagnostic=self.meta["diagnostics"])
        win=forecast["q_over"] if row["side"] in ("over","higher") else forecast["q_under"]
        return {"status":"forecast",**forecast,"q_win":win,"read_context":p["read_context"],
                "event_start":p["start_time"],"line_origin":row.get("line_origin","market"),
                "forecast_kind":"target_opportunity_projection" if row.get("line_origin")=="research_threshold" else "target_market_forecast",
                "feature_vector":p["x"],"feature_names":p["feature_names"],"feature_as_of":self.now.isoformat(),
                "source_retrieved_at":self.payload["retrieved_at"],"source_sha256":self.source_hash,
                "venue_verified_from":"nflverse_schedule","conditional_on_appearance":True,
                "availability_verified":False,"passer_method":p["read_context"]["passer_method"],
                "context_application":"joint_model_only_no_extra_B_or_read_multiplier"}


def run(*,snapshots,data_root,model_dir,out,receipt,game_date,now=None,download=False,clock=None):
    clock=clock or ((lambda: now) if now is not None else (lambda: datetime.now(timezone.utc)))
    now=now or clock()
    if now.tzinfo is None:raise ValueError("timezone_required")
    source=read_rows(snapshots)
    candidates=[r for r in source if r.get("game_date")==game_date and r.get("sport")=="NFL" and
                r.get("stat")=="targets" and r.get("run_type")=="shadow"]
    # Real posted targets markets take precedence over synthetic projections.
    # Source target lines may come from a separately approved verified provider;
    # never reinterpret reception or yardage pricing as target pricing.
    def current_market_target(r):
        try:
            when=common.instant(r.get("retrieved_at") or
                                (r.get("market") or {}).get("retrieved_at") or "")
            start=common.instant(r.get("event_start") or "")
            frozen=common.instant(r.get("forecast_at") or "")
            return (bool(r.get("player_id")) and
                    0 <= (now-when).total_seconds() <= 3600 and
                    frozen <= now < start)
        except (KeyError,ValueError,TypeError,OverflowError):
            return False
    real_targets={(r.get("player_id"),r.get("team"),r.get("opponent"))
                  for r in candidates if current_market_target(r)}
    projections=set()
    for r in read_rows(Path(data_root)/"slate_fetch.jsonl"):
        key=(r.get("player_id"),r.get("team"),r.get("opponent"))
        if (r.get("game_date")!=game_date or r.get("sport")!="NFL" or
            r.get("stat") not in ("receptions","receiving yards") or
            not all(key) or key in real_targets or key in projections):continue
        projections.add(key)
        candidates.append({**{k:r.get(k) for k in ("game_date","sport","player","player_id","team","opponent","retrieved_at")},
            "source_stat":r["stat"],"stat":"targets","side":"over","line_origin":"research_threshold",
            "reference_line":io.load_json(release.PIN_PATH)["research_line"],"forecast_at":r.get("retrieved_at"),
            "run_type":"shadow","run_id":"targets-projection:"+common.digest([key,r.get("retrieved_at")])[:20]})
    old=read_rows(out);recorded={r["source_key"] for r in old if r.get("status")=="forecast"}
    failed={(r.get("source_key"),r.get("reason")) for r in old if r.get("status")=="unavailable"}
    pending=[r for r in candidates if source_key(r) not in recorded]
    added=[];adapter=None;error=None
    if pending:
        try:
            meta,cache=release.load(model_dir,download=download)
            season=io.load_json(release.PIN_PATH)["supported_season"]
            payload,sha=live.load(Path(data_root)/"season"/f"nfl_context_{season}.json.gz",now)
            adapter=Adapter(meta,cache,payload,sha,now)
        except (OSError,ValueError,KeyError,TypeError,subprocess.CalledProcessError) as exc:
            error=type(exc).__name__+":"+str(exc)[:160]
    for row in pending:
        if source_key(row) in recorded:continue
        base={k:row.get(k) for k in ("game_date","sport","player","player_id","stat","source_stat","side","reference_line","run_id","team","opponent","event_start")}
        base.update(version=VERSION,source_key=source_key(row),parent_forecast_at=row.get("forecast_at"),
            forecast_at=now.isoformat(),release_tag=io.load_json(release.PIN_PATH)["tag"],
            line_origin=row.get("line_origin","market"),
            publication_eligible=False,ranking_allowed=False,calibrated=False,shadow_only=True)
        try:
            if error:raise ValueError(error)
            prediction=adapter.evaluate(row)
            completed=clock()
            base.update(generated_at=completed.isoformat(),generation_semantics="inference_completed")
            if not common.instant(row["forecast_at"])<=completed<common.instant(prediction["event_start"]):
                raise ValueError("model_not_completed_before_event")
            base.update(prediction)
            # Keep the snapshot's quote identity separate from the nflverse game ID.
            base["source_key"]=source_key(row)
        except (ValueError,KeyError,TypeError,OverflowError) as exc:
            reason=str(exc)[:200];base.update(status="unavailable",reason=reason)
            if (base["source_key"],reason) in failed:continue
            failed.add((base["source_key"],reason))
        added.append(base)
        if base["status"]=="forecast":recorded.add(base["source_key"])
    path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("a",encoding="utf-8") as h:
        for r in added:h.write(common.encode(r)+"\n")
    report={"schema":"nfl-context-daily-receipt-v1","date":game_date,"candidates":len(candidates),
        "previously_forecast":len(candidates)-len(pending),"new_rows":len(added),
        "available_forecasts":len(recorded),
        "forecast_count":sum(r["status"]=="forecast" for r in added),
        "market_target_forecasts":sum(r["status"]=="forecast" and r.get("line_origin")=="market"
                                      for r in added),
        "research_threshold_forecasts":sum(r["status"]=="forecast" and r.get("line_origin")=="research_threshold"
                                            for r in added),
        "unavailable_count":sum(r["status"]=="unavailable" for r in added),
        "reasons":dict(Counter(r["reason"] for r in added if r["status"]=="unavailable")),
        "status":"source_or_release_unavailable" if error else "completed","global_error":error,
        "ranking_allowed":False,"automatic_promotion":False}
    io.write_json(receipt,report);return report


def audit(*,snapshots,directory,out,now=None,refresh_actuals=False):
    settled={source_key(r):r for r in read_rows(snapshots) if r.get("outcome") in ("win","loss","push")}
    predictions={}
    for path in sorted(Path(directory).glob("*.jsonl")):
        for r in read_rows(path):
            if r.get("version")==VERSION and r.get("status")=="forecast":predictions.setdefault(r["source_key"],r)
    now=now or datetime.now(timezone.utc);actuals={}
    for path in (Path(directory).parent/"season").glob("nfl_context_*.json.gz"):
        payload,_=live.load(path,now,max_age=None)
        actuals.update({(r["game_id"],r["player_id"]):r for r in payload["bundle"]["players"]
                        if common.instant(r["available_at"])<now})
    actual_path=Path(directory).parent/'season/nfl_targets_actuals_2026.json.gz'
    if refresh_actuals and any(common.instant(p['event_start'])<now for p in predictions.values()):
        live.refresh_actuals(actual_path,2026,now)
    if actual_path.is_file():
        import gzip
        if io.file_hash(actual_path)!=io.load_json(actual_path.with_suffix('.receipt.json'))['sha256']:
            raise ValueError('nfl_actual_targets_hash_changed')
        with gzip.open(actual_path,'rt',encoding='utf-8') as h:actual_payload=json.load(h)
        if actual_payload.get('schema')!='nfl-targets-actuals-v1' or common.instant(actual_payload['retrieved_at'])>now:
            raise ValueError('nfl_actual_targets_receipt_invalid')
        actuals.update({(r['game_id'],r['player_id']):r for r in actual_payload['rows']
                        if common.instant(r['available_at'])<now})
    brier=[];loss=[];pushes=0;groups={}
    for key,p in predictions.items():
        if common.instant(p["event_start"])>=now:continue
        row=settled.get(key) if p.get("line_origin","market")=="market" else None
        outcome=row["outcome"] if row else None
        actual=actuals.get((p["game_id"],p["player_id"]))
        if outcome is None and actual is not None:
            if not common.instant(p["forecast_at"])<common.instant(actual["start_time"]):continue
            value=actual["value"];line=p["reference_line"]
            outcome="push" if value==line else ("win" if (value>line)==(p["side"] in ("over","higher")) else "loss")
        if outcome is None:continue
        if outcome=="push":pushes+=1;continue
        q=min(1-1e-12,max(1e-12,p["q_win"]/(1-p["q_push"])));y=int(outcome=="win")
        brier.append((q-y)**2);loss.append(-y*math.log(q)-(1-y)*math.log1p(-q))
        group=groups.setdefault(p.get("line_origin","market"),{"n":0,"brier_sum":0.,"logloss_sum":0.})
        group["n"]+=1;group["brier_sum"]+=brier[-1];group["logloss_sum"]+=loss[-1]
    result={"schema":"nfl-context-settled-audit-v1","forecast_rows":len(predictions),"nonpush_scored":len(brier),
        "pending":len(predictions)-len(brier)-pushes,
        "pushes":pushes,"brier":sum(brier)/len(brier) if brier else None,
        "logloss":sum(loss)/len(loss) if loss else None,"by_line_origin":groups,
        "ranking_allowed":False,"automatic_promotion":False}
    io.write_json(out,result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("stage",choices=("run","audit"))
    p.add_argument("--date",default=datetime.now(timezone.utc).astimezone(TZ).date().isoformat())
    p.add_argument("--snapshots",type=Path,default=ROOT/"data/prop_snapshots.jsonl")
    p.add_argument("--data-root",type=Path,default=ROOT/"data")
    p.add_argument("--model-dir",type=Path,default=ROOT/"data/models/nfl_targets")
    p.add_argument("--out",type=Path);p.add_argument("--receipt",type=Path,default=ROOT/"reports/nfl_context_daily.json")
    p.add_argument("--download",action="store_true")
    p.add_argument("--refresh-actuals",action="store_true");a=p.parse_args()
    if a.stage=="audit":r=audit(snapshots=a.snapshots,directory=a.data_root/"nfl_context",
        out=a.out or ROOT/"reports/nfl_context_settled.json",refresh_actuals=a.refresh_actuals)
    else:r=run(snapshots=a.snapshots,data_root=a.data_root,model_dir=a.model_dir,
        out=a.out or a.data_root/"nfl_context"/(a.date+".jsonl"),receipt=a.receipt,game_date=a.date,download=a.download)
    print(json.dumps(r,allow_nan=False));return 2 if r.get("global_error") else 0


if __name__=="__main__":raise SystemExit(main())
