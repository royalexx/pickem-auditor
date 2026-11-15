"""Phase 5 post-hoc TOI-bin sensitivity, research only; NEVER changes frozen M0--M4.
Source and scored outcomes are retrospective, not historical as-of certified.
Only changed model behavior: played 0 < TOI < 0.25 minutes maps to the 0.5 minute
MINIMUM POSITIVE exposure BIN. Original raw TOI stays in rate calculations.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, math, tempfile
from pathlib import Path

ORIGINAL = {
    "observations": "d321e8f3af9d127589c6cbcb9e9477717ebd61eb062f30e587a7a9268468671a",
    "schedule": "d9139bffcdeea57a37068b364a58621e20fdd02833b47bb71a3fbdec64a9aa1e",
    "scored": "75f1343ca3125cd9665f1ff917b91268c9aa8cb1d78223d7c47842ba79568629",
    "sealed": "12c267b7ca629d75a69f8cfd429a5a55e8510f4be7cb914ec5860c18097553dc",
    "report": "36239fb0e7d4c188cdeacf7e0f54970d148ceeeee5d129bb7ea9d2ce8fb3ffd8",
}
EXPERIMENT = "EXP-P5-NHL-SOG-MICROTOI-SENSITIVITY-V2-20261114"
OLD_SOURCE_LINE = '"model_implementation":"v2.nhl_sog_exposure_shadow frozen main"'
NEW_SOURCE_LINE = '"model_implementation":"frozen probability laws; v2 min-positive TOI exposure bin sensitivity"'
CANDIDATE_RULE = "if 0<played_TOI_minutes<0.25, bin to 0.5 minutes only for modeled exposure PMF; preserve original 0.05 in rate sums"
OLD_EXPERIMENT = 'EXPERIMENT_ID = "EXP-P5-NHL-SOG-HIST-20261114"'
OLD_SCHEMA = 'SCHEMA = "phase5_retrospective_event_time_v1"'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def check_archive(observations, schedule, original):
    targets = {"observations": observations, "schedule": schedule,
        "scored": original/"scored_played.jsonl",
        "sealed": original/"sealed_forecasts.jsonl",
        "report": original/"score_report.json"}
    for label, path in targets.items():
        digest = sha(path)
        if digest != ORIGINAL[label]:
            raise RuntimeError("FAIL_CLOSED_ORIGINAL_SHA_MISMATCH:"+label+":"+digest)

def candidate_source(original_source):
    """Fail closed against unexpected original implementation changes."""
    code = Path(original_source).read_text(encoding="utf-8")
    if code.count(OLD_EXPERIMENT)!=1 or code.count(OLD_SCHEMA)!=1 or code.count(OLD_SOURCE_LINE)!=1:
        raise RuntimeError("ORIGINAL_REPLAY_VERSION_MISMATCH")
    begin=code.index("def build_params(pid,history):")
    end=code.index("\ndef pmfs(model):",begin)
    body=code[begin:end]
    needle="frozen.bin_toi_minutes("
    if body.count(needle)!=3:
        raise RuntimeError("EXPOSURE_BIN_CALLSITE_COUNT_MISMATCH")
    new_func = (
        "def v2_microtoi_bin(minutes):\n"
        "    # Preserve actual TOI for rate/posterior sums. 3s played is NOT DNP.\n"
        "    if isinstance(minutes,(int,float)) and not isinstance(minutes,bool) and math.isfinite(minutes) and 0 < minutes < 0.25:\n"
        "        return 0.5\n"
        "    return frozen.bin_toi_minutes(minutes)\n\n"
    )
    code=code[:begin]+new_func+body.replace(needle,"v2_microtoi_bin(")+code[end:]
    code=code.replace(OLD_EXPERIMENT,'EXPERIMENT_ID = "'+EXPERIMENT+'"')
    code=code.replace(OLD_SCHEMA,'SCHEMA = "phase5_retrospective_event_time_microtoi_sensitivity_v2"')
    code=code.replace(OLD_SOURCE_LINE,NEW_SOURCE_LINE)
    return code

def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)

def summarize_paired(old_scored,new_scored,base,new):
    original={(r["game_id"],r["player_id"]):r for r in read_jsonl(old_scored)}
    added=[]; changed=[]; common=0
    import collections, statistics
    differences=collections.defaultdict(list)
    new_count=0
    for row in read_jsonl(new_scored):
        new_count+=1
        key=(row["game_id"],row["player_id"])
        prior=original.get(key)
        if prior is None:
            added.append(row)
        else:
            common+=1
            if prior["scores"]!=row["scores"] or prior["actual_sog"]!=row["actual_sog"]:
                changed.append(key)
            for m in ("M0","M1","M2","M3","M4"):
                differences[m].append(row["scores"][m]["crps"]-prior["scores"][m]["crps"])
    lost=len(original)-common
    if changed or lost:
        raise RuntimeError("COMMON_COHORT_CHANGED_OR_LOST:"+str({"changed":len(changed),"lost":lost}))
    if new_count != common+len(added):
        raise RuntimeError("MATCHED_COUNT_INVARIANT")
    if base["matched_played"] != len(original):
        raise RuntimeError("ORIGINAL_REPORT_DENOMINATOR_CHANGED")
    return {
        "old_scored":len(original), "new_scored":new_count,"identical_common_scored":common,
        "added_scored":len(added),"lost_scored":lost,
        "shared_score_changes":len(changed),
        "added_by_season":dict(collections.Counter(r["season"] for r in added)),
        "new_abstention_reasons":new["forecast_abstentions"],
        "old_abstention_reasons":base["forecast_abstentions"],
        "old_forecasted":base["forecasted"],"new_forecasted":new["forecasted"],
        "old_unscored":sum(base["unscored_forecasts"].values()),
        "new_unscored":sum(new["unscored_forecasts"].values()),
        "model_compare":{
          mid:{"old_crps":base["overall"]["models"][mid]["crps"],
               "new_crps":new["overall"]["models"][mid]["crps"],
               "old_nll":base["overall"]["models"][mid]["nll"],
               "new_nll":new["overall"]["models"][mid]["nll"]}
          for mid in ("M0","M1","M2","M3","M4")},
        "added_model_CRPS":{
          mid:(statistics.mean(r["scores"][mid]["crps"] for r in added) if added else None)
          for mid in ("M0","M1","M2","M3","M4")}
    }

def run(observations,schedule,original,output,config_path,original_source):
    observations=Path(observations);schedule=Path(schedule);original=Path(original)
    check_archive(observations,schedule,original)
    base=json.loads((original/"score_report.json").read_text())
    if base["run_id"]!="4c5d4d3f4dc840db3b42":
        raise RuntimeError("FROZEN_RUN_ID_MISMATCH")
    cfg=json.loads(Path(config_path).read_text())
    if cfg.get("market_replay") is not False or cfg.get("historical_only") is not True:
        raise RuntimeError("MUST_BE_HISTORICAL_RESEARCH_ONLY")
    cfg["posthoc_only"]=True
    cfg["source_availability"]="retrospective_retrieval_2026_not_original_pregame"
    cfg["original_forecast_sha256"]=ORIGINAL["sealed"]
    cfg["bin_sensitivity_rule"]=CANDIDATE_RULE
    code=candidate_source(original_source)
    code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest()
    # Load an isolated mathematical replay copy: never patch shared frozen modules.
    with tempfile.TemporaryDirectory(prefix="phase5_bin_sensitivity_") as folder:
        temp=Path(folder)/"research_replay_v2.py"
        temp.write_text(code,encoding="utf-8")
        spec=importlib.util.spec_from_file_location("research_replay_v2",str(temp))
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.v2_microtoi_bin(0.05)==0.5
        assert mod.v2_microtoi_bin(0.24)==0.5
        assert mod.v2_microtoi_bin(0.25)==0.5
        try:
            mod.v2_microtoi_bin(0)
        except mod.frozen.ExperimentBlocked:
            pass
        else:
            raise RuntimeError("ZERO_TOI_NOT_REJECTED")
        result=mod.run(str(observations),str(schedule),str(output),cfg,code_hash)
    root=Path(output)/result["run_id"]
    matched=summarize_paired(original/"scored_played.jsonl",root/"scored_played.jsonl",base,result)
    receipt={
        "schema":"phase5_microtoi_posthoc_sensitivity_v2",
        "status":"EXPLORATORY_ONLY_NEVER_PROSPECTIVE_OR_PRODUCTION",
        "source_classification":"retrospective event-time reconstructed not certified as-of",
        "source_observations_sha256":ORIGINAL["observations"],
        "source_schedule_sha256":ORIGINAL["schedule"],
        "frozen_original_forecast_sha256":ORIGINAL["sealed"],
        "frozen_original_scored_sha256":ORIGINAL["scored"],
        "candidate_forecast_sha256":result["forecast_sha256"],
        "candidate_scored_sha256":sha(root/"scored_played.jsonl"),
        "candidate_code_sha256":code_hash,
        "candidate_run_id":result["run_id"],
        "experimental_status":"posthoc sensitivity: known 0.05 minute observation influenced choice; not independent holdout",
        "policy":CANDIDATE_RULE,
        "cohort_comparison":matched,
        "inference_gate":"CLOSED_NO_PROMOTION_NO_MARKET_ASSERTION",
        "prospective_40_date_trial":"UNCHANGED"
    }
    out=root/"phase5_microtoi_sensitivity_receipt.json"
    with out.open("xb") as file:
        file.write(json.dumps(receipt,sort_keys=True,separators=(",",":"),allow_nan=False).encode())
    return receipt

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for arg in ("observations","schedule","original","output","config","original-source"):
        parser.add_argument("--"+arg,required=True)
    a=parser.parse_args()
    print(json.dumps(run(a.observations,a.schedule,a.original,a.output,a.config,a.original_source),sort_keys=True))
