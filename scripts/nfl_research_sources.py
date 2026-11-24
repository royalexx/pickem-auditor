"""NFL research runner for pregame acquisition and independent final validation."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo

import fetch_slate as slate
from nfl_pregame_roster import CROSSWALK, SUMMARY, _espn_nfl_team
from odds_providers import normalize_player
from phase0_input_capture import preserve, stamp, utc
from phase0_pre_eval import canonical_bytes
from pickem_math import settlement_outcome, snapshot_key

ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
TORONTO = ZoneInfo("America/Toronto")
CAPTURE = "nfl_projected_starters_inputs_v1"
FORECAST = "nfl_projected_starters_forecast_v1"
# Depth charts often include alternate personnel packages. Admit explicit
# first-slot roles from the primary offense and defense charts.
CHARTS = {
    "offense": "offense", "defense": "defense",
    "base 3-4 d": "defense", "base 4-3 d": "defense",
}
SLOTS = {
    "qb", "rb", "hb", "fb", "wr", "wr1", "wr2", "wr3", "lwr", "rwr", "swr", "te",
    "lt", "lg", "c", "rg", "rt", "de", "lde", "rde", "dt", "ldt", "rdt", "nt",
    "lb", "mlb", "ilb", "lolb", "rolb", "llb", "rlb", "slb", "wlb", "olb",
    "cb", "lcb", "rcb", "ss", "fs", "s", "nb", "ncb", "k", "p", "ls",
}
STATS = {
    "passing yards": ("passing", "YDS", None),
    "pass attempts": ("passing", "C/ATT", 1),
    "completions": ("passing", "C/ATT", 0),
    "rushing yards": ("rushing", "YDS", None),
    "rush attempts": ("rushing", "CAR", None),
    "receiving yards": ("receiving", "YDS", None),
    "receptions": ("receiving", "REC", None),
}


def now():
    return datetime.now(timezone.utc)


def save(root, role, payload):
    at = now()
    return preserve(root, "NFL", role, canonical_bytes(payload), captured=at,
                    retrieved=at)["content_sha256"]


def read(root, role, digest):
    if (not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        raise ValueError("invalid_source_hash")
    raw = (root / role / (digest + ".bin")).read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError(f"{role}_hash_mismatch")
    return raw


def acquire(root, role, url, *, fetch=slate.fetch_bytes):
    try:
        raw = fetch(url, timeout=15)
        observed = now()
        receipt = preserve(root, "NFL", role, raw, captured=observed,
                           retrieved=observed, url=url)
        return {"url": url, "received_at": stamp(observed), "sha256": receipt["content_sha256"]}
    except (OSError, ValueError) as exc:
        return {"url": url, "error": type(exc).__name__, "failed_at": stamp(now())}


def source(root, role, entry, url, cutoff):
    if not entry or entry.get("url") != url or not entry.get("sha256"):
        raise ValueError(f"{role}_source_unavailable")
    received = utc(entry.get("received_at"))
    if received is None or received > cutoff:
        raise ValueError(f"{role}_source_after_cutoff")
    return read(root, role, entry["sha256"])


def fixture(competition, event_id):
    clubs = competition["competitors"]
    sides = {r["homeAway"]: (_espn_nfl_team(r["team"]["abbreviation"]), str(r["team"]["id"]))
             for r in clubs}
    start = utc(competition["date"])
    if (str(competition["id"]) != event_id or not event_id.isdigit() or not start
            or len(clubs) != 2 or set(sides) != {"home", "away"}
            or not all(team and ident.isdigit() for team, ident in sides.values())
            or sides["home"][0] == sides["away"][0]):
        raise ValueError("espn_fixture_conflict")
    return sides, start


def games(payload, day):
    result = {}
    for event in payload.get("events", []):
        if event.get("season", {}).get("type") != 2:
            continue
        event_id = str(event["id"])
        comp, = event["competitions"]
        sides, start = fixture(comp, event_id)
        if start.astimezone(TORONTO).date().isoformat() != day:
            continue
        pair = (sides["away"][0], sides["home"][0])
        if pair in result or any(g[0] == event_id for g in result.values()):
            raise ValueError("espn_fixture_ambiguous")
        result[pair] = (event_id, sides, start, comp["status"]["type"]["state"])
    return result


def projected(payload):
    """Resolve first depth-chart slots, dropping slots with conflicting heads."""
    choices = {}
    for chart in payload.get("depthchart") or payload.get("depthCharts") or []:
        label = str(chart.get("name") or "").strip().lower()
        if not label:
            # The published ESPN format also identifies packages by the
            # position groups directly. Sub-packages cannot override a slot.
            label = str(chart.get("type") or "").strip().lower()
        group = CHARTS.get(label)
        if not group:
            continue
        for slot, node in chart.get("positions", {}).items():
            slot = slot.casefold()
            if slot not in SLOTS:
                continue
            ordered = node.get("athletes") or []
            if not ordered:
                continue
            first = ordered[0]
            athlete = first.get("athlete") or first
            ident = str(athlete.get("id") or "")
            status = athlete.get("status") or first.get("status") or {}
            designation = (status.get("type") or status.get("name")
                           if isinstance(status, dict) else status)
            out = str(designation or "").strip().lower() in {"out", "inactive", "injured reserve", "doubtful"}
            choices.setdefault((group, slot), set()).add((ident, out))
    return {next(iter(rows))[0] for rows in choices.values() if len(rows) == 1
            and next(iter(rows))[0].isdigit() and not next(iter(rows))[1]}


def archive_inputs(stage, root):
    files = {}
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            observed = now()
            receipt = preserve(root, "NFL", "model_input", path.read_bytes(),
                               captured=observed, retrieved=observed)
            files[path.relative_to(stage).as_posix()] = receipt["content_sha256"]
    return files


def collect(root, day, *, quotes_file=None, live_odds=False, fetch=slate.fetch_bytes):
    """Capture NFL history, current projected starters and one quote batch."""
    scoreboard_url = f"{ESPN}/scoreboard?dates={day.replace('-', '')}"
    entries = {
        "scoreboard": acquire(root, "scoreboard", scoreboard_url, fetch=fetch),
        "crosswalk": acquire(root, "crosswalk", CROSSWALK, fetch=fetch),
        "depth": {},
    }
    errors = []
    try:
        schedule = games(json.loads(source(root, "scoreboard", entries["scoreboard"],
                                           scoreboard_url, now())), day)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        schedule = {}
        errors.append(str(exc))
    upcoming = [game for game in schedule.values() if game[3] == "pre" and game[2] > now()]
    teams = sorted({(team, ident) for _, sides, _, _ in upcoming for team, ident in sides.values()})

    def depth(pair):
        team, ident = pair
        return team, acquire(root, "depth", f"{ESPN}/teams/{ident}/depthcharts", fetch=fetch)

    if teams:
        with ThreadPoolExecutor(max_workers=6) as pool:
            entries["depth"] = dict(pool.map(depth, teams))

    with TemporaryDirectory(prefix="nfl-research-source-") as temp:
        stage = Path(temp)
        slate_path = stage / "slate_fetch.jsonl"
        quotes_path = slate.quotes_path_for(slate_path)
        if quotes_file and upcoming:
            original_quotes = slate.read_jsonl(quotes_file)
            original_quotes = [q for q in original_quotes if q.get("sport") == "NFL"]
        elif live_odds and upcoming:
            if os.environ.get("PICKEM_ODDS_QUOTA_GUARD") != "1":
                raise ValueError("live_odds_requires_existing_quota_guard")
            original_quotes, note = slate.fetch_odds(day, sports=["NFL"])
            if note:
                errors.append(note)
        else:
            original_quotes = []
        # Existing collectors retain source quote timestamps and original provider IDs.
        def history():
            season = slate.nfl_season_from_date(day)
            return slate.fetch_nfl(day, slate.utc_now(),
                                   season_store_path=stage / "season" / f"nfl_{season}.sqlite3")
        fetchers = {"nfl": history, "odds": lambda: (original_quotes, [])} if upcoming else {}
        rows, summary = slate.collect(day, fetchers=fetchers, quotes_path=quotes_path)
        slate.commit_slate(rows, summary, slate_path)
        files = archive_inputs(stage, root) if rows and original_quotes else {}
    receipt = {
        "schema": CAPTURE, "date": day, "completed_at": stamp(now()), "sources": entries,
        "files": files, "feed_summary": summary["feeds"], "errors": errors,
        "slate_rows": len(rows), "quote_rows": len(original_quotes),
    }
    return save(root, "capture", receipt), receipt


def final_actual(payload, row):
    event_id = str(row["espn_event_id"])
    header = payload["header"]
    comp, = header["competitions"]
    sides, start = fixture(comp, event_id)
    if (str(header["id"]) != event_id or header["season"]["type"] != 2
            or (sides["away"][0], sides["home"][0]) != (row["away_team"], row["home_team"])
            or start != utc(row["event_start"])):
        raise ValueError("final_event_identity_conflict")
    status = comp["status"]["type"]
    if status["state"] != "post" or status["completed"] is not True:
        raise ValueError("official_final_pending")
    if row["stat"] not in STATS:
        raise ValueError("official_stat_policy_unverified")
    group, stat_label, index = STATS[row["stat"]]
    team_ids = {team: ident for team, ident in sides.values()}
    if {row["team"], row["opponent"]} != set(team_ids):
        raise ValueError("final_team_identity_conflict")
    blocks = [entry for entry in payload["boxscore"]["players"]
              if str(entry["team"].get("id")) == team_ids[row["team"]]]
    if len(blocks) != 1:
        raise ValueError("final_team_stats_missing_or_ambiguous")
    tables = [table for table in blocks[0]["statistics"] if table.get("name") == group]
    if len(tables) != 1:
        raise ValueError("final_stat_table_missing_or_ambiguous")
    table = tables[0]
    if table["labels"].count(stat_label) != 1:
        raise ValueError("final_stat_column_missing_or_ambiguous")
    athlete_id = str(row["espn_player_id"])
    matching = [person for person in table["athletes"] if str(person["athlete"]["id"]) == athlete_id]
    if len(matching) != 1:
        raise ValueError("final_player_stat_missing_or_ambiguous")
    person = matching[0]
    if (normalize_player(person["athlete"]["displayName"]) != normalize_player(row["player"])
            or person.get("didNotPlay") is True or person.get("active") is False):
        raise ValueError("final_player_identity_or_participation_unresolved")
    value = person["stats"][table["labels"].index(stat_label)]
    if index is not None:
        counts = value.split("/")
        if len(counts) != 2 or not all(v.isdigit() for v in counts) or int(counts[0]) > int(counts[1]):
            raise ValueError("final_stat_value_invalid")
        value = counts[index]
    actual = float(value)
    if not math.isfinite(actual) or not actual.is_integer() or (actual < 0 and stat_label != "YDS"):
        raise ValueError("final_stat_value_invalid")
    return actual


def validate(root, digest, *, fetch=slate.fetch_bytes):
    original = json.loads(read(root, "forecasts", digest))
    if original["schema"] != FORECAST:
        raise ValueError("forecast_schema_mismatch")
    capture = original["capture_sha256"]
    read(root, "capture", capture)
    committed = json.loads((root / "forecast_commits" / f"{capture}.json").read_bytes())
    completed = utc(committed["completed_at"])
    if committed["forecasts_sha256"] != digest or not completed or completed > now():
        raise ValueError("forecast_commit_invalid")
    rows, evidence, checked = original["forecasts"], {}, []
    if (len({snapshot_key(row) for row in rows}) != len(rows)
            or len({row["forecast_id"] for row in rows}) != len(rows)):
        raise ValueError("duplicate_forecast_identity")
    for row in rows:
        event = row["espn_event_id"]
        result = {
            "forecast_id": row["forecast_id"], "contract_id": row["contract_id"],
            "snapshot_key": snapshot_key(row), "actual": None, "outcome": None,
        }
        if not str(event).isdigit() or not utc(row["forecast_at"]) or not utc(row["event_start"]):
            raise ValueError("forecast_identity_or_time_invalid")
        if not utc(row["forecast_at"]) <= completed < utc(row["event_start"]):
            result["reason"] = "forecast_after_start"
        elif now() < utc(row["event_start"]):
            result["reason"] = "official_final_pending"
        else:
            url = f"{SUMMARY}?event={event}"
            if event not in evidence:
                evidence[event] = acquire(root, "final", url, fetch=fetch)
            try:
                payload = json.loads(source(root, "final", evidence[event], url, now()))
                result["actual"] = final_actual(payload, row)
                result["outcome"] = settlement_outcome(row["side"], row["reference_line"], result["actual"])
            except (KeyError, IndexError, ValueError, TypeError, OSError) as exc:
                result["reason"] = str(exc)
        checked.append(result)
    receipt = {
        "schema": "nfl_projected_starters_validation_v1", "forecasts_sha256": digest,
        "evidence": evidence, "rows": checked,
        "settled": sum(row["outcome"] is not None for row in checked),
        "unresolved": sum(row["outcome"] is None for row in checked),
    }
    return save(root, "validation", receipt), receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("collect")
    pre.add_argument("--date", type=lambda raw: date.fromisoformat(raw).isoformat(), required=True)
    odds = pre.add_mutually_exclusive_group()
    odds.add_argument("--quotes-file", type=Path, help="Reuse existing original quote JSONL")
    odds.add_argument("--live-odds", action="store_true")
    post = sub.add_parser("validate")
    post.add_argument("--forecasts-sha256", required=True)
    args = parser.parse_args()
    if args.command == "collect":
        digest, receipt = collect(args.root, args.date, quotes_file=args.quotes_file, live_odds=args.live_odds)
        print(json.dumps({"sha256": digest, "slate_rows": receipt["slate_rows"],
                          "quote_rows": receipt["quote_rows"], "errors": receipt["errors"]}))
    else:
        digest, receipt = validate(args.root, args.forecasts_sha256)
        print(json.dumps({"sha256": digest, "settled": receipt["settled"],
                          "unresolved": receipt["unresolved"]}))


if __name__ == "__main__":
    main()
