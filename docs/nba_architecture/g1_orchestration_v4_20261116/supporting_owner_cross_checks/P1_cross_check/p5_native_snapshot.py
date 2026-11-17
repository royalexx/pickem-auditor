"""Versioned native owner transport for synthetic engineering verification.

The adapter invokes the real S producer and preserves its immutable fitted
artifact, source manifest, code bytes, uncertainty and G/O lineage. Outcome
transport has a separate root and API. No transport receipt authenticates a
source or permits historical fitting/evaluation; real admission stays closed.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from v2.nba_architecture.v2_contracts import canonical, verify, validate_pregame, digest, instant
from v2.nba_architecture.families_v2 import validate_forecast, validate_integration
from .warehouse import ForecastWarehouse, WarehouseError, _write_once, _read

VERSION = "nba-c-native-owner-handoff/1.0.0"
P1_VERSION = "nba-p1-native-handoff/1.0.0"


def _req(condition, reason):
    if not condition:
        raise WarehouseError(reason)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _mode(evidence_mode):
    _req(evidence_mode == "synthetic_engineering",
         "NATIVE_REAL_ADMISSION_REGISTRY_UNAVAILABLE")


def _raw(value, expected, reason):
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise WarehouseError(reason) from exc
    _req(_sha(raw) == expected, reason)
    return raw


def _packed_source(node):
    """Integrity only: exact source/ancestor bytes do not establish admission."""
    _req(isinstance(node, dict) and isinstance(node.get("capture"), dict)
         and isinstance(node.get("prior"), list), "NATIVE_SOURCE_BUNDLE")
    previous = None
    for number, item in enumerate(node["prior"] + [node], 1):
        _req(isinstance(item, dict) and isinstance(item.get("capture"), dict)
             and (item is node or item.get("prior") == []), "NATIVE_SOURCE_ANCESTRY")
        capture = item["capture"]
        _raw(item.get("raw_base64"), capture.get("raw_sha256"),
             "NATIVE_SOURCE_BYTES_CHANGED")
        _req(capture.get("revision") == number and
             capture.get("supersedes_receipt_sha256") ==
             (digest(previous) if previous is not None else None),
             "NATIVE_SOURCE_ANCESTRY")
        if previous is not None:
            _req(capture["url"] == previous["url"] and
                 instant(capture["retrieved_at"]) > instant(previous["retrieved_at"]),
                 "NATIVE_SOURCE_REVISION_CLOCK_OR_IDENTITY")
        previous = capture


def validate_p1_export(export, *, outcome=False):
    _req(isinstance(export, dict) and export.get("schema") == P1_VERSION,
         "NATIVE_P1_SCHEMA")
    _req(export.get("admission_status") == "BLOCKED", "NATIVE_P1_ADMISSION_NOT_ACCEPTED")
    if not outcome:
        _req(export.get("kind") in ("prior_game_export", "pregame_context_export"),
             "NATIVE_OUTCOME_IN_FORECAST_SOURCE")
        if export["kind"] == "prior_game_export":
            _packed_source(export["evidence_bundle"])
        else:
            for source in export["sources"]:
                _raw(source["raw_base64"], source["raw_sha256"], "NATIVE_SOURCE_BYTES_CHANGED")
        return
    _req(export.get("kind") == "outcome_export" and export.get("scoring_authorized") is False,
         "NATIVE_P1_OUTCOME_NOT_ADMITTED")
    previous = None
    for number, revision in enumerate(export["revisions"], 1):
        raw = _raw(revision["record_raw_base64"], revision["record_raw_sha256"],
                   "NATIVE_VAULT_RECORD_BYTES_CHANGED")
        record = revision["record"]
        _req(raw == canonical(record) + b"\n", "NATIVE_VAULT_RECORD_MISMATCH")
        verify(record)
        source = _raw(revision["source_raw_base64"], revision["source_raw_sha256"],
                      "NATIVE_VAULT_SOURCE_BYTES_CHANGED")
        _req(_sha(source) == record["source_raw_sha256"], "NATIVE_VAULT_SOURCE_JOIN")
        _req(record["game_id"] == export["game_id"] and
             record["player_id"] == export["player_id"], "NATIVE_VAULT_IDENTITY")
        _req(record["revision"] == number and record["supersedes_sha256"] == previous,
             "NATIVE_VAULT_CORRECTION_CHAIN")
        previous = record["content_hash"]
        if revision["accounting_evidence"] is not None:
            _packed_source(revision["accounting_evidence"])
    _req(export["correction_version"] == (len(export["revisions"]) or None),
         "NATIVE_VAULT_CORRECTION_VERSION")
    latest = export["revisions"][-1]["record"] if export["revisions"] else None
    if latest is not None:
        _req(export["participation"] == latest["state"] and
             export["stats"] == latest["stats"] and
             export["displayed_minutes"] == latest["minutes"] and
             export["team_id"] == latest["team_id"] and
             export["vault_schema"] == latest["schema"], "NATIVE_VAULT_SUMMARY_JOIN")
    else:
        _req(export["participation"] == "UNRESOLVED" and export["stats"] == {} and
             export["team_id"] is None and export["official_count"] is None,
             "NATIVE_VAULT_UNRESOLVED_SUMMARY")


class NativeForecastArchive:
    """Forecast-only native transport; accepts no vault or outcome argument."""
    def __init__(self, root):
        self.root = Path(root) / "native_forecast_only"
        self.forecasts = ForecastWarehouse(root)

    def _store(self, kind, value):
        raw = canonical(value) + b"\n"
        sha = _sha(raw)
        _write_once(self.root / kind / (sha + ".json"), raw)
        return sha

    def _get(self, kind, sha):
        _req(isinstance(sha,str) and len(sha)==64 and
             all(c in "0123456789abcdef" for c in sha), "NATIVE_FORECAST_SHA")
        obj=_read(self.root/kind/(sha+".json"))
        _req(_sha(canonical(obj)+b"\n")==sha, "NATIVE_FORECAST_BYTES_CHANGED")
        return obj

    def get_s(self, sha):
        receipt=self._get("intake_receipts",sha)
        _req(receipt["schema"]==VERSION and receipt["kind"]=="P2_prediction_intake",
             "NATIVE_S_RECEIPT_SCHEMA")
        refs=receipt["refs"]
        objects={name:self._get(name,refs[name]) for name in
            ("pregame","source_manifest","p1_source_exports","producer_code","native_prediction")}
        for name in ("game_state","opportunity"):
            if name in refs:
                objects[name]=self._get(name,refs[name]);verify(objects[name])
        artifact=refs["fitted_artifact_raw_sha256"]
        raw=(self.root/"fitted_artifacts"/(artifact+".raw")).read_bytes()
        _req(_sha(raw)==artifact,"NATIVE_S_ARTIFACT_BYTES_CHANGED")
        objects["fitted_artifact_bytes"]=raw
        data=json.loads(raw)
        used={key:objects["source_manifest"][key] for key in data["source_receipts"]
              if key in objects["source_manifest"]}
        _req(set(used)==set(data["source_receipts"]) and
             _sha(canonical(used))==data["source_manifest_sha256"],
             "NATIVE_S_SOURCE_MANIFEST_JOIN")
        for export in objects["p1_source_exports"]:
            validate_p1_export(export)
        codes={}
        for item in objects["producer_code"]:
            code_sha=item["raw_sha256"]
            code=(self.root/"code_bytes"/(code_sha+".raw")).read_bytes()
            _req(_sha(code)==code_sha,"NATIVE_S_CODE_BYTES_CHANGED")
            codes[item["relative_path"]]=code_sha
        _req(codes.get("model.py")==data["code_sha256"],"NATIVE_S_CODE_ARTIFACT_JOIN")
        prediction=objects["native_prediction"]
        if receipt["forecast_manifest_sha256"] is not None:
            _,stored=self.forecasts.get(receipt["forecast_manifest_sha256"])
            _req(stored["pregame"]==objects["pregame"] and
                 stored["distribution"]==prediction["distribution"],
                 "NATIVE_S_STORED_FORECAST_JOIN")
            validate_forecast(prediction["distribution"],objects["pregame"],
                g=objects.get("game_state"),o=objects.get("opportunity"))
        else:
            _req(prediction["distribution"] is None and prediction["abstain_reason"] is not None,
                 "NATIVE_S_ABSTENTION_JOIN")
        return receipt,objects

    def put_s(self, producer, fitted, *, frozen_pregame, target_player_id,
              role, source_manifest, source_exports=(), opportunity=None,
              game_state=None, conditioning="unconditional", seed=0,
              evidence_mode=""):
        """Invoke the loaded P2 package; no substitute forecast is constructed."""
        _mode(evidence_mode)
        validate_pregame(frozen_pregame)
        _req(type(fitted.payload) is bytes, "NATIVE_FITTED_BYTES_REQUIRED")
        module = sys.modules.get(producer.predict.__module__)
        _req(module is not None and getattr(module, "predict", None) is producer.predict,
             "NATIVE_S_PRODUCER_REQUIRED")
        model_path = Path(module.__file__).resolve()
        _req(model_path.name == "model.py", "NATIVE_S_PRODUCER_PATH")
        data = fitted.data
        _req(data["code_sha256"] == _sha(model_path.read_bytes()), "NATIVE_S_CODE_ARTIFACT_JOIN")
        _req(fitted.artifact_sha256 == _sha(fitted.payload), "NATIVE_S_ARTIFACT_BYTES")
        used = {k: source_manifest[k] for k in data["source_receipts"] if k in source_manifest}
        _req(set(used) == set(data["source_receipts"]) and
             _sha(canonical(used)) == data["source_manifest_sha256"], "NATIVE_S_SOURCE_MANIFEST_JOIN")
        exports = deepcopy(list(source_exports))
        for export in exports:
            validate_p1_export(export)
            if export["kind"] == "pregame_context_export":
                _req(export["game_id"] == frozen_pregame["game_id"] and
                     export["input_freeze_at"] == frozen_pregame["input_freeze_at"] and
                     export["event_start_at"] == frozen_pregame["event_start_at"],
                     "NATIVE_P1_CONTEXT_IDENTITY")
        prediction = producer.predict(fitted, frozen_pregame=frozen_pregame,
            target_player_id=target_player_id, role=role, opportunity=opportunity,
            game_state=game_state, conditioning=conditioning, seed=seed)
        refs = {"pregame": self._store("pregame", frozen_pregame),
                "source_manifest": self._store("source_manifest", source_manifest),
                "p1_source_exports": self._store("p1_source_exports", exports)}
        artifact_sha = _sha(fitted.payload)
        _write_once(self.root / "fitted_artifacts" / (artifact_sha + ".raw"), fitted.payload)
        refs["fitted_artifact_raw_sha256"] = artifact_sha
        code = []
        for path in sorted(model_path.parent.glob("*.py")):
            raw = path.read_bytes(); sha = _sha(raw)
            _write_once(self.root / "code_bytes" / (sha + ".raw"), raw)
            code.append({"relative_path": path.name, "raw_sha256": sha})
        refs["producer_code"] = self._store("producer_code", code)
        for name, obj in (("game_state", game_state), ("opportunity", opportunity)):
            if obj is not None:
                verify(obj); refs[name] = self._store(name, obj)
        forecast_key = None
        if prediction.distribution is not None:
            distribution = prediction.distribution
            validate_forecast(distribution, frozen_pregame, g=game_state, o=opportunity)
            _req(distribution["lineage"]["S"]["artifact_sha256"] == artifact_sha and
                 distribution["player_id"] == target_player_id,
                 "NATIVE_S_DISTRIBUTION_ARTIFACT_JOIN")
            forecast_key = self.forecasts.put(frozen_pregame, distribution)
        response = {"distribution": prediction.distribution,
                    "abstain_reason": prediction.abstain_reason,
                    "parameters": prediction.parameters, "uncertainty": prediction.uncertainty}
        refs["native_prediction"] = self._store("native_prediction", response)
        receipt = {"schema": VERSION, "kind": "P2_prediction_intake",
            "evidence_mode": evidence_mode, "source_admission": "BLOCKED",
            "independent_acceptance": "PENDING", "not_predictive_evaluation": True,
            "attempted": 1, "produced": int(prediction.distribution is not None),
            "abstained": int(prediction.distribution is None), "refs": refs,
            "forecast_manifest_sha256": forecast_key,
            "missing_prerequisites": ["INDEPENDENT_SOURCE_ADMISSION",
                "INDEPENDENT_LATEST_OWNER_HANDOFF_ACCEPTANCE"]}
        return self._store("intake_receipts", receipt), receipt

    def put_j(self, result, *, pregame, game_state, opportunity, distributions,
              evidence_mode=""):
        """Keep actual native P4 result and same-draw G/O/J objects together."""
        _mode(evidence_mode)
        bundle = result["bundle"]
        validate_integration(bundle, pregame, game_state, opportunity)
        _req(result.get("input_shas", {}).get("pregame") == pregame["content_hash"] and
             result["input_shas"].get("G") == game_state["content_hash"] and
             result["input_shas"].get("O") == opportunity["content_hash"],
             "NATIVE_J_INPUT_JOIN")
        # Absence/pending status survives transport. It cannot be changed into
        # independent acceptance by a self-consistent hash or caller string.
        manifest = result.get("integration_manifest")
        _req(isinstance(manifest, dict), "NATIVE_J_INTEGRATION_MANIFEST_REQUIRED")
        stored = []
        for distribution in distributions:
            validate_forecast(distribution, pregame, g=game_state, o=opportunity, scenarios=bundle)
            _req(distribution["pipeline_mode"] == "S_O_J", "NATIVE_J_COMPLETE_PIPELINE")
            stored.append(self.forecasts.put(pregame, distribution, scenarios=bundle,
                game_state=game_state, opportunity=opportunity))
        _req(bool(stored), "NATIVE_J_DISTRIBUTIONS_REQUIRED")
        native = self._store("native_j_results", result)
        receipt = {"schema": VERSION, "kind": "P4_joint_intake",
            "evidence_mode": evidence_mode, "source_admission": "BLOCKED",
            "independent_acceptance": "PENDING", "native_result_sha256": native,
            "upstream_integration_manifest": deepcopy(manifest),
            "forecast_manifest_sha256": stored, "outcome_accessed": False}
        return self._store("intake_receipts", receipt), receipt


class NativeOutcomeArchive:
    """P1 native outcome/correction transport; never imports a forecast producer."""
    def __init__(self, root):
        self.root = Path(root) / "native_outcome_only"

    def put_p1(self, export, *, evidence_mode=""):
        _mode(evidence_mode)
        validate_p1_export(export, outcome=True)
        raw = canonical(export) + b"\n"; sha = _sha(raw)
        _write_once(self.root / (sha + ".json"), raw)
        return sha

    def get(self, sha):
        _req(isinstance(sha, str) and len(sha) == 64 and
             all(c in "0123456789abcdef" for c in sha), "NATIVE_OUTCOME_SHA")
        export = _read(self.root / (sha + ".json"))
        _req(_sha(canonical(export) + b"\n") == sha, "NATIVE_OUTCOME_BYTES_CHANGED")
        validate_p1_export(export, outcome=True)
        return export

    def scoring_disposition(self, sha):
        export = self.get(sha)
        return {"status": "BLOCKED", "scored": False,
            "participation": export["participation"], "source_profile": export["source_profile"],
            "correction_version": export["correction_version"],
            "missing_prerequisites": list(export["missing_requirements"]),
            "reason": "P1_NATIVE_OUTCOME_NOT_INDEPENDENTLY_ADMITTED"}
