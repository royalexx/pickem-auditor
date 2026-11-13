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
    from probability_blend import production_policy
    policy = production_policy(SKILL_ROOT)
    regime = '/' + policy['config_version'] if policy else ''
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"pickem-auditor-shadow/{game_date}/{slot}{regime}"))


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


def original_book_receipts(books: list[dict], source_quotes: list[dict] | None,
                           *, event_id=None) -> list[dict]:
    """Restore only uniquely matched ORIGINAL book quote retrieval clocks.

    The numerical candidate is not changed. Missing or ambiguous source
    timestamps stay missing so Phase 0 certification rejects those rows.
    """
    if not isinstance(source_quotes, list):
        return books
    receipts = []
    for book in books:
        try:
            side = book.get("book_side")
            if side not in ("over", "under"):
                raise ValueError("missing_original_quote_side")
            over = book.get("target") if side == "over" else book.get("other")
            under = book.get("other") if side == "over" else book.get("target")
            matches = [
                quote for quote in source_quotes
                if str(quote.get("book") or "").casefold() ==
                   str(book.get("book") or "").casefold()
                and float(quote.get("line")) == float(book.get("line"))
                and float(quote.get("over_odds")) == float(over)
                and float(quote.get("under_odds")) == float(under)
                and (not event_id or str(quote.get("event_id")) == str(event_id))
            ]
            stamps = {str(quote.get("retrieved_at") or "") for quote in matches}
            stamp = next(iter(stamps)) if len(stamps) == 1 and "" not in stamps else None
        except (ValueError, TypeError):
            over = under = stamp = None
        receipts.append({"book": book.get("book"), "line": book.get("line"),
                         "over": over, "under": under, "retrieved_at": stamp})
    return receipts


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
    quoted_books = candidate.get("books")
    quoted_consensus = result.get("consensus") or {}
    if isinstance(quoted_books, list) and quoted_books:
        # The production model can return a preliminary cross-market block
        # before independent Bayesian sidecars are available. Preserve the
        # separately validated bookmaker consensus from the SAME evaluation
        # rather than falsely treating that preliminary block as the quote.
        market = {
            **market,
            "market_valid": quoted_consensus.get("market_valid") is True,
            "line": quoted_consensus.get("line", candidate.get("line")),
            "retrieved_at": (candidate.get("market_retrieved_at")
                             or market.get("retrieved_at")),
            "books": original_book_receipts(
                quoted_books, meta.get("phase0_market_quotes"),
                event_id=candidate.get("event_id") or meta.get("event_id")),
            "receipt_basis": "evaluated_original_bookmaker_consensus",
        }
    line = candidate.get("line")
    rank = str(result.get("final_rank") or "Unranked")
    status = "UNRANKED" if rank == "Unranked" else "GRADED"
    retrieved = market.get("retrieved_at")
    record = {
        "forecast_at": meta.get('forecast_at'),
        "event_start": meta.get('event_start'),
        "model_input_binding": meta.get("model_input_binding"),
        "model_evaluation_started_at": meta.get("model_evaluation_started_at"),
        "model_fit_receipts": meta.get("model_fit_receipts"),
        "input_freeze_at": meta.get("input_freeze_at"),
        "input_freeze_basis": meta.get("input_freeze_basis"),
        "model_training_cutoff_at": meta.get("model_training_cutoff_at"),
        "model_training_cutoff_basis": meta.get("model_training_cutoff_basis"),
        "source_receipts": meta.get("source_receipts"),
        "used_source_ids": meta.get("used_source_ids"),
        "source_capture_at": meta.get("source_capture_at"),
        "source_capture_scope": meta.get("source_capture_scope"),
        "historical_usage_retrieved_at": meta.get("historical_usage_retrieved_at"),
        "source_capture_error": meta.get("source_capture_error"),
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
    # Provider-backed IDs may be numeric (notably official NHL player IDs).
    # Preserve their exact digits as a string for source-linked contract keys.
    if (record.get("player_id") is not None and
            not isinstance(record["player_id"], bool)):
        record["player_id"] = str(record["player_id"])
    blend = result.get('blend') or {}
    if blend.get('production_policy'):
        # A is still visible as a component when consensus must abstain.
        # It must never be serialized as if it were the production consensus.
        available = blend.get('available') is True
        win = grade.get('q_model') if grade else blend.get('q_win')
        push = grade.get('q_push') if grade else blend.get('q_push')
        record.update(q_model=win if available else None,
                      q_win=win if available else None,
                      q_push=push if available else None)
        if blend.get('preliminary'):
            # Historical Bayesian/NUTS sidecars have not run yet.
            # Never put the preliminary A/B forecast in a production field.
            record.update(q_model=None, q_win=None, q_push=None,
                          production_preview={'q_win':blend.get('q_win'),
                                              'q_push':blend.get('q_push'),
                                              'version':blend.get('version'),
                                              'purpose':'nonproduction_intermediate'})
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


def phase0r_live_candidate_rejection(candidate: dict, *, source_quotes, event_id, now) -> str | None:
    """Fail closed before live numerical inference when an input is unverifiable.

    This is a source-eligibility screen, NOT a calibration or ranking filter.
    The original prepared candidate is kept in the append-only attempt ledger.
    The final independent strict certificate is separately checked after inference.
    """
    # The present event-context evaluator can consult external event facts
    # that are not independently pinned. Never silently drop context and
    # predict a baseline in its place, especially for questionable/out players.
    if candidate.get("event_context"):
        return "pre_eval_external_context_unpinned"
    books = candidate.get("books")
    if not isinstance(books, list) or not books or candidate.get("q_market") is not None:
        return "market_unavailable_or_unverified"
    if candidate.get("market_valid") is False:
        return "market_unavailable_or_unverified"
    try:
        if now is None or now.tzinfo is None:
            return "market_unavailable_or_unverified"
        stamp = parse_iso_utc(candidate.get("market_retrieved_at"))
        if stamp is None or not 0 <= (now - stamp).total_seconds() <= 30 * 60:
            return "market_unavailable_or_unverified"
        matched = original_book_receipts(books, source_quotes, event_id=event_id)
        if len(matched) != len(books):
            return "market_unavailable_or_unverified"
        for quote in matched:
            retrieved = parse_iso_utc(quote.get("retrieved_at"))
            if retrieved is None or retrieved > now:
                return "market_unavailable_or_unverified"
        prepared_books = pm._books_from_payload(books)
        if pm._orient_books(prepared_books, candidate.get("side")):
            return "market_unavailable_or_unverified"
        consensus = pm.consensus(pm._consensus_tuples(prepared_books),
                                 (now - stamp).total_seconds() / 60)
        if (consensus.get("market_valid") is not True
                or float(consensus.get("line")) != float(candidate.get("line"))):
            return "market_unavailable_or_unverified"
    except (pm.PickemError, TypeError, KeyError, ValueError, OverflowError):
        return "market_unavailable_or_unverified"
    return None


def run_pipeline_batch(rows: list[dict], *, now=None, data_root=None, clock_fn=None,
                       attempt_receipts: list[dict] | None = None) -> tuple[list[dict], int]:
    """Evaluate the COMPLETE prepared slate, not the triage queue or top-10.

    A caller may record every input and its result without changing either
    the probability algorithm or the return contract. Rejected evaluations
    are explicitly visible in that optional receipt.
    """
    snapshots: list[dict] = []
    errors = 0
    for row in rows:
        evaluation_now=clock_fn() if clock_fn else now
        meta=dict(row.get('_meta') or {})
        audit={"id":row.get("id"),"sport":meta.get("sport"),
               "player_id":meta.get("player_id"),"stat":meta.get("stat"),
               "side":row.get("side"),"line":row.get("line"),
               "event_start":meta.get("event_start"),
               "attempted_at":evaluation_now.isoformat() if evaluation_now else None}
        def mark(status,reason=None):
            if attempt_receipts is not None:
                attempt_receipts.append({**audit,"status":status,"reason":reason})
        if evaluation_now and meta.get('event_start') and game_started(meta['event_start'],evaluation_now):
            mark("unavailable","event_started_before_evaluation")
            continue
        if evaluation_now:meta['forecast_at']=evaluation_now.isoformat()
        if isinstance(row.get("_phase0_market_quotes"), list):
            meta["phase0_market_quotes"] = row["_phase0_market_quotes"]
        candidate = _pipeline_input(row)
        # User policy: unverifiable contracts never enter the live prediction
        # pool. Retain their identities and reasons in the attempt ledger.
        certified_only = (os.environ.get("PICKEM_PRODUCTION_CONSENSUS") == "1"
                          or os.environ.get("PICKEM_PHASE0_CERTIFIED_ONLY") == "1")
        # C03 is a separate, opt-in strict-source experimental route. It may
        # not bypass an unavailable source or the independent Phase 0R gate.
        c03_original = None
        c03_claims = row.get("_c03_claims") or []
        c03_receipts = row.get("_c03_source_receipts") or []
        c03_binding = None
        c03_original_archive = None
        c03_enabled = (certified_only and
                       os.environ.get("PICKEM_C03_V2_SHADOW") == "1")
        if c03_enabled:
            if row.get("_c03_capture_issue"):
                mark("unavailable","c03_v2:"+str(row["_c03_capture_issue"])[:220])
                continue
            from c03_context_cohorts import classify
            c03_check = classify(
                candidate, claims=c03_claims, source_receipts=c03_receipts,
                archive_root=Path(data_root or SKILL_ROOT / "data") / "source_archives",
                input_freeze_at=evaluation_now.isoformat() if evaluation_now else "",
                event_start_at=meta.get("event_start") or "",
            )
            if c03_check["cohort"] == "D":
                mark("unavailable", "c03_v2:" + c03_check["reason"])
                continue
            if c03_check["cohort"] == "B":
                c03_original = candidate
                # Original evaluated input must be captured BEFORE the
                # numerical pre-evaluation freeze, not afterward.
                from c03_context_cohorts import archive_original_candidate
                try:
                    c03_original_archive = archive_original_candidate(
                        c03_original,
                        Path(data_root or SKILL_ROOT / "data") / "source_archives",
                        possessed_at=evaluation_now.isoformat() if evaluation_now else None)
                except (OSError,ValueError,TypeError) as exc:
                    mark("unavailable","c03_v2:original_source_capture_failed:"+
                         type(exc).__name__)
                    continue
                candidate = c03_check["neutral_candidate"]
        if certified_only:
            exclusion = phase0r_live_candidate_rejection(
                candidate, source_quotes=meta.get("phase0_market_quotes"),
                event_id=candidate.get("event_id") or meta.get("event_id"),
                now=evaluation_now,
            )
            if exclusion is not None:
                mark("unavailable", exclusion)
                continue
        from usage_baseline import using_directory
        from probability_blend import using_production
        capture_enabled = (certified_only
                           or os.environ.get("PICKEM_PHASE0_CAPTURE") == "1")
        pre_eval_error = None
        if capture_enabled:
            try:
                from phase0_pre_eval import pin
                with pin(
                    candidate, data_root=Path(data_root or SKILL_ROOT / "data"),
                    archive_root=Path(data_root or SKILL_ROOT / "data") / "source_archives",
                    policy_root=SKILL_ROOT,
                    clock=clock_fn or (lambda: datetime.now(timezone.utc)),
                    identity={key: meta.get(key) for key in
                              ("sport", "player_id", "stat", "game_date")},
                ) as (pinned_evidence, pinned_root, pinned_candidate):
                    # The model sees precisely the candidate, history, lineup
                    # and production policy bytes stored by the archive.
                    evaluation_at = datetime.fromisoformat(
                        pinned_evidence["input_freeze_at"].replace("Z", "+00:00"))
                    if c03_original is not None:
                        # Revalidate against the TRUE pre-evaluation freeze, not
                        # the earlier provisional candidate-screen timestamp.
                        from c03_context_cohorts import (
                            classify as c03_classify, neutral_digest,
                        )
                        c03_frozen = c03_classify(
                            c03_original, claims=c03_claims,
                            source_receipts=c03_receipts,
                            archive_root=Path(data_root or SKILL_ROOT / "data") / "source_archives",
                            input_freeze_at=pinned_evidence["input_freeze_at"],
                            event_start_at=meta.get("event_start") or "",
                        )
                        if (c03_frozen["cohort"] != "B" or
                                neutral_digest(c03_frozen["neutral_candidate"]) !=
                                neutral_digest(pinned_candidate)):
                            mark("unavailable", "c03_v2:frozen_cohort_or_neutral_input_changed")
                            continue
                        c03_binding = c03_frozen["binding"]
                        c03_binding["premerge_collector_receipt"]=row.get("_c03_premerge_receipt")
                        if isinstance(row.get("_c03_official_nhl_rosters"), dict):
                            # Explicit independent official roster artifacts are
                            # separately validated by the v2 strict checker.
                            c03_binding["official_nhl_roster_receipts"] = (
                                row["_c03_official_nhl_rosters"])
                    if (meta.get("event_start")
                            and game_started(meta["event_start"], evaluation_at)):
                        mark("unavailable", "event_started_before_input_freeze")
                        continue
                    with using_directory(pinned_root), using_production(pinned_root):
                        result = pm.evaluate_candidate(pinned_candidate, now=evaluation_at)
                    meta.update(pinned_evidence)
                    meta["model_evaluation_started_at"] = evaluation_at.isoformat()
                    meta["model_fit_receipts"] = [
                        {"component": "Engine_A", "fit_mode": "on_demand",
                         "training_data_cutoff_at": pinned_evidence["input_freeze_at"]},
                        {"component": "Engine_B", "fit_mode": "rule_based",
                         "training_data_cutoff_at": pinned_evidence["input_freeze_at"]},
                    ]
            except pm.PickemError as exc:
                errors += 1
                mark("unavailable", "pipeline_exception:" + str(exc)[:160])
                continue
            except (OSError, ValueError, KeyError, TypeError) as exc:
                # A missing or oversized source must never generate a fake
                # certification. The legacy result remains a research shadow.
                pre_eval_error = type(exc).__name__ + ":" + str(exc)[:180]
                if certified_only:
                    # Never fall back to mutable source data when strict
                    # certification is required by the live workflow.
                    mark("unavailable", "phase0r_source_capture_failed:" + pre_eval_error)
                    continue
        if not capture_enabled or pre_eval_error is not None:
            if pre_eval_error is not None:
                meta["source_capture_error"] = pre_eval_error
            try:
                with using_directory(data_root or SKILL_ROOT / "data"), using_production(SKILL_ROOT):
                    result = pm.evaluate_candidate(candidate, now=evaluation_now)
            except pm.PickemError as exc:
                errors += 1
                mark("unavailable", "pipeline_exception:" + str(exc)[:160])
                continue
        if not result.get("ok"):
            errors += 1
            mark("unavailable", "pipeline_not_ok:" +
                 str(result.get("error") or result.get("reason") or "unknown")[:160])
            continue
        parsed = parse_pipeline_id(result.get("id") or row.get("id"))
        if not parsed:
            errors += 1
            mark("unavailable", "invalid_pipeline_candidate_id")
            continue
        sport, player, stat, _side = parsed
        frozen_at = clock_fn() if clock_fn else (evaluation_now or datetime.now(timezone.utc))
        if frozen_at.tzinfo is None:
            errors += 1
            mark("unavailable", "naive_freeze_clock")
            continue
        if meta.get("event_start") and game_started(meta["event_start"], frozen_at):
            mark("unavailable", "event_started_before_forecast_freeze")
            continue
        # Do not repair missing input receipts by assigning the publish time.
        # Only phase0_input_capture may attest the original pregame freeze.
        meta["forecast_at"] = frozen_at.isoformat()
        forecast = pipeline_to_snapshot(
            result,
            meta=meta,
            run_id=row["_run_id"],
            run_at=row["_run_at"],
            candidate=candidate,
        )
        if certified_only:
            # The old v1 independent validator remains authoritative for A.
            # B requires BOTH neutral v1 verification and a second v2 source
            # validator. Context adjustments never enter this baseline path.
            from phase0r_contract import strict_snapshot_status
            source_root = Path(data_root or SKILL_ROOT / "data")
            if c03_original is not None:
                from c03_context_cohorts import strict_c03_snapshot_status
                if c03_binding is None or c03_original_archive is None:
                    mark("unavailable", "c03_v2:original_or_binding_missing")
                    continue
                c03_binding["original_candidate_receipt"] = c03_original_archive
                forecast["c03_context_binding"] = c03_binding
                forecast["c03_original_candidate"] = c03_original
                accepted, reason = strict_c03_snapshot_status(
                    forecast, archive_root=source_root / "source_archives")
            else:
                accepted, reason = strict_snapshot_status(
                    forecast, archive_root=source_root / "source_archives")
            if not accepted:
                mark("unavailable", "phase0r_strict_rejected:" + reason)
                continue
            forecast["phase0r_original_source_certified"] = True
            if c03_enabled:
                forecast["c03_cohort"] = ("B" if c03_original is not None else "A")
                forecast["c03_context_adjusted"] = False
        if c03_enabled and c03_original is not None:
            # Research source certification is not selection authorization.
            # Never let a verified-but-not-independent-review-approved B cohort
            # enter legacy production snapshots, ranking or publication merely
            # because the C03 flag was switched on. Audit denominator retained.
            mark("unavailable", "c03_v2_cohort_b_shadow_only_no_production_selection")
            continue
        snapshots.append(forecast)
        mark("forecast")
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

    # Before ANY research/availability merge, capture the ORIGINAL
    # collector-prepared numeric candidate in an immutable archive. Research
    # status is not allowed to back-fill or change this source. Disabled in
    # the legacy/default runner.
    if os.environ.get("PICKEM_C03_V2_SHADOW") == "1" and (
            os.environ.get("PICKEM_PRODUCTION_CONSENSUS") == "1" or
            os.environ.get("PICKEM_PHASE0_CERTIFIED_ONLY") == "1"):
        from c03_context_cohorts import archive_original_candidate
        premerge_root=slate_path.parent / "source_archives"
        for source_premerge in pipeline_rows:
            stamp_at=clock_fn()
            if stamp_at.tzinfo is None:
                raise JobError("C03_PREMERGE_NAIVE_CLOCK")
            source_premerge["_c03_premerge_receipt"]=archive_original_candidate(
                {k:v for k,v in source_premerge.items() if not str(k).startswith("_")},
                premerge_root,possessed_at=stamp_at.isoformat())
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
    # Opt-in research capture ONLY. Real HTTPS original response body and
    # named player/event claim are required. Propline IDs are NOT silently
    # treated as ESPN IDs, and a missing crosswalk is an explicit abstention.
    # This does NOT authorize context cohort B for publishing/ranking.
    if os.environ.get("PICKEM_C03_V2_SHADOW") == "1" and (
            os.environ.get("PICKEM_PRODUCTION_CONSENSUS") == "1" or
            os.environ.get("PICKEM_PHASE0_CERTIFIED_ONLY") == "1"):
        from c03_pregame_live_capture import annotate_prepared_candidates
        pipeline_rows = annotate_prepared_candidates(
            pipeline_rows,archive_root=slate_path.parent/"source_archives")
    # Stage original per-book source clocks ONLY inside the scheduled job.
    # Do not alter fetch_slate.prepare_pipeline's public numerical schema,
    # which is also used directly by offline research and engine tests.
    for prepared in pipeline_rows:
        parsed = parse_pipeline_id(prepared.get("id"))
        if not parsed:
            continue
        sport, player, stat, _side = parsed
        source_row = slate_by_key.get((sport, player, stat))
        if source_row is None:
            continue
        original_quotes = quotes_for_row(quotes, source_row)
        try:
            line = float(prepared.get("line"))
            original_quotes = [q for q in original_quotes
                               if q.get("line") is not None and
                               float(q["line"]) == line]
        except (TypeError, ValueError):
            original_quotes = []
        prepared["_phase0_market_quotes"] = [
            {k: quote.get(k) for k in
             ("book", "line", "over_odds", "under_odds",
              "retrieved_at", "event_id")}
            for quote in original_quotes
        ]
    # The complete prepared candidate universe is evaluated before ranking.
    # Retain one receipt per input, including inputs that cannot be predicted.
    evaluated_contracts=[]
    snapshots, pipeline_errors = run_pipeline_batch(
        pipeline_rows,now=now,data_root=slate_path.parent,
        clock_fn=clock_fn,attempt_receipts=evaluated_contracts)
    if len(evaluated_contracts)!=len(pipeline_rows):
        raise JobError("PIPELINE_UNIVERSE_AUDIT_INCOMPLETE")
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

    # Auditable all-market coverage, even when only the highest-ranked ten
    # are shown in the user-facing probability comparison.
    from collections import Counter
    outcomes=Counter(item["status"] for item in evaluated_contracts)
    by_stat=Counter(str(item.get("sport"))+"|"+str(item.get("stat")) for item in evaluated_contracts)
    strict_live_policy = (os.environ.get("PICKEM_PRODUCTION_CONSENSUS") == "1"
                          or os.environ.get("PICKEM_PHASE0_CERTIFIED_ONLY") == "1")
    eligibility_by_sport = {}
    for sport in sorted({str(x.get("sport")) for x in evaluated_contracts}):
        eligible = [x for x in evaluated_contracts if str(x.get("sport")) == sport]
        eligibility_by_sport[sport] = {
            "prepared": len(eligible),
            "certified_forecast": sum(x["status"] == "forecast" for x in eligible)
                                  if strict_live_policy else None,
            "unavailable": sum(x["status"] == "unavailable" for x in eligible),
        }
    scope_receipt={
        "schema":"all_prepared_props_attempts_v1","date":game_date,"run_id":run_id,
        "source_player_stat_rows":len(rows),
        "normalized_two_sided_quote_rows":len(quotes),
        "forecast_pool_policy": ("strict_certified_only_original_inputs_v1"
                                  if strict_live_policy else "legacy_research_pool"),
        "certification_exclusion_is_not_random":True,
        "all_prepared_contracts_in_coverage_denominator":True,
        "certified_forecast_contracts":outcomes["forecast"] if strict_live_policy else None,
        "excluded_from_prediction_pool":outcomes["unavailable"]
                                         if strict_live_policy else None,
        "eligibility_by_sport":eligibility_by_sport,
        "prepared_contracts":len(evaluated_contracts),
        "forecast_contracts":outcomes["forecast"],
        "unavailable_contracts":outcomes["unavailable"],
        "by_stat":dict(sorted(by_stat.items())),
        "unavailable_reasons":dict(Counter(item.get("reason") or "unknown" for item in
            evaluated_contracts if item["status"]=="unavailable")),
        "all_prepared_contracts_attempted":True,
        "no_top10_or_triage_pre_filter":True,
        "scope":"primary_comparable_two_sided_line_per_player_stat",
        "attempts":evaluated_contracts}
    report_path=SKILL_ROOT/"reports"/"all_prepared_props_attempts.json"
    report_path.parent.mkdir(parents=True,exist_ok=True)
    pending=report_path.with_suffix(".tmp")
    pending.write_text(json.dumps(scope_receipt,sort_keys=True,indent=2,allow_nan=False)+"\n",
                       encoding="utf-8")
    os.replace(pending,report_path)

    phase15_factor_capture = None
    if os.environ.get("PICKEM_PHASE15_FACTOR_CAPTURE") == "1":
        try:
            from v2.phase15_pregame_factors import integrate_shadow_factor_capture

            phase15_factor_capture = integrate_shadow_factor_capture(
                evaluated_contracts,
                run_id=run_id,
                output_root=SKILL_ROOT / "reports",
                observed_clock=now,
                data_root=slate_path.parent,
            )
        except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
            phase15_factor_capture = {
                "captured": False,
                "reason": "shadow_factor_capture_failed:" + type(exc).__name__,
            }

    return {
        "job": "snapshot",
        "universe_receipt":"reports/all_prepared_props_attempts.json",
        "prepared_contracts":len(evaluated_contracts),
        "forecast_contracts":outcomes["forecast"],
        "unavailable_contracts":outcomes["unavailable"],
        "rows_written": written,
        "skipped": skipped_started + skipped_dup,
        "errors": pipeline_errors,
        "lineup_collection":lineup_collection,
        "preflight_feeds_ready": report.get("feeds_ready"),
        "preflight_partial": not bool(report.get("ok")),
        "phase15_factor_capture": phase15_factor_capture,
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
