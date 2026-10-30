#!/usr/bin/env python3
"""Resource-aware NHL-only four-market Windows Bayesian training campaign.

A SINGLE GitHub self-hosted Windows job owns the scheduler. Up to four
independent PyMC models each run four concurrent CPU chains. Starting is
staggered; an 8GiB free-RAM gate prevents launching more fits under memory
pressure. Finishes with success/failed/blocked receipts for every stat.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Empty

STATS = ("shots on goal", "hits", "blocked shots", "saves")
SLUGS = {"shots on goal":"shots-on-goal", "hits":"hits",
         "blocked shots":"blocked-shots", "saves":"saves"}


def memory_free_mb() -> int:
    """Native Windows physical available memory; no third-party packages."""
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength",ctypes.c_ulong),("dwMemoryLoad",ctypes.c_ulong),
                        ("ullTotalPhys",ctypes.c_ulonglong),
                        ("ullAvailPhys",ctypes.c_ulonglong),
                        ("ullTotalPageFile",ctypes.c_ulonglong),
                        ("ullAvailPageFile",ctypes.c_ulonglong),
                        ("ullTotalVirtual",ctypes.c_ulonglong),
                        ("ullAvailVirtual",ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
        status=MEMORYSTATUSEX()
        status.dwLength=ctypes.sizeof(MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("windows_physical_memory_query_failed")
        return int(status.ullAvailPhys // (1024*1024))
    if hasattr(os,"sysconf"):
        return int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") // (1024*1024))
    raise OSError("cannot_measure_available_physical_memory")


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    os.replace(tmp,path)


def worker(*, root: Path):
    """A single subprocess consumes only its assigned sport/stat."""
    from precision_training_driver import execute
    started=time.monotonic()
    root=root.resolve()
    env=os.environ
    target=root/"reports/precision_training"/env.get("GITHUB_RUN_ID","manual")/env["FIT_ID"]
    target.mkdir(parents=True,exist_ok=True)
    status="failed"
    error=None
    try:
        execute("validate",root=root)
        execute("fit",root=root)
        manifest=target/"manifest.json"
        outcome=json.loads(manifest.read_text(encoding="utf-8"))
        if outcome.get("diagnostics",{}).get("posterior_sampling_ok") is not True:
            raise RuntimeError("FIT_DID_NOT_PASS_STRICT_CONVERGENCE")
        status="converged"
        return 0
    except BaseException as exc:
        status="failed"
        error=f"{type(exc).__name__}: {exc}"[:300]
        print(f"NHL_MODEL_FAILED stat={env.get('STAT')} reason={error}",flush=True)
        return 2
    finally:
        write_json(target/"model_receipt.json",{
            "schema":"precision_nhl_model_receipt_v1",
            "sport":"NHL","stat":env.get("STAT"),"fit_id":env["FIT_ID"],
            "status":status,"error":error,"elapsed_seconds":round(time.monotonic()-started),
            "model_version":"multisport-joint-bayes-v1",
            "strict_convergence_required":True,"all_historical_players":True,
            "as_of_exclusive":env.get("CUTOFF"),
            "source_branch_commit":env.get("SOURCE_HEAD"),
            "code_commit":env.get("GITHUB_SHA"),
            "finished_at_utc":datetime.now(timezone.utc).isoformat()
        })


def stream_output(stat: str, process, target: Path, queue: Queue):
    log=target/"training.log"
    try:
        with log.open("w",encoding="utf-8",errors="replace") as handle:
            for line in process.stdout:
                handle.write(line)
                handle.flush()
                queue.put((stat,line.rstrip()))
    finally:
        if process.stdout:
            process.stdout.close()


def summary(root: Path, run_id: str, statuses: dict, *, max_parallel: int):
    out=root/"reports/precision_training"/run_id
    models={}
    progress=0
    for stat in STATS:
        path=out/SLUGS[stat]/"progress.json"
        snapshot={}
        if path.is_file():
            try:
                snapshot=json.loads(path.read_text(encoding="utf-8"))
            except (OSError,ValueError):
                snapshot={"error":"UNREADABLE_PROGRESS_RECEIPT"}
        models[stat]={"status":statuses.get(stat,"pending"),
                      "progress_percent":snapshot.get("percent"),
                      "stage":snapshot.get("stage"),
                      "per_chain_iterations":snapshot.get("per_chain_iterations")}
        progress+=snapshot.get("percent",0) if isinstance(snapshot.get("percent"),(int,float)) else 0
        if statuses.get(stat)=="converged":
            progress+=max(0,100-(snapshot.get("percent") or 0))
    return {
        "schema":"precision_nhl_full_population_campaign_v1",
        "sport":"NHL","market_count":len(STATS),"completed_success":sum(statuses.get(s)=="converged" for s in STATS),
        "completed_failed":sum(statuses.get(s)=="failed" for s in STATS),
        "source_date_cutoff_exclusive":os.environ.get("CUTOFF"),
        "max_parallel_models":max_parallel,"chains_per_model":4,
        "max_parallel_cpu_chains":4*max_parallel,
        "ram_available_mb":memory_free_mb(),
        "models":models,"estimated_sampling_percent":round(progress/len(STATS),2),
        "status":"completed" if len(statuses)==len(STATS) else "running",
        "updated_utc":datetime.now(timezone.utc).isoformat()
    }


def campaign(root: Path, *, max_parallel: int =4,
             min_free_mb: int =8192, stagger_seconds: int=105):
    if not 1<=max_parallel<=4 or min_free_mb<4096 or stagger_seconds<0:
        raise ValueError("invalid_nhl_parallelism_or_memory_guard")
    root=root.resolve()
    run_id=os.environ.get("GITHUB_RUN_ID","manual")
    dest=root/"reports/precision_training"/run_id
    dest.mkdir(parents=True,exist_ok=True)
    statuses={}
    active={}
    thread_log=Queue()
    pending=list(STATS)
    last_start=-float("inf")
    last_report=-float("inf")
    critical_memory_since=None
    # If Windows doesn't have sufficient free RAM at startup, fail closed.
    start_memory=memory_free_mb()
    if start_memory<min_free_mb+2048:
        raise RuntimeError(f"NOT_ENOUGH_FREE_RAM_TO_START_NHL_TRAINING: {start_memory} MB")
    print(f"NHL_CAMPAIGN_STARTED markets={STATS} max_models={max_parallel} "
          f"chains_per_model=4 potential_parallel_chains={max_parallel*4} "
          f"memory_free_mb={start_memory} minimum_free_mb={min_free_mb}",flush=True)
    try:
        while pending or active:
            now=time.monotonic()
            try:
                available=memory_free_mb()
            except OSError:
                available=0
                print("MEMORY_MONITOR_ERROR: no new model will be started",flush=True)
            # Protect the laptop if four large PyMC models outgrow RAM.
            # Only the most recently started job is sacrificed; existing
            # completed or surviving models retain their separate receipts.
            if active and available>0 and available<4096:
                if critical_memory_since is None:
                    critical_memory_since=now
                    print(f"NHL_CRITICAL_RAM_WARNING available_mb={available} "
                          "stopping launch and waiting 45 seconds",flush=True)
                elif now-critical_memory_since>=45 and len(active)>1:
                    victim=max(active,key=lambda stat:active[stat][2])
                    victim_proc=active[victim][0]
                    print(f"NHL_RAM_SAFETY_STOP stat={victim} pid={victim_proc.pid} "
                          f"available_mb={available}",flush=True)
                    if sys.platform=="win32":
                        subprocess.run(["taskkill","/PID",str(victim_proc.pid),
                                        "/T","/F"],check=False,capture_output=True)
                    else:
                        victim_proc.terminate()
                    critical_memory_since=now
            else:
                critical_memory_since=None
            if (pending and len(active)<max_parallel and available>=min_free_mb+2048
                    and now-last_start>=stagger_seconds):
                stat=pending.pop(0)
                slug=SLUGS[stat]
                target=dest/slug
                target.mkdir(parents=True,exist_ok=True)
                env=os.environ.copy()
                env.update({
                    "SPORT":"NHL","STAT":stat,"FIT_ID":slug,
                    "MODE":"pregame_fit","TRAIN_FROM":"2018-10-01",
                    "HOLDOUT_UNTIL":env.get("CUTOFF","2026-10-29"),
                    "LINE":"2.5","MAX_PER_POSITION":"0","MAX_SEASONS":"12",
                    "PICKEM_NUTS_CHAINS":"4",
                    "PICKEM_NUTS_CORES":"4",
                    "PICKEM_STRICT_ALL_EFFECTS":"1",
                    "PICKEM_NUTS_DRAWS":env.get("PICKEM_NUTS_DRAWS","2000"),
                    "PICKEM_NUTS_TUNE":env.get("PICKEM_NUTS_TUNE","1800"),
                    "PYTHONUNBUFFERED":"1","PYTHONUTF8":"1",
                    "OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1",
                    "MKL_NUM_THREADS":"1",
                })
                proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"worker",
                                       "--root",str(root)],
                                      cwd=root,env=env,stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,text=True,
                                      encoding="utf-8",errors="replace",
                                      bufsize=1)
                thread=threading.Thread(target=stream_output,args=(stat,proc,target,thread_log),
                                        daemon=True)
                thread.start()
                active[stat]=(proc,thread,time.monotonic())
                statuses[stat]="running"
                last_start=now
                print(f"NHL_MODEL_STARTED stat={stat} pid={proc.pid} "
                      f"running_models={len(active)} free_ram_mb={available}",flush=True)
            while True:
                try:
                    stat,line=thread_log.get_nowait()
                except Empty:
                    break
                print(f"[{stat}] {line}",flush=True)
            for stat,(proc,thread,start) in list(active.items()):
                result=proc.poll()
                if result is None:
                    continue
                thread.join(timeout=2)
                del active[stat]
                report=dest/SLUGS[stat]/"model_receipt.json"
                try:
                    record=json.loads(report.read_text(encoding="utf-8"))
                    ok=(result==0 and record.get("status")=="converged")
                except (OSError,ValueError):
                    ok=False
                statuses[stat]="converged" if ok else "failed"
                print(f"NHL_MODEL_FINISHED stat={stat} success={ok} "
                      f"returncode={result} elapsed_seconds={round(time.monotonic()-start)}",
                      flush=True)
            if now-last_report>=60 or not pending and not active:
                report=summary(root,run_id,statuses,max_parallel=max_parallel)
                write_json(dest/"nhl_campaign.json",report)
                print(f"NHL_CAMPAIGN_PROGRESS finished={report['completed_success']+report['completed_failed']}/4 "
                      f"accepted={report['completed_success']} failed={report['completed_failed']} "
                      f"started={len(active)} queued={len(pending)} "
                      f"sampling={report['estimated_sampling_percent']:.1f}% "
                      f"free_ram_mb={report['ram_available_mb']}",flush=True)
                last_report=now
            if pending and not active and available<min_free_mb+2048:
                print("NHL_CAMPAIGN_HALTED insufficient available RAM to safely "
                      "start another full-population model",flush=True)
                for stat in pending:
                    statuses[stat]="blocked_low_memory"
                pending.clear()
            if pending or active:
                time.sleep(3)
    except KeyboardInterrupt:
        print("NHL_CAMPAIGN_INTERRUPTED: stopping model process parents",flush=True)
        for process,thread,_ in active.values():
            process.terminate()
        raise
    finally:
        write_json(dest/"nhl_campaign.json",summary(root,run_id,statuses,max_parallel=max_parallel))
    return 0 if all(statuses.get(s)=="converged" for s in STATS) else 2


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    run=sub.add_parser("run")
    run.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    run.add_argument("--max-parallel",type=int,default=4)
    run.add_argument("--min-free-mb",type=int,default=8192)
    run.add_argument("--stagger-seconds",type=int,default=105)
    worker_parser=sub.add_parser("worker")
    worker_parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    args=p.parse_args(argv)
    if args.mode=="worker":
        return worker(root=args.root)
    return campaign(args.root,max_parallel=args.max_parallel,
                    min_free_mb=args.min_free_mb,stagger_seconds=args.stagger_seconds)

if __name__=="__main__":
    raise SystemExit(main())
