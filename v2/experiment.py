"""P1-06: exact, deterministic experiment receipt over sealed, read-only inputs.

The signed-in-the-artifact digest binds code, protocol and exact input bytes.
It is NOT a source-publication certificate, a human cryptographic signature,
or permission to promote a historical or prospective challenger.
"""
from __future__ import annotations

import hashlib
import json

from .contracts import ContractError, canonical_hash
from .rolling import run_rolling
from .legacy_adapter import scan_original_pairs


def assess_independence(protocol: dict) -> dict:
    """No 2025 independence is assumed after prior 2024/2025 training/design."""
    flag = protocol.get("2025_independent_holdout_status")
    if flag in (None, "unknown_must_audit_prior_training_and_human_design_exposure",
                "not_demonstrated_prior_training_and_model_selection_exposure"):
        return {
            "season_2025": "not_independent_not_eligible_for_unseen_holdout_claims",
            "reason": "2025 used in earlier 2024/2025 model-fitting and research decisions; no complete historical independence register",
            "may_be_used_as_untouched_holdout": False,
        }
    if flag != "not_independent_not_eligible_for_unseen_holdout_claims":
        raise ContractError("unsupported_2025_independence_attestation")
    return {
        "season_2025": flag, "may_be_used_as_untouched_holdout": False,
        "reason": "previous training/model-selection exposure is acknowledged",
    }


def run_experiment(payload: dict, protocol: dict, *,
                   input_sha256: str, protocol_sha256: str,
                   code_commit: str, seed: int = 20261109,
                   strict_checker=None, archive_root=None) -> dict:
    for name, sha in (("input_sha256", input_sha256),
                      ("protocol_sha256", protocol_sha256)):
        if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ContractError("invalid_experiment_digest:" + name)
    if not isinstance(code_commit, str) or len(code_commit) != 40 or any(
            c not in "0123456789abcdef" for c in code_commit):
        raise ContractError("invalid_experiment_code_commit")
    if not isinstance(protocol, dict) or protocol.get("experiment_id") != "V25-EXP-B-2024-ROLLING-ORIGIN":
        raise ContractError("unregistered_experiment_protocol")
    if protocol.get("start_season") != 2024 or protocol.get("promotion_authorized") is not False:
        raise ContractError("invalid_2024_protocol_safety")
    if not isinstance(payload, dict):
        raise ContractError("experiment_bundle_not_object")
    if payload.get("experiment_id") != protocol["experiment_id"]:
        raise ContractError("experiment_id_mismatch")
    independence = assess_independence(protocol)
    result = {
        "schema": "v25-phase1-experiment-manifest-1",
        "experiment_id": protocol["experiment_id"],
        "protocol_sha256": protocol_sha256,
        "input_sha256": input_sha256,
        "code_commit": code_commit,
        "scoring_seed": seed,
        "independence_audit": independence,
        "source_publication_certified": False,
        "phase0r_live_approval": False,
        "production_promotion_authorized": False,
        "reconstructed_historical_forecasts_are_original": False,
    }
    if "rolling" in payload:
        if payload["rolling"].get("experiment_id") != protocol["experiment_id"]:
            raise ContractError("rolling_experiment_id_mismatch")
        result["rolling"] = run_rolling(payload["rolling"], seed=seed)
    legacy_pairs = []
    if "joint_scenarios" in payload:
        from .joint_evaluation import evaluate_joint
        result["joint_scenarios"]=evaluate_joint(
            payload["joint_scenarios"],bootstrap_seed=seed)
    if "legacy_originals" in payload:
        legacy = scan_original_pairs(
            payload["legacy_originals"],
            strict_checker=strict_checker, archive_root=archive_root,
        )
        legacy_pairs = legacy["pairs"]
        result["legacy_v1"] = {k:v for k,v in legacy.items() if k != "pairs"}
        result["legacy_v1"]["bound_for_scoring"] = 0
        result["legacy_v1"]["unbound_certified_pairs"] = len(legacy_pairs)
    if "legacy_bindings" in payload and "legacy_originals" not in payload:
        raise ContractError("legacy_bindings_without_original_forecasts")
    bound_forecasts = []
    if "legacy_bindings" in payload:
        from .contracts import parse_quote
        section = payload.get("frozen")
        if not isinstance(section, dict):
            raise ContractError("legacy_binding_requires_exact_frozen_quote_universe")
        quote_index = {q.quote_id: q for q in
                       (parse_quote(x) for x in section.get("quotes", []))}
        seen_bindings = set()
        for bind in payload["legacy_bindings"]:
            qid = bind.get("quote_id")
            if qid in seen_bindings:
                raise ContractError("duplicate_legacy_quote_binding")
            seen_bindings.add(qid)
            if qid not in quote_index:
                raise ContractError("legacy_binding_unknown_quote")
            quote = quote_index[qid]
            matches = [pair for pair in legacy_pairs
                       if pair.key[3] == str(quote.event_id)
                       and pair.key[4] == str(quote.player_id)
                       and pair.key[5] == str(quote.stat_key)
                       and pair.key[6] == float(quote.line)]
            # key order: run_id, game_date, sport, event_id, player_id,
            # stat, reference_line. Never choose between multiple original runs.
            if len(matches) != 1:
                raise ContractError("legacy_binding_not_uniquely_certified")
            original = matches[0]
            original_commit = bind.get("original_code_commit")
            original_artifact = bind.get("original_model_artifact_sha256")
            bound_forecasts.append(original.bind(
                quote, code_commit=original_commit,
                model_artifact_sha256=original_artifact,
            ))
        result["legacy_v1"]["bound_for_scoring"] = len(bound_forecasts)
        result["legacy_v1"]["unbound_certified_pairs"] = (
            len(legacy_pairs)-len(bound_forecasts))
    if "frozen" in payload:
        from .contracts import parse_quote, parse_snapshot
        from .evaluation import Settlement, evaluate
        section = payload["frozen"]
        if not isinstance(section, dict) or any(k not in section
                  for k in ("quotes", "forecasts", "settlements")):
            raise ContractError("invalid_frozen_replay_bundle")
        result["frozen"] = evaluate(
            [parse_quote(x) for x in section["quotes"]],
            [parse_snapshot(x) for x in section["forecasts"]] + bound_forecasts,
            [Settlement(**x) for x in section["settlements"]],
            bootstrap_seed=seed,
        )
        result["frozen"]["source_publication_independently_verified"] = False
        result["frozen"]["phase0r_certification_independently_verified"] = False
    if not any(k in result for k in ("rolling", "frozen", "legacy_v1", "joint_scenarios")):
        raise ContractError("empty_experiment_workstreams")
    result["receipt_sha256"] = canonical_hash(result)
    return result
