"""Finish an already-running V5.6 decade replay sequentially and preemption-safely.

Research only: unchanged frozen V5.6 forecast code and prior-week calibration.
No independent runs overlap in writes; waits for a held exclusive project lock
before starting a new bounded batch. Runs on existing free Deepnote Basic CPU.
"""
import fcntl,json,os,pathlib,subprocess,sys,time
BASE=pathlib.Path("reports/NFL_2016_2025_DECADE_PREQUENTIAL_RESEARCH_20261111")
DIR=BASE/"V5_6_FULL_175_WEEK_HISTORY_CALIBRATED_RESEARCH_20261112T162027Z"
CHECKPOINT=DIR/"V5_RESUME_CHECKPOINT.json"
REPORT=DIR/"V5_COMPLETE_OR_PARTIAL_RESEARCH_REPORT.json"
LOCK=DIR/"V5_RESUME_READER_WRITER.lock"
SCRIPT=pathlib.Path("research/nfl_v5_6_fast_batch_resume_20261112.py")
assert DIR.is_dir() and SCRIPT.is_file(), "Expected frozen V5.6 run/script not found"
def cp():
 data=json.loads(CHECKPOINT.read_text())
 assert data["production_authorized"] is False and data["research_only"] is True
 assert 1<=int(data["verified_contiguous_weeks"])<=175
 assert data["remaining"]==175-data["verified_contiguous_weeks"]
 return data
def is_running():
 with LOCK.open("a+") as f:
  try:
   fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
   fcntl.flock(f.fileno(),fcntl.LOCK_UN)
   return False
  except BlockingIOError:return True
def wait_for_previous():
 start=time.monotonic()
 while is_running():
  if int(time.monotonic()-start)%60<10:
   q=cp()
   print("V56_SEQUENTIAL_WAIT_FOR_ACTIVE_WRITER",json.dumps({
    "verified":q["verified_contiguous_weeks"],"remaining":q["remaining"],
    "waited_seconds":round(time.monotonic()-start)}),flush=True)
  assert time.monotonic()-start<2700,"Existing writer has held lock for more than 45 minutes: stop without corrupting history"
  time.sleep(10)
def main():
 print("V56_SEQUENTIAL_FINISH_STARTED",json.dumps({"checkpoint":str(CHECKPOINT),
  "batch_cap":20,"unchanged_model":True,"free_cpu_only":True}),flush=True)
 wait_for_previous()
 previous=cp()["verified_contiguous_weeks"]
 while previous<175:
  cmd=[sys.executable,"-u",str(SCRIPT),"--dir",str(DIR),"--max-new-weeks","20"]
  print("V56_SEQUENTIAL_NEXT_BATCH",json.dumps({"completed":previous,"remaining":175-previous}),flush=True)
  child=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
  for line in child.stdout:
   if any(key in line for key in ("V56_RESUMED_WEEK","V56_FAST_BATCH_FINISHED",
       "V56_ALL_175_RECOVERED_COMPLETE","Traceback","FAIL_CLOSED","Error","OSError")):
    print(line.strip()[-2500:],flush=True)
  rc=child.wait()
  if rc:
   print("V56_SEQUENTIAL_BATCH_FAILED",json.dumps({"returncode":rc,
       "checkpoint":cp()["verified_contiguous_weeks"]}),flush=True)
   raise RuntimeError("V5.6 historical batch failed; existing checkpoints preserved")
  current=cp()["verified_contiguous_weeks"]
  assert current>previous and current<=175, "Successful batch failed to progress"
  previous=current
  print("V56_SEQUENTIAL_BATCH_CONFIRMED",json.dumps({
   "completed":current,"remaining":175-current,
   "latest_receipt_sha256":cp()["latest_settlement_sha256"]}),flush=True)
 if not REPORT.is_file():raise RuntimeError("All 175 settled but no final report")
 report=json.loads(REPORT.read_text())
 assert report["status"]=="COMPLETE_RESEARCH_ONLY" and report["weeks_completed"]==175
 assert report["research_only"] is True and report["production_authorized"] is False
 print("V56_SEQUENTIAL_175_WEEK_COMPLETE",json.dumps({
  "weeks":175,"paired":report["overall"]["n"],
  "brier_v56":report["overall"]["brier_joint"],
  "brier_v3":report["overall"]["brier_v3"],
  "delta_brier":report["overall"]["delta_brier"],
  "result_sha256":report["result_sha256"]}),flush=True)
if __name__=="__main__":main()
