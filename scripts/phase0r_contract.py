"""Independent strict Phase 0R certification of pre-evaluation input bindings.

The legacy pregame receipt checker alone cannot certify that the model read
the archived bytes. Strict certification requires a frozen candidate digest,
an isolated evaluation context and complete source role receipts. This never
upgrades old runs which lack those original pre-evaluation proofs.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from point_in_time_provenance import pregame_snapshot_status, instant

SCHEMA = "pickem_pre_eval_input_binding_v1"


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def strict_snapshot_status(row, *, archive_root):
    okay, reason = pregame_snapshot_status(row, archive_root=Path(archive_root))
    if not okay:
        return False, reason
    try:
        binding = row.get("model_input_binding")
        if not isinstance(binding, dict) or binding.get("schema") != SCHEMA:
            return False, "pre_eval_input_binding_missing"
        if binding.get("method") != "pre_evaluation_archived_copy":
            return False, "pre_eval_binding_method_not_verified"
        if any(binding.get(key) is not True for key in
               ("evaluates_frozen_candidate", "uses_isolated_data_directory",
                "uses_isolated_production_policy")):
            return False, "pre_eval_isolation_missing"
        if binding.get("external_context_unpinned") is not False:
            return False, "pre_eval_external_context_unpinned"
        if row.get("input_freeze_basis") != "pre_evaluation_immutable_clone":
            return False, "pre_eval_freeze_basis_missing"
        frozen = instant(row.get("input_freeze_at"), "input_freeze_at")
        started = instant(row.get("model_evaluation_started_at"),
                          "model_evaluation_started_at")
        if started != frozen:
            return False, "model_started_outside_frozen_context"
        capture = instant(row.get("source_capture_at"), "source_capture_at")
        if capture != frozen:
            return False, "source_capture_does_not_match_freeze"
        if row.get("model_training_cutoff_basis") != "on_demand_model_data_cutoff":
            return False, "training_cutoff_basis_unverified"
        fits = row.get("model_fit_receipts")
        if not isinstance(fits, list) or len(fits) != 2:
            return False, "model_fit_receipts_missing"
        fit_map = {f.get("component"): f for f in fits if isinstance(f, dict)}
        if set(fit_map) != {"Engine_A", "Engine_B"}:
            return False, "model_fit_component_mismatch"
        if (fit_map["Engine_A"].get("fit_mode") != "on_demand"
                or fit_map["Engine_B"].get("fit_mode") != "rule_based"
                or any(instant(f.get("training_data_cutoff_at"), "fit_cutoff") > frozen
                       for f in fits)):
            return False, "model_fit_cutoff_inconsistent"

        candidate = row.get("inputs")
        if not isinstance(candidate, dict):
            return False, "frozen_numerical_candidate_missing"
        digest = hashlib.sha256(canonical_bytes(candidate)).hexdigest()
        if binding.get("candidate_sha256") != digest:
            return False, "frozen_numerical_candidate_digest_mismatch"
        if (candidate.get("side") != row.get("side")
                or candidate.get("line") != row.get("reference_line")):
            return False, "frozen_numerical_candidate_contract_mismatch"
        if (candidate.get("player_id") is not None
                and str(candidate["player_id"]) != str(row.get("player_id"))):
            return False, "frozen_numerical_candidate_player_mismatch"
        if (candidate.get("event_id") is not None
                and str(candidate["event_id"]) != str(row.get("event_id"))):
            return False, "frozen_numerical_candidate_event_mismatch"

        receipts = row.get("source_receipts") or []
        ids = [r.get("source_id") for r in receipts if isinstance(r, dict)]
        if binding.get("source_receipt_ids") != ids or row.get("used_source_ids") != ids:
            return False, "pre_eval_receipt_binding_mismatch"
        by_role = {}
        for receipt in receipts:
            role = (receipt.get("model_component"),
                    str(receipt.get("archive_path") or "").split("/", 1)[0])
            if role in by_role:
                return False, "pre_eval_duplicate_source_role"
            by_role[role] = receipt
        required = {
            ("Engine_A", "evaluated_candidate"),
            ("Engine_A", "historical_usage"),
            ("Engine_B", "evaluated_candidate"),
            ("Market", "original_book_quotes"),
            ("Market", "evaluated_market"),
        }
        if not (row.get("engine_b") or {}).get("abstain"):
            required.add(("Engine_B", "original_research"))
        if (row.get("blend") or {}).get("production_policy"):
            required.add(("Engine_A", "production_policy"))
        if not required <= set(by_role):
            return False, "pre_eval_required_source_role_missing"
        candidate_receipt = by_role[("Engine_A", "evaluated_candidate")]
        if candidate_receipt.get("content_sha256") != digest:
            return False, "frozen_candidate_not_equal_evaluated_candidate"
        if by_role[("Engine_B", "evaluated_candidate")].get("content_sha256") != digest:
            return False, "engine_b_frozen_candidate_drift"
        market_input = {k: candidate.get(k) for k in
                        ("books", "line", "side", "market_retrieved_at")}
        market_digest = hashlib.sha256(canonical_bytes(market_input)).hexdigest()
        if by_role[("Market", "evaluated_market")].get("content_sha256") != market_digest:
            return False, "original_market_candidate_drift"

        files = binding.get("input_files")
        if not isinstance(files, dict):
            return False, "frozen_input_file_map_missing"
        if files.get("model_input_candidate.json") != candidate_receipt["source_id"]:
            return False, "frozen_candidate_file_unbound"
        if files.get("market_input.json") != by_role[("Market", "evaluated_market")]["source_id"]:
            return False, "frozen_market_file_unbound"
        if files.get("odds_quotes.jsonl") != by_role[("Market", "original_book_quotes")]["source_id"]:
            return False, "frozen_original_quotes_file_unbound"
        if by_role.get(("Engine_A", "production_policy")) is not None:
            if files.get("config/production_consensus.json") != by_role[("Engine_A", "production_policy")]["source_id"]:
                return False, "frozen_policy_file_unbound"
        usage_id = by_role[("Engine_A", "historical_usage")]["source_id"]
        if usage_id not in {v for k, v in files.items() if k.startswith("usage/")}:
            return False, "frozen_usage_file_unbound"
        # PropLine's ORIGINAL frozen quote rows already contain an authenticated
        # API collection URL, event namespace and retrieval clock. Check their
        # exact athlete/stat/book/price identity instead of requiring a direct
        # bookmaker URL or an upstream publication clock that the API lacks.
        # Other provider namespaces retain the pre-existing strict receipt gate.
        if row.get("event_id_namespace") == "propline":
            from phase0_quote_origin import verified_original_api_quote_lineage
            origin_ok, origin_reason = verified_original_api_quote_lineage(
                row, archive_root=archive_root)
            if not origin_ok:
                return False, origin_reason
        # All claims are bounded to the recorded legacy A/B evaluation. The
        # subsequent Bayesian/NUTS sidecars need their own artifact receipts.
        return True, "strict_pre_eval_bound_source_inputs"
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        return False, "pre_eval_binding_invalid:" + type(exc).__name__
