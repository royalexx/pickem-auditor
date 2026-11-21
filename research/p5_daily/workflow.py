"""P5 settlement pipeline: consumes frozen P0 receipts, never fetches pregame data.

Official results must be supplied by the existing independent outcome collectors,
with raw source receipts. No bookmaker outcome can substitute for the official
full-count distribution outcome. All outputs are research-only.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import math

from v2.p0_integrity.contracts import (
    admit_forecast, admit_settlement, canonical_bytes, record, sha256, utc,
    validate_record, AdmissionError,
)
from v2.p0_integrity.storage import (
    attest_project_storage, verify_immutable_record, append_immutable,
)
from .scoring import ScoreError, score_count, score_contract, _utc, digest
from .registry import (
    _write_once, _secure_root, admit_training_observation,
    register_model, POLICY,
)

STAT_BASE={"pr":("points","rebounds"),"pa":("points","assists"),
           "ra":("rebounds","assists"),
           "pra":("points","rebounds","assists")}
RUN_SCHEMA="PA-P5-SETTLEMENT/1"
FINAL={"FINAL","CORRECTED"}

def _need(ok,code):
    if not ok:
        raise ScoreError(code)

def _iso(d):
    return d.astimezone(timezone.utc).isoformat().replace("+00:00","Z")

def derive_nba_combinations(observations):
    """Same official player-game evidence, no independent component draws."""
    by={}
    for o in observations:
        validate_record("OutcomeRecord",o)
        _need(o["sport"]=="NBA","NBA_ONLY")
        k=o["stat_key"]
        _need(k in ("points","rebounds","assists","threes"),"NBA_BASE_STAT_ONLY")
        _need(k not in by,"DUPLICATE_OFFICIAL_BASE_STAT")
        by[k]=o
    if not by:
        return {}
    ref=next(iter(by.values()))
    for x in by.values():
        for key in ("event_id","player_id","team_id","period","official_source_sha256",
                    "official_source_receipt_id","result_version","status",
                    "official_result_available_at","participation"):
            _need(x[key]==ref[key],"NBA_COMBO_OFFICIAL_SOURCE_MISMATCH:"+key)
    if ref["status"] not in FINAL or ref["participation"]!="PLAYED":
        return {}
    result={}
    for name,parts in STAT_BASE.items():
        if all(p in by and type(by[p]["actual_value"]) is int for p in parts):
            result[name]=sum(by[p]["actual_value"] for p in parts)
    return result

def _classification(f):
    if f["admission_class"]=="C":
        return "RECONSTRUCTED_HISTORICAL"
    return "ORIGINAL_PREGAME_VERIFIED"

def load_frozen_p0(*, forecast_sha, feature_sha, model_sha, source_shas,
                   quote_sha=None, source_root="/work"):
    """Canonical P0 reader: exact immutable paths AND original bytes verified."""
    attest_project_storage(source_root)
    load=lambda kind,hash:verify_immutable_record(source_root,kind,hash)
    forecast=load("ForecastSnapshot",forecast_sha)
    feature=load("PregameFeatureSnapshot",feature_sha)
    model=load("ModelArtifact",model_sha)
    sources=[load("SourceReceipt",s) for s in source_shas]
    quote=load("MarketQuote",quote_sha) if quote_sha is not None else None
    proof=admit_forecast(forecast,feature,model,sources,quote,
                         source_root=source_root)
    return {"forecast":forecast,"feature":feature,"model":model,
            "sources":sources,"quote":quote,"admission":proof,
            "original_forecast_sha256":forecast_sha}

def load_official_p0(*, outcome_sha, source_shas,source_root="/work"):
    attest_project_storage(source_root)
    outcome=verify_immutable_record(source_root,"OutcomeRecord",outcome_sha)
    sources=[verify_immutable_record(source_root,"SourceReceipt",s)
             for s in source_shas]
    return {"outcome":outcome,"sources":sources,"outcome_sha256":outcome_sha}

def _official_status(outcome,run_at):
    if outcome is None:
        return "OFFICIAL_RESULT_MISSING"
    validate_record("OutcomeRecord",outcome)
    if outcome["status"]=="PENDING":
        return "PENDING_FINAL"
    if _utc(outcome["official_result_available_at"])>_utc(run_at):
        return "PENDING_FINAL"
    if outcome["participation"]=="UNKNOWN":
        return "NOT_SCOREABLE"
    if outcome["participation"]=="DNP":
        return "DNP_EXCLUDED"
    if outcome["actual_value"] is None:
        return "OFFICIAL_RESULT_MISSING"
    if type(outcome["actual_value"]) is not int or outcome["actual_value"]<0:
        return "STAT_DEFINITION_MISMATCH"
    return "SETTLED"

def _valid_contract_terms(quote):
    """No inferred bet terms. This is separate from statistical scoring."""
    if quote is None or quote.get("quote_kind")!="real" or not quote.get("accepted"):
        return False
    terms=quote.get("terms",{})
    return (isinstance(terms,dict) and
            all(k in terms for k in ("stat_period","overtime_rule",
                                    "dnp_policy","partial_game_policy")) and
            terms["stat_period"]=="full" and
            terms["overtime_rule"]=="included" and
            terms["dnp_policy"] in ("void","settle") and
            terms["partial_game_policy"] in ("settle","void"))

def _match(f,o):
    for k in ("sport","event_id","team_id","player_id","stat_key","period"):
        if f[k]!=o[k]:
            raise ScoreError("IDENTITY_MISMATCH:"+k)

def settle(frozen, official, *, source_root, receipt_root,
           run_at, prior_settlement=None, evidence_type="original"):
    """Admit both immutable original source and independent official outcome.

    receipt_root is a P5 isolated research root (not a second P0 authority).
    Results based on synthetic fixtures are permanently tagged as such.
    """
    root=_secure_root(receipt_root)
    _utc(run_at)
    f=frozen["forecast"]
    feature=frozen["feature"]
    model=frozen["model"]
    quote=frozen.get("quote")
    admission=admit_forecast(f,feature,model,frozen["sources"],quote,
                             source_root=source_root)
    _need(evidence_type in ("original","synthetic_fixture","reconstructed"),
          "EVIDENCE_LABEL_REQUIRED")
    if evidence_type=="original":
        _need(f["admission_class"] in ("A","B") and
              feature["reconstruction_class"]=="original",
              "NOT_ORIGINAL_PREGAME")
    if evidence_type=="synthetic_fixture":
        classification="SYNTHETIC_ENGINEERING_ONLY"
    elif f["admission_class"]=="C" or evidence_type=="reconstructed":
        classification="RECONSTRUCTED_HISTORICAL"
    else:
        classification=_classification(f)
    if _utc(run_at)<=_utc(f["event_start_at"]):
        raise ScoreError("RESULT_NOT_YET_AVAILABLE")
    o=official.get("outcome") if official else None
    status=_official_status(o,run_at)
    if status not in ("SETTLED","DNP_EXCLUDED"):
        return {"status":status,"forecast_id":f["forecast_id"],
                "classification":classification,"training_update":"BLOCKED"}
    _match(f,o)
    if f["eligible"] is not True or f["abstention_reasons"]:
        return {"status":"FORECAST_UNCERTIFIED","forecast_id":f["forecast_id"],
                "classification":classification}
    official_sources=official.get("sources") or []
    stat=None
    contract=None
    actual=o["actual_value"]
    if status=="SETTLED":
        stat=score_count(f["distribution"],actual,forecast_id=f["forecast_id"])
        if f["admission_class"]=="B" and _valid_contract_terms(quote):
            if quote["terms"]["partial_game_policy"]=="void" and                not official.get("full_game_participation_verified",False):
                contract=None
            else:
                contract=score_contract(f["distribution"],actual,quote)
    n=1 if prior_settlement is None else prior_settlement["settlement_version"]+1
    previous=None if prior_settlement is None else prior_settlement["settlement_id"]
    if prior_settlement is not None:
        _need(prior_settlement["forecast_id"]==f["forecast_id"],
              "CORRECTION_FORECAST_MISMATCH")
        _need(o["status"]=="CORRECTED","UNJUSTIFIED_SETTLEMENT_SUPERSESSION")
    if status=="DNP_EXCLUDED":
        # A research distribution can record DNP exclusion. A market-linked
        # VOID requires verified DNP void rules, otherwise keep pending.
        disposition=("VOID" if f["admission_class"]=="A" or
                     _valid_contract_terms(quote) and quote["terms"]["dnp_policy"]=="void"
                     else "PENDING")
    elif contract is None:
        disposition="SCORED"
    elif contract["observed"]=="push":
        disposition="PUSH"
    elif contract["observed"]==f["side"]:
        disposition="HIT"
    else:
        disposition="MISS"
    settlement_id="p5:"+digest({"forecast":f["forecast_id"],"outcome":o["outcome_id"],
        "revision":n,"source":o["official_source_sha256"]})
    computation=sha256({"forecast_sha256":sha256(f),"outcome_sha256":sha256(o),
                        "statistics":stat,"contract":contract,"status":status})
    s=record("SettlementRecord",settlement_id=settlement_id,
             forecast_id=f["forecast_id"],outcome_id=o["outcome_id"],
             quote_id=f["quote_id"],contract_id=quote["contract_id"] if quote else None,
             settled_at=run_at,disposition=disposition,
             settlement_policy="research_statistic_independent_contract",
             settlement_version=n,supersedes_id=previous,
             source_receipt_ids=[o["official_source_receipt_id"]],
             computation_sha256=computation)
    proof=admit_settlement(s,f,o,quote,
                           official_sources=official_sources,source_root=source_root)
    p0_receipt=None
    # P0 canonical record registration is intentionally caller-controlled:
    # P5 never writes to live shared store in an isolated synthetic test.
    if str(receipt_root)=="/work/research/p5_daily":
        p0_receipt=append_immutable("/work","SettlementRecord",s)
    result={"schema":RUN_SCHEMA,"forecast_id":f["forecast_id"],
            "sport":f["sport"],"event_id":f["event_id"],
            "player_id":f["player_id"],"stat_key":f["stat_key"],
            "period":f["period"],"event_start_at":f["event_start_at"],"model_id":f["model_id"],
            "model_version":f["model_version"],
            "complete_pipeline_id":f["uncertainty"].get("complete_pipeline_id"),
            "outcome_id":o["outcome_id"],"outcome_available_at":o["official_result_available_at"],
            "participation":o["participation"],"classification":classification,
            "statistical_status":status,
            "market_contract_status":("VOID" if disposition=="VOID" else
                   disposition if contract is not None else "NOT_SCOREABLE"),
            "statistical_score":stat,"contract_score":contract,
            "original_forecast_sha256":sha256(f),
            "original_model_artifact_sha256":f["artifact_sha256"],
            "original_source_sha256s":[x["source_sha256"] for x in frozen["sources"]],
            "official_source_sha256":o["official_source_sha256"],
            "settlement_record":s,"admission_sha256":proof["settlement_sha256"],
            "p0_receipt":p0_receipt,"research_only":True}
    r=_write_once(root,
       f"settlements/{f['sport'].lower()}/{settlement_id.replace(':','_')}.json",result)
    result["p5_receipt"]=r
    return result

def eligible_training_row(settlement, official, frozen, *,cutoff):
    """Official completed-game row can be trained after result release.

    This independent row is not the market result; DNP is never represented
    with count zero. Exposure from raw official box can be attached later
    only by an independently certified official extractor.
    """
    _need(settlement["statistical_status"]=="SETTLED",
          "SETTLEMENT_NOT_TRAINABLE")
    _need(settlement["classification"]=="ORIGINAL_PREGAME_VERIFIED",
          "RECONSTRUCTED_OR_SYNTHETIC_TRAINING_FORBIDDEN")
    o=official["outcome"]
    _need(_utc(o["official_result_available_at"])<=_utc(cutoff),
          "OFFICIAL_RESULT_AFTER_TRAINING_CUTOFF")
    return {"sport":o["sport"],"event_id":o["event_id"],
            "player_id":o["player_id"],"team_id":o["team_id"],
            "stat_key":o["stat_key"],"official_value":o["actual_value"],
            "participation":o["participation"],
            "official_source_sha256":o["official_source_sha256"],
            "official_result_available_at":o["official_result_available_at"],
            "event_start_at":frozen["forecast"]["event_start_at"],
            "training_admitted":True,"official_outcome_id":o["outcome_id"],
            "exposure":{}}

def execute_model_update(root, *,family, model_id, sport, pipeline_id,
                         state_update, training_rows, cutoff_at, created_at,
                         code_commit, seed, diagnostics,
                         previous_version=None, fit_callback=None,
                         validation_callback=None):
    """No callback means NO_UPDATE, not successful learning.

    The callback is the P3/P4-owner-approved algorithm. P5 never substitutes
    a made-up count rate, Gamma rule, NBA S/O/J fit, or new NB2 parameter.
    """
    permitted=POLICY.get(family,set())
    if state_update not in permitted:
        return {"status":"BLOCKED","reason":"UPDATE_NOT_APPROVED_FOR_FAMILY"}
    if state_update in ("PREDICTION_ONLY","NO_ELIGIBLE_UPDATE","BLOCKED"):
        return {"status":"UNCHANGED","reason":state_update}
    if not training_rows:
        return {"status":"UNCHANGED","reason":"NO_ELIGIBLE_UPDATE"}
    if fit_callback is None:
        return {"status":"BLOCKED","reason":"OWNER_MODEL_UPDATE_INTERFACE_NOT_INSTALLED"}
    if validation_callback is None:
        return {"status":"BLOCKED","reason":"INDEPENDENT_NUMERICAL_VALIDATOR_NOT_CONFIGURED"}
    for row in training_rows:
        _need(row.get("training_admitted") is True and
              _utc(row["official_result_available_at"])<=_utc(cutoff_at),
              "UNVERIFIED_OR_FUTURE_TRAINING_ROW")
    try:
        new_state=fit_callback(training_rows,cutoff_at)
        if not isinstance(new_state,dict) or not new_state:
            raise ScoreError("OWNER_FIT_RETURNED_EMPTY_STATE")
        if validation_callback(new_state, training_rows, cutoff_at) is not True:
            raise ScoreError("OWNER_MODEL_VALIDATION_FAILED")
        return register_model(root,model_id=model_id,family=family,
               pipeline_id=pipeline_id,sport=sport,state=new_state,
               parent_version=previous_version,training_rows=training_rows,
               cutoff_at=cutoff_at,created_at=created_at,code_commit=code_commit,
               update_mode=state_update,seed=seed,diagnostics=diagnostics,
               passed_validation=True)
    except Exception as ex:
        return {"status":"BLOCKED","reason":type(ex).__name__+":"+str(ex)}

def run_isolated_daily(*, nba_cases, nhl_cases,source_root,receipt_root,run_at):
    """Idempotent per-sport loop; one sport's failure cannot stop the other."""
    groups={"NBA":nba_cases,"NHL":nhl_cases}
    report={"schema":"PA-P5-DAILY/1","run_at":run_at,"research_only":True,"sports":{}}
    for sport,cases in groups.items():
        out=[]
        for c in cases:
            try:
                f=c["frozen"]["forecast"]
                _need(f["sport"]==sport,"CROSS_SPORT_FORECAST_INPUT")
                outcome=settle(c["frozen"],c.get("official"),source_root=source_root,
                    receipt_root=receipt_root,run_at=run_at,
                    evidence_type=c.get("evidence_type","synthetic_fixture"),
                    prior_settlement=c.get("prior_settlement"))
                out.append({"forecast_id":f["forecast_id"],"status":outcome["status"]
                     if "status" in outcome else outcome["statistical_status"],
                     "p5_receipt":outcome.get("p5_receipt"),"classification":
                     outcome.get("classification")})
            except Exception as e:
                out.append({"forecast_id":c.get("frozen",{}).get("forecast",{}).get("forecast_id"),
                            "status":"BLOCKED","error":type(e).__name__+":"+str(e)})
        report["sports"][sport]={"total":len(cases),"rows":out,
            "settled":sum(z["status"]=="SETTLED" for z in out),
            "blocked":sum(z["status"]=="BLOCKED" for z in out)}
    return report
