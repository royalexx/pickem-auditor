"""Run the existing P2 and P4 paths for every game on one Toronto slate."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from functools import partial
import json
from pathlib import Path
import re
import time

from research.p2_nhl_sog.source_pipeline import (
    SourceBlocked,
    canonical_bytes,
    clock,
    current_storage,
    digest,
    probe_schedule,
    put_once,
    scheduled_games,
    stamp,
)

UTC = timezone.utc
NAMESPACE = "research/nhl_sog_full_slate"
FINAL_LEAD = timedelta(minutes=20)
EARLY_WINDOW = timedelta(minutes=65)
EARLY_CLOSE = timedelta(minutes=55)
FINAL_WINDOW = timedelta(minutes=25)


def discover_slate(day, *, probe=probe_schedule):
    """Keep the whole official slate, including games whose windows closed."""
    schedule = probe(day)
    if not isinstance(schedule, dict) or not isinstance(schedule.get("games"), list):
        raise SourceBlocked("SCHEDULE_DISCOVERY_INVALID")
    # P2's schedule parser otherwise filters games whose official state is live.
    games = scheduled_games(
        {"games": [dict(game, gameState="FUT") for game in schedule["games"]]},
        day=day,
    )
    states = {str(row["id"]): row.get("gameState") for row in schedule["games"]}
    return [
        dict(game, game_state=states[game["event_id"]])
        for game in games if game["local_date"] == day
    ]


def _now():
    return datetime.now(UTC)


def _save(root, day, category, record):
    raw = canonical_bytes(record)
    return put_once(root, f"{NAMESPACE}/{day}/{category}/{digest(raw)}.json", raw)


def _wait_until(target, now, sleep):
    while (remaining := (target - now()).total_seconds()) > 0:
        sleep(min(remaining, 30))


def _ready(source):
    return [row for row in source.get("records", ())
            if row.get("manifest_sha256") and row["status"].startswith("SOURCE_READY")]


def run_game(game, *, capture, forecast, now=_now, sleep=time.sleep,
             checkpoint=None, recovered=()):
    """Capture within P2 windows, then emit forecasts from admitted bundles."""
    start = clock(game["start_at"])
    freeze = start - FINAL_LEAD
    source_attempts = list(recovered)
    source = next((item for item in reversed(source_attempts) if _ready(item)), {})
    published = []
    if game["game_state"] not in {"FUT", "PRE"}:
        status = "EVENT_ALREADY_STARTED" if now() >= start else "EVENT_NOT_PREGAME"
        return dict(game=game, status=status, source_attempts=[], players=[])

    for opens, closes in ((start - EARLY_WINDOW, start - EARLY_CLOSE),
                          (start - FINAL_WINDOW, freeze)):
        if _ready(source):
            break
        _wait_until(opens, now, sleep)
        if now() >= closes:
            continue
        try:
            source = capture(game=game, freeze=stamp(freeze))
        except (OSError, ValueError) as exc:
            source = {"status": "SOURCE_FAILURE", "reason": str(exc)}
        source_attempts.append(source)
        if checkpoint is not None:
            checkpoint(source)

    if not source_attempts:
        return dict(game=game, status="SOURCE_WINDOW_MISSED", source_attempts=[], players=[])

    admitted = _ready(source)
    if admitted:
        _wait_until(freeze, now, sleep)
    for row in admitted:
        if now() >= start:
            published.append(dict(player_id=row["player_id"], status="FORECAST_DEADLINE_MISSED"))
            continue
        try:
            published.append(forecast(row["manifest_sha256"]))
        except (OSError, ValueError) as exc:
            published.append(dict(player_id=row["player_id"], status="FORECAST_FAILURE",
                                  reason=str(exc)))
    forecast_count = sum(len(row.get("forecasts", ())) for row in published)
    return dict(game=game, status="FORECASTS_FROZEN" if forecast_count else "NO_FORECASTS",
                source_attempts=source_attempts, players=published, forecast_count=forecast_count)


def _source_checkpoints(root, day, game, run_id):
    directory = Path(root) / NAMESPACE / day / "checks" / game["event_id"]
    freeze = stamp(clock(game["start_at"]) - FINAL_LEAD)
    accepted = []
    for path in sorted(directory.glob("*.json")):
        marker = path.with_name(path.name + ".complete")
        if not marker.is_file():
            continue
        raw = path.read_bytes()
        if marker.read_text() != path.stem or digest(raw) != path.stem:
            raise SourceBlocked("SLATE_SOURCE_CHECKPOINT_CORRUPT")
        receipt = json.loads(raw)
        if receipt["run_id"] == run_id and receipt["freeze"] == freeze:
            accepted.append(receipt)
    return [receipt["source"] for receipt in sorted(accepted, key=lambda r: r["saved_at"])]


def _run_checkpointed_game(root, day, game, run_id, capture, forecast):
    event_id = game["event_id"]
    freeze = stamp(clock(game["start_at"]) - FINAL_LEAD)

    def checkpoint(source):
        _save(root, day, f"checks/{event_id}", {
            "run_id": run_id, "game": game, "freeze": freeze,
            "saved_at": stamp(_now()), "source": source,
        })

    return run_game(game, capture=capture, forecast=forecast, checkpoint=checkpoint,
                    recovered=_source_checkpoints(root, day, game, run_id))


def run_slate(root, day, *, capture, forecast, code_commit, games=None, progress=None,
              event_ids=()):
    """Process simultaneous windows concurrently and persist each game's result."""
    current_storage(root)
    if games is None:
        games = discover_slate(day)
    scheduled_games_count = len(games)
    if event_ids:
        expected = set(event_ids)
        if expected - {game["event_id"] for game in games}:
            raise SourceBlocked("REQUESTED_EVENT_NOT_ON_OFFICIAL_SLATE")
        games = [game for game in games if game["event_id"] in expected]
    run_at = stamp(_now())
    run_id = f"nhl-sog-slate:{day}:{code_commit[:16]}"
    rows = {}
    game_forecast = partial(forecast, run_id=run_id, code_commit=code_commit)
    with ThreadPoolExecutor(max_workers=max(1, len(games))) as pool:
        pending = {pool.submit(_run_checkpointed_game, root, day, game, run_id,
                               capture, game_forecast): game
                   for game in games}
        for work in as_completed(pending):
            game = pending[work]
            try:
                result = work.result()
            except Exception as exc:
                result = dict(game=game, status="GAME_RUN_FAILED", reason=str(exc))
            result["run_id"] = run_id
            event_id = game["event_id"]
            receipt = _save(root, day, f"games/{event_id}", result)
            rows[event_id] = {
                "game": game,
                "status": result["status"],
                "forecast_count": result.get("forecast_count", 0),
                "receipt": receipt,
            }
            if progress is not None:
                progress(rows[event_id])

    ordered = [rows[game["event_id"]] for game in games]
    forecast_games = sum(row["forecast_count"] > 0 for row in ordered)
    manifest = {
        "schema": "PA-NHL-SOG-FULL-SLATE/1",
        "run_id": run_id,
        "code_commit": code_commit,
        "slate_date": day,
        "started_at": run_at,
        "completed_at": stamp(_now()),
        "research_only": True,
        "scheduled_games": scheduled_games_count,
        "attempted_games": len(games),
        "games_with_forecasts": forecast_games,
        "distribution_forecasts": sum(row["forecast_count"] for row in ordered),
        "complete_forecast_coverage": bool(games) and forecast_games == scheduled_games_count,
        "complete_requested_coverage": bool(games) and forecast_games == len(games),
        "games": ordered,
    }
    return dict(manifest, receipt=_save(root, day, "slates", manifest))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--root", default="/work")
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--signed-history-manifest", required=True)
    parser.add_argument("--signed-history-sha256", required=True)
    parser.add_argument("--history-pool", required=True)
    parser.add_argument("--event-id", action="append", default=[],
                        help="limit this worker to specified official events on the slate")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.code_commit):
        parser.error("--code-commit must be the exact 40-character revision")
    if not re.fullmatch(r"[0-9a-f]{64}", args.signed_history_sha256):
        parser.error("--signed-history-sha256 must be a 64-character SHA-256")
    from research.p2_nhl_sog.history_bridge import open_history_sources
    from research.p2_nhl_sog.slate import capture_game_sources
    from v2.nhl_sog_p4_slate import HistorySources, forecast_bundle

    day = args.day.isoformat()
    current_storage(args.root)
    games = discover_slate(day)
    print("NHL_SOG_SCHEDULE " + json.dumps(games, sort_keys=True), flush=True)
    pool = open_history_sources(args.root, args.signed_history_manifest,
                                args.signed_history_sha256, args.history_pool)
    history = {
        "signed_history_manifest_path": args.signed_history_manifest,
        "signed_history_manifest_sha256": args.signed_history_sha256,
        "history_pool": pool,
    }
    history_sources = HistorySources(args.root, args.signed_history_manifest,
                                     args.signed_history_sha256, pool)
    output = run_slate(
        args.root,
        day,
        capture=partial(capture_game_sources, args.root, **history),
        forecast=partial(forecast_bundle, args.root, history_sources=history_sources),
        code_commit=args.code_commit,
        games=games,
        event_ids=args.event_id,
        progress=lambda row: print("NHL_SOG_GAME " + json.dumps(row, sort_keys=True), flush=True),
    )
    print("NHL_SOG_SLATE " + json.dumps(output, sort_keys=True), flush=True)
    return 0 if output["complete_requested_coverage"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
