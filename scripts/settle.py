"""Fill actual_stat and outcome on past-game snapshot rows from public box scores."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fetch_slate as fs
import pickem_math as pm
from nfl_stat_definitions import combined_tackles_assists

LookupFn = Callable[[str, str, str, str], float | None]


@dataclass
class Fetchers:
    """Injectable lookup; NHL requires full player/game identity for settlement."""

    lookup: LookupFn
    lookup_record: Callable[[dict], float | None] | None = None

    @classmethod
    def from_tables(cls, tables: dict) -> "Fetchers":
        def lookup(sport: str, player: str, stat: str, game_date: str) -> float | None:
            bucket = tables.get(sport) or {}
            key = (game_date, player.strip().casefold(), stat.strip().casefold())
            value = bucket.get(key)
            if value is None:
                return None
            return float(value)

        return cls(lookup=lookup)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_past_game(game_date: str, as_of: str) -> bool:
    return str(game_date)[:10] < str(as_of)[:10]


def _nba_value(games, stat: str, game_date: str) -> float | None:
    if not games:
        return None
    target = game_date[:10]
    for game in games:
        from usage_baseline import local_day
        try:when=local_day(str(game.get("when") or "")).isoformat()
        except ValueError:continue
        if when != target:
            continue
        minutes=fs._num(game.get("minutes"))
        if minutes is None or minutes<=0:return None
        parts = fs.NBA_COMBOS.get(stat)
        if parts:
            values = [game.get(key) for key in parts]
            if any(value is None for value in values):
                return None
            return float(sum(values))
        key = fs.NBA_LOG_KEYS.get(stat, stat if stat in ("points", "rebounds", "assists", "threes") else "")
        if not key:
            return None
        value = game.get(key)
        return None if value is None else float(value)
    return None


def _nhl_value(games, stat: str, game_date: str) -> float | None:
    if not games:
        return None
    target = game_date[:10]
    for game in games:
        if str(game.get("gameDate") or "")[:10] != target:
            continue
        toi=fs.parse_toi_seconds(game.get("toi"))
        if toi is None or toi<=0:return None
        value = fs.nhl_stat_value(game, stat)
        return None if value is None else float(value)
    return None


def _nfl_column(stat: str) -> str | None:
    stat_key = stat.strip().casefold()
    for label, column in fs.NFL_COUNTING:
        if label.casefold() == stat_key:
            return column
    if stat_key == "tackles + assists":
        return None
    return None


def _nfl_value(week_rows, schedules, player: str, stat: str, game_date: str) -> float | None:
    if not week_rows:
        return None
    games=[g for g in schedules or [] if fs._date_text(g.get('gameday') or g.get('game_date'))==game_date
           and fs._reg_row(g) and fs._num(g.get('result')) is not None]
    if not games:return None
    stat=stat.strip().casefold()
    column='def_tackles_solo' if stat=='tackles' else _nfl_column(stat)
    if column is None and stat!='tackles + assists':return None
    matched=[]
    for row in week_rows:
        name=str(row.get('player_display_name') or row.get('player') or '').strip().casefold()
        if name!=player.strip().casefold():continue
        team=fs._row_team(row)
        def same_game(game):
            if row.get('game_id') and game.get('game_id'):return str(row['game_id'])==str(game['game_id'])
            return (str(row.get('season'))==str(game.get('season')) and str(row.get('week'))==str(game.get('week'))
                    and team in (game.get('home_team'),game.get('away_team')))
        if not any(same_game(g) for g in games):continue
        if column:
            value = fs._num(row.get(column))
        elif stat == "tackles + assists":
            combined = combined_tackles_assists(row)
            value = float(combined) if combined is not None else None
        else:
            value = None
        if value is not None:
            matched.append((str(row.get("player_id") or row.get("player_name") or name), float(value)))
    unique=set(matched)
    return next(iter(unique))[1] if len(unique)==1 else None


def _nhl_item_name(item: dict) -> str:
    raw_name = item.get("name")
    if isinstance(raw_name, dict):
        raw_name = raw_name.get("default")
    if raw_name:
        return str(raw_name).strip()
    first = item.get("firstName")
    if isinstance(first, dict):
        first = first.get("default")
    last = item.get("lastName")
    if isinstance(last, dict):
        last = last.get("default")
    return f"{first or ''} {last or ''}".strip()


class _CompletedNHLBoxscores:
    """Official final player-game stats, keyed by stable identity, never search names.

    Read the date-scoped, source-validated population snapshot already collected
    by the morning pipeline. When it is absent (for standalone CLI settlement),
    read the completed official NHL scoreboard and gamecenter boxscores directly.
    No guessed zero is recorded for absent, scratched or unverified players.
    """
    def __init__(self, fetch, root: Path | None = None):
        self.fetch = fetch
        self.root = Path(root) if root else SCRIPT_DIR.parent
        self._by_day = {}

    def _load(self, day: str):
        import population_history as hist
        import population_normalizers as norm
        import population_backfill as backfill

        local = self.root / "data/live_pool_staging/populations" / (day + ".jsonl")
        receipt_path = self.root / "reports" / ("live_population_collect_" + day + ".json")
        records = []
        if local.exists() or receipt_path.exists():
            if not (local.is_file() and receipt_path.is_file()):
                raise ValueError("NHL_LOCAL_POPULATION_OR_RECEIPT_MISSING")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            nhl = (receipt.get("sports") or {}).get("NHL") or {}
            completed = (receipt.get("completed_games") or {}).get("NHL")
            if (receipt.get("game_date") != day
                    or "NHL" in (receipt.get("errors") or {})
                    or not isinstance(completed,int) or completed < 1
                    or nhl.get("games") != completed):
                raise ValueError("NHL_LOCAL_COMPLETED_SOURCE_NOT_VERIFIED")
            with local.open("rt",encoding="utf-8") as stream:
                for line in stream:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    if record.get("sport") != "NHL":
                        continue
                    hist.validate(record)
                    if record["game_date"] != day:
                        raise ValueError("NHL_LOCAL_GAME_DATE_MISMATCH")
                    records.append(record)
            if len({r["game_id"] for r in records}) != completed:
                raise ValueError("NHL_LOCAL_COMPLETED_GAME_COVERAGE_MISMATCH")
        else:
            # Standalone fallback uses the same official endpoints and strict
            # completed-game normalizer as the source-verified collector.
            board = self.fetch(norm.NHL_BASE + "/score/" + day, timeout=fs.ESPN_TIMEOUT)
            ids = backfill.nhl_games(board)
            for gid in ids:
                raw = self.fetch(norm.NHL_BASE + "/gamecenter/" + str(gid) + "/boxscore",
                                 timeout=fs.ESPN_TIMEOUT)
                records.extend(norm.nhl_game(raw,day,expected_id=gid))
            if not ids:
                raise ValueError("NHL_NO_FINAL_REGULAR_SEASON_GAMES_ON_DATE")
        indexed = {}
        for record in records:
            key = (record["game_id"],record["player_id"],record["stat"])
            if key in indexed and indexed[key] != record:
                raise ValueError("NHL_CONFLICTING_OFFICIAL_PLAYER_GAME_STAT")
            indexed[key] = record
        self._by_day[day] = list(indexed.values())
        return self._by_day[day]

    def lookup(self, snapshot: dict):
        if str(snapshot.get("sport") or "").upper() != "NHL":
            raise ValueError("NHL_IDENTITY_LOOKUP_SPORT_MISMATCH")
        day = str(snapshot.get("game_date") or "")
        # A missing ID cannot be guessed via ambiguous name searches.
        player_id = str(snapshot.get("player_id") or "").strip()
        team = str(snapshot.get("team") or "").strip().upper()
        opponent = str(snapshot.get("opponent") or "").strip().upper()
        stat = str(snapshot.get("stat") or "").strip().lower()
        # Forecast market label differs from the official count statistic.
        # Keep the snapshot label untouched; translate only at source lookup.
        if stat == "goalie saves":
            stat = "saves"
        if not player_id or not team or not opponent or team == opponent:
            return None
        records = self._by_day.get(day)
        if records is None:
            records = self._load(day)
        # Only an explicit official NHL event identity is compared to the
        # gamecenter ID. Provider odds-event IDs are not NHL game IDs.
        namespace = str(snapshot.get("event_id_namespace") or "").lower()
        eid = str(snapshot.get("event_id") or "").strip()
        official_eid = eid if namespace in ("nhl","nhl_game","nhl_gamecenter") and (
            eid.isdigit() and len(eid) == 10) else None
        matches = [r for r in records
                   if r["player_id"] == player_id and r["stat"] == stat
                   and r["team"].upper() == team and r["opponent"].upper() == opponent
                   and (official_eid is None or r["game_id"] == official_eid)]
        if len(matches) > 1:
            raise ValueError("NHL_AMBIGUOUS_OFFICIAL_PLAYER_GAME_MATCH")
        if not matches:
            return None
        return float(matches[0]["value"])


class _LiveCache:
    def __init__(self, fetch):
        self.fetch = fetch
        self._nba_ids_by_season: dict[int, dict[str, str]] = {}
        self._nba_logs: dict[tuple[str, int], list] = {}
        self._nhl_logs: dict[tuple[str, str], list] = {}
        self._nhl_ids: dict[str, str | None] = {}
        self._nfl_by_season: dict[int, tuple[list, list]] = {}

    def _nba_index(self, game_date: str) -> dict[str, str]:
        season_year = fs.nba_espn_season_year(game_date)
        if season_year in self._nba_ids_by_season:
            return self._nba_ids_by_season[season_year]
        payload = self.fetch(fs.espn_nba_counting_url(season_year), timeout=fs.ESPN_TIMEOUT)
        found = {}
        for athlete in (payload or {}).get("athletes") or []:
            if not isinstance(athlete, dict):
                continue
            athlete_info = athlete.get("athlete") if isinstance(athlete.get("athlete"), dict) else athlete
            name = str((athlete_info or {}).get("displayName") or "").strip()
            player_id = (athlete_info or {}).get("id")
            if name and player_id not in (None, ""):
                found[name.casefold()] = str(player_id)
        self._nba_ids_by_season[season_year] = found
        return found

    def nba(self, player: str, stat: str, game_date: str) -> float | None:
        index = self._nba_index(game_date)
        player_id = index.get(player.strip().casefold())
        if not player_id:
            return None
        season_year = fs.nba_espn_season_year(game_date)
        key = (player_id, season_year)
        if key not in self._nba_logs:
            games = fs.load_espn_gamelog(self.fetch, player_id, season_year, [])
            self._nba_logs[key] = games or []
        return _nba_value(self._nba_logs[key], stat, game_date)

    def _nhl_player_id(self, player: str) -> str | None:
        key = player.strip().casefold()
        if key in self._nhl_ids:
            return self._nhl_ids[key]
        url = f"{fs.NHL_WEB}/search/player?culture=en-us&limit=20&q={urllib.parse.quote(player)}"
        try:
            payload = self.fetch(url, timeout=fs.ESPN_TIMEOUT)
        except Exception:
            self._nhl_ids[key] = None
            return None
        for item in (payload or {}).get("players") or []:
            if not isinstance(item, dict):
                continue
            name = _nhl_item_name(item)
            if name.casefold() == key and item.get("id") not in (None, ""):
                player_id = str(item["id"])
                self._nhl_ids[key] = player_id
                return player_id
        self._nhl_ids[key] = None
        return None

    def nhl(self, player: str, stat: str, game_date: str) -> float | None:
        player_id = self._nhl_player_id(player)
        if not player_id:
            return None
        season = fs.season_id_from_date(game_date)
        key = (player_id, season)
        if key not in self._nhl_logs:
            url = fs.nhl_game_log_url(player_id, season)
            try:
                payload = self.fetch(url, timeout=fs.ESPN_TIMEOUT)
            except Exception:
                payload = None
            self._nhl_logs[key] = fs.parse_nhl_game_log(payload) or []
        return _nhl_value(self._nhl_logs[key], stat, game_date)

    def nfl(self, player: str, stat: str, game_date: str) -> float | None:
        season = int(fs.nfl_season_from_date(game_date))
        if season not in self._nfl_by_season:
            try:
                import nflreadpy as nfl
            except ImportError:
                return None
            schedules = nfl.load_schedules(seasons=[season])
            week_stats = nfl.load_player_stats(seasons=[season], summary_level="week")
            self._nfl_by_season[season] = (
                fs.frame_to_rows(week_stats),
                fs.frame_to_rows(schedules),
            )
        week_rows, sched_rows = self._nfl_by_season[season]
        return _nfl_value(week_rows, sched_rows, player, stat, game_date)


def default_fetchers(fetch=None, *, root: Path | None = None) -> Fetchers:
    fetch = fetch or fs.fetch_json
    cache = _LiveCache(fetch)
    nhl_final = _CompletedNHLBoxscores(fetch,root=root)

    def lookup(sport: str, player: str, stat: str, game_date: str) -> float | None:
        sport = sport.strip().upper()
        if sport == "NBA":
            return cache.nba(player, stat, game_date)
        if sport == "NHL":
            # Never fall back to an unverified player-name season gamelog.
            raise ValueError("NHL_SETTLEMENT_REQUIRES_IDENTITY_ROW")
        if sport == "NFL":
            return cache.nfl(player, stat, game_date)
        return None

    return Fetchers(lookup=lookup, lookup_record=nhl_final.lookup)


def settle_row(row: dict, actual: float | None, *, settled_at: str | None = None) -> tuple[dict, bool]:
    if row.get("actual_stat") is not None:
        return row, False
    if actual is None:
        return row, False
    updated = dict(row)
    updated["actual_stat"] = actual
    updated["outcome"] = pm.settlement_outcome(
        updated["side"], updated["reference_line"], actual,
    )
    updated["settled_at"] = settled_at or utc_now_iso()
    return updated, True


def settle_rows(
    rows: list[dict],
    *,
    as_of: str,
    fetchers: Fetchers,
    settled_at: str | None = None,
) -> tuple[list[dict], int]:
    settled = 0
    out = []
    stamp = settled_at or utc_now_iso()
    for row in rows:
        if row.get("actual_stat") is not None:
            out.append(row)
            continue
        game_date = str(row.get("game_date") or "")
        if not is_past_game(game_date, as_of):
            out.append(row)
            continue
        if str(row.get("sport") or "").upper() == "NHL" and fetchers.lookup_record:
            actual = fetchers.lookup_record(row)
        else:
            actual = fetchers.lookup(
                str(row.get("sport") or ""),
                str(row.get("player") or ""),
                str(row.get("stat") or ""),
                game_date,
            )
        updated, changed = settle_row(row, actual, settled_at=stamp)
        if changed:
            settled += 1
        out.append(updated)
    return out, settled


def settle_file(
    path: Path,
    *,
    as_of: str,
    fetchers: Fetchers,
    dry_run: bool = False,
) -> int:
    path = Path(path)
    with pm.locked_snapshot(path, create=False) as (handle, text):
        rows = [row for _line_no, _line, row in pm.iter_snapshot_lines(text)]
        updated_rows, settled = settle_rows(rows, as_of=as_of, fetchers=fetchers)
        if settled and not dry_run:
            payload = "".join(pm.dump_snapshot(row) for row in updated_rows)
            handle.seek(0)
            handle.truncate(0)
            handle.write(payload)
            handle.flush()
            import os

            os.fsync(handle.fileno())
    return settled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Settle prop snapshots from box scores.")
    parser.add_argument("--path", default=str(pm.DEFAULT_SNAPSHOT_PATH))
    parser.add_argument("--as-of", default=fs.eastern_today(), help="YYYY-MM-DD; settle games before this date")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        count = settle_file(
            Path(args.path),
            as_of=args.as_of,
            fetchers=default_fetchers(),
            dry_run=args.dry_run,
        )
    except pm.PickemError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"settled={count} path={args.path} as_of={args.as_of} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
