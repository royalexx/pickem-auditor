"""P5 bridge to exact P3/P4-approved update interfaces.

No new statistical likelihood, fit algorithm, or original C10 parameter tune.
P3 S-only FULL REFIT is never silently called as a daily update.
NHL locked native NB2/Poisson/Gamma are predict-only. A distinct adaptive
Gamma challenger can update only when official final played SOG + TOI are
both verifiable and chronologically admitted.
"""
from __future__ import annotations
from datetime import datetime
import hashlib
import json
import math

from .scoring import ScoreError, _utc, digest
from .registry import POLICY

def _need(ok,code):
    if not ok:
        raise ScoreError(code)

def supported_updates():
    return {k:sorted(v) for k,v in POLICY.items()}

def nba_p3_full_refit_adapter(*,family,model_id,new_version,
          training_rows,cutoff_at,manifest_sha256,
          enable_periodic_full_refit=False):
    """Explicit owner S0/S1/S2 bounded refit only, never automatic daily.

    Raw official minutes must have an independent verified source receipt;
    P0 OutcomeRecord alone does not contain them. This bridge refuses to
    replace actual minutes with a generic pregame opportunity projection.
    """
    _need(enable_periodic_full_refit is True,"NBA_PERIODIC_REFIT_NOT_AUTHORIZED")
    _need(family in ("S0","S1","S2"),"NBA_OWNER_FAMILY_NOT_SUPPORTED")
    _need(len(training_rows)>=10,"NBA_FULL_REFIT_MINIMUM_NOT_MET")
    _need(len({x["event_id"] for x in training_rows})>=10,
          "NBA_FULL_REFIT_TOO_FEW_GAMES")
    from research.nba_p3_frozen.engine import (
        fit_research_parameters,validate_research_model)
    rows=[]
    for r in training_rows:
        _need(r.get("sport")=="NBA" and r.get("training_admitted") is True,
              "NBA_TRAINING_ROW_NOT_ADMITTED")
        _need(_utc(r["official_result_available_at"])<=_utc(cutoff_at),
              "NBA_FUTURE_OUTCOME")
        minutes=r.get("exposure",{}).get("minutes_verified")
        _need(type(minutes) in (float,int) and 0<minutes<=73,
              "NBA_OFFICIAL_MINUTES_NOT_VERIFIED")
        rows.append({"event_id":r["event_id"],"player_id":r["player_id"],
           "team_id":r["team_id"],"stat":r["stat_key"],
           "count":r["official_value"],"minutes":minutes,
           "event_start_at":r["event_start_at"],
           "outcome_available_at":r["official_result_available_at"],
           "source_sha256":r["official_source_sha256"]})
    payload=fit_research_parameters(rows,cutoff_at=cutoff_at,family=family,
                   model_id=model_id,model_version=new_version,
                   training_reference_sha256=manifest_sha256)
    _need(validate_research_model(payload,cutoff_at=cutoff_at) is True,
          "NBA_OWNER_STRUCTURAL_VALIDATION_FAILED")
    return payload

def nhl_p4_gamma_adaptive_adapter(*, previous, training_rows, cutoff_at,
                                  original_official_source_verifier):
    """Only a separately named Track B adaptive research challenger.

    previous is the exact original immutable adaptive model; the existing P4
    propose_adaptive_update validates its own schema, history and chronology.
    The caller must independently verify official source bytes before P4
    is called. The locked Gamma, plugin Poisson and native NB2 are excluded.
    """
    _need(previous.get("research_track")=="ADAPTIVE_CHALLENGER" and
          previous.get("experiment_id") not in (
              "EXP-V25-NHL-SOG-NB2-NATIVE-PLUGIN-MEAN-20261114",
              "EXP-V25-NHL-SOG-EXPOSURE-EB-001"),
          "NHL_LOCKED_COMPARATOR_MUST_NOT_ADAPT")
    _need(callable(original_official_source_verifier),
          "INDEPENDENT_OFFICIAL_SOURCE_VERIFIER_REQUIRED")
    from v2.nhl_sog_p4_forecasts import propose_adaptive_update
    converted=[]
    for r in training_rows:
        _need(r.get("sport")=="NHL" and r.get("stat_key")=="shots on goal" and
              r.get("participation")=="PLAYED" and r.get("training_admitted") is True,
              "NHL_NONPLAYED_OR_UNADMITTED")
        _need(_utc(r["official_result_available_at"])<=_utc(cutoff_at),
              "NHL_OUTCOME_TOO_LATE")
        _need(original_official_source_verifier(r) is True,
              "NHL_OFFICIAL_SOURCE_AUTHENTICATION_FAILED")
        toi=r.get("exposure",{}).get("toi_minutes_verified")
        _need(type(toi) in (int,float) and math.isfinite(toi) and 0<toi<=65,
              "NHL_OFFICIAL_TOI_NOT_VERIFIED")
        converted.append({"player_id":r["player_id"],"event_id":r["event_id"],
            "played":True,"finalized":True,
            "first_available_at":r["official_result_available_at"],
            "source_sha256":r["official_source_sha256"],
            "shots_on_goal":r["official_value"],"toi_minutes":toi})
    _need(bool(converted),"NHL_NO_NEW_OFFICIAL_RESULTS")
    payload=propose_adaptive_update(previous,converted,cutoff_at=cutoff_at)
    _need(payload["alpha"]>0 and payload["beta"]>0 and
          payload["parent_model_sha256"] is not None and
          payload["research_track"]=="ADAPTIVE_CHALLENGER" and
          payload["version"]>previous["version"],
          "NHL_P4_NUMERICAL_UPDATE_INVALID")
    return payload
