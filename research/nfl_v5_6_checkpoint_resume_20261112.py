"""Preemption-safe, exact-state continuation for NFL V5.6 frozen 175-week replay.

- Never recompute/replace a successfully settled prior week.
- Verify all prior forecast/input/settlement SHA chain and factor-state rollover.
- Resume interrupted preweek/forecast stages WITHOUT introducing labels.
- Freeze each new forecast before reading its settlement.
- Run a bounded number of weeks so Deepnote preemptible machines won't time out.
- Preserve the original model and initial 66 weeks byte-for-byte.
Research-only, retrospectively sourced synthetic lines.
"""
from __future__ import annotations
import argparse,csv,fcntl,gzip,json,os,pathlib,subprocess,sys,uuid,time,collections
import numpy as np
ROOT=pathlib.Path.cwd()
sys.path.insert(0,str(ROOT/"research"))
import nfl_v5_6_prior_coverage_decade_replay_20261112 as base
from nfl_v5_6_empirical_coverage_joint_model_20261112 import JointFactorWeights
def verify(ok,msg):
 if not ok:raise RuntimeError("V56_RESUME_FAIL_CLOSED: "+msg)
def hash_file(p):return base.sha(p.read_bytes())
def atomic_bytes(path,content):
 verify(not path.exists(),"immutable_target_exists_"+str(path))
 tmp=path.parent/(path.name+".tmp_"+uuid.uuid4().hex)
 try:
  with tmp.open("xb") as fh:
   fh.write(content);fh.flush();os.fsync(fh.fileno())
  os.link(tmp,path)   # atomic no-clobber creation
 finally:
  tmp.unlink(missing_ok=True)
 return base.sha(content)
def atomic_save(path,obj):
 data=base.canon(obj)
 if path.suffix==".gz":data=gzip.compress(data,compresslevel=4,mtime=0)
 else:data+=b"\n"
 return atomic_bytes(path,data)
def checkpoint(path,entry):
 # Progress cache only; original immutable week receipts are authoritative.
 tmp=path.parent/(path.name+".tmp_"+uuid.uuid4().hex)
 try:
  tmp.write_text(json.dumps(entry,sort_keys=True,indent=2)+"\n")
  os.replace(tmp,path)
 finally:tmp.unlink(missing_ok=True)
def expected_source_preweek(y,w,entry,weights):
 stem=f"{y}_week_{w:02d}"
 v3path=base.V3/(stem+"_v3_predictions.json.gz")
 verify(hash_file(v3path)==entry["forecast_sha256"],"baseline_sha_"+stem)
 source=base.read(base.V3/(stem+"_v3_before_outcomes.json.gz"))
 old=base.read(v3path)
 oldv2=base.read(base.V2/(stem+"_predictions.json.gz"))
 by={(f["game_id"],f["team"],f["player_id"],f["market"]):f for f in oldv2["offers"]}
 contracts=[]
 for f in old["offers"]:
  key=f["game_id"],f["team"],f["player_id"],f["market"]
  leg=by.get(key)
  verify(leg is not None,"legacy_contract_missing_"+stem)
  md=leg["forecast_models"]
  p2=md["shared_opportunity"];ph=md["player_history"]
  contracts.append({**{z:f[z] for z in
     ("game_id","team","opponent","player_id","role","market","line")},
   "v3_draws":f.get("draws") if f["status"]=="forecast" else None,
   "v3_online":f.get("p_over_online"),
   "v2_raw":float(p2["q_over_raw"]) if p2 else .5,
   "history_raw":float(ph["q_over_raw"]) if ph else .5})
 frozen={"schema":base.SCHEMA,"season":y,"week":w,
  "history":source["history"],"pbp_prior":source["pbp_prior"],
  "games":source["games"],"qb1":source["qb1"],
  "contracts":contracts,"factor_preimage":weights.receipt(),
  "original_v3_prediction_sha256":entry["forecast_sha256"],
  "pregame_certified":False,"research_only":True}
 return frozen
