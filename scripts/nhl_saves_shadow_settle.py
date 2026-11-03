#!/usr/bin/env python3
"""Settle immutable NHL saves posterior shadows without modifying forecasts.

Only joins collector-owned, timestamp-verified postgame actuals to frozen
pregame shadow rows. Receipts remain research-only and never authorize tiers.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from nhl_saves_posterior_shadow import identity


class SettlementConflict(ValueError): pass


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)


def stamp(value):
    try:
        time=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return time.astimezone(timezone.utc) if time.tzinfo else None
    except (ValueError,TypeError,OverflowError):
        return None


def digest(forecast):
    return hashlib.sha256(canonical(forecast).encode()).hexdigest()


def actual_outcome(stat, side, line):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v)
           for v in (stat,line)):
        raise SettlementConflict("INVALID_SETTLEMENT_STAT_OR_LINE")
    if stat < 0 or line < 0 or not (float(stat).is_integer()):
        raise SettlementConflict("INVALID_SAVES_INTEGER_SUPPORT")
    if stat == line:return "push"
    if side in ("over","higher"):return "win" if stat>line else "loss"
    if side in ("under","lower"):return "win" if stat<line else "loss"
    raise SettlementConflict("INVALID_SAVES_SIDE")


def settle(snapshots, forecasts_dir, out_dir, *, now=None):
    now=now or datetime.now(timezone.utc)
    if not now.tzinfo:raise SettlementConflict("NAIVE_SETTLEMENT_CLOCK")
    raw=Path(snapshots)
    if not raw.is_file():raise SettlementConflict("MISSING_SETTLED_SNAPSHOT_ARCHIVE")
    lookup={}
    for text in raw.read_text(encoding="utf-8").splitlines():
        if not text.strip():continue
        row=json.loads(text)
        if row.get("sport")!="NHL" or row.get("stat") not in ("saves","goalie saves"):
            continue
        key=identity(row)
        if key in lookup:
            # Two rows sharing forecast identity cannot be resolved by guessing.
            raise SettlementConflict("AMBIGUOUS_OR_DUPLICATE_SAVES_SNAPSHOT")
        lookup[key]=row
    directory=Path(forecasts_dir)
    result={"schema":"nhl-saves-shadow-settlements-v1","forecast_files":0,
            "forecasts_examined":0,"new_settlements":0,
            "existing_settlements":0,"unmatched_or_unsettled":0,
            "publication_eligible":False,"ranking_allowed":False}
    if not directory.is_dir():return result
    for forecast_path in sorted(directory.glob("*.jsonl")):
        day=forecast_path.stem
        output=Path(out_dir)/(day+".jsonl")
        old_text=output.read_text(encoding="utf-8") if output.exists() else ""
        prior={}
        for line in old_text.splitlines():
            if not line.strip():raise SettlementConflict("INVALID_PREVIOUS_SETTLEMENT_LINE")
            r=json.loads(line)
            if r.get("schema")!="nhl-saves-shadow-settlement-v1":
                raise SettlementConflict("INVALID_PREVIOUS_SETTLEMENT_SCHEMA")
            digest_key=r["forecast_sha256"]
            if digest_key in prior:raise SettlementConflict("DUPLICATE_PREVIOUS_SETTLEMENT")
            prior[digest_key]=r
        seen=set()
        additions=[]
        result["forecast_files"]+=1
        for line in forecast_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():raise SettlementConflict("INVALID_FORECAST_SIDECAR")
            forecast=json.loads(line)
            if forecast.get("status")!="forecast":continue
            fhash=digest(forecast)
            if fhash in seen:raise SettlementConflict("DUPLICATE_FROZEN_FORECAST")
            seen.add(fhash)
            result["forecasts_examined"]+=1
            source=lookup.get(identity(forecast))
            if source is None or source.get("actual_stat") is None or source.get("outcome") is None:
                result["unmatched_or_unsettled"]+=1
                continue
            forecast_at=stamp(forecast.get("forecast_at"))
            event=stamp(forecast.get("event_start"))
            source_at=stamp(source.get("forecast_at"))
            settled_at=stamp(source.get("settled_at"))
            if (not forecast_at or not event or not source_at or not settled_at
                    or forecast_at>=event or source_at>=event
                    or settled_at<=event or settled_at>now):
                raise SettlementConflict("INVALID_SOURCE_OR_SETTLEMENT_CLOCK")
            outcome=actual_outcome(source["actual_stat"],forecast["side"],
                                   forecast["reference_line"])
            if outcome!=source["outcome"]:
                raise SettlementConflict("SOURCE_OUTCOME_DISAGREES_WITH_ACTUAL")
            item={"schema":"nhl-saves-shadow-settlement-v1",
                  "forecast_sha256":fhash,
                  "forecast_run_id":forecast.get("run_id"),
                  "model_version":forecast.get("version"),
                  "model_source_digest":forecast.get("model_source_digest"),
                  "event_start":forecast["event_start"],
                  "game_date":forecast["game_date"],
                  "player_id":forecast["player_id"],
                  "stat":forecast["stat"],"side":forecast["side"],
                  "line":forecast["reference_line"],
                  "q_win":forecast["q_win"],"q_push":forecast["q_push"],
                  "outcome":outcome,"actual_stat":source["actual_stat"],
                  "outcome_available_at":source["settled_at"],
                  "production_snapshot_unchanged":True,
                  "publication_eligible":False}
            if fhash in prior:
                if prior[fhash]!=item:
                    raise SettlementConflict("IMMUTABLE_SAVES_SETTLEMENT_CONFLICT")
                result["existing_settlements"]+=1
            else:
                additions.append(item)
        # Prior receipts without a corresponding unchanged frozen forecast are
        # a provenance failure. They cannot remain silently scored.
        if set(prior)-seen:
            raise SettlementConflict("MISSING_FROZEN_FORECAST_FOR_SETTLEMENT")
        if additions:
            output.parent.mkdir(parents=True,exist_ok=True)
            temp=output.with_suffix(".tmp")
            extension="".join(canonical(x)+"\n" for x in additions)
            temp.write_text(old_text+extension,encoding="utf-8")
            temp.replace(output)
        result["new_settlements"]+=len(additions)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshots",type=Path,required=True)
    parser.add_argument("--forecasts-dir",type=Path,required=True)
    parser.add_argument("--out-dir",type=Path,required=True)
    parser.add_argument("--receipt",type=Path,required=True)
    args=parser.parse_args()
    report=settle(args.snapshots,args.forecasts_dir,args.out_dir)
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    args.receipt.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
