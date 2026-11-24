"""Forecast NFL projected starters offline from a pinned collector receipt."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import timedelta
from hashlib import sha256
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

import fetch_slate as slate
import jobs
from nfl_pregame_roster import CROSSWALK, _crosswalk, _identity
from nfl_research_sources import CAPTURE, ESPN, FORECAST, games, now, projected, read, save, source
from phase0_input_capture import stamp, utc
from phase0_pre_eval import canonical_bytes

MAX_CAPTURE_AGE = timedelta(minutes=30)


def digest(value):
    return sha256(canonical_bytes(value)).hexdigest()


def prepare_inputs(root, capture, stage):
    for name, checksum in capture["files"].items():
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts or not rel.parts:
            raise ValueError("unsafe_model_input_path")
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(read(root, "model_input", checksum))


def load_eligibility(root, capture):
    day = capture["date"]
    cutoff = utc(capture["completed_at"])
    entries = capture["sources"]
    scoreboard_url = f"{ESPN}/scoreboard?dates={day.replace('-', '')}"
    schedule = games(json.loads(source(root, "scoreboard", entries["scoreboard"],
                                       scoreboard_url, cutoff)), day)
    raw = source(root, "crosswalk", entries["crosswalk"], CROSSWALK, cutoff)
    crosswalk = _crosswalk(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    all_teams = {}
    failures = {}
    for event, sides, start, state in schedule.values():
        if state != "pre":
            continue
        for team, team_id in sides.values():
            depth = entries["depth"].get(team)
            try:
                url = f"{ESPN}/teams/{team_id}/depthcharts"
                raw = source(root, "depth", depth, url, cutoff)
                received = utc(depth["received_at"])
                if not received < start:
                    raise ValueError("depth_received_after_kickoff")
                players = projected(json.loads(raw))
                if not players:
                    raise ValueError("projected_starter_slots_unavailable")
                all_teams[(event, team)] = (players, depth["sha256"])
            except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
                failures[(event, team)] = str(exc)
    return schedule, crosswalk, all_teams, failures


def check_candidate(row, quotes, schedule, crosswalk, teams, failures, at):
    meta = row["_meta"]
    team, opponent = meta["team"], meta["opponent"]
    events = [g for pair, g in schedule.items() if set(pair) == {team, opponent}]
    if len(events) != 1:
        return None, "espn_fixture_missing_or_ambiguous"
    event, sides, start, state = events[0]
    if state != "pre" or start <= at:
        return None, "event_not_pregame"
    if not quotes or any(utc(q.get("event_start")) != start
                         or not q.get("event_id") or not q.get("event_id_namespace")
                         or {q.get("team"), q.get("opponent")} != {team, opponent}
                         for q in quotes):
        return None, "quote_fixture_unverified"
    market_ids = {(str(q["event_id"]), q["event_id_namespace"]) for q in quotes}
    if (len(market_ids) != 1 or next(iter(market_ids)) !=
            (str(row.get("event_id")), row.get("event_id_namespace"))):
        return None, "quote_event_identity_conflict"
    espn_id, reason = _identity(meta, crosswalk, {})
    if reason:
        return None, reason
    selected = teams.get((event, team))
    if selected is None:
        return None, failures.get((event, team), "projected_starter_source_missing")
    players, sha = selected
    if espn_id not in players:
        return None, "player_not_projected_starter"
    home, away = sides["home"][0], sides["away"][0]
    meta.update(event_start=stamp(start), home_team=home, away_team=away,
                matchup_orientation_verified=True,
                matchup=jobs.matchup_label(team, opponent, home_team=home, away_team=away))
    return {"espn_event_id": event, "espn_player_id": espn_id,
            "depth_chart_sha256": sha, "projected_starter": True}, None


def build_forecasts(root, capture_sha, *, clock, evaluate):
    if os.environ.get("PICKEM_PHASE0_CERTIFIED_ONLY") == "1":
        raise ValueError("projected_starter_forecasts_require_research_mode")
    capture = json.loads(read(root, "capture", capture_sha))
    if capture["schema"] != CAPTURE:
        raise ValueError("collector_schema_mismatch")
    at = clock()
    done = utc(capture["completed_at"])
    if not done or not timedelta(0) <= at - done <= MAX_CAPTURE_AGE:
        raise ValueError("stale_or_future_capture")
    rows, attempts = [], []
    source_rows = []
    error = None
    if not capture["files"]:
        error = "no_collected_model_inputs"
    with TemporaryDirectory(prefix="nfl-research-forecast-") as temp:
        stage = Path(temp)
        if not error:
            prepare_inputs(root, capture, stage)
            try:
                schedule, crosswalk, teams, failures = load_eligibility(root, capture)
                slate_path = stage / "slate_fetch.jsonl"
                source_rows, report = jobs.reuse_recent_collect(
                    capture["date"], slate_path, slate.quotes_path_for(slate_path), now=at)
            except (jobs.JobError, KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
                error = str(exc)
        if not error:
            quotes = [q for q in report["_fresh_quotes"] if utc(q.get("retrieved_at"))
                      and utc(q["retrieved_at"]) <= done]
            # Use the legacy numeric benchmark's prepared contracts and evaluator.
            scoped = [row for row in source_rows if row.get("sport") == "NFL"]
            lookup = jobs.slate_lookup(scoped)
            candidates = jobs.attach_meta(
                slate.prepare_pipeline(scoped, quotes, now=stamp(at)), lookup,
                game_date=capture["date"], run_id=f"nfl-starters:{capture_sha}",
                run_at=stamp(at))
            claims = {}
            ready = []
            for candidate in candidates:
                sport, player, stat, _ = jobs.parse_pipeline_id(candidate["id"])
                exact = [q for q in slate.quotes_for_row(quotes, lookup[(sport, player, stat)])
                         if q.get("line") == candidate["line"]]
                if candidate["id"] in claims:
                    raise ValueError("duplicate_prepared_candidate_id")
                claim, reason = check_candidate(candidate, exact, schedule, crosswalk,
                                                teams, failures, clock())
                claims[candidate["id"]] = claim
                if reason:
                    attempts.append({"id": candidate["id"], "status": "unavailable", "reason": reason})
                    continue
                candidate["_phase0_market_quotes"] = exact
                ready.append(candidate)
            rows, _ = evaluate(ready, now=at, clock_fn=clock, data_root=stage,
                               attempt_receipts=attempts)
            for row in rows:
                original = row["inputs"]["id"]
                event = claims[original]["espn_event_id"]
                terms = [row[k] for k in ("event_id_namespace", "event_id", "player_id", "stat",
                                         "reference_line", "side")]
                contract_id = digest(["nfl_primary_line_research_v1", event, *terms])
                row.update(claims[original], contract_id=contract_id,
                           forecast_id=digest([capture_sha, contract_id, row["forecast_at"]]),
                           final_rank="Unranked", status="UNRANKED",
                           publication_eligible=False, availability_verified=False,
                           phase0r_original_source_certified=False,
                           phase0r_certification_status="UNCERTIFIED_RESEARCH_SHADOW")
    receipt = {
        "schema": FORECAST, "date": capture["date"], "capture_sha256": capture_sha,
        "forecasts": rows, "attempts": attempts, "source_slate_rows": len(source_rows),
        "abstentions": Counter(row["reason"] for row in attempts if row["status"] == "unavailable"),
        "error": error, "publication_eligible": False,
    }
    return receipt


def forecast(root, capture_sha, *, clock=now, evaluate=jobs.run_pipeline_batch):
    # Validate the ID before using it as a path component.
    read(root, "capture", capture_sha)
    commits = root / "forecast_commits"
    commits.mkdir(parents=True, exist_ok=True)
    marker = commits / f"{capture_sha}.json"
    with (commits / f"{capture_sha}.lock").open("a+") as lock:
        jobs.pm._lock_handle(lock)
        try:
            if marker.exists():
                digest = json.loads(marker.read_bytes())["forecasts_sha256"]
                return digest, json.loads(read(root, "forecasts", digest))
            receipt = build_forecasts(root, capture_sha, clock=clock, evaluate=evaluate)
            while True:
                checksum = save(root, "forecasts", receipt)
                completed = clock()
                remaining = [row for row in receipt["forecasts"]
                             if completed < utc(row["event_start"])]
                if len(remaining) == len(receipt["forecasts"]):
                    break
                retained = {row["inputs"]["id"] for row in remaining}
                for attempt in receipt["attempts"]:
                    if attempt["status"] == "forecast" and attempt["id"] not in retained:
                        attempt.update(status="unavailable", reason="forecast_commit_after_kickoff")
                        receipt["abstentions"]["forecast_commit_after_kickoff"] += 1
                receipt["forecasts"] = remaining
            slate.write_json({"forecasts_sha256": checksum, "completed_at": stamp(completed)}, marker)
            return checksum, receipt
        finally:
            jobs.pm._unlock_handle(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--capture-sha256", required=True)
    args = parser.parse_args()
    digest, receipt = forecast(args.root, args.capture_sha256)
    print(json.dumps({"sha256": digest, "forecasts": len(receipt["forecasts"]),
                      "abstentions": receipt["abstentions"], "error": receipt["error"]}))


if __name__ == "__main__":
    main()
