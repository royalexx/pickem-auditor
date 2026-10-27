#!/usr/bin/env python3
"""Dependency-free official NHL historical boxscore collector."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BASE = "https://api-web.nhle.com/v1"
FINAL_STATES = {"FINAL", "OFF"}

def fetch_json(url, retries=3, timeout=15):
    for attempt in range(retries):
        try:
            request = Request(url, headers={
                "User-Agent": "pickem-auditor-history/1.0",
                "Accept": "application/json"
            })
            with urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP_{response.status}")
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(
                    f"SOURCE_UNAVAILABLE {url}: {type(exc).__name__}: {exc}"
                ) from exc
            time.sleep(2 ** attempt)

def normalize_game(raw, date):
    if not isinstance(raw, dict) or not raw.get("id"):
        raise ValueError("NHL boxscore has no game ID")
    by_team = raw.get("playerByGameStats") or {}
    players = []
    for side in ("awayTeam", "homeTeam"):
        team = raw.get(side) or {}
        team_code = team.get("abbrev") or team.get("abbreviation")
        rows = by_team.get(side) or {}
        for position in ("forwards", "defense", "goalies"):
            for player in rows.get(position) or []:
                if player.get("playerId") is None:
                    continue
                players.append({
                    "player_id": player["playerId"],
                    "team": team_code, "position": position,
                    "source_stats": player
                })
    if not players:
        raise ValueError("NHL completed boxscore has no player records")
    return {
        "source": "NHL official gamecenter boxscore",
        "source_url": f"{BASE}/gamecenter/{raw['id']}/boxscore",
        "game_id": raw["id"], "game_date": date,
        "state": raw.get("gameState"),
        "away_team": (raw.get("awayTeam") or {}).get("abbrev"),
        "home_team": (raw.get("homeTeam") or {}).get("abbrev"),
        "players": players
    }

def collect(dates, root):
    receipt = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "dates": dates, "status": "running",
        "games_seen": 0, "completed_games": 0,
        "player_rows": 0, "written_games": 0,
        "errors": [], "files": []
    }
    for day in dates:
        try:
            board = fetch_json(f"{BASE}/score/{day}")
            games = board.get("games")
            if not isinstance(games, list):
                raise ValueError("NHL scoreboard response lacks games array")
            receipt["games_seen"] += len(games)
            for game in games:
                if game.get("gameState") not in FINAL_STATES:
                    continue
                game_id = game.get("id")
                if not game_id:
                    raise ValueError("NHL scoreboard game missing id")
                raw = fetch_json(f"{BASE}/gamecenter/{game_id}/boxscore")
                item = normalize_game(raw, day)
                receipt["completed_games"] += 1
                receipt["player_rows"] += len(item["players"])
                path = root / "data" / "nhl" / "games" / day / f"{game_id}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = json.dumps(
                    item, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ) + "\n"
                if not path.exists() or path.read_text(encoding="utf-8") != payload:
                    path.write_text(payload, encoding="utf-8")
                    receipt["written_games"] += 1
                receipt["files"].append(str(path.relative_to(root)))
        except (RuntimeError, ValueError) as exc:
            receipt["errors"].append({"date": day, "error": str(exc)})
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    receipt["status"] = (
        "success" if not receipt["errors"]
        else "partial" if receipt["completed_games"] else "blocked"
    )
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Toronto calendar date, defaults to today")
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if not 1 <= args.days <= 14:
        parser.error("--days must be between 1 and 14")
    selected = (
        datetime.strptime(args.date, "%Y-%m-%d").date() if args.date
        else datetime.now(ZoneInfo("America/Toronto")).date()
    )
    dates = [
        (selected - timedelta(days=offset)).isoformat()
        for offset in reversed(range(args.days))
    ]
    result = collect(dates, args.root)
    out = args.root / "reports" / "nhl_collection_receipt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 2

if __name__ == "__main__":
    sys.exit(main())