def verify_preweek(p,y,w,weights,entry):
 verify(p["schema"]==base.SCHEMA,"schema_"+str((y,w)))
 verify(p["season"]==y and p["week"]==w,"week_identity_"+str((y,w)))
 verify(base.canon(p["factor_preimage"])==base.canon(weights.receipt()),
   "factor_rollover_"+str((y,w)))
 verify(p["original_v3_prediction_sha256"]==entry["forecast_sha256"],
   "original_v3_forecast_sha_"+str((y,w)))
 verify(p["pregame_certified"] is False and p["research_only"] is True,
   "not_research_"+str((y,w)))
 verify(all(g["season"]<y or(g["season"]==y and g["week"]<w)
   for g in p["history"]),"future_history_"+str((y,w)))
 verify(bool(p["history"]) and min(g["season"] for g in p["history"])>=max(2014,y-10),
    "outside_tenyear_history_"+str((y,w)))
 verify(all(g["season"]<y or(g["season"]==y and g["week"]<w)
   for g in p["pbp_prior"]),"future_pbp_"+str((y,w)))
 verify(hash_file(base.V3/(f"{y}_week_{w:02d}_v3_predictions.json.gz"))==
       entry["forecast_sha256"],"v3_source_drift")
def verify_forecast(p,f,inp,forecastfile):
 verify(f["input_sha256"]==base.sha(base.canon(p)),"forecast_not_bound_to_input")
 verify(f["factor_preimage_sha256"]==base.sha(base.canon(p["factor_preimage"])),
    "forecast_not_bound_to_factor")
 verify(f["season"]==p["season"] and f["week"]==p["week"],
    "forecast_wrong_week")
 verify(f["forecasts_did_not_receive_current_week_settlements"] is True,
    "forecast_can_see_current_labels")
 verify(f["research_only"] is True and f["production_authorized"] is False,
    "unexpected_production")
 verify(len(f["offers"])==len(p["contracts"]),"forecast_wrong_offer_count")
def make_forecast_from_pre(forecastfile,pre):
 if forecastfile.exists():return
 # Isolated child receives only immutable preweek packet; output goes through
 # an ephemeral pathname and is linked to its final name only if validated.
 tmp=forecastfile.parent/(forecastfile.stem+".incomplete_"+uuid.uuid4().hex+".gz")
 try:
  cmd=[sys.executable,str(ROOT/"research/nfl_v5_6_prior_coverage_decade_replay_20261112.py"),
       "forecast","--input",str(pre),"--output",str(tmp)]
  p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=420)
  verify(p.returncode==0,
    "isolated_child_failed_"+pre.name+"_stderr:"+p.stderr[-4000:])
  f=base.read(tmp)
  verify_forecast(base.read(pre),f,pre,tmp)
  atomic_bytes(forecastfile,tmp.read_bytes())
 finally:
  tmp.unlink(missing_ok=True)
def aggregate(rows):
 n=sum(x["all"]["n"] for x in rows)
 if not n:return {"n":0,"weeks":len(rows)}
 a={"n":n,"weeks":len(rows)}
 names=("brier_joint","brier_v3","brier_v2","crps_joint","crps_v3",
 "hit_joint","hit_v3","signed_over_residual","mean_error_joint",
 "joint_logloss","v3_logloss")
 for k in names:
  a[k]=sum(z["all"]["n"]*z["all"].get(k,0) for z in rows)/n
 a["delta_brier"]=a["brier_joint"]-a["brier_v3"]
 a["delta_crps"]=a["crps_joint"]-a["crps_v3"]
 for th in (70,80,90,95):
  pre="conf"+str(th)
  count=sum(z["all"].get(pre+"_n",0) for z in rows)
  a[pre+"_n"]=count
  a[pre+"_claimed"]=(sum(z["all"].get(pre+"_n",0)*
    (z["all"].get(pre+"_claimed") or 0) for z in rows)/count) if count else None
  a[pre+"_hit"]=(sum(z["all"].get(pre+"_n",0)*
    (z["all"].get(pre+"_hit") or 0) for z in rows)/count) if count else None
 return a
