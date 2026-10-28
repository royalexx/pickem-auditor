#!/usr/bin/env python3
"""Autonomous, bounded structured-source investigation of priority forecasts.

An observed JSON field is machine-verified only when matched to a current
player/game/source. No fabricated quotes, narrative scouting or attestations.
The verifier's existing research and ranking vetoes remain authoritative.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import fetch_slate as fs
from pick_verification import select, forecast_digest, status_verified, write_atomic
from research_triage import packet_game_key, utc_time
from research_resolver import resolve
from scouting_checklist import required_checks

VERSION = "autonomous-investigation-v1"
MAX_SUBJECTS = 30
MAX_OBSERVATIONS = 20
SPORTS = {"NHL", "NBA", "NFL"}
ALLOWED_SOURCE_HOSTS = frozenset(("api-web.nhle.com", "site.api.espn.com", "site.web.api.espn.com"))
NEWS_FEEDS = {
    "NHL": "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/news?limit=100",
    "NBA": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/news?limit=100",
    "NFL": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=100",
}
DATEZONE = ZoneInfo("America/Toronto")


def source_hash(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        if "T" in value or value.endswith("Z"):
            d = utc_time(value)
            return d.astimezone(DATEZONE).date() if d else None
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def observation_source(item, date):
    """Return one canonical official feed URL, never one inferred from a report."""
    player_id = str(item.get("player_id") or "")
    if not player_id.isdecimal() or len(player_id) > 14:
        return None
    if item["sport"] == "NHL":
        return fs.nhl_game_log_url(player_id, fs.season_id_from_date(date))
    if item["sport"] == "NBA":
        return fs.espn_gamelog_url(player_id, fs.nba_espn_season_year(date))
    return None  # NFL official play-by-play evidence needs separate signed join.


def verified_source(url):
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.hostname in ALLOWED_SOURCE_HOSTS
            and not parsed.username and not parsed.password)


def _series(item, payload):
    """Use only the repository's tested league-specific stat parsers."""
    sport, stat = item["sport"], item["stat"]
    if sport == "NHL":
        games = fs.parse_nhl_game_log(payload)
        return fs.nhl_series(games, stat) if games is not None else None
    if sport == "NBA":
        games = fs.parse_espn_gamelog(payload)
        return fs.nba_series(games, stat) if games is not None else None
    return None


def previous_season_source(item, date):
    """Canonical previous official player game log (never an active roster)."""
    current=observation_source(item,date)
    if current is None:return None
    if item["sport"]=="NHL":
        season=fs.season_id_from_date(date)
        if len(season)!=8 or not season.isdecimal():return None
        return fs.nhl_game_log_url(str(item["player_id"]),
            str(int(season[:4])-1)+str(int(season[4:])-1))
    if item["sport"]=="NBA":
        return fs.espn_gamelog_url(str(item["player_id"]),
            fs.nba_espn_season_year(date)-1)
    return None


def extend_verified_history(item,date,observations,fetch,*,expected=None):
    """Append individually validated prior-season games to a short current sample.

    Replayed validation checks SHA256, source ID, game IDs and chronology.
    Old games never prove tonight's lineup or specific role.
    """
    if observations is None or len(observations)>=15:return observations,None,None
    url=previous_season_source(item,date)
    if url is None or not verified_source(url):
        return observations,None,"PRIOR_SEASON_OFFICIAL_SOURCE_UNAVAILABLE"
    try:
        payload=fetch(url,timeout=15)
        if not isinstance(payload,(dict,list)):raise ValueError("invalid_previous_season_json")
        sha=source_hash(payload)
        if expected is not None and (expected.get("source_url")!=url or
                                    expected.get("payload_sha256")!=sha):
            return observations,None,"PRIOR_SEASON_SOURCE_DIGEST_CHANGED"
        old, issue=_validated_series(item,_series(item,payload),date)
        if issue or old is None:return observations,None,"PRIOR_SEASON_SOURCE_INVALID_"+str(issue)
        current_ids={x["game_id"] for x in observations}
        if any(x["game_id"] in current_ids for x in old):
            return observations,None,"CROSS_SEASON_GAME_ID_COLLISION"
        if observations and any(x["game_date"]>=observations[0]["game_date"] for x in old):
            return observations,None,"PRIOR_SEASON_CHRONOLOGY_INVALID"
        proof={"source_url":url,"payload_sha256":sha,"additional_games":len(old)}
        if expected is not None and expected.get("additional_games")!=len(old):
            return observations,None,"PRIOR_SEASON_SAMPLE_MISMATCH"
        return sorted(observations+old,key=lambda x:(x["game_date"],x["game_id"]),
                      reverse=True),proof,None
    except (OSError,ValueError,TypeError,KeyError,TimeoutError) as exc:
        return observations,None,"PRIOR_SEASON_SOURCE_ERROR_"+type(exc).__name__


