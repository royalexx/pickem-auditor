"""Single-owner NFL 2026-11-15 original-source research capture on Deepnote Basic CPU.

No production ranking, no GitHub Actions, no posterior fitting, no historical
forecast modifications. Each run writes content-addressed append-only files.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, urlopen
import argparse
import json
import os
import sys
import traceback

from nfl_sunday_source_contract import (
    DAY, VERSION, expected_events, instant, utc, write_immutable,
    build_universe, freeze_manifest,
)

ESPN_SCHEDULE = (
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
    "scoreboard?dates=20261115"
)
ESPN_TEAM_BASE = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/"
HTTP_UA = "pickem-auditor-v25-nfl-ws1-source-control"
ROOT = Path(__file__).resolve().parents[1]

def safe_url(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname:
        raise ValueError("SOURCE_NOT_HTTPS")
    if not (p.hostname == "site.api.espn.com" or
            p.hostname == "api.propline.app" or
            p.hostname.endswith(".propline.app")):
        # Provider's actual host is enforced by odds_providers' URL config;
        # explicitly extend only once the installed production config is inspected.
        from odds_providers import API_ROOT
        host = urlsplit(API_ROOT).hostname
        if p.hostname != host:
            raise ValueError("SOURCE_HOST_UNAPPROVED")
    clean = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if k.lower() not in ("apikey", "api_key", "token", "key")]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(clean, safe=","), ""))

def now_utc():
    return utc(datetime.now(timezone.utc))

class RawCapture:
    def __init__(self, root):
        self.root = Path(root)
        self.receipts = {}
        self.errors = []

    def fetch(self, url, *, timeout=12, headers=None, source_name=None):
        clean = safe_url(url)
        start = now_utc()
        req = Request(url, headers={
            "User-Agent": HTTP_UA,
            "Accept": "application/json",
            **(headers or {}),
        })
        try:
            with urlopen(req, timeout=timeout) as response:
                raw = response.read()
                http_status = response.status
                reported_modified = response.headers.get("Last-Modified")
            received = now_utc()
            if http_status != 200 or not raw:
                raise ValueError("SOURCE_EMPTY_OR_HTTP_NOT_200")
            payload = json.loads(raw)
            digest = sha256(raw).hexdigest()
            path = self.root / "source_control" / "raw" / (digest + ".bin")
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open("xb") as stream:
                    stream.write(raw)
            except FileExistsError:
                if path.read_bytes() != raw:
                    raise ValueError("SOURCE_RAW_HASH_COLLISION")
            if sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("SOURCE_RAW_ARCHIVE_TAMPERED")
            record = {
                "source": source_name or clean, "url": clean,
                "request_started_at": start, "source_received_at": received,
                "source_bytes_verified": True, "source_publication_at": None,
                "source_publication_truth_verified": False,
                "last_modified_header_unverified": reported_modified,
                "http_status": http_status, "size_bytes": len(raw),
                "sha256": digest, "archive_path": str(path.relative_to(self.root)),
            }
            self.receipts[source_name or clean] = record
            return payload
        except Exception as exc:
            self.errors.append({"source": source_name or clean,
                                "reason": type(exc).__name__})
            raise

def parse_espn_schedule(payload):
    observed = {}
    for x in payload.get("events", []):
        try:
            competitors = x["competitions"][0]["competitors"]
            t = {v["homeAway"]: v["team"]["abbreviation"] for v in competitors}
            pair = (t["away"], t["home"])
            observed[pair] = (str(x["id"]), utc(instant(x["date"])))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    result, errors = [], []
    for event in expected_events():
        e = dict(event)
        pair = (e["away"], e["home"])
        match = observed.get(pair)
        e["espn_event_id"] = match[0] if match else None
        e["schedule_verified"] = bool(match and match[1] == e["scheduled_kickoff"])
        if not e["schedule_verified"]:
            errors.append({"fixture": e["fixture_key"],
                           "reason": "ESPN_SCHEDULE_MISSING_OR_DIFFERENT"})
        result.append(e)
    extra = sorted(set(observed) - {(e["away"], e["home"]) for e in result})
    if extra:
        errors.append({"reason": "ADDITIONAL_ESPN_GAMES", "pairs": extra})
    return result, errors

def roster_athletes(payload):
    found = []
    for group in payload.get("athletes") or []:
        if not isinstance(group, dict):
            continue
        for p in group.get("items") or group.get("athletes") or []:
            if not isinstance(p, dict):
                continue
            node = p.get("athlete", p)
            if not isinstance(node, dict):
                continue
            pos = node.get("position") or p.get("position") or {}
            if isinstance(pos, str):
                pos = {"abbreviation": pos}
            found.append({
                "id": node.get("id"), "fullName": node.get("fullName")
                    or node.get("displayName"),
                "position": pos, "status": node.get("status")
                    or p.get("status"),
            })
    return found

def depth_qb(payload):
    """Use only ESPN's first listed QB in its independently sourced depth order.

    ESPN's live /depthcharts API uses "depthchart" and nested "qb" entries.
    It has no explicit rank field: index zero is expected QB1, NOT verified
    game-day participation. Multiple disagreeing QB1 entries fail closed.
    """
    first = []
    charts = payload.get("depthchart") or payload.get("depthCharts") or []
    if not isinstance(charts, list):
        return None
    for chart in charts:
        if not isinstance(chart, dict):
            continue
        for key, pos in (chart.get("positions") or {}).items():
            if str(key).lower() not in ("qb", "quarterback"):
                continue
            ordered = pos.get("athletes") or []
            if not isinstance(ordered, list) or not ordered:
                continue
            head = ordered[0]
            player = head.get("athlete") or head
            if player.get("id"):
                first.append(str(player["id"]))
    if len(set(first)) != 1 or not first:
        return None
    return {"espn_player_id": first[0],
            "source": "ESPN_FIRST_LISTED_QB_DEPTH_ORDER",
            "source_only_expected": True}

def injuries_by_player(payload):
    out = {}
    containers = payload.get("injuries") or payload.get("athletes") or []
    for record in containers:
        if not isinstance(record, dict):
            continue
        athlete = record.get("athlete") or {}
        rid = athlete.get("id") or record.get("athleteId")
        status = record.get("status") or record.get("injuryStatus")
        if isinstance(status, dict):
            status = status.get("name") or status.get("description")
        if rid and status:
            out[str(rid)] = str(status)
    return out

def team_ids_from_schedule(payload, valid_pairs):
    selected = {}
    for e in payload.get("events", []):
        try:
            comps = e["competitions"][0]["competitors"]
            pair = {(v["team"]["abbreviation"], v["homeAway"]) for v in comps}
            if not any({(a, "away"), (h, "home")} <= pair for a, h in valid_pairs):
                continue
            for v in comps:
                team = v["team"]
                selected[team["abbreviation"]] = str(team["id"])
        except (KeyError, TypeError, IndexError):
            continue
    return selected

def fetch_team_context(cap, team, tid):
    result = {"team": team, "id": tid, "status": "PARTIAL"}
    for kind in ("roster", "depthcharts", "injuries"):
        url = ESPN_TEAM_BASE + tid + "/" + kind
        try:
            result[kind] = cap.fetch(url, timeout=12,
                                     source_name="espn_" + team + "_" + kind)
        except Exception as exc:
            result[kind + "_error"] = type(exc).__name__
    result["status"] = ("COMPLETE" if all(k in result for k in
                        ("roster", "depthcharts", "injuries")) else "PARTIAL")
    return result

def assert_no_running_capture(out_root):
    """Advisory lock, held via O_EXCL for this process; no concurrent Deepnote writer."""
    lock = Path(out_root) / "source_control" / ".capture.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock.open("x") as f:
            f.write(json.dumps({"started_at": now_utc(), "pid": os.getpid()}))
    except FileExistsError as e:
        raise RuntimeError("COMPETING_CAPTURE_LOCK_EXISTS:" + str(lock)) from e
    return lock

def run_capture(out_root, code_sha, include_history=False):
    out_root = Path(out_root)
    lock = assert_no_running_capture(out_root)
    cap = RawCapture(out_root)
    notes = []
    quotes, nfl_rows = [], []
    event_rows = [dict(v, espn_event_id=None, schedule_verified=False)
                  for v in expected_events()]
    team_ids = {}
    try:
        try:
            schedule = cap.fetch(ESPN_SCHEDULE, timeout=15, source_name="espn_schedule")
            event_rows, schedule_issues = parse_espn_schedule(schedule)
            notes.extend(schedule_issues)
            team_ids = team_ids_from_schedule(
                schedule, {(e["away"], e["home"]) for e in event_rows
                           if e["schedule_verified"]})
        except Exception as exc:
            notes.append({"reason": "SCHEDULE_CAPTURE_FAILED",
                          "error_type": type(exc).__name__})
        # The ONLY original offer pull in this process; one quota-guarded NFL
        # bulk request. Raw HTTP response bytes are archived before parsing.
        try:
            from odds_providers import PropLineProvider
            def raw_odds(url, timeout=15, headers=None):
                return cap.fetch(url, timeout=timeout, headers=headers,
                                 source_name="propline")
            provider = PropLineProvider(fetch=raw_odds)
            if not provider.api_key:
                notes.append({"reason": "PROPLINE_KEY_ABSENT"})
            elif os.environ.get("PICKEM_ODDS_QUOTA_GUARD") != "1":
                raise RuntimeError("PROPLINE_QUOTA_GUARD_NOT_ENABLED")
            else:
                quotes = provider.fetch(DAY, sports=["NFL"])
                if provider.note:
                    notes.append({"reason": "PROPLINE_PROVIDER_NOTE",
                                  "detail": provider.note[:3500]})
        except Exception as exc:
            notes.append({"reason": "ORIGINAL_QUOTES_CAPTURE_FAILED",
                          "error_type": type(exc).__name__})
        # Source-backed rosters, QB1 depth chart, and current injury context.
        context = {}
        if team_ids:
            with ThreadPoolExecutor(max_workers=6) as executor:
                tasks = {executor.submit(fetch_team_context, cap, team, tid): team
                         for team, tid in sorted(team_ids.items())}
                for task in as_completed(tasks):
                    team = tasks[task]
                    try:
                        context[team] = task.result()
                    except Exception as exc:
                        context[team] = {"team": team, "status": "UNAVAILABLE",
                                         "reason": type(exc).__name__}
        rosters, depth_qbs, injuries = {}, {}, {}
        for team, obj in context.items():
            roster_receipt = cap.receipts.get("espn_" + team + "_roster")
            rosters[team] = {
                "athletes": roster_athletes(obj.get("roster") or {}),
                "receipt_sha256": roster_receipt.get("sha256") if roster_receipt else None,
            }
            qb = depth_qb(obj.get("depthcharts") or {})
            if cap.receipts.get("espn_" + team + "_depthcharts"):
                depth_qbs[team] = qb
            injuries[team] = injuries_by_player(obj.get("injuries") or {})
        if include_history:
            try:
                # Historical data are copied only when actually source-available.
                # The player historical publication cutoff is not reconstructed.
                import fetch_slate as fs
                nfl_rows, history_notes = fs.fetch_nfl(
                    DAY, now_utc(), source_urls=[])
                notes.extend({"reason": "HISTORY_NOTE", "detail": str(s)[:250]}
                             for s in history_notes)
            except Exception as exc:
                notes.append({"reason": "HISTORY_UNAVAILABLE",
                              "error_type": type(exc).__name__})
        freeze = now_utc()
        for row in event_rows:
            receipt = cap.receipts.get("espn_schedule")
            row["source_sha256"] = receipt.get("sha256") if receipt else None
            row["source_received_at"] = receipt.get("source_received_at") if receipt else None
        manifest = build_universe(
            events=event_rows, quotes=quotes, quote_receipts=cap.receipts,
            rosters=rosters, depth_qbs=depth_qbs, injuries=injuries,
            nfl_rows=nfl_rows, freeze_at=freeze, code_sha=code_sha)
        manifest["runtime"] = {
            "source_owner": "NFL_SUNDAY_WS1_ONLY", "compute": "Deepnote_Basic_CPU",
            "no_training": True, "no_production_changes": True,
            "source_errors": cap.errors, "capture_notes": notes,
            "roster_team_count": len(rosters),
            "source_history_rows": len(nfl_rows),
            "schedule_verified_games": sum(e["schedule_verified"] for e in event_rows),
            "quote_provider": "PropLine",
            "quote_provider_supported_markets": 8,
            "quote_collector_native_raw_bytes": bool(cap.receipts.get("propline")),
            "c03_strict_cohorts": "NOT_INTEGRATED_IN_THIS_RESEARCH_CAPTURE",
            "control_probabilities": "NOT_GENERATED_OR_RECALCULATED",
            "capture_clock": freeze,
        }
        receipt = freeze_manifest(out_root, manifest)
        print(json.dumps({"status": "CAPTURED_RESEARCH_ONLY", "receipt": receipt,
                          "games": len(event_rows),
                          "games_verified": manifest["runtime"]["schedule_verified_games"],
                          "original_quotes": len(quotes),
                          "source_certified_quotes": manifest["source_certified_quotes"],
                          "forecast_eligible": manifest["forecast_eligible_contracts"],
                          "market_coverage": manifest["market_coverage"],
                          "failures": manifest["failures"],
                          "source_errors": cap.errors, "notes": notes},
                         sort_keys=True, indent=2), flush=True)
        return receipt
    finally:
        lock.unlink(missing_ok=True)

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", choices=[DAY], default=DAY)
    p.add_argument("--out-root", type=Path,
                   default=ROOT / "reports" / "nfl_20261115_prospective")
    p.add_argument("--code-sha", required=True)
    p.add_argument("--include-history", action="store_true")
    p.add_argument("--expand-markets", action="store_true",
                   help="Build versioned eleven-market extension from authenticated WS1 archives; no odds request")
    args = p.parse_args(argv)
    if args.expand_markets:
        from nfl_sunday_market_extension import build
        build()
        return
    run_capture(args.out_root, args.code_sha, include_history=args.include_history)

if __name__ == "__main__":
    main()

