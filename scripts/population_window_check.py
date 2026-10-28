#!/usr/bin/env python3
"""Fail-closed preflight for genuinely contiguous, date-frozen multi-season studies.

Population coverage must reach the heldout end before the posterior is fitted.
Recent season data is a second independently checkpointed stream; presence of
season shards alone does NOT guarantee every intervening game has been collected.
"""
from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path
import population_backfill as ingest
import population_history as warehouse

ROOT=Path(__file__).resolve().parents[1]


def inspect(root,*,sport,stat,train_from,as_of,until,max_seasons=4,
            min_training_seasons=2,min_rows=300):
    start=date.fromisoformat(train_from)
    cutoff=date.fromisoformat(as_of)
    end=date.fromisoformat(until)
    if not start<cutoff<end or not 1<=max_seasons<=20 or not 1<=min_training_seasons<=max_seasons:
        raise ValueError("invalid_chronological_season_window")
    if min_rows<300:
        raise ValueError("invalid_minimum_population_rows")
    warehouse.family(sport,stat)
    source={"stream":None,"next_uncollected":None}
    if sport in ("NHL","NBA"):
        archive=ingest.read_state(root,sport)
        recent=ingest.read_state(root,sport,stream="recent")
        origin=date.fromisoformat(ingest.RECENT_START[sport])
        archive_next=date.fromisoformat(archive["cursor"])
        recent_next=date.fromisoformat(recent["cursor"])
        if end<=archive_next:
            source={"stream":"archive","next_uncollected":archive["cursor"]}
        elif start>=origin and end<=recent_next:
            source={"stream":"recent","next_uncollected":recent["cursor"]}
        elif start<origin and archive_next>=origin and end<=recent_next:
            source={"stream":"archive_plus_recent","next_uncollected":recent["cursor"]}
        else:
            raise ValueError("POPULATION_COLLECTION_INCOMPLETE: "+
                sport+" archive_to="+archive["cursor"]+
                " recent_to="+recent["cursor"]+
                " requested_until="+until)
    else:
        state=ingest.read_state(root,"NFL")
        # NFL seasons are committed only after the following March. A
        # 2025 season cursor=2026 validates games through Feb 2026, not 2026 fall.
        latest_completed=date(int(state["cursor"]),3,1)
        if end>latest_completed:
            raise ValueError("NFL_SEASON_COLLECTION_INCOMPLETE: "+
                "next_season="+state["cursor"]+" requested_until="+until)
        source={"stream":"archive","next_uncollected_season":state["cursor"]}
    training=warehouse.read(root,sport=sport,stat=stat,
        before=as_of,after=train_from,max_seasons=max_seasons)
    future=warehouse.read(root,sport=sport,stat=stat,
        before=until,after=as_of)
    seasons=sorted({r["season"] for r in training})
    # Never accept 2018 + 2023 as a 'two season' sample just because
    # a few distant years happened to exist in independent shards.
    years=[int(y) for y in seasons]
    if years and years!=list(range(years[0],years[-1]+1)):
        raise ValueError("DISCONNECTED_TRAINING_SEASONS: "+str(seasons))
    status="ready" if (len(training)>=min_rows and
        len(seasons)>=min_training_seasons and len(future)>0) else "insufficient"
    receipt={
        "schema":"historical_joint_training_window_v1",
        "status":status,"sport":sport,"stat":stat,
        "train_from_inclusive":train_from,"train_before_exclusive":as_of,
        "heldout_before_exclusive":until,
        "max_seasons":max_seasons,"min_training_seasons":min_training_seasons,
        "source":source,"training_seasons":seasons,
        "training_rows":len(training),"training_players":len({r["player_id"] for r in training}),
        "training_first_game":min((r["game_date"] for r in training),default=None),
        "training_last_game":max((r["game_date"] for r in training),default=None),
        "heldout_rows":len(future),"heldout_dates":len({r["game_date"] for r in future}),
        "training_source_provenance_verified":True,
        "publication_eligible":False
    }
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--sport",choices=warehouse.SPORTS,required=True)
    p.add_argument("--stat",required=True)
    p.add_argument("--train-from",required=True)
    p.add_argument("--as-of",required=True)
    p.add_argument("--until",required=True)
    p.add_argument("--max-seasons",type=int,default=4)
    p.add_argument("--min-training-seasons",type=int,default=2)
    p.add_argument("--min-rows",type=int,default=300)
    p.add_argument("--report",type=Path,default=Path("reports/multisport_joint/window_preflight.json"))
    a=p.parse_args(argv)
    try:
        report=inspect(a.root,sport=a.sport,stat=a.stat,train_from=a.train_from,
            as_of=a.as_of,until=a.until,max_seasons=a.max_seasons,
            min_training_seasons=a.min_training_seasons,min_rows=a.min_rows)
    except (ValueError,KeyError,TypeError) as exc:
        report={"schema":"historical_joint_training_window_v1","status":"blocked",
                "reason":str(exc),"sport":a.sport,"stat":a.stat,
                "publication_eligible":False}
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="ready" else 2


if __name__=="__main__":
    raise SystemExit(main())