def _validated_series(item, series, date):
    if series is None:
        return None, "STAT_NOT_AVAILABLE_IN_OFFICIAL_FEED"
    if not isinstance(series, list):
        return None, "INVALID_OFFICIAL_OBSERVATIONS"
    seen, valid = set(), []
    cutoff = datetime.strptime(date, "%Y-%m-%d").date()
    for row in series:
        if not isinstance(row, dict):
            return None, "INVALID_OFFICIAL_OBSERVATIONS"
        ident = str(row.get("tie") or "")
        day = _date(str(row.get("when") or ""))
        value = row.get("value")
        if (not ident or ident in seen or not day or day >= cutoff
                or not _finite(value) or value < 0):
            return None, "INVALID_OR_POST_EVENT_OBSERVATION"
        seen.add(ident)
        valid.append({"game_id": ident, "game_date": day.isoformat(),
                      "stat_value": float(value),
                      "workload_minutes": row.get("workload") if _finite(row.get("workload")) else None})
    valid.sort(key=lambda x: (x["game_date"], x["game_id"]), reverse=True)
    return valid, None


def crosscheck_collector(item, original, observed, now, data_root):
    """Compare independent API response with daily, content-hashed collector data."""
    if not isinstance(original.get("inputs"), dict):
        return {"status": "missing_original_input", "overlap": 0}
    scouting = (original["inputs"].get("scouting") or {})
    if not scouting.get("historical_usage"):
        return {"status": "collector_history_reference_unavailable", "overlap": 0}
    candidate = {"sport": item["sport"], "player_id": item["player_id"],
                 "stat": item["stat"], "team": item["team"],
                 "game_date": original["game_date"], "scouting": scouting}
    try:
        from usage_baseline import load, validate_rows, using_directory
        with using_directory(data_root):
            cache = load(candidate, now)
        validate_rows(cache["observations"], candidate, now)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        return {"status": "collector_history_unavailable_or_invalid",
                "issue": type(exc).__name__, "overlap": 0}
    expected = {str(row["id"]): float(row["value"]) for row in cache["observations"]}
    found = {row["game_id"]: row["stat_value"] for row in observed}
    overlap = set(expected) & set(found)
    mismatches = sorted(key for key in overlap if not math.isclose(
        expected[key], found[key], rel_tol=0, abs_tol=1e-8))
    return {
        "status": ("source_conflict" if mismatches else
                   "independently_correlated" if len(overlap) >= 3 else
                   "insufficient_shared_observations"),
        "overlap": len(overlap), "mismatch_game_ids": mismatches[:10],
        "collector_source": cache.get("source_url"),
        "collector_content_sha256": cache.get("content_sha256"),
    }


def independently_verified_deployment(item, observations, url, sha, now):
    """One precisely measurable scouting fact; never a projected role or lineup.

    Mark a deployment *trend* only when >=8 official games include workload,
    including five recent games. This cannot establish tonight's line, minutes
    or opponent matchup and therefore never completes the scouting checklist.
    """
    if item["sport"] not in ("NBA","NHL"):
        return None
    valid = [r for r in observations if _finite(r.get("workload_minutes"))
             and r["workload_minutes"] > 0]
    if len(valid) < 8:
        return None
    recent = valid[:5]
    full_avg = sum(x["workload_minutes"] for x in valid)/len(valid)
    five_avg = sum(x["workload_minutes"] for x in recent)/5
    value = {"metric":"observed_minutes_per_game",
             "last_five_mean_minutes":round(five_avg,4),
             "current_season_mean_minutes":round(full_avg,4),
             "current_season_sample":len(valid),
             "last_five_game_ids":[r["game_id"] for r in recent],
             "projection_for_tonight":None,
             "lineup_or_matchup_confirmed":False}
    return {"fact":"Official observed workload / deployment trend (not a forecast)",
            "value":value,"confidence":"confirmed","source_url":url,
            "retrieved_at":now.isoformat(),
            "source_field":("gameLog[].toi" if item["sport"]=="NHL"
                            else "seasonTypes[].categories[].events[].stats.minutes"),
            "source_payload_sha256":sha,
            "source_kind":"machine_read_structured_statistical_observation",
            "quote":""}


