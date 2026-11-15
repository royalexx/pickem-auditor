"""Independent byte-level and numerical WS4 ORIGINAL contract verifier.

Does not import, call or rely on joint_simulator.py. Only source/prediction bytes
and first-party arithmetic. Shadow provenance integrity != predictive calibration.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import pathlib
from collections import Counter

SOURCE_SHA = "5e17ff057f528a1ee049d38cde80aa3ce295eec15fff7c051ab37508157a5e71"
EXPECTED_MODELS = {"J1", "J2"}


class AuditFailure(ValueError):
    pass


def compact(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def h(data):
    return hashlib.sha256(data).hexdigest()


def timestamp(s):
    value=dt.datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if value.tzinfo is None:
        raise AuditFailure("NAIVE_TIME")
    return value.astimezone(dt.timezone.utc)


def require(test, label):
    if not test:
        raise AuditFailure(label)


def verify(raw_file:pathlib.Path, raw_ws1_file:pathlib.Path):
    original = raw_file.read_bytes()
    digest = h(original)
    require(raw_file.stem == digest, "IMMUTABLE_FORECAST_FILENAME_CONTENT_HASH")
    forecast = json.loads(original)
    require(original == compact(forecast)+b"\n", "NONCANONICAL_FORECAST_BYTES")
    require(forecast["schema"] == "PA_WS4_REAL_ORIGINAL_CONTRACT_V03_v1", "FORECAST_SCHEMA")
    require(forecast["canonical_ws1_sha256"] == SOURCE_SHA, "WRONG_WS1_PIN")
    source_bytes = raw_ws1_file.read_bytes()
    require(h(source_bytes) == SOURCE_SHA, "WS1_SOURCE_BYTES_MISMATCH")
    ws1 = json.loads(source_bytes)
    require(len(ws1["candidates"]) == 1845 and len(forecast["original_denominator_ledger"]) == 1845,
            "ORIGINAL_DENOMINATOR_MISMATCH")
    require(forecast["data_receipts_missing"] is False if "data_receipts_missing" in forecast else True,
            "MISSING_SOURCE_DATA_RECEIPT")
    inp = forecast["input_packet"]
    meta = forecast["model_output"]
    require(inp["source_certification_status"] == "SOURCE_CERTIFIED_RESEARCH_SHADOW", "SOURCE_LAUNDERED")
    require(meta["classification"] == "UNCERTIFIED_SHADOW", "FORECAST_LAUNDERED")
    require(forecast["research_only"] is True and forecast["production_promotion"] is False,
            "SHADOW_RELEASE_GATE")
    reconstructed = {k:v for k,v in inp.items() if k != "input_manifest_sha256"}
    require(h(compact(reconstructed)) == inp["input_manifest_sha256"], "CHANGED_MODEL_INPUT")
    require(meta["source_input_sha256"] == inp["input_manifest_sha256"], "INPUT_LINK_BROKEN")
    require(h(compact({k:v for k,v in meta.items() if k!="output_sha256"})) == meta["output_sha256"],
            "MODEL_OUTPUT_HASH_BROKEN")
    model_date = timestamp(inp["model_training_cutoff_at"])
    freeze = timestamp(inp["input_freeze_at"])
    created = timestamp(meta["forecast_created_at"])
    kickoff = timestamp(inp["events"][0]["event_start_at"])
    require(model_date <= freeze <= created < kickoff, "POSTKICKOFF_OR_TRAINING_LEAKAGE")
    require(len(inp["events"])==1 and len(inp["contracts"])==1, "CANARY_SCOPE_CHANGED")
    require(len({x["event_id"] for x in inp["events"]})==1, "EVENT_DUPLICATE")
    for event in inp["events"]:
        for kind in ("source_receipts","scenario_source_receipts"):
            require(event.get(kind), "MISSING_"+kind)
            for r in event[kind]:
                require(len(str(r.get("sha256",""))) == 64 and r.get("source_uri"), "MALFORMED_SOURCE_RECEIPT")
                require(timestamp(r["available_at"])<=freeze, "POSTFREEZE_SOURCE")
    c=inp["contracts"][0]
    selected = [x for x in ws1["candidates"] if x["candidate_id"] == c["contract_id"]]
    require(len(selected)==1, "WS1_ORIGINAL_CONTRACT_ID_NOT_UNIQUE")
    orig=selected[0]
    require(orig["source_certified"] and orig["research_shadow_eligible"], "INELIGIBLE_ORIGINAL_QUOTE")
    for old,new in (("quote_id","original_quote_id"),("event_id","event_id"),
                    ("player_id","player_id"),("team","team_id"),
                    ("line","line"),("period","period"),("source_sha256","original_quote_receipt_sha256")):
        require(orig[old]==c[new], "ALTERED_ORIGINAL_CONTRACT:"+old)
    require(timestamp(orig["source_received_at"]) == timestamp(c["original_quote_at"]),
            "QUOTE_TIME_IDENTITY_CHANGED")
    require(timestamp(c["original_quote_at"])<=freeze, "QUOTE_NOT_AVAILABLE")
    require(orig["stat"]=="pass attempts" and c["stat_key"]=="pass_attempts", "STAT_IDENTITY_MISMATCH")
    require(orig["position"]=="QB" and orig["eligibility_status"]=="EXPECTED_STARTER_SOURCE_BACKED",
            "EXPECTED_QB_PROVENANCE_MISSING")
    for t in inp["events"][0]["teams"]:
        require(t["starter_status"]=="EXPECTED_STARTER_SOURCE_BACKED" and
                isinstance(t["starter_source_receipts"],list) and t["starter_source_receipts"],
                "GAME_DAY_STARTER_FABRICATED")
        require(all(math.isfinite(t[k]) for k in ("plays_mean","pass_rate","sack_rate","starter_attempt_share")),
                "INVALID_PARAMETER_NUMBER")
        require(t["plays_mean"] > 0 and 0 <= t["pass_rate"] < 1 and
                0 <= t["sack_rate"] < 1 and 0 < t["starter_attempt_share"] <= 1,
                "OUT_OF_SUPPORT_PARAMETER")
        require(len(t["players"])==1 and t["players"][0]["role"]=="QB", "UNMODELED_PLAYER_PRESENT")
    original_ids=[x["candidate_id"] for x in ws1["candidates"]]
    ledger_ids=[x["candidate_id"] for x in forecast["original_denominator_ledger"]]
    require(ledger_ids==original_ids, "LEDGER_ORIGINAL_ORDER_OR_IDENTITY_CHANGED")
    require(sum(x["status"]=="READY_J1_ONLY" for x in forecast["original_denominator_ledger"])==1,
            "CANARY_ELIGIBILITY_COUNT_CHANGED")
    require(set(forecast["abstained_models"])=={"J3","J4"}, "MISSING_J3_J4_ABSTENTION")
    rows=meta["contracts"]
    require(len(rows)==2 and {x["model_id"] for x in rows}==EXPECTED_MODELS, "MODEL_COVERAGE_CHANGED")
    for row in rows:
        require(row["status"]=="FORECAST" and row["classification"]=="UNCERTIFIED_SHADOW",
                "MODEL_PROMOTED_OR_NOT_PROSPECTIVE")
        require(row["draws"]==4096, "SIMULATION_DRAW_COUNT_CHANGED")
        for field in ("event_id","player_id","team_id","line","period","stat_key",
                      "contract_id","original_quote_id","original_quote_at","original_quote_receipt_sha256"):
            require(row[field]==c[field], "SIMULATOR_CHANGED_ORIGINAL_"+field)
        ps=[row[k] for k in ("p_over","p_under","p_push")]
        require(all(math.isfinite(x) and 0<=x<=1 for x in ps), "PROBABILITY_SUPPORT_FAILURE")
        require(abs(sum(ps)-1)<=1e-12, "PROBABILITY_COMPLEMENTARITY_FAILURE")
        require(abs(row["mc_se_over"]-math.sqrt(ps[0]*(1-ps[0])/row["draws"])) <= 1e-12,
                "MONTE_CARLO_SE_INCONSISTENT")
        require(row["variance"]>=0 and math.isfinite(row["mean"]), "DISTRIBUTION_MOMENT_FAILURE")
        require(row["q05"]<=row["q50"]<=row["q95"], "QUANTILE_ORDER_FAILURE")
        require(row.get("pmf"), "MISSING_COUNT_PMF")
        weights={int(k):float(v) for k,v in row["pmf"].items()}
        require(abs(sum(weights.values())-1)<1e-12, "PMF_MASS_FAILURE")
        require(all(v>=0 and k>=0 for k,v in weights.items()),"PMF_SUPPORT_FAILURE")
        for q,k in zip(ps,("over","under","push")):
            calc=sum(v for n,v in weights.items()
                     if (n>row["line"] if k=="over" else n<row["line"] if k=="under" else n==row["line"]))
            require(abs(calc-q)<1e-12, "PMF_CDF_INCONSISTENCY:"+k)
        require(abs(sum(k*v for k,v in weights.items())-row["mean"])<1e-10,
                "MEAN_PMF_INCONSISTENCY")
        require(abs(sum((k-row["mean"])**2*v for k,v in weights.items())-row["variance"])<1e-8,
                "VARIANCE_PMF_INCONSISTENCY")
        seed=row["seed_key"]
        require(seed==inp["input_manifest_sha256"]+"|"+c["event_id"]+"|"+row["model_id"]+"|"+row["model_version"],
                "DETERMINISTIC_SEED_BINDING_BROKEN")
    require(len(meta["dependence_diagnostics"])==2, "MISSING_J4_DIAGNOSTIC_PLACEHOLDER")
    return {
      "schema":"PA_WS4_INDEPENDENT_ORIGINAL_NUMERICAL_AUDIT_v1",
      "status":"PASS_NUMERICAL_PROVENANCE_SHADOW_ONLY",
      "immutable_file_sha256":digest,
      "source_manifest_sha256":SOURCE_SHA,
      "forecast_created_at":meta["forecast_created_at"],
      "event_start_at":inp["events"][0]["event_start_at"],
      "game_id":inp["events"][0]["event_id"],
      "original_contract_id":c["contract_id"],
      "original_quote_id":c["original_quote_id"],
      "original_stat":orig["stat"],
      "original_book":orig["book"],
      "original_line":orig["line"],
      "model_forecasts":len(rows),
      "draws_per_model":4096,
      "eligible_canary_contracts":1,
      "original_quote_observations":len(ledger_ids),
      "original_coverage_abstentions":len(ledger_ids)-1,
      "uncertified":True,
      "model_ids":sorted(x["model_id"] for x in rows),
      "no_market_skill_or_calibration_claim":True,
      "no_favorite_roles_certified":True,
    }


def adversarial_cases(raw_file, ws1_file):
    original=json.loads(raw_file.read_bytes())
    def altered(mutate):
        d=json.loads(json.dumps(original))
        mutate(d)
        tmp=pathlib.Path(str(raw_file)+".adversarial_TEMP_DO_NOT_KEEP")
        try:
            # Audit rejects tampering at the file-hash layer before any deep checks.
            tmp.write_bytes(compact(d)+b"\n")
            try:
                verify(tmp,ws1_file)
            except AuditFailure:
                return True
            raise AuditFailure("NEGATIVE_CONTROL_NOT_REJECTED")
        finally:
            tmp.unlink(missing_ok=True)
    # No persisted negative-control alteration of any real forecast or WS1 manifest.
    tests={
        "changed_line":lambda d:d["model_output"]["contracts"][0].update(line=99.5),
        "changed_player_id":lambda d:d["input_packet"]["contracts"][0].update(player_id="FAKE"),
        "postkickoff_time":lambda d:d["model_output"].update(forecast_created_at="2026-11-16T00:00:00+00:00"),
        "reversed_probability":lambda d:d["model_output"]["contracts"][0].update(p_over=1.1),
        "source_quote_receipt":lambda d:d["input_packet"]["contracts"][0].update(original_quote_receipt_sha256="0"*64),
        "missing_abstentions":lambda d:d["original_denominator_ledger"].clear(),
        "changed_source_input_hash":lambda d:d["input_packet"].update(input_manifest_sha256="f"*64),
        "forged_production_promotion":lambda d:d.update(production_promotion=True),
    }
    results={}
    for label,mutate in tests.items():
        results[label]=altered(mutate)
    return results


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--file",required=True,type=pathlib.Path)
    p.add_argument("--ws1",required=True,type=pathlib.Path)
    p.add_argument("--report-root",type=pathlib.Path,required=True)
    a=p.parse_args()
    r=verify(a.file,a.ws1)
    r["adversarial_rejections"]=adversarial_cases(a.file,a.ws1)
    require(all(r["adversarial_rejections"].values()),"ADVERSARIAL_TEST_UNEXPECTED_PASS")
    raw=compact(r)+b"\n"
    a.report_root.mkdir(parents=True,exist_ok=True)
    dest=a.report_root/(h(raw)+".json")
    with dest.open("xb") as f:f.write(raw)
    print(json.dumps({**r,"audit_receipt_file":str(dest),"audit_receipt_sha256":h(raw)},sort_keys=True))


if __name__=="__main__":
    main()
