"""Freeze canonical NHL SOG research forecasts from the P2 source owner."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import json
import re

from research.p2_nhl_sog.history_bridge import checked_pool, load_signed_manifest
from research.p2_nhl_sog.source_pipeline import (
    OFFICIAL, attempt, parse_roster, put_once, retrieve_source, scheduled_games, stamp, verify_bundle,
)
from v2.nhl_sog_exposure_shadow import SCHEMA as MODEL_VERSION, fit_model, verify_observation
from v2.nhl_sog_official_history_producer import independent_verify_observation_lineage
from v2.nhl_sog_p4_forecasts import P4Blocked, _mass_for, full_law
from v2.p0_integrity.contracts import admit_forecast, canonical_bytes, record, sha256, utc
from v2.p0_integrity.storage import NAMESPACES, append_immutable, verify_immutable_record


MODELS = ("plugin_poisson", "full_gamma_poisson_exposure")
NAMESPACE = "research/p4_nhl_sog_slate"


def _check(condition, reason):
    if not condition:
        raise P4Blocked(reason)


class HistorySources:
    """Open one byte-pinned history manifest and reuse verified peer observations."""

    def __init__(self, root, path, manifest_sha256, pool):
        self.root = Path(root).resolve()
        self.pool = checked_pool(root, pool)
        self.path = path
        self.sha256 = manifest_sha256
        self.entries = {}
        self.verified = {}
        for player_id, observations in load_signed_manifest(root, path, manifest_sha256).items():
            for entry in observations:
                key = entry["observation_receipt"]["content_sha256"]
                _check(key not in self.entries, "DUPLICATE_SIGNED_HISTORY_OBSERVATION")
                self.entries[key] = (player_id, entry)

    def observation(self, row, *, freeze, start, sources):
        key = row["observation_receipt_sha256"]
        _check(key in self.entries, "P2_SIGNED_HISTORY_OBSERVATION_MISSING")
        player_id, entry = self.entries[key]
        raw_receipts = {
            "profile": entry["raw_profile_receipt"],
            "game_log": entry["raw_log_receipt"],
            "final": entry["raw_final_receipt"],
        }
        _check(row["signed_original_source_proofs"] == {
            kind: source["collector_proof_sha256"] for kind, source in raw_receipts.items()
        }, "P2_SIGNED_HISTORY_PROOF_MISMATCH")
        source_ids = row["original_source_receipt_ids"]
        _check(len(source_ids) == len(raw_receipts), "P2_HISTORICAL_SOURCE_CLOSURE_MISMATCH")
        for source_id, (kind, source) in zip(source_ids, raw_receipts.items()):
            bound = sources[source_id]
            relative_path = (self.pool / source["archive_path"]).relative_to(self.root)
            _check(bound["source_kind"] == "nhl_historical_" + kind and
                   bound["source_sha256"] == source["body_sha256"] and
                   bound["archive_path"] == str(relative_path) and
                   utc(bound["collected_at"]) == utc(source["received_at"]),
                   "P2_SIGNED_HISTORY_SOURCE_MISMATCH")
        cached = self.verified.get(key)
        if cached is None:
            receipt = independent_verify_observation_lineage(
                entry, archive_root=self.pool, freeze=freeze, event_start=start)
            observation = verify_observation(receipt, self.pool, freeze)
            self.verified[key] = (receipt, observation)
        else:
            receipt, observation = cached
        _check((observation["player_id"], observation["event_id"], observation["shots_on_goal"],
                observation["toi_minutes"], observation["source_game_log_row"]["gameDate"]) ==
               (player_id, row["game_id"], row["shots_on_goal"], row["toi_minutes"], row["game_date"]),
               "P2_SIGNED_HISTORY_DERIVED_OBSERVATION_DRIFT")
        # When reusing an observation for another event, check every original
        # clock against that event's freeze as well as the derived receipt.
        _check(all(utc(source["received_at"]) <= utc(freeze)
                   for source in (*raw_receipts.values(), receipt)),
               "HISTORICAL_SOURCE_AFTER_FREEZE")
        return player_id, receipt


def _official_identity(root, manifest, feature, sources):
    game = feature["features"]["official_game"]
    player = feature["features"]["player"]
    event, start = manifest["event_id"], manifest["event_start_at"]
    team, opponent, player_id = (feature[k] for k in ("team_id", "opponent_id", "player_id"))
    _check((feature["reconstruction_class"], feature["sport"], feature["stat_key"],
            feature["period"], feature["event_id"], feature["input_freeze_at"]) ==
           ("original", "NHL", "shots on goal", "full", event, manifest["input_freeze_at"])
           and (game["event_id"], game["start_at"], player["official_nhl_player_id"],
                player["team_id"], player["opponent_id"]) ==
           (event, start, manifest["official_nhl_player_id"], team, opponent)
           and player_id == manifest["official_nhl_player_id"]
           and {game["home_team"], game["away_team"]} == {team, opponent},
           "P2_OFFICIAL_GAME_OR_PLAYER_IDENTITY_MISMATCH")
    schedule_hash = manifest["official_schedule_source_sha256"]
    schedule = sources[schedule_hash]
    _check(schedule["source_id"] == "nhl:schedule:" + game["scheduled_day"],
           "P2_SCHEDULE_SOURCE_ID_MISMATCH")
    schedule_doc = _current_source(root, schedule_hash, schedule,
                                   manifest.get("official_schedule_c03_receipt"),
                                   OFFICIAL + "/score/" + game["scheduled_day"], manifest)
    matching = [signed for signed in scheduled_games(schedule_doc, day=game["scheduled_day"])
                if signed["event_id"] == event]
    _check(len(matching) == 1 and all(matching[0][key] == game[key] for key in (
        "home_team", "away_team", "start_at", "official_season", "game_type")),
           "P2_OFFICIAL_SCHEDULE_GAME_MISMATCH")
    rosters = manifest["official_roster_source_sha256"]
    roster_proofs = manifest.get("official_roster_c03_receipts", {})
    _check(set(rosters) == {team, opponent}, "P2_BUNDLE_TWO_TEAM_ROSTER_MISSING")
    for code in (team, opponent):
        roster_hash = rosters[code]
        roster = sources[roster_hash]
        _check(roster["source_id"] == "nhl:roster:" + code, "P2_ROSTER_SOURCE_ID_MISMATCH")
        roster_doc = _current_source(root, roster_hash, roster, roster_proofs.get(code),
                                     OFFICIAL + "/roster/" + code + "/current", manifest)
        members = parse_roster(roster_doc, code)
        if code == team:
            group = player["position_group"]
            _check(group in {"F", "D"} and player_id in members and
                   members[player_id]["position_group"] == group, "P2_ROSTER_SOG_SKATER_UNVERIFIED")
        else:
            _check(player_id not in members, "P2_OPPONENT_ROSTER_IDENTITY_CONFLICT")
    return game, player["position_group"]


def _current_source(root, record_sha256, source, proof, expected_url, manifest):
    _check(isinstance(proof, dict) and proof.get("source_url") == expected_url and
           proof.get("source_id") == source["source_id"] and
           utc(proof["received_at"]) == utc(source["collected_at"]),
           "P2_CURRENT_C03_SOURCE_PROOF_MISSING_OR_MISMATCHED")
    return retrieve_source(root, {"p0_sha256": record_sha256, "p0_receipt": source,
                                   "c03_receipt": proof}, freeze=manifest["input_freeze_at"],
                           event_start=manifest["event_start_at"])


def _distributions(model):
    laws = {kind: full_law(model, kind) for kind in MODELS}
    gamma = laws["full_gamma_poisson_exposure"]
    masses = gamma["pmf_from_zero"]
    # Preserve exact point masses through the registered line support, even if
    # P4's numerical tail tolerance is reached much earlier for this skater.
    masses = masses + [_mass_for(model, count, "full_gamma_poisson_exposure")
                       for count in range(len(masses), 81)]
    return {
        "plugin_poisson": {
            "kind": "poisson", "parameters": {"rate": laws["plugin_poisson"]["mean"]},
        },
        "full_gamma_poisson_exposure": {
            "kind": "scenario_pmf",
            "masses": [[count, mass] for count, mass in enumerate(masses)],
            "upper_tail_mass_bound": gamma["tail_mass_upper_bound"],
            "analytic_parameters": gamma["parameters"],
        },
    }, laws


def _existing_record(root, kind, logical_id):
    """Reuse only complete records independently verified by the P0 reader."""
    key = hashlib.sha256((kind + "\x00" + logical_id).encode()).hexdigest()
    directory = Path(root) / "research/p0_integrity_store" / NAMESPACES[kind]
    claim_path = directory / "_ids" / (key + ".json")
    try:
        claim = json.loads(claim_path.read_bytes())
    except FileNotFoundError:
        return None
    digest = claim["record_sha256"]
    existing = verify_immutable_record(root, kind, digest)
    id_field = "model_artifact_id" if kind == "ModelArtifact" else "forecast_id"
    _check(existing[id_field] == logical_id, "P4_IMMUTABLE_LOGICAL_ID_MISMATCH")
    return existing, digest, str((directory / (digest + ".json")).relative_to(root))


def forecast_bundle(root, manifest_sha256, *, code_commit, run_id,
                    signed_history_manifest_path=None, signed_history_manifest_sha256=None,
                    history_pool=None, history_sources=None):
    """Read one complete P2 bundle, then emit the two line-independent P0 forecasts.

    The original quote-matched Gamma generator and registered native NB2
    own their separate forecast class and retain their original admission.
    """
    event = player_id = None
    written = []
    try:
        manifest, feature = verify_bundle(root, manifest_sha256)
        event, player_id = manifest["event_id"], manifest["official_nhl_player_id"]
        start, freeze = manifest["event_start_at"], manifest["input_freeze_at"]
        _check(manifest["source_admission"] == "SOURCE_READY_LINE_INDEPENDENT_ONLY" and
               manifest["quote_id"] is None and manifest["P0_quote_record_sha256"] is None,
               "P2_UNQUOTED_DISTRIBUTION_BUNDLE_REQUIRED")
        _check(re.fullmatch(r"[a-f0-9]{40}", code_commit) is not None,
               "CODE_COMMIT_UNPINNED")
        _check(utc(start) > datetime.now(timezone.utc), "PREGAME_FORECAST_WINDOW_CLOSED")
        history = feature["features"]["history"]
        _check(not feature["features"]["missingness"]["role_transition_uncertain"],
               "ROLE_TRANSITION_UNSUPPORTED")
        source_hashes = [manifest["official_schedule_source_sha256"],
                         *manifest["official_roster_source_sha256"].values(),
                         *manifest["P0_original_historical_source_record_hashes"]]
        sources_by_hash = {digest: verify_immutable_record(root, "SourceReceipt", digest)
                            for digest in source_hashes}
        game, position = _official_identity(root, manifest, feature, sources_by_hash)
        sources = {source["receipt_id"]: source for source in sources_by_hash.values()}
        own, peers = history["own"], history["peers"]
        _check([row["observation_receipt_sha256"] for row in own + peers] ==
               manifest["signed_historical_observation_hashes"], "P2_HISTORY_OBSERVATION_HASHES_DRIFT")
        _check(len(own) == manifest["own_history_count"] and len(peers) == manifest["peer_history_count"],
               "P2_HISTORY_OBSERVATION_COUNTS_DRIFT")
        if history_sources is None:
            history_sources = HistorySources(root, signed_history_manifest_path,
                                             signed_history_manifest_sha256, history_pool)
        _check(history_sources.root == Path(root).resolve(), "P2_HISTORY_SOURCE_ROOT_MISMATCH")
        own_receipts, peer_receipts = [], []
        for for_target, rows, receipts in ((True, own, own_receipts), (False, peers, peer_receipts)):
            for row in rows:
                observed_player, receipt = history_sources.observation(
                    row, freeze=freeze, start=start, sources=sources)
                _check((observed_player == player_id) is for_target and row["game_id"] != event,
                       "P2_HISTORICAL_PLAYER_OR_GAME_MISMATCH")
                receipts.append(receipt)
        model = fit_model(own_receipts, peer_receipts, archive_root=history_sources.pool,
                          player_id=player_id, position_group=position, input_freeze_at=freeze,
                          event_start_at=start, target_event_id=event, current_team_id=feature["team_id"])
        distributions, laws = _distributions(model)
        model = {**model, "p2_bundle_sha256": manifest_sha256,
                 "p2_original_history_verified": True,
                 "p0_feature_sha256": manifest["p0_feature_record_sha256"],
                 "signed_history_manifest_sha256": history_sources.sha256,
                 "history_pool_relative_path": str(history_sources.pool.relative_to(Path(root).resolve()))}
        now = datetime.now(timezone.utc)
        _check(utc(freeze) <= now < utc(start), "SOURCE_OR_FORECAST_CHRONOLOGY_INVALID")
        artifact_sha = sha256(model)
        artifact_path = f"{NAMESPACE}/models/{artifact_sha}.json"
        put_once(root, artifact_path, canonical_bytes(model))
        season = game["official_season"]
        _check(type(season) is int and 19001901 <= season and season % 10000 == season // 10000 + 1,
               "P2_OFFICIAL_SEASON_UNVERIFIED")
        for kind in MODELS:
            _check(datetime.now(timezone.utc) < utc(start), "PREGAME_FORECAST_WINDOW_CLOSED")
            identifier = sha256([code_commit, run_id, manifest_sha256, kind])
            model_artifact_id = "p4s:model:" + identifier
            forecast_id = "p4s:forecast:" + identifier
            previous_model = _existing_record(root, "ModelArtifact", model_artifact_id)
            previous_forecast = _existing_record(root, "ForecastSnapshot", forecast_id)
            created_at = previous_model[0]["created_at"] if previous_model else stamp(datetime.now(timezone.utc))
            model_ref = record(
                "ModelArtifact", model_artifact_id=model_artifact_id,
                model_id=kind, model_version=MODEL_VERSION, model_code_sha=code_commit,
                artifact_sha256=artifact_sha, artifact_path=artifact_path,
                training_data_sha256=sha256(model["source_manifest"]),
                training_cutoff_at=model["fit_data_cutoff_at"], created_at=created_at,
                training_scope="p2_signed_prior_sog_toi_distribution_only",
                feature_schema_id=feature["schema_version"],
            )
            if previous_model:
                _check(previous_model[0] == model_ref, "P4_MODEL_RETRY_CONTENT_MISMATCH")
            else:
                append_immutable(root, "ModelArtifact", model_ref)
            forecast_at = previous_forecast[0]["forecast_at"] if previous_forecast else stamp(datetime.now(timezone.utc))
            distribution = distributions[kind]
            snapshot = record(
                "ForecastSnapshot", forecast_id=forecast_id, run_id=run_id,
                sport="NHL", league="NHL", season=season // 10000, event_id=event,
                team_id=feature["team_id"], opponent_id=feature["opponent_id"], player_id=player_id,
                stat_key=feature["stat_key"], period=feature["period"], event_start_at=start,
                forecast_at=forecast_at, input_freeze_at=freeze,
                model_training_cutoff_at=model["fit_data_cutoff_at"],
                feature_snapshot_id=feature["feature_snapshot_id"],
                model_artifact_id=model_ref["model_artifact_id"], model_id=kind,
                model_version=MODEL_VERSION, source_receipt_ids=feature["source_receipt_ids"],
                input_sha256=sha256(feature), output_sha256=sha256(distribution),
                model_code_sha=code_commit, artifact_sha256=artifact_sha, seed=0,
                distribution=distribution,
                uncertainty={"participation_condition": "conditional_on_played",
                             "dnp_probability": None, "p2_bundle_sha256": manifest_sha256,
                             "mean": laws[kind]["mean"], "variance": laws[kind]["variance"],
                             "quantiles": laws[kind]["quantiles"]},
                abstention_reasons=[], admission_class="A", eligible=True,
                quote_id=None, line=None, side=None, market_probability=None,
            )
            admitted = admit_forecast(snapshot, feature, model_ref, list(sources.values()),
                                       source_root=root)
            if previous_forecast:
                _check(previous_forecast[0] == snapshot, "P4_FORECAST_RETRY_CONTENT_MISMATCH")
                _, digest, path = previous_forecast
            else:
                _check(datetime.now(timezone.utc) < utc(start), "PREGAME_FORECAST_WINDOW_CLOSED")
                saved = append_immutable(root, "ForecastSnapshot", snapshot)
                digest, path = saved["sha256"], saved["relative_path"]
            _check(digest == admitted["snapshot_sha256"], "FORECAST_WRITE_SHA_MISMATCH")
            written.append({"kind": kind, "forecast_id": forecast_id,
                            "sha256": digest, "path": path,
                            "forecast_at": forecast_at, "mean": laws[kind]["mean"]})
        return {"status": "FROZEN", "event_id": event, "player_id": player_id,
                "source_manifest_sha256": manifest_sha256, "model_artifact_sha256": artifact_sha,
                "forecasts": written, "research_only": True}
    except (ValueError, TypeError, KeyError, OSError) as exc:
        reason = type(exc).__name__ + ":" + str(exc)[:200]
        receipt = attempt(root, "p4_pregame_distribution", "ABSTAIN", [reason],
                          event_id=event, player_id=player_id, model_code_sha=code_commit,
                          source_manifest_sha256=manifest_sha256, committed_forecasts=written)
        return {"status": "PARTIAL" if written else "ABSTAIN", "reason": reason,
                "event_id": event, "player_id": player_id, "forecasts": written,
                "attempt_sha256": receipt["receipt"]["sha256"], "research_only": True}
