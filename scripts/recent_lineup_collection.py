#!/usr/bin/env python3
"""Collect last five official team rosters for a bounded research queue.

Separate archive from the full shared-context lineup history. A missing or
partial game is NOT evidence of player absence or active status tonight.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from lineup_feeds import collect
from recent_lineup_tendency import tendency_path
from pick_verification import write_atomic


def run(queue, date, *, root="data", now=None, fetch=None, max_scopes=30):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if now.astimezone(ZoneInfo("America/Toronto")).date().isoformat() != date:
        raise ValueError("live team roster history cannot be backdated")
    if queue.get("date") != date:
        raise ValueError("cross-date research queue")
    from usage_baseline import using_directory
    attempts = []
    seen = set()
    for item in queue.get("queue") or []:
        sport, team, stat = (item.get(k) for k in ("sport", "team", "stat"))
        player_id = str(item.get("player_id") or "")
        if sport not in ("NBA", "NHL", "NFL") or not team or not stat:
            continue
        if sport == "NHL" and stat in ("saves", "goalie saves"):
            continue  # game-starting goalie still requires explicit starter news
        if sport == "NFL" and not player_id.startswith("00-"):
            continue  # no silent ESPN -> GSIS ID assumption
        key = (sport, team, stat)
        if key in seen or len(seen) >= max_scopes:
            continue
        seen.add(key)
        archive = tendency_path(root, sport, team, stat, date)
        attempt = {"sport": sport, "team": team, "stat": stat,
                   "archive": str(archive), "status": "unavailable"}
        try:
            if archive.is_file():
                cached=json.loads(archive.read_text(encoding="utf-8"))
                stamp=datetime.fromisoformat(cached["retrieved_at"].replace("Z","+00:00"))
                if (stamp.tzinfo and 0 <= (now-stamp).total_seconds() <= 4*3600
                        and cached.get("sport")==sport and cached.get("team")==team):
                    attempt.update(status="reused_source_checked_archive",
                                   completed_games=len(cached.get("games") or []))
                    attempts.append(attempt)
                    continue
            with using_directory(root):
                options={"lookback_days": 105 if sport == "NFL" else 45,
                         "max_games": 5, "persist": False}
                if fetch is not None:options["fetch"]=fetch
                history=collect(sport,team,stat,date,**options)
            if history.get("collection",{}).get("errors"):
                raise ValueError("partial source game collection")
            # A successfully collected source has already passed validated
            # complete box-score checks inside lineup_feeds.collect().
            history["retrieved_at"]=now.isoformat()
            write_atomic(archive,history)
            attempt.update(status="source_checked",completed_games=len(history["games"]),
                           collected_games=history["collection"]["discovered"])
        except (ValueError,KeyError,TypeError,OSError,ImportError) as exc:
            attempt.update(status="source_unavailable",reason=type(exc).__name__)
        attempts.append(attempt)
    return {"schema":"recent-lineup-collection-v1", "date":date,
            "source_scopes":len(seen), "attempts":attempts,
            "completed":sum(x["status"] in ("source_checked","reused_source_checked_archive")
                            for x in attempts),
            "proves_current_active_status":False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue",required=True)
    p.add_argument("--date",required=True)
    p.add_argument("--data-root",default="data")
    p.add_argument("--out",default="reports/recent_lineup_collection.json")
    a=p.parse_args(argv)
    queue=json.loads(Path(a.queue).read_text(encoding="utf-8"))
    report=run(queue,a.date,root=a.data_root)
    write_atomic(a.out,report)
    print(json.dumps(report,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
