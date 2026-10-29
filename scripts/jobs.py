"""Scheduled shadow calibration jobs for pickem-auditor. Standard library only.

Subcommands:
  snapshot  preflight, fetch slate, odds quotes, prep, pipeline batch, append shadow rows
  closing   refresh closing_line / closing_q_market for today's open snapshot rows
  settle    delegate to scripts/settle.py
  weekly    report.py then the current per-sport/stat probability_blend fitter

Each job uses a lock file, structured logging, a one-line JSON summary, and a nonzero
exit code on failure. Shadow rows use run_type=shadow and are excluded from published
boards and tier statistics (see pickem_math.user_facing_rows).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import fetch_slate as fs
import probability_blend as pb
import pickem_math as pm
import report as calibration_report
import settle as settle_mod
from odds_providers import SPORT_FROM_KEY, consensus_input, event_on_date, quotes_for_row

SKILL_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = SKILL_ROOT / "logs"
LOCK_DIR = SKILL_ROOT / "data" / ".locks"
EASTERN = ZoneInfo("America/New_York")

READS_SLATE_KEYS = tuple(pm.READS_PIPELINE_FIELDS)
CONTEXT_COPY_KEYS = (
    "spread",
    "total",
    "team_is_underdog",
    "is_starter",
    "role",
    "outdoor",
    "sustained_wind_mph",
    "gust_mph",
    "precip_prob",
    "precip_intensity",
    "back_to_back",
    "third_in_four",
    "goalie_confirmed",
)


class JobError(Exception):
    """A job step failed."""


@contextmanager
def job_lock(name: str):
    """Exclusive lock so two runs of the same job do not overlap."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    path = LOCK_DIR / f"{name}.lock"
    flags = os.O_RDWR | os.O_CREAT
    fd = os.open(path, flags, 0o644)
    handle = os.fdopen(fd, "r+", encoding="utf-8")
    try:
        pm._lock_handle(handle)
        yield path
    finally:
        pm._unlock_handle(handle)
        handle.close()


