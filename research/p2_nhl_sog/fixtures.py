"""P0-compatible offline NHL SOG fixtures for P4 source-contract integration.

These are generated TEST data, NEVER an original capture, bookmaker quote,
source certification, forecast, model fit, or a valid performance cohort.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib

from v2.p0_integrity.contracts import VERSION, sha256, canonical_bytes, validate_record

SCHEMA = "PA-P2-NHL-SOG-SYNTHETIC-FIXTURES/1"
CASES = (
    "ordinary_future_game", "synthetic_two_sided_quote",
    "sufficient_signed_format_history", "insufficient_history",
    "traded_player", "missing_current_roster", "unsupported_goalie",
    "no_quote_line_independent", "role_transition_uncertain",
    "historical_final_late", "stale_signed_roster",
    "missing_or_corrupted_raw_source", "wrong_event_player_identity",
    "duplicate_historical_game"
)
FREEZE = "2027-01-15T22:40:00Z"
START = "2027-01-15T23:00:00Z"
PLAYER = "8471234"


def hexsha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def observation(player, i, *, team="MTL", position="F"):
    base = datetime(2026,10,1,tzinfo=timezone.utc) + timedelta(days=i)
    return {
        "game_id": str(2026020000+i),
        "game_date": base.date().isoformat(),
        "player_id": str(player),
        "team_id_at_game": team,
        "position_group": position,
        "shots_on_goal": i % 6,
        "toi_minutes": 10.0 + (i % 13) * 0.5,
        "source_class": "SYNTHETIC_TEST_ONLY",
        "source_witness_sha256": hexsha(["synthetic_observation", player, i])
    }


def make_case(name):
    if name not in CASES:
        raise ValueError("UNKNOWN_P2_SYNTHETIC_CASE")
    own = [observation(PLAYER, i) for i in range(10)]
    peers = [observation(str(8480000 + p), i, team="BOS")
             for p in range(20) for i in range(10)]
    game = {
        "official_nhl_game_id": "2026020999",
        "home_team_id": "MTL", "away_team_id": "BOS",
        "event_start_at": START, "game_state": "FUT",
        "local_date": "2027-01-15"
    }
    player = {
        "official_nhl_player_id": PLAYER, "team_id": "MTL",
        "opponent_id": "BOS", "position_group": "F",
        "roster_evidence_kind": "SYNTHETIC_TEST_ONLY",
        "game_participation_status": "UNKNOWN",
        "role_uncertain": False,
        "current_roster_member": True
    }
    quote = {
        "quote_kind": "synthetic", "book": "SYNTHETIC_TEST_BOOK",
        "product_type": "sportsbook_two_sided", "stat_key": "shots on goal",
        "period": "full", "line": 2.5,
        "over_american": -125, "under_american": 105,
        "player_id": PLAYER, "event_id": game["official_nhl_game_id"],
        "provider_player_id": "synthetic-provider-player-1",
        "provider_event_id": "synthetic-provider-game-1",
        "quote_timestamp": "2027-01-15T22:10:00Z",
        "source_sha256": hexsha("SYNTHETIC_TEST_NOT_ORIGINAL")
    }
    missing = []
    if name == "insufficient_history":
        own = own[:3]
        missing.append("THIN_OWN_HISTORY")
    if name == "traded_player":
        for row in own[:-2]:
            row["team_id_at_game"] = "NYR"
        player["role_uncertain"] = True
    if name == "missing_current_roster":
        player["current_roster_member"] = False
        missing.append("CURRENT_OFFICIAL_ROSTER_MISSING")
    if name == "unsupported_goalie":
        player["position_group"] = "G"
        missing.append("UNSUPPORTED_SOG_POSITION")
    if name in ("no_quote_line_independent","ordinary_future_game"):
        quote = None
        missing.append("NO_REAL_TWO_SIDED_QUOTE")
    if name == "role_transition_uncertain":
        player["role_uncertain"] = True
        missing.append("ROLE_CHANGE_UNCONFIRMED")
    if name == "historical_final_late":
        own[-1]["source_available_at"] = "2027-01-15T22:50:00Z"
        missing.append("HISTORICAL_FINAL_AFTER_INPUT_FREEZE")
    if name == "stale_signed_roster":
        player["roster_source_collected_at"] = "2027-01-15T10:00:00Z"
        missing.append("ROSTER_RECEIPT_STALE")
    if name == "missing_or_corrupted_raw_source":
        player["raw_source_corrupted"] = True
        missing.append("IMMUTABLE_SOURCE_HASH_MISMATCH")
    if name == "wrong_event_player_identity":
        quote["player_id"] = "8479999"
        missing.append("PROVIDER_OFFICIAL_PLAYER_ID_MISMATCH")
    if name == "duplicate_historical_game":
        own.append(dict(own[0]))
        missing.append("DUPLICATE_PLAYER_GAME_HISTORY")
    features = {
        "official_game": game, "player": player,
        "history": {"own": own, "peers": peers, "cutoff_at": FREEZE,
                    "synthetic_observations_not_signed": True},
        "market": quote,
        "missingness": {"quote_missing": quote is None,
                        "participation_unconfirmed": True,
                        "test_case_rejections": missing},
        "evidence_class": "SYNTHETIC_TEST_ONLY_NOT_ORIGINAL"
    }
    feature_record = {
        "record_type": "PregameFeatureSnapshot",
        "schema_version": VERSION,
        "feature_snapshot_id": "fixture:" + hexsha([name,features]),
        "sport": "NHL", "event_id": game["official_nhl_game_id"],
        "team_id": "MTL", "opponent_id": "BOS", "player_id": PLAYER,
        "stat_key": "shots on goal", "period": "full",
        "input_freeze_at": FREEZE,
        "source_receipt_ids": [
            "SYNTHETIC_TEST_ONLY_schedule",
            "SYNTHETIC_TEST_ONLY_roster",
            "SYNTHETIC_TEST_ONLY_history"
        ],
        "feature_sha256": sha256(features),
        "reconstruction_class": "reconstructed",
        "features": features
    }
    validate_record("PregameFeatureSnapshot",feature_record)
    return {
        "schema": SCHEMA, "fixture_name": name,
        "source_admission": "TEST_ONLY_NOT_CERTIFIABLE",
        "p0_feature": feature_record,
        "has_authentic_market": False,
        "has_signed_original_sources": False,
        "model_predictions_present": False,
        "expected_source_gate_flags": missing
    }


def all_cases():
    return {x: make_case(x) for x in CASES}
