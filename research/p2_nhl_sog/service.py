"""P2 callable NHL SOG source-bundle service; P4/P5 need no HTTP.

Strict original-source receipts and P0 storage are prerequisites. Source
selection is deterministic and independent of any forecast or settlement.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path

from .source_pipeline import (
    SourceBlocked, require, attempt, build_bundle, parse_roster, retrieve_source,
    clock, current_storage
)
from .history_bridge import load_signed_manifest
from .quote_bridge import record_quote_candidate

MARKET_EXPERIMENTS = {
    "EXP-V25-NHL-SOG-EXPOSURE-EB-001",
    "EXP_NHL_SOG_P15_RATE_DISPERSION_NEXT_PROSPECTIVE",
    "EXP-V25-NHL-SOG-NB2-NATIVE-PLUGIN-MEAN-20261114"
}


def prepare_source_bundle(root, *, game, schedule_source, roster_sources,
                          signed_history_manifest_path,
                          signed_history_manifest_sha256,
                          history_pool, player_id, freeze, experiment_id=None,
                          peer_player_ids=(), market_capture=None,
                          original_provider_offer=None):
    """Return P0 feature SHA and source-only manifest, or durable abstention.

    market_capture must originate from the same immutable shared provider
    response, never from a sampled synthetic quote or later closing odds.
    """
    current_storage(root)
    player_id = str(player_id)
    try:
        require(clock(freeze) < clock(game["start_at"]),
                "SOURCE_BUNDLE_EVENT_FREEZE_INVALID")
        members = {
            team: parse_roster(retrieve_source(root, receipt, freeze=freeze,
                             event_start=game["start_at"]), team)
            for team, receipt in roster_sources.items()
        }
        require(set(members) == {game["away_team"], game["home_team"]},
                "P2_BUNDLE_TWO_TEAM_ROSTER_MISSING")
        team = next((team for team, roster in members.items()
                     if player_id in roster), None)
        require(team is not None, "P2_CURRENT_ROSTER_PLAYER_NOT_FOUND")
        group = members[team][player_id]["position_group"]
        require(group in ("F","D"), "P2_UNSUPPORTED_SOG_GOALIE")
        other = game["away_team"] if team == game["home_team"] else game["home_team"]
        require(player_id not in members[other], "P2_DUPLICATE_OPPONENT_ROSTER")
        all_entries = load_signed_manifest(root, signed_history_manifest_path,
                                           signed_history_manifest_sha256)
        own = all_entries.get(player_id)
        require(isinstance(own,list) and bool(own),
                "P2_ORIGINAL_SIGNED_PLAYER_HISTORY_MISSING")
        peers = {}
        require(len(set(str(x) for x in peer_player_ids)) == len(peer_player_ids),
                "P2_DUPLICATE_PEER_SOURCE_ID")
        for pid in sorted(str(x) for x in peer_player_ids):
            require(pid != player_id and isinstance(all_entries.get(pid),list),
                    "P2_PEER_SOURCE_IDENTITY_UNAVAILABLE")
            peers[pid] = all_entries[pid]
        evidence, quote = None, None
        if market_capture is not None or original_provider_offer is not None:
            require(market_capture is not None and
                    original_provider_offer is not None,
                    "P2_INCOMPLETE_ORIGINAL_MARKET_PAIR")
            market_attempt = record_quote_candidate(
                root, raw_ref=market_capture, offered=original_provider_offer,
                player_id=player_id, team=team, opponent=other,
                event_id=game["event_id"], start=game["start_at"],
                freeze=freeze, official_profile_entry=own[0],
                history_pool=history_pool)
            if market_attempt["status"] == "VERIFIED":
                evidence = market_attempt["quote"]
                quote = evidence["verified_quote"]
            else:
                # Preserve underlying rejection independently of model input.
                reason = market_attempt["attempt"]["reasons"]
                return {"status": "ABSTAIN_QUOTE_REJECTED",
                        "reasons": reason, "quote_attempt": market_attempt}
        result = build_bundle(
            root, game=game, schedule_source=schedule_source,
            rosters=roster_sources, roster_members=members, player_id=player_id,
            history_entries=own, peer_entries=peers, freeze=freeze,
            quote=quote, quote_evidence=evidence,
            required_experiment=experiment_id, history_pool=history_pool)
        # Final model-specific history minima and admission belong to the
        # REGISTERED experiment, never inferred from generic source readiness.
        state = result["manifest"]["source_admission"]
        item = attempt(root, "original_player_source_bundle",
                       "VERIFIED_SOURCE_ONLY" if state.startswith("SOURCE_READY")
                       else "ABSTAIN",
                       [] if state.startswith("SOURCE_READY") else [state],
                       event_id=game["event_id"], player_id=player_id,
                       manifest_sha256=result["receipt"]["sha256"],
                       experiment_id=experiment_id)
        return {"status": state, "source_bundle": result,
                "attempt": item, "P4_model_artifact_present": False,
                "P5_settled_result_present": False}
    except Exception as exc:
        abstention = attempt(root, "original_player_source_bundle", "ABSTAIN",
                    [type(exc).__name__ + ":" + str(exc)[:180]],
                    event_id=game.get("event_id"), player_id=player_id,
                    experiment_id=experiment_id)
        return {"status": "ABSTAIN_SOURCE_INVALID",
                "reasons": abstention["reasons"], "attempt": abstention}


def prepare_source_batch(root, *, game, schedule_source, roster_sources,
                         signed_history_manifest_path,
                         signed_history_manifest_sha256, history_pool,
                         player_ids, freeze, experiment_id=None,
                         peer_ids_by_player=None, original_quote_by_player=None):
    """Complete denominators; callers cannot drop failed candidate rows."""
    records = []
    seen = set()
    for player_id in player_ids:
        pid = str(player_id)
        if pid in seen:
            x = attempt(root, "batch_source_player", "ABSTAIN",
                ["DUPLICATE_PLAYER_EVENT_CANDIDATE"], player_id=pid,
                event_id=game["event_id"])
            records.append({"status": "ABSTAIN_DUPLICATE_PLAYER",
                            "player_id": pid, "attempt": x})
            continue
        seen.add(pid)
        market = (original_quote_by_player or {}).get(pid)
        out = prepare_source_bundle(
            root, game=game, schedule_source=schedule_source,
            roster_sources=roster_sources,
            signed_history_manifest_path=signed_history_manifest_path,
            signed_history_manifest_sha256=signed_history_manifest_sha256,
            history_pool=history_pool, player_id=pid, freeze=freeze,
            experiment_id=experiment_id,
            peer_player_ids=(peer_ids_by_player or {}).get(pid, ()),
            market_capture=market["source"] if market else None,
            original_provider_offer=market["offer"] if market else None)
        records.append({"player_id": pid, **out})
    counts = Counter(item["status"] for item in records)
    return {"schema": "PA-P2-NHL-SOG-SOURCE-BATCH/1",
            "official_nhl_game_id": game["event_id"],
            "input_freeze_at": freeze, "candidate_total": len(records),
            "unique_candidate_players": len(seen),
            "status_counts": dict(sorted(counts.items())),
            "P4_forecast_count": 0, "P5_settlement_count": 0,
            "research_only": True, "records": records}
