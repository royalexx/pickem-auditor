"""One next-morning official NHL SOG readback for a pinned research slate."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from research.p2_nhl_sog.slate_selection import DECISION_PATH, POLICY
from research.p2_nhl_sog.source_pipeline import (
    OFFICIAL, ROOT_NAMESPACE, UTC, clock, current_storage, put_once, verify_bundle,
)
from scripts.c03_live_transport import verify_signed_capture
from scripts.nhl_sog_full_slate import NAMESPACE, _save, discover_slate
from v2.official_nba_nhl_capture import nhl_stat_rows, normalized_team
from v2.p0_integrity.storage import verify_immutable_record


def _read(path, *, marker=False):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != path.stem:
        raise ValueError("SLATE_READBACK_SHA_MISMATCH")
    if marker and path.with_name(path.name + ".complete").read_text() != path.stem:
        raise ValueError("SLATE_READBACK_COMPLETION_MISMATCH")
    return json.loads(raw)


def _get_box(event):
    url = f"{OFFICIAL}/gamecenter/{event}/boxscore"
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "pickem-auditor-NHL-SOG-settlement/1"})
    with urlopen(request, timeout=15) as response:
        raw = response.read(8_000_001)
        if response.status != 200 or len(raw) > 8_000_000:
            raise ValueError("NHL_BOX_HTTP_OR_SIZE_INVALID")
    return url, raw


def read_game(root, day, game, slate_game, snapshots, *, fetch=_get_box):
    event = game["event_id"]
    row = {"game": game, "forecast_counts": {}, "eligible_skaters": None,
           "candidate_skaters": None, "verified_bundles": 0, "players": {}, "issues": []}
    expected_start = game["start_at"]
    if slate_game is not None:
        row["pregame_receipt_sha256"] = slate_game["receipt"]["sha256"]
        path = Path(root) / slate_game["receipt"]["relative_path"]
        if not path.resolve().is_relative_to(Path(root).resolve() / NAMESPACE / day):
            raise ValueError("SLATE_GAME_PATH_INVALID")
        saved = _read(path, marker=True)
        if not all(saved["game"][key] == game[key] for key in ("event_id", "away_team", "home_team")):
            raise ValueError("SLATE_GAME_IDENTITY_DRIFT")
        expected_start = saved["game"]["start_at"]
        row["pregame_status"] = saved["status"]
        source = next(iter(saved.get("source_attempts", ())), {})
        row["source_reasons"] = source.get("reasons", []) or ([source["reason"]] if "reason" in source else [])
        row["eligible_skaters"] = source.get("selection_eligible")
        row["candidate_skaters"] = source.get("candidate_count")
        row["selection_sha256"] = source.get("selection_sha256")
        if row["selection_sha256"]:
            try:
                selection = _read(Path(root) / (DECISION_PATH + row["selection_sha256"] + ".json"), marker=True)
                if selection["event_id"] != event or selection["policy"] != POLICY:
                    raise ValueError("SLATE_SELECTION_WRONG_EVENT_OR_POLICY")
                refs = ([selection["injury_receipt"]] +
                        [r for team in selection["team_evidence"].values() for r in team])
                for ref in filter(None, refs):
                    verify_signed_capture(ref, archive_root=Path(root) / ROOT_NAMESPACE / "c03",
                                          freeze=selection["input_freeze_at"], event_start=expected_start)
                row["verified_selection_source_count"] = len([ref for ref in refs if ref is not None])
            except (OSError, KeyError, ValueError, TypeError) as exc:
                row["issues"].append({"reason": str(exc), "stage": "selection_readback"})
        for player in source.get("records", ()):
            row["players"][player["player_id"]] = {
                "team_id": player["team_id"], "pregame_status": player["status"],
                "reasons": player["reasons"], "selection": player.get("selection"),
                "source_manifest_sha256": player["manifest_sha256"],
                "source_attempt_sha256": player["attempt_sha256"], "forecasts": []}
            row["verified_bundles"] += int(player["manifest_sha256"] is not None)
        for result in saved.get("players", ()):
            if result["player_id"] in row["players"]:
                row["players"][result["player_id"]]["model_status"] = result["status"]
                row["players"][result["player_id"]]["model_reason"] = result.get("reason")
                if "gamma_abstention" in result:
                    row["players"][result["player_id"]]["gamma_abstention"] = result["gamma_abstention"]
    else:
        row["pregame_status"] = "SLATE_GAME_RECEIPT_UNAVAILABLE"
    counts = Counter()
    bundles = {}
    for sha, forecast in snapshots:
        if not (clock(forecast["model_training_cutoff_at"]) <= clock(forecast["input_freeze_at"])
                <= clock(forecast["forecast_at"]) < clock(expected_start)
                and forecast["event_start_at"] == expected_start and forecast["quote_id"] is None):
            row["issues"].append({"forecast_sha256": sha, "reason": "FORECAST_TIMELINE_OR_QUOTE_INVALID"})
            continue
        player = row["players"].setdefault(forecast["player_id"], {
            "team_id": forecast["team_id"], "pregame_status": "FROZEN_WITHOUT_GAME_SUMMARY", "forecasts": []})
        if forecast["team_id"] != player["team_id"]:
            row["issues"].append({"forecast_sha256": sha, "reason": "FORECAST_TEAM_MISMATCH"})
            continue
        artifact = Path(root) / "research/p4_nhl_sog_slate/models" / (forecast["artifact_sha256"] + ".json")
        try:
            model = _read(artifact, marker=True)
            bundle_sha = forecast["uncertainty"]["p2_bundle_sha256"]
            if bundle_sha not in bundles:
                bundles[bundle_sha] = verify_bundle(root, bundle_sha)
            bundle, feature = bundles[bundle_sha]
            if (bundle["p0_feature_record_sha256"] != forecast["input_sha256"] or
                    feature["event_id"] != event or feature["player_id"] != forecast["player_id"] or
                    feature["team_id"] != forecast["team_id"]):
                raise ValueError("FORECAST_FEATURE_IDENTITY_MISMATCH")
            if (model["player_id"] != forecast["player_id"] or model["target_event_id"] != event or
                    model["input_freeze_at"] != forecast["input_freeze_at"]):
                raise ValueError("FORECAST_MODEL_IDENTITY_MISMATCH")
        except (OSError, KeyError, ValueError) as exc:
            row["issues"].append({"forecast_sha256": sha, "reason": str(exc)})
            continue
        player["forecasts"].append({"model": forecast["model_id"], "snapshot_sha256": sha,
            "model_sha256": forecast["artifact_sha256"], "pregame_sog_per_minute": model.get("plugin_rate"),
            "pregame_minutes": model.get("plugin_exposure")})
        counts[forecast["model_id"]] += 1
    row["forecast_counts"] = dict(counts)
    try:
        url, raw = fetch(event)
        sha = hashlib.sha256(raw).hexdigest()
        row["boxscore"] = {"source_url": url, **put_once(
            root, f"{NAMESPACE}/{day}/official_boxscores/{event}/{sha}.json", raw)}
        document = json.loads(raw)
        if str(document["id"]) != event or not all(
            document[side]["abbrev"] == game[key] for side, key in
            (("awayTeam", "away_team"), ("homeTeam", "home_team"))):
            raise ValueError("NHL_FINAL_GAME_IDENTITY_INVALID")
        if clock(expected_start) != clock(document["startTimeUTC"]):
            raise ValueError("NHL_FINAL_START_DIFFERS_FROM_FROZEN_SCHEDULE")
        teams = {normalized_team(game[k], "NHL") for k in ("home_team", "away_team")}
        outcomes = nhl_stat_rows(document, expected_teams=teams)
        row["settlement"] = "OFFICIAL_FINAL_VERIFIED"
    except (OSError, KeyError, ValueError, TypeError) as exc:
        row["settlement"] = "UNRESOLVED"
        row["issues"].append({"reason": str(exc)})
        return row
    row["played_outside_pregame_roster"] = sorted(set(outcomes) - set(row["players"]))
    for pid, player in row["players"].items():
        actual = outcomes.get(pid)
        if actual is None:
            player["outcome"] = "NO_PLAYED_APPEARANCE_IN_FINAL"
        elif normalized_team(player["team_id"], "NHL") != actual["team"]:
            player["outcome"] = "FINAL_PLAYER_TEAM_MISMATCH"
        else:
            player.update(outcome="PLAYED", shots_on_goal=actual["shots on goal"],
                          toi_minutes=actual["observed_workload_minutes"])
    return row


def run(root, day, commit):
    current_storage(root)
    path = Path(root) / NAMESPACE / day / "slates"
    manifests = [_read(p, marker=True) for p in path.glob("*.json")
                 if p.with_name(p.name + ".complete").is_file()]
    wanted = [m for m in manifests if m["code_commit"] == commit and m.get("capture_policy") == POLICY]
    if len(wanted) > 1:
        raise ValueError("MULTIPLE_MATCHING_PREGAME_SLATE_MANIFESTS")
    game_refs = {game["game"]["event_id"]: game for game in wanted[0]["games"]} if wanted else {}
    slate_run = f"nhl-sog-slate:{day}:{commit[:16]}"
    snapshots = {}
    for forecast_path in (Path(root) / "research/p0_integrity_store/forecasts").glob("*.json"):
        candidate = json.loads(forecast_path.read_bytes())
        if candidate.get("run_id") == slate_run and candidate.get("model_code_sha") == commit:
            forecast = verify_immutable_record(root, "ForecastSnapshot", forecast_path.stem)
            snapshots.setdefault(forecast["event_id"], []).append((forecast_path.stem, forecast))
    games = discover_slate(day)
    for event_id, record in game_refs.items():
        if all(game["event_id"] != event_id for game in games):
            games.append(record["game"])
    results = [read_game(root, day, game, game_refs.get(game["event_id"]),
                         sorted(snapshots.get(game["event_id"], ()))) for game in games]
    report = {"slate_date": day, "code_commit": commit, "pregame_manifest_found": bool(wanted),
              "observed_at": datetime.now(UTC).isoformat(), "research_only": True,
              "settlement_scope": "played_count_only", "structural_attribution": "unmeasured",
              "games": results}
    receipt = _save(root, day, "morning_reports", report)
    return {"receipt": receipt, **report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day", type=date.fromisoformat, required=True)
    parser.add_argument("--root", default="/work")
    parser.add_argument("--code-commit", required=True)
    args = parser.parse_args()
    if datetime.now(ZoneInfo("America/Toronto")).date() <= args.day:
        parser.error("morning readback must run after the Toronto slate date")
    result = run(args.root, args.day.isoformat(), args.code_commit)
    print("NHL_SOG_MORNING " + json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
