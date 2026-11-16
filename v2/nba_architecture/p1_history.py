"""P1 canonical historical NBA adapter for the frozen G0 v2.0.0 contract.

Consumes WS1 normalized Record/Receipt envelopes, not the live collector.
The resulting as-of representation is a RETROSPECTIVE, date-only research
proxy, never certification that the source was observed before the old game.
The official outcome vault is intentionally NOT imported by this module.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import json
import math

from .v2_contracts import (
    VERSION, canonical, digest, seal, receipt, validate_pregame, instant,
)

ADAPTER_VERSION = "nba-p1-ws1-historical-adapter/1.0.0"
ASOF_WARNING = (
    "WS1 retrospective normalized records; selected prior-game dates only. "
    "Original pregame publication/capture clocks, active rosters, historic "
    "corrections and schedule-as-known-then are not independently certified."
)
ALLOWED = {"player_game", "team_game"}
COUNT_STATS = {
    "points", "rebounds", "assists", "threes", "steals", "blocks",
    "turnovers", "pra", "pr", "pa", "ra", "fgm", "fga", "fg3a",
    "ftm", "fta", "oreb", "dreb", "personal_fouls",
}


class HistoryIntegrityError(ValueError):
    pass


def fail(code):
    raise HistoryIntegrityError(code)


def _strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: fail("NONFINITE_JSON"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise HistoryIntegrityError("INVALID_JSON_OR_ENCODING") from exc


def _utc(text):
    try:
        return instant(text).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (ValueError, TypeError) as exc:
        raise HistoryIntegrityError("TIMESTAMP_INVALID") from exc


def _stats(stats):
    if not isinstance(stats, dict) or set(stats) - COUNT_STATS:
        fail("UNSUPPORTED_STAT_DEFINITION")
    if "3PT" in stats:
        fail("THREES_REQUIRE_WS1_PAIR_NORMALIZER")
    for key, value in stats.items():
        if type(value) is not int or value < 0:
            fail("INVALID_BOX_COUNT")
    for made, attempted in (("fgm", "fga"), ("threes", "fg3a"),
                            ("ftm", "fta")):
        if made in stats and attempted in stats and stats[made] > stats[attempted]:
            fail("SHOOTING_ACCOUNTING")
    if "threes" in stats and "fgm" in stats and stats["threes"] > stats["fgm"]:
        fail("SHOOTING_ACCOUNTING")
    if all(k in stats for k in ("fgm", "threes", "ftm", "points")):
        if stats["points"] != 2 * stats["fgm"] + stats["threes"] + stats["ftm"]:
            fail("POINT_ACCOUNTING")
    if all(k in stats for k in ("oreb", "dreb", "rebounds")):
        if stats["oreb"] + stats["dreb"] != stats["rebounds"]:
            fail("REBOUND_ACCOUNTING")
    for combo, keys in (
        ("pr", ("points", "rebounds")),
        ("pa", ("points", "assists")),
        ("ra", ("rebounds", "assists")),
        ("pra", ("points", "rebounds", "assists")),
    ):
        if combo in stats and all(k in stats for k in keys):
            if stats[combo] != sum(stats[k] for k in keys):
                fail("COMBINATION_ACCOUNTING")


def validate_ws1_envelope(record, source, *, require_source_bytes=None):
    """Verify WS1's SHA-bound normalized Record and Receipt without importing WS1.

    require_source_bytes is exact original provider/shard capture bytes if
    available. Absence is recorded in the returned lineage; never assumed.
    """
    if not isinstance(record, dict) or set(record) != {
        "kind", "receipt_id", "payload", "revision", "supersedes", "record_id"
    }:
        fail("WS1_RECORD_FIELDS")
    if record["kind"] not in ALLOWED:
        fail("WS1_OUTCOME_KIND_NOT_PERMITTED")
    if record["revision"] != 1 or record["supersedes"] is not None:
        fail("CORRECTED_RECORD_REQUIRES_EXPLICIT_CHAIN")
    if record["receipt_id"] != source.get("receipt_id"):
        fail("WS1_RECEIPT_IDENTITY")
    if not isinstance(record["payload"], str):
        fail("WS1_RECORD_PAYLOAD")
    data = _strict_json(record["payload"])
    if canonical(data).decode("utf-8") != record["payload"]:
        fail("NONCANONICAL_WS1_PAYLOAD")
    record_body = {k: record[k] for k in (
        "kind", "receipt_id", "payload", "revision", "supersedes"
    )}
    if digest(record_body) != record["record_id"]:
        fail("WS1_RECORD_SHA_MISMATCH")
    expected = {"source", "raw_sha256", "observed_at",
                "source_available_at", "origin", "receipt_id"}
    if not isinstance(source, dict) or set(source) != expected:
        fail("WS1_RECEIPT_FIELDS")
    if source["origin"] != "retrospective_retrieval":
        fail("WS1_ORIGIN_NOT_RETROSPECTIVE")
    if digest({k: source[k] for k in expected - {"receipt_id"}}) != source["receipt_id"]:
        fail("WS1_RECEIPT_SHA_MISMATCH")
    observed = _utc(source["observed_at"])
    available = _utc(source["source_available_at"])
    if available < observed:
        fail("SOURCE_CLOCK_BACKDATED")
    raw_verified = False
    if require_source_bytes is not None:
        if not isinstance(require_source_bytes, bytes):
            fail("ORIGINAL_SOURCE_BYTES_REQUIRED")
        if hashlib.sha256(require_source_bytes).hexdigest() != source["raw_sha256"]:
            fail("ORIGINAL_SOURCE_SHA_MISMATCH")
        raw_verified = True
    keys = {"game_id", "player_id", "team_id", "opponent_id",
            "game_date", "minutes", "participation", "starter", "stats"}
    if record["kind"] == "player_game":
        if set(data) != keys:
            fail("PLAYER_ROW_FIELDS")
        if data["participation"] not in ("played", "dnp", "unknown"):
            fail("INVALID_DNP_STATUS")
        if data["starter"] is not None and type(data["starter"]) is not bool:
            fail("INVALID_STARTER")
        if data["participation"] == "played":
            minutes = data["minutes"]
            if type(minutes) not in (int, float) or not math.isfinite(minutes) or minutes < 0:
                fail("INVALID_MINUTES")
            _stats(data["stats"])
        elif data["minutes"] is not None or data["stats"]:
            fail("DNP_UNKNOWN_NOT_ZERO")
    elif record["kind"] == "team_game":
        if set(data) != {"game_id", "team_id", "opponent_id", "game_date",
                         "possessions", "pace_per_48", "stats", "opponent_stats"}:
            fail("TEAM_ROW_FIELDS")
        _stats(data["stats"])
        _stats(data["opponent_stats"])
        for name in ("possessions", "pace_per_48"):
            value = data[name]
            if value is not None and (
                type(value) not in (float, int) or not math.isfinite(value) or value < 0
            ):
                fail("INVALID_TEAM_RATE")
    for key in ("game_id", "player_id", "team_id", "opponent_id"):
        if key in data and (not isinstance(data[key], str) or
                            ":" not in data[key] or not data[key].strip()):
            fail("NONCANONICAL_IDENTITY")
    if data["team_id"] == data["opponent_id"]:
        fail("TEAM_COLLISION")
    try:
        date.fromisoformat(data["game_date"])
    except (TypeError, ValueError) as exc:
        raise HistoryIntegrityError("GAME_DATE_INVALID") from exc
    return data, raw_verified


def build_historical_pregame(*, game_id, team_ids, event_start_at,
                             input_freeze_at, forecast_at, training_cutoff_at,
                             decision_local_date, entries, ingested_at,
                             verified_source_bytes=None, max_history=20):
    """Produce G0-compatible immutable pregame dict from WS1 *prior* rows.

    entries: iterable of {"record": WS1 Record asdict, "receipt": Receipt asdict}.
    verified_source_bytes: optional mapping of receipt_id -> exact original bytes.
    Input clocks are caller-provided audit inputs; no guessed wall-clock times.
    """
    if not (type(max_history) is int and 1 <= max_history <= 200):
        fail("HISTORY_LIMIT")
    if not isinstance(game_id, str) or len(team_ids) != 2 or len(set(team_ids)) != 2:
        fail("EVENT_IDENTITY")
    if not isinstance(entries, (tuple, list)) or not entries:
        fail("HISTORY_INPUTS_MISSING")
    cutoff_date = date.fromisoformat(decision_local_date)
    ingestion = _utc(ingested_at)
    record_rows = []
    seen = set()
    source_bytes = verified_source_bytes or {}
    for item in entries:
        if set(item) != {"record", "receipt"}:
            fail("HISTORY_ENTRY_FIELDS")
        record, src = item["record"], item["receipt"]
        data, original_verified = validate_ws1_envelope(
            record, src, require_source_bytes=source_bytes.get(src["receipt_id"]))
        if data["game_id"] == game_id:
            fail("TARGET_GAME_OUTCOME_ACCESS")
        if date.fromisoformat(data["game_date"]) >= cutoff_date:
            fail("SAME_DAY_OR_FUTURE_HISTORY")
        natural_key = (record["kind"], data["game_id"],
                       data.get("player_id", data["team_id"]))
        if natural_key in seen:
            fail("DUPLICATE_OR_CORRECTED_HISTORY_ROW")
        seen.add(natural_key)
        # This hash is of the exact *normalized WS1 Record*, not an original
        # ESPN HTTP response nor a complete future-contaminated season shard.
        encoded_record = canonical(record)
        derived_sha = hashlib.sha256(encoded_record).hexdigest()
        record_rows.append((record, src, data, derived_sha, original_verified))
    # Limit by per-player/team chronological position, not by current target data.
    by_player = defaultdict(list)
    by_team = defaultdict(list)
    for row in record_rows:
        rec, _, data, _, _ = row
        if rec["kind"] == "player_game":
            by_player[data["player_id"]].append(row)
        else:
            by_team[data["team_id"]].append(row)
    retained = []
    player_roster = []
    for player_id, rows in sorted(by_player.items()):
        rows.sort(key=lambda x: (x[2]["game_date"], x[2]["game_id"], x[0]["record_id"]))
        latest = rows[-1][2]
        # Candidate membership only. No historical active-list claim and no
        # trade inference from the opponent's eventual target box score.
        if latest["team_id"] not in team_ids:
            continue
        if len({x[2]["team_id"] for x in rows if
                x[2]["game_date"] == latest["game_date"]}) > 1:
            fail("SAME_DAY_PLAYER_TEAM_CONFLICT")
        retained.extend(rows[-max_history:])
        player_roster.append(dict(
            player_id=player_id, team_id=latest["team_id"],
            legal_eligibility=None, eligibility_evidence=None,
            availability="unknown", availability_evidence=None))
    for team_id in sorted(team_ids):
        rows = sorted(by_team.get(team_id, ()),
                      key=lambda x: (x[2]["game_date"], x[2]["game_id"]))
        retained.extend(rows[-max_history:])
    if not player_roster:
        fail("NO_DATE_PRIOR_ROSTER_CANDIDATES")
    sources = []
    features = []
    for record, src, data, derived_sha, original_verified in sorted(
            retained, key=lambda r: (r[2]["game_date"], r[0]["record_id"])):
        source_id = "ws1:normalized:" + record["record_id"]
        source_obj = receipt(dict(
            source_id=source_id, source_revision=1,
            supersedes_receipt_sha256=None, raw_sha256=derived_sha,
            origin="retrospective_retrieval", scope="prior_game",
            contains_target_final=False, provider_published_at=None,
            publication_evidence="unknown",
            collector_observed_at=_utc(src["observed_at"]),
            retrieved_at=_utc(src["observed_at"]), ingested_at=ingestion,
            asof_basis="prior_game_date_only",
            historical_game_date=data["game_date"],
            asof_limitations=ASOF_WARNING + (
                " Original bytes independently verified."
                if original_verified else " Original provider bytes not supplied.")))
        sources.append(source_obj)
        base_name = ("player:" + data["player_id"] if record["kind"] == "player_game"
                     else "team:" + data["team_id"])
        fields = dict(data["stats"])
        if record["kind"] == "player_game":
            fields["participation"] = (
                "PLAYED_ZERO_MINUTES" if data["participation"] == "played"
                and data["minutes"] == 0 else data["participation"].upper())
            fields["minutes"] = data["minutes"]
            fields["starter"] = data["starter"]
        else:
            fields["possessions"] = data["possessions"]
            fields["pace_per_48"] = data["pace_per_48"]
        for name, value in sorted(fields.items()):
            features.append(dict(
                source_id=source_id, source_receipt_sha256=source_obj["receipt_sha256"],
                name=base_name + ":" + name, value=value,
                kind="prior_boxscore", asof_basis="prior_game_date_only",
                target_game_outcome=False, prior_game_date=data["game_date"],
                available_at=None,
                measurement_units=("minutes" if name == "minutes" else
                                   "possessions_per_48" if name == "pace_per_48"
                                   else "status" if name == "participation"
                                   else "boolean" if name == "starter"
                                   else "count")))
    payload = seal(dict(
        schema=VERSION, kind="pregame",
        source_profile="historical_reconstruction", game_id=game_id,
        team_ids=list(team_ids), event_start_at=_utc(event_start_at),
        input_freeze_at=_utc(input_freeze_at), forecast_at=_utc(forecast_at),
        training_cutoff_at=_utc(training_cutoff_at),
        decision_local_date=decision_local_date,
        certification="HISTORICAL_RECONSTRUCTION_UNCERTIFIED",
        historical_asof_limitations=ASOF_WARNING,
        sources=sources, players=sorted(player_roster, key=lambda p: p["player_id"]),
        features=features, original_offer_count=0))
    validate_pregame(payload)
    return payload


def freeze_historical(path, snapshot):
    """G0 write-once persistence, rejects a different payload at same path."""
    from .v2_contracts import freeze_once
    validate_pregame(snapshot)
    return freeze_once(path, snapshot)
