"""Fast continuation after a FULL SHA-and-factor-state chain audit has produced
V5_RESUME_CHECKPOINT.json. This tool does NOT silently trust unverified output.

- The strict 66-week restart canary first verifies every original completed
  preweek/forecast/settlement and records immutable latest hash + factor state.
- Each later batch checks the exact last verified settlement's SHA and factor
  receipt, then adds <=24 new weeks, checkpointing EVERY settled week.
- One flock lock prevents concurrent writers; atomic rename on Deepnote FUSE.
- At completion, recreate all 175 score rows and perform final full-chain audit.
"""
from __future__ import annotations
import argparse,fcntl,json,pathlib,time,sys
ROOT=pathlib.Path.cwd()
sys.path.insert(0,str(ROOT/"research"))
import nfl_v5_6_checkpoint_resume_20261112 as recovery
base=recovery.base
JointFactorWeights=recovery.JointFactorWeights
verify=recovery.verify
def run(directory,limit):
 verify(directory.is_dir(),"directory_does_not_exist")
 lock=directory/"V5_RESUME_READER_WRITER.lock"
 with lock.open("a+") as lock_handle:
  try:fcntl.flock(lock_handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError("Another replay batch is running")
  cpfile=directory/"V5_RESUME_CHECKPOINT.json"
  verify(cpfile.is_file(),"strict_full_history_canary_checkpoint_required")
  ck=base.read(cpfile)
  assert ck["research_only"] is True and ck["production_authorized"] is False
  archived=base.read(base.V3/"FINAL_V3_VS_V2_10YEAR_REPORT.json")
  archive=archived["weekly_archive"]
  verify(len(archive)==175,"no_full_archive")
  rec=base.read(directory/"V5_METHOD_AND_SOURCE_RECEIPT.json")
  modelhash=base.sha((ROOT/"research/nfl_v5_6_empirical_coverage_joint_model_20261112.py").read_bytes())
  runnerhash=base.sha((ROOT/"research/nfl_v5_6_prior_coverage_decade_replay_20261112.py").read_bytes())
  verify(rec["model_sha256"]==modelhash and ck["model_sha256"]==modelhash,
         "checkpoint_model_modified")
  verify(rec["runner_sha256"]==runnerhash,"original_runner_drift")
  verify(rec["baseline_research_sha256"]==archived["result_sha256"],
         "frozen_baseline_drift")
  verify(rec["schema"]==base.SCHEMA and rec["model_version"]==base.VERSION,
         "original_model_changed")
  cursor=int(ck["verified_contiguous_weeks"])
  verify(1<=cursor<=175,"checkpoint_outside_archive")
  previtem=archive[cursor-1]
  prev=directory/(f"{previtem['year']}_week_{previtem['week']:02d}_v5_settlement.json.gz")
  verify(prev.exists(),"checkpoint_last_settlement_missing")
  verify(recovery.hash_file(prev)==ck["latest_settlement_sha256"],
         "checkpoint_latest_settlement_hash_drift")
  settled_last=base.read(prev)
  verify(base.canon(settled_last["factor_weights_updated_only_after_settlement"])==
         base.canon(ck["last_prior_only_weight_receipt"]),
         "checkpoint_learning_state_mismatch")
  verify(ck["last_completed"]=={"season":previtem["year"],"week":previtem["week"]},
         "checkpoint_week_mismatch")
  verify((ck["next_week"] is None and cursor==175) or
    (cursor<175 and ck["next_week"]["year"]==archive[cursor]["year"] and
     ck["next_week"]["week"]==archive[cursor]["week"]),
     "checkpoint_next_week_mismatch")
  weights=JointFactorWeights()
  weights.restore(ck["last_prior_only_weight_receipt"])
  new=0;recovered=0;start=time.monotonic()
  while cursor<175 and new<limit:
   item=archive[cursor]
   y,w=item["year"],item["week"];stem=f"{y}_week_{w:02d}"
   pre=directory/(stem+"_v5_preweek.json.gz")
   fore=directory/(stem+"_v5_forecast.json.gz")
   sett=directory/(stem+"_v5_settlement.json.gz")
   if sett.exists():
    # Previous interrupted batch may have frozen settlement before writing
    # checkpoint. Do not create a second version of that week.
    verify(pre.exists() and fore.exists(),"orphan_stale_settlement_"+stem)
    packet=base.read(pre);f=base.read(fore);z=base.read(sett)
    recovery.verify_preweek(packet,y,w,weights,item)
    recovery.verify_forecast(packet,f,pre,fore)
    verify(z["preweek_sha256"]==recovery.hash_file(pre),
           "stale_preweek_hash")
    verify(z["forecast_sha256"]==recovery.hash_file(fore),
           "stale_forecast_hash")
    verify(z["season"]==y and z["week"]==w,"stale_settlement_week")
    weights.restore(z["factor_weights_updated_only_after_settlement"])
    recovered+=1
   else:
    if pre.exists():
     packet=base.read(pre)
     recovery.verify_preweek(packet,y,w,weights,item)
    else:
     packet=recovery.expected_source_preweek(y,w,item,weights)
     recovery.verify_preweek(packet,y,w,weights,item)
     recovery.atomic_save(pre,packet)
    recovery.make_forecast_from_pre(fore,pre)
    forecast=base.read(fore)
    recovery.verify_forecast(packet,forecast,pre,fore)
    # Actual result is not read until after the original pregame packet and
    # joint scenario forecast were immutable and SHA checked.
    truth=base.read(base.V2/(stem+"_settlements.json.gz"))
    z=base.evaluate(packet,forecast,truth,weights)
    z.update({"preweek_sha256":recovery.hash_file(pre),
      "forecast_sha256":recovery.hash_file(fore),
      "score_only_after_frozen_forecast":True})
    recovery.atomic_save(sett,z)
    new+=1
   cursor+=1
   latest=recovery.hash_file(sett)
   ck={"verified_contiguous_weeks":cursor,
     "last_completed":{"season":y,"week":w},
     "next_week":archive[cursor] if cursor<175 else None,
     "latest_settlement_sha256":latest,
     "last_prior_only_weight_receipt":weights.receipt(),
     "model_sha256":modelhash,"research_only":True,
     "production_authorized":False,"remaining":175-cursor,
     "checkpoint_wallclock":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
     "quick_restore_from_full_verified_chain":True}
   recovery.checkpoint(cpfile,ck)
   print("V56_RESUMED_WEEK",json.dumps({
     "year":y,"week":w,"global_complete":cursor,"new":new,
     "already_saved":bool(sett.exists() and recovered>0),
     "paired":z["paired"],"brier_v5":z["all"].get("brier_joint"),
     "brier_v3":z["all"].get("brier_v3"),
     "elapsed_s":round(time.monotonic()-start,1)}),flush=True)
  if cursor==175:
   # Reconstruct 175 tiny settlement records and full exact SHA receipts.
   # This final operation does NOT regenerate any prior scenario or forecast.
   records=[];receipts=[]
   for item in archive:
    y,w=item["year"],item["week"];stem=f"{y}_week_{w:02d}"
    pre=directory/(stem+"_v5_preweek.json.gz")
    fore=directory/(stem+"_v5_forecast.json.gz")
    sett=directory/(stem+"_v5_settlement.json.gz")
    verify(all(p.is_file() for p in (pre,fore,sett)),"final_missing_"+stem)
    v=base.read(sett)
    verify(v["preweek_sha256"]==recovery.hash_file(pre),
       "final_input_hash_"+stem)
    verify(v["forecast_sha256"]==recovery.hash_file(fore),
       "final_forecast_hash_"+stem)
    verify(v["season"]==y and v["week"]==w,"final_week_mismatch_"+stem)
    records.append(v)
    receipts.append({"season":y,"week":w,
      "input_sha256":recovery.hash_file(pre),
      "forecast_sha256":recovery.hash_file(fore),
      "settlement_sha256":recovery.hash_file(sett),
      "paired":v["paired"]})
   final=recovery.write_final(directory,archive,records,receipts,rec)
   print("V56_ALL_175_RECOVERED_COMPLETE",json.dumps({
    "weeks":175,"paired":final["overall"]["n"],
    "brier_v56":final["overall"]["brier_joint"],
    "brier_v3":final["overall"]["brier_v3"],
    "result_sha256":final["result_sha256"]}),flush=True)
  print("V56_FAST_BATCH_FINISHED",json.dumps({
   "completed":cursor,"remaining":175-cursor,"new":new,
   "recovered_settlements":recovered,
   "seconds":round(time.monotonic()-start,1)}),flush=True)
  fcntl.flock(lock_handle.fileno(),fcntl.LOCK_UN)
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--dir",type=pathlib.Path,required=True)
 p.add_argument("--max-new-weeks",type=int,default=20)
 a=p.parse_args()
 verify(1<=a.max_new_weeks<=24,"bounded_batch_limit")
 run(a.dir,a.max_new_weeks)
