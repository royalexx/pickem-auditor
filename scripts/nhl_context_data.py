"""Separated NHL context warehouse. No odds, rankings, or production writes.

One atomic bundle per completed regular-season game contains independent
team, skater and goalie rows. Matchups are separate pregame snapshots.
Historical backfills are explicitly retrospective, never publication archives.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import gzip
import json
import math
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

VERSION = "nhl-context-data-v1"
BASE = "https://api-web.nhle.com/v1"
ROOT = Path(__file__).resolve().parents[1]


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def instant(value):
    if not isinstance(value, str):
        raise ValueError("missing_timezone_timestamp")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp_requires_timezone")
    return result.astimezone(timezone.utc)


def count(value, maximum=200):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError("invalid_observed_count")
    return value


def minutes(value):
    if not isinstance(value, str) or len(value.split(":")) != 2:
        raise ValueError("missing_observed_minutes")
    m, s = value.split(":")
    if not m.isdigit() or not s.isdigit() or not 0 <= int(s) < 60:
        raise ValueError("invalid_minutes")
    result = int(m) + int(s) / 60
    if not 0 <= result <= 65:
        raise ValueError("invalid_regular_season_minutes")
    return result


def game_duration(box, pbp):
    """Exclude shootout events, retaining actual sudden-death OT duration."""
    period = box["periodDescriptor"]["number"]
    if period == 3:
        return 60.0
    if period not in (4, 5) or not isinstance(pbp, dict):
        raise ValueError("overtime_requires_verified_play_by_play")
    if str(pbp.get("id")) != str(box["id"]):
        raise ValueError("play_by_play_game_identity_mismatch")
    if period == 5 or box["periodDescriptor"].get("periodType") == "SO":
        return 65.0
    goals = [p for p in pbp.get("plays", []) if p.get("typeDescKey") == "goal"
             and p.get("periodDescriptor", {}).get("number") == 4]
    if len(goals) != 1:
        raise ValueError("missing_overtime_winning_goal_clock")
    return 60.0 + minutes(goals[0]["timeInPeriod"])


def normalize(box, *, observed_at, pbp=None, include_attempts=True):
    """Strict official boxscore adapter; absence is never a zero.

    Save counts must reconcile to goalie shots and goals. Team SOG need not
    equal goalie shots faced because of empty nets. Bench goalies are omitted.
    Advanced/situation metrics remain null until independently sourced.
    """
    if not isinstance(include_attempts, bool):
        raise ValueError("invalid_attempt_collection_mode")
    gid = box.get("id")
    if isinstance(gid, bool) or not isinstance(gid, int) or str(gid)[4:6] != "02":
        raise ValueError("requires_nhl_regular_season_game")
    if box.get("gameState") not in ("FINAL", "OFF"):
        raise ValueError("game_not_complete")
    start = instant(box["startTimeUTC"])
    observed = instant(observed_at)
    duration = game_duration(box, pbp)
    if observed <= start + timedelta(minutes=duration):
        raise ValueError("observation_precedes_possible_game_completion")
    source = {"url": f"{BASE}/gamecenter/{gid}/boxscore", "sha256": digest(box),
              "observed_at": observed.isoformat()}
    common = {"game_id": str(gid), "season": str(gid)[:4],
              "game_date": box["gameDate"], "start_time": start.isoformat(),
              "game_minutes": duration}
    if abs((start.date() - datetime.fromisoformat(common["game_date"]).date()).days) > 1:
        raise ValueError("game_date_mismatch")
    result = {"schema": VERSION, **common, "source": source,
              "teams": [], "skaters": [], "goalies": []}
    codes = {s: box[s]["abbrev"] for s in ("homeTeam", "awayTeam")}
    if any(not isinstance(c, str) or not c for c in codes.values()) or len(set(codes.values())) != 2:
        raise ValueError("invalid_team_identities")
    seen = set()
    for side, other in (("homeTeam", "awayTeam"), ("awayTeam", "homeTeam")):
        shared = {**common, "team": codes[side], "opponent": codes[other], "home": side == "homeTeam"}
        section = box["playerByGameStats"][side]
        team_skaters = []
        for group, position in (("forwards", "F"), ("defense", "D")):
            for player in section[group]:
                pid = str(count(player["playerId"], 999999999))
                if pid == "0" or pid in seen:
                    raise ValueError("duplicate_or_invalid_player_game")
                seen.add(pid)
                toi = minutes(player["toi"])
                events = {k: count(player[field]) for k, field in
                          (("shots", "sog"), ("hits", "hits"), ("blocks", "blockedShots"))}
                if toi == 0:
                    if any(events.values()):
                        raise ValueError("events_without_exposure")
                    continue
                row = {**shared, "player_id": pid, "position": position, "minutes": toi, **events}
                team_skaters.append(row)
        if not team_skaters:
            raise ValueError("missing_team_skaters")
        result["skaters"].extend(team_skaters)
        starters = 0
        side_goalies = []
        for player in section["goalies"]:
            pid = str(count(player["playerId"], 999999999))
            if pid == "0" or pid in seen:
                raise ValueError("duplicate_or_invalid_goalie_game")
            seen.add(pid)
            toi = minutes(player["toi"])
            if toi == 0:
                continue
            sa = count(player["shotsAgainst"])
            ga = count(player["goalsAgainst"])
            saves = player["saves"]
            if isinstance(saves, str) and saves.count("/") == 1:
                left, right = saves.split("/")
                if not left.isdigit() or not right.isdigit() or int(right) != sa:
                    raise ValueError("ambiguous_goalie_saves")
                saves = int(left)
            saves = count(saves)
            if saves + ga != sa or toi > duration + .02:
                raise ValueError("goalie_exposure_or_count_inconsistency")
            starter = player.get("starter")
            if not isinstance(starter, bool):
                raise ValueError("missing_verified_goalie_start")
            starters += int(starter)
            side_goalies.append({**shared, "player_id": pid, "position": "G", "minutes": toi,
                                 "starter": starter, "shots_against": sa, "goals_against": ga,
                                 "saves": saves})
        if starters != 1 or sum(g["minutes"] for g in side_goalies) > duration + .05:
            raise ValueError("invalid_goalie_start_or_team_exposure")
        result["goalies"].extend(side_goalies)
        sf, against = count(box[side]["sog"]), count(box[other]["sog"])
        shot_difference = sf - sum(p["shots"] for p in team_skaters)
        faced = sum(p["shots_against"] for p in side_goalies)
        if faced > against:
            raise ValueError("goalie_shots_exceed_opponent_shots")
        result["teams"].append({**shared, "shots_for": sf, "shots_against": against,
                                "goalie_shots_against": faced,
                                "unassigned_shots_against": against - faced,
                                "hits": sum(p["hits"] for p in team_skaters),
                                "blocks": sum(p["blocks"] for p in team_skaters),
                                "attempts_for": None, "attempts_against": None,
                                "xgf": None, "xga": None, "xg_source": None,
                                "strength_splits": None})
        if shot_difference:
            # Team SOG and the sum of skater SOG are separate source fields.
            # A goalie shot, an unassigned credit or a source discrepancy can
            # produce a difference. Preserve it without guessing the cause or
            # modifying any individual count. Omit zero for legacy roundtrips.
            result["teams"][-1]["team_minus_skater_shots"] = shot_difference
    if pbp is not None:
        if str(pbp.get("id")) != str(gid):
            raise ValueError("play_by_play_game_identity_mismatch")
        result["play_by_play_source"] = {"url": f"{BASE}/gamecenter/{gid}/play-by-play",
                                         "sha256": digest(pbp)}
        # An OT/SO boxscore needs PBP to establish game duration even when
        # attempts were not requested. Do not turn that timing dependency into
        # a requirement to resolve every blocked-shot participant.
        if not include_attempts:
            result["play_by_play_source"]["usage"] = "game_duration_only"
            return validate_bundle(result)
        # The blocked-shot event owner can be ambiguous across source versions.
        # Resolve the shooter from the verified game roster, then cross-check
        # blocker identity. Never equate blocked shots with shots on goal.
        roster = {r["player_id"]: r["team"] for r in result["skaters"]}
        team_ids = {box[s]["id"]: codes[s] for s in codes}
        attempts = {code: 0 for code in codes.values()}
        for event in pbp.get("plays", []):
            if event.get("periodDescriptor", {}).get("periodType") == "SO":
                continue
            kind = event.get("typeDescKey")
            if kind not in ("shot-on-goal", "goal", "missed-shot", "blocked-shot"):
                continue
            details = event.get("details", {})
            if kind == "blocked-shot":
                code = roster.get(str(details.get("shootingPlayerId")))
                blocker = roster.get(str(details.get("blockingPlayerId")))
                if code is None or blocker is None or blocker == code:
                    raise ValueError(f"unresolved_blocked_attempt_identity:game={gid}:event={event.get('eventId')}")
            else:
                code = team_ids.get(details.get("eventOwnerTeamId"))
                if code is None:
                    raise ValueError("unresolved_shot_event_team")
            attempts[code] += 1
        for team in result["teams"]:
            if attempts[team["team"]] < team["shots_for"]:
                raise ValueError("play_by_play_attempts_below_verified_shots")
            team["attempts_for"] = attempts[team["team"]]
            team["attempts_against"] = attempts[team["opponent"]]
    return validate_bundle(result)


def validate_bundle(bundle):
    if bundle.get("schema") != VERSION or len(bundle.get("teams", [])) != 2:
        raise ValueError("invalid_context_bundle_schema")
    started = instant(bundle["start_time"])
    observed = instant(bundle["source"]["observed_at"])
    gid = bundle["game_id"]
    if (not isinstance(gid,str) or not re.fullmatch(r"\d{4}02\d{4}",gid)
            or bundle["season"] != gid[:4]):
        raise ValueError("invalid_context_game_identity")
    day=date.fromisoformat(bundle["game_date"])
    if (bundle["season"]!=str(day.year if day.month>=9 else day.year-1)
            or abs((started.date()-day).days)>1):
        raise ValueError("context_season_or_game_date_mismatch")
    duration = bundle["game_minutes"]
    if isinstance(duration,bool) or not isinstance(duration,(float,int)) or not math.isfinite(duration) or not 60 <= duration <= 65:
        raise ValueError("invalid_context_game_duration")
    if observed <= started+timedelta(minutes=duration):
        raise ValueError("observation_precedes_possible_game_completion")
    if (not isinstance(bundle["source"]["sha256"],str) or not re.fullmatch(r"[a-f0-9]{64}",bundle["source"]["sha256"])
            or bundle["source"]["url"] != f"{BASE}/gamecenter/{gid}/boxscore"):
        raise ValueError("missing_context_source_digest")
    teams = {r["team"]: r for r in bundle["teams"]}
    if len(teams) != 2:
        raise ValueError("duplicate_team_game")
    for table in ("teams", "skaters", "goalies"):
        seen = set()
        for row in bundle[table]:
            key = row["team"] if table == "teams" else row["player_id"]
            if key in seen:
                raise ValueError("duplicate_context_entity_game")
            seen.add(key)
            if any(row[k] != bundle[k] for k in ("game_id", "season", "start_time", "game_date", "game_minutes")):
                raise ValueError("context_parent_identity_mismatch")
            if row["team"] not in teams or row["opponent"] not in teams or row["team"] == row["opponent"]:
                raise ValueError("context_team_identity_mismatch")
            if not isinstance(row["home"], bool) or row["home"] != teams[row["team"]]["home"]:
                raise ValueError("inconsistent_home_venue")
            if table != "teams":
                if (not isinstance(row["player_id"],str) or not row["player_id"].isdigit()
                        or int(row["player_id"])<=0 or isinstance(row["minutes"],bool)
                        or not isinstance(row["minutes"],(float,int)) or not math.isfinite(row["minutes"])
                        or not 0 < row["minutes"] <= row["game_minutes"] + .02):
                    raise ValueError("invalid_context_player_or_exposure")
            if table == "goalies":
                for field in ("saves","shots_against","goals_against"):
                    count(row[field])
                if row["saves"]+row["goals_against"] != row["shots_against"] or not isinstance(row["starter"],bool):
                    raise ValueError("invalid_persisted_goalie_counts")
            elif table == "skaters":
                if row["position"] not in ("F","D"):
                    raise ValueError("invalid_skater_position")
                for field in ("shots","hits","blocks"):
                    count(row[field])
            else:
                for field in ("shots_for","shots_against","goalie_shots_against","unassigned_shots_against","hits","blocks"):
                    count(row[field])
                for field in ("attempts_for","attempts_against"):
                    if row[field] is not None:
                        count(row[field],400)
    if sum(int(r["home"]) for r in bundle["teams"]) != 1:
        raise ValueError("invalid_opposing_venues")
    for team in bundle["teams"]:
        opposite=teams[team["opponent"]]
        goalies=[r for r in bundle["goalies"] if r["team"]==team["team"]]
        skaters=[r for r in bundle["skaters"] if r["team"]==team["team"]]
        difference=team.get("team_minus_skater_shots",0)
        if isinstance(difference,bool) or not isinstance(difference,int) or abs(difference)>200:
            raise ValueError("invalid_team_skater_shot_difference")
        if (team["shots_for"]!=opposite["shots_against"]
                or sum(g["shots_against"] for g in goalies)!=team["goalie_shots_against"]
                or team["goalie_shots_against"]+team["unassigned_shots_against"]!=team["shots_against"]
                or sum(s["shots"] for s in skaters)+difference!=team["shots_for"]
                or sum(s["hits"] for s in skaters)!=team["hits"]
                or sum(s["blocks"] for s in skaters)!=team["blocks"]
                or sum(int(g["starter"]) for g in goalies)!=1
                or sum(g["minutes"] for g in goalies)>duration+.05):
            raise ValueError("persisted_context_counts_do_not_reconcile")
    return bundle


def save_bundle(root, bundle):
    validate_bundle(bundle)
    path = Path(root) / "data/bayesian_warehouse/nhl_context/games" / bundle["season"] / (bundle["game_id"] + ".json")
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        # A repeat retrieval may have a later timestamp, never replace the first.
        comparable = json.loads(encode(bundle))
        comparable["source"]["observed_at"] = old["source"]["observed_at"]
        if comparable != old:
            raise ValueError("context_source_revision_requires_review")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(encode(bundle) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return True


def archive_source(root, payload):
    """Content-addressed raw source archive, retained separately from entities."""
    sha=digest(payload)
    path=Path(root)/"data/bayesian_warehouse/nhl_context/sources"/(sha+".json.gz")
    if path.exists():
        with gzip.open(path,"rt",encoding="utf-8") as handle:
            if digest(json.load(handle))!=sha:
                raise ValueError("raw_context_source_archive_corrupt")
        return sha
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp")
    temp.write_bytes(gzip.compress((encode(payload)+"\n").encode(),mtime=0))
    os.replace(temp,path)
    return sha


def check_source_archive(root, source):
    path=Path(root)/"data/bayesian_warehouse/nhl_context/sources"/(source["sha256"]+".json.gz")
    if not path.exists():
        raise ValueError("missing_raw_context_source_archive")
    with gzip.open(path,"rt",encoding="utf-8") as handle:
        if digest(json.load(handle))!=source["sha256"]:
            raise ValueError("raw_context_source_archive_corrupt")


def verify_bundle_source(root,bundle):
    """Rebuild every normalized field from archived authoritative payloads."""
    def read(source):
        check_source_archive(root,source)
        path=Path(root)/"data/bayesian_warehouse/nhl_context/sources"/(source["sha256"]+".json.gz")
        with gzip.open(path,"rt",encoding="utf-8") as handle:
            return json.load(handle)
    box=read(bundle["source"])
    pbp=read(bundle["play_by_play_source"]) if "play_by_play_source" in bundle else None
    source=bundle.get("play_by_play_source",{})
    usage=source.get("usage")
    if usage not in (None,"game_duration_only"):
        raise ValueError("unknown_play_by_play_source_usage")
    rebuilt=normalize(box,observed_at=bundle["source"]["observed_at"],pbp=pbp,
                      include_attempts=usage!="game_duration_only")
    if rebuilt!=bundle:
        raise ValueError("normalized_bundle_disagrees_with_archived_source")
    return True


def read_bundles(root):
    bundles = [validate_bundle(json.loads(p.read_text(encoding="utf-8"))) for p in
               sorted((Path(root) / "data/bayesian_warehouse/nhl_context/games").glob("*/*.json"))]
    ids = [b["game_id"] for b in bundles]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_context_game")
    return sorted(bundles, key=lambda b: (b["start_time"], b["game_id"]))


class HistoryIndex:
    """Bisected game-time index; publication filtering before rolling."""

    def __init__(self, bundles, *, policy="recorded"):
        if policy not in ("recorded", "retrospective_next_day"):
            raise ValueError("unsupported_availability_policy")
        self.policy = policy
        self.rows = defaultdict(list)
        self.team_cache = {}
        for bundle in bundles:
            validate_bundle(bundle)
            start = instant(bundle["start_time"])
            available = instant(bundle["source"]["observed_at"])
            if policy == "retrospective_next_day":
                # Explicit approximation for core boxscore backfills only.
                available = start + timedelta(hours=12)
            for table in ("teams", "skaters", "goalies"):
                for row in bundle[table]:
                    key = (table, row["team"] if table == "teams" else row["player_id"])
                    self.rows[key].append((available, start, row))
        self.times = {}
        for key, values in self.rows.items():
            values.sort(key=lambda v: (v[1], v[2]["game_id"]))
            self.times[key] = [v[1] for v in values]

    def before(self, table, entity, at, *, exclude_game=None, window=20):
        if not isinstance(window,int) or isinstance(window,bool) or window < 1:
            raise ValueError("invalid_history_window")
        cachekey=(entity,at,exclude_game,window)
        if table=="teams" and cachekey in self.team_cache:
            return self.team_cache[cachekey]
        key = (table, entity)
        target = instant(at)
        end = bisect.bisect_left(self.times.get(key, []), target)
        values = self.rows.get(key, [])
        chosen = []
        # Usually scan just `window` entries. Late publications are skipped;
        # rolling windows stay ordered by event time, never retrieval order.
        for i in range(end-1, -1, -1):
            available, _, row = values[i]
            if available < target and row["game_id"] != exclude_game:
                chosen.append(row)
                if len(chosen) == window:
                    break
        result = list(reversed(chosen))
        if table=="teams":
            self.team_cache[cachekey]=result
        return result


def save_matchup(root, snapshot):
    """Independent, immutable pregame snapshots; unresolved status stays null.

    Existing research collectors can call this after identity/source checks.
    No inference of starts from tonight's final boxscore is permitted.
    """
    required=("game_id","season","team","opponent","home","start_time","snapshot_at",
              "starter_player_id","starter_status","injuries","source_url","source_sha256")
    if any(k not in snapshot for k in required):
        raise ValueError("incomplete_pregame_snapshot")
    if (not re.fullmatch(r"\d{4}02\d{4}",str(snapshot["game_id"]))
            or str(snapshot["season"])!=str(snapshot["game_id"])[:4]
            or not re.fullmatch(r"[A-Z]{2,4}",snapshot["team"])
            or not re.fullmatch(r"[A-Z]{2,4}",snapshot["opponent"])
            or snapshot["team"]==snapshot["opponent"] or not isinstance(snapshot["home"],bool)):
        raise ValueError("invalid_pregame_snapshot_identity")
    if instant(snapshot["snapshot_at"]) >= instant(snapshot["start_time"]):
        raise ValueError("snapshot_not_pregame")
    if snapshot["starter_status"] not in ("confirmed","expected","unknown"):
        raise ValueError("invalid_starter_evidence_status")
    if snapshot["starter_status"] in ("confirmed","expected") and (
            not isinstance(snapshot["starter_player_id"],str) or not snapshot["starter_player_id"].isdigit()):
        raise ValueError("starter_evidence_missing_identity")
    if (not isinstance(snapshot["injuries"],list) or not snapshot["source_url"].startswith("https://")
            or not re.fullmatch(r"[a-f0-9]{64}",snapshot["source_sha256"])):
        raise ValueError("missing_pregame_source_evidence")
    path=(Path(root)/"data/bayesian_warehouse/nhl_context/matchups"/str(snapshot["game_id"])/
          (snapshot["team"]+"-"+digest(snapshot)+".json"))
    if path.exists():
        return False
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(encode({**snapshot,"schema":"nhl-context-matchup-v1",
                           "recorded_at":datetime.now(timezone.utc).isoformat()})+"\n",encoding="utf-8")
    return True


def collect(root, *, game_ids, fetcher=None, with_attempts=False):
    """Bounded, resumable by game ID. No changes to existing history branches."""
    if fetcher is None:
        from nhl_bayesian_backfill import fetch as fetcher
    inserted = 0
    for gid in game_ids:
        if not str(gid).isdigit() or len(str(gid)) != 10 or str(gid)[4:6] != "02":
            raise ValueError("invalid_collection_game_id")
        path = Path(root) / "data/bayesian_warehouse/nhl_context/games" / str(gid)[:4] / (str(gid) + ".json")
        if path.exists():
            existing = validate_bundle(json.loads(path.read_text(encoding="utf-8")))
            check_source_archive(root,existing["source"])
            if "play_by_play_source" in existing:
                check_source_archive(root,existing["play_by_play_source"])
            if with_attempts and existing["teams"][0]["attempts_for"] is None:
                raise ValueError("existing_bundle_missing_attempts_use_separate_dataset_root")
            continue
        box = fetcher(f"{BASE}/gamecenter/{gid}/boxscore")
        if str(box.get("id")) != str(gid):
            raise ValueError("requested_game_identity_mismatch")
        pbp = None
        if with_attempts or box.get("periodDescriptor", {}).get("number") != 3:
            pbp = fetcher(f"{BASE}/gamecenter/{gid}/play-by-play")
        # Retain fetched evidence even if a later schema/reconciliation check
        # rejects this game, so its actual payload can be inspected offline.
        archive_source(root,box)
        if pbp is not None:
            archive_source(root,pbp)
        try:
            bundle = normalize(box, observed_at=datetime.now(timezone.utc).isoformat(), pbp=pbp,
                               include_attempts=with_attempts)
        except (ValueError,KeyError) as exc:
            raise ValueError(f"collection_game={gid}: {exc}") from exc
        inserted += int(save_bundle(root, bundle))
    return {"inserted_games": inserted, "requested_games": len(game_ids)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--game-ids", type=Path, required=True, help="JSON list of official regular-season game IDs")
    p.add_argument("--with-attempts", action="store_true", help="Also fetch PBP for blocks opportunity features")
    args = p.parse_args(argv)
    print(encode(collect(args.root, game_ids=json.loads(args.game_ids.read_text(encoding="utf-8")), with_attempts=args.with_attempts)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
