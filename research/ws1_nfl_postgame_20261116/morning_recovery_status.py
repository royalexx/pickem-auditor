"""WS1 immutable morning failure-state adapter; does NOT alter live morning jobs."""
from __future__ import annotations
import hashlib,json,pathlib
from research.ws6_nfl_sunday_20261115.independent_postgame_20261116 import frozen_write
ROOT=pathlib.Path("reports/nfl_20261115_prospective")
AUDIT=ROOT/"ws1_postgame_recovery_20261116_v2"
NOV05=ROOT/"ws1_postgame_recovery_20261116_v1/nov05_collision_summary.json"
RUN=pathlib.Path("pickem_runs/2026-11-15/20261116T120008Z")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    receipt_path=RUN/"receipt.json"
    log_path=RUN/"logs/restore_yesterday_forecasts.log"
    base=json.loads(receipt_path.read_text())
    source=json.loads((AUDIT/"recovery_summary.json").read_text())
    collision=json.loads(NOV05.read_text())
    if base.get("date")!="2026-11-15" or base.get("run_phase")!="morning":
        raise ValueError("NOT_THE_ORIGINAL_MORNING_RUN")
    if base.get("morning_validation",{}).get("source_forecast_bundles")!=0:
        raise ValueError("LEGACY_ARCHIVE_STATUS_HAS_CHANGED")
    if source["original_quote_observations"]!=1845 or source["market_certified_contracts"]!=0:
        raise ValueError("SOURCE_EVIDENCE_CONFLICT")
    if collision["conflicting_identity_groups"]!=682:
        raise ValueError("HISTORICAL_POPULATION_BLOCKER_NOT_REPRODUCED")
    state={
      "schema":"PA_WS1_MORNING_RECOVERY_BLOCKED_STATE_V1",
      "date":"2026-11-15",
      "legacy_morning_stage":"BLOCKED_NO_AUTHENTIC_ORIGINAL_AFTERNOON_ARCHIVE",
      "legacy_run_source_sha256":sha(receipt_path),
      "legacy_restore_log_sha256":sha(log_path),
      "legacy_reported_restored_forecasts":0,
      "legacy_reported_scored_rows":0,
      "research_source_route":"SEPARATELY_FROZEN_SOURCE_TO_OFFICIAL_RESEARCH_REPLAY_AVAILABLE",
      "research_replay_summary_sha256":sha(AUDIT/"recovery_summary.json"),
      "research_original_quote_rows":1845,
      "research_market_certified_contracts":0,
      "conflicting_historical_population_day":"2026-11-05",
      "historical_collision_summary_sha256":sha(NOV05),
      "historical_collision_groups":682,
      "bayesian_incremental_gate":"BLOCKED_NO_UNCERTIFIED_OR_CONFLICTING_UPDATES",
      "production_morning_schedules_modified":False,
      "legacy_afternoon_archive_backfilled":False,
      "original_forecasts_rewritten":False,
      "status":"BLOCKED_RESEARCH_ONLY_DO_NOT_TREAT_AS_ZERO_ACCURACY",
      "action":"Separate research outcomes from a missing legacy afternoon archive; require source owner clearance before activation."
    }
    data=(json.dumps(state,sort_keys=True,indent=2,allow_nan=False)+"\n").encode()
    path=AUDIT/"morning_failure_recovery_state.json"
    frozen_write(path,data)
    print(json.dumps({"path":str(path),"sha256":sha(path),**state},sort_keys=True))
if __name__=="__main__":main()