class JobLog:
    def __init__(self, job: str, stamp: str):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.path = LOG_DIR / f"{job}_{stamp}.log"
        self._handle = self.path.open("a", encoding="utf-8")

    def write(self, message: str) -> None:
        line = message.rstrip("\n")
        self._handle.write(line + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def eastern_today() -> str:
    return datetime.now(EASTERN).date().isoformat()


def eastern_now_label() -> str:
    now = datetime.now(EASTERN)
    return now.strftime("%Y-%m-%d %H:%M ET")


def parse_iso_utc(value) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def game_started(commence, now: datetime) -> bool:
    start = parse_iso_utc(commence)
    if start is None:
        return False
    return now.astimezone(timezone.utc) >= start


def shadow_run_id(game_date: str, slot: str = "default") -> str:
    """Idempotent per game date AND scheduled snapshot slot (09:00 / 14:00 ET)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"pickem-auditor-shadow/{game_date}/{slot}"))


def slate_lookup(rows: list[dict]) -> dict[tuple, dict]:
    index: dict[tuple, dict] = {}
    for row in rows:
        sport = str(row.get("sport") or "").strip()
        player = str(row.get("player") or "").strip()
        stat = str(row.get("stat") or "").strip()
        if not sport or not player or not stat:
            continue
        index[(sport, player, stat)] = row
    return index


def matchup_label(team: str, opponent: str, *, home_team=None, away_team=None) -> str:
    """Show @ only when a verified bookmaker event supplies actual venue order."""
    team = str(team or "").strip()
    opponent = str(opponent or "").strip()
    home = str(home_team or "").strip()
    away = str(away_team or "").strip()
    if home and away and {home, away} == {team, opponent} and home != away:
        return f"{away} @ {home}"
    return f"{team} vs {opponent}" if team and opponent else (team or opponent or "unknown")


def team_bucket_throw_share(slate_row: dict) -> float | None:
    stat = str(slate_row.get("stat") or "").strip().lower()
    if stat == "receptions":
        return slate_row.get("qb_checkdown_tendency")
    if stat == "receiving yards":
        return slate_row.get("qb_first_read_rate")
    return slate_row.get("team_bucket_throw_share")


def enrich_pipeline_from_slate(pipeline_row: dict, slate_row: dict) -> dict:
    """Attach Engine B and context fields from the fetch row. Does not guess values."""
    out = dict(pipeline_row)
    for key in READS_SLATE_KEYS:
        if key in slate_row and slate_row[key] is not None:
            out[key] = slate_row[key]
    out["sport"] = slate_row.get("sport") or out.get("sport")
    share = team_bucket_throw_share(slate_row)
    if share is not None and out.get("team_bucket_throw_share") is None:
        out["team_bucket_throw_share"] = share
    for key in CONTEXT_COPY_KEYS:
        if key in slate_row and slate_row[key] is not None:
            out[key] = slate_row[key]
    return out


def parse_pipeline_id(ident: str) -> tuple[str, str, str, str] | None:
    parts = str(ident or "").split("|")
    if len(parts) != 4:
        return None
    return tuple(parts)


def commence_index_from_events(events: list[dict]) -> dict[tuple[str, str, str], str]:
    """Map (sport, team abbrev, opponent abbrev) -> commence_time ISO."""
    index: dict[tuple[str, str, str], str] = {}
    for event in events or []:
        if not isinstance(event, dict):
            continue
        commence = event.get("commence_time")
        if commence is None:
            continue
        sport = SPORT_FROM_KEY.get(str(event.get("sport_key") or "").lower(), "")
        if not sport:
            continue
        home = str(event.get("home_team") or "")
        away = str(event.get("away_team") or "")
        for team, opponent in ((home, away), (away, home)):
            key = (sport, team.casefold(), opponent.casefold())
            index[key] = str(commence)
    return index


def commence_index_from_quotes(quotes: list[dict], events: list[dict]) -> dict[tuple[str, str, str], str]:
    """Prefer team abbrev keys from quotes; fall back to full-name event keys."""
    by_event: dict[str, str] = {}
    for event in events or []:
        if not isinstance(event, dict):
            continue
        event_id = str(event.get("id") or "")
        commence = event.get("commence_time")
        if event_id and commence is not None:
            by_event[event_id] = str(commence)
    index: dict[tuple[str, str, str], str] = {}
    for quote in quotes or []:
        if not isinstance(quote, dict):
            continue
        sport = str(quote.get("sport") or "").strip()
        team = str(quote.get("team") or "").strip()
        opponent = str(quote.get("opponent") or "").strip()
        event_id = str(quote.get("event_id") or "")
        commence = quote.get("event_start") or by_event.get(event_id)
        if commence and parse_iso_utc(commence) is None:
            commence = None
        if sport and team and opponent and commence:
            index[(sport, team.casefold(), opponent.casefold())] = commence
    index.update(commence_index_from_events(events))
    return index


def venue_index_from_quotes(quotes: list[dict]) -> dict[tuple[str, str, str], tuple[str, str]]:
    """Use provider-confirmed [home, away]; ambiguous sources abstain."""
    from odds_providers import normalize_team
    options: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
    for quote in quotes or []:
        pair = quote.get("event_teams") if isinstance(quote, dict) else None
        if not isinstance(pair, list) or len(pair) != 2:
            continue
        home, away = (normalize_team(t) for t in pair)
        team, opponent = (normalize_team(quote.get(k)) for k in ("team", "opponent"))
        sport = str(quote.get("sport") or "").strip()
        if sport and home and away and {team, opponent} == {home, away} and home != away:
            options.setdefault((sport, team.casefold(), opponent.casefold()), set()).add((home, away))
    return {key: next(iter(choices)) for key, choices in options.items() if len(choices) == 1}


def lookup_commence(
    slate_row: dict,
    commence_index: dict[tuple[str, str, str], str],
) -> str | None:
    sport = str(slate_row.get("sport") or "").strip()
    team = str(slate_row.get("team") or "").strip().casefold()
    opponent = str(slate_row.get("opponent") or "").strip().casefold()
    if not sport or not team or not opponent:
        return None
    return commence_index.get((sport, team, opponent))


def filter_started_pipeline(
    pipeline_rows: list[dict],
    slate_by_key: dict[tuple, dict],
    commence_index: dict[tuple[str, str, str], str],
    now: datetime,
) -> tuple[list[dict], int]:
    kept: list[dict] = []
    skipped = 0
    for row in pipeline_rows:
        parsed = parse_pipeline_id(row.get("id"))
        if not parsed:
            kept.append(row)
            continue
        sport, player, stat, _side = parsed
        slate_row = slate_by_key.get((sport, player, stat))
        if slate_row is None:
            kept.append(row)
            continue
        commence = lookup_commence(slate_row, commence_index)
        if commence and game_started(commence, now):
            skipped += 1
            continue
        kept.append(row)
    return kept, skipped


def pipeline_to_snapshot(
    result: dict,
    *,
    meta: dict,
    run_id: str,
    run_at: str,
    candidate: dict,
) -> dict:
    project = result.get("project") or {}
    grade = result.get("grade") or {}
    market = result.get("market") or {}
    line = candidate.get("line")
    rank = str(result.get("final_rank") or "Unranked")
    status = "UNRANKED" if rank == "Unranked" else "GRADED"
    retrieved = market.get("retrieved_at")
    record = {
        "forecast_at": meta.get('forecast_at'),
        "event_start": meta.get('event_start'),
        "run_at": run_at,
        "game_date": str(meta["game_date"]),
        "sport": str(meta["sport"]),
        "matchup": str(meta["matchup"]),
        "home_team": meta.get("home_team"),
        "away_team": meta.get("away_team"),
        "matchup_orientation_verified": meta.get("matchup_orientation_verified") is True,
        "player": str(meta["player"]),
        **{key: candidate.get(key) or meta.get(key) for key in
           ("team", "opponent", "player_id", "event_id", "event_id_namespace")},
        "stat": str(meta["stat"]),
        "side": str(candidate.get("side") or ""),
        "reference_line": line,
        "final_rank": rank,
        "status": status,
        "researched": False,
        "run_type": pm.RUN_TYPE_SHADOW,
        "run_id": run_id,
        "dist": candidate.get("dist"),
        "inputs": dict(candidate),
        "shrunk_mean": project.get("shrunk_mean"),
        "current_role_n": project.get("current_role_n"),
        "prior_supported": bool(grade.get("prior_supported", False)),
        "q_model": grade.get("q_model") if grade else project.get("q_win"),
        "q_push": grade.get("q_push") if grade else project.get("q_push_robust"),
        "q_market": grade.get("q_market") if grade else market.get("q_market"),
        "q_market_comparable": (
            grade.get("q_market_comparable") if grade else market.get("q_market_comparable")
        ),
        "q_grade": grade.get("q_grade") if grade else None,
        "q_gap": grade.get("q_gap") if grade else None,
        "q_win": grade.get("q_model") if grade else project.get("q_win_robust"),
        "soft_flags": result.get("soft_flags_passed"),
        "mechanisms": grade.get("mechanisms") if grade else candidate.get("mechanisms"),
        "books": candidate.get("books"),
        "retrieved_at": retrieved,
        "reason": result.get("reason"),
        "derived_flags": result.get("derived_flags"),
        "engine_a": result.get("engine_a"),
        "engine_b": result.get("engine_b"),
        "crosscheck": result.get("crosscheck"),
        "blend": result.get("blend"),
        "shared_context":result.get('shared_context'),
        "market": market,
    }
    return record


def existing_snapshot_keys(path: Path, run_id: str) -> set[tuple]:
    if not path.is_file():
        return set()
    text = path.read_text(encoding="utf-8")
    keys = set()
    for _line_no, _line, row in pm.iter_snapshot_lines(text):
        if str(row.get("run_id") or "") != run_id:
            continue
        keys.add(pm.snapshot_key(row))
    return keys


def _pipeline_input(row: dict) -> dict:
    return {
        key: value
        for key, value in row.items()
        if not str(key).startswith("_")
    }


def run_pipeline_batch(rows: list[dict], *, now=None, data_root=None, clock_fn=None) -> tuple[list[dict], int]:
    snapshots: list[dict] = []
    errors = 0
    for row in rows:
        evaluation_now=clock_fn() if clock_fn else now
        meta=dict(row.get('_meta') or {})
        if evaluation_now and meta.get('event_start') and game_started(meta['event_start'],evaluation_now):continue
        if evaluation_now:meta['forecast_at']=evaluation_now.isoformat()
        candidate = _pipeline_input(row)
        try:
            from usage_baseline import using_directory
            with using_directory(data_root or SKILL_ROOT / "data"):
                result = pm.evaluate_candidate(candidate,now=evaluation_now)
        except pm.PickemError:
            errors += 1
            continue
        if not result.get("ok"):
            errors += 1
            continue
        parsed = parse_pipeline_id(result.get("id") or row.get("id"))
        if not parsed:
            errors += 1
            continue
        sport, player, stat, _side = parsed
        snapshots.append(
            pipeline_to_snapshot(
                result,
                meta=meta,
                run_id=row["_run_id"],
                run_at=row["_run_at"],
                candidate=candidate,
            )
        )
    return snapshots, errors


def attach_meta(
    pipeline_rows: list[dict],
    slate_by_key: dict[tuple, dict],
    *,
    game_date: str,
    run_id: str,
    run_at: str,
    forecast_at: str | None = None,
    commence_index: dict | None = None,
    venue_index: dict | None = None,
) -> list[dict]:
    enriched = []
    for row in pipeline_rows:
        parsed = parse_pipeline_id(row.get("id"))
        if not parsed:
            continue
        sport, player, stat, _side = parsed
        slate_row = slate_by_key.get((sport, player, stat))
        if slate_row is None:
            continue
        payload = enrich_pipeline_from_slate(row, slate_row)
        venue = (venue_index or {}).get((sport, str(slate_row.get("team") or "").casefold(),
                                        str(slate_row.get("opponent") or "").casefold()))
        payload["_meta"] = {
            "forecast_at": forecast_at,
            "event_start": lookup_commence(slate_row, commence_index or {}),
            "game_date": game_date,
            "sport": sport,
            "player": player,
            **{key: slate_row.get(key) for key in
               ("team", "opponent", "player_id", "event_id", "event_id_namespace")},
            "stat": stat,
            "matchup": matchup_label(slate_row.get("team"), slate_row.get("opponent"),
                                     home_team=venue[0] if venue else None,
                                     away_team=venue[1] if venue else None),
            "home_team": venue[0] if venue else None,
            "away_team": venue[1] if venue else None,
            "matchup_orientation_verified": venue is not None,
        }
        payload["_run_id"] = run_id
        payload["_run_at"] = run_at
        enriched.append(payload)
    return enriched


def load_odds_events(game_date: str, fetch_json_fn=fs.fetch_json) -> list[dict]:
    from odds_providers import SPORTS, PropLineProvider

    provider = PropLineProvider(fetch=fetch_json_fn)
    secret = getattr(provider, "api_key", "") or ""
    if not str(secret).strip():
        return []
    events: list[dict] = []
    for _sport, sport_key, _player_markets in SPORTS:
        batch, _error = provider._events(sport_key, str(secret).strip())
        for event in batch or []:
            if not isinstance(event, dict):
                continue
            if not event_on_date(event.get("commence_time"), game_date):
                continue
            events.append(event)
    return events


def run_snapshot(
    *,
    game_date: str,
    slate_path: Path,
    quotes_path: Path,
    snapshot_path: Path,
    now: datetime | None = None,
    preflight_fn=None,
    collect_fn=None,
    events_loader=None,
    fetch_json_fn=fs.fetch_json,
    clock_fn=None,
) -> dict:
    clock_fn=clock_fn or ((lambda:now) if now is not None else (lambda:datetime.now(timezone.utc)))
    now = clock_fn()
    run_at = now.astimezone(EASTERN).strftime("%Y-%m-%d %H:%M ET")
    # Bucket retries/delays into the intended daily local morning or afternoon
    # scheduled slot, rather than embedding the actual minute of execution.
    local_hour = now.astimezone(EASTERN).hour
    slot = "09:00" if local_hour < 12 else "14:00"
    run_id = shadow_run_id(game_date, slot)

    preflight_fn = preflight_fn or fs.preflight
    report = preflight_fn()
    if not (report.get("ok") or report.get("operational")):
        # Enumerate failures without printing credentials or credentials files.
        unavailable = []
        for feed, ready in (report.get("feeds_ready") or {}).items():
            if not ready:
                unavailable.append(feed)
        failures = [f"{c.get('feed')}:{c.get('name')}" for c in report.get("checks", [])
                    if not c.get("ok") and c.get("kind") != "credential"]
        web_checks = [c for c in report.get("checks", []) if c.get("kind") == "https"]
        dns_only = bool(web_checks) and all(
            not c.get("ok") and ("dns" in str(c.get("detail") or "").lower()
                                  or "name resolution" in str(c.get("detail") or "").lower())
            for c in web_checks
        )
        diagnostic = "RUNTIME_DNS_UNAVAILABLE: " if dns_only else ""
        raise JobError(diagnostic + "preflight blocked: feeds=" + (", ".join(unavailable) or "unknown")
                       + "; failed checks=" + (", ".join(failures) or "unspecified"))

    collect_fn = collect_fn or _default_collect
    rows, _summary = collect_fn(game_date, slate_path, quotes_path, fetch_json_fn=fetch_json_fn)
    if not rows:
        raise JobError("fetch produced zero slate rows")

    # A verified source receipt includes all collected prices; the snapshot
    # only consumes its independently timestamp-qualified subset.
    prefetched = _summary.get("_fresh_quotes") if isinstance(_summary, dict) else None
    quotes = prefetched if prefetched is not None else (
        fs.read_jsonl(quotes_path) if quotes_path.exists() else [])
    pipeline_rows = fs.prepare_pipeline(rows, quotes, now=now.isoformat())
    if not quotes:
        raise JobError(f"NO_PRICED_QUOTES: {len(rows)} slate rows; odds feed absent or empty")
    if not pipeline_rows:
        raise JobError(f"ZERO_GRADEABLE_MARKETS: {len(rows)} slate rows, {len(quotes)} odds quotes; no two-sided priced candidates")
    slate_by_key = slate_lookup(rows)
    events_loader = events_loader or (lambda date: load_odds_events(date, fetch_json_fn=fetch_json_fn))
    commence_index = commence_index_from_quotes(quotes, events_loader(game_date))
    now=clock_fn()  # Collection must not be stamped with an earlier prefetch time.
    run_at=now.astimezone(EASTERN).strftime("%Y-%m-%d %H:%M ET")
    pipeline_rows, skipped_started = filter_started_pipeline(
        pipeline_rows, slate_by_key, commence_index, now,
    )

    # Consume the freshly collected packet before snapshot evaluation. Shadow
    # forecasts may be retained when research is absent, but cannot be graded.
    import research_packet as rp
    packet_path = slate_path.parent / f"research_{game_date}.json"
    if packet_path.exists():
        packet = rp.load_json(packet_path)
        valid, issues = rp.validate_packet(packet, now=now)
        if packet.get("date") != game_date or issues:
            raise JobError("RESEARCH_PACKET_INVALID: " + "; ".join(i.message for i in issues))
        pipeline_rows = rp.merge_into_pipeline(valid, pipeline_rows)
    else:
        pipeline_rows = [{**r, "data_veto": True,
                          "availability_issue": "RESEARCH_PACKET_MISSING"} for r in pipeline_rows]

    from usage_baseline import using_directory
    from lineup_feeds import prepare as prepare_lineups
    with using_directory(slate_path.parent):
        lineup_collection=prepare_lineups(pipeline_rows,fetch=fetch_json_fn)
    now=clock_fn()
    pipeline_rows, late_started=filter_started_pipeline(pipeline_rows,slate_by_key,commence_index,now)
    skipped_started+=late_started
    pipeline_rows = attach_meta(
        pipeline_rows, slate_by_key, game_date=game_date, run_id=run_id, run_at=run_at,
        forecast_at=now.isoformat(), commence_index=commence_index,
        venue_index=venue_index_from_quotes(quotes),
    )
    snapshots, pipeline_errors = run_pipeline_batch(pipeline_rows,now=now,data_root=slate_path.parent,clock_fn=clock_fn)
    skipped_started+=max(0,len(pipeline_rows)-len(snapshots)-pipeline_errors)

    seen = existing_snapshot_keys(snapshot_path, run_id)
    to_write = []
    skipped_dup = 0
    for record in snapshots:
        key = pm.snapshot_key(pm.normalize_snapshot(record, run_id=run_id))
        if key in seen:
            skipped_dup += 1
            continue
        to_write.append(record)
        seen.add(key)

    written = 0
    if to_write:
        _path, written = pm.append_snapshots(to_write, snapshot_path)

    return {
        "job": "snapshot",
        "rows_written": written,
        "skipped": skipped_started + skipped_dup,
        "errors": pipeline_errors,
        "lineup_collection":lineup_collection,
        "preflight_feeds_ready": report.get("feeds_ready"),
        "preflight_partial": not bool(report.get("ok")),
        "run_id": run_id,
        "fresh_prefetch_quotes": len(quotes),
        "excluded_stale_prefetch_quotes": (
            _summary.get("_excluded_stale_quotes", 0) if isinstance(_summary, dict) else 0),
    }


def reuse_recent_collect(game_date: str, slate_path: Path, quotes_path: Path, *,
                         now: datetime | None = None, max_age_minutes: int = 30):
    """Reuse already-fetched, source-timestamped slate and sportsbook quotes.

    Reject mismatches and stale market rows without re-calling paid PropLine.
    A partly stale provider response is not an entirely unusable slate.
    """
    meta_path = fs.meta_path_for(slate_path)
    if not slate_path.is_file() or not meta_path.is_file() or not quotes_path.is_file():
        raise JobError('PREFETCH_MISSING: slate, source receipt and two-sided quotes are required')
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        rows = fs.read_jsonl(slate_path)
        quotes = fs.read_jsonl(quotes_path)
    except (OSError, ValueError) as exc:
        raise JobError('PREFETCH_INVALID: invalid source JSON') from exc
    if meta.get('date') != game_date or any(row.get('game_date') != game_date for row in rows):
        raise JobError('PREFETCH_DATE_MISMATCH: refusing cross-date pregame history')
    stamp = parse_iso_utc(meta.get('retrieved_at'))
    clock = now or datetime.now(timezone.utc)
    if stamp is None or not 0 <= (clock.astimezone(timezone.utc) - stamp).total_seconds() <= max_age_minutes * 60:
        raise JobError('PREFETCH_STALE: source receipt outside allowed freshness window')
    odds = (meta.get('feeds') or {}).get('odds') or {}
    if odds.get('status') != 'ok' or not quotes:
        raise JobError('PREFETCH_UNPRICED: no verified, fetched sportsbook quotes')
    if not rows or meta.get('rows') != len(rows) or odds.get('rows') != len(quotes):
        raise JobError('PREFETCH_ROW_COUNT_MISMATCH: data and receipt disagree')
    fresh = []
    stale = 0
    for quote in quotes:
        # The source receipt's count validates the entire ORIGINAL quote file.
        # A malformed or different-date record must not be silently reassigned.
        if quote.get('game_date') not in (None, game_date):
            raise JobError('PREFETCH_QUOTE_DATE_MISMATCH')
        retrieved = parse_iso_utc(quote.get('retrieved_at'))
        age = ((clock.astimezone(timezone.utc) - retrieved).total_seconds()
               if retrieved is not None else None)
        if age is None or age < 0 or age > max_age_minutes * 60:
            stale += 1
        else:
            fresh.append(quote)
    if not fresh:
        raise JobError('PREFETCH_QUOTE_STALE: zero fresh two-sided market rows')
    # The raw quote file and immutable fetch receipt remain unchanged.
    return rows, {**meta, '_fresh_quotes': fresh, '_excluded_stale_quotes': stale}


def _default_collect(game_date: str, slate_path: Path, quotes_path: Path, fetch_json_fn=fs.fetch_json):
    client, client_error = fs.make_nhl_client()
    rows, summary = fs.collect(
        game_date,
        nhl_client=client,
        nhl_client_error=client_error,
        fetch_json_fn=fetch_json_fn,
        quotes_path=quotes_path,
    )
    code = fs.commit_slate(rows, summary, slate_path)
    if code != 0:
        raise JobError(f"commit_slate exited {code}")
    try:
        if rows:
            summary["context"] = fs.emit_slate_context(
                game_date,
                rows,
                summary.get("retrieved_at") or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                fetch_json_fn=fetch_json_fn,
                data_dir=slate_path.parent,
            )
    except Exception as exc:
        summary["context"] = {"status": "failed", "notes": [str(exc)]}
    return rows, summary


def closing_consensus_for_row(row: dict, quotes: list[dict], now_iso: str) -> tuple[float | None, float | None]:
    sport = str(row.get("sport") or "")
    player = str(row.get("player") or "")
    stat = str(row.get("stat") or "")
    side = str(row.get("side") or "").lower()
    inputs = row.get("inputs") if isinstance(row.get("inputs"), dict) else {}
    fake_slate = {
        "sport": sport,
        "player": player,
        "stat": stat,
        **{key: row.get(key) or inputs.get(key) for key in
           ("team", "opponent", "player_id", "event_id", "event_id_namespace", "game_date")},
    }
    # Legacy shadow snapshots store the subject team first in matchup_label.
    # Only recover that explicitly documented format; never guess from a name.
    if not fake_slate["team"] and row.get("run_type") == pm.RUN_TYPE_SHADOW:
        matchup = str(row.get("matchup") or "").split(" @ ")
        if len(matchup) == 2 and all(part.strip() for part in matchup):
            fake_slate["team"], fake_slate["opponent"] = (part.strip() for part in matchup)
    found = quotes_for_row(quotes, fake_slate)
    from odds_providers import primary_price
    price = primary_price(found)
    if not price or price.get("line") is None:
        return None, None
    line = float(price["line"])
    on_line = [
        quote for quote in found
        if quote.get("line") is not None and abs(float(quote["line"]) - line) <= 1e-9
    ]
    groups = consensus_input(on_line, now=now_iso, side=side)
    info = next(
        (group for group in groups if abs(float(group["line"]) - line) <= 1e-9),
        None,
    )
    if not info or not info.get("books"):
        return None, None
    tuples = pm._consensus_tuples(info["books"])
    consensus = pm.consensus(tuples, info.get("retrieved_minutes_ago"))
    q_market = consensus.get("q_market")
    if q_market is None:
        return float(line), None
    return float(line), float(q_market)


def run_closing(
    *,
    game_date: str,
    snapshot_path: Path,
    quotes_path: Path,
    fetch_json_fn=fs.fetch_json,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    now_iso = now.isoformat()
    quotes, _note = fs.fetch_odds(game_date, fetch=fetch_json_fn)
    fs.write_jsonl(quotes, quotes_path)
    updated = 0
    skipped = 0
    errors = 0
    with pm.locked_snapshot(snapshot_path, create=False) as (handle, text):
        rows = [row for _line_no, _line, row in pm.iter_snapshot_lines(text)]
        out_rows = []
        for row in rows:
            if str(row.get("game_date") or "")[:10] != game_date:
                out_rows.append(row)
                continue
            if row.get("closing_line") is not None and row.get("closing_q_market") is not None:
                out_rows.append(row)
                skipped += 1
                continue
            if row.get("actual_stat") is not None:
                out_rows.append(row)
                skipped += 1
                continue
            try:
                closing_line, closing_q = closing_consensus_for_row(row, quotes, now_iso)
            except pm.PickemError:
                errors += 1
                out_rows.append(row)
                continue
            if closing_line is None:
                skipped += 1
                out_rows.append(row)
                continue
            new_row = dict(row)
            new_row["closing_line"] = closing_line
            new_row["closing_q_market"] = closing_q
            market = new_row.get("market")
            if isinstance(market, dict):
                market = dict(market)
                market["closing_q_market"] = closing_q
                new_row["market"] = market
            out_rows.append(new_row)
            updated += 1
        if updated:
            payload = "".join(pm.dump_snapshot(row) for row in out_rows)
            handle.seek(0)
            handle.truncate(0)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    return {
        "job": "closing",
        "rows_written": updated,
        "skipped": skipped,
        "errors": errors,
    }


def run_settle(*, snapshot_path: Path, as_of: str, fetchers=None) -> dict:
    fetchers = fetchers or settle_mod.default_fetchers()
    try:
        count = settle_mod.settle_file(snapshot_path, as_of=as_of, fetchers=fetchers)
    except pm.PickemError as exc:
        raise JobError(str(exc)) from exc
    except (OSError, ImportError, TimeoutError) as exc:
        # Data collection needs live feeds. Do not permit an opaque traceback or
        # report 0 settled as success when the feed could not be reached.
        raise JobError(f"SETTLEMENT_SOURCE_UNAVAILABLE: {type(exc).__name__}; "
                       "verified results could not be fetched; snapshots were not rewritten") from exc
    return {"job": "settle", "rows_written": count, "skipped": 0, "errors": 0}


def run_weekly(*, snapshot_path: Path, argv_fit: list[str] | None = None, root: Path | None = None) -> dict:
    if argv_fit:
        raise JobError('Legacy --fit-args are unsupported; weekly fits all current sport/stat scopes automatically')
    # First week may have no snapshots yet. Report that instead of failing CI.
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.touch(exist_ok=True)
    report_argv = ["--path", str(snapshot_path), "--include-shadow"]
    code = calibration_report.main(report_argv)
    if code != 0:
        raise JobError(f"report exited {code}")
    rows=[json.loads(line) for line in snapshot_path.read_text().splitlines() if line.strip()]
    scopes=pb.fit_scopes(rows,root or SKILL_ROOT)
    from context_validation import fit_scopes as fit_context_scopes
    contexts=fit_context_scopes(rows,root or SKILL_ROOT)
    available=any(result['status']=='validated' for result in scopes.values())
    return {"job": "weekly", "rows_written": 0, "skipped": 0, "errors": 0,
            "calibration_status": "validated_weights_available" if available else "underpowered_or_unvalidated",
            "scopes":scopes,"context_scopes":contexts}


def emit_summary(log: JobLog, summary: dict) -> None:
    line = json.dumps(summary, sort_keys=True)
    log.write(line)
    print(line)


def run_job(job: str, log: JobLog, runner) -> int:
    try:
        summary = runner()
    except JobError as exc:
        summary = {"job": job, "rows_written": 0, "skipped": 0, "errors": 1, "error": str(exc)}
        log.write(f"ERROR: {exc}")
        emit_summary(log, summary)
        return 1
    except pm.PickemError as exc:
        summary = {"job": job, "rows_written": 0, "skipped": 0, "errors": 1, "error": str(exc)}
        log.write(f"ERROR: {exc}")
        emit_summary(log, summary)
        return 1
    emit_summary(log, summary)
    return 0 if int(summary.get("errors") or 0) == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shadow calibration jobs.")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="Fetch slate and append shadow snapshot rows.")
    snap.add_argument("--date", default=eastern_today())
    snap.add_argument("--slate", default=str(fs.DEFAULT_OUT))
    snap.add_argument("--snapshots", default=str(pm.DEFAULT_SNAPSHOT_PATH))
    snap.add_argument("--reuse-collected", action="store_true",
                      help="Reuse the fresh slate and market quote batch rather than querying Odds API twice")

    close = sub.add_parser("closing", help="Fill closing line and market on today's open rows.")
    close.add_argument("--date", default=eastern_today())
    close.add_argument("--snapshots", default=str(pm.DEFAULT_SNAPSHOT_PATH))

    stl = sub.add_parser("settle", help="Settle past-game rows via settle.py.")
    stl.add_argument("--as-of", default=fs.eastern_today())
    stl.add_argument("--snapshots", default=str(pm.DEFAULT_SNAPSHOT_PATH))

    week = sub.add_parser("weekly", help="Calibration report then blend fit.")
    week.add_argument("--snapshots", default=str(pm.DEFAULT_SNAPSHOT_PATH))
    week.add_argument("--fit-args", nargs=argparse.REMAINDER, help="Deprecated; nonempty legacy arguments produce an error")

    args = parser.parse_args(argv)
    stamp = eastern_today()
    log = JobLog(args.command, stamp)
    log.write(f"start {args.command} at {eastern_now_label()}")

    with job_lock(args.command):
        if args.command == "snapshot":
            slate_path = Path(args.slate)
            quotes_path = fs.quotes_path_for(slate_path)
            return run_job(
                "snapshot",
                log,
                lambda: run_snapshot(
                    game_date=args.date,
                    slate_path=slate_path,
                    quotes_path=quotes_path,
                    snapshot_path=Path(args.snapshots),
                    events_loader=(lambda date: []) if args.reuse_collected else None,
                    collect_fn=(lambda date, slate_path, quotes_path, fetch_json_fn=None:
                                reuse_recent_collect(date, slate_path, quotes_path))
                               if args.reuse_collected else None,
                ),
            )
        if args.command == "closing":
            slate_default = Path(fs.DEFAULT_OUT)
            quotes_path = fs.quotes_path_for(slate_default)
            return run_job(
                "closing",
                log,
                lambda: run_closing(
                    game_date=args.date,
                    snapshot_path=Path(args.snapshots),
                    quotes_path=quotes_path,
                ),
            )
        if args.command == "settle":
            return run_job(
                "settle",
                log,
                lambda: run_settle(snapshot_path=Path(args.snapshots), as_of=args.as_of),
            )
        if args.command == "weekly":
            fit_argv = args.fit_args or None
            return run_job(
                "weekly",
                log,
                lambda: run_weekly(snapshot_path=Path(args.snapshots), argv_fit=fit_argv),
            )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
