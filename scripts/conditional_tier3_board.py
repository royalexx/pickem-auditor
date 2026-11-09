#!/usr/bin/env python3
"""Opt-in Conditional Tier 3, kept separate from verified Tier 1-3 picks.

Waives only explicit current-game ACTIVE evidence when five complete prior
team rosters prove high continuity. Requires all other real-source, probability,
opponent-evidence and fresh-price checks. Never mutates source forecasts.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from nfl_volume_market_policy import nfl_volume_market_allowed
import pickem_math as pm
from automated_scouting_review import evaluate as machine_review
from mechanism_evidence import assess as assess_mechanism
from pick_verification import (forecast_digest, quote_refresh, review_verified,
                               status_verified, utc_time, write_atomic)
from research_ranked_board import build as research_board
from research_triage import latest_batch, packet_game_key
from tier_quality import assess as assess_tier
from recent_lineup_tendency import evaluate as tendency_check

VERSION = "conditional-tier3-v1"
ACCEPTABLE_UNKNOWN = frozenset((
    "GAME_SPECIFIC_ACTIVE_STATUS_MISSING",
    "STATUS_NOT_FROM_EXPLICIT_GAME_REPORT",
    "ACTIVE_STATUS_STALE_OR_INVALID",
))


INJURY_PATH = {"NHL":"hockey/nhl", "NBA":"basketball/nba",
               "NFL":"football/nfl"}
INJURY_VETO = {"out", "doubtful", "questionable", "injured reserve",
               "ir", "suspended", "day-to-day", "day to day", "inactive",
               "long-term injured reserve"}


def current_injury_screen(item, fetch, now, cache):
    """Confirm a source *was checked*, not that injury omission proves health."""
    sport = item.get("sport")
    if sport not in INJURY_PATH or fetch is None:
        return False, "LIVE_INJURY_SOURCE_UNAVAILABLE"
    url = ("https://site.api.espn.com/apis/site/v2/sports/" +
           INJURY_PATH[sport] + "/injuries")
    if url not in cache:
        try:
            value = fetch(url, timeout=15)
            if (not isinstance(value, dict) or
                    not isinstance(value.get("injuries"), list) or
                    not value["injuries"]):
                cache[url] = None
            else:
                cache[url] = value
        except (OSError, ValueError, TypeError, KeyError, TimeoutError):
            cache[url] = None
    feed = cache[url]
    if feed is None:
        return False, "LIVE_INJURY_SOURCE_UNAVAILABLE"
    from research_resolver import team_code
    for block in feed["injuries"]:
        if not isinstance(block,dict):
            return False,"MALFORMED_INJURY_SOURCE"
        team = team_code((block.get("team") or {}).get("abbreviation",""),sport)
        if team != item.get("team"):
            continue
        for entry in block.get("injuries") or []:
            if not isinstance(entry,dict):
                return False,"MALFORMED_INJURY_ENTRY"
            player = entry.get("athlete") or {}
            name = player.get("displayName") or player.get("fullName")
            ident = player.get("id")
            if (name != item.get("player") and
                    (not ident or str(ident) != str(item.get("player_id")))):
                continue
            state = entry.get("status")
            if isinstance(state,dict):
                state = state.get("name") or state.get("type")
            if str(state or "").lower().strip() in INJURY_VETO:
                return False,"EXPLICIT_CURRENT_INJURY_DESIGNATION"
            if not str(state or "").strip():
                return False,"UNKNOWN_REPORTED_INJURY_STATUS"
    return True, None


def build(rows, queue, packet, date, *, now=None, decisions=(),
          data_root="data", fetch=None, quotes=None, quote_fetcher=None,
          reviews=None):
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    batch, run = latest_batch(rows, date)
    base = {"schema": VERSION, "date": date, "generated_at": now.isoformat(),
            "source_forecast_run_id": run, "tier": "Conditional Tier 3",
            "verified_picks": [], "strict_verified_board_unmodified": True,
            "unconfirmed_lineup_policy": "five_complete_team_games_no_negative_status",
            "conditional_picks": [], "publication_eligible": False}
    if not run or queue.get("date") != date or packet.get("date") != date:
        return {**base, "status": "invalid_current_slate_context"}
    research = research_board(rows, queue, date, now=now, decisions=decisions,
                              history_root=data_root, packet=packet)
    source = {x.get("inputs", {}).get("id"): x for x in batch
              if isinstance(x.get("inputs"), dict)}
    index = {x["candidate_id"]: x for x in queue.get("queue", [])
             if isinstance(x, dict) and x.get("candidate_id")}
    rejected = Counter()
    candidates = []
    injury_cache = {}
    reviewed = (reviews or {}).get("attestations") or []
    fresh_quotes = quotes
    for entry in research.get("research_ranked") or []:
        if not nfl_volume_market_allowed(entry.get("sport"),entry.get("stat")):
            rejected["nfl_market_excluded_volume_only_policy"] += 1
            continue
        ident = entry["candidate_id"]
        row = source.get(ident)
        item = index.get(ident)
        if not row or not item or forecast_digest(row) != entry["forecast_sha256"]:
            rejected["source_forecast_identity_mismatch"] += 1
            continue
        if row.get("sport") == "NHL" and row.get("stat") in ("saves", "goalie saves"):
            rejected["starting_goalie_requires_confirmation"] += 1
            continue
        quality = assess_tier("Tier 3", entry["q_model"])
        if not quality["eligible"]:
            rejected["below_remarkable_70pct_floor"] += 1
            continue
        tendency = tendency_check(dict(sport=row["sport"],team=row["team"],
                        stat=row["stat"],player=row["player"],
                        player_id=row.get("player_id"),game_date=date),
                        now,root=data_root,packet=packet)
        if (tendency.get("status") != "high_continuity"
                or tendency.get("likely_available") is not True
                or tendency.get("played_last_5") != 5
                or tendency.get("confirmed_active") is not False):
            rejected["five_game_tendency_not_qualifying"] += 1
            continue
        if packet_game_key(packet,item) is None:
            rejected["game_specific_fixture_unverified"] += 1
            continue
        injury_ok, injury_issue = current_injury_screen(item,fetch,now,injury_cache)
        if not injury_ok:
            rejected[injury_issue] += 1
            continue
        raw_status = (((packet.get("availability") or {}).get(row["player"]) or {})
                      .get("status") or {})
        raw_value = raw_status.get("value") if isinstance(raw_status,dict) else None
        if raw_value not in (None,"active"):
            rejected["explicit_nonactive_status"] += 1
            continue
        active, status_issue = status_verified(packet,item,now)
        if active:
            rejected["already_active_requires_strict_verified_board"] += 1
            continue
        if status_issue not in ACCEPTABLE_UNKNOWN:
            rejected["negative_or_conflicting_game_day_status"] += 1
            continue
        # Source-read opposing AND supporting cases, or the deterministic
        # full 15-game official source replay; a tendency is not causal proof.
        matched = [x for x in reviewed if isinstance(x,dict) and
                   x.get("candidate_id") == ident]
        provenance, reviewer_type = None, None
        if len(matched) == 1 and review_verified(matched[0],row,
                forecast_digest(row),now)[0]:
            reviewer_type = "human_attestation"
            provenance = {"reviewer":matched[0]["reviewer"],
                          "source_read_by_human":True}
        elif not matched:
            approved, issue, proof = machine_review(item,row,packet,now=now,
                fetch=fetch,data_root=Path(data_root),
                conditional_tendency=tendency)
            if not approved:
                rejected[issue or "machine_source_review_unavailable"] += 1
                continue
            reviewer_type = "structured_machine_verification"
            provenance = proof
        else:
            rejected["invalid_or_duplicate_human_review"] += 1
            continue
        mechanisms = assess_mechanism(packet,item,now=now,
            review_type=reviewer_type,machine_provenance=provenance,
            human_reviewed=reviewer_type=="human_attestation",
            model_inputs=row.get("inputs") or {},
            human_attestation=matched[0] if reviewer_type=="human_attestation" else None)
        if mechanisms.get("tier_ceiling") not in ("Tier 3","Tier 2","Tier 1"):
            rejected["causal_source_quality_below_tier3"] += 1
            continue
        if fresh_quotes is None and quote_fetcher is not None:
            try:
                fresh_quotes = quote_fetcher(date,sorted({
                    c["sport"] for c in research.get("research_ranked") or []
                    if c["q_model"] >= .70}))
            except (OSError,ValueError,RuntimeError,TimeoutError):
                fresh_quotes = []
                rejected["live_quote_provider_unavailable"] += 1
        refreshed, issues = quote_refresh(row.get("inputs") or {}, fresh_quotes,
                                          now,identity=row)
        if issues or refreshed is None:
            rejected["fresh_same_line_market_missing"] += 1
            continue
        books = refreshed.get("books") or []
        try:
            market = pm.consensus([(b["book"], b["line"], b["target"], b["other"])
                                   for b in books],
                                  retrieved_minutes_ago=(now-utc_time(
                                      refreshed["market_retrieved_at"])).total_seconds()/60)
            if (not market["valid"] or len([r for r in market["rows"]
                                           if not r["reject_hold"]]) < 2):
                rejected["two_independent_valid_book_prices_missing"] += 1
                continue
            p = entry["q_model"]
            push = row["q_push"]
            score = pm.grade(p,market["q_market"],row["soft_flags"],
                             row["current_role_n"],q_push=push,
                             prior_supported=row.get("prior_supported") is True)
        except (pm.PickemError,TypeError,KeyError,ValueError,ZeroDivisionError):
            rejected["refreshed_market_grade_invalid"] += 1
            continue
        gap = score["q_gap"]
        if (score["status"] != "GRADED" or
                score["probability_rank"] not in
                ("NUMERIC_TIER_1","NUMERIC_TIER_2","NUMERIC_TIER_3") or
                gap < .03 or abs(gap) >= pm.GAP_WATCH_CAP-pm.GAP_EPSILON):
            rejected["refreshed_market_graded_watchlist_or_no_edge"] += 1
            continue
        candidates.append({
            "candidate_id":ident, "sport":row["sport"], "player":row["player"],
            "team":row["team"],"opponent":row["opponent"],"stat":row["stat"],
            "side":row["side"],"line":row["reference_line"],
            "tier":"Conditional Tier 3", "modeled_win_probability":p,
            "market_probability_comparable":score["q_market_comparable"],
            "model_market_gap":round(gap,6), "source_forecast_run_id":run,
            "forecast_sha256":forecast_digest(row),
            "source_forecast_at":row.get("forecast_at"),
            "event_start":row.get("event_start"),
            "market_retrieved_at":refreshed["market_retrieved_at"],
            "same_day_injury_source_checked":True,
            "injury_list_absence_does_not_confirm_health":True,
            "historical_lineup_status":"high_continuity_not_confirmed_active",
            "lineup_tendency":tendency, "research_evidence":mechanisms,
            "source_review_type":reviewer_type, "source_review":provenance,
            "verification_status":"conditional_not_official_active",
            "conditional_publishable":True,"verified_pick":False,
            "publication_eligible":False,
            "empirical_hit_rate_certified":False,
            "requires_pregame_recheck":True,
        })
    candidates.sort(key=lambda x:(-x["modeled_win_probability"],
                                  -x["model_market_gap"],x["candidate_id"]))
    return {**base,"status": "conditional_tier3_available" if candidates else
            "no_conditional_tier3_qualified", "conditional_picks":candidates,
            "conditional_count":len(candidates),
            "excluded":dict(sorted(rejected.items())),
            "research_candidates_evaluated":len(research.get("research_ranked") or [])}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date",required=True)
    p.add_argument("--snapshots",default="data/prop_snapshots.jsonl")
    p.add_argument("--queue",required=True)
    p.add_argument("--packet",required=True)
    p.add_argument("--archive-root",default="data/verification")
    p.add_argument("--reviews")
    p.add_argument("--quotes-file")
    p.add_argument("--refresh-quotes",action="store_true")
    p.add_argument("--out",default="reports/conditional_tier3_board.json")
    args=p.parse_args(argv)
    from zoneinfo import ZoneInfo
    now=datetime.now(timezone.utc)
    if now.astimezone(ZoneInfo("America/Toronto")).date().isoformat()!=args.date:
        p.error("conditional approval requires the current Toronto slate date")
    rows=[json.loads(l) for l in Path(args.snapshots).read_text().splitlines() if l.strip()]
    queue=json.loads(Path(args.queue).read_text())
    packet=json.loads(Path(args.packet).read_text())
    directory=Path(args.archive_root)/args.date/"decisions"
    receipts=[json.loads(f.read_text()) for f in sorted(directory.glob("*.json"))]
    reviews=json.loads(Path(args.reviews).read_text()) if args.reviews else None
    quotes=[json.loads(l) for l in Path(args.quotes_file).read_text().splitlines()
            if l.strip()] if args.quotes_file else None
    cache={}
    def fetch(url,**kw):
        if url not in cache:
            from fetch_slate import fetch_json
            cache[url]=fetch_json(url,**kw)
        return cache[url]
    # Resolve current injuries and game event statuses before conditional checks.
    from research_resolver import resolve
    selected=[x["candidate_id"] for x in queue.get("queue") or []]
    packet,_=resolve(packet,selected,fetch,now=now)
    def quote_fetcher(date,sports):
        from odds_providers import PropLineProvider
        return PropLineProvider().fetch(date,sports)
    report=build(rows,queue,packet,args.date,now=now,decisions=receipts,
                 data_root=Path(args.snapshots).parent,fetch=fetch,
                 quotes=quotes,quote_fetcher=quote_fetcher if args.refresh_quotes else None,
                 reviews=reviews)
    write_atomic(args.out,report)
    import os
    run_id = os.environ.get("GITHUB_RUN_ID") or now.strftime("%Y%m%dT%H%M%S%fZ")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT","1")
    archive = (Path(args.archive_root)/args.date/"conditional" /
               (run_id+"-"+attempt+".json"))
    if archive.exists():
        raise ValueError("immutable conditional evaluation receipt already exists")
    write_atomic(archive,report)
    print(json.dumps({k:v for k,v in report.items() if k!="conditional_picks"},
                     indent=2))
    return 0 if report["status"]!="invalid_current_slate_context" else 2

if __name__=="__main__":
    raise SystemExit(main())
