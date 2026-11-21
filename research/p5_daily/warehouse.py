"""Canonical P0 daily-ledger consumption, independent outcome vault and scorecards.

No HTTP ingestion, duplicate NBA/NHL collector, model refit, or scheduler.
This module may consume only original P0 committed records, preserving every
rejected/incomplete row and never reconstructing original forecasts.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

from v2.p0_integrity.contracts import (
    SCHEMAS, AdmissionError, validate_record, verify_source_bytes,
    admit_forecast, utc, sha256,
)
from v2.p0_integrity.storage import (
    NAMESPACES, attest_project_storage, verify_immutable_record,
)
from .scoring import ScoreError, _utc, paired_differences, digest
from .workflow import (
    settle, eligible_training_row, execute_model_update,
)
from .registry import (
    _secure_root, _write_once, admit_training_observation,
    select_for_forecast,
)

P0_STORE="research/p0_integrity_store"
P5_STORE="research/p5_daily"

def _need(ok, code):
    if not ok:
        raise ScoreError(code)

def _source_receipt_key(rec):
    return rec[SCHEMAS[rec["record_type"]][0]]

def enumerate_p0(root, kind, *, max_files=100000):
    """Verify the original P0 content-addressed file and immutable ID claim."""
    _need(kind in NAMESPACES, "UNREGISTERED_P0_KIND")
    attest_project_storage(root)
    directory=Path(root)/P0_STORE/NAMESPACES[kind]
    if not directory.exists():
        return {},[]
    files=sorted(directory.glob("*.json"))
    _need(len(files)<=max_files,"P0_WAREHOUSE_CAP_EXCEEDED")
    lookup={}
    rejects=[]
    for path in files:
        try:
            _need(not path.is_symlink() and len(path.stem)==64,
                  "UNSAFE_P0_RECORD_FILENAME")
            record=verify_immutable_record(root,kind,path.stem)
            ident=_source_receipt_key(record)
            _need(ident not in lookup,"DUPLICATE_P0_LOGICAL_ID")
            lookup[ident]={"record":record,"sha256":path.stem,
                           "relative_path":str(path.relative_to(root))}
        except Exception as ex:
            rejects.append({"path":str(path.relative_to(root)),
               "reason":type(ex).__name__+":"+str(ex)})
    return lookup,rejects

def recover_frozen_forecasts(root="/work", *, sport=None, max_files=100000):
    """No inferred source/model indexes; all referenced originals must exist."""
    _need(sport in (None,"NBA","NHL"),"UNKNOWN_SPORT")
    warehouse={}
    corrupt=[]
    for kind in ("SourceReceipt","PregameFeatureSnapshot","ModelArtifact",
                 "ForecastSnapshot","MarketQuote"):
        warehouse[kind],bad=enumerate_p0(root,kind,max_files=max_files)
        corrupt.extend({"record_type":kind,**x} for x in bad)
    checked=[]
    rejected=[]
    for fid,wrap in sorted(warehouse["ForecastSnapshot"].items()):
        f=wrap["record"]
        if sport is not None and f["sport"]!=sport:
            continue
        try:
            feature=warehouse["PregameFeatureSnapshot"][f["feature_snapshot_id"]]
            model=warehouse["ModelArtifact"][f["model_artifact_id"]]
            sources=[warehouse["SourceReceipt"][r] for r in f["source_receipt_ids"]]
            quote=(warehouse["MarketQuote"][f["quote_id"]]
                   if f["admission_class"]=="B" else None)
            frozen={"forecast":f,"feature":feature["record"],
                    "model":model["record"],
                    "sources":[s["record"] for s in sources],
                    "quote":quote["record"] if quote else None,
                    "original_forecast_sha256":wrap["sha256"]}
            admitted=admit_forecast(frozen["forecast"],frozen["feature"],
                           frozen["model"],frozen["sources"],
                           frozen["quote"],source_root=root)
            _need(admitted["snapshot_sha256"]==wrap["sha256"],
                  "P0_FROZEN_HASH_DISAGREEMENT")
            checked.append(frozen)
        except Exception as ex:
            rejected.append({"forecast_id":fid,"forecast_sha256":wrap["sha256"],
                "reason":type(ex).__name__+":"+str(ex)})
    return {"accepted":checked,"rejected":rejected,
            "corrupt_or_incomplete_p0_records":corrupt,
            "n_original_prospective":sum(x["forecast"]["admission_class"] in
                   ("A","B") for x in checked),
            "n_retrospective":sum(x["forecast"]["admission_class"]=="C"
                   for x in checked),
            "n_forecast_rejections":len(rejected)}

def recover_official_outcomes(root="/work", *, max_files=100000):
    """Official vault is independent of pregame archive and has own hashes."""
    outcomes,bad=enumerate_p0(root,"OutcomeRecord",max_files=max_files)
    sources,source_bad=enumerate_p0(root,"SourceReceipt",max_files=max_files)
    valid={}
    for ident,wrapped in sorted(outcomes.items()):
        row=wrapped["record"]
        try:
            official=sources[row["official_source_receipt_id"]]["record"]
            _need(official["source_sha256"]==row["official_source_sha256"],
                  "OFFICIAL_RAW_SHA_MISMATCH")
            verify_source_bytes(official,root)
            key=tuple(row[k] for k in
                        ("sport","event_id","team_id","player_id","stat_key","period"))
            valid.setdefault(key,[]).append({"outcome":row,"sources":[official],
                                             "raw_source_sha256":official["source_sha256"]})
        except Exception as ex:
            bad.append({"outcome_id":ident,"reason":type(ex).__name__+":"+str(ex)})
    for key,records in valid.items():
        records.sort(key=lambda x:(x["outcome"]["official_result_available_at"],
                                   x["outcome"]["outcome_id"]))
        if len(records)>1:
            for i in range(1,len(records)):
                if records[i]["outcome"]["status"]!="CORRECTED":
                    bad.append({"outcome_id":records[i]["outcome"]["outcome_id"],
                                "reason":"MISSING_OFFICIAL_CORRECTION_REVISION"})
    return {"by_stat_identity":valid,"rejected":bad,"source_rejections":source_bad}

def choose_official(frozen, official_vault, *, run_at):
    f=frozen["forecast"]
    k=tuple(f[x] for x in ("sport","event_id","team_id","player_id","stat_key","period"))
    candidates=official_vault["by_stat_identity"].get(k,[])
    prior=[o for o in candidates if
           _utc(o["outcome"]["official_result_available_at"])<=_utc(run_at)]
    if not prior:
        return None
    row=prior[-1]
    # Corrections must explicitly preserve their predecessor and no earlier
    # evidence may be replaced with a reissued source record.
    if len(prior)>1 and row["outcome"]["status"]!="CORRECTED":
        return None
    return row

def scorecard(rows):
    """One observed player game per row, report event/date group denominators."""
    scores=[r for r in rows if r.get("statistical_status")=="SETTLED"
        and isinstance(r.get("statistical_score"),dict)]
    grouped=defaultdict(list)
    for r in scores:
        grouped[r["sport"],r["model_id"],r["stat_key"]].append(r)
    output=[]
    for (sport,model,stat),records in sorted(grouped.items()):
        ps=[r["statistical_score"] for r in records]
        output.append({"sport":sport,"model_id":model,"stat_key":stat,
           "n_player_game_observations":len(records),
           "n_distinct_games":len({r["event_id"] for r in records}),
           "n_distinct_dates":len({r["event_start_at"][:10]
                                   for r in records}),
           "mean_crps":sum(x["crps"] for x in ps)/len(ps),
           "mean_nlpd":sum(x["nlpd"] for x in ps)/len(ps),
           "mae":sum(x["mae"] for x in ps)/len(ps),
           "rmse":(sum(x["squared_error"] for x in ps)/len(ps))**.5,
           "signed_bias":sum(x["signed_bias"] for x in ps)/len(ps),
           "predicted_zero_frequency":sum(x["p_zero"] for x in ps)/len(ps),
           "realized_zero_frequency":sum(x["observed_zero"] for x in ps)/len(ps),
           "interval_coverage":sum(x["interval_covered"] for x in ps)/len(ps),
           "research_only":True})
    return output

def run_morning_from_frozen_p0(*,root="/work",run_at,
                              permit_research_writes=False,
                              update_adapters=None):
    """Manual P5 preflight/integration. NO active schedule mutation.

    This is intentionally not a second official-result acquisition route.
    The main morning owner must first archive original official outcome bytes,
    their SourceReceipts and P0 OutcomeRecords into the independent vault.
    """
    _utc(run_at)
    storage=attest_project_storage(root)
    frozen=recover_frozen_forecasts(root)
    official=recover_official_outcomes(root)
    if not permit_research_writes:
        return {"status":"READ_ONLY_P0_INVENTORY","storage":storage,
                "original_forecast_count":frozen["n_original_prospective"],
                "reconstructed_count":frozen["n_retrospective"],
                "forecast_rejections":frozen["rejected"],
                "record_rejections":frozen["corrupt_or_incomplete_p0_records"],
                "official_rejections":official["rejected"],
                "model_updates":"DISABLED",
                "automation_changes":False}
    _need(root=="/work","NO_NONATTESTED_LIVE_STORAGE")
    outroot=Path(root)/P5_STORE
    outroot.mkdir(exist_ok=True,parents=True)
    report={"schema":"PA-P5-DAILY-LEDGER/1","run_at":run_at,
        "research_only":True,"automation_changes":False,
        "forecast_inventory":{"admitted":len(frozen["accepted"]),
              "rejected":frozen["rejected"],"record_rejects":
              frozen["corrupt_or_incomplete_p0_records"]},
        "official_inventory":{"rejections":official["rejected"]},
        "sports":{},"update_status":"NO_OWNER_CALLBACK_CONFIGURED"}
    for sport in ("NBA","NHL"):
        cases=[r for r in frozen["accepted"] if r["forecast"]["sport"]==sport]
        completed=[]
        attempts=[]
        training=[]
        for b in cases:
            f=b["forecast"]
            if _utc(f["event_start_at"])>=_utc(run_at):
                attempts.append({"forecast_id":f["forecast_id"],"status":"PENDING_FINAL"})
                continue
            official_record=choose_official(b,official,run_at=run_at)
            if official_record is None:
                attempts.append({"forecast_id":f["forecast_id"],
                                 "status":"OFFICIAL_RESULT_MISSING"})
                continue
            try:
                res=settle(b,official_record,source_root=root,receipt_root=outroot,
                     run_at=run_at,evidence_type=("reconstructed" if
                      f["admission_class"]=="C" else "original"))
                attempts.append({"forecast_id":f["forecast_id"],
                    "status":res.get("statistical_status",res.get("status"))})
                if "statistical_status" not in res:
                    continue
                completed.append(res)
                if (res["statistical_status"]=="SETTLED" and
                    res["classification"]=="ORIGINAL_PREGAME_VERIFIED"):
                    obs=eligible_training_row(res,official_record,b,cutoff=run_at)
                    admit_training_observation(outroot,obs,effective_cutoff=run_at)
                    training.append(obs)
            except Exception as ex:
                attempts.append({"forecast_id":f["forecast_id"],"status":"BLOCKED",
                                 "reason":type(ex).__name__+":"+str(ex)})
        report["sports"][sport]={"n_candidate_forecasts":len(cases),
                   "n_settlement_receipts":len(completed),
                   "n_admitted_training_observations":len(training),
                   "attempts":attempts,"scores":scorecard(completed),
                   "owner_updates": "BLOCKED_BY_MODEL_INTERFACE" if
                                  update_adapters is None else "UNEXECUTED_PENDING_AUDIT"}
    return report