def audited_workload_mechanism(item, observations, url, now, *, prior=None):
    """A conservative, directly observed workload change, not a projected injury."""
    if item["sport"] not in ("NHL", "NBA") or len(observations) < 15:
        return None
    minutes = [r["workload_minutes"] for r in observations[:15]]
    if any(not _finite(v) or v <= 0 for v in minutes):
        return None
    recent, previous_mean = sum(minutes[:5]) / 5, sum(minutes[5:15]) / 10
    if previous_mean <= 0:
        return None
    ratio = recent / previous_mean
    side = item["side"]
    if ((ratio < 1.15 if side == "over" else ratio > .85)
            or not (ratio <= .85 or ratio >= 1.15)):
        return None
    return {"type": "workload", "supports_side": side,
            "event_id": "observed-15-game-workload-shift",
            "description": ("Observed recent-five mean workload " +
                            ("higher" if ratio > 1 else "lower") +
                            " than preceding ten official games; "
                            "historical opportunity only, no future role inferred"),
            "sources": [{"fact": "Observed minutes last 5 versus previous 10",
                         "value": {"recent_minutes": round(recent, 4),
                                   "prior_minutes": round(prior, 4),
                                   "ratio": round(ratio, 6),
                                   "game_ids": [x["game_id"] for x in observations[:15]]},
                         "confidence": "confirmed",
                         "source_url": url, "retrieved_at": now.isoformat(),
                         "source_kind": "verified_machine_observation"}]
            + ([{"fact":"Audited previous-season source in observed workload window",
                 "value":prior["additional_games"],"confidence":"confirmed",
                 "source_url":prior["source_url"],"retrieved_at":now.isoformat(),
                 "source_kind":"verified_machine_observation",
                 "source_payload_sha256":prior["payload_sha256"]}]
               if prior is not None else [])}


def _historical_findings(item, observations, url, digest, now):
    """Explicit event-level support and opposition, not forecast probabilities."""
    recent = observations[:MAX_OBSERVATIONS]
    line, side = item["line"], item["side"]
    if not _finite(line) or side not in ("over", "under"):
        return None, "INVALID_SIDE_OR_LINE"
    supporting, opposing, pushes = [], [], []
    for row in recent:
        value = row["stat_value"]
        win = value > line if side == "over" else value < line
        if value == line:
            pushes.append(row)
        elif win:
            supporting.append(row)
        else:
            opposing.append(row)
    evidence = {"source_url": url, "retrieved_at": now.isoformat(),
                "payload_sha256": digest, "observation_field": (
                    "gameLog[].shots/blockedShots/saves" if item["sport"] == "NHL"
                    else "seasonTypes[].categories[].events[].stats"),
                "source_kind": "direct_structured_league_game_log",
                "observation_count": len(observations), "sampled_count": len(recent),
                "side": side, "line": line, "support_count": len(supporting),
                "opposing_count": len(opposing), "push_count": len(pushes),
                "last_five_mean": (round(sum(x["stat_value"] for x in recent[:5]) /
                                          len(recent[:5]), 4) if recent else None),
                "observations": recent,
                "supporting_games": supporting[:5],
                "opposing_games": opposing[:5],
                "inference_policy": "historical event comparison only; neither side "
                                    "is a pregame probability or a scouting attestation"}
    return evidence, None


