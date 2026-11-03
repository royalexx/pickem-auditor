#!/usr/bin/env python3
"""Timestamped, append-only player-prop odds archive and read-only calibration.

Consumes ONLY already-collected, approved two-sided price records. Never calls
a sportsbook API, scrapes a website, changes training, or changes forecasts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from odds_providers import approved_book_name, canon_stat, normalize_player, normalize_team

EASTERN = ZoneInfo("America/Toronto")
PHASES = ("morning", "afternoon", "pregame")
SCHEMA = "pickem_market_odds_snapshot_v1"
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


def utc(value) -> datetime | None:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if result.tzinfo is None:
        return None
    return result.astimezone(timezone.utc)


def stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def digest(data) -> str:
    return hashlib.sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


def atomic_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=".odds-", suffix=".tmp",
            delete=False) as handle:
            tmp = Path(handle.name)
            json.dump(payload, handle, sort_keys=True, indent=2,
                      ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    result = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid_jsonl_row_{lineno}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"invalid_jsonl_object_{lineno}")
        result.append(value)
    return result


def valid_american(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and abs(value) >= 100)


def normalize_quote(raw: dict, *, date_text: str, observed: datetime) -> tuple[dict | None, str]:
    if not isinstance(raw, dict):
        return None, "invalid_row"
    bookmaker = approved_book_name(raw.get("book"))
    stat = canon_stat(raw.get("stat"))
    sport = str(raw.get("sport") or "").upper()
    player = " ".join(str(raw.get("player") or "").split())
    player_key = normalize_player(player)
    start = utc(raw.get("event_start"))
    updated = utc(raw.get("retrieved_at"))
    line = raw.get("line")
    if bookmaker is None or not stat or sport not in ("NHL", "NBA", "NFL"):
        return None, "unapproved_market"
    if not player_key or not raw.get("event_id") or not start:
        return None, "missing_event_identity_or_start"
    if (start.astimezone(EASTERN).date().isoformat() != date_text
            or raw.get("game_date") not in (None, "", date_text)):
        return None, "wrong_slate_date"
    if observed >= start:
        return None, "event_already_started"
    if not updated or updated > observed:
        return None, "market_update_unverified_or_future"
    if (not isinstance(line, (int, float)) or isinstance(line, bool)
            or not math.isfinite(line) or line < 0
            or not valid_american(raw.get("over_odds"))
            or not valid_american(raw.get("under_odds"))):
        return None, "not_two_sided_numeric_quote"
    source = str(raw.get("source_url") or "")
    host = urlsplit(source).hostname or ""
    if "underdog" in host.lower() or "underdog" in bookmaker.lower():
        return None, "unapproved_market"
    record = {
        "sport": sport, "game_date": date_text,
        "event_id": str(raw["event_id"]),
        "event_id_namespace": str(raw.get("event_id_namespace") or ""),
        "event_start": stamp(start),
        "team": normalize_team(raw.get("team")),
        "opponent": normalize_team(raw.get("opponent")),
        "player": player, "player_norm": player_key,
        "stat": stat, "book": bookmaker, "line": float(line),
        "over_odds": int(raw["over_odds"]) if int(raw["over_odds"]) == raw["over_odds"] else raw["over_odds"],
        "under_odds": int(raw["under_odds"]) if int(raw["under_odds"]) == raw["under_odds"] else raw["under_odds"],
        "market_updated_at": stamp(updated),
        "source_host": host,
    }
    record["quote_sha256"] = digest(record)
    return record, "accepted"


def capture_records(quotes: list[dict], *, phase: str, slate_date: str,
                    observed_at: str, archive_root: Path, capture_id: str,
                    source_status: str = "provided", receipt_out: Path | None = None) -> dict:
    if phase not in PHASES or not IDENTIFIER.fullmatch(capture_id):
        raise ValueError("invalid_capture_phase_or_id")
    date.fromisoformat(slate_date)
    observed = utc(observed_at)
    if observed is None or observed.astimezone(EASTERN).date().isoformat() != slate_date:
        raise ValueError("missing_or_wrong_date_source_capture_timestamp")
    counts: Counter = Counter()
    dedup = {}
    for raw in quotes:
        row, reason = normalize_quote(raw, date_text=slate_date, observed=observed)
        counts[reason] += 1
        if row is not None:
            dedup[row["quote_sha256"]] = row
    rows = sorted(dedup.values(), key=lambda q: (
        q["sport"], q["event_id"], q["player_norm"], q["stat"],
        q["book"], q["line"], q["quote_sha256"]))
    document = {
        "schema": SCHEMA, "date": slate_date, "phase": phase,
        "capture_id": capture_id, "observed_at": stamp(observed),
        "source_status": str(source_status or "unknown"),
        "status": "captured" if rows else "no_eligible_market_quotes",
        "quote_count": len(rows), "input_quote_count": len(quotes),
        "exclusions": dict(sorted(counts.items())), "quotes": rows,
        "uses_only_existing_collector_quotes": True,
        "api_requests_added": 0, "changes_original_predictions": False,
    }
    document["snapshot_sha256"] = digest(document)
    path = Path(archive_root) / slate_date / phase / (capture_id + ".json")
    if path.exists():
        original = json.loads(path.read_text(encoding="utf-8"))
        if original != document:
            raise ValueError("immutable_market_odds_capture_conflict")
    else:
        # Exclusive creation: parallel runs cannot silently overwrite a capture.
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8") as handle:
                json.dump(document, handle, sort_keys=True, indent=2,
                          ensure_ascii=False, allow_nan=False)
                handle.write("\n")
        except FileExistsError:
            if json.loads(path.read_text(encoding="utf-8")) != document:
                raise ValueError("immutable_market_odds_capture_conflict")
    receipt = {k: v for k, v in document.items() if k != "quotes"}
    receipt["archive_path"] = str(path)
    if receipt_out:
        atomic_json(Path(receipt_out), receipt)
    return receipt


def implied(american: float) -> float:
    return (-american / (100 - american)) if american < 0 else 100 / (american + 100)


def no_vig_probability(quote: dict, side: str) -> float:
    over = implied(quote["over_odds"])
    under = implied(quote["under_odds"])
    return (over if side == "over" else under) / (over + under)


def candidates_for_forecast(forecast: dict, documents: list[dict], *,
                            until: datetime, phases: tuple[str, ...]) -> list[tuple[datetime, dict]]:
    player_key = normalize_player(forecast.get("player"))
    line = forecast.get("reference_line")
    if not player_key or not isinstance(line, (int, float)) or isinstance(line, bool):
        return []
    if not math.isfinite(line):
        return []
    match = []
    for doc in documents:
        if doc.get("phase") not in phases or doc.get("schema") != SCHEMA:
            continue
        observed = utc(doc.get("observed_at"))
        if not observed or observed > until:
            continue
        for q in doc.get("quotes") or []:
            if (q.get("sport") != forecast.get("sport")
                    or q.get("game_date") != forecast.get("game_date")
                    or q.get("event_id") != str(forecast.get("event_id") or "")
                    or q.get("player_norm") != player_key
                    or q.get("stat") != forecast.get("stat")
                    or q.get("line") != float(line)):
                continue
            if (forecast.get("event_id_namespace") and q.get("event_id_namespace")
                    and forecast["event_id_namespace"] != q["event_id_namespace"]):
                continue
            if (forecast.get("team") and q.get("team")
                    and normalize_team(forecast["team"]) != q["team"]):
                continue
            start = utc(q.get("event_start"))
            updated = utc(q.get("market_updated_at"))
            if not start or until >= start or not updated or updated > observed:
                continue
            match.append((observed, q))
    return match


def evaluate(*, archives: Path, forecasts: Path, slate_date: str | None = None) -> dict:
    documents = []
    for path in sorted(Path(archives).glob("*/*/*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("schema") != SCHEMA:
            raise ValueError(f"unrecognized_odds_snapshot_{path.name}")
        hash_value = doc.get("snapshot_sha256")
        if digest({k: v for k, v in doc.items() if k != "snapshot_sha256"}) != hash_value:
            raise ValueError(f"modified_market_odds_snapshot_{path.name}")
        documents.append(doc)
    records, excluded = [], Counter()
    rows = read_jsonl(Path(forecasts))
    seen_forecasts = set()
    for f in rows:
        if slate_date and f.get("game_date") != slate_date:
            continue
        side = str(f.get("side") or "").lower()
        if side not in ("over", "under"):
            excluded["unknown_side"] += 1
            continue
        forecast_at = utc(f.get("forecast_at"))
        event_start = utc(f.get("event_start"))
        if not forecast_at or not event_start or forecast_at >= event_start:
            excluded["forecast_timestamp_missing_or_poststart"] += 1
            continue
        key = (f.get("run_id"), f.get("game_date"), f.get("sport"),
               f.get("event_id"), normalize_player(f.get("player")),
               f.get("stat"), side, f.get("reference_line"))
        if key in seen_forecasts:
            excluded["duplicate_forecast"] += 1
            continue
        seen_forecasts.add(key)
        quotes = candidates_for_forecast(f, documents, until=forecast_at,
                                         phases=("morning", "afternoon"))
        if not quotes:
            excluded["no_historical_same_line_market"] += 1
            continue
        newest = max(t for t, _ in quotes)
        selected = {}
        for at, q in quotes:
            if at == newest:
                # Preserve each bookmaker's independent price, never mix lines.
                prior = selected.get(q["book"])
                if prior is None or q["market_updated_at"] > prior["market_updated_at"]:
                    selected[q["book"]] = q
        probs = [no_vig_probability(q, side) for q in selected.values()]
        if not probs:
            excluded["no_two_sided_books"] += 1
            continue
        status = str(f.get("outcome") or "").lower()
        actual = f.get("actual_stat")
        settled = (status in ("win", "loss", "push") and
                   isinstance(actual, (int, float)) and not isinstance(actual, bool) and
                   math.isfinite(actual))
        model = f.get("q_model")
        valid_model = (isinstance(model, (int, float)) and not isinstance(model, bool)
                       and math.isfinite(model) and 0 <= model <= 1)
        y = 1 if status == "win" else 0 if status == "loss" else None
        market_q = statistics.median(probs)
        record = {
            "game_date": f.get("game_date"), "sport": f.get("sport"),
            "event_id": f.get("event_id"), "player": f.get("player"),
            "stat": f.get("stat"), "side": side,
            "line": f.get("reference_line"), "run_id": f.get("run_id"),
            "forecast_at": stamp(forecast_at), "odds_observed_at": stamp(newest),
            "book_count": len(selected), "bookmakers": sorted(selected),
            "market_no_vig_probability": round(market_q, 6),
            "model_probability": float(model) if valid_model else None,
            "outcome": status if settled else "pending",
            "actual_stat": actual if settled else None,
            "score_eligible": bool(settled and y is not None and valid_model),
            "model_market_gap_at_forecast": round(model - market_q, 6) if valid_model else None,
        }
        if record["score_eligible"]:
            record["model_brier"] = round((model - y) ** 2, 9)
            record["market_brier"] = round((market_q - y) ** 2, 9)
        records.append(record)
    by_market = defaultdict(list)
    for row in records:
        if row["score_eligible"]:
            by_market[(row["sport"], row["stat"])].append(row)
    scores = {}
    for (sport, stat), batch in sorted(by_market.items()):
        scores[f"{sport}:{stat}"] = {
            "settled_nonpush_count": len(batch),
            "model_brier": round(statistics.mean(x["model_brier"] for x in batch), 6),
            "market_brier": round(statistics.mean(x["market_brier"] for x in batch), 6),
            "model_beats_market_brier": (statistics.mean(x["model_brier"] for x in batch)
                                         < statistics.mean(x["market_brier"] for x in batch)),
        }
    return {
        "schema": "pickem_market_odds_evaluation_v1",
        "date_filter": slate_date,
        "status": "calculated" if scores else "insufficient_matched_settled_samples",
        "archived_snapshots_checked": len(documents),
        "forecasts_checked": len(seen_forecasts),
        "same_line_market_matches": len(records),
        "settled_nonpush_scored": sum(len(x) for x in by_market.values()),
        "excluded": dict(sorted(excluded.items())),
        "by_sport_market": scores, "matches": records,
        "changes_model_weights": False, "ranking_allowed": False,
        "no_backfilled_or_post_forecast_odds": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("--phase", required=True, choices=PHASES)
    capture.add_argument("--date", required=True)
    capture.add_argument("--quotes", default="data/odds_quotes.jsonl")
    capture.add_argument("--source-meta", default="data/slate_fetch.meta.json")
    capture.add_argument("--observed-at", help="Explicit actual quote capture timestamp (not inferred from file mtime)")
    capture.add_argument("--archive-root", default="data/market_odds_history")
    capture.add_argument("--capture-id")
    capture.add_argument("--out", default="reports/market_odds_capture.json")
    evaluation = sub.add_parser("evaluate")
    evaluation.add_argument("--archive-root", default="data/market_odds_history")
    evaluation.add_argument("--forecasts", default="data/prop_snapshots.jsonl")
    evaluation.add_argument("--date")
    evaluation.add_argument("--out", default="reports/market_odds_evaluation.json")
    args = parser.parse_args(argv)
    if args.command == "capture":
        meta = {}
        meta_path = Path(args.source_meta)
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        observed = args.observed_at or meta.get("retrieved_at")
        if utc(observed) is None:
            # Missing collector timestamp means no trusted contemporaneous odds.
            raise ValueError("cannot_archive_odds_without_authenticated_capture_timestamp")
        run_id = args.capture_id or os.environ.get("GITHUB_RUN_ID") or datetime.now(timezone.utc).strftime("local-%Y%m%dT%H%M%S%f")
        attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
        identifier = f"{run_id}-{attempt}"
        quotes = read_jsonl(Path(args.quotes))
        receipt = capture_records(
            quotes, phase=args.phase, slate_date=args.date,
            observed_at=observed, archive_root=Path(args.archive_root),
            capture_id=identifier,
            source_status=str(((meta.get("feeds") or {}).get("odds") or {}).get("status") or "provided"),
            receipt_out=Path(args.out))
        print(json.dumps(receipt, sort_keys=True))
    else:
        report = evaluate(archives=Path(args.archive_root),
                          forecasts=Path(args.forecasts), slate_date=args.date)
        atomic_json(Path(args.out), report)
        print(json.dumps({k: v for k, v in report.items() if k != "matches"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
