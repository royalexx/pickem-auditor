#!/usr/bin/env python3
"""Resumable local-only NHL context/legacy campaign. No GitHub Actions required.

Run once with a versioned configuration; resume the same command after a source
timeout. Completed sampling outputs are verified and never silently retrained.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import nhl_context_data as store
import nhl_context_features as features
import nhl_context_train as life

REQUIRED={"schema","train_from","cutoff","until","pilot_games","history_window",
          "draws","tune","chains","cores","predictive_draws","line","market",
          "feature_set","policy","with_attempts","restore_history"}


def source_receipt(root):
    scripts=Path(root)/"scripts"
    source={p.name:life.file_hash(p) for p in sorted(scripts.glob("nhl_context_*.py"))}
    for name in ("joint_population_bayes.py","population_history.py","population_normalizers.py",
                 "historical_nhl_warehouse.py","history_warehouse_load.py"):
        source[name]=life.file_hash(scripts/name)
    return source


def rebind_before_sampling(root, run_dir, config):
    """Explicit dependency migration of an intact frozen, unsampled experiment.

    Only the orchestration script may differ; data/model/feature code must match.
    Keeps the frozen design, verifies all completed outputs, archives identities.
    Call while holding campaign_lock.
    """
    run=Path(run_dir).resolve();path=run/"status.json"
    old=life.load_json(path)
    if old.get("root")!=str(Path(root).resolve()) or old.get("config_digest")!=store.digest(config):
        raise ValueError("runtime_migration_requires_same_root_and_configuration")
    steps=old["steps"]
    if (steps.get("freeze",{}).get("status")!="completed" or
            set(steps)-{"restore_history","plan","freeze","fit_challenger"} or
            steps.get("fit_challenger",{}).get("status") not in (None,"failed","running")):
        raise ValueError("runtime_migration_requires_frozen_unsampled_experiment")
    for folder in (run/"challenger",run/"incumbent"):
        if folder.exists() and (list(folder.rglob("*.nc")) or list(folder.rglob("manifest.json"))):
            raise ValueError("runtime_migration_forbidden_with_sampling_outputs")
    previous_source=life.load_json(run/"code_receipt.json")
    current_source=source_receipt(root)
    if store.digest(previous_source)!=old["code_digest"]:
        raise ValueError("runtime_migration_code_receipt_tampered")
    changed={name for name in set(previous_source)|set(current_source)
             if previous_source.get(name)!=current_source.get(name)}
    if changed-{"nhl_context_campaign.py"}:
        raise ValueError("runtime_migration_model_or_data_code_changed")
    for step in steps.values():
        if step.get("status")=="completed":
            for output,checksum in step["outputs"].items():
                if not Path(output).is_file() or life.file_hash(output)!=checksum:
                    raise ValueError("runtime_migration_frozen_output_changed")
    provenance=life.code_provenance()
    archive=run/"runtime_migrations"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive.mkdir(parents=True)
    for name in ("status.json","code_receipt.json","fit_challenger.log"):
        if (run/name).is_file():shutil.copy2(run/name,archive/name)
    life.write_json(archive/"migration_receipt.json",{
        "reason":"explicit_dependency_install_before_first_saved_posterior",
        "previous_runtime_digest":old["runtime_digest"],"new_runtime":provenance,
        "changed_scripts":sorted(changed),"frozen_outputs_verified":True})
    updated={**old,"code_digest":store.digest(current_source),
             "runtime_digest":store.digest([provenance["python"],provenance["package_versions"]])}
    life.write_json(run/"code_receipt.json",current_source)
    life.write_json(path,updated)
    print("RUNTIME_MIGRATION_ARCHIVED "+str(archive),flush=True)


def restart_before_fit(root, run_dir, config):
    """Archive pre-fit receipts and re-plan after a code fix, preserving data.

    Never reuses a frozen design or a sampled posterior under different code.
    Call only while holding campaign_lock.
    """
    run=Path(run_dir).resolve();status=run/"status.json"
    if not status.exists():
        return
    old=life.load_json(status)
    if old.get("root")!=str(Path(root).resolve()) or old.get("config_digest")!=store.digest(config):
        raise ValueError("collection_restart_requires_same_root_and_configuration")
    if any((run/name).exists() for name in ("challenger","incumbent")) or set(old["steps"])-{"restore_history","plan"}:
        raise ValueError("collection_restart_forbidden_after_freeze_or_fit")
    for step in old["steps"].values():
        if step.get("status")=="completed":
            for path,checksum in step["outputs"].items():
                if not Path(path).is_file() or life.file_hash(path)!=checksum:
                    raise ValueError("collection_restart_output_changed")
    archive=run/"collection_restarts"/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive.mkdir(parents=True)
    for name in ("status.json","code_receipt.json","config.json","history_restore.json","collection_plan.json",
                 "game_ids.json","training_game_ids.json","collect.log","audit_collection.log","collection_audit.json"):
        if (run/name).is_file():shutil.copy2(run/name,archive/name)
    life.write_json(archive/"restart_receipt.json",{"reason":"explicit_pre_fit_restart_after_source_update",
                    "dataset_preserved":True,"new_code_provenance":life.code_provenance()})
    status.unlink()
    print("COLLECTION_RESTART_ARCHIVED "+str(archive),flush=True)


@contextmanager
def campaign_lock(run_dir):
    """OS lock releases on process death; two terminals cannot launch one fit."""
    path=Path(run_dir)
    path.mkdir(parents=True,exist_ok=True)
    with (path/"campaign.lock").open("a+b") as handle:
        if handle.tell()==0:handle.write(b"0");handle.flush()
        handle.seek(0)
        try:
            if os.name=="nt":
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError("campaign_already_running_in_this_directory") from exc
        try:yield
        finally:
            handle.seek(0)
            if os.name=="nt":msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)


def validate_config(config):
    if set(config)!=REQUIRED or config["schema"]!="nhl-context-campaign-v1":
        raise ValueError("invalid_campaign_configuration_fields")
    begin,cutoff,end=(store.instant(config[k]) for k in ("train_from","cutoff","until"))
    if not begin<cutoff<end<=datetime.now(timezone.utc):
        raise ValueError("invalid_or_future_campaign_windows")
    for key,lower,upper in (("pilot_games",0,100000),("history_window",20,100),
                            ("draws",100,10000),("tune",100,10000),("chains",4,8),
                            ("cores",1,8),("predictive_draws",100,100000)):
        v=config[key]
        if isinstance(v,bool) or not isinstance(v,int) or not lower<=v<=upper:
            raise ValueError("invalid_campaign_budget:"+key)
    if config["cores"]>config["chains"] or 0<config["pilot_games"]<2:
        raise ValueError("invalid_campaign_parallelism_or_cohort")
    if config["market"] not in features.MARKETS or config["feature_set"] not in ("base","context"):
        raise ValueError("campaign_requires_core_or_context_market")
    if config["policy"] not in ("recorded","retrospective_next_day"):
        raise ValueError("invalid_campaign_availability_policy")
    for k in ("with_attempts","restore_history"):
        if not isinstance(config[k],bool):
            raise ValueError("invalid_campaign_boolean:"+k)
    if config["market"]=="blocks" and config["feature_set"]=="context" and not config["with_attempts"]:
        raise ValueError("blocks_campaign_requires_attempt_collection")
    import math
    if isinstance(config["line"],bool) or not isinstance(config["line"],(int,float)) or not math.isfinite(config["line"]) or config["line"]<0:
        raise ValueError("invalid_campaign_research_line")
    return config


def collection_plan(rows,config):
    """Only collect target games plus their actual last-N team-game dependencies.

    The source warehouse supplies IDs/dates only, not fabricated team statistics.
    This bounded pilot avoids downloading every season before testing one model.
    It is complete against those source IDs, not an official-schedule certificate.
    """
    config=validate_config(config)
    info={}
    for r in rows:
        key=r["game_id"]
        candidate={"game_id":key,"start_time":r["game_date"]+"T00:00:00Z",
                   "game_date":r["game_date"],"season":r["season"],
                   "teams":sorted((r["team"],r["opponent"]))}
        if key in info and info[key]!=candidate:
            raise ValueError("inconsistent_history_game_metadata")
        info[key]=candidate
    begin,cutoff,end=(store.instant(config[k]).date().isoformat() for k in ("train_from","cutoff","until"))
    all_games=sorted(info.values(),key=lambda r:(r["game_date"],r["game_id"]))
    training=[r for r in all_games if begin<=r["game_date"]<cutoff]
    training=features.pilot_cohort(training,config["pilot_games"])
    future=[r for r in all_games if cutoff<=r["game_date"]<end]
    if not training or not future:
        raise ValueError("campaign_source_missing_training_or_holdout_games")
    seasons={r["season"] for r in training}
    if {r["season"] for r in future}-seasons and len(seasons)<2:
        raise ValueError("campaign_requires_multiseason_training_for_unseen_season")
    team_games=defaultdict(list)
    for r in all_games:
        for team in r["teams"]:
            team_games[team].append(r)
    dates={t:[r["game_date"] for r in games] for t,games in team_games.items()}
    dependencies=set()
    targets=training+future
    for r in targets:
        for team in r["teams"]:
            stop=bisect.bisect_left(dates[team],r["game_date"])
            if stop<5:
                raise ValueError("insufficient_source_warmup_for_planned_team:"+team)
            dependencies.update(p["game_id"] for p in team_games[team][max(0,stop-config["history_window"]):stop])
    training_ids=sorted(r["game_id"] for r in training)
    future_ids=sorted(r["game_id"] for r in future)
    target_ids=set(training_ids+future_ids)
    selected=target_ids|dependencies
    return {"schema":"nhl-context-bounded-collection-plan-v1","game_ids":sorted(selected),
            "training_game_ids":training_ids,"holdout_game_ids":future_ids,
            "context_only_game_ids":sorted(dependencies-target_ids),
            "training_seasons":sorted(seasons),"games_to_collect":len(selected),
            "history_window":config["history_window"],"maximum_http_requests":2*len(selected),
            "source_date_precision":"game_date_only_actual_times_checked_after_collection",
            "schedule_completeness_verified":False,"ranking_allowed":False}


class Campaign:
    def __init__(self,root,run_dir,config):
        self.root=Path(root).resolve()
        self.run=Path(run_dir).resolve()
        self.config=validate_config(config)
        self.run.mkdir(parents=True,exist_ok=True)
        self.status_path=self.run/"status.json"
        source=source_receipt(self.root)
        runtime=life.code_provenance()
        identity={"config_digest":store.digest(config),"code_digest":store.digest(source),"root":str(self.root),
                  "runtime_digest":store.digest([runtime["python"],runtime["package_versions"]])}
        if self.status_path.exists():
            self.status=life.load_json(self.status_path)
            if any(self.status.get(k)!=v for k,v in identity.items()):
                raise ValueError("campaign_config_or_code_changed_choose_new_run_directory")
        else:
            self.status={"schema":"nhl-context-campaign-status-v1",**identity,"steps":{},"ranking_allowed":False}
            life.write_json(self.run/"config.json",config)
            life.write_json(self.run/"code_receipt.json",source)
            life.write_json(self.status_path,self.status)

    def step(self,name,action,outputs):
        paths=[Path(p) for p in outputs]
        old=self.status["steps"].get(name,{})
        if old.get("status")=="completed":
            if any(not p.is_file() or life.file_hash(p)!=old["outputs"].get(str(p)) for p in paths):
                raise ValueError("completed_campaign_output_changed:"+name)
            print("RESUME_VERIFIED "+name,flush=True)
            return
        self.status["steps"][name]={"status":"running","started_at":datetime.now(timezone.utc).isoformat()}
        life.write_json(self.status_path,self.status)
        print("START_STAGE "+name,flush=True)
        try:
            action()
            if any(not p.is_file() for p in paths):
                raise ValueError("missing_campaign_stage_output:"+name)
        except BaseException as exc:
            self.status["steps"][name].update(status="failed",error=type(exc).__name__+":"+str(exc)[:400])
            life.write_json(self.status_path,self.status)
            raise
        self.status["steps"][name].update(status="completed",outputs={str(p):life.file_hash(p) for p in paths})
        life.write_json(self.status_path,self.status)

    def command(self,name,*args):
        """Separate processes release sampler memory between independent models."""
        log=self.run/(name+".log")
        command=[sys.executable,*map(str,args)]
        started=time.monotonic()
        with log.open("w",encoding="utf-8") as stream:
            with subprocess.Popen(command,cwd=self.root,stdout=stream,stderr=subprocess.STDOUT) as process:
                try:
                    while True:
                        try:
                            code=process.wait(timeout=30)
                            break
                        except subprocess.TimeoutExpired:
                            print(f"RUNNING {name} elapsed={time.monotonic()-started:.0f}s log={log}",flush=True)
                except BaseException:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill()
                    raise
        if code:
            tail="\n".join(log.read_text(encoding="utf-8",errors="replace").splitlines()[-40:])
            raise RuntimeError(f"stage_{name}_exit_{code}: inspect {log}\n{tail}")

    def prepare(self):
        if self.config["restore_history"]:
            dest=self.run/"history_restore.json"
            def restore():
                from history_warehouse_load import restore
                life.write_json(dest,restore(self.root))
            self.step("restore_history",restore,[dest])
        dest=self.run/"collection_plan.json"
        def plan():
            import population_history as history
            warmup=(store.instant(self.config["train_from"])-timedelta(days=180)).date().isoformat()
            rows=history.read(self.root,sport="NHL",stat="saves",after=warmup,
                   before=store.instant(self.config["until"]).date().isoformat(),max_seasons=None,min_records=1)
            report=collection_plan(rows,self.config)
            life.write_json(dest,report)
            life.write_json(self.run/"game_ids.json",report["game_ids"])
            life.write_json(self.run/"training_game_ids.json",report["training_game_ids"])
        self.step("plan",plan,[dest,self.run/"game_ids.json",self.run/"training_game_ids.json"])
        return life.load_json(dest)

    def execute(self):
        config=self.config
        self.command("check_environment","-c",
                     "import pymc, arviz, arviz_stats, h5netcdf, h5py; print('NUMERICAL_ENVIRONMENT_OK', pymc.__version__)")
        plan=self.prepare()
        print("COLLECTION_GAMES="+str(plan["games_to_collect"]),flush=True)
        dataset=self.run/"dataset"
        model=self.run/"challenger"
        legacy=self.run/"incumbent"
        args=["scripts/nhl_context_data.py","--root",dataset,"--game-ids",self.run/"game_ids.json"]
        if config["with_attempts"]:args.append("--with-attempts")
        # Even a completed collection is re-read/reconciled on resume. This
        # catches raw-source loss and valid-looking normalized-row tampering.
        self.command("collect",*args)
        audit=self.run/"collection_audit.json"
        self.command("audit_collection","scripts/nhl_context_train.py","audit-collection","--root",dataset,
                     "--expected-game-ids",self.run/"game_ids.json","--verify-raw","--out",audit)
        def freeze():
            self.command("freeze","scripts/nhl_context_train.py","freeze","--root",dataset,
                "--train-from",config["train_from"],"--cutoff",config["cutoff"],"--market",config["market"],
                "--feature-set",config["feature_set"],"--policy",config["policy"],"--out",model,
                "--pilot-games",config["pilot_games"],"--training-game-ids",self.run/"training_game_ids.json")
        frozen=[model/n for n in ("preflight.json","design.json","training_rows.json","frozen_bundles.json","frozen_xg.json")]
        self.step("freeze",freeze,frozen)
        budget=["--draws",config["draws"],"--tune",config["tune"],"--chains",config["chains"],"--cores",config["cores"]]
        self.step("fit_challenger",lambda:self.command("fit_challenger","scripts/nhl_context_train.py","fit","--folder",model,*budget),
                  [model/"manifest.json",model/"posterior.nc"])
        self.step("evaluate_challenger",lambda:self.command("evaluate_challenger","scripts/nhl_context_train.py","evaluate",
                   "--folder",model,"--until",config["until"],"--line",config["line"],"--draws",config["predictive_draws"]),
                  [model/"holdout_predictions.json",model/"holdout_report.json"])
        self.step("fit_incumbent",lambda:self.command("fit_incumbent","scripts/nhl_context_incumbent.py","fit",
                   "--challenger-dir",model,"--incumbent-dir",legacy,*budget),[legacy/"manifest.json",legacy/"posterior.nc",legacy/"design.json"])
        self.step("score_incumbent",lambda:self.command("score_incumbent","scripts/nhl_context_incumbent.py","score",
                   "--challenger-dir",model,"--incumbent-dir",legacy,"--draws",config["predictive_draws"]),[legacy/"holdout_predictions.json"])
        def compare():
            from nhl_context_evaluate import paired_comparison
            life.write_json(self.run/"comparison.json",paired_comparison(life.load_json(model/"holdout_predictions.json"),
                                                                       life.load_json(legacy/"holdout_predictions.json")))
        self.step("compare",compare,[self.run/"comparison.json"])
        summary={"schema":"nhl-context-campaign-summary-v1","status":"completed",
            "training_games":len(plan["training_game_ids"]),"collection_games":plan["games_to_collect"],
            "challenger_diagnostics":life.load_json(model/"manifest.json")["diagnostics"],
            "incumbent_diagnostics":life.load_json(legacy/"manifest.json")["diagnostics"],
            "comparison":life.load_json(self.run/"comparison.json"),"ranking_allowed":False,
            "schedule_completeness_verified":False,"automatic_promotion":False}
        life.write_json(self.run/"summary.json",summary)
        paths=[self.run/n for n in ("config.json","code_receipt.json","status.json","history_restore.json",
                                   "collection_plan.json","collection_audit.json","comparison.json","summary.json")]
        paths += [folder/n for folder in (model,legacy) for n in ("manifest.json","preflight.json","holdout_report.json","holdout_predictions.json")]
        with zipfile.ZipFile(self.run/"review_packet.zip","w",zipfile.ZIP_DEFLATED) as packet:
            for path in paths:
                if path.is_file():packet.write(path,path.relative_to(self.run))
        print("REVIEW_PACKET="+str(self.run/"review_packet.zip"),flush=True)
        return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage",choices=("plan","run","status"))
    p.add_argument("--config",type=Path,default=store.ROOT/"config/nhl_context_pilot.json")
    p.add_argument("--run-dir",type=Path,default=store.ROOT/"reports/nhl_context_pilot_v2")
    p.add_argument("--root",type=Path,default=store.ROOT)
    p.add_argument("--restart-before-fit",action="store_true",
                   help="Archive pre-fit receipts and recompute the plan after code updates; preserve collected data")
    p.add_argument("--rebind-before-sampling",action="store_true",
                   help="Adopt installed dependencies for a hash-verified frozen experiment without any posterior")
    a=p.parse_args(argv)
    if a.rebind_before_sampling and (a.restart_before_fit or a.stage!="run"):
        p.error("--rebind-before-sampling requires run and cannot be combined with --restart-before-fit")
    # Configure BLAS before the subprocesses import any numerical libraries.
    for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
        os.environ[key]="1"
    if os.name=="nt":
        compiler=Path(r"C:\msys64\ucrt64\bin")
        if compiler.is_dir():os.environ["PATH"]=str(compiler)+os.pathsep+os.environ.get("PATH","")
    if a.stage=="status":
        result=life.load_json(a.run_dir/"status.json")
    else:
        with campaign_lock(a.run_dir):
            if a.rebind_before_sampling:
                rebind_before_sampling(a.root,a.run_dir,life.load_json(a.config))
            if a.restart_before_fit:
                restart_before_fit(a.root,a.run_dir,life.load_json(a.config))
            campaign=Campaign(a.root,a.run_dir,life.load_json(a.config))
            result=campaign.prepare() if a.stage=="plan" else campaign.execute()
    print(json.dumps(result,sort_keys=True,allow_nan=False),flush=True)
    return 0


if __name__=="__main__":raise SystemExit(main())
