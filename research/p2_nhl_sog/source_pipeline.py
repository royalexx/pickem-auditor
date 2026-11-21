"""NHL SOG original-source acquisition for P2 (no models/forecasts/settlement).

Requires P0 storage attestation and authentic C03 receipts for official NHL
sources. Collector HMAC proves possession, NOT NHL publication time.
Schema: PA-P2-NHL-SOG-SOURCE-BUNDLE/1; P0 records: PA-P0/1.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen
import hashlib
import json
import os
import re
import tempfile
import time

from v2.p0_integrity.contracts import VERSION as P0_VERSION, AdmissionError, utc, canonical_bytes, sha256, validate_record
from v2.p0_integrity.storage import attest_project_storage, append_immutable, verify_immutable_record
from scripts.c03_live_transport import capture_signed_live, verify_signed_capture

UTC = timezone.utc
ROOT_NAMESPACE = "research/p2_nhl_sog_original"
SCHEMA = "PA-P2-NHL-SOG-SOURCE-BUNDLE/1"
OFFICIAL = "https://api-web.nhle.com/v1"
SOURCE_FREEZE_MINUTES = 20
FUTURE_STATES = {"FUT", "PRE"}
HEX = re.compile(r"^[0-9a-f]{64}$")
PLAYER_ID = re.compile(r"^[0-9]{4,12}$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class SourceBlocked(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = str(code)


def require(condition, code):
    if not condition:
        raise SourceBlocked(code)


def clock(value):
    try:
        return utc(value)
    except (ValueError, TypeError, AdmissionError) as exc:
        raise SourceBlocked("INVALID_UTC_SOURCE_CLOCK") from exc


def stamp(t):
    require(isinstance(t, datetime) and t.tzinfo is not None, "AWARE_CLOCK_REQUIRED")
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_relative(root, rel):
    require(isinstance(rel, str) and rel and not rel.startswith("/") and
            "\\\\" not in rel and ".." not in Path(rel).parts and
            not Path(rel).is_absolute(), "UNSAFE_SOURCE_PATH")
    root = Path(root).resolve()
    path = (root / rel).resolve()
    require(path.is_relative_to(root), "SOURCE_PATH_ESCAPE")
    return path


def _completed_target(target, wanted):
    marker = target.with_name(target.name + ".complete")
    if not marker.is_file() or marker.is_symlink():
        return False
    marker_bytes = marker.read_bytes()
    if len(marker_bytes) < 64:
        # Another writer reserved the marker but has not flushed its body.
        return False
    require(marker_bytes == wanted.encode("ascii") and
            target.is_file() and not target.is_symlink() and
            digest(target.read_bytes()) == wanted,
            "IMMUTABLE_SOURCE_COLLISION")
    return True


def put_once(root, relative, raw):
    """Deepnote-compatible no-clobber O_EXCL plus verified completion marker.

    O_EXCL publishes a reserved target. Other readers must wait for its
    independently durable .complete marker. A crash leaves untrusted partial
    evidence that no runner may certify or overwrite.
    """
    require(isinstance(raw, bytes), "RAW_SOURCE_BYTES_REQUIRED")
    target = safe_relative(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    wanted = digest(raw)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o640)
    except FileExistsError:
        for _ in range(80):
            if _completed_target(target, wanted):
                return {"relative_path": relative, "sha256": wanted, "bytes": len(raw)}
            time.sleep(0.025)
        raise SourceBlocked("IMMUTABLE_PARTIAL_OR_INTERRUPTED_SOURCE")
    else:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        require(digest(target.read_bytes()) == wanted,
                "SOURCE_WRITE_READBACK_SHA_MISMATCH")
        marker = target.with_name(target.name + ".complete")
        try:
            fd = os.open(marker, flags, 0o640)
        except FileExistsError as exc:
            raise SourceBlocked("IMMUTABLE_COMPLETION_COLLISION") from exc
        with os.fdopen(fd, "wb") as f:
            f.write(wanted.encode("ascii"))
            f.flush()
            os.fsync(f.fileno())
        if hasattr(os, "O_DIRECTORY"):
            try:
                parent_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            except OSError:
                # Some attested project mounts reject directory fsync.
                # Content+marker readback is still mandatory.
                pass
    require(_completed_target(target, wanted), "SOURCE_COMPLETION_NOT_DURABLE")
    return {"relative_path": relative, "sha256": wanted, "bytes": len(raw)}


def attempt(root, stage, status, reasons, **metadata):
    """Persist all source abstentions and misses; never a model ledger."""
    now = stamp(datetime.now(UTC))
    record = {"schema": "PA-P2-NHL-ATTEMPT/1", "attempted_at": now,
              "stage": stage, "status": status, "reasons": sorted(set(reasons)),
              "metadata": metadata, "research_only": True}
    raw = canonical_bytes(record)
    path = ROOT_NAMESPACE + "/attempts/" + digest(raw) + ".json"
    saved = put_once(root, path, raw)
    return dict(record, receipt=saved)


def current_storage(root="/work"):
    return attest_project_storage(root)


def capture_official(root, url, *, event_start_at, input_freeze_at, source_kind,
                     source_id, capture=capture_signed_live,
                     verify=verify_signed_capture):
    """Capture and independently verify original NHL HTTPS bytes and C03 HMAC."""
    current_storage(root)
    freeze, start = clock(input_freeze_at), clock(event_start_at)
    require(datetime.now(UTC) < freeze < start, "ORIGINAL_SOURCE_FREEZE_EXPIRED")
    require(url.startswith(OFFICIAL + "/"), "OFFICIAL_NHL_URL_REQUIRED")
    subroot = Path(root) / ROOT_NAMESPACE / "c03"
    receipt = capture(url, archive_root=subroot, source_namespace="nhl_official",
                      source_id=source_id, input_cutoff_at=input_freeze_at,
                      event_start_at=event_start_at)
    require(receipt.get("source_url") == url, "ORIGINAL_SOURCE_URL_MISMATCH")
    doc = verify(receipt, archive_root=subroot, freeze=input_freeze_at,
                 event_start=event_start_at)
    observed = clock(receipt.get("received_at"))
    require(observed <= freeze < start, "SOURCE_AFTER_INPUT_FREEZE")
    relative = str(Path(ROOT_NAMESPACE) / "c03" / receipt["archive_path"])
    archived = safe_relative(root, relative)
    require(archived.is_file() and digest(archived.read_bytes()) ==
            receipt.get("body_sha256"), "C03_ORIGINAL_BODY_MISSING_OR_CORRUPT")
    source_record = {
        "record_type": "SourceReceipt", "schema_version": P0_VERSION,
        "receipt_id": "p2:" + digest(canonical_bytes(
            [source_id, url, receipt["body_sha256"], receipt["received_at"]])),
        "source_id": str(source_id), "source_kind": str(source_kind),
        "source_available_at": stamp(observed), "collected_at": stamp(observed),
        "source_sha256": receipt["body_sha256"], "archive_path": relative,
        "provenance_class": "collector_possession"
    }
    validate_record("SourceReceipt", source_record)
    added = append_immutable(root, "SourceReceipt", source_record)
    return {"document": doc, "c03_receipt": receipt, "p0_receipt": source_record,
            "p0_sha256": added["sha256"], "origin": "signed_collector_possession"}


def retrieve_source(root, source, *, freeze, event_start, verify=verify_signed_capture):
    """Recheck P0 record, archived raw body and C03 proof at read time."""
    require(isinstance(source, dict) and "p0_sha256" in source and
            "c03_receipt" in source, "SOURCE_RECEIPT_BUNDLE_MISSING")
    p0 = verify_immutable_record(root, "SourceReceipt", source["p0_sha256"])
    require(p0["receipt_id"] == source["p0_receipt"]["receipt_id"],
            "SOURCE_RECEIPT_ID_MISMATCH")
    require(clock(p0["source_available_at"]) <= clock(freeze) <
            clock(event_start), "SOURCE_CHRONOLOGY_INVALID")
    raw = safe_relative(root, p0["archive_path"]).read_bytes()
    require(digest(raw) == p0["source_sha256"], "RAW_SOURCE_SHA_DRIFT")
    data = verify(source["c03_receipt"],
                  archive_root=Path(root) / ROOT_NAMESPACE / "c03",
                  freeze=freeze, event_start=event_start)
    require(digest(raw) == source["c03_receipt"]["body_sha256"],
            "C03_SOURCE_BYTES_MISMATCH")
    return data


def probe_schedule(day, *, opener=urlopen):
    """Unsigned transient discovery only. NEVER certifies source bytes."""
    require(isinstance(day, str) and DATE.fullmatch(day), "INVALID_SCHEDULE_DAY")
    request = Request(OFFICIAL + "/score/" + day,
                      headers={"User-Agent": "pickem-auditor-P2-source/1"})
    with opener(request, timeout=12) as r:
        doc = json.loads(r.read())
    require(isinstance(doc, dict) and isinstance(doc.get("games"), list),
            "SCHEDULE_DISCOVERY_INVALID")
    return doc


def scheduled_games(doc, *, day):
    require(isinstance(doc, dict) and isinstance(doc.get("games"), list),
            "OFFICIAL_SCHEDULE_INVALID")
    games, seen = [], set()
    for item in doc["games"]:
        event = str(item.get("id") or "")
        if not event.isdigit():
            raise SourceBlocked("INVALID_NHL_EVENT_ID")
        require(event not in seen, "DUPLICATE_NHL_EVENT_ID")
        seen.add(event)
        team_a = (item.get("awayTeam") or {}).get("abbrev")
        team_h = (item.get("homeTeam") or {}).get("abbrev")
        start = clock(item.get("startTimeUTC"))
        if item.get("gameState") not in FUTURE_STATES:
            continue
        require(isinstance(team_a, str) and isinstance(team_h, str) and
                team_a and team_h and team_a != team_h, "OFFICIAL_EVENT_TEAMS_INVALID")
        games.append({
            "event_id": event, "away_team": team_a, "home_team": team_h,
            "start_at": stamp(start), "game_state": item["gameState"],
            "scheduled_day": day,
            "local_date": start.astimezone(ZoneInfo("America/Toronto")).date().isoformat(),
            "official_season": item.get("season"),
            "game_type": item.get("gameType")
        })
    return sorted(games, key=lambda x: (x["start_at"], x["event_id"]))


def capture_window(start_at, now, *, early_minutes=60, final_minutes=20,
                   tolerance_minutes=5):
    """An invocation window is only a scheduling opportunity, never proof."""
    start = clock(start_at)
    require(now.tzinfo is not None, "AWARE_CLOCK_REQUIRED")
    delta = (start - now.astimezone(UTC)).total_seconds() / 60
    if delta <= final_minutes:
        return "MISSED_SOURCE_FREEZE_DEADLINE"
    if abs(delta - early_minutes) <= tolerance_minutes:
        return "EARLY"
    if final_minutes < delta <= final_minutes + tolerance_minutes:
        return "FINAL"
    return "OUTSIDE_CAPTURE_WINDOW"


def signed_schedule_game(root, game, *, day, freeze, capture=capture_signed_live,
                         verify=verify_signed_capture):
    source = capture_official(root, OFFICIAL + "/score/" + day,
                              event_start_at=game["start_at"], input_freeze_at=freeze,
                              source_kind="nhl_schedule",
                              source_id="nhl:schedule:" + day,
                              capture=capture, verify=verify)
    doc = source["document"]
    matching = [g for g in doc.get("games", []) if str(g.get("id")) == game["event_id"]]
    require(len(matching) == 1, "SIGNED_OFFICIAL_EVENT_NOT_UNIQUE")
    latest = scheduled_games({"games": matching}, day=day)
    require(len(latest) == 1, "SIGNED_GAME_NOT_PREGAME")
    ref = latest[0]
    require((ref["away_team"], ref["home_team"], ref["start_at"]) ==
            (game["away_team"], game["home_team"], game["start_at"]),
            "SCHEDULE_REVISED_AFTER_DISCOVERY")
    # Every changed official schedule is an immutable new version.
    raw = canonical_bytes({"schema": "PA-P2-SCHEDULE-V1",
                           "game": ref, "source_sha256": source["p0_sha256"]})
    put_once(root, ROOT_NAMESPACE + "/schedule_versions/" +
             game["event_id"] + "/" + digest(raw) + ".json", raw)
    return source


def parse_roster(doc, team):
    require(isinstance(doc, dict), "OFFICIAL_ROSTER_INVALID")
    indexed = {}
    for key, role in (("forwards", "F"), ("defensemen", "D"),
                      ("goalies", "G")):
        rows = doc.get(key)
        require(isinstance(rows, list), "OFFICIAL_ROSTER_GROUP_MISSING")
        for row in rows:
            pid = str(row.get("id") or "")
            require(PLAYER_ID.fullmatch(pid) is not None,
                    "OFFICIAL_ROSTER_PLAYER_ID_INVALID")
            require(pid not in indexed, "OFFICIAL_ROSTER_DUPLICATE_PLAYER")
            indexed[pid] = {"player_id": pid, "team_id": team,
                            "position_group": role, "source_role": key,
                            "participation_status": "UNKNOWN"}
    return indexed


def capture_two_rosters(root, game, *, freeze, capture=capture_signed_live,
                        verify=verify_signed_capture):
    docs, source, members = {}, {}, {}
    for team in (game["home_team"], game["away_team"]):
        item = capture_official(root, OFFICIAL + "/roster/" + team + "/current",
                                event_start_at=game["start_at"], input_freeze_at=freeze,
                                source_kind="nhl_current_roster",
                                source_id="nhl:roster:" + team,
                                capture=capture, verify=verify)
        docs[team], source[team] = item["document"], item
        members[team] = parse_roster(item["document"], team)
    require(not (set(members[game["home_team"]]) &
                 set(members[game["away_team"]])), "PLAYER_IN_BOTH_ROSTERS")
    return source, members


def verified_history(root, entries, *, player_id, position_group, freeze, start,
                     allow_empty=True):
    """Consume the existing signed official SOG/TOI observation producer."""
    from v2.nhl_sog_official_history_producer import independent_verify_observation_lineage
    from v2.nhl_sog_exposure_shadow import verify_observation
    require(isinstance(entries, list), "HISTORY_ENTRIES_NOT_A_LIST")
    rows, seen = [], set()
    for entry in entries:
        receipt = independent_verify_observation_lineage(
            entry, archive_root=Path(root) / ROOT_NAMESPACE / "c03",
            freeze=freeze, event_start=start)
        obs = verify_observation(receipt, Path(root) / ROOT_NAMESPACE / "c03", freeze)
        require(obs["player_id"] == str(player_id) and
                obs["position_group"] == position_group,
                "HISTORY_WRONG_PLAYER_OR_POSITION")
        gid = obs["event_id"]
        require(gid not in seen, "DUPLICATE_PLAYER_GAME_HISTORY")
        seen.add(gid)
        original = obs["source_game_log_row"]
        game_date = original.get("gameDate")
        require(isinstance(game_date, str) and DATE.fullmatch(game_date) and
                game_date < clock(start).date().isoformat(),
                "HISTORY_NOT_PRIOR_TO_TARGET")
        require(clock(obs["event_ended_at"]) <= clock(freeze),
                "HISTORICAL_FINAL_NOT_AVAILABLE_AT_FREEZE")
        rows.append({
            "game_id": gid, "game_date": game_date,
            "historical_team": original.get("teamAbbrev"),
            "shots_on_goal": obs["shots_on_goal"],
            "toi_minutes": obs["toi_minutes"],
            "derived_observation_sha256": receipt["content_sha256"],
            "derived_archive_path": receipt["archive_path"],
            "signed_profile_proof_sha256":
                entry["raw_profile_receipt"]["collector_proof_sha256"],
            "signed_log_proof_sha256":
                entry["raw_log_receipt"]["collector_proof_sha256"],
            "signed_final_proof_sha256":
                entry["raw_final_receipt"]["collector_proof_sha256"]
        })
    if not allow_empty:
        require(rows, "NO_VERIFIED_HISTORICAL_PLAYED_GAMES")
    return sorted(rows, key=lambda x: (x["game_date"], x["game_id"]))


def quote_from_archived_raw(root, raw_ref, offered, *, player_id, team, opponent,
                            event_id, start, freeze, official_name):
    """Fail-closed native provider two-sided binding, without synthetic odds.

    raw_ref must be an ORIGINAL capture's possession/transport receipt.
    It is not accepted merely because somebody wrote a JSON quote dictionary.
    """
    from .market_capture import verify_original_provider
    payload = verify_original_provider(root, raw_ref, freeze=freeze,
                                       event_start=start)
    received = clock(raw_ref["received_at"])
    raw = safe_relative(root, raw_ref["archive_path"])
    require(offered.get("fixture_kind") != "synthetic", "SYNTHETIC_QUOTE_FORBIDDEN")
    native_id = str(offered.get("native_nhl_player_id") or "")
    provider_pid = str(offered.get("provider_player_id") or "")
    require(native_id == str(player_id) and PLAYER_ID.fullmatch(native_id) and
            provider_pid and provider_pid != "None",
            "PROVIDER_PLAYER_CROSSWALK_MISSING")
    require(str(offered.get("official_event_id")) == str(event_id) and
            str(offered.get("provider_event_id")) and
            offered.get("team") == team and offered.get("opponent") == opponent,
            "PROVIDER_GAME_TEAM_CROSSWALK_MISMATCH")
    require(offered.get("crosswalk_source_sha256") and
            HEX.fullmatch(offered["crosswalk_source_sha256"]) is not None,
            "PROVIDER_CROSSWALK_EVIDENCE_MISSING")
    def norm(s):
        import unicodedata
        s = unicodedata.normalize("NFKD", str(s)).casefold()
        return " ".join("".join(c if c.isalnum() else " " for c in s
                          if not unicodedata.combining(c)).split())
    require(norm(offered.get("provider_player_name")) == norm(official_name),
            "OFFICIAL_PROVIDER_NAME_MISMATCH")
    require(offered.get("stat") == "player_shots_on_goal" and
            offered.get("period") == "full" and
            offered.get("product_type") == "sportsbook_two_sided",
            "INCOMPATIBLE_SOG_MARKET")
    line = offered.get("line")
    require(type(line) in (int, float) and line >= 0, "INVALID_SOG_LINE")
    prices = {}
    for side in ("over", "under"):
        x = offered.get(side + "_odds")
        require(type(x) in (int, float) and (x >= 100 or x <= -100),
                "MISSING_OR_INVALID_" + side.upper() + "_PRICE")
        prices[side] = x
    events = payload if isinstance(payload, list) else payload.get(
        "events", payload.get("data", []))
    require(isinstance(events, list), "PROVIDER_EVENT_BODY_INVALID")
    matching = [e for e in events if str(e.get("id")) ==
                str(offered["provider_event_id"])]
    require(len(matching) == 1, "PROVIDER_EVENT_NOT_UNIQUE")
    counts = Counter()
    for book in matching[0].get("bookmakers", []):
        if str(book.get("key")) != str(offered.get("book")):
            continue
        for market in book.get("markets", []):
            if market.get("key") != "player_shots_on_goal":
                continue
            for o in market.get("outcomes", []):
                side = str(o.get("name", "")).lower()
                if side not in ("over", "under"):
                    continue
                if str(o.get("player_id")) != provider_pid or (
                        norm(o.get("description", o.get("player"))) != norm(official_name)):
                    continue
                if (o.get("point", o.get("line")) == line and
                        o.get("price", o.get(side + "_odds")) == prices[side]):
                    counts[side] += 1
    require(counts == {"over": 1, "under": 1},
            "ORIGINAL_TWO_SIDED_PROVIDER_ROW_MISMATCH")
    return {
        "quote_id": "p2q:" + digest(canonical_bytes(
            [event_id, player_id, provider_pid, offered["book"], line,
             prices, raw_ref["sha256"], raw_ref["received_at"]])),
        "event_id": str(event_id), "player_id": str(player_id),
        "provider_event_id": str(offered["provider_event_id"]),
        "provider_player_id": provider_pid, "provider_player_name":
            offered["provider_player_name"], "team_id": team,
        "opponent_id": opponent, "stat_key": "shots on goal",
        "period": "full", "line": line, "book": offered["book"],
        "product_type": "sportsbook_two_sided",
        "over_american": prices["over"], "under_american": prices["under"],
        "quote_timestamp": stamp(received),
        "original_raw_sha256": raw_ref["sha256"],
        "structured_row_sha256": digest(canonical_bytes(offered)),
        "crosswalk_source_sha256": offered["crosswalk_source_sha256"],
        "publisher_publication_time_verified": False,
        "source_semantics": "original_collector_possession"
    }


def build_bundle(root, *, game, schedule_source, rosters, roster_members,
                 player_id, history_entries, freeze, quote=None,
                 required_experiment=None, peer_entries=None, history_pool=None,
                 quote_evidence=None, role_transition_uncertain=False):
    """Stable source-only P4/P5 handoff, preserving P0 feature contract."""
    current_storage(root)
    start = game["start_at"]
    require(datetime.now(UTC) <= clock(freeze) < clock(start),
            "INVALID_OR_EXPIRED_ORIGINAL_INPUT_FREEZE")
    event_id = game["event_id"]
    require(game["game_state"] in FUTURE_STATES, "TARGET_NOT_PREGAME")
    require(schedule_source["p0_receipt"]["source_id"] ==
            "nhl:schedule:" + game["scheduled_day"] and
            schedule_source["c03_receipt"]["source_url"] ==
            OFFICIAL + "/score/" + game["scheduled_day"],
            "SIGNED_SCHEDULE_ORIGIN_MISMATCH")
    retrieve_source(root, schedule_source, freeze=freeze, event_start=start)
    team = next((t for t in (game["home_team"], game["away_team"])
                 if str(player_id) in roster_members[t]), None)
    if team is None:
        raise SourceBlocked("PLAYER_NOT_IN_CURRENT_SIGNED_ROSTER")
    other = game["home_team"] if team == game["away_team"] else game["away_team"]
    require(str(player_id) not in roster_members[other],
            "PLAYER_IN_OPPONENT_ROSTER")
    group = roster_members[team][str(player_id)]["position_group"]
    require(group in ("F", "D"), "UNSUPPORTED_SOG_POSITION")
    require(set(rosters) == {game["home_team"], game["away_team"]},
            "TWO_TEAM_ROSTER_SOURCE_REQUIRED")
    from .history_bridge import verified_player_history
    from .quote_bridge import verify_real_quote
    for verified_team, source in rosters.items():
        require(source["p0_receipt"]["source_id"] ==
                "nhl:roster:" + verified_team and
                source["c03_receipt"]["source_url"] ==
                OFFICIAL + "/roster/" + verified_team + "/current",
                "SIGNED_ROSTER_SOURCE_TEAM_MISMATCH")
        signed_doc = retrieve_source(root, source, freeze=freeze, event_start=start)
        if signed_doc is not None:  # Unit fixtures can mock this return.
            require(parse_roster(signed_doc, verified_team) == roster_members[verified_team],
                    "SIGNED_CURRENT_ROSTER_INDEX_DRIFT")
        require((clock(freeze) - clock(source["p0_receipt"]["collected_at"]))
                <= timedelta(hours=6), "ROSTER_SOURCE_STALE")
    require(history_pool is not None,
            "P0_BRIDGED_ORIGINAL_HISTORICAL_SOURCE_POOL_REQUIRED")
    own, own_refs = verified_player_history(root, history_pool, history_entries,
                        player_id=player_id, group=group,
                        freeze=freeze, event_start=start)
    require(len(own) > 0, "NO_ORIGINAL_VERIFIED_SOG_TOI_HISTORY")
    peer, peer_refs = [], []
    for other_player, entries in sorted((peer_entries or {}).items()):
        require(str(other_player) != str(player_id), "PEER_IS_TARGET_PLAYER")
        rows, references = verified_player_history(root, history_pool, entries,
                player_id=other_player, group=group,
                freeze=freeze, event_start=start)
        peer.extend(rows)
        peer_refs.extend(references)
    all_game_ids = [x["game_id"] for x in own]
    require(len(set(all_game_ids)) == len(own),
            "HISTORICAL_PLAYER_GAME_DOUBLE_COUNT")
    historical_source_ids = sorted({
        item["record"]["receipt_id"] for item in own_refs + peer_refs
    })
    require(historical_source_ids, "NO_P0_ORIGINAL_HISTORICAL_SOURCE_RECEIPTS")
    if quote is not None:
        require(quote_evidence is not None,
                "P0_ORIGINAL_QUOTE_RECEIPT_REQUIRED")
        original_quote = verify_real_quote(root, quote_evidence,
                        freeze=freeze, event_start=start)
        require(original_quote["quote_id"] == quote["quote_id"] and
                original_quote["event_id"] == event_id and
                original_quote["player_id"] == str(player_id),
                "SOURCE_QUOTE_P0_IDENTITY_DRIFT")
    requires_quote = required_experiment in {
        "EXP-V25-NHL-SOG-EXPOSURE-EB-001",
        "EXP_NHL_SOG_P15_RATE_DISPERSION_NEXT_PROSPECTIVE",
        "EXP-V25-NHL-SOG-NB2-NATIVE-PLUGIN-MEAN-20261114"
    }
    if requires_quote and quote is None:
        admission = "ABSTAIN_GENUINE_TWO_SIDED_QUOTE_MISSING"
    else:
        admission = ("SOURCE_READY_WITH_ORIGINAL_MARKET" if quote is not None
                     else "SOURCE_READY_LINE_INDEPENDENT_ONLY")
    require(quote is None or (quote["event_id"] == event_id and
            quote["player_id"] == str(player_id) and
            quote["team_id"] == team and quote["opponent_id"] == other),
            "QUOTE_BUNDLE_IDENTITY_MISMATCH")
    source_ids = [schedule_source["p0_receipt"]["receipt_id"]] + [
        rosters[t]["p0_receipt"]["receipt_id"]
        for t in (game["home_team"], game["away_team"])] + historical_source_ids
    if quote is not None:
        source_ids.append(quote_evidence["p0_source_record"]["receipt_id"])
    source_ids = sorted(set(source_ids))
    # Original signed history is stored by the existing C03 producer and is
    # reverified here. Its raw proof hashes remain explicit, not replaced
    # with invented P0 SourceReceipt IDs.
    latest_team = own[-1].get("historical_team")
    if isinstance(latest_team, dict):
        latest_team = latest_team.get("default")
    inferred_transition = bool(latest_team and latest_team != team)
    role_uncertain = bool(role_transition_uncertain or inferred_transition)
    features = {
        "official_game": game,
        "player": {"official_nhl_player_id": str(player_id), "team_id": team,
                   "opponent_id": other, "position_group": group,
                   "participation_status": "UNKNOWN",
                   "roster_is_not_game_participation_confirmation": True,
                   "last_verified_played_team": latest_team,
                   "prior_team_differs_from_current_roster": inferred_transition},
        "history": {"own": own, "peers": peer, "cutoff_at": freeze,
                    "P0_historical_source_receipt_ids": historical_source_ids},
        "market": quote,
        "market_source_evidence": (quote_evidence["provider_original_capture"]
                                   if quote_evidence is not None else None),
        "missingness": {"quote_missing": quote is None,
                        "participation_unconfirmed": True,
                        "role_transition_uncertain": role_uncertain},
        "evidence_class": "ORIGINAL_PREGAME_COLLECTOR_POSSESSION",
        "P4_gamma_artifact_required": True,
        "history_count_is_not_experiment_admission": True
    }
    feature_record = {
        "record_type": "PregameFeatureSnapshot", "schema_version": P0_VERSION,
        "feature_snapshot_id": "p2f:" + digest(canonical_bytes([
            event_id, str(player_id), freeze, required_experiment or "line_independent",
            sorted(source_ids), sha256(features)])),
        "sport": "NHL", "event_id": event_id, "team_id": team,
        "opponent_id": other, "player_id": str(player_id),
        "stat_key": "shots on goal", "period": "full",
        "input_freeze_at": freeze, "source_receipt_ids": source_ids,
        "feature_sha256": sha256(features), "reconstruction_class": "original",
        "features": features
    }
    validate_record("PregameFeatureSnapshot", feature_record)
    stored = append_immutable(root, "PregameFeatureSnapshot", feature_record)
    manifest = {
        "schema": SCHEMA, "p0_schema_version": P0_VERSION,
        "sport": "NHL", "stat_key": "shots on goal", "period": "full",
        "event_id": event_id, "official_nhl_player_id": str(player_id),
        "input_freeze_at": freeze, "event_start_at": start,
        "official_schedule_source_sha256": schedule_source["p0_sha256"],
        "official_roster_source_sha256": {
            team: rosters[team]["p0_sha256"],
            other: rosters[other]["p0_sha256"]},
        "signed_historical_observation_hashes": [
            x["observation_receipt_sha256"] for x in own + peer],
        "P0_original_historical_source_receipt_ids": historical_source_ids,
        "P0_original_historical_source_record_hashes": sorted({
            ref["record_sha256"] for ref in own_refs + peer_refs}),
        "P0_quote_source_sha256": (quote_evidence["p0_source_sha256"]
                                  if quote is not None else None),
        "P0_quote_record_sha256": (quote_evidence["p0_quote_sha256"]
                                  if quote is not None else None),
        "own_history_count": len(own), "peer_history_count": len(peer),
        "quote_id": quote["quote_id"] if quote else None,
        "source_admission": admission, "registered_experiment": required_experiment,
        "P4_registered_model_cohort_admission_required": True,
        "p0_feature_snapshot_id": feature_record["feature_snapshot_id"],
        "p0_feature_record_sha256": stored["sha256"],
        "source_availability_clock_semantics": "collector_possession",
        "P4_prediction_required": True, "P5_settlement_required": True,
        "model_predictions_present": False, "research_only": True
    }
    raw = canonical_bytes(manifest)
    address = put_once(root, ROOT_NAMESPACE + "/bundles/" + digest(raw) + ".json", raw)
    return {"manifest": manifest, "receipt": address, "feature": feature_record}


def verify_bundle(root, manifest_sha):
    current_storage(root)
    require(isinstance(manifest_sha, str) and HEX.fullmatch(manifest_sha),
            "SOURCE_BUNDLE_DIGEST_INVALID")
    path = ROOT_NAMESPACE + "/bundles/" + manifest_sha + ".json"
    raw = safe_relative(root, path).read_bytes()
    require(_completed_target(safe_relative(root, path), manifest_sha),
            "SOURCE_BUNDLE_INCOMPLETE_OR_CORRUPT")
    require(digest(raw) == manifest_sha, "SOURCE_BUNDLE_CORRUPT")
    doc = json.loads(raw)
    require(doc.get("schema") == SCHEMA and doc["model_predictions_present"] is False,
            "SOURCE_BUNDLE_SCHEMA_INVALID")
    from v2.p0_integrity.contracts import verify_source_bytes
    sha_list = [
        doc["official_schedule_source_sha256"],
        *doc["official_roster_source_sha256"].values(),
        *doc["P0_original_historical_source_record_hashes"]
    ]
    if doc.get("P0_quote_source_sha256"):
        sha_list.append(doc["P0_quote_source_sha256"])
    source_records = []
    for sha in sorted(set(sha_list)):
        src = verify_immutable_record(root, "SourceReceipt", sha)
        verify_source_bytes(src, root)
        require(clock(src["source_available_at"]) <= clock(doc["input_freeze_at"]) <
                clock(doc["event_start_at"]), "SOURCE_RECHECK_AFTER_FREEZE")
        source_records.append(src)
    feature = verify_immutable_record(root, "PregameFeatureSnapshot",
                                     doc["p0_feature_record_sha256"])
    require(feature["feature_snapshot_id"] == doc["p0_feature_snapshot_id"] and
            sha256(feature["features"]) == feature["feature_sha256"],
            "SOURCE_BUNDLE_FEATURE_DRIFT")
    require(set(feature["source_receipt_ids"]) == {
        src["receipt_id"] for src in source_records},
        "SOURCE_BUNDLE_P0_SOURCE_CLOSURE_MISMATCH")
    if doc.get("P0_quote_record_sha256"):
        quote = verify_immutable_record(root, "MarketQuote",
                                      doc["P0_quote_record_sha256"])
        require(quote["source_receipt_id"] in feature["source_receipt_ids"] and
                quote["event_id"] == doc["event_id"] and
                quote["player_id"] == doc["official_nhl_player_id"] and
                quote["quote_kind"] == "real",
                "SOURCE_BUNDLE_QUOTE_NOT_SOURCE_BOUND")
    return doc, feature


def run_rolling(root="/work", *, days=None, early_minutes=60,
                final_minutes=20, tolerance_minutes=5,
                max_games=None):
    """Real-clock, schedule-driven, NHL-only prospective capture attempt.

    Discovery is unsigned planning input; signed schedule/roster capture
    happens only inside the event-relative window. Missing history or quote
    must be supplied by its existing original producer; no model is run.
    """
    current_storage(root)
    now = datetime.now(UTC)
    local = now.astimezone(ZoneInfo("America/Toronto")).date()
    dates = days or [local.isoformat(),
                     (local + timedelta(days=1)).isoformat()]
    attempts, accepted = [], []
    for day in dates:
        try:
            unsigned = probe_schedule(day)
            events = scheduled_games(unsigned, day=day)
        except Exception as exc:
            attempts.append(attempt(root, "schedule_discovery", "REJECTED",
                                    [type(exc).__name__ + ":" + str(exc)[:150]],
                                    day=day))
            continue
        for game in events[:max_games] if max_games else events:
            status = capture_window(game["start_at"], datetime.now(UTC),
                                    early_minutes=early_minutes,
                                    final_minutes=final_minutes,
                                    tolerance_minutes=tolerance_minutes)
            if status != "EARLY" and status != "FINAL":
                if status == "MISSED_SOURCE_FREEZE_DEADLINE":
                    attempts.append(attempt(root, "source_window", "MISSED",
                                            [status], event_id=game["event_id"],
                                            event_start_at=game["start_at"]))
                continue
            freeze = stamp(clock(game["start_at"]) -
                           timedelta(minutes=final_minutes))
            try:
                schedule = signed_schedule_game(root, game, day=day, freeze=freeze)
                rosters, members = capture_two_rosters(root, game, freeze=freeze)
                accepted.append({
                    "event_id": game["event_id"], "window": status, "game": game,
                    "freeze": freeze, "schedule_sha256": schedule["p0_sha256"],
                    "roster_sha256": {k: v["p0_sha256"] for k, v in rosters.items()},
                    "skaters_discovered": sum(
                        sum(1 for x in r.values() if x["position_group"] in ("F", "D"))
                        for r in members.values()),
                    "source_state": "SIGNED_GAME_AND_ROSTERS_ONLY",
                    "missing": ["HISTORICAL_OBSERVATIONS", "AUTHENTIC_PROVIDER_QUOTE",
                                "PLAYER_SPECIFIC_SOURCE_BUNDLE"]
                })
                attempts.append(attempt(root, "official_game_rosters",
                                        "VERIFIED_INCOMPLETE",
                                        ["HISTORY_AND_QUOTE_PRODUCER_HANDOFF_PENDING"],
                                        event_id=game["event_id"], window=status,
                                        schedule_sha256=schedule["p0_sha256"]))
            except Exception as exc:
                attempts.append(attempt(root, "official_game_rosters", "REJECTED",
                                        [type(exc).__name__ + ":" + str(exc)[:160]],
                                        event_id=game["event_id"], window=status))
    return {"schema": "PA-P2-NHL-ROLLING-RUN/1",
            "generated_at": stamp(datetime.now(UTC)),
            "official_partial_source_games": accepted,
            "attempt_count": len(attempts),
            "source_verified_incomplete": len(accepted),
            "source_rejection_count": sum(x["status"] == "REJECTED" for x in attempts),
            "missed_deadline_count": sum(x["status"] == "MISSED" for x in attempts),
            "frozen_predictions_created": 0,
            "real_two_sided_quotes_created": 0,
            "attempt_receipt_hashes": [x["receipt"]["sha256"] for x in attempts],
            "release_certified": False}