def article_mentions(payload, item, now):
    """Find literal athlete-name mentions. Do not interpret them as verified news."""
    if not isinstance(payload, dict):
        return []
    articles = payload.get("articles") or []
    if not isinstance(articles, list):
        return []
    name = str(item.get("player") or "").strip()
    if len(name.split()) < 2:
        return []
    pattern = re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.I)
    results = []
    for article in articles[:100]:
        if not isinstance(article, dict):
            continue
        published = utc_time(article.get("published") or article.get("publishedAt"))
        if not published or not 0 <= (now-published).total_seconds() <= 48*3600:
            continue
        link = ((article.get("links") or {}).get("web") or {}).get("href")
        host = urlparse(str(link or "")).hostname
        if urlparse(str(link or "")).scheme != "https" or host not in ("www.espn.com","espn.com"):
            continue
        combined = " ".join(str(article.get(k) or "") for k in ("headline","description"))
        hit = pattern.search(combined)
        if not hit:
            continue
        begin = max(0,hit.start()-55)
        excerpt = combined[begin:hit.end()+140].strip()
        excerpt = " ".join(excerpt.split()[:25])
        results.append({"url": link, "published_at": published.isoformat(),
                        "headline": str(article.get("headline") or ""),
                        "source_excerpt": excerpt,
                        "source_field": "articles[].headline/description",
                        "verification_status": "NAME_MENTION_ONLY_NOT_SCOUTING_OR_INJURY_PROOF"})
        if len(results) >= 5:
            break
    return results


