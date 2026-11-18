"""NHL SOG source-native NB2 research control, never a Phase1 replay.

This is a NEW preregistered research comparison against the frozen Gamma
experiment's *plugin-Poisson* mean, not the older P15 pooled-peer mean.
Original source bytes, C03 HMAC, official event/roster/played histories, and
the exact original two-sided PropLine quote must independently reverify.
No retroactive/backdated forecast, independent publisher timestamp assertion,
DNP mass, production rank, settlement update or automated Tier promotion.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from zoneinfo import ZoneInfo
import hashlib
import json
import math
import os
import re
import unicodedata

from .contracts import MarketQuote
from .phase15_nb2_shadow import nb2_sog_probabilities
from .nhl_sog_exposure_shadow import forecast_lines, stable_hash
from .nhl_sog_quote_binding import verify_structured_original_sog_offer
from .nhl_sog_official_history_producer import independent_verify_observation_lineage
from scripts.c03_live_transport import verify_signed_capture

EXPERIMENT = "EXP-V25-NHL-SOG-NB2-NATIVE-PLUGIN-MEAN-20261114"
SCHEMA = "v25_sog_nb2_source_native_plugin_mean_v1"
SHAPE = 4.0
EXPERIMENT_BASELINE = "frozen_original_plugin_poisson_not_p15_pooled_peer_rate"
MAX_SOURCE_AGE = timedelta(hours=6)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
UTC = timezone.utc


class NativeNB2Blocked(ValueError):
    """Source time, content, identity, denominator or release gate failed."""


def _check(ok: bool, reason: str) -> None:
    if not ok:
        raise NativeNB2Blocked(reason)


def _utc(x) -> datetime:
    if not isinstance(x, str):
        raise NativeNB2Blocked("TIME_MISSING")
    try:
        dt = datetime.fromisoformat(x.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NativeNB2Blocked("TIME_INVALID") from exc
    _check(dt.tzinfo is not None and dt.utcoffset() is not None, "TIME_NOT_UTC_AWARE")
    return dt.astimezone(UTC)


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _within(root: Path, name: str) -> Path:
    _check(isinstance(name, str) and bool(name) and "\x00" not in name, "PATH_MISSING")
    p = Path(name)
    _check(".." not in p.parts and "\\" not in name, "UNSAFE_PATH")
    resolved = (p if p.is_absolute() else root / p).resolve()
    _check(resolved.is_relative_to(root.resolve()), "PATH_OUTSIDE_PROJECT")
    return resolved


def _read(root: Path, path: str, sha: str | None = None):
    p = _within(root, path)
    _check(p.is_file(), "ORIGINAL_ARTIFACT_MISSING")
    raw = p.read_bytes()
    if sha is not None:
        _check(isinstance(sha, str) and HEX64.fullmatch(sha) is not None
               and _sha(raw) == sha, "FROZEN_ARTIFACT_SHA_MISMATCH")
    try:
        return json.loads(raw), raw
    except (ValueError, UnicodeDecodeError) as exc:
        raise NativeNB2Blocked("FROZEN_ARTIFACT_JSON_INVALID") from exc


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in s
                            if not unicodedata.combining(c)).split())


def _proof(root: Path, pool: Path, digest: str, *, freeze: str, event: str):
    _check(isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
           "SIGNED_PROOF_SHA_MISSING")
    rel = "c03_collector_receipts/" + digest + ".json"
    data, raw = _read(pool, rel, digest)
    fields = data.get("receipt_fields")
    _check(isinstance(fields, dict), "SIGNED_PROOF_FIELDS_MISSING")
    receipt = dict(fields, transport_attestation="collector_signed_tls_bytes_v1",
                   collector_proof_archive_path=rel, collector_proof_sha256=digest)
    try:
        verified = verify_signed_capture(receipt, archive_root=pool,
                                         freeze=freeze, event_start=event)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        raise NativeNB2Blocked("SIGNED_PROOF_REJECTED:" + type(exc).__name__) from exc
    return receipt, verified


def _official_identity(root: Path, pool: Path, input_doc: dict, quote: MarketQuote,
                       snapshot: dict, now: datetime):
    chosen = input_doc["chosen_offer_identity"]
    _check(str(chosen.get("official_nhl_player_id")) == quote.player_id
           and chosen.get("provider_event_id") == quote.event_id
           and chosen.get("official_team") == quote.team_id
           and chosen.get("opponent_team") == quote.opponent_id
           and chosen.get("book") == quote.book
           and float(chosen.get("line")) == quote.line,
           "NATIVE_PROVIDER_PLAYER_EVENT_BOOK_CROSSWALK_MISMATCH")
    freeze = snapshot["input_freeze_at"]
    event = quote.event_start_at
    score, score_doc = _proof(root, pool, input_doc["new_signed_score_proof_sha256"],
                              freeze=freeze, event=event)
    source_day = _utc(input_doc["created_at"]).astimezone(
        ZoneInfo("America/Toronto")).date().isoformat()
    from .nhl_sog_pregame_schedule import official_games
    games = official_games(score["source_url"], score_doc, source_day)
    match = [g for g in games if str(g.get("id")) == str(chosen.get("nhl_official_event_id"))]
    _check(len(match) == 1, "OFFICIAL_EVENT_NOT_UNIQUE")
    g = match[0]
    _check(g.get("gameState") in ("FUT", "PRE")
           and (g.get("homeTeam") or {}).get("abbrev") in (quote.team_id, quote.opponent_id)
           and (g.get("awayTeam") or {}).get("abbrev") in (quote.team_id, quote.opponent_id)
           and (g.get("homeTeam") or {}).get("abbrev") != (g.get("awayTeam") or {}).get("abbrev")
           and _utc(g["startTimeUTC"]) == _utc(event),
           "SIGNED_OFFICIAL_EVENT_TEAM_START_MISMATCH")
    rosters = input_doc.get("new_signed_roster_proof_sha256") or {}
    _check(set((quote.team_id, quote.opponent_id)) <= set(rosters),
           "TWO_TEAM_SIGNED_ROSTER_MISSING")
    role = None
    for team in (quote.team_id, quote.opponent_id):
        rr, doc = _proof(root, pool, rosters[team], freeze=freeze, event=event)
        _check(rr["source_url"] == "https://api-web.nhle.com/v1/roster/" +
               team + "/current", "SIGNED_ROSTER_ENDPOINT_MISMATCH")
        received = _utc(rr["received_at"])
        _check(received <= now and now - received <= MAX_SOURCE_AGE,
               "ROSTER_SOURCE_TOO_OLD_FOR_NATIVE_NB2")
        forward = [x for x in doc.get("forwards", []) if str(x.get("id")) == quote.player_id]
        defense = [x for x in doc.get("defensemen", []) if str(x.get("id")) == quote.player_id]
        _check(not (forward and defense), "NHL_ROSTER_POSITION_CONFLICT")
        if team == quote.team_id:
            _check(len(forward) + len(defense) == 1, "CURRENT_PLAYER_TEAM_NOT_CONFIRMED")
            role = "F" if forward else "D"
        else:
            _check(not (forward or defense), "PLAYER_APPEARS_ON_OPPONENT_ROSTER")
    return role


def _verify_historical(pool: Path, model: dict, input_doc: dict,
                       quote: MarketQuote, snapshot: dict):
    path = pool.parent / "pr121_signed_historical_observation_contracts_parallel_v1.json"
    _check(path.is_file(), "SIGNED_HISTORICAL_MANIFEST_ABSENT")
    doc = json.loads(path.read_bytes())
    all_history = doc.get("signed_observation_contracts_by_player")
    _check(isinstance(all_history, dict), "SIGNED_HISTORICAL_CONTRACTS_INVALID")
    index = {}
    for pid, entries in all_history.items():
        for entry in entries:
            sha = (entry.get("observation_receipt") or {}).get("content_sha256")
            _check(isinstance(sha, str) and HEX64.fullmatch(sha) is not None,
                   "SIGNED_HISTORICAL_SHA_INVALID")
            _check(sha not in index, "DUPLICATE_SIGNED_HISTORICAL_DIGEST")
            index[sha] = entry
    model_sources = model.get("source_manifest")
    _check(isinstance(model_sources, list) and
           len(model_sources) == model["own_played_games"] + model["peer_games"],
           "HISTORICAL_MODEL_DENOMINATOR_MISMATCH")
    original_profile = None
    for item in model_sources:
        digest = item["content_sha256"]
        _check(digest in index, "MODEL_SOURCE_NOT_IN_SIGNED_HISTORY")
        entry = index[digest]
        try:
            receipt = independent_verify_observation_lineage(
                entry, archive_root=pool, freeze=snapshot["input_freeze_at"],
                event_start=quote.event_start_at)
        except (ValueError, TypeError, OSError, KeyError) as exc:
            raise NativeNB2Blocked("SIGNED_HISTORICAL_REVERIFY_FAILED:" +
                                   type(exc).__name__) from exc
        _check(receipt["content_sha256"] == digest and
               receipt["archive_path"] == item["archive_path"] and
               str(entry["observation_receipt"]["archive_path"]) == item["archive_path"],
               "HISTORICAL_MODEL_RECEIPT_DRIFT")
        if item["player_id"] == quote.player_id and original_profile is None:
            original_profile = entry["raw_profile_receipt"]
    _check(original_profile is not None, "TARGET_PROFILE_SIGNED_HISTORY_MISSING")
    _check(original_profile["collector_proof_sha256"] ==
           input_doc["source_profile_proof_sha256"],
           "PLAYER_PROFILE_PROOF_MISMATCH")
    proof, profile = _proof(pool, pool, original_profile["collector_proof_sha256"],
                          freeze=snapshot["input_freeze_at"], event=quote.event_start_at)
    first = profile.get("firstName"); last = profile.get("lastName")
    if isinstance(first, dict): first = first.get("default")
    if isinstance(last, dict): last = last.get("default")
    _check(str(profile.get("playerId")) == quote.player_id and
           isinstance(first, str) and isinstance(last, str),
           "SIGNED_PLAYER_PROFILE_ID_OR_NAME_UNAVAILABLE")
    full = first.strip() + " " + last.strip()
    _check(_norm(full) == _norm(input_doc["chosen_offer_identity"]["provider_player_name"]),
           "SOURCE_PLAYER_NAME_MISMATCH")
    return full


def _original_raw_market(root: Path, manifest: dict, input_doc: dict, quote: MarketQuote):
    packet = manifest["original_quote"]
    _check(packet["raw_body_sha256"] == input_doc["original_provider_http_body_sha256"]
           and packet["structured_rows_sha256"] == input_doc["original_structured_rows_sha256"]
           and _utc(packet["received_at_utc"]) == _utc(quote.quote_at),
           "ORIGINAL_PROVIDER_SOURCE_RECEIPT_MISMATCH")
    rawpath = _within(root, packet["original_raw_file"])
    _check(rawpath.is_file(), "ORIGINAL_PROVIDER_HTTP_BYTES_MISSING")
    raw = rawpath.read_bytes()
    _check(_sha(raw) == packet["raw_body_sha256"]
           and len(raw) == packet["raw_body_bytes"],
           "ORIGINAL_PROVIDER_HTTP_SHA_MISMATCH")
    provider = json.loads(raw)
    events = provider if isinstance(provider, list) else provider.get(
        "events", provider.get("data", []))
    _check(isinstance(events, list), "ORIGINAL_PROVIDER_EVENTS_MISSING")
    event = [x for x in events if str(x.get("id")) == quote.event_id]
    _check(len(event) == 1, "ORIGINAL_PROVIDER_EVENT_NOT_UNIQUE")
    e = event[0]
    player_key = input_doc["source_bound_original_native_nhl_player_id"]
    sides = {"over": 0, "under": 0}
    candidate = input_doc["chosen_offer_identity"]
    for book in e.get("bookmakers", []):
        if str(book.get("key")) != quote.book: continue
        for market in book.get("markets", []):
            if market.get("key") != "player_shots_on_goal": continue
            for x in market.get("outcomes", []):
                side = str(x.get("name") or "").lower()
                if side not in sides: continue
                if str(x.get("player_id") or "") != player_key: continue
                if _norm(x.get("description") or x.get("player")) != _norm(
                        candidate["provider_player_name"]): continue
                try:
                    point = x.get("point") if x.get("point") is not None else x.get("line")
                    price = x.get("price") if x.get("price") is not None else x.get(side + "_odds")
                    if float(point) != quote.line or float(price) != float(candidate[side + "_odds"]):
                        continue
                except (TypeError, ValueError): continue
                sides[side] += 1
    _check(sides == {"over": 1, "under": 1}, "ORIGINAL_TWO_SIDED_HTTP_OFFER_NOT_UNIQUE")


def verify_native_source(root: Path, manifest: dict, manifest_path: Path,
                         attempt_record: dict, *, now: datetime):
    _check(now.tzinfo is not None, "NAIVE_RUNTIME_CLOCK")
    a_path = attempt_record["receipt_path"]
    wrapper, _ = _read(root, a_path, attempt_record["receipt_sha256"])
    _check(wrapper["status"] == "SHADOW_FORECAST"
           and wrapper["research_shadow_only"] is True
           and wrapper["production_unchanged"] is True
           and wrapper["tier_allowed"] is False, "ORIGINAL_FORECAST_NOT_ELIGIBLE")
    original, original_raw = _read(root, str(Path(a_path).parent /
                                             "original_quote_and_source_identity_receipt.json"))
    _check(_sha(original_raw) == wrapper["run_input_receipt_sha256"] and
           original["schema"] == "v25_sog_first_real_quote_attempt_input_lineage_v1" and
           original.get("production_selection_allowed") is False and
           original.get("source_retrosigned") is False, "ORIGINAL_INPUT_LINEAGE_INVALID")
    quote = MarketQuote(**original["quote"])
    _check(quote.accepted and quote.quote_kind == "real" and
           quote.product_type == "sportsbook_two_sided" and
           quote.stat_key == "shots on goal" and quote.period == "full" and
           quote.sport == "NHL", "ORIGINAL_REAL_SOG_OFFER_NOT_CONFIRMED")
    _check(_utc(quote.quote_at) <= _utc(original["created_at"]) and
           _utc(original["created_at"]) <= now < _utc(quote.event_start_at) -
           timedelta(minutes=3), "ORIGINAL_OFFER_NOT_FUTURE_AT_NATIVE_CAPTURE")
    _check(_utc(wrapper["attempt_finished_utc"]) < now and
           _utc(wrapper["attempt_finished_utc"]) < _utc(quote.event_start_at),
           "FROZEN_SOURCE_NOT_COMPLETED_PRE_EVENT")
    _check(original["code_commit"] == manifest["code_pin_PR121"] and
           manifest["signer_pin_PR122"] and
           original["source_pool"] == manifest["source_pool"],
           "ORIGINAL_MODEL_OR_SIGNER_PIN_DRIFT")
    model, model_raw = _read(root, wrapper["model_reference"]["path"],
                              wrapper["model_reference"]["sha256"])
    shot, shot_raw = _read(root, wrapper["snapshot_reference"]["path"],
                            wrapper["snapshot_reference"]["sha256"])
    snap = shot["snapshot"]
    _check(shot["status"] == "RESEARCH_SHADOW_ONLY" and
           shot["model_promotion_allowed"] is False and
           shot["tier_publication_allowed"] is False and
           shot["full_distribution_sha256"] == stable_hash(model) and
           snap["model_artifact_sha256"] == stable_hash(model) and
           snap["code_commit"] == original["code_commit"],
           "FROZEN_MODEL_SNAPSHOT_OR_CODE_MISMATCH")
    _check(model["schema"] == "v25_nhl_sog_exposure_gamma_poisson_v1" and
           model["verified_original_source_lineage"] is True and
           model["promotion_allowed"] is False and
           model["tier_publication_allowed"] is False and
           snap["event_id"] == quote.event_id and
           snap["player_id"] == quote.player_id and
           snap["quote_id"] == quote.quote_id and
           snap["quote_receipt_sha256"] == quote.quote_receipt_sha256 and
           snap["line"] == quote.line and
           _utc(model["input_freeze_at"]) == _utc(snap["input_freeze_at"]) and
           _utc(model["input_freeze_at"]) <= _utc(snap["forecast_at"]) and
           _utc(snap["forecast_at"]) <= _utc(wrapper["attempt_finished_utc"]) and
           _utc(model["fit_data_cutoff_at"]) <= _utc(model["input_freeze_at"]) and
           _utc(model["event_start_at"]) == _utc(quote.event_start_at),
           "FROZEN_FORECAST_IDENTITY_OR_TEMPORAL_INVALID")
    pool = _within(root, original["source_pool"])
    _check(pool.is_dir(), "FROZEN_SIGNED_SOURCE_POOL_MISSING")
    source_manifest = pool.parent / "signed_original_source_manifest_v1.json"
    history_manifest = pool.parent / "pr121_signed_historical_observation_contracts_parallel_v1.json"
    _check(source_manifest.is_file() and history_manifest.is_file() and
           _sha(source_manifest.read_bytes()) == original["official_signed_manifest_sha256"] and
           _sha(source_manifest.read_bytes()) ==
           manifest["source_baseline_copy"]["legacy_signed_manifest_sha256"] and
           _sha(history_manifest.read_bytes()) ==
           manifest["source_baseline_copy"]["historical_signed_observation_manifest_sha256"],
           "FROZEN_SIGNED_HISTORY_MANIFEST_SOURCE_DRIFT")
    name = _verify_historical(pool, model, original, quote, snap)
    role = _official_identity(root, pool, original, quote, snap, now)
    _check(role == model["position_group"], "CURRENT_OFFICIAL_POSITION_GROUP_MISMATCH")
    _original_raw_market(root, manifest, original, quote)
    verify_structured_original_sog_offer(
        quote, source_root=pool, source_bound_player_name=name)
    plugin_mu = float(model["plugin_rate"]) * float(model["plugin_exposure"])
    _check(math.isfinite(plugin_mu) and plugin_mu >= 0.0,
           "FROZEN_PLUGIN_POISSON_MEAN_INVALID")
    original_baseline = forecast_lines(model, [quote.line], kind="plugin_poisson")[
        format(float(quote.line), "g")]
    baseline = wrapper["baseline_three_way"]
    _check(all(abs(float(baseline[k]) - float(original_baseline[k])) < 1e-10
               for k in ("over", "under", "push")),
           "FROZEN_POISSON_CONTROL_MISMATCH")
    return {
        "quote": quote, "model": model, "model_digest": wrapper["model_reference"]["sha256"],
        "snapshot_digest": wrapper["snapshot_reference"]["sha256"],
        "original_wrapper_digest": attempt_record["receipt_sha256"],
        "original_input_digest": wrapper["run_input_receipt_sha256"],
        "provider_http_body_digest": manifest["original_quote"]["raw_body_sha256"],
        "signed_historical_observation_count": len(model["source_manifest"]),
        "plugin_mu": plugin_mu, "poisson_control": original_baseline,
        "official_event_id": original["chosen_offer_identity"]["nhl_official_event_id"],
    }


def frozen_native_nb2(evidence: dict, *, now: datetime, code_sha: str) -> dict:
    _check(isinstance(code_sha, str) and re.fullmatch(r"[0-9a-f]{40}", code_sha) is not None,
           "NATIVE_MODEL_GIT_COMMIT_UNPINNED")
    quote = evidence["quote"]
    _check(now.astimezone(UTC) < _utc(quote.event_start_at) - timedelta(minutes=3),
           "NATIVE_CAPTURE_AFTER_GAME_CUTOFF")
    nb = nb2_sog_probabilities(evidence["plugin_mu"], quote.line, shape=SHAPE)
    return {
        "schema": SCHEMA, "experiment_id": EXPERIMENT,
        "baseline_contract": EXPERIMENT_BASELINE, "research_only": True,
        "original_p15_nb2_experiment_replayed": False,
        "source_model": "fixed_gamma_experiment_plugin_poisson_control_mean",
        "fixed_shape": SHAPE, "original_offer_book": quote.book,
        "event_id": quote.event_id, "official_nhl_event_id": evidence["official_event_id"],
        "player_id": quote.player_id, "team_id": quote.team_id,
        "opponent_id": quote.opponent_id, "quote_id": quote.quote_id,
        "contract_id": quote.contract_id, "line": quote.line,
        "quote_at": quote.quote_at, "event_start_at": quote.event_start_at,
        "native_generated_at": now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "code_commit": code_sha,
        "original_frozen_input_sha256": evidence["original_input_digest"],
        "original_frozen_snapshot_sha256": evidence["snapshot_digest"],
        "original_frozen_model_sha256": evidence["model_digest"],
        "original_frozen_attempt_sha256": evidence["original_wrapper_digest"],
        "original_provider_http_sha256": evidence["provider_http_body_digest"],
        "signed_observations_reverified": evidence["signed_historical_observation_count"],
        "same_mean_plugin_poisson": evidence["poisson_control"],
        "native_nb2": nb, "stat_key": "shots on goal",
        "conditioned_on_played": True, "dnp_risk_modeled": False,
        "lineup_participation_confirmed": False,
        "publisher_publication_time_authenticated": False,
        "tier_publication_allowed": False, "production_selection_allowed": False,
        "model_promotion_allowed": False,
        "research_not_confirmatory_evidence_until_prospective_governance": True,
    }


def _append_once(path: Path, obj: dict) -> str:
    content = _canonical(obj)
    sha = _sha(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as output:
            output.write(content)
    except FileExistsError:
        _check(path.read_bytes() == content, "APPEND_ONLY_RECORD_MUTATION")
    return sha


def run_day(root: Path, *, now: datetime, code_sha: str) -> dict:
    """Process earliest original same-day manifest; never select by model score."""
    root = Path(root).resolve()
    day = now.astimezone(ZoneInfo("America/Toronto")).date().isoformat()
    spec_path = Path(__file__).resolve().parents[1] / (
        "config/experiment_specs/EXP_V25_NHL_SOG_NB2_NATIVE_PLUGIN_MEAN_20261114.json")
    _check(spec_path.is_file(), "NATIVE_NB2_PREREGISTRATION_FILE_MISSING")
    spec = json.loads(spec_path.read_bytes())
    _check(spec.get("schema") == "v25_research_preregistered_native_nb2_control_v1"
           and spec.get("experiment_id") == EXPERIMENT
           and spec.get("fixed_shape_r") == SHAPE
           and spec.get("status") == "RESEARCH_ONLY_NO_PRODUCTION_AUTHORIZATION"
           and spec.get("created_for_first_eligible_local_date") <= day,
           "NATIVE_NB2_PREREGISTRATION_INCOMPATIBLE")
    d = root / "reports" / "v25_sog_source_cert_sprint" / day
    candidates = sorted(d.glob("daily_original_gamma_poisson_research_*/daily_research_generation_manifest.json"))
    outcome = {
        "schema": "v25_sog_nb2_native_attempt_audit_v1", "experiment_id": EXPERIMENT,
        "date_et": day, "research_only": True, "production_unchanged": True,
        "original_p15_nb2_replayed": False, "attempts": [], "source_batch_count": len(candidates),
        "source_selection_rule": "first_original_daily_generator_manifest_by_UTC_filename",
        "status": "NO_ORIGINAL_GAMMA_GENERATOR_YET",
        "code_commit": code_sha, "generated_at": now.astimezone(UTC).isoformat(),
    }
    if candidates:
        selected = candidates[0]
        manifest, _ = _read(root, str(selected))
        _check(manifest.get("schema") ==
               "v25_daily_original_sog_gamma_poisson_research_generator_v1" and
               manifest.get("research_only") is True and
               manifest.get("production_modified") is False and
               manifest.get("forecast_promotion_allowed") is False and
               manifest.get("slate_date_et") == day, "ORIGINAL_MANIFEST_INVALID")
        outcome["original_manifest_sha256"] = _sha(selected.read_bytes())
        outcome["source_manifest_path"] = str(selected.relative_to(root))
        attempted = manifest.get("attempts") or []
        _check(isinstance(attempted, list), "ORIGINAL_ATTEMPTS_LIST_MISSING")
        outcome["original_attempt_count"] = len(attempted)
        # Denominators here are source/candidate stages, NOT independent offers
        # or distinct settled player-game results.
        blocked = [x for x in manifest.get("failures", []) if isinstance(x, dict)]
        stages = Counter(str(x.get("stage") or "UNSPECIFIED") for x in blocked)
        unique_subjects = {
            stage: len({str(x["subject"]) for x in blocked if
                        str(x.get("stage") or "UNSPECIFIED") == stage and
                        x.get("subject") not in (None, "")})
            for stage in stages}
        counts = manifest.get("counts") or {}
        outcome["original_source_coverage"] = {
            "all_original_two_sided_offer_rows": counts.get("two_sided_offer_rows"),
            "native_id_qualified_candidates": counts.get("native_id_qualified"),
            "selected_candidates": counts.get("selected_candidates"),
            "original_forecasts_frozen": counts.get("successful_forecasts"),
            "signed_current_team_roster_count": counts.get("signed_current_team_rosters"),
            "source_failure_occurrences": dict(sorted(stages.items())),
            "distinct_failed_subjects_by_stage": dict(sorted(unique_subjects.items())),
            "history_sample_age_days": (
                (manifest.get("source_baseline_copy") or {}).get(
                    "frozen_historical_population_age_days")),
            "scientific_or_bookmaker_certification_implied": False,
        }
        accepted = 0
        for a in attempted:
            rec = {
                "original_attempt_sha256": a.get("receipt_sha256"),
                "source_player_id": a.get("player_id"),
                "source_official_event_id": a.get("official_nhl_event_id"),
                "status": "ABSTAIN", "reason": None,
            }
            try:
                _check(a.get("status") == "SHADOW_FORECAST", "ORIGINAL_RUN_NOT_A_FORECAST")
                ev = verify_native_source(root, manifest, selected, a, now=now)
                target = frozen_native_nb2(ev, now=now, code_sha=code_sha)
                frozen_dir = root / "reports" / "v25_sog_nb2_source_native" / day / "frozen"
                prior = []
                for previous in sorted(frozen_dir.glob("*.json")):
                    _check(_sha(previous.read_bytes()) == previous.stem,
                           "PREVIOUS_FROZEN_NATIVE_RECEIPT_MUTATED")
                    existing = json.loads(previous.read_bytes())
                    if existing.get("contract_id") == target["contract_id"]:
                        _check(existing.get("original_frozen_input_sha256") ==
                               target["original_frozen_input_sha256"] and
                               existing.get("schema") == SCHEMA and
                               existing.get("production_selection_allowed") is False,
                               "DUPLICATE_CONTRACT_SOURCE_IDENTITY_CHANGED")
                        prior.append(previous)
                _check(len(prior) <= 1, "MORE_THAN_ONE_FROZEN_NATIVE_CONTRACT")
                if prior:
                    rec.update(status="ALREADY_FROZEN_FIRST_PROSPECTIVE_SNAPSHOT_RETAINED",
                               reason="immutable_contract_first_snapshot_policy",
                               shadow_sha256=prior[0].stem,
                               shadow_path=str(prior[0].relative_to(root)))
                else:
                    path = frozen_dir / (_sha(_canonical(target)) + ".json")
                    target_sha = _append_once(path, target)
                    rec.update(status="NATIVE_NB2_RESEARCH_FROZEN", reason=None,
                               shadow_sha256=target_sha,
                               shadow_path=str(path.relative_to(root)))
                    accepted += 1
            except (NativeNB2Blocked, ValueError, TypeError, OSError, KeyError,
                    IndexError, AssertionError) as exc:
                rec["reason"] = type(exc).__name__ + ":" + str(exc)[:150]
            outcome["attempts"].append(rec)
        reused = sum(r["status"].startswith("ALREADY_FROZEN") for r in outcome["attempts"])
        outcome["status"] = ("FROZEN_NATIVE_NB2_RESEARCH" if accepted
                             else "ALREADY_FROZEN_NO_NEW_RECORDS" if reused
                             else "ABSTAIN_NO_ELIGIBLE_FUTURE_SOURCE")
        outcome["native_frozen_count"] = accepted
        outcome["prior_frozen_unchanged_count"] = reused
    outdir = root / "reports" / "v25_sog_nb2_source_native" / day / "attempt_audit"
    sha = _sha(_canonical(outcome))
    path = outdir / (sha + ".json")
    _append_once(path, outcome)
    return {"audit_path": str(path.relative_to(root)), "audit_sha256": sha,
            "status": outcome["status"], "source_batch_count": len(candidates),
            "native_frozen_count": outcome.get("native_frozen_count", 0),
            "attempts": outcome["attempts"], "research_only": True,
            "production_unchanged": True}
