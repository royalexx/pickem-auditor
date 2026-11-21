"""NBA P3 pregame integration to the *unchanged* P0 nine-record gateway.

This package creates shadow distributions, not original source evidence. P1 owns
features and source receipts, P5 owns learning schedules/calibration, and P0
owns durable admission. No collector, outcome loader, or production automation.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import hashlib
import json
import math
import statistics as py_stats

from v2.p0_integrity.contracts import (
    AdmissionError, admit_forecast, canonical_bytes, record, sha256, utc,
    validate_record, verify_source_bytes)
from v2.p0_integrity.storage import append_immutable
from .distributions import (
    ForecastBlocked, STATS, COMBOS, digest, empirical, statistics,
    s_control, opportunity_mixture, combo_counts, threshold, pmf)
from .joint import simulate, player_draws

MODEL_SCHEMA = "PA-NBA-P3-Model/1"
PIPELINES = ("S_ONLY", "S_PLUS_O", "S_O_J")
STATISTICS = STATS + tuple(COMBOS)
CODES = ("FORECAST_FROZEN", "INSUFFICIENT_HISTORY", "IDENTITY_UNVERIFIED",
         "PARTICIPATION_UNRESOLVED", "SOURCE_STALE", "SOURCE_UNCERTIFIED",
         "MODEL_NOT_READY", "NUMERICAL_FAILURE", "MISSED_FREEZE")


@dataclass(frozen=True)
class Attempt:
    status: str
    reason: str | None
    forecast: dict | None
    admission: dict | None
    warehouse: dict | None
    storage: dict | None


def _fail(status, reason):
    raise ForecastBlocked(status, reason)


def _source_safe(obj, sources, source_root, cutoff):
    refs = {x["receipt_id"]:x for x in sources}
    if not refs or len(refs) != len(sources):
        _fail("SOURCE_UNCERTIFIED", "duplicate_or_missing_source_receipt")
    if not set(obj["source_receipt_ids"]).issubset(refs):
        _fail("SOURCE_UNCERTIFIED", "feature_receipt_not_supplied")
    for src in sources:
        verify_source_bytes(src, source_root)
        if utc(src["source_available_at"]) > utc(cutoff) or \
           utc(src["collected_at"]) > utc(cutoff):
            _fail("SOURCE_STALE", "source_after_input_freeze")


def load_model(model, source_root, expected_commit):
    """Model registry reader verifies bytes, version, cutoff, SHA and code SHA."""
    validate_record("ModelArtifact", model)
    if model["model_code_sha"] != expected_commit:
        _fail("MODEL_NOT_READY", "code_commit_mismatch")
    root=Path(source_root).resolve(strict=True)
    file=Path(source_root)/model["artifact_path"]
    if not file.is_file() or file.is_symlink() or not file.resolve(strict=True).is_relative_to(root):
        _fail("MODEL_NOT_READY", "unsafe_or_missing_model_artifact")
    raw=file.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=model["artifact_sha256"]:
        _fail("MODEL_NOT_READY", "model_bytes_hash_mismatch")
    try:
        payload=json.loads(raw)
    except (ValueError,TypeError) as exc:
        raise ForecastBlocked("MODEL_NOT_READY", "invalid_model_json") from exc
    if payload.get("schema") != MODEL_SCHEMA or \
       payload.get("model_id") != model["model_id"] or \
       payload.get("model_version") != model["model_version"] or \
       payload.get("training_cutoff_at") != model["training_cutoff_at"]:
        _fail("MODEL_NOT_READY", "model_registry_identity_mismatch")
    family=payload.get("family")
    if family not in ("S0","S1","S2","S3"):
        _fail("MODEL_NOT_READY", "unregistered_statistical_family")
    if not isinstance(payload.get("training_reference_sha256"),str) or \
       len(payload["training_reference_sha256"])!=64 or \
       payload["training_reference_sha256"]!=model["training_data_sha256"]:
        _fail("MODEL_NOT_READY", "training_reference_changed")
    return payload


def _history(feature,stat):
    """Only P1-authored as-of rows, never target-game true exposure or result."""
    f=feature["features"]
    if f.get("interface_version") not in ("PA-NBA-P1/1","PA-NBA-P3/SYNTHETIC-1"):
        _fail("SOURCE_UNCERTIFIED","unknown_pregame_interface")
    rows=f.get("prior_player_history")
    if not isinstance(rows,list):
        _fail("INSUFFICIENT_HISTORY","history_not_provided_by_P1")
    histories=[]
    seen=set()
    target=utc(feature["input_freeze_at"]).date()
    for r in rows:
        if not isinstance(r,dict) or r.get("player_id")!=feature["player_id"] or \
           not isinstance(r.get("team_id"),str) or not r.get("team_id") or r.get("game_id")==feature["event_id"]:
            _fail("IDENTITY_UNVERIFIED","history_player_team_event_mismatch")
        if r["game_id"] in seen:
            _fail("IDENTITY_UNVERIFIED","duplicate_prior_game")
        seen.add(r["game_id"])
        if date.fromisoformat(r["game_date"]) >= target:
            _fail("SOURCE_STALE","historical_game_date_not_prior_to_forecast")
        if r.get("participation")!="played":
            if r.get("minutes") is not None or r.get("stats"):
                _fail("SOURCE_UNCERTIFIED","DNP_confused_with_scored_zero")
            continue
        minute=r.get("minutes")
        value=(r.get("stats") or {}).get(stat)
        if type(minute) not in (int,float) or not math.isfinite(minute) or \
           minute<=0 or minute>73 or type(value) is not int or value<0:
            continue
        if stat=="threes":
            total=(r.get("stats") or {}).get("three_attempts")
            if total is not None and (type(total) is not int or total<value):
                _fail("SOURCE_UNCERTIFIED","invalid_made_three_history")
        histories.append((minute,value))
    return histories


def _historical_rate(feature, stat, payload, family):
    history=_history(feature,stat)
    if len(history) < int(payload.get("min_history_games",2)):
        _fail("INSUFFICIENT_HISTORY","not_enough_played_historical_games")
    exposure=math.fsum(m for m,_ in history)
    scores=math.fsum(v for _,v in history)
    if family=="S0":
        rate=scores/exposure
    else:
        priors=payload.get("priors_per_minute",{})
        p=priors.get(stat)
        if not isinstance(p,dict) or set(p)!={"alpha","beta"}:
            _fail("MODEL_NOT_READY","fitted_rate_prior_missing")
        a,b=p["alpha"],p["beta"]
        if any(type(x) not in (float,int) or not math.isfinite(x) or x<=0 for x in (a,b)):
            _fail("MODEL_NOT_READY","invalid_prior_parameters")
        rate=(scores+a)/(exposure+b)
    median=py_stats.median(m for m,_ in history[-5:])
    return rate,median,{"played_history_games":len(history),"historical_exposure_minutes":exposure,
                        "historical_count":scores,"projected_minutes_origin":"median_last_five_prior_played_games"}


def _opportunity(feature,payload):
    p=feature["features"].get("participation_probability")
    atoms=None
    evidence="P1_SOURCE"
    if p is None:
        proposed=payload.get("opportunity",{}).get(feature["player_id"])
        if isinstance(proposed,dict) and proposed.get("attestation")=="FITTED_SOURCE_VERIFIED":
            p=proposed.get("participation_probability")
            atoms=proposed.get("minutes_law")
            evidence="MODEL_FITTED_NOT_INDEPENDENTLY_APPROVED"
    if p is None:
        _fail("PARTICIPATION_UNRESOLVED","no_supported_participation_probability")
    if type(p) not in (float,int) or not math.isfinite(p) or not 0<=p<=1:
        _fail("PARTICIPATION_UNRESOLVED","invalid_participation_probability")
    if atoms is None:
        atoms=payload.get("opportunity",{}).get(feature["player_id"],{}).get("minutes_law")
    if not isinstance(atoms,list):
        _fail("MODEL_NOT_READY","conditional_minute_model_not_fitted")
    return float(p),atoms,evidence


def _make_distribution(feature,payload,pipeline,stat,seed,n):
    family=payload["family"]
    if stat in COMBOS and pipeline!="S_O_J":
        _fail("MODEL_NOT_READY","combination_requires_single_joint_draw")
    if family=="S3":
        _fail("MODEL_NOT_READY","S3_conversion_requires_verified_three_attempt_fit")
    base_stat = stat if stat in STATS else COMBOS[stat][0]
    rate,mins,history=_historical_rate(feature,base_stat,payload,family)
    shape=None if family=="S0" else payload.get("dispersion_shapes",{}).get(base_stat)
    if family!="S0" and shape is None:
        _fail("MODEL_NOT_READY","missing_approved_dispersion_shape")
    scenario_sha=None
    if pipeline=="S_ONLY":
        d=s_control(rate,mins,family=family,shape=shape)
        bound=0.
    elif pipeline=="S_PLUS_O":
        participation,atoms,evidence=_opportunity(feature,payload)
        d,bound=opportunity_mixture(rate,atoms,participation,family=family,shape=shape)
        history["participation_basis"]=evidence
        history["nonparticipation_void_caveat"]=True
    else:
        joint_input=feature["features"].get("joint_game")
        if joint_input is None:
            _fail("MODEL_NOT_READY","P1_full_roster_not_admitted_for_J")
        bank=simulate(joint_input,payload,seed=seed,n=n,variant=payload.get("joint_variant","J1"))
        draws=player_draws(bank,feature["player_id"])
        d=empirical(combo_counts(draws,stat))
        scenario_sha=bank["scenario_sha256"]
        bound=0.
        history.update(shared_scenario_count=n,
                       scenario_sha256=scenario_sha,
                       empirical_mc_method="one_common_game_bank",
                       no_independent_game_multiplier=True)
    # For marginal distributions S-only is conditional on player appearance;
    # unresolved participation never becomes an eligible sportsbook assertion.
    return d,history,bound,scenario_sha


def generate(feature,model,sources,*,source_root,event_start_at,forecast_at,
             code_commit,run_id,season,seed,stat=None,pipeline="S_ONLY",
             quote=None,n_scenarios=5000,persist=False,storage_root="/work"):
    """Generate one P0-validated immutable research forecast or explicit abstention.

    persist=False performs full original-byte admission without touching the
    approved project store. persist=True uses P0's cross-run attested O_EXCL
    storage, never a local development directory.
    """
    def blocked(e):
        code=e.status if isinstance(e,ForecastBlocked) else "SOURCE_UNCERTIFIED"
        return Attempt(code,str(e),None,None,None,None)
    try:
        if pipeline not in PIPELINES:
            _fail("MODEL_NOT_READY","unknown_complete_pipeline")
        validate_record("PregameFeatureSnapshot",feature)
        validate_record("ModelArtifact",model)
        if feature["sport"]!="NBA":
            _fail("IDENTITY_UNVERIFIED","not_NBA")
        statistic=stat or feature["stat_key"]
        if statistic not in STATISTICS or statistic!=feature["stat_key"]:
            _fail("IDENTITY_UNVERIFIED","statistic_snapshot_mismatch")
        if not isinstance(run_id,str) or not run_id or \
           type(seed) is not int or seed<0 or type(season) is not int:
            _fail("MODEL_NOT_READY","invalid_run_seed_or_season")
        freeze=feature["input_freeze_at"]
        if not utc(freeze)<=utc(forecast_at)<utc(event_start_at):
            _fail("MISSED_FREEZE","forecast_after_tipoff_or_before_source_freeze")
        if utc(model["training_cutoff_at"])>utc(freeze):
            _fail("MODEL_NOT_READY","trained_after_input_freeze")
        _source_safe(feature,sources,source_root,freeze)
        payload=load_model(model,source_root,code_commit)
        distribution,metrics,bound,scenario_sha=_make_distribution(
            feature,payload,pipeline,statistic,seed,n_scenarios)
        from v2.p0_integrity.contracts import validate_distribution
        validate_distribution(distribution)
        mom=statistics(distribution)
        eligible=True
        reasons=[]
        if pipeline=="S_ONLY" and feature["features"].get("participation_probability") is None:
            eligible=False
            reasons=["PARTICIPATION_UNRESOLVED","CONDITIONAL_ON_PLAYING_ONLY"]
        if feature["features"].get("legal_eligibility")=="UNVERIFIED":
            eligible=False
            if "ELIGIBILITY_UNVERIFIED" not in reasons:
                reasons.append("ELIGIBILITY_UNVERIFIED")
        classification="C" if feature["reconstruction_class"]=="reconstructed" else "B" if quote else "A"
        prices=threshold(distribution,quote["line"]) if quote else None
        uncertainty={
            "research_only":True,"pipeline":pipeline,"family":payload["family"],
            "moments":mom,"history":metrics,"tail_truncation_bound":bound,
            "scenario_sha256":scenario_sha,"statistic":statistic,
            "market_contract_probabilities":prices,
            "calibration":"NOT_ESTABLISHED","numerical_precision":"full_distribution",
            "evidence_class":"synthetic_or_reconstructed" if classification=="C" else "original_source_with_separate_model_gate",
            "parameter_uncertainty":"NOT_INDEPENDENTLY_CERTIFIED",
            "input_uncertainty":"participation_and_roster_source_dependent",
        }
        forecast_id="nba-p3:"+digest({"run_id":run_id,"feature":sha256(feature),
            "model":model["artifact_sha256"],"pipeline":pipeline,"stat":statistic,
            "seed":seed,"forecast_at":forecast_at,"quote_id":quote["quote_id"] if quote else None})
        forecast=record("ForecastSnapshot",forecast_id=forecast_id,run_id=run_id,
            sport="NBA",league="NBA",season=season,event_id=feature["event_id"],
            team_id=feature["team_id"],opponent_id=feature["opponent_id"],
            player_id=feature["player_id"],stat_key=statistic,period=feature["period"],
            event_start_at=event_start_at,forecast_at=forecast_at,
            input_freeze_at=freeze,model_training_cutoff_at=model["training_cutoff_at"],
            feature_snapshot_id=feature["feature_snapshot_id"],
            model_artifact_id=model["model_artifact_id"],model_id=model["model_id"],
            model_version=model["model_version"],source_receipt_ids=sorted(x["receipt_id"] for x in sources),
            input_sha256=sha256(feature),output_sha256=sha256(distribution),
            model_code_sha=model["model_code_sha"],artifact_sha256=model["artifact_sha256"],
            seed=seed,distribution=distribution,uncertainty=uncertainty,
            abstention_reasons=reasons,admission_class=classification,
            eligible=eligible,quote_id=quote["quote_id"] if quote else None,
            line=quote["line"] if quote else None,side=quote["side"] if quote else None,
            market_probability=None)
        admission=admit_forecast(forecast,feature,model,sources,quote,source_root=source_root)
        storage=append_immutable(storage_root,"ForecastSnapshot",forecast) if persist else None
        warehouse={"forecast_id":forecast_id,"event_id":forecast["event_id"],
          "player_id":forecast["player_id"],"stat_key":statistic,
          "pipeline":pipeline,"model_id":model["model_id"],
          "input_freeze_at":freeze,"model_training_cutoff_at":model["training_cutoff_at"],
          "distribution":distribution,"moments":mom,"quantiles":mom["quantiles"],
          "scenario_sha256":scenario_sha,"evidence_class":uncertainty["evidence_class"],
          "research_only":True,"eligible":eligible,"abstention_reasons":reasons,
          "durable_forecast_written": bool(storage),
          "forecast_sha256":sha256(forecast)}
        return Attempt("FORECAST_FROZEN" if persist else "RESEARCH_DRY_RUN",None,
                       forecast,admission,warehouse,storage)
    except (ForecastBlocked,AdmissionError,FileNotFoundError,ValueError,KeyError,TypeError) as e:
        return blocked(e)


def fit_research_parameters(rows,*,cutoff_at,family,model_id,model_version,
                            training_reference_sha256,min_history_games=2):
    """Test-only full refit. Rows require explicitly released prior outcomes.

    P5 may invoke it on admitted training rows. P3 never schedules or promotes.
    """
    if family not in ("S0","S1","S2") or not rows:
        _fail("MODEL_NOT_READY","unsupported_fit")
    totals={s:[0.,0.] for s in STATS}
    seen=set()
    for r in rows:
        if set(r)!={"event_id","player_id","team_id","stat","count","minutes",
                     "event_start_at","outcome_available_at","source_sha256"}:
            _fail("SOURCE_UNCERTIFIED","training_row_schema")
        key=(r["event_id"],r["player_id"],r["stat"])
        if key in seen:
            _fail("SOURCE_UNCERTIFIED","duplicate_training_label")
        seen.add(key)
        if r["stat"] not in STATS or utc(r["event_start_at"])>=utc(r["outcome_available_at"]) or \
           utc(r["outcome_available_at"])>utc(cutoff_at):
            _fail("SOURCE_STALE","training_future_outcome")
        if type(r["count"]) is not int or r["count"]<0 or \
           type(r["minutes"]) not in (int,float) or not 0<r["minutes"]<=73:
            _fail("SOURCE_UNCERTIFIED","training_outcome_support")
        if not isinstance(r["source_sha256"],str) or len(r["source_sha256"])!=64:
            _fail("SOURCE_UNCERTIFIED","training_receipt_missing")
        totals[r["stat"]][0]+=r["count"]
        totals[r["stat"]][1]+=r["minutes"]
    priors={}
    for s,(counts,minutes) in totals.items():
        if minutes<=0:
            continue
        rate=counts/minutes
        priors[s]={"alpha":max(0.1,rate*120.),"beta":120.}
    return {"schema":MODEL_SCHEMA,"family":family,"model_id":model_id,
       "model_version":model_version,"training_cutoff_at":cutoff_at,
       "training_reference_sha256":training_reference_sha256,
       "min_history_games":min_history_games,"priors_per_minute":priors,
       "dispersion_shapes":{s:12. for s in priors},
       "opportunity":{},"joint_state":None,"joint_parameters":None,
       "update_policy":"PERIODIC_FULL_REFIT_ONLY"}


def previous_version(registry, model_id, current_version):
    """No mutation: resolve last existing frozen model from registry list."""
    entries=[r for r in registry if r.get("model_id")==model_id]
    indexes=[i for i,r in enumerate(entries) if r.get("model_version")==current_version]
    if len(indexes)!=1 or indexes[0]==0:
        _fail("MODEL_NOT_READY","rollback_target_not_found")
    return entries[indexes[0]-1]


def validate_research_model(payload, *, cutoff_at=None):
    """Structural validation only; not calibration or independent fit approval."""
    if not isinstance(payload,dict) or payload.get("schema")!=MODEL_SCHEMA or \
       payload.get("family") not in ("S0","S1","S2") or \
       not all(isinstance(payload.get(k),str) and payload[k] for k in
               ("model_id","model_version","training_cutoff_at","training_reference_sha256")):
        _fail("MODEL_NOT_READY","research_model_schema")
    if cutoff_at is not None and utc(payload["training_cutoff_at"])>utc(cutoff_at):
        _fail("MODEL_NOT_READY","model_fit_after_requested_cutoff")
    if not isinstance(payload.get("priors_per_minute"),dict) or \
       not isinstance(payload.get("dispersion_shapes"),dict):
        _fail("MODEL_NOT_READY","missing_model_coefficients")
    for value in payload["priors_per_minute"].values():
        if not isinstance(value,dict) or set(value)!={"alpha","beta"} or \
           any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in value.values()):
            _fail("NUMERICAL_FAILURE","invalid_rate_prior")
    for v in payload["dispersion_shapes"].values():
        if type(v) not in (int,float) or not math.isfinite(v) or v<=0:
            _fail("NUMERICAL_FAILURE","invalid_dispersion")
    return True


def create_research_model(payload, *, source_root, model_code_sha,
                          created_at, persist=False, storage_root="/work"):
    """Write-once model bytes; P0 registry recording only after model materializes.

    Creation requires an already known frozen training-reference SHA. Neither
    this function nor synthetic tests confer independent source admission.
    """
    validate_research_model(payload,cutoff_at=created_at)
    if not isinstance(model_code_sha,str) or len(model_code_sha)!=40 or \
       any(c not in "0123456789abcdef" for c in model_code_sha):
        _fail("MODEL_NOT_READY","invalid_code_commit")
    from .distributions import canonical
    raw=canonical(payload)
    artifact_sha=hashlib.sha256(raw).hexdigest()
    root=Path(source_root).resolve(strict=True)
    relative="models/nba_p3/"+artifact_sha+".json"
    target=root/relative
    if target.exists() and (target.is_symlink() or target.read_bytes()!=raw):
        _fail("MODEL_NOT_READY","model_artifact_conflict")
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True)
        # If a concurrent writer wins, verify original bytes rather than clobber.
        try:
            with target.open("xb") as file:
                file.write(raw)
                file.flush()
                import os
                os.fsync(file.fileno())
        except FileExistsError:
            if target.is_symlink() or target.read_bytes()!=raw:
                _fail("MODEL_NOT_READY","model_artifact_concurrent_conflict")
    if not target.resolve(strict=True).is_relative_to(root) or target.read_bytes()!=raw:
        _fail("MODEL_NOT_READY","model_artifact_changed_after_write")
    model=record("ModelArtifact",
      model_artifact_id="nba-p3-model:"+artifact_sha,
      model_id=payload["model_id"],model_version=payload["model_version"],
      model_code_sha=model_code_sha,artifact_sha256=artifact_sha,
      artifact_path=relative,
      training_data_sha256=payload["training_reference_sha256"],
      training_cutoff_at=payload["training_cutoff_at"],
      created_at=created_at,training_scope="research_fit_no_auto_promotion",
      feature_schema_id="PA-NBA-P1/1")
    published=append_immutable(storage_root,"ModelArtifact",model) if persist else None
    return {"record":model,"persisted":published,"research_only":True}