def write_final(out,archive,rows,receipts,frozen_receipt):
 verify(len(rows)==175,"incomplete_before_finalization")
 verify(len(receipts)==175,"incomplete_receipt_count")
 result={"status":"COMPLETE_RESEARCH_ONLY","weeks_completed":175,
  "receipts":receipts,"overall":aggregate(rows),
  "season":{str(y):aggregate([r for r in rows if r["season"]==y])
    for y in sorted({r["season"] for r in rows})},
  "source_retroactive":True,"research_only":True,"production_authorized":False,
  "unmatched_and_abstained":{
    str(r["season"])+"-"+str(r["week"]):r["ledger"] for r in rows},
  "underlying_joint_state_and_distribution_bound_to_same_game_scenario":True,
  "method_sha256":base.sha(base.canon(frozen_receipt)),
  "recovery_metadata":{"resumed_after_preemptible_kernel_timeout":True,
     "prior_forecasts_settlements_untouched":True,
     "all_175_inputs_forecasts_settlements_SHA_verified":True}}
 result["result_sha256"]=base.sha(base.canon(result))
 final=out/"V5_COMPLETE_OR_PARTIAL_RESEARCH_REPORT.json"
 if final.exists():
  prev=base.read(final)
  verify(prev["result_sha256"]==result["result_sha256"],
         "existing_final_report_conflicts")
 else:atomic_save(final,result)
 weekly=out/"V5_WEEKLY_SCORES.csv"
 if not weekly.exists():
  tmp=out/("V5_WEEKLY_SCORES.csv."+uuid.uuid4().hex)
  fields=["season","week","n","brier_joint","brier_v3","delta_brier",
   "crps_joint","crps_v3","hit_joint","hit_v3","conf80_n","conf80_claimed","conf80_hit"]
  try:
   with tmp.open("w",newline="") as fh:
    w=csv.DictWriter(fh,fieldnames=fields);w.writeheader()
    for item in rows:
     v=item["all"];w.writerow({"season":item["season"],"week":item["week"],
       "n":v["n"],**{k:v.get(k) for k in fields if k in v},
       "delta_brier":v.get("brier_joint",0)-v.get("brier_v3",0)})
   atomic_bytes(weekly,tmp.read_bytes())
  finally:tmp.unlink(missing_ok=True)
 return result
