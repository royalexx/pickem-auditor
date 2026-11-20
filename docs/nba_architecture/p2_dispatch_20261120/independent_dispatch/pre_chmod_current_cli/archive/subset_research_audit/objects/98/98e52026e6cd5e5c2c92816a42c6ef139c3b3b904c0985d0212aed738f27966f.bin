"""Append-only C warehouse; G0 v2 validated forecasts never contain outcomes.

Research-only archive. Sources are passed explicitly; no data collectors or
automatic historical-outcome lookup live in this package.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import os
import tempfile

from v2.nba_architecture.v2_contracts import (
    canonical, digest, instant, validate_pregame, validate_distribution,
    validate_evaluation, verify, ContractError,
)
from v2.nba_architecture.families_v2 import validate_integration


class WarehouseError(ValueError):
    pass


def _write_once(path, raw):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o444)
    except FileExistsError:
        if path.read_bytes()!=raw:
            raise WarehouseError("IMMUTABLE_COLLISION")
        return False
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return True


def _read(path):
    b=Path(path).read_bytes()
    try:
        x=json.loads(b,parse_constant=lambda _: (_ for _ in ()).throw(WarehouseError("NONFINITE_JSON")))
    except (TypeError,ValueError) as exc:
        raise WarehouseError("CORRUPT_ARCHIVE") from exc
    if b != canonical(x)+b"\n":
        raise WarehouseError("NONCANONICAL_ARCHIVE")
    return x


class ForecastWarehouse:
    """Immutable forecast-only content-addressed objects.

    For G0 J, provide original G and O envelopes and entire J scenario bundle;
    hash checks prohibit a forged marginal unrelated to coherent draws.
    """
    def __init__(self,root):
        self.root=Path(root)/"forecast_only"

    def put(self, pregame, distribution, *, scenarios=None, game_state=None,
            opportunity=None):
        validate_pregame(pregame)
        validate_distribution(distribution,pregame,scenarios)
        if distribution["pipeline_mode"]=="S_O_J":
            if any(x is None for x in (scenarios,game_state,opportunity)):
                raise WarehouseError("J_FULL_WITNESS_REQUIRED")
            validate_integration(scenarios,pregame,game_state,opportunity)
        elif scenarios is not None or game_state is not None or opportunity is not None:
            raise WarehouseError("UNEXPECTED_UPSTREAM_WITNESS")
        if distribution["source_profile"]=="original_prospective":
            if distribution["status"]!="UNCERTIFIED_SHADOW":
                raise WarehouseError("PROSPECTIVE_STATUS")
        else:
            if distribution["status"]!="RESEARCH_RECONSTRUCTION":
                raise WarehouseError("RECONSTRUCTION_STATUS")
        # All artifacts are preserved in immutable content-addressed objects.
        objects={"pregame":pregame,"distribution":distribution}
        if scenarios is not None:
            objects.update(scenarios=scenarios,game_state=game_state,
                           opportunity=opportunity)
        refs={}
        for typ,obj in objects.items():
            raw=canonical(obj)+b"\n"
            sha=hashlib.sha256(raw).hexdigest()
            _write_once(self.root/typ/sha[:2]/(sha+".json"),raw)
            refs[typ]={"sha256":sha,"content_hash":verify(obj)}
        manifest={"kind":"nba_c_warehouse_manifest/1",
                  "game_id":distribution["game_id"],
                  "player_id":distribution["player_id"],
                  "stat":distribution["stat"],
                  "period":distribution["period"],
                  "mode":distribution["pipeline_mode"],
                  "conditioning":distribution["conditioning"],
                  "source_profile":distribution["source_profile"],
                  "forecast_at":distribution["forecast_at"],
                  "frozen_at":distribution["frozen_at"],
                  "event_start_at":distribution["event_start_at"],
                  "refs":refs}
        mraw=canonical(manifest)+b"\n"
        key=hashlib.sha256(mraw).hexdigest()
        _write_once(self.root/"manifests"/key[:2]/(key+".json"),mraw)
        # Freeze one immutable meaning for a logical forecast identity.
        # Do NOT include its PMF/source/artifact SHA in this key: otherwise a
        # post hoc replacement could masquerade as a distinct forecast.
        models={stage:(None if m is None else [m["model_id"],m["version"]])
                for stage,m in distribution["lineage"].items()}
        logical={"game_id":distribution["game_id"],
                 "player_id":distribution["player_id"],"stat":distribution["stat"],
                 "period":distribution["period"],
                 "mode":distribution["pipeline_mode"],
                 "conditioning":distribution["conditioning"],
                 "forecast_at":distribution["forecast_at"],
                 "frozen_at":distribution["frozen_at"],
                 "source_profile":distribution["source_profile"],
                 "models":models}
        logical_key=digest(logical)
        _write_once(self.root/"logical_identity"/logical_key[:2]/
                    (logical_key+".json"),
                    canonical({"logical":logical,"manifest_sha256":key})+b"\n")
        return key

    def get(self,manifest_sha):
        if len(manifest_sha)!=64 or any(c not in "0123456789abcdef" for c in manifest_sha):
            raise WarehouseError("INVALID_MANIFEST_SHA")
        manifest=_read(self.root/"manifests"/manifest_sha[:2]/(manifest_sha+".json"))
        if hashlib.sha256(canonical(manifest)+b"\n").hexdigest()!=manifest_sha:
            raise WarehouseError("MANIFEST_HASH_MISMATCH")
        out={}
        for typ,ref in manifest["refs"].items():
            sha=ref["sha256"]
            obj=_read(self.root/typ/sha[:2]/(sha+".json"))
            if hashlib.sha256(canonical(obj)+b"\n").hexdigest()!=sha:
                raise WarehouseError("SOURCE_BYTES_CORRUPTED")
            if verify(obj)!=ref["content_hash"]:
                raise WarehouseError("CONTENT_HASH_MISMATCH")
            out[typ]=obj
        validate_distribution(out["distribution"],out["pregame"],out.get("scenarios"))
        if "scenarios" in out:
            validate_integration(out["scenarios"],out["pregame"],
                                 out["game_state"],out["opportunity"])
        return manifest,out


class OutcomeVault:
    """Physically separate official evidence, never a pregame feature import.

    Outcome settlement G0 requires actual original evaluation and correction chain.
    There is no scoring call in ForecastWarehouse.
    """
    def __init__(self,root):
        self.root=Path(root)/"official_outcome_vault"

    def put(self,evaluation,distribution,*,offer_view=None,previous=None):
        validate_evaluation(evaluation,distribution,offer_view,previous)
        sha=hashlib.sha256(canonical(evaluation)+b"\n").hexdigest()
        _write_once(self.root/sha[:2]/(sha+".json"),
                    canonical(evaluation)+b"\n")
        return sha

    def get(self,sha):
        if len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
            raise WarehouseError("INVALID_OUTCOME_SHA")
        obj=_read(self.root/sha[:2]/(sha+".json"))
        if hashlib.sha256(canonical(obj)+b"\n").hexdigest()!=sha:
            raise WarehouseError("OUTCOME_HASH_MISMATCH")
        return obj
