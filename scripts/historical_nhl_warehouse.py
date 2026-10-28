"""Verified NHL shots/TOI warehouse; no odds, pregame ranks, or production mutations."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import os
from datetime import date
from pathlib import Path

VERSION = "nhl-shots-warehouse-v1"
ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api-web.nhle.com/v1"
COMPLETE = {"FINAL", "OFF"}


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def _toi(value):
    if not isinstance(value, str):
        raise ValueError("missing_skater_toi")
    parts = value.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError("unparseable_skater_toi")
    minute, second = map(int, parts)
    if second >= 60 or minute >= 65:
        raise ValueError("invalid_skater_toi")
    return minute + second / 60


def canonical_game(raw, game_date):
    """Fail closed on malformed data. Never infer an unreported player/game."""
    day = date.fromisoformat(game_date)
    if not isinstance(raw, dict) or not isinstance(raw.get("id"), int):
        raise ValueError("missing_nhl_game_id")
    gid = raw["id"]
    if gid // 1000000 != day.year and not (day.month <= 8 and gid // 1000000 == day.year - 1):
        raise ValueError("nhl_season_date_mismatch")
    if (gid // 10000) % 100 != 2:  # regular season only
        raise ValueError("non_regular_season_game")
    if raw.get("gameState") not in COMPLETE:
        raise ValueError("game_not_final")
    stats = raw.get("playerByGameStats")
    if not isinstance(stats, dict):
        raise ValueError("missing_skater_stats")
    codes = {}
    for side in ("awayTeam", "homeTeam"):
        team = raw.get(side)
        if not isinstance(team, dict):
            raise ValueError("missing_team")
        code = team.get("abbrev")
        if isinstance(code, dict):
            code = code.get("default")
        if not isinstance(code, str) or not 2 <= len(code) <= 4:
            raise ValueError("invalid_team_code")
        codes[side] = code
    if codes["awayTeam"] == codes["homeTeam"]:
        raise ValueError("identical_teams")
    source_hash = digest(raw)
    rows = []
    seen = set()
    for side, opponent_side in (("awayTeam", "homeTeam"), ("homeTeam", "awayTeam")):
        section = stats.get(side)
        if not isinstance(section, dict):
            raise ValueError("missing_side_skater_stats")
        for group, label in (("forwards", "F"), ("defense", "D")):
            players = section.get(group)
            if not isinstance(players, list):
                raise ValueError("missing_position_group")
            for athlete in players:
                if not isinstance(athlete, dict) or isinstance(athlete.get("playerId"), bool):
                    raise ValueError("invalid_player")
                ident = athlete.get("playerId")
                shots = athlete.get("sog")
                if not isinstance(ident, int) or ident <= 0 or isinstance(shots, bool) or not isinstance(shots, int) or not 0 <= shots <= 35:
                    raise ValueError("invalid_player_shots")
                if ident in seen:
                    raise ValueError("duplicate_player_game")
                seen.add(ident)
                minutes = _toi(athlete.get("toi"))
                if minutes == 0:
                    if shots:
                        raise ValueError("shots_without_ice_time")
                    continue   # nonappearance, not a fabricated zero-shot game
                rows.append({
                    "version": VERSION, "sport": "NHL", "stat": "shots on goal",
                    "game_id": str(gid), "game_date": game_date,
                    "season": str(gid)[:4], "player_id": str(ident),
                    "position": label, "team": codes[side],
                    "opponent": codes[opponent_side], "home": side == "homeTeam",
                    "shots": shots, "toi_minutes": round(minutes, 6),
                    "source_url": f"{BASE}/gamecenter/{gid}/boxscore",
                    "source_sha256": source_hash,
                })
    if len(rows) < 10:
        raise ValueError("incomplete_nhl_skater_boxscore")
    return rows


def shard_path(root, day):
    return Path(root) / "data/bayesian_warehouse/nhl_shots" / (day[:7] + ".jsonl.gz")


def _check_row(row):
    required = ("version", "game_id", "game_date", "season", "player_id", "team",
                "opponent", "position", "shots", "toi_minutes", "source_sha256", "source_url")
    if not isinstance(row, dict) or any(k not in row for k in required):
        raise ValueError("warehouse_row_fields_missing")
    if row["version"] != VERSION or row["position"] not in ("F", "D"):
        raise ValueError("unsupported_warehouse_record")
    date.fromisoformat(row["game_date"])
    if not isinstance(row["player_id"], str) or not row["player_id"].isdigit() or len(row["source_sha256"]) != 64:
        raise ValueError("warehouse_record_identity_invalid")
    if isinstance(row["shots"], bool) or not isinstance(row["shots"], int) or not 0 <= row["shots"] <= 35:
        raise ValueError("warehouse_record_shots_invalid")
    if isinstance(row["toi_minutes"], bool) or not isinstance(row["toi_minutes"], (int, float)) or not math.isfinite(row["toi_minutes"]) or not 0 < row["toi_minutes"] < 65:
        raise ValueError("warehouse_record_workload_invalid")


def read_shard(path):
    if not Path(path).exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        data = [json.loads(line) for line in stream if line.strip()]
    keys = set()
    games = {}
    for item in data:
        _check_row(item)
        key = (item["game_id"], item["player_id"])
        if key in keys:
            raise ValueError("duplicate_warehouse_player_game")
        keys.add(key)
        if item["game_date"][:7] != Path(path).name[:7]:
            raise ValueError("warehouse_shard_month_mismatch")
        previous = games.setdefault(item["game_id"], item["source_sha256"])
        if previous != item["source_sha256"]:
            raise ValueError("inconsistent_game_source_digest")
    return data


def add_game(root, rows):
    if not rows:
        raise ValueError("no_completed_skaters")
    for row in rows:
        _check_row(row)
    day = rows[0]["game_date"]
    gid = rows[0]["game_id"]
    if any(row["game_date"] != day or row["game_id"] != gid for row in rows):
        raise ValueError("mixed_game_insert")
    path = shard_path(root, day)
    old = read_shard(path)
    existing = [r for r in old if r["game_id"] == gid]
    if existing:
        if sorted(map(encode, existing)) != sorted(map(encode, rows)):
            raise ValueError("historical_source_revision_requires_review")
        return False
    merged = sorted(old + rows, key=lambda r: (r["game_date"], r["game_id"], r["player_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = ("".join(encode(r) + "\n" for r in merged)).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0, filename="") as gz:
        gz.write(raw)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(buf.getvalue())
    os.replace(temp, path)
    return True


def read_history(root, *, before, min_games=0, max_seasons=None):
    """Filter every observation by strictly earlier game dates BEFORE inference."""
    cutoff = date.fromisoformat(before)
    rows = []
    location = Path(root) / "data/bayesian_warehouse/nhl_shots"
    for path in sorted(location.glob("????-??.jsonl.gz")):
        if path.name[:7] > before[:7]:
            continue
        for row in read_shard(path):
            if date.fromisoformat(row["game_date"]) >= cutoff:
                continue
            rows.append(row)
    if max_seasons is not None:
        eligible = sorted({r["season"] for r in rows})[-max_seasons:]
        rows = [r for r in rows if r["season"] in eligible]
    # One immutable player-game only. A player's team may change, not their ID.
    identities = [(r["game_id"], r["player_id"]) for r in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("cross_shard_duplicate_player_game")
    rows.sort(key=lambda r: (r["game_date"], r["game_id"], r["player_id"]))
    if len(rows) < min_games:
        raise ValueError("insufficient_historical_skater_games")
    return rows