def investigate(rows, queue, packet, date, *, now=None, limit=10, phase="initial",
                fetch=None, data_root=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("aware evaluation clock required")
    now = now.astimezone(timezone.utc)
    if (now.astimezone(DATEZONE).date().isoformat() != date or
            packet.get("date") != date or queue.get("date") != date):
        raise ValueError("same-day queue, packet and evaluation required")
    if not 1 <= limit <= MAX_SUBJECTS:
        raise ValueError("subject limit must be 1..30")
    if fetch is None:
        fetch = fs.fetch_json
    selected, exclusions, run_id, batch_count = select(
        rows, queue, date, now, phase, limit)
    updated = deepcopy(packet)
    resolution = {"attempts": [], "resolved_statuses": [],
                  "verified_pregame_games": [], "started_games": []}
    # Shared scoreboard/summary/injury fetches occur ONCE, not per market.
    if selected:
        updated, resolution = resolve(
            updated, [item["candidate_id"] for item, _ in selected], fetch, now=now)
    # An independent, bounded search for reports mentioning the athlete.
    # Returned article summaries are leads; no active-status or role claim is
    # inferred from a headline or snippet. One request per relevant sport.
    news = {}
    for sport in sorted({item["sport"] for item,_ in selected}):
        url = NEWS_FEEDS.get(sport)
        if not url:
            continue
        attempt = {"url": url, "retrieved_at": now.isoformat(),
                   "purpose": "literal search for potentially conflicting team news"}
        try:
            response = fetch(url, timeout=15)
            if not isinstance(response, dict):
                raise ValueError("expected ESPN news object")
            news[sport] = response
            attempt.update(status="retrieved", payload_sha256=source_hash(response))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            news[sport] = {}
            attempt.update(status="source_failed", failure_type=type(exc).__name__)
        resolution.setdefault("attempts", []).append(attempt)
    entries, counts, cache = [], Counter(), {}
    secondary_cache={}
    def fetch_prior_once(url, **kwargs):
        if url not in secondary_cache:
            secondary_cache[url]=fetch(url,**kwargs)
        return secondary_cache[url]
    for item, original in selected:
        entry = {"candidate_id": item["candidate_id"],
                 "forecast_sha256": forecast_digest(original),
                 "sport": item["sport"], "player": item["player"],
                 "player_id": item["player_id"], "team": item["team"],
                 "opponent": item["opponent"], "stat": item["stat"],
                 "side": item["side"], "line": item["line"],
                 "event_start": original.get("event_start"),
                 "checked_at": now.isoformat(), "source_attempts": [],
                 "observed_history": None, "supporting_evidence": [],
                 "opposing_evidence": [], "relevant_news_mentions": [],
                 "blockers": [],
                 "missing_scouting_checks": list(required_checks(item["sport"], item["stat"])),
                 "source_read_by_human": False, "research_attested": False,
                 "publication_eligible": False}
        reasons = entry["blockers"]
        entry["relevant_news_mentions"] = article_mentions(
            news.get(item["sport"], {}), item, now)
        if entry["relevant_news_mentions"]:
            reasons.append("NEWS_MENTIONS_REQUIRE_SOURCE_READING_AND_CONTEXT")
        if packet_game_key(updated, item) is None:
            reasons.append("CANONICAL_FIXTURE_IDENTITY_NOT_CONFIRMED")
        ok, issue = status_verified(updated, item, now)
        if not ok:
            reasons.append(issue)
        url = observation_source(item, date)
        if url is None or not verified_source(url):
            reasons.append("NO_SUPPORTED_PRIMARY_GAMELOG_URL")
        else:
            # One source per unique player, even when multiple stat/side candidates.
            if url not in cache:
                attempt = {"url": url, "retrieved_at": now.isoformat(),
                           "purpose": "independently check actual historical games",
                           "identity": {"sport": item["sport"],
                                        "player_id": str(item["player_id"])}}
                try:
                    response = fetch(url, timeout=15)
                    if not isinstance(response, (dict, list)):
                        raise ValueError("non-JSON official game log")
                    cache[url] = (response, None, source_hash(response))
                    attempt.update(status="retrieved",
                                   payload_sha256=cache[url][2])
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    cache[url] = (None, type(exc).__name__, None)
                    attempt.update(status="source_failed",
                                   failure_type=type(exc).__name__)
                entry["source_attempts"].append(attempt)
            payload, error, sha = cache[url]
            if error:
                reasons.append("OFFICIAL_GAMELOG_UNAVAILABLE_" + error.upper())
            else:
                series = _series(item, payload)
                observations, issue = _validated_series(item, series, date)
                if issue:
                    reasons.append(issue)
                else:
                    # A previous-year observation must NOT be mislabeled as
                    # part of the current-season deployment average.
                    current_season_observations=observations
                    extra_proof = None
                    if len(observations)<15:
                        observations,extra_proof,extra_issue=extend_verified_history(
                            item,date,observations,fetch_prior_once)
                        if extra_issue:
                            reasons.append(extra_issue)
                        elif extra_proof:
                            entry["prior_season_extension"]=extra_proof
                            counts["historical_samples_extended"] += 1
                    history, issue = _historical_findings(item, observations, url, sha, now)
                    if issue:
                        reasons.append(issue)
                    else:
                        entry["observed_history"] = history
                        entry["supporting_evidence"] = history["supporting_games"]
                        entry["opposing_evidence"] = history["opposing_games"]
                        checked = crosscheck_collector(
                            item, original, observations, now, data_root or Path("data"))
                        entry["collector_independent_check"] = checked
                        if checked["status"] != "source_conflict":
                            deploy = independently_verified_deployment(
                                item, current_season_observations, url, sha, now)
                            slot = ((updated.get("scouting") or {})
                                    .get(item["candidate_id"]) or {}).get("supporting_stats")
                            if (deploy is not None and isinstance(slot, dict)
                                    and slot.get("deployment_trends") is None):
                                slot["deployment_trends"] = deploy
                                entry["validated_stat_specific_facts"] = [
                                    "deployment_trends"]
                                entry["missing_scouting_checks"] = [
                                    x for x in entry["missing_scouting_checks"]
                                    if x != "deployment_trends"]
                                counts["deployment_facts_filled"] += 1
                        if checked["status"] == "source_conflict":
                            reasons.append("COLLECTOR_VS_OFFICIAL_OBSERVATION_CONFLICT")
                        if checked["status"] == "independently_correlated":
                            mechanism = audited_workload_mechanism(
                                item, observations, url, now,
                                prior=extra_proof)
                            if mechanism:
                                slot = updated.setdefault("mechanisms", {}).setdefault(
                                    item["candidate_id"], [])
                                if not any(x.get("event_id") == mechanism["event_id"]
                                           for x in slot if isinstance(x, dict)):
                                    slot.append(mechanism)
                                    entry["sourced_opportunity_mechanism"] = (
                                        mechanism["event_id"])
                                    counts["workload_mechanisms_added"] += 1
                        if not observations:
                            reasons.append("NO_PRE_EVENT_GAME_OBSERVATIONS")
                        counts["primary_history_retrieved"] += 1
                        if checked["status"] == "independently_correlated":
                            counts["collector_history_correlated"] += 1
        # Structured observations never silently fulfill line matching, goalie
        # quality, pace, opponent schemes or the reviewer-read checklist.
        reasons.append("UNVERIFIED_CONTEXTUAL_MATCHUP_AND_ADVERSARIAL_REVIEW")
        entry["status"] = "partial_source_research" if entry["observed_history"] else "source_research_blocked"
        counts[entry["status"]] += 1
        entries.append(entry)
    attempts = list(resolution.get("attempts") or [])
    attempts += [a for e in entries for a in e["source_attempts"]]
    report = {
        "schema": VERSION, "date": date, "phase": phase,
        "generated_at": now.isoformat(), "source_forecast_run_id": run_id,
        "original_forecast_count": batch_count, "selected_candidates": len(entries),
        "not_selected": dict(exclusions), "source_calls_attempted": len(attempts),
        "official_event_checks": len(resolution.get("verified_pregame_games") or []),
        "confirmed_active_subjects": sum(1 for item,_ in selected
                                         if status_verified(updated, item, now)[0]),
        "counts": dict(counts), "attempts": attempts, "candidates": entries,
        "research_complete": False, "publication_eligible": False,
        "verification_gate": "requires independent contextual/qualitative "
                             "scouting plus adversarial review; machine observations "
                             "are NOT reviewer attestations",
        "prop_line_requests": 0,
    }
    # This section is outside the scoring packet schema: never mark
    # scouting facts confirmed merely because a source URL was reachable.
    updated["_autonomous_investigation"] = {
        "schema": VERSION, "generated_at": now.isoformat(),
        "candidate_summaries": {e["candidate_id"]: {
            "forecast_sha256": e["forecast_sha256"],
            "source": (e["observed_history"] or {}).get("source_url"),
            "source_payload_sha256": (e["observed_history"] or {}).get("payload_sha256"),
            "source_retrieved_at": (e["observed_history"] or {}).get("retrieved_at"),
            "sampled_games": (e["observed_history"] or {}).get("observations"),
            "sampled_count": (e["observed_history"] or {}).get("sampled_count"),
            "prior_season_extension": e.get("prior_season_extension"),
            "side": e["side"], "line": e["line"], "player_id": e["player_id"],
            "team": e["team"], "opponent": e["opponent"],
            "collector_status": (e.get("collector_independent_check") or {}).get("status"),
            "collector_overlap": (e.get("collector_independent_check") or {}).get("overlap", 0),
            "sourced_opportunity_mechanism": e.get("sourced_opportunity_mechanism"),
            "supporting_game_count": (e["observed_history"] or {}).get("support_count", 0),
            "opposing_game_count": (e["observed_history"] or {}).get("opposing_count", 0),
            "news_mention_count": len(e["relevant_news_mentions"]),
            "blockers": e["blockers"]}
            for e in entries},
        "research_complete": False, "promotion_authorized": False}
    return report, updated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--snapshots", default="data/prop_snapshots.jsonl")
    parser.add_argument("--queue", default="reports/research_triage.json")
    parser.add_argument("--packet", help="Input research packet, never a guessed file")
    parser.add_argument("--out", default="reports/autonomous_investigation.json")
    parser.add_argument("--phase", choices=("initial", "recheck"), default="initial")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--data-root", default="data")
    parser.add_argument("--now", help="Test-only timestamp")
    args = parser.parse_args(argv)
    now = utc_time(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        parser.error("invalid aware timestamp")
    packet_path = Path(args.packet or f"data/research_{args.date}.json")
    rows = [json.loads(line) for line in Path(args.snapshots).read_text().splitlines() if line.strip()]
    queue = json.loads(Path(args.queue).read_text())
    packet = json.loads(packet_path.read_text())
    report, updated = investigate(rows, queue, packet, args.date, now=now,
                                  limit=args.limit, phase=args.phase,
                                  data_root=Path(args.data_root))
    write_atomic(args.out, report)
    # Snapshot is untouched. Current research packet gains only machine
    # observations and independently rechecked official status facts.
    write_atomic(packet_path, updated)
    print(json.dumps({"date": args.date, "status": "investigated",
                      "selected": report["selected_candidates"],
                      "counts": report["counts"], "source_attempts": report["source_calls_attempted"],
                      "research_complete": False, "publication_eligible": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
