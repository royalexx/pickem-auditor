"""Deterministic, live-rechecked source adjudication. NEVER a human attestation.

Only an independently corroborated official game log, source-proven workload
event, explicitly active game roster, and both historical sides qualify.
This supplements--not loosens--the existing numeric Tier/market vetoes.
"""
from __future__ import annotations
from datetime import date, datetime, timezone

from autonomous_investigator import (
    observation_source, verified_source, _series, _validated_series,
    audited_workload_mechanism, crosscheck_collector, source_hash,
    extend_verified_history,
)
from pick_verification import forecast_digest, status_verified, _report_timestamp
from research_triage import packet_game_key


REVIEWER = "machine:deterministic-primary-source-v1"


def evaluate(item, original, packet, *, now, fetch=None, data_root=None):
    """Return (eligible, machine-readable blocker, provenance). No assertions from URLs alone."""
    provenance = {"review_type": "structured_machine_verification",
                  "reviewer": REVIEWER, "source_read_by_human": False,
                  "independent_live_refetch": False,
                  "reviewed_at": now.isoformat(), "source": None}
    def fail(reason):
        return False, reason, provenance
    record = (((packet.get("_autonomous_investigation") or {})
               .get("candidate_summaries") or {}).get(item["candidate_id"]))
    if not isinstance(record, dict):
        return fail("MACHINE_DOSSIER_MISSING")
    if record.get("forecast_sha256") != forecast_digest(original):
        return fail("MACHINE_FORECAST_DIGEST_MISMATCH")
    if (str(record.get("player_id")) != str(item.get("player_id"))
            or record.get("team") != item.get("team")
            or record.get("opponent") != item.get("opponent")
            or record.get("side") != item.get("side")
            or record.get("line") != item.get("line")):
        return fail("MACHINE_SUBJECT_IDENTITY_MISMATCH")
    if packet_game_key(packet, item) is None:
        return fail("MACHINE_FIXTURE_NOT_CONFIRMED")
    active, issue = status_verified(packet, item, now)
    if not active:
        return fail("MACHINE_"+str(issue))
    if item["sport"] not in ("NHL", "NBA"):
        return fail("MACHINE_SPORT_SOURCE_NOT_SUPPORTED")
    # Any unresolved conflicting status evidence blocks the review.
    if record.get("news_mention_count") != 0:
        return fail("MACHINE_PLAYER_NEWS_REQUIRES_SOURCE_REVIEW")
    if (record.get("collector_status") != "independently_correlated"
            or not isinstance(record.get("collector_overlap"), int)
            or record["collector_overlap"] < 3):
        return fail("MACHINE_INDEPENDENT_COLLECTOR_CORROBORATION_MISSING")
    if not _report_timestamp(record.get("source_retrieved_at"), now):
        return fail("MACHINE_SOURCE_EVIDENCE_STALE")
    url = observation_source(item, original.get("game_date"))
    if (not url or url != record.get("source") or not verified_source(url)
            or fetch is None):
        return fail("MACHINE_LIVE_OFFICIAL_SOURCE_REQUIRED")
    try:
        payload = fetch(url, timeout=15)
        if not isinstance(payload, (dict, list)):
            return fail("MACHINE_OFFICIAL_SOURCE_NOT_JSON")
        sha = source_hash(payload)
        if record.get("source_payload_sha256") != sha:
            return fail("MACHINE_OFFICIAL_SOURCE_HASH_CHANGED")
        series = _series(item, payload)
        observations, issue = _validated_series(item, series, original["game_date"])
        if issue:
            return fail("MACHINE_"+issue)
        extra=record.get("prior_season_extension")
        if extra is not None and (not isinstance(extra,dict) or len(observations)>=15):
            return fail("MACHINE_PRIOR_SEASON_PROVENANCE_INVALID")
        if observations is not None and len(observations)<15 and extra is not None:
            observations,replayed,extra_issue=extend_verified_history(
                item,original["game_date"],observations,fetch,expected=extra)
            if extra_issue or replayed!=extra:
                return fail("MACHINE_"+str(extra_issue or "PRIOR_SEASON_REPLAY_FAILED"))
        if not observations or len(observations) < 15:
            return fail("MACHINE_HISTORY_FEWER_THAN_15_GAMES")
        # A recent *trend* cannot be inferred from observations whose newest
        # game was weeks before the fixture. Treat long injury/roster gaps as
        # unresolved even if old samples are numerous.
        last_day = date.fromisoformat(observations[0]["game_date"])
        slate_day = date.fromisoformat(original["game_date"])
        if not 0 < (slate_day-last_day).days <= 14:
            return fail("MACHINE_RECENT_WORKLOAD_EVIDENCE_STALE")
        if record.get("sampled_games") != observations[:20]:
            return fail("MACHINE_HISTORICAL_GAME_EVIDENCE_CHANGED")
        if record.get("sampled_count") != min(len(observations),20):
            return fail("MACHINE_HISTORICAL_SAMPLE_COUNT_MISMATCH")
        wins = sum((r["stat_value"] > item["line"] if item["side"] == "over"
                    else r["stat_value"] < item["line"]) for r in observations[:20])
        losses = sum((r["stat_value"] < item["line"] if item["side"] == "over"
                      else r["stat_value"] > item["line"]) for r in observations[:20])
        if (wins < 1 or losses < 1
                or record.get("supporting_game_count") != wins
                or record.get("opposing_game_count") != losses):
            return fail("MACHINE_ADVERSARIAL_HISTORICAL_EVIDENCE_INCOMPLETE")
        independent = crosscheck_collector(item, original, observations, now, data_root)
        if (independent["status"] != "independently_correlated"
                or independent["overlap"] < 3):
            return fail("MACHINE_LIVE_COLLECTOR_MISMATCH")
        mechanism = audited_workload_mechanism(
            item, observations, url, datetime.fromisoformat(
                record["source_retrieved_at"].replace("Z","+00:00")),
            prior=extra)
        if mechanism is None:
            return fail("MACHINE_SOURCE_BACKED_CAUSAL_WORKLOAD_UNPROVEN")
        existing = (packet.get("mechanisms") or {}).get(item["candidate_id"]) or []
        if not any(source_hash(x) == source_hash(mechanism) for x in existing
                   if isinstance(x, dict)):
            return fail("MACHINE_CAUSAL_MECHANISM_NOT_REPRODUCIBLE")
        if extra is not None:
            provenance["prior_season_extension"]=extra
        provenance.update(source=url, source_payload_sha256=sha,
                          supporting_game_count=wins, opposing_game_count=losses,
                          shared_collector_games=independent["overlap"],
                          validated_mechanism=mechanism["event_id"],
                          independent_live_refetch=True)
        return True, None, provenance
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        provenance["failure_type"] = type(exc).__name__
        return fail("MACHINE_SOURCE_FETCH_OR_VALIDATION_FAILED")