def run(out,max_new_weeks):
 verify(out.is_dir(),"existing_run_directory_required")
 lockfile=out/"V5_RESUME_READER_WRITER.lock"
 with lockfile.open("a+") as fh:
  try:fcntl.flock(fh.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:raise RuntimeError("Another V5.6 writer is active")
  receipt=base.read(out/"V5_METHOD_AND_SOURCE_RECEIPT.json")
  modelsha=base.sha((ROOT/"research/nfl_v5_6_empirical_coverage_joint_model_20261112.py").read_bytes())
  runnersha=base.sha((ROOT/"research/nfl_v5_6_prior_coverage_decade_replay_20261112.py").read_bytes())
  verify(receipt["model_sha256"]==modelsha,"original_model_modified_since_freeze")
  verify(receipt["runner_sha256"]==runnersha,"original_runner_modified_since_freeze")
  verify(receipt["schema"]==base.SCHEMA and receipt["model_version"]==base.VERSION,
       "source_receipt_mismatch")
  verify(receipt["production_authorized"] is False,"no_production")
  v3=base.read(base.V3/"FINAL_V3_VS_V2_10YEAR_REPORT.json")
  verify(v3["cycles"]==175 and v3["result_sha256"]==receipt["baseline_research_sha256"],
       "frozen_v3_source_changed")
  archive=v3["weekly_archive"]
  weights=JointFactorWeights();rows=[];receipts=[];start=time.monotonic()
  created=0;existing=0;resumed=False
  for index,item in enumerate(archive):
   y,w=item["year"],item["week"];stem=f"{y}_week_{w:02d}"
   pre=out/(stem+"_v5_preweek.json.gz")
   fore=out/(stem+"_v5_forecast.json.gz")
   sett=out/(stem+"_v5_settlement.json.gz")
   if sett.exists():
    verify(not resumed,"noncontiguous_prior_settlement_"+stem)
    verify(pre.exists() and fore.exists(),"orphan_settlement_"+stem)
    p=base.read(pre);f=base.read(fore);r=base.read(sett)
    verify_preweek(p,y,w,weights,item)
    verify_forecast(p,f,pre,fore)
    verify(r["season"]==y and r["week"]==w,"settlement_wrong_week_"+stem)
    verify(r["preweek_sha256"]==hash_file(pre),"preweek_settlement_sha_"+stem)
    verify(r["forecast_sha256"]==hash_file(fore),"forecast_settlement_sha_"+stem)
    verify(r["paired"]==r["all"]["n"],"settlement_paired_denominator_"+stem)
    snap=JointFactorWeights()
    snap.restore(r["factor_weights_updated_only_after_settlement"])
    weights.restore(r["factor_weights_updated_only_after_settlement"])
    existing+=1
   else:
    resumed=True
    if created>=max_new_weeks:break
    if pre.exists():
     p=base.read(pre);verify_preweek(p,y,w,weights,item)
    else:
     p=expected_source_preweek(y,w,item,weights)
     verify_preweek(p,y,w,weights,item)
     atomic_save(pre,p)
    make_forecast_from_pre(fore,pre)
    f=base.read(fore)
    verify_forecast(p,f,pre,fore)
    # Only after forecast is immutable and SHA-verified: access outcomes.
    truth=base.read(base.V2/(stem+"_settlements.json.gz"))
    r=base.evaluate(p,f,truth,weights)
    r.update({"preweek_sha256":hash_file(pre),
      "forecast_sha256":hash_file(fore),
      "score_only_after_frozen_forecast":True})
    atomic_save(sett,r)
    created+=1
    print("V56_CHECKPOINT_WEEK_COMPLETED",json.dumps({
     "season":y,"week":w,"global_week":existing+created,
     "paired":r["paired"],"brier_v56":r["all"].get("brier_joint"),
     "brier_v3":r["all"].get("brier_v3"),
     "seconds_elapsed":round(time.monotonic()-start,1)}),flush=True)
   rows.append(r)
   receipts.append({"season":y,"week":w,
      "input_sha256":hash_file(pre),"forecast_sha256":hash_file(fore),
      "settlement_sha256":hash_file(sett),"paired":r["paired"]})
   if created and (created%3==0 or len(rows)==175):
    checkpoint(out/"V5_RESUME_CHECKPOINT.json",{
     "verified_contiguous_weeks":len(rows),
     "last_completed":{"season":y,"week":w},
     "next_week":(archive[len(rows)] if len(rows)<175 else None),
     "latest_settlement_sha256":hash_file(sett),
     "last_prior_only_weight_receipt":weights.receipt(),
     "model_sha256":modelsha,"research_only":True,
     "production_authorized":False,
     "remaining":175-len(rows),
     "checkpoint_wallclock":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())})
  verify(len(rows)==existing+created,"contiguous_recovery_length")
  if len(rows)==175:
   final=write_final(out,archive,rows,receipts,receipt)
   print("V56_ALL_175_RECOVERED_COMPLETE",json.dumps({
      "weeks":175,"paired":final["overall"]["n"],
      "brier_v56":final["overall"]["brier_joint"],
      "brier_v3":final["overall"]["brier_v3"],
      "result_sha256":final["result_sha256"]}),flush=True)
  else:
   last=rows[-1] if rows else None
   checkpoint(out/"V5_RESUME_CHECKPOINT.json",{
    "verified_contiguous_weeks":len(rows),
    "last_completed":({k:last[k] for k in ("season","week")} if last else None),
    "next_week":archive[len(rows)],
    "latest_settlement_sha256":receipts[-1]["settlement_sha256"] if receipts else None,
    "last_prior_only_weight_receipt":weights.receipt(),
    "model_sha256":modelsha,"research_only":True,
    "production_authorized":False,
    "remaining":175-len(rows),
    "checkpoint_wallclock":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())})
  print("V56_RESUME_BATCH_FINISHED",json.dumps({
    "verified_existing":existing,"new_weeks":created,
    "completed":len(rows),"total":175,"remaining":175-len(rows),
    "elapsed_seconds":round(time.monotonic()-start,1),
    "run_directory":str(out)}),flush=True)
  fcntl.flock(fh.fileno(),fcntl.LOCK_UN)
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--dir",type=pathlib.Path,required=True)
 p.add_argument("--max-new-weeks",type=int,default=18)
 a=p.parse_args()
 verify(1<=a.max_new_weeks<=30,"batch_size_between_one_and_thirty")
 run(a.dir,a.max_new_weeks)
